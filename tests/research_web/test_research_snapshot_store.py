"""Native response persistence contracts; no database, network or credentials."""

import base64
import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.research_snapshot_store import SnapshotSeries
from app.research_web.market_store import (
    Batch,
    FrozenSnapshot,
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)

OBSERVED = datetime(2026, 1, 20, 10, tzinfo=UTC)


def query(**updates):
    return BusinessQuery(
        **{
            "capability": "financials",
            "source": "wind",
            "parameters": {"asset": "600000.SH", "periods": ["2025-12-31"]},
            **updates,
        }
    )


def response(value=1, **updates):
    return Result(
        **{
            "rows": [{"report_period": "2025-12-31", "native_unknown": value}],
            "fields": {"native_unknown": {"unit": None, "currency": None}},
            "raw": [b"original\x00bytes", str(value).encode()],
            "status": "complete",
            "provider_id": "wind",
            "metadata": {"provider_semantics_revision": "v1", "token": "must-not-save"},
            **updates,
        }
    )


@pytest.fixture
def context():
    backend = InMemoryMarketStore()
    permitted = [True]
    service = MarketStoreService(
        backend, lambda actor, scope, action: permitted[0] and actor == "alice"
    )
    scope = StoreScope("alice", "license", "wind", "a" * 64)
    series = SnapshotSeries(service, "alice", scope)
    series._now = lambda: OBSERVED
    return series, backend, service, permitted


def captured(at=OBSERVED, **updates):
    return query(as_of=at, **updates)


def test_preserves_native_fields_raw_and_export_restore(context):
    series, _, _, _ = context
    result = response()
    series.ingest(query(), result)
    result.rows[0]["native_unknown"] = 99
    result.fields.clear()
    read = series.read(captured())
    assert read.rows == [{"report_period": "2025-12-31", "native_unknown": 1}]
    assert read.fields["native_unknown"]["unit"] is None
    assert "token" not in read.metadata
    assert read.metadata["formal_backtest_eligible"] is False
    assert read.metadata["availability_basis"] == "first_observed"
    assert "single_response_not_complete_history" in read.limitations
    frozen = FrozenSnapshot.load(read.raw[0])
    replacement = MarketStoreService(InMemoryMarketStore(), lambda *args: True)
    restored = replacement.export_restore("alice", series.scope, frozen.export())
    assert restored.digest == frozen.digest
    new = SnapshotSeries(replacement, "alice", series.scope)
    new._now = lambda: OBSERVED
    again = new.read(captured())
    assert again.rows == read.rows
    assert again.fields == read.fields
    assert again.raw == read.raw
    original = json.loads(frozen.payload)["batch"]["originals"][0]
    envelope = json.loads(base64.b64decode(original["base64"]))
    assert base64.b64decode(envelope["payloads"][0]["base64"]) == b"original\x00bytes"


def test_aba_keeps_three_captures_and_adjacent_unchanged_idempotent(context):
    series, backend, _, _ = context
    first = series.ingest(query(), response(1))
    assert series.ingest(query(), response(1)) == first
    series._now = lambda: OBSERVED + timedelta(seconds=1)
    second = series.ingest(query(), response(2))
    series._now = lambda: OBSERVED + timedelta(seconds=2)
    third = series.ingest(query(), response(1))
    assert len({first, second, third}) == 3
    assert len(backend.history(series.scope, series.dataset(query()))) == 3
    assert series.read(captured(OBSERVED)).rows[0]["native_unknown"] == 1
    assert series.read(captured(OBSERVED + timedelta(seconds=1))).rows[0]["native_unknown"] == 2
    final = series.read(captured(OBSERVED + timedelta(seconds=2)))
    assert final.rows[0]["native_unknown"] == 1
    assert len(json.loads(FrozenSnapshot.load(final.raw[0]).payload)["batch"]["facts"]) == 1


