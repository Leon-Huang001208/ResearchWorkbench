"""Transaction-coupled invalidation and durable market-home scheduler runtime."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from core.contracts.platform_shared import ScheduledJob
from core.observability import get_logger
from data_layer.repositories.market_home_invalidation import aware_utc
from data_layer.repositories.market_home_repository import MarketHomeRepository
from services.market_home_service import MarketHomeService

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


class CjpyAShareTradingCalendar:
    """Authoritative exchange-day lookup backed by the registered Cjpy provider."""

    def __init__(self, adapter_factory: Callable[[], Any] | None = None) -> None:
        self._adapter_factory = adapter_factory or self._build_adapter
        self._cache: dict[date, bool] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _build_adapter() -> Any:
        from data_layer.adapters.cjpy_adapter import CjpyAdapter

        return CjpyAdapter()

    def is_trading_day(self, trading_day: date) -> bool | None:
        """Return ``None`` when authority cannot answer, so callers fail closed."""

        with self._lock:
            cached = self._cache.get(trading_day)
        if cached is not None:
            return cached
        day_value = trading_day.strftime("%Y%m%d")
        try:
            values = self._adapter_factory().fetch_trading_days(
                start=day_value,
                end=day_value,
            )
        except Exception as exc:  # noqa: BLE001 - external provider availability boundary
            logger.warning(
                "authoritative A-share calendar unavailable",
                trading_day=trading_day.isoformat(),
                error_type=type(exc).__name__,
            )
            return None
        normalized = {str(value).replace("-", "")[:8] for value in values if value is not None}
        result = day_value in normalized
        with self._lock:
            self._cache[trading_day] = result
        return result


class SchedulerCoordinatorProtocol(Protocol):
    """Stable generic scheduler surface consumed by the market-home runtime."""

    def register_handler(
        self, job_type: str, handler: Callable[[ScheduledJob], object]
    ) -> None: ...

    def run_due(
        self, worker_id: str, *, lease_seconds: int, limit: int = 1
    ) -> list[ScheduledJob]: ...


class DurableSchedulerRuntimeProtocol(Protocol):
    """Registration surface shared by all durable scheduler domains."""

    def register_materializer(
        self,
        name: str,
        materializer: Callable[[datetime], object],
    ) -> None: ...

    def register_handler(
        self,
        job_type: str,
        handler: Callable[[ScheduledJob], object],
    ) -> None: ...


class MarketHomeSchedulerBindings:
    """Transaction-owning callbacks registered on the shared durable runtime."""

    JOB_TYPE = "market_home.close_snapshot"
    MATERIALIZER_NAME = "market-home-close"

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        is_trading_day: Callable[[date], bool | None] | None = None,
        service_factory: Callable[[Session, datetime | None], MarketHomeService] | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._is_trading_day = is_trading_day
        self._service_factory = service_factory or self._build_service
        # Store bound methods once because the runtime uses callable identity for
        # idempotent duplicate registration.
        self.materializer_callback = self.materialize
        self.handler_callback = self.handle

    @staticmethod
    def _build_service(db: Session, now: datetime | None) -> MarketHomeService:
        repository = MarketHomeRepository(db)
        if now is None:
            return MarketHomeService(repository)
        return MarketHomeService(repository, now_provider=lambda: now)

    def register(self, runtime: DurableSchedulerRuntimeProtocol) -> None:
        runtime.register_materializer(self.MATERIALIZER_NAME, self.materializer_callback)
        runtime.register_handler(self.JOB_TYPE, self.handler_callback)

    def materialize(self, moment: datetime) -> ScheduledJob | None:
        """Ensure one 15:05 Asia/Shanghai close job for the current workday."""

        normalized = aware_utc(moment)
        trading_day = normalized.astimezone(SHANGHAI_TZ).date()
        if trading_day.weekday() >= 5:
            return None
        if self._is_trading_day is None:
            logger.warning(
                "market home close job skipped without authoritative calendar",
                trading_day=trading_day.isoformat(),
            )
            return None
        try:
            calendar_result = self._is_trading_day(trading_day)
        except Exception as exc:  # noqa: BLE001 - injected provider availability boundary
            logger.warning(
                "market home close job skipped after calendar failure",
                trading_day=trading_day.isoformat(),
                error_type=type(exc).__name__,
            )
            return None
        if calendar_result is not True:
            logger.info(
                "market home close job skipped for non-trading or unknown day",
                trading_day=trading_day.isoformat(),
                calendar_available=calendar_result is not None,
            )
            return None
        db = self._session_factory()
        try:
            job = self._service_factory(db, normalized).schedule_close_snapshot(trading_day)
            db.commit()
            logger.info(
                "market home close job materialized",
                trading_day=trading_day.isoformat(),
                scheduled_for=job.scheduled_for.isoformat(),
            )
            return job
        except Exception:
            db.rollback()
            logger.exception(
                "market home close job materialization failed",
                trading_day=trading_day.isoformat(),
            )
            raise
        finally:
            db.close()

    def handle(self, job: ScheduledJob) -> object:
        """Create all five immutable close-section snapshots in one transaction."""

        if job.job_type != self.JOB_TYPE:
            raise ValueError("unexpected market-home job type")
        trading_day_value = str(job.payload.get("trading_day") or "")
        if not trading_day_value:
            raise ValueError("market-home close job requires trading_day")
        trading_day = date.fromisoformat(trading_day_value)
        db = self._session_factory()
        try:
            snapshots = self._service_factory(db, None).create_close_snapshot(trading_day)
            db.commit()
            logger.info(
                "market home close snapshots persisted",
                trading_day=trading_day.isoformat(),
                snapshot_count=len(snapshots),
            )
            return snapshots
        except Exception:
            db.rollback()
            logger.exception(
                "market home close snapshot handler failed",
                trading_day=trading_day.isoformat(),
            )
            raise
        finally:
            db.close()


_default_market_home_bindings: MarketHomeSchedulerBindings | None = None


def register_default_market_home_scheduler(
    runtime: DurableSchedulerRuntimeProtocol,
) -> MarketHomeSchedulerBindings:
    """Register stable process-wide market callbacks before runtime startup."""

    global _default_market_home_bindings
    if _default_market_home_bindings is None:
        from data_layer.repositories.base import SessionLocal

        calendar = CjpyAShareTradingCalendar()
        _default_market_home_bindings = MarketHomeSchedulerBindings(
            SessionLocal,
            is_trading_day=calendar.is_trading_day,
        )
    _default_market_home_bindings.register(runtime)
    return _default_market_home_bindings


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
