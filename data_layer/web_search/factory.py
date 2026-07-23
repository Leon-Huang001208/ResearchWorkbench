"""
Web search provider 工厂.

按 settings.WEB_SEARCH_PROVIDER 选择具体 provider（tavily / bing），
优先使用 WEB_SEARCH_API_KEYS 环境变量中的 key 池。
"""

from core.interfaces import WebSearchProvider
from core.observability import get_logger
from core.settings import settings
from data_layer.web_search.bing_provider import BingProvider
from data_layer.web_search.key_pool import ApiKeyPool
from data_layer.web_search.tavily_provider import TavilyProvider

logger = get_logger(__name__)


def _build_key_pool() -> ApiKeyPool | None:
    """从 WEB_SEARCH_API_KEYS 环境变量构建 key 池.

    如果未配置（空或格式错误），返回 None——provider 会自动回退到单 key 模式。
    """
    from data_layer.web_search.key_pool import PoolConfig

    config = PoolConfig(
        rotation_strategy=settings.WEB_SEARCH_KEY_ROTATION,
        max_consecutive_failures=settings.WEB_SEARCH_KEY_MAX_FAILURES,
        lock_seconds=settings.WEB_SEARCH_KEY_LOCK_SECONDS,
        disable_cooldown_seconds=settings.WEB_SEARCH_KEY_COOLDOWN_SECONDS,
        quota_limit=settings.WEB_SEARCH_KEY_QUOTA_LIMIT,
    )
    pool = ApiKeyPool.from_json_env("WEB_SEARCH_API_KEYS", config=config)
    if pool.key_count == 0:
        return None
    return pool


def build_web_search_provider() -> WebSearchProvider:
    """根据配置构建 web search provider.

    优先级：WEB_SEARCH_API_KEYS（池）> TAVILY_API_KEY / BING_API_KEY（单 key）.

    Returns:
        WebSearchProvider 实例。key 全部未配置时 provider 的 search 方法返回空列表。
    """
    name = settings.WEB_SEARCH_PROVIDER.lower()
    key_pool = _build_key_pool()

    if name == "bing":
        logger.info("web search provider: bing" + (" (pool)" if key_pool else ""))
        return BingProvider(key_pool=key_pool)
    if name == "tavily":
        logger.info("web search provider: tavily" + (" (pool)" if key_pool else ""))
        return TavilyProvider(key_pool=key_pool)
    # 默认 tavily
    logger.info("web search provider: tavily (default, unknown=%s)", name)
    return TavilyProvider(key_pool=key_pool)
