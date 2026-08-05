"""System health endpoint — scheduler / queue / worker 状态"""

import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from core.observability import get_logger
from services.system_event_bus import event_bus

logger = get_logger(__name__)

# 优先使用环境变量，打包部署（Tauri sidecar）时 __file__ 指向 exe 内部路径失效
PROJECT_DIR = (
    Path(os.environ["ALPHAFOUNDRY_PROJECT_ROOT"])
    if "ALPHAFOUNDRY_PROJECT_ROOT" in os.environ
    else Path(__file__).resolve().parent.parent.parent.parent
)

router = APIRouter(prefix="/api/system", tags=["system"])
_resource_monitoring_service_lock = threading.Lock()


def get_resource_monitoring_service() -> Any:
    """延迟创建并复用进程资源监控服务。"""
    with _resource_monitoring_service_lock:
        service = getattr(get_resource_monitoring_service, "_instance", None)
        if service is None:
            from services.resource_monitor_service import ResourceMonitoringService

            service = ResourceMonitoringService()
            get_resource_monitoring_service._instance = service
    return service


class ResourceEventResolveRequest(BaseModel):
    """人工解决资源异常时可选的处理说明。"""

    notes: str = Field(default="", max_length=500)


def _resource_event_service_call(callback: Any) -> Any:
    """在独立数据库会话中执行资源事件操作，避免跨请求复用 Session。"""
    from data_layer.repositories.base import db_session
    from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
    from services.resource_monitor_alert_service import ResourceMonitorAlertService

    with db_session() as session:
        return callback(ResourceMonitorAlertService(MonitoringRepositoryImpl(session)))


def _sanitize_resource_warning(warning: Any) -> Dict[str, Any]:
    """将服务内部采集错误映射为稳定的公开警告码。"""
    if not isinstance(warning, dict):
        return {"code": "partial_data"}

    if warning.get("code") == "root_process_unavailable":
        return {"code": "root_process_unavailable"}

    if warning.get("code") == "process_field_unavailable":
        public_warning: Dict[str, Any] = {"code": "field_unavailable"}
        if warning.get("pid") is not None:
            public_warning["pid"] = warning["pid"]
        if warning.get("field") is not None:
            public_warning["field"] = warning["field"]
        return public_warning

    if warning.get("code") == "managed_process_unavailable":
        public_warning = {"code": "managed_process_unavailable"}
        if isinstance(warning.get("pid"), int):
            public_warning["pid"] = warning["pid"]
        return public_warning

    return {"code": "partial_data"}


def _sanitize_resource_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """移除资源采集实现细节，避免将内部异常类型暴露给 API 调用方。"""
    public_snapshot = dict(snapshot)
    warnings = snapshot.get("warnings", [])
    public_snapshot["warnings"] = (
        [_sanitize_resource_warning(warning) for warning in warnings]
        if isinstance(warnings, list)
        else [{"code": "partial_data"}]
    )

    processes = snapshot.get("processes", [])
    if isinstance(processes, list):
        public_processes = []
        for process in processes:
            if not isinstance(process, dict):
                continue
            public_process = dict(process)
            if public_process.get("unavailable_reason") is not None:
                public_process["unavailable_reason"] = "field_unavailable"
            public_processes.append(public_process)
        public_snapshot["processes"] = public_processes
    else:
        public_snapshot["processes"] = []
    task_failures = snapshot.get("task_failures", [])
    public_snapshot["task_failures"] = [
        _sanitize_resource_task(task) for task in task_failures if isinstance(task, dict)
    ]
    return public_snapshot


def _sanitize_resource_task(task: Dict[str, Any]) -> Dict[str, Any]:
    """仅公开任务归因字段，避免错误文本或其他运行时内容离开 API。"""
    allowed = {"task_id", "task_kind", "source_key", "label", "pid", "error_type", "failed_at"}
    return {
        key: value
        for key, value in task.items()
        if key in allowed and isinstance(value, (str, int, float, type(None)))
    }


def _serialize_resource_event(event: Any) -> Dict[str, Any]:
    """将 Pydantic 资源告警映射为仅含安全字段的 JSON 响应。"""
    metadata = event.metadata if isinstance(getattr(event, "metadata", None), dict) else {}
    allowed_metadata = {
        "event_kind",
        "task_id",
        "task_kind",
        "source_key",
        "label",
        "pid",
        "role",
        "attribution_kind",
        "confidence",
        "error_type",
        "cpu_percent",
        "memory_bytes",
    }
    return {
        "alert_id": event.alert_id,
        "severity": event.severity.value,
        "status": event.status.value,
        "title": event.title,
        "description": event.description,
        "triggered_at": event.triggered_at.isoformat(),
        "acknowledged_at": event.acknowledged_at.isoformat() if event.acknowledged_at else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "metadata": {
            key: value
            for key, value in metadata.items()
            if key in allowed_metadata and isinstance(value, (str, int, float, type(None)))
        },
    }


