"""Durable Agent Schedule execution through the bounded Claw runtime path."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from threading import Event, Thread
from typing import Any

from core.contracts.platform_shared import ScheduledJob
from core.contracts.research_workspace import (
    RuntimeProvider,
    RuntimeProviderStatus,
)
from core.observability import get_logger
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.agent_team_service import (
    AgentBudgetError,
    AgentSupervisorContext,
    AgentTeamRun,
    AgentTeamService,
)
from services.runtime_provider_service import (
    ProductionResearchExecutionAdapters,
    RuntimeBlockedError,
    RuntimeFailedError,
    RuntimeProviderService,
)

logger = get_logger(__name__)


class AgentScheduleExecutionService:
    """Execute each persisted schedule job at most once despite ack replay."""

    def __init__(
        self,
        *,
        repository: ResearchWorkspaceRepository,
        runtime_service: RuntimeProviderService,
        provider_invoker: Callable[[RuntimeProvider, dict[str, Any], str], Any],
        agent_worker: Callable[[Any], Any],
        agent_supervisor: Callable[[AgentSupervisorContext], Any],
        clock: Callable[[], datetime] | None = None,
        heartbeat_session_factory: Callable[[], Any] | None = None,
        heartbeat_interval_seconds: float | None = None,
        reservation_seconds: int | None = None,
    ) -> None:
        if heartbeat_interval_seconds is not None and heartbeat_interval_seconds <= 0:
            raise ValueError("heartbeat_interval_seconds must be positive")
        if reservation_seconds is not None and reservation_seconds < 1:
            raise ValueError("reservation_seconds must be positive")
        self._repository = repository
        self._runtime_service = runtime_service
        self._provider_invoker = provider_invoker
        self._agent_worker = agent_worker
        self._agent_supervisor = agent_supervisor
        self._clock = clock or (lambda: datetime.now(UTC))
        self._heartbeat_session_factory = heartbeat_session_factory
        self._heartbeat_interval_seconds = heartbeat_interval_seconds
        self._reservation_seconds = reservation_seconds
        self._team_service = AgentTeamService(repository=repository, clock=self._clock)

    def execute_job(self, job: ScheduledJob) -> AgentTeamRun:
        """Return a stored terminal result on delivery replay without model/tool calls."""

        if job.job_type != "agent_schedule":
            raise ValueError("job is not an Agent Schedule execution")
        schedule_id = str(job.payload.get("schedule_id") or "")
        if not schedule_id:
            raise ValueError("agent schedule job is missing schedule_id")
        replay = self._repository.get_agent_schedule_execution_result(job.job_id)
        if replay is not None:
            return self._replay_terminal(replay)
        schedule = self._repository.get_schedule_row(schedule_id)
        team = self._repository.get_agent_team(schedule.team_id)
        reservation_seconds = self._reservation_seconds or team.budget.deadline_seconds + 5
        execution_id, acquired, first_attempt = self._repository.reserve_agent_schedule_execution(
            job.job_id,
            schedule_id=schedule_id,
            attempt=job.attempt,
            occurred_at=self._clock(),
            reservation_seconds=reservation_seconds,
        )
        self._repository.db.commit()
        if not acquired:
            raise RuntimeBlockedError(
                "Agent Schedule execution is already reserved",
                code="agent_schedule_execution_reserved",
            )
        try:
            initial_steps = list(job.payload.get("steps") or [])
            if not initial_steps:
                initial_steps = [
                    {
                        "role": role,
                        "task": {
                            "schedule_id": schedule_id,
                            "job_id": job.job_id,
                            "execution_id": execution_id,
                        },
                    }
                    for role in team.roles
                    if role != team.supervisor_role
                ]

            def invoke(provider: RuntimeProvider):
                if provider.provider_type == "dsh":
                    return self._provider_invoker(
                        provider,
                        {
                            "run_id": execution_id,
                            "execution_id": execution_id,
                            "job_id": job.job_id,
                            "attempt": job.attempt,
                            "schedule_id": schedule_id,
                            "team_id": team.team_id,
                            "agent_steps": initial_steps,
                        },
                        execution_id,
                    )
                return {"agent_steps": initial_steps}

            routed = self._runtime_service.execute("claw", {"agent_team"}, invoke)
            output = routed.output
            if not isinstance(output, dict):
                raise RuntimeFailedError(
                    "Agent Team provider output must be an object",
                    code="invalid_agent_team_plan",
                )
            routed_steps = output.get("agent_steps", initial_steps)
            if not isinstance(routed_steps, list):
                raise RuntimeFailedError(
                    "Agent Team provider plan must be a list",
                    code="invalid_agent_team_plan",
                )
            team_run = self._team_service.execute_plan(
                team,
                routed_steps,
                self._agent_worker,
                supervisor=self._agent_supervisor,
            )
            terminal = {
                "status": "completed",
                "execution_id": execution_id,
                "job_id": job.job_id,
                "schedule_id": schedule_id,
                "first_attempt": first_attempt,
                "completed_attempt": job.attempt,
                "provider_id": routed.provider_id,
                "provider_result_id": routed.provider_result_id,
                "team_run": team_run.model_dump(mode="json"),
            }
            self._repository.record_agent_schedule_execution_result(
                job.job_id,
                writer_attempt=job.attempt,
                payload=terminal,
                occurred_at=self._clock(),
            )
            self._repository.db.commit()
            logger.info(
                "agent schedule execution completed",
                job_id=job.job_id,
                attempt=job.attempt,
                execution_id=execution_id,
                provider_id=routed.provider_id,
            )
            return team_run
        except Exception as exc:
            self._repository.db.rollback()
            status = (
                "blocked" if isinstance(exc, (RuntimeBlockedError, AgentBudgetError)) else "failed"
            )
            code = getattr(exc, "code", "agent_schedule_execution_failed")
            terminal = {
                "status": status,
                "execution_id": execution_id,
                "job_id": job.job_id,
                "schedule_id": schedule_id,
                "first_attempt": first_attempt,
                "completed_attempt": job.attempt,
                "error_code": code,
            }
            self._repository.record_agent_schedule_execution_result(
                job.job_id,
                writer_attempt=job.attempt,
                payload=terminal,
                occurred_at=self._clock(),
            )
            self._repository.db.commit()
            logger.exception(
                "agent schedule execution reached terminal error",
                job_id=job.job_id,
                attempt=job.attempt,
                error_code=code,
            )
            raise

    def run_once(
        self,
        coordinator,
        schedule_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
    ) -> tuple[ScheduledJob, AgentTeamRun]:
        """Manual worker entry with durable lease and completion acknowledgement."""

        job = coordinator.claim(schedule_id, worker_id, lease_seconds=lease_seconds)
        if job is None:
            raise ValueError("no claimable scheduled job")
        self._repository.db.commit()
        heartbeat_stop = Event()
        heartbeat_failures: list[Exception] = []
        heartbeat_interval = self._heartbeat_interval_seconds or max(0.1, lease_seconds / 3)
        heartbeat_interval = min(heartbeat_interval, lease_seconds * 0.8)

        def heartbeat() -> None:
            while not heartbeat_stop.wait(heartbeat_interval):
                try:
                    self._renew_job_lease(job, worker_id, lease_seconds)
                except Exception as exc:
                    heartbeat_failures.append(exc)
                    heartbeat_stop.set()
                    logger.exception(
                        "manual Agent Schedule heartbeat failed",
                        job_id=job.job_id,
                        attempt=job.attempt,
                        worker_id=worker_id,
                    )
                    return

        heartbeat_thread = Thread(
            target=heartbeat,
            name=f"agent-schedule-heartbeat-{job.job_id}",
            daemon=True,
        )
        heartbeat_thread.start()
        try:
            team_run = self.execute_job(job)
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=max(1.0, heartbeat_interval * 2))
            if heartbeat_failures:
                raise RuntimeBlockedError(
                    "Agent Schedule heartbeat failed before completion",
                    code="scheduler_heartbeat_failed",
                ) from heartbeat_failures[0]
            completed = coordinator.complete(
                job.job_id,
                worker_id,
                fencing_token=job.fencing_token,
                succeeded=True,
            )
            self._repository.db.commit()
            return completed, team_run
        except Exception as exc:
            heartbeat_stop.set()
            heartbeat_thread.join(timeout=max(1.0, heartbeat_interval * 2))
            self._repository.db.rollback()
            if heartbeat_failures:
                raise
            try:
                coordinator.complete(
                    job.job_id,
                    worker_id,
                    fencing_token=job.fencing_token,
                    succeeded=False,
                    error_code=getattr(exc, "code", "agent_schedule_execution_failed"),
                )
                self._repository.db.commit()
            except Exception:
                self._repository.db.rollback()
                logger.exception(
                    "agent schedule failure acknowledgement failed",
                    job_id=job.job_id,
                    attempt=job.attempt,
                )
            raise

    def _renew_job_lease(
        self,
        job: ScheduledJob,
        worker_id: str,
        lease_seconds: int,
    ) -> None:
        if self._heartbeat_session_factory is None:
            raise RuntimeError("heartbeat session factory is unavailable")
        from services.scheduler_coordinator import SchedulerCoordinator

        session = self._heartbeat_session_factory()
        try:
            SchedulerCoordinator(ResearchWorkspaceRepository(session)).renew(
                job.job_id,
                worker_id,
                fencing_token=job.fencing_token,
                lease_seconds=lease_seconds,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    @staticmethod
    def _replay_terminal(payload: dict[str, Any]) -> AgentTeamRun:
        status = payload.get("status")
        if status == "completed":
            return AgentTeamRun.model_validate(payload.get("team_run"))
        code = str(payload.get("error_code") or "agent_schedule_execution_failed")
        if status == "blocked":
            raise RuntimeBlockedError("Stored Agent Schedule execution blocked", code=code)
        raise RuntimeFailedError("Stored Agent Schedule execution failed", code=code)


def build_agent_schedule_execution_service(
    repository: ResearchWorkspaceRepository,
) -> AgentScheduleExecutionService:
    from data_layer.repositories.base import SessionLocal

    adapters = ProductionResearchExecutionAdapters()
    builtin = RuntimeProvider(
        provider_id="builtin-agent-team",
        provider_type="langgraph",
        name="Built-in Agent Team",
        capabilities={"agent_team"},
        status=RuntimeProviderStatus.HEALTHY,
        checked_at=datetime.now(UTC),
    )
    return AgentScheduleExecutionService(
        repository=repository,
        runtime_service=RuntimeProviderService(providers=[builtin], repository=repository),
        provider_invoker=adapters.invoke_provider,
        agent_worker=adapters.invoke_agent,
        agent_supervisor=adapters.invoke_supervisor,
        heartbeat_session_factory=SessionLocal,
    )


def register_default_agent_schedule_runtime(runtime) -> None:
    """Register the production handler; each invocation owns an independent DB session."""

    from data_layer.repositories.base import SessionLocal

    def handle(job: ScheduledJob) -> AgentTeamRun:
        session = SessionLocal()
        try:
            service = build_agent_schedule_execution_service(ResearchWorkspaceRepository(session))
            return service.execute_job(job)
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    runtime.register_handler("agent_schedule", handle)
