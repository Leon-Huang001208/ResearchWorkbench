"""Compiled report project generation readiness plans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

from core.observability import get_logger
from reporting.projects.generation import (
    ReportPeriod,
    RetrievalConfig,
    apply_composite_component_overrides,
    apply_report_defaults_to_placeholder,
    build_retrieval_config,
    iter_placeholder_configs,
    normalize_placeholder_output_type,
    parse_prompt_templates,
    resolve_report_generation_scope,
)
from reporting.projects.keyword_profiles import apply_keyword_profile_to_config

logger = get_logger(__name__)


@dataclass(frozen=True)
class CompiledPlaceholderPlan:
    """Effective readiness for one report placeholder before generation starts."""

    placeholder: str
    title: str
    output_type: str
    prompt_template: str
    prompt_found: bool
    retrieval_ready: bool
    evidence_required: bool
    deterministic: bool
    warnings: List[str] = field(default_factory=list)
    retrieval_config: RetrievalConfig | None = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the plan for API consumers."""
        retrieval_config = None
        if self.retrieval_config:
            retrieval_config = {
                "mode": self.retrieval_config.mode,
                "top_k": self.retrieval_config.top_k,
                "candidate_k": self.retrieval_config.candidate_k,
                "must_any": self.retrieval_config.must_any,
                "exclude": self.retrieval_config.exclude,
                "source_types": self.retrieval_config.source_types,
                "rerank_enabled": self.retrieval_config.rerank_enabled,
                "rerank_provider": self.retrieval_config.rerank_provider,
                "rerank_model": self.retrieval_config.rerank_model,
                "rerank_top_n": self.retrieval_config.rerank_top_n,
                "min_rerank_score": self.retrieval_config.min_rerank_score,
            }
        return {
            "placeholder": self.placeholder,
            "title": self.title,
            "output_type": self.output_type,
            "prompt_template": self.prompt_template,
            "prompt_found": self.prompt_found,
            "retrieval_ready": self.retrieval_ready,
            "evidence_required": self.evidence_required,
            "deterministic": self.deterministic,
            "warnings": list(self.warnings),
            "retrieval_config": retrieval_config,
        }


@dataclass(frozen=True)
class CompiledReportPlan:
    """Generation plan shared by the API and report workbench preflight UI."""

    placeholders: List[CompiledPlaceholderPlan]
    report_period: ReportPeriod
    lookback_days: int
    data_scope: str
    ready: bool
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the plan for API consumers."""
        return {
            "ready": self.ready,
            "report_period": {
                "start_date": self.report_period.start_date,
                "end_date": self.report_period.end_date,
            },
            "lookback_days": self.lookback_days,
            "data_scope": self.data_scope,
            "warnings": list(self.warnings),
            "placeholders": [placeholder.to_dict() for placeholder in self.placeholders],
        }


def compile_report_plan(
    report_config: Dict[str, Any],
    prompt_templates_source: str,
    *,
    report_date: str | None = None,
    lookback_days: int | None = None,
    data_scope: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> CompiledReportPlan:
    """Compile effective placeholder generation settings without rendering output."""
    safe_config = report_config if isinstance(report_config, dict) else {}
    scope = resolve_report_generation_scope(
        safe_config,
        report_date=report_date,
        lookback_days=lookback_days,
        data_scope=data_scope,
        start_date=start_date,
        end_date=end_date,
    )
    templates = parse_prompt_templates(prompt_templates_source or "")
    placeholders: List[CompiledPlaceholderPlan] = []
    warnings: List[str] = []

    for placeholder, raw_config in iter_placeholder_configs(safe_config):
        try:
            placeholder_plan = _compile_placeholder_plan(
                safe_config,
                placeholder,
                raw_config,
                templates,
            )
        except Exception as exc:
            logger.warning(
                "Failed to compile report placeholder plan",
                placeholder=placeholder,
                error=str(exc),
            )
            placeholder_plan = CompiledPlaceholderPlan(
                placeholder=placeholder,
                title=str(raw_config.get("title") or placeholder),
                output_type="unknown",
                prompt_template="",
                prompt_found=False,
                retrieval_ready=False,
                evidence_required=True,
                deterministic=False,
                warnings=[f"{placeholder}: 计划编译失败 {exc}"],
            )
        placeholders.append(placeholder_plan)
        warnings.extend(placeholder_plan.warnings)

    ready = all(
        placeholder.prompt_found and placeholder.retrieval_ready and not placeholder.warnings
        for placeholder in placeholders
        if placeholder.evidence_required
    )
    logger.debug(
        "Compiled report plan",
        placeholder_count=len(placeholders),
        ready=ready,
        warning_count=len(warnings),
    )
    return CompiledReportPlan(
        placeholders=placeholders,
        report_period=scope.report_period,
        lookback_days=scope.lookback_days,
        data_scope=scope.data_scope,
        ready=ready,
        warnings=warnings,
    )


def _compile_placeholder_plan(
    report_config: Dict[str, Any],
    placeholder: str,
    raw_config: Dict[str, Any],
    templates: Dict[str, Any],
) -> CompiledPlaceholderPlan:
    config = apply_report_defaults_to_placeholder(report_config, raw_config)
    if str(config.get("type") or "").strip().lower() == "composite_market_review":
        config = apply_composite_component_overrides(config)
    output_type = normalize_placeholder_output_type(config)
    title = str(config.get("title") or placeholder).strip() or placeholder
    prompt_template = str(config.get("prompt_template") or "").strip()
    evidence_required = _requires_evidence(config, output_type)
    deterministic = not evidence_required
    retrieval_config = None
    retrieval_ready = True
    prompt_found = True
    item_warnings: List[str] = []

    if evidence_required:
        prompt_found = bool(prompt_template and prompt_template in templates)
        if not prompt_found:
            item_warnings.append(f"{placeholder}: 缺少 Prompt 模板 {prompt_template}")
        prompt = templates.get(prompt_template)
        config = apply_keyword_profile_to_config(
            placeholder,
            config,
            prompt_text=(prompt.raw_text or prompt.retrieval_query) if prompt else "",
        )
        retrieval_config = build_retrieval_config(
            config,
            default_top_k=int(config.get("evidence_limit") or 8),
        )
        retrieval_ready = bool(
            prompt and (retrieval_config.must_any or prompt.retrieval_query.strip())
        )
        if not retrieval_ready:
            item_warnings.append(f"{placeholder}: 缺少检索关键词或 Query")

    return CompiledPlaceholderPlan(
        placeholder=placeholder,
        title=title,
        output_type=output_type,
        prompt_template=prompt_template,
        prompt_found=prompt_found,
        retrieval_ready=retrieval_ready,
        evidence_required=evidence_required,
        deterministic=deterministic,
        warnings=item_warnings,
        retrieval_config=retrieval_config,
    )


def _requires_evidence(config: Dict[str, Any], output_type: str) -> bool:
    legacy_type = str(config.get("type") or "").strip().lower()
    if legacy_type in {"excel_commodity_market_review"}:
        return False
    if legacy_type in {"prompt", "ai_text", "composite_market_review"}:
        return True
    return output_type == "paragraph"
