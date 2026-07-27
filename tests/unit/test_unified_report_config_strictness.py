"""Strict contract tests for the unified report-project configuration model."""

import pytest

from app.api.main import app
from reporting.projects.generation import (
    iter_placeholder_configs,
    parse_prompt_templates,
    resolve_markdown_prompt_template,
)
from reporting.projects.plan import compile_report_plan
from reporting.templates.template_manager import TemplateManager
from reporting.builder.pipeline import UnifiedPipeline


def test_sections_schema_is_rejected():
    """The retired section-list schema must not be translated at runtime."""
    with pytest.raises(ValueError, match="report_config.placeholders"):
        list(iter_placeholder_configs({"sections": [{"key": "legacy"}]}))


def test_prompt_template_must_resolve_from_markdown_library():
    """Inline config cannot synthesize a missing Prompt template."""
    templates = parse_prompt_templates(
        "## 已存在\n\n检索 Query：市场\n\n写作要求：输出一段正文。\n"
    )

    with pytest.raises(ValueError, match="prompt_templates.md"):
        resolve_markdown_prompt_template(
            placeholder="市场回顾",
            config={"prompt_template": "不存在", "query": "不应兜底"},
            templates=templates,
        )


def test_plan_marks_missing_markdown_prompt_as_not_ready():
    """预检应明确提示缺失 Markdown 标题，而非接受 inline query/prompt。"""
    plan = compile_report_plan(
        {
            "placeholders": {
                "市场回顾": {
                    "type": "paragraph",
                    "prompt_template": "不存在",
                    "query": "不应兜底",
                }
            }
        },
        "## 已存在\n\n检索 Query：市场\n\n写作要求：输出一段正文。\n",
    )

    assert plan.ready is False
    assert plan.placeholders[0].prompt_found is False
    assert any("缺少 Prompt 模板 不存在" in warning for warning in plan.warnings)


def test_legacy_templates_api_is_not_registered():
    """Report workbench must not expose the retired /api/templates surface."""
    assert not any(route.path.startswith("/api/templates") for route in app.routes)


def test_legacy_yaml_template_manager_is_closed():
    """Retired YAML template storage must not be scanned or executed."""
    manager = TemplateManager()

    assert manager.list_templates() == []
    with pytest.raises(RuntimeError, match="retired"):
        manager.load_template("weekly_report")


def test_unified_pipeline_rejects_retired_template_strategy():
    """The builder no longer accepts the old YAML-template strategy."""
    pipeline = UnifiedPipeline()

    with pytest.raises(ValueError, match="Unsupported build strategy"):
        pipeline._build(object(), "template", None)
