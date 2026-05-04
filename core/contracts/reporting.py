from typing import Literal

from pydantic import BaseModel, Field


class SectionSpec(BaseModel):
    """报告段落规范 - 定义报告各段落的要求"""

    key: str
    title: str
    target_words: int
    required_facets: list[str] = Field(default_factory=list)
    scenario_required: bool = True
    evidence_policy: Literal["strict", "allow_synthesis"] = "strict"


class SectionOutput(BaseModel):
    """报告段落输出 - 生成的单个段落"""

    key: str
    content: str
    evidence_refs: list[str] = Field(default_factory=list)
    scenario_refs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
