import sqlite3
from datetime import datetime

from data_layer.coordinator.cache_manager import MarketDataCache
from data_layer.crawlers.akshare.base import MarketData


def _market_data(symbol: str, timestamp: datetime, close: float) -> MarketData:
    return MarketData(
        symbol=symbol,
        timestamp=timestamp,
        open=close - 0.1,
        high=close + 0.2,
        low=close - 0.2,
        close=close,
        volume=1000,
        amount=close * 1000,
        turnover=1.2,
    )


def test_save_data_reads_existing_metadata_on_same_connection(tmp_path, monkeypatch):
    cache = MarketDataCache(cache_dir=tmp_path)
    symbol = "600000.SH"
    cache.save_data(symbol, [_market_data(symbol, datetime(2026, 6, 1), 10.0)], "seed")

    def fail_if_public_range_lookup_is_used(symbol: str):
        raise AssertionError("save_data must not open a nested SQLite connection")

    monkeypatch.setattr(cache, "get_cache_range", fail_if_public_range_lookup_is_used)

    cache.save_data(symbol, [_market_data(symbol, datetime(2026, 6, 2), 10.2)], "baostock")

    with sqlite3.connect(cache.db_path) as conn:
        cache_range = cache._get_cache_range_with_cursor(conn.cursor(), symbol)
    assert cache_range is not None
    assert cache_range.start_date.isoformat() == "2026-06-01"
    assert cache_range.end_date.isoformat() == "2026-06-02"
