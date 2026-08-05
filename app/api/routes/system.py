"""System health endpoint — scheduler / queue / worker 状态"""

import json
import os
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Query

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
    return public_snapshot


@router.get("/resource-usage")
def get_resource_usage(
    service: Any = Depends(get_resource_monitoring_service),
) -> Dict[str, Any]:
    """返回 AlphaFoundry 根进程及其后代的当前资源快照。"""
    return _sanitize_resource_snapshot(service.collect_snapshot())


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
