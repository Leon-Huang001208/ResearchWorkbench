"""信号仓储实现"""
from typing import List, Optional
from sqlalchemy.orm import Session

from core.contracts import AlphaSignal, EventAlphaSignal, TradeCandidate
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import AlphaSignalDB, TradeCandidateDB

logger = get_logger(__name__)


class SignalRepositoryImpl(BaseRepository):
    """信号仓储实现"""

    def save(self, signal: AlphaSignal) -> AlphaSignal:
        """保存信号"""
        existing = self.db.query(AlphaSignalDB).filter_by(signal_id=signal.signal_id).first()
        if existing:
            existing.subject_id = signal.subject_id
            existing.horizon = signal.horizon
            existing.thesis = signal.thesis
            existing.score = signal.score
            existing.confidence = signal.confidence
            existing.scenario_refs = signal.scenario_refs
            existing.evidence_refs = signal.evidence_refs
            existing.status = signal.status
            if isinstance(signal, EventAlphaSignal):
                existing.discriminator = "event_alpha_signal"
                existing.event_id = signal.event_id
                existing.event_type = signal.event_type
                existing.event_time = signal.event_time
                existing.impact_path = signal.impact_path
                existing.industry_impacts = signal.industry_impacts
                existing.bullish_companies = signal.bullish_companies
                existing.bearish_companies = signal.bearish_companies
                existing.diffusion_stage = signal.diffusion_stage
                existing.market_regime = signal.market_regime
                existing.validation_status = signal.validation_status
                existing.validation_metrics = signal.validation_metrics
            db_signal = existing
        else:
            db_signal = AlphaSignalDB(
                signal_id=signal.signal_id,
                discriminator="event_alpha_signal" if isinstance(signal, EventAlphaSignal) else "alpha_signal",
                subject_id=signal.subject_id,
                horizon=signal.horizon,
                thesis=signal.thesis,
                score=signal.score,
                confidence=signal.confidence,
                scenario_refs=signal.scenario_refs,
                evidence_refs=signal.evidence_refs,
                status=signal.status,
            )

            if isinstance(signal, EventAlphaSignal):
                db_signal.event_id = signal.event_id
                db_signal.event_type = signal.event_type
                db_signal.event_time = signal.event_time
                db_signal.impact_path = signal.impact_path
                db_signal.industry_impacts = signal.industry_impacts
                db_signal.bullish_companies = signal.bullish_companies
                db_signal.bearish_companies = signal.bearish_companies
                db_signal.diffusion_stage = signal.diffusion_stage
                db_signal.market_regime = signal.market_regime
                db_signal.validation_status = signal.validation_status
                db_signal.validation_metrics = signal.validation_metrics
            self.db.add(db_signal)
        self.db.flush()
        logger.info(f"Saved signal: {signal.signal_id}")
        return self._to_domain(db_signal)

    def get(self, signal_id: str) -> Optional[AlphaSignal]:
        """获取信号"""
        db_signal = self.db.query(AlphaSignalDB).filter(AlphaSignalDB.signal_id == signal_id).first()
        if not db_signal:
            return None
        return self._to_domain(db_signal)

    def list(
        self,
        status: Optional[str] = None,
        subject_id: Optional[str] = None,
        limit: int = 100,
    ) -> List[AlphaSignal]:
        """列出信号"""
        query = self.db.query(AlphaSignalDB)
        if status:
            query = query.filter(AlphaSignalDB.status == status)
        if subject_id:
            query = query.filter(AlphaSignalDB.subject_id == subject_id)
        db_signals = query.order_by(AlphaSignalDB.created_at.desc()).limit(limit).all()
        return [self._to_domain(s) for s in db_signals]

    def update_status(self, signal_id: str, new_status: str) -> Optional[AlphaSignal]:
        """更新信号状态"""
        db_signal = self.db.query(AlphaSignalDB).filter(AlphaSignalDB.signal_id == signal_id).first()
        if not db_signal:
            return None
        db_signal.status = new_status
        self.db.flush()
        logger.info(f"Updated signal status: {signal_id} -> {new_status}")
        return self._to_domain(db_signal)

    def save_trade_candidate(self, candidate: TradeCandidate) -> TradeCandidate:
        """保存交易候选"""
        existing = self.db.query(TradeCandidateDB).filter_by(candidate_id=candidate.candidate_id).first()
        if existing:
            existing.signal_id = candidate.signal_id
            existing.action = candidate.action
            existing.sizing_hint = candidate.sizing_hint
            existing.risk_notes = candidate.risk_notes
            db_candidate = existing
        else:
            db_candidate = TradeCandidateDB(
                candidate_id=candidate.candidate_id,
                signal_id=candidate.signal_id,
                action=candidate.action,
                sizing_hint=candidate.sizing_hint,
                risk_notes=candidate.risk_notes,
            )
            self.db.add(db_candidate)
        self.db.flush()
        logger.info(f"Saved trade candidate: {candidate.candidate_id}")
        return candidate

    def _to_domain(self, db_signal: AlphaSignalDB) -> AlphaSignal:
        """转换为领域模型"""
        if db_signal.discriminator == "event_alpha_signal":
            return EventAlphaSignal(
                signal_id=db_signal.signal_id,
                subject_id=db_signal.subject_id,
                horizon=db_signal.horizon,
                thesis=db_signal.thesis,
                score=float(db_signal.score),
                confidence=float(db_signal.confidence),
                scenario_refs=db_signal.scenario_refs,
                evidence_refs=db_signal.evidence_refs,
                status=db_signal.status,
                event_id=db_signal.event_id,
                event_type=db_signal.event_type,
                event_time=db_signal.event_time,
                impact_path=db_signal.impact_path,
                industry_impacts=db_signal.industry_impacts,
                bullish_companies=db_signal.bullish_companies,
                bearish_companies=db_signal.bearish_companies,
                diffusion_stage=db_signal.diffusion_stage,
                market_regime=db_signal.market_regime,
                validation_status=db_signal.validation_status,
                validation_metrics=db_signal.validation_metrics,
            )
        return AlphaSignal(
            signal_id=db_signal.signal_id,
            subject_id=db_signal.subject_id,
            horizon=db_signal.horizon,
            thesis=db_signal.thesis,
            score=float(db_signal.score),
            confidence=float(db_signal.confidence),
            scenario_refs=db_signal.scenario_refs,
            evidence_refs=db_signal.evidence_refs,
            status=db_signal.status,
        )
