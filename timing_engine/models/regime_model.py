"""市场风格状态判断模型。"""

from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class RegimeModel(BaseTimingModel):
    model_name = "regime"

    def score(self, context: TimingContext) -> TimingModelScore:
        """判断市场风格状态。"""
        confidence = 0.5
        score = 0.5
        rationale = "Market regime assessment based on available data"
        evidence_refs = []

        # Try to determine regime from context
        if context.market_regime != "unknown":
            confidence = 0.8
            rationale = f"Regime explicitly provided: {context.market_regime}"
            # Score higher if regime is favorable
            if context.market_regime in ["ai_growth", "institutional_trend", "liquidity_bull"]:
                score = 0.7
            elif context.market_regime in ["risk_off", "bear_rebound"]:
                score = 0.3
            elif context.market_regime == "hot_money_theme":
                score = 0.6
        else:
            # Use price_data, sentiment_data, macro_data to infer regime
            if context.price_data:
                confidence += 0.1
                evidence_refs.append("price_data")
            if context.sentiment_data:
                confidence += 0.1
                evidence_refs.append("sentiment_data")
            if context.macro_data:
                confidence += 0.1
                evidence_refs.append("macro_data")
            confidence = min(confidence, 0.8)

        logger.debug(
            "Regime model scored",
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
