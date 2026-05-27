"""Knowledge Worker API — 知识加工 Worker 进程管理

Knowledge Worker 跑在独立进程 (workers/knowledge_worker.py)，
API 通过 subprocess/PID 文件与其交互。支持多进程水平扩展。
"""
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Query

from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent.parent


def _pid_file_for(worker_id: int | None = None) -> Path:
    if worker_id is not None:
        return PROJECT_DIR / "logs" / f"knowledge_worker_{worker_id}.pid"
    return PROJECT_DIR / "logs" / "knowledge_worker.pid"


def _get_all_worker_statuses() -> List[Dict[str, Any]]:
    """检查所有 knowledge worker 进程状态"""
    pid_dir = PROJECT_DIR / "logs"
    if not pid_dir.exists():
        return []

    results: List[Dict[str, Any]] = []
    for pid_path in sorted(pid_dir.glob("knowledge_worker*.pid")):
        status: Dict[str, Any] = {
            "alive": False,
            "pid": None,
            "pid_file": str(pid_path),
            "worker_id": None,
        }
        try:
            pid = int(pid_path.read_text().strip())
            status["pid"] = pid
            os.kill(pid, 0)
            status["alive"] = True
        except (ValueError, OSError):
            pass

        stem = pid_path.stem
        if stem.startswith("knowledge_worker_"):
            try:
                status["worker_id"] = int(stem.split("_")[-1])
            except ValueError:
                pass

        results.append(status)
    return results


@router.get("/status")
async def get_knowledge_status() -> Dict[str, Any]:
    """获取所有 Knowledge Worker 状态"""
    all_statuses = _get_all_worker_statuses()
    alive_count = sum(1 for w in all_statuses if w["alive"])
    return {
        "available": True,
        "total_workers": len(all_statuses),
        "alive_workers": alive_count,
        "workers": all_statuses,
    }


@router.post("/start")
async def start_knowledge(
    workers: int = Query(default=1, ge=1, le=16, description="Worker 进程数量"),
) -> Dict[str, Any]:
    """启动 Knowledge Worker 进程（支持多进程）"""
    existing = _get_all_worker_statuses()
    alive_map = {w["worker_id"]: w for w in existing if w["alive"]}

    worker_module = "workers.knowledge_worker"
    started: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for worker_id in range(1, workers + 1):
        if worker_id in alive_map:
            skipped.append({"worker_id": worker_id, "pid": alive_map[worker_id]["pid"]})
            continue

        try:
            subprocess.Popen(
                [sys.executable, "-m", worker_module, "--worker-id", str(worker_id)],
                cwd=str(PROJECT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            started.append({"worker_id": worker_id})
        except Exception as e:
            logger.error("Failed to start knowledge worker", worker_id=worker_id, error=str(e))
            failed.append({"worker_id": worker_id, "error": str(e)})

    return {
        "success": len(failed) == 0,
        "started": started,
        "skipped": skipped,
        "failed": failed,
        "message": f"Started {len(started)}, skipped {len(skipped)} already running, failed {len(failed)}",
    }


@router.post("/stop")
async def stop_knowledge() -> Dict[str, Any]:
    """停止所有 Knowledge Worker 进程"""
    all_statuses = _get_all_worker_statuses()
    alive_workers = [w for w in all_statuses if w["alive"]]

    if not alive_workers:
        for pid_path in PROJECT_DIR.glob("logs/knowledge_worker*.pid"):
            pid_path.unlink(missing_ok=True)
        return {"success": True, "message": "No knowledge workers running", "stopped": []}

    stopped: List[Dict[str, Any]] = []
    failed: List[Dict[str, Any]] = []

    for w in alive_workers:
        try:
            os.kill(w["pid"], signal.SIGTERM)
            stopped.append({"worker_id": w["worker_id"], "pid": w["pid"]})
        except OSError as e:
            logger.error("Failed to stop knowledge worker", worker_id=w["worker_id"], error=str(e))
            failed.append({"worker_id": w["worker_id"], "pid": w["pid"], "error": str(e)})

    return {
        "success": len(failed) == 0,
        "stopped": stopped,
        "failed": failed,
        "message": f"Stopped {len(stopped)}, failed {len(failed)}",
    }
