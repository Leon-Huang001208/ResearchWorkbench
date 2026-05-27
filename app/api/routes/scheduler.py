"""Scheduler API — 自动数据刷新调度管理

调度器跑在独立进程 (workers/crawl_scheduler_worker.py)，
API 通过 subprocess/PID 文件和 DB 共享状态与其交互。
"""
import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from core.contracts import SourceType
from core.observability import get_logger
from services.crawl_orchestrator import CrawlOrchestrator
from services.crawl_scheduler import (
    APSCHEDULER_AVAILABLE,
    DEFAULT_CRAWL_CONFIGS,
    SourceCrawlConfig,
    build_scheduler_status,
    get_scheduler_process_status,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/api/scheduler", tags=["scheduler"])

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent
PID_FILE = PROJECT_DIR / "logs" / "scheduler.pid"


def _get_config(source_type: SourceType) -> SourceCrawlConfig | None:
    for cfg in DEFAULT_CRAWL_CONFIGS:
        if cfg.source_type == source_type:
            return cfg
    return None


@router.get("/status")
async def get_scheduler_status() -> Dict[str, Any]:
    """获取调度器状态"""
    if not APSCHEDULER_AVAILABLE:
        return {"available": False, "message": "APScheduler not installed"}

    process_status = get_scheduler_process_status(str(PID_FILE))
    db_status = build_scheduler_status()

    return {
        "available": True,
        "running": process_status["alive"],
        "current_time": db_status["current_time"],
        "sources": db_status["sources"],
        "jobs": [],
    }


@router.post("/start")
async def start_scheduler() -> Dict[str, Any]:
    """启动调度器进程"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    process_status = get_scheduler_process_status(str(PID_FILE))
    if process_status["alive"]:
        return {
            "success": True,
            "message": "Scheduler already running",
            "pid": process_status["pid"],
        }

    worker_module = "workers.crawl_scheduler_worker"
    try:
        subprocess.Popen(
            [sys.executable, "-m", worker_module],
            cwd=str(PROJECT_DIR),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except Exception as e:
        logger.error("Failed to start scheduler process", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to start scheduler: {e}")

    return {"success": True, "message": "Scheduler process started"}


@router.post("/stop")
async def stop_scheduler() -> Dict[str, Any]:
    """停止调度器进程"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    process_status = get_scheduler_process_status(str(PID_FILE))
    if not process_status["alive"]:
        if PID_FILE.exists():
            PID_FILE.unlink()
        return {"success": True, "message": "Scheduler already stopped"}

    try:
        os.kill(process_status["pid"], signal.SIGTERM)
    except OSError as e:
        logger.error("Failed to stop scheduler", error=str(e))
        raise HTTPException(status_code=500, detail=f"Failed to stop scheduler: {e}")

    return {"success": True, "message": "Scheduler stopped", "pid": process_status["pid"]}


@router.post("/trigger/{source_type}")
async def trigger_crawl(source_type: str) -> Dict[str, Any]:
    """手动触发指定来源的抓取"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    try:
        st = SourceType(source_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source type: {source_type}")

    config = _get_config(st)
    if not config:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_type}")

    orchestrator = CrawlOrchestrator()
    result = await asyncio.to_thread(
        orchestrator.crawl_source,
        source_type=config.source_type,
        source_name=config.source_name,
        days=config.days_per_crawl,
        max_docs=config.max_docs,
        enable_backfill=config.backfill_enabled,
    )

    return {
        "success": True,
        "result": {
            "source_type": source_type,
            "success_count": result.success_count,
            "skipped_count": result.skipped_count,
            "failure_count": result.failure_count,
            "saved_doc_ids": result.saved_doc_ids,
        },
    }


@router.post("/backfill/{source_type}")
async def trigger_backfill(source_type: str, lookback_days: int = 7) -> Dict[str, Any]:
    """手动触发补漏"""
    if not APSCHEDULER_AVAILABLE:
        raise HTTPException(status_code=500, detail="APScheduler not installed")

    try:
        st = SourceType(source_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source type: {source_type}")

    config = _get_config(st)
    if not config:
        raise HTTPException(status_code=404, detail=f"Source not found: {source_type}")

    orchestrator = CrawlOrchestrator()
    result = await asyncio.to_thread(
        orchestrator.backfill_source,
        source_type=config.source_type,
        lookback_days=lookback_days,
    )

    return {
        "success": True,
        "result": {
            "source_type": source_type,
            "success_count": result.success_count,
            "skipped_count": result.skipped_count,
            "failure_count": result.failure_count,
        },
    }
