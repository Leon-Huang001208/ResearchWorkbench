"""Invalid provenance declarations, budgets and no-authority regression cases."""

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


def fixture(name):
    return copy.deepcopy(next(x for x in VECTORS if x["id"] == name))


def execute(v):
    return execute_atom(v["atom"], v["records_by_kind"], v["parameters"])


@pytest.mark.parametrize(
    "field,value", [("owner_id", "other"), ("rights", "yes"), ("passed", True), ("arbitrary", 1)]
)
def test_unknown_nested_fields_rejected(field, value):
    v = fixture("validate_positions.success")
    v["records_by_kind"]["position"][0][field] = value
    with pytest.raises(PackError, match="record_contract_invalid"):
        execute(v)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True])
def test_invalid_weights(value):
    v = fixture("validate_positions.success")
    v["records_by_kind"]["position"][0]["weight"] = value
    with pytest.raises(PackError):
        execute(v)


def test_duplicate_unknown_positions_and_date_precision():
    v = fixture("validate_positions.success")
    v["records_by_kind"]["position"][1]["security"] = v["records_by_kind"]["position"][0][
        "security"
    ]
    with pytest.raises(PackError, match="duplicate_position"):
        execute(v)
    v = fixture("validate_positions.success")
    v["records_by_kind"]["position"][0]["security"]["market"] = "OTHER"
    with pytest.raises(PackError, match="universe_mismatch"):
        execute(v)
    v["parameters"]["as_of"] = "2026-01-12"
    with pytest.raises(PackError, match="as_of_precision_required"):
        execute(v)


@pytest.mark.parametrize("field", ["basis", "currency", "unit", "report_period", "attribution"])
def test_expectation_mismatches_never_pair(field):
    v = fixture("compare_qualified_expectations.success")
    for r in v["records_by_kind"]["forecast"]:
        r[field] = (
            "single-quarter"
            if field == "basis" and r[field] == "cumulative"
            else ("cumulative" if field == "basis" else "other")
        )
    result = execute(v)
    assert not result["rows"]
    assert result["status"] == "insufficient_data"


