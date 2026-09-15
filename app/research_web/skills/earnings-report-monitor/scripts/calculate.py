"""Calculate disclosure progress and reported growth distributions."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
    checked_number,
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

LOGGER = logging.getLogger("research.skill.earnings_report_monitor")
SKILL_SLUG = "earnings-report-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("records", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "records"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes", "data_contract"))
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub"})
CONTRACT_UNITS = {"revenue": "CNY", "net_profit": "CNY", "growth": "percent"}
REQUIRED_RECORD_FIELDS = (
    "security",
    "report_period",
    "disclosure_date",
    "revenue",
    "net_profit",
    "revenue_yoy_pct",
    "net_profit_yoy_pct",
    "revenue_qoq_pct",
    "net_profit_qoq_pct",
)
RECORD_FIELDS = frozenset(REQUIRED_RECORD_FIELDS)


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


def _number(value: Any) -> float:
    return checked_number(value, error=CalculatorError)


def _distribution(values: list[float]) -> list[dict[str, int | str]]:
    bins = [
        ("negative", lambda x: x < 0),
        ("zero_to_20", lambda x: 0 <= x < 20),
        ("20_to_50", lambda x: 20 <= x < 50),
        ("50_plus", lambda x: x >= 50),
    ]
    return [
        {"bucket": name, "count": sum(predicate(value) for value in values)}
        for name, predicate in bins
    ]


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
    records = payload["records"]
    if not isinstance(records, list):
        raise CalculatorError("invalid_field_type")
    if not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_batch(symbol_count=len(records), rows_per_symbol=1)
    as_of = _day(payload["as_of"])
    validate_data_contract(
        payload.get("data_contract"),
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="disclosure_date",
        adjustment="not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    params = strict_object(
        payload["parameters"],
        required=frozenset({"expected_count"}),
        allowed=frozenset({"expected_count"}),
        error=CalculatorError,
    )
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    expected_count = params.get("expected_count")
    if type(expected_count) is not int or expected_count < len(records) or expected_count <= 0:
        raise CalculatorError("invalid_field_type")
    normalized: list[dict[str, Any]] = []
    measures: dict[str, list[float]] = {
        field: [] for field in REQUIRED_RECORD_FIELDS if field.endswith("_pct")
    }
    seen: set[tuple[str, str]] = set()
    for raw in records:
        raw = strict_object(
            raw,
            required=RECORD_FIELDS,
            allowed=RECORD_FIELDS,
            error=CalculatorError,
        )
        security = _text(raw["security"])
        period = reject_future(raw["report_period"], as_of=as_of, error=CalculatorError)
        identity = (security, period)
        if identity in seen:
            raise CalculatorError("duplicate_record")
        seen.add(identity)
        row: dict[str, Any] = {
            "security": security,
            "report_period": period,
            "disclosure_date": reject_future(
                raw["disclosure_date"], as_of=as_of, error=CalculatorError
            ),
            "revenue": _number(raw["revenue"]),
            "net_profit": _number(raw["net_profit"]),
        }
        for field, values in measures.items():
            row[field] = _number(raw[field])
            values.append(row[field])
        normalized.append(row)
    normalized.sort(key=lambda row: (row["disclosure_date"], row["security"]))
    limitations = (
        [] if len(normalized) == expected_count else ["expected_universe_not_fully_disclosed"]
    )
    limitations.extend(source_limitations)
    output_rows, row_delivery = bounded_result_rows(
        normalized,
        processed_input_rows=len(records),
        dataset_refs=refs,
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {"expected_count": expected_count},
        "dataset_refs": refs,
        "status": "partial" if limitations else "complete",
        "metrics": {
            "disclosed_count": len(normalized),
            "expected_count": expected_count,
            "disclosure_progress": checked_divide(
                len(normalized), expected_count, error=CalculatorError
            ),
            "change_distributions": {
                field: _distribution(values) for field, values in measures.items()
            },
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
                "validate_complete_fields",
                "progress_ratio",
                "growth_buckets",
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
        print(strict_json_dumps(calculate(payload, input_bytes=size), error=CalculatorError))
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
