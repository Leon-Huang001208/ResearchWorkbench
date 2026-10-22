"""Market-wide snapshot integrity, identity and bounded transport contracts."""

import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.research_web.datahub.providers_market import MarketProvider, MarketProviderError

STAMP = int(datetime(2026, 10, 22, 10, tzinfo=ZoneInfo("Asia/Shanghai")).timestamp())


def quote(code, market=0, **values):
    return {
        "f12": code,
        "f13": market,
        "f14": "测试",
        "f124": STAMP,
        "f2": 10,
        "f3": 0,
        "f4": 0,
        "f5": 2,
        "f6": 2000,
        **values,
    }


def transport_for(scopes, mutate=None):
    async def handle(request):
        params = request.url.params
        scope = params.get("fs", "")
        rows = scopes.get(scope, [])
        page, size = int(params.get("pn", 1)), int(params.get("pz", 100))
        data = {"total": len(rows), "diff": rows[(page - 1) * size : page * size]}
        if mutate:
            data = mutate(scope, page, data)
        return httpx.Response(200, json={"rc": 0, "data": data})

    return httpx.MockTransport(handle)


SH = "m:1 t:2,m:1 t:23"
SZ = "m:0 t:6,m:0 t:80"
BJ = "m:0 t:81 s:2048"


@pytest.mark.asyncio
async def test_previous_day_quote_never_enters_current_day_breadth_or_amount():
    scopes = {
        SH: [quote("600001", 1, f124=STAMP - 86400, f3=9)],
        SZ: [quote("000001", f3=0)],
        BJ: [quote("920001", f3=-1)],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["pagination_complete"] is True
    assert result["summary"]["breadth"] == {"up": 0, "down": 1, "flat": 1, "unknown": 1, "total": 3}
    assert result["summary"]["amount"] is None
    assert result["missing"]["quote_date"] == 1
    assert result["temporal_complete"] is False
    assert all(row["asset"] != "600001.SH" for row in result["summary"]["gainers"])


@pytest.mark.asyncio
async def test_twelve_index_comparison_excludes_previous_day_series():
    async def handle(request):
        code = request.url.params["secid"].split(".")[1]
        old = code == "000001"
        if request.url.path.endswith("stock/get"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "f57": code,
                        "f43": 101,
                        "f60": 100,
                        "f86": STAMP - (86400 if old else 0),
                        "f170": 1,
                    }
                },
            )
        day = "2026-10-21" if old else "2026-10-22"
        return httpx.Response(
            200, json={"data": {"code": code, "trends": [f"{day} 09:31,100,101,101,100,1,100,100"]}}
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("indices")
    old = next(row for row in result["rows"] if row["asset"] == "000001.SH")
    assert old["series"] == []
    assert result["missing"]["quote_date"] == 1
    assert result["temporal_complete"] is False


@pytest.mark.asyncio
async def test_full_universe_exceeds_legacy_5000_and_keeps_beijing_identity():
    scopes = {
        SH: [quote(f"{600000 + i}", 1) for i in range(2501)],
        SZ: [quote(f"{i:06}") for i in range(2501)],
        BJ: [quote("920001"), quote("810011")],
    }
    provider = MarketProvider(transport=transport_for(scopes))
    try:
        result = await provider.fetch("quotes")
    finally:
        await provider.close()
    assert result["complete"] is True
    assert len(result["rows"]) == result["provider_total"] == 5004
    assert {r["asset"] for r in result["rows"] if r["exchange"] == "BJ"} == {
        "920001.BJ",
        "810011.BJ",
    }
    assert result["summary"]["breadth"]["flat"] == 5004
    assert result["rows"][0]["volume"] == 200
    assert result["rows"][0]["change_pct"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["duplicate", "missing", "changing_total"])
async def test_bad_pagination_never_publishes_full_market_statistics(failure):
    scopes = {
        SH: [quote(f"{600000 + i}", 1) for i in range(101)],
        SZ: [quote("000001")],
        BJ: [quote("920001")],
    }

    def mutate(scope, page, data):
        if scope == SH and page == 2:
            if failure == "duplicate":
                data["diff"] = [quote("600000", 1)]
            elif failure == "missing":
                data["diff"] = []
            else:
                data["total"] += 1
        return data

    async with MarketProvider(transport=transport_for(scopes, mutate)) as provider:
        result = await provider.fetch("quotes")
    assert result["complete"] is False
    assert result["pagination_complete"] is False
    assert "breadth" not in result["summary"]
    assert result["limitations"]


@pytest.mark.asyncio
async def test_missing_quote_is_not_flat_and_nonfinite_values_are_null():
    scopes = {
        SH: [quote("600001", 1, f2="-", f3="-", f6="-")],
        SZ: [quote("000001", f3=0, f9="NaN")],
        BJ: [quote("920001", f3=1)],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["summary"]["breadth"] == {"up": 1, "down": 0, "flat": 1, "unknown": 1, "total": 3}
    assert result["rows"][1]["pe_dynamic"] is None
    assert result["rows"][0]["as_of"].endswith("+08:00")
    assert result["missing"]["quote"] == 1


@pytest.mark.asyncio
async def test_wrong_exchange_identity_is_rejected():
    async with MarketProvider(transport=transport_for({SH: [quote("600001", 0)]})) as provider:
        result = await provider.fetch("quotes")
    assert result["complete"] is False
    assert not result["rows"]
    assert "breadth" not in result["summary"]


@pytest.mark.asyncio
async def test_members_keep_raw_market_for_snapshot_intersection():
    async with MarketProvider(
        transport=transport_for({"b:BK0420 f:!50": [quote("920001")]})
    ) as provider:
        result = await provider.fetch("members", board_id="BK0420")
    assert result["rows"] == [{"code": "920001", "market": 0, "name": "测试"}]
    assert result["limitations"]


@pytest.mark.asyncio
async def test_invalid_arguments_do_not_touch_network():
    called = False

    async def handler(request):
        nonlocal called
        called = True
        raise AssertionError("must not call")

    async with MarketProvider(transport=httpx.MockTransport(handler)) as provider:
        for kwargs in (
            {"section": "other"},
            {"section": "members", "board_id": "BK1 http://x"},
            {"section": "flows", "kind": "arbitrary"},
            {"section": "flows", "period": "yesterday"},
        ):
            with pytest.raises(MarketProviderError):
                await provider.fetch(**kwargs)
    assert called is False


@pytest.mark.asyncio
async def test_upstream_request_cancel_reaches_transport():
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def handler(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    async with MarketProvider(transport=httpx.MockTransport(handler)) as provider:
        task = asyncio.create_task(provider.fetch("industry"))
        await entered.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_total_limit_and_redirect_fail_closed():
    for response in (
        httpx.Response(200, json={"data": {"total": 20001, "diff": []}}),
        httpx.Response(302, headers={"location": "https://example.com"}),
    ):
        async with MarketProvider(
            transport=httpx.MockTransport(lambda request, result=response: result)
        ) as provider:
            with pytest.raises(MarketProviderError):
                await provider.fetch("industry")


@pytest.mark.asyncio
async def test_flow_fields_follow_selected_period():
    rows = [
        {
            "f12": "BK0420",
            "f14": "测试板块",
            "f124": STAMP,
            "f109": 1.5,
            "f164": 12,
            "f165": 3,
            "f166": 4,
            "f168": 8,
            "f170": -4,
            "f172": -8,
        }
    ]
    async with MarketProvider(transport=transport_for({"m:90 t:2": rows})) as provider:
        result = await provider.fetch("flows", period="5d")
    row = result["rows"][0]
    assert row["main_net"] == 12
    assert row["super_net"] == 4
    assert row["large_net"] == 8
    assert row["change_pct"] == 1.5
    assert result["summary"]["period"] == "5d"


@pytest.mark.asyncio
async def test_index_no_data_keeps_all_twelve_missing_entries():
    async with MarketProvider(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"rc": 100, "data": None})
        )
    ) as provider:
        result = await provider.fetch("indices")
    assert len(result["rows"]) == 12
    assert result["complete"] is False
    assert result["missing"]["indices"] == 12
    assert any(row["asset"] == "899050.BJ" for row in result["rows"])


