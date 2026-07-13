"""
Multi-provider ModelGateway implementation with per-task routing.

ModelGatewayImpl reads ProviderProfile definitions from settings and initializes
one provider per profile (OpenAI-compatible or Anthropic). Task-to-provider+model
routing is configured via TASK_ROUTES in settings, allowing different tasks
(extraction, classification, code, reasoning, embedding) to use different
providers and models.

LLM 响应缓存：基于 (model, messages_hash, temperature) 的 TTL 缓存，
默认 5 分钟有效期，减少重复 prompt 的 API 调用开销。
"""
import hashlib
import json
import threading
import time
from typing import Any

from pydantic import BaseModel

from core.interfaces import EmbeddingResponse
from core.interfaces import ModelGateway as ModelGatewayInterface
from core.interfaces import ModelResponse
from core.model_gateway.base import BaseProvider
from core.model_gateway.providers import (
    AnthropicProvider,
    LocalEmbeddingProvider,
    OpenAICompatibleProvider,
)
from core.observability import get_logger
from core.settings import settings

logger = get_logger(__name__)

# 缓存默认 TTL（秒）
_CACHE_TTL = 300  # 5 分钟


class ModelGatewayImpl(ModelGatewayInterface):
    """多 provider 模型网关，支持按任务路由到不同平台/模型."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        self._task_routes: dict[str, Any] = {}
        self._default_provider: BaseProvider | None = None
        self._cache: dict[str, tuple[float, Any]] = {}  # key → (expire_at, response)
        self._cache_lock = threading.Lock()
        self._init_providers()

    def _init_providers(self) -> None:
        """从 settings.PROVIDER_PROFILES 初始化所有 provider."""
        for name, profile in settings.PROVIDER_PROFILES.items():
            try:
                if profile.protocol == "anthropic":
                    provider: BaseProvider = AnthropicProvider(profile)
                elif profile.protocol == "local":
                    provider = LocalEmbeddingProvider(profile)
                else:
                    provider = OpenAICompatibleProvider(profile)
                self._providers[name] = provider
                logger.info(
                    "provider initialized",
                    name=name,
                    protocol=profile.protocol,
                )
            except Exception as e:
                logger.error(
                    "failed to initialize provider",
                    name=name,
                    error=str(e),
                )

        self._task_routes = dict(settings.TASK_ROUTES)

        # 设置默认 provider：优先 "default" task 路由的 provider，其次第一个
        default_route = self._task_routes.get("default")
        if default_route and default_route.provider in self._providers:
            self._default_provider = self._providers[default_route.provider]
        elif self._providers:
            self._default_provider = next(iter(self._providers.values()))

        if not self._providers:
            logger.warning("no model providers configured — all calls will fail")

    def set_provider(self, provider: BaseProvider) -> None:
        """替换默认 provider（用于测试注入）."""
        self._default_provider = provider
        self._providers["_injected"] = provider

    # ── LLM Response Cache ──────────────────────────────────────

    @staticmethod
    def _cache_key(
        messages: list[dict[str, str]],
        model: str | None,
        temperature: float,
    ) -> str:
        """生成确定性缓存键：model + messages_hash + temperature。"""
        payload = json.dumps({"m": messages, "t": temperature}, sort_keys=True, ensure_ascii=False)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
        return f"{model or 'default'}:{digest}"

    def _cache_get(self, key: str) -> Any | None:
        """从缓存读取未过期的值。"""
        with self._cache_lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            expire_at, value = entry
            if time.monotonic() > expire_at:
                del self._cache[key]
                return None
            return value

    def _cache_set(self, key: str, value: Any, ttl: int = _CACHE_TTL) -> None:
        """写入缓存。"""
        with self._cache_lock:
            self._cache[key] = (time.monotonic() + ttl, value)

    def _resolve(self, task: str | None, model: str | None) -> tuple[BaseProvider, str]:
        """Resolve (provider, model) for a given task.

        Priority:
        1. Task route lookup → use route.provider + (model or route.model)
        2. Explicit model only → use default provider + explicit model
        3. Fallback → default provider + empty model (provider uses its own default)
        """
        if task and task in self._task_routes:
            route = self._task_routes[task]
            provider = self._providers.get(route.provider)
            if provider is not None:
                resolved_model = model or route.model
                return provider, resolved_model

        provider = self._default_provider
        if provider is None:
            # Last resort: pick first available
            provider = next(iter(self._providers.values()), None)  # type: ignore[arg-type]
        if provider is None:
            raise RuntimeError(
                "No model provider available. " "Configure PROVIDER_PROFILES in settings."
            )
        default_route = self._task_routes.get("default")
        return provider, model or (default_route.model if default_route else "")

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
        task: str | None = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Chat completion with optional task-based routing.

        Args:
            messages: List of message dicts (each with "role" and "content").
            model: Model name override (defaults to task route or provider default).
            temperature: Sampling temperature (0.0 to 2.0).
            max_tokens: Maximum tokens to generate.
            task: Task name for routing (e.g. "extraction", "code", "default").
            **kwargs: Additional provider-specific parameters.

        Returns:
            ModelResponse with content, model name, provider, tokens, and latency.
        """
        provider, resolved_model = self._resolve(task, model)

        # Check TTL cache
        cache_key = self._cache_key(messages, resolved_model or None, temperature)
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("chat cache hit", cache_key=cache_key[:40])
            return cached

        logger.debug(
            "chat request",
            message_count=len(messages),
            model=resolved_model,
            task=task,
            provider=getattr(provider, "_provider_name", "unknown"),
            temperature=temperature,
        )

        response = provider.chat(
            messages=messages,
            model=resolved_model or None,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs,
        )
        self._cache_set(cache_key, response)
        return response

    def structured_output(
        self,
        messages: list[dict[str, str]],
        output_schema: type[BaseModel],
        model: str | None = None,
        temperature: float = 0.1,
        task: str | None = None,
        **kwargs: Any,
    ) -> BaseModel:
        """Structured output with optional task-based routing.

        Args:
            messages: List of message dicts.
            output_schema: Pydantic BaseModel class for parsing output.
            model: Model name override.
            temperature: Sampling temperature.
            task: Task name for routing.
            **kwargs: Additional provider-specific parameters.

        Returns:
            Parsed BaseModel instance.
        """
        provider, resolved_model = self._resolve(task, model)

        # Check TTL cache (include schema name in key for structured output)
        cache_key = self._cache_key(
            [{"schema": output_schema.__name__}] + messages,
            resolved_model or None,
            temperature,
        )
        cached = self._cache_get(cache_key)
        if cached is not None:
            logger.debug("structured output cache hit", cache_key=cache_key[:40])
            return cached

        logger.debug(
            "structured output request",
            message_count=len(messages),
            model=resolved_model,
            task=task,
            schema_name=output_schema.__name__,
            provider=getattr(provider, "_provider_name", "unknown"),
        )

        response = provider.structured_output(
            messages=messages,
            output_schema=output_schema,
            model=resolved_model or None,
            temperature=temperature,
            **kwargs,
        )
        self._cache_set(cache_key, response)
        return response

    def embed(
        self,
        text: str,
        model: str | None = None,
        task: str | None = "embedding",
        **kwargs: Any,
    ) -> EmbeddingResponse:
        """Text embedding with optional task-based routing.

        Defaults to task="embedding" for embedding-specific routing.

        Args:
            text: Text to embed.
            model: Model name override.
            task: Task name for routing (defaults to "embedding").
            **kwargs: Additional provider-specific parameters.

        Returns:
            EmbeddingResponse with embedding vector and metadata.
        """
        provider, resolved_model = self._resolve(task, model)

        logger.debug(
            "embed request",
            text_length=len(text),
            model=resolved_model,
            task=task,
            provider=getattr(provider, "_provider_name", "unknown"),
        )

        return provider.embed(text=text, model=resolved_model or None, **kwargs)
