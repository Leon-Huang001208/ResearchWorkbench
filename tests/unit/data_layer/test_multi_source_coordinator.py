from dataclasses import dataclass
from datetime import date, datetime, timedelta

from data_layer.coordinator.multi_source_coordinator import MultiSourceCoordinator
from data_layer.crawlers.akshare.base import MarketData


@dataclass
class FakeCacheRange:
    symbol: str
    start_date: date
    end_date: date


class FakeCache:
    def __init__(self, symbol: str, cached_data: list[MarketData], cache_end: date):
        self.symbol = symbol
        self.cached_data = cached_data
        self.cache_end = cache_end

    def get_cache_range(self, symbol: str):
        assert symbol == self.symbol
        return FakeCacheRange(
            symbol=symbol,
            start_date=self.cached_data[0].timestamp.date(),
            end_date=self.cache_end,
        )

    def calculate_missing_ranges(self, symbol: str, requested_start: date, requested_end: date):
        assert symbol == self.symbol
        return [(self.cache_end + timedelta(days=1), requested_end)]

    def get_cached_data(self, symbol: str, start_date: date, end_date: date):
        assert symbol == self.symbol
        return [
            item
            for item in self.cached_data
            if start_date <= item.timestamp.date() <= end_date
        ]


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


def test_recent_cache_tail_gap_returns_cache_without_live_source():
    symbol = "688981.SH"
    end_date = date.today()
    cache_end = end_date - timedelta(days=1)
    start_date = end_date - timedelta(days=365)
    cached_data = [
        _market_data(symbol, datetime.combine(start_date, datetime.min.time()), 50.0),
        _market_data(symbol, datetime.combine(cache_end, datetime.min.time()), 51.0),
    ]
    coordinator = MultiSourceCoordinator(cache=FakeCache(symbol, cached_data, cache_end))

    def fail_if_source_availability_is_checked():
        raise AssertionError("recent cache tail gap must not check live source availability")

    coordinator._get_available_sources = fail_if_source_availability_is_checked  # type: ignore[method-assign]

    result = coordinator.fetch_historical_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )

    assert result.success is True
    assert result.from_cache is True
    assert result.primary_source == "cache"
    assert result.data == cached_data


def test_stale_cache_tail_gap_still_requires_live_source():
    symbol = "688981.SH"
    end_date = date.today()
    cache_end = end_date - timedelta(days=10)
    start_date = end_date - timedelta(days=365)
    cached_data = [
        _market_data(symbol, datetime.combine(start_date, datetime.min.time()), 50.0),
        _market_data(symbol, datetime.combine(cache_end, datetime.min.time()), 51.0),
    ]
    coordinator = MultiSourceCoordinator(cache=FakeCache(symbol, cached_data, cache_end))
    coordinator._get_available_sources = lambda: []  # type: ignore[method-assign]

    result = coordinator.fetch_historical_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
    )

    assert result.success is False
    assert result.error_message == "No data sources available"


def test_force_refresh_does_not_use_recent_cache_tail_fast_path():
    symbol = "688981.SH"
    end_date = date.today()
    cache_end = end_date - timedelta(days=1)
    start_date = end_date - timedelta(days=365)
    cached_data = [
        _market_data(symbol, datetime.combine(start_date, datetime.min.time()), 50.0),
        _market_data(symbol, datetime.combine(cache_end, datetime.min.time()), 51.0),
    ]
    coordinator = MultiSourceCoordinator(cache=FakeCache(symbol, cached_data, cache_end))
    coordinator._get_available_sources = lambda: []  # type: ignore[method-assign]

    result = coordinator.fetch_historical_data(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        force_refresh=True,
    )

    assert result.success is False
    assert result.error_message == "No data sources available"
