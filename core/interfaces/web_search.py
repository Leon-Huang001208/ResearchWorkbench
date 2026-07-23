"""
Web search provider interfaces for real-time online query augmentation.

当用户提问时，AlphaFoundry 优先联网搜索补充证据，再交给 LLM 生成带引用的答案。
本模块定义 WebSearchProvider 抽象接口与 WebSearchResult 数据模型，具体实现见
data_layer/web_search/（Tavily、Bing 等）。
"""

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field


class WebSearchResult(BaseModel):
    """单条网页搜索结果.

    Attributes:
        title: 网页标题.
        url: 网页 URL.
        snippet: 搜索 API 返回的摘要.
        content: 抓取并抽取的正文（截断后），无则为 None.
        source: 结果来源标识（如 "tavily"、"bing"）.
        score: 相关性分数（0.0-1.0），部分 provider 不提供.
    """

    title: str = Field(description="网页标题")
    url: str = Field(description="网页 URL")
    snippet: str = Field(default="", description="搜索 API 返回的摘要")
    content: Optional[str] = Field(default=None, description="抓取的正文（截断后）")
    source: str = Field(default="", description="结果来源标识")
    score: Optional[float] = Field(default=None, description="相关性分数")


class WebSearchProvider(ABC):
    """网页搜索 provider 抽象基类.

    各 provider（Tavily、Bing 等）实现 search()，返回统一的 WebSearchResult 列表。
    """

    @abstractmethod
    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """执行网页搜索.

        Args:
            query: 搜索关键词.
            max_results: 最大返回条数.

        Returns:
            WebSearchResult 列表.
        """
        pass
