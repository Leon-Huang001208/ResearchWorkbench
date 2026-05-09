"""
Abstract base class for model gateway providers.

Defines the BaseProvider interface for model providers that implement chat completions,
structured outputs, and embeddings for the ModelGatewayImpl in AlphaFoundry.
"""
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.observability import get_logger

logger = get_logger(__name__)


class BaseProvider(ABC):
    """模型提供商基类.

    Abstract base class for model providers, which implement chat completions, structured
    outputs, and embeddings for specific LLM providers (e.g., OpenAI, Volcano).
    """

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """聊天补全.

        Sends a chat completion request and returns a ModelResponse.

        Args:
            messages: List of message dictionaries (each with "role" and "content").
            model: Name of the model to use (if None, uses default).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate (if None, uses provider default).
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            ModelResponse: Response from the model provider.
        """
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
        """结构化输出.

        Sends a chat completion request with a structured output schema and returns a
        parsed BaseModel instance.

        Args:
            messages: List of message dictionaries (each with "role" and "content").
            output_schema: Pydantic BaseModel class to use for parsing the output.
            model: Name of the model to use (if None, uses default).
            temperature: Sampling temperature (0.0 to 2.0).
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            BaseModel: Parsed structured output as an instance of output_schema.
        """
        pass

    @abstractmethod
    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """文本嵌入.

        Generates an embedding for the input text and returns an EmbeddingResponse.

        Args:
            text: Text to embed.
            model: Name of the embedding model to use (if None, uses default).
            **kwargs: Additional provider-specific keyword arguments.

        Returns:
            EmbeddingResponse: Response from the embedding provider.
        """
        pass
