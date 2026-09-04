"""
Abstract base class (interface) for model gateways and response models.

Defines the ModelGateway interface (for unified access to LLM providers) and response
models (ModelResponse, EmbeddingResponse) in Research Workbench.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class ModelResponse(BaseModel):
    """模型响应.

    Represents a response from a chat completion call, including content, model name,
    provider, tokens used, latency, and raw response.

    Attributes:
        content: Text content of the response.
        model_name: Name of the model used.
        provider: Provider of the model (e.g., "openai", "volcano").
        tokens_used: Total tokens used in the request/response.
        latency_ms: Latency of the request in milliseconds.
        raw_response: Raw response from the provider (if available).
    """

    content: str = Field(description="Text content of the response")
    model_name: str = Field(description="Name of the model used")
    provider: str = Field(description="Provider of the model (e.g., openai, volcano)")
    tokens_used: int = Field(description="Total tokens used in the request/response")
    latency_ms: int = Field(description="Latency of the request in milliseconds")
    raw_response: Any = Field(
        default=None, description="Raw response from the provider (if available)"
    )


class EmbeddingResponse(BaseModel):
    """嵌入响应.

    Represents a response from an embedding call, including embedding vector, model name,
    provider, tokens used, and latency.

    Attributes:
        embedding: Embedding vector as a list of floats.
        model_name: Name of the embedding model used.
        provider: Provider of the embedding model (e.g., "openai", "volcano").
        tokens_used: Total tokens used in the request.
        latency_ms: Latency of the request in milliseconds.
    """

    embedding: list[float] = Field(description="Embedding vector as a list of floats")
    model_name: str = Field(description="Name of the embedding model used")
    provider: str = Field(description="Provider of the embedding model (e.g., openai, volcano)")
    tokens_used: int = Field(description="Total tokens used in the request")
    latency_ms: int = Field(description="Latency of the request in milliseconds")


class ModelGateway(ABC):
    """模型网关基类 - 统一访问不同的模型提供商.

    Abstract base class for model gateways, which provide a unified interface to interact
    with different LLM providers (e.g., OpenAI, Volcano) for chat completions, structured
    outputs, and embeddings.
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

        Sends a chat completion request to the model provider and returns a ModelResponse.

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
