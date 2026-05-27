"""Agent-related shared types.

These types define the structured output format for cognitive agents.
Centralized here so both cognitive_agents/ and data_layer/ can depend on them
without creating a data-layer → agent-layer dependency.
"""
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
    """Structured view written to the blackboard by a single agent."""

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
    """Multi-perspective conflict detected by the blackboard."""

    conflict_id: str
    target_id: str
    event_id: str | None = None
    view_ids: list[str]
    summary: str
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
