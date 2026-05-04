from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.observability import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC):
    """模型提供商基类"""

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """聊天补全"""
        pass

    @abstractmethod
    def structured_output(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> BaseModel:
        """结构化输出"""
        pass

    @abstractmethod
    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """文本嵌入"""
        pass
