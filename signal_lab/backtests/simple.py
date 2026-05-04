"""
简单回测器

提供基础的回测功能。
"""
from typing import Any, Dict, List, Optional

import pandas as pd
import numpy as np

from core.contracts import AlphaSignal
from core.observability import get_logger
from signal_lab.backtests.base import BacktestResult, Backtester

logger = get_logger(__name__)


class SimpleBacktester(Backtester):
    """简单回测器"""

    def __init__(
        self,
        initial_capital: float = 1000000.0,
        position_size: float = 0.1,
        risk_free_rate: float = 0.03,
        transaction_cost: float = 0.001,
    ):
        """
        初始化简单回测器

        Args:
            initial_capital: 初始资金
            position_size: 仓位大小（占资金比例）
            risk_free_rate: 无风险利率
            transaction_cost: 交易成本（双边）
        """
        super().__init__(
            name="simple_backtester",
            description="简单趋势跟踪回测器"
        )
        self.initial_capital = initial_capital
        self.position_size = position_size
        self.risk_free_rate = risk_free_rate
        self.transaction_cost = transaction_cost

    def run(
        self,
        prices: pd.DataFrame,
        signals: Optional[List[AlphaSignal]] = None,
        **kwargs: Any,
    ) -> BacktestResult:
        """
        运行回测

        Args:
            prices: 价格数据
            signals: 信号列表（可选）
            **kwargs: 其他参数

        Returns:
            回测结果
        """
        if isinstance(prices, pd.Series):
            price_series = prices
        elif "close" in prices.columns:
            price_series = prices["close"]
        else:
            raise ValueError("Prices must contain 'close' column or be a Series")

        # 计算收益率
        returns = price_series.pct_change().fillna(0)

        # 生成信号
        if signals is None:
            # 默认使用简单的移动平均交叉策略
            positions = self._generate_simple_signals(price_series)
        else:
            # 基于AlphaSignal生成位置
            positions = self._signal_to_positions(price_series, signals)

        # 计算策略收益
        strategy_returns = positions.shift(1) * returns - abs(positions.diff()) * self.transaction_cost

        # 计算净值曲线
        equity_curve = self.initial_capital * (1 + strategy_returns).cumprod()

        # 计算绩效指标
        total_return = (equity_curve.iloc[-1] / self.initial_capital) - 1
        num_periods = len(equity_curve)
        annual_return = (1 + total_return) ** (252 / num_periods) - 1
        volatility = strategy_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_return - self.risk_free_rate) / volatility if volatility != 0 else 0

        # 计算最大回撤
        rolling_max = equity_curve.expanding().max()
        drawdown = (equity_curve - rolling_max) / rolling_max
        max_drawdown = drawdown.min()

        # 计算胜率
        trade_returns = strategy_returns[positions.diff() != 0]
        win_rate = (trade_returns > 0).sum() / len(trade_returns) if len(trade_returns) > 0 else 0
        num_trades = len(trade_returns)

        result = BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            num_trades=num_trades,
            returns=strategy_returns,
            positions=positions,
            equity_curve=equity_curve,
            metadata={"initial_capital": self.initial_capital},
        )

        logger.info(f"Backtest completed: {result}")
        return result

    def _generate_simple_signals(self, prices: pd.Series) -> pd.Series:
        """生成简单的移动平均交叉信号"""
        ma_short = prices.rolling(20).mean()
        ma_long = prices.rolling(60).mean()

        positions = pd.Series(0.0, index=prices.index)
        positions[ma_short > ma_long] = self.position_size
        positions[ma_short < ma_long] = -self.position_size

        return positions

    def _signal_to_positions(
        self,
        prices: pd.Series,
        signals: List[AlphaSignal],
    ) -> pd.Series:
        """将信号转换为仓位"""
        positions = pd.Series(0.0, index=prices.index)

        for signal in signals:
            # 这里简化处理，实际应该更复杂
            if signal.status in ["candidate", "paper_trade"]:
                # 基于信号方向设置仓位
                signal_strength = signal.score * signal.confidence
                # 假设正分数做多，负分数做空
                if signal_strength > 0.5:
                    positions[:] = self.position_size
                elif signal_strength < -0.5:
                    positions[:] = -self.position_size

        return positions
