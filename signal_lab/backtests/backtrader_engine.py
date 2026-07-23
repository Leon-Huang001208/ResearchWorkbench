"""
Backtrader回测引擎

使用Backtrader实现事件驱动的策略回测。
"""

from typing import Any, List, Optional

import numpy as np
import pandas as pd

from core.contracts import AlphaSignal
from core.observability import get_logger
from signal_lab.backtests.base import Backtester, BacktestResult

logger = get_logger(__name__)

_BACKTRADER_AVAILABLE = False
try:
    import backtrader as bt

    _BACKTRADER_AVAILABLE = True
except ImportError:
    bt = None  # type: ignore
    logger.warning("backtrader not installed; BacktraderEngine will fall back to SimpleBacktester")


class AlphaSignalStrategy(bt.Strategy):
    """将AlphaSignal转换为Backtrader策略

    策略逻辑:
    - 当信号score * confidence > 0.5时做多
    - 当信号score * confidence < -0.5时做空（如果支持）
    - 根据horizon决定持仓天数
    - 默认使用MA交叉作为fallback
    """

    params = (
        ("signal_strength", 0.0),
        ("horizon_days", 20),
        ("position_size", 0.1),
        ("use_default_strategy", True),
    )

    def __init__(self):
        self.order = None
        self.trade_count = 0
        self.win_count = 0
        self.trade_pnls: list[float] = []
        self._bar_count = 0
        self._entry_bar = 0

        # 默认MA交叉指标
        if self.p.use_default_strategy:
            self.ma_short = bt.indicators.SMA(self.data.close, period=20)
            self.ma_long = bt.indicators.SMA(self.data.close, period=60)

    def next(self):
        self._bar_count += 1

        if self.order:
            return

        if self.p.use_default_strategy:
            # 默认MA交叉策略
            if not self.position:
                if self.ma_short[0] > self.ma_long[0]:
                    size = int((self.broker.getcash() * self.p.position_size) / self.data.close[0])
                    if size > 0:
                        self.order = self.buy(size=size)
                        self._entry_bar = self._bar_count
            else:
                # 平仓条件: MA死叉 或 持仓超过horizon
                if (self.ma_short[0] < self.ma_long[0]) or (
                    self._bar_count - self._entry_bar >= self.p.horizon_days
                ):
                    self.order = self.close()
        else:
            # 基于信号强度
            if not self.position:
                if self.p.signal_strength > 0.5:
                    size = int((self.broker.getcash() * self.p.position_size) / self.data.close[0])
                    if size > 0:
                        self.order = self.buy(size=size)
                        self._entry_bar = self._bar_count
            else:
                if self._bar_count - self._entry_bar >= self.p.horizon_days:
                    self.order = self.close()

    def notify_order(self, order):
        if order.status in [order.Completed]:
            self.order = None
        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.order = None

    def notify_trade(self, trade):
        if trade.isclosed:
            self.trade_count += 1
            pnl = trade.pnl
            self.trade_pnls.append(pnl)
            if pnl > 0:
                self.win_count += 1


