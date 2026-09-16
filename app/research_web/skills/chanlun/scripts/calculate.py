"""Build deterministic confirmed fractals and strokes for one supplied series."""

from __future__ import annotations

import json
import logging
import sys
from itertools import pairwise
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_number,
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

LOGGER = logging.getLogger("research.skill.chanlun")
SKILL_SLUG = "chanlun"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"pivot_span", "minimum_separation_bars"})
RECORD_FIELDS = frozenset({"asset_id", "date", "high", "low", "close"})
CONTRACT_UNITS = {
    "price": "CNY_per_share",
    "bar_index": "integer",
    "stroke_change": "CNY_per_share",
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
    span = raw_parameters["pivot_span"]
    separation = raw_parameters["minimum_separation_bars"]
    if type(span) is not int or not 1 <= span <= 20:
        raise CalculatorError("invalid_field_type")
    if type(separation) is not int or not 1 <= separation <= 100:
        raise CalculatorError("invalid_field_type")
    parameters = {"pivot_span": span, "minimum_separation_bars": separation}
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    if len(records) < 2 * span + 2:
        raise CalculatorError("insufficient_history")
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        contract_provider=contract["provider"],
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    normalized: list[dict[str, Any]] = []
    asset_id: str | None = None
    previous_date: str | None = None
    for raw in records:
        row = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        row_asset = checked_text(row["asset_id"], error=CalculatorError)
        if asset_id is None:
            asset_id = row_asset
        elif row_asset != asset_id:
            raise CalculatorError("data_not_equivalent")
        day = reject_future(row["date"], as_of=as_of, error=CalculatorError)
        if previous_date is not None and day <= previous_date:
            raise CalculatorError("data_not_equivalent")
        previous_date = day
        high = _number(row["high"], positive=True)
        low = _number(row["low"], positive=True)
        close = _number(row["close"], positive=True)
        if low > high or not low <= close <= high:
            raise CalculatorError("data_not_equivalent")
        normalized.append({"date": day, "high": high, "low": low, "close": close})
    if normalized[-1]["date"] != as_of or asset_id is None:
        raise CalculatorError("data_not_equivalent")

    candidates: list[dict[str, Any]] = []
    for index in range(span, len(normalized) - span):
        window = normalized[index - span : index + span + 1]
        highs = [float(row["high"]) for row in window]
        lows = [float(row["low"]) for row in window]
        center_high = float(normalized[index]["high"])
        center_low = float(normalized[index]["low"])
        top_plateau = center_high == max(highs) and highs.count(center_high) > 1
        bottom_plateau = center_low == min(lows) and lows.count(center_low) > 1
        if top_plateau or bottom_plateau:
            raise CalculatorError("ambiguous_structure")
        is_top = center_high > max(highs[:span] + highs[span + 1 :])
        is_bottom = center_low < min(lows[:span] + lows[span + 1 :])
        if is_top and is_bottom:
            raise CalculatorError("ambiguous_structure")
        if is_top:
            candidates.append(
                {
                    "index": index,
                    "date": normalized[index]["date"],
                    "kind": "top",
                    "price": center_high,
                }
            )
        elif is_bottom:
            candidates.append(
                {
                    "index": index,
                    "date": normalized[index]["date"],
                    "kind": "bottom",
                    "price": center_low,
                }
            )

    pivots: list[dict[str, Any]] = []
    for pivot in candidates:
        if not pivots:
            pivots.append(pivot)
            continue
        prior = pivots[-1]
        if pivot["kind"] == prior["kind"]:
            if pivot["price"] == prior["price"]:
                raise CalculatorError("ambiguous_structure")
            more_extreme = (
                pivot["price"] > prior["price"]
                if pivot["kind"] == "top"
                else pivot["price"] < prior["price"]
            )
            if more_extreme:
                pivots[-1] = pivot
            continue
        if int(pivot["index"]) - int(prior["index"]) < separation:
            raise CalculatorError("ambiguous_structure")
        pivots.append(pivot)
    strokes: list[dict[str, Any]] = []
    for start, end in pairwise(pivots):
        direction = "up" if end["kind"] == "top" else "down"
        strokes.append(
            {
                "start_date": start["date"],
                "end_date": end["date"],
                "start_kind": start["kind"],
                "end_kind": end["kind"],
                "start_price": start["price"],
                "end_price": end["price"],
                "direction": direction,
            }
        )
    latest_signal = (
        "confirmed_up_swing"
        if strokes and strokes[-1]["direction"] == "up"
        else "confirmed_down_swing" if strokes else "insufficient_confirmed_structure"
    )
    rows, row_delivery = bounded_result_rows(
        strokes, processed_input_rows=len(normalized), dataset_refs=refs
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": parameters,
        "dataset_refs": refs,
        "status": "partial" if source_limitations or not strokes else "complete",
        "metrics": {
            "sample_size": len(normalized),
            "confirmed_pivot_count": len(pivots),
            "confirmed_stroke_count": len(strokes),
            "latest_research_signal": latest_signal,
        },
        "rows": rows,
        "row_delivery": row_delivery,
        "research_summary": {
            "sample_size": len(normalized),
            "conditions": ["strict_confirmed_fractals", "alternating_non_recursive_strokes"],
            "counterexamples": ["equal_extreme_plateau_is_ambiguous_and_rejected"],
            "failure_conditions": [
                "different_inclusion_or_fractal_rules",
                "corporate_action_or_adjustment_mismatch",
                "unconfirmed_terminal_bars",
            ],
            "data_cutoff": as_of,
        },
        "limitations": [
            "research_signal_only_not_an_order_or_trade_instruction",
            "one_asset_per_run",
            "confirmed_fractal_and_stroke_subset_not_a_complete_chanlun_system",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "strict_local_fractals",
                "iterative_alternating_strokes",
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
