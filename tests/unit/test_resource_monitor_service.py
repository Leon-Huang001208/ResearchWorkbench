"""ResourceMonitoringService 的受限进程树采集单元测试。"""

from __future__ import annotations

import inspect
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from typing import Any

import psutil
import pytest

from services import resource_monitor_service
from services.resource_monitor_service import ManagedProcess


class FakeProcess:
    """提供确定性 psutil 进程接口的测试替身。"""

    def __init__(
        self,
        pid: int,
        parent_pid: int | None,
        *,
        name: str,
        command: list[str] | None = None,
        cpu_samples: list[float] | None = None,
        memory_bytes: int = 0,
        read_bytes: int = 0,
        write_bytes: int = 0,
        connections: int = 0,
        children: list["FakeProcess"] | None = None,
        failure: Exception | None = None,
        field_failures: dict[str, Exception] | None = None,
    ) -> None:
        self.pid = pid
        self._parent_pid = parent_pid
        self._name = name
        self._command = command or [name]
        self._cpu_samples = list(cpu_samples or [0.0])
        self._memory_bytes = memory_bytes
        self._read_bytes = read_bytes
        self._write_bytes = write_bytes
        self._connections = connections
        self._children = children or []
        self._failure = failure
        self._field_failures = field_failures or {}
        self.cpu_intervals: list[float | None] = []

    def _raise_if_failed(self, field: str) -> None:
        if self._failure is not None:
            raise self._failure
        if field in self._field_failures:
            raise self._field_failures[field]

    def ppid(self) -> int:
        self._raise_if_failed("parent_pid")
        return self._parent_pid or 0

    def name(self) -> str:
        self._raise_if_failed("name")
        return self._name

    def cmdline(self) -> list[str]:
        self._raise_if_failed("command")
        return list(self._command)

    def create_time(self) -> float:
        self._raise_if_failed("create_time")
        return float(self.pid)

    def status(self) -> str:
        self._raise_if_failed("status")
        return "running"

    def cpu_percent(self, interval: float | None = None) -> float:
        self._raise_if_failed("cpu_percent")
        self.cpu_intervals.append(interval)
        return self._cpu_samples.pop(0) if self._cpu_samples else 0.0

    def memory_info(self) -> SimpleNamespace:
        self._raise_if_failed("memory_bytes")
        return SimpleNamespace(rss=self._memory_bytes)

    def num_threads(self) -> int:
        self._raise_if_failed("thread_count")
        return 4

    def io_counters(self) -> SimpleNamespace:
        self._raise_if_failed("io_counters")
        return SimpleNamespace(read_bytes=self._read_bytes, write_bytes=self._write_bytes)

    def net_connections(self) -> list[object]:
        self._raise_if_failed("network_connection_count")
        return [object() for _ in range(self._connections)]

    def children(self, recursive: bool = False) -> list["FakeProcess"]:
        self._raise_if_failed("children")
        assert recursive is True
        return list(self._children)


@pytest.fixture
def scoped_process_tree(monkeypatch: pytest.MonkeyPatch) -> tuple[FakeProcess, FakeProcess]:
    child = FakeProcess(
        102,
        101,
        name="worker",
        command=["worker", "--job", "sync", "sensitive-argument"],
        cpu_samples=[2.5, 3.5],
        memory_bytes=200,
        read_bytes=200,
        write_bytes=400,
        connections=2,
    )
    root = FakeProcess(
        101,
        None,
        name="api",
        command=["python", "--token", "topsecret", "unreported"],
        cpu_samples=[10.0, 15.0],
        memory_bytes=100,
        read_bytes=100,
        write_bytes=300,
        connections=1,
        children=[child],
    )
    unrelated = FakeProcess(999, 1, name="unrelated")

    def only_root(pid: int) -> FakeProcess:
        assert pid == root.pid
        return root

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", only_root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    return root, unrelated


