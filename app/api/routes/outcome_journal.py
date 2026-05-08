"""API routes for outcome journal and failure memory engine."""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException

from core.contracts.outcome_journal import (
    TradeOutcome,
    SimilarCase,
    WeeklyReviewReport,
    FailureClassification,
)
from core.services.outcome_journal_service import OutcomeJournalService
from core.services.failure_memory_service import FailureMemoryService
from data_layer.repositories.base import get_db

router = APIRouter()
outcome_journal_service = OutcomeJournalService()
failure_memory_service = FailureMemoryService()


@router.post("/", response_model=TradeOutcome, tags=["outcome-journal"])
def record_outcome(
    outcome: TradeOutcome,
):
    """Record a new trade outcome in the outcome journal."""
    try:
        return outcome_journal_service.record_outcome(outcome)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to record outcome: {str(e)}")


@router.get("/{outcome_id}", response_model=Optional[TradeOutcome], tags=["outcome-journal"])
def get_outcome(
    outcome_id: str,
):
    """Get an outcome record by ID."""
    outcome = outcome_journal_service.get_outcome(outcome_id)
    if not outcome:
        raise HTTPException(status_code=404, detail="Outcome not found")
    return outcome


@router.get("/signal/{signal_id}", response_model=List[TradeOutcome], tags=["outcome-journal"])
def list_outcomes_for_signal(
    signal_id: str,
):
    """List all outcomes for a given signal ID."""
    return outcome_journal_service.list_outcomes_for_signal(signal_id)


@router.get("/failures/{failure_class}", response_model=List[TradeOutcome], tags=["failure-memory"])
def list_failures_by_classification(
    failure_class: FailureClassification,
):
    """List all failures with the given failure classification."""
    return outcome_journal_service.list_failures_by_class(failure_class)


@router.post("/similar", response_model=List[SimilarCase], tags=["failure-memory"])
def find_similar_cases(
    current_thesis: str,
    min_similarity: float = 0.2,
    limit: int = 10,
    filter_success: Optional[bool] = None,
):
    """Find similar historical cases based on thesis similarity."""
    return failure_memory_service.retrieve_similar_cases(
        current_thesis=current_thesis,
        min_similarity=min_similarity,
        limit=limit,
        filter_success=filter_success,
    )


@router.post("/similar/failures", response_model=List[SimilarCase], tags=["failure-memory"])
def find_similar_failures(
    current_thesis: str,
    failure_class: Optional[FailureClassification] = None,
    min_similarity: float = 0.2,
    limit: int = 10,
):
    """Find similar historical failures, optionally filtered by failure class."""
    return failure_memory_service.retrieve_similar_failures(
        current_thesis=current_thesis,
        failure_class=failure_class,
        min_similarity=min_similarity,
        limit=limit,
    )


@router.post("/similar/successes", response_model=List[SimilarCase], tags=["failure-memory"])
def find_similar_successes(
    current_thesis: str,
    min_similarity: float = 0.2,
    limit: int = 10,
):
    """Find similar historical successes."""
    return failure_memory_service.retrieve_similar_successes(
        current_thesis=current_thesis,
        min_similarity=min_similarity,
        limit=limit,
    )


@router.get("/weekly-review", response_model=WeeklyReviewReport, tags=["outcome-journal"])
def get_weekly_review(
    weeks_ago: int = 0,
):
    """Generate a weekly review report for the specified week (0 = current)."""
    return outcome_journal_service.generate_weekly_review(weeks_ago=weeks_ago)


@router.get("/failure-distribution", response_model=dict[FailureClassification, int], tags=["failure-memory"])
def get_failure_distribution():
    """Get the count of failures by classification."""
    return outcome_journal_service.count_failure_distribution()
