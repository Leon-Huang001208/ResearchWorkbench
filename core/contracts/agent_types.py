"""Agent-related shared types.

These types define the structured input/output format for cognitive agents.
Centralized here so both cognitive_agents/ and data_layer/ can depend on them
without creating a data-layer → agent-layer dependency.
"""

from datetime import datetime
from typing import Any, Literal

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
WorkflowStagePolicy = Literal["parallel", "sequential"]

EvidenceKind = Literal[
    "official",
    "research",
    "meeting",
    "media",
    "catalyst",
    "structured",
    "market_reaction",
    "agent_view",
    "memory",
    "other",
]

EvidenceRefType = Literal[
    "source_document",
    "assertion",
    "canonical_event",
    "market_data",
    "agent_view",
    "memory",
    "external",
    "other",
]

_EVIDENCE_KINDS = {
    "official",
    "research",
    "meeting",
    "media",
    "catalyst",
    "structured",
    "market_reaction",
    "agent_view",
    "memory",
    "other",
}

_EVIDENCE_REF_TYPES = {
    "source_document",
    "assertion",
    "canonical_event",
    "market_data",
    "agent_view",
    "memory",
    "external",
    "other",
}


class EvidenceItem(BaseModel):
    """Single evidence item made available to an Agent."""

    evidence_id: str
    ref_id: str
    ref_type: EvidenceRefType = "other"
    evidence_kind: EvidenceKind = "other"
    source_type: str = "unknown"
    source_name: str | None = None
    title: str | None = None
    summary: str = ""
    observed_at: datetime | None = None
    reliability: float = Field(default=0.5, ge=0.0, le=1.0)
    relevance: float = Field(default=0.5, ge=0.0, le=1.0)
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_legacy(cls, index: int, data: dict[str, Any]) -> "EvidenceItem":
        """Build a typed evidence item from the previous loose dict format."""
        evidence_id = str(
            data.get("evidence_id")
            or data.get("id")
            or data.get("assertion_id")
            or data.get("doc_id")
            or data.get("event_id")
            or f"legacy_evidence_{index}"
        )
        ref_id = str(
            data.get("ref_id")
            or data.get("assertion_id")
            or data.get("doc_id")
            or data.get("event_id")
            or evidence_id
        )
        ref_type = str(data.get("ref_type", "other"))
        evidence_kind = str(data.get("evidence_kind", data.get("kind", "other")))
        reliability = _clamp_score(data.get("reliability", data.get("confidence", 0.5)))
        relevance = _clamp_score(data.get("relevance", 0.5))
        return cls(
            evidence_id=evidence_id,
            ref_id=ref_id,
            ref_type=ref_type if ref_type in _EVIDENCE_REF_TYPES else "other",
            evidence_kind=evidence_kind if evidence_kind in _EVIDENCE_KINDS else "other",
            source_type=str(data.get("source_type", "unknown")),
            source_name=data.get("source_name"),
            title=data.get("title"),
            summary=str(data.get("summary") or data.get("text") or data.get("content") or ""),
            observed_at=data.get("observed_at"),
            reliability=reliability,
            relevance=relevance,
            payload=data,
        )


class EvidenceBundle(BaseModel):
    """Evidence package passed into Agents for one target/event analysis."""

    target_id: str
    event_id: str | None = None
    question: str = ""
    as_of: datetime = Field(default_factory=datetime.utcnow)
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    market_snapshot: dict[str, Any] = Field(default_factory=dict)
    prior_view_refs: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_legacy(
        cls,
        target_id: str,
        event_id: str | None,
        question: str,
        evidence: list[dict[str, Any]],
        market_snapshot: dict[str, Any] | None = None,
        prior_view_refs: list[str] | None = None,
    ) -> "EvidenceBundle":
        """Build an evidence bundle from legacy context fields."""
        return cls(
            target_id=target_id,
            event_id=event_id,
            question=question,
            evidence_items=[
                EvidenceItem.from_legacy(index, item) for index, item in enumerate(evidence)
            ],
            market_snapshot=market_snapshot or {},
            prior_view_refs=prior_view_refs or [],
            metadata={"source": "legacy_agent_context"},
        )

    def evidence_ref_ids(self) -> list[str]:
        """Return stable evidence references for AgentView.evidence_refs."""
        return [item.ref_id for item in self.evidence_items]


