"""
Web search provider 工厂.

按 settings.WEB_SEARCH_PROVIDER 选择具体 provider（tavily / bing），
优先使用 WEB_SEARCH_API_KEYS 环境变量中的 key 池。
"""

import os

from core.interfaces import WebSearchProvider
from core.observability import get_logger
from core.settings import settings
from data_layer.web_search.bing_provider import BingProvider
from data_layer.web_search.key_pool import ApiKeyPool
from data_layer.web_search.tavily_provider import TavilyProvider

logger = get_logger(__name__)


def build_web_search_provider() -> WebSearchProvider:
    """Build a provider from effective runtime settings."""
    return build_web_search_provider_from_values(
        provider_name=settings.WEB_SEARCH_PROVIDER,
        key_pool_json=os.environ.get("WEB_SEARCH_API_KEYS"),
        tavily_api_key=settings.TAVILY_API_KEY,
        bing_api_key=settings.BING_API_KEY,
        rotation_strategy=settings.WEB_SEARCH_KEY_ROTATION,
        max_consecutive_failures=settings.WEB_SEARCH_KEY_MAX_FAILURES,
        lock_seconds=settings.WEB_SEARCH_KEY_LOCK_SECONDS,
        cooldown_seconds=settings.WEB_SEARCH_KEY_COOLDOWN_SECONDS,
        quota_limit=settings.WEB_SEARCH_KEY_QUOTA_LIMIT,
    )


def build_web_search_provider_from_values(
    *,
    provider_name: str,
    key_pool_json: str | None,
    tavily_api_key: str,
    bing_api_key: str,
    rotation_strategy: str,
    max_consecutive_failures: int,
    lock_seconds: int,
    cooldown_seconds: float,
    quota_limit: int,
) -> WebSearchProvider:
    """Build a provider from explicit values without reading process environment."""
    from data_layer.web_search.key_pool import PoolConfig

    pool_config = PoolConfig(
        rotation_strategy=rotation_strategy,
        max_consecutive_failures=max_consecutive_failures,
        lock_seconds=lock_seconds,
        disable_cooldown_seconds=cooldown_seconds,
        quota_limit=quota_limit,
    )
    key_pool = ApiKeyPool.from_json_value(key_pool_json or "", config=pool_config)
    if key_pool.key_count == 0:
        key_pool = None

    name = provider_name.lower()
    if name == "bing":
        logger.info("web search provider: bing" + (" (pool)" if key_pool else ""))
        return BingProvider(api_key=bing_api_key, key_pool=key_pool)
    if name == "tavily":
        logger.info("web search provider: tavily" + (" (pool)" if key_pool else ""))
        return TavilyProvider(api_key=tavily_api_key, key_pool=key_pool)
    logger.info("web search provider: tavily (default, unknown=%s)", name)
    return TavilyProvider(api_key=tavily_api_key, key_pool=key_pool)
