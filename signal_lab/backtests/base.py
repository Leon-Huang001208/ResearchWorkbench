"""
回测基类

定义回测的基础接口和BacktestResult契约。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Literal, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field

from core.contracts import AlphaSignal
from core.observability import get_logger

logger = get_logger(__name__)


class BacktestResult(BaseModel):
    """回测结果 — Pydantic契约"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    total_return: float = 0.0
    annual_return: float = 0.0
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    signal_id: str = ""
    engine: Literal["simple", "vectorbt", "backtrader", "event_study"] = "simple"
    returns: Optional[Any] = Field(default=None, exclude=True)
    positions: Optional[Any] = Field(default=None, exclude=True)
    equity_curve: Optional[Any] = Field(default=None, exclude=True)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_return": self.total_return,
            "annual_return": self.annual_return,
            "volatility": self.volatility,
            "sharpe_ratio": self.sharpe_ratio,
            "max_drawdown": self.max_drawdown,
            "win_rate": self.win_rate,
            "total_trades": self.total_trades,
            "signal_id": self.signal_id,
            "engine": self.engine,
            **self.metadata,
        }

    def __repr__(self) -> str:
        return (
            f"BacktestResult(total_return={self.total_return:.2%}, "
            f"sharpe={self.sharpe_ratio:.2f}, "
            f"max_dd={self.max_drawdown:.2%}, "
            f"engine={self.engine})"
        )


class Backtester(ABC):
    """回测器基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
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
        pass

    def __call__(
        self,
        prices: pd.DataFrame,
        signals: Optional[List[AlphaSignal]] = None,
        **kwargs: Any,
    ) -> BacktestResult:
        """调用run方法"""
        return self.run(prices, signals, **kwargs)
