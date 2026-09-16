"""Score supplied pre-aggregated industry indicators with explicit directions."""

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

LOGGER = logging.getLogger("research.skill.industry_prosperity")
SKILL_SLUG = "industry-prosperity"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"period_end", "minimum_indicators"})
RECORD_FIELDS = frozenset(
    {"industry", "indicator", "period_end", "current_value", "prior_value", "direction", "weight"}
)
CONTRACT_UNITS = {
    "indicator_values": "native_consistent_within_indicator",
    "change": "percent",
    "weight": "decimal",
    "score": "weighted_directional_percent_change",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload, required=ROOT_FIELDS, allowed=ALLOWED_ROOT_FIELDS, error=CalculatorError
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
    data_contract = validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="report_period_end",
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
    period_end = reject_future(parameters["period_end"], as_of=as_of, error=CalculatorError)
    minimum_indicators = parameters["minimum_indicators"]
    if type(minimum_indicators) is not int or not 1 <= minimum_indicators <= 1000:
        raise CalculatorError("invalid_field_type")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        contract_provider=data_contract["provider"],
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    for raw in records:
        raw = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        industry = checked_text(raw["industry"], error=CalculatorError)
        indicator = checked_text(raw["indicator"], error=CalculatorError)
        if (industry, indicator) in seen:
            raise CalculatorError("duplicate_indicator")
        seen.add((industry, indicator))
        if reject_future(raw["period_end"], as_of=as_of, error=CalculatorError) != period_end:
            raise CalculatorError("data_not_equivalent")
        current = checked_number(raw["current_value"], error=CalculatorError)
        prior = checked_number(raw["prior_value"], error=CalculatorError)
        if prior == 0:
            raise CalculatorError("invalid_prior_value")
        direction = raw["direction"]
        if type(direction) is not int or direction not in {-1, 1}:
            raise CalculatorError("invalid_direction")
        weight = checked_number(raw["weight"], error=CalculatorError, positive=True)
        raw_change = checked_multiply(
            checked_divide(
                checked_subtract(current, prior, error=CalculatorError),
                abs(prior),
                error=CalculatorError,
            ),
            100.0,
            error=CalculatorError,
        )
        directional_change = checked_multiply(raw_change, direction, error=CalculatorError)
        contribution = checked_multiply(directional_change, weight, error=CalculatorError)
        grouped.setdefault(industry, []).append(
            {
                "indicator": indicator,
                "current_value": current,
                "prior_value": prior,
                "direction": direction,
                "weight": weight,
                "raw_change_pct": raw_change,
                "directional_change_pct": directional_change,
                "weighted_contribution": contribution,
            }
        )
    budget.validate_batch(
        symbol_count=len(grouped), rows_per_symbol=max(len(values) for values in grouped.values())
    )
    rows: list[dict[str, Any]] = []
    insufficient: list[str] = []
    for industry, indicators in grouped.items():
        if len(indicators) < minimum_indicators:
            insufficient.append(industry)
            continue
        total_weight = checked_sum([row["weight"] for row in indicators], error=CalculatorError)
        score = checked_divide(
            checked_sum(
                [row["weighted_contribution"] for row in indicators], error=CalculatorError
            ),
            total_weight,
            error=CalculatorError,
        )
        if abs(score) <= 1e-12:
            score = 0.0
        signal = "improving" if score > 0 else "weakening" if score < 0 else "neutral"
        rows.append(
            {
                "industry": industry,
                "period_end": period_end,
                "indicator_count": len(indicators),
                "prosperity_score": score,
                "research_signal": signal,
                "indicator_contributions": sorted(indicators, key=lambda row: row["indicator"]),
            }
        )
    if not rows:
        raise CalculatorError("insufficient_indicators")
    rows.sort(key=lambda row: (-row["prosperity_score"], row["industry"]))
    limitations = [
        "preaggregated_indicators_only_no_constituent_scan",
        "directions_and_weights_are_supplied_not_inferred",
        "research_signal_not_trading_advice",
        *source_limitations,
    ]
    if insufficient:
        limitations.append("industries_below_minimum_indicator_count_omitted")
    output_rows, row_delivery = bounded_result_rows(
        rows, processed_input_rows=len(records), dataset_refs=refs
    )
    nested_total = sum(len(row["indicator_contributions"]) for row in output_rows)
    if nested_total > 128:
        remaining = 128
        for row in output_rows:
            contributions = row["indicator_contributions"]
            row["indicator_contributions"] = contributions[:remaining]
            remaining -= len(row["indicator_contributions"])
        row_delivery.update(
            {
                "mode": "summary_with_dataset_refs",
                "nested_inline_output_rows": 128,
                "nested_omitted_output_rows": nested_total - 128,
            }
        )
        limitations.append("indicator_contributions_projected_globally_to_128")
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {"period_end": period_end, "minimum_indicators": minimum_indicators},
        "dataset_refs": refs,
        "status": "partial" if source_limitations or insufficient else "complete",
        "metrics": {
            "industry_count": len(rows),
            "input_indicator_count": len(records),
            "omitted_industry_count": len(insufficient),
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": limitations,
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "strict_report_period",
                "directional_percent_change",
                "weighted_mean",
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
