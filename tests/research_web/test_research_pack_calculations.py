"""Independent hand-calculated expectations; no provider/model execution."""

import copy
import json
from pathlib import Path

import pytest

from app.research_web.scenarios.packs import PackError, execute_atom, execute_pack

VECTORS = json.loads(
    (
        Path(__file__).parents[2] / "app/research_web/scenarios/packs/synthetic_vectors.json"
    ).read_text()
)


def vector(name):
    return copy.deepcopy(next(v for v in VECTORS if v["id"] == name))


def run(name):
    v = vector(name)
    return execute_atom(v["atom"], v["records_by_kind"], v["parameters"])


def test_positions_hand_calculated():
    result = run("validate_positions.success")
    assert result["metrics"]["known_weight"] == 1
    assert result["metrics"]["unknown_weight"] == 0
    assert run("validate_positions.missing")["metrics"]["unknown_weight"] == pytest.approx(0.4)
    assert run("validate_positions.missing-weight")["metrics"]["unweighted_count"] == 1


def test_expectation_hand_calculated():
    r = run("compare_qualified_expectations.success")
    assert r["rows"][0]["absolute_low"] == 20
    assert r["rows"][0]["relative_low"] == 0.2
    r = run("compare_qualified_expectations.range")
    assert r["rows"][0]["absolute_low"] == -10
    assert r["rows"][0]["absolute_high"] == 10
    assert all(
        x["relative_low"] is None
        for x in run("compare_qualified_expectations.zero-negative")["rows"]
    )


def test_valuation_ties_and_alignment_close_rule():
    assert run("compare_valuation_samples.success")["metrics"]["percentile_interval"] == [
        0.25,
        0.75,
    ]
    assert run("compare_valuation_samples.missing")["status"] == "insufficient_data"
    r = run("align_event_trading_day.success")
    assert r["metrics"]["event_date"] == "2026-01-12"
    assert r["metrics"]["return_algorithm"] == "comparison_receipt_required"


def test_source_dedupe_and_limited_packs():
    r = run("deduplicate_source_versions.success")
    assert r["metrics"]["version_groups"] < r["processed_input_rows"]
    assert run("sentiment_counts.success")["rows"][0]["up_ratio"] == 0.4
    assert run("disclosed_ownership.success")["metrics"]["total_shares"] > 0
    assert run("earnings_calendar.success")["metrics"]["disclosed_fraction"] == 0.5


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: v["id"])
def test_all_vectors_run_with_explicit_boundary(v):
    if v["atom"] == "join_risk_windows":
        # v2 complete strings are not a qualified scope assertion.
        with pytest.raises(PackError):
            execute_atom(v["atom"], v["records_by_kind"], v["parameters"])
        return
    r = execute_atom(v["atom"], v["records_by_kind"], v["parameters"])
    assert r["research_quality"] == "NOT_RUN"
    assert r["host_qualification"] == "NOT_RUN"
    assert r["row_delivery"]["total_output_rows"] >= len(r["rows"])


def test_all_nine_missing_packs_are_runnable():
    for pack in (
        "position-risk",
        "expectation-gap",
        "short-sentiment",
        "research-prep",
        "event-review",
        "global-opinion",
        "valuation-check",
        "ownership-structure",
        "earnings-preview",
    ):
        r = execute_pack(pack, {}, {"as_of": "2026-01-12T23:59:59Z"})
        assert r["status"] in ("partial", "insufficient_data")
        assert r["missing"]
        assert r["host_qualification"] == "NOT_RUN"


@pytest.mark.parametrize(
    "pack,method,case",
    [
        (
            "expectation-gap",
            "compare_qualified_expectations",
            "compare_qualified_expectations.success",
        ),
        ("short-sentiment", "sentiment_counts", "sentiment_counts.success"),
        ("research-prep", "deduplicate_source_versions", "deduplicate_source_versions.success"),
        ("event-review", "align_event_trading_day", "align_event_trading_day.success"),
        ("global-opinion", "deduplicate_source_versions", "deduplicate_source_versions.success"),
        ("valuation-check", "compare_valuation_samples", "compare_valuation_samples.success"),
        ("ownership-structure", "disclosed_ownership", "disclosed_ownership.success"),
        ("earnings-preview", "earnings_calendar", "earnings_calendar.success"),
    ],
)
def test_pack_runs_real_subcalculation(pack, method, case):
    v = vector(case)
    r = execute_pack(
        pack,
        v["records_by_kind"],
        {
            "as_of": v["parameters"]["as_of"],
            method: {k: x for k, x in v["parameters"].items() if k != "as_of"},
        },
    )
    assert r["metrics"]["subresults_executed"] == 1
    assert r["rows"][0]["result"]["method"] == method
    assert r["rows"][0]["result"]["processed_input_rows"] > 0
    assert r["status"] == "partial"
    assert r["host_qualification"] == "NOT_RUN"


def test_position_pack_executes_both_methods_and_keeps_unknown_weight():
    v = vector("validate_positions.missing")
    positions = v["parameters"]["expected_universe"]
    r = execute_pack(
        "position-risk",
        v["records_by_kind"],
        {
            "as_of": v["parameters"]["as_of"],
            "validate_positions": {k: x for k, x in v["parameters"].items() if k != "as_of"},
            "join_risk_windows": {
                "positions": positions,
                "window_start": "2026-01-01",
                "window_end": "2026-01-12",
                "category_coverage": [],
            },
        },
    )
    # Empty source rows are evaluated with unknown coverage, never fabricated signals.
    assert r["metrics"]["subresults_executed"] == 2
    assert r["rows"][0]["result"]["metrics"]["unknown_weight"] == pytest.approx(0.4)
    assert any(x.get("component") == "join_risk_windows" for x in r["missing"])
