"""Closed adjustment series through the real Broker/Provider, replacing only the SDK."""

import asyncio
import json
import sys
import threading
from datetime import date, timedelta
from types import ModuleType

import pytest

from app.research_web.datahub import BusinessQuery, DataHub
from app.research_web.datahub import providers_cjpy as provider
from app.research_web.store import Store, StoreError


@pytest.fixture
def sdk(monkeypatch):
    package = ModuleType("cjpy")
    calls = []
    definitions = [
        {
            "因子名称": "复权因子",
            "公式": "stock_Adjust_ForwardPriceFactor_Cal(EndT,firstday(), 1)",
            "说明": "",
        },
        {"因子名称": "上市日期", "公式": "datetostr(Firstday())", "说明": ""},
    ]

    def metadata(**kwargs):
        assert threading.current_thread().name.startswith("datahub-tinysoft")
        calls.append(("metadata", kwargs))
        return definitions

    def factors(**kwargs):
        assert threading.current_thread().name.startswith("datahub-tinysoft")
        calls.append(("factors", kwargs))
        dates = kwargs["date"]
        if isinstance(dates, str):
            dates = [dates]
        return [
            {
                "截止日": day.replace("-", ""),
                "代码": "SZ000001",
                "名称": "合成证券",
                "复权因子": 2.0,
                "上市日期": "2020-01-02",
            }
            for day in dates
        ]

    package.list_factors = metadata
    package.get_factor_data = factors
    monkeypatch.setitem(sys.modules, "cjpy", package)
    monkeypatch.setattr(provider, "_client", lambda _token: "synthetic-client")
    return package, calls, definitions


def query(series="adjustment_factors", **parameters):
    return BusinessQuery(
        capability="factor_macro",
        source="tinysoft",
        parameters={"series": series, **parameters},
    )


@pytest.mark.asyncio
async def test_closed_factor_series_normalizes_exact_days_and_keeps_original_evidence(sdk):
    _package, calls, _definitions = sdk
    request = query(assets=["000001.SZ"], dates=["2024-01-03", "2024-01-02"])
    result = await provider.fetch(request, token="synthetic-token")
    assert result.status == "complete"
    assert result.rows == [
        {"asset": "000001.SZ", "date": "2024-01-02", "factor": 2.0, "listing_date": "2020-01-02"},
        {"asset": "000001.SZ", "date": "2024-01-03", "factor": 2.0, "listing_date": "2020-01-02"},
    ]
    assert [item[0] for item in calls] == ["metadata", "factors"]
    assert calls[1][1]["factors"] == ["复权因子", "上市日期"]
    assert calls[1][1]["code"] == "SZ000001"
    assert "repo" not in calls[1][1]
    assert json.loads(result.raw[-1])[0]["复权因子"] == 2.0
    assert result.fields["factor"]["unit"] == "dimensionless"
    assert result.metadata["adjustment_contract"]["vendor_guarantee"] is False
    assert len(result.metadata["adjustment_contract"]["definition_sha256"]) == 64


@pytest.mark.asyncio
async def test_metadata_and_listing_are_fixed_closed_subseries(sdk):
    _package, calls, _definitions = sdk
    metadata = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
    assert metadata.status == "complete"
    contract = metadata.rows[0]
    assert contract["contract_version"] == "tinysoft-adjustment-v1"
    assert contract["qfq_formula"] == "P(t)*A(t)/A(as_of)"
    assert contract["hfq_formula"] == "P(t)*A(t)/A(listing_date)"
    assert [item[0] for item in calls] == ["metadata"]
    listing = await provider.fetch(
        query("listing_date", assets=["000001.SZ"]), token="synthetic-token"
    )
    assert listing.rows == [{"asset": "000001.SZ", "listing_date": "2020-01-02"}]
    assert calls[-1][1]["factors"] == ["上市日期"]


