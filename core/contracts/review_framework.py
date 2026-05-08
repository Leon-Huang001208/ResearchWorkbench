from enum import Enum
from typing import Optional, List, Dict
from pydantic import BaseModel, Field


class ReviewPosition(str, Enum):
    """Review position enum: Bull/Bear/Skeptic"""
    BULL = "bull"
    BEAR = "bear"
    SKEPTIC = "skeptic"


class EvidenceReference(BaseModel):
    """Evidence reference linking to stored evidence documents/events"""
    evidence_id: str
    evidence_type: str  # "event", "document", "signal", "data_point"
    url: Optional[str] = None  # Clickable/traceable link
    description: str
    confidence_in_evidence: float  # 0.0 to 1.0


class ReviewCard(BaseModel):
    """Structured review for a thesis in one position (Bull/Bear/Skeptic)"""
    review_id: str
    thesis_id: str
    position: ReviewPosition
    summary: str
    evidence_refs: List[EvidenceReference] = Field(default_factory=list)
    confidence_score: float  # 0.0 to 1.0 - confidence in this review's conclusion
    reasoning_chain: List[str] = Field(default_factory=list)  # Step-by-step reasoning
    invalidation_triggers: List[str] = Field(default_factory=list)  # What would invalidate this view
    created_at: str


class CognitiveBlackboard(BaseModel):
    """Evidence-linked cognitive blackboard for the review process"""
    blackboard_id: str
    thesis_id: str
    bull_review: Optional[ReviewCard] = None
    bear_review: Optional[ReviewCard] = None
    skeptic_review: Optional[ReviewCard] = None
    aggregated_evidence: List[EvidenceReference] = Field(default_factory=list)
    conflicting_evidence_count: int = 0
    missing_evidence_count: int = 0
    metadata: Dict = Field(default_factory=dict)


class ConflictDetectionSummary(BaseModel):
    """Summary of detected conflicts between reviews"""
    conflict_id: str
    thesis_id: str
    total_conflicts: int
    conflicting_claims: List[Dict[str, str]] = Field(default_factory=list)  # Each item has bull_claim, bear_claim, evidence_point
    unresolved_conflicts: int
    has_sufficient_opposing_view: bool
    can_promote_to_candidate: bool  # Follows hard rules: has evidence + bear/skeptic review
    reasoning: str
