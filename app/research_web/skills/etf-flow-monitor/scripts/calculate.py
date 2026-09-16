"""Calculate ETF flows only from supplied shares, NAV and classifications."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_add,
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

LOGGER = logging.getLogger("research.skill.etf_flow_monitor")
SKILL_SLUG = "etf-flow-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("rows", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "rows"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes", "data_contract"))
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub", "user_input"})
CONTRACT_UNITS = {
    "shares": "share",
    "nav": "CNY_per_share",
    "price": "CNY_per_share",
    "estimated_flow": "CNY",
}
ROW_FIELDS = frozenset({"code", "date", "shares", "prior_shares", "nav", "price", "classification"})
CLASSIFICATION_FIELDS = frozenset({"type", "industry", "theme"})


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any) -> str:
    return checked_text(value, error=CalculatorError)


def _day(value: Any) -> str:
    return iso_day(value, error=CalculatorError)


def _number(value: Any, *, positive: bool = False) -> float:
    return checked_number(value, error=CalculatorError, positive=positive)


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    if not isinstance(payload, dict):
        raise CalculatorError("invalid_field_type")
    strict_object(
        payload,
        required=frozenset(REQUIRED_ROOT_FIELDS),
        allowed=ALLOWED_ROOT_FIELDS,
        error=CalculatorError,
    )
    rows = payload["rows"]
    if not isinstance(rows, list):
        raise CalculatorError("invalid_field_type")
    if not rows:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(rows), bytes_count=0)
    budget.validate_batch(symbol_count=len(rows), rows_per_symbol=1)
    as_of = _day(payload["as_of"])
    validate_data_contract(
        payload.get("data_contract"),
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="trade_date",
        adjustment="not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    params = strict_object(
        payload["parameters"],
        required=frozenset({"currency"}),
        allowed=frozenset({"currency"}),
        error=CalculatorError,
    )
    if params["currency"] != "CNY":
        raise CalculatorError("data_not_equivalent")
    params = {"currency": "CNY"}
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    normalized: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, float]] = {"type": {}, "industry": {}, "theme": {}}
    for raw in rows:
        if isinstance(raw, dict) and "classification" not in raw:
            raise CalculatorError("classification_required")
        raw = strict_object(
            raw,
            required=ROW_FIELDS,
            allowed=ROW_FIELDS,
            error=CalculatorError,
        )
        classification = raw.get("classification")
        if not isinstance(classification, dict):
            raise CalculatorError("classification_required")
        if set(classification) != CLASSIFICATION_FIELDS:
            if set(classification) - CLASSIFICATION_FIELDS:
                raise CalculatorError("unknown_field")
            raise CalculatorError("classification_required")
        if any(
            not isinstance(classification.get(dimension), str)
            or not classification[dimension].strip()
            for dimension in grouped
        ):
            raise CalculatorError("classification_required")
        shares = _number(raw.get("shares"), positive=True)
        prior_shares = _number(raw.get("prior_shares"), positive=True)
        nav = _number(raw.get("nav"), positive=True)
        price = _number(raw.get("price"), positive=True)
        change = checked_subtract(shares, prior_shares, error=CalculatorError)
        flow = checked_multiply(change, nav, error=CalculatorError)
        row: dict[str, Any] = {
            "code": _text(raw.get("code")),
            "date": reject_future(raw.get("date"), as_of=as_of, error=CalculatorError),
            "share_change": change,
            "estimated_flow": flow,
            "nav": nav,
            "price": price,
            "classification": {key: _text(classification[key]) for key in grouped},
        }
        normalized.append(row)
        for dimension, values in grouped.items():
            category = row["classification"][dimension]
            values[category] = checked_add(values.get(category, 0.0), flow, error=CalculatorError)
    normalized.sort(key=lambda row: (row["date"], row["code"]))
    summaries = {
        dimension: [
            {"category": category, "estimated_flow": flow}
            for category, flow in sorted(values.items())
        ]
        for dimension, values in grouped.items()
    }
    output_rows, row_delivery = bounded_result_rows(
        normalized,
        processed_input_rows=len(rows),
        dataset_refs=refs,
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": params,
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "etf_count": len(normalized),
            "total_estimated_flow": checked_sum(
                [row["estimated_flow"] for row in normalized], error=CalculatorError
            ),
            "classification_summaries": summaries,
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "flow_equals_share_change_times_supplied_nav",
            "classifications_are_user_supplied",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "validate_classification",
                "share_change",
                "nav_flow",
                "group_sum",
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
        serialized = strict_json_dumps(calculate(payload, input_bytes=size), error=CalculatorError)
        sys.stdout.write(serialized)
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        print(
            json.dumps(safe_error_payload(exc), sort_keys=True, allow_nan=False),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