def test_calendar_decodes_actual_sina_fixed_alias_wrapper():
    # Downloaded payload is data only: the trailing known alias is not executed.
    from app.research_web.datahub.providers_market import _calendar_payload

    assert _calendar_payload(b'var datelist="LC/AAApNDX";var KLC_TD_SH=datelist;') == "LC/AAApNDX"
    with pytest.raises(MarketProviderError):
        _calendar_payload(b'var datelist="LC/AAApNDX";alert("unexpected");')


@pytest.mark.asyncio
async def test_calendar_validity_alias_is_available_to_service(monkeypatch):
    monkeypatch.setattr(
        MarketProvider, "_decode_calendar", staticmethod(lambda raw: ["2026-10-22", "2027-01-01"])
    )
    async with MarketProvider(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="fixture"))
    ) as provider:
        result = await provider.fetch("calendar")
    assert result["summary"]["valid_until"] == "2027-01-01"


@pytest.mark.asyncio
async def test_index_series_never_normalizes_another_trading_day():
    async def handle(request):
        code = request.url.params["secid"].split(".")[1]
        if request.url.path.endswith("stock/get"):
            return httpx.Response(
                200, json={"data": {"f57": code, "f43": 101, "f60": 100, "f86": STAMP, "f170": 1}}
            )
        return httpx.Response(
            200,
            json={"data": {"code": code, "trends": ["2026-10-21 09:31,100,101,101,100,1,100,100"]}},
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("indices")
    assert result["complete"] is False
    assert all(row["series"] == [] for row in result["rows"])


@pytest.mark.asyncio
async def test_response_bytes_limit_is_enforced(monkeypatch):
    from app.research_web.datahub import providers_market

    monkeypatch.setattr(providers_market, "MAX_RESPONSE_BYTES", 8)
    async with MarketProvider(transport=transport_for({})) as provider:
        with pytest.raises(MarketProviderError, match="上限"):
            await provider.fetch("industry")


@pytest.mark.asyncio
async def test_total_deadline_cancels_all_underlying_requests():
    cancelled = asyncio.Event()

    async def handle(request):
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async with MarketProvider(transport=httpx.MockTransport(handle), deadline=0.01) as provider:
        with pytest.raises(MarketProviderError) as failure:
            await provider.fetch("quotes")
    assert failure.value.code == "market_timeout"
    assert cancelled.is_set()
