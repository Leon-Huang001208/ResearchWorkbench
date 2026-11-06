"""Global price indices use source-native bars and isolated cache identities."""

import json
from datetime import datetime, timedelta

import httpx
import pytest


def chart(symbol="^GSPC"):
    return {
        "chart": {
            "error": None,
            "result": [
                {
                    "meta": {
                        "symbol": symbol,
                        "instrumentType": "INDEX",
                        "currency": "USD",
                        "exchangeTimezoneName": "America/New_York",
                        "regularMarketPrice": 101,
                        "regularMarketTime": 1793966400,
                        "chartPreviousClose": 99,
                    },
                    "timestamp": [1793793600, 1793880000, 1793966400],
                    "indicators": {
                        "quote": [
                            {
                                "open": [98, 99, 100],
                                "high": [100, 102, 103],
                                "low": [97, 98, 99],
                                "close": [99, 100, 101],
                                "volume": [0, 200, 300],
                            }
                        ]
                    },
                }
            ],
        }
    }


def test_native_ohlcv_closed_days_and_partial_are_separate():
    from app.research_web.datahub.providers_global_indices import parse_chart

    row = parse_chart(chart(), "SP500", now=datetime.fromisoformat("2026-11-06T15:00:00-05:00"))
    assert row["daily_bars"][0]["volume"] == 0
    assert len(row["daily_bars"]) == 2
    assert row["partial_daily_bar"]["close"] == 101
    assert row["daily_bars"][-1]["close"] == 100
    assert row["source"]["historical_pit_verified"] is False
    assert row["return_basis"] == "price_index"
    assert row["previous_close"] == 100


@pytest.mark.parametrize("mutation", ["symbol", "etf", "nan", "duplicates", "timezone", "currency"])
def test_untrusted_chart_identity_and_shape_rejected(mutation):
    from app.research_web.datahub.providers_global_indices import GlobalIndexError, parse_chart

    payload = chart()
    data = payload["chart"]["result"][0]
    if mutation == "symbol":
        data["meta"]["symbol"] = "SPY"
    elif mutation == "etf":
        data["meta"]["instrumentType"] = "ETF"
    elif mutation == "nan":
        data["indicators"]["quote"][0]["close"][0] = float("nan")
    elif mutation == "duplicates":
        data["timestamp"][1] = data["timestamp"][0]
    elif mutation == "timezone":
        data["meta"]["exchangeTimezoneName"] = "Asia/Hong_Kong"
    else:
        data["meta"]["currency"] = "HKD"
    with pytest.raises(GlobalIndexError):
        parse_chart(payload, "SP500", now=datetime.fromisoformat("2026-11-09T18:00:00-05:00"))


def test_missing_ohlc_is_not_fabricated():
    from app.research_web.datahub.providers_global_indices import parse_chart

    payload = chart()
    payload["chart"]["result"][0]["indicators"]["quote"][0]["open"][0] = None
    row = parse_chart(payload, "SP500", now=datetime.fromisoformat("2026-11-09T18:00:00-05:00"))
    assert row["daily_bars"][0]["open"] is None
    assert any(gap["code"] == "ohlcv_incomplete" for gap in row["gaps"])


@pytest.mark.asyncio
async def test_fixed_nine_failure_rows_and_legacy_unchanged():
    from app.research_web.datahub.providers_market import MarketProvider
    from app.research_web.market_indices import CORE, TERMINAL, public_catalog, selected_indexes

    calls = []

    async def handle(request):
        calls.append(request.url)
        return httpx.Response(404, json={"chart": {"result": None, "error": {"code": "Not Found"}}})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("indices", index_set="global-v1")
    assert len(calls) == 9
    assert len(result["rows"]) == 9
    assert all(row["price"] is None and row["gaps"] for row in result["rows"])
    assert result["index_set"] == "global-v1"
    assert result["complete"] is False
    assert len(selected_indexes(CORE)) == 12
    assert len(selected_indexes(TERMINAL)) == 24
    assert len(public_catalog()["items"]) == 24


@pytest.mark.asyncio
async def test_cache_only_reads_and_distinct_account_set_keys(tmp_path):
    from app.research_web.market_service import MarketService

    class Provider:
        calls = 0

        async def fetch(self, section, **kwargs):
            self.calls += 1
            return {
                "rows": [],
                "summary": {},
                "complete": True,
                "pagination_complete": True,
                "index_set": kwargs["index_set"],
                "provider": "yahoo",
            }

        async def close(self):
            pass

    provider = Provider()
    service = MarketService(tmp_path / "one", provider=provider)
    assert service.overview() and provider.calls == 0
    result = await service.refresh(
        ["indices"], index_set="global-v1", idempotency_key="global-test-1"
    )
    import asyncio

    while service.request(result["request_id"])["status"] in {"pending", "running"}:
        await asyncio.sleep(0)
    assert provider.calls == 1
    assert "indices:global-v1" in service.overview()["sections"]
    restored = MarketService(tmp_path / "one")
    assert restored.overview()["sections"]["indices:global-v1"]["index_set"] == "global-v1"
    other = MarketService(tmp_path / "two")
    assert "indices:global-v1" not in other.overview()["sections"]
    await service.close()
    await restored.close()
    await other.close()


