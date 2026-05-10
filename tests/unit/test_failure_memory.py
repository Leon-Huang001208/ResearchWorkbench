"""Unit tests for failure memory engine and similar case retrieval."""
import uuid
from datetime import datetime, timezone

from core.contracts.outcome_journal import FailureClassification, TradeOutcome
from core.services.failure_memory_service import FailureMemoryService
from core.services.outcome_journal_service import OutcomeJournalService


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


def test_retrieve_similar_cases():
    """Test retrieving similar cases from failure memory."""
    service = FailureMemoryService()

    # Add a test failure to search for
    outcome_service = OutcomeJournalService()
    outcome_id = str(uuid.uuid4())
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
        thesis_text="Earnings growth will exceed market expectations for this tech company",
        market_regime="bear",
    )
    outcome_service.record_outcome(outcome)

    # Search for similar theses
    similar = service.retrieve_similar_cases(
        "Tech company earnings are expected to grow faster than the market expects",
        min_similarity=0.2,
        limit=5,
    )

    assert isinstance(similar, list)
    # Should find at least our test case
    assert any(case.outcome_id == outcome_id for case in similar)


def test_retrieve_similar_failures():
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


def test_retrieve_similar_successes():
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


def test_get_all_categorized_failures():
    """Test getting all categorized failures from memory."""
    service = FailureMemoryService()
    failures = service.get_all_categorized_failures()
    assert isinstance(failures, list)
    for failure in failures:
        assert failure.thesis_success is False
        assert failure.failure_classification is not None
