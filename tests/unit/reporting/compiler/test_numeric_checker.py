"""Phase 3.2: numeric_checker 测试."""

from core.contracts import (
    Citation,
    ClaimType,
    CompiledSection,
    CritiqueCategory,
    FactRecord,
    Provenance,
    SourceTier,
)
from reporting.compiler.numeric_checker import NumericChecker


def _make_fact(
    fact_id: str = "f1",
    claim_text: str = "营收100亿元",
    value: float | None = 100.0,
    unit: str | None = "亿元",
    period: str | None = "2024",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim_text,
        claim_type=ClaimType.METRIC,
        value=value,
        unit=unit,
        period=period,
        provenance=Provenance(doc_id="d1", source_tier=SourceTier.TIER_B),
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


class TestNumericChecker:
    """数字检查器测试."""

    def test_all_numbers_matched_passes(self):
        """所有数字都能匹配到 fact → 0 issues."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        f2 = _make_fact("f2", "毛利率45%", 45.0, "%")
        section = _make_section(content="公司营收100亿元，毛利率45%。")
        checker = NumericChecker()
        issues = checker.check([section], [f1, f2])
        assert len(issues) == 0

    def test_fabricated_number_detected(self):
        """正文数字无法匹配任何 fact → FABRICATED_NUMBER issue."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        section = _make_section(content="公司营收100亿元，投融资规模达200亿元。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        fabricated = [i for i in issues if i.category == CritiqueCategory.FABRICATED_NUMBER]
        assert len(fabricated) >= 1
        assert "200" in fabricated[0].description

    def test_unit_mismatch_detected(self):
        """正文数字值匹配但单位不同 → UNIT_MISMATCH issue."""
        f1 = _make_fact("f1", "营收100亿元", 100.0, "亿元")
        section = _make_section(content="公司营收100万元。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        unit_issues = [i for i in issues if i.category == CritiqueCategory.UNIT_MISMATCH]
        assert len(unit_issues) >= 1
        assert "亿元" in unit_issues[0].description

    def test_period_mismatch_detected(self):
        """正文数字值匹配但期间不同 → PERIOD_MISMATCH issue."""
        f1 = _make_fact("f1", "营收100亿元", 100.0, "亿元", "2024")
        section = _make_section(content="公司2025年营收100亿元。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        period_issues = [i for i in issues if i.category == CritiqueCategory.PERIOD_MISMATCH]
        assert len(period_issues) >= 1
        assert "2024" in period_issues[0].description

    def test_year_numbers_filtered(self):
        """年份数字不被视为内容数字."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        section = _make_section(content="公司2024年营收100亿元。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        # 2024 年份应被过滤，100 应匹配 f1
        assert len(issues) == 0

    def test_citation_markers_filtered(self):
        """引用标记 [f1] 和 [1] 内的数字不被提取."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        section = _make_section(content="公司营收100亿元[f1]。行业排名第1。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        # [f1] 中不应该提取 "1"，"第1" 也应该被过滤
        fabricated = [i for i in issues if i.category == CritiqueCategory.FABRICATED_NUMBER]
        assert len(fabricated) == 0

    def test_mixed_results_tracked(self):
        """同时有虚构、单位不匹配、期间不匹配 → 全部报告."""
        f1 = _make_fact("f1", "营收100亿元", 100.0, "亿元", "2024")
        f2 = _make_fact("f2", "毛利率45%", 45.0, "%", "2024")
        section = _make_section(content="公司2024年营收100万元，2025年毛利率45%，投融资200亿元。")
        checker = NumericChecker()
        issues = checker.check([section], [f1, f2])

        fabricated = [i for i in issues if i.category == CritiqueCategory.FABRICATED_NUMBER]
        unit_mismatch = [i for i in issues if i.category == CritiqueCategory.UNIT_MISMATCH]
        period_mismatch = [i for i in issues if i.category == CritiqueCategory.PERIOD_MISMATCH]

        assert len(fabricated) >= 1  # "200亿元"
        assert len(unit_mismatch) >= 1  # "100万元" vs fact "亿元"
        assert len(period_mismatch) >= 1  # "2025年" vs fact "2024"

    def test_empty_content_passes(self):
        """空内容 → 0 issues."""
        section = CompiledSection(
            section_id="s1",
            title="空",
            content="",
            citations=[],
            fact_ids=[],
        )
        checker = NumericChecker()
        issues = checker.check([section], [])
        assert len(issues) == 0

    def test_no_numbers_returns_empty(self):
        """正文无数字 → 0 issues."""
        f1 = _make_fact("f1")
        section = _make_section(content="公司经营稳健，发展良好。")
        checker = NumericChecker()
        issues = checker.check([section], [f1])
        assert len(issues) == 0

    def test_check_multiple_sections(self):
        """多章节独立检查."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        f2 = _make_fact("f2", "毛利20亿元", 20.0)

        s1 = _make_section(
            section_id="s1",
            content="营收100亿元。虚构数字300亿元。",
        )
        s2 = _make_section(
            section_id="s2",
            content="毛利20亿元。",
        )
        checker = NumericChecker()
        issues = checker.check([s1, s2], [f1, f2])

        fabricated = [i for i in issues if i.category == CritiqueCategory.FABRICATED_NUMBER]
        assert len(fabricated) >= 1
        assert fabricated[0].section_id == "s1"
