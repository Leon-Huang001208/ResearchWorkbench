"""Timing Engine and Event Study validation API routes"""
from fastapi import APIRouter, Depends

from core.contracts.timing_engine import EventStudyMetrics, ReadinessScore, TimingFactors
from core.observability import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/api/timing-engine", tags=["timing-engine"])


def ensure_schema_silent():
    """Ensure schema exists but don't fail if it can't"""
    try:
        from data_layer.repositories.base import ensure_schema

        ensure_schema()
    except Exception as e:
        logger.warning(f"ensure_schema failed: {e}")


@router.post("/calculate-timing-fit", response_model=TimingFactors)
async def calculate_timing_fit(
    regime: float,
    flow: float,
    theme_diffusion: float,
    crowding: float,
):
    """Calculate timing factors and get overall timing fit"""
    ensure_schema_silent()
    timing_factors = TimingFactors(
        regime=regime, flow=flow, theme_diffusion=theme_diffusion, crowding=crowding
    )
    overall_fit = timing_factors.overall_timing_fit()
    logger.debug(
        f"Calculated timing fit: {overall_fit:.3f} "
        f"(regime={regime}, flow={flow}, theme={theme_diffusion}, crowding={crowding})"
    )
    return timing_factors


@router.post("/calculate-historical-edge", response_model=EventStudyMetrics)
async def calculate_historical_edge(
    event_count: int,
    average_excess_return: float,
    win_rate: float,
    max_drawdown_after_entry: float,
    decay_by_day: list[float] | None = None,
):
    """Calculate historical edge from event study metrics"""
    ensure_schema_silent()
    metrics = EventStudyMetrics(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry,
    )
    edge_score = metrics.historical_edge_score()
    logger.debug(
        f"Calculated historical edge: {edge_score:.3f} from {event_count} events, "
        f"avg_excess={average_excess_return:.3f}, win_rate={win_rate:.3f}"
    )
    return metrics


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
):
    """Calculate unified readiness score combining all three dimensions"""
    ensure_schema_silent()
    historical_metrics = EventStudyMetrics(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry,
    )
    timing_factors = TimingFactors(
        regime=regime, flow=flow, theme_diffusion=theme_diffusion, crowding=crowding
    )
    readiness = ReadinessScore.calculate(
        thesis_quality=thesis_quality,
        historical_edge=historical_metrics.historical_edge_score(),
        timing_fit=timing_factors.overall_timing_fit(),
    )
    logger.info(
        f"Calculated readiness: overall={readiness.overall_score:.3f}, "
        f"recommendation={readiness.recommendation} "
        f"(thesis={thesis_quality}, historical_edge={readiness.historical_edge:.3f}, timing_fit={readiness.timing_fit:.3f})"
    )
    return readiness


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
):
    """Check if candidate should be blocked based on readiness score"""
    ensure_schema_silent()
    historical_metrics = EventStudyMetrics(
        event_count=event_count,
        average_excess_return=average_excess_return,
        win_rate=win_rate,
        decay_by_day=decay_by_day or [],
        max_drawdown_after_entry=max_drawdown_after_entry,
    )
    timing_factors = TimingFactors(
        regime=regime, flow=flow, theme_diffusion=theme_diffusion, crowding=crowding
    )
    readiness = ReadinessScore.calculate(
        thesis_quality=thesis_quality,
        historical_edge=historical_metrics.historical_edge_score(),
        timing_fit=timing_factors.overall_timing_fit(),
    )
    should_block = readiness.should_block()
    reason = readiness.get_blocking_reason() if should_block else None

    if should_block:
        logger.warning(
            f"Candidate blocked due to low readiness score: {readiness.overall_score:.3f}"
        )

    return {
        "should_block": should_block,
        "readiness_score": readiness.overall_score,
        "recommendation": readiness.recommendation,
        "block_reason": reason,
    }
