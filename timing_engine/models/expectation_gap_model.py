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
            # Example: count number of agents with contrarian views
            contrarian_count = sum(
                1 for view in context.agent_views if view.get("contrarian", False)
            )
            if contrarian_count > len(context.agent_views) / 2:
                score = 0.8
                rationale = "High expectation gap: many contrarian views"
            elif contrarian_count > 0:
                score = 0.6
                rationale = "Moderate expectation gap"
            else:
                score = 0.4
                rationale = "Low expectation gap"
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
