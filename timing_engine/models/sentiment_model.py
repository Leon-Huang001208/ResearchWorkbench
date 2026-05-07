
"""市场情绪模型。"""
from core.observability import get_logger

from timing_engine.contracts import TimingModelScore
from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class SentimentModel(BaseTimingModel):
    model_name = "sentiment"

    def score(self, context: TimingContext) -> TimingModelScore:
        """市场情绪评分（连板高度、炸板率、涨停溢价）。"""
        confidence = 0.4
        score = 0.5
        rationale = "Sentiment assessment based on available data"
        evidence_refs = []

        if context.sentiment_data:
            confidence = 0.8
            evidence_refs.append("sentiment_data")
            # Example logic using sentiment data
            consecutive_limit_up = context.sentiment_data.get("consecutive_limit_up", 0)
            limit_up_failure_rate = context.sentiment_data.get("limit_up_failure_rate", 0.5)
            limit_up_premium = context.sentiment_data.get("limit_up_premium", 0)

            if consecutive_limit_up >= 5 and limit_up_failure_rate < 0.2:
                score = 0.85
                rationale = "Strong sentiment: high consecutive limit ups, low failure rate"
            elif consecutive_limit_up >= 3 and limit_up_failure_rate < 0.4:
                score = 0.7
                rationale = "Moderate sentiment"
            elif limit_up_failure_rate > 0.6:
                score = 0.3
                rationale = "Weak sentiment: high limit up failure rate"
        else:
            confidence = 0.3
            rationale = "No sentiment data available"

        logger.debug(
            "Sentiment model scored",
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

