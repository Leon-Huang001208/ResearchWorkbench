
"""Timing API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from timing_engine import (
    MetaTimingEngine,
    TimingModelRegistry,
    TimingContext,
    TimingModelScore,
    TimingDecision,
    MarketRegime,
)
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/timing", tags=["timing"])

timing_engine = MetaTimingEngine()
timing_registry = TimingModelRegistry()


class EvaluateRequest(BaseModel):
    scores: List[TimingModelScore]
    signal_id: Optional[str] = None
    market_regime: MarketRegime = "unknown"


class EvaluateSignalRequest(BaseModel):
    signal_id: str


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
async def evaluate_signal(signal_id: str):
    """Evaluate timing for an existing signal"""
    try:
        # TODO: Retrieve signal from repository and build TimingContext
        context = TimingContext(signal_id=signal_id)
        model_scores = timing_registry.score_all(context)
        decision = timing_engine.evaluate(model_scores, signal_id=signal_id)
        return decision
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

