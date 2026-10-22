"""Source-qualified native responses captured for reproducible research, not PIT bars."""

from __future__ import annotations

import base64
import json
from datetime import UTC, date, datetime, timedelta
from threading import RLock
from uuid import uuid4

from core.observability import get_logger

from ..market_store import Batch, DatasetIdentity, Fact, MarketStoreError, RawOriginal
from ..market_store.models import canonical, digest, parse_batch
from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, Result

log = get_logger(__name__)
CAPABILITIES = frozenset(
    {"financials", "market_activity", "factor_macro", "fund_data", "index_data"}
)
SOURCES = frozenset(
    {
        "akshare",
        "baostock",
        "wind",
        "tinysoft",
        "eastmoney_fund",
        "fund_nav",
        "fund_profile",
        "fund_distributions",
        "fund_holdings",
    }
)
# Named public numeric endpoints only. Calendars, news and credential endpoints excluded.
PUBLIC_NUMERIC = frozenset(
    {
        ("ext_fred", "series"),
        ("ext_bls", "series"),
        ("ext_worldbank", "inflation"),
        ("ext_ths", "cmd_history_quotation"),
        ("ext_ths", "basic_data_service"),
        ("ext_ths", "real_time_quotation"),
    }
)
METADATA_KEYS = frozenset(
    {
        "upstream_id",
        "provider_semantics_revision",
        "adjustment_contract",
        "field_dictionary_evidence",
        "schema_version",
        "units",
        "currency",
        "accounting_standard",
        "consolidation",
        "revision_policy",
    }
)
RESULT_KEYS = (
    "rows",
    "fields",
    "source_url",
    "status",
    "pages_fetched",
    "provider_total",
    "pagination_complete",
    "limitations",
    "missing",
    "duplicates",
    "as_of",
    "provider_id",
)
# Storage slot for one exact query; never a report, release or observation date.
# All observations are revisions of this one logical fact, projected by cutoff.
START = date(1970, 1, 1)
NAV_SEMANTIC_GAPS = frozenset(
    {"adjusted_total_return", "benchmark_timeseries", "verified_currency"}
)


def _bounded_nav_capture(query, result, source):
    """Admit disclosed NAV semantics gaps only for a complete, narrow source response."""
    if (
        source != "eastmoney_fund"
        or result.provider_id != source
        or query.capability != "fund_data"
        or query.parameters.get("dataset") not in {"nav", "fund_nav"}
        or result.status != "complete"
        or result.pagination_complete is not True
        or not set(result.missing) <= NAV_SEMANTIC_GAPS
    ):
        return False
    try:
        start, end = (
            date.fromisoformat(query.parameters[name]) for name in ("start_date", "end_date")
        )
    except (KeyError, TypeError, ValueError):
        return False
    return 0 <= (end - start).days <= 30


