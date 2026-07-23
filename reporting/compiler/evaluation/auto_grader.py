"""
自动评分器 - 报告编译器第三阶段 3.3.

编排 ClaimExtractor → CitationVerifier → NumericChecker → MetricsComputer，
产出完整的 EvaluationReport。既可嵌入 compile() 流程，也可独立调用。
"""

from datetime import datetime

from core.contracts import (
    CompiledReport,
    CritiqueIssue,
    CritiqueReport,
    EvaluationReport,
)
from core.observability import get_logger
from reporting.compiler.citation_verifier import CitationVerifier
from reporting.compiler.evaluation.claim_extractor import ClaimExtractor
from reporting.compiler.evaluation.metrics import MetricsComputer
from reporting.compiler.numeric_checker import NumericChecker

logger = get_logger(__name__)


class AutoGrader:
    """自动评分器 — 评测管线的编排器.

    复用 CitationVerifier + NumericChecker + ClaimExtractor，
    通过 MetricsComputer 汇总为 EvaluationReport。
    """

    def __init__(
        self,
        model_gateway=None,
        metric_computer: MetricsComputer | None = None,
        citation_verifier: CitationVerifier | None = None,
        numeric_checker: NumericChecker | None = None,
    ):
        """初始化.

        Args:
            model_gateway: 可选的 ModelGateway，用于 claim_extractor 的 LLM 路径
            metric_computer: 可选的自定义 MetricsComputer
            citation_verifier: 可选的自定义 CitationVerifier
            numeric_checker: 可选的自定义 NumericChecker
        """
        self.metric_computer = metric_computer or MetricsComputer()
        self.claim_extractor = ClaimExtractor(model_gateway)
        self.citation_verifier = citation_verifier or CitationVerifier()
        self.numeric_checker = numeric_checker or NumericChecker()

    def grade(
        self,
        report: CompiledReport,
        critique: CritiqueReport | None = None,
        precomputed_citation_issues: list[CritiqueIssue] | None = None,
        precomputed_numeric_issues: list[CritiqueIssue] | None = None,
        compilation_time_ms: float = 0.0,
        tokens_used: int = 0,
    ) -> EvaluationReport:
        """对编译后的报告执行完整评测.

        Args:
            report: 编译后的报告
            critique: 批判器输出（可选，有则复用）
            precomputed_citation_issues: 预计算的引用问题（可选复用）
            precomputed_numeric_issues: 预计算的数字问题（可选复用）
            compilation_time_ms: 编译耗时
            tokens_used: token 消耗

        Returns:
            EvaluationReport: 完整评测报告
        """
        logger.info("AutoGrader starting", report_id=report.report_id)

        # 1. 抽取声明
        claims = self.claim_extractor.extract_from_report(report)

        # 2. 引用与数字验证（如未预计算）
        citation_issues = precomputed_citation_issues
        if citation_issues is None:
            citation_issues = self.citation_verifier.verify(report.sections, report.facts)

        numeric_issues = precomputed_numeric_issues
        if numeric_issues is None:
            numeric_issues = self.numeric_checker.check(report.sections, report.facts)

        # 3. 计算指标
        metrics = self.metric_computer.compute(
            report=report,
            critique=critique,
            citation_issues=citation_issues,
            numeric_issues=numeric_issues,
            compilation_time_ms=compilation_time_ms,
            tokens_used=tokens_used,
        )

        # 4. 合并所有 issues
        all_issues = list(citation_issues) + list(numeric_issues)
        if critique:
            all_issues.extend(critique.issues)

        # 5. 组装 EvaluationReport
        evaluation = EvaluationReport(
            report_id=report.report_id,
            metrics=metrics,
            claims=claims,
            critique_issues=all_issues,
            overall_score=metrics.overall_score,
            grade=metrics.grade,
            evaluated_at=datetime.utcnow(),
        )

        logger.info(
            "AutoGrader complete",
            report_id=report.report_id,
            overall=metrics.overall_score,
            grade=metrics.grade,
            claims=len(claims),
            issues=len(all_issues),
        )
        return evaluation
