"""
Core contracts for the review framework (cognitive blackboard, review cards, conflict detection).

This module defines Pydantic models for the review framework, including review positions,
evidence references, review cards, cognitive blackboard, and conflict detection summaries in Research Workbench.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class ReviewPosition(str, Enum):
    """Review position enum: Bull/Bear/Skeptic.

    Enumeration of possible review positions for a thesis.
    """

    BULL = "bull"
    BEAR = "bear"
    SKEPTIC = "skeptic"


class EvidenceReference(BaseModel):
    """Evidence reference linking to stored evidence documents/events.

    Represents a reference to evidence, including evidence ID, type, URL, description,
    and confidence in the evidence.

    Attributes:
        evidence_id: Unique identifier for the evidence.
        evidence_type: Type of evidence ("event", "document", "signal", "data_point").
        url: Optional clickable/traceable link to the evidence (if available).
        description: Description of the evidence.
        confidence_in_evidence: Confidence in the evidence (0.0 to 1.0).
    """

    evidence_id: str = Field(description="Unique identifier for the evidence")
    evidence_type: str = Field(description="Type of evidence (event, document, signal, data_point)")
    url: Optional[str] = Field(
        default=None, description="Optional clickable/traceable link to the evidence (if available)"
    )
    description: str = Field(description="Description of the evidence")
    confidence_in_evidence: float = Field(description="Confidence in the evidence (0.0 to 1.0)")


class ReviewCard(BaseModel):
    """Structured review for a thesis in one position (Bull/Bear/Skeptic).

    Represents a structured review for a thesis in a specific position, including
    review ID, thesis ID, position, summary, evidence references, confidence score,
    reasoning chain, invalidation triggers, and creation time.

    Attributes:
        review_id: Unique identifier for the review.
        thesis_id: Unique identifier for the thesis.
        position: Review position (Bull/Bear/Skeptic).
        summary: Summary of the review.
        evidence_refs: List of evidence references supporting the review.
        confidence_score: Confidence in the review's conclusion (0.0 to 1.0).
        reasoning_chain: Step-by-step reasoning for the review.
        invalidation_triggers: List of triggers that would invalidate this view.
        created_at: Timestamp when the review was created (as a string).
    """

    review_id: str = Field(description="Unique identifier for the review")
    thesis_id: str = Field(description="Unique identifier for the thesis")
    position: ReviewPosition = Field(description="Review position (Bull/Bear/Skeptic)")
    summary: str = Field(description="Summary of the review")
    evidence_refs: List[EvidenceReference] = Field(
        default_factory=list, description="List of evidence references supporting the review"
    )
    confidence_score: float = Field(
        description="Confidence in the review's conclusion (0.0 to 1.0)"
    )
    reasoning_chain: List[str] = Field(
        default_factory=list, description="Step-by-step reasoning for the review"
    )
    invalidation_triggers: List[str] = Field(
        default_factory=list, description="List of triggers that would invalidate this view"
    )
    created_at: str = Field(description="Timestamp when the review was created (as a string)")


class CognitiveBlackboard(BaseModel):
    """Evidence-linked cognitive blackboard for the review process.

    Represents the cognitive blackboard for a thesis, including blackboard ID,
    thesis ID, reviews (bull/bear/skeptic), aggregated evidence, conflicting/missing
    evidence counts, and metadata.

    Attributes:
        blackboard_id: Unique identifier for the blackboard.
        thesis_id: Unique identifier for the thesis.
        bull_review: Optional bull review card (if available).
        bear_review: Optional bear review card (if available).
        skeptic_review: Optional skeptic review card (if available).
        aggregated_evidence: List of all evidence references aggregated.
        conflicting_evidence_count: Number of conflicting evidence items (default 0).
        missing_evidence_count: Number of missing evidence items (default 0).
        metadata: Additional metadata as a dictionary.
    """

    blackboard_id: str = Field(description="Unique identifier for the blackboard")
    thesis_id: str = Field(description="Unique identifier for the thesis")
    bull_review: Optional[ReviewCard] = Field(
        default=None, description="Optional bull review card (if available)"
    )
    bear_review: Optional[ReviewCard] = Field(
        default=None, description="Optional bear review card (if available)"
    )
    skeptic_review: Optional[ReviewCard] = Field(
        default=None, description="Optional skeptic review card (if available)"
    )
    aggregated_evidence: List[EvidenceReference] = Field(
        default_factory=list, description="List of all evidence references aggregated"
    )
    conflicting_evidence_count: int = Field(
        default=0, description="Number of conflicting evidence items"
    )
    missing_evidence_count: int = Field(default=0, description="Number of missing evidence items")
    metadata: Dict = Field(default_factory=dict, description="Additional metadata as a dictionary")


class ConflictDetectionSummary(BaseModel):
    """Summary of detected conflicts between reviews.

    Represents a summary of detected conflicts between reviews, including conflict ID,
    thesis ID, total conflicts, conflicting claims, unresolved conflicts, whether there's
    a sufficient opposing view, whether the thesis can be promoted to candidate,
    and reasoning.

    Attributes:
        conflict_id: Unique identifier for the conflict summary.
        thesis_id: Unique identifier for the thesis.
        total_conflicts: Total number of detected conflicts.
        conflicting_claims: List of conflicting claims (each with bull_claim, bear_claim, evidence_point).
        unresolved_conflicts: Number of unresolved conflicts.
        has_sufficient_opposing_view: Whether there is a sufficient opposing view (bear/skeptic review).
        can_promote_to_candidate: Whether the thesis can be promoted to candidate (follows hard rules: has evidence + bear/skeptic review).
        reasoning: Reasoning for the conclusions.
    """

    conflict_id: str = Field(description="Unique identifier for the conflict summary")
    thesis_id: str = Field(description="Unique identifier for the thesis")
    total_conflicts: int = Field(description="Total number of detected conflicts")
    conflicting_claims: List[Dict[str, str]] = Field(
        default_factory=list,
        description="List of conflicting claims (each with bull_claim, bear_claim, evidence_point)",
    )
    unresolved_conflicts: int = Field(description="Number of unresolved conflicts")
    has_sufficient_opposing_view: bool = Field(
        description="Whether there is a sufficient opposing view (bear/skeptic review)"
    )
    can_promote_to_candidate: bool = Field(
        description="Whether the thesis can be promoted to candidate (follows hard rules: has evidence + bear/skeptic review)"
    )
    reasoning: str = Field(description="Reasoning for the conclusions")
