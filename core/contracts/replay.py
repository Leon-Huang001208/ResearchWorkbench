"""回放任务与结果契约 — 历史事件批量回放 & 信号校准。"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ReplayJob(BaseModel):
    """回放任务"""

    job_id: str
    name: str
    description: Optional[str] = None
    event_filter: Optional[dict] = None  # 过滤条件：event_type, source_type, date_range
    max_events: int = 100
    status: str = "pending"  # pending, running, completed, failed
    created_at: datetime
    completed_at: Optional[datetime] = None


class ReplayResult(BaseModel):
    """单事件回放结果"""

    job_id: str
    event_id: str
    signal_id: Optional[str] = None
    outcome_id: Optional[str] = None
    event_type: str
    source_type: str
    signal_score: Optional[float] = None
    signal_confidence: Optional[float] = None
    timing_action: Optional[str] = None
    outcome_return: Optional[float] = None
    outcome_excess_return: Optional[float] = None
    max_drawdown: Optional[float] = None
    decay: Optional[float] = None
    error: Optional[str] = None


class ReplayAggregate(BaseModel):
    """回放聚合结果"""

    job_id: str
    total_events: int
    successful: int
    failed: int
    hit_rate: float  # 正收益比例
    avg_excess_return: float
    avg_max_drawdown: float
    avg_decay: float
    by_event_type: dict[str, dict] = Field(default_factory=dict)
    by_source_type: dict[str, dict] = Field(default_factory=dict)
    by_timing_action: dict[str, dict] = Field(default_factory=dict)
    calibration: dict = Field(default_factory=dict)


class ReplayJobCreateRequest(BaseModel):
    """创建回放任务请求"""

    name: str = "Default Replay"
    description: Optional[str] = None
    event_filter: Optional[dict] = None
    max_events: int = 100
