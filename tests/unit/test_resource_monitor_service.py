"""ResourceMonitoringService 的受限进程树采集单元测试。"""

from __future__ import annotations

from types import SimpleNamespace

import psutil
import pytest

from services import resource_monitor_service


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
        self.cpu_intervals: list[float | None] = []

    def _raise_if_failed(self) -> None:
        if self._failure is not None:
            raise self._failure

    def ppid(self) -> int:
        self._raise_if_failed()
        return self._parent_pid or 0

    def name(self) -> str:
        self._raise_if_failed()
        return self._name

    def cmdline(self) -> list[str]:
        self._raise_if_failed()
        return list(self._command)

    def create_time(self) -> float:
        self._raise_if_failed()
        return float(self.pid)

    def status(self) -> str:
        self._raise_if_failed()
        return "running"

    def cpu_percent(self, interval: float | None = None) -> float:
        self._raise_if_failed()
        self.cpu_intervals.append(interval)
        return self._cpu_samples.pop(0) if self._cpu_samples else 0.0

    def memory_info(self) -> SimpleNamespace:
        self._raise_if_failed()
        return SimpleNamespace(rss=self._memory_bytes)

    def num_threads(self) -> int:
        self._raise_if_failed()
        return 4

    def io_counters(self) -> SimpleNamespace:
        self._raise_if_failed()
        return SimpleNamespace(read_bytes=self._read_bytes, write_bytes=self._write_bytes)

    def net_connections(self) -> list[object]:
        self._raise_if_failed()
        return [object() for _ in range(self._connections)]

    def children(self, recursive: bool = False) -> list["FakeProcess"]:
        self._raise_if_failed()
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
        command=["python", "-m", "server", "unreported"],
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
    assert snapshot["processes"][0]["command"] == "python -m server"
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
    assert snapshot["summary"]["disk_read_bytes_per_second"] is None


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
    assert snapshot["summary"] == {
        "cpu_percent": 18.5,
        "memory_bytes": 300,
        "process_count": 2,
        "disk_read_bytes_per_second": 60.0,
        "disk_write_bytes_per_second": 50.0,
        "network_connection_count": 3,
    }
    root_sample = next(item for item in snapshot["processes"] if item["pid"] == root.pid)
    assert root_sample["disk_read_bytes_per_second"] == 30.0
    assert root.cpu_intervals == [None, None]


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

    assert snapshot["status"] == "warming_up"
    assert [process["pid"] for process in snapshot["processes"]] == [101]
    assert snapshot["warnings"] == [{"code": "child_process_unavailable", "pid": 102}]


def test_history_keeps_fixed_150_point_limit_when_smaller_capacity_is_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = FakeProcess(101, None, name="api")
    monkeypatch.setattr(resource_monitor_service.psutil, "Process", lambda pid: root)
    monotonic_values = iter(float(index) for index in range(200))
    monkeypatch.setattr(resource_monitor_service.time, "monotonic", monotonic_values.__next__)
    service = resource_monitor_service.ResourceMonitoringService(root_pid=101, history_size=1)

    for _ in range(151):
        service.collect_snapshot()

    assert len(service.history(window_seconds=3600)) == 150
