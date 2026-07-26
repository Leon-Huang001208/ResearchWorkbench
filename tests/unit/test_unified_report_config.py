"""Tests for the unified report configuration runtime contract."""

import pytest

from reporting.projects.unified_config import (
    UnifiedReportConfigError,
    parse_unified_report_config,
)


def test_unified_config_preserves_prompt_retrieval_and_rendering():
    """The unified V1-shaped config retains generation and rendering semantics."""
    config = parse_unified_report_config(
        {
            "name": "周报",
            "assets": {"prompt_templates": "prompt_templates.md"},
            "placeholders": {
                "市场回顾": {
                    "type": "paragraph",
                    "prompt_template": "市场回顾",
                    "retrieval": {"keywords": ["A股"]},
                    "rendering": {"paragraph_style": "正文"},
                }
            },
        }
    )

    placeholder = config.placeholders["市场回顾"]
    assert placeholder.prompt_template == "市场回顾"
    assert placeholder.retrieval == {"keywords": ["A股"]}
    assert placeholder.rendering.paragraph_style == "正文"


def test_unified_config_rejects_unmigrated_v2_shape():
    """The runtime parser never treats the legacy V2 schema as a fallback."""
    with pytest.raises(UnifiedReportConfigError, match="迁移"):
        parse_unified_report_config({"meta": {}, "template": {}, "placeholders": {}})