def test_snapshot_limits_collection_to_root_and_descendants_and_warms_up(
    scoped_process_tree: tuple[FakeProcess, FakeProcess],
) -> None:
    root, unrelated = scoped_process_tree
    service = resource_monitor_service.ResourceMonitoringService(root_pid=root.pid)

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "warming_up"
    assert {process["pid"] for process in snapshot["processes"]} == {101, 102}
    assert unrelated.pid not in {process["pid"] for process in snapshot["processes"]}
    assert root.cpu_intervals == [None]
    assert snapshot["processes"][0]["role"] == "API"
    assert snapshot["processes"][0]["command"] == "python [redacted] [redacted]"
    assert "topsecret" not in snapshot["processes"][0]["command"]
    assert snapshot["processes"][1]["role"] == "AlphaFoundry child process"
    assert {
        "pid",
        "parent_pid",
        "name",
        "command",
        "create_time",
        "status",
        "role",
        "cpu_percent",
        "memory_bytes",
        "thread_count",
        "disk_read_bytes_per_second",
        "disk_write_bytes_per_second",
        "network_connection_count",
        "unavailable_reason",
    } <= snapshot["processes"][0].keys()
    assert len(snapshot["processes"][1]["command"]) <= 160
    assert all(process["cpu_percent"] is None for process in snapshot["processes"])
    assert snapshot["summary"]["cpu_percent"] is None
    assert snapshot["summary"]["disk_read_bytes_per_second"] is None


def test_command_summary_keeps_only_executable_and_redacts_all_arguments() -> None:
    summary = resource_monitor_service.ResourceMonitoringService._command_summary(
        ["python", "API_KEY=topsecret", "--client-secret=supersecret"]
    )

    assert summary == "python [redacted] [redacted]"
    assert "topsecret" not in summary
    assert "supersecret" not in summary

    inline_code_summary = resource_monitor_service.ResourceMonitoringService._command_summary(
        ["python", "-c", "token=embedded-secret"]
    )
    assert inline_code_summary == "python [redacted] [redacted]"
    assert "embedded-secret" not in inline_code_summary


def test_second_snapshot_calculates_cpu_io_rates_and_aggregates_summary(
    scoped_process_tree: tuple[FakeProcess, FakeProcess],
) -> None:
    root, _ = scoped_process_tree
    service = resource_monitor_service.ResourceMonitoringService(root_pid=root.pid)
    service.collect_snapshot()
    root._read_bytes = 160
    root._write_bytes = 360
    root._children[0]._read_bytes = 260
    root._children[0]._write_bytes = 440

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "ok"
    assert {
        key: snapshot["summary"][key]
        for key in {
            "cpu_percent",
            "memory_bytes",
            "process_count",
            "disk_read_bytes_per_second",
            "disk_write_bytes_per_second",
            "network_connection_count",
        }
    } == {
        "cpu_percent": 18.5,
        "memory_bytes": 300,
        "process_count": 2,
        "disk_read_bytes_per_second": 60.0,
        "disk_write_bytes_per_second": 50.0,
        "network_connection_count": 3,
    }
    assert snapshot["summary"]["cpu_host_percent"] == (18.5 / snapshot["host"]["logical_cpu_count"])
    assert snapshot["summary"]["memory_host_percent"] == (
        300 / snapshot["host"]["memory_total_bytes"] * 100.0
    )
    root_sample = next(item for item in snapshot["processes"] if item["pid"] == root.pid)
    assert root_sample["disk_read_bytes_per_second"] == 30.0
    assert root.cpu_intervals == [None, None]


