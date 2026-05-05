"""
回测模块

提供信号回测功能。
"""
from .base import BacktestResult, Backtester
from .simple import SimpleBacktester

# 条件导入 — 不可用时仍可import模块，但类在运行时fallback
from .vectorbt_engine import VectorBTBacktester
from .backtrader_engine import BacktraderEngine

__all__ = [
    "Backtester",
    "BacktestResult",
    "SimpleBacktester",
    "VectorBTBacktester",
    "BacktraderEngine",
]
