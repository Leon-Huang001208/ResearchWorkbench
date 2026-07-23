"""预期差模型。"""

from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class ExpectationGapModel(BaseTimingModel):
    model_name = "expectation_gap"

    def score(self, context: TimingContext) -> TimingModelScore:
        """预期差评分。"""
        confidence = 0.4
        score = 0.5
        rationale = "Expectation gap assessment based on available data"
        evidence_refs = []

        # Check agent views or event signal for expectation gaps
        if context.agent_views:
            confidence = 0.7
            evidence_refs.append("agent_views")
            # Compute bull/bear ratio from agent views
            bullish = sum(1 for v in context.agent_views if v.get("direction") == "bullish")
            bearish = sum(1 for v in context.agent_views if v.get("direction") == "bearish")
            total_directional = bullish + bearish or 1
            bull_ratio = bullish / total_directional

            # Contrarian: if market is bullish but agents lean bearish, or vice versa
            event_direction = (
                context.event_signal.get("impact_direction", "") if context.event_signal else ""
            )
            market_is_bullish = event_direction == "positive"
            agent_is_bullish = bull_ratio >= 0.5

            if market_is_bullish != agent_is_bullish:
                score = 0.8
                rationale = (
                    f"High expectation gap: bull ratio={bull_ratio:.2f} diverges from "
                    f"market direction ({event_direction})"
                )
            elif abs(bull_ratio - 0.5) < 0.15:
                score = 0.6
                rationale = f"Moderate expectation gap: split views (bull ratio={bull_ratio:.2f})"
            else:
                score = 0.4
                rationale = f"Low expectation gap: consensus aligned (bull ratio={bull_ratio:.2f})"
        elif context.event_signal:
            confidence = 0.6
            evidence_refs.append("event_signal")
            # Check if event has surprise factor
            surprise = context.event_signal.get("surprise", 0.5)
            score = 0.5 + (surprise - 0.5) * 0.4
            rationale = f"Expectation gap based on event surprise: {surprise}"
        else:
            confidence = 0.3
            rationale = "No agent views or event signal available"

        logger.debug(
            "Expectation gap model scored",
            model_name=self.model_name,
            score=score,
            confidence=confidence,
            signal_id=context.signal_id,
        )

        return TimingModelScore(
            model_name=self.model_name,
            score=score,
            confidence=confidence,
            rationale=rationale,
            evidence_refs=evidence_refs,
        )