def test_snapshot_collects_host_capacity_without_global_process_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主机汇总只读取主机 API，绝不扩大受控 PID 的采集范围。"""
    gibibyte = 1024**3
    root = FakeProcess(
        101,
        None,
        name="api",
        cpu_samples=[0.0, 40.0],
        memory_bytes=4 * gibibyte,
    )
    host_cpu_samples = iter([0.0, 40.0])

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda _: root)
    monkeypatch.setattr(
        resource_monitor_service.psutil,
        "cpu_percent",
        lambda interval=None: next(host_cpu_samples),
    )
    monkeypatch.setattr(
        resource_monitor_service.psutil,
        "cpu_count",
        lambda logical=True: 8,
    )
    monkeypatch.setattr(
        resource_monitor_service.psutil,
        "virtual_memory",
        lambda: SimpleNamespace(
            total=16 * gibibyte,
            used=8 * gibibyte,
            available=8 * gibibyte,
        ),
    )
    monkeypatch.setattr(
        resource_monitor_service.psutil,
        "process_iter",
        lambda: pytest.fail("host capacity sampling must not enumerate system processes"),
    )
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    warming_up = service.collect_snapshot()
    snapshot = service.collect_snapshot()

    assert warming_up["host"]["cpu_percent"] is None
    assert warming_up["host"]["cpu_idle_percent"] is None
    assert snapshot["host"] == {
        "cpu_percent": 40.0,
        "cpu_idle_percent": 60.0,
        "logical_cpu_count": 8,
        "memory_total_bytes": 16 * gibibyte,
        "memory_used_bytes": 8 * gibibyte,
        "memory_available_bytes": 8 * gibibyte,
        "memory_available_percent": 50.0,
    }
    assert snapshot["summary"]["cpu_host_percent"] == 5.0
    assert snapshot["summary"]["memory_host_percent"] == 25.0


def test_host_field_failures_and_invalid_values_are_degraded_with_warnings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """主机字段异常或无效值必须保持未知，并保留稳定警告码。"""

    class CapturingLogger:
        def __init__(self) -> None:
            self.warnings: list[tuple[str, dict[str, object]]] = []

        def warning(self, message: str, **kwargs: object) -> None:
            self.warnings.append((message, kwargs))

    root = FakeProcess(101, None, name="api")
    logger = CapturingLogger()

    def unavailable_cpu(interval: float | None = None) -> float:
        raise psutil.Error("cpu unavailable")

    def unavailable_memory() -> SimpleNamespace:
        raise psutil.Error("memory unavailable")

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda _: root)
    monkeypatch.setattr(resource_monitor_service.psutil, "cpu_percent", unavailable_cpu)
    monkeypatch.setattr(resource_monitor_service.psutil, "cpu_count", lambda logical=True: None)
    monkeypatch.setattr(resource_monitor_service.psutil, "virtual_memory", unavailable_memory)
    monkeypatch.setattr(resource_monitor_service, "logger", logger)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    assert snapshot["host"] == {
        "cpu_percent": None,
        "cpu_idle_percent": None,
        "logical_cpu_count": None,
        "memory_total_bytes": None,
        "memory_used_bytes": None,
        "memory_available_bytes": None,
        "memory_available_percent": None,
    }
    assert snapshot["summary"]["cpu_host_percent"] is None
    assert snapshot["summary"]["memory_host_percent"] is None
    assert snapshot["status"] == "degraded"
    assert snapshot["warnings"] == [
        {
            "code": "host_field_unavailable",
            "field": "cpu_percent",
            "error_type": "Error",
        },
        {
            "code": "host_field_unavailable",
            "field": "logical_cpu_count",
            "error_type": "invalid_value",
        },
        {
            "code": "host_field_unavailable",
            "field": "memory_total_bytes",
            "error_type": "Error",
        },
        {
            "code": "host_field_unavailable",
            "field": "memory_used_bytes",
            "error_type": "Error",
        },
        {
            "code": "host_field_unavailable",
            "field": "memory_available_bytes",
            "error_type": "Error",
        },
        {
            "code": "host_field_unavailable",
            "field": "memory_available_percent",
            "error_type": "Error",
        },
    ]
    assert all(
        message == "resource monitor host field unavailable" and "error_type" in details
        for message, details in logger.warnings
    )


def test_known_worker_pid_is_collected_without_global_process_scan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """仅注入的受控 Worker PID 可被采样，绝不调用全局进程迭代。"""
    root = FakeProcess(101, None, name="api", cpu_samples=[1.0, 1.0])
    worker = FakeProcess(202, 1, name="knowledge", cpu_samples=[2.0, 2.0])

    def process_for_pid(pid: int) -> FakeProcess:
        assert pid in {101, 202}
        return root if pid == 101 else worker

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", process_for_pid)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(
        root_pid=101,
        managed_process_provider=lambda: [
            ManagedProcess(
                pid=202,
                role="Knowledge Worker",
                attribution_kind="worker",
            )
        ],
        task_snapshot_reader=lambda _: {"active_tasks": [], "recent_failures": []},
    )

    service.collect_snapshot()
    snapshot = service.collect_snapshot()

    assert {item["pid"] for item in snapshot["processes"]} == {101, 202}
    worker_sample = next(item for item in snapshot["processes"] if item["pid"] == 202)
    assert worker_sample["role"] == "Knowledge Worker"
    assert worker_sample["attribution_kind"] == "worker"
    assert worker_sample["confidence"] == "exact_process"


def test_api_active_tasks_are_labeled_as_shared_process_estimate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API 内任务只能显示共享估算，不能伪造任务级 CPU。"""
    root = FakeProcess(101, None, name="api", cpu_samples=[1.0, 1.0])
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda _: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(
        root_pid=101,
        managed_process_provider=lambda: [],
        task_snapshot_reader=lambda _: {
            "active_tasks": [
                {
                    "task_id": "resource-task-1",
                    "task_kind": "wind",
                    "label": "Wind 工作簿读取",
                    "source_key": None,
                }
            ],
            "recent_failures": [],
        },
    )

    service.collect_snapshot()
    sample = service.collect_snapshot()["processes"][0]

    assert sample["confidence"] == "shared_process_estimate"
    assert sample["active_tasks"][0]["task_kind"] == "wind"
    assert "cpu_percent" not in sample["active_tasks"][0]


