"""大纲规划器单元测试.

验证基于 facts + task 生成 ReportOutline 的结构完整性、各节 must_answer /
required_claim_types / counterpoints 填充、以及无 LLM 或无 facts 时的默认大纲回退。

对应 deep-research-report.md 第一阶段 "大纲规划器" 技能。
"""

from core.contracts import (
    ClaimType,
    FactRecord,
    Provenance,
    ReportOutline,
    ReportTask,
    SourceReliabilityLevel,
    SourceTier,
    SourceType,
)
from reporting.compiler.outline_planner import OutlinePlanner


def _make_fact(fact_id: str = "fact_a"):
    return FactRecord(
        fact_id=fact_id,
        claim_text="营收100亿元",
        claim_type=ClaimType.METRIC,
        value=100.0,
        unit="亿元",
        evidence_span="营收100亿元",
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


def _make_task():
    return ReportTask(task_id="task_1", template_name="某公司研究")


class TestOutlineWithStub:
    """使用 StubModelGateway 的大纲规划."""

    def test_generates_outline_with_sections(self, stub_gateway):
        planner = OutlinePlanner(stub_gateway)
        outline = planner.plan([_make_fact()], _make_task())
        assert isinstance(outline, ReportOutline)
        assert outline.report_title == "某公司研究"
        assert outline.thesis == "营收增长稳健"
        # stub 返回 2 节
        assert len(outline.sections) == 2
        # 各节 section_id 自动编号
        section_ids = [s.section_id for s in outline.sections]
        assert section_ids == ["sec_0", "sec_1"]

    def test_sections_carry_goal_and_must_answer(self, stub_gateway):
        planner = OutlinePlanner(stub_gateway)
        outline = planner.plan([_make_fact()], _make_task())
        first = outline.sections[0]
        assert first.title == "营收分析"
        assert first.goal == "分析营收"
        assert "营收增速" in first.must_answer
        assert ClaimType.METRIC in first.required_claim_types

    def test_counterpoints_populated(self, stub_gateway):
        planner = OutlinePlanner(stub_gateway)
        outline = planner.plan([_make_fact()], _make_task())
        risk_section = outline.sections[1]
        assert risk_section.title == "风险与反证"
        assert ClaimType.RISK in risk_section.required_claim_types
        assert len(risk_section.counterpoints) > 0


class TestDefaultOutlineFallback:
    """无 LLM 或无 facts 时的默认大纲."""

    def test_no_gateway_returns_default_outline(self):
        planner = OutlinePlanner(model_gateway=None)
        outline = planner.plan([_make_fact()], _make_task())
        # 默认大纲 3 节
        assert len(outline.sections) == 3
        titles = [s.title for s in outline.sections]
        assert "摘要与核心判断" in titles
        assert "关键证据与数据" in titles
        assert "风险与反证" in titles
        assert outline.metadata.get("default") is True

    def test_no_facts_returns_default_outline(self, stub_gateway):
        """无证据时即使有 LLM 也回退默认大纲."""
        planner = OutlinePlanner(stub_gateway)
        outline = planner.plan([], _make_task())
        assert len(outline.sections) == 3
        assert outline.metadata.get("default") is True

    def test_default_outline_covers_metric_and_risk(self):
        planner = OutlinePlanner(model_gateway=None)
        outline = planner.plan([_make_fact()], _make_task())
        all_claim_types = set()
        for s in outline.sections:
            all_claim_types.update(s.required_claim_types)
        assert ClaimType.METRIC in all_claim_types
        assert ClaimType.RISK in all_claim_types


class TestDigestFacts:
    def test_digest_includes_source_tier(self, stub_gateway):
        """_digest_facts 应包含来源 tier 信息."""
        planner = OutlinePlanner(stub_gateway)
        digest = planner._digest_facts([_make_fact()])
        assert "巨潮资讯网" in digest
        assert "tier_a" in digest
