"""
信号验证器实现

实现SignalValidator接口。
"""
import uuid
from typing import Any, Dict, Optional

import pandas as pd

from core.contracts import AlphaSignal, TradeCandidate
from core.interfaces import SignalValidator
from core.observability import get_logger
from signal_lab.backtests import SimpleBacktester
from signal_lab.features import FeatureBuilder
from signal_lab.features.groups import (
    FinancialFeatures,
    FundFlowFeatures,
    PriceVolumeFeatures,
    ValuationFeatures,
)
from signal_lab.scoring import CompositeScorer

logger = get_logger(__name__)


class SignalValidatorImpl(SignalValidator):
    """信号验证器实现"""

    def __init__(
        self,
        feature_builder: Optional[FeatureBuilder] = None,
        backtester: Optional[SimpleBacktester] = None,
        scorer: Optional[CompositeScorer] = None,
    ):
        """
        初始化信号验证器

        Args:
            feature_builder: 特征构建器
            backtester: 回测器
            scorer: 评分器
        """
        if feature_builder is None:
            feature_builder = FeatureBuilder()
            feature_builder.add_group(PriceVolumeFeatures())
            feature_builder.add_group(ValuationFeatures())
            feature_builder.add_group(FinancialFeatures())
            feature_builder.add_group(FundFlowFeatures())

        self.feature_builder = feature_builder
        self.backtester = backtester or SimpleBacktester()
        self.scorer = scorer or CompositeScorer()

    def generate_features(self, subject_id: str, **kwargs: Any) -> Dict[str, float]:
        """
        生成特征

        Args:
            subject_id: 主体ID
            **kwargs: 其他参数（包含数据）

        Returns:
            特征字典
        """
        data = kwargs.get("data")
        if data is None:
            logger.warning("No data provided for feature generation")
            return {}

        features_df = self.feature_builder.compute_features(data, **kwargs)

        if len(features_df) > 0:
            latest_features = features_df.iloc[-1].to_dict()
            return {str(k): float(v) for k, v in latest_features.items() if pd.notna(v)}

        return {}

    def score_signal(self, signal: AlphaSignal, **kwargs: Any) -> float:
        """
        对信号进行评分

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            评分
        """
        return self.scorer.score(signal, **kwargs)

    def backtest(self, signal: AlphaSignal, **kwargs: Any) -> Dict[str, Any]:
        """
        回测信号

        Args:
            signal: 信号对象
            **kwargs: 其他参数（包含价格数据）

        Returns:
            回测结果字典
        """
        prices = kwargs.get("prices")
        if prices is None:
            logger.warning("No prices provided for backtest")
            return {"error": "No prices data"}

        result = self.backtester.run(prices, [signal], **kwargs)
        return result.to_dict()

    def generate_candidate(self, signal: AlphaSignal, **kwargs: Any) -> TradeCandidate:
        """
        生成交易候选

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            交易候选
        """
        # 基于信号分数确定方向
        signal_strength = signal.score * signal.confidence

        if signal_strength > 0.6:
            action = "long"
            sizing_hint = min(0.2, signal_strength)
        elif signal_strength < -0.6:
            action = "short"
            sizing_hint = min(0.2, -signal_strength)
        else:
            action = "neutral"
            sizing_hint = 0.0

        risk_notes = []
        if len(signal.evidence_refs) < 2:
            risk_notes.append("有限证据支持")

        if signal.status == "research_only":
            risk_notes.append("仅用于研究")

        return TradeCandidate(
            candidate_id=str(uuid.uuid4()),
            signal_id=signal.signal_id,
            action=action,
            sizing_hint=sizing_hint,
            risk_notes=risk_notes,
        )
