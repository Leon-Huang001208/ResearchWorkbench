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
    """PostgreSQL 向量存储.

    第二阶段实现（deep-research-report.md "PGVectorStore 实现策略"）：

    - 第一步（DB-backed brute-force，始终可用）：embedding 以 JSON 序列化存入
      ``document_chunk_v1.embedding``（TEXT 列），search 时加载到内存算余弦 top_k。
      适用于 <10 万文档的规模。
    - 第二步（pgvector 原生，条件依赖）：若 pgvector 扩展可用且 embedding 列已迁移
      为 ``vector`` 类型，search 改用 ``<=>``（cosine distance）下推到 DB。当前环境
      pgvector 系统级未安装（``CREATE EXTENSION vector`` 报 FeatureNotSupported），
      故自动回退到第一步，并在首次调用时记录一次降级 warning。

    本类按 chunk 粒度存储与检索（与 document_chunk_v1 对齐），add_document 会
    upsert 一条 chunk 记录的 embedding 字段。
    """

    _pgvector_checked: bool = False
    _pgvector_available: bool = False

    def __init__(self, session_factory, model_gateway: Optional[ModelGateway] = None):
        self._session_factory = session_factory
        self._model_gateway = model_gateway
        self._check_pgvector_once()

    @classmethod
    def _check_pgvector_once(cls) -> None:
        """惰性检测 pgvector 扩展可用性，结果类级缓存。"""
        if cls._pgvector_checked:
            return
        cls._pgvector_checked = True
        try:
            from sqlalchemy import text

            from data_layer.repositories.base import engine

            with engine.connect() as conn:
                row = conn.execute(
                    text("SELECT 1 FROM pg_extension WHERE extname='vector'")
                ).first()
                cls._pgvector_available = row is not None
        except Exception as exc:  # noqa: BLE001 - 检测失败按不可用处理
            cls._pgvector_available = False
            logger.warning("pgvector availability check failed, using brute-force: %s", exc)
        if not cls._pgvector_available:
            logger.info(
                "pgvector not available, PGVectorStore falling back to DB-backed brute-force search"
            )

    def _get_embedding(self, text: str) -> List[float]:
        """获取文本嵌入（与 InMemoryVectorStore 同优先级：gateway > st > bigram）."""
        if self._model_gateway:
            try:
                return self._model_gateway.embed(text).embedding
            except Exception as e:  # noqa: BLE001
                logger.warning("model_gateway.embed failed, trying fallbacks: %s", e)
        # 复用 InMemoryVectorStore 的本地/伪嵌入逻辑
        embed = InMemoryVectorStore._st_embed(text)
        if embed is not None:
            return embed
        return self._dummy_embedding(text)

    def add_document(
        self,
        doc_id: str,
        text: str,
        metadata: Optional[Dict] = None,
    ) -> None:
        """为已存在的 chunk 写入 embedding.

        document_chunk_v1.doc_id 是指向 document_v1 的外键，故本方法不自行 INSERT
        chunk 行（会违反 FK）。生产中 chunk 由 knowledge_worker 随 document_v1 一起
        创建，本方法只负责 upsert 这些已存在 chunk 的 embedding 字段。

        若 chunk 不存在（独立向量化场景），记录 warning 并跳过——调用方应先确保
        document_v1 + chunk 已落库。
        """
        import json

        from data_layer.repositories.models import DocumentChunkV1DB

        embedding = self._get_embedding(text)
        embedding_json = json.dumps(embedding)
        session = self._session_factory()
        try:
            existing = session.get(DocumentChunkV1DB, doc_id)
            if existing is None:
                logger.warning(
                    "PGVectorStore.add_document: chunk %s not found, skipping "
                    "(document_v1 + chunk must be persisted first)",
                    doc_id,
                )
                return
            existing.embedding = embedding_json
            session.commit()
            logger.debug("PGVectorStore.add_document: %s (dim=%d)", doc_id, len(embedding))
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error("PGVectorStore.add_document failed: %s", e)
            raise
        finally:
            session.close()

    def search(
        self,
        query: str,
        top_k: int = 10,
        filters: Optional[Dict] = None,
    ) -> List[Dict]:
        """搜索相似文档.

        pgvector 可用时下推 cosine distance 到 DB；否则加载全部 embedding 到内存
        brute-force 算余弦 top_k。
        """
        if self._pgvector_available:
            try:
                return self._search_pgvector(query, top_k, filters)
            except Exception as e:  # noqa: BLE001
                logger.warning("pgvector search failed, falling back to brute-force: %s", e)
        return self._search_brute_force(query, top_k, filters)

    def _search_brute_force(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
    ) -> List[Dict]:
        """DB-backed brute-force：加载全部 embedding 到内存算余弦 top_k."""
        import json

        from sqlalchemy import select

        from data_layer.repositories.models import DocumentChunkV1DB

        query_embedding = self._get_embedding(query)
        session = self._session_factory()
        try:
            stmt = select(DocumentChunkV1DB).where(DocumentChunkV1DB.embedding.isnot(None))
            rows = session.execute(stmt).scalars().all()
            scored: List[Tuple[str, float, DocumentChunkV1DB]] = []
            for row in rows:
                if not row.embedding:
                    continue
                try:
                    emb = json.loads(row.embedding)
                except (ValueError, TypeError):
                    continue
                if filters and not self._match_chunk_filters(row, filters):
                    continue
                sim = self._cosine_similarity(query_embedding, emb)
                scored.append((row.chunk_id, sim, row))
            scored.sort(key=lambda x: x[1], reverse=True)
            results: List[Dict] = []
            for chunk_id, score, row in scored[:top_k]:
                results.append(
                    {
                        "doc_id": chunk_id,
                        "text": row.content,
                        "metadata": {"doc_id": row.doc_id, "chunk_index": row.chunk_index},
                        "score": score,
                    }
                )
            return results
        finally:
            session.close()

    def _search_pgvector(
        self,
        query: str,
        top_k: int,
        filters: Optional[Dict],
    ) -> List[Dict]:
        """pgvector 原生 cosine distance 查询（需 embedding 列为 vector 类型）.

        当前 schema 的 embedding 列为 TEXT，此路径仅在将来迁移到 Vector 列后生效。
        未迁移时会抛错并由 search() 回退到 brute-force。
        """
        import json

        from sqlalchemy import text

        query_embedding = self._get_embedding(query)
        # 用参数化向量字面量；pgvector 的 cosine distance 操作符为 <=>
        stmt = text(
            "SELECT chunk_id, doc_id, content, chunk_index, "
            "embedding <=> cast(:q as vector) AS distance "
            "FROM document_chunk_v1 WHERE embedding IS NOT NULL "
            "ORDER BY embedding <=> cast(:q as vector) LIMIT :k"
        )
        session = self._session_factory()
        try:
            rows = session.execute(stmt, {"q": json.dumps(query_embedding), "k": top_k}).all()
            return [
                {
                    "doc_id": r[0],
                    "text": r[2],
                    "metadata": {"doc_id": r[1], "chunk_index": r[3]},
                    "score": 1.0 - float(r[4]) if r[4] is not None else 0.0,
                }
                for r in rows
            ]
        finally:
            session.close()

    def delete_document(self, doc_id: str) -> None:
        """删除文档（按 chunk_id 删除 chunk 行）."""
        from data_layer.repositories.models import DocumentChunkV1DB

        session = self._session_factory()
        try:
            row = session.get(DocumentChunkV1DB, doc_id)
            if row is not None:
                session.delete(row)
                session.commit()
            logger.debug("PGVectorStore.delete_document: %s", doc_id)
        except Exception as e:  # noqa: BLE001
            session.rollback()
            logger.error("PGVectorStore.delete_document failed: %s", e)
        finally:
            session.close()

    @staticmethod
    def _match_chunk_filters(row, filters: Dict) -> bool:
        """按 chunk 元数据/doc_id 过滤（与 InMemoryVectorStore._match_filters 对齐）."""
        meta = row.chunk_metadata or {}
        for key, value in filters.items():
            if key == "doc_id":
                if row.doc_id != value:
                    return False
            elif meta.get(key) != value:
                return False
        return True

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(y * y for y in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _dummy_embedding(text: str) -> List[float]:
        """字符 bigram 伪嵌入（无模型时兜底，与 InMemoryVectorStore 对齐）."""
        import hashlib

        dim = 256
        embedding = [0.0] * dim
        normalized = text.lower().strip()
        for i in range(len(normalized) - 1):
            bucket = int(hashlib.md5(normalized[i : i + 1].encode("utf-8")).hexdigest(), 16) % dim
            embedding[bucket] += 1.0
        for ch in normalized:
            embedding[ord(ch) % dim] += 0.5
        for word in normalized.split():
            bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % dim
            embedding[bucket] += 2.0
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]
        return embedding
