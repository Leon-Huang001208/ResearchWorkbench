"""
指标计算器 - 报告编译器第三阶段 3.3.

从 CompiledReport + critic/verifier 输出计算五维度 ReportMetrics，
加权聚合为综合评分与等级。所有计算纯规则驱动，不调用 LLM。
"""

from core.contracts import (
    CompiledReport,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    ReportMetrics,
    SourceTier,
)
from core.observability import get_logger

logger = get_logger(__name__)

# 默认维度权重
DEFAULT_WEIGHTS: dict[str, float] = {
    "retrieval": 0.15,
    "fact": 0.35,
    "citation": 0.25,
    "report": 0.15,
    "efficiency": 0.10,
}

# 等级阈值
GRADE_THRESHOLDS: list[tuple[float, str]] = [
    (85.0, "A"),
    (70.0, "B"),
    (55.0, "C"),
    (40.0, "D"),
]


class MetricsComputer:
    """指标计算器 — 聚合所有编译器产出为 ReportMetrics.

    构造函数接受可选权重，允许按场景调参。
    """

    def __init__(self, weights: dict[str, float] | None = None):
        self.weights = weights or dict(DEFAULT_WEIGHTS)

    # ── Public API ──────────────────────────────────────────────────────

    def compute(
        self,
        report: CompiledReport,
        critique: CritiqueReport | None = None,
        citation_issues: list[CritiqueIssue] | None = None,
        numeric_issues: list[CritiqueIssue] | None = None,
        compilation_time_ms: float = 0.0,
        tokens_used: int = 0,
    ) -> ReportMetrics:
        """计算完整 ReportMetrics.

        Args:
            report: 编译后的报告
            critique: 批判器输出（可选）
            citation_issues: CitationVerifier 产出（可选）
            numeric_issues: NumericChecker 产出（可选）
            compilation_time_ms: 编译耗时
            tokens_used: token 消耗

        Returns:
            ReportMetrics: 五维度指标
        """
        citation_issues = citation_issues or []
        numeric_issues = numeric_issues or []

        # 各维度独立计算
        retrieval = self._compute_retrieval(report)
        fact_quality = self._compute_fact_quality(report, critique, numeric_issues)
        citation_quality = self._compute_citation_quality(report, citation_issues)
        report_quality = self._compute_report_quality(report, critique)
        efficiency = self._compute_efficiency(compilation_time_ms, tokens_used, critique)

        # 加权综合
        overall = self._weighted_overall(
            retrieval, fact_quality, citation_quality, report_quality, efficiency
        )
        grade = self._to_grade(overall)

        metrics = ReportMetrics(
            source_tier_a_b_ratio=retrieval,
            total_evidence_chunks=len(report.facts),
            evidence_diversity=self._calc_evidence_diversity(report),
            total_facts=len(report.facts),
            claim_support_rate=fact_quality,
            fabricated_number_count=sum(
                1 for i in numeric_issues if i.category == CritiqueCategory.FABRICATED_NUMBER
            ),
            citation_coverage=citation_quality,
            orphan_citation_count=sum(
                1 for i in citation_issues if i.category == CritiqueCategory.ORPHAN_CITATION
            ),
            source_diversity_pct=self._calc_source_dominance(report),
            total_words=self._count_words(report),
            total_sections=len(report.sections),
            structure_score=report_quality,
            counterpoint_coverage=self._calc_counterpoint(report, critique),
            compilation_time_ms=compilation_time_ms,
            tokens_used=tokens_used,
            cost_estimate=tokens_used * 0.00001 if tokens_used else 0.0,
            revision_rounds=critique.metrics.get("revision_rounds", 0) if critique else 0,
            overall_score=overall,
            grade=grade,
        )
        logger.info("Metrics computed", overall=overall, grade=grade)
        return metrics

    @staticmethod
    def to_grade(score: float) -> str:
        """静态方法：分数 → 等级."""
        return MetricsComputer._to_grade(score)

    # ── 维度计算 ────────────────────────────────────────────────────────

    def _compute_retrieval(self, report: CompiledReport) -> float:
        """检索质量：Tier A+B 占比."""
        facts = report.facts
        if not facts:
            return 0.0
        tier_ab = sum(
            1 for f in facts if f.provenance.source_tier in (SourceTier.TIER_A, SourceTier.TIER_B)
        )
        return tier_ab / len(facts)

    def _compute_fact_quality(
        self,
        report: CompiledReport,
        critique: CritiqueReport | None,
        numeric_issues: list[CritiqueIssue],
    ) -> float:
        """事实质量：声明支撑率 × 0.6 + 安全支撑率 × 0.4."""
        # claim_support_rate 来自 critic
        support_rate = 1.0
        if critique and "claim_support_rate" in critique.metrics:
            support_rate = float(critique.metrics["claim_support_rate"])

        # safe_supported: 有数值的 fact 占比（可验证比例）
        facts = report.facts
        safe = sum(1 for f in facts if f.value is not None) / max(len(facts), 1)

        # 虚构数字惩罚
        fab_count = sum(
            1 for i in numeric_issues if i.category == CritiqueCategory.FABRICATED_NUMBER
        )
        if fab_count > 0:
            fab_penalty = max(0.0, 1.0 - fab_count / max(len(facts), 1))
            support_rate *= fab_penalty

        return support_rate * 0.6 + safe * 0.4

    def _compute_citation_quality(
        self,
        report: CompiledReport,
        citation_issues: list[CritiqueIssue],
    ) -> float:
        """引用品质：覆盖率 × 0.5 + (1-孤儿率) × 0.3 + (1-集中度) × 0.2."""
        total_facts = max(len(report.facts), 1)

        # 覆盖率
        cited: set[str] = set()
        for section in report.sections:
            for citation in section.citations:
                cited.update(citation.fact_ids)
        coverage = len(cited & {f.fact_id for f in report.facts}) / total_facts

        # 孤儿率
        orphan_count = sum(
            1 for i in citation_issues if i.category == CritiqueCategory.ORPHAN_CITATION
        )
        total_citations = max(sum(len(s.citations) for s in report.sections), 1)
        orphan_rate = orphan_count / total_citations

        # 来源集中度
        dominance = self._calc_source_dominance(report)

        return coverage * 0.5 + (1.0 - orphan_rate) * 0.3 + (1.0 - dominance) * 0.2

    def _compute_report_quality(
        self,
        report: CompiledReport,
        critique: CritiqueReport | None,
    ) -> float:
        """报告质量：结构评分."""
        structure = 1.0
        if critique and "structure_score" in critique.metrics:
            structure = float(critique.metrics["structure_score"])

        # 章节内容非空率
        non_empty = sum(1 for s in report.sections if s.content.strip()) / max(
            len(report.sections), 1
        )
        return structure * 0.5 + non_empty * 0.5

    @staticmethod
    def _compute_efficiency(
        compilation_time_ms: float,
        tokens_used: int,
        critique: CritiqueReport | None,
    ) -> float:
        """生产效率：归一化为 0-1 分数（越低越好）."""
        # 时间得分：<30s 满分, >300s 0分
        time_score = max(0.0, 1.0 - compilation_time_ms / 300_000.0) if compilation_time_ms else 0.5

        # token 得分：<10k 满分, >200k 0分
        token_score = max(0.0, 1.0 - tokens_used / 200_000.0) if tokens_used else 0.5

        # 修订轮数得分：1轮满分, >3轮 0分
        rounds = critique.metrics.get("revision_rounds", 1) if critique else 1
        round_score = max(0.0, 1.0 - (rounds - 1) / 3.0)

        return time_score * 0.3 + token_score * 0.3 + round_score * 0.4

    def _weighted_overall(
        self,
        retrieval: float,
        fact: float,
        citation: float,
        report: float,
        efficiency: float,
    ) -> float:
        """加权综合评分（0-100）."""
        raw = (
            self.weights.get("retrieval", 0.15) * retrieval
            + self.weights.get("fact", 0.35) * fact
            + self.weights.get("citation", 0.25) * citation
            + self.weights.get("report", 0.15) * report
            + self.weights.get("efficiency", 0.10) * efficiency
        )
        return min(100.0, max(0.0, raw * 100.0))

    # ── 辅助计算 ────────────────────────────────────────────────────────

    @staticmethod
    def _calc_evidence_diversity(report: CompiledReport) -> float:
        """证据多样性：去重来源数 / 总 fact 数."""
        facts = report.facts
        if not facts:
            return 0.0
        unique_sources = len({f.provenance.doc_id for f in facts})
        return unique_sources / len(facts)

    @staticmethod
    def _calc_source_dominance(report: CompiledReport) -> float:
        """来源集中度：最大单一来源占比."""
        from collections import Counter

        source_counts: Counter[str] = Counter()
        for section in report.sections:
            for citation in section.citations:
                # 用 display_text 中的来源名
                source_counts[citation.display_text] += 1
        total = sum(source_counts.values())
        if total == 0:
            return 0.0
        return source_counts.most_common(1)[0][1] / total

    @staticmethod
    def _calc_counterpoint(report: CompiledReport, critique: CritiqueReport | None) -> float:
        """反证覆盖率."""
        if critique and "counterpoint_coverage" in critique.metrics:
            return float(critique.metrics["counterpoint_coverage"])
        # 启发式：检查 outline 中是否有关键词
        counterpoint_sections = 0
        for section in report.outline.sections:
            title_lower = section.title.lower()
            if any(
                kw in title_lower for kw in ("risk", "风险", "counterpoint", "反证", "bear", "空")
            ):
                counterpoint_sections += 1
        total = max(len(report.outline.sections), 1)
        return min(1.0, counterpoint_sections / total + 0.3)  # base coverage

    @staticmethod
    def _count_words(report: CompiledReport) -> int:
        """粗略字数统计."""
        total = 0
        for section in report.sections:
            total += len(section.content)
        return total

    @staticmethod
    def _to_grade(score: float) -> str:
        """分数 → 等级."""
        for threshold, grade in GRADE_THRESHOLDS:
            if score >= threshold:
                return grade
        return "F"
