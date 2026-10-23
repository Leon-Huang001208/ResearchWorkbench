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
    assert binding["datasets"] == ["quarterly_profitability"]
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


def stored_response():
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.providers_baostock import (
        FINANCIAL_DICTIONARY,
        FINANCIAL_DICTIONARY_SHA256,
        FINANCIAL_SCHEMA,
    )

    return Result(
        rows=[
            {
                "asset": "600000.SH",
                "report_period": "2026-06-30",
                "publication_date": "2026-08-27",
                "publication_precision": "date",
                "netProfit": 12.0,
                "MBRevenue": 30.0,
                "roeAvg": 0.02,
            }
        ],
        raw=[b'{"synthetic_original":true}'],
        source_url="https://github.com/zxygithub/baostock/blob/master/docs/pythonAPI.md",
        provider_id="baostock",
        status="complete",
        pagination_complete=True,
        fields={
            "netProfit": {"unit": "CNY", "currency": "CNY"},
            "MBRevenue": {"unit": "CNY", "currency": "CNY"},
            "roeAvg": {"unit": None, "currency": None},
        },
        metadata={
            "schema_version": FINANCIAL_SCHEMA,
            "upstream_id": "baostock",
            "availability_basis": "first_observed",
            "historical_point_in_time": False,
            "formal_backtest_eligible": False,
            "field_dictionary_evidence": {
                "source_url": FINANCIAL_DICTIONARY,
                "document_sha256": FINANCIAL_DICTIONARY_SHA256,
                "fields": ["netProfit", "MBRevenue"],
                "unit": "CNY",
                "currency": "CNY",
            },
            "token": "synthetic-must-not-persist",
        },
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

    from app.research_web.datahub import DataHub, connections, providers
    from app.research_web.store import Store

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
