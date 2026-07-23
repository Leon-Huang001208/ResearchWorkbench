"""Unit tests for outcome_service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

from core.contracts.outcomes import SignalOutcome
from services.outcome_service import OutcomeService


def test_record_outcome_basic():
    """Test recording a basic outcome."""
    service = OutcomeService()

    outcome_id = str(uuid.uuid4())
    outcome = SignalOutcome(
        outcome_id=outcome_id,
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.02,
        timing_action="enter",
    )

    result = service.record_outcome(outcome)

    assert result is not None
    assert result.outcome_id == outcome_id
    assert result.evaluated_at is not None


def test_record_outcome_with_metadata():
    """Test recording an outcome with metadata."""
    service = OutcomeService()

    outcome = SignalOutcome(
        outcome_id=str(uuid.uuid4()),
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600036.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.1,
        outcome_excess_return=0.08,
        timing_action="enter",
        metadata={"event_type": "earnings", "market_regime": "bull"},
    )

    result = service.record_outcome(outcome)

    assert result is not None
    assert result.metadata["event_type"] == "earnings"
    assert result.metadata["market_regime"] == "bull"


def test_get_outcome():
    """Test retrieving an outcome by ID."""
    service = OutcomeService()

    outcome = SignalOutcome(
        outcome_id="test_outcome_123",
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.02,
        timing_action="enter",
    )

    service.record_outcome(outcome)
    retrieved = service.get_outcome("test_outcome_123")

    assert retrieved is not None
    assert retrieved.outcome_id == "test_outcome_123"
    assert retrieved.subject_id == "600519.SH"


def test_get_outcome_not_found():
    """Test retrieving non-existent outcome returns None."""
    service = OutcomeService()
    assert service.get_outcome("non_existent_id") is None


def test_get_outcome_by_signal():
    """Test retrieving outcome by signal ID."""
    service = OutcomeService()

    signal_id = str(uuid.uuid4())
    outcome = SignalOutcome(
        outcome_id=str(uuid.uuid4()),
        signal_id=signal_id,
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.02,
        timing_action="enter",
    )

    service.record_outcome(outcome)
    retrieved = service.get_outcome_by_signal(signal_id)

    assert retrieved is not None
    assert retrieved.signal_id == signal_id


def test_get_outcome_by_signal_not_found():
    """Test retrieving outcome by non-existent signal returns None."""
    service = OutcomeService()
    assert service.get_outcome_by_signal("non_existent_signal") is None


def test_list_outcomes():
    """Test listing outcomes."""
    service = OutcomeService()

    for i in range(5):
        outcome = SignalOutcome(
            outcome_id=str(uuid.uuid4()),
            signal_id=str(uuid.uuid4()),
            event_id=str(uuid.uuid4()),
            subject_id=f"600519.SH_{i}",
            horizon="20d",
            event_date=datetime.now(timezone.utc),
            outcome_return=0.05,
            outcome_excess_return=0.02,
            timing_action="enter",
            metadata={"event_type": "earnings" if i % 2 == 0 else "news"},
        )
        service.record_outcome(outcome)

    all_outcomes = service.list_outcomes()
    assert len(all_outcomes) == 5

    filtered_earnings = service.list_outcomes(event_type="earnings")
    assert len(filtered_earnings) == 3

    limited = service.list_outcomes(limit=2)
    assert len(limited) == 2


def test_update_lesson():
    """Test updating the lesson for an outcome."""
    service = OutcomeService()

    outcome_id = str(uuid.uuid4())
    outcome = SignalOutcome(
        outcome_id=outcome_id,
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=-0.05,
        outcome_excess_return=-0.08,
        timing_action="enter",
        failure_reason="Timing was off",
    )

    service.record_outcome(outcome)
    updated = service.update_lesson(outcome_id, "Avoid entering before earnings")

    assert updated is not None
    assert updated.lesson == "Avoid entering before earnings"


def test_update_lesson_not_found():
    """Test updating lesson for non-existent outcome returns None."""
    service = OutcomeService()
    assert service.update_lesson("non_existent_id", "Lesson") is None


def test_outcome_service_with_mock_repository():
    """Test outcome service with mock repository."""
    mock_repo = MagicMock()
    mock_outcome = SignalOutcome(
        outcome_id="test_outcome_456",
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.02,
        timing_action="enter",
    )
    mock_repo.save.return_value = mock_outcome

    service = OutcomeService(repository=mock_repo)
    outcome = SignalOutcome(
        outcome_id=str(uuid.uuid4()),
        signal_id=str(uuid.uuid4()),
        event_id=str(uuid.uuid4()),
        subject_id="600519.SH",
        horizon="20d",
        event_date=datetime.now(timezone.utc),
        outcome_return=0.05,
        outcome_excess_return=0.02,
        timing_action="enter",
    )
    result = service.record_outcome(outcome)

    mock_repo.save.assert_called_once()
    assert result.outcome_id == "test_outcome_456"
