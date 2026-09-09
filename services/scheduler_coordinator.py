"""Database-backed no-reentry scheduler coordinator with lease takeover."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from threading import Event, Lock, RLock, Thread
from typing import Any
from uuid import uuid4

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import func, select

from core.contracts.platform_shared import ScheduledJob
from core.observability import get_logger
from data_layer.repositories.models import ScheduledJobDB
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.agent_team_service import AgentTeamRun, AgentTeamService

logger = get_logger(__name__)


class SchedulerCoordinator:
    def __init__(
        self,
        repository: ResearchWorkspaceRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        handlers: dict[str, Callable[[ScheduledJob], object]] | None = None,
        max_attempts: int = 3,
        retry_base_seconds: int = 5,
        retry_max_seconds: int = 60,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        if retry_base_seconds < 1 or retry_max_seconds < retry_base_seconds:
            raise ValueError("retry backoff bounds are invalid")
        self.repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._handlers = dict(handlers or {})
        self._max_attempts = max_attempts
        self._retry_base_seconds = retry_base_seconds
        self._retry_max_seconds = retry_max_seconds

    @staticmethod
    def _owner(schedule_id: str) -> str:
        return f"agent_schedule:{schedule_id}"

    def register_handler(self, job_type: str, handler: Callable[[ScheduledJob], object]) -> None:
        """Register one process-local executor for a durable job type."""

        if not job_type.strip():
            raise ValueError("job_type is required")
        existing = self._handlers.get(job_type)
        if existing is not None and existing is not handler:
            raise ValueError(f"handler already registered for {job_type}")
        self._handlers[job_type] = handler

    def enqueue(
        self,
        *,
        owner: str,
        job_type: str,
        idempotency_key: str,
        scheduled_for: datetime,
        payload: dict | None = None,
    ) -> ScheduledJob:
        """Persist a generic job without importing its domain repository."""

        existing = self.repository.find_job_by_idempotency(owner, idempotency_key)
        if existing is not None:
            if existing.job_type != job_type or dict(existing.payload or {}) != dict(payload or {}):
                raise ValueError("scheduled job idempotency conflict")
            return self.repository.to_scheduled_job(existing)
        now = self._clock()
        row = ScheduledJobDB(
            job_id=f"job-{uuid4().hex}",
            owner=owner,
            job_type=job_type,
            idempotency_key=idempotency_key,
            status="idle",
            scheduled_for=self._aware(scheduled_for),
            allow_concurrent=False,
            coalesce_policy="latest",
            payload=dict(payload or {}),
            created_at=now,
            updated_at=now,
        )
        self.repository.add_job(row)
        logger.info("scheduled job enqueued", job_id=row.job_id, job_type=job_type, owner=owner)
        return self.repository.to_scheduled_job(row)

    def claim_due(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledJob | None:
        """Claim one due job whose type has a registered handler."""

        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        if not self._handlers:
            return None
        moment = now or self._clock()
        row = self.repository.claimable_due_job(
            job_types=set(self._handlers),
            now=moment,
        )
        if row is None:
            return None
        row.status = "leased"
        row.lease_owner = worker_id
        row.lease_expires_at = moment + timedelta(seconds=lease_seconds)
        row.attempt += 1
        row.updated_at = moment
        self.repository.db.flush()
        return self.repository.to_scheduled_job(row)

    def run_due(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        limit: int = 1,
        claim_now: datetime | None = None,
        heartbeat_callback: Callable[[ScheduledJob, str, int, int], None] | None = None,
        heartbeat_interval_seconds: float | None = None,
        lease_acquired_callback: Callable[[ScheduledJob], None] | None = None,
    ) -> list[ScheduledJob]:
        """Execute registered due jobs through claim/renew/fenced-complete."""

        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        completed: list[ScheduledJob] = []
        for _ in range(limit):
            claimed = self.claim_due(
                worker_id,
                lease_seconds=lease_seconds,
                now=claim_now,
            )
            if claimed is None:
                break
            running = self.renew(
                claimed.job_id,
                worker_id,
                fencing_token=claimed.fencing_token,
                lease_seconds=lease_seconds,
            )
            if lease_acquired_callback is not None:
                lease_acquired_callback(running)
            handler = self._handlers[running.job_type]
            heartbeat_stop = Event()
            heartbeat_thread: Thread | None = None
            if heartbeat_callback is not None:
                heartbeat_interval = heartbeat_interval_seconds or max(0.1, lease_seconds / 3)
                if heartbeat_interval <= 0:
                    raise ValueError("heartbeat_interval_seconds must be positive")

                def heartbeat_loop(
                    stop: Event = heartbeat_stop,
                    interval: float = heartbeat_interval,
                    current: ScheduledJob = running,
                ) -> None:
                    while not stop.wait(interval):
                        try:
                            heartbeat_callback(
                                current,
                                worker_id,
                                current.fencing_token,
                                lease_seconds,
                            )
                        except Exception:
                            logger.exception(
                                "scheduled job lease heartbeat failed",
                                job_id=current.job_id,
                                worker_id=worker_id,
                            )
                            return

                heartbeat_thread = Thread(
                    target=heartbeat_loop,
                    name=f"scheduler-heartbeat-{running.job_id}",
                    daemon=True,
                )
                heartbeat_thread.start()
            try:
                handler(running)
            except Exception as exc:  # persist failure before continuing loop
                logger.exception(
                    "scheduled job handler failed",
                    job_id=running.job_id,
                    job_type=running.job_type,
                    error_type=type(exc).__name__,
                )
                completed.append(
                    self.complete(
                        running.job_id,
                        worker_id,
                        fencing_token=running.fencing_token,
                        succeeded=False,
                        error_code=getattr(exc, "code", "handler_failed"),
                    )
                )
                continue
            finally:
                heartbeat_stop.set()
                if heartbeat_thread is not None:
                    heartbeat_thread.join(timeout=max(1.0, heartbeat_interval * 2))
            completed.append(
                self.complete(
                    running.job_id,
                    worker_id,
                    fencing_token=running.fencing_token,
                    succeeded=True,
                )
            )
        return completed

    def materialize_due_schedules(self, *, now: datetime | None = None) -> list[ScheduledJob]:
        """Turn due cron definitions into one coalesced durable job each."""

        moment = self._aware(now or self._clock())
        materialized: list[ScheduledJob] = []
        for schedule in self.repository.due_agent_schedule_rows(moment):
            trigger = CronTrigger.from_crontab(schedule.cron_expression, timezone=UTC)
            latest_due = self._aware(schedule.next_run_at)
            missed_count = 1
            while True:
                next_run = trigger.get_next_fire_time(latest_due, latest_due)
                if next_run is None or self._aware(next_run) > moment:
                    break
                latest_due = self._aware(next_run)
                missed_count += 1
                if missed_count > 10_000:
                    raise ValueError(
                        f"agent schedule {schedule.schedule_id} exceeds missed-run safety bound"
                    )
            job = self.record_missed(
                schedule.schedule_id,
                latest_due,
                count=missed_count,
            )
            if next_run is None:
                schedule.status = "paused"
                schedule.next_run_at = None
                logger.warning(
                    "agent schedule cron has no future occurrence",
                    schedule_id=schedule.schedule_id,
                )
            else:
                schedule.next_run_at = self._aware(next_run)
            schedule.updated_at = moment
            materialized.append(job)
        self.repository.db.flush()
        return materialized

    def record_missed(
        self, schedule_id: str, scheduled_for: datetime, *, count: int
    ) -> ScheduledJob:
        if count < 1:
            raise ValueError("missed run count must be positive")
        schedule = self.repository.get_schedule_row(schedule_id, for_update=True)
        if schedule.status != "active":
            raise ValueError("schedule is not active")
        owner = self._owner(schedule_id)
        row = self.repository.active_job(owner)
        if row is None:
            now = self._clock()
            row = ScheduledJobDB(
                job_id=f"job-{uuid4().hex}",
                owner=owner,
                job_type="agent_schedule",
                idempotency_key=f"coalesced:{schedule_id}",
                status="idle",
                scheduled_for=scheduled_for,
                allow_concurrent=False,
                coalesce_policy="latest",
                payload={"schedule_id": schedule_id, "missed_count": count},
                created_at=now,
                updated_at=now,
            )
            self.repository.add_job(row)
        elif row.status in {"leased", "running"}:
            payload = dict(row.payload or {})
            previous = dict(payload.get("pending_latest") or {})
            previous_for = (
                datetime.fromisoformat(str(previous["scheduled_for"]))
                if previous.get("scheduled_for")
                else scheduled_for
            )
            payload["pending_latest"] = {
                "scheduled_for": max(previous_for, scheduled_for).isoformat(),
                "missed_count": int(previous.get("missed_count", 0)) + count,
            }
            row.payload = payload
            row.updated_at = self._clock()
        else:
            payload = dict(row.payload or {})
            payload["missed_count"] = int(payload.get("missed_count", 0)) + count
            row.payload = payload
            row.scheduled_for = max(self._aware(row.scheduled_for), self._aware(scheduled_for))
            row.updated_at = self._clock()
        schedule.scheduled_job_id = row.job_id
        schedule.next_run_at = scheduled_for
        self.repository.db.flush()
        logger.info(
            "agent schedule missed runs coalesced",
            schedule_id=schedule_id,
            job_id=row.job_id,
            missed_count=(row.payload or {}).get("missed_count")
            or ((row.payload or {}).get("pending_latest") or {}).get("missed_count"),
        )
        return self.repository.to_scheduled_job(row)

    def trigger(
        self,
        schedule_id: str,
        *,
        idempotency_key: str,
        scheduled_for: datetime | None = None,
        payload: dict | None = None,
    ) -> ScheduledJob:
        schedule = self.repository.get_schedule_row(schedule_id, for_update=True)
        if schedule.status != "active":
            raise ValueError("schedule is not active")
        owner = self._owner(schedule_id)
        requested_for = self._aware(scheduled_for or self._clock())
        request_hash = self._trigger_hash(scheduled_for, payload)
        mapped = self.repository.get_idempotent_record(
            "agent_schedule.triggered", f"{schedule_id}:{idempotency_key}"
        )
        if mapped:
            if mapped.get("request_hash") not in {None, request_hash}:
                raise ValueError("schedule trigger idempotency conflict")
            return self.repository.to_scheduled_job(
                self.repository.get_job(str(mapped["resource_id"]))
            )
        existing = self.repository.find_job_by_idempotency(owner, idempotency_key)
        if existing is not None:
            return self.repository.to_scheduled_job(existing)
        active = self.repository.active_job(owner)
        if active is not None:
            if active.status in {"leased", "running"}:
                active_payload = dict(active.payload or {})
                previous = dict(active_payload.get("pending_latest") or {})
                previous_for = (
                    datetime.fromisoformat(str(previous["scheduled_for"]))
                    if previous.get("scheduled_for")
                    else requested_for
                )
                active_payload["pending_latest"] = {
                    "idempotency_key": idempotency_key,
                    "scheduled_for": max(self._aware(previous_for), requested_for).isoformat(),
                    "missed_count": int(previous.get("missed_count", 0)) + 1,
                    **({"steps": payload["steps"]} if payload and "steps" in payload else {}),
                }
                active.payload = active_payload
            else:
                active.scheduled_for = max(self._aware(active.scheduled_for), requested_for)
                if payload:
                    active.payload = {**dict(active.payload or {}), **payload}
            self.repository.record_idempotent_resource(
                "agent_schedule.triggered",
                f"{schedule_id}:{idempotency_key}",
                active.job_id,
                occurred_at=self._clock(),
                metadata={"request_hash": request_hash},
            )
            self.repository.db.flush()
            return self.repository.to_scheduled_job(active)
        now = self._clock()
        row = ScheduledJobDB(
            job_id=f"job-{uuid4().hex}",
            owner=owner,
            job_type="agent_schedule",
            idempotency_key=idempotency_key,
            status="idle",
            scheduled_for=requested_for,
            allow_concurrent=False,
            coalesce_policy="latest",
            payload={"schedule_id": schedule_id, **(payload or {})},
            created_at=now,
            updated_at=now,
        )
        self.repository.add_job(row)
        self.repository.record_idempotent_resource(
            "agent_schedule.triggered",
            f"{schedule_id}:{idempotency_key}",
            row.job_id,
            occurred_at=now,
            metadata={"request_hash": request_hash},
        )
        schedule.scheduled_job_id = row.job_id
        self.repository.db.flush()
        return self.repository.to_scheduled_job(row)

    def pending_runs(self, schedule_id: str) -> int:
        self.repository.get_schedule_row(schedule_id)
        return min(1, self.repository.count_pending_jobs(self._owner(schedule_id)))

    def count_pending_jobs(
        self,
        *,
        due_by: datetime,
        job_type: str | None = None,
    ) -> int:
        """Count scheduler backlog that competes for capacity before a deadline."""

        statement = select(func.count(ScheduledJobDB.job_id)).where(
            ScheduledJobDB.status.in_(["idle", "leased", "running"]),
            ScheduledJobDB.scheduled_for <= self._aware(due_by),
        )
        if job_type is not None:
            statement = statement.where(ScheduledJobDB.job_type == job_type)
        return int(self.repository.db.scalar(statement) or 0)

    def claim(
        self,
        schedule_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledJob | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        moment = now or self._clock()
        schedule = self.repository.get_schedule_row(schedule_id, for_update=True)
        if schedule.status != "active" or schedule.scheduled_job_id is None:
            return None
        row = self.repository.get_job(schedule.scheduled_job_id, for_update=True)
        lease_active = (
            row.status in {"leased", "running"}
            and row.lease_expires_at is not None
            and self._aware(row.lease_expires_at) > moment
        )
        if lease_active:
            return None
        if row.status not in {"idle", "leased", "running"}:
            return None
        row.status = "leased"
        row.lease_owner = worker_id
        row.lease_expires_at = moment + timedelta(seconds=lease_seconds)
        row.attempt += 1
        row.updated_at = moment
        self.repository.db.flush()
        logger.info(
            "scheduled job lease acquired",
            schedule_id=schedule_id,
            job_id=row.job_id,
            lease_owner=worker_id,
            attempt=row.attempt,
        )
        return self.repository.to_scheduled_job(row)

    def complete(
        self,
        job_id: str,
        worker_id: str,
        *,
        fencing_token: int,
        succeeded: bool,
        error_code: str | None = None,
    ) -> ScheduledJob:
        row = self.repository.get_job(job_id, for_update=True)
        self._validate_fence(row, worker_id, fencing_token, now=self._clock())
        pending_latest = dict((row.payload or {}).get("pending_latest") or {})
        completed_at = self._clock()
        retry_scheduled = not succeeded and row.attempt < self._max_attempts
        if retry_scheduled:
            delay_seconds = min(
                self._retry_max_seconds,
                self._retry_base_seconds * (2 ** max(0, row.attempt - 1)),
            )
            row.status = "idle"
            row.scheduled_for = completed_at + timedelta(seconds=delay_seconds)
        else:
            row.status = "succeeded" if succeeded else "failed"
        row.last_error_code = None if succeeded else (error_code or "job_failed")
        row.lease_owner = None
        row.lease_expires_at = None
        row.updated_at = completed_at
        schedule_id = str((row.payload or {}).get("schedule_id") or "")
        if schedule_id and not retry_scheduled:
            schedule = self.repository.get_schedule_row(schedule_id, for_update=True)
            schedule.last_run_at = row.updated_at
            if pending_latest:
                scheduled_for = datetime.fromisoformat(str(pending_latest["scheduled_for"]))
                follow_up = ScheduledJobDB(
                    job_id=f"job-{uuid4().hex}",
                    owner=self._owner(schedule_id),
                    job_type="agent_schedule",
                    idempotency_key=f"coalesced:{schedule_id}:{scheduled_for.isoformat()}",
                    status="idle",
                    scheduled_for=scheduled_for,
                    allow_concurrent=False,
                    coalesce_policy="latest",
                    payload={
                        "schedule_id": schedule_id,
                        "missed_count": int(pending_latest.get("missed_count", 1)),
                        **({"steps": pending_latest["steps"]} if "steps" in pending_latest else {}),
                    },
                    created_at=row.updated_at,
                    updated_at=row.updated_at,
                )
                self.repository.add_job(follow_up)
                schedule.scheduled_job_id = follow_up.job_id
        self.repository.db.flush()
        if retry_scheduled:
            logger.warning(
                "scheduled job retry queued",
                job_id=row.job_id,
                job_type=row.job_type,
                attempt=row.attempt,
                error_code=row.last_error_code,
                scheduled_for=self._aware(row.scheduled_for).isoformat(),
            )
        return self.repository.to_scheduled_job(row)

    def renew(
        self,
        job_id: str,
        worker_id: str,
        *,
        fencing_token: int,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> ScheduledJob:
        """Extend an owned lease without allowing a stale worker to revive it."""

        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        moment = now or self._clock()
        row = self.repository.get_job(job_id, for_update=True)
        self._validate_fence(row, worker_id, fencing_token, now=moment)
        row.status = "running"
        row.lease_expires_at = moment + timedelta(seconds=lease_seconds)
        row.updated_at = moment
        self.repository.db.flush()
        return self.repository.to_scheduled_job(row)

    def run_once(
        self,
        schedule_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        team_service: AgentTeamService,
        worker,
    ) -> tuple[ScheduledJob, AgentTeamRun]:
        """Claim one due job, execute its persisted team, and fence completion."""

        claimed = self.claim(schedule_id, worker_id, lease_seconds=lease_seconds)
        if claimed is None:
            raise ValueError("no claimable scheduled job")
        running = self.renew(
            claimed.job_id,
            worker_id,
            fencing_token=claimed.attempt,
            lease_seconds=lease_seconds,
        )
        schedule = self.repository.get_schedule_row(schedule_id)
        team = self.repository.get_agent_team(schedule.team_id)
        steps = list(running.payload.get("steps") or [])
        if not steps:
            steps = [
                {
                    "role": role,
                    "task": {"schedule_id": schedule_id, "job_id": running.job_id},
                }
                for role in team.roles
                if role != team.supervisor_role
            ]
        try:
            team_run = team_service.execute_plan(team, steps, worker)
        except Exception as exc:
            logger.exception(
                "scheduled Agent Team execution failed",
                schedule_id=schedule_id,
                job_id=running.job_id,
                error_type=type(exc).__name__,
            )
            self.complete(
                running.job_id,
                worker_id,
                fencing_token=running.attempt,
                succeeded=False,
                error_code=getattr(exc, "code", "agent_team_failed"),
            )
            raise
        completed = self.complete(
            running.job_id,
            worker_id,
            fencing_token=running.attempt,
            succeeded=True,
        )
        return completed, team_run

    def _validate_fence(
        self,
        row: ScheduledJobDB,
        worker_id: str,
        fencing_token: int,
        *,
        now: datetime,
    ) -> None:
        lease_expired = row.lease_expires_at is None or self._aware(row.lease_expires_at) <= now
        if (
            row.lease_owner != worker_id
            or row.status not in {"leased", "running"}
            or row.attempt != fencing_token
            or lease_expired
        ):
            raise ValueError("scheduled job fencing token or lease is no longer valid")

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @staticmethod
    def _trigger_hash(scheduled_for: datetime | None, payload: dict | None) -> str:
        serialized = json.dumps(
            {
                "scheduled_for": scheduled_for.isoformat() if scheduled_for else "immediate",
                "payload": payload or {},
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class DurableSchedulerRuntime:
    """Single polling runtime shared by agent, market, and alert job handlers."""

    def __init__(
        self,
        *,
        session_factory,
        worker_id: str | None = None,
        poll_seconds: float = 5.0,
        lease_seconds: int = 30,
        batch_limit: int = 20,
        agent_worker: Callable[[Any], Any] | None = None,
        clock: Callable[[], datetime] | None = None,
        thread_factory: Callable[..., Thread] = Thread,
    ) -> None:
        if poll_seconds <= 0:
            raise ValueError("poll_seconds must be positive")
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        if batch_limit < 1 or batch_limit > 100:
            raise ValueError("batch_limit must be between 1 and 100")
        self._session_factory = session_factory
        self._worker_id = worker_id or f"scheduler-{uuid4().hex}"
        self._poll_seconds = poll_seconds
        self._lease_seconds = lease_seconds
        self._batch_limit = batch_limit
        self._handlers: dict[str, Callable[[ScheduledJob], object]] = {}
        self._materializers: dict[str, Callable[[datetime], object]] = {}
        self._agent_worker = agent_worker
        self._clock = clock or (lambda: datetime.now(UTC))
        self._thread_factory = thread_factory
        self._stop = Event()
        self._thread: Thread | None = None
        self._lifecycle_lock = RLock()

    def register_handler(self, job_type: str, handler: Callable[[ScheduledJob], object]) -> None:
        if not job_type.strip():
            raise ValueError("job_type is required")
        existing = self._handlers.get(job_type)
        if existing is not None and existing is not handler:
            raise ValueError(f"handler already registered for {job_type}")
        self._handlers[job_type] = handler

    def register_materializer(
        self,
        name: str,
        materializer: Callable[[datetime], object],
    ) -> None:
        """Register one idempotent domain job materializer for each polling cycle."""

        if not name.strip():
            raise ValueError("materializer name is required")
        existing = self._materializers.get(name)
        if existing is not None and existing is not materializer:
            raise ValueError(f"materializer already registered for {name}")
        self._materializers[name] = materializer

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    @property
    def poll_seconds(self) -> float:
        """Expose the polling SLA for production readiness checks."""

        return self._poll_seconds

    @property
    def batch_limit(self) -> int:
        return self._batch_limit

    def jobs_per_minute_capacity_for(self, *, max_execution_seconds: float) -> int:
        """Conservative serial-handler capacity within a sixty-second window."""

        if max_execution_seconds <= 0:
            raise ValueError("max_execution_seconds must be positive")
        batch_duration = self._batch_limit * max_execution_seconds
        cycle_duration = max(self._poll_seconds, batch_duration)
        full_batches = int(60 // cycle_duration)
        remaining_seconds = max(0.0, 60 - (full_batches * cycle_duration))
        partial_batch = min(
            self._batch_limit,
            int(remaining_seconds // max_execution_seconds),
        )
        return (full_batches * self._batch_limit) + partial_batch

    def start(self) -> None:
        with self._lifecycle_lock:
            if self.running:
                return
            self._stop.clear()
            self._thread = self._thread_factory(
                target=self._run_loop,
                name="durable-scheduler-runtime",
                daemon=True,
            )
            self._thread.start()
            logger.info("durable scheduler runtime started", worker_id=self._worker_id)

    def stop(self, *, timeout_seconds: float = 5.0) -> None:
        with self._lifecycle_lock:
            self._stop.set()
            if self._thread is not None:
                self._thread.join(timeout=timeout_seconds)
                if self._thread.is_alive():
                    logger.warning("durable scheduler runtime did not stop before timeout")
                    return
            self._thread = None

    def tick(self, *, now: datetime | None = None) -> list[ScheduledJob]:
        """Materialize schedules and execute one durable batch."""

        session = self._session_factory()
        try:
            repository = ResearchWorkspaceRepository(session)
            handlers = dict(self._handlers)
            if self._agent_worker is not None:
                handlers.setdefault(
                    "agent_schedule",
                    self._build_agent_schedule_handler(repository),
                )
            moment = self._aware(now or self._clock())
            coordinator = SchedulerCoordinator(
                repository,
                handlers=handlers,
                clock=self._clock,
            )
            for name, materializer in tuple(self._materializers.items()):
                try:
                    materializer(moment)
                except Exception:
                    logger.exception(
                        "durable scheduler materializer failed",
                        materializer=name,
                        worker_id=self._worker_id,
                    )
                    raise
            coordinator.materialize_due_schedules(now=moment)
            session.commit()
            completed = coordinator.run_due(
                self._worker_id,
                lease_seconds=self._lease_seconds,
                limit=self._batch_limit,
                claim_now=moment,
                lease_acquired_callback=lambda _job: session.commit(),
                heartbeat_callback=self._heartbeat,
            )
            session.commit()
            return completed
        except Exception:
            session.rollback()
            logger.exception("durable scheduler runtime tick failed", worker_id=self._worker_id)
            raise
        finally:
            session.close()

    @staticmethod
    def _aware(value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _build_agent_schedule_handler(
        self, repository: ResearchWorkspaceRepository
    ) -> Callable[[ScheduledJob], object]:
        def execute(job: ScheduledJob) -> AgentTeamRun:
            schedule_id = str(job.payload.get("schedule_id") or "")
            if not schedule_id:
                raise ValueError("agent schedule job is missing schedule_id")
            schedule = repository.get_schedule_row(schedule_id)
            team = repository.get_agent_team(schedule.team_id)
            steps = list(job.payload.get("steps") or [])
            if not steps:
                steps = [
                    {
                        "role": role,
                        "task": {"schedule_id": schedule_id, "job_id": job.job_id},
                    }
                    for role in team.roles
                    if role != team.supervisor_role
                ]
            return AgentTeamService(repository=repository).execute_plan(
                team,
                steps,
                self._agent_worker,
            )

        return execute

    def _heartbeat(
        self,
        job: ScheduledJob,
        worker_id: str,
        fencing_token: int,
        lease_seconds: int,
    ) -> None:
        session = self._session_factory()
        try:
            coordinator = SchedulerCoordinator(ResearchWorkspaceRepository(session))
            coordinator.renew(
                job.job_id,
                worker_id,
                fencing_token=fencing_token,
                lease_seconds=lease_seconds,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("durable scheduler heartbeat transaction failed", job_id=job.job_id)
            raise
        finally:
            session.close()

    def _run_loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception as exc:  # noqa: BLE001 - tick logs and runtime must remain alive
                logger.debug(
                    "durable scheduler cycle recovered after logged failure",
                    error_type=type(exc).__name__,
                )
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.01, self._poll_seconds - elapsed))


_default_runtime: DurableSchedulerRuntime | None = None
_default_runtime_lock = Lock()


def get_default_scheduler_runtime() -> DurableSchedulerRuntime:
    """Return the process-wide durable worker used by all registered domains."""

    global _default_runtime
    if _default_runtime is None:
        with _default_runtime_lock:
            if _default_runtime is None:
                from data_layer.repositories.base import SessionLocal
                from services.runtime_provider_service import (
                    ProductionResearchExecutionAdapters,
                )

                adapters = ProductionResearchExecutionAdapters()
                _default_runtime = DurableSchedulerRuntime(
                    session_factory=SessionLocal,
                    agent_worker=adapters.invoke_agent,
                )
    return _default_runtime
