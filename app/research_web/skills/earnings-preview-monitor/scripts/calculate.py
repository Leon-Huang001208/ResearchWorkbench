"""Calculate earnings-preview interval midpoints and transparent exposures."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.earnings_preview_monitor")
SKILL_SLUG = "earnings-preview-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("records", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "records"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes"))
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


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalculatorError("invalid_field_type")
    return value.strip()


def _day(value: Any) -> str:
    value = _text(value)
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CalculatorError("invalid_date") from exc


def _dataset_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if set(payload) - ALLOWED_ROOT_FIELDS:
        raise CalculatorError("unknown_field")
    refs = payload.get("dataset_refs")
    required = {"dataset_id", "provider_id", "as_of", "sha256"}
    if not isinstance(refs, list) or not refs:
        raise CalculatorError("invalid_field_type")
    for ref in refs:
        if not isinstance(ref, dict) or not required <= set(ref):
            raise CalculatorError("invalid_dataset_ref")
        _text(ref["dataset_id"])
        _text(ref["provider_id"])
        _day(ref["as_of"])
        digest = ref["sha256"]
        if (
            not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest.lower())
        ):
            raise CalculatorError("invalid_dataset_ref")
    return refs


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("invalid_field_type")
    result = float(value)
    if not math.isfinite(result):
        raise CalculatorError("invalid_number")
    return result


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
    for field in REQUIRED_ROOT_FIELDS:
        if field not in payload:
            raise CalculatorError("missing_required_field")
    records = payload["records"]
    if not isinstance(records, list):
        raise CalculatorError("invalid_field_type")
    if not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_batch(symbol_count=len(records), rows_per_symbol=1)
    params = payload["parameters"]
    refs = _dataset_refs(payload)
    if not isinstance(params, dict):
        raise CalculatorError("invalid_field_type")
    normalized = []
    counts = {"negative": 0, "zero_to_20": 0, "20_to_50": 0, "50_plus": 0}
    exposure_values: dict[str, list[float]] = {field: [] for field in OPTIONAL_EXPOSURES}
    seen = set()
    for raw in records:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        if any(field not in raw for field in REQUIRED_RECORD_FIELDS):
            raise CalculatorError("missing_required_field")
        security = _text(raw["security"])
        period = _day(raw["report_period"])
        if (security, period) in seen:
            raise CalculatorError("duplicate_record")
        seen.add((security, period))
        profit_low = _number(raw["profit_low"])
        profit_high = _number(raw["profit_high"])
        growth_low = _number(raw["growth_low_pct"])
        growth_high = _number(raw["growth_high_pct"])
        if profit_low > profit_high or growth_low > growth_high:
            raise CalculatorError("invalid_interval")
        midpoint = (profit_low + profit_high) / 2.0
        growth_midpoint = (growth_low + growth_high) / 2.0
        counts[_bucket(growth_midpoint)] += 1
        row: dict[str, Any] = {
            "security": security,
            "report_period": period,
            "disclosure_date": _day(raw["disclosure_date"]),
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
            "mean": sum(values) / len(values) if values else None,
        }
        for field, values in exposure_values.items()
    }
    missing = [field for field, values in exposure_values.items() if len(values) < len(normalized)]
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": _day(payload["as_of"]),
        "parameters": params,
        "dataset_refs": refs,
        "status": "partial" if missing else "complete",
        "metrics": {
            "record_count": len(normalized),
            "growth_midpoint_distribution": [
                {"bucket": bucket, "count": counts[bucket]}
                for bucket in ("negative", "zero_to_20", "20_to_50", "50_plus")
            ],
            "provided_field_summaries": summaries,
        },
        "rows": normalized,
        "limitations": [f"missing_optional_field:{field}" for field in missing],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": payload.get("source_hashes", {}),
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
        print(json.dumps({"error": {"code": code, "message": code}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
