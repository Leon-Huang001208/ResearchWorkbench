"""文档数据连接器 — DocumentConnector 实现."""
from connectors.document.cls import CLSDocumentConnector
from connectors.document.cninfo import CninfoDocumentConnector
from connectors.document.cnstock import CNStockDocumentConnector
from connectors.document.zq import ZQDocumentConnector

__all__ = [
    "CLSDocumentConnector",
    "CninfoDocumentConnector",
    "CNStockDocumentConnector",
    "ZQDocumentConnector",
]
