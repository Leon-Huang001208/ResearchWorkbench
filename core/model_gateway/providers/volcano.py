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


class VolcanoProvider(BaseProvider):
    """火山方舟提供商实现"""

    def __init__(self):
        if OpenAI is not None:
            self._client = OpenAI(
                api_key=settings.VOLCANO_API_KEY,
                base_url=settings.VOLCANO_BASE_URL,
            )
        self._provider_name = "volcano"

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
                content = "[Volcano API not available - OpenAI package not installed"
        except Exception as e:
            logger.error("volcano chat error", error=str(e))
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
            # 尝试解析
            import json

            # 清理响应
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
            # 返回默认实例
            return output_schema.model_construct()

    def embed(self, text: str, model: str | None = None, **kwargs: Any) -> EmbeddingResponse:
        """文本嵌入 — 支持多模态嵌入端点（doubao-embedding-vision）"""
        model = model or settings.DEFAULT_EMBEDDING_MODEL
        start_time = time.time()
        tokens_used = 0
        embedding = []

        try:
            if self._client:
                # 先尝试标准 /v1/embeddings 端点
                try:
                    response = self._client.embeddings.create(
                        model=model,
                        input=text,
                        **kwargs,
                    )
                    embedding = response.data[0].embedding
                    tokens_used = response.usage.total_tokens if response.usage else 0
                except Exception as standard_err:
                    # 标准端点失败，尝试多模态端点 /v3/embeddings/multimodal
                    err_str = str(standard_err)
                    if (
                        "does not support this api" in err_str
                        or "InvalidEndpointOrModel" in err_str
                    ):
                        logger.debug(
                            "standard embed failed, trying multimodal endpoint", model=model
                        )
                        embedding, tokens_used = self._embed_multimodal(text, model, **kwargs)
                    else:
                        raise
        except Exception as e:
            logger.error("volcano embed error", error=str(e))

        latency_ms = int((time.time() - start_time) * 1000)

        return EmbeddingResponse(
            embedding=embedding,
            model_name=model,
            provider=self._provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    def _embed_multimodal(self, text: str, model: str, **kwargs: Any) -> tuple[list[float], int]:
        """调用多模态嵌入端点 /v3/embeddings/multimodal"""
        import httpx

        url = f"{settings.VOLCANO_BASE_URL}/embeddings/multimodal"
        payload = {
            "model": model,
            "input": [{"type": "text", "text": text}],
        }
        headers = {
            "Authorization": f"Bearer {settings.VOLCANO_API_KEY}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        # 火山多模态嵌入响应: data 可能是 dict{"embedding": [...]} 或 list[{"embedding": [...]}]
        data_field = data.get("data", {})
        if isinstance(data_field, dict):
            embedding = data_field.get("embedding", [])
        elif isinstance(data_field, list) and len(data_field) > 0:
            embedding = data_field[0].get("embedding", [])
        else:
            embedding = []

        tokens_used = data.get("usage", {}).get("total_tokens", 0)

        logger.debug("multimodal embed success", dim=len(embedding), tokens=tokens_used)
        return embedding, tokens_used
