"""Research the lagged rate moving-average signal on one supplied daily series."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_add,
    checked_divide,
    checked_mean,
    checked_multiply,
    checked_number,
    checked_subtract,
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

LOGGER = logging.getLogger("research.skill.rate_ma_timing_research")
SKILL_SLUG = "rate-ma-timing-research"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset(
    {"as_of", "parameters", "data_contract", "series_identity", "dataset_refs", "records"}
)
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"moving_average_window", "deviation_threshold", "position_step"})
RECORD_FIELDS = frozenset({"date", "asset_close", "rate_pct"})
SERIES_IDENTITY_FIELDS = frozenset({"asset_series", "rate_series"})
SERIES_DESCRIPTOR_FIELDS = frozenset({"role", "identity", "version", "tenor"})
SERIES_IDENTITY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
SERIES_ROLE_CONTRACTS = {
    "asset_series": {
        "role": "asset_index",
        "version": "close_v1",
        "tenor": "spot",
    },
    "rate_series": {
        "role": "government_bond_yield",
        "version": "yield_pct_v1",
        "tenor": "10Y",
    },
}
SYNTHETIC_SERIES_IDENTITIES = {
    "asset_series": "synthetic_rate_timing_asset_index",
    "rate_series": "synthetic_rate_timing_government_bond_yield",
}
CONTRACT_UNITS = {
    "asset_close": "index_points",
    "rate": "percent",
    "deviation": "decimal",
    "research_exposure": "decimal",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: Any, *, positive: bool = False) -> float:
    return checked_number(value, error=CalculatorError, positive=positive)


def _parameters(value: Any) -> dict[str, float | int]:
    raw = strict_object(
        value,
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    window = raw["moving_average_window"]
    if type(window) is not int or not 2 <= window <= 500:
        raise CalculatorError("invalid_field_type")
    threshold = _number(raw["deviation_threshold"])
    step = _number(raw["position_step"], positive=True)
    if not 0 <= threshold <= 1 or step > 1:
        raise CalculatorError("invalid_number")
    return {
        "moving_average_window": window,
        "deviation_threshold": threshold,
        "position_step": step,
    }


def _series_identity(value: Any, *, provider: str) -> dict[str, dict[str, str]]:
    identity = strict_object(
        value,
        required=SERIES_IDENTITY_FIELDS,
        allowed=SERIES_IDENTITY_FIELDS,
        error=CalculatorError,
    )
    normalized: dict[str, dict[str, str]] = {}
    for name in SERIES_IDENTITY_FIELDS:
        descriptor = strict_object(
            identity[name],
            required=SERIES_DESCRIPTOR_FIELDS,
            allowed=SERIES_DESCRIPTOR_FIELDS,
            error=CalculatorError,
        )
        normalized[name] = {
            field: descriptor[field] for field in ("role", "identity", "version", "tenor")
        }
        if not all(isinstance(item, str) for item in normalized[name].values()):
            raise CalculatorError("invalid_field_type")
        expected = SERIES_ROLE_CONTRACTS[name]
        if any(normalized[name][field] != value for field, value in expected.items()):
            raise CalculatorError("data_not_equivalent")
        if re.fullmatch(SERIES_IDENTITY_PATTERN, normalized[name]["identity"]) is None:
            raise CalculatorError("data_not_equivalent")
        if provider == "synthetic" and (
            normalized[name]["identity"] != SYNTHETIC_SERIES_IDENTITIES[name]
        ):
            raise CalculatorError("data_not_equivalent")
        if provider not in {"synthetic", "user_input"}:
            raise CalculatorError("data_not_equivalent")
    if len({descriptor["identity"] for descriptor in normalized.values()}) != len(normalized):
        raise CalculatorError("data_not_equivalent")
    return normalized


def calculate(payload: dict[str, Any], *, input_bytes: int) -> dict[str, Any]:
    budget = WorkloadBudget()
    budget.add_input(rows=0, bytes_count=input_bytes)
    payload = strict_object(
        payload,
        required=ROOT_FIELDS,
        allowed=ALLOWED_ROOT_FIELDS,
        error=CalculatorError,
    )
    as_of = iso_day(payload["as_of"], error=CalculatorError)
    data_contract = validate_data_contract(
        payload["data_contract"],
        mapping_id=SKILL_SLUG,
        mapping_version=METHOD_VERSION,
        units=CONTRACT_UNITS,
        date_semantics="trade_date",
        adjustment="asset_forward_rate_not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    series_identity = _series_identity(
        payload["series_identity"], provider=data_contract["provider"]
    )
    parameters = _parameters(payload["parameters"])
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    window = int(parameters["moving_average_window"])
    if len(records) < window + 1:
        raise CalculatorError("insufficient_history")
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        contract_provider=data_contract["provider"],
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)
    normalized: list[dict[str, Any]] = []
    previous_date: str | None = None
    for raw in records:
        row = strict_object(
            raw,
            required=RECORD_FIELDS,
            allowed=RECORD_FIELDS,
            error=CalculatorError,
        )
        day = reject_future(row["date"], as_of=as_of, error=CalculatorError)
        if previous_date is not None and day <= previous_date:
            raise CalculatorError("data_not_equivalent")
        previous_date = day
        normalized.append(
            {
                "date": day,
                "asset_close": _number(row["asset_close"], positive=True),
                "rate_pct": _number(row["rate_pct"]),
            }
        )
    if normalized[-1]["date"] != as_of:
        raise CalculatorError("data_not_equivalent")

    moving_averages: list[float | None] = [None] * len(normalized)
    for index in range(window - 1, len(normalized)):
        moving_averages[index] = checked_mean(
            [float(row["rate_pct"]) for row in normalized[index - window + 1 : index + 1]],
            error=CalculatorError,
        )

    processed_signal = 0
    output: list[dict[str, Any]] = []
    for index in range(window, len(normalized)):
        current = normalized[index]
        current_average = moving_averages[index]
        prior_average = moving_averages[index - 1]
        if current_average is None or prior_average is None or current_average == 0:
            raise CalculatorError("invalid_number")
        deviation = abs(
            checked_subtract(
                checked_divide(float(current["rate_pct"]), current_average, error=CalculatorError),
                1.0,
                error=CalculatorError,
            )
        )
        prior_processed = processed_signal
        preliminary = 0
        if deviation > float(parameters["deviation_threshold"]):
            if current_average < prior_average:
                preliminary = -1
            elif current_average > prior_average:
                preliminary = 1
        if preliminary:
            processed_signal = preliminary
        exposure = checked_add(
            1.0,
            checked_multiply(
                -float(prior_processed),
                float(parameters["position_step"]),
                error=CalculatorError,
            ),
            error=CalculatorError,
        )
        label = {
            -1: "rate_falling_above_deviation",
            0: "no_new_rate_signal",
            1: "rate_rising_above_deviation",
        }[preliminary]
        output.append(
            {
                "date": current["date"],
                "rate_pct": current["rate_pct"],
                "moving_average_pct": current_average,
                "deviation": deviation,
                "preliminary_signal": label,
                "persistent_signal": processed_signal,
                "lagged_research_exposure": exposure,
            }
        )
    rows, row_delivery = bounded_result_rows(
        output,
        processed_input_rows=len(normalized),
        dataset_refs=refs,
    )
    latest = output[-1]
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": parameters,
        "series_identity": series_identity,
        "dataset_refs": refs,
        "status": "partial" if source_limitations else "complete",
        "metrics": {
            "sample_size": len(normalized),
            "signal_observations": len(output),
            "latest_research_signal": latest["preliminary_signal"],
            "latest_lagged_research_exposure": latest["lagged_research_exposure"],
        },
        "rows": rows,
        "row_delivery": row_delivery,
        "research_summary": {
            "sample_size": len(normalized),
            "conditions": [
                "rate_moving_average_direction_and_absolute_deviation_threshold",
                "research_exposure_uses_prior_persistent_signal",
            ],
            "counterexamples": ["small_deviation_produces_no_new_signal"],
            "failure_conditions": [
                "rate_definition_or_unit_changes",
                "missing_or_non_equivalent_trading_dates",
                "structural_rate_regime_change",
            ],
            "data_cutoff": as_of,
        },
        "limitations": [
            "research_signal_only_not_an_order_or_trade_instruction",
            "no_financing_or_transaction_cost_model",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "trailing_rate_moving_average",
                "absolute_rate_deviation",
                "one_observation_signal_lag",
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
