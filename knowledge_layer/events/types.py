"""
事件提取 - 类型定义
"""
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """事件类型"""

    EARNINGS = "earnings"  # 财报发布
    MERGER_ACQUISITION = "merger_acquisition"  # 并购
    DIVIDEND = "dividend"  # 分红
    STOCK_SPLIT = "stock_split"  # 拆股
    REGULATION = "regulation"  # 政策变化
    MACRO_DATA = "macro_data"  # 宏观数据发布
    PRODUCT_LAUNCH = "product_launch"  # 产品发布
    MANAGEMENT_CHANGE = "management_change"  # 管理层变动
    LAWSUIT = "lawsuit"  # 诉讼
    DISASTER = "disaster"  # 灾害
    OTHER = "other"  # 其他


class ExtractedEvent(BaseModel):
    """提取的事件（原始）"""

    event_type: EventType
    summary: str
    event_time: Optional[datetime] = None
    impact_direction: str = "unknown"  # positive/negative/mixed/unknown
    confidence: float = Field(ge=0.0, le=1.0)
    entities: List[Dict] = Field(default_factory=list)
    assertions: List[Dict] = Field(default_factory=list)
    evidence_spans: List[Dict] = Field(default_factory=list)
    source_doc_id: str
    metadata: Dict = Field(default_factory=dict)