class AgentSOP(BaseModel):
    """Role-specific analysis discipline for an Agent."""

    agent_role: AgentRole
    objective: str
    focus_areas: list[str] = Field(default_factory=list)
    required_evidence_kinds: list[EvidenceKind] = Field(default_factory=list)
    analysis_steps: list[str] = Field(default_factory=list)
    output_expectations: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class AgentWorkflowStage(BaseModel):
    """One executable stage in a multi-Agent workflow."""

    stage_id: str
    label: str
    agent_roles: list[AgentRole] = Field(default_factory=list)
    policy: WorkflowStagePolicy = "parallel"
    requires_prior_views: bool = True
    synthesis_after_stage: bool = False


class AgentWorkflow(BaseModel):
    """Reusable workflow definition for orchestrating Agent analysis."""

    workflow_id: str
    target_id: str
    question: str
    event_id: str | None = None
    stages: list[AgentWorkflowStage] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def default_research_committee(
        cls,
        target_id: str,
        question: str,
        event_id: str | None = None,
        workflow_id: str = "workflow_research_committee_v1",
    ) -> "AgentWorkflow":
        """Default B-stage workflow: information, research, debate, validation."""
        return cls(
            workflow_id=workflow_id,
            target_id=target_id,
            event_id=event_id,
            question=question,
            stages=[
                AgentWorkflowStage(
                    stage_id="information",
                    label="信息收集",
                    agent_roles=["news", "financial_report", "industry_data"],
                    policy="parallel",
                    requires_prior_views=False,
                ),
                AgentWorkflowStage(
                    stage_id="research",
                    label="多维分析",
                    agent_roles=["macro", "fundamental", "technical", "industry_chain"],
                    policy="parallel",
                ),
                AgentWorkflowStage(
                    stage_id="adversarial_review",
                    label="多空与怀疑审查",
                    agent_roles=["bull", "bear", "skeptic"],
                    policy="parallel",
                ),
                AgentWorkflowStage(
                    stage_id="validation",
                    label="验证与组合约束",
                    agent_roles=["alpha_validation", "regime", "portfolio"],
                    policy="parallel",
                    synthesis_after_stage=True,
                ),
            ],
            metadata={"version": "v1", "layer": "B"},
        )


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
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    recommended_next_checks: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    tool_refs: list[str] = Field(default_factory=list)
    memory_refs: list[str] = Field(default_factory=list)
    workflow_id: str | None = None
    evaluation: dict[str, float] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CommitteeSynthesis(BaseModel):
    """Committee-level synthesis derived from blackboard Agent views."""

    synthesis_id: str
    workflow_id: str | None = None
    target_id: str
    event_id: str | None = None
    final_view: ViewDirection
    confidence: float = Field(ge=0.0, le=1.0)
    thesis: str
    rationale: list[str] = Field(default_factory=list)
    supporting_view_ids: list[str] = Field(default_factory=list)
    dissenting_view_ids: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    recommended_next_checks: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class BlackboardConflict(BaseModel):
    """Multi-perspective conflict detected by the blackboard."""

    conflict_id: str
    target_id: str
    event_id: str | None = None
    view_ids: list[str]
    summary: str
    severity: Literal["low", "medium", "high"]
    confidence: float = Field(ge=0.0, le=1.0)


class AgentWorkflowResult(BaseModel):
    """Result of running an AgentWorkflow."""

    workflow_id: str
    target_id: str
    event_id: str | None = None
    views: list[AgentView] = Field(default_factory=list)
    conflicts: list[BlackboardConflict] = Field(default_factory=list)
    synthesis: CommitteeSynthesis | None = None


def _clamp_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, score))
