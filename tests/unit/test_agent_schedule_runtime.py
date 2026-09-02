"""Production Agent Schedule execution tests."""

import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.contracts.research_workspace import (
    AgentBudget,
    AgentSchedule,
    AgentTeamDefinition,
    RuntimeProvider,
    RuntimeProviderStatus,
)
from data_layer.repositories.base import Base
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.agent_schedule_runtime import AgentScheduleExecutionService
from services.agent_team_service import AgentSupervisorResult, AgentWorkerResult
from services.runtime_provider_service import (
    RuntimeBlockedError,
    RuntimeProviderService,
)
from services.scheduler_coordinator import SchedulerCoordinator

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _seed_claimed_job(repository: ResearchWorkspaceRepository):
    repository.save_agent_team(
        AgentTeamDefinition(
            team_id="team-1",
            name="Scheduled team",
            supervisor_role="supervisor",
            roles=["supervisor", "analyst"],
            budget=AgentBudget(
                max_steps=3,
                max_concurrency=1,
                max_tokens=100,
                max_cost=1,
                deadline_seconds=60,
            ),
            status="active",
        )
    )
    repository.save_agent_schedule(
        AgentSchedule(
            schedule_id="schedule-1",
            team_id="team-1",
            cron_expression="0 9 * * 1-5",
            status="active",
            next_run_at=NOW,
        )
    )
    coordinator = SchedulerCoordinator(repository, clock=lambda: NOW)
    coordinator.trigger(
        "schedule-1",
        idempotency_key="scheduled-1",
        payload={"steps": [{"role": "analyst", "task": {"topic": "gold"}}]},
    )
    return coordinator.claim("schedule-1", "worker-a", lease_seconds=60)


class TrackingRuntimeProviderService(RuntimeProviderService):
    def __init__(self):
        super().__init__(
            providers=[
                RuntimeProvider(
                    provider_id="builtin-agent-team",
                    provider_type="langgraph",
                    name="Built-in Agent Team",
                    capabilities={"agent_team"},
                    status=RuntimeProviderStatus.HEALTHY,
                    checked_at=NOW,
                )
            ]
        )
        self.calls = 0

    def execute(self, *args, **kwargs):
        self.calls += 1
        return super().execute(*args, **kwargs)


def test_agent_schedule_routes_through_runtime_and_dynamic_supervisor_once(db_session):
    repository = ResearchWorkspaceRepository(db_session)
    job = _seed_claimed_job(repository)
    assert job is not None
    runtime_service = TrackingRuntimeProviderService()
    supervisor_calls = []
    worker_snapshots = []

    def supervisor(context):
        supervisor_calls.append(context)
        results = [item for item in context.blackboard_snapshot if item.entry_type == "result"]
        if len(results) == 0:
            return AgentSupervisorResult(
                action="assign",
                assignments=[{"role": "analyst", "task": {"step": "first"}}],
                tokens_used=1,
                cost_used=0.01,
            )
        if len(results) == 1:
            return AgentSupervisorResult(
                action="assign",
                assignments=[{"role": "analyst", "task": {"step": "follow-up"}}],
                tokens_used=1,
                cost_used=0.01,
            )
        return AgentSupervisorResult(
            action="complete",
            tokens_used=1,
            cost_used=0.01,
        )

    def worker(assignment):
        worker_snapshots.append(assignment.blackboard_snapshot)
        return AgentWorkerResult(
            payload={"answer": assignment.task["step"]},
            tokens_used=1,
            cost_used=0.01,
        )

    service = AgentScheduleExecutionService(
        repository=repository,
        runtime_service=runtime_service,
        provider_invoker=lambda *_args: None,
        agent_worker=worker,
        agent_supervisor=supervisor,
        clock=lambda: NOW,
    )

    first = service.execute_job(job)
    replay = service.execute_job(job.model_copy(update={"attempt": 2, "fencing_token": 2}))

    assert runtime_service.calls == 1
    assert len(supervisor_calls) == 3
    assert len(worker_snapshots) == 2
    assert worker_snapshots[1][-1].payload == {"answer": "first"}
    assert replay == first
    assert replay.steps_used == 2
    ledger = repository.get_agent_schedule_execution_result(job.job_id)
    assert ledger is not None
    assert ledger["first_attempt"] == 1
    assert ledger["completed_attempt"] == 1


def _single_step_supervisor(context):
    results = [item for item in context.blackboard_snapshot if item.entry_type == "result"]
    if results:
        return AgentSupervisorResult(
            action="complete",
            tokens_used=1,
            cost_used=0.01,
        )
    return AgentSupervisorResult(
        action="assign",
        assignments=[{"role": "analyst", "task": {"step": "slow"}}],
        tokens_used=1,
        cost_used=0.01,
    )


