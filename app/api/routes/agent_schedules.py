"""Agent schedule CRUD and idempotent manual trigger API."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.contracts.platform_shared import ScheduledJob
from core.contracts.research_workspace import AgentSchedule
from core.observability import get_logger
from data_layer.repositories.base import get_db

logger = get_logger(__name__)
router = APIRouter(prefix="/api/agent-schedules", tags=["agent-schedules"])


class TriggerScheduleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scheduled_for: datetime | None = None
    steps: list[dict] = Field(default_factory=list)


class ScheduleWorkerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    worker_id: str = Field(min_length=1)
    lease_seconds: int = Field(default=60, ge=1, le=3600)


class ScheduleWorkResponse(BaseModel):
    job: ScheduledJob
    team_run: dict


def get_schedule_dependencies(db: Session = Depends(get_db)):
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.agent_schedule_runtime import build_agent_schedule_execution_service
    from services.scheduler_coordinator import SchedulerCoordinator

    repository = ResearchWorkspaceRepository(db)
    return (
        repository,
        SchedulerCoordinator(repository),
        build_agent_schedule_execution_service(repository),
    )


@router.get("", response_model=list[AgentSchedule])
async def list_schedules(dependencies=Depends(get_schedule_dependencies)):
    repository, _, _ = dependencies
    return repository.list_agent_schedules()


@router.post("", response_model=AgentSchedule, status_code=status.HTTP_201_CREATED)
async def save_schedule(
    schedule: AgentSchedule, dependencies=Depends(get_schedule_dependencies)
) -> AgentSchedule:
    repository, _, _ = dependencies
    try:
        return repository.save_agent_schedule(schedule)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent team not found") from exc
    except Exception as exc:
        logger.error("agent schedule API failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=409, detail="Agent schedule conflict") from exc


IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=240)]


@router.post("/{schedule_id}/trigger", response_model=ScheduledJob)
async def trigger_schedule(
    schedule_id: str,
    idempotency_key: IdempotencyKey,
    request: TriggerScheduleRequest | None = None,
    dependencies=Depends(get_schedule_dependencies),
) -> ScheduledJob:
    _, coordinator, _ = dependencies
    try:
        payload = {"steps": request.steps} if request and request.steps else None
        return coordinator.trigger(
            schedule_id,
            idempotency_key=idempotency_key,
            scheduled_for=request.scheduled_for if request else None,
            payload=payload,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent schedule not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Agent schedule is not active") from exc


@router.post("/{schedule_id}/work", response_model=ScheduleWorkResponse)
async def work_schedule(
    schedule_id: str,
    request: ScheduleWorkerRequest,
    dependencies=Depends(get_schedule_dependencies),
) -> ScheduleWorkResponse:
    """Claim, run, renew/fence, and complete one persisted Agent Team job."""

    _, coordinator, execution_service = dependencies
    try:
        job, team_run = execution_service.run_once(
            coordinator,
            schedule_id,
            request.worker_id,
            lease_seconds=request.lease_seconds,
        )
        return ScheduleWorkResponse(job=job, team_run=team_run.model_dump(mode="json"))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Agent schedule resource not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail="Agent schedule work conflict") from exc
    except Exception as exc:
        logger.error("Agent schedule worker failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Agent schedule worker failed") from exc
