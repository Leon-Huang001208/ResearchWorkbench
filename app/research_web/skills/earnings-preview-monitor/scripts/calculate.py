"""Calculate earnings-preview interval midpoints and transparent exposures."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_mean,
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

LOGGER = logging.getLogger("research.skill.earnings_preview_monitor")
SKILL_SLUG = "earnings-preview-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("records", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "records"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes", "data_contract"))
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub"})
CONTRACT_UNITS = {
    "profit": "CNY",
    "growth": "percent",
    "market_cap": "CNY",
    "valuation": "multiple",
    "exposure": "ratio",
    "research_coverage": "count",
}
REQUIRED_RECORD_FIELDS = (
    "security",
    "report_period",
    "disclosure_date",
    "profit_low",
    "profit_high",
    "growth_low_pct",
    "growth_high_pct",
)
OPTIONAL_EXPOSURES = (
    "market_cap",
    "valuation",
    "fund_exposure",
    "northbound_exposure",
    "research_coverage",
)
RECORD_FIELDS = frozenset((*REQUIRED_RECORD_FIELDS, *OPTIONAL_EXPOSURES))


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


def _bucket(value: float) -> str:
    if value < 0:
        return "negative"
    if value < 20:
        return "zero_to_20"
    if value < 50:
        return "20_to_50"
    return "50_plus"


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
        required=frozenset({"report_period"}),
        allowed=frozenset({"report_period"}),
        error=CalculatorError,
    )
    params = {
        "report_period": reject_future(params["report_period"], as_of=as_of, error=CalculatorError)
    }
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    normalized = []
    counts = {"negative": 0, "zero_to_20": 0, "20_to_50": 0, "50_plus": 0}
    exposure_values: dict[str, list[float]] = {field: [] for field in OPTIONAL_EXPOSURES}
    seen = set()
    for raw in records:
        raw = strict_object(
            raw,
            required=frozenset(REQUIRED_RECORD_FIELDS),
            allowed=RECORD_FIELDS,
            error=CalculatorError,
        )
        security = _text(raw["security"])
        period = reject_future(raw["report_period"], as_of=as_of, error=CalculatorError)
        if period != params["report_period"]:
            raise CalculatorError("data_not_equivalent")
        if (security, period) in seen:
            raise CalculatorError("duplicate_record")
        seen.add((security, period))
        profit_low = _number(raw["profit_low"])
        profit_high = _number(raw["profit_high"])
        growth_low = _number(raw["growth_low_pct"])
        growth_high = _number(raw["growth_high_pct"])
        if profit_low > profit_high or growth_low > growth_high:
            raise CalculatorError("invalid_interval")
        midpoint = checked_mean([profit_low, profit_high], error=CalculatorError)
        growth_midpoint = checked_mean([growth_low, growth_high], error=CalculatorError)
        counts[_bucket(growth_midpoint)] += 1
        row: dict[str, Any] = {
            "security": security,
            "report_period": period,
            "disclosure_date": reject_future(
                raw["disclosure_date"], as_of=as_of, error=CalculatorError
            ),
            "profit_low": profit_low,
            "profit_high": profit_high,
            "profit_midpoint": midpoint,
            "growth_low_pct": growth_low,
            "growth_high_pct": growth_high,
            "growth_midpoint_pct": growth_midpoint,
        }
        for field in OPTIONAL_EXPOSURES:
            value = raw.get(field)
            row[field] = None if value is None else _number(value)
            if row[field] is not None:
                exposure_values[field].append(row[field])
        normalized.append(row)
    normalized.sort(key=lambda row: (row["disclosure_date"], row["security"]))
    summaries = {
        field: {
            "provided_count": len(values),
            "mean": checked_mean(values, error=CalculatorError) if values else None,
        }
        for field, values in exposure_values.items()
    }
    missing = [field for field, values in exposure_values.items() if len(values) < len(normalized)]
    limitations = [f"missing_optional_field:{field}" for field in missing]
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
        "parameters": params,
        "dataset_refs": refs,
        "status": "partial" if limitations else "complete",
        "metrics": {
            "record_count": len(normalized),
            "growth_midpoint_distribution": [
                {"bucket": bucket, "count": counts[bucket]}
                for bucket in ("negative", "zero_to_20", "20_to_50", "50_plus")
            ],
            "provided_field_summaries": summaries,
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
                "validate_intervals",
                "interval_midpoints",
                "growth_buckets",
                "provided_only_summary",
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
