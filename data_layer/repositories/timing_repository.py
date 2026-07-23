"""Timing Engine 择时决策仓储实现"""

import uuid
from typing import List, Optional

from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import TimingDecisionDB
from timing_engine.contracts import TimingDecision, TimingModelScore

logger = get_logger(__name__)


class TimingRepositoryImpl(BaseRepository):
    """Timing 决策仓储实现"""

    def save(self, decision: TimingDecision) -> TimingDecision:
        """保存择时决策，如果没有 decision_id，自动生成一个"""
        decision_id = getattr(decision, "decision_id", None)
        if not decision_id:
            decision_id = str(uuid.uuid4())
            # 给 decision 添加 decision_id，返回的时候包含它
            object.__setattr__(decision, "decision_id", decision_id)

        existing = self.db.query(TimingDecisionDB).filter_by(decision_id=decision_id).first()
        if existing:
            existing.signal_id = decision.signal_id
            existing.action = decision.action
            existing.readiness_score = decision.readiness_score
            existing.market_regime = decision.market_regime
            # Convert model_scores to list of dicts for JSON storage
            existing.model_scores = [m.model_dump() for m in decision.model_scores]
            existing.active_weights = decision.active_weights
            existing.blockers = decision.blockers
            existing.rationale = decision.rationale
            db_decision = existing
        else:
            db_decision = TimingDecisionDB(
                decision_id=decision_id,
                signal_id=decision.signal_id,
                action=decision.action,
                readiness_score=decision.readiness_score,
                market_regime=decision.market_regime,
                model_scores=[m.model_dump() for m in decision.model_scores],
                active_weights=decision.active_weights,
                blockers=decision.blockers,
                rationale=decision.rationale,
            )
            self.db.add(db_decision)

        self.db.flush()
        logger.info(f"Saved timing decision: {decision_id} for signal: {decision.signal_id}")
        return self._to_domain(db_decision)

    def get(self, decision_id: str) -> Optional[TimingDecision]:
        """根据 ID 获取择时决策"""
        db_decision = (
            self.db.query(TimingDecisionDB)
            .filter(TimingDecisionDB.decision_id == decision_id)
            .first()
        )
        if not db_decision:
            return None
        return self._to_domain(db_decision)

    def list(
        self,
        signal_id: Optional[str] = None,
        action: Optional[str] = None,
        limit: int = 100,
    ) -> List[TimingDecision]:
        """列出择时决策，支持按 signal_id 和 action 过滤"""
        query = self.db.query(TimingDecisionDB)

        if signal_id:
            query = query.filter(TimingDecisionDB.signal_id == signal_id)
        if action:
            query = query.filter(TimingDecisionDB.action == action)

        db_decisions = query.order_by(TimingDecisionDB.created_at.desc()).limit(limit).all()
        return [self._to_domain(d) for d in db_decisions]

    def get_latest_for_signal(self, signal_id: str) -> Optional[TimingDecision]:
        """获取某个信号最新的择时决策"""
        db_decision = (
            self.db.query(TimingDecisionDB)
            .filter(TimingDecisionDB.signal_id == signal_id)
            .order_by(TimingDecisionDB.created_at.desc())
            .first()
        )

        if not db_decision:
            return None
        return self._to_domain(db_decision)

    def _to_domain(self, db_decision: TimingDecisionDB) -> TimingDecision:
        """转换为领域模型"""
        # 解析 model_scores
        model_scores = []
        for score_dict in db_decision.model_scores:
            try:
                model_scores.append(TimingModelScore(**score_dict))
            except Exception as e:
                logger.warning(f"Failed to parse TimingModelScore: {e}, skipping: {score_dict}")

        return TimingDecision(
            decision_id=db_decision.decision_id,
            signal_id=db_decision.signal_id,
            action=db_decision.action,
            readiness_score=float(db_decision.readiness_score),
            market_regime=db_decision.market_regime,
            model_scores=model_scores,
            active_weights=db_decision.active_weights,
            blockers=db_decision.blockers,
            rationale=db_decision.rationale,
        )
