"""
Yahoo Finance 数据爬虫模块

提供全球市场数据获取，包括美股、港股、ETF等。
作为 AkShare/BaoStock 的补充数据源。

使用示例:
from data_layer.crawlers.yahoo import YahooAdapter

adapter = YahooAdapter()

data = adapter.market.get_historical_data("AAPL", period="1y")

info = adapter.fundamental.get_stock_info("AAPL")
"""

from .base import (
    DEFAULT_CONFIG,
    YahooAdapter,
    YahooConfig,
    YahooError,
    YahooFinancialData,
    YahooMarketData,
    YahooStockInfo,
)
from .utils import (
    convert_symbol,
    detect_market,
    get_supported_intervals,
    get_supported_periods,
    is_valid_yahoo_symbol,
)

__all__ = [
    "YahooConfig",
    "YahooMarketData",
    "YahooStockInfo",
    "YahooFinancialData",
    "YahooAdapter",
    "YahooError",
    "DEFAULT_CONFIG",
    "convert_symbol",
    "detect_market",
    "get_supported_intervals",
    "get_supported_periods",
    "is_valid_yahoo_symbol",
]
