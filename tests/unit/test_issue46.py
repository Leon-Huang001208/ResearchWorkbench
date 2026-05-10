"""
Issue #46 单元测试 - 模板化研报生成.

Tests for:
- Template management
- Fact card building
- Report validation
- Word/Excel output
- Report pipeline
"""
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from core.contracts import (
    FactCard,
    ReportTask,
    SectionOutput,
    SectionSpec,
    ValidationResults,
)
from reporting.composer.fact_card_builder import FactCardBuilder
from reporting.composer.report_pipeline import ReportPipeline
from reporting.composer.validator import ReportValidator
from reporting.templates.template_manager import TemplateManager


class TestTemplateManager:
    """测试模板管理器."""

    def test_list_templates(self):
        """测试列出模板."""
        manager = TemplateManager()
        templates = manager.list_templates()
        # Should have at least the weekly report template
        assert isinstance(templates, list)

    def test_create_weekly_report_template(self):
        """测试创建周报模板."""
        manager = TemplateManager()

        template = manager.create_weekly_report_template()
        assert template.name == "weekly_report"
        assert len(template.sections) == 5

    def test_template_section_parsing(self):
        """测试模板段落解析."""
        manager = TemplateManager()
        template = manager.create_weekly_report_template()

        assert template.sections[0].key == "market_summary"
        assert template.sections[0].title == "市场概览"
        assert template.sections[0].target_words == 300


class TestFactCardBuilder:
    """测试 Fact Card 构建器."""

    def test_build_empty_fact_card(self):
        """测试构建空 Fact Card."""
        builder = FactCardBuilder()
        fact_card = builder.build_fact_card([])

        assert isinstance(fact_card, FactCard)
        assert len(fact_card.key_changes) == 0

    def test_build_fact_card_from_evidence(self):
        """测试从证据构建 Fact Card."""
        builder = FactCardBuilder()

        evidence = [
            {
                "source": "财联社",
                "content": "市场大幅上涨，成交量显著增加。",
            },
            {
                "source": "中国证券网",
                "content": "政策利好推动行业发展。",
            },
        ]

        fact_card = builder.build_fact_card(evidence)
        assert isinstance(fact_card, FactCard)

    def test_fact_card_rule_based_extraction(self):
        """测试规则提取 Fact Card."""
        builder = FactCardBuilder()

        evidence = [
            {
                "source": "Test",
                "content": "股价上涨了5%。由于利好政策，市场表现强劲。",
            },
        ]

        fact_card = builder.build_fact_card(evidence)
        assert isinstance(fact_card, FactCard)

    def test_quick_check(self):
        """测试快速检查."""
        validator = ReportValidator()

        # Test with good content
        assert validator.quick_check("这是一段正常的内容。") is True

        # Test with too short content
        assert validator.quick_check("") is False

        # Test with repetitive garbage
        assert validator.quick_check("aaaaa") is False


class TestReportValidator:
    """测试报告校验器."""

    def test_validate_word_count(self):
        """测试词数校验."""
        validator = ReportValidator()

        spec = SectionSpec(
            key="test",
            title="Test",
            target_words=200,
        )

        content = "这是一段测试内容。" * 20  # Should be around 100 chars

        results = validator.validate_section(content, spec)
        assert isinstance(results, ValidationResults)

    def test_check_forbidden_terms(self):
        """测试禁用词检查."""
        validator = ReportValidator()

        validator.set_default_forbidden_terms(["绝对", "肯定"])

        spec = SectionSpec(
            key="test",
            title="Test",
            target_words=100,
            forbidden_terms=["垃圾"],
        )

        content = "这绝对是肯定正确的。"
        results = validator.validate_section(content, spec)

        # Should have found forbidden terms
        assert any(r.check_name == "forbidden_terms" for r in results.results)

    def test_check_objectivity(self):
        """测试客观性检查."""
        validator = ReportValidator()

        spec = SectionSpec(
            key="test",
            title="Test",
            target_words=100,
        )

        subjective_content = "我认为这绝对是最好的。"
        results = validator.validate_section(subjective_content, spec)

        assert any(r.check_name == "objectivity" for r in results.results)

    def test_check_required_facets(self):
        """测试必填方面检查."""
        validator = ReportValidator()

        spec = SectionSpec(
            key="test",
            title="Test",
            target_words=100,
            required_facets=["大盘", "成交量"],
        )

        content = "市场平静。"  # Missing required facets
        results = validator.validate_section(content, spec)

        assert any(r.check_name == "required_facets" for r in results.results)

    def test_word_count_function(self):
        """测试词数计算函数."""
        validator = ReportValidator()

        # Chinese text
        count = validator._count_words("这是一段中文文本。")
        assert count > 0

        # English text
        count = validator._count_words("This is a test.")
        assert count > 0

        # Mixed
        count = validator._count_words("这是 mixed 文本。")
        assert count > 0


