"""Compare two supplied style indices with one explicit deterministic rule."""

from __future__ import annotations

import json
import logging
import re
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
    checked_mean,
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

LOGGER = logging.getLogger("research.skill.style_rotation_research")
SKILL_SLUG = "style-rotation-research"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset(
    {"as_of", "parameters", "data_contract", "series_identity", "dataset_refs", "records"}
)
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset(
    {
        "method",
        "moving_average_window",
        "deviation_threshold",
        "relative_strength_window",
        "relative_momentum_window",
    }
)
RECORD_FIELDS = frozenset({"date", "style_a_close", "style_b_close"})
SERIES_IDENTITY_FIELDS = frozenset({"style_a_series", "style_b_series"})
SERIES_DESCRIPTOR_FIELDS = frozenset({"role", "identity", "version", "tenor"})
SERIES_IDENTITY_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
SERIES_ROLE_CONTRACTS = {
    "style_a_series": {
        "role": "style_a_index",
        "version": "close_v1",
        "tenor": "spot",
    },
    "style_b_series": {
        "role": "style_b_index",
        "version": "close_v1",
        "tenor": "spot",
    },
}
SYNTHETIC_SERIES_IDENTITIES = {
    "style_a_series": "synthetic_style_a_index",
    "style_b_series": "synthetic_style_b_index",
}
CONTRACT_UNITS = {
    "style_close": "index_points",
    "relative_ratio": "decimal",
    "relative_strength": "decimal_return_spread",
    "relative_momentum": "decimal_change",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: Any, *, positive: bool = False) -> float:
    return checked_number(value, error=CalculatorError, positive=positive)


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
        if any(normalized[name][field] != expected[field] for field in expected):
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
    series_identity = _series_identity(payload["series_identity"], provider=contract["provider"])
    raw_parameters = strict_object(
        payload["parameters"],
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    method = checked_text(raw_parameters["method"], error=CalculatorError)
    if method not in {"moving_average_deviation", "relative_strength_momentum"}:
        raise CalculatorError("ambiguous_rule")
    integer_parameters: dict[str, int] = {}
    for name in (
        "moving_average_window",
        "relative_strength_window",
        "relative_momentum_window",
    ):
        value = raw_parameters[name]
        if type(value) is not int or not 2 <= value <= 500:
            raise CalculatorError("invalid_field_type")
        integer_parameters[name] = value
    threshold = _number(raw_parameters["deviation_threshold"])
    if not 0 <= threshold <= 1:
        raise CalculatorError("invalid_number")
    parameters = {"method": method, **integer_parameters, "deviation_threshold": threshold}
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    needed = (
        integer_parameters["moving_average_window"] + 1
        if method == "moving_average_deviation"
        else integer_parameters["relative_strength_window"]
        + integer_parameters["relative_momentum_window"]
        - 1
    )
    if len(records) < needed:
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
    previous_date: str | None = None
    for raw in records:
        row = strict_object(
            raw, required=RECORD_FIELDS, allowed=RECORD_FIELDS, error=CalculatorError
        )
        day = reject_future(row["date"], as_of=as_of, error=CalculatorError)
        if previous_date is not None and day <= previous_date:
            raise CalculatorError("data_not_equivalent")
        previous_date = day
        normalized.append(
            {
                "date": day,
                "style_a_close": _number(row["style_a_close"], positive=True),
                "style_b_close": _number(row["style_b_close"], positive=True),
            }
        )
    if normalized[-1]["date"] != as_of:
        raise CalculatorError("data_not_equivalent")
    ratios = [
        checked_divide(
            float(row["style_a_close"]), float(row["style_b_close"]), error=CalculatorError
        )
        for row in normalized
    ]
    persistent = "neutral"
    output: list[dict[str, Any]] = []
    if method == "moving_average_deviation":
        window = integer_parameters["moving_average_window"]
        averages: list[float | None] = [None] * len(ratios)
        for index in range(window - 1, len(ratios)):
            averages[index] = checked_mean(
                ratios[index - window + 1 : index + 1], error=CalculatorError
            )
        for index in range(window, len(ratios)):
            average = averages[index]
            prior_average = averages[index - 1]
            if average is None or prior_average is None or average == 0:
                raise CalculatorError("invalid_number")
            deviation = abs(
                checked_subtract(
                    checked_divide(ratios[index], average, error=CalculatorError),
                    1.0,
                    error=CalculatorError,
                )
            )
            signal = "neutral"
            if deviation < threshold:
                if average > prior_average:
                    signal = "style_a_preferred"
                elif average < prior_average:
                    signal = "style_b_preferred"
            if signal != "neutral":
                persistent = signal
            output.append(
                {
                    "date": normalized[index]["date"],
                    "relative_ratio": ratios[index],
                    "relative_strength": None,
                    "relative_momentum": None,
                    "moving_average": average,
                    "deviation": deviation,
                    "research_signal": signal,
                    "persistent_research_signal": persistent,
                }
            )
    else:
        strength_window = integer_parameters["relative_strength_window"]
        momentum_window = integer_parameters["relative_momentum_window"]
        strengths: list[float | None] = [None] * len(normalized)
        for index in range(strength_window - 1, len(normalized)):
            prior = index - strength_window + 1
            a_return = checked_subtract(
                checked_divide(
                    float(normalized[index]["style_a_close"]),
                    float(normalized[prior]["style_a_close"]),
                    error=CalculatorError,
                ),
                1.0,
                error=CalculatorError,
            )
            b_return = checked_subtract(
                checked_divide(
                    float(normalized[index]["style_b_close"]),
                    float(normalized[prior]["style_b_close"]),
                    error=CalculatorError,
                ),
                1.0,
                error=CalculatorError,
            )
            strengths[index] = checked_subtract(a_return, b_return, error=CalculatorError)
        start = strength_window + momentum_window - 2
        for index in range(start, len(normalized)):
            strength = strengths[index]
            prior_strength = strengths[index - momentum_window + 1]
            if strength is None or prior_strength is None:
                raise CalculatorError("insufficient_history")
            momentum = checked_subtract(strength, prior_strength, error=CalculatorError)
            if strength >= 0 and momentum >= 0:
                signal = "style_a_preferred"
            elif strength < 0 and momentum <= 0:
                signal = "style_b_preferred"
            else:
                signal = "neutral"
            if signal != "neutral":
                persistent = signal
            output.append(
                {
                    "date": normalized[index]["date"],
                    "relative_ratio": ratios[index],
                    "relative_strength": strength,
                    "relative_momentum": momentum,
                    "moving_average": None,
                    "deviation": None,
                    "research_signal": signal,
                    "persistent_research_signal": persistent,
                }
            )
    rows, row_delivery = bounded_result_rows(
        output, processed_input_rows=len(normalized), dataset_refs=refs
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
            "latest_research_signal": latest["research_signal"],
            "latest_persistent_research_signal": latest["persistent_research_signal"],
        },
        "rows": rows,
        "row_delivery": row_delivery,
        "research_summary": {
            "sample_size": len(normalized),
            "conditions": [method, "two_explicit_style_index_series"],
            "counterexamples": ["conflicting_strength_and_momentum_is_neutral"],
            "failure_conditions": [
                "style_index_definition_changes",
                "non_equivalent_adjustment_or_calendar",
                "structural_style_regime_change",
            ],
            "data_cutoff": as_of,
        },
        "limitations": [
            "research_signal_only_not_an_order_or_trade_instruction",
            "compares_only_the_two_supplied_style_indices",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [method, "persistent_neutral_handling", METHOD_VERSION],
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
