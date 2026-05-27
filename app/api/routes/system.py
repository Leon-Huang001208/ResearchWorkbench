"""System health endpoint — scheduler / queue / worker 状态"""

from datetime import datetime, timezone
from typing import Any, Dict, List

from fastapi import APIRouter

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def get_health():
    """返回系统健康状态"""
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.ingestion_repository import IngestionQueueRepository

        db = SessionLocal()
        try:
            repo = IngestionQueueRepository(db)
            stats = repo.get_stats()

            heartbeats = event_bus.get_worker_heartbeats()

            return {
                "status": "healthy",
                "scheduler": "active",
                "db_connected": True,
                "queue_depth": stats.depth,
                "queue_pending": stats.pending,
                "queue_processing": stats.processing,
                "queue_completed": stats.completed,
                "queue_failed": stats.failed,
                "avg_latency_ms": round(stats.avg_latency_ms, 2),
                "worker_heartbeats": heartbeats,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "degraded",
            "scheduler": "unknown",
            "db_connected": False,
            "queue_depth": 0,
            "queue_pending": 0,
            "queue_processing": 0,
            "queue_completed": 0,
            "queue_failed": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }


@router.post("/event")
async def publish_event(request: dict):
    """发布系统事件到 event bus（用于外部系统/测试集成）"""
    event_type = request.get("event_type", "system")
    payload = request.get("payload", {})
    event = await event_bus.publish(event_type, payload)
    return {"status": "published", "event_id": event.event_id}


@router.get("/health/minimal")
async def get_health_minimal():
    """最小健康检查（不查数据库，快速返回）"""
    heartbeats = event_bus.get_worker_heartbeats()
    return {
        "status": "ok",
        "worker_heartbeats": heartbeats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/workers/status")
async def get_workers_status():
    """聚合返回所有后台 worker 的实时状态和队列统计"""
    result: Dict[str, Any] = {
        "workers": [],
        "scheduler": {"name": "crawl_scheduler", "alive": False, "pid": None},
        "queue_stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
    }

    # ── Knowledge Workers (PID-based) ──────────────────────────
    try:
        from workers.knowledge_worker import get_all_worker_statuses

        kw_statuses: List[Dict[str, Any]] = get_all_worker_statuses()
        for ws in kw_statuses:
            worker_info: Dict[str, Any] = {
                "name": f"knowledge_worker_{ws.get('worker_id')}" if ws.get("worker_id") is not None else "knowledge_worker",
                "type": "knowledge",
                "pid": ws.get("pid"),
                "alive": ws.get("alive", False),
            }
            result["workers"].append(worker_info)
    except Exception as e:
        logger.warning(f"Failed to get knowledge worker statuses: {e}")

    # ── Crawl Scheduler (PID-based) ────────────────────────────
    try:
        from services.crawl_scheduler import get_scheduler_process_status

        scheduler_status = get_scheduler_process_status()
        result["scheduler"] = {
            "name": "crawl_scheduler",
            "pid": scheduler_status.get("pid"),
            "alive": scheduler_status.get("alive", False),
        }
    except Exception as e:
        logger.warning(f"Failed to get scheduler process status: {e}")

    # ── Heartbeats (in-process event_bus) ──────────────────────
    heartbeats = event_bus.get_worker_heartbeats()
    for worker_info in result["workers"]:
        name = worker_info["name"]
        if name in heartbeats:
            hb = heartbeats[name]
            worker_info["last_heartbeat"] = hb.get("timestamp") if isinstance(hb, dict) else hb
            worker_info["activity"] = hb.get("activity") if isinstance(hb, dict) else None
        else:
            worker_info["last_heartbeat"] = None
            worker_info["activity"] = None

    sched_name = result["scheduler"]["name"]
    if sched_name in heartbeats:
        hb = heartbeats[sched_name]
        result["scheduler"]["last_heartbeat"] = hb.get("timestamp") if isinstance(hb, dict) else hb
        result["scheduler"]["activity"] = hb.get("activity") if isinstance(hb, dict) else None
    else:
        result["scheduler"]["last_heartbeat"] = None
        result["scheduler"]["activity"] = None

    # ── Queue Stats ────────────────────────────────────────────
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.ingestion_repository import IngestionQueueRepository

        db = SessionLocal()
        try:
            repo = IngestionQueueRepository(db)
            stats = repo.get_stats()
            result["queue_stats"] = {
                "pending": stats.pending,
                "processing": stats.processing,
                "completed": stats.completed,
                "failed": stats.failed,
            }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to get queue stats: {e}")

    return result
