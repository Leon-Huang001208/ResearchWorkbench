"""Byte-bound routing inventory; never execute a supplier alias or grant rights.

No request can choose a file, module, URL, builder or catalog version here.
The existing Host owns actual selection, freezing, admission and execution.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from .catalog import BASELINE_SHA256, read_catalog
from .models import ScenarioError

log = logging.getLogger(__name__)
OWNED_TARGETS = {
    "tool:company_one_pager": "owned-company-evidence",
    "tool:fundamental_analysis": "owned-company-evidence",
    "tool:research_outline": "owned-research-prep",
    "tool:query_news": "rwb_query_latest_cls_news",
}


def owned_target(original_id):
    if original_id not in OWNED_TARGETS:
        return None
    news = original_id == "tool:query_news"
    return {
        "capability_id": OWNED_TARGETS[original_id],
        "builder_id": (
            "public-data.apply" if news else "scenario_method_packages.scenario_method_packages"
        ),
        "pack_id": None,
        "version_policy": (
            "fixed_host_wrapper_per_call_authorization"
            if news
            else "resolve_current_catalog_then_freeze_version_compiled_sha256_and_closure"
        ),
    }


def owned_parameter(original_id, name):
    if original_id not in OWNED_TARGETS or name not in (
        {"query", "limit"} if original_id == "tool:query_news" else {"query"}
    ):
        return None
    news = original_id == "tool:query_news"
    return {
        "support": "native_subset",
        "native_target": name if news else "question",
        "normalization": (
            "host_cls_latest_snapshot" if news else "host_selected_owned_question_preset"
        ),
        "range": (
            {"minimum": 1, "maximum": 100, "strict_integer": True}
            if name == "limit"
            else {"max_length": 2000, "url": False}
        ),
        "error_code": "owned_news_arguments_invalid" if news else "owned_question_preset_invalid",
    }


BINDINGS_SHA256 = "9ea0bfcdd26f33ca42c3ab298ba30ad4fb46a423e4ecc11462938c5dc8885e3b"
ROUTES = frozenset(
    {
        "native_skill",
        "typed_datahub",
        "managed_mcp",
        "T4_pending",
        "T5_pending",
        "excluded",
        "postponed_generic",
    }
)


def _fail(code):
    log.warning("research_execution_binding_rejected code=%s", code)
    raise ScenarioError(code)


def read_execution_bindings():
    """Return a fresh closed inventory bound to the original immutable baseline."""
    try:
        with Path(__file__).with_name("execution-bindings-v1.json").open("rb") as stream:
            raw = stream.read(512 * 1024 + 1)
        if len(raw) > 512 * 1024 or hashlib.sha256(raw).hexdigest() != BINDINGS_SHA256:
            _fail("execution_bindings_invalid")
        result = json.loads(raw)
        baseline = read_catalog()
        originals = {row["id"]: row for row in baseline["skills"] + baseline["tools"]}
        rows = result["bindings"]
        if (
            set(result) != {"schema", "version", "baseline_sha256", "authority", "bindings"}
            or result["schema"] != "research_execution_bindings_v1"
            or result["version"] != "1.0.0"
            or result["baseline_sha256"] != BASELINE_SHA256
            or result["authority"] != "static_routing_contract_only"
            or len(rows) != 140
            or {row["original_id"] for row in rows} != set(originals)
        ):
            _fail("execution_bindings_invalid")
        row_keys = {
            "original_id",
            "original_name",
            "original_kind",
            "original_definition_sha256",
            "binding_version",
            "baseline_sha256",
            "route",
            "original",
            "native",
            "native_target",
            "parameters",
            "source_contract",
            "output_contract",
            "quality_contract",
            "limitation",
        }
        parameter_keys = {
            "name",
            "type",
            "required",
            "support",
            "native_target",
            "normalization",
            "range",
            "semantic_difference",
            "error_code",
        }
        evidence_keys = {
            "action",
            "ready",
            "callable",
            "runtime",
            "quality",
            "fixture",
            "live_source",
        }
        source_keys = {
            "authority",
            "required_evidence",
            "published_at",
            "observed_at",
            "rights",
            "coverage",
            "historical_pit",
        }
        pack_ids = {
            "position-risk",
            "expectation-gap",
            "short-sentiment",
            "research-prep",
            "event-review",
            "global-opinion",
            "valuation-check",
            "ownership-structure",
            "earnings-preview",
        }
        for row in rows:
            if set(row) != row_keys or set(row["source_contract"]) != source_keys:
                _fail("execution_bindings_invalid")
            for side in ("original", "native"):
                evidence = row[side]
                if (
                    set(evidence) != evidence_keys
                    or evidence["ready"] != "requires_current_host_evidence"
                    or evidence["callable"] != "unverified"
                    or any(
                        evidence[key] != "NOT_RUN"
                        for key in ("runtime", "quality", "fixture", "live_source")
                    )
                ):
                    _fail("execution_bindings_invalid")
            target = row["native_target"]
            owned = owned_target(row["original_id"])
            if owned is not None and (
                target != owned
                or row["route"]
                != ("typed_datahub" if row["original_id"] == "tool:query_news" else "native_skill")
            ):
                _fail("execution_bindings_invalid")
            if (
                owned is None
                and target is not None
                and (
                    set(target) != {"capability_id", "builder_id", "pack_id", "version_policy"}
                    or target["pack_id"] not in pack_ids
                    or target["capability_id"] != "research-pack-" + target["pack_id"]
                    or target["builder_id"] != "pack_resources.pack_packages"
                    or target["version_policy"]
                    != "resolve_current_catalog_then_freeze_version_compiled_sha256_and_closure"
                    or row["route"] != "native_skill"
                )
            ):
                _fail("execution_bindings_invalid")
            for parameter in row["parameters"]:
                subset = owned_parameter(row["original_id"], parameter["name"])
                if subset is not None:
                    if (
                        set(parameter) != parameter_keys
                        or parameter["required"] != "unknown"
                        or any(parameter[key] != value for key, value in subset.items())
                    ):
                        _fail("execution_bindings_invalid")
                    continue
                if (
                    set(parameter) != parameter_keys
                    or parameter["required"] != "unknown"
                    or parameter["support"] != "unsupported"
                    or any(
                        parameter[key] is not None
                        for key in ("native_target", "normalization", "range")
                    )
                    or parameter["error_code"] != "execution_parameter_unsupported"
                ):
                    _fail("execution_bindings_invalid")
            original = originals[row["original_id"]]
            if (
                row["original"]["action"]
                != (
                    "unregistered_supplier_alias"
                    if row["original_id"].startswith("tool:")
                    else "reference_only"
                )
                or row["native"]["action"]
                != (
                    "implemented_owned_native_subset"
                    if owned is not None
                    else "implemented_pack_subset" if target is not None else "pending_slice"
                )
                or row["source_contract"]["authority"] != "current_owner_original_readback_only"
                or row["source_contract"]["rights"] != "current_host_revalidation_required"
                or row["source_contract"]["coverage"] != "unverified"
                or row["source_contract"]["historical_pit"] != "NOT_RUN"
                or row["source_contract"]["required_evidence"] != original["dependencies"]["data"]
                or row["output_contract"]
                != (
                    "datahub_snapshot"
                    if row["original_id"] == "tool:query_news"
                    else (
                        "research_method_source_ledger_v1_and_canonical_report"
                        if owned is not None
                        else (
                            "research_pack_full_result_v1"
                            if target is not None
                            else "pending_slice"
                        )
                    )
                )
            ):
                _fail("execution_bindings_invalid")
            expected_kind = "skill" if row["original_id"].startswith("skill:") else "tool"
            if (
                row["route"] not in ROUTES
                or row["original_name"] != original["name"]
                or row["original_kind"] != expected_kind
                or row["original_definition_sha256"] != original.get("raw_definition_sha256")
                or row["baseline_sha256"] != BASELINE_SHA256
                or row["binding_version"] != "1.0.0"
                or [(p["name"], p["type"]) for p in row["parameters"]]
                != [(p["name"], p["type"]) for p in original.get("parameters", [])]
            ):
                _fail("execution_bindings_invalid")
        return result
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        _fail("execution_bindings_invalid")


def binding_for(original_id):
    """Lookup an exact source ID; free text and guessed aliases are rejected."""
    if not isinstance(original_id, str):
        _fail("execution_binding_unknown")
    for row in read_execution_bindings()["bindings"]:
        if row["original_id"] == original_id:
            return row
    _fail("execution_binding_unknown")


def validate_supplier_arguments(original_id, arguments):
    """Fail closed until a named, tested supplier argument adapter is registered.

    Explicit unsupported fields receive a stable error, even when None. Empty
    arguments cannot turn an inventory entry into a registered executable tool.
    """
    row = binding_for(original_id)
    if not isinstance(arguments, dict) or set(arguments) - {p["name"] for p in row["parameters"]}:
        _fail("execution_arguments_invalid")
    if arguments:
        _fail("execution_parameter_unsupported")
    _fail("execution_alias_unregistered")
