"""Report project render orchestration.

This module owns one report-project run: placeholder generation, template
projection, deterministic tables/charts, and run-log assembly.

v2 (config-driven): When config/report_config.yaml exists, uses
ConfigDrivenTemplateRenderer for rich-text injection and chart grids.
v1 (legacy): Falls back to WordProjection.save_from_template() with flat
placeholder replacement.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List

import yaml

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
        # ── v2 配置检测 ──
        # report_config.yaml 可能由前端配置编辑器生成，格式不一定是 v2。
        # v2 格式的顶层必须包含 meta / template / placeholders 字段；
        # 缺少这些字段说明是中间格式，应回退到 v1 路径。
        v2_config_path = project.project_dir / "config" / "report_config.yaml"
        if v2_config_path.exists():
            try:
                config_data = yaml.safe_load(v2_config_path.read_text(encoding="utf-8"))
                if isinstance(config_data, dict) and "meta" in config_data and "template" in config_data:
                    logger.info(
                        "检测到 v2 配置，使用 ConfigDrivenTemplateRenderer",
                        path=str(v2_config_path),
                    )
                    return self._execute_word_v2(
                        project=project,
                        v2_config_path=v2_config_path,
                        request=request,
                        generation_scope=generation_scope,
                    )
                else:
                    logger.info(
                        "report_config.yaml 存在但不是 v2 格式（缺少 meta/template），使用 v1 路径",
                        path=str(v2_config_path),
                    )
            except Exception:
                logger.warning(
                    "无法解析 report_config.yaml 为 v2 格式，回退到 v1 路径",
                    path=str(v2_config_path),
                    exc_info=True,
                )

        # ── v1 路径（原逻辑，完全不变）──
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

    def _execute_word_v2(
        self,
        *,
        project: ReportProject,
        v2_config_path: Path,
        request: ReportProjectRunRequest,
        generation_scope: Any,
    ) -> ReportProjectRunResult:
        """使用 v2 ConfigDrivenTemplateRenderer 执行 Word 报告渲染.

        Args:
            project: 报告项目.
            v2_config_path: report_config.yaml 路径.
            request: 渲染请求.
            generation_scope: 生成范围.

        Returns:
            渲染结果.
        """
        from core.contracts.reporting import ReportTemplateConfig
        from reporting.rendering.template_renderer import ConfigDrivenTemplateRenderer

        # 加载 v2 配置
        config_data = yaml.safe_load(v2_config_path.read_text(encoding="utf-8"))
        v2_config = ReportTemplateConfig(**config_data)
        logger.info("v2 配置已加载", config_name=v2_config.meta.name, version=v2_config.meta.version)

        # 读取 prompt 模板（与 v1 共享）
        prompt_templates_source = ""
        if project.prompt_templates_path and project.prompt_templates_path.exists():
            prompt_templates_source = project.prompt_templates_path.read_text(encoding="utf-8")

        # 为 evidence_grounded 类型的占位符预生成内容
        # 使用现有 generation_service（与 v1 共享）
        generated_texts: Dict[str, str] = {}
        generation_warnings: List[str] = []
        generated_count = 0
        evidence_total = 0

        for key, placeholder in v2_config.placeholders.items():
            if placeholder.generation_mode.value in ("evidence_grounded", "llm_direct"):
                try:
                    # 委托给现有 generation_service
                    gen_scope = resolve_report_generation_scope(
                        {
                            "defaults": {
                                "report_period": {"mode": "current_week", "lookback_days": 7}
                            }
                        },
                        report_date=request.report_date,
                        lookback_days=request.lookback_days,
                    )
                    # 通过 generation_service 的单占位符接口生成
                    result_text = self._generate_single_placeholder(
                        project=project,
                        key=key,
                        placeholder=placeholder,
                        generation_scope=gen_scope,
                        prompt_templates_source=prompt_templates_source,
                        defaults=v2_config.defaults,
                    )
                    generated_texts[key] = result_text or ""
                    if result_text:
                        generated_count += 1
                except Exception:
                    logger.exception("v2 占位符生成失败", extra={"key": key})
                    generation_warnings.append(f"{key}: 生成失败")
                    generated_texts[key] = ""

        # 使用 ConfigDrivenTemplateRenderer 渲染
        renderer = ConfigDrivenTemplateRenderer(
            config=v2_config,
            generation_service=self.generation_service,
            chart_service=self.chart_service,
            project_dir=project.project_dir,
        )

        generated_at = datetime.now()
        file_name = self._artifact_file_name(project, generated_at, ".docx")
        output_path = project.output_dir / file_name

        renderer.render(
            output_path=output_path,
            extra_context={
                "generated_texts": generated_texts,
                "generated_count": generated_count,
                "evidence_count": evidence_total,
                "report_date": request.report_date or generated_at.strftime("%Y%m%d"),
                "report_period_start": (
                    generation_scope.report_period.start_date
                    if hasattr(generation_scope, "report_period")
                    else None
                ),
                "report_period_end": (
                    generation_scope.report_period.end_date
                    if hasattr(generation_scope, "report_period")
                    else None
                ),
            },
        )

        # 写入运行日志
        run_record = {
            "config_version": "2.0",
            "project_name": project.name,
            "slug": project.slug,
            "v2_config_path": str(v2_config_path),
            "output_path": str(output_path),
            "generated_at": generated_at.isoformat(),
            "placeholder_count": len(v2_config.placeholders),
            "generated_count": generated_count,
            "report_date": request.report_date,
            "warnings": generation_warnings,
        }
        run_path = self._write_run_record(project, generated_at, run_record)

        logger.info(
            "Rendered v2 report project",
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
            generated_placeholder_count=generated_count,
            evidence_count=evidence_total,
            warnings=generation_warnings,
        )

    def _generate_single_placeholder(
        self,
        *,
        project: ReportProject,
        key: str,
        placeholder: Any,
        generation_scope: Any,
        prompt_templates_source: str = "",
        defaults: Any = None,
    ) -> str:
        """为单个 v2 EnhancedPlaceholder 生成内容.

        委托给 generation_service（复用现有 evidence retrieval + LLM 管道）。

        Args:
            project: 报告项目.
            key: 占位符 key.
            placeholder: EnhancedPlaceholder 实例.
            generation_scope: 生成范围.
            prompt_templates_source: prompt_templates.md 原始内容.
            defaults: v2 DefaultSettings.

        Returns:
            生成的文本内容.
        """
        if self.generation_service is None:
            return ""

        try:
            # 通过 generation_service 的通用接口生成
            result = self.generation_service.generate_placeholder_content(  # type: ignore[union-attr]
                key=key,
                title=placeholder.title or key,
                gen_config=placeholder.generation_config,
                defaults=defaults,
                context={
                    "report_date": (
                        generation_scope.report_date
                        if hasattr(generation_scope, "report_date")
                        else None
                    ),
                    "lookback_days": (
                        generation_scope.lookback_days
                        if hasattr(generation_scope, "lookback_days")
                        else 7
                    ),
                },
                project=project,
                prompt_templates_source=prompt_templates_source,
            )
            return result or ""
        except AttributeError:
            # generation_service 可能还没有 generate_placeholder_content 方法
            # fallback: 尝试通过 generate_placeholders 调用
            logger.warning(
                "generation_service 缺少 generate_placeholder_content，使用占位文本",
                extra={"key": key},
            )
            return f"[{placeholder.title or key} — 待生成]"
        except Exception:
            logger.exception("单占位符生成失败", extra={"key": key})
            return ""

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
            f"PPT 占位符未配置：{placeholder}"
            for placeholder in projection_result.missing_placeholders
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
            "prompt_templates_path": (
                str(project.prompt_templates_path) if project.prompt_templates_path else None
            ),
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
            "prompt_templates_path": (
                str(project.prompt_templates_path) if project.prompt_templates_path else None
            ),
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
        timestamp = generated_at.strftime("%Y%m%d")
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
