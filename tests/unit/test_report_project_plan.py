"""Tests for compiled report project generation plans."""

from __future__ import annotations

from reporting.projects.plan import compile_report_plan


def test_compile_report_plan_marks_data_template_evidence_retrieval_ready():
    """Compiled plans should mirror the explicit data-template paragraph config."""
    report_config = {
        "defaults": {
            "retrieval": {
                "mode": "hybrid",
                "top_k": 6,
                "candidate_k": 24,
            },
        },
        "placeholders": {
            "summary": {
                "type": "paragraph",
                "mode": "evidence_ai",
                "title": "人工智能",
                "prompt_template": "AI",
                "retrieval": {"keywords": ["人工智能"]},
            },
            "period_end": {
                "type": "field",
                "title": "结束日期",
                "source": {"kind": "report_period", "field": "end_date"},
            },
            "market_review": {
                "type": "paragraph",
                "mode": "data_template_plus_evidence_ai",
                "title": "A股市场回顾",
                "prompt_template": "市场",
                "components": [
                    {
                        "type": "llm_writing",
                        "retrieval": {"keywords": ["上证指数", "成交额"]},
                    },
                ],
            },
        },
    }
    prompt_source = "\n\n".join(
        [
            "## AI\n检索 Query：人工智能\n\n写作要求：写一段周报正文。",
            "## 市场\n检索 Query：A股市场\n\n写作要求：结合底稿与新闻材料。",
        ]
    )

    plan = compile_report_plan(
        report_config,
        prompt_source,
        report_date="2026-07-03",
        lookback_days=10,
        data_scope="uploaded",
    )

    assert plan.ready is True
    assert plan.report_period.end_date == "2026-07-03"
    assert plan.lookback_days == 10
    by_placeholder = {item.placeholder: item for item in plan.placeholders}
    assert by_placeholder["summary"].prompt_found is True
    assert by_placeholder["summary"].retrieval_config is not None
    assert by_placeholder["summary"].retrieval_config.must_any == ["人工智能"]
    assert by_placeholder["period_end"].deterministic is True
    assert by_placeholder["period_end"].evidence_required is False
    assert by_placeholder["market_review"].prompt_found is True
    assert by_placeholder["market_review"].retrieval_ready is True
    assert by_placeholder["market_review"].retrieval_config is not None
    assert by_placeholder["market_review"].retrieval_config.must_any == ["上证指数", "成交额"]
    assert plan.warnings == []


def test_compile_report_plan_warns_when_evidence_paragraph_lacks_prompt_template():
    """Missing prompt templates should surface before the user starts generation."""
    report_config = {
        "placeholders": {
            "content": {
                "type": "paragraph",
                "title": "缺失模板段落",
                "prompt_template": "缺失模板段落",
                "retrieval": {"keywords": ["ETF"]},
            },
        },
    }

    plan = compile_report_plan(report_config, "", report_date="2026-07-03")

    assert plan.ready is False
    assert len(plan.placeholders) == 1
    placeholder = plan.placeholders[0]
    assert placeholder.placeholder == "content"
    assert placeholder.prompt_template == "缺失模板段落"
    assert placeholder.prompt_found is False
    assert placeholder.retrieval_ready is False
    assert placeholder.warnings == [
        "content: 缺少 Prompt 模板 缺失模板段落",
        "content: 缺少检索关键词或 Query",
    ]
    assert plan.warnings == placeholder.warnings
