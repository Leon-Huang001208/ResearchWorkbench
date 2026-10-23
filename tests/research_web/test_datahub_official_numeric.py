"""Offline replay of public official responses, including adversarial mutations."""

import json
from pathlib import Path

import httpx
import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers_external import fetch

FIXTURES = Path(__file__).parent / "fixtures" / "official_numeric"
DATASETS = {"nyfed": "rates", "treasury": "cash", "worldbank": "inflation"}
ARGS = {
    "nyfed": {"params": {"start": "2024-03-01", "end": "2024-03-01"}},
    "treasury": {"query": {"filter": "record_date:eq:2024-03-01", "page[size]": 2}},
    "worldbank": {"query": {"date": "2022:2023", "per_page": 10}},
}


def query(name, args=None):
    return BusinessQuery(
        capability="external_data",
        source="ext_" + name,
        parameters={
            "dataset": DATASETS[name],
            "arguments_json": json.dumps(ARGS[name] if args is None else args),
        },
    )


async def replay(name, payload=None, args=None):
    raw = (
        (FIXTURES / (name + ".json")).read_bytes()
        if payload is None
        else json.dumps(payload).encode()
    )
    result = await fetch(
        query(name, args),
        transport=httpx.MockTransport(
            lambda _: httpx.Response(200, content=raw, headers={"content-type": "application/json"})
        ),
    )
    return result, raw


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,total,status",
    [("nyfed", 6, "snapshot"), ("treasury", 4, "partial"), ("worldbank", 2, "snapshot")],
)
async def test_actual_official_payloads(name, total, status):
    result, raw = await replay(name)
    assert result.status == status
    assert result.raw == [raw]
    assert result.provider_total == total
    assert result.pagination_complete is (status == "snapshot")
    assert result.metadata["schema_version"] == "official-numeric-v2"
    if name == "treasury":
        assert result.rows[0]["close_today_bal"] == "null"
        assert result.fields["open_today_bal"]["unit"] == "USD_million"
    elif name == "worldbank":
        assert result.fields["value"]["unit"] == "percent_per_year"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", DATASETS)
@pytest.mark.parametrize(
    "payload", [None, {}, {"data": None}, {"error": "invalid"}, "<html>Access denied</html>"]
)
async def test_invalid_envelopes_fail_closed(name, payload):
    result, _ = await replay(name, payload if payload is not None else [])
    assert result.status == "failed"
    assert result.rows == [] and result.raw == []


@pytest.mark.asyncio
@pytest.mark.parametrize("name", DATASETS)
async def test_wrong_dates_identity_and_null_are_not_success(name):
    body = json.loads((FIXTURES / (name + ".json")).read_bytes())
    rows = body["refRates"] if name == "nyfed" else body["data"] if name == "treasury" else body[1]
    field = "effectiveDate" if name == "nyfed" else "record_date" if name == "treasury" else "date"
    rows[0][field] = "1900" if name == "worldbank" else "1900-01-01"
    result, _ = await replay(name, body)
    assert result.status == "failed"
    body = json.loads((FIXTURES / (name + ".json")).read_bytes())
    rows = body["refRates"] if name == "nyfed" else body["data"] if name == "treasury" else body[1]
    if name == "worldbank":
        rows[0]["countryiso3code"] = "CHN"
    elif name == "nyfed":
        rows[0]["type"] = "made-up"
    else:
        rows[0]["table_nbr"] = "II"
    assert (await replay(name, body))[0].status == "failed"


@pytest.mark.asyncio
async def test_worldbank_null_is_preserved_but_partial():
    body = json.loads((FIXTURES / "worldbank.json").read_bytes())
    body[1][0]["value"] = None
    result, raw = await replay("worldbank", body)
    assert result.status == "partial" and result.raw == [raw]
    assert "numeric_values_missing" in result.missing


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name,args",
    [
        ("worldbank", {"query": {"date": "2023:2022"}}),
        ("worldbank", {"query": {"format": "xml"}}),
        ("nyfed", {"params": {"start": "2024-02-30", "end": "2024-03-01"}}),
        ("treasury", {"query": {"filter": "account_type:eq:other"}}),
    ],
)
async def test_unsupported_filters_rejected_before_http(name, args):
    def forbidden(_):
        raise AssertionError("invalid contract must not perform HTTP")

    result = await fetch(query(name, args), transport=httpx.MockTransport(forbidden))
    assert result.status == "failed"


