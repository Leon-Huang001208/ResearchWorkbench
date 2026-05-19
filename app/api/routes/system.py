"""System health endpoint — scheduler / queue / worker 状态"""

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from core.observability import get_logger
from core.services.system_event_bus import event_bus

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
