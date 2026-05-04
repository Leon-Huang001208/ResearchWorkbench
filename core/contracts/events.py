from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CanonicalEvent(BaseModel):
    """规范事件 - 从文档中提取的标准化事件"""

    event_id: str
    event_type: str
    summary: str
    event_time: datetime | None = None
    impact_direction: Literal["positive", "negative", "mixed", "unknown"]
    confidence: float
    needs_review: bool = True
    entities: list[dict] = Field(default_factory=list)
    assertions: list[dict] = Field(default_factory=list)
    evidence_spans: list[dict] = Field(default_factory=list)
    source_doc_id: str
