"""第三阶段 3.1: revision_pass 测试."""

from core.contracts import (
    Citation,
    ClaimType,
    CompiledSection,
    CritiqueCategory,
    CritiqueIssue,
    CritiqueReport,
    CritiqueSeverity,
    FactRecord,
    OutlineSection,
    Provenance,
    ReportOutline,
    SourceTier,
)
from reporting.compiler.revision_pass import RevisionPass, RevisionResult


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
    content: str = "公司2024年营收100亿元[f1]，毛利率45%[f2]。",
    fact_ids: list[str] | None = None,
) -> CompiledSection:
    if fact_ids is None:
        fact_ids = ["f1", "f2"]
    citations = [
        Citation(citation_id=f"c{i + 1}", fact_ids=[fid], display_text=f"[{i + 1}] 来源")
        for i, fid in enumerate(fact_ids)
    ]
    return CompiledSection(
        section_id=section_id,
        title=title,
        content=content,
        citations=citations,
        fact_ids=fact_ids,
    )


def _make_outline(
    sections: list[OutlineSection] | None = None,
) -> ReportOutline:
    return ReportOutline(
        report_title="测试报告",
        sections=sections or [],
    )


class TestRevisionPass:
    """修订器测试."""

    def test_revise_conflict_replaces_number(self):
        """CONFLICT: 正文矛盾数字被替换为事实表值."""
        facts = [
            _make_fact("f1", "营收100亿元", 100.0),
        ]
        section = _make_section(
            content="公司营收150亿元[f1]。",
            fact_ids=["f1"],
        )
        issue = CritiqueIssue(
            issue_id="i1",
            category=CritiqueCategory.CONFLICT,
            severity="error",
            section_id="s1",
            description="数字矛盾：正文 150.0 高于 事实表 100.0",
            location="公司营收150亿元[f1]。",
            conflicting_fact_id="f1",
            suggested_fix="将正文中的 150 替换为事实表值 100",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MAJOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, facts, _make_outline())
        assert len(result.fixed_issue_ids) == 1
        assert "150" not in result.sections[0].content
        assert "100" in result.sections[0].content

    def test_revise_counterpoint_adds_suffix(self):
        """COUNTERPOINT: 节尾追加反证提示句."""
        section = _make_section(
            content="公司营收增长稳定[f1]。",
            fact_ids=["f1"],
        )
        issue = CritiqueIssue(
            issue_id="i2",
            category=CritiqueCategory.COUNTERPOINT,
            severity="warning",
            section_id="s1",
            description="反证点未覆盖：「需求可能下滑」",
            suggested_fix="在正文中加入对「需求可能下滑」的讨论",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        assert len(result.fixed_issue_ids) == 1
        assert "需求可能下滑" in result.sections[0].content

    def test_revise_forbidden_term_removed(self):
        """FORBIDDEN_TERM: 禁用词被删除."""
        section = _make_section(
            content="强力推荐买入。营收100亿元[f1]。",
            fact_ids=["f1"],
        )
        issue = CritiqueIssue(
            issue_id="i3",
            category=CritiqueCategory.FORBIDDEN_TERM,
            severity="error",
            section_id="s1",
            description="正文包含禁用词「强力推荐」",
            location="强力推荐买入。",
            suggested_fix="删除或替换「强力推荐」",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MAJOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        assert len(result.fixed_issue_ids) == 1
        assert "强力推荐" not in result.sections[0].content
        assert "已删除违规表述" in result.sections[0].content

    def test_revise_structure_unfixable(self):
        """STRUCTURE: 不可自动修复 → unfixable_ids."""
        section = _make_section(content="短。[f1]", fact_ids=["f1"])
        issue = CritiqueIssue(
            issue_id="i4",
            category=CritiqueCategory.STRUCTURE,
            severity="warning",
            section_id="s1",
            description="字数不足目标",
            suggested_fix="补充内容达到目标字数",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        assert len(result.fixed_issue_ids) == 0
        assert len(result.unfixable_issue_ids) == 1

    def test_revise_claim_support_adds_ref(self):
        """CLAIM_SUPPORT: 在未支撑句子后插入 fact 引用标记."""
        facts = [
            _make_fact("f1", "营收100亿元", 100.0),
            _make_fact("f3", "毛利率提升至42%", 42.0, "%"),
        ]
        # section 只有 f1 引用，但提到"毛利率42%"—匹配到 f3
        section = _make_section(
            content="公司营收100亿元[f1]。毛利率提升至42%，表现亮眼。",
            fact_ids=["f1"],
        )
        issue = CritiqueIssue(
            issue_id="i5",
            category=CritiqueCategory.CLAIM_SUPPORT,
            severity="warning",
            section_id="s1",
            description="句子中的数字缺少事实支撑",
            location="毛利率提升至42%，表现亮眼。",
            suggested_fix="为此句添加引用标记 [fact_id]",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, facts, _make_outline())
        assert len(result.fixed_issue_ids) == 1
        # 应插入了 f3 引用
        assert "[f3]" in result.sections[0].content

    def test_revise_max_rounds_enforced(self):
        """超过 MAX_ROUNDS → 返回 unchanged sections."""
        section = _make_section(content="营收100亿元[f1]。", fact_ids=["f1"])
        issue = CritiqueIssue(
            issue_id="i6",
            category=CritiqueCategory.CONFLICT,
            severity="error",
            section_id="s1",
            description="数字矛盾",
            location="营收100亿元[f1]。",
            conflicting_fact_id="f1",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MAJOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise(
            [section],
            critique,
            [_make_fact("f1", "营收100亿元", 100.0)],
            _make_outline(),
            round_number=3,  # > MAX_ROUNDS
        )
        assert result.rounds == 3
        assert result.converged is False
        assert "已达最大修订轮次上限" in result.summary

    def test_revise_tracks_fixed_and_unfixable_counts(self):
        """正确追踪 fixed / unfixable 计数."""
        section = _make_section(content="营收增长。[f1]", fact_ids=["f1"])
        issues = [
            CritiqueIssue(
                issue_id="if",
                category=CritiqueCategory.FORBIDDEN_TERM,
                severity="error",
                section_id="s1",
                description="正文包含禁用词「营收」",
                suggested_fix="删除「营收」",
            ),
            CritiqueIssue(
                issue_id="iu",
                category=CritiqueCategory.STRUCTURE,
                severity="warning",
                section_id="s1",
                description="字数不足",
            ),
        ]
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MAJOR,
            issues=issues,
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        assert len(result.fixed_issue_ids) == 1  # 禁用词可修复
        assert len(result.unfixable_issue_ids) == 1  # 结构不可修
        assert len(result.remaining_issues) == 1

    def test_revise_result_is_dataclass(self):
        """RevisionResult 是 dataclass，字段可访问."""
        result = RevisionResult()
        assert result.sections == []
        assert result.fixed_issue_ids == []
        assert result.rounds == 0
        assert result.converged is False

    def test_revise_converged_when_no_errors_remain(self):
        """修复后没有 error 级别 → converged=True."""
        section = _make_section(content="营收100亿元。[f1]", fact_ids=["f1"])
        # 只有一个 warning 级别的 issue
        issue = CritiqueIssue(
            issue_id="iw",
            category=CritiqueCategory.EVIDENCE_SUFFICIENCY,
            severity="info",
            section_id="s1",
            description="证据密度略低",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MINOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        # EVIDENCE_SUFFICIENCY 不可自动修复 → unfixable
        # 但没有 error → 应 converged
        assert result.converged is True
        # 或者：MINOR 整体严重度 + 无 error → converged
        assert "所有错误已修复" in result.summary or result.converged

    def test_revise_with_missing_section_id_skips(self):
        """issue 指向不存在的 section → unfixable."""
        section = _make_section(section_id="s1", content="营收100亿元[f1]。")
        issue = CritiqueIssue(
            issue_id="ix",
            category=CritiqueCategory.CONFLICT,
            severity="error",
            section_id="s_nonexistent",  # 不存在
            description="数字矛盾",
            conflicting_fact_id="f1",
        )
        critique = CritiqueReport(
            report_id="r1",
            overall_severity=CritiqueSeverity.MAJOR,
            issues=[issue],
        )
        rp = RevisionPass()
        result = rp.revise([section], critique, [], _make_outline())
        assert len(result.unfixable_issue_ids) == 1
