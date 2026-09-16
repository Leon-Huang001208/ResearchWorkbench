"""Versioned public contracts for unified integration state."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class IntegrationItemStatus(BaseModel):
    """One safe, provider-neutral integration status projection."""

    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = 1
    id: str = Field(min_length=3, max_length=160)
    scope: Literal["data", "local"]
    kind: str = Field(min_length=1, max_length=64)
    source_id: str | None = Field(default=None, max_length=64)
    label: str = Field(min_length=1, max_length=160)
    registered: bool
    implementation_state: Literal["implemented", "not_delivered"]
    configured: bool
    authorized: bool
    probe_state: str = Field(min_length=1, max_length=64)
    runtime_callable: bool
    stages: dict[Literal["registration", "authorization", "probe", "adaptation", "runtime"], str]
    bucket: Literal["available", "checking", "user_action", "system_fault", "not_delivered"]
    responsibility: Literal["user", "system", "vendor", "developer"]
    capabilities: list[str] = Field(default_factory=list, max_length=64)
    last_attempt_at: str | None = Field(default=None, max_length=64)
    last_success_at: str | None = Field(default=None, max_length=64)
    stale: bool
    error_code: str | None = Field(default=None, max_length=96)
    details: dict[str, Any] = Field(default_factory=dict)
