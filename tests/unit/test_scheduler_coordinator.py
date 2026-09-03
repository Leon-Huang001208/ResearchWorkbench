"""PostgreSQL-compatible scheduler lease behavior tests."""

import time
from datetime import UTC, datetime, timedelta
from threading import Event, Thread

import pytest

from core.contracts.research_workspace import (
    AgentBudget,
    AgentSchedule,
    AgentTeamDefinition,
)
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.agent_team_service import AgentTeamService
from services.scheduler_coordinator import DurableSchedulerRuntime, SchedulerCoordinator

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


def _coordinator(db_session) -> SchedulerCoordinator:
    repository = ResearchWorkspaceRepository(db_session)
    repository.save_agent_team(
        AgentTeamDefinition(
            team_id="team-1",
            name="Team",
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
    return SchedulerCoordinator(repository, clock=lambda: NOW)


def test_schedule_coalesces_missed_runs_to_latest(db_session):
    coordinator = _coordinator(db_session)
    first = coordinator.record_missed("schedule-1", NOW - timedelta(minutes=3), count=3)
    second = coordinator.record_missed("schedule-1", NOW, count=2)
    assert first.job_id == second.job_id
    assert coordinator.pending_runs("schedule-1") == 1
    assert second.scheduled_for == NOW


def test_schedule_is_single_flight_and_expired_lease_can_be_taken_over(db_session):
    coordinator = _coordinator(db_session)
    coordinator.record_missed("schedule-1", NOW, count=1)
    claimed = coordinator.claim("schedule-1", "worker-a", lease_seconds=30)
    assert claimed is not None
    assert coordinator.claim("schedule-1", "worker-b", lease_seconds=30) is None

    takeover = coordinator.claim(
        "schedule-1",
        "worker-b",
        lease_seconds=30,
        now=NOW + timedelta(seconds=31),
    )
    assert takeover is not None
    assert takeover.lease_owner == "worker-b"
    assert takeover.attempt == 2


def test_manual_trigger_is_idempotent_and_completion_clears_lease(db_session):
    coordinator = _coordinator(db_session)
    first = coordinator.trigger("schedule-1", idempotency_key="manual-1")
    duplicate = coordinator.trigger("schedule-1", idempotency_key="manual-1")
    assert duplicate.job_id == first.job_id
    claimed = coordinator.claim("schedule-1", "worker-a", lease_seconds=30)
    completed = coordinator.complete(
        claimed.job_id, "worker-a", fencing_token=claimed.attempt, succeeded=True
    )
    assert completed.status.value == "succeeded"
    assert completed.lease_owner is None


def test_missed_runs_during_execution_create_one_latest_follow_up(db_session):
    coordinator = _coordinator(db_session)
    current = coordinator.trigger("schedule-1", idempotency_key="current")
    claimed = coordinator.claim("schedule-1", "worker-a", lease_seconds=30)
    latest_for = NOW + timedelta(minutes=5)
    coordinator.record_missed("schedule-1", latest_for, count=4)

    coordinator.complete(claimed.job_id, "worker-a", fencing_token=claimed.attempt, succeeded=True)

    assert coordinator.pending_runs("schedule-1") == 1
    follow_up = coordinator.claim("schedule-1", "worker-b", lease_seconds=30, now=latest_for)
    assert follow_up is not None
    assert follow_up.job_id != current.job_id
    assert follow_up.scheduled_for == latest_for


def test_trigger_idempotency_survives_completion(db_session):
    coordinator = _coordinator(db_session)
    first = coordinator.trigger("schedule-1", idempotency_key="durable-key")
    aliased = coordinator.trigger("schedule-1", idempotency_key="coalesced-key")
    assert aliased.job_id == first.job_id
    claimed = coordinator.claim("schedule-1", "worker-a", lease_seconds=30)
    coordinator.complete(claimed.job_id, "worker-a", fencing_token=claimed.attempt, succeeded=True)

    duplicate = coordinator.trigger("schedule-1", idempotency_key="durable-key")
    duplicate_alias = coordinator.trigger("schedule-1", idempotency_key="coalesced-key")
    assert duplicate.job_id == first.job_id
    assert duplicate_alias.job_id == first.job_id
    assert coordinator.pending_runs("schedule-1") == 0


def test_trigger_idempotency_rejects_changed_request_payload(db_session):
    coordinator = _coordinator(db_session)
    coordinator.trigger(
        "schedule-1",
        idempotency_key="same-key",
        payload={"steps": [{"role": "analyst", "task": {"version": 1}}]},
    )
    with pytest.raises(ValueError, match="idempotency"):
        coordinator.trigger(
            "schedule-1",
            idempotency_key="same-key",
            payload={"steps": [{"role": "analyst", "task": {"version": 2}}]},
        )


def test_stale_fencing_token_cannot_renew_or_complete_after_takeover(db_session):
    coordinator = _coordinator(db_session)
    coordinator.trigger("schedule-1", idempotency_key="fenced")
    first = coordinator.claim("schedule-1", "worker-a", lease_seconds=30)
    second = coordinator.claim(
        "schedule-1", "worker-b", lease_seconds=30, now=NOW + timedelta(seconds=31)
    )
    assert second.attempt > first.attempt

    with pytest.raises(ValueError, match="fencing"):
        coordinator.renew(
            first.job_id,
            "worker-a",
            fencing_token=first.attempt,
            lease_seconds=30,
            now=NOW + timedelta(seconds=32),
        )
    with pytest.raises(ValueError, match="fencing"):
        coordinator.complete(
            first.job_id,
            "worker-a",
            fencing_token=first.attempt,
            succeeded=True,
        )


def test_coalescing_keeps_max_scheduled_for_and_worker_executes_team(db_session):
    coordinator = _coordinator(db_session)
    later = NOW + timedelta(minutes=10)
    coordinator.record_missed("schedule-1", later, count=1)
    coalesced = coordinator.record_missed("schedule-1", NOW + timedelta(minutes=2), count=1)
    assert coalesced.scheduled_for == later

    completed, team_run = coordinator.run_once(
        "schedule-1",
        "worker-a",
        lease_seconds=30,
        team_service=AgentTeamService(clock=lambda: NOW),
        worker=lambda assignment: {
            "payload": {"role": assignment.role},
            "tokens_used": 1,
            "cost_used": 0,
        },
    )
    assert completed.status.value == "succeeded"
    assert team_run.status == "completed"


def test_generic_registered_handler_consumes_market_close_snapshot_job(db_session):
    coordinator = _coordinator(db_session)
    handled: list[tuple[str, str]] = []
    coordinator.register_handler(
        "market_home.close_snapshot",
        lambda job: handled.append((job.job_type, job.payload["trading_day"])),
    )
    queued = coordinator.enqueue(
        owner="market_home:close",
        job_type="market_home.close_snapshot",
        idempotency_key="2026-09-01",
        scheduled_for=NOW,
        payload={"trading_day": "2026-09-01"},
    )

    completed = coordinator.run_due("generic-worker", lease_seconds=30, limit=1)

    assert [job.job_id for job in completed] == [queued.job_id]
    assert completed[0].status.value == "succeeded"
    assert handled == [("market_home.close_snapshot", "2026-09-01")]


@pytest.mark.parametrize(
    "job_type",
    ["asset_alert.evaluate", "market_home.close_snapshot"],
)
def test_failed_domain_job_retries_with_backoff_and_preserves_attempt_error(
    db_session,
    job_type: str,
):
    current = [NOW]
    failures = [RuntimeError("temporary one"), RuntimeError("temporary two")]

    def flaky_handler(_job):
        if failures:
            raise failures.pop(0)

    coordinator = SchedulerCoordinator(
        ResearchWorkspaceRepository(db_session),
        clock=lambda: current[0],
        handlers={job_type: flaky_handler},
    )
    queued = coordinator.enqueue(
        owner=f"retry:{job_type}",
        job_type=job_type,
        idempotency_key="retry-same-job",
        scheduled_for=NOW,
    )

    first = coordinator.run_due("worker", lease_seconds=30, claim_now=current[0])[0]

    assert first.job_id == queued.job_id
    assert first.status.value == "idle"
    assert first.attempt == 1
    assert first.last_error_code == "handler_failed"
    assert first.scheduled_for == NOW + timedelta(seconds=5)
    assert coordinator.claim_due("worker", lease_seconds=30, now=NOW) is None
    duplicate = coordinator.enqueue(
        owner=f"retry:{job_type}",
        job_type=job_type,
        idempotency_key="retry-same-job",
        scheduled_for=NOW,
    )
    assert duplicate.job_id == queued.job_id
    assert duplicate.last_error_code == "handler_failed"

    current[0] = NOW + timedelta(seconds=5)
    second = coordinator.run_due("worker", lease_seconds=30, claim_now=current[0])[0]
    assert second.status.value == "idle"
    assert second.attempt == 2
    assert second.last_error_code == "handler_failed"
    assert second.scheduled_for == NOW + timedelta(seconds=15)

    current[0] = NOW + timedelta(seconds=15)
    succeeded = coordinator.run_due("worker", lease_seconds=30, claim_now=current[0])[0]
    assert succeeded.status.value == "succeeded"
    assert succeeded.attempt == 3
    assert succeeded.last_error_code is None


def test_failed_job_becomes_terminal_after_retry_budget(db_session):
    current = [NOW]
    coordinator = SchedulerCoordinator(
        ResearchWorkspaceRepository(db_session),
        clock=lambda: current[0],
        handlers={"asset_alert.evaluate": lambda _job: (_ for _ in ()).throw(RuntimeError())},
        max_attempts=2,
    )
    coordinator.enqueue(
        owner="asset_alert:terminal",
        job_type="asset_alert.evaluate",
        idempotency_key="terminal-retry",
        scheduled_for=NOW,
    )

    first = coordinator.run_due("worker", lease_seconds=30, claim_now=current[0])[0]
    current[0] = first.scheduled_for
    terminal = coordinator.run_due("worker", lease_seconds=30, claim_now=current[0])[0]

    assert terminal.status.value == "failed"
    assert terminal.attempt == 2
    assert terminal.last_error_code == "handler_failed"
    assert (
        coordinator.claim_due(
            "worker",
            lease_seconds=30,
            now=current[0] + timedelta(days=1),
        )
        is None
    )


def test_postgresql_lock_sql_uses_run_row_lock_and_due_skip_locked():
    from sqlalchemy.dialects import postgresql

    run_sql = str(
        ResearchWorkspaceRepository.run_lock_statement("run-1").compile(
            dialect=postgresql.dialect()
        )
    )
    due_sql = str(
        ResearchWorkspaceRepository.due_job_lock_statement(
            job_types={"agent_schedule", "market_home.close_snapshot"},
            now=NOW,
        ).compile(dialect=postgresql.dialect())
    )
    assert "FOR UPDATE" in run_sql
    assert "FOR UPDATE SKIP LOCKED" in due_sql


def test_due_schedule_is_materialized_once_and_cron_advances_deterministically(db_session):
    coordinator = _coordinator(db_session)

    materialized = coordinator.materialize_due_schedules(now=NOW)
    duplicate = coordinator.materialize_due_schedules(now=NOW)

    assert len(materialized) == 1
    assert duplicate == []
    schedule = coordinator.repository.get_schedule_row("schedule-1")
    assert coordinator._aware(schedule.next_run_at) == datetime(2026, 9, 2, 9, 0, tzinfo=UTC)
    assert materialized[0].scheduled_for == NOW


def test_due_schedule_coalesces_all_missed_cron_occurrences_to_latest(db_session):
    coordinator = _coordinator(db_session)
    schedule = coordinator.repository.get_schedule_row("schedule-1")
    schedule.next_run_at = datetime(2026, 8, 28, 9, 0, tzinfo=UTC)
    coordinator.repository.db.flush()

    materialized = coordinator.materialize_due_schedules(now=NOW)

    assert len(materialized) == 1
    assert materialized[0].scheduled_for == NOW
    assert materialized[0].payload["missed_count"] == 3
    assert coordinator._aware(schedule.next_run_at) == datetime(2026, 9, 2, 9, 0, tzinfo=UTC)


def test_run_due_heartbeats_lease_while_handler_is_executing(db_session):
    coordinator = _coordinator(db_session)
    heartbeat_seen = Event()
    release_handler = Event()

    def handler(_job):
        assert release_handler.wait(timeout=1)

    def heartbeat(_job, _worker_id, _token, _lease_seconds):
        heartbeat_seen.set()
        release_handler.set()

    coordinator.register_handler("heartbeat.job", handler)
    coordinator.enqueue(
        owner="heartbeat:test",
        job_type="heartbeat.job",
        idempotency_key="heartbeat-1",
        scheduled_for=NOW,
    )

    completed = coordinator.run_due(
        "heartbeat-worker",
        lease_seconds=30,
        heartbeat_callback=heartbeat,
        heartbeat_interval_seconds=0.01,
    )

    assert heartbeat_seen.is_set()
    assert completed[0].status.value == "succeeded"


def test_production_agent_schedule_runtime_materializes_and_executes_due_team(db_session):
    from sqlalchemy.orm import sessionmaker

    from services.runtime_provider_service import ProductionResearchExecutionAdapters

    class GatewayResponse:
        content = '{"summary":"scheduled analysis completed"}'
        tokens_used = 7

    class Gateway:
        def __init__(self):
            self.calls: list[dict] = []

        def chat(self, **kwargs):
            self.calls.append(kwargs)
            return GatewayResponse()

    _coordinator(db_session)
    db_session.commit()
    gateway = Gateway()
    session_factory = sessionmaker(bind=db_session.get_bind())
    runtime = DurableSchedulerRuntime(
        session_factory=session_factory,
        worker_id="production-agent-worker",
        agent_worker=ProductionResearchExecutionAdapters(model_gateway=gateway).invoke_agent,
        clock=lambda: NOW,
    )

    completed = runtime.tick(now=NOW)

    assert len(completed) == 1
    assert completed[0].status.value == "succeeded"
    assert gateway.calls[0]["max_tokens"] == 100
    assert 0 < gateway.calls[0]["timeout"] <= 60


def test_api_startup_uses_one_process_wide_durable_scheduler_runtime(monkeypatch):
    from app.api import main
    from services import scheduler_coordinator

    calls: list[str] = []

    class Runtime:
        def register_materializer(self, name, _callback):
            calls.append(f"materializer:{name}")

        def register_handler(self, job_type, _callback):
            calls.append(f"handler:{job_type}")

        def start(self):
            calls.append("start")

        def stop(self):
            calls.append("stop")

    runtime = Runtime()
    monkeypatch.setattr(
        scheduler_coordinator,
        "get_default_scheduler_runtime",
        lambda: runtime,
    )
    monkeypatch.setattr(main, "_durable_scheduler_runtime", None)

    main._start_durable_scheduler_runtime()
    main._start_durable_scheduler_runtime()
    main._stop_durable_scheduler_runtime()

    assert calls == [
        "handler:datahub.ingest",
        "materializer:market-home-close",
        "handler:market_home.close_snapshot",
        "materializer:asset-alert-evaluation",
        "handler:asset_alert.evaluate",
        "handler:agent_schedule",
        "start",
        "start",
        "stop",
    ]


def test_agent_schedule_api_uses_production_runtime_and_supervisor(db_session):
    from app.api.routes.agent_schedules import get_schedule_dependencies
    from services.agent_schedule_runtime import AgentScheduleExecutionService

    _, _, execution_service = get_schedule_dependencies(db_session)

    assert isinstance(execution_service, AgentScheduleExecutionService)
    assert execution_service._agent_supervisor is not None


def test_runtime_materializers_are_idempotent_and_run_before_claim(db_session):
    from sqlalchemy.orm import sessionmaker

    repository = ResearchWorkspaceRepository(db_session)
    coordinator = SchedulerCoordinator(repository, clock=lambda: NOW)
    coordinator.enqueue(
        owner="market_home:close",
        job_type="market_home.close_snapshot",
        idempotency_key="close:2026-09-01",
        scheduled_for=NOW,
    )
    db_session.commit()
    events: list[tuple[str, datetime | None]] = []

    def materialize(moment: datetime):
        events.append(("materialize", moment))

    def handle(job):
        events.append(("handle", job.scheduled_for))

    runtime = DurableSchedulerRuntime(
        session_factory=sessionmaker(bind=db_session.get_bind()),
        worker_id="shared-worker",
        clock=lambda: NOW,
    )
    runtime.register_materializer("market-home", materialize)
    runtime.register_materializer("market-home", materialize)
    runtime.register_handler("market_home.close_snapshot", handle)

    completed = runtime.tick(now=NOW)

    assert [event[0] for event in events] == ["materialize", "handle"]
    assert events[0][1] == NOW
    assert completed[0].status.value == "succeeded"
    with pytest.raises(ValueError, match="materializer already registered"):
        runtime.register_materializer("market-home", lambda _moment: None)


def test_materializer_failure_rolls_back_tick_and_skips_claim(db_session):
    from sqlalchemy.orm import sessionmaker

    repository = ResearchWorkspaceRepository(db_session)
    coordinator = SchedulerCoordinator(repository, clock=lambda: NOW)
    job = coordinator.enqueue(
        owner="asset-alert:evaluate",
        job_type="asset_alert.evaluate",
        idempotency_key="evaluate:2026-09-01T09:00:00Z",
        scheduled_for=NOW,
    )
    db_session.commit()
    handled: list[str] = []
    runtime = DurableSchedulerRuntime(
        session_factory=sessionmaker(bind=db_session.get_bind()),
        worker_id="shared-worker",
        clock=lambda: NOW,
    )

    def fail_materialization(_moment: datetime):
        raise RuntimeError("materialization failed")

    runtime.register_materializer("asset-alert", fail_materialization)
    runtime.register_handler("asset_alert.evaluate", lambda item: handled.append(item.job_id))

    with pytest.raises(RuntimeError, match="materialization failed"):
        runtime.tick(now=NOW)

    db_session.expire_all()
    persisted = repository.get_job(job.job_id)
    assert handled == []
    assert persisted.status == "idle"
    assert persisted.attempt == 0


def test_runtime_start_is_atomic_under_concurrent_callers():
    constructed: list[str] = []

    class FakeWorkerThread:
        def __init__(self, *, target, name: str, daemon: bool) -> None:
            constructed.append(name)
            self._alive = False

        def start(self) -> None:
            time.sleep(0.01)
            self._alive = True

        def is_alive(self) -> bool:
            return self._alive

        def join(self, timeout: float | None = None) -> None:
            self._alive = False

    runtime = DurableSchedulerRuntime(
        session_factory=lambda: None,
        thread_factory=FakeWorkerThread,
    )
    callers = [Thread(target=runtime.start) for _ in range(8)]

    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join()

    assert constructed == ["durable-scheduler-runtime"]
    runtime.stop()


def test_default_runtime_initialization_is_atomic(monkeypatch):
    from services import runtime_provider_service, scheduler_coordinator

    constructed: list[object] = []

    def build_runtime(**_kwargs):
        time.sleep(0.01)
        runtime = object()
        constructed.append(runtime)
        return runtime

    monkeypatch.setattr(scheduler_coordinator, "_default_runtime", None)
    monkeypatch.setattr(scheduler_coordinator, "DurableSchedulerRuntime", build_runtime)
    monkeypatch.setattr(
        runtime_provider_service,
        "ProductionResearchExecutionAdapters",
        lambda: type("Adapters", (), {"invoke_agent": None})(),
    )
    returned: list[object] = []
    callers = [
        Thread(
            target=lambda: returned.append(scheduler_coordinator.get_default_scheduler_runtime())
        )
        for _ in range(8)
    ]

    for caller in callers:
        caller.start()
    for caller in callers:
        caller.join()

    assert len(constructed) == 1
    assert returned == [constructed[0]] * 8


def test_runtime_rejects_stale_completion_after_heartbeat_failure_and_allows_takeover(
    db_session,
):
    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(bind=db_session.get_bind())
    repository = ResearchWorkspaceRepository(db_session)
    coordinator = SchedulerCoordinator(repository, clock=lambda: NOW)
    queued = coordinator.enqueue(
        owner="runtime:fencing",
        job_type="runtime.fencing",
        idempotency_key="runtime-fencing-1",
        scheduled_for=NOW,
    )
    db_session.commit()
    current = [NOW]
    heartbeat_failed = Event()

    def slow_handler(_job):
        assert heartbeat_failed.wait(timeout=2)

    runtime = DurableSchedulerRuntime(
        session_factory=session_factory,
        worker_id="stale-worker",
        lease_seconds=1,
        clock=lambda: current[0],
    )
    runtime.register_handler("runtime.fencing", slow_handler)

    def fail_heartbeat(_job, _worker_id, _token, _lease_seconds):
        current[0] = NOW + timedelta(seconds=2)
        heartbeat_failed.set()
        raise RuntimeError("heartbeat storage unavailable")

    runtime._heartbeat = fail_heartbeat

    with pytest.raises(ValueError, match="fencing token or lease"):
        runtime.tick(now=NOW)

    takeover_session = session_factory()
    try:
        takeover = SchedulerCoordinator(
            ResearchWorkspaceRepository(takeover_session),
            handlers={"runtime.fencing": lambda _job: None},
            clock=lambda: current[0],
        ).claim_due("replacement-worker", lease_seconds=30, now=current[0])
        assert takeover is not None
        assert takeover.job_id == queued.job_id
        assert takeover.attempt == 2
    finally:
        takeover_session.rollback()
        takeover_session.close()
