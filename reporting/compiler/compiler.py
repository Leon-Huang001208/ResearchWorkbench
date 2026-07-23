"""
报告编译器主编排器 - 报告编译器第一阶段.

ReportCompiler 是 AlphaFoundry "outline-first + evidence-first" 报告编译器的统一入口。
对应 deep-research-report.md 的 mermaid 流水线图：

    用户需求 → 任务分解器 → 来源规划器 → 证据检索器 → 事实抽取与归一化
    → 大纲规划器 → 分节写作器 → 引用绑定器 → 批判器 → 渲染器

设计原则：研究规划与章节写作可以 agent 化；事实抽取、表格生成、引用绑定、
质量检查则尽量结构化。所有进入正文/表格/图表的数字与结论，必须先落到 FactRecord。
"""

from typing import Optional

from core.contracts import (
    CompiledReport,
    CritiqueReport,
    CritiqueSeverity,
    ReportTask,
)
from core.interfaces import ModelGateway
from core.observability import get_logger
from core.utils.id_gen import generate_id
from reporting.compiler.citation_binder import CitationBinder
from reporting.compiler.citation_verifier import CitationVerifier
from reporting.compiler.critic import Critic
from reporting.compiler.evidence_retriever import EvidenceRetriever, EvidenceRetrieverProtocol
from reporting.compiler.fact_extractor import FactExtractor
from reporting.compiler.numeric_checker import NumericChecker
from reporting.compiler.outline_planner import OutlinePlanner
from reporting.compiler.renderer import Renderer
from reporting.compiler.revision_pass import RevisionPass
from reporting.compiler.section_writer import SectionWriter
from reporting.compiler.source_planner import SourcePlanner
from reporting.compiler.task_decomposer import TaskDecomposer

logger = get_logger(__name__)


