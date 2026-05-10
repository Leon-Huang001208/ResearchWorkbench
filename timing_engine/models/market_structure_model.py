"""市场结构模型。"""
from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class MarketStructureModel(BaseTimingModel):
    model_name = "market_structure"

    def score(self, context: TimingContext) -> TimingModelScore:
        """市场结构评分（波动聚集、突破、趋势）。"""
        confidence = 0.4
        score = 0.5
        rationale = "Market structure assessment based on available data"
        evidence_refs = []

        if context.price_data:
            confidence = 0.8
            evidence_refs.append("price_data")
            # Example logic: check trend and volatility
            trend = context.price_data.get("trend", "neutral")
            volatility = context.price_data.get("volatility", "medium")
            breakout = context.price_data.get("breakout", False)

            if trend == "up" and breakout:
                score = 0.8
                rationale = "Bullish trend with breakout"
            elif trend == "up":
                score = 0.7
                rationale = "Bullish trend"
            elif trend == "down":
                score = 0.3
                rationale = "Bearish trend"
            if volatility == "high":
                score -= 0.1
                rationale += " (high volatility)"
        else:
            confidence = 0.3
            rationale = "No price data available"

        logger.debug(
            "Market structure model scored",
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
