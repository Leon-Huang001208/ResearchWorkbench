"""Intraday timestamps and units must never inherit daily chart semantics."""

import pytest

from app.research_web.asset_intraday import normalize_minutes


def point(time="09:31:00", **values):
    return {
        "代码": "SH603986",
        "时间": "2026-10-23 " + time,
        "open": 10,
        "high": 12,
        "low": 9,
        "close": 11,
        "vol": 100,
        "amount": 1100,
        "sectional_yclose": 10,
        "sectional_vol": 100,
        "sectional_amount": 1100,
        **values,
    }


def test_retains_minutes_and_uses_fixed_daily_reference():
    rows = [point(), point("09:32:00", vol=0, amount=0, yclose=11)]
    out = normalize_minutes(rows, "603986.SH", "2026-10-23")
    assert len(out["rows"]) == 2
    assert out["previous_close"] == 10
    assert out["rows"][1]["mean"] == 11
    assert out["rows"][1]["volume_lots"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"代码": "SH600000"},
        {"时间": "2026-10-22 09:31:00"},
        {"时间": "2026-10-23 12:00:00"},
        {"时间": "2026-10-23 09:31:37"},
        {"vol": -1},
        {"close": float("nan")},
        {"amount": None},
    ],
)
def test_rejects_invalid_rows(change):
    with pytest.raises(ValueError):
        normalize_minutes([point(**change)], "603986.SH", "2026-10-23")


def test_conflicting_duplicate_and_daily_reference_rejected():
    for rows in ([point(), point(close=12)], [point(), point("09:32:00", sectional_yclose=9)]):
        with pytest.raises(ValueError):
            normalize_minutes(rows, "603986.SH", "2026-10-23")


def test_all_zero_volume_mean_is_missing_not_zero():
    assert (
        normalize_minutes(
            [point(vol=0, amount=0, sectional_vol=0, sectional_amount=0)], "603986.SH", "2026-10-23"
        )["rows"][0]["mean"]
        is None
    )


@pytest.mark.asyncio
async def test_frozen_snapshot_coalescence_cache_and_unit_gate(tmp_path):
    import asyncio
    from types import SimpleNamespace

    from app.research_web.asset_intraday import Intraday
    from app.research_web.datahub.contracts import BusinessQuery
    from app.research_web.datahub.providers import Result
    from app.research_web.datahub.snapshots import Snapshots
    from app.research_web.store import Store

    store = Store(tmp_path)
    sid = store.create("fingpt", "intraday test")["id"]
    snapshots = Snapshots(store)
    calls = []

    async def query(session, call_id, request):
        assert isinstance(request, BusinessQuery)
        assert session == sid and request.source == "tinysoft"
        assert request.parameters["adjustment"] == "none"
        calls.append(request)
        await asyncio.sleep(0)
        minute = request.parameters["frequency"] == "1m"
        result = Result(
            rows=[point()] if minute else [{"时间": "2026-10-23"}],
            status="complete",
            pagination_complete=True,
            metadata={"intraday_field_dictionary": {"applied": True}},
            provider_id="tinysoft",
        )
        return snapshots.publish(
            sid, request, result, request_query=request, authorization_fingerprint="a" * 64
        )

    observation = {"id": "test", "session_id": sid, "asset": "603986.SH", "asset_type": "stock"}
    hub = SimpleNamespace(
        query=query,
        snapshots=snapshots,
        _authorize_query=lambda *a: None,
        source_configuration_digest=lambda source: "a" * 64,
    )
    workspace = SimpleNamespace(
        store=store,
        closed=False,
        tasks={},
        observation=lambda oid: observation,
        service=SimpleNamespace(datahub=hub),
    )
    service = Intraday(workspace)
    first, second = await asyncio.gather(service.load("test"), service.load("test"))
    assert first == second and len(calls) == 2
    assert first["trading_date"] == "2026-10-23"
    first["rows"].clear()
    assert len((await service.load("test"))["rows"]) == 1
    assert not workspace.tasks
    await service.close()
    with pytest.raises(ValueError, match="intraday_closed"):
        await service.load("test")


def test_vendor_dictionary_is_exact_not_a_guess():
    from app.research_web.datahub.intraday_contract import DEFINITIONS, validate_definitions
    from app.research_web.datahub.providers import ProviderError

    assert len(validate_definitions(DEFINITIONS)) == 64
    altered = [dict(row) for row in DEFINITIONS]
    altered[0]["单位/计算规则"] = "手"
    with pytest.raises(ProviderError, match="intraday_field_definition_changed"):
        validate_definitions(altered)


@pytest.mark.asyncio
async def test_route_uses_existing_json_error_contract():
    from types import SimpleNamespace

    from app.research_web.asset_routes import IntradayRequest, intraday
    from app.research_web.store import StoreError

    async def unavailable(*_args, **_kwargs):
        raise ValueError("intraday_units_unverified")

    request = SimpleNamespace(
        app=SimpleNamespace(
            state=SimpleNamespace(
                research=SimpleNamespace(
                    asset_workspace=SimpleNamespace(intraday=SimpleNamespace(load=unavailable))
                )
            )
        )
    )
    with pytest.raises(StoreError) as caught:
        await intraday("own-observation", IntradayRequest(), request)
    assert caught.value.code == "intraday_units_unverified"
    assert caught.value.status == 422
    assert "单位" in str(caught.value)


@pytest.mark.asyncio
async def test_composite_deadline_cancels_owned_wait_and_reports_uncertainty(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.research_web import asset_intraday as module
    from app.research_web.store import StoreError

    service = module.Intraday(SimpleNamespace())
    cancelled = asyncio.Event()

    async def pending(*_args):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    monkeypatch.setattr(module, "REQUEST_SECONDS", 0.001)
    monkeypatch.setattr(service, "_load", pending)
    with pytest.raises(StoreError) as caught:
        await service._bounded_load({}, None)
    assert caught.value.code == "intraday_deadline" and caught.value.status == 504
    assert cancelled.is_set()
