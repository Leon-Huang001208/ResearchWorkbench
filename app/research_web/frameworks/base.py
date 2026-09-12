"""Thin shared contracts for framework metadata and evidence freshness."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FrameworkError(RuntimeError):
    def __init__(self, message: str, code: str = "framework_error", status: int = 422):
        super().__init__(message)
        self.code = code
        self.status = status


class SourceRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    url: str = Field(min_length=1, max_length=1000)
    observed_at: str = Field(min_length=1, max_length=40)
    unit: str = Field(min_length=1, max_length=80)
    method: str = Field(min_length=1, max_length=240)
    proxy: bool = False


class GapRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=1, max_length=180)
    severity: Literal["low", "medium", "high"]
    next_check: str = Field(min_length=1, max_length=280)


class BlockMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: str = Field(min_length=1, max_length=40)
    fetched_at: str = Field(min_length=1, max_length=40)
    status: Literal["complete", "partial", "stale", "proxy", "missing", "fixture"]
    sources: list[SourceRecord] = Field(default_factory=list, max_length=20)
    gaps: list[GapRecord] = Field(default_factory=list, max_length=20)


class FrameworkSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z0-9-]+$")
    label: str = Field(min_length=1, max_length=80)
    question: str = Field(min_length=1, max_length=280)


class FrameworkDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str = Field(min_length=1, max_length=120)
    domain: str = Field(min_length=1, max_length=80)
    version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    source_revision: str = Field(pattern=r"^[a-f0-9]{10,40}$")
    question: str = Field(min_length=1, max_length=500)
    chain: list[str] = Field(min_length=2, max_length=12)
    counter_evidence: list[str] = Field(min_length=1, max_length=20)
    sections: list[FrameworkSection] = Field(min_length=1, max_length=20)
    method: str = Field(min_length=1, max_length=1000)
