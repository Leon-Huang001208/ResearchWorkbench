"""Report project render orchestration.

This module owns one report-project run: placeholder generation, template
projection, deterministic tables/charts, and run-log assembly.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

from core.observability import get_logger
from reporting.projections.ppt import PPTTemplateProjection
from reporting.projections.word import WordProjection
from reporting.projects.chart_generation import ReportProjectChartService
from reporting.projects.generation import (
    GeneratedSectionInfo,
    ReportGenerationResult,
    ReportProjectGenerationService,
    resolve_report_generation_scope,
)
from reporting.projects.project_manager import ReportProject
from reporting.projects.table_generation import build_project_tables

logger = get_logger(__name__)

TableBuilder = Callable[..., tuple[Any, List[Dict[str, Any]]]]


@dataclass(frozen=True)
class ReportProjectRunRequest:
    """Inputs required to render one report project artifact."""

    placeholders: Dict[str, str] = field(default_factory=dict)
    generate_from_config: bool = True
    lookback_days: int | None = None
    report_date: str | None = None
    data_scope: str | None = None
    start_date: str | None = None
    end_date: str | None = None


@dataclass(frozen=True)
class ReportProjectRunResult:
    """Rendered artifact metadata and aggregated warnings."""

    project_name: str
    slug: str
    file_name: str
    output_path: Path
    run_log_path: Path
    generated_at: datetime
    generated_placeholder_count: int
    evidence_count: int
    warnings: List[str] = field(default_factory=list)


class ReportProjectRunService:
    """Execute a project-level Word or PPT report render."""

    def __init__(
        self,
        *,
        generation_service: Any | None = None,
        chart_service: Any | None = None,
        table_builder: TableBuilder | None = None,
        word_projection_factory: Callable[[], Any] | None = None,
        ppt_projection_factory: Callable[[], Any] | None = None,
    ) -> None:
        self.generation_service = generation_service or ReportProjectGenerationService()
        self.chart_service = chart_service or ReportProjectChartService()
        self.table_builder = table_builder or build_project_tables
        self.word_projection_factory = word_projection_factory or WordProjection
        self.ppt_projection_factory = ppt_projection_factory or PPTTemplateProjection

    def execute(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        request: ReportProjectRunRequest,
    ) -> ReportProjectRunResult:
        """Render the configured report project and write its run log."""
        generation_scope = resolve_report_generation_scope(
            section_config,
            report_date=request.report_date,
            lookback_days=request.lookback_days,
            data_scope=request.data_scope,
            start_date=request.start_date,
            end_date=request.end_date,
        )
        if project.project_type == "ppt":
            return self._execute_ppt(
                project=project,
                section_config=section_config,
                prompt_templates_source=prompt_templates_source,
                request=request,
                generation_scope=generation_scope,
            )
        return self._execute_word(
            project=project,
            section_config=section_config,
            prompt_templates_source=prompt_templates_source,
            request=request,
            generation_scope=generation_scope,
        )

    def _execute_word(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        request: ReportProjectRunRequest,
        generation_scope: Any,
    ) -> ReportProjectRunResult:
        generation_result = self._generate_placeholders(
            project=project,
            section_config=section_config,
            prompt_templates_source=prompt_templates_source,
            request=request,
            generation_scope=generation_scope,
        )
        placeholder_map = generation_result.placeholders
        generated_sections = generation_result.sections
        generation_warnings = generation_result.warnings

        generated_at = datetime.now()
        file_name = self._artifact_file_name(project, generated_at, ".docx")
        output_path = project.output_dir / file_name

        tables, table_infos = self.table_builder(
            project=project,
            section_config=section_config,
        )
        self.word_projection_factory().save_from_template(
            output_path=output_path,
            template_path=project.word_template_path,
            sections=[],
            placeholders=placeholder_map,
            tables=tables,
        )
        chart_infos = self.chart_service.generate_and_embed(
            project=project,
            section_config=section_config,
            docx_path=output_path,
        )
        run_path = self._write_word_run_log(
            project=project,
            request=request,
            generation_scope=generation_scope,
            output_path=output_path,
            generated_at=generated_at,
            placeholder_map=placeholder_map,
            generated_sections=generated_sections,
            generation_warnings=generation_warnings,
            chart_infos=chart_infos,
            table_infos=table_infos,
        )

        logger.info(
            "Rendered report project",
            slug=project.slug,
            output_path=str(output_path),
            run_path=str(run_path),
        )

        return ReportProjectRunResult(
            project_name=project.name,
            slug=project.slug,
            file_name=file_name,
            output_path=output_path,
            run_log_path=run_path,
            generated_at=generated_at,
            generated_placeholder_count=len(placeholder_map),
            evidence_count=sum(section.evidence_count for section in generated_sections),
            warnings=self._word_warnings(
                generation_warnings=generation_warnings,
                generated_sections=generated_sections,
                chart_infos=chart_infos,
                table_infos=table_infos,
            ),
        )

    def _execute_ppt(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        request: ReportProjectRunRequest,
        generation_scope: Any,
    ) -> ReportProjectRunResult:
        if not project.ppt_template_path or not project.ppt_template_path.exists():
            raise FileNotFoundError(f"Report project PPT template not found: {project.slug}")

        generation_result = self._generate_placeholders(
            project=project,
            section_config=section_config,
            prompt_templates_source=prompt_templates_source,
            request=request,
            generation_scope=generation_scope,
        )
        placeholder_map = generation_result.placeholders
        generated_sections = generation_result.sections
        generation_warnings = generation_result.warnings

        generated_at = datetime.now()
        file_name = self._artifact_file_name(project, generated_at, ".pptx")
        output_path = project.output_dir / file_name

        projection_result = self.ppt_projection_factory().save_from_template(
            output_path=output_path,
            template_path=project.ppt_template_path,
            placeholders=placeholder_map,
        )
        projection_warnings = [
            f"PPT 占位符未配置：{placeholder}" for placeholder in projection_result.missing_placeholders
        ]
        run_path = self._write_ppt_run_log(
            project=project,
            request=request,
            generation_scope=generation_scope,
            output_path=output_path,
            generated_at=generated_at,
            placeholder_map=placeholder_map,
            generated_sections=generated_sections,
            generation_warnings=generation_warnings,
            projection_result=projection_result,
        )

        logger.info(
            "Rendered PPT report project",
            slug=project.slug,
            output_path=str(output_path),
            run_path=str(run_path),
        )

        return ReportProjectRunResult(
            project_name=project.name,
            slug=project.slug,
            file_name=file_name,
            output_path=output_path,
            run_log_path=run_path,
            generated_at=generated_at,
            generated_placeholder_count=len(placeholder_map),
            evidence_count=sum(section.evidence_count for section in generated_sections),
            warnings=generation_warnings
            + [warning for section in generated_sections for warning in section.warnings]
            + projection_warnings,
        )

    def _generate_placeholders(
        self,
        *,
        project: ReportProject,
        section_config: Dict[str, Any],
        prompt_templates_source: str,
        request: ReportProjectRunRequest,
        generation_scope: Any,
    ) -> ReportGenerationResult:
        if request.generate_from_config:
            return self.generation_service.generate_placeholders(
                project=project,
                section_config=section_config,
                prompt_templates_source=prompt_templates_source,
                manual_placeholders=request.placeholders,
                lookback_days=generation_scope.lookback_days,
                report_period=generation_scope.report_period,
            )
        return ReportGenerationResult(placeholders=request.placeholders, sections=[], warnings=[])

    def _write_word_run_log(
        self,
        *,
        project: ReportProject,
        request: ReportProjectRunRequest,
        generation_scope: Any,
        output_path: Path,
        generated_at: datetime,
        placeholder_map: Dict[str, str],
        generated_sections: List[GeneratedSectionInfo],
        generation_warnings: List[str],
        chart_infos: Any,
        table_infos: List[Dict[str, Any]],
    ) -> Path:
        report_period = generation_scope.report_period
        run_record = {
            "project_name": project.name,
            "slug": project.slug,
            "word_template_path": str(project.word_template_path),
            "excel_workbook_path": str(project.excel_workbook_path),
            "section_config_path": str(project.section_config_path),
            "prompt_templates_path": str(project.prompt_templates_path)
            if project.prompt_templates_path
            else None,
            "data_source_paths": [str(path) for path in project.data_source_paths],
            "output_path": str(output_path),
            "generated_at": generated_at.isoformat(),
            "placeholder_count": len(placeholder_map),
            "manual_placeholder_count": len(request.placeholders),
            "generate_from_config": request.generate_from_config,
            "report_date": generation_scope.report_date,
            "data_scope": generation_scope.data_scope,
            "lookback_days": generation_scope.lookback_days,
            "report_period": {
                "start_date": report_period.start_date,
                "end_date": report_period.end_date,
            },
            "generation": self._generation_record(generated_sections, generation_warnings),
            "charts": [
                {
                    "chart_id": chart.chart_id,
                    "title": chart.title,
                    "workbook": chart.workbook,
                    "source_chart": chart.source_chart,
                    "replace_kind": chart.replace_kind,
                    "point_count": chart.point_count,
                    "warnings": chart.warnings,
                }
                for chart in chart_infos
            ],
            "tables": table_infos,
        }
        return self._write_run_record(project, generated_at, run_record)

    def _write_ppt_run_log(
        self,
        *,
        project: ReportProject,
        request: ReportProjectRunRequest,
        generation_scope: Any,
        output_path: Path,
        generated_at: datetime,
        placeholder_map: Dict[str, str],
        generated_sections: List[GeneratedSectionInfo],
        generation_warnings: List[str],
        projection_result: Any,
    ) -> Path:
        report_period = generation_scope.report_period
        run_record = {
            "project_name": project.name,
            "slug": project.slug,
            "project_type": project.project_type,
            "ppt_template_path": str(project.ppt_template_path),
            "section_config_path": str(project.section_config_path),
            "prompt_templates_path": str(project.prompt_templates_path)
            if project.prompt_templates_path
            else None,
            "data_source_paths": [str(path) for path in project.data_source_paths],
            "output_path": str(output_path),
            "generated_at": generated_at.isoformat(),
            "placeholder_count": len(placeholder_map),
            "manual_placeholder_count": len(request.placeholders),
            "generate_from_config": request.generate_from_config,
            "report_date": generation_scope.report_date,
            "data_scope": generation_scope.data_scope,
            "lookback_days": generation_scope.lookback_days,
            "report_period": {
                "start_date": report_period.start_date,
                "end_date": report_period.end_date,
            },
            "projection": {
                "kind": "ppt",
                "replaced_count": projection_result.replaced_count,
                "missing_placeholders": projection_result.missing_placeholders,
            },
            "generation": self._generation_record(generated_sections, generation_warnings),
        }
        return self._write_run_record(project, generated_at, run_record)

    def _write_run_record(
        self,
        project: ReportProject,
        generated_at: datetime,
        run_record: Dict[str, Any],
    ) -> Path:
        run_path = project.run_log_dir / f"{generated_at.strftime('%Y-%m-%d_%H%M%S')}.json"
        run_path.write_text(
            json.dumps(run_record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return run_path

    @staticmethod
    def _generation_record(
        generated_sections: List[GeneratedSectionInfo],
        generation_warnings: List[str],
    ) -> Dict[str, Any]:
        return {
            "sections": [
                {
                    "placeholder": section.placeholder,
                    "title": section.title,
                    "prompt_template": section.prompt_template,
                    "retrieval_query": section.retrieval_query,
                    "evidence_count": section.evidence_count,
                    "model_name": section.model_name,
                    "provider": section.provider,
                    "tokens_used": section.tokens_used,
                    "warnings": section.warnings,
                    "retrieval_config": serialize_retrieval_config(section.retrieval_config),
                    "evidence": [serialize_evidence(item) for item in section.evidence],
                }
                for section in generated_sections
            ],
            "warnings": generation_warnings,
        }

    @staticmethod
    def _word_warnings(
        *,
        generation_warnings: List[str],
        generated_sections: List[GeneratedSectionInfo],
        chart_infos: Any,
        table_infos: List[Dict[str, Any]],
    ) -> List[str]:
        chart_warnings = [warning for chart in chart_infos for warning in chart.warnings]
        table_warnings = [warning for table in table_infos for warning in table["warnings"]]
        return (
            generation_warnings
            + [warning for section in generated_sections for warning in section.warnings]
            + chart_warnings
            + table_warnings
        )

    @staticmethod
    def _artifact_file_name(
        project: ReportProject,
        generated_at: datetime,
        suffix: str,
    ) -> str:
        timestamp = generated_at.strftime("%Y-%m-%d_%H%M%S")
        safe_project_name = project.name.replace("/", "_").replace(":", "_")
        return f"{timestamp}_{safe_project_name}{suffix}"


def serialize_retrieval_config(config: Any) -> Dict[str, Any] | None:
    """Serialize retrieval config for project run logs."""
    if config is None:
        return None
    return {
        "mode": config.mode,
        "top_k": config.top_k,
        "candidate_k": config.candidate_k,
        "must_any": config.must_any,
        "exclude": config.exclude,
        "source_types": config.source_types,
        "min_keyword_score": config.min_keyword_score,
        "fusion_method": config.fusion_method,
        "keyword_weight": config.keyword_weight,
        "semantic_weight": config.semantic_weight,
        "embedding_model": config.embedding_model,
        "rrf_k": config.rrf_k,
        "semantic_candidate_k": config.semantic_candidate_k,
        "rerank_enabled": config.rerank_enabled,
        "rerank_provider": config.rerank_provider,
        "rerank_model": config.rerank_model,
        "rerank_top_n": config.rerank_top_n,
        "min_rerank_score": config.min_rerank_score,
    }


def serialize_evidence(evidence: Any) -> Dict[str, Any]:
    """Serialize evidence snippets for project run logs."""
    return {
        "source": evidence.source,
        "title": evidence.title,
        "content": evidence.content,
        "published_at": evidence.published_at,
        "url": evidence.url,
        "keyword_score": evidence.keyword_score,
        "semantic_score": evidence.semantic_score,
        "retrieval_score": evidence.retrieval_score,
        "retrieval_rank": evidence.retrieval_rank,
        "retrieval_method": evidence.retrieval_method,
        "rerank_score": evidence.rerank_score,
        "rerank_rank": evidence.rerank_rank,
        "rerank_reason": evidence.rerank_reason,
        "matched_terms": evidence.matched_terms,
    }
