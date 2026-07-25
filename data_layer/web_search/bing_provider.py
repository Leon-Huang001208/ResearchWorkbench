"""
Bing Web Search provider.

调用 Bing Web Search API（v7），返回搜索结果摘要+URL。
Bing 不直接返回正文，故对 Top-N 结果用 page_fetcher 补抓正文。

支持单 key 或 key 池模式。
"""

from typing import TYPE_CHECKING, Optional

from core.interfaces import WebSearchProvider, WebSearchResult
from core.observability import get_logger
from core.settings import settings
from data_layer.web_search.page_fetcher import fetch_content

if TYPE_CHECKING:
    from data_layer.web_search.key_pool import ApiKeyPool

logger = get_logger(__name__)

_BING_ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

_FETCH_CONTENT_TOP_N = 3


def _is_quota_error(exc: Exception) -> bool:
    """判断是否为 API 配额/限流错误."""
    status: int | None = None
    if hasattr(exc, "response"):
        resp = getattr(exc, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
    if status is None and hasattr(exc, "__cause__"):
        cause = exc.__cause__
        if cause is not None:
            status = getattr(
                cause, "status_code", getattr(getattr(cause, "response", None), "status_code", None)
            )
    return status in (402, 429)


class BingProvider(WebSearchProvider):
    """Bing Web Search provider.

    池模式优先：传入 key_pool 时从池中租借 key；无 pool 时回退到 settings.BING_API_KEY。
    """

    def __init__(
        self,
        api_key: str | None = None,
        key_pool: "ApiKeyPool | None" = None,
    ) -> None:
        self._api_key = api_key or settings.BING_API_KEY
        self._key_pool = key_pool
        self._leased_key_name: str | None = None

    def search(self, query: str, max_results: int = 5) -> list[WebSearchResult]:
        if self._key_pool is not None and self._key_pool.key_count > 0:
            return self._search_with_pool(query, max_results)
        return self._search_with_key(query, max_results, self._api_key)

    # ── 池模式 ──────────────────────────────────────────

    def _search_with_pool(self, query: str, max_results: int) -> list[WebSearchResult]:
        assert self._key_pool is not None
        key_name = self._key_pool.acquire()
        if key_name is None:
            logger.warning("no available api key in pool, bing search skipped")
            return []

        self._leased_key_name = key_name
        api_key = self._key_pool.get_key(key_name)
        try:
            results = self._search_with_key(query, max_results, api_key, raise_errors=True)
            self._key_pool.report_success(key_name)
            self._key_pool.report_quota_used(key_name)
            return results
        except Exception as e:
            # 402/429 → 配额耗尽
            if _is_quota_error(e):
                self._key_pool.report_quota_exhausted(key_name)
            else:
                self._key_pool.report_failure(key_name)
            raise
        finally:
            self._key_pool.release(key_name)
            self._leased_key_name = None

    # ── 单 key 模式 ─────────────────────────────────────

    def _search_with_key(
        self, query: str, max_results: int, api_key: str, *, raise_errors: bool = False
    ) -> list[WebSearchResult]:
        if not api_key:
            logger.warning("BING_API_KEY not configured, bing search skipped")
            return []

        try:
            import httpx

            params: dict[str, str] = {
                "q": query,
                "count": str(max_results),
                "responseFilter": "Webpages",
            }
            headers = {"Ocp-Apim-Subscription-Key": api_key}
            with httpx.Client(timeout=settings.WEB_SEARCH_TIMEOUT) as client:
                resp = client.get(_BING_ENDPOINT, params=params, headers=headers)
                resp.raise_for_status()
                data = resp.json()
        except Exception as exc:
            logger.error("bing search failed", query=query, error_type=type(exc).__name__)
            if raise_errors:
                raise
            return []

        web_pages = (data.get("webPages") or {}).get("value", [])
        results: list[WebSearchResult] = []
        for idx, item in enumerate(web_pages[:max_results]):
            url = item.get("url", "")
            snippet = item.get("snippet", "") or ""
            content: Optional[str] = None
            if settings.WEB_SEARCH_FETCH_CONTENT and idx < _FETCH_CONTENT_TOP_N and url:
                content = fetch_content(url)
            results.append(
                WebSearchResult(
                    title=item.get("name", ""),
                    url=url,
                    snippet=snippet,
                    content=content,
                    source="bing",
                    score=None,
                )
            )
        logger.info(
            "bing search done",
            query=query,
            result_count=len(results),
        )
        return results