def _file_database(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'agent-schedule.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return engine, factory


def _queue_schedule(repository, *, moment):
    repository.save_agent_team(
        AgentTeamDefinition(
            team_id="team-heartbeat",
            name="Heartbeat team",
            supervisor_role="supervisor",
            roles=["supervisor", "analyst"],
            budget=AgentBudget(
                max_steps=1,
                max_concurrency=1,
                max_tokens=100,
                max_cost=1,
                deadline_seconds=5,
            ),
            status="active",
        )
    )
    repository.save_agent_schedule(
        AgentSchedule(
            schedule_id="schedule-heartbeat",
            team_id="team-heartbeat",
            cron_expression="* * * * *",
            status="active",
            next_run_at=moment,
        )
    )
    coordinator = SchedulerCoordinator(repository, clock=lambda: datetime.now(UTC))
    coordinator.trigger("schedule-heartbeat", idempotency_key="heartbeat-job")
    repository.db.commit()
    return coordinator


def test_manual_work_heartbeats_during_long_execution(tmp_path):
    engine, session_factory = _file_database(tmp_path)
    session = session_factory()
    try:
        repository = ResearchWorkspaceRepository(session)
        coordinator = _queue_schedule(repository, moment=datetime.now(UTC))
        calls = []

        def slow_worker(_assignment):
            calls.append("worker")
            time.sleep(1.2)
            return AgentWorkerResult(payload={"answer": "done"}, tokens_used=1, cost_used=0.01)

        service = AgentScheduleExecutionService(
            repository=repository,
            runtime_service=TrackingRuntimeProviderService(),
            provider_invoker=lambda *_args: None,
            agent_worker=slow_worker,
            agent_supervisor=_single_step_supervisor,
            heartbeat_session_factory=session_factory,
            heartbeat_interval_seconds=0.1,
        )

        completed, team_run = service.run_once(
            coordinator,
            "schedule-heartbeat",
            "manual-worker",
            lease_seconds=1,
        )

        assert calls == ["worker"]
        assert team_run.status == "completed"
        assert completed.status.value == "succeeded"
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_manual_work_heartbeat_failure_rejects_stale_completion(tmp_path):
    engine, session_factory = _file_database(tmp_path)
    session = session_factory()
    try:
        repository = ResearchWorkspaceRepository(session)
        coordinator = _queue_schedule(repository, moment=datetime.now(UTC))
        worker_calls = []

        def slow_worker(_assignment):
            worker_calls.append("worker")
            time.sleep(1.2)
            return AgentWorkerResult(payload={"answer": "done"}, tokens_used=1, cost_used=0.01)

        service = AgentScheduleExecutionService(
            repository=repository,
            runtime_service=TrackingRuntimeProviderService(),
            provider_invoker=lambda *_args: None,
            agent_worker=slow_worker,
            agent_supervisor=_single_step_supervisor,
            heartbeat_session_factory=session_factory,
            heartbeat_interval_seconds=0.1,
        )

        def fail_heartbeat(*_args, **_kwargs):
            raise RuntimeError("heartbeat storage unavailable")

        service._renew_job_lease = fail_heartbeat
        with pytest.raises(RuntimeBlockedError) as raised:
            service.run_once(
                coordinator,
                "schedule-heartbeat",
                "stale-worker",
                lease_seconds=1,
            )
        assert raised.value.code == "scheduler_heartbeat_failed"

        session.expire_all()
        takeover = coordinator.claim(
            "schedule-heartbeat",
            "replacement-worker",
            lease_seconds=1,
            now=datetime.now(UTC),
        )
        assert takeover is not None
        assert takeover.attempt == 2
        assert worker_calls == ["worker"]
        replay = service.execute_job(takeover)
        assert replay.status == "completed"
        assert worker_calls == ["worker"]
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_expired_reservation_can_recover_after_process_crash(db_session):
    current = [NOW]
    repository = ResearchWorkspaceRepository(db_session)
    repository.save_agent_team(
        AgentTeamDefinition(
            team_id="team-recovery",
            name="Recovery team",
            supervisor_role="supervisor",
            roles=["supervisor", "analyst"],
            budget=AgentBudget(
                max_steps=1,
                max_concurrency=1,
                max_tokens=100,
                max_cost=1,
                deadline_seconds=1,
            ),
            status="active",
        )
    )
    repository.save_agent_schedule(
        AgentSchedule(
            schedule_id="schedule-recovery",
            team_id="team-recovery",
            cron_expression="* * * * *",
            status="active",
            next_run_at=NOW,
        )
    )
    coordinator = SchedulerCoordinator(repository, clock=lambda: current[0])
    coordinator.trigger("schedule-recovery", idempotency_key="crash-job")
    first = coordinator.claim("schedule-recovery", "crashed-worker", lease_seconds=1)
    assert first is not None
    repository.reserve_agent_schedule_execution(
        first.job_id,
        schedule_id="schedule-recovery",
        attempt=first.attempt,
        occurred_at=current[0],
        reservation_seconds=1,
    )
    db_session.commit()

    current[0] = NOW + timedelta(seconds=61)
    takeover = coordinator.claim(
        "schedule-recovery",
        "replacement-worker",
        lease_seconds=1,
        now=current[0],
    )
    assert takeover is not None
    runtime_service = TrackingRuntimeProviderService()
    service = AgentScheduleExecutionService(
        repository=repository,
        runtime_service=runtime_service,
        provider_invoker=lambda *_args: None,
        agent_worker=lambda _assignment: AgentWorkerResult(
            payload={"answer": "recovered"}, tokens_used=1, cost_used=0.01
        ),
        agent_supervisor=_single_step_supervisor,
        reservation_seconds=1,
        clock=lambda: current[0],
    )

    recovered = service.execute_job(takeover)

    assert recovered.status == "completed"
    assert runtime_service.calls == 1
    ledger = repository.get_agent_schedule_execution_result(takeover.job_id)
    assert ledger is not None
    assert ledger["first_attempt"] == 1
    assert ledger["completed_attempt"] == 2


def test_active_reservation_blocks_concurrent_model_execution(db_session):
    repository = ResearchWorkspaceRepository(db_session)
    job = _seed_claimed_job(repository)
    assert job is not None
    repository.reserve_agent_schedule_execution(
        job.job_id,
        schedule_id="schedule-1",
        attempt=job.attempt,
        occurred_at=NOW,
        reservation_seconds=60,
    )
    db_session.commit()
    runtime_service = TrackingRuntimeProviderService()
    service = AgentScheduleExecutionService(
        repository=repository,
        runtime_service=runtime_service,
        provider_invoker=lambda *_args: None,
        agent_worker=lambda _assignment: (_ for _ in ()).throw(
            AssertionError("worker must not run")
        ),
        agent_supervisor=_single_step_supervisor,
        clock=lambda: NOW,
    )

    with pytest.raises(RuntimeBlockedError) as raised:
        service.execute_job(job)

    assert raised.value.code == "agent_schedule_execution_reserved"
    assert runtime_service.calls == 0


def test_stale_attempt_cannot_write_terminal_after_reservation_takeover(db_session):
    current = [NOW]
    repository = ResearchWorkspaceRepository(db_session)
    first = _seed_claimed_job(repository)
    assert first is not None
    repository.reserve_agent_schedule_execution(
        first.job_id,
        schedule_id="schedule-1",
        attempt=first.attempt,
        occurred_at=current[0],
        reservation_seconds=1,
    )
    db_session.commit()
    current[0] = NOW + timedelta(seconds=61)
    coordinator = SchedulerCoordinator(repository, clock=lambda: current[0])
    takeover = coordinator.claim(
        "schedule-1",
        "replacement-worker",
        lease_seconds=1,
        now=current[0],
    )
    assert takeover is not None
    repository.reserve_agent_schedule_execution(
        takeover.job_id,
        schedule_id="schedule-1",
        attempt=takeover.attempt,
        occurred_at=current[0],
        reservation_seconds=1,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="stale execution attempt"):
        repository.record_agent_schedule_execution_result(
            first.job_id,
            writer_attempt=first.attempt,
            payload={
                "status": "completed",
                "execution_id": f"agent-schedule-execution:{first.job_id}",
                "first_attempt": first.attempt,
                "completed_attempt": first.attempt,
                "team_run": {
                    "status": "completed",
                    "steps_used": 0,
                    "tokens_used": 0,
                    "cost_used": 0,
                    "blackboard": [],
                },
            },
            occurred_at=current[0],
        )

    assert repository.get_agent_schedule_execution_result(first.job_id) is None


def test_expired_reservation_rejects_same_attempt_takeover(db_session):
    repository = ResearchWorkspaceRepository(db_session)
    job = _seed_claimed_job(repository)
    assert job is not None
    repository.reserve_agent_schedule_execution(
        job.job_id,
        schedule_id="schedule-1",
        attempt=job.attempt,
        occurred_at=NOW,
        reservation_seconds=1,
    )
    db_session.commit()

    with pytest.raises(ValueError, match="newer fencing attempt"):
        repository.reserve_agent_schedule_execution(
            job.job_id,
            schedule_id="schedule-1",
            attempt=job.attempt,
            occurred_at=NOW.replace(second=2),
            reservation_seconds=1,
        )
