"""
估值特征组

提供估值相关的特征。
"""
from typing import Any

import pandas as pd
import numpy as np

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class PEFeature(Feature):
    """市盈率特征"""

    def __init__(self):
        super().__init__(
            name="pe_ratio",
            description="市盈率"
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        pe_col = kwargs.get("pe_col", "pe")
        if pe_col in data.columns:
            return data[pe_col]

        close_col = kwargs.get("close_col", "close")
        eps_col = kwargs.get("eps_col", "eps")
        if close_col in data.columns and eps_col in data.columns:
            eps = data[eps_col].replace(0, np.nan)
            return data[close_col] / eps

        return pd.Series([pd.NA] * len(data), index=data.index)


class PBFeature(Feature):
    """市净率特征"""

    def __init__(self):
        super().__init__(
            name="pb_ratio",
            description="市净率"
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        pb_col = kwargs.get("pb_col", "pb")
        if pb_col in data.columns:
            return data[pb_col]

        close_col = kwargs.get("close_col", "close")
        bvps_col = kwargs.get("bvps_col", "bvps")
        if close_col in data.columns and bvps_col in data.columns:
            bvps = data[bvps_col].replace(0, np.nan)
            return data[close_col] / bvps

        return pd.Series([pd.NA] * len(data), index=data.index)


class PSFeature(Feature):
    """市销率特征"""

    def __init__(self):
        super().__init__(
            name="ps_ratio",
            description="市销率"
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        ps_col = kwargs.get("ps_col", "ps")
        if ps_col in data.columns:
            return data[ps_col]

        close_col = kwargs.get("close_col", "close")
        sales_col = kwargs.get("sales_col", "sales_per_share")
        if close_col in data.columns and sales_col in data.columns:
            sales = data[sales_col].replace(0, np.nan)
            return data[close_col] / sales

        return pd.Series([pd.NA] * len(data), index=data.index)


class DividendYieldFeature(Feature):
    """股息率特征"""

    def __init__(self):
        super().__init__(
            name="dividend_yield",
            description="股息率"
        )

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        dy_col = kwargs.get("dividend_yield_col", "dividend_yield")
        if dy_col in data.columns:
            return data[dy_col]

        dividend_col = kwargs.get("dividend_col", "dividend_per_share")
        close_col = kwargs.get("close_col", "close")
        if close_col in data.columns and dividend_col in data.columns:
            close = data[close_col].replace(0, np.nan)
            return data[dividend_col] / close

        return pd.Series([pd.NA] * len(data), index=data.index)


class ValuationPercentileFeature(Feature):
    """估值百分位特征"""

    def __init__(self, window: int = 252, metric: str = "pe"):
        super().__init__(
            name=f"{metric}_percentile_{window}d",
            description=f"{metric} {window}日百分位"
        )
        self.window = window
        self.metric = metric

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        metric_col = kwargs.get(f"{self.metric}_col", self.metric)
        if metric_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        def percentile_rank(x):
            return pd.Series(x).rank(pct=True).iloc[-1] if len(x) > 0 else pd.NA

        return data[metric_col].rolling(self.window).apply(percentile_rank, raw=True)


class ValuationFeatures(FeatureGroup):
    """估值特征组"""

    def __init__(self):
        features = [
            PEFeature(),
            PBFeature(),
            PSFeature(),
            DividendYieldFeature(),
            ValuationPercentileFeature(252, "pe"),
            ValuationPercentileFeature(252, "pb"),
            ValuationPercentileFeature(126, "pe"),
        ]

        super().__init__("valuation", features)
