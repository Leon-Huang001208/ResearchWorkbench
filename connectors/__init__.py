"""数据源连接器实现 — MarketDataConnector + DocumentConnector 的具体实现.

每个 connector 包装现有 adapter/crawler，实现统一的 BaseConnector 接口。
Wrapper-first 策略：内部委托给现有模块，不立即重写内部逻辑。
"""

from connectors.document.cls import CLSDocumentConnector
from connectors.document.cninfo import CninfoDocumentConnector
from connectors.document.cnstock import CNStockDocumentConnector
from connectors.document.zq import ZQDocumentConnector
from connectors.market.akshare import AkShareMarketConnector
from connectors.market.baostock import BaostockMarketConnector
from connectors.market.cjpy import CjpyMarketConnector
from connectors.market.csindex import CsindexMarketConnector
from connectors.market.szse import SzseMarketConnector
from connectors.market.wind import WindMarketConnector
from connectors.market.yahoo import YahooMarketConnector

__all__ = [
    "AkShareMarketConnector",
    "BaostockMarketConnector",
    "CjpyMarketConnector",
    "CLSDocumentConnector",
    "CninfoDocumentConnector",
    "CNStockDocumentConnector",
    "CsindexMarketConnector",
    "SzseMarketConnector",
    "WindMarketConnector",
    "YahooMarketConnector",
    "ZQDocumentConnector",
]
