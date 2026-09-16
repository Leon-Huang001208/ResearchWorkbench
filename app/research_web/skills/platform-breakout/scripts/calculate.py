"""Classify prior-window platform breakouts for a bounded supplied watchlist."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
    checked_multiply,
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

LOGGER = logging.getLogger("research.skill.platform_breakout")
SKILL_SLUG = "platform-breakout"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"lookback", "confirmation_buffer_pct", "minimum_resistance_touches"})
RECORD_FIELDS = frozenset({"asset_id", "date", "high", "low", "close"})
CONTRACT_UNITS = {
    "price": "CNY_per_share",
    "buffer": "percent",
    "platform_range": "decimal",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: Any, *, positive: bool = False) -> float:
    return checked_number(value, error=CalculatorError, positive=positive)


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload, required=ROOT_FIELDS, allowed=ALLOWED_ROOT_FIELDS, error=CalculatorError
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
    contract = validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="trade_date",
        adjustment="forward",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    raw_parameters = strict_object(
        payload["parameters"],
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    lookback = raw_parameters["lookback"]
    touches_required = raw_parameters["minimum_resistance_touches"]
    if type(lookback) is not int or not 5 <= lookback <= 250:
        raise CalculatorError("invalid_field_type")
    if type(touches_required) is not int or not 2 <= touches_required <= lookback:
        raise CalculatorError("invalid_field_type")
    buffer_pct = _number(raw_parameters["confirmation_buffer_pct"])
    if not 0 <= buffer_pct <= 10:
        raise CalculatorError("invalid_number")
    parameters = {
        "lookback": lookback,
        "confirmation_buffer_pct": buffer_pct,
        "minimum_resistance_touches": touches_required,
    }
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        contract_provider=contract["provider"],
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for raw in records:
        row = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        asset_id = checked_text(row["asset_id"], error=CalculatorError)
        day = reject_future(row["date"], as_of=as_of, error=CalculatorError)
        high = _number(row["high"], positive=True)
        low = _number(row["low"], positive=True)
        close = _number(row["close"], positive=True)
        if low > high or not low <= close <= high:
            raise CalculatorError("data_not_equivalent")
        series = grouped.setdefault(asset_id, [])
        if series and day <= series[-1]["date"]:
            raise CalculatorError("data_not_equivalent")
        series.append({"date": day, "high": high, "low": low, "close": close})
    max_rows = max(len(series) for series in grouped.values())
    budget.validate_batch(symbol_count=len(grouped), rows_per_symbol=max_rows)
    output: list[dict[str, Any]] = []
    buffer = checked_divide(buffer_pct, 100.0, error=CalculatorError)
    for asset_id in sorted(grouped):
        series = grouped[asset_id]
        if len(series) < lookback + 1:
            raise CalculatorError("insufficient_history")
        if series[-1]["date"] != as_of:
            raise CalculatorError("data_not_equivalent")
        prior = series[-lookback - 1 : -1]
        current = series[-1]
        resistance = max(float(item["high"]) for item in prior)
        support = min(float(item["low"]) for item in prior)
        range_width = checked_divide(
            checked_subtract(resistance, support, error=CalculatorError),
            support,
            error=CalculatorError,
        )
        touch_floor = checked_multiply(
            resistance, checked_subtract(1.0, buffer, error=CalculatorError), error=CalculatorError
        )
        touches = sum(1 for item in prior if float(item["high"]) >= touch_floor)
        upper = checked_multiply(resistance, 1.0 + buffer, error=CalculatorError)
        lower = checked_multiply(
            support, checked_subtract(1.0, buffer, error=CalculatorError), error=CalculatorError
        )
        if touches >= touches_required and float(current["close"]) > upper:
            signal = "confirmed_breakout"
        elif float(current["close"]) < lower:
            signal = "confirmed_breakdown"
        else:
            signal = "inside_or_unconfirmed_platform"
        output.append(
            {
                "asset_id": asset_id,
                "date": current["date"],
                "prior_resistance": resistance,
                "prior_support": support,
                "platform_range": range_width,
                "resistance_touches": touches,
                "current_close": current["close"],
                "research_signal": signal,
            }
        )
    rows, row_delivery = bounded_result_rows(
        output, processed_input_rows=len(records), dataset_refs=refs
    )
    counts = {
        label: sum(1 for row in output if row["research_signal"] == label)
        for label in (
            "confirmed_breakout",
            "confirmed_breakdown",
            "inside_or_unconfirmed_platform",
        )
    }
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": parameters,
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "sample_size": len(records),
            "asset_count": len(grouped),
            "signal_counts": counts,
        },
        "rows": rows,
        "row_delivery": row_delivery,
        "research_summary": {
            "sample_size": len(records),
            "conditions": [
                "prior_window_only",
                "close_beyond_buffer",
                "minimum_resistance_touches",
            ],
            "counterexamples": ["intraday_high_without_close_confirmation_is_unconfirmed"],
            "failure_conditions": [
                "corporate_action_or_adjustment_mismatch",
                "illiquid_or_gap_dominated_prices",
                "platform_definition_changes",
            ],
            "data_cutoff": as_of,
        },
        "limitations": [
            "research_signal_only_not_an_order_or_trade_instruction",
            "single_asset_or_explicit_watchlist_of_at_most_50",
            "no_full_market_or_multi_year_minute_scan",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "prior_window_support_resistance",
                "close_confirmation",
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
