"""爬虫摄取桥接器 — 将所有爬虫输出统一转为 IngestionQueueItem 入队

职责：
    Crawler 只负责抓取，CrawlerIngestionBridge 负责：
    1. 将爬虫输出转为 DocumentEnvelope
    2. 封装为 EnqueueRequest
    3. 通过 IngestionQueueService 入队
"""
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.contracts import DocumentEnvelope
from core.contracts.ingestion import EnqueueRequest
from core.observability import get_logger

logger = get_logger(__name__)

SOURCE_TYPE_TO_CATEGORY: Dict[str, str] = {
    "cls": "news",
    "cnstock": "news",
    "zq": "report",
    "report": "report",
    "pdf": "pdf",
    "manual": "internal_note",
}

DEFAULT_PRIORITIES: Dict[str, int] = {
    "zq": 1,
    "report": 1,
    "cls": 0,
    "cnstock": 0,
    "pdf": 0,
    "manual": 0,
}


class CrawlerIngestionBridge:
    """爬虫摄取桥接器 — 统一入口，将爬虫输出送入摄取队列"""

    def __init__(self, queue_service: Any) -> None:
        self._queue_service = queue_service

    def submit_crawled_item(self, source_type: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """将单个爬虫条目入队

        Args:
            source_type: 爬虫来源标识（cls, cnstock, zq, report, manual 等）
            item: 爬虫输出的原始字典，至少包含 title/content，可选 url/id/published_at

        Returns:
            enqueue 结果字典，含 item_id, dedup_hash, was_duplicate, message
        """
        envelope = self._to_document_envelope(source_type, item)
        request = EnqueueRequest(
            source_type=source_type,
            source_id=envelope.doc_id,
            raw_content=envelope.raw_text,
            title=envelope.title,
            url=item.get("url", ""),
            priority=self._infer_priority(source_type),
        )
        result = self._queue_service.enqueue(request)
        logger.info(
            "Crawler item submitted to queue",
            source_type=source_type,
            doc_id=envelope.doc_id,
            item_id=result["item_id"],
            was_duplicate=result.get("was_duplicate", False),
        )
        return result

    def submit_batch(self, source_type: str, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """批量将爬虫条目入队"""
        results: List[Dict[str, Any]] = []
        for item in items:
            result = self.submit_crawled_item(source_type, item)
            results.append(result)
        logger.info("Batch submitted to queue", source_type=source_type, count=len(results))
        return results

    def _to_document_envelope(self, source_type: str, item: Dict[str, Any]) -> DocumentEnvelope:
        item_id = item.get("id") or self._hash_item(item)
        category = SOURCE_TYPE_TO_CATEGORY.get(source_type, "news")
        return DocumentEnvelope(
            doc_id=item_id,
            source_type=category,  # type: ignore[arg-type]
            title=item.get("title", ""),
            source_name=item.get("source_name", source_type),
            raw_text=item.get("content", ""),
            canonical_text=item.get("content", ""),
            published_at=item.get("published_at"),
            metadata={
                "url": item.get("url"),
                "crawler": source_type,
            },
        )

    @staticmethod
    def _infer_priority(source_type: str) -> int:
        return DEFAULT_PRIORITIES.get(source_type, 0)

    @staticmethod
    def _hash_item(item: Dict[str, Any]) -> str:
        raw = item.get("content", "") or item.get("title", "") or str(uuid.uuid4())
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
