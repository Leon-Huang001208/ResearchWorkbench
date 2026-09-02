"""PostgreSQL-only semantics for the merged platform coordination boundary."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from core.settings import settings
from data_layer.repositories.models import ScheduledJobDB
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.database_readiness import probe_postgresql
from services.research_workspace_service import (
    ResearchWorkspaceService,
    WorkspaceScopeError,
)
from services.scheduler_coordinator import SchedulerCoordinator


def _session_factory():
    readiness = probe_postgresql(settings.DATABASE_URL)
    if not readiness.ready:
        pytest.skip(
            "PostgreSQL platform semantics require a migrated database: " f"{readiness.code.value}"
        )
    engine = create_engine(settings.DATABASE_URL)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


@pytest.mark.integration
def test_postgresql_scheduler_skip_locked_takeover_and_fencing():
    """Only one worker owns a row, while an expired lease can be fenced and replaced."""

    engine, sessions = _session_factory()
    suffix = uuid4().hex
    owner = f"integration:scheduler:{suffix}"
    now = datetime.now(UTC)

    try:
        with sessions() as setup:
            coordinator = SchedulerCoordinator(
                ResearchWorkspaceRepository(setup), clock=lambda: now
            )
            coordinator.register_handler("integration.scheduler", lambda _job: None)
            coordinator.enqueue(
                owner=owner,
                job_type="integration.scheduler",
                idempotency_key="single-flight",
                scheduled_for=now,
            )
            setup.commit()

        first = sessions()
        second = sessions()
        try:
            coordinator_a = SchedulerCoordinator(
                ResearchWorkspaceRepository(first), clock=lambda: now
            )
            coordinator_b = SchedulerCoordinator(
                ResearchWorkspaceRepository(second), clock=lambda: now
            )
            for coordinator in (coordinator_a, coordinator_b):
                coordinator.register_handler("integration.scheduler", lambda _job: None)

            claimed_a = coordinator_a.claim_due("worker-a", lease_seconds=30, now=now)
            assert claimed_a is not None
            assert coordinator_b.claim_due("worker-b", lease_seconds=30, now=now) is None
            first.commit()

            takeover_at = now + timedelta(seconds=31)
            claimed_b = coordinator_b.claim_due("worker-b", lease_seconds=30, now=takeover_at)
            assert claimed_b is not None
            assert claimed_b.attempt == claimed_a.attempt + 1
            second.commit()
        finally:
            first.close()
            second.close()

        with sessions() as stale_session:
            stale = SchedulerCoordinator(
                ResearchWorkspaceRepository(stale_session),
                clock=lambda: now + timedelta(seconds=31),
            )
            with pytest.raises(ValueError, match="fencing"):
                stale.complete(
                    claimed_a.job_id,
                    "worker-a",
                    fencing_token=claimed_a.fencing_token,
                    succeeded=True,
                )
            stale_session.rollback()

        with sessions() as winner_session:
            winner = SchedulerCoordinator(
                ResearchWorkspaceRepository(winner_session),
                clock=lambda: now + timedelta(seconds=31),
            )
            completed = winner.complete(
                claimed_b.job_id,
                "worker-b",
                fencing_token=claimed_b.fencing_token,
                succeeded=True,
            )
            assert completed.status.value == "succeeded"
            winner_session.commit()
    finally:
        with sessions() as cleanup:
            cleanup.execute(delete(ScheduledJobDB).where(ScheduledJobDB.owner == owner))
            cleanup.commit()
        engine.dispose()


@pytest.mark.integration
def test_postgresql_workspace_idempotency_and_project_isolation():
    """Workspace retries converge and a different project cannot cross the boundary."""

    engine, sessions = _session_factory()
    suffix = uuid4().hex
    with sessions() as session:
        service = ResearchWorkspaceService(ResearchWorkspaceRepository(session))
        created = service.create_workspace(
            f"project-a-{suffix}", "Integration workspace", f"workspace-{suffix}"
        )
        duplicate = service.create_workspace(
            f"project-a-{suffix}", "Integration workspace", f"workspace-{suffix}"
        )

        assert duplicate.workspace_id == created.workspace_id
        with pytest.raises(WorkspaceScopeError, match="does not belong"):
            service.get_workspace_scoped(created.workspace_id, f"project-b-{suffix}")

        # Keep this integration test side-effect free for developer databases.
        session.rollback()
    engine.dispose()
