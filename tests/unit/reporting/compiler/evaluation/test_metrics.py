"""Phase 3.3: test_metrics.py — MetricsComputer 测试."""

import pytest

from core.contracts import (
    Citation,
    ClaimType,
    CompiledReport,
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    FactRecord,
    Provenance,
    ReportOutline,
    SourceTier,
)
from reporting.compiler.evaluation.metrics import MetricsComputer


def _make_fact(
    fact_id: str = "f1",
    claim_text: str = "营收100亿元",
    value: float | None = 100.0,
    unit: str | None = "亿元",
    source_name: str = "巨潮资讯网",
    tier: SourceTier = SourceTier.TIER_A,
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim_text,
        claim_type=ClaimType.METRIC,
        value=value,
        unit=unit,
        provenance=Provenance(doc_id="d1", source_tier=tier, source_name=source_name),
        confidence=0.9,
    )


def _make_section(
    section_id: str = "s1",
    title: str = "营收分析",
    content: str = "公司营收100亿元[1]。",
    fact_ids: list[str] | None = None,
) -> CompiledSection:
    if fact_ids is None:
        fact_ids = ["f1"]
    citations = [
        Citation(
            citation_id=f"c{i + 1}",
            fact_ids=[fid],
            display_text=f"[{i + 1}] 来源",
        )
        for i, fid in enumerate(fact_ids)
    ]
    return CompiledSection(
        section_id=section_id,
        title=title,
        content=content,
        citations=citations,
        fact_ids=fact_ids,
    )


def _make_report(
    facts: list[FactRecord] | None = None,
    sections: list[CompiledSection] | None = None,
) -> CompiledReport:
    from core.contracts import OutlineSection

    if facts is None:
        facts = [_make_fact("f1")]
    if sections is None:
        sections = [_make_section("s1", fact_ids=["f1"])]

    outline = ReportOutline(
        report_title="测试报告",
        sections=[
            OutlineSection(section_id="s1", title="营收分析"),
        ],
    )
    return CompiledReport(
        report_id="test_r1",
        outline=outline,
        sections=sections,
        facts=facts,
    )


class TestMetricsComputer:
    """指标计算器测试."""

    def test_compute_all_dimensions_populated(self):
        """所有五维度指标均有非默认值."""
        report = _make_report()
        mc = MetricsComputer()
        metrics = mc.compute(report)

        assert metrics.total_facts == 1
        assert metrics.total_sections == 1
        assert metrics.total_words > 0
        assert metrics.grade != "N/A"
        assert 0.0 <= metrics.overall_score <= 100.0

    def test_source_tier_ratio_correct(self):
        """Tier A+B 占比计算正确."""
        f1 = _make_fact("f1", tier=SourceTier.TIER_A)
        f2 = _make_fact("f2", claim_text="毛利20亿", value=20.0, tier=SourceTier.TIER_B)
        f3 = _make_fact("f3", claim_text="净利5亿", value=5.0, tier=SourceTier.TIER_D)
        report = _make_report(facts=[f1, f2, f3])

        mc = MetricsComputer()
        metrics = mc.compute(report)

        assert metrics.source_tier_a_b_ratio == pytest.approx(2 / 3, abs=0.01)

    def test_fabricated_number_counted(self):
        """FABRICATED_NUMBER 类别 issues 计数."""
        report = _make_report()
        numeric_issues = [
            CritiqueIssue(
                issue_id="ni1",
                category=CritiqueCategory.FABRICATED_NUMBER,
                severity="error",
                section_id="s1",
                description="数字无匹配",
            ),
        ]
        mc = MetricsComputer()
        metrics = mc.compute(report, numeric_issues=numeric_issues)

        assert metrics.fabricated_number_count == 1

    def test_orphan_citation_counted(self):
        """ORPHAN_CITATION 类别 issues 计数."""
        report = _make_report()
        citation_issues = [
            CritiqueIssue(
                issue_id="ci1",
                category=CritiqueCategory.ORPHAN_CITATION,
                severity="error",
                section_id="s1",
                description="孤立引用",
            ),
        ]
        mc = MetricsComputer()
        metrics = mc.compute(report, citation_issues=citation_issues)

        assert metrics.orphan_citation_count == 1

    def test_to_grade_thresholds(self):
        """等级阈值映射正确."""
        mc = MetricsComputer()
        assert mc.to_grade(90) == "A"
        assert mc.to_grade(85) == "A"
        assert mc.to_grade(75) == "B"
        assert mc.to_grade(70) == "B"
        assert mc.to_grade(60) == "C"
        assert mc.to_grade(55) == "C"
        assert mc.to_grade(45) == "D"
        assert mc.to_grade(40) == "D"
        assert mc.to_grade(30) == "F"
        assert mc.to_grade(0) == "F"

    def test_empty_report_handles_gracefully(self):
        """空报告不崩溃，使用默认值（score 偏低但合法）."""
        report = _make_report(facts=[], sections=[])
        mc = MetricsComputer()
        metrics = mc.compute(report)

        assert metrics.total_facts == 0
        assert metrics.total_sections == 0
        assert 0.0 <= metrics.overall_score <= 100.0
        assert metrics.grade in ("A", "B", "C", "D", "F")

    def test_custom_weights_affect_overall(self):
        """自定义权重影响综合评分."""
        report = _make_report()
        mc_default = MetricsComputer()
        mc_custom = MetricsComputer(
            weights={
                "retrieval": 0.5,
                "fact": 0.2,
                "citation": 0.1,
                "report": 0.1,
                "efficiency": 0.1,
            }
        )

        m1 = mc_default.compute(report)
        m2 = mc_custom.compute(report)

        # 不同权重应产生不同综合评分
        assert m1.overall_score != pytest.approx(m2.overall_score, abs=0.5)

    def test_efficiency_metrics_passthrough(self):
        """耗时与 token 参数透传."""
        report = _make_report()
        mc = MetricsComputer()
        metrics = mc.compute(
            report,
            compilation_time_ms=5000.0,
            tokens_used=10000,
        )

        assert metrics.compilation_time_ms == 5000.0
        assert metrics.tokens_used == 10000

    def test_revision_rounds_from_critique(self):
        """修订轮数从 critique 中读取."""
        report = _make_report()
        critique = CritiqueReport(
            report_id="test_r1",
            overall_severity=CritiqueSeverity.PASS,
            metrics={"revision_rounds": 2},
        )
        mc = MetricsComputer()
        metrics = mc.compute(report, critique=critique)

        assert metrics.revision_rounds == 2

    def test_citation_coverage_with_citations(self):
        """引用覆盖率在有引用时正确计算."""
        f1 = _make_fact("f1")
        f2 = _make_fact("f2", claim_text="毛利20亿", value=20.0)
        s1 = _make_section("s1", content="营收100亿[1]。", fact_ids=["f1"])
        report = _make_report(facts=[f1, f2], sections=[s1])

        mc = MetricsComputer()
        metrics = mc.compute(report)

        # f1 被引用, f2 未引用
        assert 0.4 <= metrics.citation_coverage <= 0.6
