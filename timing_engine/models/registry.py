"""择时模型注册表。"""
from core.observability import get_logger
from timing_engine.contracts import TimingModelScore

from .alpha_decay_model import AlphaDecayModel
from .base import BaseTimingModel, TimingContext
from .crowding_model import CrowdingModel
from .expectation_gap_model import ExpectationGapModel
from .flow_model import FlowModel
from .liquidity_model import LiquidityModel
from .market_structure_model import MarketStructureModel
from .regime_model import RegimeModel
from .sentiment_model import SentimentModel
from .theme_diffusion_model import ThemeDiffusionModel

logger = get_logger(__name__)


class TimingModelRegistry:
    """择时模型注册表。"""

    def __init__(self):
        self._models: dict[str, BaseTimingModel] = {}
        self._register_defaults()

    def _register_defaults(self):
        """注册默认的 9 个择时模型。"""
        self.register(RegimeModel())
        self.register(FlowModel())
        self.register(ThemeDiffusionModel())
        self.register(SentimentModel())
        self.register(MarketStructureModel())
        self.register(LiquidityModel())
        self.register(CrowdingModel())
        self.register(ExpectationGapModel())
        self.register(AlphaDecayModel())
        logger.info("Default timing models registered")

    def get(self, model_name: str) -> BaseTimingModel:
        """获取指定名称的模型。"""
        return self._models[model_name]

    def register(self, model: BaseTimingModel) -> None:
        """注册一个新模型。"""
        self._models[model.model_name] = model
        logger.info(f"Registered timing model: {model.model_name}")

    def list_models(self) -> list[str]:
        """列出所有注册的模型名称。"""
        return list(self._models.keys())

    def score_all(self, context: TimingContext) -> list[TimingModelScore]:
        """用所有注册的模型对上下文进行评分。"""
        scores: list[TimingModelScore] = []
        for model in self._models.values():
            try:
                score = model.score(context)
                scores.append(score)
            except Exception as e:
                logger.error(
                    "Failed to score with model",
                    model_name=model.model_name,
                    error=str(e),
                    signal_id=context.signal_id,
                )
        return scores
