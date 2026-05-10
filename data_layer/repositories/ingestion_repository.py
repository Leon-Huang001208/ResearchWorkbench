"""统一摄取队列仓储"""
import hashlib
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func

from core.contracts.ingestion import IngestionQueueItem, IngestionQueueStats
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import IngestionQueueItemDB

logger = get_logger(__name__)


class IngestionQueueRepository(BaseRepository):
    """统一摄取队列仓储"""

    def enqueue(self, item: IngestionQueueItem) -> IngestionQueueItem:
        """入队（含去重检查）"""
        # 生成 dedup_hash
        if item.dedup_hash is None:
            item.dedup_hash = self._compute_dedup_hash(item)

        # 去重检查
        existing = self.find_by_dedup_hash(item.dedup_hash)
        if existing:
            logger.info(
                "Duplicate item skipped",
                dedup_hash=item.dedup_hash,
                existing_item_id=existing.item_id,
            )
            return existing

        db_item = IngestionQueueItemDB(
            item_id=item.item_id,
            source_type=item.source_type,
            source_id=item.source_id,
            raw_content=item.raw_content,
            title=item.title,
            url=item.url,
            priority=item.priority,
            status=item.status,
            retry_count=item.retry_count,
            max_retries=item.max_retries,
            failure_reason=item.failure_reason,
            created_at=item.created_at,
            processed_at=item.processed_at,
            dedup_hash=item.dedup_hash,
        )
        self.db.add(db_item)
        self.db.flush()
        logger.info("Item enqueued", item_id=item.item_id, source_type=item.source_type)
        return self._to_domain(db_item)

    def dequeue(self, limit: int = 10) -> List[IngestionQueueItem]:
        """出队（按 priority 降序 + created_at 升序）"""
        db_items = (
            self.db.query(IngestionQueueItemDB)
            .filter(IngestionQueueItemDB.status == "pending")
            .order_by(
                IngestionQueueItemDB.priority.desc(),
                IngestionQueueItemDB.created_at.asc(),
            )
            .limit(limit)
            .all()
        )

        # 标记为 processing
        for db_item in db_items:
            db_item.status = "processing"
        self.db.flush()

        result = [self._to_domain(db_item) for db_item in db_items]
        if result:
            logger.info("Dequeued items", count=len(result))
        return result

    def mark_completed(self, item_id: str) -> Optional[IngestionQueueItem]:
        """标记完成"""
        db_item = self.db.query(IngestionQueueItemDB).filter_by(item_id=item_id).first()
        if not db_item:
            return None
        db_item.status = "completed"
        db_item.processed_at = datetime.now(timezone.utc)
        self.db.flush()
        logger.info("Item completed", item_id=item_id)
        return self._to_domain(db_item)

    def mark_failed(self, item_id: str, reason: str) -> Optional[IngestionQueueItem]:
        """标记失败（retry_count < max_retries 时重置为 pending 以便重试）"""
        db_item = self.db.query(IngestionQueueItemDB).filter_by(item_id=item_id).first()
        if not db_item:
            return None
        db_item.retry_count += 1
        db_item.failure_reason = reason
        if db_item.retry_count < db_item.max_retries:
            db_item.status = "pending"  # 重置为 pending 以便重试
            logger.info(
                "Item failed, queued for retry",
                item_id=item_id,
                retry_count=db_item.retry_count,
                max_retries=db_item.max_retries,
            )
        else:
            db_item.status = "failed"
            logger.warning(
                "Item failed permanently",
                item_id=item_id,
                retry_count=db_item.retry_count,
                reason=reason,
            )
        self.db.flush()
        return self._to_domain(db_item)

    def get_stats(self) -> IngestionQueueStats:
        """队列统计"""
        pending = (
            self.db.query(func.count(IngestionQueueItemDB.item_id))
            .filter(IngestionQueueItemDB.status == "pending")
            .scalar()
            or 0
        )
        processing = (
            self.db.query(func.count(IngestionQueueItemDB.item_id))
            .filter(IngestionQueueItemDB.status == "processing")
            .scalar()
            or 0
        )
        completed = (
            self.db.query(func.count(IngestionQueueItemDB.item_id))
            .filter(IngestionQueueItemDB.status == "completed")
            .scalar()
            or 0
        )
        failed = (
            self.db.query(func.count(IngestionQueueItemDB.item_id))
            .filter(IngestionQueueItemDB.status == "failed")
            .scalar()
            or 0
        )

        # 计算平均延迟
        avg_latency_result = (
            self.db.query(
                func.avg(
                    func.strftime("%s", IngestionQueueItemDB.processed_at)
                    - func.strftime("%s", IngestionQueueItemDB.created_at)
                )
                * 1000
            )
            .filter(
                IngestionQueueItemDB.status == "completed",
                IngestionQueueItemDB.processed_at.isnot(None),
            )
            .scalar()
        )
        avg_latency_ms = float(avg_latency_result) if avg_latency_result else 0.0

        return IngestionQueueStats(
            depth=pending + processing,
            pending=pending,
            processing=processing,
            completed=completed,
            failed=failed,
            avg_latency_ms=avg_latency_ms,
        )

    def find_by_dedup_hash(self, dedup_hash: str) -> Optional[IngestionQueueItem]:
        """根据去重哈希查找"""
        db_item = (
            self.db.query(IngestionQueueItemDB)
            .filter_by(dedup_hash=dedup_hash)
            .first()
        )
        if not db_item:
            return None
        return self._to_domain(db_item)

    def get_failed_items(self, limit: int = 100) -> List[IngestionQueueItem]:
        """获取失败项"""
        db_items = (
            self.db.query(IngestionQueueItemDB)
            .filter(IngestionQueueItemDB.status == "failed")
            .order_by(IngestionQueueItemDB.created_at.asc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(db_item) for db_item in db_items]

    def get_recent(self, limit: int = 20) -> List[IngestionQueueItem]:
        """获取最近处理记录"""
        db_items = (
            self.db.query(IngestionQueueItemDB)
            .filter(IngestionQueueItemDB.status.in_(["completed", "failed"]))
            .order_by(IngestionQueueItemDB.processed_at.desc())
            .limit(limit)
            .all()
        )
        return [self._to_domain(db_item) for db_item in db_items]

    def reset_failed_for_retry(self, limit: int = 100) -> int:
        """将失败项重置为 pending 以便重试"""
        db_items = (
            self.db.query(IngestionQueueItemDB)
            .filter(IngestionQueueItemDB.status == "failed")
            .order_by(IngestionQueueItemDB.created_at.asc())
            .limit(limit)
            .all()
        )
        count = 0
        for db_item in db_items:
            db_item.status = "pending"
            db_item.retry_count = 0
            db_item.failure_reason = None
            count += 1
        self.db.flush()
        logger.info("Reset failed items for retry", count=count)
        return count

    def _compute_dedup_hash(self, item: IngestionQueueItem) -> str:
        """计算去重哈希"""
        # 优先用 (source_type, source_id) 如果 source_id 存在
        if item.source_id:
            raw = f"{item.source_type}:{item.source_id}"
        else:
            # 否则对 raw_content 做 hash
            raw = f"{item.source_type}:{hashlib.sha256(item.raw_content.encode()).hexdigest()[:16]}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _to_domain(self, db_item: IngestionQueueItemDB) -> IngestionQueueItem:
        """转换为领域模型"""
        return IngestionQueueItem(
            item_id=db_item.item_id,
            source_type=db_item.source_type,
            source_id=db_item.source_id,
            raw_content=db_item.raw_content,
            title=db_item.title,
            url=db_item.url,
            priority=db_item.priority,
            status=db_item.status,
            retry_count=db_item.retry_count,
            max_retries=db_item.max_retries,
            failure_reason=db_item.failure_reason,
            created_at=db_item.created_at,
            processed_at=db_item.processed_at,
            dedup_hash=db_item.dedup_hash,
        )
