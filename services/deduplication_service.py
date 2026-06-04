"""
去重服务 - Issue #43: 三层去重机制

1. source_doc_id 去重（快速）
2. content_hash 去重（内容哈希）
3. 近似重复检测（语义相似度）
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set, Tuple

from core.contracts import DocType, DocumentV1
from core.observability import get_logger

logger = get_logger(__name__)


class DeduplicationResult:
    """去重结果"""

    def __init__(self):
        self.is_duplicate: bool = False
        self.duplicate_type: Optional[str] = None  # "source_id", "content_hash", "approximate"
        self.duplicate_doc_id: Optional[str] = None
        self.confidence: float = 0.0
        self.details: Dict[str, Any] = {}


class DeduplicationService:
    """去重服务"""

    def __init__(self):
        # 内存缓存（用于快速去重）
        self._seen_source_ids: Dict[
            str, Tuple[str, datetime]
        ] = {}  # source_id -> (doc_id, timestamp)
        self._seen_content_hashes: Dict[
            str, Tuple[str, datetime]
        ] = {}  # hash -> (doc_id, timestamp)
        self._cache_ttl = timedelta(hours=24)

    def check_duplicate(
        self,
        doc: DocumentV1,
        existing_doc_ids: Optional[Dict[str, str]] = None,
        existing_content_hashes: Optional[Dict[str, str]] = None,
    ) -> DeduplicationResult:
        """
        检查文档是否重复

        Args:
            doc: 待检查的文档
            existing_doc_ids: 已存在的 source_id -> doc_id 映射
            existing_content_hashes: 已存在的 content_hash -> doc_id 映射

        Returns:
            DeduplicationResult
        """
        result = DeduplicationResult()

        # 第1层: source_doc_id 去重
        source_doc_id = doc.source_metadata.get("source_doc_id") or doc.source_metadata.get(
            "original_id"
        )
        if source_doc_id:
            # 检查 DB 提供的已存在列表（key 是纯 source_doc_id，不带 source_type 前缀）
            if existing_doc_ids and source_doc_id in existing_doc_ids:
                result.is_duplicate = True
                result.duplicate_type = "source_id"
                result.duplicate_doc_id = existing_doc_ids[source_doc_id]
                result.confidence = 1.0
                result.details["source_key"] = source_doc_id
                logger.debug(f"Duplicate by source_id: {source_doc_id}")
                return result

            # 检查内存缓存（key 格式: {source_type}:{source_doc_id}）
            source_key = f"{doc.source_type.value}:{source_doc_id}"
            if source_key in self._seen_source_ids:
                cached_doc_id, cached_ts = self._seen_source_ids[source_key]
                if datetime.now() - cached_ts < self._cache_ttl:
                    result.is_duplicate = True
                    result.duplicate_type = "source_id"
                    result.duplicate_doc_id = cached_doc_id
                    result.confidence = 1.0
                    result.details["source_key"] = source_key
                    logger.debug(f"Duplicate by source_id (cache): {source_key}")
                    return result

        # 第2层: content_hash 去重
        content_hash = self._compute_content_hash(doc)
        if content_hash:
            # 检查传入的已存在列表
            if existing_content_hashes and content_hash in existing_content_hashes:
                result.is_duplicate = True
                result.duplicate_type = "content_hash"
                result.duplicate_doc_id = existing_content_hashes[content_hash]
                result.confidence = 0.95
                result.details["content_hash"] = content_hash
                logger.debug(f"Duplicate by content_hash: {content_hash}")
                return result

            # 检查内存缓存
            if content_hash in self._seen_content_hashes:
                cached_doc_id, cached_ts = self._seen_content_hashes[content_hash]
                if datetime.now() - cached_ts < self._cache_ttl:
                    result.is_duplicate = True
                    result.duplicate_type = "content_hash"
                    result.duplicate_doc_id = cached_doc_id
                    result.confidence = 0.95
                    result.details["content_hash"] = content_hash
                    logger.debug(f"Duplicate by content_hash (cache): {content_hash}")
                    return result

        # 第3层: 近似重复检测（对于新闻类内容）
        if doc.doc_type in [DocType.NEWS, DocType.TELEGRAM]:
            approx_result = self._check_approximate_duplicate(doc)
            if approx_result.is_duplicate:
                return approx_result

        return result

    def mark_seen(self, doc: DocumentV1) -> None:
        """标记文档为已见过"""
        # 标记 source_id
        source_doc_id = doc.source_metadata.get("source_doc_id") or doc.source_metadata.get(
            "original_id"
        )
        if source_doc_id:
            source_key = f"{doc.source_type.value}:{source_doc_id}"
            self._seen_source_ids[source_key] = (doc.doc_id, datetime.now())

        # 标记 content_hash
        content_hash = self._compute_content_hash(doc)
        if content_hash:
            self._seen_content_hashes[content_hash] = (doc.doc_id, datetime.now())

    def batch_check(
        self,
        docs: List[DocumentV1],
        existing_doc_ids: Optional[Dict[str, str]] = None,
        existing_content_hashes: Optional[Dict[str, str]] = None,
    ) -> Dict[str, DeduplicationResult]:
        """
        批量检查重复

        Returns:
            doc_id -> DeduplicationResult
        """
        results: Dict[str, DeduplicationResult] = {}
        batch_seen_source_ids: Set[str] = set()
        batch_seen_hashes: Set[str] = set()

        for doc in docs:
            # 先检查此批次内的重复
            source_doc_id = doc.source_metadata.get("source_doc_id") or doc.source_metadata.get(
                "original_id"
            )
            if source_doc_id:
                source_key = f"{doc.source_type.value}:{source_doc_id}"
                if source_key in batch_seen_source_ids:
                    result = DeduplicationResult()
                    result.is_duplicate = True
                    result.duplicate_type = "batch_source_id"
                    result.confidence = 1.0
                    results[doc.doc_id] = result
                    continue

            content_hash = self._compute_content_hash(doc)
            if content_hash and content_hash in batch_seen_hashes:
                result = DeduplicationResult()
                result.is_duplicate = True
                result.duplicate_type = "batch_content_hash"
                result.confidence = 0.95
                results[doc.doc_id] = result
                continue

            # 检查全局重复
            result = self.check_duplicate(doc, existing_doc_ids, existing_content_hashes)
            results[doc.doc_id] = result

            # 标记为批次内已见
            if not result.is_duplicate:
                if source_doc_id:
                    batch_seen_source_ids.add(f"{doc.source_type.value}:{source_doc_id}")
                if content_hash:
                    batch_seen_hashes.add(content_hash)

        return results

    def cleanup_cache(self) -> int:
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = []

        for key, (_, ts) in list(self._seen_source_ids.items()):
            if now - ts >= self._cache_ttl:
                expired_keys.append(("source", key))

        for key, (_, ts) in list(self._seen_content_hashes.items()):
            if now - ts >= self._cache_ttl:
                expired_keys.append(("hash", key))

        for type_, key in expired_keys:
            if type_ == "source":
                del self._seen_source_ids[key]
            else:
                del self._seen_content_hashes[key]

        return len(expired_keys)

    def _compute_content_hash(self, doc: DocumentV1) -> Optional[str]:
        """计算内容哈希"""
        if not doc.content:
            return None

        # 规范化内容
        normalized = self._normalize_content(doc.content)
        if not normalized:
            return None

        return hashlib.md5(normalized.encode("utf-8")).hexdigest()

    def _normalize_content(self, content: str) -> str:
        """规范化内容以用于哈希计算"""
        if not content:
            return ""

        # 去除多余空白
        normalized = re.sub(r"\s+", " ", content.strip())

        # 去除常见的时间戳模式
        normalized = re.sub(r"\d{4}[-/年]\d{1,2}[-/月]\d{1,2}[日\s]*\d{1,2}:\d{2}", "", normalized)
        normalized = re.sub(r"\d{1,2}:\d{2}(:\d{2})?", "", normalized)

        # 去除特殊符号
        normalized = re.sub(r"[^\w\s一-鿿]", "", normalized)

        return normalized

    def _check_approximate_duplicate(self, doc: DocumentV1) -> DeduplicationResult:
        """
        检查近似重复（简单版本，基于标题和内容开头的相似度）

        生产环境可以使用：
        - MinHash + LSH
        - SimHash
        - 向量相似度
        """
        result = DeduplicationResult()

        # 简化实现：暂不做复杂的近似重复检测
        # 可以在后续扩展中添加向量存储和相似度查询

        return result
