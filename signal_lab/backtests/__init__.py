"""
回测模块

提供信号回测功能。VectorBTBacktester 通过 PEP 562 __getattr__ 按需加载，
避免启动时 import vectorbt（~10s 开销）。
"""

from .backtrader_engine import BacktraderEngine
from .base import Backtester, BacktestResult
from .event_study import EventStudyBacktester
from .simple import SimpleBacktester

__all__ = [
    "Backtester",
    "BacktestResult",
    "EventStudyBacktester",
    "SimpleBacktester",
    "VectorBTBacktester",
    "BacktraderEngine",
]

# ── PEP 562 懒加载：避免启动时 import vectorbt（~10s） ──

_LAZY_BACKTESTS: dict[str, str] = {
    "VectorBTBacktester": ".vectorbt_engine",
}


def __getattr__(name: str):
    if name in _LAZY_BACKTESTS:
        import importlib

        module = importlib.import_module(_LAZY_BACKTESTS[name], __package__)
        cls = getattr(module, name)
        globals()[name] = cls
        return cls
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
