"""Local embedding model resolution helpers.

The sentence-transformers API accepts both Hugging Face model ids and local
directories. AlphaFoundry keeps local embeddings offline by default: model ids
are loaded from cache only unless downloads are explicitly enabled.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from core.observability import get_logger

logger = get_logger(__name__)

DISABLE_LOCAL_EMBEDDINGS_ENV = "ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS"
LOCAL_EMBEDDING_MODEL_PATH_ENV = "ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH"
ALLOW_EMBEDDING_DOWNLOAD_ENV = "ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD"


def local_embeddings_disabled() -> bool:
    """Return True when local embedding model loading is disabled."""

    return os.getenv(DISABLE_LOCAL_EMBEDDINGS_ENV) == "1"


def embedding_download_allowed() -> bool:
    """Return True only when network model downloads are explicitly enabled."""

    return os.getenv(ALLOW_EMBEDDING_DOWNLOAD_ENV) == "1"


def resolve_local_embedding_model(default_model: str) -> str | None:
    """Resolve the model reference to pass to sentence-transformers.

    Resolution order:
    1. Disabled env flag -> None.
    2. Explicit local model path -> that path, if it exists.
    3. Default model id -> cache-only by default; download only when explicitly allowed.
    """

    if local_embeddings_disabled():
        return None

    configured_path = os.getenv(LOCAL_EMBEDDING_MODEL_PATH_ENV, "").strip()
    if configured_path:
        model_path = Path(configured_path).expanduser()
        if model_path.exists():
            return str(model_path)
        logger.warning("configured local embedding model path does not exist", path=str(model_path))
        return None

    return default_model


def sentence_transformer_kwargs(model_ref: str) -> dict[str, Any]:
    """Build safe SentenceTransformer constructor kwargs for a model reference."""

    if Path(model_ref).expanduser().exists():
        return {}
    return {"local_files_only": not embedding_download_allowed()}
