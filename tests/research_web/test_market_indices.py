"""Index-set versioning must not contaminate the legacy fixed12 cache contract."""

import asyncio

import httpx
import pytest

from app.research_web.datahub.providers_market import (
    MarketProvider,
    MarketProviderError,
    _Reader,
    parse_index_daily,
)
from app.research_web.market_indices import CORE, TERMINAL, public_catalog, selected_indexes


def test_catalog_identity_and_legacy_scope():
    assert len(selected_indexes(CORE)) == 12
    assert len(selected_indexes(TERMINAL)) == 24
    c = public_catalog()
    assert len({row["asset"] for row in c["items"]}) == 24
    assert {"932000.SH", "000824.SH"} <= set(c["default_pins"])
    assert all(row["return_basis"] == "price_index" for row in c["items"])
    assert next(x[2] for x in selected_indexes(TERMINAL) if x[0] == "932000.SH") == "2.932000"
    with pytest.raises(ValueError):
        selected_indexes("arbitrary")


@pytest.mark.asyncio
async def test_provider_index_set_is_explicit_and_unknown_rejected_before_network():
    seen = []

    async def handle(request):
        seen.append(request)
        return httpx.Response(200, json={"rc": 0, "data": None})

    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        with pytest.raises(MarketProviderError):
            await provider.fetch("indices", index_set="arbitrary")
        assert not seen
        legacy = await provider.fetch("indices")
        extended = await provider.fetch("indices", index_set=TERMINAL)
    assert legacy["provider_total"] == 12
    assert extended["provider_total"] == 24
    assert extended["index_set"] == TERMINAL
    assert {r["asset"] for r in extended["rows"]} == {x[0] for x in selected_indexes(TERMINAL)}


def test_history_excludes_partial_today_preserves_zero_volume_and_rejects_duplicates():
    bars = parse_index_daily(
        [
            {"day": "2026-10-22", "close": "100", "volume": "0"},
            {"day": "2026-10-23", "close": "101"},
        ],
        "2026-10-23T12:00:00+08:00",
    )
    assert bars == [{"date": "2026-10-22", "close": 100, "volume": 0}]
    with pytest.raises(MarketProviderError):
        parse_index_daily([{"day": "2026-10-22", "close": 100}] * 2, "2026-10-23")
    with pytest.raises(MarketProviderError):
        parse_index_daily([{"day": "2026-10-22", "close": 0}], "2026-10-23")


@pytest.mark.asyncio
@pytest.mark.parametrize("previous,accepted", [(100, True), (101, False)])
async def test_daily_source_success_and_cross_vendor_mismatch(previous, accepted):
    async def handle(request):
        assert request.url.host == "money.finance.sina.com.cn"
        assert request.url.params["symbol"] == "sz399372"
        assert request.url.params["scale"] == "240"
        return httpx.Response(
            200,
            json=[
                {"day": "2026-10-22", "close": "100", "volume": "0"},
                {"day": "2026-10-23", "close": "999"},
            ],
        )

    row = {
        "asset": "399372.SZ",
        "price": 110,
        "previous_close": previous,
        "as_of": "2026-10-23T10:00:00+08:00",
    }
    async with MarketProvider(transport=httpx.MockTransport(handle)) as provider:
        reader = _Reader(provider._client, asyncio.Semaphore(1))
        await provider._index_daily(reader, row)
    assert bool(row["daily_bars"]) is accepted
    if accepted:
        assert row["daily_source"]["provider"] == "sina"
        assert row["daily_source"]["historical_pit_verified"] is False
        assert row["daily_bars"] == [{"date": "2026-10-22", "close": 100, "volume": 0}]
    else:
        assert row["daily_history_status"] == "unavailable"
        assert "daily_source" not in row
