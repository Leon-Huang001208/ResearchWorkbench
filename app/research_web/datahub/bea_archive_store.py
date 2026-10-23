"""Trusted bridge for reviewed official release vintages; no native PIT promotion."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime

from core.observability import get_logger

from ..market_store import Batch, DatasetIdentity, Fact, MarketStoreError, RawOriginal
from .providers import ProviderError
from .providers_bea_archive import (
    CATALOG,
    FIELDS,
    PERIOD,
    SCHEMA,
    SERIES,
    metadata,
    parse_release,
    validate_supported_query,
)
from .warehouse import WarehouseBinding, WarehouseBridge

log = get_logger(__name__)


def archive_bridge(service, actor, scope):
    semantic = {
        **metadata(),
        "catalog": [
            {
                "release": item.identifier,
                "stage": item.stage,
                "at": item.published_at.isoformat(),
                "url": item.url,
            }
            for item in CATALOG
        ],
        "unit": "percent_qoq_saar",
        "seasonal_adjustment": "seasonally_adjusted",
    }
    dataset = DatasetIdentity(
        "factor_macro",
        SERIES,
        "US",
        "quarterly",
        "percent_qoq_saar",
        "seasonally_adjusted",
        "annualized_rate",
        hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest(),
        metrics=("row", "gdp_growth"),
    )
    business_day = date.fromisoformat(PERIOD)

    def check_pair(facts):
        if (
            len(facts) != 2
            or {fact.metric for fact in facts} != {"row", "gdp_growth"}
            or len({(f.source_version, f.available_at, f.raw_hash) for f in facts}) != 1
        ):
            raise MarketStoreError("bea_archive_revision_pair_invalid")
        row = next(f.value for f in facts if f.metric == "row")
        number = next(f.value for f in facts if f.metric == "gdp_growth")
        release = next(
            (item for item in CATALOG if item.identifier == facts[0].source_version), None
        )
        if (
            release is None
            or not isinstance(row, dict)
            or row.get("value") != number
            or row.get("release_id") != release.identifier
            or row.get("published_at") != release.published_at.isoformat()
            or any(
                f.available_at != release.published_at
                or f.business_date != business_day
                or f.period != "2024-Q2"
                for f in facts
            )
        ):
            raise MarketStoreError("bea_archive_revision_pair_invalid")
        return row

    def normalize(result, _previous):
        if (
            result.provider_id != "bea_archive"
            or result.status != "snapshot"
            or len(result.raw) != len(CATALOG)
            or result.pagination_complete is not True
            or result.missing
            or result.metadata.get("schema_version") != SCHEMA
            or result.fields != FIELDS
        ):
            raise MarketStoreError("bea_archive_capture_invalid")
        try:
            rows = [parse_release(raw, item) for raw, item in zip(result.raw, CATALOG, strict=True)]
        except ProviderError:
            raise MarketStoreError("bea_archive_original_invalid") from None
        if result.rows != rows[-1:]:
            raise MarketStoreError("bea_archive_capture_invalid")
        facts, originals = [], []
        observed = datetime.now(UTC)
        for release, row, raw in zip(CATALOG, rows, result.raw, strict=True):
            # Reading only the latest projection would conceal conflicts in an
            # older release. Compare each revision at its own published cutoff.
            old = service.read_range(
                actor, scope, dataset, business_day, business_day, as_of=release.published_at
            ).facts
            if old and any(f.source_version == release.identifier for f in old):
                selected = check_pair(old)
                if (
                    any(
                        f.source_version != release.identifier
                        or f.available_at != release.published_at
                        for f in old
                    )
                    or selected != row
                ):
                    log.warning("datahub_bea_archive_release_conflict", release=release.identifier)
                    raise MarketStoreError("bea_archive_release_conflict")
                continue
            if old and any(f.available_at == release.published_at for f in old):
                raise MarketStoreError("bea_archive_release_conflict")
            original = RawOriginal(raw)
            originals.append(original)
            for metric, value in (("row", row), ("gdp_growth", row["value"])):
                facts.append(
                    Fact(
                        metric,
                        business_day,
                        "2024-Q2",
                        json.dumps(value, sort_keys=True, allow_nan=False),
                        release.published_at,
                        observed,
                        release.identifier,
                        original.sha256,
                    )
                )
        return Batch(tuple(facts), tuple(originals)) if facts else None

    def render(batch):
        row = check_pair(batch.facts)
        release = next(item for item in CATALOG if item.identifier == row["release_id"])
        originals = [raw for raw in batch.originals if raw.sha256 == batch.facts[0].raw_hash]
        try:
            if len(originals) != 1 or parse_release(originals[0].payload, release) != row:
                raise MarketStoreError("bea_archive_original_invalid")
        except ProviderError:
            raise MarketStoreError("bea_archive_original_invalid") from None
        return [row]

    def provenance(batch):
        row = check_pair(batch.facts)
        return {
            **metadata(),
            "selected_release_id": row["release_id"],
            "selected_published_at": row["published_at"],
            "archive_original_sha256": sorted({fact.raw_hash for fact in batch.facts}),
            "system_known_at_publication": False,
            "revision_policy": "official_archive_publication_vintage_not_system_knowledge",
        }

    binding = WarehouseBinding(
        actor,
        scope,
        dataset,
        (business_day,),
        normalize,
        source_url=CATALOG[-1].url,
        render=render,
        field_metadata=FIELDS,
        source_metadata=provenance,
    )
    return _ArchiveBridge(service, lambda *_args: binding)


class _ArchiveBridge(WarehouseBridge):
    def read(self, query, source, configuration_digest):
        try:
            validate_supported_query(query, storage_read=True)
        except ProviderError:
            raise MarketStoreError("bea_archive_scope_unverified") from None
        context = self._context(query, source, configuration_digest)
        if context is None:
            return None
        expected = next(
            release
            for release in reversed(CATALOG)
            if query.as_of is None or release.published_at <= query.as_of
        )
        selected = self.service.read_range(
            context.actor,
            context.scope,
            context.dataset,
            date.fromisoformat(PERIOD),
            date.fromisoformat(PERIOD),
            as_of=query.as_of,
        )
        if not selected.facts or any(
            f.source_version != expected.identifier for f in selected.facts
        ):
            log.info("datahub_bea_required_release_missing", release=expected.identifier)
            return None
        result = super().read(query, source, configuration_digest)
        if result is not None:
            result.source_url = result.rows[0]["source_url"]
            result.metadata["formal_backtest_eligible"] = query.as_of is not None
        return result

    def ingest(self, query, source, configuration_digest, result):
        try:
            validate_supported_query(query)
        except ProviderError:
            raise MarketStoreError("bea_archive_scope_unverified") from None
        try:
            return super().ingest(query, source, configuration_digest, result)
        except MarketStoreError as exc:
            if str(exc) != "immutable_revision_conflict":
                raise
            # Another Host may have committed exactly this official release
            # after our empty read. Revalidate once against that committed
            # revision; any changed value still raises release_conflict.
            log.info("datahub_bea_concurrent_release_revalidate")
            return super().ingest(query, source, configuration_digest, result)
