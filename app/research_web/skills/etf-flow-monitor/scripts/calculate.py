"""Calculate ETF flows only from supplied shares, NAV and classifications."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.etf_flow_monitor")
SKILL_SLUG = "etf-flow-monitor"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("rows", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "rows"
ALLOWED_ROOT_FIELDS = frozenset((*REQUIRED_ROOT_FIELDS, "source_hashes"))


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
    for field in REQUIRED_ROOT_FIELDS:
        if field not in payload:
            raise CalculatorError("missing_required_field")
    rows = payload["rows"]
    if not isinstance(rows, list):
        raise CalculatorError("invalid_field_type")
    if not rows:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(rows), bytes_count=0)
    budget.validate_batch(symbol_count=len(rows), rows_per_symbol=1)
    params = payload["parameters"]
    refs = _dataset_refs(payload)
    if not isinstance(params, dict):
        raise CalculatorError("invalid_field_type")
    normalized: list[dict[str, Any]] = []
    grouped: dict[str, dict[str, float]] = {"type": {}, "industry": {}, "theme": {}}
    for raw in rows:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        classification = raw.get("classification")
        if not isinstance(classification, dict) or any(
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
            "date": _day(raw.get("date")),
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
        "as_of": _day(payload["as_of"]),
        "parameters": params,
        "dataset_refs": refs,
        "status": "complete",
        "metrics": {
            "etf_count": len(normalized),
            "total_estimated_flow": sum(row["estimated_flow"] for row in normalized),
            "classification_summaries": summaries,
        },
        "rows": normalized,
        "limitations": [
            "flow_equals_share_change_times_supplied_nav",
            "classifications_are_user_supplied",
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": payload.get("source_hashes", {}),
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
        print(json.dumps({"error": {"code": code, "message": code}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
