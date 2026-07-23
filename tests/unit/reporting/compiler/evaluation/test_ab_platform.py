"""Phase 3.3: test_ab_platform.py — ABPlatform 测试."""

from datetime import datetime

from core.contracts import ABComparison, EvaluationReport, ReportMetrics
from reporting.compiler.evaluation.ab_platform import ABPlatform


def _make_metrics(**overrides) -> ReportMetrics:
    """创建带可选覆盖的 ReportMetrics."""
    defaults = {
        "source_tier_a_b_ratio": 0.8,
        "total_evidence_chunks": 10,
        "evidence_diversity": 0.6,
        "total_facts": 5,
        "claim_support_rate": 0.9,
        "fabricated_number_count": 0,
        "citation_coverage": 0.85,
        "orphan_citation_count": 0,
        "source_diversity_pct": 0.3,
        "total_words": 2000,
        "total_sections": 5,
        "structure_score": 0.85,
        "counterpoint_coverage": 0.7,
        "compilation_time_ms": 5000.0,
        "tokens_used": 10000,
        "cost_estimate": 0.1,
        "revision_rounds": 1,
        "overall_score": 82.0,
        "grade": "B",
    }
    defaults.update(overrides)
    return ReportMetrics(**defaults)


def _make_eval(report_id: str = "r1", metrics: ReportMetrics | None = None) -> EvaluationReport:
    if metrics is None:
        metrics = _make_metrics()
    return EvaluationReport(
        report_id=report_id,
        metrics=metrics,
        overall_score=metrics.overall_score,
        grade=metrics.grade,
        evaluated_at=datetime.utcnow(),
    )


class TestABPlatform:
    """A/B 对比平台测试."""

    def test_compare_returns_ab_comparison(self):
        """基本测试：返回 ABComparison."""
        platform = ABPlatform()
        eval_a = _make_eval("r1", _make_metrics(overall_score=82.0))
        eval_b = _make_eval("r2", _make_metrics(overall_score=75.0))

        result = platform.compare(eval_a, eval_b)
        assert isinstance(result, ABComparison)
        assert result.report_id_a == "r1"
        assert result.report_id_b == "r2"

    def test_compare_all_dimensions_present(self):
        """所有维度都出现."""
        platform = ABPlatform()
        eval_a = _make_eval("r1")
        eval_b = _make_eval("r2")

        result = platform.compare(eval_a, eval_b)
        assert len(result.dimensions) >= 6

    def test_overall_winner_a_wins(self):
        """A 在各维度显著优于 B → winner A."""
        platform = ABPlatform()
        eval_a = _make_eval(
            "r1",
            _make_metrics(
                claim_support_rate=0.95,
                citation_coverage=0.95,
                structure_score=0.95,
                overall_score=90.0,
            ),
        )
        eval_b = _make_eval(
            "r2",
            _make_metrics(
                claim_support_rate=0.5,
                citation_coverage=0.5,
                structure_score=0.5,
                overall_score=50.0,
            ),
        )

        result = platform.compare(eval_a, eval_b)
        assert result.overall_winner == "A"

    def test_blind_mode_labels(self):
        """盲评模式使用 配置 A/B 标签."""
        platform = ABPlatform()
        eval_a = _make_eval("r1")
        eval_b = _make_eval("r2")

        result = platform.compare(eval_a, eval_b, blind=True)
        # 盲评模式可能交换标签（随机），但结果仍应有 win_count
        assert result.blind_mode is True
        assert sum(result.win_count.values()) > 0

    def test_identical_reports_tie(self):
        """完全相同的报告 → tie."""
        platform = ABPlatform()
        metrics = _make_metrics()
        eval_a = _make_eval("r1", metrics)
        eval_b = _make_eval("r2", metrics.model_copy())

        result = platform.compare(eval_a, eval_b)
        assert result.overall_winner == "tie"

    def test_summary_generated(self):
        """ABComparison.summary 非空."""
        platform = ABPlatform()
        eval_a = _make_eval("r1")
        eval_b = _make_eval("r2")

        result = platform.compare(eval_a, eval_b)
        assert result.summary
        assert "对比结果" in result.summary

    def test_dimensions_have_delta(self):
        """每个 ABDimensionDiff 有 delta/pct_change/winner."""
        platform = ABPlatform()
        eval_a = _make_eval("r1", _make_metrics(claim_support_rate=0.9))
        eval_b = _make_eval("r2", _make_metrics(claim_support_rate=0.7))

        result = platform.compare(eval_a, eval_b)
        # 找到 claim_support_rate 对应的维度
        dim = [d for d in result.dimensions if "支撑率" in d.dimension][0]
        assert dim.diff < 0  # B < A
        assert dim.pct_change < 0
        assert dim.winner == "A"

    def test_non_blind_uses_report_ids(self):
        """非盲评使用实际 report_id."""
        platform = ABPlatform()
        eval_a = _make_eval("report_alpha")
        eval_b = _make_eval("report_beta")

        result = platform.compare(eval_a, eval_b, blind=False)
        assert result.report_id_a == "report_alpha"
        assert result.report_id_b == "report_beta"
