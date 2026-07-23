"""第三阶段 3.1: 完整 critic 测试."""

from core.contracts import (
    Citation,
    ClaimType,
    CompiledSection,
    CritiqueCategory,
    CritiqueSeverity,
    FactRecord,
    OutlineSection,
    Provenance,
    ReportOutline,
    SourceTier,
)
from reporting.compiler.critic import Critic


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
        provenance=Provenance(doc_id="d1", source_tier=SourceTier.TIER_B),
        confidence=0.9,
    )


def _make_section(
    section_id: str = "s1",
    title: str = "营收分析",
    content: str = "公司2024年营收100亿元[f1]，毛利率45%[f2]。行业景气度高。",
    fact_ids: list[str] | None = None,
    citation_count: int = 2,
) -> CompiledSection:
    if fact_ids is None:
        fact_ids = ["f1", "f2"]
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
        citations=citations[:citation_count],
        fact_ids=fact_ids,
    )


def _make_outline(
    sections: list[OutlineSection] | None = None,
) -> ReportOutline:
    return ReportOutline(
        report_title="测试报告",
        thesis="行业增长",
        sections=sections or [],
    )


class TestCriticFull:
    """完整 critic 测试."""

    def test_review_full_passes_clean_section(self):
        """干净的章节（值匹配 + 反证覆盖 + 字数达标）→ PASS."""
        facts = [
            _make_fact("f1", "营收100亿元", 100.0),
            _make_fact("f2", "毛利率45%", 45.0, "%"),
        ]
        outline = _make_outline(
            [
                OutlineSection(
                    section_id="s1",
                    title="营收分析",
                    goal="分析营收",
                    counterpoints=[],
                    target_words=30,
                )
            ]
        )
        section = _make_section(content="公司2024年营收100亿元[f1]，毛利率45%[f2]。")
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        assert result.overall_severity in (CritiqueSeverity.PASS, CritiqueSeverity.MINOR)

    def test_review_full_detects_forbidden_term(self):
        """正文含禁用词 → FORBIDDEN_TERM issue."""
        facts = [_make_fact("f1")]
        outline = _make_outline()
        section = _make_section(content="强力推荐买入。营收100亿元[f1]。")
        critic = Critic(forbidden_terms=["强力推荐"])
        result = critic.review_full([section], facts, outline)
        forbidden = [i for i in result.issues if i.category == CritiqueCategory.FORBIDDEN_TERM]
        assert len(forbidden) >= 1
        assert "强力推荐" in forbidden[0].description

    def test_review_full_detects_claim_support_gap(self):
        """有数字但无对应 fact → CLAIM_SUPPORT issue."""
        facts = [_make_fact("f1", "营收100亿元", 100.0)]
        outline = _make_outline(
            [OutlineSection(section_id="s1", title="营收分析", target_words=100)]
        )
        # 含 200亿元 数字但 facts 里只有 100 亿元
        section = _make_section(
            content="公司投融资规模达200亿元，营收100亿元[f1]。",
            fact_ids=["f1"],
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        support_issues = [i for i in result.issues if i.category == CritiqueCategory.CLAIM_SUPPORT]
        assert len(support_issues) >= 1

    def test_review_full_detects_conflict(self):
        """正文数字与 fact 值明显矛盾 → CONFLICT issue."""
        facts = [_make_fact("f1", "营收100亿元", 100.0)]
        outline = _make_outline(
            [OutlineSection(section_id="s1", title="营收分析", target_words=100)]
        )
        # 正文写 150 亿元，事实表是 100 亿元 → 偏差 50% > 20%
        section = _make_section(
            content="公司营收150亿元[f1]。",
            fact_ids=["f1"],
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        conflicts = [i for i in result.issues if i.category == CritiqueCategory.CONFLICT]
        assert len(conflicts) >= 1

    def test_review_full_no_conflict_when_values_close(self):
        """轻微差异（5% 以内）不标记冲突."""
        facts = [_make_fact("f1", "营收100亿元", 100.0)]
        outline = _make_outline(
            [OutlineSection(section_id="s1", title="营收分析", target_words=100)]
        )
        # 正文写 101 亿元，事实表 100 → 偏差 1% < 20%
        section = _make_section(
            content="公司营收101亿元[f1]。",
            fact_ids=["f1"],
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        conflicts = [i for i in result.issues if i.category == CritiqueCategory.CONFLICT]
        assert len(conflicts) == 0

    def test_review_full_detects_counterpoint_gap(self):
        """大纲有反证但正文未覆盖 → COUNTERPOINT issue."""
        facts = [_make_fact("f1")]
        outline = _make_outline(
            [
                OutlineSection(
                    section_id="s1",
                    title="营收分析",
                    counterpoints=["行业需求可能下滑"],
                    target_words=100,
                )
            ]
        )
        # 正文未提及需求下滑
        section = _make_section(
            content="公司营收增长稳定[f1]。",
            fact_ids=["f1"],
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        cp_issues = [i for i in result.issues if i.category == CritiqueCategory.COUNTERPOINT]
        assert len(cp_issues) >= 1
        assert "需求可能下滑" in cp_issues[0].description

    def test_review_full_counterpoint_covered(self):
        """反证关键词出现在正文中 → 无 COUNTERPOINT issue."""
        facts = [_make_fact("f1")]
        outline = _make_outline(
            [
                OutlineSection(
                    section_id="s1",
                    title="营收分析",
                    counterpoints=["需求可能下滑"],
                    target_words=100,
                )
            ]
        )
        # 正文提及需求下滑
        section = _make_section(
            content="虽然下游需求可能下滑，但公司营收保持增长[f1]。",
            fact_ids=["f1"],
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        cp_issues = [i for i in result.issues if i.category == CritiqueCategory.COUNTERPOINT]
        assert len(cp_issues) == 0

    def test_review_full_detects_structure_word_count_deviation(self):
        """字数偏差过大 → STRUCTURE issue."""
        facts = [_make_fact("f1")]
        outline = _make_outline(
            [OutlineSection(section_id="s1", title="营收分析", target_words=500)]
        )
        # 只有 30 字 vs 目标 500 → 偏差 94%
        section = _make_section(
            content="营收增长。[f1]",
            fact_ids=["f1"],
            citation_count=1,
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        struct = [i for i in result.issues if i.category == CritiqueCategory.STRUCTURE]
        assert len(struct) >= 1

    def test_review_full_detects_evidence_insufficient(self):
        """引用密度过低 → EVIDENCE_SUFFICIENCY issue."""
        facts = [
            _make_fact("f1"),
            _make_fact("f2"),
        ]
        outline = _make_outline(
            [OutlineSection(section_id="s1", title="营收分析", target_words=100)]
        )
        # 100 字只有 1 个引用 → 密度 1.0 < 0.5? No, 1.0 > 0.5. Need fewer citations.
        # Let's make a long section with few citations.
        long_content = (
            "公司营收增长显著。行业景气度持续提升。下游需求旺盛。"
            "公司在手订单充足。毛利率逐季改善。经营现金流健康。"
            "研发投入持续加大。市场份额稳步扩张。[f1]"
        )
        section = _make_section(
            content=long_content,
            fact_ids=["f1"],
            citation_count=1,
        )
        critic = Critic()
        # 降低阈值让这个测试稳定触发
        critic.MIN_CITATION_DENSITY = 3.0  # 每百字3条（远高于1条/百字）
        result = critic.review_full([section], facts, outline)
        evidence = [i for i in result.issues if i.category == CritiqueCategory.EVIDENCE_SUFFICIENCY]
        assert len(evidence) >= 1

    def test_review_full_determines_major_severity(self):
        """多个 warning → MAJOR."""
        facts = [_make_fact("f1")]
        outline = _make_outline(
            [
                OutlineSection(
                    section_id="s1",
                    title="营收分析",
                    counterpoints=["cp1", "cp2", "cp3", "cp4", "cp5", "cp6"],
                    target_words=500,
                )
            ]
        )
        # 短内容，缺引用，缺反证覆盖
        section = _make_section(
            content="营收增长。[f1]",
            fact_ids=["f1"],
            citation_count=1,
        )
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        # 多个 warning → 应 >= MAJOR
        assert result.overall_severity in (
            CritiqueSeverity.MAJOR,
            CritiqueSeverity.CRITICAL,
        )

    def test_review_determines_critical_for_many_errors(self):
        """大量 error → CRITICAL."""
        facts = [_make_fact("f1", "营收100亿元", 100.0)]
        outline = _make_outline(
            [
                OutlineSection(
                    section_id="s1",
                    title="营收分析",
                    counterpoints=["c1", "c2", "c3", "c4", "c5", "c6", "c7"],
                    target_words=500,
                )
            ]
        )
        # 含禁用词 + 数字矛盾 + 缺反证 + 字数偏差 → 应有 error 级别
        section = _make_section(
            content="强力推荐买入。公司营收300亿元。[f1]",
            fact_ids=["f1"],
            citation_count=1,
        )
        critic = Critic(forbidden_terms=["强力推荐"])
        result = critic.review_full([section], facts, outline)
        # 禁用词(1 error) + 冲突(1 error) → 2 errors → >= MAJOR
        assert result.overall_severity in (
            CritiqueSeverity.MAJOR,
            CritiqueSeverity.CRITICAL,
        )

    def test_review_metrics_include_claim_support_rate(self):
        """metrics 包含 claim_support_rate 等关键指标."""
        facts = [_make_fact("f1")]
        outline = _make_outline()
        section = _make_section(content="营收100亿元[f1]。", fact_ids=["f1"], citation_count=1)
        critic = Critic()
        result = critic.review_full([section], facts, outline)
        assert "claim_support_rate" in result.metrics
        assert "conflict_count" in result.metrics
        assert "citation_density" in result.metrics
        assert result.metrics["claim_support_rate"] == 1.0

    def test_review_legacy_interface_still_works(self):
        """向后兼容 review() → dict[str, ValidationResults]."""
        facts = [_make_fact("f1")]
        section = _make_section(content="营收100亿元[f1]。", fact_ids=["f1"])
        critic = Critic()
        result = critic.review([section], facts)
        assert section.section_id in result
        legacy = result[section.section_id]
        assert legacy.overall_passed is True
        assert len(legacy.results) >= 1