class BacktraderEngine(Backtester):
    """基于Backtrader的事件驱动回测引擎

    支持:
    - 将AlphaSignal转换为Backtrader Strategy
    - 事件驱动的策略回测
    - 与VectorBTBacktester相同的BacktestResult输出格式

    如果backtrader未安装，自动fallback到SimpleBacktester。
    """

    def __init__(
        self,
        initial_capital: float = 1_000_000.0,
        commission: float = 0.001,
        risk_free_rate: float = 0.03,
    ):
        """
        Args:
            initial_capital: 初始资金
            commission: 交易手续费率
            risk_free_rate: 无风险利率（年化）
        """
        super().__init__(
            name="backtrader_engine",
            description="基于Backtrader的事件驱动回测引擎",
        )
        self.initial_capital = initial_capital
        self.commission = commission
        self.risk_free_rate = risk_free_rate

        # Fallback引擎
        from signal_lab.backtests.simple import SimpleBacktester

        self._fallback = SimpleBacktester(
            initial_capital=initial_capital,
            transaction_cost=commission,
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
            prices: 价格数据 (需含 'close' 列)
            signals: 信号列表
            **kwargs:
                - strategy: bt.Strategy 子类 (可选)

        Returns:
            BacktestResult
        """
        if not _BACKTRADER_AVAILABLE:
            logger.info("backtrader unavailable, falling back to SimpleBacktester")
            result = self._fallback.run(prices, signals, **kwargs)
            result.engine = "backtrader"
            result.metadata["fallback"] = True
            return result

        # 提取价格序列
        price_series = self._extract_close(prices)

        # 准备数据
        data_feed = self._create_data_feed(prices, price_series)

        # 确定策略参数
        signal_strength = 0.0
        horizon_days = 20
        use_default = True
        signal_id = ""

        if signals and len(signals) > 0:
            primary = signals[0]
            signal_id = primary.signal_id
            if primary.status in ("candidate", "paper_trade"):
                signal_strength = primary.score * primary.confidence
                horizon_days = self._horizon_to_days(primary.horizon)
                use_default = False

        # 使用自定义策略或默认策略
        custom_strategy = kwargs.get("strategy", None)

        try:
            cerebro = bt.Cerebro()
            cerebro.adddata(data_feed)
            cerebro.broker.setcash(self.initial_capital)
            cerebro.broker.setcommission(commission=self.commission)

            if custom_strategy:
                cerebro.addstrategy(custom_strategy)
            else:
                cerebro.addstrategy(
                    AlphaSignalStrategy,
                    signal_strength=signal_strength,
                    horizon_days=horizon_days,
                    use_default_strategy=use_default,
                )

            # 添加分析器
            cerebro.addanalyzer(
                bt.analyzers.SharpeRatio, _name="sharpe", riskfreerate=self.risk_free_rate / 252
            )
            cerebro.addanalyzer(bt.analyzers.DrawDown, _name="drawdown")
            cerebro.addanalyzer(bt.analyzers.Returns, _name="returns")
            cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name="trades")

            # 运行
            strat = cerebro.run()[0]

            # 提取结果
            return self._build_result(strat, price_series, signal_id)

        except Exception as e:
            logger.error(f"Backtrader run failed: {e}, falling back to SimpleBacktester")
            result = self._fallback.run(prices, signals, **kwargs)
            result.engine = "backtrader"
            result.metadata["fallback"] = True
            result.metadata["error"] = str(e)
            return result

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
        return prices.iloc[:, 0]

    @staticmethod
    def _create_data_feed(prices: pd.DataFrame, price_series: pd.Series) -> "bt.feeds.PandasData":
        """创建Backtrader数据源"""
        # Backtrader需要OHLCV格式
        df = pd.DataFrame(index=price_series.index)
        df["close"] = price_series.values

        if isinstance(prices, pd.DataFrame):
            if "open" in prices.columns:
                df["open"] = prices["open"].values
            else:
                df["open"] = price_series.values
            if "high" in prices.columns:
                df["high"] = prices["high"].values
            else:
                df["high"] = price_series.values
            if "low" in prices.columns:
                df["low"] = prices["low"].values
            else:
                df["low"] = price_series.values
            if "volume" in prices.columns:
                df["volume"] = prices["volume"].values
            else:
                df["volume"] = 0
        else:
            df["open"] = price_series.values
            df["high"] = price_series.values
            df["low"] = price_series.values
            df["volume"] = 0

        if "open" not in df.columns:
            df["open"] = price_series.values
        if "high" not in df.columns:
            df["high"] = price_series.values
        if "low" not in df.columns:
            df["low"] = price_series.values
        if "volume" not in df.columns:
            df["volume"] = 0

        return bt.feeds.PandasData(dataname=df)

    @staticmethod
    def _horizon_to_days(horizon: str) -> int:
        """将horizon字符串转换为天数"""
        mapping = {"1d": 1, "5d": 5, "20d": 20, "60d": 60}
        return mapping.get(horizon, 20)

    def _build_result(
        self,
        strat: "bt.Strategy",
        price_series: pd.Series,
        signal_id: str,
    ) -> BacktestResult:
        """从Backtrader策略结果中提取指标"""
        final_value = strat.broker.getvalue()
        total_return = (final_value / self.initial_capital) - 1

        # 年化收益
        n_days = len(price_series)
        annual_return = (1 + total_return) ** (252 / max(n_days, 1)) - 1 if n_days > 0 else 0.0

        # 夏普比率
        try:
            sharpe_analysis = strat.analyzers.sharpe.get_analysis()
            sharpe_ratio = float(sharpe_analysis.get("sharperatio", 0.0) or 0.0)
        except Exception:
            sharpe_ratio = 0.0

        # 最大回撤
        try:
            dd_analysis = strat.analyzers.drawdown.get_analysis()
            max_drawdown = (
                -float(dd_analysis.max.drawdown) / 100.0 if dd_analysis.max.drawdown else 0.0
            )
        except Exception:
            max_drawdown = 0.0

        # 波动率
        try:
            returns_analysis = strat.analyzers.returns.get_analysis()
            # 用日收益计算年化波动率
            daily_returns = (
                pd.Series(list(returns_analysis.values()))
                if returns_analysis
                else pd.Series(dtype=float)
            )
            volatility = (
                float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0
            )
        except Exception:
            volatility = 0.0

        # 交易统计
        total_trades = strat.trade_count
        win_rate = float(strat.win_count / total_trades) if total_trades > 0 else 0.0

        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            win_rate=win_rate,
            total_trades=total_trades,
            signal_id=signal_id,
            engine="backtrader",
            returns=None,
            positions=None,
            equity_curve=None,
            metadata={
                "initial_capital": self.initial_capital,
                "final_value": final_value,
                "fallback": False,
            },
        )
