"""Fusion of event alpha, dynamic factor alpha, timing, and risk penalties."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from core.observability import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class FusionWeights:
    """Transparent alpha fusion weights."""

    factor_weight: float = 0.40
    event_weight: float = 0.35
    timing_weight: float = 0.15
    risk_weight: float = 0.10

    def __post_init__(self) -> None:
        if (
            min(
                self.factor_weight,
                self.event_weight,
                self.timing_weight,
                self.risk_weight,
            )
            < 0
        ):
            raise ValueError("fusion weights must be non-negative")
        total_positive = self.factor_weight + self.event_weight + self.timing_weight
        if total_positive <= 0:
            raise ValueError("at least one positive alpha weight is required")


class EventFactorFusion:
    """Combine factor, event, timing, and risk signals into final alpha scores."""

    def __init__(self, weights: FusionWeights | None = None):
        self.weights = weights or FusionWeights()

    def fuse(
        self,
        factor_scores: pd.Series | dict[str, float],
        event_scores: pd.Series | dict[str, float],
        timing_readiness: float | pd.Series | dict[str, float],
        risk_penalties: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Return a bounded final alpha score for each subject."""
        factor = self._to_series(factor_scores, "factor_alpha_score")
        event = self._to_series(event_scores, "event_alpha_score")
        timing = self._timing_series(timing_readiness, factor.index.union(event.index))
        subjects = factor.index.union(event.index).union(timing.index)

        frame = pd.DataFrame(index=subjects)
        frame["factor_alpha_score"] = factor.reindex(subjects).fillna(0.0).clip(0.0, 1.0)
        frame["event_alpha_score"] = event.reindex(subjects).fillna(0.0).clip(0.0, 1.0)
        frame["timing_readiness"] = timing.reindex(subjects).fillna(0.5).clip(0.0, 1.0)
        frame["risk_penalty"] = self._risk_penalty(risk_penalties, subjects)

        raw = (
            self.weights.factor_weight * frame["factor_alpha_score"]
            + self.weights.event_weight * frame["event_alpha_score"]
            + self.weights.timing_weight * frame["timing_readiness"]
            - self.weights.risk_weight * frame["risk_penalty"]
        )
        frame["final_alpha_score"] = raw.clip(0.0, 1.0)
        frame["top_contributors"] = frame.apply(self._top_contributors, axis=1)

        logger.info("event-factor fusion completed", subject_count=len(frame.index))
        return frame.sort_values("final_alpha_score", ascending=False)

    @staticmethod
    def _to_series(values: pd.Series | dict[str, float], name: str) -> pd.Series:
        if isinstance(values, pd.Series):
            return values.astype(float).rename(name)
        return pd.Series(values, dtype=float, name=name)

    @staticmethod
    def _timing_series(
        timing_readiness: float | pd.Series | dict[str, float],
        subjects: pd.Index,
    ) -> pd.Series:
        if isinstance(timing_readiness, pd.Series):
            return timing_readiness.astype(float).rename("timing_readiness")
        if isinstance(timing_readiness, dict):
            return pd.Series(timing_readiness, dtype=float, name="timing_readiness")
        return pd.Series(float(timing_readiness), index=subjects, name="timing_readiness")

    @staticmethod
    def _risk_penalty(
        risk_penalties: pd.DataFrame | None,
        subjects: pd.Index,
    ) -> pd.Series:
        if risk_penalties is None or risk_penalties.empty:
            return pd.Series(0.0, index=subjects, name="risk_penalty")
        aligned = risk_penalties.reindex(subjects).fillna(0.0).clip(0.0, 1.0)
        return aligned.mean(axis=1).rename("risk_penalty")

    @staticmethod
    def _top_contributors(row: pd.Series) -> list[str]:
        contributions = {
            "factor_alpha_score": float(row["factor_alpha_score"]),
            "event_alpha_score": float(row["event_alpha_score"]),
            "timing_readiness": float(row["timing_readiness"]),
            "risk_penalty": -float(row["risk_penalty"]),
        }
        return [
            name
            for name, _ in sorted(
                contributions.items(),
                key=lambda item: abs(item[1]),
                reverse=True,
            )
        ][:3]
