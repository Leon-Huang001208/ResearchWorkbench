"""
Core contracts for the timing engine (factors, event study metrics, readiness score).

This module defines Pydantic models for the timing engine, including timing factors,
event study metrics, and readiness score in AlphaFoundry.
"""
from typing import List

from pydantic import BaseModel, Field


class TimingFactors(BaseModel):
    """Timing engine v1 factors calculating current market timing fit."""

    regime: float = Field(
        ge=0.0, le=1.0, description="Market regime matching score (0=poor match, 1=ideal match)"
    )
    flow: float = Field(
        ge=0.0, le=1.0, description="Money flow state matching score (0=poor flow, 1=ideal flow)"
    )
    theme_diffusion: float = Field(
        ge=0.0,
        le=1.0,
        description="Theme diffusion stage score (0=early/too late, 1=optimal stage)",
    )
    crowding: float = Field(
        ge=0.0, le=1.0, description="Crowding score (0=extremely crowded, 1=no crowding)"
    )

    def overall_timing_fit(self) -> float:
        """Calculate aggregate timing fit score as average of all factors."""
        return (self.regime + self.flow + self.theme_diffusion + self.crowding) / 4.0


class EventStudyMetrics(BaseModel):
    """Historical event study validation metrics for similar events."""

    event_count: int = Field(ge=0, description="Number of similar historical events in the dataset")
    average_excess_return: float = Field(
        description="Average cumulative excess return over benchmark after event"
    )
    win_rate: float = Field(
        ge=0.0, le=1.0, description="Percentage of events with positive excess return"
    )
    decay_by_day: List[float] = Field(
        default_factory=list, description="Average excess return by day after entry (decay curve)"
    )
    max_drawdown_after_entry: float = Field(
        description="Maximum drawdown experienced after entry for historical events"
    )

    def historical_edge_score(self) -> float:
        """
        Normalize historical edge to 0-1 score combining win rate and average excess return.
        Scales average return relative to expected volatility and clips to 0-1.
        """
        if self.event_count == 0:
            return 0.0

        # Combine win rate with normalized excess return
        # Assume 10% annualized excess is max for normalization
        normalized_return = min(max(self.average_excess_return / 0.1, 0.0), 1.0)
        return 0.5 * self.win_rate + 0.5 * normalized_return


class ReadinessScore(BaseModel):
    """Unified readiness score combining all three dimensions."""

    thesis_quality: float = Field(
        ge=0.0, le=1.0, description="Quality score of the investment thesis itself (0-1)"
    )
    historical_edge: float = Field(
        ge=0.0, le=1.0, description="Normalized edge from similar historical events (0-1)"
    )
    timing_fit: float = Field(ge=0.0, le=1.0, description="Current market timing fit score (0-1)")
    overall_score: float = Field(
        ge=0.0, le=1.0, description="Final aggregated readiness score per the formula"
    )
    recommendation: str = Field(
        description="Human-readable recommendation: PROCEED, CAUTION, or BLOCK"
    )

    @classmethod
    def calculate(
        cls, thesis_quality: float, historical_edge: float, timing_fit: float
    ) -> "ReadinessScore":
        """Calculate overall score using the standard formula:
        readiness_score = 0.35 * thesis_quality + 0.35 * historical_edge + 0.30 * timing_fit
        """
        assert 0.0 <= thesis_quality <= 1.0
        assert 0.0 <= historical_edge <= 1.0
        assert 0.0 <= timing_fit <= 1.0

        overall_score = 0.35 * thesis_quality + 0.35 * historical_edge + 0.30 * timing_fit

        if overall_score >= 0.7:
            recommendation = "PROCEED"
        elif overall_score >= 0.5:
            recommendation = "CAUTION"
        else:
            recommendation = "BLOCK"

        return cls(
            thesis_quality=thesis_quality,
            historical_edge=historical_edge,
            timing_fit=timing_fit,
            overall_score=overall_score,
            recommendation=recommendation,
        )

    def should_block(self) -> bool:
        """Return True if candidate should be blocked due to low readiness."""
        return self.recommendation == "BLOCK"

    def get_blocking_reason(self) -> str | None:
        """Get human-readable blocking reason if candidate should be blocked."""
        if not self.should_block():
            return None

        reasons: list[str] = []
        if self.thesis_quality <= 0.4:
            reasons.append("Thesis quality is too low")
        if self.historical_edge <= 0.3:
            reasons.append("Historical edge is weak or inconsistent")
        if self.timing_fit <= 0.3:
            reasons.append("Current market timing is unfavorable")

        if not reasons:
            reasons.append(
                f"Overall readiness score {self.overall_score:.2f} below blocking threshold"
            )

        return ", ".join(reasons)
