"""Regression for the live GDP report's unregistered arithmetic error."""

import pytest

from app.research_web.research_arithmetic import check_arithmetic


@pytest.mark.parametrize(
    "text",
    [
        "第三产业的43396亿元（808879−765583）增量。",
        "808879 - 765583 = 43396亿元",
    ],
)
def test_live_gdp_difference_is_recomputed_without_model_claims(text):
    rows = check_arithmetic(text)
    assert any(row["status"] == "mismatch" and row["expected"] == "43296" for row in rows)


@pytest.mark.parametrize(
    "text",
    [
        "第三产业的43296亿元（808879−765583）增量。",
        "(1401879-1349084)/1349084*100%=3.91%",
        "-5 + 2 = -3",
        "50% * 200 = 100",
    ],
)
def test_literal_calculations_are_bounded_and_precision_aware(text):
    rows = check_arithmetic(text)
    assert rows and all(row["status"] == "matched" for row in rows)


def test_unsupported_or_unsafe_text_never_executes():
    assert check_arithmetic("__import__('os').system('exit') = 0") == []
    assert check_arithmetic("研究日期2026-10-16，实际增速5.0%。") == []
    assert any(row["status"] == "unverified" for row in check_arithmetic("1 / 0 = 9"))


def test_chain_checks_every_pair_and_sentence_punctuation_and_approximation():
    assert any(row["status"] == "mismatch" for row in check_arithmetic("1+1=4-1=3"))
    assert check_arithmetic("1/3≈33%")[0]["status"] == "matched"
    assert check_arithmetic("3.0-1.0=2.0.")[0]["status"] == "matched"
    assert check_arithmetic("1/3=33%")[0]["status"] == "mismatch"
    assert check_arithmetic("−5亿元（2−7）")[0]["status"] == "matched"
    assert check_arithmetic("1/3≈3/10")[0]["status"] == "unverified"


def test_quality_retains_unregistered_number_gate_even_for_matching_arithmetic():
    from app.research_web.research_quality import assess_quality, make_contract

    text = "第三产业的43396亿元（808879−765583）增量。"
    report = {
        "task_id": "a" * 24,
        "title": "增量",
        "sections": [{"id": "s1", "heading": "增量", "text": text, "citations": []}],
        "sources": [],
        "notes": [],
        "coverage": [],
    }
    result = assess_quality(
        make_contract("a" * 24, "检查增量", ["增量"], "2026-10-16", "deep"), report, []
    )
    assert "numeric_arithmetic_mismatch:s1" in result["issues"]
    assert "numeric_claims_need_independent_review:增量" in result["issues"]
    assert result["status"] != "passed"
