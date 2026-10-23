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


SH = "m:1 t:2 f:!2,m:1 t:23 f:!2"
SZ = "m:0 t:6 f:!2,m:0 t:80 f:!2"
BJ = "m:0 t:81 s:262144 f:!2"


@pytest.mark.asyncio
async def test_limits_use_vendor_prices_including_st_and_beijing_not_percent_thresholds():
    scopes = {
        SH: [quote("600000", 1, f2=10.63, f350=10.63, f351=8.69, f292=5)],
        SZ: [quote("002717", f2=0.41, f3=-8.89, f350=0.50, f351=0.41, f292=5)],
        BJ: [quote("920001", f2=13.4, f3=30.0, f350=13.4, f351=7.22, f292=5)],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["summary"]["limit_up"] == 2
    assert result["summary"]["limit_down"] == 1
    assert result["missing"]["price_limit_status"] == 0
    assert result["rows"][1]["limit_status"] == "down"


@pytest.mark.asyncio
async def test_unknown_trading_state_cannot_certify_a_price_limit():
    scopes = {
        SH: [quote("600000", 1, f350=10, f351=8)],
        SZ: [quote("000001")],
        BJ: [quote("920001")],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["rows"][0]["limit_status"] == "unknown"
    assert result["summary"]["limit_up"] is None


@pytest.mark.asyncio
async def test_absent_invalid_limit_prices_never_become_zero_limit_counts():
    scopes = {
        SH: [quote("600000", 1, f350=0, f351=0)],
        SZ: [quote("000001", f350=8, f351=12)],
        BJ: [quote("920001")],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["summary"]["limit_up"] is None
    assert result["summary"]["limit_unknown"] == 3
    assert all(row["limit_status"] == "unknown" for row in result["rows"])


@pytest.mark.asyncio
async def test_details_have_a_separate_hundred_request_capacity():
    count = 0

    async def handle(request):
        nonlocal count
        if request.url.path.endswith("/stock/get"):
            count += 1
            return httpx.Response(200, json={"data": None})
        scope = request.url.params["fs"]
        rows = (
            [quote(str(600000 + i), 1, f6=None) for i in range(105)]
            if scope == SH
            else [quote("000001")] if scope == SZ else [quote("920001")]
        )
        page = int(request.url.params["pn"])
        return httpx.Response(
            200, json={"data": {"total": len(rows), "diff": rows[(page - 1) * 100 : page * 100]}}
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    assert count == 100 and result["complete"] and len(result["rows"]) == 107
    assert result["summary"]["amount_missing"] == 105


@pytest.mark.asyncio
async def test_cancellation_reaches_the_detail_transport():
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def handle(request):
        if request.url.path.endswith("/stock/get"):
            entered.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        scope = request.url.params["fs"]
        rows = (
            [quote("601326", 1, f6=None)]
            if scope == SH
            else [quote("000001")] if scope == SZ else [quote("920001")]
        )
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        task = asyncio.create_task(provider.fetch("quotes"))
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert cancelled.is_set()


@pytest.mark.parametrize("state,basis", [(5, "quote"), (6, "suspended_reference")])
@pytest.mark.asyncio
async def test_detail_repairs_normal_price_change_and_labels_suspended_f43(state, basis):
    async def handle(request):
        if request.url.path.endswith("/stock/get"):
            return httpx.Response(
                200,
                json={
                    "data": {
                        "f57": "601326",
                        "f58": "测试",
                        "f43": 3.57,
                        "f169": 0.2,
                        "f170": 5.93,
                        "f86": STAMP,
                    }
                },
            )
        scope = request.url.params["fs"]
        rows = (
            [quote("601326", 1, f292=state, f2=None, f3=None, f4=None)]
            if scope == SH
            else [quote("000001")] if scope == SZ else [quote("920001")]
        )
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    row = result["rows"][0]
    assert row["price"] == 3.57 and row["price_basis"] == basis
    if state == 5:
        assert row["change_pct"] == 5.93 and row["change"] == 0.2
        assert result["summary"]["up"] == 1 and result["summary"]["unknown"] == 0


@pytest.mark.asyncio
async def test_suspended_detail_recovers_real_zero_amount_and_scaled_reference():
    async def handle(request):
        if request.url.path.endswith("/stock/get"):
            assert request.url.params["fltt"] == "2"
            return httpx.Response(
                200,
                json={
                    "data": {
                        "f57": "601326",
                        "f58": "测试",
                        "f59": 2,
                        "f43": 0,
                        "f301": 357,
                        "f60": 3.57,
                        "f47": 0,
                        "f48": 0,
                        "f86": STAMP,
                        "f292": 6,
                    }
                },
            )
        scope = request.url.params["fs"]
        rows = (
            [quote("601326", 1, f292=6, f2="-", f3="-", f6="-", f5="-")]
            if scope == SH
            else (
                [quote("000001")]
                if scope == SZ
                else [quote("920285", f292=9, f26=20261023, f2="-", f3="-", f6=0)]
            )
        )
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    row = result["rows"][0]
    assert row["price"] == 3.57 and row["amount"] == 0 and row["volume"] == 0
    assert row["trade_status"] == "suspended" and row["price_basis"] == "last_traded_reference"
    assert result["summary"]["amount"] == 2000
    assert result["summary"]["suspended"] == 1 and result["summary"]["unlisted"] == 1
    assert result["summary"]["flat"] == 1 and result["summary"]["unknown"] == 0


@pytest.mark.asyncio
async def test_market_flow_uses_working_guest_and_owns_its_daily_metadata():
    async def handle(request):
        assert request.url.host == "82.push2.eastmoney.com"
        assert request.url.path == "/webguest/api/qt/stock/fflow/daykline/get"
        return httpx.Response(
            200, json={"data": {"klines": ["2026-10-22,-10,1,9,-4,-6,0,0,0,0,0,3658,-1,11357,-2"]}}
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        from app.research_web.datahub.providers_market import _Reader

        result = await provider._market_flow(_Reader(provider._client, provider._semaphore))
    assert result["row_count"] == 1 and result["trade_date"] == "2026-10-22"
    assert result["rows"][0]["main_net"] == -10
    assert result["source_url"].startswith("https://") and result["retrieved_at"]


@pytest.mark.parametrize("bad", ["identity", "name", "old_date", "null", "negative"])
@pytest.mark.asyncio
async def test_quote_detail_never_repairs_wrong_identity_date_or_missing_value(bad):
    async def handle(request):
        if request.url.path.endswith("/stock/get"):
            detail = {"f57": "601326", "f58": "测试", "f48": 0, "f86": STAMP}
            if bad == "identity":
                detail["f57"] = "600000"
            if bad == "name":
                detail["f58"] = "其他"
            if bad == "old_date":
                detail["f86"] -= 86400
            if bad == "null":
                detail["f48"] = None
            if bad == "negative":
                detail["f48"] = -1
            return httpx.Response(200, json={"data": detail})
        scope = request.url.params["fs"]
        rows = (
            [quote("601326", 1, f6=None)]
            if scope == SH
            else [quote("000001")] if scope == SZ else [quote("920001")]
        )
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    assert result["complete"] and result["rows"][0]["amount"] is None
    assert result["summary"]["amount"] is None and result["missing"]["amount"] == 1


@pytest.mark.parametrize(
    "lines",
    [
        [],
        ["2026-10-22,-,1,2,3,4,0,0,0,0,0,1,2,3,4"],
        ["bad"],
        ["2026-10-22,1,2,3,4,5,0,0,0,0,0,1,2,3,4"] * 2,
    ],
)
@pytest.mark.asyncio
async def test_market_flow_rejects_empty_null_malformed_and_duplicate_days(lines):
    from app.research_web.datahub.providers_market import _Reader

    async def handle(request):
        return httpx.Response(200, json={"data": {"klines": lines}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        with pytest.raises(MarketProviderError):
            await provider._market_flow(_Reader(provider._client, provider._semaphore))


@pytest.mark.asyncio
async def test_current_site_universe_preserves_halts_without_legacy_instruments():
    current = {
        "m:1 t:2 f:!2,m:1 t:23 f:!2": [
            quote("600000", 1),
            quote("600012", 1, f2="-", f3="-", f6=0),
        ],
        "m:0 t:6 f:!2,m:0 t:80 f:!2": [quote("000001")],
        "m:0 t:81 s:262144 f:!2": [quote("920001")],
    }

    async def handle(request):
        if request.url.path.endswith("/stock/get"):
            return httpx.Response(200, json={"data": None})
        scope = request.url.params["fs"]
        rows = current.get(
            scope, [quote("600001", 1, f14="历史退市"), quote("810011", f14="非普通股")]
        )
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    assert result["complete"] is True
    assert {row["asset"] for row in result["rows"]} == {
        "600000.SH",
        "600012.SH",
        "000001.SZ",
        "920001.BJ",
    }
    assert result["summary"]["breadth"]["unknown"] == 1
    assert result["summary"]["amount"] == 6000


@pytest.mark.asyncio
async def test_source_listing_dates_distinguish_upcoming_from_unknown_quotes():
    scopes = {
        SH: [quote("600000", 1, f26=20000101)],
        SZ: [quote("000001", f26=19910403)],
        BJ: [quote("920285", f26=20261023, f2=20, f3=10, f6=100)],
    }
    async with MarketProvider(transport=transport_for(scopes)) as provider:
        result = await provider.fetch("quotes")
    assert result["rows"][-1]["listing_date"] == "2026-10-23"
    assert result["summary"]["upcoming_count"] == 1
    assert result["summary"]["breadth"]["unknown"] == 0
    assert result["summary"]["breadth"]["unlisted"] == 1
    assert result["summary"]["amount"] == 4000
    assert result["summary"]["amount_scope_count"] == 2
    assert any("待上市" in text for text in result["limitations"])


@pytest.mark.asyncio
async def test_public_guest_quotes_work_when_old_api_disconnects():
    scopes = {SH: [quote("600001", 1)], SZ: [quote("000001")], BJ: [quote("920001")]}

    async def handle(request):
        if request.url.path != "/webguest/api/qt/clist/get":
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        rows = scopes[request.url.params["fs"]]
        return httpx.Response(200, json={"data": {"total": len(rows), "diff": rows}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("quotes")
    assert result["complete"] is True
    assert len(result["rows"]) == 3
    assert result["summary"]["breadth"]["total"] == 3


@pytest.mark.asyncio
async def test_index_intraday_uses_public_guest_when_history_disconnects():
    async def handle(request):
        code = request.url.params["secid"].split(".")[1]
        if request.url.host != "82.push2.eastmoney.com":
            raise httpx.RemoteProtocolError("Server disconnected without sending a response.")
        if request.url.path == "/webguest/api/qt/stock/get":
            return httpx.Response(
                200, json={"data": {"f57": code, "f43": 101, "f60": 100, "f86": STAMP, "f170": 1}}
            )
        assert request.url.path == "/webguest/api/qt/stock/trends2/get"
        return httpx.Response(
            200,
            json={"data": {"code": code, "trends": ["2026-10-22 09:31,100,101,101,100,1,100,100"]}},
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("indices")
    assert result["complete"] is True
    assert all(row["series"] for row in result["rows"])


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
    assert result["summary"]["breadth"] == {
        "up": 0,
        "down": 1,
        "flat": 1,
        "unknown": 1,
        "total": 3,
        "suspended": 0,
        "unlisted": 0,
    }
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
    assert result["summary"]["breadth"] == {
        "up": 1,
        "down": 0,
        "flat": 1,
        "unknown": 1,
        "total": 3,
        "suspended": 0,
        "unlisted": 0,
    }
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
