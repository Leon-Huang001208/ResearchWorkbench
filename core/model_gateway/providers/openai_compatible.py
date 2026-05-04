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
    """OpenAI 兼容提供商实现"""

    def __init__(self):
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
        """聊天补全"""
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
        """结构化输出"""
        model = model or settings.DEFAULT_CHAT_MODEL

        # 简单实现：先获取 JSON 字符串，再解析
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
        """文本嵌入"""
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
