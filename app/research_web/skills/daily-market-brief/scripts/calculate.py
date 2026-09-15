"""Deterministically arrange supplied market evidence into a daily brief."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
    checked_mean,
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

LOGGER = logging.getLogger("research.skill.daily_market_brief")
SKILL_SLUG = "daily-market-brief"
METHOD_VERSION = "1.0.0"
REQUIRED_ROOT_FIELDS = (
    "market_snapshot",
    "breadth",
    "sectors",
    "themes",
    "news",
    "as_of",
    "dataset_refs",
    "parameters",
    "data_contract",
)
PRIMARY_ROWS_FIELD = "market_snapshot"
ALLOWED_ROOT_FIELDS = frozenset(
    (
        *REQUIRED_ROOT_FIELDS,
        "source_hashes",
    )
)
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub"})
DATASET_PROVIDERS = frozenset({"synthetic", "datahub", "wind"})
CONTRACT_UNITS = {
    "price": "native_quote",
    "change_pct": "percent",
    "turnover": "CNY",
}


class CalculatorError(ValueError):
    """Stable content-free calculator rejection."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _day(value: Any) -> str:
    return iso_day(value, error=CalculatorError)


def _number(value: Any) -> float:
    return checked_number(value, error=CalculatorError)


def _text(value: Any) -> str:
    return checked_text(value, error=CalculatorError)


def _list(payload: dict[str, Any], field: str) -> list[Any]:
    if field not in payload:
        raise CalculatorError("missing_required_field")
    value = payload[field]
    if not isinstance(value, list):
        raise CalculatorError("invalid_field_type")
    return value


def _count(value: Any) -> int:
    if type(value) is not int:
        raise CalculatorError("invalid_field_type")
    if value < 0:
        raise CalculatorError("invalid_number")
    return value


def _base(
    payload: dict[str, Any], *, rows: int, budget: WorkloadBudget
) -> tuple[WorkloadBudget, dict]:
    strict_object(
        payload,
        required=frozenset(REQUIRED_ROOT_FIELDS),
        allowed=ALLOWED_ROOT_FIELDS,
        error=CalculatorError,
    )
    if not isinstance(payload[REQUIRED_ROOT_FIELDS[0]], list):
        raise CalculatorError("invalid_field_type")
    budget.add_input(rows=rows, bytes_count=0)
    as_of = _day(payload["as_of"])
    validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="trade_date",
        adjustment="not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    parameters = strict_object(
        payload["parameters"],
        required=frozenset({"market", "currency"}),
        allowed=frozenset({"market", "currency"}),
        error=CalculatorError,
    )
    parameters = {"market": _text(parameters["market"]), "currency": parameters["currency"]}
    if parameters["currency"] != "CNY":
        raise CalculatorError("data_not_equivalent")
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=DATASET_PROVIDERS,
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    return budget, {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": parameters,
        "dataset_refs": refs,
        "source_hashes": source_hashes,
        "source_limitations": source_limitations,
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
        raw = strict_object(
            raw,
            required=frozenset({"date", "asset", "name", "price", "change_pct", "turnover"}),
            allowed=frozenset({"date", "asset", "name", "price", "change_pct", "turnover"}),
            error=CalculatorError,
        )
        indices.append(
            {
                "date": reject_future(raw["date"], as_of=result["as_of"], error=CalculatorError),
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
            raw = strict_object(
                raw,
                required=frozenset({"date", "name", "change_pct"}),
                allowed=frozenset({"date", "name", "change_pct"}),
                error=CalculatorError,
            )
            values.append(
                {
                    "date": reject_future(
                        raw["date"], as_of=result["as_of"], error=CalculatorError
                    ),
                    "name": _text(raw.get("name")),
                    "change_pct": _number(raw.get("change_pct")),
                }
            )
        return sorted(values, key=lambda row: (-row["change_pct"], row["name"]))

    news = []
    for raw in collections["news"]:
        raw = strict_object(
            raw,
            required=frozenset({"published_at", "title", "source", "source_ref"}),
            allowed=frozenset({"published_at", "title", "source", "source_ref"}),
            error=CalculatorError,
        )
        if not raw.get("source_ref"):
            raise CalculatorError("evidence_required")
        news.append(
            {
                "published_at": reject_future(
                    raw["published_at"], as_of=result["as_of"], error=CalculatorError
                ),
                "title": _text(raw.get("title")),
                "source": _text(raw.get("source")),
                "source_ref": _text(raw.get("source_ref")),
            }
        )
    news.sort(key=lambda row: (row["published_at"], row["source_ref"]))
    breadth = payload.get("breadth")
    breadth = strict_object(
        breadth,
        required=frozenset({"date", "advances", "declines", "flat"}),
        allowed=frozenset({"date", "advances", "declines", "flat"}),
        error=CalculatorError,
    )
    breadth_date = reject_future(breadth["date"], as_of=result["as_of"], error=CalculatorError)
    advances = _count(breadth.get("advances"))
    declines = _count(breadth.get("declines"))
    flat = _count(breadth.get("flat"))
    covered = advances + declines + flat
    if covered == 0 or not indices:
        raise CalculatorError("empty_input")

    output_rows, row_delivery = bounded_result_rows(
        {
            "market_snapshot": indices,
            "breadth": {
                "date": breadth_date,
                "advances": advances,
                "declines": declines,
                "flat": flat,
            },
            "sectors": ranked("sectors"),
            "themes": ranked("themes"),
            "news_evidence": news,
        },
        processed_input_rows=row_count,
        dataset_refs=result["dataset_refs"],
    )
    result.update(
        status="partial" if result["source_limitations"] else "complete",
        metrics={
            "index_count": len(indices),
            "average_change_pct": checked_mean(
                [row["change_pct"] for row in indices], error=CalculatorError
            ),
            "total_turnover": checked_sum(
                [row["turnover"] for row in indices], error=CalculatorError
            ),
            "advance_ratio": checked_divide(advances, covered, error=CalculatorError),
            "news_count": len(news),
        },
        rows=output_rows,
        row_delivery=row_delivery,
        limitations=[
            "arrangement_only_no_event_or_policy_inference",
            *result.pop("source_limitations"),
        ],
        research_only=True,
        provenance={
            "dataset_refs": result["dataset_refs"],
            "source_hashes": result.pop("source_hashes"),
            "rights": "internal-only",
            "transformations": ["validate", "sort", "aggregate", METHOD_VERSION],
        },
    )
    return result


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
