"""信号结果评估仓储实现"""

from typing import Any, Dict, List, Optional

from core.contracts.outcomes import SignalOutcome
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import SignalOutcomeDB

logger = get_logger(__name__)


class OutcomeRepositoryImpl(BaseRepository):
    """信号结果评估仓储实现"""

    def save(self, outcome: SignalOutcome) -> SignalOutcome:
        """保存结果评估"""
        event_type = outcome.metadata.get("event_type") if outcome.metadata else None
        existing = self.db.query(SignalOutcomeDB).filter_by(outcome_id=outcome.outcome_id).first()
        if existing:
            existing.event_id = outcome.event_id
            existing.signal_id = outcome.signal_id
            existing.subject_id = outcome.subject_id
            existing.event_date = outcome.event_date
            existing.event_type = event_type
            existing.timing_action = outcome.timing_action
            existing.entry_rule = outcome.entry_rule
            existing.horizon = outcome.horizon
            existing.benchmark = outcome.benchmark
            existing.outcome_return = outcome.outcome_return
            existing.outcome_excess_return = outcome.outcome_excess_return
            existing.max_drawdown = outcome.max_drawdown
            existing.decay = outcome.decay
            existing.failure_reason = outcome.failure_reason
            existing.lesson = outcome.lesson
            existing.evaluated_at = outcome.evaluated_at
            existing.outcome_metadata = outcome.metadata
            db_outcome = existing
        else:
            db_outcome = SignalOutcomeDB(
                outcome_id=outcome.outcome_id,
                event_id=outcome.event_id,
                signal_id=outcome.signal_id,
                subject_id=outcome.subject_id,
                event_date=outcome.event_date,
                event_type=event_type,
                timing_action=outcome.timing_action,
                entry_rule=outcome.entry_rule,
                horizon=outcome.horizon,
                benchmark=outcome.benchmark,
                outcome_return=outcome.outcome_return,
                outcome_excess_return=outcome.outcome_excess_return,
                max_drawdown=outcome.max_drawdown,
                decay=outcome.decay,
                failure_reason=outcome.failure_reason,
                lesson=outcome.lesson,
                evaluated_at=outcome.evaluated_at,
                outcome_metadata=outcome.metadata,
            )
            self.db.add(db_outcome)
        self.db.flush()
        logger.info("outcome saved", outcome_id=outcome.outcome_id, signal_id=outcome.signal_id)
        return self._to_domain(db_outcome)

    def get(self, outcome_id: str) -> Optional[SignalOutcome]:
        """按 ID 获取结果评估"""
        db_outcome = (
            self.db.query(SignalOutcomeDB).filter(SignalOutcomeDB.outcome_id == outcome_id).first()
        )
        if not db_outcome:
            return None
        return self._to_domain(db_outcome)

    def get_by_signal_id(self, signal_id: str) -> Optional[SignalOutcome]:
        """按 signal_id 获取结果评估"""
        db_outcome = (
            self.db.query(SignalOutcomeDB).filter(SignalOutcomeDB.signal_id == signal_id).first()
        )
        if not db_outcome:
            return None
        return self._to_domain(db_outcome)

    def list(
        self,
        event_type: Optional[str] = None,
        strategy_family: Optional[str] = None,
        limit: int = 100,
    ) -> List[SignalOutcome]:
        """列出结果评估。

        Args:
            event_type: 按事件类型过滤（使用 event_type 列）
            strategy_family: 按策略家族过滤（匹配 metadata 中的 strategy_family）
            limit: 返回数量限制
        """
        query = self.db.query(SignalOutcomeDB)
        if event_type is not None:
            query = query.filter(SignalOutcomeDB.event_type == event_type)
        if strategy_family is not None:
            query = query.filter(
                SignalOutcomeDB.outcome_metadata.contains({"strategy_family": strategy_family})
            )
        db_outcomes = query.order_by(SignalOutcomeDB.created_at.desc()).limit(limit).all()
        return [self._to_domain(o) for o in db_outcomes]

    def update_lesson(self, outcome_id: str, lesson: str) -> Optional[SignalOutcome]:
        """更新教训字段"""
        db_outcome = (
            self.db.query(SignalOutcomeDB).filter(SignalOutcomeDB.outcome_id == outcome_id).first()
        )
        if not db_outcome:
            return None
        db_outcome.lesson = lesson
        self.db.flush()
        logger.info("lesson updated", outcome_id=outcome_id)
        return self._to_domain(db_outcome)

    def _to_domain(self, db_outcome: SignalOutcomeDB) -> SignalOutcome:
        """转换为领域模型"""
        metadata: Dict[str, Any] = (
            dict(db_outcome.outcome_metadata) if db_outcome.outcome_metadata else {}
        )
        if db_outcome.event_type:
            metadata["event_type"] = db_outcome.event_type
        return SignalOutcome(
            outcome_id=db_outcome.outcome_id,
            event_id=db_outcome.event_id,
            signal_id=db_outcome.signal_id,
            subject_id=db_outcome.subject_id,
            event_date=db_outcome.event_date,
            timing_action=db_outcome.timing_action,
            entry_rule=db_outcome.entry_rule,
            horizon=db_outcome.horizon,
            benchmark=db_outcome.benchmark,
            outcome_return=float(db_outcome.outcome_return),
            outcome_excess_return=float(db_outcome.outcome_excess_return),
            max_drawdown=(
                float(db_outcome.max_drawdown) if db_outcome.max_drawdown is not None else None
            ),
            decay=float(db_outcome.decay) if db_outcome.decay is not None else None,
            failure_reason=db_outcome.failure_reason,
            lesson=db_outcome.lesson,
            evaluated_at=db_outcome.evaluated_at,
            metadata=metadata,
        )