def test_root_process_unavailable_returns_controlled_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable_root(pid: int) -> FakeProcess:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", unavailable_root)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "unavailable"
    assert snapshot["processes"] == []
    assert snapshot["warnings"] == [{"code": "root_process_unavailable"}]


def test_exited_child_is_skipped_without_failing_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    exited = FakeProcess(102, 101, name="worker", failure=psutil.NoSuchProcess(102))
    root = FakeProcess(101, None, name="api", children=[exited])
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "degraded"
    assert [process["pid"] for process in snapshot["processes"]] == [101]
    assert snapshot["warnings"] == [{"code": "child_process_unavailable", "pid": 102}]


def test_optional_field_errors_keep_root_and_child_with_none_values_and_structured_logs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class CapturingLogger:
        def __init__(self) -> None:
            self.warnings: list[tuple[str, dict[str, object]]] = []

        def warning(self, message: str, **kwargs: object) -> None:
            self.warnings.append((message, kwargs))

    child = FakeProcess(
        102,
        101,
        name="worker",
        field_failures={
            "name": psutil.AccessDenied(102),
            "io_counters": psutil.AccessDenied(102),
            "network_connection_count": NotImplementedError("unsupported"),
        },
    )
    root = FakeProcess(
        101,
        None,
        name="api",
        field_failures={"thread_count": psutil.AccessDenied(101)},
        children=[child],
    )
    logger = CapturingLogger()
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    monkeypatch.setattr(resource_monitor_service, "logger", logger)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "degraded"
    samples = {sample["pid"]: sample for sample in snapshot["processes"]}
    assert set(samples) == {101, 102}
    assert samples[101]["thread_count"] is None
    assert "thread_count:AccessDenied" in samples[101]["unavailable_reason"]
    assert samples[102]["network_connection_count"] is None
    assert samples[102]["name"] is None
    assert samples[102]["disk_read_bytes_per_second"] is None
    assert "io_counters:AccessDenied" in samples[102]["unavailable_reason"]
    assert "name:AccessDenied" in samples[102]["unavailable_reason"]
    assert "network_connection_count:NotImplementedError" in samples[102]["unavailable_reason"]
    assert snapshot["warnings"] == [
        {
            "code": "process_field_unavailable",
            "pid": 101,
            "field": "thread_count",
            "error_type": "AccessDenied",
        },
        {
            "code": "process_field_unavailable",
            "pid": 102,
            "field": "name",
            "error_type": "AccessDenied",
        },
        {
            "code": "process_field_unavailable",
            "pid": 102,
            "field": "io_counters",
            "error_type": "AccessDenied",
        },
        {
            "code": "process_field_unavailable",
            "pid": 102,
            "field": "network_connection_count",
            "error_type": "NotImplementedError",
        },
    ]
    assert logger.warnings == [
        (
            "resource monitor process field unavailable",
            {
                "root_pid": 101,
                "pid": 101,
                "field": "thread_count",
                "error_type": "AccessDenied",
            },
        ),
        (
            "resource monitor process field unavailable",
            {
                "root_pid": 101,
                "pid": 102,
                "field": "name",
                "error_type": "AccessDenied",
            },
        ),
        (
            "resource monitor process field unavailable",
            {
                "root_pid": 101,
                "pid": 102,
                "field": "io_counters",
                "error_type": "AccessDenied",
            },
        ),
        (
            "resource monitor process field unavailable",
            {
                "root_pid": 101,
                "pid": 102,
                "field": "network_connection_count",
                "error_type": "NotImplementedError",
            },
        ),
    ]


def test_root_identity_field_error_is_degraded_to_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api", field_failures={"name": psutil.AccessDenied(101)})
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "degraded"
    assert snapshot["processes"][0]["name"] is None
    assert "name:AccessDenied" in snapshot["processes"][0]["unavailable_reason"]


def test_processes_sort_by_cpu_then_pid_after_warm_up(monkeypatch: pytest.MonkeyPatch) -> None:
    child_high_pid = FakeProcess(103, 101, name="worker-high", cpu_samples=[1.0, 20.0])
    child_low_pid = FakeProcess(102, 101, name="worker-low", cpu_samples=[1.0, 20.0])
    root = FakeProcess(
        101,
        None,
        name="api",
        cpu_samples=[1.0, 5.0],
        children=[child_high_pid, child_low_pid],
    )
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    warming_up = service.collect_snapshot()
    ready = service.collect_snapshot()

    assert [sample["pid"] for sample in warming_up["processes"]] == [101, 102, 103]
    assert [sample["pid"] for sample in ready["processes"]] == [102, 103, 101]


