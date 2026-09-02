"""HTTP and durable SSE contracts for the merged research runtime."""

from datetime import UTC, datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import (
    research_runs,
    research_sessions,
    research_workspaces,
    runtime_providers,
)
from data_layer.repositories.base import Base
from data_layer.repositories.base import get_db as production_get_db
from data_layer.repositories.research_run_repository import ResearchRunRepository
from data_layer.repositories.research_workspace_repository import (
    ResearchWorkspaceRepository,
)
from services.research_workspace_service import ResearchWorkspaceService
from services.runtime_provider_service import RuntimeFailedError

NOW = datetime(2026, 9, 1, 9, 0, tzinfo=UTC)


class _FailedRunView:
    def model_dump(self, *, mode: str):
        assert mode == "json"
        return {"run_id": "run-provider-failed", "status": "failed"}


class _FailedRunService:
    def execute(self, *_args, **_kwargs):
        raise RuntimeFailedError("provider failed", code="provider_crashed")

    def get(self, *_args, **_kwargs):
        return _FailedRunView()


class _FailedOrchestrationService:
    run_service = _FailedRunService()

    def execute_session_run(self, *_args, **_kwargs):
        raise RuntimeFailedError("provider failed", code="provider_crashed")


def test_execute_routes_preserve_typed_provider_failure_code_in_terminal_response():
    app = FastAPI()
    app.include_router(research_runs.router)
    app.include_router(research_sessions.router)
    failed_run_service = _FailedRunService()
    app.dependency_overrides[research_runs.get_research_run_service] = lambda: failed_run_service
    app.dependency_overrides[research_sessions.get_research_orchestration_service] = (
        lambda: _FailedOrchestrationService()
    )
    client = TestClient(app)

    direct = client.post(
        "/api/research-runs/run-provider-failed/execute",
        headers={"Idempotency-Key": "failed-direct"},
    )
    session = client.post(
        "/api/research-sessions/session-1/runs/run-provider-failed/execute",
        headers={"Idempotency-Key": "failed-session"},
        json={"project_id": "project-1", "workspace_id": "workspace-1"},
    )

    assert direct.status_code == session.status_code == 500
    assert direct.json()["code"] == "provider_crashed"
    assert session.json()["code"] == "provider_crashed"


def test_workspace_session_message_and_promotion_api_are_idempotent():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    db_session = sessionmaker(bind=engine)()
    service = ResearchWorkspaceService(ResearchWorkspaceRepository(db_session), clock=lambda: NOW)
    app = FastAPI()
    app.include_router(research_workspaces.router)
    app.include_router(research_sessions.router)
    app.dependency_overrides[research_workspaces.get_research_workspace_service] = lambda: service
    app.dependency_overrides[research_sessions.get_research_workspace_service] = lambda: service
    client = TestClient(app)

    try:
        workspace = client.post(
            "/api/research-workspaces",
            headers={"Idempotency-Key": "workspace-1"},
            json={"project_id": "project-1", "title": "黄金"},
        )
        duplicate = client.post(
            "/api/research-workspaces",
            headers={"Idempotency-Key": "workspace-1"},
            json={"project_id": "project-1", "title": "黄金"},
        )
        assert workspace.status_code == 201
        assert duplicate.json()["workspace_id"] == workspace.json()["workspace_id"]

        session = client.post(
            "/api/research-sessions",
            headers={"Idempotency-Key": "session-1"},
            json={"mode": "temporary"},
        )
        session_id = session.json()["session_id"]
        first_message = client.post(
            f"/api/research-sessions/{session_id}/messages",
            headers={"Idempotency-Key": "message-1"},
            json={"role": "user", "content": "研究黄金"},
        )
        duplicate_message = client.post(
            f"/api/research-sessions/{session_id}/messages",
            headers={"Idempotency-Key": "message-1"},
            json={"role": "user", "content": "研究黄金"},
        )
        assert first_message.status_code == 201
        assert duplicate_message.json()["message_id"] == first_message.json()["message_id"]

        promoted = client.post(
            f"/api/research-sessions/{session_id}/promote",
            json={
                "workspace_id": workspace.json()["workspace_id"],
                "project_id": "project-1",
            },
        )
        assert promoted.status_code == 200
        assert promoted.json()["mode"] == "workspace"
        assert (
            len(
                client.get(
                    f"/api/research-sessions/{session_id}/messages",
                    headers={
                        "X-Project-ID": "project-1",
                        "X-Workspace-ID": workspace.json()["workspace_id"],
                    },
                ).json()
            )
            == 1
        )
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_research_run_sse_is_ordered_resumable_and_contains_only_safe_refs():
    class EventService:
        def list_events(self, run_id: str, after_event_id: str | None = None):
            events = [
                {"event_id": "ev-1", "sequence": 0, "status": "draft", "stage": "draft"},
                {
                    "event_id": "ev-2",
                    "sequence": 1,
                    "status": "planning",
                    "stage": "planning",
                },
            ]
            return events[1:] if after_event_id == "ev-1" else events

    app = FastAPI()
    app.include_router(research_runs.router)
    app.dependency_overrides[research_runs.get_research_run_service] = lambda: EventService()
    response = TestClient(app).get(
        "/api/research-runs/run-1/events?follow=false",
        headers={"Last-Event-ID": "ev-1"},
    )

    assert response.status_code == 200
    assert "id: ev-2" in response.text
    assert '"sequence":1' in response.text
    assert "prompt" not in response.text
    assert "artifact" not in response.text


