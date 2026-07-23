"""
渲染衔接器 - 报告编译器第一阶段.

将 CompiledReport 转换为既有渲染层可消费的格式（SectionOutput / TableSpec /
ChartSpec），调用现有 reporting/projections 进行渲染。对应 deep-research-report.md
"渲染器" 技能。

关键：renderer 是编译器与现有渲染层的适配器，不修改 reporting/projections/ 下
任何文件。第二阶段会扩展 table_renderer / chart_renderer 从 facts store 渲染表格图表。
"""

from pathlib import Path
from typing import Any, Optional

from core.contracts import (
    ChartSpec,
    CompiledReport,
    FactCard,
    FactRecord,
    ReportRunLog,
    SectionOutput,
    TableSpec,
)
from core.observability import get_logger
from reporting.compiler.chart_renderer import ChartRenderer
from reporting.compiler.table_renderer import TableRenderer

logger = get_logger(__name__)


class Renderer:
    """渲染衔接器.

    把 CompiledReport 适配为 SectionOutput 列表，并委托现有 projection 渲染。
    """

    def __init__(
        self,
        table_renderer: Optional[TableRenderer] = None,
        chart_renderer: Optional[ChartRenderer] = None,
    ):
        self._table_renderer = table_renderer or TableRenderer()
        self._chart_renderer = chart_renderer or ChartRenderer()

    def to_section_outputs(
        self,
        report: CompiledReport,
        validation_results: Optional[dict[str, Any]] = None,
    ) -> list[SectionOutput]:
        """把 CompiledReport 的章节转为 SectionOutput 列表.

        Args:
            report: 编译后的报告
            validation_results: critic 产出的校验结果（section_id -> ValidationResults）

        Returns:
            既有渲染层可消费的 SectionOutput 列表
        """
        facts_by_id = {f.fact_id: f for f in report.facts}
        outputs: list[SectionOutput] = []

        for section in report.sections:
            fact_records = [facts_by_id[fid] for fid in section.fact_ids if fid in facts_by_id]
            fact_card = self._build_fact_card(fact_records)
            evidence_refs = [c.display_text for c in section.citations]
            val_results = validation_results.get(section.section_id) if validation_results else None

            outputs.append(
                SectionOutput(
                    key=section.section_id,
                    title=section.title,
                    content=section.content,
                    evidence_refs=evidence_refs,
                    warnings=[],
                    fact_card=fact_card,
                    validation_results=val_results,
                    compiled_section=section,
                    citations=section.citations,
                )
            )
        return outputs

    def render_tables(self, report: CompiledReport) -> list[TableSpec]:
        """从 facts store 渲染指标表格（第二阶段：表格数字必须来自 facts）.

        以报告级 facts 表为输入，产出一张聚合指标表。未来可按 section 细分。
        """
        table = self._table_renderer.render(report.facts)
        return [table] if table is not None else []

    def render_charts(self, report: CompiledReport) -> list[ChartSpec]:
        """从 facts store 渲染图表（第二阶段：图值必须来自 facts）."""
        chart = self._chart_renderer.render(report.facts)
        return [chart] if chart is not None else []

    def _build_fact_card(self, facts: list[FactRecord]) -> Optional[FactCard]:
        """从 FactRecord 列表构建向后兼容的 FactCard."""
        if not facts:
            return None
        return FactCard(
            key_changes=[f.claim_text for f in facts if f.claim_type.value == "event"],
            drivers=[f.claim_text for f in facts if f.claim_type.value == "metric"],
            impacts=[],
            watch_points=[],
            risks=[f.claim_text for f in facts if f.claim_type.value == "risk"],
            source_refs=[f.provenance.source_name for f in facts],
            fact_records=facts,
            provenance_summary=[f.provenance for f in facts],
        )

    def render_markdown(
        self,
        report: CompiledReport,
        output_path: Path | str,
        validation_results: Optional[dict[str, Any]] = None,
    ) -> Path:
        """渲染为 Markdown 文件（审稿版含引用表）."""
        from reporting.projections.markdown import MarkdownProjection

        sections = self.to_section_outputs(report, validation_results)
        metadata = {
            "compiler_version": report.compiler_version,
            "facts_count": len(report.facts),
            "thesis": report.outline.thesis,
        }
        # 追加审稿版引用表
        sections_with_refs = self._append_citation_table(report, sections)
        MarkdownProjection().save(
            output_path=output_path,
            title=report.outline.report_title,
            sections=sections_with_refs,
            metadata=metadata,
        )
        logger.info(f"Rendered Markdown report to: {output_path}")
        return Path(output_path)

    def _append_citation_table(
        self,
        report: CompiledReport,
        sections: list[SectionOutput],
    ) -> list[SectionOutput]:
        """追加一个'参考文献'章节，列出所有引用（审稿版）."""
        if not any(s.citations for s in sections):
            return sections
        citation_lines: list[str] = []
        seen: set[str] = set()
        for section in sections:
            for cit in section.citations:
                if cit.display_text not in seen:
                    seen.add(cit.display_text)
                    citation_lines.append(f"- {cit.display_text}")
        ref_content = "\n".join(citation_lines) if citation_lines else "（无引用）"
        sections.append(
            SectionOutput(
                key="references",
                title="参考文献",
                content=ref_content,
                evidence_refs=[],
            )
        )
        return sections

    def build_run_log(
        self,
        report: CompiledReport,
        task_id: str,
        template_name: str,
    ) -> ReportRunLog:
        """构建运行日志（含 compiler_version 与 outline）."""
        return ReportRunLog(
            task_id=task_id,
            template_name=template_name,
            sections_log={
                s.section_id: {
                    "title": s.title,
                    "facts_used": len(s.fact_ids),
                    "citations": len(s.citations),
                }
                for s in report.sections
            },
            sources_used=list(
                {f.provenance.source_name for f in report.facts if f.provenance.source_name}
            ),
            compiler_version=report.compiler_version,
            outline=report.outline.model_dump(),
        )
