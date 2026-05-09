"""
Core contracts for reporting (section specs and outputs).

This module defines Pydantic models for report section specifications and
section outputs in AlphaFoundry.
"""
from typing import Literal

from pydantic import BaseModel, Field


class SectionSpec(BaseModel):
    """报告段落规范 - 定义报告各段落的要求.

    Defines the requirements for a report section, including key, title,
    target word count, required facets, scenario requirement, and evidence policy.

    Attributes:
        key: Unique key for the section.
        title: Title of the section.
        target_words: Target word count for the section.
        required_facets: List of required facets for the section.
        scenario_required: Whether a scenario is required (default True).
        evidence_policy: Evidence policy ("strict", "allow_synthesis") (default "strict").
    """

    key: str = Field(description="Unique key for the section")
    title: str = Field(description="Title of the section")
    target_words: int = Field(description="Target word count for the section")
    required_facets: list[str] = Field(default_factory=list, description="List of required facets for the section")
    scenario_required: bool = Field(default=True, description="Whether a scenario is required")
    evidence_policy: Literal["strict", "allow_synthesis"] = Field(default="strict", description="Evidence policy (strict, allow_synthesis)")


class SectionOutput(BaseModel):
    """报告段落输出 - 生成的单个段落.

    Represents the output for a single report section, including key, content,
    evidence references, scenario references, and warnings.

    Attributes:
        key: Unique key for the section.
        content: Generated content for the section.
        evidence_refs: List of evidence references used.
        scenario_refs: List of scenario references used.
        warnings: List of warnings generated during section creation.
    """

    key: str = Field(description="Unique key for the section")
    content: str = Field(description="Generated content for the section")
    evidence_refs: list[str] = Field(default_factory=list, description="List of evidence references used")
    scenario_refs: list[str] = Field(default_factory=list, description="List of scenario references used")
    warnings: list[str] = Field(default_factory=list, description="List of warnings generated during section creation")
