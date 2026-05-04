from abc import ABC, abstractmethod
from typing import Any

from core.contracts import AlphaSignal, TradeCandidate


class SignalValidator(ABC):
    """信号验证器基类 - 验证和回测信号"""

    @abstractmethod
    def generate_features(self, subject_id: str, **kwargs: Any) -> dict[str, float]:
        """生成特征"""
        pass

    @abstractmethod
    def score_signal(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """对信号进行评分"""
        pass

    @abstractmethod
    def backtest(self, signal: AlphaSignal, **kwargs: Any) -> dict[str, Any]:
        """回测信号"""
        pass

    @abstractmethod
    def generate_candidate(self, signal: AlphaSignal, **kwargs: Any) -> TradeCandidate:
        """生成交易候选"""
        pass
