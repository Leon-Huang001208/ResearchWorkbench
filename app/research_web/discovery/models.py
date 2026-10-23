"""Closed, user-action request contracts for discovery."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..store import StoreError

Horizon = Literal["short", "medium", "long"]
UUID_PATTERN = r"^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$"


class DiscoveryError(StoreError):
    """A safe, structured error without upstream bodies or local credentials."""


class Prepare(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    request_id: str = Field(pattern=UUID_PATTERN)
    feed_id: str = Field(pattern=UUID_PATTERN)
    horizon: Horizon = "medium"
    theme_id: str = Field(min_length=1, max_length=160, pattern=r"^[A-Za-z0-9_-]+$")
    material_ids: list[str] = Field(min_length=1, max_length=20)
    target_mode: Literal["fingpt", "claw"] = "fingpt"
    question: str = Field(min_length=1, max_length=6000)

    @field_validator("request_id", "feed_id")
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value))

    @field_validator("material_ids")
    @classmethod
    def selected_materials(cls, value):
        if len(set(value)) != len(value) or any(not 1 <= len(item) <= 256 for item in value):
            raise ValueError("资料选择重复或标识非法")
        return value

    @field_validator("question")
    @classmethod
    def nonempty_question(cls, value):
        if not value.strip():
            raise ValueError("研究问题不能为空")
        return value.strip()
