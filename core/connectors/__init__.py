"""数据源连接器 — BaseConnector + DocumentConnector + MarketDataConnector + ConnectorRegistry."""

from core.connectors.base import (
    BaseConnector,
    DiscoveryItem,
    DocumentConnector,
    MarketDataConnector,
    ParsedDocument,
    ParsedTable,
    RawObject,
)
from core.connectors.registry import (
    ConnectorRegistry,
    get_connector_registry,
    reset_connector_registry,
)

__all__ = [
    "BaseConnector",
    "DiscoveryItem",
    "DocumentConnector",
    "MarketDataConnector",
    "ParsedDocument",
    "ParsedTable",
    "RawObject",
    "ConnectorRegistry",
    "get_connector_registry",
    "reset_connector_registry",
]
