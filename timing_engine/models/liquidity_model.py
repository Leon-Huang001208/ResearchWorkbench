"""流动性模型。"""
from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class LiquidityModel(BaseTimingModel):
    model_name = "liquidity"

    def score(self, context: TimingContext) -> TimingModelScore:
        """流动性评分（利率、国债、社融、M2）。"""
        confidence = 0.4
        score = 0.5
        rationale = "Liquidity assessment based on available data"
        evidence_refs = []

        if context.macro_data:
            confidence = 0.8
            evidence_refs.append("macro_data")
            # Example logic: check interest rates, M2, social financing
            interest_rate = context.macro_data.get("interest_rate", 0.03)
            m2_growth = context.macro_data.get("m2_growth", 0.08)
            social_financing = context.macro_data.get("social_financing", 0)

            if interest_rate < 0.025 and m2_growth > 0.08:
                score = 0.8
                rationale = "Loose liquidity: low rates, high M2 growth"
            elif interest_rate < 0.03:
                score = 0.7
                rationale = "Moderately loose liquidity"
            elif interest_rate > 0.035:
                score = 0.3
                rationale = "Tight liquidity: high rates"
        else:
            confidence = 0.3
            rationale = "No macro data available"

        logger.debug(
            "Liquidity model scored",
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
