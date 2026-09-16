"""Research a supplied equity risk-premium series with rolling empirical ranks."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from cpu_budget import WorkloadBudget
from input_contract import (
    bounded_result_rows,
    checked_divide,
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

LOGGER = logging.getLogger("research.skill.equity_risk_premium_timing")
SKILL_SLUG = "equity-risk-premium-timing"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset(
    {"as_of", "parameters", "data_contract", "series_identity", "dataset_refs", "records"}
)
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"quantile_window", "lower_quantile", "upper_quantile"})
RECORD_FIELDS = frozenset({"date", "index_close", "pe_ttm", "bond_yield_pct"})
SERIES_IDENTITY_FIELDS = frozenset({"index_series", "bond_yield_series"})
SERIES_DESCRIPTOR_FIELDS = frozenset({"identity", "version", "tenor"})
EXPECTED_SERIES_IDENTITY = {
    "index_series": {
        "identity": "synthetic_equity_risk_premium_index",
        "version": "pe_ttm_v1",
        "tenor": "spot",
    },
    "bond_yield_series": {
        "identity": "synthetic_equity_risk_premium_government_bond_yield",
        "version": "yield_pct_v1",
        "tenor": "10Y",
    },
}
CONTRACT_UNITS = {
    "index_close": "index_points",
    "pe_ttm": "multiple",
    "bond_yield": "percent",
    "risk_premium": "decimal",
    "percentile": "empirical_0_to_1",
}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _number(value: Any, *, positive: bool = False) -> float:
    return checked_number(value, error=CalculatorError, positive=positive)


def _series_identity(value: Any) -> dict[str, dict[str, str]]:
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
        normalized[name] = {field: descriptor[field] for field in ("identity", "version", "tenor")}
        if not all(isinstance(item, str) and item for item in normalized[name].values()):
            raise CalculatorError("invalid_field_type")
    if normalized != EXPECTED_SERIES_IDENTITY:
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
        adjustment="index_forward_rates_not_applicable",
        providers=SUPPORTED_PROVIDERS,
        error=CalculatorError,
    )
    series_identity = _series_identity(payload["series_identity"])
    raw_parameters = strict_object(
        payload["parameters"],
        required=PARAMETER_FIELDS,
        allowed=PARAMETER_FIELDS,
        error=CalculatorError,
    )
    window = raw_parameters["quantile_window"]
    if type(window) is not int or not 2 <= window <= 5000:
        raise CalculatorError("invalid_field_type")
    lower = _number(raw_parameters["lower_quantile"])
    upper = _number(raw_parameters["upper_quantile"])
    if not 0 <= lower < upper <= 1:
        raise CalculatorError("invalid_number")
    parameters = {"quantile_window": window, "lower_quantile": lower, "upper_quantile": upper}
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    if len(records) < window:
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
        pe = _number(row["pe_ttm"], positive=True)
        yield_pct = _number(row["bond_yield_pct"])
        premium = checked_subtract(
            checked_divide(1.0, pe, error=CalculatorError),
            checked_divide(yield_pct, 100.0, error=CalculatorError),
            error=CalculatorError,
        )
        normalized.append(
            {
                "date": day,
                "index_close": _number(row["index_close"], positive=True),
                "pe_ttm": pe,
                "bond_yield_pct": yield_pct,
                "risk_premium": premium,
            }
        )
    if normalized[-1]["date"] != as_of:
        raise CalculatorError("data_not_equivalent")
    output: list[dict[str, Any]] = []
    for index in range(window - 1, len(normalized)):
        row = normalized[index]
        history = [
            float(item["risk_premium"]) for item in normalized[index - window + 1 : index + 1]
        ]
        percentile = checked_divide(
            sum(1 for value in history if value <= float(row["risk_premium"])),
            len(history),
            error=CalculatorError,
        )
        if percentile > upper:
            signal = "elevated_risk_premium"
        elif percentile < lower:
            signal = "compressed_risk_premium"
        else:
            signal = "middle_risk_premium"
        output.append({**row, "rolling_percentile": percentile, "research_signal": signal})
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
            "latest_risk_premium": latest["risk_premium"],
            "latest_percentile": latest["rolling_percentile"],
            "latest_research_signal": latest["research_signal"],
        },
        "rows": rows,
        "row_delivery": row_delivery,
        "research_summary": {
            "sample_size": len(normalized),
            "conditions": ["earnings_yield_minus_bond_yield", "rolling_empirical_percentile"],
            "counterexamples": ["middle_percentile_has_no_extreme_signal"],
            "failure_conditions": [
                "pe_definition_or_bond_yield_maturity_changes",
                "loss_making_index_or_nonpositive_pe",
                "structural_valuation_regime_change",
            ],
            "data_cutoff": as_of,
        },
        "limitations": [
            "research_signal_only_not_an_order_or_trade_instruction",
            "empirical_rank_is_window_dependent",
            *source_limitations,
        ],
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "earnings_yield_minus_bond_yield",
                "rolling_empirical_rank",
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