def tencent_chart(index_id):
    from app.research_web.datahub.providers_global_indices import TENCENT_SYMBOLS

    symbol = TENCENT_SYMBOLS[index_id]
    qt = [""] * 33
    qt[2:5] = [symbol[2:], "101", "100"]
    qt[30] = {
        "SP500": "2026-11-06 12:00:00",
        "HSI": "2026/11/06 12:00:00",
        "SSE": "20261106120000",
    }[index_id]
    qt[31:33] = ["1", "1"]
    return {
        "code": 0,
        "data": {
            symbol: {
                "qt": {symbol: qt},
                "day": [
                    ["2026-11-04", "98", "99", "100", "97", "0"],
                    ["2026-11-05", "99", "100", "102", "98", "200"],
                    ["2026-11-06", "100", "101", "103", "99", "300"],
                ],
            }
        },
    }


@pytest.mark.parametrize("index_id", ["SSE", "SP500", "HSI"])
def test_tencent_native_fields_and_market_local_timestamp(index_id):
    from app.research_web.datahub.providers_global_indices import parse_tencent_chart

    row = parse_tencent_chart(
        tencent_chart(index_id), index_id, now=datetime.fromisoformat("2026-11-06T20:00:00+00:00")
    )
    assert len(row["daily_bars"]) == (2 if index_id == "SP500" else 3)
    assert row["daily_bars"][0]["open"] == 98
    assert row["daily_bars"][0]["close"] == 99
    assert row["daily_bars"][0]["volume"] == 0
    assert row["source"]["provider"] == "tencent"
    assert row["source"]["volume_unit"] == "source_reported_volume"
    assert row["quote_trade_date"] == "2026-11-06"
    assert row["change_pct"] == 1


@pytest.mark.parametrize("mutation", ["adjusted", "identity", "nonfinite", "reverse"])
def test_tencent_rejects_adjusted_identity_and_bad_bars(mutation):
    from app.research_web.datahub.providers_global_indices import (
        GlobalIndexError,
        parse_tencent_chart,
    )

    payload = tencent_chart("SP500")
    data = payload["data"]["us.INX"]
    if mutation == "adjusted":
        data["qfqday"] = data.pop("day")
    elif mutation == "identity":
        data["qt"]["us.INX"][2] = ".NDX"
    elif mutation == "nonfinite":
        data["day"][0][2] = "nan"
    else:
        data["day"].reverse()
    with pytest.raises(GlobalIndexError):
        parse_tencent_chart(
            payload, "SP500", now=datetime.fromisoformat("2026-11-06T20:00:00+00:00")
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_payload", [None, [], "invalid"])
async def test_one_malformed_source_retains_other_eight_native_indices(bad_payload):
    from app.research_web.datahub.providers_global_indices import TENCENT_SYMBOLS
    from app.research_web.datahub.providers_market import MarketProvider
    from app.research_web.market_scoring.profiles import profile_for

    symbol_ids = {symbol: index_id for index_id, symbol in TENCENT_SYMBOLS.items()}

    async def handle(request):
        symbol = request.url.params["param"].split(",")[0]
        if symbol_ids[symbol] == "HSTECH":
            return httpx.Response(200, content=json.dumps(bad_payload))
        market = profile_for(symbol_ids[symbol])["market"]
        qt = [""] * 33
        qt[2:5] = [symbol[2:], "101", "100"]
        qt[30] = {"CN": "20261030120000", "US": "2026-10-30 12:00:00", "HK": "2026/10/30 12:00:00"}[
            market
        ]
        qt[31:33] = ["1", "1"]
        bars = [
            [
                (datetime(2026, 10, 9) + timedelta(days=i)).date().isoformat(),
                "99",
                "100" if i < 21 else "101",
                "102",
                "98",
                "0",
            ]
            for i in range(22)
        ]
        return httpx.Response(
            200, json={"code": 0, "data": {symbol: {"qt": {symbol: qt}, "day": bars}}}
        )

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        result = await provider.fetch("indices", index_set="global-v1")
    assert result["complete"] is False
    assert len(result["rows"]) == 9
    assert result["missing"]["indices"] == 1
    good = [row for row in result["rows"] if row["index_id"] != "HSTECH"]
    assert len(good) == 8
    assert all(
        row["price"] == 101 and len(row["daily_bars"]) == 22 and not row["gaps"] for row in good
    )
    failed = next(row for row in result["rows"] if row["index_id"] == "HSTECH")
    assert failed["price"] is None and not failed["daily_bars"]
    assert failed["gaps"][0]["code"] == "invalid_tencent_schema"
