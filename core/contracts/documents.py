"""
Core contracts for document-related data structures.

This module defines Pydantic models that standardize document representations
across the AlphaFoundry system, including envelopes that wrap raw documents
and their metadata.
"""
from datetime import datetime

from pydantic import BaseModel, Field


class DocumentEnvelope(BaseModel):
    """文档信封 - 封装原始文档及其元数据.

    Represents a document envelope that contains the raw document text, canonicalized
    text, and associated metadata (source type, title, publication date, etc.).

    Attributes:
        doc_id: Unique identifier for the document.
        source_type: Type of source (policy, news, report, pdf, ppt, filing, vendor_snapshot, internal_note).
        title: Title of the document.
        published_at: Publication date/time of the document (if available).
        source_name: Name of the source (e.g., "Reuters", "Company X").
        language: Language of the document (default "zh" for Chinese).
        metadata: Additional metadata as a dictionary.
        raw_text: Raw, unprocessed text of the document.
        canonical_text: Canonicalized (cleaned/normalized) text of the document.
    """

    doc_id: str = Field(description="Unique identifier for the document")
    source_type: str = Field(description="Type of source")
    title: str = Field(description="Title of the document")
    published_at: datetime | None = Field(
        default=None, description="Publication date/time of the document (if available)"
    )
    source_name: str = Field(description="Name of the source")
    language: str = Field(default="zh", description="Language of the document")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    raw_text: str = Field(description="Raw, unprocessed text of the document")
    canonical_text: str = Field(
        description="Canonicalized (cleaned/normalized) text of the document"
    )
