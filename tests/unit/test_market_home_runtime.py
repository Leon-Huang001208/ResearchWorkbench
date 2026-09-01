"""Market-home close snapshots use the durable generic scheduler runtime."""

from __future__ import annotations

from datetime import UTC, date, datetime

from app.api import main
from core.contracts.platform_shared import ScheduledJob, ScheduledJobStatus
from data_layer.repositories.market_home_repository import MarketHomeRepository
from data_layer.repositories.models import MarketHomeSnapshotDB, ScheduledJobDB
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services import market_home_invalidation
from services.market_home_invalidation import MarketHomeSchedulerRuntime
from services.market_home_service import MarketHomeService
from services.scheduler_coordinator import SchedulerCoordinator

NOW = datetime(2026, 9, 1, 8, 0, tzinfo=UTC)
LOCAL_CLOSE = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)


class FakeThread:
    def __init__(self, *, target, name: str, daemon: bool) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.started = False
        self.joined = False

    def start(self) -> None:
        self.started = True

    def is_alive(self) -> bool:
        return self.started and not self.joined

    def join(self, timeout: float | None = None) -> None:
        self.joined = True


class FakeCoordinator:
    def __init__(self) -> None:
        self.handlers: dict[str, object] = {}
        self.run_calls = 0

    def register_handler(self, job_type: str, handler) -> None:
        self.handlers[job_type] = handler

    def run_due(self, worker_id: str, *, lease_seconds: int, limit: int = 1):
        self.run_calls += 1
        return []


def _job() -> ScheduledJob:
    return ScheduledJob(
        job_id="market-close-1",
        owner="market_home",
        job_type="market_home.close_snapshot",
        idempotency_key="market-home-close:2026-09-01",
        status=ScheduledJobStatus.IDLE,
        scheduled_for=NOW,
        payload={"trading_day": "2026-09-01"},
        attempt=0,
        fencing_token=0,
    )


def test_runtime_registers_handler_ensures_daily_job_and_starts_consumption() -> None:
    coordinator = FakeCoordinator()
    ensured: list[date] = []
    snapshots: list[date] = []
    runtime = MarketHomeSchedulerRuntime(
        coordinator,
        ensure_job=lambda day: ensured.append(day) or _job(),
        create_snapshot=lambda day: snapshots.append(day),
        clock=lambda: NOW,
        thread_factory=FakeThread,
    )

    assert runtime.start() is True
    assert runtime.start() is False
    assert ensured == [date(2026, 9, 1)]
    assert runtime.worker_thread is not None
    assert runtime.worker_thread.started is True
    handler = coordinator.handlers["market_home.close_snapshot"]
    handler(_job())
    assert snapshots == [date(2026, 9, 1)]
    assert runtime.run_once() == []
    assert coordinator.run_calls == 1
    assert runtime.stop() is True


def test_real_coordinator_consumes_persisted_close_job_with_registered_handler(
    db_session,
) -> None:
    coordinator = SchedulerCoordinator(ResearchWorkspaceRepository(db_session), clock=lambda: NOW)
    service = MarketHomeService(MarketHomeRepository(db_session), now_provider=lambda: LOCAL_CLOSE)
    runtime = MarketHomeSchedulerRuntime(
        coordinator,
        ensure_job=service.schedule_close_snapshot,
        create_snapshot=service.create_close_snapshot,
        clock=lambda: NOW,
        thread_factory=FakeThread,
        commit_callback=db_session.flush,
    )

    runtime.start()
    completed = runtime.run_once()

    assert len(completed) == 1
    assert completed[0].status == ScheduledJobStatus.SUCCEEDED
    assert db_session.query(ScheduledJobDB).count() == 1
    assert db_session.query(MarketHomeSnapshotDB).count() == 5


def test_api_startup_builder_holds_and_stops_market_home_runtime(monkeypatch) -> None:
    calls: list[str] = []

    class FakeRuntime:
        def start(self) -> None:
            calls.append("start")

        def stop(self) -> None:
            calls.append("stop")

    runtime = FakeRuntime()
    previous = main._market_home_scheduler_runtime
    monkeypatch.setattr(main, "_market_home_scheduler_runtime", None)
    monkeypatch.setattr(
        market_home_invalidation,
        "build_default_market_home_scheduler_runtime",
        lambda: runtime,
    )
    try:
        main._start_market_home_scheduler_runtime()
        main._start_market_home_scheduler_runtime()
        main._stop_market_home_scheduler_runtime()
    finally:
        main._market_home_scheduler_runtime = previous

    assert calls == ["start", "start", "stop"]
