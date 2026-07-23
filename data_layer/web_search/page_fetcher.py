"""
网页正文抓取与抽取.

给定 URL，用 httpx 抓取 HTML，用 trafilatura 抽取干净正文并截断。
抓取失败时优雅降级（返回 None），不阻塞整体搜索流程。
"""

from typing import Optional

from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# 正文截断字符数上限（避免单条结果撑爆 LLM 上下文）
_DEFAULT_MAX_CHARS = 2000

# 请求头，模拟浏览器避免被反爬拦截
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


def fetch_content(
    url: str,
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
    timeout: int | None = None,
) -> Optional[str]:
    """抓取并抽取网页正文.

    Args:
        url: 目标网页 URL.
        max_chars: 正文截断上限（字符数）.
        timeout: 请求超时秒数，None 则用 settings.WEB_SEARCH_TIMEOUT.

    Returns:
        抽取并截断后的正文；抓取或抽取失败返回 None.
    """
    if timeout is None:
        timeout = settings.WEB_SEARCH_TIMEOUT

    # 延迟导入：trafilatura 较重，且仅在真正抓取时需要
    try:
        import trafilatura  # type: ignore[import-untyped]
    except ImportError:
        logger.warning("trafilatura not installed, cannot extract page content")
        return None

    try:
        import httpx

        with httpx.Client(timeout=timeout, follow_redirects=True, headers=_HEADERS) as client:
            resp = client.get(url)
            resp.raise_for_status()
            # 优先 UTF-8，避免 GBK 站点乱码
            html = resp.content.decode(resp.encoding or "utf-8", errors="ignore")
    except Exception as e:
        logger.info("page fetch failed", url=url, error=str(e))
        return None

    try:
        extracted = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
    except Exception as e:
        logger.info("trafilatura extract failed", url=url, error=str(e))
        return None

    if not extracted:
        return None

    extracted = extracted.strip()
    if len(extracted) > max_chars:
        extracted = extracted[:max_chars].rstrip() + "…"
    return extracted or None
