"""Processed Item Repository — 已处理项目仓储"""
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import and_, func
from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.repositories.models import ProcessedItemV1DB

logger = get_logger(__name__)


def item_exists(db: Session, item_id: str) -> bool:
    """检查项目是否已处理"""
    return (
        db.query(ProcessedItemV1DB).filter(ProcessedItemV1DB.item_id == item_id).first() is not None
    )


def item_exists_by_hash(db: Session, content_hash: str) -> bool:
    """通过内容哈希检查项目是否已处理"""
    if not content_hash:
        return False
    return (
        db.query(ProcessedItemV1DB).filter(ProcessedItemV1DB.content_hash == content_hash).first()
        is not None
    )


def add_processed_item(db: Session, item: ProcessedItemV1DB) -> ProcessedItemV1DB:
    """添加已处理项目"""
    existing = db.query(ProcessedItemV1DB).filter(ProcessedItemV1DB.item_id == item.item_id).first()

    if existing:
        # 已存在，增加处理计数
        existing.process_count += 1
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # 新记录
        db.add(item)
        db.commit()
        db.refresh(item)
        return item


def get_recent_processed(
    db: Session, source_type: str, source_name: Optional[str] = None, limit: int = 100
) -> list[ProcessedItemV1DB]:
    """获取最近处理的项目"""
    query = db.query(ProcessedItemV1DB).filter(ProcessedItemV1DB.source_type == source_type)
    if source_name:
        query = query.filter(ProcessedItemV1DB.source_name == source_name)

    return query.order_by(ProcessedItemV1DB.first_seen_at.desc()).limit(limit).all()


def get_processed_stats(
    db: Session, source_type: Optional[str] = None, since: Optional[datetime] = None
) -> dict:
    """获取处理统计"""
    query = db.query(ProcessedItemV1DB)

    if source_type:
        query = query.filter(ProcessedItemV1DB.source_type == source_type)

    if since:
        query = query.filter(ProcessedItemV1DB.first_seen_at >= since)

    total = query.count()

    # 按来源类型分组统计
    if not source_type:
        type_stats = (
            db.query(ProcessedItemV1DB.source_type, func.count(ProcessedItemV1DB.item_id))
            .group_by(ProcessedItemV1DB.source_type)
            .all()
        )
        by_type = {st[0]: st[1] for st in type_stats}
    else:
        by_type = {source_type: total}

    return {"total_items": total, "by_source_type": by_type}


def get_processed_stats_by_day(db: Session, source_type: str, days: int = 7) -> list[dict]:
    """按天获取处理统计"""
    since = datetime.utcnow() - timedelta(days=days)

    items = (
        db.query(ProcessedItemV1DB)
        .filter(
            and_(
                ProcessedItemV1DB.source_type == source_type,
                ProcessedItemV1DB.first_seen_at >= since,
            )
        )
        .all()
    )

    # 简单的按天聚合
    stats = {}
    for item in items:
        day = item.first_seen_at.date().isoformat()
        stats[day] = stats.get(day, 0) + 1

    return [{"date": k, "count": v} for k, v in sorted(stats.items())]
