"""ResourceMonitorRuntime 的后台采样与依赖协调测试。"""

from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from core.contracts.monitoring import AlertStatus
from services import resource_monitor_runtime
from services.resource_monitor_alert_service import ResourceAlertState
from services.resource_monitor_runtime import ResourceMonitorRuntime


class FakeMonitor:
    def __init__(self) -> None:
        self.calls = 0

    def collect_snapshot(self) -> dict[str, object]:
        self.calls += 1
        return {"host": {}, "summary": {}, "sequence": self.calls}


class FakeHistory:
    def __init__(self) -> None:
        self.snapshots: list[object] = []

    def record_if_due(self, snapshot: object) -> bool:
        self.snapshots.append(snapshot)
        return True


class FakeAlerts:
    def __init__(self) -> None:
        self.snapshots: list[object] = []

    def evaluate(self, snapshot: object) -> list[object]:
        self.snapshots.append(snapshot)
        return []


class PressureMonitor:
    def collect_snapshot(self) -> dict[str, object]:
        return {
            "host": {},
            "summary": {},
            "status": "ok",
            "warnings": [],
            "task_failures": [],
            "processes": [{"pid": 101, "cpu_percent": 95.0, "memory_bytes": 1}],
        }


class AlertRepository:
    def __init__(self) -> None:
        self.alerts: list[object] = []
        self.incidents: list[object] = []

    def list_alerts(self, **_: object) -> list[object]:
        return list(self.alerts)

    def save_alert(self, alert: object) -> object:
        self.alerts.append(alert)
        return alert

    def save_incident(self, incident: object) -> object:
        self.incidents.append(incident)
        return incident

    def list_incidents(self, **_: object) -> list[object]:
        return list(self.incidents)


def test_run_once_collects_persists_and_evaluates_with_one_shared_state() -> None:
    monitor = FakeMonitor()
    history = FakeHistory()
    alerts = FakeAlerts()
    repositories: list[object] = []
    state_values: list[object] = []

    @contextmanager
    def session_factory():
        session = object()
        yield session

    def history_factory(repository: object) -> FakeHistory:
        repositories.append(repository)
        return history

    def alert_factory(repository: object, *, state: object) -> FakeAlerts:
        repositories.append(repository)
        state_values.append(state)
        return alerts

    runtime = ResourceMonitorRuntime(
        monitor=monitor,
        history_factory=history_factory,
        alert_factory=alert_factory,
        session_factory=session_factory,
        repository_factory=lambda session: session,
    )

    assert runtime.run_once() is True
    assert monitor.calls == 1
    assert history.snapshots == [{"host": {}, "summary": {}, "sequence": 1}]
    assert alerts.snapshots == [{"host": {}, "summary": {}, "sequence": 1}]
    assert repositories[0] is repositories[1]
    assert state_values == [runtime.state]
    assert runtime.last_error_type is None


def test_run_once_keeps_future_cycles_alive_after_history_or_alert_failure() -> None:
    monitor = FakeMonitor()

    @contextmanager
    def session_factory():
        yield object()

    class FailingHistory(FakeHistory):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def record_if_due(self, snapshot: object) -> bool:
            self.calls += 1
            if self.calls == 1:
                raise RuntimeError("history unavailable")
            return super().record_if_due(snapshot)

    class FailingAlerts(FakeAlerts):
        def __init__(self) -> None:
            super().__init__()
            self.calls = 0

        def evaluate(self, snapshot: object) -> list[object]:
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("alerts unavailable")
            return super().evaluate(snapshot)

    history = FailingHistory()
    alerts = FailingAlerts()

    runtime = ResourceMonitorRuntime(
        monitor=monitor,
        history_factory=lambda _: history,
        alert_factory=lambda _, *, state: alerts,
        session_factory=session_factory,
        repository_factory=lambda session: session,
    )

    assert runtime.run_once() is False
    assert runtime.last_error_type == "RuntimeError"
    assert runtime.run_once() is False
    assert runtime.last_error_type == "RuntimeError"
    assert runtime.run_once() is True
    assert monitor.calls == 3


def test_default_alert_factory_shares_pressure_state_across_runtime_cycles() -> None:
    repository = AlertRepository()

    @contextmanager
    def session_factory():
        yield repository

    runtime = ResourceMonitorRuntime(
        monitor=PressureMonitor(),
        history_factory=lambda _: FakeHistory(),
        session_factory=session_factory,
        repository_factory=lambda session: session,
    )

    assert isinstance(runtime.state, ResourceAlertState)
    assert runtime.run_once() is True
    assert runtime.run_once() is True
    assert runtime.state.pressure_counts["resource_pressure:101"] == 2
    assert runtime.run_once() is True
    assert len(repository.alerts) == 1
    assert repository.alerts[0].status is AlertStatus.OPEN


def test_start_is_idempotent_and_stop_joins_the_worker(monkeypatch) -> None:
    class FakeThread:
        instances: list["FakeThread"] = []

        def __init__(self, *, target, name, daemon) -> None:
            self.target = target
            self.name = name
            self.daemon = daemon
            self.started = False
            self.joined = False
            FakeThread.instances.append(self)

        def start(self) -> None:
            self.started = True

        def is_alive(self) -> bool:
            return self.started and not self.joined

        def join(self, timeout: float | None = None) -> None:
            self.joined = True

    monkeypatch.setattr("services.resource_monitor_runtime.threading.Thread", FakeThread)
    runtime = ResourceMonitorRuntime(monitor=FakeMonitor())

    assert runtime.start() is True
    assert runtime.start() is False
    assert len(FakeThread.instances) == 1
    assert runtime.stop() is True
    assert FakeThread.instances[0].joined is True
    assert runtime.stop() is False


def test_stop_times_out_without_blocking_api_shutdown(monkeypatch) -> None:
    entered = threading.Event()
    release = threading.Event()
    log = MagicMock()

    class BlockingMonitor:
        def collect_snapshot(self) -> dict[str, object]:
            entered.set()
            release.wait()
            return {"host": {}, "summary": {}}

    monkeypatch.setattr(resource_monitor_runtime, "logger", log)
    runtime = ResourceMonitorRuntime(
        monitor=BlockingMonitor(),
        history_factory=lambda _: FakeHistory(),
        alert_factory=lambda _, *, state: FakeAlerts(),
        join_timeout_seconds=0.01,
    )

    assert runtime.start() is True
    assert entered.wait(timeout=1.0)
    started_at = time.monotonic()
    assert runtime.stop() is False
    assert time.monotonic() - started_at < 0.5
    log.warning.assert_called_once_with(
        "resource monitor runtime shutdown timed out",
        error_type="RuntimeStopTimeout",
        thread_alive=True,
    )

    release.set()
    assert runtime._thread is not None
    runtime._thread.join(timeout=1.0)
    assert runtime._thread.is_alive() is False


def test_join_timeout_must_be_positive() -> None:
    with pytest.raises(ValueError, match="join_timeout_seconds must be positive"):
        ResourceMonitorRuntime(monitor=FakeMonitor(), join_timeout_seconds=0)
