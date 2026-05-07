
"""Alpha衰减模型。"""
from core.observability import get_logger

from timing_engine.contracts import TimingModelScore
from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class AlphaDecayModel(BaseTimingModel):
    model_name = "alpha_decay"

    def score(self, context: TimingContext) -> TimingModelScore:
        """Alpha衰减评分（逻辑是否已 price in）。"""
        confidence = 0.4
        score = 0.5
        rationale = "Alpha decay assessment based on available data"
        evidence_refs = []

        if context.event_signal:
            confidence = 0.7
            evidence_refs.append("event_signal")
            # Example: check time since event, or how much the price has moved
            hours_since_event = context.event_signal.get("hours_since_event", 0)
            price_move_since_event = context.event_signal.get("price_move_since_event", 0)

            if hours_since_event > 48 and price_move_since_event > 0.1:
                score = 0.8
                rationale = "High alpha decay: event is old and price has moved"
            elif hours_since_event > 24:
                score = 0.6
                rationale = "Moderate alpha decay"
            else:
                score = 0.3
                rationale = "Low alpha decay: event is recent"
        elif context.price_data:
            confidence = 0.5
            evidence_refs.append("price_data")
            # Check if price has already moved a lot
            recent_returns = context.price_data.get("recent_returns", 0)
            if recent_returns > 0.15:
                score = 0.7
                rationale = "High alpha decay: recent large price move"
            else:
                score = 0.4
                rationale = "Low alpha decay"
        else:
            confidence = 0.3
            rationale = "No event or price data available"

        logger.debug(
            "Alpha decay model scored",
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