@pytest.mark.parametrize(
    "parameters",
    [
        {"series": "CPI"},
        {"series": "adjustment_metadata", "assets": ["000001.SZ"]},
        {"series": "listing_date", "assets": ["000001.SZ"], "dates": ["2024-01-02"]},
        {
            "series": "adjustment_factors",
            "assets": ["000001.SZ"],
            "dates": ["2024-01-02"],
            "start_date": "2024-01-02",
        },
        {
            "series": "adjustment_factors",
            "assets": ["000001.SZ"],
            "dates": ["2024-01-02", "2024-01-02"],
        },
        {"series": "adjustment_factors", "assets": ["000001.SZ"], "dates": ["20240102"]},
        {"series": "listing_date", "assets": ["510300.SH"]},
        {"series": "listing_date", "assets": ["000001.SH"]},
        {"series": "listing_date", "assets": ["920001.BJ"]},
        {"series": "listing_date", "assets": ["SH600000"]},
        {"series": "listing_date", "assets": ["000001.SZ", "600000.SH"]},
    ],
)
def test_tinysoft_factor_parameters_reject_nonclosed_requests(parameters):
    with pytest.raises(ValueError):
        BusinessQuery(capability="factor_macro", source="tinysoft", parameters=parameters)


@pytest.mark.asyncio
async def test_factor_dates_500_are_complete_and_501_are_rejected_before_sdk(sdk):
    days = [(date(2022, 1, 1) + timedelta(days=index)).isoformat() for index in range(501)]
    result = await provider.fetch(
        query(assets=["000001.SZ"], dates=days[:500]), token="synthetic-token"
    )
    assert result.status == "complete" and len(result.rows) == 500
    with pytest.raises(ValueError):
        query(assets=["000001.SZ"], dates=days)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect",
    [
        "zero",
        "negative",
        "boolean",
        "nan",
        "infinity",
        "duplicate",
        "extra",
        "missing",
        "asset",
        "date_conflict",
        "listing_conflict",
        "ipo_not_one",
    ],
)
async def test_factor_rows_fail_closed_for_invalid_or_inexact_evidence(sdk, defect):
    package, _calls, _definitions = sdk
    valid = package.get_factor_data

    def broken(**kwargs):
        rows = valid(**kwargs)
        if defect in {"zero", "negative", "boolean", "nan", "infinity"}:
            rows[0]["复权因子"] = {
                "zero": 0,
                "negative": -1,
                "boolean": True,
                "nan": float("nan"),
                "infinity": float("inf"),
            }[defect]
        elif defect == "duplicate":
            rows.append(dict(rows[0]))
        elif defect == "extra":
            rows.append({**rows[0], "截止日": "20240104"})
        elif defect == "missing":
            rows.pop()
        elif defect == "asset":
            rows[0]["代码"] = "SH600000"
        elif defect == "date_conflict":
            rows[0]["date"] = "2024-01-04"
        elif defect == "listing_conflict":
            rows[0]["上市日期"] = "2020-01-03"
        elif defect == "ipo_not_one":
            rows[0]["上市日期"] = "2024-01-02"
        return rows

    package.get_factor_data = broken
    result = await provider.fetch(
        query(assets=["000001.SZ"], dates=["2024-01-02", "2024-01-03"]), token="synthetic-token"
    )
    assert result.status == "failed"
    assert result.rows == [] and result.raw == []


@pytest.mark.asyncio
async def test_changed_or_absent_metadata_blocks_factor_sdk_call(sdk):
    package, calls, definitions = sdk
    definitions[0]["公式"] = "changed()"
    changed = await provider.fetch(
        query(assets=["000001.SZ"], dates=["2024-01-02"]), token="synthetic-token"
    )
    assert changed.limitations == ["factor_contract_unverified"]
    assert [item[0] for item in calls] == ["metadata"]
    package.list_factors = lambda **_kwargs: []
    missing = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
    assert missing.limitations == ["factor_contract_unverified"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "defect", ["missing_call", "schema", "duplicate", "description", "unhashable_name"]
)
async def test_unverified_metadata_has_one_stable_failure_and_no_factor_call(sdk, defect):
    package, calls, definitions = sdk
    if defect == "missing_call":
        del package.list_factors
    elif defect == "schema":
        package.list_factors = lambda **_kwargs: None
    elif defect == "duplicate":
        definitions.append(dict(definitions[0]))
    elif defect == "description":
        definitions[0]["说明"] = "changed semantics"
    else:
        definitions[0]["因子名称"] = []
    result = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
    assert result.status == "failed"
    assert result.limitations == ["factor_contract_unverified"]
    assert all(operation != "factors" for operation, _ in calls)