@router.get("/resource-usage")
def get_resource_usage(
    service: Any = Depends(get_resource_monitoring_service),
) -> Dict[str, Any]:
    """返回 AlphaFoundry 受控进程的当前资源快照，并异步式落库异常。"""
    snapshot = service.collect_snapshot()
    try:
        _resource_event_service_call(lambda event_service: event_service.evaluate(snapshot))
    except Exception as exc:
        logger.warning(
            "resource monitor event persistence unavailable", error_type=type(exc).__name__
        )
    return _sanitize_resource_snapshot(snapshot)


@router.get("/resource-usage/history")
def get_resource_usage_history(
    window_seconds: int = Query(300, ge=2, le=300),
    service: Any = Depends(get_resource_monitoring_service),
) -> Dict[str, Any]:
    """返回指定时间窗口内已采集的资源快照。"""
    return {
        "window_seconds": window_seconds,
        "points": [
            _sanitize_resource_snapshot(snapshot) for snapshot in service.history(window_seconds)
        ],
    }


@router.get("/resource-events")
def list_resource_events(
    days: int = Query(90, ge=1, le=3650),
    status: str = Query("all", pattern="^(all|open|acknowledged|resolved)$"),
    severity: str | None = Query(None, pattern="^(info|warning|critical)$"),
    task_kind: str | None = Query(None, max_length=80),
    source_key: str | None = Query(None, max_length=80),
) -> Dict[str, Any]:
    """查询资源异常历史；未恢复事件不受指定时间窗口隐藏。"""
    try:
        events = _resource_event_service_call(
            lambda event_service: event_service.list_events(
                days=days,
                status=status,
                severity=severity,
                task_kind=task_kind,
                source_key=source_key,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid resource event filter") from exc
    except Exception as exc:
        logger.error("resource monitor event query failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Resource event history unavailable") from exc
    return {"days": days, "items": [_serialize_resource_event(event) for event in events]}


@router.post("/resource-events/{alert_id}/acknowledge")
def acknowledge_resource_event(alert_id: str) -> Dict[str, Any]:
    """确认一个未恢复资源异常。"""
    try:
        event = _resource_event_service_call(
            lambda event_service: event_service.acknowledge(alert_id)
        )
    except Exception as exc:
        logger.error("resource monitor event acknowledgement failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Resource event acknowledgement unavailable"
        ) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Resource event not found or already resolved")
    return _serialize_resource_event(event)


@router.post("/resource-events/{alert_id}/resolve")
def resolve_resource_event(alert_id: str, request: ResourceEventResolveRequest) -> Dict[str, Any]:
    """人工解决资源异常并保存简短说明。"""
    try:
        event = _resource_event_service_call(
            lambda event_service: event_service.resolve(alert_id, notes=request.notes)
        )
    except Exception as exc:
        logger.error("resource monitor event resolution failed", error_type=type(exc).__name__)
        raise HTTPException(
            status_code=503, detail="Resource event resolution unavailable"
        ) from exc
    if event is None:
        raise HTTPException(status_code=404, detail="Resource event not found")
    return _serialize_resource_event(event)


def _get_git_branch() -> str:
    """获取当前 git 分支名"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_DIR),
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def _get_db_type() -> str:
    """从 DATABASE_URL 解析数据库类型"""
    try:
        from core.settings.config import settings

        url = settings.DATABASE_URL
        scheme = url.split("://")[0] if "://" in url else url
        return {"postgresql": "PostgreSQL", "sqlite": "SQLite", "mysql": "MySQL"}.get(
            scheme.lower(), scheme.capitalize()
        )
    except Exception:
        return "PostgreSQL"


def _get_llm_provider() -> str:
    """获取当前默认 LLM provider 名称"""
    try:
        from core.settings.config import settings

        # 优先使用 TASK_DEFAULT_PROVIDER 对应的 provider
        default_route = settings.TASK_ROUTES.get("default")
        if default_route:
            return default_route.provider
        # fallback: 第一个 provider profile
        profiles = settings.PROVIDER_PROFILES
        if profiles:
            return list(profiles.keys())[0]
    except Exception:
        pass
    return "unknown"


@router.get("/status-bar")
async def get_status_bar():
    """返回底部状态栏所需的动态数据"""
    result: Dict[str, Any] = {
        "git_branch": _get_git_branch(),
        "db_type": _get_db_type(),
        "llm_provider": _get_llm_provider(),
        "error_count": 0,
        "warning_count": 0,
        "doc_count": 0,
    }

    # 文档总数
    try:
        from sqlalchemy import func

        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.dashboard_data import DocumentV1DB

        db = SessionLocal()
        try:
            doc_count = db.query(func.count(DocumentV1DB.doc_id)).scalar()
            result["doc_count"] = doc_count or 0
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to get doc count for status bar: {e}")

    # 告警计数
    try:
        from data_layer.repositories.base import get_db
        from data_layer.repositories.monitoring_repository import MonitoringRepositoryImpl
        from services.monitoring_service import MonitoringService

        db_gen = get_db()
        session = next(db_gen)
        try:
            repo = MonitoringRepositoryImpl(session)
            service = MonitoringService(monitoring_repository=repo)
            dashboard = service.get_system_health_dashboard()
            result["error_count"] = dashboard.total_open_critical
            result["warning_count"] = max(
                0, dashboard.total_open_alerts - dashboard.total_open_critical
            )
        finally:
            try:
                next(db_gen)
            except StopIteration:
                pass
    except Exception as e:
        logger.warning(f"Failed to get alert counts for status bar: {e}")

    return result


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


def _read_heartbeat_files() -> Dict[str, Dict[str, Any]]:
    """扫描 logs/ 目录下的 .heartbeat.json 文件，返回 {worker_name: {timestamp, activity}}"""
    heartbeats: Dict[str, Dict[str, Any]] = {}
    log_dir = PROJECT_DIR / "logs"
    if not log_dir.exists():
        return heartbeats

    for hb_path in log_dir.glob("*.heartbeat.json"):
        worker_name = Path(hb_path.stem).stem  # strip both .json and .heartbeat
        try:
            data = json.loads(hb_path.read_text())
            heartbeats[worker_name] = {
                "timestamp": data.get("timestamp"),
                "activity": data.get("activity"),
            }
        except (json.JSONDecodeError, OSError):
            pass

    return heartbeats


@router.get("/workers/status")
async def get_workers_status():
    """聚合返回所有后台 worker 的实时状态和队列统计"""
    result: Dict[str, Any] = {
        "workers": [],
        "scheduler": {"name": "crawl_scheduler", "alive": False, "pid": None},
        "queue_stats": {"pending": 0, "processing": 0, "completed": 0, "failed": 0},
        "processing_stats": {
            "today": 0,
            "last_7_days": 0,
            "last_30_days": 0,
            "total": 0,
            "yesterday_same_time": 0,
            "daily_avg_7d": 0.0,
        },
    }

    # ── Knowledge Workers (PID-based) ──────────────────────────
    try:
        from workers.knowledge_worker import get_all_worker_statuses

        kw_statuses: List[Dict[str, Any]] = get_all_worker_statuses()
        for ws in kw_statuses:
            worker_info: Dict[str, Any] = {
                "name": (
                    f"knowledge_worker_{ws.get('worker_id')}"
                    if ws.get("worker_id") is not None
                    else "knowledge_worker"
                ),
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

    # ── Heartbeats (file-based primary, in-process event_bus fallback) ──
    file_heartbeats = _read_heartbeat_files()
    inproc_heartbeats = event_bus.get_worker_heartbeats()
    # file-based takes priority since workers run in separate processes
    merged = {**inproc_heartbeats, **file_heartbeats}

    for worker_info in result["workers"]:
        name = worker_info["name"]
        if name in merged:
            hb = merged[name]
            worker_info["last_heartbeat"] = hb.get("timestamp") if isinstance(hb, dict) else hb
            worker_info["activity"] = hb.get("activity") if isinstance(hb, dict) else None
        else:
            worker_info["last_heartbeat"] = None
            worker_info["activity"] = None

    sched_name = result["scheduler"]["name"]
    sched_hb = merged.get(sched_name) or merged.get("scheduler")
    if sched_hb:
        result["scheduler"]["last_heartbeat"] = (
            sched_hb.get("timestamp") if isinstance(sched_hb, dict) else sched_hb
        )
        result["scheduler"]["activity"] = (
            sched_hb.get("activity") if isinstance(sched_hb, dict) else None
        )
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
            result["processing_stats"] = repo.get_processing_stats()
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to get queue stats: {e}")

    return result
