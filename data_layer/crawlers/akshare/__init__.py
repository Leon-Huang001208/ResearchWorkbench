"""
AkShare 数据适配器模块

提供统一的金融数据接口，基于 AkShare 开源库。
支持：行情数据、财务数据、新闻数据、宏观数据。
"""
from .base import AkShareAdapter, FinancialData, MacroData, MarketData, NewsData, StockInfo
from .config import DEFAULT_CONFIG, AkShareConfig
from .financial import AkShareFinancialFetcher
from .macro import AkShareMacroFetcher
from .market import AkShareMarketFetcher
from .news import AkShareNewsFetcher

__all__ = [
    "AkShareConfig",
    "DEFAULT_CONFIG",
    "AkShareAdapter",
    "MarketData",
    "NewsData",
    "FinancialData",
    "MacroData",
    "StockInfo",
    "AkShareMarketFetcher",
    "AkShareFinancialFetcher",
    "AkShareNewsFetcher",
    "AkShareMacroFetcher",
]
