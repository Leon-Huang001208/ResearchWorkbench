"""
Tavily 搜索 provider.

Tavily 是专为 LLM 设计的搜索 API，返回已抽取的干净正文+摘要。
API 文档：https://docs.tavily.com/

支持单 key 或 key 池模式——传入 ``key_pool`` 时自动 acquire/release 和失败追踪。
"""

from typing import TYPE_CHECKING, Any

from core.interfaces import WebSearchProvider, WebSearchResult
from core.observability import get_logger
from core.settings import settings

if TYPE_CHECKING:
    from data_layer.web_search.key_pool import ApiKeyPool

logger = get_logger(__name__)

_TAVILY_ENDPOINT = "https://api.tavily.com/search"


def _is_quota_error(exc: Exception) -> bool:
    """判断是否为 API 配额/限流错误（402 Payment Required, 429 Too Many Requests）."""
    status: int | None = None
    if hasattr(exc, "response"):
        resp = getattr(exc, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
    # httpx.HTTPStatusError
    if status is None and hasattr(exc, "__cause__"):
        cause = exc.__cause__
        if cause is not None:
            status = getattr(
                cause, "status_code", getattr(getattr(cause, "response", None), "status_code", None)
            )
    return status in (402, 429)


class TavilyProvider(WebSearchProvider):
    """Tavily 搜索 provider.

    池模式优先：传入 key_pool 时从池中租借 key，调用完成后上报成功/失败；
    无 pool 时回退到单 key（settings.TAVILY_API_KEY）。
    """

    def __init__(
        self,
        api_key: str | None = None,
        key_pool: "ApiKeyPool | None" = None,
    ) -> None:
        self._api_key = api_key or settings.TAVILY_API_KEY
        self._key_pool = key_pool
        # 当前租借的 key 名（用于上报）
        self._leased_key_name: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        """调用 Tavily API 搜索.

        Args:
            query: 搜索关键词.
            max_results: 最大返回条数.

        Returns:
            WebSearchResult 列表.
        """
        # ── 池模式：租借 key ──
        if self._key_pool is not None and self._key_pool.key_count > 0:
            return self._search_with_pool(query, max_results)

        # ── 单 key 模式（向后兼容）──
        return self._search_with_key(query, max_results, self._api_key)

    # ── 池模式 ──────────────────────────────────────────

    def _search_with_pool(self, query: str, max_results: int) -> list[WebSearchResult]:
        assert self._key_pool is not None
        key_name = self._key_pool.acquire()
        if key_name is None:
            logger.warning("no available api key in pool, tavily search skipped")
            return []

        self._leased_key_name = key_name
        api_key = self._key_pool.get_key(key_name)
        try:
            results = self._search_with_key(query, max_results, api_key)
            self._key_pool.report_success(key_name)
            self._key_pool.report_quota_used(key_name)
            return results
        except Exception as e:
            # 402/429 → 配额耗尽，标记后下月自动恢复
            if _is_quota_error(e):
                self._key_pool.report_quota_exhausted(key_name)
            else:
                self._key_pool.report_failure(key_name)
            raise
        finally:
            self._key_pool.release(key_name)
            self._leased_key_name = None

    # ── 单 key 模式 ─────────────────────────────────────

    def _search_with_key(self, query: str, max_results: int, api_key: str) -> list[WebSearchResult]:
        if not api_key:
            logger.warning("TAVILY_API_KEY not configured, tavily search skipped")
            return []

        try:
            import httpx

            payload: dict[str, Any] = {
                "api_key": api_key,
                "query": query,
                "max_results": max_results,
                "search_depth": "advanced",
                "include_raw_content": True,
            }
            with httpx.Client(timeout=settings.WEB_SEARCH_TIMEOUT) as client:
                resp = client.post(_TAVILY_ENDPOINT, json=payload)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:
            logger.error("tavily search failed", query=query, error=str(e))
            return []

        results: list[WebSearchResult] = []
        for item in data.get("results", []):
            content = item.get("raw_content") or item.get("content")
            if content and len(content) > settings.WEB_SEARCH_MAX_CHARS:
                content = content[: settings.WEB_SEARCH_MAX_CHARS].rstrip() + "…"
            results.append(
                WebSearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "") or "",
                    content=content,
                    source="tavily",
                    score=item.get("score"),
                )
            )
        logger.info(
            "tavily search done",
            query=query,
            result_count=len(results),
        )
        return results
