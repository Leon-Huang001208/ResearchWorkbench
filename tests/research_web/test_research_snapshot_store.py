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


NAV_MISSING = ["adjusted_total_return", "benchmark_timeseries", "verified_currency"]


def nav_query(**updates):
    return query(
        capability="fund_data",
        source="eastmoney_fund",
        parameters={
            "dataset": "nav",
            "code": "510050",
            "start_date": "2025-01-02",
            "end_date": "2025-01-03",
        },
        **updates,
    )


def nav_series(context):
    _, _, service, _ = context
    series = SnapshotSeries(
        service, "alice", StoreScope("alice", "public", "eastmoney_fund", "a" * 64)
    )
    series._now = lambda: OBSERVED
    return series


@pytest.mark.parametrize("dataset", ["nav", "fund_nav"])
def test_complete_bounded_nav_preserves_disclosed_semantic_gaps(context, dataset):
    series = nav_series(context)
    request = nav_query()
    request.parameters["dataset"] = dataset
    result = response(
        provider_id="eastmoney_fund",
        missing=NAV_MISSING,
        pagination_complete=True,
        limitations=["unadjusted"],
    )
    assert series.ingest(request, result)
    read = series.read(request.model_copy(update={"as_of": OBSERVED}))
    assert read.missing == NAV_MISSING
    assert read.fields == result.fields
    assert "unadjusted" in read.limitations
    assert read.metadata["quality_accepted"] is False
    assert read.metadata["formal_backtest_eligible"] is False


@pytest.mark.parametrize(
    "change",
    [
        "unknown_gap",
        "wrong_provider",
        "missing_provider",
        "wrong_source",
        "wrong_dataset",
        "unbounded",
        "wide",
        "invalid_date",
        "reversed_dates",
        "snapshot",
        "empty",
        "pagination",
        "raw",
        "as_of",
        "partial",
    ],
)
def test_nav_exception_does_not_relax_other_capture_requirements(context, change):
    series = nav_series(context)
    request = nav_query()
    result = response(provider_id="eastmoney_fund", missing=NAV_MISSING, pagination_complete=True)
    if change == "unknown_gap":
        result.missing = [*NAV_MISSING, "unit_nav"]
    elif change == "wrong_provider":
        result.provider_id = "fund_nav"
    elif change == "missing_provider":
        result.provider_id = None
    elif change == "wrong_source":
        series = SnapshotSeries(
            series.service, "alice", StoreScope("alice", "public", "fund_nav", "a" * 64)
        )
        request = request.model_copy(update={"source": "fund_nav"})
        result.provider_id = "fund_nav"
    elif change == "wrong_dataset":
        request.parameters["dataset"] = "profile"
    elif change == "unbounded":
        request.parameters.pop("start_date")
        request.parameters.pop("end_date")
    elif change == "wide":
        request.parameters["end_date"] = "2025-03-03"
    elif change == "invalid_date":
        request.parameters["start_date"] = "not-a-date"
    elif change == "reversed_dates":
        request.parameters["start_date"] = "2025-01-04"
    elif change in {"snapshot", "partial", "empty"}:
        result.status = change
    elif change == "pagination":
        result.pagination_complete = False
    elif change == "raw":
        result.raw = []
    else:
        request = request.model_copy(update={"as_of": OBSERVED})
    if change in {"as_of", "partial"}:
        assert series.ingest(request, result) is None
    else:
        with pytest.raises(MarketStoreError):
            series.ingest(request, result)
    assert context[1].history(series.scope, series.dataset(request)) == ()


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


