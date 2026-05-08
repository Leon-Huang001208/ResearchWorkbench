"""事件信号结果评估协议。

定义什么算成功、失败、衰减、教训，为 Memory & Learning 层提供一致的结果评估标准。
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from memory_learning.contracts import OutcomeHorizon, TimingAction


class SignalOutcome(BaseModel):
    """事件信号结果评估协议。

    每个 SignalOutcome 记录一条信号在给定时间窗口内的实际表现，
    是 MarketEpisode 的结构化评估补充。
    """

    outcome_id: str
    event_id: str
    signal_id: str
    subject_id: str
    event_date: datetime
    timing_action: TimingAction = "wait"
    entry_rule: Optional[str] = None
    horizon: OutcomeHorizon = "20d"
    benchmark: Optional[str] = None
    outcome_return: float = 0.0
    outcome_excess_return: float = 0.0
    max_drawdown: float = 0.0
    decay: float = 0.0
    failure_reason: Optional[str] = None
    lesson: Optional[str] = None
    evaluated_at: Optional[datetime] = None
    metadata: dict[str, str] = Field(default_factory=dict)
