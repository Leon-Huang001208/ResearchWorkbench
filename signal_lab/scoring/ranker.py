"""
信号排名器

提供信号排名功能。
"""
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from core.contracts import AlphaSignal
from core.observability import get_logger
from signal_lab.scoring.scorer import CompositeScorer, SignalScorer

logger = get_logger(__name__)


class SignalRanker:
    """信号排名器"""

    def __init__(
        self,
        scorer: Optional[SignalScorer] = None,
    ):
        """
        初始化信号排名器

        Args:
            scorer: 评分器（默认使用组合评分器）
        """
        if scorer is None:
            from signal_lab.scoring.scorer import (
                ConfidenceScorer,
                EvidenceScorer,
                ScenarioScorer,
                StrengthScorer,
            )

            scorer = CompositeScorer(
                scorers=[
                    ConfidenceScorer(),
                    StrengthScorer(),
                    EvidenceScorer(),
                    ScenarioScorer(),
                ],
                weights=[0.3, 0.3, 0.2, 0.2],
            )

        self.scorer = scorer

    def rank(
        self,
        signals: List[AlphaSignal],
        **kwargs: Any,
    ) -> List[Tuple[AlphaSignal, float, int]]:
        """
        对信号进行排名

        Args:
            signals: 信号列表
            **kwargs: 其他参数

        Returns:
            排名后的信号列表，每个元素是（信号, 评分, 排名）
        """
        if not signals:
            return []

        # 计算评分
        scored_signals = []
        for signal in signals:
            score = self.scorer.score(signal, **kwargs)
            scored_signals.append((signal, score))

        # 按评分排序
        scored_signals.sort(key=lambda x: x[1], reverse=True)

        # 分配排名
        ranked_signals = []
        for i, (signal, score) in enumerate(scored_signals, 1):
            ranked_signals.append((signal, score, i))

        logger.info(f"Ranked {len(signals)} signals")
        return ranked_signals

    def to_dataframe(
        self,
        signals: List[AlphaSignal],
        **kwargs: Any,
    ) -> pd.DataFrame:
        """
        将排名结果转换为DataFrame

        Args:
            signals: 信号列表
            **kwargs: 其他参数

        Returns:
            排名DataFrame
        """
        ranked = self.rank(signals, **kwargs)

        data = []
        for signal, score, rank in ranked:
            data.append({
                "signal_id": signal.signal_id,
                "subject_id": signal.subject_id,
                "horizon": signal.horizon,
                "thesis": signal.thesis,
                "score": signal.score,
                "confidence": signal.confidence,
                "status": signal.status,
                "num_evidences": len(signal.evidence_refs),
                "num_scenarios": len(signal.scenario_refs),
                "composite_score": score,
                "rank": rank,
            })

        return pd.DataFrame(data)

    def filter_top_n(
        self,
        signals: List[AlphaSignal],
        n: int = 10,
        **kwargs: Any,
    ) -> List[AlphaSignal]:
        """
        筛选前N个信号

        Args:
            signals: 信号列表
            n: 要筛选的数量
            **kwargs: 其他参数

        Returns:
            前N个信号
        """
        ranked = self.rank(signals, **kwargs)
        return [signal for signal, _, _ in ranked[:n]]

    def filter_by_score(
        self,
        signals: List[AlphaSignal],
        min_score: float = 0.5,
        **kwargs: Any,
    ) -> List[AlphaSignal]:
        """
        按评分筛选信号

        Args:
            signals: 信号列表
            min_score: 最低评分
            **kwargs: 其他参数

        Returns:
            评分大于等于min_score的信号
        """
        scored = [(signal, self.scorer.score(signal, **kwargs)) for signal in signals]
        filtered = [signal for signal, score in scored if score >= min_score]
        return sorted(filtered, key=lambda s: self.scorer.score(s, **kwargs), reverse=True)
