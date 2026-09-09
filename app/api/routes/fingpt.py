"""FinGPT shell APIs; DSH owns transcript storage, AlphaFoundry owns governance."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.routes.runtime_workflows import require_dsh_tool_access
from data_layer.repositories.base import get_db
from data_layer.repositories.fingpt_repository import FinGPTRepository
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from services.fingpt_service import FinGPTService
from services.runtime_workflow_service import RuntimeWorkflowService

router = APIRouter(prefix="/api/v2/fingpt", tags=["fingpt"])


class CreateTaskRequest(BaseModel):
    preset_id: str = Field(min_length=1)


class ExecuteDailyTaskRequest(BaseModel):
    as_of: datetime = Field(default_factory=lambda: datetime.now(UTC))
    question: str = Field(default="生成当日 A 股每日收盘点评。", min_length=1)


class DshSyncEvent(BaseModel):
    session_id: str = Field(min_length=1)
    event_key: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    sequence: int = -1
    task_id: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)
    payload: dict[str, object] = Field(default_factory=dict)


def get_fingpt_service(db: Session = Depends(get_db)) -> FinGPTService:  # noqa: B008
    return FinGPTService(
        FinGPTRepository(db), RuntimeWorkflowService(RuntimeWorkflowRepository(db))
    )


@router.get("/health")
async def fingpt_health(service: FinGPTService = Depends(get_fingpt_service)):  # noqa: B008
    try:
        return service.health()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/sessions")
async def list_sessions(service: FinGPTService = Depends(get_fingpt_service)):  # noqa: B008
    return {"sessions": service.sessions()}


@router.get("/tasks")
async def list_tasks(service: FinGPTService = Depends(get_fingpt_service)):  # noqa: B008
    return {"tasks": service.tasks()}


@router.post("/tasks", status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: CreateTaskRequest, service: FinGPTService = Depends(get_fingpt_service)  # noqa: B008
):
    try:
        return service.create_task(payload.preset_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/tasks/{task_id}/execute")
async def execute_daily_task(
    task_id: str,
    payload: ExecuteDailyTaskRequest,
    service: FinGPTService = Depends(get_fingpt_service),  # noqa: B008
):
    try:
        return service.execute_daily_task(task_id, as_of=payload.as_of, question=payload.question)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/launches/{launch_id}/consume", dependencies=[Depends(require_dsh_tool_access)])
async def consume_launch(
    launch_id: str, service: FinGPTService = Depends(get_fingpt_service)  # noqa: B008
):
    try:
        return service.consume_launch(launch_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post(
    "/dsh-events",
    dependencies=[Depends(require_dsh_tool_access)],
    status_code=status.HTTP_202_ACCEPTED,
)
async def accept_dsh_event(
    payload: DshSyncEvent, service: FinGPTService = Depends(get_fingpt_service)  # noqa: B008
):
    try:
        return {"accepted": service.accept_dsh_event(payload.model_dump())}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/tasks/{task_id}/artifacts")
async def task_artifacts(
    task_id: str, service: FinGPTService = Depends(get_fingpt_service)  # noqa: B008
):
    try:
        return {"artifacts": service.artifacts(task_id)}
    except Exception as exc:
        raise _http_error(exc) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="FinGPT 任务或启动标识不存在。")
    if isinstance(exc, ValueError):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=503, detail="FinGPT 服务暂不可用。")
