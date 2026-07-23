"""统一摄取队列服务 — 将实时源事件归一化后送入 Golden Path"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.contracts import CanonicalEvent
from core.contracts.ingestion import EnqueueRequest, IngestionQueueItem, IngestionQueueStats
from core.observability import MetricsCollector, get_logger
from data_layer.repositories.ingestion_repository import IngestionQueueRepository

logger = get_logger(__name__)

# 事件类型映射：source_type -> event_type hint
_SOURCE_TYPE_TO_EVENT_TYPE = {
    "cls": "regulation",
    "cnstock": "regulation",
    "cnstock_flash": "regulation",
    "zq": "earnings",
    "zhiqiu_reports": "earnings",
    "zhiqiu_wechat": "industry",
    "zhiqiu_transcript": "earnings",
    "report": "earnings",
    "manual": "other",
}


class IngestionQueueService:
    """统一摄取队列服务"""

    def __init__(
        self,
        repository: IngestionQueueRepository,
        pipeline: Optional[Any] = None,
    ):
        self._repo = repository
        self._pipeline = pipeline
        self._metrics = MetricsCollector()

    def enqueue(self, request: EnqueueRequest) -> Dict[str, Any]:
        """入队（含去重检查）"""
        item = IngestionQueueItem(
            item_id=str(uuid.uuid4()),
            source_type=request.source_type,
            source_id=request.source_id,
            raw_content=request.raw_content,
            title=request.title,
            url=request.url,
            priority=request.priority,
            created_at=datetime.now(timezone.utc),
            published_at=request.published_at,
        )

        persisted = self._repo.enqueue(item)
        was_duplicate = persisted.item_id != item.item_id

        self._metrics.increment(
            "ingestion_queue.enqueue",
            tags={"source_type": request.source_type, "duplicate": str(was_duplicate)},
        )

        logger.info(
            "Enqueue result",
            item_id=persisted.item_id,
            dedup_hash=persisted.dedup_hash,
            was_duplicate=was_duplicate,
        )

        return {
            "item_id": persisted.item_id,
            "dedup_hash": persisted.dedup_hash or "",
            "was_duplicate": was_duplicate,
            "message": "duplicate_skipped" if was_duplicate else "enqueued",
        }

    def dequeue(self, limit: int = 10) -> List[IngestionQueueItem]:
        """出队"""
        items = self._repo.dequeue(limit=limit)
        self._metrics.increment("ingestion_queue.dequeue", value=len(items))
        return items

    async def process_item(self, item: IngestionQueueItem) -> Dict[str, Any]:
        """处理单个队列项：归一化为 CanonicalEvent -> 送入 Golden Path"""
        self._metrics.increment(
            "ingestion_queue.process_item", tags={"source_type": item.source_type}
        )
        logger.info("Processing item", item_id=item.item_id, source_type=item.source_type)

        try:
            # 归一化为 CanonicalEvent
            event = self._normalize_to_event(item)

            # 送入 Golden Path（如果 pipeline 可用）
            if self._pipeline is not None:
                signal = await self._pipeline.run_event_signal(event)
                logger.info(
                    "Golden Path completed for item",
                    item_id=item.item_id,
                    signal_id=signal.signal_id,
                )
                result = {
                    "item_id": item.item_id,
                    "event_id": event.event_id,
                    "signal_id": signal.signal_id,
                    "status": "completed",
                }
            else:
                logger.info(
                    "No pipeline available, item normalized only",
                    item_id=item.item_id,
                )
                result = {
                    "item_id": item.item_id,
                    "event_id": event.event_id,
                    "signal_id": None,
                    "status": "completed_no_pipeline",
                }

            # 标记完成
            self._repo.mark_completed(item.item_id)
            self._metrics.increment("ingestion_queue.item_completed")
            return result

        except Exception as e:
            logger.error(
                "Failed to process item",
                item_id=item.item_id,
                error=str(e),
                exc_info=True,
            )
            self._repo.mark_failed(item.item_id, str(e))
            self._metrics.increment("ingestion_queue.item_failed")
            return {
                "item_id": item.item_id,
                "status": "failed",
                "error": str(e),
            }

    async def process_batch(self, limit: int = 10) -> Dict[str, Any]:
        """处理下一批队列项"""
        items = self.dequeue(limit=limit)
        if not items:
            return {"processed_count": 0, "results": []}

        results = []
        for item in items:
            result = await self.process_item(item)
            results.append(result)

        logger.info("Batch processed", count=len(results))
        return {"processed_count": len(results), "results": results}

    def get_stats(self) -> IngestionQueueStats:
        """队列统计"""
        stats = self._repo.get_stats()
        self._metrics.record("ingestion_queue.depth", stats.depth)
        self._metrics.record("ingestion_queue.failed", stats.failed)
        return stats

    def retry_failed(self, limit: int = 100) -> Dict[str, Any]:
        """重试失败项"""
        count = self._repo.reset_failed_for_retry(limit=limit)
        self._metrics.increment("ingestion_queue.retry", value=count)
        logger.info("Failed items reset for retry", count=count)
        return {"retried_count": count, "message": f"Reset {count} items for retry"}

    def get_recent(self, limit: int = 20) -> List[IngestionQueueItem]:
        """获取最近处理记录"""
        return self._repo.get_recent(limit=limit)

    def _normalize_to_event(self, item: IngestionQueueItem) -> CanonicalEvent:
        """将 IngestionQueueItem 归一化为 CanonicalEvent"""
        # 确定事件类型
        event_type = _SOURCE_TYPE_TO_EVENT_TYPE.get(item.source_type, "other")

        # 构建摘要：优先使用 title，否则截取 raw_content
        summary = item.title or item.raw_content[:200]

        return CanonicalEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            source_type=item.source_type,
            source_name=item.source_type,
            title=item.title or item.raw_content[:80],
            summary=summary[:200],
            event_time=item.created_at,
            impact_direction="unknown",
            confidence=0.7,
            needs_review=True,
            entities=[],
            assertions=[],
            evidence_spans=[{"text": item.raw_content[:300], "source_type": item.source_type}],
            source_doc_id=item.item_id,
        )
