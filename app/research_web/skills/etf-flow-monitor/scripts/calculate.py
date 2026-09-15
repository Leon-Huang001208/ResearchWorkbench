"""Calculate ETF flows only from supplied shares, NAV and classifications."""

from __future__ import annotations

import json
import logging
import math
import sys
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    iso_day,
    reject_future,
    safe_error_payload,
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
    if not isinstance(value, str) or not value.strip():
        raise CalculatorError("invalid_field_type")
    return value.strip()


def _day(value: Any) -> str:
    return iso_day(value, error=CalculatorError)


def _number(value: Any, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("invalid_field_type")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0):
        raise CalculatorError("invalid_number")
    return result


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
    source_hashes, source_limitations = validate_source_hashes(
        payload.get("source_hashes"), error=CalculatorError
    )
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
        change = shares - prior_shares
        flow = change * nav
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
            values[category] = values.get(category, 0.0) + flow
    normalized.sort(key=lambda row: (row["date"], row["code"]))
    summaries = {
        dimension: [
            {"category": category, "estimated_flow": flow}
            for category, flow in sorted(values.items())
        ]
        for dimension, values in grouped.items()
    }
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
            "total_estimated_flow": sum(row["estimated_flow"] for row in normalized),
            "classification_summaries": summaries,
        },
        "rows": normalized,
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


def _path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise CalculatorError("unsafe_input_path")
    result = (Path.cwd() / path).resolve()
    if not result.is_file():
        raise CalculatorError("input_unavailable")
    return result


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        if len(args) != 1:
            raise CalculatorError("usage_error")
        path = _path(args[0])
        size = path.stat().st_size
        WorkloadBudget().add_input(rows=0, bytes_count=size)
        print(
            json.dumps(
                calculate(json.loads(path.read_text(encoding="utf-8")), input_bytes=size),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        print(json.dumps(safe_error_payload(exc), sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
