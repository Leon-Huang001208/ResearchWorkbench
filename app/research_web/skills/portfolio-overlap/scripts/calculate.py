"""Compute deterministic holdings overlap between two supplied portfolios."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_add,
    checked_divide,
    checked_number,
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

LOGGER = logging.getLogger("research.skill.portfolio_overlap")
SKILL_SLUG = "portfolio-overlap"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"left_portfolio_id", "right_portfolio_id"})
RECORD_FIELDS = frozenset({"portfolio_id", "asset_id", "weight", "weight_unit", "as_of"})
CONTRACT_UNITS = {"weight": "record_declared_decimal_or_percent", "overlap": "decimal"}


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
    if weight <= 0 or weight > 1:
        raise CalculatorError("invalid_weight")
    return weight


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
        date_semantics="holding_disclosure_date",
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
    left_id = checked_text(parameters["left_portfolio_id"], error=CalculatorError)
    right_id = checked_text(parameters["right_portfolio_id"], error=CalculatorError)
    if left_id == right_id:
        raise CalculatorError("portfolio_ids_must_differ")
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
    books: dict[str, dict[str, float]] = {left_id: {}, right_id: {}}
    input_counts = {left_id: 0, right_id: 0}
    duplicate_rows = 0
    snapshot_date: str | None = None
    for raw in records:
        raw = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        portfolio_id = checked_text(raw["portfolio_id"], error=CalculatorError)
        if portfolio_id not in books:
            raise CalculatorError("unknown_portfolio")
        input_counts[portfolio_id] += 1
        asset_id = checked_text(raw["asset_id"], error=CalculatorError)
        holding_date = reject_future(raw["as_of"], as_of=as_of, error=CalculatorError)
        if snapshot_date is None:
            snapshot_date = holding_date
        elif holding_date != snapshot_date:
            raise CalculatorError("data_not_equivalent")
        weight = _weight(raw["weight"], raw["weight_unit"])
        if asset_id in books[portfolio_id]:
            duplicate_rows += 1
            books[portfolio_id][asset_id] = checked_add(
                books[portfolio_id][asset_id], weight, error=CalculatorError
            )
            if books[portfolio_id][asset_id] > 1:
                raise CalculatorError("invalid_weight")
        else:
            books[portfolio_id][asset_id] = weight
    budget.validate_batch(symbol_count=2, rows_per_symbol=max(input_counts.values()))
    totals = {
        book: checked_sum(list(weights.values()), error=CalculatorError)
        for book, weights in books.items()
    }
    if any(total <= 0 for total in totals.values()):
        raise CalculatorError("empty_portfolio")
    if any(total > 1.000000001 for total in totals.values()):
        raise CalculatorError("invalid_weight_sum")
    normalized = {
        book: {
            asset: checked_divide(weight, totals[book], error=CalculatorError)
            for asset, weight in weights.items()
        }
        for book, weights in books.items()
    }
    rows: list[dict[str, Any]] = []
    for asset in sorted(set(normalized[left_id]) | set(normalized[right_id])):
        left_weight = normalized[left_id].get(asset, 0.0)
        right_weight = normalized[right_id].get(asset, 0.0)
        rows.append(
            {
                "asset_id": asset,
                "left_weight": left_weight,
                "right_weight": right_weight,
                "common_weight": min(left_weight, right_weight),
            }
        )
    rows.sort(key=lambda row: (-row["common_weight"], row["asset_id"]))
    overlap = checked_sum([row["common_weight"] for row in rows], error=CalculatorError)
    output_rows, row_delivery = bounded_result_rows(
        rows, processed_input_rows=len(records), dataset_refs=refs
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {"left_portfolio_id": left_id, "right_portfolio_id": right_id},
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "overlap_ratio": overlap,
            "left_unique_asset_count": len(normalized[left_id]),
            "right_unique_asset_count": len(normalized[right_id]),
            "duplicate_rows_aggregated": duplicate_rows,
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "weights_are_normalized_within_each_supplied_portfolio",
            "overlap_is_sum_of_minimum_normalized_weights",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "normalize_weight_units",
                "aggregate_duplicates",
                "sum_minimum_weights",
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
