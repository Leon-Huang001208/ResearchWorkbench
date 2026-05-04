from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class DocumentEnvelope(BaseModel):
    """文档信封 - 封装原始文档及其元数据"""

    doc_id: str
    source_type: Literal[
        "policy", "news", "report", "pdf", "ppt", "filing", "vendor_snapshot", "internal_note"
    ]
    title: str
    published_at: datetime | None = None
    source_name: str
    language: str = "zh"
    metadata: dict = Field(default_factory=dict)
    raw_text: str
    canonical_text: str
