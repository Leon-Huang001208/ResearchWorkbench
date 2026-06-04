"""
向量存储 - pgvector 封装
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from core.interfaces import ModelGateway
from core.model_gateway.local_embedding_config import (
    resolve_local_embedding_model,
    sentence_transformer_kwargs,
)
from core.observability import get_logger

logger = get_logger(__name__)


class VectorStore(ABC):
    """向量存储接口"""

    @abstractmethod
    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """添加文档到向量存储"""
        pass

    @abstractmethod
    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """搜索相似文档"""
        pass

    @abstractmethod
    def delete_document(self, doc_id: str) -> None:
        """删除文档"""
        pass


class InMemoryVectorStore(VectorStore):
    """内存向量存储（用于测试和开发）。

    嵌入优先级：
    1. model_gateway.embed()（若已注入）
    2. 本地 sentence-transformers 模型（本地目录或已缓存模型；默认不联网下载）
    3. character-bigram 伪嵌入（始终可用）
    """

    _sentence_model = None  # 类级别缓存，所有实例共享
    _st_disabled = False  # 可设为 True 来禁用 sentence-transformers

    def __init__(self, model_gateway: Optional[ModelGateway] = None):
        self._model_gateway = model_gateway
        self._documents: Dict[str, Dict] = {}  # doc_id -> {text, metadata, embedding}
        self._embeddings: Dict[str, List[float]] = {}

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """添加文档"""
        embedding = self._get_embedding(text)
        self._documents[doc_id] = {
            "text": text,
            "metadata": metadata or {},
        }
        self._embeddings[doc_id] = embedding
        logger.debug(f"Added document to vector store: {doc_id}")

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """搜索相似文档"""
        if not self._embeddings:
            return []

        query_embedding = self._get_embedding(query)

        # 计算相似度
        scores: List[Tuple[str, float]] = []
        for doc_id, embedding in self._embeddings.items():
            # 应用过滤
            if filters:
                doc_metadata = self._documents[doc_id]["metadata"]
                if not self._match_filters(doc_metadata, filters):
                    continue

            similarity = self._cosine_similarity(query_embedding, embedding)
            scores.append((doc_id, similarity))

        # 排序
        scores.sort(key=lambda x: x[1], reverse=True)

        # 构建结果
        results = []
        for doc_id, score in scores[:top_k]:
            doc = self._documents[doc_id]
            results.append(
                {
                    "doc_id": doc_id,
                    "text": doc["text"],
                    "metadata": doc["metadata"],
                    "score": score,
                }
            )

        return results

    def delete_document(self, doc_id: str) -> None:
        """删除文档"""
        if doc_id in self._documents:
            del self._documents[doc_id]
        if doc_id in self._embeddings:
            del self._embeddings[doc_id]
        logger.debug(f"Deleted document from vector store: {doc_id}")

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本的嵌入向量。

        优先级：model_gateway > sentence-transformers > bigram dummy。
        """
        # 1. 优先使用已注入的 model_gateway
        if self._model_gateway:
            try:
                return self._model_gateway.embed(text).embedding
            except Exception as e:
                logger.warning("model_gateway.embed failed, trying fallbacks: %s", e)

        # 2. 尝试本地 sentence-transformers
        embed = self._st_embed(text)
        if embed is not None:
            return embed

        # 3. 回退到 bigram 伪嵌入
        return self._dummy_embedding(text)

    @classmethod
    def _st_embed(cls, text: str) -> List[float] | None:
        """使用本地 sentence-transformers 编码，失败返回 None。"""
        try:
            model = cls._load_st_model()
            if model is None:
                return None
            vec = model.encode(text, normalize_embeddings=True)
            return vec.tolist()
        except Exception:
            return None

    @classmethod
    def _load_st_model(cls):
        """惰性加载 sentence-transformers 模型（类级别缓存）。"""
        if cls._st_disabled:
            return None
        if cls._sentence_model is not None:
            return cls._sentence_model
        model_ref = resolve_local_embedding_model("all-MiniLM-L6-v2")
        if model_ref is None:
            return None
        try:
            from sentence_transformers import SentenceTransformer

            kwargs = sentence_transformer_kwargs(model_ref)
            cls._sentence_model = SentenceTransformer(model_ref, **kwargs)
            logger.info("Loaded sentence-transformers model: %s", model_ref)
        except ImportError:
            logger.debug("sentence-transformers not installed, using bigram fallback")
        except Exception as exc:
            logger.warning("Failed to load sentence-transformers model: %s", exc)
        return cls._sentence_model

    def _dummy_embedding(self, text: str) -> List[float]:
        """生成基于字符 n-gram 的伪嵌入（用于无模型时）

        Uses character bigrams so that texts sharing characters/words
        produce similar vectors, enabling basic semantic similarity.
        """
        import hashlib

        # Use 256 bigram buckets for a compact, meaningful embedding
        dim = 256
        embedding = [0.0] * dim

        # Normalize text
        normalized = text.lower().strip()

        # Count character bigrams
        for i in range(len(normalized) - 1):
            bigram = normalized[i : i + 1]
            bucket = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16) % dim
            embedding[bucket] += 1.0

        # Also count individual characters for unigram signal
        for ch in normalized:
            bucket = ord(ch) % dim
            embedding[bucket] += 0.5

        # Also count word-level features
        words = normalized.split()
        for word in words:
            bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim
            embedding[bucket] += 2.0  # words get higher weight

        # Normalize to unit vector for cosine similarity
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """计算余弦相似度"""
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def _match_filters(self, metadata: Dict, filters: Dict) -> bool:
        """检查元数据是否匹配过滤条件"""
        for key, value in filters.items():
            if metadata.get(key) != value:
                return False
        return True


class PGVectorStore(VectorStore):
    """PostgreSQL pgvector 存储（占位实现）"""

    def __init__(self, session_factory, model_gateway: Optional[ModelGateway] = None):
        self._session_factory = session_factory
        self._model_gateway = model_gateway

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """添加文档"""
        # TODO: 实现真正的 pgvector 存储
        logger.debug(f"PGVectorStore.add_document (not implemented): {doc_id}")

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """搜索"""
        logger.debug(f"PGVectorStore.search (not implemented): {query}")
        return []

    def delete_document(self, doc_id: str) -> None:
        """删除"""
        logger.debug(f"PGVectorStore.delete_document (not implemented): {doc_id}")
