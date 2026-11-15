"""Bounded, non-secret Research Bot configuration; no execution authority."""

import json
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SkillBinding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,254}$")
    version: int = Field(ge=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    arguments: dict = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def bounded_arguments(cls, value):
        if len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode()) > 4000:
            raise ValueError("bot_skill_arguments_too_large")
        return value


class BotConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    objective: str = Field(min_length=1, max_length=3000)
    avatar: str = Field(default="cow", pattern=r"^(cow|cat|dog|bear|rabbit|panda|fox|penguin)$")
    color: str = Field(default="#0786ff", pattern=r"^#[a-fA-F0-9]{6}$")
    keywords: list[str] = Field(default_factory=list, max_length=20)
    watchlist: list[str] = Field(default_factory=list, max_length=10)
    skills: list[SkillBinding] = Field(default_factory=list, max_length=12)
    approved_tools: list[str] = Field(default_factory=list, max_length=64)
    interval_minutes: int = Field(default=30, ge=5, le=1440)

    @field_validator("objective")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("bot_objective_required")
        return value.strip()

    @field_validator("keywords", "watchlist")
    @classmethod
    def unique_terms(cls, values):
        if any(not v.strip() or len(v) > 40 or v != v.strip() for v in values):
            raise ValueError("bot_term_invalid")
        if len({v.casefold() for v in values}) != len(values):
            raise ValueError("bot_term_duplicate")
        return values

    @model_validator(mode="after")
    def unique_skills(self):
        if len({b.id for b in self.skills}) != len(self.skills):
            raise ValueError("bot_skill_duplicate")
        if len(set(self.approved_tools)) != len(self.approved_tools):
            raise ValueError("bot_tool_duplicate")
        return self


class BotSave(BotConfiguration):
    name: str = Field(min_length=1, max_length=80)
    model_provider: str = Field(pattern=r"^(deepseek-official|openai-compatible)$")
    model_id: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    expected_version: int | None = Field(default=None, ge=1)
    request_id: str | None = None

    @field_validator("name")
    @classmethod
    def name_nonblank(cls, value):
        if not value.strip():
            raise ValueError("bot_name_required")
        return value.strip()

    @field_validator("request_id")
    @classmethod
    def request_uuid(cls, value):
        if value is not None and str(UUID(value)) != value:
            raise ValueError("bot_request_id_invalid")
        return value

    def configuration(self):
        return BotConfiguration.model_validate(
            self.model_dump(
                exclude={"name", "model_provider", "model_id", "expected_version", "request_id"}
            )
        )
