"""Cross-domain, evidence-first Research Run API."""

# ruff: noqa: B008 - FastAPI dependency declarations are evaluated at import time.

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.orm import Session

from core.contracts.research import (
    ResearchEvidenceInput,
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunOutputs,
    ResearchTemplateDefinition,
)
from core.contracts.research_workspace import RuntimeProvider
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.research_run_repository import ResearchRunRepository
from services.research_templates import ResearchTemplateValidationError

if TYPE_CHECKING:
    from services.research_run_service import ResearchRunService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/research-runs", tags=["research-runs"])
template_router = APIRouter(prefix="/api/research-templates", tags=["research-templates"])


def _scope_kwargs(project_id: str | None, workspace_id: str | None) -> dict[str, str]:
    if bool(project_id) != bool(workspace_id):
        raise HTTPException(status_code=422, detail="Both project and workspace scope are required")
    return (
        {"project_id": project_id, "workspace_id": workspace_id}
        if project_id and workspace_id
        else {}
    )


def get_research_run_service(db: Session = Depends(get_db)) -> ResearchRunService:
    """Inject the aggregate service with the request-scoped database session."""
    from data_layer.repositories.research_workspace_repository import (
        ResearchWorkspaceRepository,
    )
    from services.agent_team_service import AgentTeamService
    from services.research_run_service import ResearchRunService
    from services.research_tool_registry import (
        build_production_research_tool_dispatcher,
        record_datahub_tool_evidence,
    )
    from services.research_workspace_service import ResearchWorkspaceService
    from services.runtime_provider_service import (
        ProductionResearchExecutionAdapters,
        RuntimeProviderService,
        load_authorized_tool_registry,
    )

    repository = ResearchWorkspaceRepository(db)
    workspace_service = ResearchWorkspaceService(repository)
    runtime_service = RuntimeProviderService(
        repository=repository,
        providers=[
            RuntimeProvider(
                provider_id="builtin-langgraph",
                provider_type="langgraph",
                name="Built-in LangGraph",
                capabilities={"single_agent", "resume", "sse"},
                status="healthy",
                checked_at=datetime.now(UTC),
            )
        ],
    )
    adapters = ProductionResearchExecutionAdapters(
        tool_dispatcher=build_production_research_tool_dispatcher(db),
        tool_result_sink=lambda run_id, tool_id, arguments, result: record_datahub_tool_evidence(
            db, run_id, tool_id, arguments, result
        ),
    )
    executable_tool_ids = load_authorized_tool_registry().intersection(adapters.authorized_tool_ids)
    return ResearchRunService(
        ResearchRunRepository(db),
        workspace_service=workspace_service,
        runtime_service=runtime_service,
        agent_team_service=AgentTeamService(repository=repository),
        provider_invoker=adapters.invoke_provider,
        skill_invoker=adapters.invoke_skill,
        agent_worker=adapters.invoke_agent,
        agent_supervisor=adapters.invoke_supervisor,
        authorized_tool_ids=executable_tool_ids,
    )


