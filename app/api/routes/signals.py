"""信号路由"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.models import (
    ErrorResponse,
    SignalCreateRequest,
    SignalPromoteResponse,
    SignalResponse,
    SignalValidateResponse,
)
from data_layer.repositories.base import get_db
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.signal_service import SignalService

router = APIRouter(prefix="/api/signals", tags=["signals"])

# 模块级单例：SignalService 只创建一次，repository 的 db session 每次请求更新
_signal_service: SignalService | None = None


def get_signal_service(db: Session = Depends(get_db)) -> SignalService:
    """获取信号服务实例（单例 + 请求级 DB session）"""
    global _signal_service
    if _signal_service is None:
        repo = SignalRepositoryImpl(db)
        _signal_service = SignalService(repository=repo)
    else:
        # 每次请求更新 repository 的 db session
        if _signal_service.repository:
            _signal_service.repository.db = db
    return _signal_service


def _reset_signal_service():
    """重置模块级单例（仅用于测试）"""
    global _signal_service
    _signal_service = None


@router.post(
    "/create",
    response_model=SignalResponse,
    responses={500: {"model": ErrorResponse}},
)
async def create_signal(
    request: SignalCreateRequest,
    service: SignalService = Depends(get_signal_service),
):
    """创建信号"""
    try:
        signal = service.create_signal(
            subject_id=request.subject_id,
            thesis=request.thesis,
            horizon=request.horizon,
            score=request.score,
            confidence=request.confidence,
            scenario_refs=request.scenario_refs,
            evidence_refs=request.evidence_refs,
            status=request.status,
        )
        return SignalResponse(
            signal_id=signal.signal_id,
            subject_id=signal.subject_id,
            horizon=signal.horizon,
            thesis=signal.thesis,
            score=signal.score,
            confidence=signal.confidence,
            scenario_refs=signal.scenario_refs,
            evidence_refs=signal.evidence_refs,
            status=signal.status,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/list",
    response_model=List[SignalResponse],
)
async def list_signals(
    status: Optional[str] = Query(None),
    subject_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    service: SignalService = Depends(get_signal_service),
):
    """列出信号"""
    signals = service.list_signals(status=status, subject_id=subject_id, limit=limit)
    return [
        SignalResponse(
            signal_id=s.signal_id,
            subject_id=s.subject_id,
            horizon=s.horizon,
            thesis=s.thesis,
            score=s.score,
            confidence=s.confidence,
            scenario_refs=s.scenario_refs,
            evidence_refs=s.evidence_refs,
            status=s.status,
        )
        for s in signals
    ]


@router.post(
    "/validate/{signal_id}",
    response_model=SignalValidateResponse,
    responses={404: {"model": ErrorResponse}},
)
async def validate_signal(
    signal_id: str,
    service: SignalService = Depends(get_signal_service),
):
    """验证信号"""
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")
    try:
        result = service.validate_signal(signal)
        return SignalValidateResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/promote/{signal_id}",
    response_model=SignalPromoteResponse,
    responses={404: {"model": ErrorResponse}},
)
async def promote_signal(
    signal_id: str,
    new_status: str = "candidate",
    service: SignalService = Depends(get_signal_service),
):
    """升级信号状态"""
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    old_status = signal.status
    updated = service.promote_signal(signal_id, new_status=new_status)
    if updated is None:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot promote signal from {old_status} to {new_status}",
        )
    return SignalPromoteResponse(
        signal_id=signal_id,
        old_status=old_status,
        new_status=new_status,
        success=True,
        message=f"Signal promoted from {old_status} to {new_status}",
    )


@router.get(
    "/{signal_id}/detail",
    responses={404: {"model": ErrorResponse}},
)
async def get_signal_detail(
    signal_id: str,
    service: SignalService = Depends(get_signal_service),
):
    """获取信号完整详情：基本信息、关联事件、择时建议、关联 Outcome、审核历史"""
    signal = service.get_signal(signal_id)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

    from core.observability import get_logger

    logger = get_logger(__name__)

    result: dict = {
        "signal": {
            "signal_id": signal.signal_id,
            "subject_id": signal.subject_id,
            "horizon": signal.horizon,
            "thesis": signal.thesis,
            "score": signal.score,
            "confidence": signal.confidence,
            "scenario_refs": signal.scenario_refs,
            "evidence_refs": signal.evidence_refs,
            "status": signal.status,
        },
        "event": None,
        "timing": None,
        "outcome": None,
        "audit_trail": [],
    }

    # EventAlphaSignal 特有字段
    if hasattr(signal, "event_id") and signal.event_id:
        result["signal"]["event_id"] = signal.event_id
        result["signal"]["event_type"] = signal.event_type
        result["signal"]["diffusion_stage"] = signal.diffusion_stage
        result["signal"]["market_regime"] = signal.market_regime
        result["signal"]["validation_status"] = signal.validation_status

        # 关联 CanonicalEvent
        try:
            from data_layer.repositories.base import SessionLocal
            from data_layer.repositories.models import CanonicalEvent

            db = SessionLocal()
            try:
                event = (
                    db.query(CanonicalEvent)
                    .filter(CanonicalEvent.event_id == signal.event_id)
                    .first()
                )
                if event:
                    result["event"] = {
                        "event_id": event.event_id,
                        "event_type": event.event_type,
                        "summary": event.summary,
                        "event_time": event.event_time.isoformat() if event.event_time else None,
                        "impact_direction": event.impact_direction,
                        "confidence": float(event.confidence),
                    }
            finally:
                db.close()
        except Exception as e:
            logger.warning(f"Failed to load canonical event: {e}")

    # 择时建议
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.timing_repository import TimingRepositoryImpl

        db = SessionLocal()
        try:
            timing_repo = TimingRepositoryImpl(db)
            timing = timing_repo.get_latest_for_signal(signal_id)
            if timing:
                result["timing"] = {
                    "decision_id": timing.decision_id,
                    "action": timing.action,
                    "readiness_score": timing.readiness_score,
                    "market_regime": timing.market_regime,
                    "blockers": timing.blockers,
                    "rationale": timing.rationale,
                }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load timing decision: {e}")

    # 关联 Outcome
    try:
        from data_layer.repositories.base import SessionLocal
        from data_layer.repositories.outcome_repository import OutcomeRepositoryImpl

        db = SessionLocal()
        try:
            outcome_repo = OutcomeRepositoryImpl(db)
            outcome = outcome_repo.get_by_signal_id(signal_id)
            if outcome:
                result["outcome"] = {
                    "outcome_id": outcome.outcome_id,
                    "outcome_return": outcome.outcome_return,
                    "outcome_excess_return": outcome.outcome_excess_return,
                    "max_drawdown": outcome.max_drawdown,
                    "lesson": outcome.lesson,
                    "evaluated_at": (
                        outcome.evaluated_at.isoformat() if outcome.evaluated_at else None
                    ),
                }
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load outcome: {e}")

    # 审核历史
    try:
        from data_layer.repositories.audit_repository import AuditRepositoryImpl
        from data_layer.repositories.base import SessionLocal
        from services.audit_service import AuditService

        db = SessionLocal()
        try:
            audit_repo = AuditRepositoryImpl(db)
            audit_service = AuditService(repository=audit_repo)
            result["audit_trail"] = audit_service.get_trail("signal", signal_id)
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Failed to load audit trail: {e}")

    return result
