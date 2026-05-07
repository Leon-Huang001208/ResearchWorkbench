"""择时层。

Timing Engine 是市场行为模型，负责判断市场现在是否会认可某个逻辑。
"""
from .contracts import MarketRegime, TimingAction, TimingDecision, TimingModelName, TimingModelScore
from .meta import MetaTimingEngine
from .models.base import BaseTimingModel, TimingContext
from .models.registry import TimingModelRegistry

__all__ = [
    "MarketRegime",
    "MetaTimingEngine",
    "TimingAction",
    "TimingDecision",
    "TimingModelName",
    "TimingModelScore",
    "BaseTimingModel",
    "TimingContext",
    "TimingModelRegistry",
]
