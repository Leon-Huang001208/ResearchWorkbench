"""Measure rolling turnover-share crowding from supplied industry aggregates."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_add,
    checked_divide,
    checked_number,
    checked_subtract,
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

LOGGER = logging.getLogger("research.skill.industry_crowding_monitor")
SKILL_SLUG = "industry-crowding-monitor"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "datahub", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"rolling_days", "percentile_days", "high_crowding_threshold"})
RECORD_FIELDS = frozenset({"industry", "date", "industry_turnover", "total_market_turnover"})
CONTRACT_UNITS = {
    "industry_turnover": "CNY",
    "total_market_turnover": "CNY",
    "crowding": "rolling_turnover_share_decimal",
    "percentile": "empirical_0_to_1",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload, required=ROOT_FIELDS, allowed=ALLOWED_ROOT_FIELDS, error=CalculatorError
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
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
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    rolling_days = parameters["rolling_days"]
    percentile_days = parameters["percentile_days"]
    threshold = checked_number(parameters["high_crowding_threshold"], error=CalculatorError)
    if (
        type(rolling_days) is not int
        or not 1 <= rolling_days <= 250
        or type(percentile_days) is not int
        or not 2 <= percentile_days <= 1000
        or not 0 <= threshold <= 1
    ):
        raise CalculatorError("invalid_field_type")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    refs = validate_dataset_refs(
        payload["dataset_refs"], as_of=as_of, providers=SUPPORTED_PROVIDERS, error=CalculatorError
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    grouped: dict[str, list[dict[str, Any]]] = {}
    seen: set[tuple[str, str]] = set()
    total_by_date: dict[str, float] = {}
    for raw in records:
        raw = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        industry = checked_text(raw["industry"], error=CalculatorError)
        day = reject_future(raw["date"], as_of=as_of, error=CalculatorError)
        if (industry, day) in seen:
            raise CalculatorError("duplicate_industry_date")
        seen.add((industry, day))
        industry_turnover = checked_number(raw["industry_turnover"], error=CalculatorError)
        total_turnover = checked_number(
            raw["total_market_turnover"], error=CalculatorError, positive=True
        )
        if industry_turnover < 0 or industry_turnover > total_turnover:
            raise CalculatorError("invalid_turnover")
        if day in total_by_date and total_by_date[day] != total_turnover:
            raise CalculatorError("inconsistent_market_total")
        total_by_date[day] = total_turnover
        grouped.setdefault(industry, []).append(
            {
                "date": day,
                "industry_turnover": industry_turnover,
                "total_market_turnover": total_turnover,
            }
        )
    budget.validate_batch(
        symbol_count=len(grouped), rows_per_symbol=max(len(values) for values in grouped.values())
    )
    rows: list[dict[str, Any]] = []
    for industry, series in grouped.items():
        series.sort(key=lambda row: row["date"])
        if len(series) < rolling_days:
            raise CalculatorError("insufficient_history")
        industry_prefix = [0.0]
        market_prefix = [0.0]
        for row in series:
            industry_prefix.append(
                checked_add(industry_prefix[-1], row["industry_turnover"], error=CalculatorError)
            )
            market_prefix.append(
                checked_add(market_prefix[-1], row["total_market_turnover"], error=CalculatorError)
            )
        crowding_history: list[float] = []
        for end in range(rolling_days, len(series) + 1):
            start = end - rolling_days
            industry_sum = checked_subtract(
                industry_prefix[end], industry_prefix[start], error=CalculatorError
            )
            market_sum = checked_subtract(
                market_prefix[end], market_prefix[start], error=CalculatorError
            )
            crowding_history.append(checked_divide(industry_sum, market_sum, error=CalculatorError))
        comparison = crowding_history[-percentile_days:]
        latest = crowding_history[-1]
        percentile = checked_divide(
            float(sum(1 for value in comparison if value <= latest)),
            float(len(comparison)),
            error=CalculatorError,
        )
        rows.append(
            {
                "industry": industry,
                "date": series[-1]["date"],
                "rolling_turnover_share": latest,
                "crowding_percentile": percentile,
                "percentile_observations": len(comparison),
                "research_signal": (
                    "high_crowding" if percentile >= threshold else "normal_crowding"
                ),
            }
        )
    rows.sort(
        key=lambda row: (
            -row["crowding_percentile"],
            -row["rolling_turnover_share"],
            row["industry"],
        )
    )
    output_rows, row_delivery = bounded_result_rows(
        rows, processed_input_rows=len(records), dataset_refs=refs
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {
            "rolling_days": rolling_days,
            "percentile_days": percentile_days,
            "high_crowding_threshold": threshold,
        },
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "industry_count": len(rows),
            "high_crowding_count": sum(row["research_signal"] == "high_crowding" for row in rows),
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": [
            "preaggregated_industry_and_market_turnover_only",
            "percentile_is_empirical_less_than_or_equal_rank",
            "research_signal_not_trading_advice",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "rolling_turnover_share",
                "empirical_percentile",
                "threshold_signal",
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
        sys.stdout.write(
            strict_json_dumps(calculate(payload, input_bytes=size), error=CalculatorError)
        )
        return 0
    except (CalculatorError, json.JSONDecodeError, UnicodeError, OSError, ValueError) as exc:
        code = getattr(exc, "code", "invalid_input")
        LOGGER.error("calculator_failed code=%s", code)
        sys.stderr.write(json.dumps(safe_error_payload(exc), sort_keys=True, allow_nan=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
