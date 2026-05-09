"""
OpenAI-compatible model provider implementation.

Provides OpenAICompatibleProvider, which uses the OpenAI Python SDK (if installed)
to connect to an OpenAI-compatible API endpoint (configured via OPENAI_API_KEY and
OPENAI_BASE_URL in settings) for chat completions, structured outputs, and embeddings.
"""
import time
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.model_gateway.base import BaseProvider
from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容提供商实现.

    Concrete BaseProvider implementation that connects to an OpenAI-compatible API
    endpoint (configured via settings.OPENAI_API_KEY and settings.OPENAI_BASE_URL).
    Falls back to placeholder responses if the OpenAI package is not installed.
    """

    def __init__(self):
        # Initialize OpenAI client if the package is available
        if OpenAI is not None:
            self._client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
            )
        self._provider_name = "openai_compatible"

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """聊天补全.

        Sends a chat completion request to the OpenAI-compatible API and returns a
        ModelResponse. Tracks latency and token usage.

        Args:
            messages: List of message dictionaries (each with "role" and "content").
            model: Name of the model to use (if None, uses DEFAULT_CHAT_MODEL from settings).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate (if None, uses provider default).
            **kwargs: Additional keyword arguments to pass to the API client.

        Returns:
            ModelResponse: Response with content, model name, provider, tokens used, and latency.
        """
        model = model or settings.DEFAULT_CHAT_MODEL
        start_time = time.time()
        tokens_used = 0
        content = ""

        try:
            if self._client:
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs,
                )
                content = response.choices[0].message.content or ""
                tokens_used = response.usage.total_tokens if response.usage else 0
            else:
                content = "[OpenAI compatible API not available - OpenAI package not installed]"
        except Exception as e:
            logger.error("openai compatible chat error", error=str(e))
            content = f"Error: {e}"

        latency_ms = int((time.time() - start_time) * 1000)

        return ModelResponse(
            content=content,
            model_name=model,
            provider=self._provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    def structured_output(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.1,
        **kwargs: Any,
    ) -> BaseModel:
        """结构化输出.

        Sends a chat completion request with a system prompt to return JSON matching the
        output schema, then parses the response into a BaseModel instance. Strips markdown
        code blocks (if any) before parsing.

        Args:
            messages: List of message dictionaries (each with "role" and "content").
            output_schema: Pydantic BaseModel class to use for parsing the output.
            model: Name of the model to use (if None, uses DEFAULT_CHAT_MODEL from settings).
            temperature: Sampling temperature (0.0 to 2.0).
            **kwargs: Additional keyword arguments to pass to the chat method.

        Returns:
            BaseModel: Parsed structured output as an instance of output_schema. If parsing
                fails, returns an empty model constructed with model_construct().
        """
        model = model or settings.DEFAULT_CHAT_MODEL

        # Simple implementation: first get JSON string, then parse
        schema_str = output_schema.model_json_schema()
        system_msg = f"Please respond only JSON matching this schema: {schema_str}"

        response = self.chat(
            messages=messages + [{"role": "system", "content": system_msg}],
            temperature=temperature,
            model=model,
            **kwargs,
        )

        try:
            import json

            content = response.content.strip()
            # Strip markdown code block markers if present
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

            data = json.loads(content)
            return output_schema(**data)
        except Exception as e:
            logger.error("structured output parse error", error=str(e))
            return output_schema.model_construct()

    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """文本嵌入.

        Sends an embedding request to the OpenAI-compatible API and returns an
        EmbeddingResponse. Tracks latency and token usage.

        Args:
            text: Text to embed.
            model: Name of the embedding model to use (if None, uses DEFAULT_EMBEDDING_MODEL
                from settings).
            **kwargs: Additional keyword arguments to pass to the API client.

        Returns:
            EmbeddingResponse: Response with embedding, model name, provider, tokens used,
                and latency.
        """
        model = model or settings.DEFAULT_EMBEDDING_MODEL
        start_time = time.time()
        tokens_used = 0
        embedding = []

        try:
            if self._client:
                response = self._client.embeddings.create(
                    model=model,
                    input=text,
                    **kwargs,
                )
                embedding = response.data[0].embedding
                tokens_used = response.usage.total_tokens if response.usage else 0
        except Exception as e:
            logger.error("openai compatible embed error", error=str(e))

        latency_ms = int((time.time() - start_time) * 1000)

        return EmbeddingResponse(
            embedding=embedding,
            model_name=model,
            provider=self._provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )
