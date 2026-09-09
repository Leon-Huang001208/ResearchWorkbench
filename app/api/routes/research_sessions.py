"""Thin API routes for research sessions and idempotent messages."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.routes.research_runs import get_research_run_service
from app.api.routes.research_workspaces import get_research_workspace_service
from core.contracts.research import ResearchRun, ResearchRunCreateRequest
from core.contracts.research_workspace import (
    ResearchMessage,
    ResearchSession,
    SessionMode,
)
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/research-sessions", tags=["research-sessions"])


class SessionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: SessionMode
    workspace_id: str | None = Field(default=None, min_length=1)
    project_id: str | None = Field(default=None, min_length=1)
    run_id: str | None = Field(default=None, min_length=1)


class MessageCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["user", "assistant", "system", "tool"]
    content: str | None = None
    content_ref: str | None = None


class PromoteSessionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)


class SessionRunCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    run: ResearchRunCreateRequest


class SessionRunExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=240)]


def get_research_orchestration_service(
    workspace_service=Depends(get_research_workspace_service),
    run_service=Depends(get_research_run_service),
):
    from services.research_orchestration_service import ResearchOrchestrationService

    return ResearchOrchestrationService(
        workspace_service=workspace_service,
        run_service=run_service,
    )


def _http_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(status_code=404, detail="Research session resource not found") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=409, detail="Research session conflict") from exc
    logger.error("research session API failed", error_type=type(exc).__name__)
    raise HTTPException(status_code=500, detail="Research session request failed") from exc


@router.post("", response_model=ResearchSession, status_code=status.HTTP_201_CREATED)
async def create_session(
    request: SessionCreateRequest,
    idempotency_key: IdempotencyKey,
    service=Depends(get_research_workspace_service),
) -> ResearchSession:
    try:
        if request.workspace_id:
            if not request.project_id:
                raise ValueError("project_id is required for a workspace session")
            service.get_workspace_scoped(request.workspace_id, request.project_id)
        return service.create_session(
            mode=request.mode,
            idempotency_key=idempotency_key,
            workspace_id=request.workspace_id,
            run_id=request.run_id,
        )
    except Exception as exc:  # noqa: BLE001 - translate request boundary failures
        _http_error(exc)


@router.get("/{session_id}", response_model=ResearchSession)
async def get_session(
    session_id: str,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service=Depends(get_research_workspace_service),
):
    try:
        return service.get_session(session_id, project_id=project_id, workspace_id=workspace_id)
    except Exception as exc:  # noqa: BLE001 - translate request boundary failures
        _http_error(exc)


@router.post("/{session_id}/promote", response_model=ResearchSession)
async def promote_session(
    session_id: str,
    request: PromoteSessionRequest,
    service=Depends(get_research_workspace_service),
) -> ResearchSession:
    try:
        service.get_workspace_scoped(request.workspace_id, request.project_id)
        return service.promote_session(session_id, request.workspace_id)
    except Exception as exc:  # noqa: BLE001 - translate request boundary failures
        _http_error(exc)


@router.post(
    "/{session_id}/messages",
    response_model=ResearchMessage,
    status_code=status.HTTP_201_CREATED,
)
async def append_message(
    session_id: str,
    request: MessageCreateRequest,
    idempotency_key: IdempotencyKey,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service=Depends(get_research_workspace_service),
) -> ResearchMessage:
    try:
        return service.append_message(
            session_id,
            role=request.role,
            content=request.content,
            content_ref=request.content_ref,
            idempotency_key=idempotency_key,
            project_id=project_id,
            workspace_id=workspace_id,
        )
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.get("/{session_id}/messages", response_model=list[ResearchMessage])
async def list_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service=Depends(get_research_workspace_service),
) -> list[ResearchMessage]:
    try:
        return service.list_messages(
            session_id,
            limit=limit,
            project_id=project_id,
            workspace_id=workspace_id,
        )
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.post("/{session_id}/runs", status_code=status.HTTP_201_CREATED)
async def create_session_run(
    session_id: str,
    request: SessionRunCreateRequest,
    idempotency_key: IdempotencyKey,
    service=Depends(get_research_orchestration_service),
):
    """Atomically create and bind one project-scoped Research Run."""

    try:
        return service.create_session_run(
            session_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
            request=request.run,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.post("/{session_id}/runs/{run_id}/execute", response_model=ResearchRun)
async def execute_session_run(
    session_id: str,
    run_id: str,
    request: SessionRunExecuteRequest,
    idempotency_key: IdempotencyKey,
    service=Depends(get_research_orchestration_service),
) -> ResearchRun:
    """Execute a Run only inside its explicitly supplied project/workspace scope."""

    from services.runtime_provider_service import (
        RuntimeBlockedError,
        RuntimeFailedError,
    )

    try:
        return service.execute_session_run(
            session_id,
            run_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
            idempotency_key=idempotency_key,
        )
    except RuntimeBlockedError as exc:
        blocked = service.run_service.get(
            run_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
        )
        return JSONResponse(
            status_code=409,
            content={"code": exc.code, "run": blocked.model_dump(mode="json")},
        )
    except RuntimeFailedError as exc:
        failed = service.run_service.get(
            run_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
        )
        return JSONResponse(
            status_code=500,
            content={"code": exc.code, "run": failed.model_dump(mode="json")},
        )
    except ValueError as exc:
        _http_error(exc)
    except Exception as exc:
        logger.exception(
            "research Session Run execution failed",
            session_id=session_id,
            run_id=run_id,
            error_type=type(exc).__name__,
        )
        failed = service.run_service.get(
            run_id,
            project_id=request.project_id,
            workspace_id=request.workspace_id,
        )
        return JSONResponse(
            status_code=500,
            content={"code": "research_runtime_failed", "run": failed.model_dump(mode="json")},
        )
