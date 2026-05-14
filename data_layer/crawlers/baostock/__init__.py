"""
BaoStock 数据爬取模块

提供与 AkShare 相同接口的 BaoStock 数据源适配器。
"""
from data_layer.crawlers.baostock.base import (
    BaoStockAdapter,
    BaoStockConfig,
    BaoStockError,
    DEFAULT_CONFIG,
)
from data_layer.crawlers.baostock.market import BaoStockMarketFetcher

__all__ = [
    "BaoStockAdapter",
    "BaoStockConfig",
    "BaoStockError",
    "BaoStockMarketFetcher",
    "DEFAULT_CONFIG",
]

