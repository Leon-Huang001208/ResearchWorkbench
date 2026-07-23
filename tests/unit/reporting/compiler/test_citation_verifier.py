"""Phase 3.2: citation_verifier 测试."""

from core.contracts import (
    Citation,
    ClaimType,
    CompiledSection,
    CritiqueCategory,
    FactRecord,
    Provenance,
    SourceTier,
)
from reporting.compiler.citation_verifier import CitationVerifier


def _make_fact(
    fact_id: str = "f1",
    claim_text: str = "营收100亿元",
    value: float | None = 100.0,
    unit: str | None = "亿元",
    source_name: str = "巨潮资讯网",
) -> FactRecord:
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim_text,
        claim_type=ClaimType.METRIC,
        value=value,
        unit=unit,
        provenance=Provenance(doc_id="d1", source_tier=SourceTier.TIER_B, source_name=source_name),
        confidence=0.9,
    )


def _make_section(
    section_id: str = "s1",
    title: str = "营收分析",
    content: str = "公司营收100亿元[1]。",
    fact_ids: list[str] | None = None,
    source_names: list[str] | None = None,
) -> CompiledSection:
    if fact_ids is None:
        fact_ids = ["f1"]
    if source_names is None:
        source_names = ["巨潮资讯网"]
    citations = [
        Citation(
            citation_id=f"c{i + 1}",
            fact_ids=[fid],
            display_text=f"[{i + 1}] {source_names[i] if i < len(source_names) else '来源'}",
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


class TestCitationVerifier:
    """引用验证器测试."""

    def test_precise_citation_when_value_and_text_overlap(self):
        """值与文本均重叠 → 无 CITATION_PRECISION issue."""
        fact = _make_fact("f1", "营收100亿元", 100.0)
        section = _make_section(content="公司营收100亿元[1]。", fact_ids=["f1"])
        verifier = CitationVerifier()
        issues = verifier.verify([section], [fact])
        precision_issues = [i for i in issues if i.category == CritiqueCategory.CITATION_PRECISION]
        assert len(precision_issues) == 0

    def test_low_precision_when_no_overlap(self):
        """引用标记所在句子与 fact 文本不匹配 → CITATION_PRECISION issue."""
        fact = _make_fact("f1", "毛利率45%", 45.0, "%")
        section = _make_section(
            content="公司营收100亿元[1]。行业景气度高。",
            fact_ids=["f1"],
        )
        verifier = CitationVerifier()
        issues = verifier.verify([section], [fact])
        precision_issues = [i for i in issues if i.category == CritiqueCategory.CITATION_PRECISION]
        assert len(precision_issues) >= 1

    def test_orphan_citation_detected(self):
        """引用的 fact_id 不存在 → ORPHAN_CITATION issue."""
        section = _make_section(content="营收100亿元[1]。", fact_ids=["f999"])
        verifier = CitationVerifier()
        issues = verifier.verify([section], [])
        orphans = [i for i in issues if i.category == CritiqueCategory.ORPHAN_CITATION]
        assert len(orphans) >= 1
        assert "f999" in orphans[0].description

    def test_no_orphan_when_all_facts_exist(self):
        """所有 fact_id 都存在 → 无 ORPHAN_CITATION."""
        fact = _make_fact("f1")
        section = _make_section(content="营收100亿元[1]。", fact_ids=["f1"])
        verifier = CitationVerifier()
        issues = verifier.verify([section], [fact])
        orphans = [i for i in issues if i.category == CritiqueCategory.ORPHAN_CITATION]
        assert len(orphans) == 0

    def test_source_diversity_warning_when_single_source(self):
        """单一来源 >80% → SOURCE_DIVERSITY issue."""
        f1 = _make_fact("f1", "营收100亿元", 100.0, source_name="来源A")
        f2 = _make_fact("f2", "毛利20亿元", 20.0, source_name="来源A")
        f3 = _make_fact("f3", "净利5亿元", 5.0, source_name="来源A")
        section = _make_section(
            content="营收100亿[1]，毛利20亿[2]，净利5亿[3]。",
            fact_ids=["f1", "f2", "f3"],
            source_names=["来源A", "来源A", "来源A"],
        )
        section.citations = [
            Citation(citation_id="c1", fact_ids=["f1"], display_text="[1] 来源A"),
            Citation(citation_id="c2", fact_ids=["f2"], display_text="[2] 来源A"),
            Citation(citation_id="c3", fact_ids=["f3"], display_text="[3] 来源A"),
        ]
        verifier = CitationVerifier()
        issues = verifier.verify([section], [f1, f2, f3])
        diversity = [i for i in issues if i.category == CritiqueCategory.SOURCE_DIVERSITY]
        assert len(diversity) >= 1

    def test_source_diversity_pass_with_mixed_sources(self):
        """多来源分布均匀 → 无 SOURCE_DIVERSITY issue."""
        f1 = _make_fact("f1", "营收100亿元", 100.0, source_name="来源A")
        f2 = _make_fact("f2", "毛利20亿元", 20.0, source_name="来源B")
        section = _make_section(
            content="营收100亿[1]，毛利20亿[2]。",
            fact_ids=["f1", "f2"],
            source_names=["来源A", "来源B"],
        )
        section.citations = [
            Citation(citation_id="c1", fact_ids=["f1"], display_text="[1] 来源A"),
            Citation(citation_id="c2", fact_ids=["f2"], display_text="[2] 来源B"),
        ]
        verifier = CitationVerifier()
        issues = verifier.verify([section], [f1, f2])
        diversity = [i for i in issues if i.category == CritiqueCategory.SOURCE_DIVERSITY]
        assert len(diversity) == 0

    def test_empty_section_passes(self):
        """空章节 → 无 issue."""
        section = CompiledSection(
            section_id="s1",
            title="空",
            content="",
            citations=[],
            fact_ids=[],
        )
        verifier = CitationVerifier()
        issues = verifier.verify([section], [])
        assert len(issues) == 0

    def test_coverage_when_all_facts_cited(self):
        """所有 fact 都被引用 → 覆盖率 100%，无 coverage issue."""
        f1 = _make_fact("f1")
        f2 = _make_fact("f2")
        section = _make_section(
            content="营收100亿[1]，毛利20亿[2]。",
            fact_ids=["f1", "f2"],
        )
        verifier = CitationVerifier()
        verifier.MIN_COVERAGE_RATE = 0.5  # 确保不触发
        issues = verifier.verify([section], [f1, f2])
        precision = [i for i in issues if i.category == CritiqueCategory.CITATION_PRECISION]
        # 只检查 CIATION_PRECISION 类的 coverage issue 不出现
        coverage_issues = [i for i in precision if "覆盖率" in i.description]
        assert len(coverage_issues) == 0

    def test_precision_score_perfect_when_both_match(self):
        """值匹配 + 文本重叠 → 精度分数 = 1.0."""
        fact = _make_fact("f1", "营收100亿元", 100.0)
        section = _make_section(
            content="公司2024年营收100亿元[1]。",
            fact_ids=["f1"],
        )
        verifier = CitationVerifier()
        issues = verifier.verify([section], [fact])
        precision = [i for i in issues if i.category == CritiqueCategory.CITATION_PRECISION]
        assert len(precision) == 0

    def test_verify_multiple_sections(self):
        """多章节验证 → 汇总覆盖率跨章节计算."""
        f1 = _make_fact("f1", "营收100亿元", 100.0)
        f2 = _make_fact("f2", "毛利20亿元", 20.0)
        f3 = _make_fact("f3", "净利5亿元", 5.0)

        s1 = _make_section(
            section_id="s1",
            content="营收100亿[1]。",
            fact_ids=["f1"],
        )
        s2 = _make_section(
            section_id="s2",
            content="毛利20亿[2]。",
            fact_ids=["f2"],
        )
        verifier = CitationVerifier()
        verifier.MIN_COVERAGE_RATE = 0.9  # 2/3 = 67% < 90%
        issues = verifier.verify([s1, s2], [f1, f2, f3])
        # 应有 coverage issue（f3 未被引用）
        # f3 出现在 suggested_fix 中
        coverage = [
            i
            for i in issues
            if "覆盖率" in i.description and i.suggested_fix and "f3" in i.suggested_fix
        ]
        assert len(coverage) >= 1
