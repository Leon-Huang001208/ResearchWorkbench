"""
向量存储 - pgvector 封装
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

from core.interfaces import ModelGateway
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
    """内存向量存储（用于测试和开发）"""

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
        """获取文本的嵌入向量"""
        if self._model_gateway:
            try:
                return self._model_gateway.embed(text).embedding
            except Exception as e:
                logger.error(f"Failed to get embedding: {e}", exc_info=True)

        # 回退到简单的伪嵌入（仅用于测试）
        return self._dummy_embedding(text)

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
