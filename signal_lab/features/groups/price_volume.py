"""
价量特征组

提供价格和成交量相关的技术指标。
"""
from typing import Any, Optional

import pandas as pd
import numpy as np

from core.observability import get_logger
from signal_lab.features.base import Feature, FeatureGroup

logger = get_logger(__name__)


class PriceChangeFeature(Feature):
    """价格变化特征"""

    def __init__(self, periods: int = 1):
        super().__init__(
            name=f"price_change_{periods}d",
            description=f"{periods}日价格变化率"
        )
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
        super().__init__(
            name=f"ma_{window}d",
            description=f"{window}日移动平均"
        )
        self.window = window

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        close_col = kwargs.get("close_col", "close")
        if close_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[close_col].rolling(self.window).mean()


class VolatilityFeature(Feature):
    """波动率特征"""

    def __init__(self, window: int = 20):
        super().__init__(
            name=f"volatility_{window}d",
            description=f"{window}日波动率"
        )
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
        super().__init__(
            name=f"volume_change_{periods}d",
            description=f"{periods}日成交量变化率"
        )
        self.periods = periods

    def compute(self, data: pd.DataFrame, **kwargs: Any) -> pd.Series:
        volume_col = kwargs.get("volume_col", "volume")
        if volume_col not in data.columns:
            return pd.Series([pd.NA] * len(data), index=data.index)

        return data[volume_col].pct_change(self.periods)


class VWAPFeature(Feature):
    """成交量加权平均价特征"""

    def __init__(self, window: int = 20):
        super().__init__(
            name=f"vwap_{window}d",
            description=f"{window}日成交量加权平均价"
        )
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
        super().__init__(
            name=f"rsi_{window}d",
            description=f"{window}日RSI指标"
        )
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

        features.extend([
            PriceChangeFeature(1),
            PriceChangeFeature(5),
            PriceChangeFeature(20),
            VolumeChangeFeature(1),
            VolumeChangeFeature(5),
            RSI(14),
            RSI(28),
        ])

        super().__init__("price_volume", features)
