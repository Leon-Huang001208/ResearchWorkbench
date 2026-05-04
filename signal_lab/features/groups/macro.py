"""
宏观特征组

提供宏观经济相关的特征。
"""
from typing import Any

import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class MacroExposureFeature(Feature):
    """宏观风险暴露特征"""

    def __init__(self, factor: str = "market"):
        super().__init__(
            name=f"{factor}_exposure",
            description=f"{factor}因子暴露"
        )
        self.factor = factor

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get(f"{self.factor}_col", self.factor)
        if col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[col]


class MacroFeatures(FeatureGroup):
    """宏观特征组"""

    def __init__(self):
        features = [
            MacroExposureFeature("market"),
            MacroExposureFeature("interest_rate"),
            MacroExposureFeature("inflation"),
        ]

        super().__init__("macro", features)
