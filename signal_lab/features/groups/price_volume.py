"""
价量特征组

提供价格和成交量相关的技术指标。
"""
from typing import Any, Optional

import numpy as np
import pandas as pd

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class PriceChangeFeature(Feature):
    """价格变化特征"""

    def __init__(self, periods: int = 1):
        super().__init__(name=f"price_change_{periods}d", description=f"{periods}日价格变化率")
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            logger.warning(f"Column {close_col} not found, returning NA")
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[close_col].pct_change(self.periods)


class MovingAverageFeature(Feature):
    """移动平均特征"""

    def __init__(self, window: int):
        super().__init__(name=f"ma_{window}d", description=f"{window}日移动平均")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[close_col].rolling(self.window).mean()


class VolatilityFeature(Feature):
    """波动率特征"""

    def __init__(self, window: int = 20):
        super().__init__(name=f"volatility_{window}d", description=f"{window}日波动率")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        returns = data[close_col].pct_change()
        return returns.rolling(self.window).std()


class VolumeChangeFeature(Feature):
    """成交量变化特征"""

    def __init__(self, periods: int = 1):
        super().__init__(name=f"volume_change_{periods}d", description=f"{periods}日成交量变化率")
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        volume_col = kwargs.get("volume_col", "volume")
        if volume_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[volume_col].pct_change(self.periods)


class VWAPFeature(Feature):
    """成交量加权平均价特征"""

    def __init__(self, window: int = 20):
        super().__init__(name=f"vwap_{window}d", description=f"{window}日成交量加权平均价")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        volume_col = kwargs.get("volume_col", "volume")

        if close_col not in data.columns or volume_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        pv = data[close_col] * data[volume_col]
        pv_sum = pv.rolling(self.window).sum()
        volume_sum = data[volume_col].rolling(self.window).sum()
        return pv_sum / volume_sum


class RSI(Feature):
    """相对强弱指标"""

    def __init__(self, window: int = 14):
        super().__init__(name=f"rsi_{window}d", description=f"{window}日RSI指标")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        delta = data[close_col].diff()
        gain = (delta.where(delta > 0, 0)).rolling(self.window).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(self.window).mean()

        rs = gain / loss
        return 100 - (100 / (1 + rs))


class TurnoverRateFeature(Feature):
    """换手率特征"""

    def __init__(self, window: int = 20):
        super().__init__(name=f"turnover_rate_{window}d", description=f"{window}日平均换手率")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        turnover_col = kwargs.get("turnover_col", "turnover")
        if turnover_col in data.columns:
            return data[turnover_col].rolling(self.window).mean()
        # 如果没有直接换手率列，尝试用volume / shares_outstanding估算
        volume_col = kwargs.get("volume_col", "volume")
        shares_col = kwargs.get("shares_col", "shares_outstanding")
        if volume_col in data.columns and shares_col in data.columns:
            shares = data[shares_col].replace(0, np.nan)
            turnover = data[volume_col] / shares
            return turnover.rolling(self.window).mean()
        return pd.Series([pd.NA] * len(data), index=data.index)


class AmountFeature(Feature):
    """成交额特征"""

    def __init__(self, window: int = 20):
        super().__init__(name=f"amount_{window}d", description=f"{window}日成交额均值")
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        amount_col = kwargs.get("amount_col", "amount")
        if amount_col in data.columns:
            return data[amount_col].rolling(self.window).mean()
        # 用 close * volume 估算
        close_col = kwargs.get("close_col", "close")
        volume_col = kwargs.get("volume_col", "volume")
        if close_col in data.columns and volume_col in data.columns:
            amount = data[close_col] * data[volume_col]
            return amount.rolling(self.window).mean()
        return pd.Series([pd.NA] * len(data), index=data.index)


class AbnormalReturnFeature(Feature):
    """事件窗异常收益特征"""

    def __init__(self, window: int = 20, benchmark_col: str = "benchmark_return"):
        super().__init__(name=f"abnormal_return_{window}d", description=f"{window}日事件窗异常收益")
        self.window = window
        self.benchmark_col = benchmark_col

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        stock_returns = data[close_col].pct_change()
        bench_col = kwargs.get("benchmark_col", self.benchmark_col)
        if bench_col in data.columns:
            bench_returns = data[bench_col]
        else:
            # 如果没有基准收益，用市场收益或0
            bench_returns = pd.Series(0.0, index=data.index)

        abnormal = stock_returns - bench_returns
        return abnormal.rolling(self.window).sum()


class PriceVolumeFeatures(FeatureGroup):
    """价量特征组"""

    def __init__(self, windows: Optional[list[int]] = None):
        if windows is None:
            windows = [5, 10, 20, 60]

        features = []
        for window in windows:
            features.append(MovingAverageFeature(window))
            features.append(VolatilityFeature(window))
            features.append(VWAPFeature(window))

        features.extend(
            [
                PriceChangeFeature(1),
                PriceChangeFeature(5),
                PriceChangeFeature(20),
                VolumeChangeFeature(1),
                VolumeChangeFeature(5),
                RSI(14),
                RSI(28),
                TurnoverRateFeature(20),
                TurnoverRateFeature(60),
                AmountFeature(20),
                AmountFeature(60),
                AbnormalReturnFeature(20),
                AbnormalReturnFeature(60),
            ]
        )

        super().__init__("price_volume", features)
