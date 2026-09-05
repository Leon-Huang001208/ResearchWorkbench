"""Version 2 runtime-neutral workflow API with replayable SSE events."""

from __future__ import annotations

import ipaddress
import json
import os
import secrets
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from data_layer.repositories.base import get_db
from data_layer.repositories.runtime_workflow_repository import (
    RuntimeWorkflowRepository,
)
from services.daily_market_commentary_spec import (
    DailyMarketCommentarySpec,
    load_daily_market_commentary_spec,
    save_daily_market_commentary_spec,
)
from services.runtime_workflow_service import (
    DailyMarketCommentaryRequest,
    RuntimeWorkflowService,
)

router = APIRouter(prefix="/api/v2", tags=["runtime-workflows"])


class RuntimeToolInvocation(BaseModel):
    """Payload accepted only from the local AlphaFoundry DSH bundle."""

    run_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    correlation_id: UUID
    input: dict[str, object] = Field(default_factory=dict)


def require_dsh_tool_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> None:
    """Fail closed: DSH tools are local-only and require a dedicated token."""
    client_host = request.client.host if request.client is not None else ""
    try:
        is_loopback = client_host == "testclient" or ipaddress.ip_address(client_host).is_loopback
    except ValueError:
        is_loopback = False
    expected = os.getenv("ALPHAFOUNDRY_DSH_TOOL_TOKEN", "")
    submitted = authorization.removeprefix("Bearer ") if authorization else ""
    if not expected or not is_loopback or not secrets.compare_digest(expected, submitted):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def get_runtime_workflow_service(
    db: Session = Depends(get_db),  # noqa: B008
) -> RuntimeWorkflowService:
    return RuntimeWorkflowService(RuntimeWorkflowRepository(db))


@router.get("/runtimes")
async def list_runtimes(
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    return service.capabilities()


@router.get("/capabilities")
async def list_capabilities(
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    return {"runtimes": service.capabilities(), "workflow_ids": ["daily-market-commentary"]}


@router.get("/workflows/daily-market-commentary")
async def get_daily_market_commentary_workflow() -> DailyMarketCommentarySpec:
    """Return the editable source-of-truth specification for the production studio."""
    try:
        return load_daily_market_commentary_spec()
    except Exception as exc:
        raise _http_error(exc) from exc


@router.put("/workflows/daily-market-commentary")
async def update_daily_market_commentary_workflow(
    spec: DailyMarketCommentarySpec,
) -> DailyMarketCommentarySpec:
    """Persist a validated visual-editor configuration, never an arbitrary prompt."""
    try:
        save_daily_market_commentary_spec(spec)
        return spec
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runtime-tools/{capability_id}", dependencies=[Depends(require_dsh_tool_access)])
async def run_runtime_tool(
    capability_id: str,
    invocation: RuntimeToolInvocation,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    if invocation.input:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Tool input must be empty"
        )
    try:
        return service.run_native_tool(
            run_id=invocation.run_id,
            capability_id=capability_id,
            execution_id=invocation.execution_id,
            correlation_id=str(invocation.correlation_id),
        )
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/market-commentary/runs", status_code=status.HTTP_201_CREATED)
async def create_market_commentary_run(
    request: DailyMarketCommentaryRequest,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        return service.create_daily_market_commentary(request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}")
async def get_workflow_run(
    run_id: str,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        row = service.get(run_id)
        return {
            "run_id": row.run_id,
            "workflow_id": row.workflow_id,
            "workflow_version": row.workflow_version,
            "runtime_id": row.runtime_id,
            "status": row.status,
            "error_message": row.error_message,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
        }
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/execute")
async def execute_workflow_run(
    run_id: str,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        return service.execute(run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/cancel", status_code=status.HTTP_202_ACCEPTED)
async def cancel_workflow_run(
    run_id: str,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        service.cancel(run_id)
        return {"run_id": run_id, "status": "cancelled"}
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/runs/{run_id}/resume")
async def resume_workflow_run(
    run_id: str,
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        return service.resume(run_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/runs/{run_id}/events")
async def stream_workflow_events(
    run_id: str,
    after_sequence: int = Query(default=-1, ge=-1),
    service: RuntimeWorkflowService = Depends(get_runtime_workflow_service),  # noqa: B008
):
    try:
        events = service.events(run_id, after_sequence=after_sequence)
    except Exception as exc:
        raise _http_error(exc) from exc

    def iterator():
        for event in events:
            yield f"id: {event.sequence}\nevent: {event.event_type}\ndata: {json.dumps(event.model_dump(mode='json'), ensure_ascii=False)}\n\n"

    return StreamingResponse(
        iterator(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"}
    )


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="工作流不存在。")
    if isinstance(exc, (ValueError, RuntimeError)):
        return HTTPException(status_code=409, detail=str(exc))
    return HTTPException(status_code=500, detail="工作流服务执行失败。")
