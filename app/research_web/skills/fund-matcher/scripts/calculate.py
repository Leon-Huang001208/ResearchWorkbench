"""Rank supplied fund candidates against an explicit target profile."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
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

LOGGER = logging.getLogger("research.skill.fund_matcher")
SKILL_SLUG = "fund-matcher"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
METRICS = (
    "annual_return_pct",
    "max_drawdown_pct",
    "volatility_pct",
    "expense_ratio_pct",
    "manager_tenure_years",
)
RECORD_FIELDS = frozenset({"fund_code", "name", "category", "as_of", *METRICS})
TARGET_FIELDS = frozenset(METRICS)
PARAMETER_FIELDS = frozenset({"category", "top_n", "targets", "metric_weights"})
CONTRACT_UNITS = {
    "return": "percent",
    "drawdown": "percent",
    "volatility": "percent",
    "expense_ratio": "percent",
    "tenure": "years",
    "score": "0_to_100",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: Any) -> float:
    return checked_number(value, error=CalculatorError)


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload,
        required=ROOT_FIELDS,
        allowed=ALLOWED_ROOT_FIELDS,
        error=CalculatorError,
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
    validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="fund_metrics_as_of",
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
    category = checked_text(parameters["category"], error=CalculatorError)
    top_n = parameters["top_n"]
    if type(top_n) is not int or not 1 <= top_n <= 50:
        raise CalculatorError("invalid_field_type")
    targets = strict_object(
        parameters["targets"],
        required=TARGET_FIELDS,
        allowed=TARGET_FIELDS,
        error=CalculatorError,
    )
    metric_weights = strict_object(
        parameters["metric_weights"],
        required=TARGET_FIELDS,
        allowed=TARGET_FIELDS,
        error=CalculatorError,
    )
    normalized_targets = {metric: _number(targets[metric]) for metric in METRICS}
    normalized_weights = {
        metric: checked_number(metric_weights[metric], error=CalculatorError, positive=True)
        for metric in METRICS
    }
    total_weight = checked_sum(list(normalized_weights.values()), error=CalculatorError)
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_batch(symbol_count=len(records), rows_per_symbol=1)
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    seen: set[str] = set()
    matches: list[dict[str, Any]] = []
    for raw in records:
        raw = strict_object(
            raw,
            required=RECORD_FIELDS,
            allowed=RECORD_FIELDS,
            error=CalculatorError,
        )
        fund_code = checked_text(raw["fund_code"], error=CalculatorError)
        if fund_code in seen:
            raise CalculatorError("duplicate_fund")
        seen.add(fund_code)
        record_category = checked_text(raw["category"], error=CalculatorError)
        record_as_of = reject_future(raw["as_of"], as_of=as_of, error=CalculatorError)
        values = {metric: _number(raw[metric]) for metric in METRICS}
        if record_category != category:
            continue
        components: dict[str, float] = {}
        weighted: list[float] = []
        for metric in METRICS:
            difference = abs(
                checked_subtract(values[metric], normalized_targets[metric], error=CalculatorError)
            )
            scale = max(abs(normalized_targets[metric]), 1.0)
            component = checked_divide(difference, scale, error=CalculatorError)
            components[metric] = component
            weighted.append(
                checked_multiply(component, normalized_weights[metric], error=CalculatorError)
            )
        distance = checked_divide(
            checked_sum(weighted, error=CalculatorError), total_weight, error=CalculatorError
        )
        score = max(
            0.0,
            checked_multiply(
                checked_subtract(1.0, distance, error=CalculatorError),
                100.0,
                error=CalculatorError,
            ),
        )
        matches.append(
            {
                "fund_code": fund_code,
                "name": checked_text(raw["name"], error=CalculatorError),
                "category": record_category,
                "as_of": record_as_of,
                "match_score": score,
                "weighted_distance": distance,
                "distance_components": components,
            }
        )
    if not matches:
        raise CalculatorError("no_matching_candidates")
    matches.sort(key=lambda row: (-row["match_score"], row["fund_code"]))
    selected = matches[:top_n]
    output_rows, row_delivery = bounded_result_rows(
        selected,
        processed_input_rows=len(records),
        dataset_refs=refs,
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {
            "category": category,
            "top_n": top_n,
            "targets": normalized_targets,
            "metric_weights": normalized_weights,
        },
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "eligible_candidate_count": len(matches),
            "returned_candidate_count": len(selected),
            "best_match_score": selected[0]["match_score"],
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "deterministic_profile_distance_not_future_performance",
            "category_must_match_exactly",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": ["strict_category_filter", "weighted_l1_distance", METHOD_VERSION],
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
