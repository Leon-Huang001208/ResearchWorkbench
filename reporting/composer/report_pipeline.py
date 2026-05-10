"""
报告生成流水线 - 完整的端到端报告生成.

Report pipeline orchestrates the complete end-to-end report generation:
1. Report task initialization
2. Section planning
3. Evidence retrieval (by section)
4. Fact card building
5. Paragraph generation
6. Validation
7. Output rendering
"""
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.contracts import (
    ChartSpec,
    EvidencePackage,
    FactCard,
    ReportRunLog,
    ReportTask,
    SectionOutput,
    SectionSpec,
    TableSpec,
)
from core.interfaces import ModelGateway
from core.observability import get_logger
from core.services.rag_retrieval import RAGRetrievalService
from reporting.composer.fact_card_builder import FactCardBuilder
from reporting.composer.validator import ReportValidator
from reporting.projections.excel import ExcelProjection
from reporting.projections.markdown import MarkdownProjection
from reporting.projections.word import WordProjection
from reporting.templates.template_manager import TemplateManager

logger = get_logger(__name__)


class ReportPipeline:
    """报告生成流水线.

    Orchestrates complete report generation from template to output.
    """

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        template_manager: Optional[TemplateManager] = None,
        retrieval_service: Optional[RAGRetrievalService] = None,
    ):
        """初始化报告生成流水线.

        Args:
            model_gateway: Model gateway for LLM calls.
            template_manager: Template manager for loading templates.
            retrieval_service: RAG retrieval service for evidence.
        """
        self.model_gateway = model_gateway
        self.template_manager = template_manager or TemplateManager()
        self.retrieval_service = retrieval_service
        self.fact_card_builder = FactCardBuilder(model_gateway)
        self.validator = ReportValidator()

    def create_report_task(
        self,
        template_name: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ReportTask:
        """创建报告任务.

        Args:
            template_name: Name of the template to use.
            context: Context data for the report.

        Returns:
            Created ReportTask.
        """
        from core.utils.id_gen import generate_id

        task = ReportTask(
            task_id=generate_id(),
            template_name=template_name,
            context=context or {},
            status="pending",
        )

        logger.info(f"Created report task: {task.task_id}, template: {template_name}")
        return task

    def generate_report(
        self,
        task: ReportTask,
        evidence_packages: Optional[Dict[str, EvidencePackage]] = None,
    ) -> List[SectionOutput]:
        """生成报告.

        Args:
            task: Report task.
            evidence_packages: Optional pre-retrieved evidence by section key.

        Returns:
            List of section outputs.
        """
        logger.info(f"Starting report generation: {task.task_id}")
        task.status = "running"
        task.started_at = datetime.utcnow()

        try:
            # Load template
            template = self.template_manager.load_template(task.template_name)

            # Generate each section
            sections = []
            evidence_packages = evidence_packages or {}

            for section_spec in template.sections:
                section_output = self._generate_section(
                    section_spec,
                    task.context,
                    evidence_packages.get(section_spec.key),
                )
                sections.append(section_output)

            task.status = "completed"
            task.completed_at = datetime.utcnow()

            logger.info(f"Report generation completed: {task.task_id}, sections: {len(sections)}")
            return sections

        except Exception as e:
            task.status = "failed"
            task.error_message = str(e)
            logger.error(f"Report generation failed: {task.task_id}, error: {e}", exc_info=True)
            raise

    def _generate_section(
        self,
        spec: SectionSpec,
        context: Dict[str, Any],
        evidence_package: Optional[EvidencePackage] = None,
    ) -> SectionOutput:
        """生成单个段落.

        Args:
            spec: Section specification.
            context: Report context.
            evidence_package: Optional pre-retrieved evidence.

        Returns:
            Section output.
        """
        logger.info(f"Generating section: {spec.key}")

        # Step 1: Retrieve evidence if needed and not provided
        evidence_dicts = []
        if evidence_package:
            for doc in evidence_package.documents:
                evidence_dicts.append(
                    {
                        "source": f"{doc.doc_type.value} - {doc.source_name or 'Unknown'}",
                        "content": doc.summary or doc.title or "",
                    }
                )
        elif self.retrieval_service and spec.retrieval_profile:
            evidence_package = self._retrieve_evidence_for_section(spec, context)
            for doc in evidence_package.documents:
                evidence_dicts.append(
                    {
                        "source": f"{doc.doc_type.value} - {doc.source_name or 'Unknown'}",
                        "content": doc.summary or doc.title or "",
                    }
                )

        # Step 2: Build fact card
        fact_card = self.fact_card_builder.build_fact_card(
            evidence_dicts,
            {"section_key": spec.key, "section_title": spec.title, **context},
        )

        # Step 3: Generate paragraph content
        content = self._generate_paragraph_from_fact_card(spec, fact_card, context)

        # Step 4: Validate
        validation_results = self.validator.validate_section(
            content,
            spec,
            [str(i) for i in range(1, len(evidence_dicts) + 1)],
        )

        # Build warnings
        warnings = []
        for r in validation_results.results:
            if not r.passed:
                warnings.append(f"{r.check_name}: {r.message}")

        # Create output
        output = SectionOutput(
            key=spec.key,
            title=spec.title,
            content=content,
            evidence_refs=[str(i) for i in range(1, len(evidence_dicts) + 1)],
            scenario_refs=[],
            warnings=warnings,
            fact_card=fact_card,
            validation_results=validation_results,
        )

        logger.info(f"Section generated: {spec.key}, passed: {validation_results.overall_passed}")
        return output

    def _retrieve_evidence_for_section(
        self,
        spec: SectionSpec,
        context: Dict[str, Any],
    ) -> EvidencePackage:
        """为段落检索证据.

        Args:
            spec: Section specification.
            context: Report context.

        Returns:
            Retrieved evidence package.
        """
        from core.contracts import RetrievalQuery

        if not self.retrieval_service:
            return EvidencePackage(
                query=RetrievalQuery(query_text=""),
                profile_used=None,
                total_documents_found=0,
                total_chunks_found=0,
                documents=[],
                source_distribution={},
                industry_distribution={},
            )

        # Build query from context and section title
        query_text = context.get("query", spec.title)
        retrieval_profile = spec.retrieval_profile

        query = RetrievalQuery(
            query_text=query_text,
            profile_type=retrieval_profile,
        )

        evidence = self.retrieval_service.retrieve(query)
        logger.info(f"Retrieved {evidence.total_documents_found} documents for section: {spec.key}")
        return evidence

    def _generate_paragraph_from_fact_card(
        self,
        spec: SectionSpec,
        fact_card: FactCard,
        context: Dict[str, Any],
    ) -> str:
        """从 Fact Card 生成段落.

        Args:
            spec: Section specification.
            fact_card: Fact card with extracted facts.
            context: Report context.

        Returns:
            Generated paragraph content.
        """
        # If no model gateway, use simple template-based generation
        if not self.model_gateway:
            return self._generate_paragraph_simple(spec, fact_card)

        # Use LLM for generation
        prompt = self._build_paragraph_generation_prompt(spec, fact_card, context)

        try:
            response = self.model_gateway.chat(
                messages=[{"role": "user", "content": prompt}],
                model="default",
                temperature=0.7,
            )
            return response.content.strip()
        except Exception as e:
            logger.error(
                f"LLM paragraph generation failed: {e}, falling back to simple", exc_info=True
            )
            return self._generate_paragraph_simple(spec, fact_card)

    def _generate_paragraph_simple(self, spec: SectionSpec, fact_card: FactCard) -> str:
        """简单的段落生成（不使用 LLM）.

        Args:
            spec: Section specification.
            fact_card: Fact card with extracted facts.

        Returns:
            Generated paragraph content.
        """
        parts = [f"## {spec.title}\n"]

        if fact_card.key_changes:
            parts.append("### 关键变化\n")
            for change in fact_card.key_changes:
                parts.append(f"- {change}\n")

        if fact_card.drivers:
            parts.append("\n### 驱动因素\n")
            for driver in fact_card.drivers:
                parts.append(f"- {driver}\n")

        if fact_card.impacts:
            parts.append("\n### 影响分析\n")
            for impact in fact_card.impacts:
                parts.append(f"- {impact}\n")

        if fact_card.risks:
            parts.append("\n### 风险提示\n")
            for risk in fact_card.risks:
                parts.append(f"- {risk}\n")

        return "".join(parts)

    def _build_paragraph_generation_prompt(
        self,
        spec: SectionSpec,
        fact_card: FactCard,
        context: Dict[str, Any],
    ) -> str:
        """构建段落生成提示词.

        Args:
            spec: Section specification.
            fact_card: Fact card with extracted facts.
            context: Report context.

        Returns:
            Prompt string.
        """
        prompt_parts = [
            f"# 段落生成: {spec.title}",
            "",
            f"请生成一段约 {spec.target_words} 字的报告内容。",
            "",
            "## 参考事实：",
        ]

        if fact_card.key_changes:
            prompt_parts.append("### 关键变化")
            for change in fact_card.key_changes:
                prompt_parts.append(f"- {change}")

        if fact_card.drivers:
            prompt_parts.append("\n### 驱动因素")
            for driver in fact_card.drivers:
                prompt_parts.append(f"- {driver}")

        if fact_card.impacts:
            prompt_parts.append("\n### 影响分析")
            for impact in fact_card.impacts:
                prompt_parts.append(f"- {impact}")

        if fact_card.risks:
            prompt_parts.append("\n### 风险提示")
            for risk in fact_card.risks:
                prompt_parts.append(f"- {risk}")

        if spec.required_facets:
            prompt_parts.append("\n## 必须覆盖的方面")
            for facet in spec.required_facets:
                prompt_parts.append(f"- {facet}")

        if spec.structure:
            prompt_parts.append(f"\n## 结构要求\n{spec.structure}")

        prompt_parts.append("\n## 输出要求")
        prompt_parts.append("- 请只返回段落内容，不要包含标题")
        prompt_parts.append("- 内容要专业、客观、逻辑清晰")

        if spec.evidence_policy == "strict":
            prompt_parts.append("- 只基于提供的事实，不要编造信息")

        return "\n".join(prompt_parts)

    def save_report(
        self,
        output_path: Path | str,
        title: str,
        sections: List[SectionOutput],
        task: Optional[ReportTask] = None,
        tables: Optional[List[TableSpec]] = None,
        charts: Optional[List[ChartSpec]] = None,
    ):
        """保存报告.

        Args:
            output_path: Output file path.
            title: Report title.
            sections: List of section outputs.
            task: Optional report task for metadata.
            tables: Optional table specifications.
            charts: Optional chart specifications.
        """
        output_path = Path(output_path)
        suffix = output_path.suffix.lower()

        metadata = {}
        if task:
            metadata = {
                "任务ID": task.task_id,
                "模板": task.template_name,
                "创建时间": task.created_at.strftime("%Y-%m-%d %H:%M:%S") if task.created_at else "",
            }

        if suffix == ".md":
            projection = MarkdownProjection()
            projection.save(output_path, title, sections, metadata)
        elif suffix == ".docx":
            # Try to load template and use it
            template = None
            try:
                if task:
                    template = self.template_manager.load_template(task.template_name)
            except Exception:
                pass

            if template and template.word_template_path:
                # Use template
                projection = WordProjection()
                projection.save_from_template(
                    output_path,
                    template.word_template_path,
                    sections,
                    template.placeholders,
                    tables,
                )
            else:
                # Simple save
                projection = WordProjection()
                projection.save(output_path, title, sections, metadata)
        elif suffix == ".xlsx":
            projection = ExcelProjection()
            projection.save(output_path, title, tables, charts, metadata)
        else:
            raise ValueError(f"Unsupported output format: {suffix}")

    def create_run_log(
        self,
        task: ReportTask,
        sections: List[SectionOutput],
    ) -> ReportRunLog:
        """创建运行日志.

        Args:
            task: Report task.
            sections: Generated sections.

        Returns:
            Report run log.
        """
        sections_log = {}
        sources_used = []

        for section in sections:
            log_entry = {
                "key": section.key,
                "warnings": section.warnings,
                "num_evidence_refs": len(section.evidence_refs),
            }
            if section.validation_results:
                log_entry["validation_passed"] = section.validation_results.overall_passed
                log_entry["word_count"] = section.validation_results.word_count
            sections_log[section.key] = log_entry
            sources_used.extend(section.evidence_refs)

        return ReportRunLog(
            task_id=task.task_id,
            template_name=task.template_name,
            sections_log=sections_log,
            sources_used=sources_used,
        )

    def generate_and_save(
        self,
        template_name: str,
        output_path: Path | str,
        title: str,
        context: Optional[Dict[str, Any]] = None,
        tables: Optional[List[TableSpec]] = None,
        charts: Optional[List[ChartSpec]] = None,
    ) -> Tuple[List[SectionOutput], ReportRunLog]:
        """生成并保存报告（一站式）.

        Args:
            template_name: Name of the template to use.
            output_path: Output file path.
            title: Report title.
            context: Optional report context.
            tables: Optional table specifications.
            charts: Optional chart specifications.

        Returns:
            Tuple of (section outputs, run log).
        """
        # Create task
        task = self.create_report_task(template_name, context)

        # Generate report
        sections = self.generate_report(task)

        # Save
        self.save_report(output_path, title, sections, task, tables, charts)

        # Create log
        run_log = self.create_run_log(task, sections)

        return sections, run_log
