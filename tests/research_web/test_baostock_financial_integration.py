"""Source-qualified BaoStock profitability routing and warehouse contracts."""

import pytest

from app.research_web.datahub.broker import resolve
from app.research_web.datahub.catalog import build_catalog
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.store import StoreError


def profitability(source="baostock", **updates):
    return BusinessQuery(
        capability="financials",
        source=source,
        parameters={
            "asset": "600000.SH",
            "statements": ["profitability"],
            "periods": ["2026-06-30"],
        },
        **updates,
    )


def test_catalog_declares_distinct_bounded_baostock_financial_dataset():
    catalog = build_catalog(environ={})
    binding = next(
        item
        for item in catalog["bindings"]
        if item["source_id"] == "baostock" and item["capability_id"] == "financials"
    )
    assert binding["implemented"] is True
    assert binding["datasets"] == ["quarterly_profitability", "quarterly_cash_flow_ratios"]
    assert binding["semantics"]["quarterly_profitability"]["historical_point_in_time"] is False


def test_explicit_and_auto_profitability_select_same_supplier_without_summary_substitution(
    monkeypatch,
):
    from app.research_web.datahub import catalog

    monkeypatch.setattr(catalog, "find_spec", lambda _name: object())
    for source in ["baostock", "auto"]:
        result = resolve(profitability(source), environ={})
        assert result.provider_id == "baostock"
        assert result.query.parameters == profitability().parameters
        assert {attempt["source"] for attempt in result.attempted_sources} == {"baostock"}
    with pytest.raises(StoreError):
        resolve(profitability("akshare", allow_fallback=True), environ={})
    with pytest.raises(StoreError):
        resolve(profitability("auto"), environ={}, excluded_sources=frozenset({"baostock"}))


def test_profitability_missing_sdk_is_rejected_before_provider_execution(monkeypatch):
    from app.research_web.datahub import catalog

    monkeypatch.setattr(catalog, "find_spec", lambda _name: None)
    for source in ["baostock", "auto"]:
        with pytest.raises(StoreError) as rejected:
            resolve(profitability(source), environ={})
        assert rejected.value.code == "data_capability_unavailable"
        assert rejected.value.status == 503


def stored_response():
    import json

    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.providers_baostock import FINANCIAL_DICTIONARY, FINANCIAL_FIELDS
    from app.research_web.datahub.providers_baostock_reference import (
        profitability_fields,
        profitability_metadata,
        profitability_projection,
    )

    record = dict.fromkeys(FINANCIAL_FIELDS.split(","), "1.0")
    record.update(code="sh.600000", statDate="2026-06-30", pubDate="2026-08-27")
    original = json.dumps([record]).encode()
    rows, missing = profitability_projection(original, "600000.SH", "2026-06-30")
    return Result(
        rows=rows,
        raw=[original],
        source_url=FINANCIAL_DICTIONARY,
        provider_id="baostock",
        status="complete",
        provider_total=1,
        pagination_complete=True,
        fields=profitability_fields(),
        missing=missing,
        metadata={**profitability_metadata(), "token": "synthetic-must-not-persist"},
    )


def test_profitability_capture_restore_keeps_native_scale_and_date_without_pit_promotion():
    from datetime import date

    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    scope = StoreScope("alice", "personal", "baostock", "a" * 64)
    service = MarketStoreService(
        InMemoryMarketStore(),
        lambda actor, requested, _action: actor == "alice" and requested == scope,
    )
    series = SnapshotSeries(service, "alice", scope)
    request = profitability()
    original = stored_response()
    assert series.ingest(request, original)
    assert series.read(request) is None
    display = request.model_copy(update={"purpose": "display", "quality": "allow_stale"})
    captured = series.read(display)
    assert captured.rows == original.rows
    assert captured.fields == original.fields
    assert captured.metadata["formal_backtest_eligible"] is False
    assert captured.metadata["availability_basis"] == "first_observed"
    assert "token" not in captured.metadata
    frozen = service.freeze(
        "alice", scope, series.dataset(request), date(1970, 1, 1), date(1970, 1, 1)
    )
    target = MarketStoreService(InMemoryMarketStore(), lambda *_args: True)
    assert target.export_restore("alice", scope, frozen.export()).digest == frozen.digest
    restored = SnapshotSeries(target, "alice", scope).read(display)
    assert restored.rows == captured.rows and restored.fields == captured.fields
    assert restored.raw == captured.raw