def test_cross_day_aba_is_one_logical_projection_with_historical_exports(context):
    series, backend, service, _ = context
    series.ingest(query(), response(1))
    initial_export = series.read(captured()).raw[0]
    next_day = OBSERVED + timedelta(days=1)
    series._now = lambda: next_day
    series.ingest(query(), response(2))
    second_export = series.read(captured(next_day)).raw[0]
    final_day = OBSERVED + timedelta(days=2)
    series._now = lambda: final_day
    series.ingest(query(), response(1))
    dataset = series.dataset(query())
    history = backend.history(series.scope, dataset)
    assert len(history) == 3
    assert len({fact.logical_key for fact in history}) == 1
    assert len({fact.source_version for fact in history}) == 3
    assert series.read(captured()).raw[0] == initial_export
    assert series.read(captured(next_day)).raw[0] == second_export
    for at, expected in ((OBSERVED, 1), (next_day, 2), (final_day, 1)):
        result = series.read(captured(at))
        assert result.rows[0]["native_unknown"] == expected
        document = json.loads(FrozenSnapshot.load(result.raw[0]).payload)
        assert len(document["batch"]["facts"]) == len(document["batch"]["originals"]) == 1
        assert document["start"] == document["end"] == "1970-01-01"
        assert (
            len(
                service.read_range(
                    "alice",
                    series.scope,
                    dataset,
                    history[0].business_date,
                    history[0].business_date,
                    as_of=at,
                ).facts
            )
            == 1
        )


def test_over_ten_thousand_revisions_still_read_freeze_and_append_one_projection(context):
    series, backend, service, _ = context
    series.ingest(query(), response(1))
    dataset = series.dataset(query())
    original = backend.history(series.scope, dataset)[0]
    revisions = tuple(
        replace(
            original,
            available_at=OBSERVED + timedelta(seconds=index),
            ingested_at=OBSERVED + timedelta(seconds=index),
            source_version=f"revision-{index}",
        )
        for index in range(1, 10001)
    )
    service.commit_batch("alice", series.scope, dataset, Batch(revisions, ()))
    current = OBSERVED + timedelta(days=1)
    series._now = lambda: current
    assert len(backend.history(series.scope, dataset)) == 10001
    assert len(series._facts(dataset, current)) == 1
    assert (
        len(
            json.loads(FrozenSnapshot.load(series.read(captured(current)).raw[0]).payload)["batch"][
                "facts"
            ]
        )
        == 1
    )
    series.ingest(query(), response(2))
    assert len(backend.history(series.scope, dataset)) == 10002
    assert series.read(captured(current)).rows[0]["native_unknown"] == 2
    assert series.read(captured()).rows[0]["native_unknown"] == 1


def test_cutoff_has_no_period_or_later_capture_leak(context):
    series, _, _, _ = context
    series.ingest(query(), response())
    assert series.read(captured(OBSERVED - timedelta(microseconds=1))) is None
    assert series.read(query()) is None
    assert series.ingest(captured(), response(99)) is None


def test_display_ttl_is_explicit_and_bounded(context):
    series, _, _, _ = context
    series.ingest(query(), response())
    display = query(purpose="display", quality="allow_stale")
    assert series.read(display).metadata["observed_at"] == OBSERVED.isoformat()
    assert series.read(display.model_copy(update={"refresh": True})) is None
    series._now = lambda: OBSERVED + timedelta(seconds=301)
    assert series.read(display) is None
    assert series.read(captured()) is not None
    with pytest.raises(MarketStoreError, match="snapshot_ttl_invalid"):
        SnapshotSeries(series.service, "alice", series.scope, display_ttl_seconds=86400)


def test_authorization_revoked_on_hit_strict_and_ingest(context):
    series, _, _, permitted = context
    series.ingest(query(), response())
    permitted[0] = False
    for operation in (
        lambda: series.read(captured()),
        lambda: series.read(query()),
        lambda: series.ingest(query(), response(status="failed")),
    ):
        with pytest.raises(MarketStoreError, match="warehouse_access_denied"):
            operation()


@pytest.mark.parametrize("status", ["partial", "failed", "cancelled"])
def test_incomplete_not_persisted(context, status):
    series, backend, _, _ = context
    assert series.ingest(query(), response(status=status)) is None
    assert backend.history(series.scope, series.dataset(query())) == ()


