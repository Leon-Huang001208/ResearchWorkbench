"""
相对收益标签器

生成基于相对收益率的标签。
"""

from typing import Any, Optional

import pandas as pd

from core.observability import get_logger
from signal_lab.labels.base import Labeler

logger = get_logger(__name__)


class RelativeReturnLabeler(Labeler):
    """相对收益标签器"""

    def __init__(
        self,
        horizon: int = 20,
        forward: bool = True,
        relative: bool = True,
    ):
        """
        初始化相对收益标签器

        Args:
            horizon: 预测期（交易日）
            forward: 是否使用未来收益作为标签
            relative: 是否计算相对基准的收益
        """
        super().__init__(name=f"relative_return_{horizon}d", description=f"{horizon}日相对收益标签")
        self.horizon = horizon
        self.forward = forward
        self.relative = relative

    def compute(
        self,
        prices: pd.DataFrame,
        benchmark_prices: Optional[pd.Series] = None,
        **kwargs: Any,
    ) -> pd.Series:
        """
        计算相对收益标签

        Args:
            prices: 价格数据（包含close列或直接传入Series）
            benchmark_prices: 基准价格序列（可选）
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

        # 计算资产收益
        if self.forward:
            asset_returns = asset_prices.pct_change(self.horizon).shift(-self.horizon)
        else:
            asset_returns = asset_prices.pct_change(self.horizon)

        if not self.relative or benchmark_prices is None:
            return asset_returns

        # 计算基准收益
        if self.forward:
            benchmark_returns = benchmark_prices.pct_change(self.horizon).shift(-self.horizon)
        else:
            benchmark_returns = benchmark_prices.pct_change(self.horizon)

        # 计算相对收益
        relative_returns = asset_returns - benchmark_returns

        logger.debug(f"Computed relative return labels for {len(relative_returns)} periods")
        return relative_returns
