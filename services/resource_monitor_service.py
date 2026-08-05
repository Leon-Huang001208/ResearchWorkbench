"""采集 AlphaFoundry 根进程及其后代的受限资源快照。"""

from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, Optional, Tuple

import psutil

from core.observability import get_logger

logger = get_logger(__name__)

_ROOT_UNAVAILABLE_EXCEPTIONS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error, OSError)
_OPTIONAL_FIELD_EXCEPTIONS = (*_ROOT_UNAVAILABLE_EXCEPTIONS, NotImplementedError, AttributeError)
_HISTORY_SIZE = 150


class ResourceMonitoringService:
    """仅监控指定根进程及其递归后代的本机资源使用情况。"""

    def __init__(self, root_pid: Optional[int] = None) -> None:
        """初始化具有固定 150 点历史容量的服务。"""
        self._root_pid = root_pid if root_pid is not None else os.getpid()
        self._lock = threading.RLock()
        self._history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_SIZE)
        self._io_baselines: Dict[Tuple[int, float], Tuple[float, int, int]] = {}
        self._process_cache: Dict[Tuple[int, float], psutil.Process] = {}
        self._has_warmed_up = False

    @property
    def root_pid(self) -> int:
        """返回受限采集树的唯一根进程 PID。"""
        return self._root_pid

    def collect_snapshot(self) -> Dict[str, Any]:
        """采集一次资源快照，不访问根进程树之外的任何进程。"""
        with self._lock:
            return self._collect_snapshot_locked()

    def _collect_snapshot_locked(self) -> Dict[str, Any]:
        """在锁保护下采集一次资源快照。"""
        sampled_at = datetime.now(timezone.utc).isoformat()
        sample_monotonic = time.monotonic()

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
            snapshot = self._unavailable_snapshot(sampled_at)
            self._history.append(snapshot)
            return snapshot

        processes, active_keys = self._current_processes(discovered_processes)
        self._cleanup_process_state(active_keys)
        warming_up = not self._has_warmed_up
        warnings = []
        process_samples = []
        for process in self._deduplicated_processes(processes):
            try:
                process_sample = self._collect_process_sample(
                    process=process,
                    is_root=process.pid == self._root_pid,
                    sample_monotonic=sample_monotonic,
                    warming_up=warming_up,
                )
                process_samples.append(process_sample)
                warnings.extend(self._field_warnings(process_sample))
            except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
                if process.pid == self._root_pid:
                    logger.error(
                        "resource monitor root process unavailable",
                        root_pid=self._root_pid,
                        error_type=type(exc).__name__,
                    )
                    self._cleanup_process_state(set())
                    snapshot = self._unavailable_snapshot(sampled_at)
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
        status = "degraded" if warnings else ("warming_up" if warming_up else "ok")
        snapshot = {
            "sampled_at": sampled_at,
            "root_pid": self._root_pid,
            "status": status,
            "warnings": warnings,
            "summary": self._build_summary(process_samples),
            "processes": process_samples,
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

    def _collect_process_sample(
        self,
        *,
        process: psutil.Process,
        is_root: bool,
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
            "role": "API" if is_root else "AlphaFoundry child process",
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
            read_bytes = io_counters.read_bytes
            write_bytes = io_counters.write_bytes

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
        if warming_up:
            cpu_percent = None

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
                    lambda: len(process.net_connections()),
                    unavailable_reasons,
                ),
                "unavailable_reason": "; ".join(unavailable_reasons) or None,
            }
        )
        return sample

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
    def _build_summary(process_samples: list[Dict[str, Any]]) -> Dict[str, Any]:
        def aggregate(field: str) -> Optional[float]:
            values = [sample[field] for sample in process_samples if sample[field] is not None]
            return sum(values) if values else None

        return {
            "cpu_percent": aggregate("cpu_percent"),
            "memory_bytes": aggregate("memory_bytes"),
            "process_count": len(process_samples),
            "disk_read_bytes_per_second": aggregate("disk_read_bytes_per_second"),
            "disk_write_bytes_per_second": aggregate("disk_write_bytes_per_second"),
            "network_connection_count": aggregate("network_connection_count"),
        }

    def _unavailable_snapshot(self, sampled_at: str) -> Dict[str, Any]:
        return {
            "sampled_at": sampled_at,
            "root_pid": self._root_pid,
            "status": "unavailable",
            "warnings": [{"code": "root_process_unavailable"}],
            "summary": {
                "cpu_percent": None,
                "memory_bytes": None,
                "process_count": 0,
                "disk_read_bytes_per_second": None,
                "disk_write_bytes_per_second": None,
                "network_connection_count": None,
            },
            "processes": [],
        }
