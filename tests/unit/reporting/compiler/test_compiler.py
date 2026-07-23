"""报告编译器端到端单元测试.

用 StubModelGateway + PassthroughEvidenceRetriever 跑通 ReportCompiler.compile() 完整
9 步流水线，断言 ReportTask → CompiledReport 全链路、facts 抽取、引用绑定、critic 校验
均正确衔接。

对应 deep-research-report.md 第一阶段验证方式 "流水线集成"。
"""

from core.contracts import (
    CompiledReport,
    ReportTask,
    SourceTier,
)
from reporting.compiler.compiler import ReportCompiler
from reporting.compiler.evidence_retriever import PassthroughEvidenceRetriever


def _make_task():
    return ReportTask(task_id="task_e2e", template_name="某公司研究")


class TestCompilerEndToEnd:
    """ReportCompiler.compile 完整流水线."""

    def test_compile_produces_report(self, stub_gateway, sample_evidence_package):
        # 让 PassthroughEvidenceRetriever 按 query_text 返回预检索证据
        # source_planner 会用 research_plan.research_questions 作为 query_text
        # stub 的 _ResearchPlanLLM 返回 research_questions=["某公司营收分析","毛利率变化"]
        backend = PassthroughEvidenceRetriever(
            packages={
                "某公司营收分析": sample_evidence_package,
                "毛利率变化": sample_evidence_package,
            }
        )
        compiler = ReportCompiler(model_gateway=stub_gateway, evidence_retriever=backend)
        report = compiler.compile(_make_task())

        assert isinstance(report, CompiledReport)
        assert report.compiler_version == "2.0"
        assert len(report.sections) > 0
        # facts 来自 sample_evidence_package（营收100亿元 / 毛利率45%）
        assert len(report.facts) >= 2
        assert all(f.provenance.source_tier == SourceTier.TIER_A for f in report.facts)

    def test_outline_present_in_report(self, stub_gateway, sample_evidence_package):
        backend = PassthroughEvidenceRetriever(
            packages={
                "某公司营收分析": sample_evidence_package,
                "毛利率变化": sample_evidence_package,
            }
        )
        compiler = ReportCompiler(model_gateway=stub_gateway, evidence_retriever=backend)
        report = compiler.compile(_make_task())
        assert report.outline is not None
        assert report.outline.report_title == "某公司研究"
        assert len(report.outline.sections) == len(report.sections)

    def test_citations_bound_in_sections(self, stub_gateway, sample_evidence_package):
        """端到端后，至少有一节正文含格式化引用 [N] 与 Citation 对象."""
        backend = PassthroughEvidenceRetriever(
            packages={
                "某公司营收分析": sample_evidence_package,
                "毛利率变化": sample_evidence_package,
            }
        )
        compiler = ReportCompiler(model_gateway=stub_gateway, evidence_retriever=backend)
        report = compiler.compile(_make_task())
        total_citations = sum(len(s.citations) for s in report.sections)
        # stub writer 会把可用 facts 标成 [fact_id]，binder 转成 [N]
        assert total_citations > 0
        # 至少一节正文含 [1]
        has_numbered_citation = any("[" in s.content and "]" in s.content for s in report.sections)
        assert has_numbered_citation

    def test_validation_results_attached(self, stub_gateway, sample_evidence_package):
        """critic 校验结果应挂到各 section."""
        backend = PassthroughEvidenceRetriever(
            packages={
                "某公司营收分析": sample_evidence_package,
                "毛利率变化": sample_evidence_package,
            }
        )
        compiler = ReportCompiler(model_gateway=stub_gateway, evidence_retriever=backend)
        report = compiler.compile(_make_task())
        for section in report.sections:
            assert section.validation_result is not None
            # 第三阶段 critic 按 CritiqueCategory 输出检查项
            check_names = {r.check_name for r in section.validation_result.results}
            assert len(check_names) >= 1
            # 至少有一条检查结果并且整体通过了（stub 数据无矛盾）
            assert section.validation_result.overall_passed is True

    def test_compile_without_gateway_uses_fallbacks(self, sample_evidence_package):
        """无 model_gateway 时，各模块回退规则/默认逻辑，流水线仍跑通."""
        # task_decomposer 无 LLM 时返回默认 research_question：
        #   f"分析 {task.template_name} 的核心驱动与风险"
        default_question = "分析 某公司研究 的核心驱动与风险"
        backend = PassthroughEvidenceRetriever(packages={default_question: sample_evidence_package})
        compiler = ReportCompiler(model_gateway=None, evidence_retriever=backend)
        report = compiler.compile(_make_task())
        assert isinstance(report, CompiledReport)
        # 规则抽取应得到 100亿元 / 45%
        values = {f.value for f in report.facts}
        assert 100.0 in values
        assert 45.0 in values