def test_session_run_vertical_slice_is_atomic_scoped_and_idempotent():
    from data_layer.repositories.research_run_repository import ResearchRunRepository
    from services.research_orchestration_service import ResearchOrchestrationService
    from services.research_run_service import ResearchRunService

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db_session = sessionmaker(bind=engine)()
    workspace_service = ResearchWorkspaceService(
        ResearchWorkspaceRepository(db_session), clock=lambda: NOW
    )
    orchestration = ResearchOrchestrationService(
        workspace_service=workspace_service,
        run_service=ResearchRunService(
            ResearchRunRepository(db_session), workspace_service=workspace_service
        ),
    )
    app = FastAPI()
    app.include_router(research_sessions.router)
    app.dependency_overrides[research_sessions.get_research_workspace_service] = (
        lambda: workspace_service
    )
    app.dependency_overrides[research_sessions.get_research_orchestration_service] = (
        lambda: orchestration
    )
    client = TestClient(app)
    try:
        workspace = workspace_service.create_workspace("project-1", "黄金", "workspace-vertical")
        session = workspace_service.create_session(
            mode="workspace",
            workspace_id=workspace.workspace_id,
            idempotency_key="session-vertical",
        )
        body = {
            "project_id": "project-1",
            "workspace_id": workspace.workspace_id,
            "run": {
                "template_key": "a_share_deep_research",
                "target_id": "600519.SH",
                "as_of": NOW.isoformat(),
                "question": "证据是否充分？",
                "mode": "fingpt",
            },
        }
        created = client.post(
            f"/api/research-sessions/{session.session_id}/runs",
            headers={"Idempotency-Key": "session-run-1"},
            json=body,
        )
        duplicate = client.post(
            f"/api/research-sessions/{session.session_id}/runs",
            headers={"Idempotency-Key": "session-run-1"},
            json=body,
        )
        assert created.status_code == 201
        assert duplicate.json()["run"]["run_id"] == created.json()["run"]["run_id"]
        assert duplicate.json()["session"]["run_id"] == created.json()["run"]["run_id"]

        conflict = client.post(
            f"/api/research-sessions/{session.session_id}/runs",
            headers={"Idempotency-Key": "session-run-1"},
            json={**body, "run": {**body["run"], "question": "篡改请求"}},
        )
        assert conflict.status_code == 409
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_dsh_callback_api_is_typed_idempotent_and_rejects_altered_replay():
    from core.contracts.research_workspace import RuntimeProvider
    from services.runtime_provider_service import RuntimeProviderService

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    db_session = sessionmaker(bind=engine)()
    repository = ResearchWorkspaceRepository(db_session)
    repository.save_runtime_provider(
        RuntimeProvider(
            provider_id="dsh-1",
            provider_type="dsh",
            name="DSH",
            capabilities={"single_agent"},
            status="healthy",
            checked_at=NOW,
        )
    )
    service = RuntimeProviderService(repository=repository)
    app = FastAPI()
    app.include_router(runtime_providers.router)
    app.dependency_overrides[runtime_providers.get_runtime_provider_service] = lambda: service

    class CallbackBridge:
        def accept_provider_result(self, result, *, request_hash):
            return service.accept_provider_result(result, request_hash=request_hash)

    app.dependency_overrides[runtime_providers.get_research_run_service] = CallbackBridge
    client = TestClient(app)
    body = {
        "request_hash": "sha256:a",
        "result": {
            "provider_id": "dsh-1",
            "provider_result_id": "result-1",
            "request_id": "run-1:0",
            "run_id": "run-1",
            "request_hash": "sha256:a",
            "terminal_status": "completed",
            "output": {"summary": "完成"},
        },
    }
    try:
        first = client.post("/api/runtime-providers/dsh-1/results", json=body)
        duplicate = client.post("/api/runtime-providers/dsh-1/results", json=body)
        altered = client.post(
            "/api/runtime-providers/dsh-1/results",
            json={
                **body,
                "request_hash": "sha256:b",
                "result": {
                    **body["result"],
                    "request_hash": "sha256:b",
                    "output": {"summary": "篡改"},
                },
            },
        )
        assert first.status_code == duplicate.status_code == 202
        assert first.json() == duplicate.json()
        assert altered.status_code == 409
    finally:
        db_session.close()
        Base.metadata.drop_all(bind=engine)


