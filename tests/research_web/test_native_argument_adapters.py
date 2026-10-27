"""Strict compatibility inputs; no supplier aliases or inferred securities."""

import pytest

from app.research_web.scenarios.native_argument_adapters import (
    ArgumentAdapterError,
    adapt_query_news,
    adapt_research_question,
)


def test_news_arguments_preserve_bounded_native_semantics():
    assert adapt_query_news({"query": " 降息 ", "limit": 7}) == {"query": "降息", "limit": 7}
    assert adapt_query_news({}) == {}


@pytest.mark.parametrize(
    "arguments",
    [{"limit": value} for value in [True, False, 1.0, "2", 0, 101, None]]
    + [
        {key: "x"}
        for key in ["url", "days", "stock", "source", "sentiment", "importance", "start_date"]
    ]
    + [{"query": value} for value in [False, None, "x" * 2001, "https://example.org"]],
)
def test_news_rejects_unsupported_inputs(arguments):
    with pytest.raises(ArgumentAdapterError):
        adapt_query_news(arguments)


def test_research_requires_explicit_host_selection():
    with pytest.raises(ArgumentAdapterError, match="missing_selection"):
        adapt_research_question("company_one_pager", {"query": "分析微软"}, None)


@pytest.mark.parametrize(
    "tool,method",
    [
        ("company_one_pager", "owned-company-evidence"),
        ("fundamental_analysis", "owned-company-evidence"),
        ("research_outline", "owned-research-prep"),
    ],
)
def test_question_presets_keep_subject_and_materials_in_host(tool, method):
    selection = {
        "subject": {"kind": "stock", "identity": "MSFT.US"},
        "as_of": "2026-10-27",
        "material_ids": ["web:" + "a" * 24],
        "capability": {"id": method, "version": 1, "sha256": "b" * 64},
    }
    assert adapt_research_question(tool, {"query": "核验公开资料"}, selection) == {
        "capability_id": method,
        "question": "核验公开资料",
    }
    assert selection["subject"]["identity"] == "MSFT.US"
    selection["capability"]["sha256"] = "x" * 64
    with pytest.raises(ArgumentAdapterError, match="missing_selection"):
        adapt_research_question(tool, {"query": "核验公开资料"}, selection)
