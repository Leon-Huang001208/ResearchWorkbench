"""
Core contracts for assertion-related data structures.

This module defines Pydantic models that standardize assertion representations
across the AlphaFoundry system. Assertions are factual statements extracted from
documents, with metadata about their source, validity, and review status.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Assertion(BaseModel):
    """断言 - 从文档中提取的事实陈述.

    Represents a factual statement (assertion) extracted from a source document,
    including subject, predicate, object, validity period, confidence score, source
    information, and review status.

    Attributes:
        assertion_id: Unique identifier for the assertion.
        subject_entity_id: Canonical ID of the subject entity (if applicable).
        predicate: Predicate describing the relationship or property (e.g., "has_revenue", "is_related_to").
        object_entity_id: Canonical ID of the object entity (if applicable).
        object_value: Dictionary representing the object value (if not an entity).
        observed_at: Timestamp when the assertion was observed in the source.
        valid_from: Start of the assertion's validity period (if time-bound).
        valid_to: End of the assertion's validity period (if time-bound).
        confidence: Confidence score (0.0 to 1.0) of the assertion's accuracy.
        source_doc_id: ID of the source document from which the assertion was extracted.
        source_span: Dictionary describing the location in the source document (e.g., page, line numbers).
        extractor_version: Version identifier of the extractor that generated this assertion.
        reviewer_status: Review status (draft, pending, approved, rejected).
        reviewer: Identifier of the user who reviewed the assertion (if applicable).
        reviewed_at: Timestamp when the assertion was reviewed (if applicable).
        trace_ref: Optional reference to a trace for auditing/debugging.
        team_id: Optional team ID for multi-tenant environments.
        project_id: Optional project ID for multi-project environments.
    """

    assertion_id: str = Field(description="Unique identifier for the assertion")
    subject_entity_id: str | None = Field(default=None, description="Canonical ID of the subject entity (if applicable)")
    predicate: str = Field(description="Predicate describing the relationship or property")
    object_entity_id: str | None = Field(default=None, description="Canonical ID of the object entity (if applicable)")
    object_value: dict | None = Field(default=None, description="Object value (if not an entity)")
    observed_at: datetime | None = Field(default=None, description="Timestamp when the assertion was observed in the source")
    valid_from: datetime | None = Field(default=None, description="Start of the assertion's validity period")
    valid_to: datetime | None = Field(default=None, description="End of the assertion's validity period")
    confidence: float = Field(description="Confidence score (0.0 to 1.0) of the assertion's accuracy")
    source_doc_id: str = Field(description="ID of the source document")
    source_span: dict = Field(default_factory=dict, description="Location in the source document (page, line numbers, etc.)")
    extractor_version: str = Field(description="Version of the extractor that generated this assertion")
    reviewer_status: Literal["draft", "pending", "approved", "rejected"] = Field(default="draft", description="Review status")
    reviewer: str | None = Field(default=None, description="Identifier of the reviewer (if applicable)")
    reviewed_at: datetime | None = Field(default=None, description="Timestamp when the assertion was reviewed (if applicable)")
    trace_ref: str | None = Field(default=None, description="Optional trace reference for auditing/debugging")
    team_id: str | None = Field(default=None, description="Optional team ID")
    project_id: str | None = Field(default=None, description="Optional project ID")
