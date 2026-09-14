"""Editable package contracts; validation issues are retained with drafts."""

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..store import StoreError


class CapabilityError(StoreError):
    def __init__(self, message, code="invalid_capability", status=422):
        super().__init__(message)
        self.code, self.status = code, status


class InputField(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z][a-zA-Z0-9_]*$")
    label: str = Field(min_length=1, max_length=120)
    type: Literal["text", "file", "date", "number"] = "text"
    required: bool = True


class MethodPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    required: list[str] = Field(default_factory=list, max_length=3)
    recommended: list[str] = Field(default_factory=list, max_length=3)
    excluded: list[str] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def validate_sets(self):
        for values in (self.required, self.recommended, self.excluded):
            if len(values) != len(set(values)) or any(
                not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", value) for value in values
            ):
                raise ValueError("方法策略包含空值或重复项")
        if set(self.required) & set(self.excluded):
            raise ValueError("必需方法不能同时被排除")
        return self


class Metadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str = Field(min_length=1, max_length=2000)
    category: str = Field(min_length=1, max_length=80)
    inputs: list[InputField] = Field(min_length=1, max_length=30)
    scenarios: list[str] = Field(min_length=1, max_length=30)
    default_formats: list[Literal["md", "html", "docx", "xlsx", "pptx", "png"]]
    required_tools: list[str] = Field(default_factory=list, max_length=20)
    dependencies: list[str] = Field(default_factory=list, max_length=40)
    method_policy: MethodPolicy = Field(default_factory=MethodPolicy)


class Step(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    instruction: str = Field(min_length=1, max_length=10000)
    skill_id: str | None = None
    tools: list[str] = Field(default_factory=list, max_length=20)


class DraftInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["skill", "workflow"] = "skill"
    metadata: dict = Field(default_factory=dict)
    instructions: str = Field(default="", max_length=1000000)
    files: list[dict] = Field(default_factory=list, max_length=128)
    steps: list[dict] = Field(default_factory=list, max_length=40)
    reviewed_scripts: list[str] = Field(default_factory=list, max_length=128)


class CopyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    slug: str = Field(min_length=1, max_length=80)


class VersionInput(BaseModel):
    version: int = Field(ge=1, strict=True)


class CreationInput(BaseModel):
    kind: Literal["skill", "workflow"] = "skill"
    goal: str = Field(min_length=1, max_length=10000)


class ArtifactInput(BaseModel):
    session_id: str
    file_id: str


def issue(code, message, path=None):
    return {"code": code, "message": message, "path": path}
