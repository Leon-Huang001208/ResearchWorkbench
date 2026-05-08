"""统一摄取队列契约"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class IngestionQueueItem(BaseModel):
    """统一摄取队列项"""

    item_id: str
    source_type: str  # cls, cnstock, zq, report, manual, future...
    source_id: Optional[str] = None  # 来源 ID（用于去重）
    raw_content: str  # 原始内容
    title: Optional[str] = None
    url: Optional[str] = None
    priority: int = 0  # 0=normal, 1=high, 2=urgent
    status: str = "pending"  # pending, processing, completed, failed
    retry_count: int = 0
    max_retries: int = 3
    failure_reason: Optional[str] = None
    created_at: datetime
    processed_at: Optional[datetime] = None
    dedup_hash: Optional[str] = None  # 用于去重


class IngestionQueueStats(BaseModel):
    """队列统计"""

    depth: int  # 队列深度
    pending: int
    processing: int
    completed: int
    failed: int
    avg_latency_ms: float


class EnqueueRequest(BaseModel):
    """入队请求"""

    source_type: str = Field(..., description="来源类型")
    source_id: Optional[str] = Field(None, description="来源 ID")
    raw_content: str = Field(..., description="原始内容")
    title: Optional[str] = Field(None, description="标题")
    url: Optional[str] = Field(None, description="URL")
    priority: int = Field(0, description="优先级: 0=normal, 1=high, 2=urgent")


class EnqueueResponse(BaseModel):
    """入队响应"""

    item_id: str
    dedup_hash: str
    was_duplicate: bool = False
    message: str = "enqueued"


class ProcessResponse(BaseModel):
    """处理响应"""

    processed_count: int
    results: list[dict] = Field(default_factory=list)


class RetryResponse(BaseModel):
    """重试响应"""

    retried_count: int
    message: str
