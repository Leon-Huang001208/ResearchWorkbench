"""Outcome journal repository implementation for persistent storage of trade outcomes."""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import desc

from core.contracts.outcome_journal import FailureClassification, TradeOutcome
from core.observability import get_logger
from data_layer.repositories.base import BaseRepository
from data_layer.repositories.models import OutcomeRecordDB

logger = get_logger(__name__)


class OutcomeJournalRepository(BaseRepository):
    """Repository for outcome journal records."""

    def get_by_id(self, outcome_id: str) -> Optional[TradeOutcome]:
        """Get an outcome record by ID."""
        record = self.db.query(OutcomeRecordDB).filter_by(outcome_id=outcome_id).first()
        if not record:
            return None
        return self._to_contract(record)

    def list_by_signal_id(self, signal_id: str) -> List[TradeOutcome]:
        """List all outcome records for a given signal ID."""
        records = self.db.query(OutcomeRecordDB).filter_by(signal_id=signal_id).all()
        return [self._to_contract(r) for r in records]

    def list_by_failure_class(self, failure_class: FailureClassification) -> List[TradeOutcome]:
        """List all outcomes with a specific failure classification."""
        records = (
            self.db.query(OutcomeRecordDB)
            .filter_by(failure_classification=failure_class.value)
            .all()
        )
        return [self._to_contract(r) for r in records]

    def list_weekly(self, start_date: datetime, end_date: datetime) -> List[TradeOutcome]:
        """List all outcomes created between start and end date (UTC)."""
        records = (
            self.db.query(OutcomeRecordDB)
            .filter(OutcomeRecordDB.created_at >= start_date)
            .filter(OutcomeRecordDB.created_at <= end_date)
            .order_by(desc(OutcomeRecordDB.created_at))
            .all()
        )
        return [self._to_contract(r) for r in records]

    def list_all_failures(self) -> List[TradeOutcome]:
        """List all failed outcomes."""
        records = (
            self.db.query(OutcomeRecordDB)
            .filter_by(thesis_success=False)
            .filter(OutcomeRecordDB.failure_classification.isnot(None))
            .all()
        )
        return [self._to_contract(r) for r in records]

    def save(self, outcome: TradeOutcome) -> TradeOutcome:
        """Save or update an outcome record."""
        existing = self.db.query(OutcomeRecordDB).filter_by(outcome_id=outcome.outcome_id).first()

        if existing:
            existing.signal_id = outcome.signal_id
            existing.candidate_id = outcome.candidate_id
            existing.entry_time = outcome.entry_time
            existing.exit_time = outcome.exit_time
            existing.entry_price = outcome.entry_price
            existing.exit_price = outcome.exit_price
            existing.return_5d = outcome.return_5d
            existing.return_20d = outcome.return_20d
            existing.return_60d = outcome.return_60d
            existing.benchmark_excess_return = outcome.benchmark_excess_return
            existing.thesis_success = outcome.thesis_success
            existing.failure_classification = (
                outcome.failure_classification.value if outcome.failure_classification else None
            )
            existing.failure_notes = outcome.failure_notes
            existing.thesis_text = outcome.thesis_text
            existing.propagation_path = outcome.propagation_path
            existing.market_regime = outcome.market_regime
            db_record = existing
        else:
            db_record = OutcomeRecordDB(
                outcome_id=outcome.outcome_id,
                signal_id=outcome.signal_id,
                candidate_id=outcome.candidate_id,
                entry_time=outcome.entry_time,
                exit_time=outcome.exit_time,
                entry_price=outcome.entry_price,
                exit_price=outcome.exit_price,
                return_5d=outcome.return_5d,
                return_20d=outcome.return_20d,
                return_60d=outcome.return_60d,
                benchmark_excess_return=outcome.benchmark_excess_return,
                thesis_success=outcome.thesis_success,
                failure_classification=(
                    outcome.failure_classification.value if outcome.failure_classification else None
                ),
                failure_notes=outcome.failure_notes,
                thesis_text=outcome.thesis_text,
                propagation_path=outcome.propagation_path,
                market_regime=outcome.market_regime,
                created_at=outcome.created_at,
            )
            self.db.add(db_record)

        self.db.flush()
        return self._to_contract(db_record)

    def delete(self, outcome_id: str) -> bool:
        """Delete an outcome record by ID."""
        record = self.db.query(OutcomeRecordDB).filter_by(outcome_id=outcome_id).first()
        if not record:
            return False
        self.db.delete(record)
        self.db.flush()
        return True

    def count_by_failure_class(self) -> dict[FailureClassification, int]:
        """Count the number of failures by each failure classification."""
        from sqlalchemy import func

        results = (
            self.db.query(
                OutcomeRecordDB.failure_classification, func.count(OutcomeRecordDB.outcome_id)
            )
            .filter(OutcomeRecordDB.thesis_success.is_(False))
            .filter(OutcomeRecordDB.failure_classification.isnot(None))
            .group_by(OutcomeRecordDB.failure_classification)
            .all()
        )

        counts: dict[FailureClassification, int] = {}
        for failure_type_str, count in results:
            try:
                failure_type = FailureClassification(failure_type_str)
                counts[failure_type] = count
            except ValueError:
                logger.warning(f"Unknown failure classification {failure_type_str} in database")
                continue
        return counts

    def _to_contract(self, model: OutcomeRecordDB) -> TradeOutcome:
        """Convert ORM model to contract."""
        failure_class = None
        if model.failure_classification:
            try:
                failure_class = FailureClassification(model.failure_classification)
            except ValueError:
                logger.warning(f"Invalid failure classification {model.failure_classification}")

        return TradeOutcome(
            outcome_id=model.outcome_id,
            signal_id=model.signal_id,
            candidate_id=model.candidate_id,
            entry_time=model.entry_time,
            exit_time=model.exit_time,
            entry_price=float(model.entry_price),
            exit_price=float(model.exit_price),
            return_5d=float(model.return_5d) if model.return_5d is not None else None,
            return_20d=float(model.return_20d) if model.return_20d is not None else None,
            return_60d=float(model.return_60d) if model.return_60d is not None else None,
            benchmark_excess_return=float(model.benchmark_excess_return),
            thesis_success=model.thesis_success,
            failure_classification=failure_class,
            failure_notes=model.failure_notes,
            thesis_text=model.thesis_text,
            propagation_path=model.propagation_path,
            market_regime=model.market_regime,
            created_at=model.created_at,
        )
