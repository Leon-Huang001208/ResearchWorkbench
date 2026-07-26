"""Tests for the unified report configuration runtime contract."""

import logging

import pytest

from reporting.projects.unified_config import (
    UnifiedReportConfigError,
    parse_unified_report_config,
)


def test_unified_config_preserves_v1_semantics_and_optional_rendering():
    """The unified V1-shaped config retains generation and rendering semantics."""
    raw = {
        "name": "周报",
        "meta": {"project_note": "V1 extension, not a V2 template"},
        "assets": {"prompt_templates": "prompt_templates.md"},
        "defaults": {"retrieval": {"top_k": 10}},
        "validators": {"forbidden_terms": ["保本"]},
        "components": {"disclaimer": {"type": "static"}},
        "retrieval": {"mode": "hybrid"},
        "charts": {"市场走势": {"type": "line"}},
        "tables": {"重要日程": {"columns": ["日期"]}},
        "placeholders": {
            "市场回顾": {
                "type": "paragraph",
                "prompt_template": "市场回顾",
                "retrieval": {"keywords": ["A股"]},
                "rendering": {
                    "paragraph_style": "正文",
                    "runs": [{"text": "市场：", "bold": True}],
                    "visible_if": "{{ include_market_review }}",
                    "chart_grid": {"rows": 2, "cols": 2},
                },
            }
        },
    }
    config = parse_unified_report_config(raw)

    placeholder = config.placeholders["市场回顾"]
    assert placeholder.prompt_template == "市场回顾"
    assert placeholder.retrieval == {"keywords": ("A股",)}
    assert placeholder.rendering.paragraph_style == "正文"
    assert tuple(placeholder.rendering.runs) == ({"text": "市场：", "bold": True},)
    assert placeholder.rendering.visible_if == "{{ include_market_review }}"
    assert placeholder.rendering.chart_grid == {"rows": 2, "cols": 2}
    assert config.defaults == {"retrieval": {"top_k": 10}}
    assert config.validators == {"forbidden_terms": ("保本",)}
    assert config.components == {"disclaimer": {"type": "static"}}
    assert config.charts == {"市场走势": {"type": "line"}}
    assert config.tables == {"重要日程": {"columns": ("日期",)}}

    serialized = config.to_generation_dict()
    assert serialized["defaults"] == raw["defaults"]
    assert serialized["validators"] == raw["validators"]
    assert serialized["components"] == raw["components"]
    assert serialized["retrieval"] == raw["retrieval"]
    assert serialized["charts"] == raw["charts"]
    assert serialized["tables"] == raw["tables"]
    assert serialized["placeholders"]["市场回顾"] == raw["placeholders"]["市场回顾"]
    assert "## 市场回顾" not in str(serialized)


def test_unified_config_isolates_input_and_serialized_output():
    """Parsed config is immutable and detached from both input and returned mappings."""
    raw = {
        "defaults": {"retrieval": {"top_k": 10}},
        "placeholders": {"市场回顾": {"retrieval": {"keywords": ["A股"]}}},
    }
    config = parse_unified_report_config(raw)

    raw["defaults"]["retrieval"]["top_k"] = 99
    raw["placeholders"]["市场回顾"]["retrieval"]["keywords"].append("港股")
    first_output = config.to_generation_dict()
    first_output["defaults"]["retrieval"]["top_k"] = 88
    first_output["placeholders"]["市场回顾"]["retrieval"]["keywords"].append("美股")

    assert config.defaults["retrieval"]["top_k"] == 10
    assert config.placeholders["市场回顾"].retrieval["keywords"] == ("A股",)
    assert config.to_generation_dict() == {
        "defaults": {"retrieval": {"top_k": 10}},
        "placeholders": {"市场回顾": {"retrieval": {"keywords": ["A股"]}}},
    }
    with pytest.raises(TypeError):
        config.defaults["retrieval"]["top_k"] = 1


@pytest.mark.parametrize("rendering", [{}, {"paragraph_style": None}])
def test_unified_config_preserves_explicit_empty_rendering_blocks(rendering):
    """Present rendering blocks are retained even when all optional values are empty."""
    config = parse_unified_report_config(
        {"placeholders": {"正文": {"type": "paragraph", "rendering": rendering}}}
    )

    assert config.to_generation_dict()["placeholders"]["正文"]["rendering"] == rendering


def test_unified_config_logs_source_path_for_invalid_raw(caplog):
    """Parse errors include the supplied YAML source path in project logs."""
    source_path = "/tmp/broken-report-config.yaml"
    caplog.set_level(logging.ERROR, logger="reporting.projects.unified_config")

    with pytest.raises(UnifiedReportConfigError, match="根节点"):
        parse_unified_report_config([], source_path=source_path)

    assert source_path in caplog.text


def test_unified_config_rejects_unmigrated_v2_shape():
    """The runtime parser never treats the legacy V2 schema as a fallback."""
    with pytest.raises(UnifiedReportConfigError, match="迁移"):
        parse_unified_report_config({"meta": {}, "template": {}, "placeholders": {}})
