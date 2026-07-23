"""
AskService 装配工厂.

供 CLI / API 等入口共用，避免重复初始化 ModelGateway 和 WebSearchService。
"""

from functools import lru_cache

from core.interfaces import ModelGateway
from core.model_gateway.gateway import ModelGatewayImpl
from data_layer.web_search import build_web_search_provider
from services.ask_service import AskService
from services.web_search_service import WebSearchService


@lru_cache(maxsize=1)
def _default_model_gateway() -> ModelGateway:
    """单例 ModelGatewayImpl."""
    return ModelGatewayImpl()


def build_ask_service(
    model_gateway: ModelGateway | None = None,
) -> AskService:
    """装配 AskService.

    Args:
        model_gateway: 可选注入的 ModelGateway（测试用），None 则用默认单例.

    Returns:
        AskService 实例.
    """
    gateway = model_gateway or _default_model_gateway()
    provider = build_web_search_provider()
    web_search = WebSearchService(provider=provider)
    return AskService(model_gateway=gateway, web_search=web_search)
