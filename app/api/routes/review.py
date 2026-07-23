"""审核路由"""

from typing import List

from fastapi import APIRouter, Depends, HTTPException

from app.api.models import (
    ErrorResponse,
    ReviewActionResponse,
    ReviewItemResponse,
    ReviewStatsResponse,
)
from services.review_service import ReviewService

router = APIRouter(prefix="/api/review", tags=["review"])


def get_review_service() -> ReviewService:
    """获取审核服务实例，确保数据库 schema 就绪"""
    try:
        from data_layer.repositories.base import ensure_schema

        ensure_schema()
    except Exception as e:
        from core.observability import get_logger

        get_logger(__name__).warning(f"ensure_schema failed: {e}")
    return ReviewService()


@router.get(
    "/pending",
    response_model=List[ReviewItemResponse],
)
async def list_pending(
    limit: int = 100,
    service: ReviewService = Depends(get_review_service),
):
    """列出待审核项"""
    assertions = service.list_pending_assertions(limit=limit)
    return [
        ReviewItemResponse(
            assertion_id=a.assertion_id,
            subject_entity_id=a.subject_entity_id,
            predicate=a.predicate,
            confidence=a.confidence,
            source_doc_id=a.source_doc_id,
            reviewer_status=a.reviewer_status,
            reviewer=a.reviewer,
        )
        for a in assertions
    ]


@router.post(
    "/approve/{item_id}",
    response_model=ReviewActionResponse,
    responses={404: {"model": ErrorResponse}},
)
async def approve_item(
    item_id: str,
    reviewer: str = "api",
    service: ReviewService = Depends(get_review_service),
):
    """批准审核项"""
    success = service.approve_assertion(item_id, reviewer=reviewer)
    if not success:
        raise HTTPException(status_code=404, detail=f"Assertion {item_id} not found")
    return ReviewActionResponse(
        item_id=item_id,
        action="approved",
        success=True,
        message="Assertion approved",
    )


@router.post(
    "/reject/{item_id}",
    response_model=ReviewActionResponse,
    responses={404: {"model": ErrorResponse}},
)
async def reject_item(
    item_id: str,
    reviewer: str = "api",
    service: ReviewService = Depends(get_review_service),
):
    """拒绝审核项"""
    success = service.reject_assertion(item_id, reviewer=reviewer)
    if not success:
        raise HTTPException(status_code=404, detail=f"Assertion {item_id} not found")
    return ReviewActionResponse(
        item_id=item_id,
        action="rejected",
        success=True,
        message="Assertion rejected",
    )


@router.get(
    "/stats",
    response_model=ReviewStatsResponse,
)
async def review_stats(
    service: ReviewService = Depends(get_review_service),
):
    """审核统计"""
    stats = service.get_statistics()
    return ReviewStatsResponse(**stats)
