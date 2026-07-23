"""Phase 3.3: test_auto_grader.py — AutoGrader 测试."""

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
    EvaluationReport,
    FactRecord,
    OutlineSection,
    Provenance,
    ReportOutline,
    SourceTier,
)
from reporting.compiler.evaluation.auto_grader import AutoGrader
from reporting.compiler.evaluation.metrics import MetricsComputer


def _make_fact(
    fact_id: str = "f1",
    claim_text: str = "营收100亿元",
    value: float | None = 100.0,
    unit: str | None = "亿元",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim_text,
        claim_type=ClaimType.METRIC,
        value=value,
        unit=unit,
        provenance=Provenance(doc_id="d1", source_tier=SourceTier.TIER_A, source_name="来源A"),
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


def _make_report(facts=None, sections=None):
    if facts is None:
        facts = [_make_fact("f1")]
    if sections is None:
        sections = [_make_section("s1", fact_ids=["f1"])]
    outline = ReportOutline(
        report_title="测试报告",
        sections=[OutlineSection(section_id="s1", title="营收分析")],
    )
    return CompiledReport(
        report_id="test_r1",
        outline=outline,
        sections=sections,
        facts=facts,
    )


class TestAutoGrader:
    """自动评分器测试."""

    def test_grade_returns_evaluation_report(self, stub_gateway):
        """基本烟雾测试：返回 EvaluationReport."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        result = grader.grade(report)

        assert isinstance(result, EvaluationReport)
        assert result.report_id == "test_r1"
        assert 0.0 <= result.overall_score <= 100.0
        assert result.grade != "N/A"
        assert result.evaluated_at is not None

    def test_grade_with_reuse_critique(self, stub_gateway):
        """传入 critique → issues 合并."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        critique = CritiqueReport(
            report_id="test_r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[
                CritiqueIssue(
                    issue_id="cr1",
                    category=CritiqueCategory.CLAIM_SUPPORT,
                    severity="warning",
                    section_id="s1",
                    description="声明缺乏支撑",
                ),
            ],
            metrics={"claim_support_rate": 0.8, "revision_rounds": 1},
        )
        result = grader.grade(report, critique=critique)
        assert len(result.critique_issues) >= 1  # 至少包含 critic issue

    def test_grade_without_critique_works(self, stub_gateway):
        """无 critique → 正常评测."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        result = grader.grade(report)

        assert isinstance(result, EvaluationReport)
        assert result.overall_score >= 0.0

    def test_grade_without_gateway_works(self):
        """无 gateway → 用规则回退，不崩溃."""
        grader = AutoGrader(model_gateway=None)
        report = _make_report()
        result = grader.grade(report)

        assert isinstance(result, EvaluationReport)
        assert len(result.claims) >= 0  # 规则回退至少不崩溃

    def test_all_issues_aggregated(self, stub_gateway):
        """critic + citation + numeric issues 全部汇总."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        critique = CritiqueReport(
            report_id="test_r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[
                CritiqueIssue(
                    issue_id="cr1",
                    category=CritiqueCategory.CLAIM_SUPPORT,
                    severity="warning",
                    section_id="s1",
                    description="声明缺乏支撑",
                ),
            ],
        )
        pre_cit = [
            CritiqueIssue(
                issue_id="ci1",
                category=CritiqueCategory.ORPHAN_CITATION,
                severity="error",
                section_id="s1",
                description="孤立引用",
            ),
        ]
        pre_num = [
            CritiqueIssue(
                issue_id="ni1",
                category=CritiqueCategory.FABRICATED_NUMBER,
                severity="error",
                section_id="s1",
                description="虚构数字",
            ),
        ]
        result = grader.grade(
            report,
            critique=critique,
            precomputed_citation_issues=pre_cit,
            precomputed_numeric_issues=pre_num,
        )
        assert len(result.critique_issues) >= 3

    def test_precomputed_issues_reused(self, stub_gateway):
        """预计算 issues 被复用，不计两次."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        pre_cit = [
            CritiqueIssue(
                issue_id="ci_custom",
                category=CritiqueCategory.CITATION_PRECISION,
                severity="info",
                section_id="s1",
                description="定制引用问题",
            ),
        ]
        result = grader.grade(report, precomputed_citation_issues=pre_cit)
        assert any("定制引用问题" in i.description for i in result.critique_issues)

    def test_metrics_populated(self, stub_gateway):
        """EvaluationReport.metrics 正确填充."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        result = grader.grade(report)

        assert result.metrics.total_facts == 1
        assert result.metrics.total_sections == 1
        assert result.metrics.overall_score == result.overall_score

    def test_no_gateway_claim_extraction(self):
        """无 LLM → 规则抽取 claims，不崩溃."""
        grader = AutoGrader(model_gateway=None)
        report = _make_report()
        result = grader.grade(report)

        assert isinstance(result, EvaluationReport)
        assert result.grade in ("A", "B", "C", "D", "F", "N/A")

    def test_custom_metric_computer_used(self, stub_gateway):
        """自定义 MetricsComputer 影响输出."""
        custom_mc = MetricsComputer(
            weights={
                "retrieval": 1.0,
                "fact": 0.0,
                "citation": 0.0,
                "report": 0.0,
                "efficiency": 0.0,
            }
        )
        grader = AutoGrader(model_gateway=stub_gateway, metric_computer=custom_mc)
        report = _make_report()
        result = grader.grade(report)

        assert result.overall_score == pytest.approx(100.0, abs=5.0)  # Tier A → ~100

    def test_grade_assigned_from_metrics(self, stub_gateway):
        """等级从 metrics.overall_score 映射."""
        grader = AutoGrader(model_gateway=stub_gateway)
        report = _make_report()
        result = grader.grade(report)

        expected_grade = MetricsComputer.to_grade(result.overall_score)
        assert result.grade == expected_grade
