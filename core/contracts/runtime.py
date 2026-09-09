"""Runtime-neutral contracts for AlphaFoundry capability execution.

This module deliberately contains no runtime SDK imports.  Adapters translate
between these models and a concrete runtime such as DSH.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field, model_validator


class CapabilityKind(str, Enum):
    TOOL = "tool"
    SKILL = "skill"
    WORKFLOW = "workflow"
    EVALUATOR = "evaluator"
    RENDERER = "renderer"


class CapabilitySpec(BaseModel):
    """Versioned description of a capability owned by the core domain."""

    capability_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    kind: CapabilityKind
    description: str = Field(min_length=1)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=60, gt=0)
    idempotency_key: str = Field(min_length=1)
    artifact_types: list[str] = Field(default_factory=list)


class ToolSpec(CapabilitySpec):
    kind: Literal[CapabilityKind.TOOL] = CapabilityKind.TOOL


class SkillSpec(CapabilitySpec):
    kind: Literal[CapabilityKind.SKILL] = CapabilityKind.SKILL


class EvaluatorSpec(CapabilitySpec):
    kind: Literal[CapabilityKind.EVALUATOR] = CapabilityKind.EVALUATOR


class TemplateSpec(CapabilitySpec):
    kind: Literal[CapabilityKind.RENDERER] = CapabilityKind.RENDERER


class WorkflowStep(BaseModel):
    step_id: str = Field(min_length=1)
    capability_id: str = Field(min_length=1)
    kind: CapabilityKind
    depends_on: list[str] = Field(default_factory=list)
    input_bindings: dict[str, str] = Field(default_factory=dict)
    output_name: str = Field(min_length=1)
    timeout_seconds: int = Field(default=60, gt=0)
    max_attempts: int = Field(default=1, gt=0)


class WorkflowSpec(BaseModel):
    workflow_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    title: str = Field(min_length=1)
    steps: list[WorkflowStep] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dependencies(self) -> WorkflowSpec:
        ids = {step.step_id for step in self.steps}
        if len(ids) != len(self.steps):
            raise ValueError("workflow step_id values must be unique")
        for step in self.steps:
            unknown = set(step.depends_on) - ids
            if unknown:
                raise ValueError(f"unknown workflow dependencies: {sorted(unknown)}")
            if step.step_id in step.depends_on:
                raise ValueError("workflow step cannot depend on itself")
        return self


class RuntimeCapabilities(BaseModel):
    tool_calling: bool = False
    skills: bool = False
    workflow: bool = False
    streaming: bool = False
    cancellation: bool = False
    resume: bool = False

    def supports(self, kind: CapabilityKind) -> bool:
        return {
            CapabilityKind.TOOL: self.tool_calling,
            CapabilityKind.SKILL: self.skills,
            CapabilityKind.WORKFLOW: self.workflow,
        }.get(kind, True)


class RuntimeDescriptor(BaseModel):
    runtime_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    protocol_version: str = Field(min_length=1)
    capabilities: RuntimeCapabilities


class ExecutionHandle(BaseModel):
    run_id: str = Field(min_length=1)
    runtime_id: str = Field(min_length=1)
    execution_id: str = Field(min_length=1)
    resumable: bool = False


class AlphaEvent(BaseModel):
    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    sequence: int = Field(ge=0)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceRecord(BaseModel):
    evidence_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_name: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    observed_at: datetime | None = None
    conflict: bool = False


class QualityGate(BaseModel):
    gate_key: str = Field(min_length=1)
    passed: bool
    message: str = Field(min_length=1)
    details: dict[str, Any] = Field(default_factory=dict)


class ReportSection(BaseModel):
    heading: str = Field(min_length=1)
    content: str = Field(min_length=1)


class ReportChart(BaseModel):
    """Renderer-neutral chart payload owned by AlphaFoundry."""

    chart_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    chart_type: Literal["bar", "line"]
    data: list[dict[str, Any]] = Field(default_factory=list)


class ReportDocument(BaseModel):
    title: str = Field(min_length=1)
    as_of: datetime
    sections: list[ReportSection] = Field(min_length=1)
    evidence_refs: list[str] = Field(default_factory=list)
    charts: list[ReportChart] = Field(default_factory=list)


class WorkflowRunResult(BaseModel):
    run_id: str
    status: Literal["completed", "blocked", "failed", "cancelled"]
    workflow: WorkflowSpec
    report_document: ReportDocument | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    gates: list[QualityGate] = Field(default_factory=list)
    events: list[AlphaEvent] = Field(default_factory=list)
    error_message: str | None = None


class RuntimeUnavailableError(RuntimeError):
    """Raised when a requested capability is not advertised by a runtime."""


class RuntimeInterface(Protocol):
    """The only port through which the core may invoke a runtime."""

    descriptor: RuntimeDescriptor

    def create_session(self, *, run_id: str) -> ExecutionHandle: ...
    def run_task(self, *, handle: ExecutionHandle, task: dict[str, Any]) -> dict[str, Any]: ...
    def register_tools(self, tools: list[ToolSpec]) -> None: ...
    def register_skills(self, skills: list[SkillSpec]) -> None: ...
    def run_workflow(
        self, *, handle: ExecutionHandle, workflow: WorkflowSpec
    ) -> dict[str, Any]: ...
    def stream_events(self, *, run_id: str, after_sequence: int = 0) -> list[AlphaEvent]: ...
    def cancel(self, *, handle: ExecutionHandle) -> None: ...
    def resume(self, *, run_id: str) -> ExecutionHandle: ...
    def health(self) -> dict[str, Any]: ...
    def dispose(self) -> None: ...