@pytest.mark.asyncio
async def test_metadata_deadline_holds_single_sdk_capacity_until_real_completion(sdk, monkeypatch):
    package, calls, _definitions = sdk
    started, release = threading.Event(), threading.Event()
    original = package.list_factors

    def blocked(**kwargs):
        started.set()
        release.wait(timeout=2)
        return original(**kwargs)

    package.list_factors = blocked
    monkeypatch.setattr(provider, "DEADLINE", 0.01)
    try:
        result = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
        assert started.is_set()
        assert result.limitations == ["deadline"]
        assert len(provider.active_futures()) == 1
        assert all(operation != "factors" for operation, _ in calls)
        blocked_result = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
        assert blocked_result.limitations == ["provider_busy"]
    finally:
        release.set()
        assert await provider.wait_for_idle(timeout=1) is True


@pytest.mark.asyncio
async def test_cancelled_wait_retains_real_future_witness_until_drain(sdk):
    package, _calls, _definitions = sdk
    started, release = threading.Event(), threading.Event()

    def blocked(**_kwargs):
        started.set()
        release.wait(timeout=2)
        return []

    package.list_factors = blocked
    task = asyncio.create_task(
        provider.fetch(query("adjustment_metadata"), token="synthetic-token")
    )
    try:
        for _ in range(100):
            if started.is_set():
                break
            await asyncio.sleep(0.001)
        assert started.is_set()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert len(provider.active_futures()) == 1
        assert await provider.wait_for_idle(timeout=0.005) is False
        busy = await provider.fetch(query("adjustment_metadata"), token="synthetic-token")
        assert busy.limitations == ["provider_busy"]
    finally:
        release.set()
        assert await provider.wait_for_idle(timeout=1) is True
    assert provider.active_futures() == ()


@pytest.mark.asyncio
async def test_factor_real_datahub_snapshot_cache_copy_and_grant_recheck(
    tmp_path, monkeypatch, sdk
):
    from app.research_web.datahub import catalog

    _package, calls, _definitions = sdk
    monkeypatch.setattr(catalog, "_dependency_status", lambda *_args: (True, None))
    store = Store(tmp_path)
    sid = store.create("claw", "synthetic adjustment")["id"]
    copied_sid = store.create("claw", "copied adjustment")["id"]
    hub = DataHub(store)
    status = {"configured": True, "secret_configured": True}
    monkeypatch.setattr(hub.connections, "statuses", lambda: {"tinysoft": dict(status)})
    monkeypatch.setattr(hub.connections, "source_status", lambda _source: dict(status))
    monkeypatch.setattr(hub.connections, "configuration_revision", lambda _source: "synthetic-v1")
    monkeypatch.setattr(hub.connections, "read_source_secret", lambda _source: "synthetic-token")
    try:
        request = query(assets=["000001.SZ"], dates=["2024-01-02"])
        first = await hub.query(sid, "factor-first", request)
        assert first["provider"] == "tinysoft"
        assert first["status"] == "complete"
        assert first["row_count"] == 1
        contract = first["provider_metadata"]["adjustment_contract"]
        assert first["fields"]["factor"]["unit"] == "dimensionless"
        cached = await hub.query(sid, "factor-cached", request)
        assert cached["cache_hit"] is True
        assert cached["provider_metadata"]["adjustment_contract"] == contract
        assert len(calls) == 2
        copied = hub.copy_selected(sid, copied_sid, [first["dataset_id"]])
        assert copied[0]["provider_metadata"]["adjustment_contract"] == contract
        assert copied[0]["fields"] == first["fields"]
        status["configured"] = False
        with pytest.raises(StoreError) as denied:
            await hub.query(sid, "factor-denied", request)
        assert denied.value.code == "data_capability_unavailable"
        assert len(calls) == 2
    finally:
        await hub.close()
