"""Reconstruct overlay activity from a trusted versioned calendar and events."""

from dataclasses import dataclass

from core.observability import get_logger

from .contracts import OverlayContext, qualified_receipts
from .engine import digest, stamp
from .profiles import PROFILE_VERSION

log = get_logger(__name__)


@dataclass(frozen=True)
class OverlayApplicability:
    index_id: str
    as_of: str
    report_sha256: str
    rules_digest: str
    source_version: str
    source_refs_sha256: str
    context_sha256: str
    event_versions: tuple[tuple[str, int], ...]
    window_start: str | None
    window_end: str | None


def applicability_for(context, report, spec, index_id, as_of):
    from ..event_studies.calendars import (
        FAMILIES,
        calendar_knowledge_gaps,
        calendar_windows,
        event_windows,
    )
    from ..event_studies.contracts import Calendar, rule_contract
    from ..event_studies.events import forecast_window_gaps
    from ..event_studies.registry import INDICES

    if not isinstance(context, OverlayContext) or not isinstance(context.calendar, Calendar):
        raise TypeError("overlay_context_required")
    cutoff = stamp(as_of)
    if (
        context.index_id != index_id
        or stamp(context.as_of) != cutoff
        or not qualified_receipts(context)
    ):
        raise ValueError("overlay_context_binding_invalid")
    if (
        not isinstance(context.events, tuple)
        or not isinstance(context.holidays, tuple)
        or len(context.events) > 200
        or len(context.holidays) > 200
    ):
        raise ValueError("overlay_context_events_invalid")
    if context.calendar.exchange != INDICES[index_id]["exchange"]:
        raise ValueError("overlay_calendar_identity_mismatch")
    if not isinstance(context.source_version, str) or not 1 <= len(context.source_version) <= 128:
        raise ValueError("overlay_source_version_required")
    if not isinstance(spec, dict) or not isinstance(report, dict):
        raise TypeError("overlay_frozen_spec_required")
    required = ("role", "family", "direction", "rule", "index_id", "horizon", "profile_version")
    if (
        any(spec.get(key) != report.get(key) for key in required)
        or spec.get("index_id") != index_id
        or spec.get("horizon") != 20
        or spec.get("profile_version") != PROFILE_VERSION
    ):
        raise ValueError("overlay_spec_report_mismatch")
    family, rule = spec.get("family"), spec.get("rule")
    if family not in FAMILIES or rule not in FAMILIES[family]:
        raise ValueError("overlay_exact_window_rule_required")
    rules_digest = digest(
        rule_contract(spec["role"], PROFILE_VERSION, family, spec["direction"], rule)
    )
    if (
        report.get("rules_digest") != rules_digest
        or report.get("signal_rule_sha256") != rules_digest
    ):
        raise ValueError("overlay_frozen_rule_changed")
    candidates, versions = [], []
    for event in context.events if spec["role"] == "event_overlay" else context.holidays:
        if not isinstance(event, dict):
            raise TypeError("overlay_event_invalid")
        try:
            known = stamp(event.get("known_at"))
        except (TypeError, ValueError):
            continue
        if known > cutoff or event.get("lifecycle") in {"cancelled", "scenario"}:
            continue
        if spec["role"] == "event_overlay":
            if type(event.get("revision")) is not int or event["revision"] < 1:
                raise ValueError("overlay_event_version_required")
            versions.append((event.get("id"), event["revision"]))
        candidates.append(event)
    windows = (
        event_windows(context.calendar, candidates)
        if spec["role"] == "event_overlay"
        else calendar_windows(context.calendar, candidates)
    )
    sessions = {session.day.isoformat(): session for session in context.calendar.sessions}
    bounds = []
    for window in windows:
        if window["rule"] != rule:
            continue
        if calendar_knowledge_gaps(context.calendar, window, cutoff):
            continue
        if forecast_window_gaps(
            context.calendar,
            window,
            events=candidates,
            deterministic_calendar=spec["role"] == "calendar_overlay",
        ):
            continue
        first, last = sessions[window["start"]], sessions[window["end"]]
        # A close-to-open reopening gap ends at the actual reopening open.
        end = last.opens if window["end_price"] == "open" else last.closes
        bounds.append((first.closes, end))
    bounds.sort()
    active = next(((start, end) for start, end in bounds if start <= cutoff < end), None)
    log.info(
        "market_overlay_window_resolved",
        index_id=index_id,
        family=family,
        active_window_count=int(active is not None),
    )
    return OverlayApplicability(
        index_id=index_id,
        as_of=as_of,
        report_sha256=digest(report),
        rules_digest=rules_digest,
        source_version=context.source_version,
        source_refs_sha256=digest(context.source_refs),
        context_sha256=digest(
            {
                "calendar": context.calendar.model_dump(mode="json"),
                "events": candidates,
                "source_version": context.source_version,
            }
        ),
        event_versions=tuple(sorted(versions)),
        window_start=active[0].isoformat() if active else None,
        window_end=active[1].isoformat() if active else None,
    )


def applicability_reasons(proof, report, index_id, as_of):
    if not isinstance(proof, OverlayApplicability):
        return ["overlay_applicability_required"]
    if (
        proof.index_id != index_id
        or stamp(proof.as_of) != stamp(as_of)
        or proof.report_sha256 != digest(report)
        or proof.rules_digest != report.get("rules_digest")
    ):
        return ["overlay_applicability_binding_mismatch"]
    if not proof.window_start or not proof.window_end:
        return ["overlay_outside_active_window"]
    if not stamp(proof.window_start) <= stamp(as_of) < stamp(proof.window_end):
        return ["overlay_outside_active_window"]
    return []
