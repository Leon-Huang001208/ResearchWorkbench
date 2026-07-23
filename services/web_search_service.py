"""
Web search service：联网搜索内核.

协调 WebSearchProvider 执行搜索，必要时补抓网页正文，并将结果格式化为
带编号的参考资料文本，供 AskService 注入 LLM prompt。
"""

from typing import Optional

from core.interfaces import WebSearchProvider, WebSearchResult
from core.observability import get_logger
from core.settings import settings
from data_layer.web_search.page_fetcher import fetch_content as fetch_page_content

logger = get_logger(__name__)


class WebSearchService:
    """联网搜索服务.

    封装 provider 调用、正文补抓、结果格式化，供 AskService 等入口复用。
    """

    def __init__(
        self,
        provider: WebSearchProvider,
        fetch_content_enabled: Optional[bool] = None,
        max_chars: Optional[int] = None,
    ) -> None:
        self._provider = provider
        self._fetch_content_enabled = (
            fetch_content_enabled
            if fetch_content_enabled is not None
            else settings.WEB_SEARCH_FETCH_CONTENT
        )
        self._max_chars = max_chars or settings.WEB_SEARCH_MAX_CHARS

    def search(
        self,
        query: str,
        max_results: Optional[int] = None,
        fetch_content: Optional[bool] = None,
    ) -> list[WebSearchResult]:
        """执行联网搜索.

        Args:
            query: 搜索关键词.
            max_results: 最大返回条数，None 用 settings.WEB_SEARCH_MAX_RESULTS.
            fetch_content: 是否补抓正文，None 用实例默认配置.

        Returns:
            WebSearchResult 列表（可能为空，表示搜索失败或无 key）.
        """
        if max_results is None:
            max_results = settings.WEB_SEARCH_MAX_RESULTS

        results = self._provider.search(query, max_results=max_results)
        if not results:
            logger.info("web search returned no results", query=query)
            return []

        # 对缺少正文的结果补抓（当 provider 未直接返回 content 时）
        should_fetch = fetch_content if fetch_content is not None else self._fetch_content_enabled
        if should_fetch:
            for r in results:
                if r.content is None and r.url:
                    r.content = fetch_page_content(r.url, max_chars=self._max_chars)

        logger.info(
            "web search complete",
            query=query,
            result_count=len(results),
            with_content=sum(1 for r in results if r.content),
        )
        return results

    def format_for_prompt(self, results: list[WebSearchResult]) -> str:
        """将搜索结果格式化为带编号的参考资料文本.

        格式：
            [1] 标题 (url)
            正文或摘要...

            [2] ...

        Args:
            results: 搜索结果列表.

        Returns:
            格式化后的文本，供注入 LLM prompt。空列表返回空串。
        """
        if not results:
            return ""
        blocks: list[str] = []
        for idx, r in enumerate(results, 1):
            body = r.content or r.snippet or "(无内容)"
            blocks.append(f"[{idx}] {r.title}\nURL: {r.url}\n{body}")
        return "\n\n".join(blocks)
