"""Atomic, project-scoped orchestration for Session-to-Run vertical slices."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from core.contracts.research import ResearchRun, ResearchRunCreateRequest
from core.contracts.research_workspace import ResearchSession
from core.observability import get_logger
from services.research_run_service import ResearchRunService
from services.research_workspace_service import ResearchWorkspaceService

logger = get_logger(__name__)


class SessionRunBinding(BaseModel):
    """Atomic response containing the linked Session and created Run."""

    model_config = ConfigDict(extra="forbid")

    session: ResearchSession
    run: ResearchRun


class ResearchOrchestrationService:
    """Coordinate aggregates without allowing either module to write the other's tables."""

    def __init__(
        self,
        *,
        workspace_service: ResearchWorkspaceService,
        run_service: ResearchRunService,
    ) -> None:
        self.workspace_service = workspace_service
        self.run_service = run_service

    def create_session_run(
        self,
        session_id: str,
        *,
        project_id: str,
        workspace_id: str,
        request: ResearchRunCreateRequest,
        idempotency_key: str,
    ) -> SessionRunBinding:
        """Create and bind in one database transaction/savepoint."""

        db = self.workspace_service.repository.db
        try:
            with db.begin_nested():
                self.workspace_service.get_session_scoped(
                    session_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                )
                run = self.run_service.create(request, idempotency_key=idempotency_key)
                session = self.workspace_service.link_session_run(
                    session_id,
                    run.run_id,
                    project_id=project_id,
                    workspace_id=workspace_id,
                )
        except Exception:
            logger.exception(
                "research Session-to-Run binding failed",
                session_id=session_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            raise
        logger.info(
            "research Session bound to Run",
            session_id=session_id,
            run_id=run.run_id,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        return SessionRunBinding(session=session, run=run)

    def execute_session_run(
        self,
        session_id: str,
        run_id: str,
        *,
        project_id: str,
        workspace_id: str,
        idempotency_key: str,
    ) -> ResearchRun:
        """Execute only after revalidating the full project/workspace/session scope."""

        try:
            session = self.workspace_service.get_session_scoped(
                session_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )
            if session.run_id != run_id:
                raise ValueError("run is not linked to the scoped session")
            self.workspace_service.assert_run_scope(
                run_id,
                project_id=project_id,
                workspace_id=workspace_id,
            )
            return self.run_service.execute(
                run_id,
                idempotency_key=idempotency_key,
                project_id=project_id,
                workspace_id=workspace_id,
            )
        except Exception:
            logger.exception(
                "scoped research Run execution failed",
                session_id=session_id,
                run_id=run_id,
                workspace_id=workspace_id,
                project_id=project_id,
            )
            raise
