"""Deterministically arrange supplied market evidence into a daily brief."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.daily_market_brief")
SKILL_SLUG = "daily-market-brief"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = ("market_snapshot", "as_of", "dataset_refs", "parameters")
PRIMARY_ROWS_FIELD = "market_snapshot"
ALLOWED_ROOT_FIELDS = frozenset(
    (*REQUIRED_ROOT_FIELDS, "source_hashes", "breadth", "sectors", "themes", "news")
)


class CalculatorError(ValueError):
    """Stable content-free calculator rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _day(value: Any) -> str:
    if not isinstance(value, str):
        raise CalculatorError("invalid_field_type")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise CalculatorError("invalid_date") from exc


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalculatorError("invalid_field_type")
    result = float(value)
    if not math.isfinite(result):
        raise CalculatorError("invalid_number")
    return result


def _text(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalculatorError("invalid_field_type")
    return value.strip()


def _list(payload: dict[str, Any], field: str, *, required: bool = False) -> list[Any]:
    value = payload.get(field, [])
    if not isinstance(value, list):
        raise CalculatorError("invalid_field_type")
    if required and not value:
        raise CalculatorError("empty_input")
    return value


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


def _base(
    payload: dict[str, Any], *, rows: int, budget: WorkloadBudget
) -> tuple[WorkloadBudget, dict]:
    for field in REQUIRED_ROOT_FIELDS:
        if field not in payload:
            raise CalculatorError("missing_required_field")
    if not isinstance(payload[REQUIRED_ROOT_FIELDS[0]], list):
        raise CalculatorError("invalid_field_type")
    budget.add_input(rows=rows, bytes_count=0)
    parameters = payload["parameters"]
    refs = _dataset_refs(payload)
    if not isinstance(parameters, dict):
        raise CalculatorError("invalid_field_type")
    return budget, {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": _day(payload["as_of"]),
        "parameters": parameters,
        "dataset_refs": refs,
    }


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    """Return a fixed brief structure without inferring policy or event impacts."""
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    if not isinstance(payload, dict):
        raise CalculatorError("invalid_field_type")
    collections = {
        name: _list(payload, name) for name in ("market_snapshot", "sectors", "themes", "news")
    }
    row_count = sum(len(value) for value in collections.values())
    budget, result = _base(payload, rows=row_count, budget=budget)
    if row_count == 0:
        raise CalculatorError("empty_input")
    budget.validate_series(len(collections["market_snapshot"]))

    indices: list[dict[str, Any]] = []
    for raw in collections["market_snapshot"]:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        indices.append(
            {
                "asset": _text(raw.get("asset")),
                "name": _text(raw.get("name")),
                "price": _number(raw.get("price")),
                "change_pct": _number(raw.get("change_pct")),
                "turnover": _number(raw.get("turnover")),
            }
        )
    indices.sort(key=lambda row: row["asset"])

    def ranked(name: str) -> list[dict[str, Any]]:
        values: list[dict[str, Any]] = []
        for raw in collections[name]:
            if not isinstance(raw, dict):
                raise CalculatorError("invalid_field_type")
            values.append(
                {"name": _text(raw.get("name")), "change_pct": _number(raw.get("change_pct"))}
            )
        return sorted(values, key=lambda row: (-row["change_pct"], row["name"]))

    news = []
    for raw in collections["news"]:
        if not isinstance(raw, dict) or not raw.get("source_ref"):
            raise CalculatorError("evidence_required")
        news.append(
            {
                "published_at": _text(raw.get("published_at")),
                "title": _text(raw.get("title")),
                "source": _text(raw.get("source")),
                "source_ref": _text(raw.get("source_ref")),
            }
        )
    news.sort(key=lambda row: (row["published_at"], row["source_ref"]))
    breadth = payload.get("breadth")
    if not isinstance(breadth, dict):
        raise CalculatorError("missing_required_field")
    advances = int(_number(breadth.get("advances")))
    declines = int(_number(breadth.get("declines")))
    flat = int(_number(breadth.get("flat")))
    if min(advances, declines, flat) < 0:
        raise CalculatorError("invalid_number")
    covered = advances + declines + flat
    if covered == 0 or not indices:
        raise CalculatorError("empty_input")

    result.update(
        status="complete",
        metrics={
            "index_count": len(indices),
            "average_change_pct": sum(row["change_pct"] for row in indices) / len(indices),
            "total_turnover": sum(row["turnover"] for row in indices),
            "advance_ratio": advances / covered,
            "news_count": len(news),
        },
        rows={
            "market_snapshot": indices,
            "breadth": {"advances": advances, "declines": declines, "flat": flat},
            "sectors": ranked("sectors"),
            "themes": ranked("themes"),
            "news_evidence": news,
        },
        limitations=["arrangement_only_no_event_or_policy_inference"],
        research_only=True,
        provenance={
            "dataset_refs": payload["dataset_refs"],
            "source_hashes": payload.get("source_hashes", {}),
            "rights": "internal-only",
            "transformations": ["validate", "sort", "aggregate", METHOD_VERSION],
        },
    )
    return result


def _input_path(argument: str) -> Path:
    path = Path(argument)
    if path.is_absolute() or ".." in path.parts:
        raise CalculatorError("unsafe_input_path")
    resolved = (Path.cwd() / path).resolve()
    if not resolved.is_file():
        raise CalculatorError("input_unavailable")
    return resolved


def main(argv: list[str] | None = None) -> int:
    try:
        args = sys.argv[1:] if argv is None else argv
        if len(args) != 1:
            raise CalculatorError("usage_error")
        path = _input_path(args[0])
        size = path.stat().st_size
        WorkloadBudget().add_input(rows=0, bytes_count=size)
        payload = json.loads(path.read_text(encoding="utf-8"))
        print(json.dumps(calculate(payload, input_bytes=size), ensure_ascii=False, sort_keys=True))
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        print(json.dumps({"error": {"code": code, "message": code}}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