def test_history_keeps_fixed_150_point_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api")
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monotonic_values = iter(float(index) for index in range(200))
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", monotonic_values.__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    for _ in range(151):
        service.collect_snapshot()

    assert (
        "history_size"
        not in inspect.signature(resource_monitor_service.ResourceMonitoringService).parameters
    )
    assert len(service.history(window_seconds=3600)) == 150


def test_cpu_is_continuous_when_process_factory_returns_new_objects(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_root = FakeProcess(101, None, name="api", cpu_samples=[1.0, 42.0])
    second_root = FakeProcess(101, None, name="api", cpu_samples=[99.0])
    roots = iter([first_root, second_root])
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: next(roots))
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    service.collect_snapshot()
    snapshot = service.collect_snapshot()

    assert snapshot["status"] == "ok"
    assert snapshot["processes"][0]["cpu_percent"] == 42.0
    assert first_root.cpu_intervals == [None, None]
    assert second_root.cpu_intervals == []


def test_new_child_process_is_cpu_warmed_independently_of_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api", cpu_samples=[1.0, 10.0])
    new_child = FakeProcess(102, 101, name="worker", cpu_samples=[0.0, 42.0])
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    service.collect_snapshot()
    root._children = [new_child]
    snapshot = service.collect_snapshot()

    samples = {sample["pid"]: sample for sample in snapshot["processes"]}
    assert snapshot["status"] == "ok"
    assert samples[101]["cpu_percent"] == 10.0
    assert samples[102]["cpu_percent"] is None
    assert snapshot["summary"]["cpu_percent"] == 10.0
    assert new_child.cpu_intervals == [None]


def test_missing_optional_process_methods_are_degraded_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class MissingOptionalMethodsProcess(FakeProcess):
        def __getattribute__(self, name: str) -> object:
            if name in {"io_counters", "net_connections", "num_threads"}:
                raise AttributeError(name)
            return super().__getattribute__(name)

    root = MissingOptionalMethodsProcess(101, None, name="api")
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    process = snapshot["processes"][0]
    assert snapshot["status"] == "degraded"
    assert process["thread_count"] is None
    assert process["disk_read_bytes_per_second"] is None
    assert process["network_connection_count"] is None
    assert "io_counters:AttributeError" in process["unavailable_reason"]
    assert "thread_count:AttributeError" in process["unavailable_reason"]
    assert "network_connection_count:AttributeError" in process["unavailable_reason"]


def test_incomplete_io_counters_are_degraded_without_raising(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class IncompleteIoCountersProcess(FakeProcess):
        def io_counters(self) -> SimpleNamespace:
            return SimpleNamespace(read_bytes=100)

    root = IncompleteIoCountersProcess(101, None, name="api")
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    snapshot = service.collect_snapshot()

    process = snapshot["processes"][0]
    assert snapshot["status"] == "degraded"
    assert process["disk_read_bytes_per_second"] is None
    assert process["disk_write_bytes_per_second"] is None
    assert "io_counters:AttributeError" in process["unavailable_reason"]


def test_process_cache_and_io_baselines_drop_exited_descendants(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    child = FakeProcess(102, 101, name="worker")
    root = FakeProcess(101, None, name="api", children=[child])
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    service.collect_snapshot()
    root._children = []
    service.collect_snapshot()

    assert {key[0] for key in service._process_cache} == {101}
    assert {key[0] for key in service._io_baselines} == {101}


def test_root_unavailability_clears_process_cache_and_io_baselines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api")
    process_calls = iter([root, psutil.NoSuchProcess(101)])

    def process_factory(pid: int) -> FakeProcess:
        result = next(process_calls)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(resource_monitor_service.psutil, "Process", process_factory)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", iter([10.0, 12.0]).__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    service.collect_snapshot()
    unavailable_snapshot = service.collect_snapshot()

    assert unavailable_snapshot["status"] == "unavailable"
    assert service._process_cache == {}
    assert service._io_baselines == {}


def test_collect_snapshot_and_history_are_safe_when_called_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api")
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", lambda: 10.0)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101)

    with ThreadPoolExecutor(max_workers=4) as executor:
        collect_futures = [executor.submit(service.collect_snapshot) for _ in range(20)]
        history_futures = [executor.submit(service.history, 3600) for _ in range(20)]
        results: list[Any] = [future.result() for future in collect_futures]
        results.extend(future.result() for future in history_futures)

    assert all(isinstance(result, (dict, list)) for result in results)
    assert len(service.history(window_seconds=3600)) <= 150
