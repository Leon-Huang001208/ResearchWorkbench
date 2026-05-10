"""
实体解析 - 类型定义
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """实体类型"""

    COMPANY = "company"  # 公司
    PERSON = "person"  # 人物
    CONCEPT = "concept"  # 概念
    INDEX = "index"  # 指数
    COMMODITY = "commodity"  # 商品
    CURRENCY = "currency"  # 货币
    GOVERNMENT = "government"  # 政府机构
    ORGANIZATION = "organization"  # 其他组织


class EntityCandidate(BaseModel):
    """实体候选"""

    text: str  # 原始文本
    entity_type: EntityType
    confidence: float = Field(ge=0.0, le=1.0)
    start_pos: int | None = None
    end_pos: int | None = None
    metadata: dict = Field(default_factory=dict)


class ResolvedEntity(BaseModel):
    """已解析实体"""

    canonical_id: str
    entity_type: EntityType
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    matched_text: str
    vendor_ids: dict[str, str] = Field(default_factory=dict)
    properties: dict = Field(default_factory=dict)
    resolved_at: datetime = Field(default_factory=datetime.utcnow)
