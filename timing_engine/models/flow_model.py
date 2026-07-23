"""资金流方向和强度模型。"""

from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class FlowModel(BaseTimingModel):
    model_name = "flow"

    def score(self, context: TimingContext) -> TimingModelScore:
        """资金流方向和强度评分。"""
        confidence = 0.4
        score = 0.5
        rationale = "Flow assessment based on available data"
        evidence_refs = []

        if context.flow_data:
            confidence = 0.8
            evidence_refs.append("flow_data")
            # Example logic: if net inflow is positive, score higher
            net_inflow = context.flow_data.get("net_inflow", 0)
            if net_inflow > 0:
                score = min(0.9, 0.5 + net_inflow / 1000000000)  # Scale down
                rationale = f"Net inflow positive: {net_inflow}"
            elif net_inflow < 0:
                score = max(0.1, 0.5 - abs(net_inflow) / 1000000000)
                rationale = f"Net outflow negative: {net_inflow}"
            else:
                rationale = "Net flow neutral"
        else:
            confidence = 0.3
            rationale = "No flow data available"

        logger.debug(
            "Flow model scored",
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
