"""Calculate disclosure progress and reported growth distributions."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.earnings_report_monitor")
SKILL_SLUG = "earnings-report-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("records", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "records"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes"))
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
    expected_count = params.get("expected_count")
    if type(expected_count) is not int or expected_count < len(records) or expected_count <= 0:
        raise CalculatorError("invalid_field_type")
    normalized: list[dict[str, Any]] = []
    measures: dict[str, list[float]] = {
        field: [] for field in REQUIRED_RECORD_FIELDS if field.endswith("_pct")
    }
    seen: set[tuple[str, str]] = set()
    for raw in records:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        if any(field not in raw for field in REQUIRED_RECORD_FIELDS):
            raise CalculatorError("missing_required_field")
        security = _text(raw["security"])
        period = _day(raw["report_period"])
        identity = (security, period)
        if identity in seen:
            raise CalculatorError("duplicate_record")
        seen.add(identity)
        row: dict[str, Any] = {
            "security": security,
            "report_period": period,
            "disclosure_date": _day(raw["disclosure_date"]),
            "revenue": _number(raw["revenue"]),
            "net_profit": _number(raw["net_profit"]),
        }
        for field, values in measures.items():
            row[field] = _number(raw[field])
            values.append(row[field])
        normalized.append(row)
    normalized.sort(key=lambda row: (row["disclosure_date"], row["security"]))
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": _day(payload["as_of"]),
        "parameters": {"expected_count": expected_count},
        "dataset_refs": refs,
        "status": "complete" if len(normalized) == expected_count else "partial",
        "metrics": {
            "disclosed_count": len(normalized),
            "expected_count": expected_count,
            "disclosure_progress": len(normalized) / expected_count,
            "change_distributions": {
                field: _distribution(values) for field, values in measures.items()
            },
        },
        "rows": normalized,
        "limitations": (
            [] if len(normalized) == expected_count else ["expected_universe_not_fully_disclosed"]
        ),
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": payload.get("source_hashes", {}),
            "rights": "internal-only",
            "transformations": [
                "validate_complete_fields",
                "progress_ratio",
                "growth_buckets",
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
