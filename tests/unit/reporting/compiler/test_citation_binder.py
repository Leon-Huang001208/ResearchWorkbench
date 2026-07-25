"""引用绑定器单元测试.

验证 [fact_id] → [N] 替换、Citation 对象生成、orphan citation 检测（引用不存在
的 fact 时移除标记）、unsupported claim 检测（含数字但零引用）。

对应 deep-research-report.md 第一阶段 "引用绑定器" 技能（LongCite 式句级引用）。
"""

from core.contracts import (
    ClaimType,
    CompiledSection,
    FactRecord,
    Provenance,
    SourceReliabilityLevel,
    SourceTier,
    SourceType,
)
from reporting.compiler.citation_binder import CitationBinder


def _make_fact(fact_id: str, claim_text: str = "营收100亿元", value: float = 100.0, unit: str = "亿元"):
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim_text,
        claim_type=ClaimType.METRIC,
        value=value,
        unit=unit,
        evidence_span=claim_text,
        provenance=Provenance(
            doc_id="d1",
            chunk_id="c1",
            source_type=SourceType.CNINFO,
            source_name="巨潮资讯网",
            source_url="http://example.com",
            published_at=None,
            source_reliability=SourceReliabilityLevel.OFFICIAL,
            source_tier=SourceTier.TIER_A,
        ),
    )


class TestCitationReplacement:
    """[fact_id] → [N] 替换与 Citation 生成."""

    def test_single_citation_replaced(self):
        fact = _make_fact("fact_a")
        section = CompiledSection(
            section_id="s1",
            title="营收分析",
            content="营收增长稳健，关键数据见 [fact_a]。",
        )
        bound = CitationBinder().bind([section], [fact])[0]
        assert "[fact_a]" not in bound.content
        assert "[1]" in bound.content
        assert len(bound.citations) == 1
        assert bound.citations[0].fact_ids == ["fact_a"]
        assert bound.fact_ids == ["fact_a"]
        # display_text 形如 "[1] 巨潮资讯网 无日期"
        assert bound.citations[0].display_text.startswith("[1] 巨潮资讯网")

    def test_multiple_citations_numbered_sequentially(self):
        f1 = _make_fact("fact_a", "营收100亿元", 100.0, "亿元")
        f2 = _make_fact("fact_b", "毛利率45%", 45.0, "%")
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="营收见 [fact_a]，毛利率见 [fact_b]。",
        )
        bound = CitationBinder().bind([section], [f1, f2])[0]
        assert "[1]" in bound.content and "[2]" in bound.content
        assert len(bound.citations) == 2
        assert bound.citations[0].fact_ids == ["fact_a"]
        assert bound.citations[1].fact_ids == ["fact_b"]

    def test_repeated_citation_reuses_number(self):
        """同一 fact 多次引用应复用同一编号."""
        fact = _make_fact("fact_a")
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="先提 [fact_a]，再提 [fact_a]。",
        )
        bound = CitationBinder().bind([section], [fact])[0]
        # 两次引用只生成一条 Citation，编号都是 [1]
        assert bound.content.count("[1]") == 2
        assert len(bound.citations) == 1
        assert bound.fact_ids == ["fact_a"]

    def test_citation_anchor_carries_evidence_span(self):
        fact = _make_fact("fact_a", "营收100亿元")
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="数据见 [fact_a]。",
        )
        bound = CitationBinder().bind([section], [fact])[0]
        anchor = bound.citations[0].anchor
        assert anchor is not None
        assert anchor.locator_type == "span"
        assert anchor.locator_value == "营收100亿元"


class TestOrphanCitation:
    """orphan citation 检测 - 引用不存在的 fact."""

    def test_orphan_citation_marker_removed(self):
        """正文引用了不在事实表中的 fact_id，应移除标记且不生成 Citation."""
        fact = _make_fact("fact_a")
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="有效引用 [fact_a]，无效引用 [fact_ghost]。",
        )
        bound = CitationBinder().bind([section], [fact])[0]
        # ghost 标记被移除
        assert "[fact_ghost]" not in bound.content
        # 只有有效引用生成 Citation
        assert len(bound.citations) == 1
        assert bound.citations[0].fact_ids == ["fact_a"]


class TestUnsupportedClaim:
    """unsupported claim 检测 - 含数字但无引用."""

    def test_section_without_citations_or_numbers_passes_silently(self):
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="本节无数字也无引用。",
        )
        bound = CitationBinder().bind([section], [])[0]
        # 无数字无引用：不报 unsupported，citations 为空
        assert bound.citations == []

    def test_numbers_without_citation_does_not_crash(self):
        """含数字但无引用 - 第一阶段只记日志，不影响输出结构."""
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="公司营收达到200亿元，但未标注引用。",
        )
        bound = CitationBinder().bind([section], [])[0]
        # 无 fact 引用，citations 为空；正文数字保留（第三阶段 numeric_checker 处理）
        assert bound.citations == []
        assert "200亿元" in bound.content


class TestEmptyContent:
    def test_no_fact_refs_in_content(self):
        fact = _make_fact("fact_a")
        section = CompiledSection(
            section_id="s1",
            title="分析",
            content="本节未引用任何 fact。",
        )
        bound = CitationBinder().bind([section], [fact])[0]
        assert bound.citations == []
        assert bound.fact_ids == []
