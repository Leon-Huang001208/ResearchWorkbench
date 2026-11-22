"""Reviewed dataset bindings between DataHub and the independently authorized store.

Bindings are trusted host adapters, never executable declarations supplied by a
browser or plugin. No calendar, units or publication time is inferred here.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from core.observability import get_logger

from ..market_store import (
    Batch,
    DatasetIdentity,
    MarketStoreError,
    MarketStoreService,
    ReadResult,
    StoreScope,
)
from ..market_store.models import parse_batch
from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, Result

log = get_logger(__name__)


@dataclass(frozen=True)
class WarehouseBinding:
    actor: str
    scope: StoreScope
    dataset: DatasetIdentity
    expected_dates: tuple[date, ...]
    normalize: Callable[[Result, ReadResult], Batch | None]
    source_url: str = ""
    render: Callable[[Batch], list[dict]] | None = None
    field_metadata: dict | None = None
    source_metadata: Callable[[Batch], dict] | None = None


class WarehouseBridge:
    def __init__(self, service: MarketStoreService, binding: Callable):
        if not callable(binding):
            raise MarketStoreError("warehouse_binding_required")
        self.service, self.binding = service, binding

    def _context(self, query, source, configuration_digest):
        context = self.binding(query, source, configuration_digest)
        if context is None:
            return None
        if (
            not isinstance(context, WarehouseBinding)
            or context.scope.source != source
            or context.scope.config_digest != configuration_digest
            or context.dataset.capability != query.capability
            or (
                query.parameters.get("asset") is not None
                and context.dataset.asset != query.parameters["asset"]
            )
        ):
            log.warning("datahub_warehouse_binding_rejected", source=source)
            raise MarketStoreError("warehouse_binding_mismatch")
        return context

    @staticmethod
    def _window(query):
        parameters = query.parameters
        if parameters.get("start_date") and parameters.get("end_date"):
            start, end = date.fromisoformat(parameters["start_date"]), date.fromisoformat(
                parameters["end_date"]
            )
        elif parameters.get("periods"):
            periods = tuple(date.fromisoformat(value) for value in parameters["periods"])
            start, end = min(periods), max(periods)
        else:
            return None
        if start > end:
            raise MarketStoreError("invalid_date_range")
        return start, end

    def missing_queries(self, query: BusinessQuery, source: str, configuration_digest: str):
        """Plan raw daily gaps from the authoritative calendar, never a max-date watermark.

        Refresh explicitly re-fetches the requested window to discover revisions.
        Excessively fragmented gaps collapse to one bounded range rather than
        generating an unbounded number of vendor calls.
        """
        if (
            query.refresh
            or query.as_of is not None
            or query.capability != "market_bars"
            or query.parameters.get("adjustment") != "none"
            or query.parameters.get("frequency") not in {"daily", "day", "1d"}
        ):
            return None
        context = self._context(query, source, configuration_digest)
        window = self._window(query)
        if context is None or window is None or not context.expected_dates:
            return None
        expected = tuple(sorted(context.expected_dates))
        if any(not window[0] <= day <= window[1] for day in expected):
            raise MarketStoreError("warehouse_calendar_outside_request")
        gaps = set(self.service.find_gaps(context.actor, context.scope, context.dataset, expected))
        ranges: list[tuple[date, date]] = []
        start = end = None
        for day in expected:
            if day in gaps:
                start = day if start is None else start
                end = day
            elif start is not None:
                assert end is not None
                ranges.append((start, end))
                start = end = None
        if start is not None:
            assert end is not None
            ranges.append((start, end))
        if len(ranges) > 16:
            ranges = [(min(gaps), max(gaps))]
        return tuple(
            query.model_copy(
                update={
                    "source": source,
                    "allow_fallback": False,
                    "parameters": {
                        **query.parameters,
                        "start_date": start.isoformat(),
                        "end_date": end.isoformat(),
                    },
                }
            )
            for start, end in ranges
        )

    def read(self, query: BusinessQuery, source: str, configuration_digest: str) -> Result | None:
        context = self._context(query, source, configuration_digest)
        window = self._window(query)
        if context is None or window is None or not context.expected_dates:
            return None
        start, end = window
        if any(not start <= value <= end for value in context.expected_dates):
            raise MarketStoreError("warehouse_calendar_outside_request")
        gaps = self.service.find_gaps(
            context.actor, context.scope, context.dataset, context.expected_dates, as_of=query.as_of
        )
        if gaps:
            return None
        frozen = self.service.freeze(
            context.actor, context.scope, context.dataset, start, end, as_of=query.as_of
        )
        if len(frozen.payload) > MAX_QUERY_BYTES:
            raise MarketStoreError("warehouse_window_too_large")
        document = json.loads(frozen.payload)
        if query.as_of is not None and not document["pit_complete"]:
            return None
        batch = parse_batch(document["batch"])
        grouped: dict[tuple, dict] = {}
        for fact in batch.facts:
            key = (fact.business_date, fact.period, fact.dimensions)
            row = grouped.setdefault(
                key,
                {
                    "date": fact.business_date.isoformat(),
                    "period": fact.period,
                    **dict(fact.dimensions),
                },
            )
            row[fact.metric] = fact.value
        rows = [grouped[key] for key in sorted(grouped)]
        if context.render is not None:
            rows = context.render(batch)
        if query.capability == "market_bars":
            for row in rows:
                if row.get("asset", context.dataset.asset) != context.dataset.asset:
                    raise MarketStoreError("warehouse_fact_identity_mismatch")
                row["asset"] = context.dataset.asset
                if context.render is None and "adjustment" in query.parameters:
                    row.setdefault("adjustment", query.parameters["adjustment"])
        log.info("datahub_warehouse_hit", source=source, rows=len(rows))
        return Result(
            rows=rows,
            raw=[frozen.export()],
            source_url=context.source_url,
            status="complete" if rows else "empty",
            provider_total=len(rows),
            pagination_complete=True,
            provider_id=source,
            fields=context.field_metadata
            or {metric: {"unit": context.dataset.units} for metric in context.dataset.metrics},
            as_of=query.as_of.isoformat() if query.as_of else None,
            metadata={
                **(context.source_metadata(batch) if context.source_metadata else {}),
                "warehouse_hit": True,
                "warehouse_snapshot_sha256": frozen.digest,
                "warehouse_scope_digest": context.scope.key,
                "warehouse_semantics_digest": context.dataset.semantic_digest,
                "quality_accepted": True,
                "historical_point_in_time": query.as_of is not None,
            },
        )

    def ingest(
        self, query: BusinessQuery, source: str, configuration_digest: str, result: Result
    ) -> str | None:
        context = self._context(query, source, configuration_digest)
        window = self._window(query)
        if context is None or window is None or result.status not in {"complete", "snapshot"}:
            return None
        previous = self.service.read_range(context.actor, context.scope, context.dataset, *window)
        try:
            batch = context.normalize(result, previous)
        except MarketStoreError:
            raise
        except (TypeError, ValueError, KeyError) as exc:
            log.warning("datahub_warehouse_normalization_failed", error_type=type(exc).__name__)
            raise MarketStoreError("warehouse_normalization_failed") from None
        if batch is None:
            return self.service.version(context.actor, context.scope, context.dataset)
        if any(not window[0] <= fact.business_date <= window[1] for fact in batch.facts):
            raise MarketStoreError("warehouse_fact_outside_request")
        version = self.service.commit_batch(context.actor, context.scope, context.dataset, batch)
        log.info("datahub_warehouse_ingested", source=source, facts=len(batch.facts))
        return version
