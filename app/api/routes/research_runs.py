"""Cross-domain, evidence-first Research Run API."""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from core.contracts.research import (
    ResearchEvidenceInput,
    ResearchRun,
    ResearchRunCreateRequest,
    ResearchRunOutputs,
    ResearchTemplateDefinition,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.research_run_repository import ResearchRunRepository
from services.research_templates import ResearchTemplateValidationError

if TYPE_CHECKING:
    from services.research_run_service import ResearchRunService

logger = get_logger(__name__)
router = APIRouter(prefix="/api/research-runs", tags=["research-runs"])
template_router = APIRouter(prefix="/api/research-templates", tags=["research-templates"])


def get_research_run_service(db: Session = Depends(get_db)) -> ResearchRunService:
    """Inject the aggregate service with the request-scoped database session."""
    from services.research_run_service import ResearchRunService

    return ResearchRunService(ResearchRunRepository(db))


@router.post("", response_model=ResearchRun, status_code=status.HTTP_201_CREATED)
async def create_research_run(
    request: ResearchRunCreateRequest,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    """Create a durable research task; execution remains explicit and resumable."""
    try:
        return service.create(request)
    except ResearchTemplateValidationError as exc:
        logger.warning(
            "research run request rejected",
            template_key=request.template_key,
            error=str(exc),
        )
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("research run creation failed", error=str(exc), exc_info=True)
        raise HTTPException(status_code=500, detail="无法创建研究任务。") from exc


@router.get("", response_model=list[ResearchRun])
async def list_research_runs(
    service: ResearchRunService = Depends(get_research_run_service),
) -> list[ResearchRun]:
    """List recent cross-domain Research Runs for the unified research center."""
    return service.list_recent()


@template_router.get("", response_model=list[ResearchTemplateDefinition])
async def list_research_templates() -> list[ResearchTemplateDefinition]:
    """Expose template capability metadata without framework executor objects."""
    from services.research_templates import get_default_research_template_registry

    return get_default_research_template_registry().list_definitions()


@router.get("/{run_id}", response_model=ResearchRun)
async def get_research_run(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.get(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="研究任务不存在。") from exc


@router.post("/{run_id}/execute", response_model=ResearchRun)
async def execute_research_run(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.execute(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/resume", response_model=ResearchRun)
async def resume_research_run(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.resume(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/evidence", response_model=ResearchRun)
async def add_research_evidence(
    run_id: str,
    evidence: ResearchEvidenceInput,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRun:
    try:
        return service.add_evidence(run_id, evidence)
    except ResearchTemplateValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/{run_id}/outputs", response_model=ResearchRunOutputs)
async def get_research_outputs(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> ResearchRunOutputs:
    try:
        return service.get_outputs(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="研究任务不存在。") from exc


@router.get("/{run_id}/downloads/markdown")
async def download_research_markdown(
    run_id: str,
    service: ResearchRunService = Depends(get_research_run_service),
) -> Response:
    """Download the report projection only after all publishing gates passed."""
    try:
        content = service.export_markdown(run_id)
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
    service: ResearchRunService = Depends(get_research_run_service),
) -> Response:
    """Download the Word report projection only after all publishing gates passed."""
    try:
        content = service.export_word(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": f'attachment; filename="{run_id}.docx"'},
    )
