"""
事件研究回测器

把事件数据库中的事件转化为事件窗收益统计，用来回答“这类事件过去是否真的赚钱”。
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np
import pandas as pd

from core.contracts import AlphaSignal
from core.observability import get_logger
from signal_lab.backtests.base import Backtester, BacktestResult

logger = get_logger(__name__)


class EventStudyBacktester(Backtester):
    """事件研究回测器"""

    def __init__(
        self,
        horizon: int = 20,
        risk_free_rate: float = 0.03,
    ):
        """
        Args:
            horizon: 事件后的观察窗口，单位为交易日
            risk_free_rate: 年化无风险利率，用于夏普比率
        """
        super().__init__(
            name="event_study_backtester",
            description="事件窗收益与超额收益统计回测器",
        )
        if horizon <= 0:
            raise ValueError("horizon must be positive")
        self.horizon = horizon
        self.risk_free_rate = risk_free_rate

    def run(
        self,
        prices: pd.DataFrame,
        signals: Optional[list[AlphaSignal]] = None,
        **kwargs: Any,
    ) -> BacktestResult:
        """
        运行事件研究。

        Args:
            prices: 资产价格，需包含 close 列，或直接传入 Series
            signals: 保留 Backtester 统一接口，本实现不依赖该参数
            **kwargs:
                - events: 包含 event_date 列的 DataFrame
                - benchmark: 可选基准价格，用于计算超额收益

        Returns:
            BacktestResult，核心指标和事件研究明细放在 metadata 中
        """
        events = kwargs.get("events")
        benchmark = kwargs.get("benchmark")
        if events is None:
            raise ValueError("events DataFrame is required")
        if "event_date" not in events.columns:
            raise ValueError("events DataFrame must contain event_date column")

        price_series = self._extract_close(prices).sort_index()
        benchmark_series = None
        if benchmark is not None:
            benchmark_series = self._extract_close(benchmark).sort_index()

        try:
            study = self._compute_event_windows(price_series, events, benchmark_series)
        except Exception as exc:
            logger.error("event study backtest failed", error=str(exc), exc_info=True)
            raise

        if study.empty:
            logger.warning("event study produced no valid event windows")
            return BacktestResult(
                engine="event_study",
                total_trades=0,
                metadata={
                    "event_count": 0,
                    "horizon": self.horizon,
                    "average_excess_return": 0.0,
                    "median_excess_return": 0.0,
                    "decay_by_day": {},
                    "aligned_event_dates": [],
                },
            )

        excess_returns = study["excess_return"]
        event_returns = study["event_return"]
        total_return = float(excess_returns.mean())
        annual_return = float((1 + total_return) ** (252 / self.horizon) - 1)
        volatility = float(excess_returns.std(ddof=0) * np.sqrt(252 / self.horizon))
        sharpe_ratio = self._safe_sharpe(excess_returns, volatility)
        win_rate = float((excess_returns > 0).sum() / len(excess_returns))

        logger.info(
            "event study backtest completed",
            event_count=len(study),
            horizon=self.horizon,
            average_excess_return=total_return,
        )
        return BacktestResult(
            total_return=total_return,
            annual_return=annual_return,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=float(min(0.0, event_returns.min())),
            win_rate=win_rate,
            total_trades=int(len(study)),
            signal_id=signals[0].signal_id if signals else "",
            engine="event_study",
            returns=excess_returns,
            metadata={
                "event_count": int(len(study)),
                "horizon": self.horizon,
                "average_event_return": float(event_returns.mean()),
                "average_excess_return": total_return,
                "median_excess_return": float(excess_returns.median()),
                "decay_by_day": self._decay_by_day(
                    price_series,
                    study["aligned_event_date"],
                    benchmark_series,
                ),
                "aligned_event_dates": [
                    d.isoformat() for d in study["aligned_event_date"].tolist()
                ],
                "turnover": float(len(study) / max(len(price_series), 1)),
            },
        )

    @staticmethod
    def _extract_close(prices: pd.DataFrame | pd.Series) -> pd.Series:
        """从价格对象中提取收盘价序列。"""
        if isinstance(prices, pd.Series):
            return prices
        if "close" in prices.columns:
            return prices["close"]
        raise ValueError("Prices must contain 'close' column or be a Series")

    def _compute_event_windows(
        self,
        prices: pd.Series,
        events: pd.DataFrame,
        benchmark: pd.Series | None,
    ) -> pd.DataFrame:
        """计算每个事件窗口收益。"""
        rows: list[dict[str, Any]] = []
        for _, event in events.iterrows():
            aligned_date = self._align_to_next_session(
                pd.Timestamp(event["event_date"]), prices.index
            )
            if aligned_date is None:
                continue

            start_idx = prices.index.get_loc(aligned_date)
            if not isinstance(start_idx, int):
                continue
            end_idx = start_idx + self.horizon
            if end_idx >= len(prices):
                continue

            event_return = self._window_return(prices, start_idx, end_idx)
            benchmark_return = 0.0
            if benchmark is not None:
                benchmark_aligned = self._align_to_next_session(aligned_date, benchmark.index)
                if benchmark_aligned is not None:
                    benchmark_start_idx = benchmark.index.get_loc(benchmark_aligned)
                    if not isinstance(benchmark_start_idx, int):
                        continue
                    benchmark_end_idx = benchmark_start_idx + self.horizon
                    if benchmark_end_idx < len(benchmark):
                        benchmark_return = self._window_return(
                            benchmark,
                            benchmark_start_idx,
                            benchmark_end_idx,
                        )

            rows.append(
                {
                    "aligned_event_date": aligned_date,
                    "event_return": event_return,
                    "benchmark_return": benchmark_return,
                    "excess_return": event_return - benchmark_return,
                }
            )

        return pd.DataFrame(rows)

    @staticmethod
    def _align_to_next_session(
        event_date: pd.Timestamp,
        index: pd.Index,
    ) -> pd.Timestamp | None:
        """把事件日对齐到当天或下一个交易日。"""
        if event_date in index:
            return event_date
        future_dates = index[index >= event_date]
        if len(future_dates) == 0:
            return None
        return pd.Timestamp(future_dates[0])

    @staticmethod
    def _window_return(series: pd.Series, start_idx: int, end_idx: int) -> float:
        """计算窗口收益。"""
        start_value = float(series.iloc[start_idx])
        end_value = float(series.iloc[end_idx])
        if start_value == 0:
            raise ValueError("window start price cannot be zero")
        return (end_value - start_value) / start_value

    def _decay_by_day(
        self,
        prices: pd.Series,
        aligned_event_dates: pd.Series,
        benchmark: pd.Series | None,
    ) -> dict[int, float]:
        """计算从 D+1 到 D+horizon 的平均超额收益衰减。"""
        decay: dict[int, float] = {}
        for day in range(1, self.horizon + 1):
            daily_excess_returns: list[float] = []
            for event_date in aligned_event_dates:
                start_idx = prices.index.get_loc(event_date)
                if not isinstance(start_idx, int):
                    continue
                end_idx = start_idx + day
                if end_idx >= len(prices):
                    continue
                event_return = self._window_return(prices, start_idx, end_idx)
                benchmark_return = 0.0
                if benchmark is not None:
                    benchmark_start = self._align_to_next_session(event_date, benchmark.index)
                    if benchmark_start is not None:
                        benchmark_start_idx = benchmark.index.get_loc(benchmark_start)
                        if not isinstance(benchmark_start_idx, int):
                            continue
                        benchmark_end_idx = benchmark_start_idx + day
                        if benchmark_end_idx < len(benchmark):
                            benchmark_return = self._window_return(
                                benchmark,
                                benchmark_start_idx,
                                benchmark_end_idx,
                            )
                daily_excess_returns.append(event_return - benchmark_return)
            decay[day] = float(np.mean(daily_excess_returns)) if daily_excess_returns else 0.0
        return decay

    def _safe_sharpe(self, excess_returns: pd.Series, volatility: float) -> float:
        """稳定计算事件窗夏普比率。"""
        if volatility == 0 or np.isnan(volatility):
            return 0.0
        period_risk_free = self.risk_free_rate * self.horizon / 252
        return float((excess_returns.mean() - period_risk_free) / volatility)
