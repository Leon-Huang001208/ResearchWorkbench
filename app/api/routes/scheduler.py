"""Scheduler API — 自动数据刷新调度管理"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from core.observability import get_logger
from core.services.crawl_scheduler import (
    APSCHEDULER_AVAILABLE,
    CrawlScheduler,
    get_crawl_scheduler,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

# 全局调度器实例
_scheduler_instance: Optional[CrawlScheduler] = None


def _get_scheduler() -> CrawlScheduler:
    """获取调度器实例（延迟初始化）"""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = get_crawl_scheduler()
    return _scheduler_instance


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """获取调度器状态"""
    if not APSCHEDULER_AVAILABLE:
        return {
            "available": False,
            "message": "APScheduler not installed",
        }

    scheduler = _get_scheduler()
    status = scheduler.get_status()

    return {
        "available": True,
        **status,
    }


@router.post("/start")
async def start_scheduler() -> Dict[str, Any]:
    """启动调度器"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    scheduler = _get_scheduler()
    if scheduler.running:
        return {"success": True, "message": "Scheduler already running"}

    scheduler.start()
    return {"success": True, "message": "Scheduler started"}


@router.post("/stop")
async def stop_scheduler() -> Dict[str, Any]:
    """停止调度器"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    scheduler = _get_scheduler()
    if not scheduler.running:
        return {"success": True, "message": "Scheduler already stopped"}

    scheduler.stop()
    return {"success": True, "message": "Scheduler stopped"}


@router.post("/trigger/{source_type}")
async def trigger_crawl(source_type: str) -> Dict[str, Any]:
    """手动触发指定来源的抓取"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    scheduler = _get_scheduler()

    # 转换为 SourceType
    from core.contracts import SourceType

    try:
        st = SourceType(source_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source type: {source_type}")

    result = scheduler.trigger_crawl(st)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_type}")

    return {"success": True, "result": result}


@router.post("/backfill/{source_type}")
async def trigger_backfill(source_type: str, lookback_days: int = 7) -> Dict[str, Any]:
    """手动触发补漏"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    scheduler = _get_scheduler()

    from core.contracts import SourceType

    try:
        st = SourceType(source_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source type: {source_type}")

    result = scheduler.trigger_backfill(st, lookback_days)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_type}")

    return {"success": True, "result": result}
