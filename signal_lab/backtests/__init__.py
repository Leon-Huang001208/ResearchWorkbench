"""
回测模块

提供信号回测功能。
"""
from .base import BacktestResult, Backtester
from .simple import SimpleBacktester

__all__ = [
    "Backtester",
    "BacktestResult",
    "SimpleBacktester",
]
