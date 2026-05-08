"""Timing API"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from timing_engine import (
    MetaTimingEngine,
    TimingModelRegistry,
    TimingContext,
    TimingModelScore,
    TimingDecision,
    MarketRegime,
)
from core.observability import get_logger
from data_layer.repositories.base import get_db
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from data_layer.repositories.timing_repository import TimingRepositoryImpl

logger = get_logger(__name__)
router = APIRouter(prefix="/api/timing", tags=["timing"])

timing_engine = MetaTimingEngine()
timing_registry = TimingModelRegistry()

# 模块级单例
_timing_repo: TimingRepositoryImpl | None = None
_signal_repo: SignalRepositoryImpl | None = None


class EvaluateRequest(BaseModel):
    scores: List[TimingModelScore]
    signal_id: Optional[str] = None
    market_regime: MarketRegime = "unknown"


class EvaluateSignalRequest(BaseModel):
    signal_id: str


def get_timing_repo(db: Session = Depends(get_db)) -> TimingRepositoryImpl:
    """获取 Timing 仓储实例（单例 + 请求级 DB session）"""
    global _timing_repo
    if _timing_repo is None:
        _timing_repo = TimingRepositoryImpl(db)
    else:
        _timing_repo.db = db
    return _timing_repo


def get_signal_repo(db: Session = Depends(get_db)) -> SignalRepositoryImpl:
    """获取 Signal 仓储实例（单例 + 请求级 DB session）"""
    global _signal_repo
    if _signal_repo is None:
        _signal_repo = SignalRepositoryImpl(db)
    else:
        _signal_repo.db = db
    return _signal_repo


def _reset_timing_services():
    """重置模块级单例（仅用于测试）"""
    global _timing_repo, _signal_repo
    _timing_repo = None
    _signal_repo = None


@router.post("/evaluate", response_model=TimingDecision)
async def evaluate(request: EvaluateRequest):
    """Given model scores, return TimingDecision"""
    try:
        decision = timing_engine.evaluate(
            request.scores,
            signal_id=request.signal_id,
            market_regime=request.market_regime,
        )
        return decision
    except Exception as e:
        logger.error(f"Timing evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate-signal/{signal_id}", response_model=TimingDecision)
async def evaluate_signal(
    signal_id: str,
    signal_repo: SignalRepositoryImpl = Depends(get_signal_repo),
    timing_repo: TimingRepositoryImpl = Depends(get_timing_repo),
):
    """Evaluate timing for an existing signal"""
    try:
        # Retrieve signal from repository
        signal = signal_repo.get(signal_id)
        if signal is None:
            raise HTTPException(status_code=404, detail=f"Signal {signal_id} not found")

        # Build TimingContext from the persisted signal
        context = TimingContext(
            signal_id=signal_id,
            event_signal=signal.model_dump() if hasattr(signal, "model_dump") else {},
        )
        model_scores = timing_registry.score_all(context)
        decision = timing_engine.evaluate(model_scores, signal_id=signal_id)
        # Persist the timing decision
        decision = timing_repo.save(decision)
        return decision
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signal timing evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/regime-weights/{regime}", response_model=dict)
async def get_regime_weights(regime: MarketRegime):
    """Get model weights for a given market regime"""
    try:
        weights = timing_engine.weights_for_regime(regime)
        return {"regime": regime, "weights": weights}
    except Exception as e:
        logger.error(f"Failed to get regime weights: {e}")
        raise HTTPException(status_code=500, detail=str(e))
