"""Classify supplied industry scores by explicit level and momentum thresholds."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_number,
    checked_subtract,
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

LOGGER = logging.getLogger("research.skill.industry_quadrant_monitor")
SKILL_SLUG = "industry-quadrant-monitor"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"observation_date", "level_threshold", "momentum_threshold"})
RECORD_FIELDS = frozenset({"industry", "observation_date", "current_score", "prior_score"})
CONTRACT_UNITS = {"prosperity_score": "supplied_index", "momentum": "index_change"}
QUADRANTS = (
    "high_and_improving",
    "high_but_weakening",
    "low_but_improving",
    "low_and_weakening",
)


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
    validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="observation_date",
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
    observation_date = reject_future(
        parameters["observation_date"], as_of=as_of, error=CalculatorError
    )
    level_threshold = checked_number(parameters["level_threshold"], error=CalculatorError)
    momentum_threshold = checked_number(parameters["momentum_threshold"], error=CalculatorError)
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_batch(symbol_count=len(records), rows_per_symbol=1)
    refs = validate_dataset_refs(
        payload["dataset_refs"], as_of=as_of, providers=SUPPORTED_PROVIDERS, error=CalculatorError
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    counts = {quadrant: 0 for quadrant in QUADRANTS}
    for raw in records:
        raw = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        industry = checked_text(raw["industry"], error=CalculatorError)
        if industry in seen:
            raise CalculatorError("duplicate_industry")
        seen.add(industry)
        if (
            reject_future(raw["observation_date"], as_of=as_of, error=CalculatorError)
            != observation_date
        ):
            raise CalculatorError("data_not_equivalent")
        current = checked_number(raw["current_score"], error=CalculatorError)
        prior = checked_number(raw["prior_score"], error=CalculatorError)
        momentum = checked_subtract(current, prior, error=CalculatorError)
        high = current >= level_threshold
        improving = momentum >= momentum_threshold
        if high and improving:
            quadrant = "high_and_improving"
        elif high:
            quadrant = "high_but_weakening"
        elif improving:
            quadrant = "low_but_improving"
        else:
            quadrant = "low_and_weakening"
        counts[quadrant] += 1
        rows.append(
            {
                "industry": industry,
                "observation_date": observation_date,
                "current_score": current,
                "prior_score": prior,
                "momentum": momentum,
                "quadrant": quadrant,
                "research_signal": quadrant,
            }
        )
    order = {quadrant: index for index, quadrant in enumerate(QUADRANTS)}
    rows.sort(key=lambda row: (order[row["quadrant"]], row["industry"]))
    output_rows, row_delivery = bounded_result_rows(
        rows, processed_input_rows=len(records), dataset_refs=refs
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {
            "observation_date": observation_date,
            "level_threshold": level_threshold,
            "momentum_threshold": momentum_threshold,
        },
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {"industry_count": len(rows), "quadrant_counts": counts},
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "preaggregated_scores_only_no_constituent_scan",
            "thresholds_are_user_supplied",
            "research_signal_not_trading_advice",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "strict_observation_date",
                "score_difference",
                "threshold_quadrant",
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
