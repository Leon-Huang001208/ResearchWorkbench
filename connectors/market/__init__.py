"""市场数据连接器 — MarketDataConnector 实现."""
from connectors.market.akshare import AkShareMarketConnector
from connectors.market.baostock import BaostockMarketConnector
from connectors.market.csindex import CsindexMarketConnector
from connectors.market.szse import SzseMarketConnector
from connectors.market.wind import WindMarketConnector
from connectors.market.yahoo import YahooMarketConnector

__all__ = [
    "AkShareMarketConnector",
    "BaostockMarketConnector",
    "CsindexMarketConnector",
    "SzseMarketConnector",
    "WindMarketConnector",
    "YahooMarketConnector",
]
