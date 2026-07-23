"""
Web search 子包：通用网页搜索 provider（Tavily / Bing）。

与 data_layer/crawlers 不同，这里面向"查询时实时联网搜索"，
而非批量数据采集。provider 实现 core.interfaces.WebSearchProvider。
"""

from .bing_provider import BingProvider
from .factory import build_web_search_provider
from .key_pool import ApiKeyPool, PoolConfig
from .page_fetcher import fetch_content
from .tavily_provider import TavilyProvider

__all__ = [
    "BingProvider",
    "TavilyProvider",
    "ApiKeyPool",
    "PoolConfig",
    "build_web_search_provider",
    "fetch_content",
]
