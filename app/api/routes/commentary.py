"""Commentary production API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.contracts.commentary import (
    CommentaryContextPack,
    CommentaryDraftRequest,
    CommentaryDraftResponse,
    CommentaryQualityCheckRequest,
    CommentaryQualityCheckResponse,
    CommentaryRecipeCatalog,
    CommentaryRunRecord,
    CommentaryRunRecordRequest,
    CommentaryRunRecordResponse,
    CommentarySectionRewriteRequest,
    CommentarySectionRewriteResponse,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.commentary_context_service import CommentaryContextService
from services.commentary_draft_service import CommentaryDraftService, get_commentary_recipe_catalog
from services.commentary_run_service import CommentaryRunService
from services.dashboard_service import DashboardService

logger = get_logger(__name__)

router = APIRouter(prefix="/api/commentary", tags=["commentary"])


def get_commentary_context_service(
    db: Session = Depends(get_db),
) -> CommentaryContextService:
    """Build a request-scoped commentary context service."""
    return CommentaryContextService(DashboardService(db))


def get_commentary_draft_service() -> CommentaryDraftService:
    """Build a request-scoped commentary draft service."""
    from core.model_gateway import ModelGatewayImpl

    return CommentaryDraftService(ModelGatewayImpl())


def get_commentary_run_service() -> CommentaryRunService:
    """Build a commentary run log service."""
    return CommentaryRunService()


@router.get("/recipes", response_model=CommentaryRecipeCatalog)
async def get_commentary_recipes() -> CommentaryRecipeCatalog:
    """Return shared commentary recipes used by the workbench and draft service."""
    return get_commentary_recipe_catalog()


@router.get("/context", response_model=CommentaryContextPack)
async def get_commentary_context(
    recipe_id: str = Query("daily-close", description="Commentary recipe id"),
    service: CommentaryContextService = Depends(get_commentary_context_service),
) -> CommentaryContextPack:
    """Return market data and evidence prefill content for commentary writing."""
    try:
        return service.build_context(recipe_id=recipe_id)
    except Exception as exc:
        logger.exception("commentary_context_api_failed", recipe_id=recipe_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to build commentary context",
        ) from exc


@router.post("/draft", response_model=CommentaryDraftResponse)
async def generate_commentary_draft(
    request: CommentaryDraftRequest,
    service: CommentaryDraftService = Depends(get_commentary_draft_service),
) -> CommentaryDraftResponse:
    """Generate an editable commentary draft from prepared data and evidence."""
    try:
        return service.generate_draft(request)
    except Exception as exc:
        logger.exception("commentary_draft_api_failed", recipe_id=request.recipe_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate commentary draft",
        ) from exc


@router.post("/section-rewrite", response_model=CommentarySectionRewriteResponse)
async def rewrite_commentary_section(
    request: CommentarySectionRewriteRequest,
    service: CommentaryDraftService = Depends(get_commentary_draft_service),
) -> CommentarySectionRewriteResponse:
    """Rewrite one editable commentary section with the current evidence context."""
    try:
        context = CommentaryDraftRequest(
            recipe_id=request.recipe_id,
            data_snapshot_text=request.data_snapshot_text,
            evidence_pack_text=request.evidence_pack_text,
            subjective_judgement=request.subjective_judgement,
            evidence_items=request.evidence_items,
            attribution_signals=request.attribution_signals,
            writing_preferences=request.writing_preferences,
        )
        return service.rewrite_section(
            recipe_id=request.recipe_id,
            section_heading=request.section_heading,
            section_content=request.section_content,
            action=request.action,
            context=context,
        )
    except Exception as exc:
        logger.exception(
            "commentary_section_rewrite_api_failed",
            recipe_id=request.recipe_id,
            section_heading=request.section_heading,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to rewrite commentary section",
        ) from exc


@router.post("/quality-check", response_model=CommentaryQualityCheckResponse)
async def check_commentary_quality(
    request: CommentaryQualityCheckRequest,
    service: CommentaryDraftService = Depends(get_commentary_draft_service),
) -> CommentaryQualityCheckResponse:
    """Run publish-gate quality checks for an editable commentary draft."""
    try:
        context = CommentaryDraftRequest(
            recipe_id=request.recipe_id,
            data_snapshot_text=request.data_snapshot_text,
            evidence_pack_text=request.evidence_pack_text,
            subjective_judgement=request.subjective_judgement,
            evidence_items=request.evidence_items,
            attribution_signals=request.attribution_signals,
            writing_preferences=request.writing_preferences,
        )
        return service.check_quality(
            draft_markdown=request.draft_markdown,
            context=context,
        )
    except Exception as exc:
        logger.exception(
            "commentary_quality_check_api_failed",
            recipe_id=request.recipe_id,
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to check commentary quality",
        ) from exc


@router.post("/runs", response_model=CommentaryRunRecordResponse)
async def record_commentary_run(
    request: CommentaryRunRecordRequest,
    service: CommentaryRunService = Depends(get_commentary_run_service),
) -> CommentaryRunRecordResponse:
    """Persist one commentary generation run."""
    try:
        return service.record_run(request)
    except Exception as exc:
        logger.exception("commentary_run_record_api_failed", recipe_id=request.recipe_id)
        raise HTTPException(
            status_code=500,
            detail="Failed to record commentary run",
        ) from exc


@router.get("/runs", response_model=list[CommentaryRunRecord])
async def list_commentary_runs(
    limit: int = Query(20, ge=1, le=100),
    service: CommentaryRunService = Depends(get_commentary_run_service),
) -> list[CommentaryRunRecord]:
    """Return recent commentary generation runs."""
    try:
        return service.list_runs(limit=limit)
    except Exception as exc:
        logger.exception("commentary_run_list_api_failed")
        raise HTTPException(
            status_code=500,
            detail="Failed to list commentary runs",
        ) from exc
