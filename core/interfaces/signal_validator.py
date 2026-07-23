"""
Abstract base class (interface) for signal validators.

Defines the interface for signal validators, which generate features, score signals,
backtest signals, and generate trade candidates in AlphaFoundry.
"""

from abc import ABC, abstractmethod
from typing import Any

from core.contracts import AlphaSignal, TradeCandidate


class SignalValidator(ABC):
    """信号验证器基类 - 验证和回测信号.

    Abstract base class for signal validators, which are responsible for generating
    features, scoring signals, backtesting signals, and generating trade candidates.
    """

    @abstractmethod
    def generate_features(self, subject_id: str, **kwargs: Any) -> dict[str, float]:
        """生成特征.

        Generates a dictionary of features for a given subject ID.

        Args:
            subject_id: Canonical ID of the subject to generate features for.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            dict[str, float]: Dictionary of feature names to values.
        """
        pass

    @abstractmethod
    def score_signal(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """对信号进行评分.

        Scores an AlphaSignal and returns a float score (higher is better).

        Args:
            signal: AlphaSignal to score.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            float: Score for the signal.
        """
        pass

    @abstractmethod
    def backtest(self, signal: AlphaSignal, **kwargs: Any) -> dict[str, Any]:
        """回测信号.

        Backtests an AlphaSignal and returns a dictionary of backtest results.

        Args:
            signal: AlphaSignal to backtest.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            dict[str, Any]: Dictionary of backtest results.
        """
        pass

    @abstractmethod
    def generate_candidate(self, signal: AlphaSignal, **kwargs: Any) -> TradeCandidate:
        """生成交易候选.

        Generates a TradeCandidate from an AlphaSignal.

        Args:
            signal: AlphaSignal to generate a candidate for.
            **kwargs: Implementation-specific keyword arguments.

        Returns:
            TradeCandidate: Generated trade candidate.
        """
        pass
