"""Lightweight snapshot contract for embedded (iframe) frameworks."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ..base import BlockMeta, GapRecord, SourceRecord


class EmbeddedModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ResearchState(EmbeddedModel):
    label: Literal["可用", "待启动", "不可达"] = "可用"
    note: str = "外部项目独立运行，点击进入完整交互。"


class ExternalApp(EmbeddedModel):
    url: str = Field(min_length=1, max_length=1000)
    local_path: str = Field(default="", max_length=1000)
    launch_command: str = Field(default="", max_length=500)
    port: int | None = Field(default=None, ge=1, le=65535)


class EmbeddedSnapshot(EmbeddedModel):
    schema_version: Literal[1] = 1
    revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    as_of: str
    fetched_at: str
    status: Literal["可用", "待启动", "不可达"]
    coverage: int = Field(ge=0, le=100)
    overview: BlockMeta
    external_app: ExternalApp
    research_state: ResearchState
    gaps: list[GapRecord] = Field(default_factory=list, max_length=20)
