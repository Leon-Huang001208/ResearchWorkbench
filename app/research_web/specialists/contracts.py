"""Strict business contracts; none of these objects authorize native execution."""

import json
import re
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..store import StoreError


class SpecialistError(StoreError):
    def __init__(self, message: str, code="specialist_invalid", status=422):
        super().__init__(message, code, status)


class StrictContract(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Budget(StrictContract):
    confirmed: Literal[True]
    max_tokens: int = Field(gt=0, le=2_000_000)
    max_calls: int = Field(gt=0, le=48)
    max_concurrency: int = Field(default=2, ge=1, le=2)
    timeout_seconds: int = Field(default=1800, ge=1, le=1800)
    max_revisions: int = Field(default=2, ge=0, le=2)

    @field_validator("confirmed", mode="before")
    @classmethod
    def explicit_confirmation(cls, value):
        if value is not True:
            raise ValueError("预算必须明确确认")
        return value


class PlanNode(StrictContract):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    role: Literal["orchestrator", "industry", "quant", "review"]
    input: dict = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list, max_length=16)
    skills: list[str] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def bounded_input(self):
        try:
            encoded = json.dumps(self.input, ensure_ascii=False, allow_nan=False)
        except (ValueError, TypeError) as exc:
            raise ValueError("节点输入必须是有限JSON值") from exc
        if len(encoded.encode()) > 32768:
            raise ValueError("节点输入过大")
        if len(set(self.depends_on)) != len(self.depends_on):
            raise ValueError("依赖不能重复")
        return self


class PlanUpdate(StrictContract):
    expected_version: int = Field(ge=0)
    nodes: list[PlanNode] = Field(min_length=3, max_length=16)

    @model_validator(mode="after")
    def valid_graph(self):
        nodes = {node.id: node for node in self.nodes}
        if len(nodes) != len(self.nodes):
            raise ValueError("节点标识不能重复")
        ancestors: dict[str, set[str]] = {}

        def visit(node_id, visiting):
            if node_id in ancestors:
                return ancestors[node_id]
            if node_id in visiting or node_id not in nodes:
                raise ValueError("计划含循环或未知依赖")
            values = set()
            for dependency in nodes[node_id].depends_on:
                values.add(dependency)
                values.update(visit(dependency, visiting | {node_id}))
            ancestors[node_id] = values
            return values

        for node in self.nodes:
            visit(node.id, set())
        roles = {node.role for node in self.nodes}
        if not {"industry", "quant", "review"} <= roles:
            raise ValueError("行业、量化和独立审查节点均为必需")
        for node in self.nodes:
            if node.role == "review":
                reviewed = {nodes[value].role for value in ancestors[node.id]}
                if not {"industry", "quant"} <= reviewed:
                    raise ValueError("独立审查必须依赖行业和量化成果")
        return self


class NodeResult(StrictContract):
    conclusion: str = Field(min_length=1, max_length=20000)
    evidence_ids: list[str] = Field(max_length=100)
    as_of_date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    limitations: list[str] = Field(max_length=30)
    artifact_ids: list[str] = Field(max_length=50)

    @model_validator(mode="after")
    def references(self):
        date.fromisoformat(self.as_of_date)
        if not self.conclusion.strip():
            raise ValueError("节点结论不能为空")
        if any(
            len(values) != len(set(values)) for values in (self.evidence_ids, self.artifact_ids)
        ):
            raise ValueError("证据或产物引用不能重复")
        for value in self.evidence_ids + self.artifact_ids:
            if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,199}", value):
                raise ValueError("证据与产物必须使用本会话引用标识")
        if any(not value.strip() or len(value) > 2000 for value in self.limitations):
            raise ValueError("限制条件无效")
        return self
