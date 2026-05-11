"""Unit tests for outcome journal implementation."""
import uuid
from datetime import datetime, timedelta, timezone

from core.contracts.outcome_journal import FailureClassification, TradeOutcome
from core.services.outcome_journal_service import OutcomeJournalService
from data_layer.repositories.base import db_session
from data_layer.repositories.outcome_journal_repository import OutcomeJournalRepository


def test_create_and_retrieve_outcome():
    """Test creating a new outcome and retrieving it."""
    outcome_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    outcome = TradeOutcome(
        outcome_id=outcome_id,
        signal_id=str(uuid.uuid4()),
        entry_time=now - timedelta(days=5),
        exit_time=now,
        entry_price=100.0,
        exit_price=105.0,
        return_5d=0.05,
        benchmark_excess_return=0.02,
        thesis_success=True,
        thesis_text="This is a test thesis about company earnings growth exceeding expectations",
        market_regime="bull",
    )

    service = OutcomeJournalService()
    saved = service.record_outcome(outcome)
    assert saved is not None
    assert saved.outcome_id == outcome_id
    assert saved.thesis_success is True

    retrieved = service.get_outcome(outcome_id)
    assert retrieved is not None
    assert retrieved.outcome_id == outcome_id
    assert retrieved.entry_price == 100.0
    assert retrieved.exit_price == 105.0
    assert abs(retrieved.benchmark_excess_return - 0.02) < 0.0001


def test_failed_outcome_with_classification():
    """Test saving a failed outcome with failure classification."""
    outcome_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    outcome = TradeOutcome(
        outcome_id=outcome_id,
        signal_id=str(uuid.uuid4()),
        entry_time=now - timedelta(days=5),
        exit_time=now,
        entry_price=100.0,
        exit_price=95.0,
        return_5d=-0.05,
        benchmark_excess_return=-0.04,
        thesis_success=False,
        failure_classification=FailureClassification.timing_error,
        failure_notes="Entered too early before earnings announcement",
        thesis_text="Thesis that market would react positively to earnings but timing was off",
        market_regime="volatile",
    )

    service = OutcomeJournalService()
    saved = service.record_outcome(outcome)
    assert saved.failure_classification == FailureClassification.timing_error

    retrieved = service.get_outcome(outcome_id)
    assert retrieved is not None
    assert retrieved.thesis_success is False
    assert retrieved.failure_classification == FailureClassification.timing_error
    assert retrieved.failure_notes == "Entered too early before earnings announcement"


def test_list_by_failure_class():
    """Test listing outcomes by failure classification."""
    service = OutcomeJournalService()
    failures = service.list_failures_by_class(FailureClassification.timing_error)
    assert isinstance(failures, list)


def test_generate_weekly_review():
    """Test generating a weekly review report."""
    service = OutcomeJournalService()
    report = service.generate_weekly_review(weeks_ago=0)
    assert report is not None
    assert report.report_id is not None
    assert report.total_outcomes >= 0
    assert 0 <= report.success_rate <= 100


def test_repository_count_by_failure_class():
    """Test that repository correctly counts failures by classification."""
    with db_session() as db:
        repo = OutcomeJournalRepository(db)
        counts = repo.count_by_failure_class()
        assert isinstance(counts, dict)
        # All keys should be FailureClassification enum
        for key in counts.keys():
            assert isinstance(key, FailureClassification)
