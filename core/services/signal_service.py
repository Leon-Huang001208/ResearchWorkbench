"""
信号服务

提供信号生成和管理功能。
"""
import uuid
from typing import Any, Dict, List, Optional
from datetime import datetime

from core.contracts import AlphaSignal, TradeCandidate
from core.interfaces import SignalValidator
from core.observability import get_logger
from core.services.signal_validator_impl import SignalValidatorImpl

logger = get_logger(__name__)


class SignalService:
    """信号服务"""

    def __init__(
        self,
        validator: Optional[SignalValidator] = None,
    ):
        """
        初始化信号服务

        Args:
            validator: 信号验证器
        """
        self.validator = validator or SignalValidatorImpl()
        self.signals: Dict[str, AlphaSignal] = {}

    def create_signal(
        self,
        subject_id: str,
        thesis: str,
        horizon: str = "20d",
        score: float = 0.5,
        confidence: float = 0.5,
        scenario_refs: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
        status: str = "research_only",
        **kwargs: Any,
    ) -> AlphaSignal:
        """
        创建信号

        Args:
            subject_id: 主体ID
            thesis: 研究论点
            horizon: 预测期
            score: 分数
            confidence: 置信度
            scenario_refs: 情景引用
            evidence_refs: 证据引用
            status: 状态
            **kwargs: 其他参数

        Returns:
            信号对象
        """
        signal = AlphaSignal(
            signal_id=str(uuid.uuid4()),
            subject_id=subject_id,
            horizon=horizon,
            thesis=thesis,
            score=score,
            confidence=confidence,
            scenario_refs=scenario_refs or [],
            evidence_refs=evidence_refs or [],
            status=status,
        )

        self.signals[signal.signal_id] = signal
        logger.info(f"Created signal: {signal.signal_id} for {subject_id}")
        return signal

    def get_signal(self, signal_id: str) -> Optional[AlphaSignal]:
        """
        获取信号

        Args:
            signal_id: 信号ID

        Returns:
            信号对象（如果存在）
        """
        return self.signals.get(signal_id)

    def list_signals(
        self,
        status: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AlphaSignal]:
        """
        列出信号

        Args:
            status: 状态过滤
            subject_id: 主体过滤
            limit: 返回数量限制

        Returns:
            信号列表
        """
        signals = list(self.signals.values())

        if status:
            signals = [s for s in signals if s.status == status]
        if subject_id:
            signals = [s for s in signals if s.subject_id == subject_id]

        return signals[:limit]

    def validate_signal(
        self,
        signal: AlphaSignal,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        验证信号

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            验证结果
        """
        score = self.validator.score_signal(signal, **kwargs)
        features = self.validator.generate_features(signal.subject_id, **kwargs)
        backtest_result = self.validator.backtest(signal, **kwargs)

        return {
            "signal_id": signal.signal_id,
            "composite_score": score,
            "features": features,
            "backtest": backtest_result,
            "validated_at": datetime.utcnow().isoformat(),
        }

    def promote_signal(
        self,
        signal_id: str,
        new_status: str = "candidate",
    ) -> Optional[AlphaSignal]:
        """
        升级信号状态

        Args:
            signal_id: 信号ID
            new_status: 新状态

        Returns:
            更新后的信号对象
        """
        signal = self.get_signal(signal_id)
        if signal is None:
            logger.warning(f"Signal not found: {signal_id}")
            return None

        valid_statuses = ["research_only", "candidate", "paper_trade"]
        if new_status not in valid_statuses:
            logger.warning(f"Invalid status: {new_status}")
            return None

        current_idx = valid_statuses.index(signal.status)
        new_idx = valid_statuses.index(new_status)

        if new_idx < current_idx:
            logger.warning(f"Cannot demote signal from {signal.status} to {new_status}")
            return None

        signal.status = new_status
        logger.info(f"Promoted signal {signal_id} to {new_status}")
        return signal

    def generate_trade_candidate(
        self,
        signal: AlphaSignal,
        **kwargs: Any,
    ) -> TradeCandidate:
        """
        生成交易候选

        Args:
            signal: 信号对象
            **kwargs: 其他参数

        Returns:
            交易候选
        """
        return self.validator.generate_candidate(signal, **kwargs)
