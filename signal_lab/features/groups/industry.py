"""
行业特征组

提供行业相关的特征。
"""
from typing import Any

import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class IndustryMomentumFeature(Feature):
    """行业动量特征"""

    def __init__(self, periods: int = 20):
        super().__init__(
            name=f"industry_momentum_{periods}d",
            description=f"{periods}日行业动量"
        )
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        industry_return_col = kwargs.get("industry_return_col", "industry_return")
        if industry_return_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[industry_return_col].rolling(self.periods).sum()


class IndustryStrengthFeature(Feature):
    """行业相对强弱特征"""

    def __init__(self, periods: int = 20):
        super().__init__(
            name=f"industry_strength_{periods}d",
            description=f"{periods}日行业相对强弱"
        )
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        stock_return_col = kwargs.get("stock_return_col", "return")
        industry_return_col = kwargs.get("industry_return_col", "industry_return")
        if stock_return_col not in data.columns or industry_return_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        stock_cum = data[stock_return_col].rolling(self.periods).sum()
        industry_cum = data[industry_return_col].rolling(self.periods).sum()
        return stock_cum - industry_cum


class IndustryFeatures(FeatureGroup):
    """行业特征组"""

    def __init__(self):
        features = [
            IndustryMomentumFeature(20),
            IndustryMomentumFeature(60),
            IndustryStrengthFeature(20),
            IndustryStrengthFeature(60),
        ]

        super().__init__("industry", features)
