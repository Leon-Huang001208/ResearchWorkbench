"""Versioned pure research checks. Inputs are declarations, never Host authority.

Only freeze this entire package as a reviewed Native resource. Historical Native
versions must not import a mutable Host calculator. This package is not an executor.
"""

from __future__ import annotations

import hashlib

from . import atoms, limited
from .bundles import (
    ExecutionBundle,
    FullClosureBudget,
    FullResultArtifact,
    build_bundle,
    canonical_json,
    capture_result,
)
from .contracts import PackError, encoded, require, result, security, validate_inputs

__all__ = [
    "ExecutionBundle",
    "FullResultArtifact",
    "PackError",
    "execute_atom",
    "execute_atom_bundle",
    "execute_pack",
    "execute_pack_bundle",
]

METHODS = {
    "validate_positions": (
        atoms.validate_positions,
        {"position"},
        {"expected_universe", "target_weight"},
    ),
    "join_risk_windows": (
        atoms.join_risk_windows,
        {"risk-event"},
        {"positions", "window_start", "window_end", "category_coverage"},
    ),
    "deduplicate_source_versions": (atoms.deduplicate_source_versions, {"source-version"}, set()),
    "compare_qualified_expectations": (
        atoms.compare_qualified_expectations,
        {"actual", "forecast", "guidance"},
        set(),
    ),
    "compare_valuation_samples": (
        atoms.compare_valuation_samples,
        {"valuation"},
        {"current_row_id", "window_start", "window_end", "minimum_samples"},
    ),
    "align_event_trading_day": (
        atoms.align_event_trading_day,
        {"exchange-session", "daily-price"},
        {"release_at", "pre_sessions", "post_sessions", "adjustment"},
    ),
    "sentiment_counts": (limited.sentiment_counts, {"sentiment-counts"}, set()),
    "disclosed_ownership": (limited.disclosed_ownership, {"holder-disclosure"}, {"report_periods"}),
    "earnings_calendar": (
        limited.earnings_calendar,
        {"report-calendar"},
        {"expected_universe", "report_period"},
    ),
}
PACKS = {
    "position-risk": ("validate_positions", "join_risk_windows"),
    "expectation-gap": ("compare_qualified_expectations",),
    "short-sentiment": ("sentiment_counts",),
    "research-prep": ("deduplicate_source_versions",),
    "event-review": ("align_event_trading_day",),
    "global-opinion": ("deduplicate_source_versions",),
    "valuation-check": ("compare_valuation_samples",),
    "ownership-structure": ("disclosed_ownership",),
    "earnings-preview": ("earnings_calendar", "compare_qualified_expectations"),
}
OPTIONAL = {"disclosed_ownership": {"disjoint_holder_ids"}}
BLOCKED = {
    "event-review": ["event_return_comparison_receipt_required"],
    "ownership-structure": ["fund_penetration_comparison_receipt_required"],
    "earnings-preview": ["earnings_monitor_comparison_receipt_required"],
}
REQUIRED_COVERAGE = {
    "position-risk": ("positions", "risk", "unlock", "insider"),
    "expectation-gap": ("actual_or_guidance", "historical_consensus"),
    "short-sentiment": ("counts", "flows", "seats"),
    "research-prep": ("original_materials",),
    "event-review": ("calendar", "target_prices", "benchmark_prices"),
    "global-opinion": ("domestic_originals", "overseas_originals"),
    "valuation-check": ("valuation_samples",),
    "ownership-structure": ("holder_disclosures", "float", "holder_coverage"),
    "earnings-preview": ("calendar", "actual_or_guidance", "historical_consensus"),
}


def _calculate_atom(method: str, records_by_kind: dict, parameters: dict):
    """Compute a format-checked receipt. Never asserts rights or report quality."""
    require(isinstance(method, str) and method in METHODS, "method_unknown")
    function, kinds, keys = METHODS[method]
    require(
        isinstance(parameters, dict)
        and keys | {"as_of"} <= set(parameters) <= keys | {"as_of"} | OPTIONAL.get(method, set()),
        "parameters_invalid",
    )
    require(
        isinstance(records_by_kind, dict) and set(records_by_kind) <= kinds, "record_kind_mismatch"
    )
    records, cutoff, count = validate_inputs(records_by_kind, parameters)
    try:
        rows, metrics, missing, rejected, limitations = function(records, parameters, cutoff)
    except (KeyError, TypeError, ValueError, OverflowError) as exc:
        if isinstance(exc, PackError):
            raise
        raise PackError("calculation_invalid") from exc
    metrics["input_counts"] = {kind: len(values) for kind, values in records.items()}
    refs = list(
        {
            tuple(sorted(r["origin"]["locator"].items()))
            for values in records.values()
            for r in values
        }
    )
    refs = [dict(x) for x in sorted(refs)]
    status = (
        "insufficient_data"
        if missing and not rows and not metrics.get("percentile_interval")
        else None
    )
    receipt = result(
        method,
        count,
        rows,
        metrics,
        missing,
        rejected,
        limitations,
        status,
        refs,
        parameters,
        hashlib.sha256(encoded({"records": records, "parameters": parameters})).hexdigest(),
    )
    return capture_result(
        receipt,
        rows,
        hashlib.sha256(canonical_json({"records": records, "parameters": parameters})).hexdigest(),
    )


