"""Bounded report calculations consume actual scoped primitives, never model values."""

import copy
import hashlib
from decimal import Decimal

import pytest

from app.research_web.research_business_evidence import _emit
from app.research_web.resources.research_report import business_evidence
from app.research_web.resources.research_report_calculations import derive_business_observations


def observation(metric, period, value, *, source="a", unit="亿元", scope="session:task"):
    text = f"{period} {value} {unit}"
    proof = {
        "source_id": "web:" + source * 24,
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
        "offset_unit": "unicode_codepoint",
        "spans": [{"start": 0, "end": len(text), "text": text}],
    }
    return _emit(scope, metric, period, Decimal(value), unit, [proof])


def gdp():
    return [
        observation("gdp_current_price_preliminary", "2025", "1401879"),
        observation("gdp_current_price_final", "2024", "1348066", source="b"),
    ]


def recipe(rows, **overrides):
    return {
        "id": "nominal_growth",
        "operation": "percent_change",
        "operands": [r["id"] for r in rows],
        "decimal_places": 2,
        **overrides,
    }


def test_gdp_rounding_exact_lineage_and_existing_identity_contract():
    rows = gdp()
    recipes = [recipe(rows)]
    before = copy.deepcopy((rows, recipes))
    result = derive_business_observations(rows, recipes, task_id="task-a")
    row = result[0]
    assert row["value"] == "3.99"
    assert row["unit"] == "%"
    assert row["metric"] == "gdp_current_price_percent_change"
    assert row["period"] == "2025"
    assert row["selection_id"] == "$nominal_growth"
    from fractions import Fraction

    assert Fraction(row["exact_value"]) == Fraction(53813, 1348066) * 100
    assert set(row["source_ids"]) == {r["source_id"] for r in rows}
    assert row["proofs"] == sorted([r["proofs"][0] for r in rows], key=lambda p: p["source_id"])
    assert row["sha256"] == hashlib.sha256(row["content"].encode()).hexdigest()
    assert not any(c.isdigit() for c in row["content"].split("\n", 1)[1])
    assert derive_business_observations(rows, recipes, task_id="task-a") == result
    assert (rows, recipes) == before
    assert business_evidence(result, {row["id"]: ["r1"]})["numeric_claims"][0]["value"] == "3.99"
    assert derive_business_observations(rows, recipes, task_id="task-b")[0]["id"] != row["id"]


def test_unique_metric_period_alias_and_scope_binding():
    rows = gdp()
    aliases = [r["metric"] + "@" + r["period"] for r in rows]
    original = derive_business_observations(rows, [recipe(rows, operands=aliases)], task_id="t")[0]
    changed = [
        observation("gdp_current_price_preliminary", "2025", "1401879", scope="other"),
        rows[1],
    ]
    assert (
        derive_business_observations(changed, [recipe(changed, operands=aliases)], task_id="t")[0][
            "scope_sha256"
        ]
        != original["scope_sha256"]
    )
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(
            rows + [observation(rows[0]["metric"], "2025", "1401879", source="c")],
            [recipe(rows, operands=aliases)],
            task_id="t",
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("sha256", "0" * 64),
        ("scope_sha256", "0" * 64),
        ("source_id", "web:" + "f" * 24),
        ("value", "99"),
        ("kind", "business_quote"),
        ("id", "business_" + "0" * 32),
    ],
)
def test_forged_primitive_metadata_rejected(field, value):
    rows = gdp()
    rows[0][field] = value
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(rows, [recipe(rows)], task_id="t")


@pytest.mark.parametrize(
    "overrides",
    [
        {"decimal_places": True},
        {"decimal_places": -1},
        {"decimal_places": 13},
        {"value": "3.99"},
        {"unit": "%"},
        {"id": "a" * 41},
        {"id": "bad.id"},
        {"operation": "eval"},
        {"operands": []},
        {"operands": ["$future"]},
        {"operands": ["unknown"]},
        {"operands": ["1.0", "2.0"]},
    ],
)
def test_bad_recipe_rejected(overrides):
    rows = gdp()
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(rows, [recipe(rows, **overrides)], task_id="t")


@pytest.mark.parametrize("operation", ["ratio", "percent_change"])
def test_cross_metric_and_zero_denominator_rejected(operation):
    rows = gdp()
    for second in [
        observation("gdp_real_growth_final", "2024", "5.0"),
        observation("gdp_current_price_final", "2024", "0"),
    ]:
        inputs = [rows[0], second]
        with pytest.raises(ValueError, match="research_report_calculation_invalid"):
            derive_business_observations(inputs, [recipe(inputs, operation=operation)], task_id="t")


