"""Outcome journal service for recording and managing trade outcomes."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from core.contracts.outcome_journal import FailureClassification, TradeOutcome, WeeklyReviewReport
from core.observability import get_logger
from data_layer.repositories.base import db_session
from data_layer.repositories.outcome_journal_repository import OutcomeJournalRepository

logger = get_logger(__name__)


class OutcomeJournalService:
    """Service for managing the outcome journal."""

    def __init__(self, repository: Optional[OutcomeJournalRepository] = None):
        self._repository = repository

    @property
    def repository(self) -> OutcomeJournalRepository:
        """Get repository with database session."""
        if self._repository is None:
            with db_session() as db:
                self._repository = OutcomeJournalRepository(db)
        return self._repository

    def record_outcome(self, outcome: TradeOutcome) -> TradeOutcome:
        """Record a new trade outcome. If outcome_id is not provided, generate one."""
        if not outcome.outcome_id:
            outcome.outcome_id = str(uuid.uuid4())

        if self._repository is not None:
            return self._repository.save(outcome)

        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.save(outcome)

    def get_outcome(self, outcome_id: str) -> Optional[TradeOutcome]:
        """Get an outcome by ID."""
        if self._repository is not None:
            return self._repository.get_by_id(outcome_id)

        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.get_by_id(outcome_id)

    def list_outcomes_for_signal(self, signal_id: str) -> List[TradeOutcome]:
        """List all outcomes for a signal."""
        if self._repository is not None:
            return self._repository.list_by_signal_id(signal_id)

        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.list_by_signal_id(signal_id)

    def list_failures_by_class(self, failure_class: FailureClassification) -> List[TradeOutcome]:
        """List all failures of a specific class."""
        if self._repository is not None:
            return self._repository.list_by_failure_class(failure_class)

        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.list_by_failure_class(failure_class)

    def generate_weekly_review(self, weeks_ago: int = 0) -> WeeklyReviewReport:
        """Generate a weekly review report for the given week (default is current week)."""
        # Calculate week start and end (Monday to Sunday UTC)
        today = datetime.now(timezone.utc).date()
        start_of_week = today - timedelta(days=today.weekday() + 7 * weeks_ago)
        end_of_week = start_of_week + timedelta(days=6)

        # Convert to datetimes with timezone
        start_datetime = datetime.combine(start_of_week, datetime.min.time(), tzinfo=timezone.utc)
        end_datetime = datetime.combine(end_of_week, datetime.max.time(), tzinfo=timezone.utc)

        if self._repository is not None:
            outcomes = self._repository.list_weekly(start_datetime, end_datetime)
            failure_counts = self._repository.count_by_failure_class()
        else:
            with db_session() as db:
                repo = OutcomeJournalRepository(db)
                outcomes = repo.list_weekly(start_datetime, end_datetime)
                failure_counts = repo.count_by_failure_class()

        total = len(outcomes)
        successful = sum(1 for o in outcomes if o.thesis_success)
        failed = total - successful
        success_rate = (successful / total) * 100 if total > 0 else 0.0

        most_common_failure = None
        if failure_counts:
            most_common_failure = max(failure_counts.items(), key=lambda x: x[1])[0]

        # Collect top lessons (simple approach: take failure notes from top failures)
        top_lessons: List[str] = []
        for outcome in outcomes:
            if not outcome.thesis_success and outcome.failure_notes:
                top_lessons.append(outcome.failure_notes)
                if len(top_lessons) >= 5:
                    break

        report_id = str(uuid.uuid4())

        return WeeklyReviewReport(
            report_id=report_id,
            week_start_date=start_datetime,
            week_end_date=end_datetime,
            total_outcomes=total,
            successful_outcomes=successful,
            failed_outcomes=failed,
            success_rate=success_rate,
            failure_distribution=failure_counts,
            top_lessons=top_lessons,
            most_common_failure=most_common_failure,
        )

    def count_failure_distribution(self) -> Dict[FailureClassification, int]:
        """Get the current failure distribution across all outcomes."""
        if self._repository is not None:
            return self._repository.count_by_failure_class()

        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.count_by_failure_class()
