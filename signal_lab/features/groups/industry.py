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


class IndustryConcentrationFeature(Feature):
    """行业集中度特征 — 市值占比"""

    def __init__(self, window: int = 60):
        super().__init__(
            name=f"industry_concentration_{window}d",
            description=f"{window}日行业集中度"
        )
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        conc_col = kwargs.get("concentration_col", "industry_concentration")
        if conc_col in data.columns:
            return data[conc_col].rolling(self.window).mean()
        # 退而求其次用行业收益率标准差作为集中度代理
        industry_return_col = kwargs.get("industry_return_col", "industry_return")
        if industry_return_col in data.columns:
            return data[industry_return_col].rolling(self.window).std()
        return pd.Series([pd.NA] * len(data), index=data.index)


class CrossSectionalRankFeature(Feature):
    """截面排名特征"""

    def __init__(self, metric: str = "return", window: int = 20):
        super().__init__(
            name=f"cs_rank_{metric}_{window}d",
            description=f"{metric}的{window}日截面排名"
        )
        self.metric = metric
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get(f"{self.metric}_col", self.metric)
        if col in data.columns:
            return data[col].rolling(self.window).apply(
                lambda x: pd.Series(x).rank(pct=True).iloc[-1], raw=True
            )
        return pd.Series([pd.NA] * len(data), index=data.index)


class IndustryFeatures(FeatureGroup):
    """行业特征组"""

    def __init__(self):
        features = [
            IndustryMomentumFeature(20),
            IndustryMomentumFeature(60),
            IndustryStrengthFeature(20),
            IndustryStrengthFeature(60),
            IndustryConcentrationFeature(60),
            CrossSectionalRankFeature("return", 20),
            CrossSectionalRankFeature("volume", 20),
        ]

        super().__init__("industry", features)
