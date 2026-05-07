"""认知 Agent 层契约。"""
from typing import Literal

from pydantic import BaseModel, Field


AgentRole = Literal[
    "news",
    "social_media",
    "financial_report",
    "industry_data",
    "fundamental",
    "technical",
    "macro",
    "industry_chain",
    "policy",
    "sentiment",
    "bull",
    "bear",
    "skeptic",
    "alpha_validation",
    "regime",
    "portfolio",
    "execution",
]

ViewDirection = Literal["bullish", "bearish", "neutral", "mixed", "unknown"]


class AgentView(BaseModel):
    """单个 Agent 写入黑板的结构化观点。"""

    view_id: str
    agent_name: str
    agent_role: AgentRole
    target_id: str
    view: ViewDirection
    thesis: str
    confidence: float = Field(ge=0.0, le=1.0)
    event_id: str | None = None
    reasoning: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    evaluation: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, str] = Field(default_factory=dict)


class BlackboardConflict(BaseModel):
    """黑板检测出的多视角冲突。"""

    conflict_id: str
    target_id: str
    event_id: str | None = None
    view_ids: list[str]
    summary: str
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