@pytest.mark.parametrize("bad", ["schema", "units", "dictionary", "asof-claim", "partial", "empty"])
def test_profitability_rejects_incomplete_native_contract_before_capture(bad):
    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    scope = StoreScope("alice", "personal", "baostock", "a" * 64)
    series = SnapshotSeries(
        MarketStoreService(InMemoryMarketStore(), lambda *_args: True), "alice", scope
    )
    result = stored_response()
    if bad == "schema":
        result.metadata["schema_version"] = "legacy"
    if bad == "dictionary":
        result.metadata["field_dictionary_evidence"]["document_sha256"] = "a" * 64
    if bad == "units":
        result.fields["netProfit"]["unit"] = "CNY_10000"
    if bad == "asof-claim":
        result.metadata["formal_backtest_eligible"] = True
    if bad in {"partial", "empty"}:
        result.status = bad
    assert series.ingest(profitability(), result) is None
    assert series.read(profitability()) is None


@pytest.mark.asyncio
async def test_legacy_profitability_session_cache_is_not_reused_but_receipt_remains_readable(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from app.research_web.datahub import DataHub, catalog, connections, providers
    from app.research_web.store import Store

    # The provider below is synthetic; model its installed SDK explicitly so
    # cache compatibility does not depend on the developer's site-packages.
    monkeypatch.setattr(catalog, "find_spec", lambda _name: object())
    monkeypatch.setattr(connections.os, "environ", {})
    monkeypatch.setattr(
        connections,
        "default_credential_backend",
        lambda: SimpleNamespace(get_password=lambda *_args: None),
    )
    calls = []

    async def fetch(request, **_kwargs):
        calls.append(request)
        result = stored_response()
        result.metadata.pop("token")
        if len(calls) == 1:
            result.metadata["schema_version"] = "legacy-financial-schema"
        return result

    monkeypatch.setattr(providers, "fetch", fetch)
    store = Store(tmp_path)
    sid = store.create("claw", "profitability cache contract")["id"]
    hub = DataHub(store)
    try:
        first = await hub.query(sid, "first", profitability())
        second = await hub.query(sid, "second", profitability())
        assert len(calls) == 2
        assert not second["cache_hit"]
        assert first["dataset_id"] != second["dataset_id"]
        again = await hub.query(sid, "first", profitability())
        assert again["dataset_id"] == first["dataset_id"]
        assert len(calls) == 2
    finally:
        await hub.close()


@pytest.mark.parametrize(
    "tamper",
    [
        "row",
        "reference",
        "raw",
        "raw-bool",
        "raw-duplicate",
        "fields",
        "metadata",
        "basis",
        "source",
        "count",
    ],
)
def test_profitability_original_binding_rejects_forgery_and_preserves_previous(tamper):
    import json

    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    scope = StoreScope("alice", "personal", "baostock", "a" * 64)
    series = SnapshotSeries(
        MarketStoreService(InMemoryMarketStore(), lambda *_: True), "alice", scope
    )
    query = profitability()
    good = stored_response()
    assert series.ingest(query, good)
    display = query.model_copy(update={"purpose": "display", "quality": "allow_stale"})
    before = series.read(display)
    bad = stored_response()
    if tamper == "row":
        bad.rows[0]["netProfit"] = 2.0
    elif tamper == "reference":
        bad.rows[0]["reference_evidence"] = {"reporting_basis": "year_to_date"}
    elif tamper == "raw":
        bad.raw = [b'{"synthetic_original":true}']
    elif tamper == "raw-bool":
        original = json.loads(bad.raw[0])
        original[0]["netProfit"] = True
        bad.raw = [json.dumps(original).encode()]
    elif tamper == "raw-duplicate":
        bad.raw = [
            bad.raw[0].replace(b'"netProfit": "1.0"', b'"netProfit": "1.0", "netProfit": "1.0"')
        ]
    elif tamper == "fields":
        bad.fields["roeAvg"]["unit"] = "percent"
    elif tamper == "metadata":
        bad.metadata["reference_dictionary"]["document_sha256"] = "f" * 64
    elif tamper == "basis":
        bad.metadata["reporting_basis"] = "single_quarter"
    elif tamper == "source":
        bad.source_url = "https://invalid.example/forged"
    else:
        bad.provider_total = True
    assert series.ingest(query, bad) is None
    after = series.read(display)
    assert after.rows == before.rows and after.raw == before.raw
