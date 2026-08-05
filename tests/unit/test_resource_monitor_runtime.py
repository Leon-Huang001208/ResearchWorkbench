"""ResourceMonitorRuntime 的后台采样与依赖协调测试。"""

from __future__ import annotations

from contextlib import contextmanager

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

        def join(self) -> None:
            self.joined = True

    monkeypatch.setattr("services.resource_monitor_runtime.threading.Thread", FakeThread)
    runtime = ResourceMonitorRuntime(monitor=FakeMonitor())

    assert runtime.start() is True
    assert runtime.start() is False
    assert len(FakeThread.instances) == 1
    assert runtime.stop() is True
    assert FakeThread.instances[0].joined is True
    assert runtime.stop() is False
