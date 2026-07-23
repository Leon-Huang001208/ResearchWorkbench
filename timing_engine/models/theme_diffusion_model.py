"""主题传播模型。"""

from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .base import BaseTimingModel, TimingContext

logger = get_logger(__name__)


class ThemeDiffusionModel(BaseTimingModel):
    model_name = "theme_diffusion"

    def score(self, context: TimingContext) -> TimingModelScore:
        """主题从龙头到补涨的传播时钟评分。"""
        confidence = 0.4
        score = 0.5
        rationale = "Theme diffusion assessment based on available data"
        evidence_refs = []

        if context.diffusion_data:
            confidence = 0.8
            evidence_refs.append("diffusion_data")
            # Example: check diffusion stage (0=early, 1=mid, 2=late)
            stage = context.diffusion_data.get("stage", 1)
            if stage == 0:
                score = 0.8
                rationale = "Theme diffusion in early stage"
            elif stage == 1:
                score = 0.6
                rationale = "Theme diffusion in mid stage"
            elif stage == 2:
                score = 0.3
                rationale = "Theme diffusion in late stage"
        else:
            confidence = 0.3
            rationale = "No diffusion data available"

        logger.debug(
            "Theme diffusion model scored",
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