def execute_atom(method: str, records_by_kind: dict, parameters: dict) -> dict:
    """Return the compatible bounded receipt from one in-memory calculation."""
    return _calculate_atom(method, records_by_kind, parameters).receipt


def execute_atom_bundle(method: str, records_by_kind: dict, parameters: dict) -> ExecutionBundle:
    """Return one calculation's receipt and immutable complete-result bytes."""
    return build_bundle(_calculate_atom(method, records_by_kind, parameters))


def _calculate_pack(
    pack_id: str,
    records_by_kind: dict,
    parameters: dict,
    *,
    source_coverage: dict | None = None,
    bundle_budget: bool = False,
):
    """Limited nine-pack composition; source coverage remains a declaration.

    parameters contains as_of plus a method-named object for each chosen method.
    B must bind these declarations to authenticated Snapshot bytes and scope.
    """
    require(isinstance(pack_id, str) and pack_id in PACKS, "pack_unknown")
    methods = PACKS[pack_id]
    require(
        isinstance(parameters, dict) and set(parameters) <= {"as_of", *methods},
        "parameters_invalid",
    )
    records, _, count = validate_inputs(records_by_kind, {"as_of": parameters.get("as_of")})
    allowed = set().union(*(METHODS[m][1] for m in methods))
    require(set(records) <= allowed, "record_kind_mismatch")
    source_coverage = source_coverage or {}
    require(
        isinstance(source_coverage, dict)
        and set(source_coverage) <= set(REQUIRED_COVERAGE[pack_id]),
        "coverage_invalid",
    )
    require(
        all(
            isinstance(v, dict)
            and set(v) == {"source_ref", "exhaustive"}
            and isinstance(v["source_ref"], str)
            and 0 < len(v["source_ref"]) <= 4096
            and isinstance(v["exhaustive"], bool)
            for v in source_coverage.values()
        ),
        "coverage_invalid",
    )
    encoded(source_coverage)
    missing = [
        {"code": "source_coverage_missing", "component": c}
        for c in REQUIRED_COVERAGE[pack_id]
        if not source_coverage.get(c, {}).get("exhaustive")
    ]
    subresults, rows, components = [], [], []
    full_budget = FullClosureBudget() if bundle_budget else None
    for method in methods:
        _, kinds, keys = METHODS[method]
        selected = {k: v for k, v in records.items() if k in kinds}
        if (
            not any(selected.values()) and method != "join_risk_windows"
        ) or method not in parameters:
            missing.append({"code": "method_input_missing", "component": method})
            continue
        require(
            isinstance(parameters[method], dict)
            and keys <= set(parameters[method]) <= keys | OPTIONAL.get(method, set()),
            "parameters_invalid",
        )
        if pack_id == "position-risk" and method == "join_risk_windows":
            position_parameters = parameters.get("validate_positions")
            require(isinstance(position_parameters, dict), "position_universe_required")
            expected = position_parameters.get("expected_universe")
            requested = parameters[method]["positions"]
            require(
                isinstance(expected, list) and isinstance(requested, list), "risk_universe_mismatch"
            )
            expected_keys = [security(item) for item in expected]
            risk_keys = [security(item) for item in requested]
            require(
                len(risk_keys) == len(expected_keys) and set(risk_keys) == set(expected_keys),
                "risk_universe_mismatch",
            )
        calculation = _calculate_atom(
            method, selected, {"as_of": parameters["as_of"], **parameters[method]}
        )
        if full_budget is not None:
            full_budget.add(calculation.full)
        components.append(calculation.full)
        sub = calculation.receipt
        subresults.append(sub)
        missing.extend({"component": method, **x} for x in sub["missing"])
        # Retain child projection accounting; never pretend this is the full row set.
        rows.append({"method": method, "result": sub})
    blocked = BLOCKED.get(pack_id, [])
    missing.extend({"code": x} for x in blocked)
    output = result(
        "pack:" + pack_id,
        count,
        rows,
        {
            "subresults_executed": len(subresults),
            "blocked_components": blocked,
            "coverage_is_declaration": True,
            "dsh_handoff_state": "host_review_required",
        },
        missing,
        limitations=["limited_deterministic_scope", "DSH_NOT_RUN", "no_research_passed"],
        status="partial" if subresults else "insufficient_data",
        parameters=parameters,
        input_sha256=hashlib.sha256(
            encoded(
                {"records": records, "parameters": parameters, "source_coverage": source_coverage}
            )
        ).hexdigest(),
    )
    full_rows = [{"component_id": component["method"]} for component in components]
    canonical_input = {
        "records": records,
        "parameters": parameters,
        "source_coverage": source_coverage,
    }
    return capture_result(
        output, full_rows, hashlib.sha256(canonical_json(canonical_input)).hexdigest(), components
    )


def execute_pack(
    pack_id: str, records_by_kind: dict, parameters: dict, *, source_coverage: dict | None = None
) -> dict:
    return _calculate_pack(
        pack_id, records_by_kind, parameters, source_coverage=source_coverage
    ).receipt


def execute_pack_bundle(
    pack_id: str, records_by_kind: dict, parameters: dict, *, source_coverage: dict | None = None
) -> ExecutionBundle:
    return build_bundle(
        _calculate_pack(
            pack_id,
            records_by_kind,
            parameters,
            source_coverage=source_coverage,
            bundle_budget=True,
        )
    )
