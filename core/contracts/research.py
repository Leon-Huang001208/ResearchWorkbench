"""Contracts for resumable, evidence-first research runs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ResearchRunStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    COLLECTING = "collecting"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    PUBLISHING = "publishing"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ResearchSourceTier = Literal["licensed", "official", "public", "user"]
ResearchSubjectType = Literal["security", "etf", "index", "commodity", "macro", "industry"]


class ResearchSubject(BaseModel):
    """One normalized research subject shared by every Research Template."""

    subject_type: ResearchSubjectType
    subject_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    market: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ResearchTemplateDefinition(BaseModel):
    """Public, framework-free metadata for one registered research template."""

    template_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    supported_subject_types: list[ResearchSubjectType]
    available: bool
    status: Literal["available", "planned"]
    input_requirements: dict[str, Any] = Field(default_factory=dict)
    evidence_kinds: list[str] = Field(default_factory=list)
    quality_gate_keys: list[str] = Field(default_factory=list)


class ResearchEvidenceInput(BaseModel):
    """A normalized, source-addressable input supplied to one research run."""

    evidence_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    evidence_kind: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    claim_text: str = Field(min_length=1)
    source_tier: ResearchSourceTier = "public"
    observed_at: datetime | None = None
    numeric_value: float | None = None
    numeric_unit: str | None = None
    numeric_period: str | None = None
    calculation: str | None = None
    conflict: bool = False

    @model_validator(mode="after")
    def validate_numeric_context(self) -> "ResearchEvidenceInput":
        numeric_fields = (self.numeric_value, self.numeric_unit, self.numeric_period)
        if any(value is not None for value in numeric_fields) and not all(
            value is not None and value != "" for value in numeric_fields
        ):
            raise ValueError("numeric evidence requires value, unit, and period")
        return self


class ResearchRunCreateRequest(BaseModel):
    template_key: str = Field(min_length=1)
    subject: ResearchSubject | None = None
    target_id: str | None = Field(default=None, min_length=1)
    as_of: datetime
    question: str = Field(min_length=1)
    attachment_refs: list[str] = Field(default_factory=list)
    evidence_inputs: list[ResearchEvidenceInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_legacy_target(self) -> "ResearchRunCreateRequest":
        if self.subject is None and self.target_id is None:
            raise ValueError("subject or legacy target_id is required")
        if self.subject is None and self.target_id is not None:
            self.subject = ResearchSubject(
                subject_type="security",
                subject_id=self.target_id,
                display_name=self.target_id,
            )
        if self.subject is not None and self.target_id is None:
            self.target_id = self.subject.subject_id
        if self.subject is not None and self.target_id != self.subject.subject_id:
            raise ValueError("target_id must match subject.subject_id")
        return self


class ResearchTask(BaseModel):
    task_id: str
    run_id: str
    task_key: str
    status: ResearchRunStatus
    attempt: int = 0
    resume_from: str | None = None
    state_snapshot: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class ResearchArtifact(BaseModel):
    artifact_id: str
    run_id: str
    artifact_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ResearchClaim(BaseModel):
    claim_id: str
    run_id: str
    category: str = Field(min_length=1)
    text: str
    evidence_refs: list[str] = Field(default_factory=list)
    numeric_context: dict[str, Any] = Field(default_factory=dict)
    conflict_status: Literal["clear", "unresolved"] = "clear"
    created_at: datetime


class QualityGateResult(BaseModel):
    gate_id: str
    run_id: str
    gate_key: str
    passed: bool
    severity: Literal["error", "warning", "info"] = "error"
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    checked_at: datetime


class ResearchDecisionCard(BaseModel):
    run_id: str
    target_id: str
    subject: ResearchSubject | None = None
    as_of: datetime
    conclusion: str
    confidence: float = Field(ge=0.0, le=1.0)
    core_drivers: list[str] = Field(default_factory=list)
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    invalidation_triggers: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    data_coverage: dict[str, bool] = Field(default_factory=dict)


class ResearchRun(BaseModel):
    run_id: str
    template_key: str
    target_id: str
    subject: ResearchSubject
    as_of: datetime
    question: str
    attachment_refs: list[str] = Field(default_factory=list)
    source_plan: dict[str, Any] = Field(default_factory=dict)
    status: ResearchRunStatus
    retry_count: int = 0
    resume_from: str | None = None
    blocked_reasons: list[str] = Field(default_factory=list)
    quality_gates: list[QualityGateResult] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ResearchRunOutputs(BaseModel):
    run_id: str
    status: ResearchRunStatus
    decision_card: ResearchDecisionCard | None = None
    research_notes: list[dict[str, Any]] = Field(default_factory=list)
    claims: list[ResearchClaim] = Field(default_factory=list)
    quality_gates: list[QualityGateResult] = Field(default_factory=list)
    artifacts: list[ResearchArtifact] = Field(default_factory=list)
    report_markdown: str | None = None