def test_future_and_unknown_disclosure():
    v = fixture("compare_qualified_expectations.success")
    v["records_by_kind"]["actual"][0]["disclosed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(PackError, match="future_data"):
        execute(v)
    v = fixture("compare_qualified_expectations.success")
    v["records_by_kind"]["actual"][0]["origin"]["published_at"] = None
    with pytest.raises(PackError, match="disclosure_time_unknown"):
        execute(v)


def test_late_vintage_and_ambiguous_consensus():
    v = fixture("compare_qualified_expectations.success")
    actual = v["records_by_kind"]["actual"][0]
    for f in v["records_by_kind"]["forecast"]:
        f["vintage_at"] = actual["disclosed_at"]
    r = execute(v)
    assert not r["rows"]
    assert r["rejected_rows"]
    v = fixture("compare_qualified_expectations.success")
    f = copy.deepcopy(v["records_by_kind"]["forecast"][0])
    f["row_id"] = "conflict"
    f["value"] += 3
    v["records_by_kind"]["forecast"].append(f)
    with pytest.raises(PackError, match="ambiguous_consensus"):
        execute(v)


def test_full_positions_tail_and_projection():
    base = fixture("validate_positions.success")
    row = base["records_by_kind"]["position"][0]
    records, universe = [], []
    for i in range(1000):
        r = copy.deepcopy(row)
        r["row_id"] = str(i)
        r["security"]["security_id"] = f"SYN:{i}"
        r["weight"], r["weight_unit"] = 0.0005, "fraction"
        records.append(r)
        universe.append(r["security"])
    p = {"as_of": base["parameters"]["as_of"], "target_weight": 1, "expected_universe": universe}
    r = execute_atom("validate_positions", {"position": records}, p)
    assert r["metrics"]["known_weight"] == 0.5
    assert r["processed_input_rows"] == 1000
    assert len(r["rows"]) == 128
    assert r["row_delivery"]["omitted_output_rows"] == 872
    records[-1]["weight"] = 0.25
    assert execute_atom("validate_positions", {"position": records}, p)["metrics"][
        "known_weight"
    ] == pytest.approx(0.7495)


def test_row_budget_rejected_before_processing():
    v = fixture("validate_positions.success")
    v["records_by_kind"]["position"] = [v["records_by_kind"]["position"][0]] * 50001
    with pytest.raises(PackError, match="workload_too_large"):
        execute(v)


def test_complete_output_budget_no_truncating_missing():
    v = fixture("validate_positions.success")
    v["records_by_kind"] = {}
    v["parameters"]["expected_universe"] = [
        dict(v["parameters"]["expected_universe"][0], security_id="SYN:" + str(i) + "x" * 1000)
        for i in range(100)
    ]
    with pytest.raises(PackError, match="workload_too_large"):
        execute(v)


def test_risk_scope_join_boundaries_and_missing_category():
    v = fixture("join_risk_windows.success")
    securities = [
        v["records_by_kind"]["risk-event"][0]["security"],
        dict(v["records_by_kind"]["risk-event"][0]["security"], security_id="SYN:B"),
    ]
    p = v["parameters"]
    p.pop("required_categories")
    p["positions"] = securities
    p["category_coverage"] = [
        {
            "security": s,
            "category": category,
            "source_ref": "declared-only",
            "exhaustive": True,
            "window_start": p["window_start"],
            "window_end": p["window_end"],
        }
        for s in securities
        for category in ("risk", "unlock", "insider")
    ]
    r = execute(v)
    assert r["metrics"]["joined_events"] == 2
    assert r["host_qualification"] == "NOT_RUN"
    p["category_coverage"] = [x for x in p["category_coverage"] if x["category"] != "unlock"]
    assert execute(v)["status"] == "partial"
    p["category_coverage"] = []
    v["records_by_kind"]["risk-event"] = []
    assert all(x["observation"] == "unknown" for x in execute(v)["rows"])


def test_same_url_new_hash_preserved():
    v = fixture("deduplicate_source_versions.success")
    rows = v["records_by_kind"]["source-version"]
    rows[-1]["url_ref"] = rows[0]["url_ref"]
    rows[-1]["content_sha256"] = "f" * 64
    assert execute(v)["metrics"]["version_groups"] == len({r["content_sha256"] for r in rows})


def test_valuation_duplicate_dates_and_invalid_pe():
    v = fixture("compare_valuation_samples.success")
    rows = v["records_by_kind"]["valuation"]
    rows[2]["observation_at"] = rows[1]["observation_at"]
    rows[2]["value"] = rows[1]["value"] + 1
    with pytest.raises(PackError, match="conflicting_sample_date"):
        execute(v)
    v = fixture("compare_valuation_samples.success")
    v["records_by_kind"]["valuation"][0]["value"] = 0
    with pytest.raises(PackError, match="nonpositive_current_pe"):
        execute(v)


def test_pack_does_not_accept_self_asserted_rights():
    with pytest.raises(PackError):
        execute_pack("research-prep", {}, {"as_of": "2026-01-12T00:00:00Z", "passed": True})
    with pytest.raises(PackError):
        execute_pack(
            "research-prep",
            {},
            {"as_of": "2026-01-12T00:00:00Z"},
            source_coverage={
                "original_materials": {"source_ref": "x", "exhaustive": True, "rights": True}
            },
        )


def test_event_no_return_algorithm_execution():
    v = fixture("align_event_trading_day.success")
    r = execute_pack(
        "event-review",
        v["records_by_kind"],
        {
            "as_of": v["parameters"]["as_of"],
            "align_event_trading_day": {k: x for k, x in v["parameters"].items() if k != "as_of"},
        },
    )
    assert r["status"] == "partial"
    assert r["metrics"]["blocked_components"]
    assert r["research_quality"] == "NOT_RUN"


def test_receipt_reproducible_parameters_and_inputs_digest():
    v = fixture("validate_positions.success")
    r = execute(v)
    assert r["parameters"]["target_weight"] == v["parameters"]["target_weight"]
    assert r["parameters"]["expected_universe"]["item_count"] == 2
    assert len(r["input_sha256"]) == 64
    assert r["method_source_binding"] == "host_required"


def test_disjoint_holding_totals_and_overcoverage():
    v = fixture("disclosed_ownership.success")
    v["parameters"]["disjoint_holder_ids"] = [
        v["records_by_kind"]["holder-disclosure"][0]["holder_id"]
    ]
    r = execute(v)
    assert r["metrics"]["period_totals"][-1]["shares"] == 30
    assert r["metrics"]["period_totals"][-1]["disclosed_float_fraction"] == 0.3
    v["records_by_kind"]["holder-disclosure"][-1]["shares"] = 110
    r = execute(v)
    assert r["metrics"]["period_totals"][-1]["disclosed_float_fraction"] is None
    assert any(x["code"] == "aggregate_overcoverage" for x in r["missing"])


def test_alignment_future_window_price_cannot_sneak_same_day():
    v = fixture("align_event_trading_day.success")
    v["parameters"]["as_of"] = "2026-01-12T01:00:00Z"
    # Fixture origins are already before cutoff; the Jan12 close has not happened.
    with pytest.raises(PackError, match="future_data"):
        execute(v)


def test_forecast_batch_symbol_budget():
    v = fixture("compare_qualified_expectations.success")
    base = v["records_by_kind"]["forecast"][0]
    records = []
    for i in range(51):
        row = copy.deepcopy(base)
        row["row_id"] = str(i)
        row["security"]["security_id"] = f"SYN:{i}"
        records.append(row)
    v["records_by_kind"] = {"forecast": records}
    with pytest.raises(PackError, match="workload_too_large"):
        execute(v)


@pytest.mark.parametrize("field,value", [("unit", "HKD_per_share"), ("adjustment", "none")])
def test_alignment_rejects_mixed_price_contract(field, value):
    v = fixture("align_event_trading_day.success")
    v["records_by_kind"]["daily-price"][0][field] = value
    with pytest.raises(PackError):
        execute(v)


def test_calendar_wrong_period_and_future_actual():
    v = fixture("earnings_calendar.success")
    v["records_by_kind"]["report-calendar"][0]["report_period"] = "2024FY"
    with pytest.raises(PackError, match="report_period_mismatch"):
        execute(v)
    v = fixture("earnings_calendar.success")
    v["records_by_kind"]["report-calendar"][0]["actual_disclosed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(PackError, match="future_data"):
        execute(v)


def test_empty_sources_are_unknown_and_not_complete():
    r = execute_atom("deduplicate_source_versions", {}, {"as_of": "2026-01-12T00:00:00Z"})
    assert r["status"] == "insufficient_data"
    assert r["missing"]


def test_preallocation_series_limit():
    v = fixture("compare_valuation_samples.success")
    v["records_by_kind"]["valuation"] = v["records_by_kind"]["valuation"] * 1001
    with pytest.raises(PackError, match="workload_too_large"):
        execute(v)


def test_empty_risk_source_scope_can_only_claim_observed_no_match():
    v = fixture("validate_positions.success")
    positions = v["parameters"]["expected_universe"]
    coverage = [
        {
            "security": s,
            "category": c,
            "source_ref": "declared-query",
            "exhaustive": True,
            "window_start": "2026-01-01",
            "window_end": "2026-01-12",
        }
        for s in positions
        for c in ("risk", "unlock", "insider")
    ]
    records = v["records_by_kind"] | {"risk-event": []}
    r = execute_pack(
        "position-risk",
        records,
        {
            "as_of": v["parameters"]["as_of"],
            "validate_positions": {k: x for k, x in v["parameters"].items() if k != "as_of"},
            "join_risk_windows": {
                "positions": positions,
                "window_start": "2026-01-01",
                "window_end": "2026-01-12",
                "category_coverage": coverage,
            },
        },
    )
    assert r["metrics"]["subresults_executed"] == 2
    risk = r["rows"][1]["result"]
    assert all(x["observation"] == "observed_no_match" for x in risk["rows"])
    assert risk["host_qualification"] == "NOT_RUN"
    assert r["status"] == "partial"


@pytest.mark.parametrize("stamp", ["20260112T00:00:00Z", "2026-01-12 00:00:00+00:00"])
def test_noncanonical_instant_rejected(stamp):
    v = fixture("validate_positions.success")
    v["parameters"]["as_of"] = stamp
    with pytest.raises(PackError):
        execute(v)


@pytest.mark.parametrize("mode", ["empty", "omit_unknown_weight", "omit_missing_position"])
def test_spec_risk_cannot_shrink_authoritative_position_universe(mode):
    v = fixture(
        "validate_positions.success"
        if mode == "empty"
        else (
            "validate_positions.missing-weight"
            if mode == "omit_unknown_weight"
            else "validate_positions.missing"
        )
    )
    universe = v["parameters"]["expected_universe"]
    risk_positions = [] if mode == "empty" else universe[:1]
    parameters = {
        "as_of": v["parameters"]["as_of"],
        "validate_positions": {
            key: value for key, value in v["parameters"].items() if key != "as_of"
        },
        "join_risk_windows": {
            "positions": risk_positions,
            "category_coverage": [],
            "window_start": "2026-01-01",
            "window_end": "2026-01-12",
        },
    }
    coverage = {
        key: {"source_ref": key, "exhaustive": True}
        for key in ("positions", "risk", "unlock", "insider")
    }
    with pytest.raises(PackError, match="risk_universe_mismatch"):
        execute_pack(
            "position-risk",
            v["records_by_kind"] | {"risk-event": []},
            parameters,
            source_coverage=coverage,
        )


def multiplied_expectations(actual_count=25, forecast_count=25):
    v = fixture("compare_qualified_expectations.success")
    actual = v["records_by_kind"]["actual"][0]
    forecast = v["records_by_kind"]["forecast"][0]
    actuals, forecasts = [], []
    for i in range(actual_count):
        r = copy.deepcopy(actual)
        r["row_id"] = f"actual-{i}"
        r["disclosed_at"] = f"2026-01-10T00:{i:02d}:00Z"
        actuals.append(r)
    for i in range(forecast_count):
        r = copy.deepcopy(forecast)
        r["row_id"] = f"forecast-{i}"
        r["consensus_id"] = f"independent-series-{i}"
        r["vintage_at"] = "2026-01-05T00:00:00Z"
        forecasts.append(r)
    v["records_by_kind"] = {"actual": actuals, "forecast": forecasts}
    return v


def test_spec_derived_cardinality_rejected_before_arithmetic(monkeypatch):
    from app.research_web.scenarios.packs import atoms, contracts

    # Fifty accepted inputs imply 625 results. Lower only the budget for a cheap sentinel.
    monkeypatch.setattr(contracts, "MAX_DERIVED_ROWS", 512, raising=False)
    calls = []
    original = atoms.number

    def spy(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(atoms, "number", spy)
    with pytest.raises(PackError, match="workload_too_large"):
        execute(multiplied_expectations())
    assert calls == []


def test_spec_derived_bytes_stop_during_generation(monkeypatch):
    from app.research_web.scenarios.packs import atoms, contracts

    monkeypatch.setattr(contracts, "MAX_DERIVED_BYTES", 512, raising=False)
    calls = []
    original = atoms.number

    def spy(value):
        calls.append(value)
        return original(value)

    monkeypatch.setattr(atoms, "number", spy)
    with pytest.raises(PackError, match="workload_too_large"):
        execute(multiplied_expectations())
    assert len(calls) < 25


def test_spec_ownership_periods_are_chronological():
    v = fixture("disclosed_ownership.success")
    v["parameters"]["report_periods"].reverse()
    r = execute(v)
    by_period = {row["report_period"]: row for row in r["rows"]}
    assert by_period["2025Q2"]["change_shares"] is None
    assert by_period["2025Q3"]["change_shares"] == 10


@pytest.mark.parametrize("periods", [["unknown", "2025Q3"], ["2025Q0"], ["2025Q4", "2025FY"]])
def test_spec_unknown_or_ambiguous_period_order_rejected(periods):
    v = fixture("disclosed_ownership.success")
    v["parameters"]["report_periods"] = periods
    with pytest.raises(PackError, match="report_periods_invalid"):
        execute(v)


def test_spec_missing_holder_period_is_explicit_and_not_zero():
    v = fixture("disclosed_ownership.success")
    v["records_by_kind"]["holder-disclosure"] = v["records_by_kind"]["holder-disclosure"][:1]
    holder = v["records_by_kind"]["holder-disclosure"][0]["holder_id"]
    v["parameters"]["disjoint_holder_ids"] = [holder]
    r = execute(v)
    assert r["status"] == "partial"
    assert any(
        x["code"] == "holder_period_missing"
        and x["holder_id"] == holder
        and x["report_period"] == "2025Q3"
        for x in r["missing"]
    )
    assert all(x["report_period"] != "2025Q3" for x in r["rows"])


def test_spec_ownership_does_not_bridge_missing_requested_period():
    v = fixture("disclosed_ownership.success")
    v["parameters"]["report_periods"] = ["2025Q1", "2025Q2", "2025Q3"]
    v["records_by_kind"]["holder-disclosure"][0]["report_period"] = "2025Q1"
    r = execute(v)
    assert next(x for x in r["rows"] if x["report_period"] == "2025Q3")["change_shares"] is None
    assert any(
        x["code"] == "holder_period_missing" and x["report_period"] == "2025Q2"
        for x in r["missing"]
    )


def test_spec_older_conflicting_vintage_cannot_hide_behind_newer_consensus():
    v = fixture("compare_qualified_expectations.success")
    f = copy.deepcopy(v["records_by_kind"]["forecast"][0])
    f["row_id"], f["vintage_at"] = "old-conflict-a", "2025-12-01T00:00:00Z"
    g = copy.deepcopy(f)
    g["row_id"], g["value"] = "old-conflict-b", f["value"] + 5
    # Origins describe these earlier forecast publications explicitly.
    for row in (f, g):
        row["origin"]["published_at"] = row["origin"]["observed_at"] = row["vintage_at"]
    v["records_by_kind"]["forecast"].extend([f, g])
    with pytest.raises(PackError, match="ambiguous_consensus"):
        execute(v)
