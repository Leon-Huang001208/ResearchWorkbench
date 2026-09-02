"""Supervisor Agent Team definition API."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.contracts.research_workspace import AgentTeamDefinition
from core.observability import get_logger
from data_layer.repositories.base import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/agent-teams", tags=["agent-teams"])


def get_agent_team_service(db: Session = Depends(get_db)):
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.agent_team_service import AgentTeamService

    return AgentTeamService(repository=ResearchWorkspaceRepository(db))


@router.get("", response_model=list[AgentTeamDefinition])
async def list_agent_teams(service=Depends(get_agent_team_service)):
    return service.list_teams()


@router.post("", response_model=AgentTeamDefinition, status_code=status.HTTP_201_CREATED)
async def save_agent_team(
    team: AgentTeamDefinition, service=Depends(get_agent_team_service)
) -> AgentTeamDefinition:
    try:
        return service.save_team(team)
    except Exception as exc:
        logger.error("agent team API failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=409, detail="Agent team conflict") from exc
