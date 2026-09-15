"""Compare supplied portfolio holdings with a supplied benchmark snapshot."""

from __future__ import annotations

import json
import logging
import math
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_add,
    checked_divide,
    checked_mean,
    checked_multiply,
    checked_number,
    checked_subtract,
    checked_sum,
    checked_text,
    iso_day,
    load_relative_json,
    reject_future,
    safe_error_payload,
    strict_json_dumps,
    strict_object,
    validate_data_contract,
    validate_dataset_refs,
    validate_source_hashes,
)

LOGGER = logging.getLogger("research.skill.portfolio_benchmark_deviation")
SKILL_SLUG = "portfolio-benchmark-deviation"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"portfolio_id", "benchmark_id"})
FEATURES = ("market_cap", "pe_ttm", "profit_growth_yoy_pct")
RECORD_FIELDS = frozenset(
    {"book", "book_id", "asset_id", "industry", "weight", "weight_unit", "as_of", *FEATURES}
)
CONTRACT_UNITS = {
    "weight": "record_declared_decimal_or_percent",
    "market_cap": "CNY_100m",
    "pe_ttm": "multiple",
    "profit_growth_yoy": "percent",
    "deviation": "benchmark_standard_deviation",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _weight(value: Any, unit: Any) -> float:
    weight = checked_number(value, error=CalculatorError)
    if unit == "percent":
        weight = checked_divide(weight, 100.0, error=CalculatorError)
    elif unit != "decimal":
        raise CalculatorError("data_not_equivalent")
    if weight <= 0:
        raise CalculatorError("invalid_weight")
    return weight


def _sample_std(values: list[float]) -> float:
    if len(values) < 2:
        raise CalculatorError("benchmark_sample_too_small")
    mean = checked_mean(values, error=CalculatorError)
    variance = checked_divide(
        checked_sum(
            [
                checked_multiply(
                    checked_subtract(value, mean, error=CalculatorError),
                    checked_subtract(value, mean, error=CalculatorError),
                    error=CalculatorError,
                )
                for value in values
            ],
            error=CalculatorError,
        ),
        len(values) - 1,
        error=CalculatorError,
    )
    result = checked_number(math.sqrt(variance), error=CalculatorError)
    if result <= 0:
        raise CalculatorError("benchmark_zero_dispersion")
    return result


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload, required=ROOT_FIELDS, allowed=ALLOWED_ROOT_FIELDS, error=CalculatorError
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
    validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="holding_and_factor_as_of",
        adjustment="not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    parameters = strict_object(
        payload["parameters"],
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    portfolio_id = checked_text(parameters["portfolio_id"], error=CalculatorError)
    benchmark_id = checked_text(parameters["benchmark_id"], error=CalculatorError)
    if portfolio_id == benchmark_id:
        raise CalculatorError("book_ids_must_differ")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    refs = validate_dataset_refs(
        payload["dataset_refs"], as_of=as_of, providers=SUPPORTED_PROVIDERS, error=CalculatorError
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    books: dict[str, dict[str, dict[str, Any]]] = {"portfolio": {}, "benchmark": {}}
    expected_ids = {"portfolio": portfolio_id, "benchmark": benchmark_id}
    duplicate_rows = 0
    for raw in records:
        raw = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        book = raw["book"]
        if book not in books or raw["book_id"] != expected_ids[book]:
            raise CalculatorError("data_not_equivalent")
        asset_id = checked_text(raw["asset_id"], error=CalculatorError)
        industry = checked_text(raw["industry"], error=CalculatorError)
        reject_future(raw["as_of"], as_of=as_of, error=CalculatorError)
        values = {
            feature: checked_number(raw[feature], error=CalculatorError) for feature in FEATURES
        }
        weight = _weight(raw["weight"], raw["weight_unit"])
        if asset_id in books[book]:
            existing = books[book][asset_id]
            if existing["industry"] != industry or any(
                existing[key] != values[key] for key in FEATURES
            ):
                raise CalculatorError("conflicting_duplicate_asset")
            existing["weight"] = checked_add(existing["weight"], weight, error=CalculatorError)
            duplicate_rows += 1
        else:
            books[book][asset_id] = {"weight": weight, "industry": industry, **values}
    budget.validate_batch(
        symbol_count=max(len(books["portfolio"]), len(books["benchmark"])), rows_per_symbol=1
    )
    totals = {
        book: checked_sum([row["weight"] for row in values.values()], error=CalculatorError)
        for book, values in books.items()
    }
    if any(total <= 0 for total in totals.values()):
        raise CalculatorError("empty_book")
    for book, values in books.items():
        for row in values.values():
            row["weight"] = checked_divide(row["weight"], totals[book], error=CalculatorError)

    weighted_means: dict[str, dict[str, float]] = {}
    for book, values in books.items():
        weighted_means[book] = {
            feature: checked_sum(
                [
                    checked_multiply(row["weight"], row[feature], error=CalculatorError)
                    for row in values.values()
                ],
                error=CalculatorError,
            )
            for feature in FEATURES
        }
    standard_deviations = {
        feature: _sample_std([row[feature] for row in books["benchmark"].values()])
        for feature in FEATURES
    }
    zscores = {
        feature: checked_divide(
            checked_subtract(
                weighted_means["portfolio"][feature],
                weighted_means["benchmark"][feature],
                error=CalculatorError,
            ),
            standard_deviations[feature],
            error=CalculatorError,
        )
        for feature in FEATURES
    }
    industry_weights: dict[str, dict[str, float]] = {"portfolio": {}, "benchmark": {}}
    for book, values in books.items():
        for row in values.values():
            industry = row["industry"]
            industry_weights[book][industry] = checked_add(
                industry_weights[book].get(industry, 0.0), row["weight"], error=CalculatorError
            )
    rows = [
        {
            "industry": industry,
            "portfolio_weight": industry_weights["portfolio"].get(industry, 0.0),
            "benchmark_weight": industry_weights["benchmark"].get(industry, 0.0),
            "weight_deviation": checked_subtract(
                industry_weights["portfolio"].get(industry, 0.0),
                industry_weights["benchmark"].get(industry, 0.0),
                error=CalculatorError,
            ),
        }
        for industry in sorted(
            set(industry_weights["portfolio"]) | set(industry_weights["benchmark"])
        )
    ]
    rows.sort(key=lambda row: (-row["weight_deviation"], row["industry"]))
    output_rows, row_delivery = bounded_result_rows(
        rows, processed_input_rows=len(records), dataset_refs=refs
    )
    overall = {
        "portfolio_market_cap": weighted_means["portfolio"]["market_cap"],
        "benchmark_market_cap": weighted_means["benchmark"]["market_cap"],
        "market_cap_zscore": zscores["market_cap"],
        "portfolio_pe_ttm": weighted_means["portfolio"]["pe_ttm"],
        "benchmark_pe_ttm": weighted_means["benchmark"]["pe_ttm"],
        "pe_ttm_zscore": zscores["pe_ttm"],
        "portfolio_profit_growth_yoy_pct": weighted_means["portfolio"]["profit_growth_yoy_pct"],
        "benchmark_profit_growth_yoy_pct": weighted_means["benchmark"]["profit_growth_yoy_pct"],
        "profit_growth_zscore": zscores["profit_growth_yoy_pct"],
    }
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {"portfolio_id": portfolio_id, "benchmark_id": benchmark_id},
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {"overall": overall, "duplicate_rows_aggregated": duplicate_rows},
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "benchmark_dispersion_is_unweighted_sample_standard_deviation",
            "industry_deviation_is_normalized_weight_difference",
            "negative_or_missing_factor_values_are_not_imputed",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "normalize_weight_units",
                "weighted_means",
                "sample_standard_deviation",
                "industry_weight_difference",
                METHOD_VERSION,
            ],
        },
    }


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        if len(args) != 1:
            raise CalculatorError("usage_error")
        payload, size = load_relative_json(args[0], error=CalculatorError, budget=WorkloadBudget())
        sys.stdout.write(
            strict_json_dumps(calculate(payload, input_bytes=size), error=CalculatorError)
        )
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        sys.stderr.write(json.dumps(safe_error_payload(exc), sort_keys=True, allow_nan=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
