"""Workspace, runtime, Skill, Agent Team, and schedule contracts."""

from __future__ import annotations

import re
from collections.abc import Collection
from enum import Enum
from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

# Closed platform-owned capability set; additions require contract and security review.
SAFE_INTERNAL_TOOL_IDS: frozenset[str] = frozenset({"internal:asset_snapshot"})


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
    created_at: AwareDatetime
    updated_at: AwareDatetime
    archived_at: AwareDatetime | None = None


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
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @model_validator(mode="after")
    def validate_scope(self) -> ResearchSession:
        """Require workspace sessions to carry their isolation scope."""

        if self.mode is SessionMode.WORKSPACE and (
            self.workspace_id is None or not self.workspace_id.strip()
        ):
            raise ValueError("workspace_id is required for workspace session")
        if self.mode is SessionMode.TEMPORARY and self.workspace_id is not None:
            raise ValueError("temporary session cannot have workspace_id before promotion")
        return self


class ResearchMessage(BaseModel):
    """Persisted message whose workspace scope is derived from its session.

    Services must load the referenced session when enforcing workspace isolation;
    messages deliberately carry no second, potentially contradictory scope field.
    """

    message_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    role: Literal["user", "assistant", "system", "tool"]
    content: str | None = None
    content_ref: str | None = None
    idempotency_key: str = Field(min_length=1)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_content(self) -> ResearchMessage:
        """Require exactly one message content representation."""

        has_content = self.content is not None and bool(self.content.strip())
        has_content_ref = self.content_ref is not None and bool(self.content_ref.strip())
        if has_content == has_content_ref:
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
    checked_at: AwareDatetime


class SkillManifest(BaseModel):
    """Declarative Skill requiring a closed internal allowlist and trusted registry.

    Task 6 execution services MUST call :meth:`validate_tool_registry` with the
    platform-owned authorized tool IDs before compiling or running a Skill. A
    manifest can declare references, but it cannot grant permissions to itself.
    """

    model_config = ConfigDict(extra="forbid")

    skill_key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    prompt_template: str = Field(min_length=1)
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    allowed_tools: list[str] = Field(default_factory=list)
    attachment_refs: list[str] = Field(default_factory=list)
    status: Literal["draft", "validated", "enabled", "disabled"] = "draft"

    @model_validator(mode="after")
    def validate_allowed_tools(self) -> SkillManifest:
        """Accept only declarative references and fixed platform capabilities."""

        for tool in self.allowed_tools:
            permitted = (
                bool(re.fullmatch(r"(?:internal|mcp):[a-z][a-z0-9_.-]*", tool))
                or tool == "attachment:read"
                or tool == "web:controlled"
            )
            if not permitted:
                raise ValueError(f"allowed_tools contains forbidden tool: {tool}")
        return self

    def validate_tool_registry(self, authorized_tool_ids: Collection[str]) -> SkillManifest:
        """Validate references against the platform-owned trusted tool registry.

        This is an explicit execution-boundary check: callers supply the trusted
        registry, and neither manifest fields nor manifest content can authorize
        an internal or MCP tool. Internal references must also belong to the
        closed :data:`SAFE_INTERNAL_TOOL_IDS` set, so registry misconfiguration
        cannot expose arbitrary internal capabilities.
        """

        authorized = set(authorized_tool_ids)
        unsafe_internal: list[str] = []
        unauthorized: list[str] = []
        for tool in self.allowed_tools:
            if tool.startswith("internal:"):
                if tool not in SAFE_INTERNAL_TOOL_IDS:
                    unsafe_internal.append(tool)
                elif tool not in authorized:
                    unauthorized.append(tool)
            elif tool.startswith("mcp:") and tool not in authorized:
                unauthorized.append(tool)
        if unsafe_internal or unauthorized:
            raise ValueError(
                "allowed_tools violates the safe internal tool allowlist or authorized tool "
                f"registry: unsafe_internal={sorted(unsafe_internal)}, "
                f"unauthorized={sorted(unauthorized)}"
            )
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
    last_run_at: AwareDatetime | None = None
    next_run_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def validate_execution_policy(self) -> AgentSchedule:
        """Enforce the platform-wide single-flight/latest-only policy."""

        if self.allow_concurrent:
            raise ValueError("concurrent schedule reentry is forbidden")
        if self.coalesce_policy != "latest":
            raise ValueError("coalesce policy must be latest")
        return self


class ResearchNote(BaseModel):
    """Versioned user-selected Claim or paragraph reference.

    Services must verify workspace ownership by loading the Claim for claim notes,
    or the Research Run for paragraph notes. Claim notes derive their run from the
    Claim and therefore must not persist a second run reference.
    """

    note_id: str = Field(min_length=1)
    workspace_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    source_kind: Literal["claim", "paragraph"]
    run_id: str | None = Field(default=None, min_length=1)
    claim_id: str | None = None
    paragraph_ref: str | None = None
    summary: str = Field(min_length=1)
    pinned: bool = True
    created_at: AwareDatetime

    @model_validator(mode="after")
    def validate_source_reference(self) -> ResearchNote:
        """Require exactly one of the two approved source shapes."""

        if self.source_kind == "claim" and (
            not self.claim_id or self.run_id is not None or self.paragraph_ref is not None
        ):
            raise ValueError("claim note requires claim_id and forbids run_id and paragraph_ref")
        if self.source_kind == "paragraph" and (
            not self.run_id or not self.paragraph_ref or self.claim_id is not None
        ):
            raise ValueError(
                "paragraph note requires run_id and paragraph_ref and forbids claim_id"
            )
        return self
