"""Warehouse-first planning: decide what to read locally and what to fetch.

Pure functions only. No provider, network, clock or credential access, so the
planner can be unit tested with plain in-memory callables and the same input
always produces the same plan.

The algorithm is extracted from the reviewed implementation in
``datahub/warehouse.py`` (``missing_queries``) rather than rewritten: that code
already computed gaps against an authoritative calendar, merged contiguous days
and folded excessive fragmentation into one bounded range. The difference here
is that the decision is available *before* a source is selected.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from core.observability import get_logger

from ..market_store import CoverageProof
from .contracts import BusinessQuery

log = get_logger(__name__)
PLAN_VERSION = "plan-v2"
MAX_SEGMENTS = 16
PLANNABLE_FREQUENCIES = frozenset({"daily", "day", "1d"})

# Capabilities whose warehouse rows are addressed by a date window.
#
# Only ``market_bars`` qualifies. The 2026-11-27 audit explains why the others
# cannot simply be added here:
#
# * ``financials`` and ``market_activity`` are already warehouse-backed, but via
#   ``research_snapshot_store.SnapshotSeries``: they ingest one frozen
#   projection and serve it only when the caller asks for ``display`` with
#   ``allow_stale``. That path never calls ``find_gaps``, so there is no
#   per-date gap list for the planner to produce. Moving them onto this planner
#   is new work, not a rename.
# * ``market_snapshot`` stores a single point-in-time row per dataset, so a
#   date-range gap is undefined.
# * ``search_assets`` / ``trading_calendar`` carry no dataset row to diff.
#
# ``DataHub._can_plan_wind_gaps`` holds a third, deliberately narrower gate
# (``source in {auto, wind}`` plus ``asset_type == stock``) because only trusted
# wind raw bars may defer the original span cap. Widening this set alone would
# not widen planning; that gate would still refuse.
PLANNABLE_CAPABILITIES = frozenset({"market_bars"})


@dataclass(frozen=True, order=True)
class Segment:
    """Inclusive calendar-day range."""

    start: date
    end: date

    def __post_init__(self) -> None:
        if self.start > self.end:
            raise ValueError("segment_start_after_end")

    def as_parameter_updates(self) -> dict[str, str]:
        return {"start_date": self.start.isoformat(), "end_date": self.end.isoformat()}

    def as_manifest(self) -> list[str]:
        return [self.start.isoformat(), self.end.isoformat()]


@dataclass(frozen=True)
class Plan:
    """What the warehouse already covers and what still needs a supplier."""

    hits: tuple[Segment, ...] = ()
    gaps: tuple[Segment, ...] = ()
    proofs: tuple[CoverageProof, ...] = ()
    expected_days: int = 0
    covered_days: int = 0
    gap_days: int = 0
    folded: bool = False
    version: str = PLAN_VERSION

    @property
    def complete(self) -> bool:
        return not self.gaps

    def manifest(self) -> dict:
        """Bounded summary for the snapshot manifest; never the full hit list."""
        return {
            "version": self.version,
            "expected_days": self.expected_days,
            "covered_days": self.covered_days,
            "gap_days": self.gap_days,
            "gap_segments": [segment.as_manifest() for segment in self.gaps],
            "folded": self.folded,
        }


def plannable(query: BusinessQuery) -> bool:
    """Whether a request may consult the warehouse before choosing a source.

    Mirrors the reviewed ``_can_plan_wind_gaps`` predicate but deliberately does
    not constrain ``source``: an explicitly chosen source must also be able to
    hit the warehouse first instead of always calling the vendor.

    This is the single place that decides plannability. ``warehouse`` must not
    restate the same conditions, or the two drift and a capability silently
    loses (or gains) planning without any test noticing.
    """

    parameters = query.parameters
    if query.refresh or query.as_of is not None:
        return False
    if query.capability not in PLANNABLE_CAPABILITIES:
        return False
    if query.capability == "market_bars":
        # Bars additionally require a raw, unadjusted, daily series. The old
        # warehouse predicate did not look at ``asset_type``; keeping that
        # unchanged avoids silently narrowing planning for index/etf bars.
        return (
            parameters.get("frequency") in PLANNABLE_FREQUENCIES
            and parameters.get("adjustment") == "none"
        )
    return True


def merge_days(days: Iterable[date], *, max_segments: int = MAX_SEGMENTS) -> tuple[Segment, ...]:
    """Merge sorted business days into contiguous calendar-day segments.

    Contiguity is calendar based, not trading-day based: suppliers take a
    ``start_date``/``end_date`` pair and skip holidays themselves, so one range
    spanning a weekend saves a call. Excessively fragmented gaps collapse to a
    single bounded range, matching the reviewed warehouse behaviour.
    """

    if max_segments < 1:
        raise ValueError("max_segments_invalid")
    ordered = tuple(sorted(set(days)))
    if not ordered:
        return ()
    ranges: list[Segment] = []
    start = end = ordered[0]
    for day in ordered[1:]:
        if day == end + timedelta(days=1):
            end = day
            continue
        ranges.append(Segment(start, end))
        start = end = day
    ranges.append(Segment(start, end))
    if len(ranges) > max_segments:
        return (Segment(ordered[0], ordered[-1]),)
    return tuple(ranges)


def plan(
    query: BusinessQuery,
    *,
    expected_dates: tuple[date, ...],
    find_gaps: Callable[[tuple[date, ...]], Iterable[date]],
    proofs: tuple[CoverageProof, ...] = (),
    max_segments: int = MAX_SEGMENTS,
) -> Plan | None:
    """Build a plan, or return ``None`` when this request is not plannable.

    ``None`` keeps the existing direct-fetch path for requests that must never
    be served from the warehouse (explicit refresh, point-in-time reads, other
    capabilities). Callers must treat ``None`` as "unchanged behaviour".
    """

    if not plannable(query):
        return None
    expected = tuple(sorted(set(expected_dates)))
    if not expected:
        return None
    missing = tuple(sorted(set(find_gaps(expected))))
    if any(day not in expected for day in missing):
        # A gap outside the requested window would silently widen the fetch.
        raise ValueError("gap_outside_expected_dates")
    covered = tuple(day for day in expected if day not in set(missing))
    raw_gaps = merge_gaps(expected, missing, max_segments=len(missing) or 1)
    gaps = merge_gaps(expected, missing, max_segments=max_segments)
    hits = merge_gaps(expected, covered, max_segments=max(len(covered), 1))
    return Plan(
        hits=hits,
        gaps=gaps,
        proofs=tuple(sorted(proofs, key=lambda proof: proof.business_date)),
        expected_days=len(expected),
        covered_days=len(covered),
        gap_days=len(missing),
        # Folded means fragmentation exceeded the threshold and was collapsed.
        folded=bool(missing) and len(gaps) < len(raw_gaps),
    )


def merge_gaps(expected_dates, missing_dates, *, max_segments=MAX_SEGMENTS):
    """Merge adjacent trading days, preserving covered days as boundaries."""
    if max_segments < 1:
        raise ValueError("max_segments_invalid")
    expected = tuple(sorted(set(expected_dates)))
    missing = set(missing_dates)
    if missing.difference(expected):
        log.warning("datahub_plan_invalid", code="gap_outside_expected_dates")
        raise ValueError("gap_outside_expected_dates")
    ranges = []
    start = end = None
    for day in expected:
        if day in missing:
            start = day if start is None else start
            end = day
        elif start is not None:
            ranges.append(Segment(start, end))
            start = end = None
    if start is not None:
        ranges.append(Segment(start, end))
    if len(ranges) > max_segments:
        return (Segment(min(missing), max(missing)),)
    return tuple(ranges)


def plan_queries(query: BusinessQuery, plan_result: Plan, source: str) -> tuple[BusinessQuery, ...]:
    """Turn gap segments into source-bound queries, one per segment."""

    if plan_result.complete:
        return ()
    if not isinstance(source, str) or not source:
        raise ValueError("source_required")
    segments = []
    for segment in plan_result.gaps:
        start = segment.start
        while start <= segment.end:
            end = min(segment.end, start + timedelta(days=59)) if source == "wind" else segment.end
            segments.append(Segment(start, end))
            start = end + timedelta(days=1)
    return tuple(
        query.model_copy(
            update={
                "source": source,
                "allow_fallback": False,
                "parameters": {**query.parameters, **segment.as_parameter_updates()},
            }
        )
        for segment in segments
    )
