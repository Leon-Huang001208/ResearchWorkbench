"""
Anthropic native protocol provider implementation.

Provides AnthropicProvider, which uses the Anthropic Python SDK to connect
to the Anthropic API (or compatible endpoint) for chat completions and
structured outputs. Embeddings are not supported by Anthropic.

Message format conversion:
  OpenAI:  [{"role":"system","content":"..."}, {"role":"user","content":"..."}]
  Anthropic: system="..." (separate param), messages=[{"role":"user","content":"..."}]
"""
import time
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.model_gateway.base import BaseProvider
from core.observability import get_logger
from core.settings.config import ProviderProfile

logger = get_logger(__name__)

try:
    import anthropic
except ImportError:
    anthropic = None  # type: ignore[assignment]


def _extract_system_and_messages(
    messages: list[dict[str, str]],
) -> tuple[str | None, list[dict[str, str]]]:
    """Extract system message from OpenAI-format messages for Anthropic.

    Anthropic API requires system as a separate parameter and does not allow
    "system" role in the messages array.

    Returns:
        (system_prompt, filtered_messages)
    """
    system_parts: list[str] = []
    filtered: list[dict[str, str]] = []
    for msg in messages:
        if msg.get("role") == "system":
            system_parts.append(msg["content"])
        else:
            filtered.append({"role": msg["role"], "content": msg["content"]})

    system = "\n\n".join(system_parts) if system_parts else None
    return system, filtered


class AnthropicProvider(BaseProvider):
    """Anthropic 原生协议提供商.

    Uses the Anthropic Python SDK for chat completions and structured outputs.
    Embeddings are not supported (raises NotImplementedError).
    """

    def __init__(self, profile: ProviderProfile):
        self._provider_name = profile.name
        if anthropic is not None:
            kwargs: dict[str, Any] = {"api_key": profile.api_key}
            if profile.base_url:
                kwargs["base_url"] = profile.base_url
            self._client = anthropic.Anthropic(**kwargs)
        else:
            self._client = None

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        model = model or "claude-sonnet-4-6"
        start_time = time.time()
        tokens_used = 0
        content = ""

        try:
            if self._client:
                system, api_messages = _extract_system_and_messages(messages)

                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": api_messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens or 4096,
                }
                if system:
                    create_kwargs["system"] = system
                create_kwargs.update(kwargs)

                response = self._client.messages.create(**create_kwargs)
                content = response.content[0].text
                tokens_used = response.usage.input_tokens + response.usage.output_tokens
            else:
                content = (
                    f"[{self._provider_name} API not available"
                    " - anthropic package not installed]"
                )
        except Exception as e:
            logger.error(
                f"{self._provider_name} chat error",
                error=str(e),
            )
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
        model = model or "claude-sonnet-4-6"

        schema_str = output_schema.model_json_schema()
        system_msg = f"Please respond only with valid JSON matching this schema: {schema_str}"

        system, api_messages = _extract_system_and_messages(messages)
        if system:
            system = system + "\n\n" + system_msg
        else:
            system = system_msg

        response = self.chat(
            messages=api_messages + [{"role": "system", "content": system_msg}],
            temperature=temperature,
            model=model,
            **kwargs,
        )

        try:
            import json

            content = response.content.strip()
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
            logger.error(
                f"{self._provider_name} structured output parse error",
                error=str(e),
            )
            return output_schema.model_construct()

    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """Anthropic does not support embedding API."""
        raise NotImplementedError(
            "Anthropic does not support embeddings. Use an OpenAI-compatible provider."
        )