class SnapshotSeries:
    """Trusted Host adapter; actor/scope/schema/units must never come from a browser.

    ``schema_identity`` and ``units_identity`` name the reviewed provider contract,
    not a claim that unknown units or historical releases have been verified.
    Host must serialize ingestion for the same series across adapter instances.
    """

    def __init__(
        self,
        service,
        actor,
        scope,
        *,
        schema_identity="provider-native-v1",
        units_identity="provider-defined-unknown",
        display_ttl_seconds=300,
    ):
        if (
            not isinstance(schema_identity, str)
            or not schema_identity
            or not isinstance(units_identity, str)
            or not units_identity
        ):
            raise MarketStoreError("snapshot_contract_required")
        if type(display_ttl_seconds) is not int or not 1 <= display_ttl_seconds <= 3600:
            raise MarketStoreError("snapshot_ttl_invalid")
        self.service, self.actor, self.scope = service, actor, scope
        self.schema_identity, self.units_identity = schema_identity, units_identity
        self.display_ttl = timedelta(seconds=display_ttl_seconds)
        self._lock = RLock()

    def _now(self):
        return datetime.now(UTC)

    def dataset(self, query: BusinessQuery) -> DatasetIdentity | None:
        """Construct identity from all business parameters and reviewed source contract."""
        if query.required_semantics is not None:
            # Native captures retain unverified fields and never satisfy the
            # canonical raw-price contract, including historical cache reads.
            return None
        if query.source not in {"auto", self.scope.source}:
            raise MarketStoreError("snapshot_source_mismatch")
        accepted = query.capability in CAPABILITIES and self.scope.source in SOURCES
        accepted |= (
            query.capability == "market_bars"
            and (
                query.parameters.get("asset_type") in {"etf", "index"}
                or (
                    self.scope.source == "tinysoft"
                    and query.parameters.get("asset_type", "stock") == "stock"
                )
            )
            and self.scope.source in SOURCES
        )
        accepted |= (
            query.capability == "external_data"
            and (self.scope.source, query.parameters.get("dataset")) in PUBLIC_NUMERIC
        )
        if not accepted:
            return None
        if query.purpose == "backtest":
            raise MarketStoreError("snapshot_formal_backtest_unavailable")
        identity = {
            "format": "provider_native_snapshot-v1",
            "source": self.scope.source,
            "capability": query.capability,
            "parameters": query.parameters,
            "schema_identity": self.schema_identity,
            "units_identity": self.units_identity,
        }
        semantic = digest(canonical(identity))
        # Arbitrary native asset/series names remain in the hashed complete identity.
        return DatasetIdentity(
            query.capability,
            "query-" + semantic,
            "provider-native",
            "observed",
            "provider-native",
            "native",
            "unverified",
            semantic,
            ("snapshot",),
        )

    def _facts(self, dataset, cutoff):
        facts = self.service.read_range(
            self.actor, self.scope, dataset, START, START, as_of=cutoff
        ).facts
        if len(facts) > 1 or any(
            fact.logical_key != (START, "snapshot", "first-observed", ()) for fact in facts
        ):
            raise MarketStoreError("snapshot_projection_invalid")
        return facts

    def ingest(self, query: BusinessQuery, result: Result) -> str | None:
        dataset = self.dataset(query)
        if dataset is None:
            return None
        with self._lock:
            # Even rejected/empty outcomes recheck current read entitlement.
            previous = self._facts(dataset, None)
            if query.as_of is not None or result.status not in {"complete", "snapshot", "empty"}:
                log.info("research_snapshot_not_ingested", reason="historical_or_incomplete")
                return None
            if result.provider_id not in {None, self.scope.source} or (
                result.missing and not _bounded_nav_capture(query, result, self.scope.source)
            ):
                raise MarketStoreError("snapshot_provider_or_completeness_mismatch")
            if result.status == "empty" and result.rows:
                raise MarketStoreError("snapshot_empty_status_mismatch")
            if not result.raw or any(not isinstance(raw, bytes) for raw in result.raw):
                raise MarketStoreError("snapshot_original_required")
            document = {key: getattr(result, key) for key in RESULT_KEYS}
            document["metadata"] = {
                key: value for key, value in result.metadata.items() if key in METADATA_KEYS
            }
            document["provider_id"] = self.scope.source
            document["format"] = "provider_native_snapshot-v1"
            document["payloads"] = [
                {"sha256": digest(raw), "base64": base64.b64encode(raw).decode("ascii")}
                for raw in result.raw
            ]
            content = canonical(document)
            if len(content) > MAX_QUERY_BYTES:
                raise MarketStoreError("snapshot_response_limit")
            raw = RawOriginal(content)
            latest = previous[0] if previous else None
            if latest is not None and latest.raw_hash == raw.sha256:
                return self.service.version(self.actor, self.scope, dataset)
            observed = self._now()
            if latest is not None and observed <= latest.ingested_at:
                raise MarketStoreError("snapshot_clock_not_advanced")
            capture_id = uuid4().hex
            value = {
                "response_sha256": raw.sha256,
                "observed_at": observed.isoformat(),
                "availability_basis": "first_observed",
                "formal_backtest_eligible": False,
                "provider_schema_sha256": digest(canonical(result.fields)),
            }
            fact = Fact(
                "snapshot",
                START,
                "first-observed",
                canonical(value).decode(),
                observed,
                observed,
                capture_id,
                raw.sha256,
            )
            version = self.service.commit_batch(
                self.actor, self.scope, dataset, Batch((fact,), (raw,))
            )
            log.info("research_snapshot_ingested", rows=len(result.rows), empty=not result.rows)
            return version

    def read(self, query: BusinessQuery) -> Result | None:
        dataset = self.dataset(query)
        if dataset is None:
            return None
        facts = self._facts(dataset, query.as_of)
        # Latest strict research always fetches upstream; elapsed TTL is no proof of freshness.
        if query.refresh or (
            query.as_of is None and (query.purpose != "display" or query.quality != "allow_stale")
        ):
            return None
        if not facts:
            return None
        selected = facts[0]
        if query.as_of is None and self._now() - selected.ingested_at > self.display_ttl:
            return None
        frozen = self.service.freeze(
            self.actor, self.scope, dataset, START, START, as_of=query.as_of
        )
        if len(frozen.payload) > MAX_QUERY_BYTES:
            raise MarketStoreError("snapshot_response_limit")
        batch = parse_batch(json.loads(frozen.payload)["batch"])
        # Choose from the frozen read itself so a concurrent writer cannot mix reads.
        if len(batch.facts) != 1 or batch.facts[0].logical_key != (
            START,
            "snapshot",
            "first-observed",
            (),
        ):
            raise MarketStoreError("snapshot_projection_invalid")
        selected = batch.facts[0]
        if query.as_of is None and self._now() - selected.ingested_at > self.display_ttl:
            return None
        original = next((raw for raw in batch.originals if raw.sha256 == selected.raw_hash), None)
        if original is None:
            raise MarketStoreError("snapshot_original_missing")
        try:
            document = json.loads(original.payload)
            if (
                document["format"] != "provider_native_snapshot-v1"
                or document["provider_id"] != self.scope.source
            ):
                raise ValueError("invalid_snapshot")
            for payload in document["payloads"]:
                if digest(base64.b64decode(payload["base64"], validate=True)) != payload["sha256"]:
                    raise ValueError("invalid_payload")
            result = Result(**{key: document[key] for key in RESULT_KEYS})
        except (KeyError, TypeError, ValueError):
            raise MarketStoreError("snapshot_original_invalid") from None
        result.raw = [frozen.export()]
        result.metadata = {
            **document["metadata"],
            "warehouse_hit": True,
            "warehouse_snapshot_sha256": frozen.digest,
            "warehouse_scope_digest": self.scope.key,
            "warehouse_semantics_digest": dataset.semantic_digest,
            "storage_form": "provider_native_snapshot",
            "formal_backtest_eligible": False,
            "availability_basis": "first_observed",
            "observed_at": selected.ingested_at.isoformat(),
            "historical_point_in_time": False,
            "captured_as_of": query.as_of.isoformat() if query.as_of else None,
            "quality_accepted": False,
            "display_cache_ttl_seconds": int(self.display_ttl.total_seconds()),
        }
        result.limitations = list(
            dict.fromkeys(
                [
                    *result.limitations,
                    "provider_native_fields",
                    "single_response_not_complete_history",
                    "publication_time_unverified",
                    "units_not_normalized",
                    "not_formal_backtest_data",
                ]
            )
        )
        log.info(
            "research_snapshot_hit",
            rows=len(result.rows),
            historical_capture=query.as_of is not None,
        )
        return result