@pytest.mark.asyncio
@pytest.mark.parametrize("name", DATASETS)
async def test_duplicates_and_inconsistent_counts_fail(name):
    body = json.loads((FIXTURES / (name + ".json")).read_bytes())
    rows = body["refRates"] if name == "nyfed" else body["data"] if name == "treasury" else body[1]
    rows[1] = rows[0].copy()
    assert (await replay(name, body))[0].status == "failed"
    if name != "nyfed":
        body = json.loads((FIXTURES / (name + ".json")).read_bytes())
        (body["meta"] if name == "treasury" else body[0])[
            "total-count" if name == "treasury" else "total"
        ] = 999
        assert (await replay(name, body))[0].status == "failed"


@pytest.mark.asyncio
async def test_empty_rates_and_worldbank_are_empty_and_all_null_rates_partial():
    assert (await replay("nyfed", {"refRates": []}))[0].status == "empty"
    body = [{"page": 1, "pages": 0, "per_page": 10, "total": 0}, None]
    assert (await replay("worldbank", body))[0].status == "empty"
    body = json.loads((FIXTURES / "nyfed.json").read_bytes())
    body["refRates"][0]["percentRate"] = None
    result, _ = await replay("nyfed", body)
    assert result.status == "partial" and "numeric_values_missing" in result.missing


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["nyfed", "worldbank", "treasury"])
async def test_native_admission_freeze_restore_and_backtest(name):
    import base64
    from datetime import UTC, datetime

    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import (
        FrozenSnapshot,
        InMemoryMarketStore,
        MarketStoreError,
        MarketStoreService,
        StoreScope,
    )

    result, raw = await replay(name)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    scope = StoreScope("alice", "public", "ext_" + name, "a" * 64)
    series = SnapshotSeries(service, "alice", scope, schema_identity="official-numeric-v2")
    stamp = datetime(2026, 10, 23, tzinfo=UTC)
    series._now = lambda: stamp
    request = query(name)
    if name == "treasury":
        assert series.ingest(request, result) is None  # Actual 2/4 rows cannot be warehoused.
        assert series.read(request.model_copy(update={"as_of": stamp})) is None
        return
    assert series.ingest(request, result)
    read = series.read(request.model_copy(update={"as_of": stamp}))
    assert read.fields == result.fields and read.rows == result.rows
    assert read.metadata["schema_version"] == "official-numeric-v2"
    frozen = FrozenSnapshot.load(read.raw[0])
    original = json.loads(frozen.payload)["batch"]["originals"][0]
    envelope = json.loads(base64.b64decode(original["base64"]))
    assert base64.b64decode(envelope["payloads"][0]["base64"]) == raw
    replacement = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    assert replacement.export_restore("alice", scope, frozen.export()).digest == frozen.digest
    restored = SnapshotSeries(replacement, "alice", scope, schema_identity="official-numeric-v2")
    again = restored.read(request.model_copy(update={"as_of": stamp}))
    assert again.rows == read.rows and again.fields == read.fields and again.raw == read.raw
    assert again.metadata["formal_backtest_eligible"] is False
    with pytest.raises(MarketStoreError, match="snapshot_formal_backtest_unavailable"):
        series.dataset(request.model_copy(update={"purpose": "backtest"}))


