"""
OpenAI-compatible model provider implementation.

Provides OpenAICompatibleProvider, which uses the OpenAI Python SDK (if installed)
to connect to any OpenAI-compatible API endpoint for chat completions, structured
outputs, and embeddings. Accepts a ProviderProfile to support multiple simultaneous
providers (Volcano, DeepSeek, OpenAI, local vLLM/Ollama, etc.).

Volcano-specific multimodal embedding endpoint is auto-detected from the base_url.
"""

import time
from typing import Any

import httpx
from pydantic import BaseModel

from core.interfaces import EmbeddingResponse, ModelResponse
from core.model_gateway.base import BaseProvider
from core.observability import get_logger
from core.settings.config import ProviderProfile

logger = get_logger(__name__)

OpenAIClient: Any = None
try:
    from openai import OpenAI as _OpenAIClient

    OpenAIClient = _OpenAIClient
except ImportError:
    pass


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI 兼容提供商实现.

    Connects to any OpenAI-compatible API endpoint using a ProviderProfile.
    Supports chat completions, structured outputs (via JSON prompt injection),
    and embeddings. Auto-detects Volcano multimodal embedding endpoint from
    the base_url.
    """

    def __init__(self, profile: ProviderProfile):
        self._provider_name = profile.name
        self._base_url = profile.base_url
        self._api_key = profile.api_key
        self._has_multimodal_embed = profile.base_url and "volces.com" in profile.base_url
        endpoint = httpx.URL(profile.base_url)
        loopback = endpoint.host in {"127.0.0.1", "localhost", "::1"}
        if endpoint.scheme != "https" and not (endpoint.scheme == "http" and loopback):
            raise ValueError("OpenAI-compatible provider URL is unsafe")
        if endpoint.query or endpoint.fragment:
            raise ValueError("OpenAI-compatible provider URL must not contain query or fragment")
        self._chat_endpoint = f"{profile.base_url.rstrip('/')}/chat/completions"
        timeout = httpx.Timeout(120.0, connect=30.0)
        self._http_client = httpx.Client(timeout=timeout, trust_env=False)
        if OpenAIClient is not None:
            self._client = OpenAIClient(
                api_key=profile.api_key,
                base_url=profile.base_url,
                timeout=timeout,
                http_client=self._http_client,
            )
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
        model = model or "gpt-3.5-turbo"
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
                request_timeout = kwargs.pop("timeout", None)
                payload: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                }
                if max_tokens is not None:
                    payload["max_tokens"] = max_tokens
                payload.update(kwargs)
                request_options = (
                    {"timeout": request_timeout} if request_timeout is not None else {}
                )
                response = self._http_client.post(
                    self._chat_endpoint,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    **request_options,
                )
                response.raise_for_status()
                body = response.json()
                message = body["choices"][0]["message"]
                value = message.get("content") or ""
                if not isinstance(value, str):
                    raise ValueError("provider content must be text")
                content = value
                model = str(body.get("model") or model)
                tokens_used = int((body.get("usage") or {}).get("total_tokens") or 0)
        except Exception as e:  # noqa: BLE001 - provider SDK exceptions vary by version
            logger.error(
                "OpenAI-compatible provider chat failed",
                provider_name=self._provider_name,
                error_type=type(e).__name__,
                status_code=(
                    e.response.status_code if isinstance(e, httpx.HTTPStatusError) else None
                ),
            )
            content = "Error: configured provider request failed"

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
        """结构化输出 - 优先用 OpenAI 原生 response_format，回退 prompt 注入+重试.

        三级策略（deep-research-report.md 第一阶段要求）：
        1. 优先：response_format={"type":"json_schema",...,"strict":True} 原生结构化输出
        2. 回退：provider 不支持时走 prompt 注入 + retry_structured_parse 重试
        3. 兜底：重试仍失败返回 model_construct() 空对象
        """
        model = model or "gpt-3.5-turbo"

        # 优先路径：原生 response_format（直接调 SDK，绕过 self.chat 以保留结构化元数据）
        if self._client is not None:
            try:
                from core.model_gateway.structured_output_utils import (
                    pydantic_to_openai_json_schema,
                )

                strict_schema = pydantic_to_openai_json_schema(output_schema)
                schema_name = output_schema.__name__
                response = self._client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    response_format={
                        "type": "json_schema",
                        "json_schema": {
                            "name": schema_name,
                            "schema": strict_schema,
                            "strict": True,
                        },
                    },
                )
                content = response.choices[0].message.content or ""
                from core.model_gateway.structured_output_utils import (
                    parse_json_content,
                )

                data = parse_json_content(content)
                return output_schema(**data)
            except Exception as e:  # noqa: BLE001 - structured providers vary by SDK
                # 原生路径不可用（端点不支持 strict / 解析失败），降级到 prompt 注入重试
                logger.warning(
                    f"{self._provider_name} native response_format unavailable, "
                    "falling back to prompt injection + retry",
                    error=str(e),
                )

        # 回退路径：prompt 注入 + 重试
        from core.model_gateway.structured_output_utils import retry_structured_parse

        schema_str = output_schema.model_json_schema()
        system_msg = f"Please respond only JSON matching this schema: {schema_str}"
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
        model = model or "text-embedding-3-small"
        start_time = time.time()
        tokens_used = 0
        embedding: list[float] = []

        try:
            if self._client:
                embedding, tokens_used = self._do_embed(text, model, **kwargs)
        except Exception as e:  # noqa: BLE001 - embedding providers vary by SDK
            logger.error(
                f"{self._provider_name} embed error",
                error=str(e),
            )

        latency_ms = int((time.time() - start_time) * 1000)

        return EmbeddingResponse(
            embedding=embedding,
            model_name=model,
            provider=self._provider_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

    def _do_embed(self, text: str, model: str, **kwargs: Any) -> tuple[list[float], int]:
        """Try standard embeddings first, fall back to multimodal endpoint."""
        try:
            assert self._client is not None
            response = self._client.embeddings.create(
                model=model,
                input=text,
                **kwargs,
            )
            embedding = response.data[0].embedding
            tokens_used = response.usage.total_tokens if response.usage else 0
            return embedding, tokens_used
        except Exception as standard_err:
            if self._has_multimodal_embed:
                err_str = str(standard_err)
                if "does not support this api" in err_str or "InvalidEndpointOrModel" in err_str:
                    logger.debug(
                        "standard embed failed, trying multimodal endpoint",
                        model=model,
                    )
                    return self._embed_multimodal(text, model, **kwargs)
            raise

    def _embed_multimodal(self, text: str, model: str, **kwargs: Any) -> tuple[list[float], int]:
        """调用火山多模态嵌入端点 /v3/embeddings/multimodal"""
        import httpx

        base_url = self._base_url
        # Strip /v1 suffix if present (multimodal endpoint uses /v3)
        base_url = base_url.removesuffix("/v1")

        url = f"{base_url.rstrip('/')}/v3/embeddings/multimodal"
        payload = {
            "model": model,
            "input": [{"type": "text", "text": text}],
        }
        headers = {
            "Authorization": f"Bearer {self._client.api_key if self._client else ''}",
            "Content-Type": "application/json",
        }

        resp = httpx.post(url, json=payload, headers=headers, timeout=30.0)
        resp.raise_for_status()
        data = resp.json()

        data_field = data.get("data", {})
        if isinstance(data_field, dict):
            embedding = data_field.get("embedding", [])
        elif isinstance(data_field, list) and len(data_field) > 0:
            embedding = data_field[0].get("embedding", [])
        else:
            embedding = []

        tokens_used = data.get("usage", {}).get("total_tokens", 0)

        logger.debug(
            f"{self._provider_name} multimodal embed success",
            dim=len(embedding),
            tokens=tokens_used,
        )
        return embedding, tokens_used
