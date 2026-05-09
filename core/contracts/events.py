"""
Core contracts for event-related data structures.

This module defines Pydantic models that standardize event representations
across the AlphaFoundry system, including canonical events extracted from
documents with metadata, impact targeting, and scoring.
"""
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CanonicalEvent(BaseModel):
    """规范事件 - 从文档中提取的标准化Alpha事件.

    Represents a standardized alpha event extracted from a source document,
    including core fields, source metadata, extracted content, impact targeting,
    scoring, and legacy fields for backward compatibility.

    Attributes:
        event_id: Unique identifier for the event.
        event_type: Type of event (e.g., "earnings", "news", "regulatory").
        event_time: Timestamp of the event (if available).
        source_type: Type of source (e.g., "news", "report", "filing").
        source_name: Name of the source (e.g., "Reuters", "Company X").
        title: Title of the event or source document.
        raw_text: Raw text of the event/source (if available).
        extracted_assertions: List of assertions extracted from the event.
        impacted_industries: List of industries impacted by this event.
        impacted_symbols: List of ticker symbols impacted by this event.
        confidence: Confidence score (0.0 to 1.0) of the event's accuracy/impact.
        novelty_score: Novelty score (0.0 to 1.0) indicating how new/unusual the event is.
        summary: Legacy field: summary of the event (optional).
        impact_direction: Legacy field: direction of impact (positive, negative, mixed, unknown).
        needs_review: Legacy field: whether the event needs review (default True).
        entities: Legacy field: list of entities extracted from the event.
        assertions: Legacy field: list of assertions extracted from the event.
        evidence_spans: Legacy field: list of evidence spans in the source document.
        source_doc_id: Legacy field: ID of the source document.
        reviewer_status: Legacy field: review status (draft, pending, approved, rejected).
        reviewer: Legacy field: identifier of the reviewer (if applicable).
        reviewed_at: Legacy field: timestamp when the event was reviewed (if applicable).
    """

    # Required core fields
    event_id: str = Field(description="Unique identifier for the event")
    event_type: str = Field(description="Type of event (earnings, news, regulatory, etc.)")
    event_time: datetime | None = Field(default=None, description="Timestamp of the event (if available)")
    
    # Source metadata
    source_type: str = Field(description="Type of source (news, report, filing, etc.)")
    source_name: str = Field(description="Name of the source")
    title: str = Field(description="Title of the event or source document")
    raw_text: Optional[str] = Field(default=None, description="Raw text of the event/source (if available)")
    
    # Extracted content
    extracted_assertions: list[dict] = Field(default_factory=list, description="List of assertions extracted from the event")
    
    # Impact targeting
    impacted_industries: list[str] = Field(default_factory=list, description="List of industries impacted by this event")
    impacted_symbols: list[str] = Field(default_factory=list, description="List of ticker symbols impacted by this event")
    
    # Scoring
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")
    novelty_score: float = Field(default=0.0, description="Novelty score (0.0 to 1.0)")
    
    # Legacy fields for backward compatibility
    summary: Optional[str] = Field(default=None, description="Legacy field: summary of the event")
    impact_direction: Literal["positive", "negative", "mixed", "unknown"] = Field(
        default="unknown", description="Legacy field: direction of impact"
    )
    needs_review: bool = Field(default=True, description="Legacy field: whether the event needs review")
    entities: list[dict] = Field(default_factory=list, description="Legacy field: list of entities")
    assertions: list[dict] = Field(default_factory=list, description="Legacy field: list of assertions")
    evidence_spans: list[dict] = Field(default_factory=list, description="Legacy field: list of evidence spans")
    source_doc_id: str = Field(default="", description="Legacy field: ID of the source document")
    reviewer_status: Literal["draft", "pending", "approved", "rejected"] = Field(
        default="draft", description="Legacy field: review status"
    )
    reviewer: str | None = Field(default=None, description="Legacy field: identifier of the reviewer (if applicable)")
    reviewed_at: datetime | None = Field(default=None, description="Legacy field: timestamp when the event was reviewed (if applicable)")
