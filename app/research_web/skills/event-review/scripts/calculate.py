"""Deterministic event-window performance and pre-event beta calculation."""

from __future__ import annotations

import json
import logging
import math
import sys
from datetime import date
from pathlib import Path
from typing import Any

from cpu_budget import WorkloadBudget

LOGGER = logging.getLogger("research.skill.event_review")
SKILL_SLUG = "event-review"
METHOD_VERSION = "1.0.0"
MIN_BETA_OBSERVATIONS = 20
REQUIRED_ROOT_FIELDS = (
    "target_series",
    "benchmark_series",
    "event_date",
    "as_of",
    "dataset_refs",
    "parameters",
)
PRIMARY_ROWS_FIELD = "target_series"
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


def _series(value: Any) -> list[dict[str, float | str]]:
    if not isinstance(value, list):
        raise CalculatorError("invalid_field_type")
    if not value:
        raise CalculatorError("empty_input")
    result: list[dict[str, float | str]] = []
    seen: set[str] = set()
    for raw in value:
        if not isinstance(raw, dict):
            raise CalculatorError("invalid_field_type")
        day = _day(raw.get("date"))
        if day in seen:
            raise CalculatorError("duplicate_date")
        seen.add(day)
        result.append(
            {
                "date": day,
                "close": _number(raw.get("close"), positive=True),
                "volume": _number(raw.get("volume"), positive=True),
            }
        )
    return sorted(result, key=lambda row: row["date"])


def _returns(rows: list[dict[str, float | str]]) -> dict[str, float]:
    return {
        str(rows[index]["date"]): float(rows[index]["close"]) / float(rows[index - 1]["close"])
        - 1.0
        for index in range(1, len(rows))
    }


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    if not isinstance(payload, dict):
        raise CalculatorError("invalid_field_type")
    for field in REQUIRED_ROOT_FIELDS:
        if field not in payload:
            raise CalculatorError("missing_required_field")
    if not isinstance(payload[REQUIRED_ROOT_FIELDS[0]], list):
        raise CalculatorError("invalid_field_type")
    target = _series(payload["target_series"])
    benchmark = _series(payload["benchmark_series"])
    budget.add_input(rows=len(target) + len(benchmark), bytes_count=0)
    budget.validate_series(len(target))
    budget.validate_series(len(benchmark))
    params = payload["parameters"]
    refs = _dataset_refs(payload)
    if not isinstance(params, dict):
        raise CalculatorError("invalid_field_type")
    pre_days = params.get("pre_days")
    post_days = params.get("post_days")
    if type(pre_days) is not int or type(post_days) is not int or pre_days < 1 or post_days < 1:
        raise CalculatorError("invalid_field_type")
    event = _day(payload["event_date"])
    target_by_day = {str(row["date"]): row for row in target}
    benchmark_by_day = {str(row["date"]): row for row in benchmark}
    common_days = sorted(set(target_by_day) & set(benchmark_by_day))
    if event not in common_days:
        raise CalculatorError("event_date_unavailable")
    position = common_days.index(event)
    if position < pre_days or len(common_days) - position - 1 < post_days:
        raise CalculatorError("event_window_incomplete")
    window_days = common_days[position - pre_days : position + post_days + 1]
    start, end = window_days[0], window_days[-1]
    target_return = float(target_by_day[end]["close"]) / float(target_by_day[start]["close"]) - 1.0
    benchmark_return = (
        float(benchmark_by_day[end]["close"]) / float(benchmark_by_day[start]["close"]) - 1.0
    )
    pre_volumes = [float(target_by_day[day]["volume"]) for day in window_days[:pre_days]]
    post_volumes = [float(target_by_day[day]["volume"]) for day in window_days[pre_days:]]
    volume_change = (
        sum(post_volumes) / len(post_volumes) / (sum(pre_volumes) / len(pre_volumes)) - 1.0
    )

    target_returns = _returns(target)
    benchmark_returns = _returns(benchmark)
    beta_days = [
        day
        for day in common_days
        if day < event and day in target_returns and day in benchmark_returns
    ]
    beta_status: dict[str, Any]
    limitations = []
    if len(beta_days) < MIN_BETA_OBSERVATIONS:
        beta_status = {
            "status": "unavailable",
            "observations": len(beta_days),
            "beta": None,
            "daily_alpha": None,
        }
        limitations.append("beta_alpha_insufficient_pre_event_sample")
    else:
        stocks = [target_returns[day] for day in beta_days]
        markets = [benchmark_returns[day] for day in beta_days]
        mean_stock = sum(stocks) / len(stocks)
        mean_market = sum(markets) / len(markets)
        variance = sum((value - mean_market) ** 2 for value in markets)
        if variance <= 0:
            beta_status = {
                "status": "unavailable",
                "observations": len(beta_days),
                "beta": None,
                "daily_alpha": None,
            }
            limitations.append("beta_alpha_zero_benchmark_variance")
        else:
            beta = (
                sum(
                    (stock - mean_stock) * (market - mean_market)
                    for stock, market in zip(stocks, markets, strict=True)
                )
                / variance
            )
            beta_status = {
                "status": "available",
                "observations": len(beta_days),
                "beta": beta,
                "daily_alpha": mean_stock - beta * mean_market,
            }
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": _day(payload["as_of"]),
        "parameters": {"event_date": event, "pre_days": pre_days, "post_days": post_days},
        "dataset_refs": refs,
        "status": "partial" if limitations else "complete",
        "metrics": {
            "window_start": start,
            "window_end": end,
            "target_return": target_return,
            "benchmark_return": benchmark_return,
            "excess_return": target_return - benchmark_return,
            "post_vs_pre_volume_change": volume_change,
            "beta_alpha": beta_status,
        },
        "rows": [
            {
                "date": day,
                "target_close": target_by_day[day]["close"],
                "benchmark_close": benchmark_by_day[day]["close"],
                "target_volume": target_by_day[day]["volume"],
            }
            for day in window_days
        ],
        "limitations": limitations,
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": payload.get("source_hashes", {}),
            "rights": "internal-only",
            "transformations": [
                "align_dates",
                "event_window_returns",
                "volume_ratio",
                "pre_event_ols",
                METHOD_VERSION,
            ],
        },
    }


def _path(value: str) -> Path:
    path = Path(value)
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
