"""Memory & Learning 契约。"""
from pydantic import BaseModel, Field

from core.contracts.timing_types import FailureType, OutcomeHorizon, TimingAction


class MarketEpisode(BaseModel):
    """事件记忆：记录发生了什么、市场如何反应、最终结果如何。"""

    episode_id: str
    event_id: str
    event_type: str
    market_regime: str
    initial_reaction: str
    outcome_horizon: OutcomeHorizon
    outcome_return: float
    outcome_excess_return: float
    timing_action: TimingAction | None = None
    signal_id: str | None = None
    timing_decision_id: str | None = None
    failed_reason: str | None = None
    lesson: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class StrategyMemory(BaseModel):
    """策略记忆：记录某类策略在某种 regime 下是否有效。"""

    strategy_id: str
    signal_family: str
    market_regime: str
    sample_size: int = Field(ge=0)
    win_rate: float = Field(ge=0.0, le=1.0)
    average_excess_return: float
    sharpe_ratio: float
    notes: list[str] = Field(default_factory=list)


class AgentMemory(BaseModel):
    """Agent 记忆：记录 Agent 长期观点和表现。"""

    memory_id: str
    agent_name: str
    agent_role: str
    belief: str
    confidence: float = Field(ge=0.0, le=1.0)
    support_count: int = Field(default=0, ge=0)
    contradiction_count: int = Field(default=0, ge=0)
    last_updated_reason: str | None = None


class FailureMemory(BaseModel):
    """失败记忆：记录为什么错，以及应该怎样修正。"""

    failure_id: str
    source_id: str
    failure_type: FailureType
    root_cause: str
    corrective_action: str
    evidence_refs: list[str] = Field(default_factory=list)
