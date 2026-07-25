"""Unit tests for failure memory engine and similar case retrieval."""

import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from core.contracts.outcome_journal import FailureClassification, TradeOutcome
from services.failure_memory_service import FailureMemoryService
from services.outcome_journal_service import OutcomeJournalService


@pytest.fixture
def isolated_failure_memory_db(monkeypatch, db_session):
    """Route outcome and failure-memory services through the in-memory database."""

    @contextmanager
    def session_context():
        yield db_session

    monkeypatch.setattr("services.failure_memory_service.db_session", session_context)
    monkeypatch.setattr("services.outcome_journal_service.db_session", session_context)


def test_similarity_calculation():
    """Test that similarity calculation works."""
    service = FailureMemoryService()

    # Similar theses should have higher similarity than dissimilar
    thesis1 = "Company earnings will grow faster than expected due to new product launch"
    thesis2 = "Faster than expected earnings growth from the new product should lead to price appreciation"
    thesis3 = "Interest rate hikes will cause valuation contraction in growth stocks"

    sim1 = service._calculate_similarity(thesis1, thesis2)
    sim2 = service._calculate_similarity(thesis1, thesis3)

    assert sim1 > sim2


def test_retrieve_similar_cases(isolated_failure_memory_db):
    """Test retrieving similar cases from failure memory."""
    service = FailureMemoryService()

    # Add a test failure to search for
    outcome_service = OutcomeJournalService()
    outcome_id = str(uuid.uuid4())
    test_unique_marker = f"unique_test_marker_{outcome_id}"
    now = datetime.now(timezone.utc)

    outcome = TradeOutcome(
        outcome_id=outcome_id,
        signal_id=str(uuid.uuid4()),
        entry_time=now,
        exit_time=now,
        entry_price=100.0,
        exit_price=90.0,
        benchmark_excess_return=-0.1,
        thesis_success=False,
        failure_classification=FailureClassification.wrong_thesis,
        thesis_text=f"Unique test thesis about {test_unique_marker} semiconductor supply chain disruption",
        market_regime="bear",
    )
    outcome_service.record_outcome(outcome)

    # Search for similar theses using the unique marker
    similar = service.retrieve_similar_cases(
        f"Semiconductor supply chain disruption related to {test_unique_marker}",
        min_similarity=0.1,
        limit=5,
    )

    assert isinstance(similar, list)
    # Should find at least our test case
    assert any(case.outcome_id == outcome_id for case in similar)


def test_retrieve_similar_failures(isolated_failure_memory_db):
    """Test retrieving only similar failures."""
    service = FailureMemoryService()
    similar = service.retrieve_similar_failures(
        "Interest rate increase will impact growth stock valuations",
        min_similarity=0.1,
        limit=10,
    )
    assert isinstance(similar, list)
    for case in similar:
        assert case.is_success is False


def test_retrieve_similar_successes(isolated_failure_memory_db):
    """Test retrieving only similar successes."""
    service = FailureMemoryService()
    similar = service.retrieve_similar_successes(
        "Company earnings beat will drive price increase",
        min_similarity=0.1,
        limit=10,
    )
    assert isinstance(similar, list)
    for case in similar:
        assert case.is_success is True


def test_get_all_categorized_failures(isolated_failure_memory_db):
    """Test getting all categorized failures from memory."""
    service = FailureMemoryService()
    failures = service.get_all_categorized_failures()
    assert isinstance(failures, list)
    for failure in failures:
        assert failure.thesis_success is False
        assert failure.failure_classification is not None
