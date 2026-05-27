"""Failure memory service for retrieving similar historical cases based on thesis similarity."""
from typing import List, Optional

from core.contracts.outcome_journal import FailureClassification, SimilarCase, TradeOutcome
from core.observability import get_logger
from data_layer.repositories.base import db_session
from data_layer.repositories.models import OutcomeRecordDB
from data_layer.repositories.outcome_journal_repository import OutcomeJournalRepository

logger = get_logger(__name__)


class FailureMemoryService:
    """Service for failure memory and similar case retrieval."""

    def __init__(self):
        pass

    def _calculate_similarity(self, current_thesis: str, historical_thesis: str) -> float:
        """
        Calculate similarity between current thesis and historical thesis.

        Simple Jaccard similarity based on word tokens.
        For production, this would be replaced with embedding-based similarity.
        """
        current_words = set(current_thesis.lower().split())
        historical_words = set(historical_thesis.lower().split())

        intersection = len(current_words.intersection(historical_words))
        union = len(current_words.union(historical_words))

        if union == 0:
            return 0.0

        return intersection / union

    def retrieve_similar_cases(
        self,
        current_thesis: str,
        min_similarity: float = 0.2,
        limit: int = 10,
        filter_success: Optional[bool] = None,
    ) -> List[SimilarCase]:
        """
        Retrieve similar historical cases based on thesis similarity.

        Args:
            current_thesis: The current thesis text
            min_similarity: Minimum similarity threshold (0-1)
            limit: Maximum number of results to return
            filter_success: Filter results to only successful (True) or failed (False) cases. None = all.

        Returns:
            List of similar cases sorted by similarity descending
        """
        with db_session() as db:
            repo = OutcomeJournalRepository(db)

            if filter_success is False:
                all_outcomes = repo.list_all_failures()
            elif filter_success is True:
                # Get only successful outcomes
                results = db.query(OutcomeRecordDB).filter_by(thesis_success=True).all()
                all_outcomes = [repo._to_contract(r) for r in results]
            else:
                # Get all outcomes if filter is not just successes or failures
                # TODO: Optimize this for larger datasets
                # For now just get all outcomes - in production add pagination or embedding search
                results = db.query(OutcomeRecordDB).all()
                all_outcomes = [repo._to_contract(r) for r in results]

        # Calculate similarities
        similar_cases: List[SimilarCase] = []
        for outcome in all_outcomes:
            if filter_success is not None and outcome.thesis_success != filter_success:
                continue

            similarity = self._calculate_similarity(current_thesis, outcome.thesis_text)

            if similarity >= min_similarity:
                similar_cases.append(
                    SimilarCase(
                        outcome_id=outcome.outcome_id,
                        similarity_score=similarity,
                        trade_outcome=outcome,
                        is_success=outcome.thesis_success,
                    )
                )

        # Sort descending by similarity and limit
        similar_cases.sort(key=lambda x: x.similarity_score, reverse=True)
        return similar_cases[:limit]

    def retrieve_similar_failures(
        self,
        current_thesis: str,
        failure_class: Optional[FailureClassification] = None,
        min_similarity: float = 0.2,
        limit: int = 10,
    ) -> List[SimilarCase]:
        """Retrieve similar historical failures, optionally filtered by failure class."""
        similar_cases = self.retrieve_similar_cases(
            current_thesis,
            min_similarity=min_similarity,
            limit=limit,
            filter_success=False,
        )

        if failure_class is not None:
            similar_cases = [
                c for c in similar_cases if c.trade_outcome.failure_classification == failure_class
            ]

        return similar_cases

    def retrieve_similar_successes(
        self,
        current_thesis: str,
        min_similarity: float = 0.2,
        limit: int = 10,
    ) -> List[SimilarCase]:
        """Retrieve similar historical successes."""
        return self.retrieve_similar_cases(
            current_thesis,
            min_similarity=min_similarity,
            limit=limit,
            filter_success=True,
        )

    def get_all_categorized_failures(self) -> List[TradeOutcome]:
        """Get all categorized failures from memory."""
        with db_session() as db:
            repo = OutcomeJournalRepository(db)
            return repo.list_all_failures()
