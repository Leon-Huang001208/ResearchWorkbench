"""Crawl State Repository — 爬虫状态仓储"""
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from core.observability import get_logger
from data_layer.repositories.models import CrawlStateV1DB

logger = get_logger(__name__)


def get_crawl_state(
    db: Session, source_type: str, source_name: Optional[str] = None
) -> Optional[CrawlStateV1DB]:
    """获取指定来源的爬虫状态"""
    query = db.query(CrawlStateV1DB).filter(CrawlStateV1DB.source_type == source_type)
    if source_name:
        query = query.filter(CrawlStateV1DB.source_name == source_name)
    return query.first()


def get_all_crawl_states(db: Session) -> list[CrawlStateV1DB]:
    """获取所有来源的爬虫状态"""
    return db.query(CrawlStateV1DB).all()


def upsert_crawl_state(db: Session, state: CrawlStateV1DB) -> CrawlStateV1DB:
    """更新或插入爬虫状态"""
    source_name = str(state.source_name) if state.source_name is not None else None
    existing = get_crawl_state(db, str(state.source_type), source_name)
    if existing:
        # 更新现有记录
        for key, value in vars(state).items():
            if not key.startswith("_"):
                setattr(existing, key, value)
        existing.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        return existing
    else:
        # 插入新记录
        db.add(state)
        db.commit()
        db.refresh(state)
        return state


def pause_crawl(db: Session, source_type: str, reason: str) -> Optional[CrawlStateV1DB]:
    """暂停指定来源的爬虫"""
    state = get_crawl_state(db, source_type)
    if state:
        state.is_paused = True
        state.pause_reason = reason
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
        logger.info(f"Crawling paused for {source_type}: {reason}")
    return state


def resume_crawl(db: Session, source_type: str) -> Optional[CrawlStateV1DB]:
    """恢复指定来源的爬虫"""
    state = get_crawl_state(db, source_type)
    if state:
        state.is_paused = False
        state.pause_reason = None
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
        logger.info(f"Crawling resumed for {source_type}")
    return state


def update_watermark(
    db: Session,
    source_type: str,
    watermark_id: str,
    watermark_ts: datetime,
    watermark_metadata: Optional[dict] = None,
) -> Optional[CrawlStateV1DB]:
    """更新水位线"""
    state = get_crawl_state(db, source_type)
    if state:
        state.watermark_id = watermark_id
        state.watermark_timestamp = watermark_ts
        if watermark_metadata:
            state.watermark_metadata = watermark_metadata
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
    return state


def increment_crawl_stats(
    db: Session, source_type: str, fetched: int = 0, skipped: int = 0, failed: int = 0
) -> Optional[CrawlStateV1DB]:
    """递增爬虫统计"""
    state = get_crawl_state(db, source_type)
    if state:
        state.total_fetched += fetched
        state.total_skipped += skipped
        state.total_failed += failed
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
    return state


def reset_crawl_state(db: Session, source_type: str) -> Optional[CrawlStateV1DB]:
    """重置爬虫状态（清除水位线和统计）"""
    state = get_crawl_state(db, source_type)
    if state:
        state.watermark_id = None
        state.watermark_timestamp = None
        state.watermark_metadata = {}
        state.total_fetched = 0
        state.total_skipped = 0
        state.total_failed = 0
        state.dedupe_key = None
        state.dedupe_count = 0
        state.last_run_id = None
        state.last_run_start = None
        state.last_run_end = None
        state.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(state)
        logger.info(f"Crawl state reset for {source_type}")
    return state
