"""
vectorbt回测引擎

使用vectorbt实现高性能向量化回测。
"""
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from core.contracts import AlphaSignal
from core.observability import get_logger
from signal_lab.backtests.base import Backtester, BacktestResult

logger = get_logger(__name__)

_VECTORBT_AVAILABLE = False
try:
    import vectorbt as vbt

    _VECTORBT_AVAILABLE = True
except Exception as exc:
    vbt = None  # type: ignore
    logger.warning(
        "vectorbt unavailable; VectorBTBacktester will fall back to SimpleBacktester",
        error=str(exc),
    )


class VectorBTBacktester(Backtester):
    """基于vectorbt的向量化回测引擎

    支持:
    - 多信号组合回测
    - 高性能向量化计算
    - 完整的绩效指标输出

    如果vectorbt未安装，自动fallback到SimpleBacktester。
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        fees: float = 0.001,
        slippage: float = 0.0,
        risk_free_rate: float = 0.03,
        freq: str = "1D",
    ):
        """
        Args:
            initial_capital: 初始资金
            fees: 交易费率（单边）
            slippage: 滑点
            risk_free_rate: 无风险利率（年化）
            freq: 数据频率
        """
        super().__init__(
            name="vectorbt_backtester",
            description="基于vectorbt的向量化回测引擎",
        )
        self.initial_capital = initial_capital
        self.fees = fees
        self.slippage = slippage
        self.risk_free_rate = risk_free_rate
        self.freq = freq

        # Fallback引擎
        from signal_lab.backtests.simple import SimpleBacktester

        self._fallback = SimpleBacktester(
            initial_capital=initial_capital,
            transaction_cost=fees,
            risk_free_rate=risk_free_rate,
        )

    def run(
        self,
        prices: pd.DataFrame,
        signals: Optional[List[AlphaSignal]] = None,
        **kwargs: Any,
    ) -> BacktestResult:
        """
        运行回测

        Args:
            prices: 价格数据 (需含 'close' 列，或自身为单列DataFrame)
            signals: 信号列表
            **kwargs:
                - entries: pd.Series 布尔入场信号
                - exits: pd.Series 布尔出场信号

        Returns:
            BacktestResult
        """
        if not _VECTORBT_AVAILABLE:
            logger.info("vectorbt unavailable, falling back to SimpleBacktester")
            result = self._fallback.run(prices, signals, **kwargs)
            result.engine = "vectorbt"
            result.metadata["fallback"] = True
            return result

        # 提取价格序列
        price_series = self._extract_close(prices)

        # 生成入场/出场信号
        entries, exits = self._resolve_signals(price_series, signals, kwargs)

        # 运行vectorbt Portfolio
        try:
            portfolio = vbt.Portfolio.from_signals(
                close=price_series,
                entries=entries,
                exits=exits,
                init_cash=self.initial_capital,
                fees=self.fees,
                slippage=self.slippage,
                freq=self.freq,
            )
        except Exception as e:
            logger.error(f"vectorbt Portfolio.from_signals failed: {e}, falling back")
            result = self._fallback.run(prices, signals, **kwargs)
            result.engine = "vectorbt"
            result.metadata["fallback"] = True
            result.metadata["error"] = str(e)
            return result

        # 提取绩效指标
        return self._build_result(portfolio, price_series, signals)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_close(prices: pd.DataFrame) -> pd.Series:
        """从DataFrame中提取收盘价"""
        if isinstance(prices, pd.Series):
            return prices
        if "close" in prices.columns:
            return prices["close"]
        # 使用第一列
        return prices.iloc[:, 0]

    def _resolve_signals(
        self,
        price_series: pd.Series,
        signals: Optional[List[AlphaSignal]],
        kwargs: Dict[str, Any],
    ) -> tuple[pd.Series, pd.Series]:
        """将AlphaSignal或kwargs中的entries/exits转换为布尔Series"""
        # 优先使用直接传入的entries/exits
        if "entries" in kwargs and "exits" in kwargs:
            entries = kwargs["entries"]
            exits = kwargs["exits"]
            if len(entries) != len(price_series):
                raise ValueError(
                    f"entries length ({len(entries)}) != price length ({len(price_series)})"
                )
            return entries, exits

        # 默认生成MA交叉信号
        if signals is None or len(signals) == 0:
            return self._default_ma_cross(price_series)

        # 基于AlphaSignal生成信号
        entries = pd.Series(False, index=price_series.index)
        exits = pd.Series(False, index=price_series.index)

        for signal in signals:
            if signal.status not in ("candidate", "paper_trade"):
                continue
            strength = signal.score * signal.confidence
            if strength > 0.5:
                # 正信号 — 做多入场
                # 在信号起始日入场，持仓horizon天后出场
                horizon_days = self._horizon_to_days(signal.horizon)
                entries.iloc[: max(1, len(entries) - horizon_days)] = True
                exits.iloc[horizon_days:] = True
            elif strength < -0.5:
                # 负信号 — 暂不处理做空（vectorbt默认只支持多头）
                pass

        return entries, exits

    @staticmethod
    def _horizon_to_days(horizon: str) -> int:
        """将horizon字符串转换为天数"""
        mapping = {"1d": 1, "5d": 5, "20d": 20, "60d": 60}
        return mapping.get(horizon, 20)

    def _default_ma_cross(self, price_series: pd.Series) -> tuple[pd.Series, pd.Series]:
        """默认MA交叉策略"""
        ma_short = price_series.rolling(20).mean()
        ma_long = price_series.rolling(60).mean()
        entries = (ma_short > ma_long).fillna(False)
        exits = (ma_short < ma_long).fillna(False)
        return entries, exits

    def _build_result(
        self,
        portfolio: "vbt.Portfolio",
        price_series: pd.Series,
        signals: Optional[List[AlphaSignal]],
    ) -> BacktestResult:
        """从vectorbt Portfolio中提取指标构建BacktestResult"""
        # vectorbt 1.0: total_return, max_drawdown, sharpe_ratio, final_value, returns, value are methods
        total_return = float(portfolio.total_return())
        final_value = float(portfolio.final_value())

        # 年化收益
        n_days = len(price_series)
        annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1 if n_days > 0 else 0.0

        # 夏普比率
        daily_returns = portfolio.returns()
        if len(daily_returns.dropna()) > 1:
            std = daily_returns.std()
            if std != 0 and not np.isnan(std):
                sharpe_ratio = float(
                    (daily_returns.mean() - self.risk_free_rate / 252) / std * np.sqrt(252)
                )
            else:
                sharpe_ratio = 0.0
        else:
            sharpe_ratio = 0.0

        # 波动率
        volatility = (
            float(daily_returns.std() * np.sqrt(252)) if len(daily_returns.dropna()) > 1 else 0.0
        )
        if np.isnan(volatility):
            volatility = 0.0

        # 最大回撤
        max_drawdown = float(portfolio.max_drawdown())
        # vectorbt返回小数形式 (e.g., -0.0723 表示 -7.23%)，已符合我们的约定

        # 胜率 & 交易数
        trades = portfolio.trades
        trade_count = len(trades.records_readable)
        if trade_count > 0:
            trade_pnls = trades.pnl.values
            win_rate = (
                float((trade_pnls > 0).sum() / len(trade_pnls)) if len(trade_pnls) > 0 else 0.0
            )
        else:
            win_rate = 0.0

        # 信号ID
        signal_id = signals[0].signal_id if signals and len(signals) > 0 else ""

        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=trade_count,
            signal_id=signal_id,
            engine="vectorbt",
            returns=daily_returns,
            positions=None,
            equity_curve=portfolio.value(),
            metadata={
                "initial_capital": self.initial_capital,
                "final_value": final_value,
                "fallback": False,
            },
        )
