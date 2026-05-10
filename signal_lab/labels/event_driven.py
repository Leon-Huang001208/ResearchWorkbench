"""
事件驱动标签器

基于事件生成标签。
"""
from typing import Any, Optional

import pandas as pd

from core.observability import get_logger
from signal_lab.labels.base import Labeler

logger = get_logger(__name__)


class EventDrivenLabeler(Labeler):
    """事件驱动标签器"""

    def __init__(
        self,
        horizon: int = 20,
        event_type: str = "earnings",
        return_threshold: float = 0.05,
    ):
        """
        初始化事件驱动标签器

        Args:
            horizon: 事件后的观察期
            event_type: 事件类型
            return_threshold: 收益阈值（用于分类）
        """
        super().__init__(
            name=f"event_{event_type}_{horizon}d",
            description=f"{event_type}事件{horizon}日收益标签"
        )
        self.horizon = horizon
        self.event_type = event_type
        self.return_threshold = return_threshold

    def compute(
        self,
        prices: pd.DataFrame,
        events: Optional[pd.DataFrame] = None,
        **kwargs: Any,
    ) -> pd.Series:
        """
        计算事件驱动标签

        Args:
            prices: 价格数据
            events: 事件数据（可选，包含事件日期和类型）
            **kwargs: 其他参数

        Returns:
            标签序列
        """
        if isinstance(prices, pd.Series):
            asset_prices = prices
        elif "close" in prices.columns:
            asset_prices = prices["close"]
        else:
            raise ValueError("Prices data must contain 'close' column or be a Series")

        # 计算未来收益
        future_returns = asset_prices.pct_change(self.horizon).shift(-self.horizon)

        if events is None:
            return future_returns

        # 如果有事件数据，计算事件后收益
        if "event_date" in events.columns:
            labels = pd.Series([pd.NA] * len(asset_prices), index=asset_prices.index)

            for _, event in events.iterrows():
                event_date = event["event_date"]
                if event_date in asset_prices.index:
                    start_idx = asset_prices.index.get_loc(event_date)
                    end_idx = min(start_idx + self.horizon, len(asset_prices) - 1)

                    if end_idx < len(asset_prices):
                        start_price = asset_prices.iloc[start_idx]
                        end_price = asset_prices.iloc[end_idx]
                        event_return = (end_price - start_price) / start_price
                        labels.iloc[start_idx] = event_return

            return labels

        return future_returns

    def classify(
        self,
        returns: pd.Series,
    ) -> pd.Series:
        """
        将收益分类为标签

        Args:
            returns: 收益序列

        Returns:
            分类标签（1: 上涨, 0: 中性, -1: 下跌）
        """
        labels = pd.Series([0] * len(returns), index=returns.index)
        labels[returns > self.return_threshold] = 1
        labels[returns < -self.return_threshold] = -1
        return labels