class TestReportPipeline:
    """测试报告生成流水线."""

    def test_create_report_task(self):
        """测试创建报告任务."""
        pipeline = ReportPipeline()

        task = pipeline.create_report_task(
            "weekly_report",
            {"market": "A-share", "week": "2024-W20"},
        )

        assert isinstance(task, ReportTask)
        assert task.task_id is not None
        assert task.template_name == "weekly_report"
        assert task.status == "pending"

    def test_save_markdown_report(self):
        """测试保存 Markdown 报告."""
        with TemporaryDirectory() as tmpdir:
            pipeline = ReportPipeline()

            # Create simple sections
            from core.contracts import SectionOutput

            sections = [
                SectionOutput(
                    key="market_summary",
                    title="市场概览",
                    content="本周市场表现良好。",
                ),
            ]

            output_path = Path(tmpdir) / "report.md"
            pipeline.save_report(output_path, "测试报告", sections)

            assert output_path.exists()

    def test_create_run_log(self):
        """测试创建运行日志."""
        pipeline = ReportPipeline()


        task = pipeline.create_report_task("weekly_report", {})
        sections = [
            SectionOutput(
                key="test",
                title="Test",
                content="Test content",
                warnings=["Warning 1"],
            ),
        ]

        run_log = pipeline.create_run_log(task, sections)

        assert run_log.task_id == task.task_id
        assert run_log.template_name == "weekly_report"
        assert "test" in run_log.sections_log


class TestIntegration:
    """集成测试."""

    def test_template_validation_workflow(self):
        """测试模板验证工作流."""
        manager = TemplateManager()

        template = manager.create_weekly_report_template()
        assert len(template.sections) > 0

        # Check that sections have required fields
        for section in template.sections:
            assert section.key is not None
            assert section.title is not None
            assert section.target_words > 0

    def test_simple_fact_extraction_and_validation(self):
        """测试简单事实提取和校验."""
        builder = FactCardBuilder()
        validator = ReportValidator()

        evidence = [
            {"source": "Test", "content": "市场上涨了3%，成交量增加。"},
        ]

        fact_card = builder.build_fact_card(evidence)

        spec = SectionSpec(
            key="test",
            title="Test",
            target_words=100,
        )

        # Create content from fact card
        content = " ".join(fact_card.key_changes) if fact_card.key_changes else "No content"
        results = validator.validate_section(content, spec)

        assert isinstance(results, ValidationResults)


@pytest.mark.parametrize(
    "forbidden_terms,content,should_fail",
    [
        (["绝对"], "这绝对不行。", True),
        (["绝对"], "这可能不行。", False),
        ([], "正常内容。", False),
    ],
)
def test_forbidden_terms_parametrized(forbidden_terms, content, should_fail):
    """参数化测试禁用词检查."""
    validator = ReportValidator()
    validator.set_default_forbidden_terms(forbidden_terms)

    spec = SectionSpec(
        key="test",
        title="Test",
        target_words=100,
    )

    results = validator.validate_section(content, spec)

    forbidden_result = next((r for r in results.results if r.check_name == "forbidden_terms"), None)

    if should_fail:
        assert forbidden_result is not None
        assert not forbidden_result.passed
    else:
        if forbidden_result:
            assert forbidden_result.passed
