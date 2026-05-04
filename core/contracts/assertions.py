from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Assertion(BaseModel):
    """断言 - 从文档中提取的事实陈述"""

    assertion_id: str
    subject_entity_id: str | None = None
    predicate: str
    object_entity_id: str | None = None
    object_value: dict | None = None
    observed_at: datetime | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    confidence: float
    source_doc_id: str
    source_span: dict = Field(default_factory=dict)
    extractor_version: str
    reviewer_status: Literal["draft", "pending", "approved", "rejected"] = "draft"
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    trace_ref: str | None = None
    team_id: str | None = None
    project_id: str | None = None
