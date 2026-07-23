"""表格/图表渲染器单元测试 - 第二阶段 2.5.

验证表格数字带 fact 短码、event 类 fact 被排除、图表类型选择、空 facts 返回 None。
"""

from core.contracts import (
    ClaimType,
    CompiledReport,
    FactRecord,
    Provenance,
    ReportOutline,
    SourceTier,
)
from reporting.compiler.chart_renderer import ChartRenderer
from reporting.compiler.renderer import Renderer
from reporting.compiler.table_renderer import TableRenderer

_prov = Provenance(doc_id="d1", source_name="巨潮", source_tier=SourceTier.TIER_A)


def _fact(fact_id, claim, claim_type, value=None, unit=None, entity="某公司", period="2024"):
    return FactRecord(
        fact_id=fact_id,
        claim_text=claim,
        claim_type=claim_type,
        entities=[entity],
        period=period,
        value=value,
        unit=unit,
        confidence=0.9,
        provenance=_prov,
    )


class TestTableRenderer:
    def test_metric_facts_become_table(self):
        facts = [
            _fact("fact_aaa111", "营收100亿", ClaimType.METRIC, 100.0, "亿元"),
            _fact("fact_bbb222", "营收120亿", ClaimType.METRIC, 120.0, "亿元", period="2025"),
        ]
        t = TableRenderer().render(facts)
        assert t is not None
        assert "主体" in t.headers[0]
        assert any("100" in str(r) for r in t.rows)
        assert any("aaa111" in str(r) for r in t.rows)

    def test_event_facts_excluded_from_table(self):
        facts = [
            _fact("fact_aaa111", "营收100亿", ClaimType.METRIC, 100.0, "亿元"),
            _fact("fact_evt999", "订单落地", ClaimType.EVENT),
        ]
        t = TableRenderer().render(facts)
        assert t is not None
        assert all("evt999" not in str(r) for r in t.rows)

    def test_no_metric_returns_none(self):
        facts = [_fact("fact_evt999", "订单落地", ClaimType.EVENT)]
        assert TableRenderer().render(facts) is None

    def test_empty_facts_returns_none(self):
        assert TableRenderer().render([]) is None


class TestChartRenderer:
    def test_single_entity_line_chart(self):
        facts = [
            _fact("fact_aaa111", "营收100亿", ClaimType.METRIC, 100.0, "亿元", period="2024"),
            _fact("fact_bbb222", "营收120亿", ClaimType.METRIC, 120.0, "亿元", period="2025"),
        ]
        c = ChartRenderer().render(facts)
        assert c is not None
        assert c.chart_type == "line"
        assert "某公司" in c.data_range

    def test_no_numeric_returns_none(self):
        facts = [_fact("fact_evt999", "订单落地", ClaimType.EVENT)]
        assert ChartRenderer().render(facts) is None


class TestRendererIntegration:
    def test_render_tables_and_charts(self):
        facts = [
            _fact("fact_aaa111", "营收100亿", ClaimType.METRIC, 100.0, "亿元"),
            _fact("fact_bbb222", "营收120亿", ClaimType.METRIC, 120.0, "亿元", period="2025"),
        ]
        report = CompiledReport(
            report_id="r1",
            outline=ReportOutline(report_title="t"),
            sections=[],
            facts=facts,
        )
        r = Renderer()
        tables = r.render_tables(report)
        charts = r.render_charts(report)
        assert len(tables) == 1
        assert len(charts) == 1

    def test_render_empty_report_no_artifacts(self):
        report = CompiledReport(
            report_id="r1",
            outline=ReportOutline(report_title="t"),
            sections=[],
            facts=[],
        )
        r = Renderer()
        assert r.render_tables(report) == []
        assert r.render_charts(report) == []
