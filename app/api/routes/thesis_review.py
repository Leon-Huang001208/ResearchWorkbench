"""Thesis Review routes - Bull/Bear/Skeptic structured review endpoints"""
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.contracts import (
    CognitiveBlackboard,
    ConflictDetectionSummary,
    EvidenceReference,
    ThesisCard,
)
from services.thesis_review_service import ThesisReviewService

router = APIRouter(prefix="/api/thesis-review", tags=["thesis-review"])


def get_thesis_review_service() -> ThesisReviewService:
    """Dependency injection for ThesisReviewService"""
    return ThesisReviewService()


@router.post(
    "/generate-full-review",
    response_model=Dict[str, Any],
    responses={400: {"description": "Bad request - missing required data"}},
)
async def generate_full_review(
    thesis: ThesisCard,
    available_evidence: list[EvidenceReference],
    service: ThesisReviewService = Depends(get_thesis_review_service),
):
    """Generate full three-position (Bull/Bear/Skeptic) review with conflict detection"""
    if not thesis:
        raise HTTPException(status_code=400, detail="ThesisCard is required")
    if not available_evidence:
        raise HTTPException(status_code=400, detail="At least one piece of evidence is required")

    result = service.generate_full_review(thesis, available_evidence)

    # Convert Pydantic models to dict for JSON response
    return {
        "thesis_id": result["thesis_id"],
        "bull_review": result["bull_review"].model_dump(),
        "bear_review": result["bear_review"].model_dump(),
        "skeptic_review": result["skeptic_review"].model_dump(),
        "cognitive_blackboard": result["cognitive_blackboard"].model_dump(),
        "conflict_summary": result["conflict_summary"].model_dump(),
    }


@router.post(
    "/detect-conflicts",
    response_model=ConflictDetectionSummary,
)
async def detect_conflicts(
    blackboard: CognitiveBlackboard,
    service: ThesisReviewService = Depends(get_thesis_review_service),
):
    """Detect conflicts in the cognitive blackboard and check hard rules"""
    return service.detect_conflicts(blackboard)
