"""受控资源监控任务上下文与跨进程安全快照。"""

from __future__ import annotations

import json
import os
import threading
import uuid
from contextlib import AbstractContextManager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from core.observability import get_logger

logger = get_logger(__name__)

ALLOWED_TASK_KINDS = frozenset(
    {"crawl", "pdf_conversion", "knowledge_processing", "wind", "report_render"}
)
_MAX_RECENT_FAILURES = 20
_MAX_LABEL_LENGTH = 160
_MAX_SOURCE_KEY_LENGTH = 80


def _utc_now() -> str:
    """返回一致的 UTC ISO 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def _runtime_directory() -> Path:
    """解析仅供 AlphaFoundry 使用的任务快照目录。"""
    explicit = os.environ.get("ALPHAFOUNDRY_RUNTIME_DIR")
    if explicit:
        return Path(explicit) / "resource-monitor-tasks"

    desktop_data_dir = os.environ.get("ALPHAFOUNDRY_DESKTOP_DATA_DIR")
    if desktop_data_dir:
        return Path(desktop_data_dir) / "runtime" / "resource-monitor-tasks"

    project_root = Path(os.environ.get("ALPHAFOUNDRY_PROJECT_ROOT", Path.cwd()))
    return project_root / "logs" / "resource-monitor-tasks"


class _ResourceTaskScope(AbstractContextManager[None]):
    """维护单个任务生命周期的同步上下文管理器。"""

    def __init__(
        self,
        registry: "ResourceTaskRegistry",
        *,
        task_kind: str,
        label: str,
        source_key: Optional[str],
    ) -> None:
        self._registry = registry
        self._task = {
            "task_id": f"resource-task-{uuid.uuid4().hex}",
            "task_kind": task_kind,
            "label": label,
            "source_key": source_key,
            "pid": registry.pid,
            "thread_id": threading.get_ident(),
            "started_at": _utc_now(),
            "state": "running",
        }

    def __enter__(self) -> None:
        self._registry._start(self._task)
        return None

    def __exit__(self, exc_type: Any, exc_value: Any, traceback: Any) -> bool:
        self._registry._finish(self._task, exc_type=exc_type)
        return False


class ResourceTaskRegistry:
    """按 PID 维护运行任务，供本进程与资源采样器安全交换归因信息。"""

    def __init__(self, runtime_dir: Optional[Path] = None, pid: Optional[int] = None) -> None:
        self._runtime_dir = Path(runtime_dir) if runtime_dir is not None else _runtime_directory()
        self._pid = int(pid if pid is not None else os.getpid())
        self._lock = threading.RLock()
        self._active: Dict[str, Dict[str, Any]] = {}
        self._recent_failures: list[Dict[str, Any]] = []

    @property
    def pid(self) -> int:
        """返回登记器所属进程 PID。"""
        return self._pid

    @property
    def snapshot_path(self) -> Path:
        """返回本进程唯一且受控的快照路径。"""
        return self._runtime_dir / f"{self._pid}.json"

    def resource_task(
        self,
        *,
        task_kind: str,
        label: str,
        source_key: Optional[str] = None,
    ) -> AbstractContextManager[None]:
        """返回一个登记任务开始、结束和失败的上下文管理器。"""
        normalized_source_key = self._validate_task(
            task_kind=task_kind,
            label=label,
            source_key=source_key,
        )
        return _ResourceTaskScope(
            self,
            task_kind=task_kind,
            label=label.strip(),
            source_key=normalized_source_key,
        )

    def read_snapshot(self, pid: Optional[int] = None) -> Dict[str, Any]:
        """读取指定受控 PID 的快照；损坏文件返回空载荷。"""
        target_pid = self._pid if pid is None else int(pid)
        return self.read_snapshot_file(self._runtime_dir / f"{target_pid}.json")

    @staticmethod
    def read_snapshot_file(snapshot_path: Path) -> Dict[str, Any]:
        """读取并最小化验证一个任务快照，不向调用方传播文件错误。"""
        empty = {"active_tasks": [], "recent_failures": []}
        try:
            data = json.loads(snapshot_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return empty
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.warning(
                "resource task snapshot unavailable",
                snapshot_path=str(snapshot_path),
                error_type=type(exc).__name__,
            )
            return empty

        if not isinstance(data, dict):
            logger.warning(
                "resource task snapshot has invalid payload", snapshot_path=str(snapshot_path)
            )
            return empty

        active_tasks = data.get("active_tasks")
        recent_failures = data.get("recent_failures")
        if not isinstance(active_tasks, list) or not isinstance(recent_failures, list):
            logger.warning(
                "resource task snapshot has invalid collections", snapshot_path=str(snapshot_path)
            )
            return empty

        return {
            "pid": data.get("pid"),
            "updated_at": data.get("updated_at"),
            "active_tasks": [task for task in active_tasks if isinstance(task, dict)],
            "recent_failures": [
                failure for failure in recent_failures if isinstance(failure, dict)
            ],
        }

    def _validate_task(
        self, *, task_kind: str, label: str, source_key: Optional[str]
    ) -> Optional[str]:
        if task_kind not in ALLOWED_TASK_KINDS:
            raise ValueError(f"task_kind must be one of {sorted(ALLOWED_TASK_KINDS)}")
        if (
            not isinstance(label, str)
            or not label.strip()
            or len(label.strip()) > _MAX_LABEL_LENGTH
        ):
            raise ValueError("label must be a non-empty safe string up to 160 characters")
        if source_key is None:
            return None
        if not isinstance(source_key, str) or not source_key.strip():
            raise ValueError("source_key must be a non-empty string when provided")
        normalized = source_key.strip()
        if len(normalized) > _MAX_SOURCE_KEY_LENGTH or any(char.isspace() for char in normalized):
            raise ValueError("source_key must be a compact safe string up to 80 characters")
        return normalized

    def _start(self, task: Dict[str, Any]) -> None:
        with self._lock:
            self._active[task["task_id"]] = dict(task)
            self._write_snapshot_locked()
        logger.info(
            "resource task started",
            task_id=task["task_id"],
            task_kind=task["task_kind"],
            source_key=task["source_key"],
            pid=self._pid,
        )

    def _finish(self, task: Dict[str, Any], *, exc_type: Any) -> None:
        with self._lock:
            self._active.pop(task["task_id"], None)
            if exc_type is not None:
                self._recent_failures.insert(
                    0,
                    {
                        **task,
                        "state": "failed",
                        "failed_at": _utc_now(),
                        "error_type": getattr(exc_type, "__name__", "Exception"),
                        "error_summary": "任务执行失败；详情请查看 AlphaFoundry 日志。",
                    },
                )
                del self._recent_failures[_MAX_RECENT_FAILURES:]
            self._write_snapshot_locked()

        if exc_type is not None:
            logger.error(
                "resource task failed",
                task_id=task["task_id"],
                task_kind=task["task_kind"],
                source_key=task["source_key"],
                pid=self._pid,
                error_type=getattr(exc_type, "__name__", "Exception"),
            )
        else:
            logger.info(
                "resource task completed",
                task_id=task["task_id"],
                task_kind=task["task_kind"],
                source_key=task["source_key"],
                pid=self._pid,
            )

    def _write_snapshot_locked(self) -> None:
        """使用同目录临时文件原子替换，避免采样器读到半写入 JSON。"""
        self._runtime_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": self._pid,
            "updated_at": _utc_now(),
            "active_tasks": list(self._active.values()),
            "recent_failures": list(self._recent_failures),
        }
        temporary_path = self.snapshot_path.with_suffix(".tmp")
        try:
            temporary_path.write_text(
                json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                encoding="utf-8",
            )
            os.replace(temporary_path, self.snapshot_path)
        except OSError as exc:
            logger.warning(
                "resource task snapshot write failed",
                snapshot_path=str(self.snapshot_path),
                error_type=type(exc).__name__,
            )
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


_registry_lock = threading.Lock()


def get_resource_task_registry() -> ResourceTaskRegistry:
    """延迟创建当前进程的共享任务登记器。"""
    with _registry_lock:
        registry = getattr(get_resource_task_registry, "_instance", None)
        if registry is None:
            registry = ResourceTaskRegistry()
            get_resource_task_registry._instance = registry
    return registry


def resource_task(
    *,
    task_kind: str,
    label: str,
    source_key: Optional[str] = None,
) -> AbstractContextManager[None]:
    """使用当前进程登记器登记一段同步任务范围。"""
    return get_resource_task_registry().resource_task(
        task_kind=task_kind,
        label=label,
        source_key=source_key,
    )
