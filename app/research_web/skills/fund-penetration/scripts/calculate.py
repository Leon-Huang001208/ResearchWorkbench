"""Flatten a supplied fund-of-funds holding graph into terminal exposures."""

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
    checked_multiply,
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

LOGGER = logging.getLogger("research.skill.fund_penetration")
SKILL_SLUG = "fund-penetration"
METHOD_VERSION = "1.0.0"
SUPPORTED_PROVIDERS = frozenset({"synthetic", "user_input"})
ROOT_FIELDS = frozenset({"as_of", "parameters", "data_contract", "dataset_refs", "records"})
ALLOWED_ROOT_FIELDS = ROOT_FIELDS | {"source_hashes"}
PARAMETER_FIELDS = frozenset({"root_fund_id", "max_depth"})
RECORD_FIELDS = frozenset(
    {"owner_id", "holding_id", "holding_type", "weight", "weight_unit", "as_of"}
)
CONTRACT_UNITS = {"weight": "record_declared_decimal_or_percent", "output_weight": "decimal"}


class CalculatorError(ValueError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _weight(value: Any, unit: Any) -> float:
    weight = checked_number(value, error=CalculatorError)
    if unit == "percent":
        weight = checked_divide(weight, 100.0, error=CalculatorError)
    elif unit != "decimal":
        raise CalculatorError("data_not_equivalent")
    if weight <= 0 or weight > 1:
        raise CalculatorError("invalid_weight")
    return weight


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
        date_semantics="holding_disclosure_date",
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
    root = checked_text(parameters["root_fund_id"], error=CalculatorError)
    max_depth = parameters["max_depth"]
    if type(max_depth) is not int or not 1 <= max_depth <= 20:
        raise CalculatorError("invalid_field_type")
    records = payload["records"]
    if not isinstance(records, list) or not records:
        raise CalculatorError("empty_input")
    budget.add_input(rows=len(records), bytes_count=0)
    budget.validate_series(len(records))
    refs = validate_dataset_refs(
        payload["dataset_refs"],
        as_of=as_of,
        providers=SUPPORTED_PROVIDERS,
        contract_provider=data_contract["provider"],
        error=CalculatorError,
    )
    source_hashes, source_limitations = validate_source_hashes(payload, error=CalculatorError)

    edges: dict[tuple[str, str, str], float] = {}
    edge_dates: dict[tuple[str, str, str], str] = {}
    duplicate_edges = 0
    holding_types: dict[str, str] = {}
    owners: set[str] = set()
    raw_rows_by_owner: dict[str, int] = {}
    snapshot_date: str | None = None
    for raw in records:
        raw = strict_object(
            raw,
            required=RECORD_FIELDS,
            allowed=RECORD_FIELDS,
            error=CalculatorError,
        )
        owner = checked_text(raw["owner_id"], error=CalculatorError)
        holding = checked_text(raw["holding_id"], error=CalculatorError)
        holding_type = raw["holding_type"]
        if holding_type not in {"fund", "security"}:
            raise CalculatorError("invalid_field_type")
        previous_type = holding_types.get(holding)
        if previous_type is not None and previous_type != holding_type:
            raise CalculatorError("conflicting_holding_type")
        holding_types[holding] = holding_type
        owners.add(owner)
        raw_rows_by_owner[owner] = raw_rows_by_owner.get(owner, 0) + 1
        budget.validate_batch(
            symbol_count=len(raw_rows_by_owner),
            rows_per_symbol=max(raw_rows_by_owner.values()),
        )
        key = (owner, holding, holding_type)
        weight = _weight(raw["weight"], raw["weight_unit"])
        disclosure_date = reject_future(raw["as_of"], as_of=as_of, error=CalculatorError)
        if snapshot_date is None:
            snapshot_date = disclosure_date
        elif disclosure_date != snapshot_date:
            raise CalculatorError("data_not_equivalent")
        if key in edges:
            duplicate_edges += 1
            edges[key] = checked_add(edges[key], weight, error=CalculatorError)
        else:
            edges[key] = weight
        edge_dates[key] = disclosure_date
    if root not in owners:
        raise CalculatorError("root_fund_unavailable")
    adjacency: dict[str, list[tuple[str, str, float, str]]] = {}
    for (owner, holding, holding_type), weight in edges.items():
        if weight > 1:
            raise CalculatorError("invalid_weight")
        adjacency.setdefault(owner, []).append(
            (holding, holding_type, weight, edge_dates[(owner, holding, holding_type)])
        )
    for owner, owner_edges in adjacency.items():
        total = checked_sum([edge[2] for edge in owner_edges], error=CalculatorError)
        if total > 1.000000001:
            raise CalculatorError("invalid_weight_sum")
        owner_edges.sort(key=lambda edge: (edge[0], edge[1]))
        if holding_types.get(owner) == "security":
            raise CalculatorError("invalid_hierarchy")
    visited: set[str] = set()
    visiting: set[str] = set()

    def validate_acyclic(owner: str) -> None:
        if owner in visiting:
            raise CalculatorError("cycle_detected")
        if owner in visited:
            return
        visiting.add(owner)
        for holding, holding_type, _weight_value, _disclosure_date in adjacency.get(owner, []):
            if holding_type == "fund" and holding in adjacency:
                validate_acyclic(holding)
        visiting.remove(owner)
        visited.add(owner)

    for owner in sorted(adjacency):
        validate_acyclic(owner)

    exposures: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_leaf_paths = 0
    unresolved = 0

    def visit(
        owner: str,
        multiplier: float,
        depth: int,
        path: frozenset[str],
        path_as_of: str | None,
    ) -> None:
        nonlocal duplicate_leaf_paths, unresolved
        if owner in path:
            raise CalculatorError("cycle_detected")
        next_path = path | {owner}
        for holding, holding_type, weight, disclosure_date in adjacency.get(owner, []):
            contribution = checked_multiply(multiplier, weight, error=CalculatorError)
            effective_as_of = max(path_as_of or disclosure_date, disclosure_date)
            expandable = holding_type == "fund" and holding in adjacency
            if expandable:
                if holding in next_path:
                    raise CalculatorError("cycle_detected")
                if depth >= max_depth:
                    unresolved += 1
                else:
                    visit(holding, contribution, depth + 1, next_path, effective_as_of)
                    continue
            key = (holding, holding_type)
            if key in exposures:
                duplicate_leaf_paths += 1
                exposures[key]["effective_weight"] = checked_add(
                    exposures[key]["effective_weight"], contribution, error=CalculatorError
                )
                exposures[key]["path_count"] += 1
                exposures[key]["as_of"] = max(exposures[key]["as_of"], effective_as_of)
            else:
                exposures[key] = {
                    "asset_id": holding,
                    "asset_type": holding_type,
                    "effective_weight": contribution,
                    "path_count": 1,
                    "as_of": effective_as_of,
                }

    visit(root, 1.0, 1, frozenset(), None)
    rows = sorted(exposures.values(), key=lambda row: (-row["effective_weight"], row["asset_id"]))
    total_exposure = checked_sum([row["effective_weight"] for row in rows], error=CalculatorError)
    limitations = [
        "lookthrough_uses_only_supplied_disclosed_hierarchy",
        "undisclosed_fund_holdings_remain_terminal_fund_exposure",
        *source_limitations,
    ]
    if unresolved:
        limitations.append("max_depth_reached")
    output_rows, row_delivery = bounded_result_rows(
        rows,
        processed_input_rows=len(records),
        dataset_refs=refs,
    )
    return {
        "protocol": "cpu_bounded_v1",
        "skill_slug": SKILL_SLUG,
        "method_version": METHOD_VERSION,
        "compute_profile": "cpu_bounded_v1",
        "as_of": as_of,
        "parameters": {"root_fund_id": root, "max_depth": max_depth},
        "dataset_refs": refs,
        "status": "partial" if source_limitations or unresolved else "complete",
        "metrics": {
            "terminal_exposure_count": len(rows),
            "total_effective_weight": total_exposure,
            "duplicate_input_edges_aggregated": duplicate_edges,
            "duplicate_leaf_paths_aggregated": duplicate_leaf_paths,
            "unresolved_fund_count": unresolved,
        },
        "rows": output_rows,
        "row_delivery": row_delivery,
        "limitations": limitations,
        "research_only": True,
        "provenance": {
            "dataset_refs": refs,
            "source_hashes": source_hashes,
            "rights": "internal-only",
            "transformations": [
                "normalize_weight_units",
                "cycle_check",
                "path_weight_product",
                "aggregate_duplicate_exposure",
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
