"""Commentary production API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from core.contracts.commentary import (
    CommentaryContextPack,
    CommentaryDraftRequest,
    CommentaryDraftResponse,
)
from core.model_gateway import ModelGatewayImpl
from core.observability import get_logger
from data_layer.repositories.base import get_db
from services.commentary_context_service import CommentaryContextService
from services.commentary_draft_service import CommentaryDraftService
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
    return CommentaryDraftService(ModelGatewayImpl())


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
