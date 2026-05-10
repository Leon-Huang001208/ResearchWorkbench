"""
资金流特征组

提供资金流向相关的特征。
"""
from typing import Any

import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class NetInflowFeature(Feature):
    """净流入特征"""

    def __init__(self, periods: int = 1):
        super().__init__(name=f"net_inflow_{periods}d", description=f"{periods}日资金净流入")
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        inflow_col = kwargs.get("inflow_col", "net_inflow")
        if inflow_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[inflow_col].rolling(self.periods).sum()


class InflowRatioFeature(Feature):
    """净流入比率特征"""

    def __init__(self):
        super().__init__(name="inflow_ratio", description="净流入占成交额比率")

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        inflow_col = kwargs.get("inflow_col", "net_inflow")
        amount_col = kwargs.get("amount_col", "amount")
        if inflow_col not in data.columns or amount_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        amount = data[amount_col].replace(0, pd.NA)
        return data[inflow_col] / amount


class LargeOrderRatioFeature(Feature):
    """大单占比特征"""

    def __init__(self, window: int = 20):
        super().__init__(name=f"large_order_ratio_{window}d", description=f"{window}日大单成交占比")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        large_col = kwargs.get("large_order_col", "large_order_amount")
        amount_col = kwargs.get("amount_col", "amount")
        if large_col in data.columns and amount_col in data.columns:
            amount = data[amount_col].replace(0, pd.NA)
            ratio = data[large_col] / amount
            return ratio.rolling(self.window).mean()
        return pd.Series([pd.NA] * len(data), index=data.index)


class MainForceNetInflowFeature(Feature):
    """主力净流入特征"""

    def __init__(self, window: int = 5):
        super().__init__(name=f"main_force_net_inflow_{window}d", description=f"{window}日主力净流入")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        main_col = kwargs.get("main_force_col", "main_force_inflow")
        if main_col in data.columns:
            return data[main_col].rolling(self.window).sum()
        # 退而求其次用net_inflow
        inflow_col = kwargs.get("inflow_col", "net_inflow")
        if inflow_col in data.columns:
            return data[inflow_col].rolling(self.window).sum() * 0.6  # 估算主力占60%
        return pd.Series([pd.NA] * len(data), index=data.index)


class FundFlowFeatures(FeatureGroup):
    """资金流特征组"""

    def __init__(self):
        features = [
            NetInflowFeature(1),
            NetInflowFeature(5),
            NetInflowFeature(20),
            InflowRatioFeature(),
            LargeOrderRatioFeature(20),
            LargeOrderRatioFeature(60),
            MainForceNetInflowFeature(5),
            MainForceNetInflowFeature(20),
        ]

        super().__init__("fund_flow", features)
