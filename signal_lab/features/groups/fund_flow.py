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
        super().__init__(
            name=f"net_inflow_{periods}d",
            description=f"{periods}日资金净流入"
        )
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        inflow_col = kwargs.get("inflow_col", "net_inflow")
        if inflow_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[inflow_col].rolling(self.periods).sum()


class InflowRatioFeature(Feature):
    """净流入比率特征"""

    def __init__(self):
        super().__init__(
            name="inflow_ratio",
            description="净流入占成交额比率"
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        inflow_col = kwargs.get("inflow_col", "net_inflow")
        amount_col = kwargs.get("amount_col", "amount")
        if inflow_col not in data.columns or amount_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        amount = data[amount_col].replace(0, pd.NA)
        return data[inflow_col] / amount


class FundFlowFeatures(FeatureGroup):
    """资金流特征组"""

    def __init__(self):
        features = [
            NetInflowFeature(1),
            NetInflowFeature(5),
            NetInflowFeature(20),
            InflowRatioFeature(),
        ]

        super().__init__("fund_flow", features)