def test_field_dictionary_evidence_survives_native_freeze_export_restore():
    evidence = {
        "contract_version": "tinysoft-stock-daily-fields-v1",
        "observed_sdk_version": "0.5.2",
        "runtime_sdk_version": "0.5.2",
        "method": "markettable_columns",
        "dictionary_sha256": "27df9e431be417c522e65151179dcc476822f38e792f8ea497bd19733ac4d829",
        "applied": True,
        "scope": "explicit_stock_daily_native_vol_amount",
        "price_currency_verified": False,
        "identity_basis": "single_security_request",
        "response_identity_observed": False,
    }
    scope = StoreScope("alice", "license", "tinysoft", "a" * 64)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    series = SnapshotSeries(service, "alice", scope)
    series._now = lambda: OBSERVED
    request = BusinessQuery(
        capability="market_bars",
        source="tinysoft",
        parameters={
            "asset": "600000.SH",
            "asset_type": "stock",
            "frequency": "daily",
            "adjustment": "none",
            "start_date": "2026-01-01",
            "end_date": "2026-01-19",
        },
    )
    result = response(
        rows=[{"date": "2026-01-19", "vol": 100}],
        fields={"vol": {"unit": "share", "currency": None}},
        provider_id="tinysoft",
        metadata={"field_dictionary_evidence": evidence, "token": "must-not-save"},
    )
    assert series.ingest(request, result)
    evidence["dictionary_sha256"] = "mutated-after-ingestion"
    read = series.read(request.model_copy(update={"as_of": OBSERVED}))
    assert (
        read.metadata["field_dictionary_evidence"]["dictionary_sha256"]
        == "27df9e431be417c522e65151179dcc476822f38e792f8ea497bd19733ac4d829"
    )
    assert "token" not in read.metadata
    frozen = FrozenSnapshot.load(read.raw[0])
    replacement = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    restored = replacement.export_restore("alice", scope, frozen.export())
    assert restored.digest == frozen.digest
    again = SnapshotSeries(replacement, "alice", scope)
    again._now = lambda: OBSERVED
    recovered = again.read(request.model_copy(update={"as_of": OBSERVED}))
    assert (
        recovered.metadata["field_dictionary_evidence"]
        == read.metadata["field_dictionary_evidence"]
    )
    assert recovered.fields == read.fields and recovered.raw == read.raw
    assert recovered.metadata["quality_accepted"] is False
    assert recovered.metadata["formal_backtest_eligible"] is False
    assert recovered.metadata["historical_point_in_time"] is False


def test_unverified_native_series_cannot_satisfy_required_stock_price_semantics():
    scope = StoreScope("alice", "license", "tinysoft", "a" * 64)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    series = SnapshotSeries(service, "alice", scope)
    series._now = lambda: OBSERVED
    request = BusinessQuery(
        capability="market_bars",
        source="tinysoft",
        parameters={
            "asset": "600000.SH",
            "asset_type": "stock",
            "frequency": "daily",
            "adjustment": "none",
            "start_date": "2026-01-01",
            "end_date": "2026-01-19",
        },
    )
    result = response(provider_id="tinysoft")
    assert series.ingest(request, result)
    required = BusinessQuery.model_validate(
        {**request.model_dump(), "required_semantics": "cn_stock_daily_cny_share_v1"}
    )
    assert series.dataset(required) is None
    assert series.read(required) is None


@pytest.mark.parametrize(
    "capability,parameters,schema",
    [
        (
            "financials",
            {"asset": "600600.SH", "statements": ["income_statement"], "periods": ["2025-06-30"]},
            "akshare-sina-financial-disclosure-v3",
        ),
        (
            "factor_macro",
            {"series": "gdp", "start_date": "2025-09-01", "end_date": "2025-09-30"},
            "akshare-china-macro-v3",
        ),
        (
            "market_activity",
            {"asset": "600000.SH", "dataset": "fund_flow"},
            "akshare-eastmoney-fund-flow-provenance-v2",
        ),
    ],
)
def test_research_families_cutoff_revision_boundary(capability, parameters, schema):
    # Synthetic source envelopes retain strict raw binding while exercising revision time.
    from test_ak_native_binding import macro_result, sina_result

    request = BusinessQuery(capability=capability, source="akshare", parameters=parameters)
    scope = StoreScope("alice", "personal", "akshare", "c" * 64)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    series = SnapshotSeries(service, "alice", scope)
    first, second = OBSERVED, OBSERVED + timedelta(days=1)
    for stamp, value in [(first, 1), (second, 2)]:
        series._now = lambda stamp=stamp: stamp
        native = response(
            value,
            provider_id="akshare",
            status="snapshot",
            pagination_complete=True,
            metadata={"schema_version": schema},
            rows=[{"native_unknown": value}],
        )
        if capability == "financials":
            native = sina_result(str(value))
        elif capability == "factor_macro":
            native = macro_result(value=value)
        else:
            native.metadata["upstream_attempts"] = [
                {"upstream": "eastmoney", "endpoint": "akshare_sdk", "status": "snapshot"}
            ]
        assert series.ingest(request, native)
    assert (
        series.read(request.model_copy(update={"as_of": first - timedelta(microseconds=1)})) is None
    )
    for cutoff, expected in [(first, 1), (second - timedelta(microseconds=1), 1), (second, 2)]:
        captured = series.read(request.model_copy(update={"as_of": cutoff}))
        if capability == "financials":
            assert captured.rows[0]["data"][0]["item_value"] == str(expected)
        elif capability == "factor_macro":
            assert captured.rows[0]["DOMESTICL_PRODUCT_BASE"] == expected
        else:
            assert captured.rows[0]["native_unknown"] == expected
        assert captured.metadata["historical_point_in_time"] is False
        assert captured.metadata["formal_backtest_eligible"] is False
    with pytest.raises(MarketStoreError):
        series.read(request.model_copy(update={"purpose": "backtest", "as_of": first}))
