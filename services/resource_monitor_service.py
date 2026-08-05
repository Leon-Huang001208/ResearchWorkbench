"""采集 AlphaFoundry 根进程及其后代的受限资源快照。"""

from __future__ import annotations

import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, Optional, Tuple

import psutil

from core.observability import get_logger

logger = get_logger(__name__)

_ROOT_UNAVAILABLE_EXCEPTIONS = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.Error, OSError)
_HISTORY_SIZE = 150


class ResourceMonitoringService:
    """仅监控指定根进程及其递归后代的本机资源使用情况。"""

    def __init__(self, root_pid: Optional[int] = None, history_size: Optional[int] = None) -> None:
        """初始化服务；保留 ``history_size`` 参数仅为调用方兼容性。"""
        self._root_pid = root_pid if root_pid is not None else os.getpid()
        self._history: Deque[Dict[str, Any]] = deque(maxlen=_HISTORY_SIZE)
        self._io_baselines: Dict[Tuple[int, float], Tuple[float, int, int]] = {}
        self._has_warmed_up = False

    @property
    def root_pid(self) -> int:
        """返回受限采集树的唯一根进程 PID。"""
        return self._root_pid

    def collect_snapshot(self) -> Dict[str, Any]:
        """采集一次资源快照，不访问根进程树之外的任何进程。"""
        sampled_at = datetime.now(timezone.utc).isoformat()
        sample_monotonic = time.monotonic()

        try:
            root = psutil.Process(self._root_pid)
            processes = [root, *root.children(recursive=True)]
        except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
            logger.error(
                "resource monitor root process unavailable",
                root_pid=self._root_pid,
                error_type=type(exc).__name__,
            )
            snapshot = self._unavailable_snapshot(sampled_at)
            self._history.append(snapshot)
            return snapshot

        warnings = []
        process_samples = []
        for process in self._deduplicated_processes(processes):
            try:
                process_samples.append(
                    self._collect_process_sample(
                        process=process,
                        is_root=process.pid == self._root_pid,
                        sample_monotonic=sample_monotonic,
                    )
                )
            except _ROOT_UNAVAILABLE_EXCEPTIONS as exc:
                if process.pid == self._root_pid:
                    logger.error(
                        "resource monitor root process unavailable",
                        root_pid=self._root_pid,
                        error_type=type(exc).__name__,
                    )
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

        status = "warming_up" if not self._has_warmed_up else "ok"
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
        return [
            snapshot
            for snapshot in self._history
            if datetime.fromisoformat(snapshot["sampled_at"]).timestamp() >= cutoff
        ]

    def _collect_process_sample(
        self,
        *,
        process: psutil.Process,
        is_root: bool,
        sample_monotonic: float,
    ) -> Dict[str, Any]:
        create_time = process.create_time()
        io_counters = process.io_counters()
        unavailable_reasons = []
        read_bytes: Optional[int]
        write_bytes: Optional[int]

        if io_counters is None:
            read_bytes = None
            write_bytes = None
            unavailable_reasons.append("io_counters_unavailable")
        else:
            read_bytes = io_counters.read_bytes
            write_bytes = io_counters.write_bytes

        read_rate, write_rate = self._io_rates(
            pid=process.pid,
            create_time=create_time,
            sample_monotonic=sample_monotonic,
            read_bytes=read_bytes,
            write_bytes=write_bytes,
        )

        if read_rate is None and write_rate is None and not unavailable_reasons:
            unavailable_reasons.append("io_rate_warming_up")

        command = self._command_summary(process.cmdline())
        return {
            "pid": process.pid,
            "parent_pid": process.ppid(),
            "name": process.name(),
            "command": command,
            "create_time": create_time,
            "status": process.status(),
            "role": "API" if is_root else "AlphaFoundry child process",
            "cpu_percent": process.cpu_percent(interval=None),
            "memory_bytes": process.memory_info().rss,
            "thread_count": process.num_threads(),
            "disk_read_bytes_per_second": read_rate,
            "disk_write_bytes_per_second": write_rate,
            "network_connection_count": len(process.net_connections()),
            "unavailable_reason": "; ".join(unavailable_reasons) or None,
        }

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
        return " ".join(command[:3])[:160]

    @staticmethod
    def _deduplicated_processes(processes: Iterable[psutil.Process]) -> Iterable[psutil.Process]:
        seen_pids = set()
        for process in processes:
            if process.pid not in seen_pids:
                seen_pids.add(process.pid)
                yield process

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
