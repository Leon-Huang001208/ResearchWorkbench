"""
Local embedding provider using sentence-transformers.

Loads HuggingFace embedding models (e.g., BAAI/bge-base-zh-v1.5) for
offline, zero-cost text embeddings. First load downloads the model (~400MB)
and caches it in ~/.cache/huggingface/.
"""
import time

from core.interfaces import EmbeddingResponse
from core.model_gateway.base import BaseProvider
from core.observability import get_logger
from core.settings.config import ProviderProfile

logger = get_logger(__name__)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None


class LocalEmbeddingProvider(BaseProvider):
    """本地 embedding provider，使用 sentence-transformers 加载模型.

    Only supports embed(). chat() and structured_output() raise NotImplementedError.
    """

    def __init__(self, profile: ProviderProfile) -> None:
        self._provider_name = profile.name
        self._model: "SentenceTransformer | None" = None
        self._loaded_model_name: str = ""

    def _load_model(self, model_name: str) -> None:
        if self._model is not None and self._loaded_model_name == model_name:
            return
        if SentenceTransformer is None:
            raise RuntimeError(
                "sentence-transformers not installed. "
                "Install it with: pip install sentence-transformers"
            )
        logger.info("loading local embedding model", model=model_name)
        self._model = SentenceTransformer(model_name)
        self._loaded_model_name = model_name

    def chat(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError("LocalEmbeddingProvider only supports embeddings, not chat")

    def structured_output(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError(
            "LocalEmbeddingProvider only supports embeddings, not structured output"
        )

    def embed(
        self,
        text: str,
        model: str | None = None,
        **kwargs,
    ) -> EmbeddingResponse:
        model_name = model or "BAAI/bge-base-zh-v1.5"
        start = time.perf_counter()

        try:
            self._load_model(model_name)
            assert self._model is not None
            vec = self._model.encode(text, **kwargs).tolist()
            latency_ms = int((time.perf_counter() - start) * 1000)

            logger.debug(
                "local embed success",
                model=model_name,
                dim=len(vec),
                latency_ms=latency_ms,
            )
            return EmbeddingResponse(
                embedding=vec,
                model_name=model_name,
                provider=self._provider_name,
                tokens_used=0,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.error("local embed error", model=model_name, error=str(e))
            latency_ms = int((time.perf_counter() - start) * 1000)
            return EmbeddingResponse(
                embedding=[],
                model_name=model_name,
                provider=self._provider_name,
                tokens_used=0,
                latency_ms=latency_ms,
            )
