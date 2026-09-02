"""Durable minute-bucket scheduling for asset alert evaluation."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session

from core.contracts.platform_shared import ScheduledJob
from core.observability import get_logger
from data_layer.repositories.asset_observation_repository import (
    AssetObservationRepository,
)
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.asset_observation_service import AssetObservationService
from services.scheduler_coordinator import SchedulerCoordinator

logger = get_logger(__name__)


@dataclass(frozen=True)
class AlertSchedulerHealth:
    """Observable capacity decision for the latest minute materialization."""

    minute_bucket: datetime
    status: str
    active_profiles: int
    pending_jobs: int
    jobs_per_minute_capacity: int | None
    max_execution_seconds: float | None = None
    last_execution_seconds: float | None = None


class DurableSchedulerRuntimeProtocol(Protocol):
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


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("scheduler moment must be timezone-aware")
    return value.astimezone(UTC)


class AssetAlertSchedulerBindings:
    """Transaction-owning materializer and handler for active profiles."""

    JOB_TYPE = "asset_alert.evaluate"
    MATERIALIZER_NAME = "asset-alert-evaluation"

    def __init__(
        self,
        session_factory: Callable[[], Session],
        *,
        service_factory: Callable[[Session], AssetObservationService] | None = None,
        capacity_per_minute: int | None = None,
        max_execution_seconds: float = 1.0,
        monotonic_clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if capacity_per_minute is not None and capacity_per_minute < 1:
            raise ValueError("capacity_per_minute must be positive")
        if max_execution_seconds <= 0:
            raise ValueError("max_execution_seconds must be positive")
        self._session_factory = session_factory
        self._service_factory = service_factory or (
            lambda db: AssetObservationService(AssetObservationRepository(db))
        )
        self._capacity_per_minute = capacity_per_minute
        self._max_execution_seconds = max_execution_seconds
        self._monotonic_clock = monotonic_clock
        self._execution_budget_breached = False
        self.last_health: AlertSchedulerHealth | None = None
        self.materializer_callback = self.materialize
        self.handler_callback = self.handle

    def register(self, runtime: DurableSchedulerRuntimeProtocol) -> None:
        capacity_calculator = getattr(runtime, "jobs_per_minute_capacity_for", None)
        runtime_capacity = (
            capacity_calculator(max_execution_seconds=self._max_execution_seconds)
            if callable(capacity_calculator)
            else None
        )
        if runtime_capacity is not None:
            if runtime_capacity < 1:
                raise ValueError("durable runtime cannot service minute alert jobs")
            self._capacity_per_minute = (
                runtime_capacity
                if self._capacity_per_minute is None
                else min(self._capacity_per_minute, runtime_capacity)
            )
        runtime.register_materializer(self.MATERIALIZER_NAME, self.materializer_callback)
        runtime.register_handler(self.JOB_TYPE, self.handler_callback)

    @property
    def is_ready(self) -> bool:
        """Fail closed after unknown capacity or an observed execution overrun."""

        blocked = self.last_health is not None and self.last_health.status.startswith("blocked")
        return (
            self._capacity_per_minute is not None
            and not self._execution_budget_breached
            and not blocked
        )

    def materialize(self, moment: datetime) -> list[ScheduledJob]:
        """Enqueue one idempotent job per active profile and UTC minute bucket."""

        bucket = _aware_utc(moment).replace(second=0, microsecond=0)
        if self._execution_budget_breached:
            previous = self.last_health
            self.last_health = AlertSchedulerHealth(
                minute_bucket=bucket,
                status="blocked_execution_budget",
                active_profiles=previous.active_profiles if previous else 0,
                pending_jobs=previous.pending_jobs if previous else 0,
                jobs_per_minute_capacity=self._capacity_per_minute,
                max_execution_seconds=self._max_execution_seconds,
                last_execution_seconds=(previous.last_execution_seconds if previous else None),
            )
            logger.error(
                "asset alert materialization blocked after execution budget breach",
                minute_bucket=bucket.isoformat(),
                max_execution_seconds=self._max_execution_seconds,
                last_execution_seconds=self.last_health.last_execution_seconds,
            )
            return []
        if self._capacity_per_minute is None:
            self.last_health = AlertSchedulerHealth(
                minute_bucket=bucket,
                status="blocked_capacity_unknown",
                active_profiles=0,
                pending_jobs=0,
                jobs_per_minute_capacity=None,
                max_execution_seconds=self._max_execution_seconds,
            )
            logger.error(
                "asset alert materialization blocked without runtime capacity",
                minute_bucket=bucket.isoformat(),
            )
            return []
        db = self._session_factory()
        try:
            profiles = AssetObservationRepository(db).list_active_alert_profile_ids()
            coordinator = SchedulerCoordinator(ResearchWorkspaceRepository(db))
            jobs = [
                coordinator.enqueue(
                    owner=f"asset_alert:{profile_id}",
                    job_type=self.JOB_TYPE,
                    idempotency_key=f"evaluate:{profile_id}:{bucket.isoformat()}",
                    scheduled_for=bucket,
                    payload={
                        "profile_id": profile_id,
                        "evaluated_at": bucket.isoformat(),
                    },
                )
                for profile_id in profiles
            ]
            minute_deadline = bucket + timedelta(minutes=1, microseconds=-1)
            pending_jobs = coordinator.count_pending_jobs(due_by=minute_deadline)
            if pending_jobs > self._capacity_per_minute:
                db.rollback()
                self.last_health = AlertSchedulerHealth(
                    minute_bucket=bucket,
                    status="blocked_capacity",
                    active_profiles=len(profiles),
                    pending_jobs=pending_jobs,
                    jobs_per_minute_capacity=self._capacity_per_minute,
                    max_execution_seconds=self._max_execution_seconds,
                )
                logger.error(
                    "asset alert minute SLA capacity gate blocked materialization",
                    minute_bucket=bucket.isoformat(),
                    active_profiles=len(profiles),
                    pending_jobs=pending_jobs,
                    jobs_per_minute_capacity=self._capacity_per_minute,
                )
                return []
            db.commit()
            self.last_health = AlertSchedulerHealth(
                minute_bucket=bucket,
                status="ready",
                active_profiles=len(profiles),
                pending_jobs=pending_jobs,
                jobs_per_minute_capacity=self._capacity_per_minute,
                max_execution_seconds=self._max_execution_seconds,
            )
            logger.info(
                "asset alert jobs materialized",
                minute_bucket=bucket.isoformat(),
                profile_count=len(profiles),
                job_count=len(jobs),
                pending_jobs=pending_jobs,
                jobs_per_minute_capacity=self._capacity_per_minute,
            )
            return jobs
        except Exception:
            db.rollback()
            logger.exception(
                "asset alert job materialization failed",
                minute_bucket=bucket.isoformat(),
            )
            raise
        finally:
            db.close()

    def handle(self, job: ScheduledJob) -> object:
        """Evaluate one profile and persist alert events/notifications atomically."""

        if job.job_type != self.JOB_TYPE:
            raise ValueError("unexpected asset-alert job type")
        profile_id = str(job.payload.get("profile_id") or "").strip()
        evaluated_at_value = str(job.payload.get("evaluated_at") or "")
        if not profile_id or not evaluated_at_value:
            raise ValueError("asset-alert job requires profile_id and evaluated_at")
        evaluated_at = _aware_utc(datetime.fromisoformat(evaluated_at_value))
        db = self._session_factory()
        started = self._monotonic_clock()
        try:
            result = self._service_factory(db).evaluate_due_alerts(profile_id, evaluated_at)
            db.commit()
            elapsed_seconds = self._monotonic_clock() - started
            if elapsed_seconds > self._max_execution_seconds:
                previous = self.last_health
                self._execution_budget_breached = True
                self.last_health = AlertSchedulerHealth(
                    minute_bucket=evaluated_at.replace(second=0, microsecond=0),
                    status="degraded_execution_budget",
                    active_profiles=previous.active_profiles if previous else 1,
                    pending_jobs=previous.pending_jobs if previous else 0,
                    jobs_per_minute_capacity=self._capacity_per_minute,
                    max_execution_seconds=self._max_execution_seconds,
                    last_execution_seconds=elapsed_seconds,
                )
                logger.error(
                    "asset alert handler exceeded execution budget",
                    profile_id=profile_id,
                    evaluated_at=evaluated_at.isoformat(),
                    elapsed_seconds=elapsed_seconds,
                    max_execution_seconds=self._max_execution_seconds,
                )
            logger.info(
                "asset alert job completed",
                profile_id=profile_id,
                evaluated_at=evaluated_at.isoformat(),
                elapsed_seconds=elapsed_seconds,
            )
            return result
        except Exception:
            db.rollback()
            logger.exception(
                "asset alert job failed",
                profile_id=profile_id,
                evaluated_at=evaluated_at.isoformat(),
            )
            raise
        finally:
            db.close()


_default_asset_alert_bindings: AssetAlertSchedulerBindings | None = None


def register_default_asset_alert_scheduler(
    runtime: DurableSchedulerRuntimeProtocol,
) -> AssetAlertSchedulerBindings:
    """Register stable process-wide alert callbacks before runtime startup."""

    global _default_asset_alert_bindings
    if _default_asset_alert_bindings is None:
        from data_layer.repositories.base import SessionLocal

        _default_asset_alert_bindings = AssetAlertSchedulerBindings(SessionLocal)
    _default_asset_alert_bindings.register(runtime)
    return _default_asset_alert_bindings