def test_session_execute_http_commits_blocked_runtime_terminal_state():
    """Regression: translating RuntimeBlockedError to HTTPException rolled DB state back."""

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    def request_db():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app = FastAPI()
    app.include_router(research_workspaces.router)
    app.include_router(research_sessions.router)
    app.dependency_overrides[production_get_db] = request_db
    client = TestClient(app)
    try:
        workspace = client.post(
            "/api/research-workspaces",
            headers={"Idempotency-Key": "blocked-workspace"},
            json={"project_id": "project-blocked", "title": "Claw"},
        ).json()
        session = client.post(
            "/api/research-sessions",
            headers={"Idempotency-Key": "blocked-session"},
            json={
                "mode": "workspace",
                "project_id": "project-blocked",
                "workspace_id": workspace["workspace_id"],
            },
        ).json()
        created = client.post(
            f"/api/research-sessions/{session['session_id']}/runs",
            headers={"Idempotency-Key": "blocked-create"},
            json={
                "project_id": "project-blocked",
                "workspace_id": workspace["workspace_id"],
                "run": {
                    "template_key": "a_share_deep_research",
                    "target_id": "600519.SH",
                    "as_of": NOW.isoformat(),
                    "question": "Claw 能否运行？",
                    "mode": "claw",
                    "agent_team_id": "missing-team",
                },
            },
        )
        run_id = created.json()["run"]["run_id"]

        response = client.post(
            f"/api/research-sessions/{session['session_id']}/runs/{run_id}/execute",
            headers={"Idempotency-Key": "blocked-execute"},
            json={
                "project_id": "project-blocked",
                "workspace_id": workspace["workspace_id"],
            },
        )

        assert response.status_code == 409
        assert response.json()["code"] == "blocked_runtime"
        with session_factory() as verification_session:
            persisted = ResearchRunRepository(verification_session).get_run_or_raise(run_id)
            assert persisted.status.value == "blocked"
    finally:
        Base.metadata.drop_all(bind=engine)


def test_dsh_callback_correlates_and_completes_persisted_run():
    """Regression: callback was stored as an orphan event and never advanced its Run."""

    from core.contracts.research import ResearchRunCreateRequest, ResearchRunStatus
    from core.contracts.research_workspace import RuntimeProvider
    from services.research_graph import AShareDeepResearchGraph
    from services.research_run_service import ResearchRunService

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    def request_db():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    with session_factory() as setup:
        workspace_repository = ResearchWorkspaceRepository(setup)
        workspace_repository.save_runtime_provider(
            RuntimeProvider(
                provider_id="dsh-callback-real",
                provider_type="dsh",
                name="DSH callback",
                capabilities={"single_agent"},
                status="healthy",
                config_ref="env:ALPHAFOUNDRY_TEST_UNUSED_DSH",
                checked_at=NOW,
            )
        )
        run_service = ResearchRunService(ResearchRunRepository(setup))
        request = ResearchRunCreateRequest(
            template_key="a_share_deep_research",
            target_id="600519.SH",
            as_of=NOW,
            question="回传是否真正落库？",
        )
        created = run_service.create(request)
        request_id = f"{created.run_id}:0"
        request_hash = "sha256:callback-input"
        ResearchRunRepository(setup).update_run(created.run_id, status=ResearchRunStatus.PLANNING)
        ResearchRunRepository(setup).update_task(
            created.run_id,
            status=ResearchRunStatus.PLANNING,
            attempt=0,
            resume_from=None,
            state_snapshot={
                "status": "planning",
                "attempt": 0,
                "provider_request_id": request_id,
                "provider_request_hash": request_hash,
                "provider_id": "dsh-callback-real",
            },
        )
        setup.commit()
        runtime_input = {
            "run_id": created.run_id,
            "target_id": created.target_id,
            "subject": created.subject.model_dump(mode="json"),
            "as_of": created.as_of.isoformat(),
            "question": created.question,
            "evidence": [],
        }
        output = AShareDeepResearchGraph().invoke(runtime_input)

    app = FastAPI()
    app.include_router(runtime_providers.router)
    app.dependency_overrides[production_get_db] = request_db
    response = TestClient(app).post(
        "/api/runtime-providers/dsh-callback-real/results",
        json={
            "request_hash": request_hash,
            "result": {
                "provider_id": "dsh-callback-real",
                "provider_result_id": "provider-result-callback",
                "request_id": request_id,
                "run_id": created.run_id,
                "request_hash": request_hash,
                "terminal_status": "completed",
                "output": output,
            },
        },
    )

    try:
        assert response.status_code == 202
        with session_factory() as verification:
            persisted = ResearchRunRepository(verification).get_run_or_raise(created.run_id)
            assert persisted.status.value == "blocked"
            assert ResearchRunRepository(verification).list_artifacts(created.run_id)
    finally:
        Base.metadata.drop_all(bind=engine)
