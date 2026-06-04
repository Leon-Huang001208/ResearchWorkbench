from unittest.mock import Mock

from core.model_gateway.local_embedding_config import (
    resolve_local_embedding_model,
    sentence_transformer_kwargs,
)
from core.model_gateway.providers import local_embedding
from core.model_gateway.providers.local_embedding import LocalEmbeddingProvider
from core.settings.config import ProviderProfile
from knowledge_layer.retrieval.vector_store import InMemoryVectorStore


def test_resolve_local_embedding_model_disabled(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS", "1")
    monkeypatch.delenv("ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH", raising=False)

    assert resolve_local_embedding_model("all-MiniLM-L6-v2") is None


def test_sentence_transformer_kwargs_cache_only_by_default(monkeypatch):
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD", raising=False)

    assert sentence_transformer_kwargs("all-MiniLM-L6-v2") == {"local_files_only": True}


def test_sentence_transformer_kwargs_allows_download_only_when_enabled(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD", "1")

    assert sentence_transformer_kwargs("all-MiniLM-L6-v2") == {"local_files_only": False}


def test_sentence_transformer_kwargs_local_path_uses_path_without_download_flag(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD", raising=False)

    assert sentence_transformer_kwargs(str(tmp_path)) == {}


def test_local_embedding_provider_uses_configured_local_path(tmp_path, monkeypatch):
    monkeypatch.delenv("ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS", raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH", str(tmp_path))
    fake_model = Mock()
    fake_model.encode.return_value.tolist.return_value = [0.1, 0.2]
    fake_sentence_transformer = Mock(return_value=fake_model)
    monkeypatch.setattr(local_embedding, "SentenceTransformer", fake_sentence_transformer)

    provider = LocalEmbeddingProvider(ProviderProfile(name="local_embeddings", protocol="local"))
    response = provider.embed("hello")

    fake_sentence_transformer.assert_called_once_with(str(tmp_path))
    assert response.embedding == [0.1, 0.2]


def test_vector_store_uses_cache_only_sentence_transformer_by_default(monkeypatch):
    monkeypatch.delenv("ALPHAFOUNDRY_DISABLE_LOCAL_EMBEDDINGS", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_LOCAL_EMBEDDING_MODEL_PATH", raising=False)
    monkeypatch.delenv("ALPHAFOUNDRY_ALLOW_EMBEDDING_DOWNLOAD", raising=False)
    InMemoryVectorStore._sentence_model = None

    fake_model = Mock()
    fake_model.encode.return_value.tolist.return_value = [0.1, 0.2]
    fake_sentence_transformer = Mock(return_value=fake_model)

    import sentence_transformers

    monkeypatch.setattr(sentence_transformers, "SentenceTransformer", fake_sentence_transformer)

    assert InMemoryVectorStore._st_embed("hello") == [0.1, 0.2]
    fake_sentence_transformer.assert_called_once_with("all-MiniLM-L6-v2", local_files_only=True)

    InMemoryVectorStore._sentence_model = None
