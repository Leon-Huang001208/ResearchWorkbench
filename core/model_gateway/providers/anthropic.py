"""
Anthropic native protocol provider implementation.

Provides AnthropicProvider, which uses the Anthropic Python SDK to connect
to the Anthropic API (or compatible endpoint) for chat completions and
structured outputs. Embeddings are not supported by Anthropic.

Message format conversion:
  OpenAI:  [{"role":"system","content":"..."}, {"role":"user","content":"..."}]
  Anthropic: system="..." (separate param), messages=[{"role":"user","content":"..."}]
"""

import importlib
import time
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.model_gateway.base import BaseProvider
from core.observability import get_logger
from core.settings.config import ProviderProfile

logger = get_logger(__name__)

try:
    anthropic = importlib.import_module("anthropic")
except ImportError:
    anthropic = None


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
        """结构化输出 - 优先用 Anthropic tool use，回退 prompt 注入+重试.

        三级策略（deep-research-report.md 第一阶段要求）：
        1. 优先：tool use（tools=[tool], tool_choice={"type":"tool",...}），
           从 tool_use block 提取 input，比 prompt 注入更可靠
        2. 回退：tool use 不可用时走 prompt 注入 + retry_structured_parse 重试
        3. 兜底：重试仍失败返回 model_construct() 空对象
        """
        model = model or "claude-sonnet-4-6"

        # 优先路径：tool use（直接调 SDK，绕过 self.chat 以保留 tool_use 结构）
        if self._client is not None:
            try:
                from core.model_gateway.structured_output_utils import (
                    pydantic_to_anthropic_tool_schema,
                )

                tool = pydantic_to_anthropic_tool_schema(
                    output_schema,
                    description="Return the structured output matching the schema.",
                )
                system, api_messages = _extract_system_and_messages(messages)
                create_kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": api_messages,
                    "temperature": temperature,
                    "max_tokens": kwargs.pop("max_tokens", 4096),
                    "tools": [tool],
                    "tool_choice": {"type": "tool", "name": tool["name"]},
                }
                if system:
                    create_kwargs["system"] = system
                create_kwargs.update(kwargs)

                response = self._client.messages.create(**create_kwargs)
                # 从 tool_use block 提取结构化输入
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        return output_schema(**block.input)
                # 模型未返回 tool_use block，尝试按文本解析
                text_content = ""
                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        text_content += block.text
                if text_content:
                    from core.model_gateway.structured_output_utils import (
                        parse_json_content,
                    )

                    data = parse_json_content(text_content)
                    return output_schema(**data)
                raise ValueError("Anthropic response contained no tool_use or text content")
            except Exception as e:
                logger.warning(
                    f"{self._provider_name} tool use structured output unavailable, "
                    "falling back to prompt injection + retry",
                    error=str(e),
                )

        # 回退路径：prompt 注入 + 重试
        from core.model_gateway.structured_output_utils import retry_structured_parse

        schema_str = output_schema.model_json_schema()
        system_msg = f"Please respond only with valid JSON matching this schema: {schema_str}"
        return retry_structured_parse(
            chat_fn=self.chat,
            messages=messages + [{"role": "system", "content": system_msg}],
            output_schema=output_schema,
            max_retries=2,
            temperature=temperature,
            model=model,
            **kwargs,
        )

    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """Anthropic does not support embedding API."""
        raise NotImplementedError(
            "Anthropic does not support embeddings. Use an OpenAI-compatible provider."
        )