@pytest.mark.asyncio
async def test_treasury_complete_envelope_and_cash_nulls():
    """Synthetic complete-page mutation checks semantics, not real history coverage."""
    from datetime import UTC, datetime

    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.market_store import InMemoryMarketStore, MarketStoreService, StoreScope

    body = json.loads((FIXTURES / "treasury.json").read_bytes())
    body["meta"].update({"total-count": 2, "total-pages": 1})
    body["links"]["next"] = None
    result, _ = await replay("treasury", body)
    assert result.status == "snapshot" and result.pagination_complete
    scope = StoreScope("alice", "public", "ext_treasury", "a" * 64)
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
    series = SnapshotSeries(service, "alice", scope, schema_identity="official-numeric-v2")
    stamp = datetime(2026, 10, 23, tzinfo=UTC)
    series._now = lambda: stamp
    request = query("treasury")
    assert series.ingest(request, result)
    captured = series.read(request.model_copy(update={"as_of": stamp}))
    assert captured.fields["open_today_bal"]["unit"] == "USD_million"
    for field in ("close_today_bal", "open_today_bal", "open_month_bal", "open_fiscal_year_bal"):
        body["data"][0][field] = "null"
    missing, _ = await replay("treasury", body)
    assert missing.status == "partial" and "numeric_values_missing" in missing.missing
    assert series.ingest(request, missing) is None
    assert series.read(request.model_copy(update={"as_of": stamp})).rows == captured.rows


@pytest.mark.asyncio
@pytest.mark.parametrize("name", ["worldbank", "treasury"])
@pytest.mark.parametrize("count", [True, 1.2, -1, "not-a-count"])
async def test_noninteger_pagination_is_rejected(name, count):
    body = json.loads((FIXTURES / (name + ".json")).read_bytes())
    (body["meta"] if name == "treasury" else body[0])[
        "total-count" if name == "treasury" else "total"
    ] = count
    assert (await replay(name, body))[0].status == "failed"


@pytest.mark.asyncio
async def test_new_query_skips_old_contract_session_cache_but_receipt_remains_readable(tmp_path):
    from app.research_web.datahub import DataHub
    from app.research_web.datahub.providers import Result
    from app.research_web.store import Store

    store = Store(tmp_path)
    sid = store.create("claw", "official numeric")["id"]
    calls = []
    raw = (FIXTURES / "worldbank.json").read_bytes()

    def handle(request):
        calls.append(request)
        return httpx.Response(200, content=raw, headers={"content-type": "application/json"})

    hub = DataHub(store, transport=httpx.MockTransport(handle))
    request = query("worldbank")
    old = Result(
        provider_id="ext_worldbank",
        status="snapshot",
        rows=[{"date": "2023", "value": 99}],
        raw=[b"old"],
    )
    saved = hub.snapshots.publish(
        sid,
        request,
        old,
        request_query=request,
        authorization_fingerprint=hub.source_configuration_digest("ext_worldbank"),
    )
    hub.snapshots.receipt(
        sid,
        "old-call",
        {
            "status": "completed",
            "fingerprint": request.fingerprint(include_refresh=True),
            "dataset_id": saved["dataset_id"],
            "cache_hit": False,
        },
    )
    try:
        old_receipt = await hub.query(sid, "old-call", request)
        assert old_receipt["dataset_id"] == saved["dataset_id"] and not calls
        fresh = await hub.query(sid, "new-call", request)
        assert fresh["dataset_id"] != saved["dataset_id"] and len(calls) == 1
        cached = await hub.query(sid, "cached-call", request)
        assert cached["dataset_id"] == fresh["dataset_id"] and len(calls) == 1
    finally:
        await hub.close()


def test_host_numeric_schema_isolated_without_changing_authorization_scope():
    from types import SimpleNamespace

    from app.research_web.datahub.research_snapshot_store import SnapshotSeries
    from app.research_web.datahub.research_warehouse import ResearchWarehouse
    from app.research_web.market_store import InMemoryMarketStore

    profile = {"enabled": True, "id": "public", "configuration": {}, "owner": "alice"}
    host = SimpleNamespace(
        owner="alice",
        _profile=lambda: profile,
        _secret=lambda _: "fixture",
        _factory=lambda *_: InMemoryMarketStore(),
    )
    request = query("worldbank")
    series, effective = ResearchWarehouse._snapshot_series(host, request, "ext_worldbank", "a" * 64)
    old = SnapshotSeries(
        series.service,
        "alice",
        series.scope,
        schema_identity="datahub-provider-native-v1:" + "a" * 64,
        units_identity="vendor-fields-retained-unverified-v1",
    )
    assert series.scope == old.scope
    assert series.dataset(effective) != old.dataset(effective)
    assert series.schema_identity.endswith(":official-numeric-v2")
    assert series.units_identity == "official-numeric-v2"
