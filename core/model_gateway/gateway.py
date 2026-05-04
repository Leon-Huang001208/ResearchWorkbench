from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse
from core.interfaces import ModelGateway as ModelGatewayInterface
from core.interfaces import ModelResponse
from core.model_gateway.base import BaseProvider
from core.model_gateway.providers import OpenAICompatibleProvider, VolcanoProvider
from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)


class ModelGatewayImpl(ModelGatewayInterface):
    """模型网关实现"""

    def __init__(self):
        self._provider: BaseProvider | None = None
        self._init_provider()

    def _init_provider(self) -> None:
        """初始化提供商"""
        if settings.MODEL_PROVIDER == "volcano":
            self._provider = VolcanoProvider()
        elif settings.MODEL_PROVIDER == "openai_compatible":
            self._provider = OpenAICompatibleProvider()
        else:
            logger.warning(
                "unknown model provider, using volcano", provider=settings.MODEL_PROVIDER
            )
            self._provider = VolcanoProvider()

    def set_provider(self, provider: BaseProvider) -> None:
        """设置提供商"""
        self._provider = provider

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """聊天补全"""
        if self._provider is None:
            raise RuntimeError("No model provider initialized")

        logger.debug(
            "chat request",
            message_count=len(messages),
            model=model or settings.DEFAULT_CHAT_MODEL,
            temperature=temperature,
        )

        return self._provider.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )

    def structured_output(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> BaseModel:
        """结构化输出"""
        if self._provider is None:
            raise RuntimeError("No model provider initialized")

        logger.debug(
            "structured output request",
            message_count=len(messages),
            model=model or settings.DEFAULT_CHAT_MODEL,
            schema_name=output_schema.__name__,
        )

        return self._provider.structured_output(
            messages=messages,
            output_schema=output_schema,
            model=model,
            temperature=temperature,
            **kwargs,
        )

    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """文本嵌入"""
        if self._provider is None:
            raise RuntimeError("No model provider initialized")

        logger.debug(
            "embed request",
            text_length=len(text),
            model=model or settings.DEFAULT_EMBEDDING_MODEL,
        )

        return self._provider.embed(text=text, model=model, **kwargs)
