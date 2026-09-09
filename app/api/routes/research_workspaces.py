"""Thin API routes for project-isolated research workspaces and notes."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.contracts.research_workspace import ResearchNote, ResearchWorkspace
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.research_workspace_service import WorkspaceScopeError

logger = get_logger(__name__)
router = APIRouter(prefix="/api/research-workspaces", tags=["research-workspaces"])


class WorkspaceCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=240)


class NoteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_key: str = Field(min_length=1, max_length=160)
    source_kind: Literal["claim", "paragraph"]
    summary: str = Field(min_length=1, max_length=4000)
    claim_id: str | None = None
    run_id: str | None = None
    paragraph_ref: str | None = None


def get_research_workspace_service(db: Session = Depends(get_db)):
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.research_workspace_service import ResearchWorkspaceService

    return ResearchWorkspaceService(ResearchWorkspaceRepository(db))


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=240)]


def _http_error(exc: Exception) -> None:
    if isinstance(exc, KeyError):
        raise HTTPException(
            status_code=404, detail="Research workspace resource not found"
        ) from exc
    if isinstance(exc, WorkspaceScopeError):
        raise HTTPException(status_code=409, detail="Research workspace scope conflict") from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail="Invalid research workspace request") from exc
    logger.error("research workspace API failed", error_type=type(exc).__name__)
    raise HTTPException(status_code=500, detail="Research workspace request failed") from exc


@router.post("", response_model=ResearchWorkspace, status_code=status.HTTP_201_CREATED)
async def create_workspace(
    request: WorkspaceCreateRequest,
    idempotency_key: IdempotencyKey,
    service=Depends(get_research_workspace_service),
) -> ResearchWorkspace:
    try:
        return service.create_workspace(request.project_id, request.title, idempotency_key)
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.get("", response_model=list[ResearchWorkspace])
async def list_workspaces(
    project_id: str = Query(min_length=1, max_length=160),
    service=Depends(get_research_workspace_service),
) -> list[ResearchWorkspace]:
    try:
        return service.list_workspaces(project_id)
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.get("/{workspace_id}", response_model=ResearchWorkspace)
async def get_workspace(
    workspace_id: str,
    project_id: str = Header(alias="X-Project-ID", min_length=1),
    service=Depends(get_research_workspace_service),
):
    try:
        return service.get_workspace_scoped(workspace_id, project_id)
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.get("/{workspace_id}/notes", response_model=list[ResearchNote])
async def list_workspace_notes(
    workspace_id: str,
    project_id: str = Header(alias="X-Project-ID", min_length=1),
    service=Depends(get_research_workspace_service),
) -> list[ResearchNote]:
    try:
        service.get_workspace_scoped(workspace_id, project_id)
        return service.build_memory_context(workspace_id)
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)


@router.post(
    "/{workspace_id}/notes",
    response_model=ResearchNote,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace_note(
    workspace_id: str,
    request: NoteCreateRequest,
    project_id: str = Header(alias="X-Project-ID", min_length=1),
    service=Depends(get_research_workspace_service),
) -> ResearchNote:
    try:
        service.get_workspace_scoped(workspace_id, project_id)
        return service.pin_note(workspace_id, **request.model_dump())
    except Exception as exc:  # noqa: BLE001
        _http_error(exc)
