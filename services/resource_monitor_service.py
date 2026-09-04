"""采集 Research Workbench 根进程及其后代的受限资源快照。"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Deque, Dict, Iterable, Optional, Tuple

import psutil

from core.observability import get_logger

logger = get_logger(__name__)

_ROOT_UNAVAILABLE_EXCEPTIONS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error, OSError)
_OPTIONAL_FIELD_EXCEPTIONS = (*_ROOT_UNAVAILABLE_EXCEPTIONS, NotImplementedError, AttributeError)
_HISTORY_SIZE = 150
_NON_DEGRADING_PROCESS_FIELDS = frozenset({"io_counters", "network_connection_count"})


@dataclass(frozen=True)
class ManagedProcess:
    """由 Research Workbench 显式登记、可在 API 树之外运行的进程。"""

    pid: int
    role: str
    attribution_kind: str


def _default_managed_processes() -> list[ManagedProcess]:
    """仅从项目自身 PID 状态函数获取独立 Worker，不扫描系统进程。"""
    managed: list[ManagedProcess] = []
    try:
        from workers.knowledge_worker import get_all_worker_statuses

        for status in get_all_worker_statuses():
            pid = status.get("pid")
            if status.get("alive") and isinstance(pid, int) and pid > 0:
                worker_id = status.get("worker_id")
                role = (
                    f"Knowledge Worker {worker_id}"
                    if isinstance(worker_id, int)
                    else "Knowledge Worker"
                )
                managed.append(ManagedProcess(pid=pid, role=role, attribution_kind="worker"))
    except Exception as exc:
        logger.warning(
            "resource monitor could not read knowledge worker pids", error_type=type(exc).__name__
        )

    try:
        from services.crawl_scheduler import get_scheduler_process_status

        status = get_scheduler_process_status()
        pid = status.get("pid")
        if status.get("alive") and isinstance(pid, int) and pid > 0:
            managed.append(
                ManagedProcess(
                    pid=pid,
                    role="Crawl Scheduler",
                    attribution_kind="scheduler",
                )
            )
    except Exception as exc:
        logger.warning(
            "resource monitor could not read scheduler pid", error_type=type(exc).__name__
        )
    return managed


class ResourceMonitoringService:
    """仅监控 API 进程树及 Research Workbench 显式登记 Worker 的本机资源。"""

    def __init__(
        self,
        root_pid: Optional[int] = None,
        managed_process_provider: Optional[Callable[[], list[ManagedProcess]]] = None,
        task_snapshot_reader: Optional[Callable[[int], Dict[str, Any]]] = None,
    ) -> None:
        """初始化具有固定 150 点历史容量的服务。"""
        self._root_pid = root_pid if root_pid is not None else os.getpid()
        self._lock = threading.RLock()
        self._history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_SIZE)
        self._io_baselines: Dict[Tuple[int, float], Tuple[float, int, int]] = {}
        self._process_cache: Dict[Tuple[int, float], psutil.Process] = {}
        self._cpu_warmed_processes: set[Tuple[int, float]] = set()
        self._host_cpu_warmed_up = False
        self._has_warmed_up = False
        self._managed_process_provider = managed_process_provider or _default_managed_processes
        self._task_snapshot_reader = task_snapshot_reader or self._read_task_snapshot

    @property
    def root_pid(self) -> int:
        """返回受限采集树的唯一根进程 PID。"""
        return self._root_pid

    def collect_snapshot(self) -> Dict[str, Any]:
        """采集一次资源快照，不访问受控 PID 范围之外的任何进程。"""
        with self._lock:
            return self._collect_snapshot_locked()

    def _collect_snapshot_locked(self) -> Dict[str, Any]:
        """在锁保护下采集一次资源快照。"""
        sampled_at = datetime.now(timezone.utc).isoformat()
        sample_monotonic = time.monotonic()
        host, host_warnings = self._collect_host_snapshot()

        try:
            root = psutil.Process(self._root_pid)
            discovered_processes = [root, *root.children(recursive=True)]
        except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
            logger.error(
                "resource monitor root process unavailable",
                root_pid=self._root_pid,
                error_type=type(exc).__name__,
            )
            self._cleanup_process_state(set())
            snapshot = self._unavailable_snapshot(sampled_at, host, host_warnings)
            self._history.append(snapshot)
            return snapshot

        roles_by_pid: Dict[int, ManagedProcess] = {
            root.pid: ManagedProcess(pid=root.pid, role="API", attribution_kind="api")
        }
        for process in discovered_processes[1:]:
            roles_by_pid.setdefault(
                process.pid,
                ManagedProcess(
                    pid=process.pid,
                    role="Research Workbench child process",
                    attribution_kind="child_process",
                ),
            )

        warnings: list[Dict[str, Any]] = list(host_warnings)
        for managed in self._managed_processes():
            roles_by_pid[managed.pid] = managed
            if managed.pid in {process.pid for process in discovered_processes}:
                continue
            try:
                discovered_processes.append(psutil.Process(managed.pid))
            except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
                logger.warning(
                    "resource monitor managed process unavailable",
                    pid=managed.pid,
                    role=managed.role,
                    error_type=type(exc).__name__,
                )
                warnings.append({"code": "managed_process_unavailable", "pid": managed.pid})

        processes, active_keys = self._current_processes(discovered_processes)
        self._cleanup_process_state(active_keys)
        warming_up = not self._has_warmed_up
        process_samples = []
        task_failures: list[Dict[str, Any]] = []
        for process in self._deduplicated_processes(processes):
            try:
                managed = roles_by_pid.get(
                    process.pid,
                    ManagedProcess(
                        pid=process.pid,
                        role="Research Workbench child process",
                        attribution_kind="child_process",
                    ),
                )
                process_sample = self._collect_process_sample(
                    process=process,
                    managed=managed,
                    sample_monotonic=sample_monotonic,
                    warming_up=warming_up,
                )
                process_samples.append(process_sample)
                warnings.extend(self._field_warnings(process_sample))
                task_failures.extend(process_sample.pop("recent_task_failures", []))
            except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
                if process.pid == self._root_pid:
                    logger.error(
                        "resource monitor root process unavailable",
                        root_pid=self._root_pid,
                        error_type=type(exc).__name__,
                    )
                    self._cleanup_process_state(set())
                    snapshot = self._unavailable_snapshot(sampled_at, host, warnings)
                    self._history.append(snapshot)
                    return snapshot

                logger.warning(
                    "resource monitor child process unavailable",
                    root_pid=self._root_pid,
                    child_pid=process.pid,
                    error_type=type(exc).__name__,
                )
                warnings.append({"code": "child_process_unavailable", "pid": process.pid})

        process_samples.sort(key=self._process_sort_key)
        status = (
            "degraded"
            if any(self._is_degrading_warning(warning) for warning in warnings)
            else ("warming_up" if warming_up else "ok")
        )
        snapshot = {
            "sampled_at": sampled_at,
            "root_pid": self._root_pid,
            "status": status,
            "warnings": warnings,
            "host": host,
            "summary": self._build_summary(process_samples, host),
            "processes": process_samples,
            "task_failures": task_failures,
        }
        self._history.append(snapshot)
        self._has_warmed_up = True
        return snapshot

    def history(self, window_seconds: float) -> list[Dict[str, Any]]:
        """返回历史中落在指定时间窗口内的快照点位。"""
        if window_seconds < 0:
            raise ValueError("window_seconds must not be negative")

        cutoff = datetime.now(timezone.utc).timestamp() - window_seconds
        with self._lock:
            snapshots = list(self._history)
        return [
            snapshot
            for snapshot in snapshots
            if datetime.fromisoformat(snapshot["sampled_at"]).timestamp() >= cutoff
        ]

    def _current_processes(
        self,
        discovered_processes: Iterable[psutil.Process],
    ) -> Tuple[list[psutil.Process], set[Tuple[int, float]]]:
        """将当前进程树映射到同一身份的缓存对象，维持 CPU 采样基线。"""
        processes = []
        active_keys = set()
        for process in self._deduplicated_processes(discovered_processes):
            process_key = self._process_key(process)
            if process_key is None:
                processes.append(process)
                continue

            active_keys.add(process_key)
            processes.append(self._process_cache.setdefault(process_key, process))
        return processes, active_keys

    @staticmethod
    def _process_key(process: psutil.Process) -> Optional[Tuple[int, float]]:
        try:
            return process.pid, process.create_time()
        except _OPTIONAL_FIELD_EXCEPTIONS:
            return None

    def _cleanup_process_state(self, active_keys: set[Tuple[int, float]]) -> None:
        """移除当前进程树中不再存在的 CPU 与 I/O 基线。"""
        self._process_cache = {
            process_key: process
            for process_key, process in self._process_cache.items()
            if process_key in active_keys
        }
        self._io_baselines = {
            process_key: baseline
            for process_key, baseline in self._io_baselines.items()
            if process_key in active_keys
        }
        self._cpu_warmed_processes.intersection_update(active_keys)

    def _collect_process_sample(
        self,
        *,
        process: psutil.Process,
        managed: ManagedProcess,
        sample_monotonic: float,
        warming_up: bool,
    ) -> Dict[str, Any]:
        """逐字段读取进程数据，将单字段异常降级为 ``None``。"""
        unavailable_reasons: list[str] = []
        create_time = self._read_core_field(
            process,
            "create_time",
            lambda: process.create_time(),
            unavailable_reasons,
        )
        process_key = (process.pid, create_time) if create_time is not None else None
        cpu_is_warmed = process_key in self._cpu_warmed_processes
        sample = {
            "pid": process.pid,
            "parent_pid": self._read_core_field(
                process,
                "parent_pid",
                lambda: process.ppid(),
                unavailable_reasons,
            ),
            "name": self._read_core_field(
                process,
                "name",
                lambda: process.name(),
                unavailable_reasons,
            ),
            "create_time": create_time,
            "status": self._read_core_field(
                process,
                "status",
                lambda: process.status(),
                unavailable_reasons,
            ),
            "role": managed.role,
            "attribution_kind": managed.attribution_kind,
        }

        command = self._read_optional_field(
            process,
            "command",
            lambda: process.cmdline(),
            unavailable_reasons,
        )
        io_counters = self._read_optional_field(
            process,
            "io_counters",
            lambda: process.io_counters(),
            unavailable_reasons,
        )
        read_bytes: Optional[int]
        write_bytes: Optional[int]

        if io_counters is None:
            read_bytes = None
            write_bytes = None
        else:
            io_bytes = self._read_optional_field(
                process,
                "io_counters",
                lambda: (io_counters.read_bytes, io_counters.write_bytes),
                unavailable_reasons,
            )
            if io_bytes is None:
                read_bytes = None
                write_bytes = None
            else:
                read_bytes, write_bytes = io_bytes

        if create_time is None:
            read_rate, write_rate = None, None
        else:
            read_rate, write_rate = self._io_rates(
                pid=process.pid,
                create_time=create_time,
                sample_monotonic=sample_monotonic,
                read_bytes=read_bytes,
                write_bytes=write_bytes,
            )
        if io_counters is not None and read_rate is None and write_rate is None:
            unavailable_reasons.extend(
                [
                    "disk_read_bytes_per_second:warming_up",
                    "disk_write_bytes_per_second:warming_up",
                ]
            )

        cpu_percent = self._read_optional_field(
            process,
            "cpu_percent",
            lambda: process.cpu_percent(interval=None),
            unavailable_reasons,
        )
        if process_key is not None and cpu_percent is not None:
            self._cpu_warmed_processes.add(process_key)
        if warming_up or not cpu_is_warmed:
            cpu_percent = None

        task_snapshot = self._task_snapshot_for_pid(process.pid)
        active_tasks = task_snapshot["active_tasks"]
        sample.update(
            {
                "command": self._command_summary(command) if command is not None else None,
                "cpu_percent": cpu_percent,
                "memory_bytes": self._read_optional_field(
                    process,
                    "memory_bytes",
                    lambda: process.memory_info().rss,
                    unavailable_reasons,
                ),
                "thread_count": self._read_optional_field(
                    process,
                    "thread_count",
                    lambda: process.num_threads(),
                    unavailable_reasons,
                ),
                "disk_read_bytes_per_second": read_rate,
                "disk_write_bytes_per_second": write_rate,
                "network_connection_count": self._read_optional_field(
                    process,
                    "network_connection_count",
                    lambda: self._network_connection_count(process),
                    unavailable_reasons,
                ),
                "unavailable_reason": "; ".join(unavailable_reasons) or None,
                "active_tasks": active_tasks,
                "confidence": (
                    "shared_process_estimate"
                    if managed.attribution_kind == "api" and active_tasks
                    else "exact_process"
                ),
                "recent_task_failures": task_snapshot["recent_failures"],
            }
        )
        return sample

    def _managed_processes(self) -> list[ManagedProcess]:
        """读取并净化受控进程提供方结果。"""
        try:
            candidates = self._managed_process_provider()
        except Exception as exc:
            logger.warning(
                "resource monitor managed process provider failed", error_type=type(exc).__name__
            )
            return []
        managed: list[ManagedProcess] = []
        for candidate in candidates:
            if isinstance(candidate, ManagedProcess) and candidate.pid > 0:
                managed.append(candidate)
        return managed

    @staticmethod
    def _read_task_snapshot(pid: int) -> Dict[str, Any]:
        """延迟读取任务登记快照，避免服务模块在启动时引入额外依赖。"""
        from services.resource_task_registry import get_resource_task_registry

        return get_resource_task_registry().read_snapshot(pid)

    def _task_snapshot_for_pid(self, pid: int) -> Dict[str, list[Dict[str, Any]]]:
        """读取并最小化验证某受控进程的任务归因快照。"""
        empty: Dict[str, list[Dict[str, Any]]] = {"active_tasks": [], "recent_failures": []}
        try:
            payload = self._task_snapshot_reader(pid)
        except Exception as exc:
            logger.warning(
                "resource monitor task snapshot read failed", pid=pid, error_type=type(exc).__name__
            )
            return empty
        if not isinstance(payload, dict):
            return empty
        return {
            "active_tasks": [
                item for item in payload.get("active_tasks", []) if isinstance(item, dict)
            ],
            "recent_failures": [
                item for item in payload.get("recent_failures", []) if isinstance(item, dict)
            ],
        }

    def _read_core_field(
        self,
        process: psutil.Process,
        field: str,
        reader: Any,
        unavailable_reasons: list[str],
    ) -> Any:
        try:
            return reader()
        except psutil.NoSuchProcess:
            raise
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            self._record_unavailable_field(process, field, exc, unavailable_reasons)
            return None

    def _read_optional_field(
        self,
        process: psutil.Process,
        field: str,
        reader: Any,
        unavailable_reasons: list[str],
    ) -> Any:
        try:
            return reader()
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            self._record_unavailable_field(process, field, exc, unavailable_reasons)
            return None

    def _record_unavailable_field(
        self,
        process: psutil.Process,
        field: str,
        exc: Exception,
        unavailable_reasons: list[str],
    ) -> None:
        logger.warning(
            "resource monitor process field unavailable",
            root_pid=self._root_pid,
            pid=process.pid,
            field=field,
            error_type=type(exc).__name__,
        )
        unavailable_reasons.append(f"{field}:{type(exc).__name__}")

    @staticmethod
    def _network_connection_count(process: psutil.Process) -> int:
        """兼容不同 psutil 版本的进程网络连接接口。"""
        net_connections = getattr(process, "net_connections", None)
        if callable(net_connections):
            return len(net_connections())

        connections = getattr(process, "connections", None)
        if callable(connections):
            return len(connections())

        raise AttributeError("process network connection counters are unavailable")

    def _collect_host_snapshot(self) -> Tuple[Dict[str, Any], list[Dict[str, Any]]]:
        """采集整机容量，不枚举或访问受控范围外的任何进程。"""
        host: Dict[str, Any] = {
            "cpu_percent": None,
            "cpu_idle_percent": None,
            "logical_cpu_count": None,
            "memory_total_bytes": None,
            "memory_used_bytes": None,
            "memory_available_bytes": None,
            "memory_available_percent": None,
        }
        warnings: list[Dict[str, Any]] = []

        try:
            cpu_percent = psutil.cpu_percent(interval=None)
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            self._record_unavailable_host_field(
                field="cpu_percent",
                error_type=type(exc).__name__,
                warnings=warnings,
            )
        else:
            if self._is_valid_percentage(cpu_percent):
                if self._host_cpu_warmed_up:
                    host["cpu_percent"] = float(cpu_percent)
                    host["cpu_idle_percent"] = 100.0 - float(cpu_percent)
                self._host_cpu_warmed_up = True
            else:
                self._record_unavailable_host_field(
                    field="cpu_percent",
                    error_type="invalid_value",
                    warnings=warnings,
                )

        try:
            logical_cpu_count = psutil.cpu_count(logical=True)
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            self._record_unavailable_host_field(
                field="logical_cpu_count",
                error_type=type(exc).__name__,
                warnings=warnings,
            )
        else:
            if (
                isinstance(logical_cpu_count, int)
                and not isinstance(logical_cpu_count, bool)
                and logical_cpu_count > 0
            ):
                host["logical_cpu_count"] = logical_cpu_count
            else:
                self._record_unavailable_host_field(
                    field="logical_cpu_count",
                    error_type="invalid_value",
                    warnings=warnings,
                )

        try:
            memory = psutil.virtual_memory()
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            for field in (
                "memory_total_bytes",
                "memory_used_bytes",
                "memory_available_bytes",
                "memory_available_percent",
            ):
                self._record_unavailable_host_field(
                    field=field,
                    error_type=type(exc).__name__,
                    warnings=warnings,
                )
        else:
            total = self._read_host_memory_value(
                memory,
                "total",
                "memory_total_bytes",
                warnings,
                minimum=1,
            )
            used = self._read_host_memory_value(
                memory,
                "used",
                "memory_used_bytes",
                warnings,
                minimum=0,
                maximum=total,
            )
            available = self._read_host_memory_value(
                memory,
                "available",
                "memory_available_bytes",
                warnings,
                minimum=0,
                maximum=total,
            )
            host["memory_total_bytes"] = total
            host["memory_used_bytes"] = used
            host["memory_available_bytes"] = available
            if total is not None and available is not None:
                host["memory_available_percent"] = available / total * 100.0
            else:
                self._record_unavailable_host_field(
                    field="memory_available_percent",
                    error_type="invalid_value",
                    warnings=warnings,
                )

        return host, warnings

    def _read_host_memory_value(
        self,
        memory: Any,
        attribute: str,
        field: str,
        warnings: list[Dict[str, Any]],
        *,
        minimum: int,
        maximum: Optional[int] = None,
    ) -> Optional[int]:
        """读取并校验主机内存字段，确保无效数据不会伪装为零。"""
        try:
            value = getattr(memory, attribute)
        except _OPTIONAL_FIELD_EXCEPTIONS as exc:
            self._record_unavailable_host_field(
                field=field,
                error_type=type(exc).__name__,
                warnings=warnings,
            )
            return None

        valid = isinstance(value, int) and not isinstance(value, bool) and value >= minimum
        if maximum is not None:
            valid = valid and value <= maximum
        if not valid:
            self._record_unavailable_host_field(
                field=field,
                error_type="invalid_value",
                warnings=warnings,
            )
            return None
        return value

    @staticmethod
    def _is_valid_percentage(value: Any) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0.0 <= value <= 100.0
        )

    def _record_unavailable_host_field(
        self,
        *,
        field: str,
        error_type: str,
        warnings: list[Dict[str, Any]],
    ) -> None:
        logger.warning(
            "resource monitor host field unavailable",
            root_pid=self._root_pid,
            field=field,
            error_type=error_type,
        )
        warnings.append(
            {
                "code": "host_field_unavailable",
                "field": field,
                "error_type": error_type,
            }
        )

    def _io_rates(
        self,
        *,
        pid: int,
        create_time: float,
        sample_monotonic: float,
        read_bytes: Optional[int],
        write_bytes: Optional[int],
    ) -> Tuple[Optional[float], Optional[float]]:
        if read_bytes is None or write_bytes is None:
            return None, None

        process_key = (pid, create_time)
        baseline = self._io_baselines.get(process_key)
        self._io_baselines[process_key] = (sample_monotonic, read_bytes, write_bytes)
        if baseline is None:
            return None, None

        previous_monotonic, previous_read, previous_write = baseline
        elapsed = sample_monotonic - previous_monotonic
        if elapsed <= 0:
            return None, None

        return (
            max(0.0, (read_bytes - previous_read) / elapsed),
            max(0.0, (write_bytes - previous_write) / elapsed),
        )

    @staticmethod
    def _command_summary(command: list[str]) -> Optional[str]:
        if not command:
            return None

        summary_parts = [command[0]]
        summary_parts.extend("[redacted]" for _ in command[1:3])
        return " ".join(summary_parts)[:160]

    @staticmethod
    def _deduplicated_processes(processes: Iterable[psutil.Process]) -> Iterable[psutil.Process]:
        seen_pids = set()
        for process in processes:
            if process.pid not in seen_pids:
                seen_pids.add(process.pid)
                yield process

    @staticmethod
    def _process_sort_key(sample: Dict[str, Any]) -> Tuple[bool, float, int]:
        cpu_percent = sample["cpu_percent"]
        return (cpu_percent is None, -(cpu_percent or 0.0), sample["pid"])

    @staticmethod
    def _field_warnings(sample: Dict[str, Any]) -> list[Dict[str, Any]]:
        reason = sample.get("unavailable_reason")
        if not reason:
            return []

        warnings = []
        for item in reason.split("; "):
            field, separator, error_type = item.partition(":")
            if not separator or error_type == "warming_up":
                continue
            warnings.append(
                {
                    "code": "process_field_unavailable",
                    "pid": sample["pid"],
                    "field": field,
                    "error_type": error_type,
                }
            )
        return warnings

    @staticmethod
    def _is_degrading_warning(warning: Dict[str, Any]) -> bool:
        """仅把影响监控正确性的缺失字段视为服务降级。"""
        return not (
            warning.get("code") == "process_field_unavailable"
            and warning.get("field") in _NON_DEGRADING_PROCESS_FIELDS
        )

    @staticmethod
    def _build_summary(
        process_samples: list[Dict[str, Any]], host: Dict[str, Any]
    ) -> Dict[str, Any]:
        def aggregate(field: str) -> Optional[float]:
            values = [sample[field] for sample in process_samples if sample[field] is not None]
            return sum(values) if values else None

        cpu_percent = aggregate("cpu_percent")
        memory_bytes = aggregate("memory_bytes")
        logical_cpu_count = host["logical_cpu_count"]
        memory_total_bytes = host["memory_total_bytes"]

        return {
            "cpu_percent": cpu_percent,
            "memory_bytes": memory_bytes,
            "cpu_host_percent": (
                cpu_percent / logical_cpu_count
                if cpu_percent is not None and logical_cpu_count is not None
                else None
            ),
            "memory_host_percent": (
                memory_bytes / memory_total_bytes * 100.0
                if memory_bytes is not None and memory_total_bytes is not None
                else None
            ),
            "process_count": len(process_samples),
            "disk_read_bytes_per_second": aggregate("disk_read_bytes_per_second"),
            "disk_write_bytes_per_second": aggregate("disk_write_bytes_per_second"),
            "network_connection_count": aggregate("network_connection_count"),
        }

    def _unavailable_snapshot(
        self,
        sampled_at: str,
        host: Dict[str, Any],
        host_warnings: list[Dict[str, Any]],
    ) -> Dict[str, Any]:
        return {
            "sampled_at": sampled_at,
            "root_pid": self._root_pid,
            "status": "unavailable",
            "warnings": [*host_warnings, {"code": "root_process_unavailable"}],
            "host": host,
            "summary": {
                "cpu_percent": None,
                "memory_bytes": None,
                "cpu_host_percent": None,
                "memory_host_percent": None,
                "process_count": 0,
                "disk_read_bytes_per_second": None,
                "disk_write_bytes_per_second": None,
                "network_connection_count": None,
            },
            "processes": [],
            "task_failures": [],
        }
