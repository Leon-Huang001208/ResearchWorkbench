from core.contracts.timing_engine import (
    TimingFactors,
    EventStudyMetrics,
    ReadinessScore,
)
from core.observability import get_logger

logger = get_logger(__name__)


class TimingEngineService:
    """Service for calculating timing fit and unified readiness score."""

    def __init__(self):
        logger.info("TimingEngineService initialized")

    def calculate_timing_fit(
        self,
        regime: float,
        flow: float,
        theme_diffusion: float,
        crowding: float
    ) -> TimingFactors:
        """Create TimingFactors and calculate overall timing fit score."""
        timing_factors = TimingFactors(
            regime=regime,
            flow=flow,
            theme_diffusion=theme_diffusion,
            crowding=crowding
        )
        overall_fit = timing_factors.overall_timing_fit()
        logger.debug(
            f"Calculated timing fit: {overall_fit:.3f} "
            f"(regime={regime}, flow={flow}, theme={theme_diffusion}, crowding={crowding})"
        )
        return timing_factors

    def calculate_historical_edge(
        self,
        event_count: int,
        average_excess_return: float,
        win_rate: float,
        max_drawdown_after_entry: float,
        decay_by_day: list[float] | None = None,
    ) -> EventStudyMetrics:
        """Create EventStudyMetrics and calculate normalized historical edge score."""
        metrics = EventStudyMetrics(
            event_count=event_count,
            average_excess_return=average_excess_return,
            win_rate=win_rate,
            decay_by_day=decay_by_day or [],
            max_drawdown_after_entry=max_drawdown_after_entry
        )
        edge_score = metrics.historical_edge_score()
        logger.debug(
            f"Calculated historical edge: {edge_score:.3f} from {event_count} events, "
            f"avg_excess={average_excess_return:.3f}, win_rate={win_rate:.3f}"
        )
        return metrics

    def calculate_readiness(
        self,
        thesis_quality: float,
        historical_metrics: EventStudyMetrics,
        timing_factors: TimingFactors
    ) -> ReadinessScore:
        """Calculate unified readiness score combining all three dimensions."""
        historical_edge = historical_metrics.historical_edge_score()
        timing_fit = timing_factors.overall_timing_fit()
        readiness = ReadinessScore.calculate(
            thesis_quality=thesis_quality,
            historical_edge=historical_edge,
            timing_fit=timing_fit
        )
        logger.info(
            f"Calculated readiness: overall={readiness.overall_score:.3f}, "
            f"recommendation={readiness.recommendation} "
            f"(thesis={thesis_quality}, historical_edge={historical_edge:.3f}, timing_fit={timing_fit:.3f})"
        )
        return readiness

    def should_block_candidate(self, readiness: ReadinessScore) -> bool:
        """Return True if candidate should be blocked due to low readiness."""
        should_block = readiness.recommendation == "BLOCK"
        if should_block:
            logger.warning(
                f"Candidate blocked due to low readiness score: {readiness.overall_score:.3f}"
            )
        return should_block

    def get_candidate_blocking_reason(self, readiness: ReadinessScore) -> str | None:
        """Get human-readable blocking reason if candidate should be blocked."""
        if not self.should_block_candidate(readiness):
            return None

        reasons: list[str] = []
        if readiness.thesis_quality <= 0.4:
            reasons.append("Thesis quality is too low")
        if readiness.historical_edge <= 0.3:
            reasons.append("Historical edge is weak or inconsistent")
        if readiness.timing_fit <= 0.3:
            reasons.append("Current market timing is unfavorable")

        if not reasons:
            reasons.append(f"Overall readiness score {readiness.overall_score:.2f} below blocking threshold")

        return ", ".join(reasons)
