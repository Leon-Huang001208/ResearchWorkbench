"""
财务特征组

提供财务指标相关的特征。
"""

from typing import Any

import numpy as np
import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class ROEFeature(Feature):
    """净资产收益率特征"""

    def __init__(self):
        super().__init__(name="roe", description="净资产收益率")

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        roe_col = kwargs.get("roe_col", "roe")
        if roe_col in data.columns:
            return data[roe_col]

        net_profit_col = kwargs.get("net_profit_col", "net_profit")
        equity_col = kwargs.get("equity_col", "equity")
        if net_profit_col in data.columns and equity_col in data.columns:
            equity = data[equity_col].replace(0, np.nan)
            return data[net_profit_col] / equity

        return pd.Series([pd.NA] * len(data), index=data.index)


class ROAFeature(Feature):
    """总资产收益率特征"""

    def __init__(self):
        super().__init__(name="roa", description="总资产收益率")

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        roa_col = kwargs.get("roa_col", "roa")
        if roa_col in data.columns:
            return data[roa_col]

        net_profit_col = kwargs.get("net_profit_col", "net_profit")
        assets_col = kwargs.get("assets_col", "total_assets")
        if net_profit_col in data.columns and assets_col in data.columns:
            assets = data[assets_col].replace(0, np.nan)
            return data[net_profit_col] / assets

        return pd.Series([pd.NA] * len(data), index=data.index)


class GrowthFeature(Feature):
    """营收/利润增长率特征"""

    def __init__(self, metric: str = "revenue", periods: int = 4):
        super().__init__(
            name=f"{metric}_growth_{periods}q", description=f"{metric}{periods}季度增长率"
        )
        self.metric = metric
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        col = kwargs.get(f"{self.metric}_col", self.metric)
        if col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[col].pct_change(self.periods)


class DebtRatioFeature(Feature):
    """资产负债率特征"""

    def __init__(self):
        super().__init__(name="debt_ratio", description="资产负债率")

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        debt_col = kwargs.get("debt_col", "total_debt")
        assets_col = kwargs.get("assets_col", "total_assets")
        if debt_col in data.columns and assets_col in data.columns:
            assets = data[assets_col].replace(0, np.nan)
            return data[debt_col] / assets
        return pd.Series([pd.NA] * len(data), index=data.index)


class CurrentRatioFeature(Feature):
    """流动比率特征"""

    def __init__(self):
        super().__init__(name="current_ratio", description="流动比率")

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        cr_col = kwargs.get("current_ratio_col", "current_ratio")
        if cr_col in data.columns:
            return data[cr_col]
        current_assets_col = kwargs.get("current_assets_col", "current_assets")
        current_liab_col = kwargs.get("current_liab_col", "current_liabilities")
        if current_assets_col in data.columns and current_liab_col in data.columns:
            liab = data[current_liab_col].replace(0, np.nan)
            return data[current_assets_col] / liab
        return pd.Series([pd.NA] * len(data), index=data.index)


class FinancialFeatures(FeatureGroup):
    """财务特征组"""

    def __init__(self):
        features = [
            ROEFeature(),
            ROAFeature(),
            GrowthFeature("revenue", 4),
            GrowthFeature("revenue", 1),
            GrowthFeature("net_profit", 4),
            GrowthFeature("net_profit", 1),
            DebtRatioFeature(),
            CurrentRatioFeature(),
        ]

        super().__init__("financial", features)
