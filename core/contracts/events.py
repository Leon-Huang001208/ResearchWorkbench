from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CanonicalEvent(BaseModel):
    """规范事件 - 从文档中提取的标准化Alpha事件"""

    # Required core fields
    event_id: str
    event_type: str
    event_time: datetime | None = None
    
    # Source metadata
    source_type: str
    source_name: str
    title: str
    raw_text: Optional[str] = None
    
    # Extracted content
    extracted_assertions: list[dict] = Field(default_factory=list)
    
    # Impact targeting
    impacted_industries: list[str] = Field(default_factory=list)
    impacted_symbols: list[str] = Field(default_factory=list)
    
    # Scoring
    confidence: float
    novelty_score: float = 0.0
    
    # Legacy fields for backward compatibility
    summary: Optional[str] = None
    impact_direction: Literal["positive", "negative", "mixed", "unknown"] = "unknown"
    needs_review: bool = True
    entities: list[dict] = Field(default_factory=list)
    assertions: list[dict] = Field(default_factory=list)
    evidence_spans: list[dict] = Field(default_factory=list)
    source_doc_id: str = ""
    reviewer_status: Literal["draft", "pending", "approved", "rejected"] = "draft"
    reviewer: str | None = None
    reviewed_at: datetime | None = None
