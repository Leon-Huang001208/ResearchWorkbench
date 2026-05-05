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


class MacroMomentumFeature(Feature):
    """宏观动量特征"""

    def __init__(self, factor: str = "market", window: int = 60):
        super().__init__(
            name=f"{factor}_momentum_{window}d",
            description=f"{factor}的{window}日动量"
        )
        self.factor = factor
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get(f"{self.factor}_col", self.factor)
        if col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)
        return data[col].diff(self.window)


class CreditSpreadFeature(Feature):
    """信用利差特征"""

    def __init__(self, window: int = 20):
        super().__init__(
            name=f"credit_spread_{window}d",
            description=f"{window}日信用利差"
        )
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        spread_col = kwargs.get("credit_spread_col", "credit_spread")
        if spread_col in data.columns:
            return data[spread_col].rolling(self.window).mean()
        # 尝试从利率和风险利率计算
        risk_col = kwargs.get("interest_rate_col", "interest_rate")
        safe_col = kwargs.get("risk_free_col", "risk_free_rate")
        if risk_col in data.columns and safe_col in data.columns:
            spread = data[risk_col] - data[safe_col]
            return spread.rolling(self.window).mean()
        return pd.Series([pd.NA] * len(data), index=data.index)


class MacroFeatures(FeatureGroup):
    """宏观特征组"""

    def __init__(self):
        features = [
            MacroExposureFeature("market"),
            MacroExposureFeature("interest_rate"),
            MacroExposureFeature("inflation"),
            MacroMomentumFeature("market", 60),
            MacroMomentumFeature("interest_rate", 60),
            CreditSpreadFeature(20),
            CreditSpreadFeature(60),
        ]

        super().__init__("macro", features)
