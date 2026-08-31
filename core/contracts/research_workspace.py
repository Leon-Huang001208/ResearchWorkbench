"""Workspace, runtime, Skill, Agent Team, and schedule contracts."""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class WorkspaceStatus(str, Enum):
    """Lifecycle state of a local research workspace."""

    ACTIVE = "active"
    ARCHIVED = "archived"


class ResearchWorkspace(BaseModel):
    """Project-isolated container for sessions, runs, and notes."""

    workspace_id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    status: WorkspaceStatus = WorkspaceStatus.ACTIVE
    created_at: datetime
    updated_at: datetime
    archived_at: datetime | None = None


class SessionMode(str, Enum):
    """Whether a session is ephemeral or bound to a workspace."""

    TEMPORARY = "temporary"
    WORKSPACE = "workspace"


class SessionStatus(str, Enum):
    """Lifecycle of a research conversation."""

    ACTIVE = "active"
    PROMOTED = "promoted"
    ARCHIVED = "archived"


class ResearchSession(BaseModel):
    """Temporary or workspace-scoped research conversation."""

    session_id: str = Field(min_length=1)
    mode: SessionMode
    status: SessionStatus = SessionStatus.ACTIVE
    workspace_id: str | None = None
    run_id: str | None = None
    created_at: datetime
    updated_at: datetime

    @model_validator(mode="after")
    def validate_scope(self) -> ResearchSession:
        """Require workspace sessions to carry their isolation scope."""

        if self.mode is SessionMode.WORKSPACE and not self.workspace_id:
            raise ValueError("workspace_id is required for workspace session")
        if self.mode is SessionMode.TEMPORARY and self.workspace_id:
            raise ValueError("temporary session cannot have workspace_id before promotion")
        return self


class ResearchMessage(BaseModel):
    """Persisted message with content stored directly or by safe reference."""

    message_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    workspace_id: str | None = None
    role: Literal["user", "assistant", "system", "tool"]
    content: str | None = None
    content_ref: str | None = None
    idempotency_key: str = Field(min_length=1)
    created_at: datetime

    @model_validator(mode="after")
    def validate_content(self) -> ResearchMessage:
        """Require exactly one message content representation."""

        if bool(self.content) == bool(self.content_ref):
            raise ValueError("exactly one of content or content_ref is required")
        return self


class RuntimeProviderStatus(str, Enum):
    """Health state advertised by a research runtime provider."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class RuntimeProvider(BaseModel):
    """Capability declaration for LangGraph or the optional DSH sidecar."""

    provider_id: str = Field(min_length=1)
    provider_type: Literal["langgraph", "dsh"]
    name: str = Field(min_length=1)
    capabilities: set[Literal["single_agent", "agent_team", "sse", "resume"]]
    status: RuntimeProviderStatus
    config_ref: str | None = None
    checked_at: datetime


class SkillManifest(BaseModel):
    """Declarative research Skill with a closed tool permission surface."""

    skill_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    prompt_template: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    allowed_tools: list[str] = Field(default_factory=list)
    registered_mcp_tools: list[str] = Field(default_factory=list)
    attachment_refs: list[str] = Field(default_factory=list)
    status: Literal["draft", "validated", "enabled", "disabled"] = "draft"

    @model_validator(mode="after")
    def validate_allowed_tools(self) -> SkillManifest:
        """Reject code, Shell, filesystem, arbitrary URL, and unknown MCP access."""

        registered = set(self.registered_mcp_tools)
        forbidden_internal_terms = {
            "browser",
            "code",
            "exec",
            "filesystem",
            "shell",
            "subprocess",
            "terminal",
        }
        for tool in self.allowed_tools:
            internal_name = tool.removeprefix("internal:")
            internal_terms = set(re.split(r"[._-]", internal_name))
            safe_internal = bool(re.fullmatch(r"internal:[a-z][a-z0-9_.-]*", tool)) and not (
                forbidden_internal_terms & internal_terms
            )
            permitted = (
                safe_internal
                or tool == "attachment:read"
                or tool == "web:controlled"
                or (tool.startswith("mcp:") and tool in registered)
            )
            if not permitted:
                raise ValueError(f"allowed_tools contains forbidden tool: {tool}")
        return self


class AgentBudget(BaseModel):
    """Hard execution bounds checked before every Agent step."""

    max_steps: int = Field(ge=1, le=100)
    max_concurrency: int = Field(ge=1, le=16)
    max_tokens: int = Field(ge=1, le=1_000_000)
    max_cost: float = Field(ge=0, le=10_000)
    deadline_seconds: int = Field(ge=1, le=86_400)


class AgentTeamDefinition(BaseModel):
    """Supervisor-led team whose workers communicate through a blackboard."""

    team_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    supervisor_role: str = Field(min_length=1)
    roles: list[str] = Field(min_length=1)
    budget: AgentBudget
    skill_keys: list[str] = Field(default_factory=list)
    status: Literal["draft", "active", "paused", "retired"] = "draft"

    @model_validator(mode="after")
    def validate_supervisor(self) -> AgentTeamDefinition:
        """Require the declared supervisor to be a member of the team."""

        if self.supervisor_role not in self.roles:
            raise ValueError("supervisor_role must be included in roles")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError("roles must be unique")
        return self


class AgentSchedule(BaseModel):
    """No-reentry schedule that coalesces missed executions to the latest."""

    schedule_id: str = Field(min_length=1)
    team_id: str = Field(min_length=1)
    cron_expression: str = Field(min_length=1)
    status: Literal["active", "paused", "retired"]
    allow_concurrent: bool = False
    coalesce_policy: str = "latest"
    scheduled_job_id: str | None = None
    last_run_at: datetime | None = None
    next_run_at: datetime | None = None

    @model_validator(mode="after")
    def validate_execution_policy(self) -> AgentSchedule:
        """Enforce the platform-wide single-flight/latest-only policy."""

        if self.allow_concurrent:
            raise ValueError("concurrent schedule reentry is forbidden")
        if self.coalesce_policy != "latest":
            raise ValueError("coalesce policy must be latest")
        return self


class ResearchNote(BaseModel):
    """Versioned user-selected Claim or paragraph reference."""

    note_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    source_kind: Literal["claim", "paragraph"]
    run_id: str = Field(min_length=1)
    claim_id: str | None = None
    paragraph_ref: str | None = None
    summary: str = Field(min_length=1)
    pinned: bool = True
    created_at: datetime

    @model_validator(mode="after")
    def validate_source_reference(self) -> ResearchNote:
        """Require the reference that matches the selected source kind."""

        if self.source_kind == "claim" and not self.claim_id:
            raise ValueError("claim_id is required for claim note")
        if self.source_kind == "paragraph" and not self.paragraph_ref:
            raise ValueError("paragraph_ref is required for paragraph note")
        return self
