"""Framework-free registry for Research Template metadata and executors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from core.contracts.research import (
    ResearchSubject,
    ResearchTemplateDefinition,
)
from core.observability import get_logger

logger = get_logger(__name__)


class ResearchGraphExecutor(Protocol):
    def invoke(self, state: dict) -> dict: ...


class ResearchTemplateValidationError(ValueError):
    """Raised before persistence when a template request is not executable."""


@dataclass(frozen=True)
class RegisteredResearchTemplate:
    definition: ResearchTemplateDefinition
    task_key: str
    graph_factory: Callable[[], ResearchGraphExecutor] | None = None


class ResearchTemplateRegistry:
    """Resolve template metadata without leaking LangGraph into domain contracts."""

    def __init__(self, templates: list[RegisteredResearchTemplate]):
        self._templates = {item.definition.template_key: item for item in templates}

    def list_definitions(self) -> list[ResearchTemplateDefinition]:
        return [item.definition for item in self._templates.values()]

    def resolve(self, template_key: str) -> RegisteredResearchTemplate:
        template = self._templates.get(template_key)
        if template is None:
            logger.warning("research template not found", template_key=template_key)
            raise ResearchTemplateValidationError(f"未知研究模板：{template_key}")
        return template

    def require_executable(
        self, template_key: str, subject: ResearchSubject
    ) -> RegisteredResearchTemplate:
        template = self.resolve(template_key)
        definition = template.definition
        if subject.subject_type not in definition.supported_subject_types:
            raise ResearchTemplateValidationError(
                f"模板 {definition.name} 不支持 {subject.subject_type} 研究对象。"
            )
        if not definition.available or template.graph_factory is None:
            raise ResearchTemplateValidationError(f"模板 {definition.name} 尚在规划中。")
        return template

    def validate_evidence_kinds(self, template_key: str, evidence_kinds: list[str]) -> None:
        definition = self.resolve(template_key).definition
        unsupported = sorted(set(evidence_kinds) - set(definition.evidence_kinds))
        if unsupported:
            raise ResearchTemplateValidationError(
                f"模板 {definition.name} 不支持证据分类：{', '.join(unsupported)}"
            )


def build_default_research_template_registry() -> ResearchTemplateRegistry:
    from services.research_graph import AShareDeepResearchGraph

    common_inputs = {"question": True, "as_of": True, "attachments": True}
    templates = [
        RegisteredResearchTemplate(
            definition=ResearchTemplateDefinition(
                template_key="a_share_deep_research",
                name="A股公司深研",
                description="验证财务质量、行业位置、估值、风险与一致预期。",
                supported_subject_types=["security"],
                available=True,
                status="available",
                input_requirements={**common_inputs, "subject_id": True},
                evidence_kinds=["financial", "industry", "valuation", "risk", "consensus"],
                quality_gate_keys=[
                    "citation_coverage",
                    "required_facets",
                    "consensus_coverage",
                    "numeric_integrity",
                    "conflict_resolution",
                ],
            ),
            task_key="a_share_deep_research_graph",
            graph_factory=AShareDeepResearchGraph,
        ),
        _planned_template(
            "macro_research", "宏观研究", "追踪增长、通胀、流动性与政策传导。", ["macro"]
        ),
        _planned_template(
            "commodity_research", "商品研究", "分析供需、库存、成本曲线与周期位置。", ["commodity"]
        ),
        _planned_template(
            "index_research", "指数研究", "拆解指数、ETF、权重结构与风格暴露。", ["index", "etf"]
        ),
        _planned_template(
            "industry_research", "行业研究", "研究产业链、竞争格局、景气与关键事件。", ["industry"]
        ),
    ]
    return ResearchTemplateRegistry(templates)


def _planned_template(
    template_key: str,
    name: str,
    description: str,
    subject_types: list[str],
) -> RegisteredResearchTemplate:
    return RegisteredResearchTemplate(
        definition=ResearchTemplateDefinition(
            template_key=template_key,
            name=name,
            description=description,
            supported_subject_types=subject_types,
            available=False,
            status="planned",
            input_requirements={"question": True, "as_of": True, "attachments": True},
        ),
        task_key=f"{template_key}_graph",
    )


_default_registry: ResearchTemplateRegistry | None = None


def get_default_research_template_registry() -> ResearchTemplateRegistry:
    """Build the executor registry lazily to keep API imports lightweight."""
    global _default_registry
    if _default_registry is None:
        try:
            _default_registry = build_default_research_template_registry()
        except Exception:
            logger.exception("default research template registry initialization failed")
            raise
    return _default_registry