class ReportCompiler:
    """报告编译器 - 统一入口.

    串联任务分解→来源规划→检索→事实抽取→大纲→分节写作→引用绑定→批判→渲染。
    """

    def __init__(
        self,
        model_gateway: Optional[ModelGateway] = None,
        evidence_retriever: Optional[EvidenceRetrieverProtocol] = None,
        forbidden_terms: Optional[list[str]] = None,
        auto_grader=None,
    ):
        """初始化编译器.

        Args:
            model_gateway: 模型网关，用于 LLM 调用（任务分解/事实抽取/大纲/写作）
            evidence_retriever: 证据检索后端，实现 EvidenceRetrieverProtocol
            forbidden_terms: 批判器禁用词列表
            auto_grader: 可选的 AutoGrader，启用 Step 10.5 评测
        """
        self.model_gateway = model_gateway
        self.task_decomposer = TaskDecomposer(model_gateway)
        self.source_planner = SourcePlanner()
        self.evidence_retriever = EvidenceRetriever(evidence_retriever)
        self.fact_extractor = FactExtractor(model_gateway)
        self.outline_planner = OutlinePlanner(model_gateway)
        self.section_writer = SectionWriter(model_gateway)
        self.citation_binder = CitationBinder()
        self.critic = Critic(forbidden_terms)
        self.revision_pass = RevisionPass()
        self.citation_verifier = CitationVerifier()
        self.numeric_checker = NumericChecker()
        self.renderer = Renderer()
        self.auto_grader = auto_grader  # Phase 3.3: 可选评测

    # 编译器版本（第三阶段升级为 2.0）
    VERSION = "2.0"

    def compile(self, task: ReportTask) -> CompiledReport:
        """编译报告 - 完整 10 步流水线（含 revision 循环）.

        第三阶段新增：批判后若 severity ∈ {MAJOR, CRITICAL}，自动触发
        revision_pass → 重新绑定引用 → 重新批判，最多 2 轮。

        Args:
            task: 报告生成任务

        Returns:
            CompiledReport：含大纲、章节、事实表、运行日志
        """
        logger.info(
            "Report compilation started",
            task_id=task.task_id,
            template=task.template_name,
        )

        # 1. 任务分解
        research_plan = self.task_decomposer.decompose(task)

        # 2. 来源规划
        source_plan = self.source_planner.plan(research_plan)

        # 3. 证据检索
        evidence_packages = self.evidence_retriever.retrieve_evidence(source_plan.queries)

        # 4. 事实抽取与归一化
        facts = self.fact_extractor.extract(evidence_packages)

        # 5. 大纲规划
        outline = self.outline_planner.plan(facts, task)

        # 6. 分节写作
        sections = self.section_writer.write(outline, facts)

        # 7. 引用绑定
        sections = self.citation_binder.bind(sections, facts)

        # 8. 批判 + 修订循环（第三阶段）
        sections, final_critique = self._critic_revision_loop(sections, facts, outline)

        # 8.5 引用验证 + 数字检查（第三阶段 3.2）
        citation_issues = self.citation_verifier.verify(sections, facts)
        numeric_issues = self.numeric_checker.check(sections, facts)
        logger.info(
            "Phase 3.2 verification complete",
            citation_issues=len(citation_issues),
            numeric_issues=len(numeric_issues),
            total_verifier_issues=len(citation_issues) + len(numeric_issues),
        )

        # 9. 挂载校验结果（向后兼容旧 ValidationResults 格式）
        legacy_validation = self.critic.review(sections, facts)
        sections = self._attach_validation(sections, legacy_validation)

        # 10. 组装 CompiledReport
        report = CompiledReport(
            report_id=generate_id(),
            outline=outline,
            sections=sections,
            facts=facts,
            compiler_version=self.VERSION,
        )

        # 10.5 评测（第三阶段 3.3，可选）
        if self.auto_grader is not None:
            try:
                evaluation = self.auto_grader.grade(
                    report,
                    critique=final_critique,
                    precomputed_citation_issues=citation_issues,
                    precomputed_numeric_issues=numeric_issues,
                )
                logger.info(
                    "Phase 3.3 evaluation complete",
                    overall=evaluation.overall_score,
                    grade=evaluation.grade,
                    claims=len(evaluation.claims),
                )
            except Exception:
                logger.warning(
                    "Phase 3.3 evaluation failed (non-fatal)",
                    exc_info=True,
                )

        logger.info(
            "Report compilation complete",
            report_id=report.report_id,
            sections=len(sections),
            facts=len(facts),
            tier_a_b_ratio=source_plan.tier_a_b_ratio(),
            critic_rounds=(
                final_critique.metrics.get("revision_rounds", 1) if final_critique else 1
            ),
        )
        return report

    def _critic_revision_loop(
        self,
        sections: list,
        facts: list,
        outline,
    ) -> tuple[list, Optional["CritiqueReport"]]:
        """批判 → 修订 → 重新批判循环（最多 2 轮）.

        Returns:
            (最终 sections, 最终 CritiqueReport)
        """
        current_sections = sections
        final_critique: Optional[CritiqueReport] = None

        for round_num in range(1, self.revision_pass.MAX_ROUNDS + 1):
            # 先重新绑定引用（修订可能插入新 fact_id 标记）
            if round_num > 1:
                current_sections = self.citation_binder.bind(current_sections, facts)

            critique = self.critic.review_full(current_sections, facts, outline)

            if critique.overall_severity in (
                CritiqueSeverity.PASS,
                CritiqueSeverity.MINOR,
            ):
                logger.info(
                    "Critic revision converged",
                    round=round_num,
                    severity=critique.overall_severity.value,
                )
                critique.metrics["revision_rounds"] = round_num
                final_critique = critique
                break

            # 需要修订
            logger.info(
                "Critic found issues, triggering revision",
                round=round_num,
                severity=critique.overall_severity.value,
                issues=len(critique.issues),
            )
            result = self.revision_pass.revise(
                current_sections, critique, facts, outline, round_num
            )
            current_sections = result.sections
            critique.metrics["revision_rounds"] = round_num
            final_critique = critique

            if result.converged:
                logger.info(
                    "Revision converged after fixes",
                    round=round_num,
                    fixed=len(result.fixed_issue_ids),
                )
                break

        return current_sections, final_critique

    def _attach_validation(self, sections, validation_results):
        """把 critic 结果挂到各 section."""
        from core.contracts import CompiledSection

        updated: list[CompiledSection] = []
        for section in sections:
            val = validation_results.get(section.section_id)
            updated.append(
                section.model_copy(update={"validation_result": val}) if val else section
            )
        return updated