def test_arity_period_units_duplicates_limits_and_derived_operands_rejected():
    rows = gdp()
    cases = [
        ([recipe(rows, operation="difference")], rows),
        ([recipe(rows, operation="sum")], rows),
        ([recipe(rows), recipe(rows)], rows),
        ([recipe(rows)] * 17, rows),
        ([recipe(rows, operation="identity")], rows),
    ]
    mixed = [rows[0], observation("gdp_current_price_final", "2024", "1348066", unit="USD")]
    cases.append(([recipe(mixed)], mixed))
    derived = derive_business_observations(rows, [recipe(rows)], task_id="t")
    cases.append(([recipe(derived, operation="identity")], derived))
    for recipes, inputs in cases:
        with pytest.raises(ValueError, match="research_report_calculation_invalid"):
            derive_business_observations(inputs, recipes, task_id="t")


@pytest.mark.parametrize(
    "operation,expected,unit",
    [
        ("identity", "100.00", "亿元"),
        ("sum", "140.00", "亿元"),
        ("difference", "60.00", "亿元"),
        ("ratio", "2.50", "ratio"),
    ],
)
def test_primitive_operations(operation, expected, unit):
    rows = [observation("revenue", "2025", "100"), observation("revenue", "2025", "40", source="b")]
    selected = rows[:1] if operation == "identity" else rows
    row = derive_business_observations(rows, [recipe(selected, operation=operation)], task_id="t")[
        0
    ]
    assert (row["value"], row["unit"]) == (expected, unit)


@pytest.mark.parametrize(
    "value", ["1e999", "NaN", "Infinity", "9" * 129, "0." + "0" * 61 + "1", "1" + "0" * 31]
)
def test_unbounded_or_non_decimal_primitives_rejected(value):
    rows = gdp()
    rows[0]["value"] = value
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(rows, [recipe(rows)], task_id="t")


@pytest.mark.parametrize(
    "change",
    [
        lambda p: p.update(sha256="not-a-sha"),
        lambda p: p.update(offset_unit="bytes"),
        lambda p: p.update(spans=[]),
        lambda p: p["spans"][0].update(start=True),
        lambda p: p["spans"][0].update(end=999),
        lambda p: p["spans"][0].update(text="changed original span"),
    ],
)
def test_proof_mutation_rejected(change):
    rows = gdp()
    change(rows[0]["proofs"][0])
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(rows, [recipe(rows)], task_id="t")


def test_half_up_empty_and_private_errors(caplog):
    rows = [observation("amount", "2025", "1.005")]
    assert (
        derive_business_observations(rows, [recipe(rows, operation="identity")], task_id="t")[0][
            "value"
        ]
        == "1.01"
    )
    assert derive_business_observations([], [], task_id="t") == []
    rows[0]["value"] = "private-invalid-payload"
    with pytest.raises(ValueError, match="^research_report_calculation_invalid$"):
        derive_business_observations(rows, [recipe(rows, operation="identity")], task_id="t")
    assert "private-invalid-payload" not in caplog.text


def test_invalid_tasks_duplicate_refs_and_excessive_observations_rejected():
    rows = gdp()
    for inputs, recipes, task in [
        (rows, [recipe(rows)], ""),
        (rows, [recipe(rows)], "t" * 129),
        (rows, [recipe(rows, operands=[rows[0]["id"]] * 2)], "t"),
        (rows, [recipe(rows, operands=[rows[0]["id"]] * 9)], "t"),
        (rows * 129, [], "t"),
    ]:
        with pytest.raises(ValueError, match="research_report_calculation_invalid"):
            derive_business_observations(inputs, recipes, task_id=task)


@pytest.mark.parametrize("sign", ["", "-"])
def test_single_rounding_at_arbitrary_accepted_decimal_boundary(sign):
    rows = [
        observation("amount", "2025", sign + "1.004" + "9" * 100),
        observation("amount", "2025", "0", source="b"),
    ]
    value = derive_business_observations(rows, [recipe(rows, operation="sum")], task_id="t")[0]
    assert value["value"] == sign + "1.00"


def test_unselected_noncanonical_host_layout_does_not_break_other_recipes():
    rows = gdp()
    unused = _emit(
        "scope",
        "stated_policy_assessment",
        "2024",
        Decimal(4),
        "count",
        rows[0]["proofs"],
        text="An actual noncanonical Host layout.",
    )
    assert derive_business_observations([*rows, unused], [], task_id="t") == []
    assert (
        derive_business_observations([*rows, unused], [recipe(rows)], task_id="t")[0]["value"]
        == "3.99"
    )


@pytest.mark.parametrize("operation", ["sum", "difference", "ratio", "percent_change"])
def test_different_metric_families_never_get_the_first_metrics_label(operation):
    rows = [
        observation("revenue", "2025", "100"),
        observation("net_income", "2025", "40", source="b"),
    ]
    with pytest.raises(ValueError, match="research_report_calculation_invalid"):
        derive_business_observations(rows, [recipe(rows, operation=operation)], task_id="t")
