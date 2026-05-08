"""Timing Engine and Event Study validation API routes"""
from fastapi import APIRouter, Depends

from core.contracts.timing_engine import (
    TimingFactors,
    EventStudyMetrics,
    ReadinessScore,
)
from core.services.timing_engine_service import TimingEngineService
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/timing-engine", tags=["timing-engine"])


def get_timing_engine_service() -> TimingEngineService:
    """Get TimingEngineService instance with schema check"""
    try:
        from data_layer.repositories.base import ensure_schema
        ensure_schema()
    except Exception as e:
        logger.warning(f"ensure_schema failed: {e}")
    return TimingEngineService()


@router.post("/calculate-timing-fit", response_model=TimingFactors)
async def calculate_timing_fit(
    regime: float,
    flow: float,
    theme_diffusion: float,
    crowding: float,
    service: TimingEngineService = Depends(get_timing_engine_service),
):
    """Calculate timing factors and get overall timing fit"""
    return service.calculate_timing_fit(
        regime=regime,
        flow=flow,
        theme_diffusion=theme_diffusion,
        crowding=crowding
    )


@router.post("/calculate-historical-edge", response_model=EventStudyMetrics)
async def calculate_historical_edge(
    event_count: int,
    average_excess_return: float,
    win_rate: float,
    max_drawdown_after_entry: float,
    decay_by_day: list[float] | None = None,
    service: TimingEngineService = Depends(get_timing_engine_service),
):
    """Calculate historical edge from event study metrics"""
    return service.calculate_historical_edge(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry
    )


@router.post("/calculate-readiness", response_model=ReadinessScore)
async def calculate_readiness_score(
    thesis_quality: float,
    event_count: int,
    average_excess_return: float,
    win_rate: float,
    max_drawdown_after_entry: float,
    regime: float,
    flow: float,
    theme_diffusion: float,
    crowding: float,
    decay_by_day: list[float] | None = None,
    service: TimingEngineService = Depends(get_timing_engine_service),
):
    """Calculate unified readiness score combining all three dimensions"""
    historical_metrics = service.calculate_historical_edge(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry
    )
    timing_factors = service.calculate_timing_fit(
        regime=regime,
        flow=flow,
        theme_diffusion=theme_diffusion,
        crowding=crowding
    )
    return service.calculate_readiness(
        thesis_quality=thesis_quality,
        historical_metrics=historical_metrics,
        timing_factors=timing_factors
    )


@router.post("/check-blocking-rule")
async def check_candidate_blocking(
    thesis_quality: float,
    event_count: int,
    average_excess_return: float,
    win_rate: float,
    max_drawdown_after_entry: float,
    regime: float,
    flow: float,
    theme_diffusion: float,
    crowding: float,
    decay_by_day: list[float] | None = None,
    service: TimingEngineService = Depends(get_timing_engine_service),
):
    """Check if candidate should be blocked based on readiness score"""
    historical_metrics = service.calculate_historical_edge(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry
    )
    timing_factors = service.calculate_timing_fit(
        regime=regime,
        flow=flow,
        theme_diffusion=theme_diffusion,
        crowding=crowding
    )
    readiness = service.calculate_readiness(
        thesis_quality=thesis_quality,
        historical_metrics=historical_metrics,
        timing_factors=timing_factors
    )
    should_block = service.should_block_candidate(readiness)
    reason = service.get_candidate_blocking_reason(readiness) if should_block else None
    
    return {
        "should_block": should_block,
        "readiness_score": readiness.overall_score,
        "recommendation": readiness.recommendation,
        "block_reason": reason
    }
