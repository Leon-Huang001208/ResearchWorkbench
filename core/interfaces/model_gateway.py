from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel


class ModelResponse(BaseModel):
    """模型响应"""

    content: str
    model_name: str
    provider: str
    tokens_used: int
    latency_ms: int
    raw_response: Any = None


class EmbeddingResponse(BaseModel):
    """嵌入响应"""

    embedding: list[float]
    model_name: str
    provider: str
    tokens_used: int
    latency_ms: int


class ModelGateway(ABC):
    """模型网关基类 - 统一访问不同的模型提供商"""

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
