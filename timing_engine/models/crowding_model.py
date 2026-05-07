
"""拥挤度模型。"""
from core.observability import get_logger

from timing_engine.contracts import TimingModelScore
from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class CrowdingModel(BaseTimingModel):
    model_name = "crowding"

    def score(self, context: TimingContext) -> TimingModelScore:
        """拥挤度评分（持仓、研报覆盖、热搜、融资余额）。"""
        confidence = 0.4
        score = 0.5
        rationale = "Crowding assessment based on available data"
        evidence_refs = []

        # Check context for crowding indicators
        # For MVP, use macro_data or sentiment_data
        has_crowding_data = False
        if context.macro_data:
            has_crowding_data = True
            evidence_refs.append("macro_data")
        if context.sentiment_data:
            has_crowding_data = True
            evidence_refs.append("sentiment_data")

        if has_crowding_data:
            confidence = 0.7
            # Example: check if search热度 is high, or financing balance is high
            search_hotness = context.sentiment_data.get("search_hotness", 50)
            financing_balance_ratio = context.macro_data.get("financing_balance_ratio", 0.5)

            if search_hotness > 80 or financing_balance_ratio > 0.8:
                score = 0.8
                rationale = "High crowding: hot search or high financing balance"
            elif search_hotness > 60 or financing_balance_ratio > 0.6:
                score = 0.6
                rationale = "Moderate crowding"
            else:
                score = 0.3
                rationale = "Low crowding"
        else:
            confidence = 0.3
            rationale = "No crowding-related data available"

        logger.debug(
            "Crowding model scored",
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

