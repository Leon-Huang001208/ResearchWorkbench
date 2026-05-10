"""
回测模块

提供信号回测功能。
"""
from .backtrader_engine import BacktraderEngine
from .base import Backtester, BacktestResult
from .event_study import EventStudyBacktester
from .simple import SimpleBacktester

# 条件导入 — 不可用时仍可import模块，但类在运行时fallback
from .vectorbt_engine import VectorBTBacktester

__all__ = [
    "Backtester",
    "BacktestResult",
    "EventStudyBacktester",
    "SimpleBacktester",
    "VectorBTBacktester",
    "BacktraderEngine",
]