def test_empty_is_captured_without_full_history_claim(context):
    series, _, _, _ = context
    series.ingest(query(), response(rows=[], status="empty", raw=[b"[]"]))
    result = series.read(captured())
    assert result.status == "empty" and result.rows == []
    assert result.metadata["quality_accepted"] is False
    assert "single_response_not_complete_history" in result.limitations


def test_business_source_schema_and_unit_identities_do_not_mix(context):
    series, _, service, _ = context
    series.ingest(query(), response())
    assert (
        series.read(captured(parameters={"asset": "600000.SH", "periods": ["2025-09-30"]})) is None
    )
    for kwargs in ({"schema_identity": "v2"}, {"units_identity": "USD"}):
        other = SnapshotSeries(service, "alice", series.scope, **kwargs)
        other._now = lambda: OBSERVED
        assert other.read(captured()) is None
    other_scope = StoreScope("alice", "license", "akshare", "a" * 64)
    other = SnapshotSeries(service, "alice", other_scope)
    other._now = lambda: OBSERVED
    assert other.read(captured(source="akshare")) is None
    with pytest.raises(MarketStoreError, match="snapshot_source_mismatch"):
        series.read(captured(source="akshare"))


def test_etf_and_index_have_native_separate_identity(context):
    series, _, _, _ = context
    for asset_type in ("etf", "index"):
        request = query(
            capability="market_bars",
            parameters={
                "asset": "510300.SH",
                "asset_type": asset_type,
                "frequency": "daily",
                "adjustment": "none",
            },
        )
        series.ingest(request, response(fields={"volume": {"unit": "provider_defined"}}))
        result = series.read(request.model_copy(update={"as_of": OBSERVED}))
        assert result.fields["volume"]["unit"] == "provider_defined"
        assert result.metadata["formal_backtest_eligible"] is False
    assert (
        series.dataset(query(capability="market_bars", parameters={"asset_type": "stock"})) is None
    )


def test_only_named_public_numeric_endpoints_admitted(context):
    series, _, service, _ = context
    other = SnapshotSeries(service, "alice", StoreScope("alice", "public", "ext_bls", "a" * 64))
    assert (
        other.dataset(
            query(capability="external_data", source="ext_bls", parameters={"dataset": "series"})
        )
        is not None
    )
    assert (
        other.dataset(
            query(
                capability="external_data", source="ext_bls", parameters={"dataset": "cpi-calendar"}
            )
        )
        is None
    )
    assert series.dataset(query(capability="search_news", parameters={"query": "news"})) is None
    with pytest.raises(MarketStoreError, match="snapshot_formal_backtest_unavailable"):
        series.read(captured(purpose="backtest"))


def test_missing_raw_wrong_source_and_missing_fields_rejected(context):
    series, _, _, _ = context
    for result in (
        response(raw=[]),
        response(provider_id="akshare"),
        response(missing=["critical"]),
    ):
        with pytest.raises(MarketStoreError):
            series.ingest(query(), result)


def test_clock_conflict_never_randomly_orders_revisions(context):
    series, backend, _, _ = context
    series.ingest(query(), response(1))
    with pytest.raises(MarketStoreError, match="snapshot_clock_not_advanced"):
        series.ingest(query(), response(2))
    assert len(backend.history(series.scope, series.dataset(query()))) == 1


def test_export_and_restore_actions_are_independently_authorized(context):
    series, backend, _, _ = context
    series.ingest(query(), response())
    export_denied = MarketStoreService(backend, lambda actor, scope, action: action == "read")
    reader = SnapshotSeries(export_denied, "alice", series.scope)
    reader._now = lambda: OBSERVED
    with pytest.raises(MarketStoreError, match="warehouse_access_denied"):
        reader.read(captured())
    content = series.read(captured()).raw[0]
    with pytest.raises(MarketStoreError, match="warehouse_access_denied"):
        export_denied.export_restore("alice", series.scope, content)
