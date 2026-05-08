"""Outcome 评估协议 API 路由"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.models import ErrorResponse
from core.contracts.outcomes import SignalOutcome
from core.services.outcome_service import OutcomeService

router = APIRouter(prefix="/api/outcomes", tags=["outcomes"])


def get_outcome_service() -> OutcomeService:
    """获取 OutcomeService 实例（内存版）"""
    if not hasattr(get_outcome_service, "_instance"):
        get_outcome_service._instance = OutcomeService()
    return get_outcome_service._instance


# ─── SignalOutcome 路由 ─────────────────────────────────────────────────


@router.post(
    "/record",
    response_model=SignalOutcome,
    responses={500: {"model": ErrorResponse}},
)
async def record_outcome(
    outcome: SignalOutcome,
    service: OutcomeService = Depends(get_outcome_service),
):
    """记录信号结果评估"""
    try:
        return service.record_outcome(outcome)
    except Exception as e:
        from core.observability import get_logger
        logger = get_logger(__name__)
        logger.error("Failed to record outcome", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/aggregate/list",
    response_model=list[SignalOutcome],
)
async def list_outcomes(
    event_type: Optional[str] = Query(None),
    strategy_family: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: OutcomeService = Depends(get_outcome_service),
):
    """聚合查询结果评估（支持 event_type, strategy_family 过滤）"""
    return service.list_outcomes(
        event_type=event_type,
        strategy_family=strategy_family,
        limit=limit,
    )


@router.get(
    "/{signal_id}",
    response_model=SignalOutcome,
    responses={404: {"model": ErrorResponse}},
)
async def get_outcome_by_signal(
    signal_id: str,
    service: OutcomeService = Depends(get_outcome_service),
):
    """按 signal_id 查询结果评估"""
    outcome = service.get_outcome_by_signal(signal_id)
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"Outcome for signal {signal_id} not found")
    return outcome


@router.patch(
    "/{outcome_id}/lesson",
    response_model=SignalOutcome,
    responses={404: {"model": ErrorResponse}},
)
async def update_lesson(
    outcome_id: str,
    lesson: str = Query(..., description="Updated lesson text"),
    service: OutcomeService = Depends(get_outcome_service),
):
    """更新教训字段"""
    outcome = service.update_lesson(outcome_id, lesson)
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"Outcome {outcome_id} not found")
    return outcome
