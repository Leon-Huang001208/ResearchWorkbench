"""
信号服务

提供信号生成和管理功能。
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.contracts import AlphaSignal, EventAlphaSignal, TradeCandidate
from core.interfaces import SignalValidator
from core.observability import get_logger
from core.settings.config import settings
from data_layer.repositories.signal_repository import SignalRepositoryImpl
from services.signal_validator_impl import SignalValidatorImpl

logger = get_logger(__name__)


class SignalService:
    """信号服务"""

    def __init__(
        self,
        validator: Optional[SignalValidator] = None,
        repository: Optional[SignalRepositoryImpl] = None,
    ):
        """
        初始化信号服务

        Args:
            validator: 信号验证器
            repository: 信号仓储（可选，启用持久化）
        """
        self.validator = validator or SignalValidatorImpl()
        self.repository = repository
        self.signals: Dict[str, AlphaSignal] = {}  # fallback if no repo

        if settings.APP_ENV == "prod" and self.repository is None:
            raise RuntimeError(
                "SignalService: No repository provided in production mode (APP_ENV=prod). "
                "In-memory fallback is not allowed in production for durable persistence."
            )

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

        if self.repository:
            signal = self.repository.save(signal)
        else:
            self.signals[signal.signal_id] = signal
        logger.info(f"Created signal: {signal.signal_id} for {subject_id}")
        return signal

    def create_event_signal(
        self,
        event_id: str,
        event_type: str,
        subject_id: str,
        thesis: str,
        horizon: str = "20d",
        score: float = 0.5,
        confidence: float = 0.5,
        event_time: Optional[datetime] = None,
        impact_path: Optional[List[str]] = None,
        industry_impacts: Optional[List[str]] = None,
        bullish_companies: Optional[List[str]] = None,
        bearish_companies: Optional[List[str]] = None,
        scenario_refs: Optional[List[str]] = None,
        evidence_refs: Optional[List[str]] = None,
        status: str = "research_only",
        **kwargs: Any,
    ) -> EventAlphaSignal:
        """
        创建事件型信号

        Args:
            event_id: 事件ID
            event_type: 事件类型
            subject_id: 主体ID
            thesis: 研究论点
            horizon: 预测期
            score: 分数
            confidence: 置信度
            event_time: 事件时间
            impact_path: 影响路径
            industry_impacts: 行业影响
            bullish_companies: 看涨公司
            bearish_companies: 看跌公司
            scenario_refs: 情景引用
            evidence_refs: 证据引用
            status: 状态
            **kwargs: 其他参数

        Returns:
            事件型信号对象
        """
        signal = EventAlphaSignal(
            signal_id=str(uuid.uuid4()),
            event_id=event_id,
            event_type=event_type,
            subject_id=subject_id,
            horizon=horizon,
            thesis=thesis,
            score=score,
            confidence=confidence,
            event_time=event_time,
            impact_path=impact_path or [],
            industry_impacts=industry_impacts or [],
            bullish_companies=bullish_companies or [],
            bearish_companies=bearish_companies or [],
            scenario_refs=scenario_refs or [],
            evidence_refs=evidence_refs or [],
            status=status,
        )

        if self.repository:
            signal = self.repository.save(signal)
        else:
            self.signals[signal.signal_id] = signal
        logger.info(f"Created event signal: {signal.signal_id} for {event_id}")
        return signal

    def get_signal(self, signal_id: str) -> Optional[AlphaSignal]:
        """
        获取信号

        Args:
            signal_id: 信号ID

        Returns:
            信号对象（如果存在）
        """
        if self.repository:
            return self.repository.get(signal_id)
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
        if self.repository:
            return self.repository.list(status=status, subject_id=subject_id, limit=limit)

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

    def validate_event_signal(
        self,
        signal: EventAlphaSignal,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        验证事件型信号

        Args:
            signal: 事件型信号对象
            **kwargs: 其他参数

        Returns:
            验证结果
        """
        validation_result = self.validate_signal(signal, **kwargs)
        if self.repository:
            signal.validation_status = (
                "validated" if validation_result["composite_score"] >= 0.6 else "rejected"
            )
            signal.validation_metrics = validation_result
            self.repository.save(signal)
        return validation_result

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
        if self.repository:
            signal = self.repository.update_status(signal_id, new_status)
        else:
            self.signals[signal_id] = signal
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
        candidate = self.validator.generate_candidate(signal, **kwargs)
        if self.repository:
            self.repository.save_trade_candidate(candidate)
        return candidate
