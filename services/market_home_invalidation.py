"""Transaction-coupled invalidation and durable market-home scheduler runtime."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterable
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.contracts.market_home import (
    MarketHomeInvalidationEvent,
    MarketHomeSectionKey,
)
from core.contracts.platform_shared import ScheduledJob
from core.observability import get_logger
from data_layer.repositories.market_home_repository import MarketHomeRepository
from services.market_home_service import MarketHomeService

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class SchedulerCoordinatorProtocol(Protocol):
    """Stable generic scheduler surface consumed by the market-home runtime."""

    def register_handler(
        self, job_type: str, handler: Callable[[ScheduledJob], object]
    ) -> None: ...

    def run_due(
        self, worker_id: str, *, lease_seconds: int, limit: int = 1
    ) -> list[ScheduledJob]: ...


def aware_utc(value: datetime) -> datetime:
    """Normalize legacy naive writer timestamps without changing aware instants."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def record_market_home_fact_update(
    db: Session,
    section_keys: Iterable[MarketHomeSectionKey],
    *,
    as_of: datetime,
    idempotency_key: str,
) -> list[MarketHomeInvalidationEvent]:
    """Flush idempotent outbox rows in the caller's uncommitted fact transaction."""

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    normalized_as_of = aware_utc(as_of)
    repository = MarketHomeRepository(db)
    events = [
        repository.record_invalidation(
            section_key,
            as_of=normalized_as_of,
            idempotency_key=idempotency_key,
        )
        for section_key in sorted(set(section_keys), key=lambda item: item.value)
    ]
    logger.info(
        "market home fact update invalidations flushed",
        idempotency_key=idempotency_key,
        section_keys=[event.section_key.value for event in events],
        as_of=normalized_as_of.isoformat(),
    )
    return events


class MarketHomeSchedulerRuntime:
    """Small background consumer around the generic durable coordinator."""

    JOB_TYPE = "market_home.close_snapshot"

    def __init__(
        self,
        coordinator: SchedulerCoordinatorProtocol,
        *,
        ensure_job: Callable[[date], ScheduledJob],
        create_snapshot: Callable[[date], object],
        clock: Callable[[], datetime] | None = None,
        poll_interval_seconds: float = 15.0,
        lease_seconds: int = 60,
        worker_id: str | None = None,
        thread_factory: Callable[..., Any] = threading.Thread,
        commit_callback: Callable[[], object] | None = None,
        rollback_callback: Callable[[], object] | None = None,
        cleanup_callback: Callable[[], object] | None = None,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.coordinator = coordinator
        self.ensure_job = ensure_job
        self.create_snapshot = create_snapshot
        self.clock = clock or (lambda: datetime.now(UTC))
        self.poll_interval_seconds = poll_interval_seconds
        self.lease_seconds = lease_seconds
        self.worker_id = worker_id or f"market-home-{uuid4().hex}"
        self.thread_factory = thread_factory
        self.commit_callback = commit_callback
        self.rollback_callback = rollback_callback
        self.cleanup_callback = cleanup_callback
        self.worker_thread: Any | None = None
        self._stop_event = threading.Event()
        self._registered_handler = self._handle_close_snapshot

    def start(self) -> bool:
        """Register, ensure today's job, and start one idempotent consumer thread."""

        if self.worker_thread is not None and self.worker_thread.is_alive():
            return False
        self.coordinator.register_handler(self.JOB_TYPE, self._registered_handler)
        self._ensure_today_job()
        self._stop_event.clear()
        self.worker_thread = self.thread_factory(
            target=self._run_loop,
            name="market-home-scheduler",
            daemon=True,
        )
        self.worker_thread.start()
        logger.info("market home scheduler runtime started", worker_id=self.worker_id)
        return True

    def stop(self) -> bool:
        """Stop the consumer without blocking API shutdown indefinitely."""

        if self.worker_thread is None or not self.worker_thread.is_alive():
            return False
        self._stop_event.set()
        self.worker_thread.join(timeout=min(5.0, self.poll_interval_seconds + 1.0))
        if self.cleanup_callback is not None:
            self.cleanup_callback()
        logger.info("market home scheduler runtime stopped", worker_id=self.worker_id)
        return True

    def run_once(self) -> list[ScheduledJob]:
        """Ensure the daily job and consume due registered work once."""

        self._ensure_today_job()
        try:
            completed = self.coordinator.run_due(
                self.worker_id,
                lease_seconds=self.lease_seconds,
                limit=10,
            )
            if self.commit_callback is not None:
                self.commit_callback()
            return completed
        except Exception:
            if self.rollback_callback is not None:
                self.rollback_callback()
            raise

    def _ensure_today_job(self) -> ScheduledJob | None:
        now = self.clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        trading_day = now.astimezone(SHANGHAI_TZ).date()
        if trading_day.weekday() >= 5:
            return None
        return self.ensure_job(trading_day)

    def _handle_close_snapshot(self, job: ScheduledJob) -> object:
        if job.job_type != self.JOB_TYPE:
            raise ValueError("unexpected market-home job type")
        trading_day_value = job.payload.get("trading_day")
        if not trading_day_value:
            raise ValueError("market-home close job requires trading_day")
        return self.create_snapshot(date.fromisoformat(str(trading_day_value)))

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                logger.exception(
                    "market home scheduler cycle failed",
                    worker_id=self.worker_id,
                    error_type=type(exc).__name__,
                )
            self._stop_event.wait(self.poll_interval_seconds)


def build_default_market_home_scheduler_runtime() -> MarketHomeSchedulerRuntime:
    """Build the production runtime lazily after PostgreSQL/schema readiness."""

    from data_layer.repositories.base import SessionLocal
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.scheduler_coordinator import SchedulerCoordinator

    coordinator_session = SessionLocal()
    coordinator = SchedulerCoordinator(ResearchWorkspaceRepository(coordinator_session))

    def ensure_job(trading_day: date) -> ScheduledJob:
        with SessionLocal() as db:
            try:
                job = MarketHomeService(MarketHomeRepository(db)).schedule_close_snapshot(
                    trading_day
                )
                db.commit()
                return job
            except Exception:
                db.rollback()
                raise

    def create_snapshot(trading_day: date) -> object:
        with SessionLocal() as db:
            try:
                snapshots = MarketHomeService(MarketHomeRepository(db)).create_close_snapshot(
                    trading_day
                )
                db.commit()
                return snapshots
            except Exception:
                db.rollback()
                raise

    return MarketHomeSchedulerRuntime(
        coordinator,
        ensure_job=ensure_job,
        create_snapshot=create_snapshot,
        commit_callback=coordinator_session.commit,
        rollback_callback=coordinator_session.rollback,
        cleanup_callback=coordinator_session.close,
    )
