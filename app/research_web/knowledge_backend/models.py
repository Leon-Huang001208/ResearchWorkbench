"""Small explicit contracts; report approval cannot be supplied by a tool callback."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Binding(StrictModel):
    token: SecretStr
    workspace_id: str = Field(pattern=r"^[1-9][0-9]{0,18}$")


class Search(StrictModel):
    query: str = Field(min_length=1, max_length=2000)
    knowledge_base_ids: list[str] = Field(min_length=1, max_length=10)
    document_ids: list[str] | None = Field(default=None, min_length=1, max_length=100)
    scope_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class SourceApproval(StrictModel):
    document_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    available_at: str = Field(max_length=40)
    time_evidence: str = Field(min_length=8, max_length=1000)

    @field_validator("available_at")
    @classmethod
    def aware_time(cls, value):
        stamp = datetime.fromisoformat(value)
        if stamp.tzinfo is None:
            raise ValueError("explicit time zone required")
        return value


class Scope(StrictModel):
    report_period: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    cutoff: str = Field(max_length=40)
    documents: list[SourceApproval] = Field(min_length=1, max_length=100)
    # This records an authenticated operator approval, never vendor metadata inferred by a model.
    confirm_source_times: bool

    _cutoff_time = field_validator("cutoff")(SourceApproval.aware_time.__func__)


class Read(StrictModel):
    document_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    scope_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class Freeze(StrictModel):
    scope_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    chunks: dict[str, list[str]] = Field(min_length=1, max_length=8)
