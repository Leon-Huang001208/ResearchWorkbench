"""SPDR source-native persistence, original binding and legacy-cache isolation."""

import base64
import json
from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.providers_external import (
    SPDR_METRIC_UNITS,
    SPDR_NUMERIC_CONTRACT,
    spdr_fields,
    spdr_projection,
)
from app.research_web.datahub.research_snapshot_store import SnapshotSeries
from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)
from app.research_web.market_store.models import parse_batch


def query(**updates):
    return BusinessQuery(
        capability="external_data",
        source="ext_spdr",
        parameters={"dataset": "gld", "arguments_json": "{}", "limit": 5},
        **updates,
    )


def response():
    values = ["US$ 123,456.78", "12.50", "400,000.00", "1"]
    raw = json.dumps(
        {
            "data": {
                key: {"value": value, "date": f"January {index + 1}, 2024"}
                for index, (key, value) in enumerate(zip(SPDR_METRIC_UNITS, values, strict=True))
            }
        }
    ).encode()
    return Result(
        rows=spdr_projection(raw),
        raw=[raw],
        fields=spdr_fields(),
        provider_id="ext_spdr",
        status="snapshot",
        provider_total=4,
        pagination_complete=True,
        metadata={
            "schema_version": SPDR_NUMERIC_CONTRACT,
            "provider_semantics_revision": SPDR_NUMERIC_CONTRACT,
            "upstream_id": "spdrgoldshares",
            "availability_basis": "first_observed",
            "revision_policy": "first_observed_not_historical_vintage",
            "historical_point_in_time": False,
            "formal_backtest_eligible": False,
            "units": dict(SPDR_METRIC_UNITS),
        },
    )


def binding(granted=None):
    scope = StoreScope("alice", "personal", "ext_spdr", "a" * 64)
    granted = granted if granted is not None else {"value": True}
    service = MarketStoreService(
        InMemoryMarketStore(),
        lambda actor, requested, _action: (
            granted["value"] and actor == "alice" and requested == scope
        ),
    )
    series = SnapshotSeries(
        service,
        "alice",
        scope,
        schema_identity=SPDR_NUMERIC_CONTRACT,
        units_identity=SPDR_NUMERIC_CONTRACT,
    )
    return scope, service, series


def test_complete_spdr_capture_freeze_restore_preserves_dates_units_and_original():
    scope, service, series = binding()
    original = response()
    request = query()
    assert series.ingest(request, original)
    assert series.read(request) is None
    display = request.model_copy(update={"purpose": "display", "quality": "allow_stale"})
    captured = series.read(display)
    assert captured.rows == original.rows
    assert captured.fields == original.fields
    assert len({row["reference_date"] for row in captured.rows}) == 4
    assert captured.metadata["formal_backtest_eligible"] is False
    assert captured.metadata["historical_point_in_time"] is False
    assert captured.metadata["availability_basis"] == "first_observed"
    frozen = service.freeze(
        "alice", scope, series.dataset(request), date(1970, 1, 1), date(1970, 1, 1)
    )
    batch = parse_batch(json.loads(frozen.payload)["batch"])
    document = json.loads(batch.originals[0].payload)
    assert base64.b64decode(document["payloads"][0]["base64"], validate=True) == original.raw[0]
    target = MarketStoreService(InMemoryMarketStore(), lambda *_args: True)
    assert target.export_restore("alice", scope, frozen.export()).digest == frozen.digest
    restored = SnapshotSeries(
        target,
        "alice",
        scope,
        schema_identity=SPDR_NUMERIC_CONTRACT,
        units_identity=SPDR_NUMERIC_CONTRACT,
    ).read(display)
    assert restored.rows == captured.rows
    assert restored.fields == captured.fields
    assert restored.raw == captured.raw
    assert series.ingest(query(as_of=datetime(2024, 2, 1, tzinfo=UTC)), original) is None
    assert series.read(query(as_of=datetime(2024, 2, 1, tzinfo=UTC))) is None
    with pytest.raises(MarketStoreError):
        series.read(query(purpose="backtest", as_of=datetime(2024, 2, 1, tzinfo=UTC)))


@pytest.mark.parametrize(
    "bad",
    [
        "schema",
        "upstream",
        "units",
        "availability",
        "pit",
        "revision",
        "fields",
        "forged-value",
        "bool-value",
        "original",
        "partial",
        "missing",
        "pagination",
        "no-raw",
        "empty",
        "total",
    ],
)
def test_spdr_capture_rejects_unverified_or_unbound_result(bad):
    _scope, _service, series = binding()
    result = response()
    if bad == "schema":
        result.metadata["schema_version"] = "legacy"
    elif bad == "upstream":
        result.metadata["upstream_id"] = "other"
    elif bad == "units":
        result.metadata["units"]["total_tonnes"] = "kg"
    elif bad == "availability":
        result.metadata["availability_basis"] = "published"
    elif bad == "pit":
        result.metadata["formal_backtest_eligible"] = True
    elif bad == "revision":
        result.metadata["revision_policy"] = "historical-vintage"
    elif bad == "fields":
        result.fields["value"]["unit"] = "CNY"
    elif bad == "forged-value":
        result.rows[0]["value"] += 1
    elif bad == "bool-value":
        result.rows[-1]["value"] = True
    elif bad == "original":
        body = json.loads(result.raw[0])
        body["data"]["total_tonnes"]["value"] = "14.50"
        result.raw = [json.dumps(body).encode()]
    elif bad == "partial":
        result.status = "partial"
    elif bad == "missing":
        result.missing = ["total_tonnes"]
    elif bad == "pagination":
        result.pagination_complete = False
    elif bad == "no-raw":
        result.raw = []
    elif bad == "empty":
        result.rows = []
        result.status = "empty"
    elif bad == "total":
        result.provider_total = 23
    assert series.ingest(query(), result) is None
    assert series.read(query()) is None


def test_spdr_capture_whitelist_and_current_authorization_remain_narrow():
    granted = {"value": True}
    _scope, _service, series = binding(granted)
    other = query().model_copy(update={"parameters": {"dataset": "other"}})
    override = query().model_copy(
        update={"parameters": {"dataset": "gld", "arguments_json": '{"query":{"product":"gldm"}}'}}
    )
    assert series.dataset(other) is None
    assert series.dataset(override) is None
    assert series.ingest(query(), response())
    granted["value"] = False
    with pytest.raises(MarketStoreError):
        series.read(query(purpose="display", quality="allow_stale"))


@pytest.mark.asyncio
async def test_legacy_spdr_cache_is_not_reused_but_original_receipt_is_readable(
    tmp_path, monkeypatch
):
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
        result = response()
        if len(calls) == 1:
            result.metadata = {}
        return result

    monkeypatch.setattr(providers, "fetch", fetch)
    store = Store(tmp_path)
    sid = store.create("claw", "SPDR cache contract")["id"]
    hub = DataHub(store)
    try:
        first = await hub.query(sid, "first", query())
        second = await hub.query(sid, "second", query())
        assert len(calls) == 2 and not second["cache_hit"]
        assert first["dataset_id"] != second["dataset_id"]
        again = await hub.query(sid, "first", query())
        assert again["dataset_id"] == first["dataset_id"] and len(calls) == 2
    finally:
        await hub.close()