@router.post("", response_model=ResearchRun, status_code=status.HTTP_201_CREATED)
async def create_research_run(
    request: ResearchRunCreateRequest,
    idempotency_key: str
    | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=240),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun | Response:
    """Create a durable research task; execution remains explicit and resumable."""
    try:
        return service.create(request, idempotency_key=idempotency_key)
    except ResearchTemplateValidationError as exc:
        logger.warning(
            "research run request rejected",
            template_key=request.template_key,
            error=str(exc),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("research run creation failed", error=str(exc))
        raise HTTPException(status_code=500, detail="无法创建研究任务。") from exc


@router.get("", response_model=list[ResearchRun])
async def list_research_runs(
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> list[ResearchRun]:
    """List recent cross-domain Research Runs for the unified research center."""
    try:
        return service.list_recent(project_id=project_id, workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@template_router.get("", response_model=list[ResearchTemplateDefinition])
async def list_research_templates() -> list[ResearchTemplateDefinition]:
    """Expose template capability metadata without framework executor objects."""
    from services.research_templates import get_default_research_template_registry

    return get_default_research_template_registry().list_definitions()


@router.get("/{run_id}", response_model=ResearchRun)
async def get_research_run(
    run_id: str,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.get(run_id, **_scope_kwargs(project_id, workspace_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="研究任务不存在。") from exc


@router.post("/{run_id}/execute", response_model=ResearchRun)
async def execute_research_run(
    run_id: str,
    idempotency_key: str
    | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=240),
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    from services.runtime_provider_service import (
        RuntimeBlockedError,
        RuntimeFailedError,
    )

    try:
        return service.execute(
            run_id,
            idempotency_key=idempotency_key,
            **_scope_kwargs(project_id, workspace_id),
        )
    except RuntimeBlockedError as exc:
        blocked = service.get(run_id, **_scope_kwargs(project_id, workspace_id))
        return JSONResponse(
            status_code=409,
            content={
                "code": exc.code,
                "run": blocked.model_dump(mode="json"),
            },
        )
    except RuntimeFailedError as exc:
        failed = service.get(run_id, **_scope_kwargs(project_id, workspace_id))
        return JSONResponse(
            status_code=500,
            content={"code": exc.code, "run": failed.model_dump(mode="json")},
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception(
            "research run execution failed", run_id=run_id, error_type=type(exc).__name__
        )
        failed = service.get(run_id, **_scope_kwargs(project_id, workspace_id))
        return JSONResponse(
            status_code=500,
            content={"code": "research_runtime_failed", "run": failed.model_dump(mode="json")},
        )


@router.post("/{run_id}/resume", response_model=ResearchRun)
async def resume_research_run(
    run_id: str,
    idempotency_key: str
    | None = Header(default=None, alias="Idempotency-Key", min_length=1, max_length=240),
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun | Response:
    from services.runtime_provider_service import RuntimeBlockedError

    try:
        return service.resume(
            run_id,
            idempotency_key=idempotency_key,
            **_scope_kwargs(project_id, workspace_id),
        )
    except RuntimeBlockedError as exc:
        blocked = service.get(run_id, **_scope_kwargs(project_id, workspace_id))
        return JSONResponse(
            status_code=409,
            content={"code": exc.code, "run": blocked.model_dump(mode="json")},
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("research run resume failed", run_id=run_id, error_type=type(exc).__name__)
        failed = service.get(run_id, **_scope_kwargs(project_id, workspace_id))
        return JSONResponse(
            status_code=500,
            content={"code": "research_runtime_failed", "run": failed.model_dump(mode="json")},
        )


@router.get("/{run_id}/events")
async def stream_research_run_events(
    run_id: str,
    request: Request,
    follow: bool = Query(default=True),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> StreamingResponse:
    """Stream only durable status references with ordered cursor replay."""

    try:
        scope = _scope_kwargs(project_id, workspace_id)
        initial = (
            service.list_events(run_id, last_event_id, **scope)
            if scope
            else service.list_events(run_id, last_event_id)
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Research event cursor not found") from exc

    async def generate():
        cursor = last_event_id
        pending = initial
        while True:
            for event in pending:
                cursor = event["event_id"]
                safe_payload = {
                    "event_id": event["event_id"],
                    "sequence": event["sequence"],
                    "status": event["status"],
                    "stage": event["stage"],
                }
                yield (
                    f"id: {event['event_id']}\n"
                    "event: research_run_status\n"
                    f"data: {json.dumps(safe_payload, separators=(',', ':'))}\n\n"
                )
            if not follow or await request.is_disconnected():
                break
            await asyncio.sleep(1)
            pending = (
                service.list_events(run_id, cursor, **scope)
                if scope
                else service.list_events(run_id, cursor)
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/evidence", response_model=ResearchRun)
async def add_research_evidence(
    run_id: str,
    evidence: ResearchEvidenceInput,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.add_evidence(run_id, evidence, **_scope_kwargs(project_id, workspace_id))
    except ResearchTemplateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{run_id}/outputs", response_model=ResearchRunOutputs)
async def get_research_outputs(
    run_id: str,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRunOutputs:
    try:
        return service.get_outputs(run_id, **_scope_kwargs(project_id, workspace_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="研究任务不存在。") from exc


@router.get("/{run_id}/downloads/markdown")
async def download_research_markdown(
    run_id: str,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> Response:
    """Download the report projection only after all publishing gates passed."""
    try:
        content = service.export_markdown(run_id, **_scope_kwargs(project_id, workspace_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.md"'},
    )


@router.get("/{run_id}/downloads/word")
async def download_research_word(
    run_id: str,
    project_id: str | None = Header(default=None, alias="X-Project-ID"),
    workspace_id: str | None = Header(default=None, alias="X-Workspace-ID"),
    service: ResearchRunService = Depends(get_research_run_service),
) -> Response:
    """Download the Word report projection only after all publishing gates passed."""
    try:
        content = service.export_word(run_id, **_scope_kwargs(project_id, workspace_id))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.docx"'},
    )
