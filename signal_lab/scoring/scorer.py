"""
信号评分器

提供信号评分功能。
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

import numpy as np

from core.contracts import AlphaSignal
from core.observability import get_logger

logger = get_logger(__name__)


class SignalScorer(ABC):
    """信号评分器基类"""

    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description

    @abstractmethod
    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """
        对信号进行评分

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            评分（0-1之间）
        """
        pass

    def __call__(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """调用score方法"""
        return self.score(signal, **kwargs)


class ConfidenceScorer(SignalScorer):
    """置信度评分器"""

    def __init__(self):
        super().__init__(name="confidence", description="基于置信度的评分")

    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """基于信号置信度评分"""
        return float(signal.confidence)


class StrengthScorer(SignalScorer):
    """信号强度评分器"""

    def __init__(self):
        super().__init__(name="strength", description="基于信号强度的评分")

    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """基于信号强度评分"""
        return float(signal.score)


class EvidenceScorer(SignalScorer):
    """证据评分器"""

    def __init__(self):
        super().__init__(name="evidence", description="基于证据支持的评分")

    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """基于证据数量评分"""
        num_evidences = len(signal.evidence_refs)
        # 证据越多，评分越高，但边际递减
        return min(1.0, np.log(1 + num_evidences) / np.log(10))


class ScenarioScorer(SignalScorer):
    """情景支持评分器"""

    def __init__(self):
        super().__init__(name="scenario", description="基于情景支持的评分")

    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """基于情景支持评分"""
        num_scenarios = len(signal.scenario_refs)
        return min(1.0, num_scenarios / 3.0)


class CompositeScorer(SignalScorer):
    """组合评分器 - 组合多个评分器"""

    def __init__(
        self,
        scorers: Optional[List[SignalScorer]] = None,
        weights: Optional[List[float]] = None,
    ):
        super().__init__(name="composite", description="组合评分器")
        self.scorers = scorers or []
        self.weights = weights or [1.0] * len(self.scorers)
        if len(self.weights) != len(self.scorers):
            raise ValueError("Weights length must match scorers length")

    def add_scorer(self, scorer: SignalScorer, weight: float = 1.0) -> None:
        """
        添加评分器

        Args:
            scorer: 评分器对象
            weight: 权重
        """
        self.scorers.append(scorer)
        self.weights.append(weight)

    def score(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """
        组合评分

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            综合评分
        """
        if not self.scorers:
            return 0.5

        scores = [scorer.score(signal, **kwargs) for scorer in self.scorers]
        total_weight = sum(self.weights)

        if total_weight == 0:
            return 0.5

        weighted_score = sum(s * w for s, w in zip(scores, self.weights)) / total_weight
        return float(np.clip(weighted_score, 0.0, 1.0))

    def score_details(self, signal: AlphaSignal, **kwargs: Any) -> Dict[str, float]:
        """
        获取详细评分

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            详细评分数组
        """
        details = {}
        for scorer in self.scorers:
            details[scorer.name] = scorer.score(signal, **kwargs)
        details["composite"] = self.score(signal, **kwargs)
        return details
