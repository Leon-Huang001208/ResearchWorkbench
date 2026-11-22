"""Cash-flow financial ratios retain source identity, raw binding and first observation."""

import base64
import json
from copy import deepcopy
from datetime import UTC, date, datetime, timedelta

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.providers_baostock_cashflow import (
    CASH_FLOW_FIELDS,
    cash_flow_fields,
    cash_flow_metadata,
    cash_flow_projection,
)
from app.research_web.datahub.research_snapshot_store import SnapshotSeries
from app.research_web.market_store import (
    InMemoryMarketStore,
    MarketStoreError,
    MarketStoreService,
    StoreScope,
)


def query(**updates):
    return BusinessQuery(
        capability="financials",
        source="baostock",
        parameters={
            "asset": "600600.SH",
            "statements": ["cash_flow"],
            "periods": ["2026-06-30"],
        },
        **updates,
    )


def response():
    names = CASH_FLOW_FIELDS.split(",") if isinstance(CASH_FLOW_FIELDS, str) else CASH_FLOW_FIELDS
    native = dict.fromkeys(names, "0.125")
    native.update(code="sh.600600", pubDate="2026-08-28", statDate="2026-06-30")
    native["CAToAsset"] = ""
    native["CFOToNP"] = "-0.5"
    raw = json.dumps([native]).encode()
    rows, missing = cash_flow_projection(raw, "600600.SH", "2026-06-30")
    assert not missing
    return Result(
        rows=rows,
        raw=[raw],
        fields=cash_flow_fields(),
        metadata=cash_flow_metadata(),
        provider_id="baostock",
        provider_total=1,
        pagination_complete=True,
        status="complete",
    )


def series(allowed=None):
    scope = StoreScope("alice", "personal", "baostock", "a" * 64)
    service = MarketStoreService(InMemoryMarketStore(), allowed or (lambda *_args: True))
    return SnapshotSeries(service, "alice", scope), service, scope


def test_raw_bound_ratios_reopen_and_restore_keep_null_scale_and_scope():
    adapter, service, scope = series()
    result = response()
    assert adapter.ingest(query(), result)
    assert adapter.read(query()) is None
    display = query(purpose="display", quality="allow_stale")
    captured = SnapshotSeries(service, "alice", scope).read(display)
    assert captured.rows == result.rows
    envelope = json.loads(captured.raw[0])
    document = json.loads(base64.b64decode(envelope["payload"]["batch"]["originals"][0]["base64"]))
    assert [base64.b64decode(item["base64"]) for item in document["payloads"]] == result.raw
    assert captured.rows[0]["CAToAsset"] is None
    assert captured.rows[0]["CFOToNP"] == -0.5
    assert captured.metadata["reporting_basis"] == "unverified"
    assert captured.metadata["statement"] == "cash_flow"
    assert captured.metadata["projection_scope"] == "quarterly_cash_flow_ratios_native"
    assert captured.metadata["formal_backtest_eligible"] is False
    assert all(field["unit"] is None for field in captured.fields.values())
    frozen = service.freeze(
        "alice", scope, adapter.dataset(query()), date(1970, 1, 1), date(1970, 1, 1)
    )
    target = MarketStoreService(InMemoryMarketStore(), lambda *_args: True)
    assert target.export_restore("alice", scope, frozen.export()).digest == frozen.digest
    restored = SnapshotSeries(target, "alice", scope).read(display)
    assert restored.rows == captured.rows and restored.raw == captured.raw
    assert restored.fields == captured.fields and restored.metadata == captured.metadata


@pytest.mark.parametrize(
    "changed",
    [
        "value",
        "raw",
        "fields",
        "unit",
        "period",
        "asset",
        "publication",
        "schema",
        "basis",
        "pit",
        "scope",
        "count",
        "partial",
    ],
)
def test_warehouse_rejects_projection_or_semantics_unbound_to_original(changed):
    adapter, _, _ = series()
    good = response()
    assert adapter.ingest(query(), good)
    bad = deepcopy(good)
    if changed in {"value", "period", "asset", "publication"}:
        key = {
            "value": "CFOToNP",
            "period": "report_period",
            "asset": "asset",
            "publication": "publication_date",
        }[changed]
        bad.rows[0][key] = 99.0 if changed == "value" else "mismatch"
    elif changed == "raw":
        bad.raw = [b"[]"]
    elif changed in {"fields", "unit"}:
        bad.fields["CFOToNP"]["unit"] = "CNY"
    elif changed == "count":
        bad.provider_total = True
    elif changed == "partial":
        bad.status = "partial"
    else:
        key = {
            "schema": "schema_version",
            "basis": "reporting_basis",
            "pit": "historical_point_in_time",
            "scope": "projection_scope",
        }[changed]
        bad.metadata[key] = "forged"
    assert adapter.ingest(query(), bad) is None
    assert adapter.read(query(purpose="display", quality="allow_stale")).rows == good.rows


def test_cutoff_before_first_observation_does_not_make_publication_a_vintage():
    adapter, _, _ = series()
    assert adapter.ingest(query(), response())
    request = query(purpose="research", as_of=datetime.now(UTC) - timedelta(days=1))
    assert adapter.read(request) is None
    with pytest.raises(MarketStoreError):
        adapter.dataset(query(purpose="backtest", as_of=datetime.now(UTC)))


def test_cached_capture_still_checks_revoked_entitlement():
    allowed = [True]
    adapter, _, _ = series(lambda *_args: allowed[0])
    assert adapter.ingest(query(), response())
    allowed[0] = False
    with pytest.raises(MarketStoreError):
        adapter.read(query(purpose="display", quality="allow_stale"))
