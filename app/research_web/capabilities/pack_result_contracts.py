"""Independent versioned audit contracts, never inferred from returned receipts."""

import copy
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from core.observability import get_logger

from ..scenarios.packs import METHODS, PACKS
from ..scenarios.packs.contracts import method_version
from ..scenarios.packs.format_profile import format_checker, require_local_schema
from .models import CapabilityError

log = get_logger(__name__)
SHA = {"type": "string", "pattern": "^[a-f0-9]{64}$"}
TEXT = {"type": "string", "minLength": 1, "maxLength": 4096}
COUNT = {"type": "integer", "minimum": 0}
NUMBER = {"type": "number"}
NULLABLE_NUMBER = {"type": ["number", "null"]}
STRINGS = {"type": "array", "items": TEXT}
BASE_LIMITS = [
    "source_format_not_authority",
    "host_readback_rights_pit_required",
    "not_vendor_equivalence",
]
LIMITS = {
    "validate_positions": [],
    "join_risk_windows": ["observed_no_match_is_not_no_risk"],
    "deduplicate_source_versions": ["byte_hash_dedupe_only", "questions_and_sentiment_NOT_RUN"],
    "compare_qualified_expectations": ["no_surprise_score"],
    "compare_valuation_samples": ["not_return_probability"],
    "align_event_trading_day": ["alignment_only"],
    "sentiment_counts": ["no_sentiment_score", "flows_and_seats_not_computed"],
    "disclosed_ownership": [
        "disclosed_subset_only",
        "holder_disjointness_not_verified",
        "fund_penetration_blocked",
    ],
    "earnings_calendar": ["calendar_not_probability", "growth_monitor_blocked"],
}


def obj(properties, required=None):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties) if required is None else required,
        "additionalProperties": False,
    }


def array(items):
    return {"type": "array", "items": items}


LOCATOR = obj({key: TEXT for key in ("source_ref", "resource_id", "record_id", "location")})
SECURITY_KEY = {"type": "array", "items": TEXT, "minItems": 4, "maxItems": 4}
AUDIT = obj(
    {
        "code": TEXT,
        "component": TEXT,
        "row_id": TEXT,
        "security": SECURITY_KEY,
        "category": TEXT,
        "holder_id": TEXT,
        "report_period": TEXT,
        "session_date": {"type": "string", "format": "date"},
    },
    ["code"],
)
COUNTS = obj(
    {
        key: COUNT
        for key in (
            "processed_input_rows",
            "total_output_rows",
            "missing_count",
            "rejected_count",
            "source_ref_count",
        )
    }
)
DELIVERY = obj(
    {
        "mode": {"enum": ["inline", "summary_with_source_refs"]},
        "total_output_rows": COUNT,
        "inline_output_rows": COUNT,
        "omitted_output_rows": COUNT,
    }
)
CODE_VERSION = obj(
    {
        "method_version": {"const": "1.0.0"},
        "source_binding": {"const": "host_required"},
        "source_sha256": {"type": "null"},
        "frozen_resource_version": {"type": "null"},
    }
)
METRICS = {
    "validate_positions": obj(
        {
            "known_weight": NUMBER,
            "unknown_weight": NUMBER,
            "unweighted_count": COUNT,
            "expected_count": COUNT,
            "observed_count": COUNT,
        }
    ),
    "join_risk_windows": obj(
        {
            "joined_events": COUNT,
            "unmatched_events": COUNT,
            "coverage_is_declaration": {"const": True},
        }
    ),
    "deduplicate_source_versions": obj(
        {
            "version_groups": COUNT,
            "versions": COUNT,
            "reprint_lags": array(
                obj({"version_id": TEXT, "parent_version_id": TEXT, "lag_seconds": NUMBER})
            ),
            "timeline_row_ids": STRINGS,
        }
    ),
    "compare_qualified_expectations": obj({"comparisons": COUNT}),
    "compare_valuation_samples": obj(
        {
            "sample_count": COUNT,
            "current": NUMBER,
            "percentile_interval": {
                "anyOf": [
                    {"type": "null"},
                    {"type": "array", "items": NUMBER, "minItems": 2, "maxItems": 2},
                ]
            },
            "tie_rule": {"const": "[count_less/n,count_less_or_equal/n]"},
        }
    ),
    "align_event_trading_day": obj(
        {
            "event_date": {"anyOf": [{"type": "null"}, {"type": "string", "format": "date"}]},
            "return_algorithm": {"const": "comparison_receipt_required"},
        }
    ),
    "sentiment_counts": obj({"strata": COUNT}),
    "disclosed_ownership": obj(
        {
            "total_shares": NUMBER,
            "aggregate_fraction": {"type": "null"},
            "period_totals": array(
                obj(
                    {
                        "security": array(TEXT),
                        "report_period": TEXT,
                        "shares": NULLABLE_NUMBER,
                        "disclosed_float_fraction": NULLABLE_NUMBER,
                        "disjointness_is_declaration": {"const": True},
                    }
                )
            ),
            "report_period_order": STRINGS,
        }
    ),
    "earnings_calendar": obj(
        {"expected_count": COUNT, "actual_count": COUNT, "disclosed_fraction": NULLABLE_NUMBER}
    ),
}
PACK_METRICS = obj(
    {
        "subresults_executed": COUNT,
        "blocked_components": STRINGS,
        "coverage_is_declaration": {"const": True},
        "dsh_handoff_state": {"const": "host_review_required"},
    }
)


def payload(method, *, full=False, pack=False):
    metrics = copy.deepcopy(PACK_METRICS if pack else METRICS[method])
    if not pack:
        metrics["properties"]["input_counts"] = {
            "type": "object",
            "properties": {kind: COUNT for kind in METHODS[method][1]},
            "additionalProperties": False,
        }
        metrics["required"].append("input_counts")
    limits = BASE_LIMITS + (
        ["limited_deterministic_scope", "DSH_NOT_RUN", "no_research_passed"]
        if pack
        else LIMITS[method]
    )
    properties = {
        "schema_version": {"const": 1, "type": "integer"},
        "method": {"const": method},
        "method_version": {"const": method_version(method)},
        "status": {"enum": ["complete", "partial", "insufficient_data"]},
        "host_qualification": {"const": "NOT_RUN"},
        "research_quality": {"const": "NOT_RUN"},
        "parameters": {"type": "object"},
        "input_sha256": SHA,
        "parameter_delivery": {"const": "collections_bound_by_input_digest"},
        "method_source_binding": {"const": "host_required"},
        "processed_input_rows": COUNT,
        "metrics": metrics,
        "rows": array({"type": "object"}),
        "missing": array(AUDIT),
        "rejected_rows": array(AUDIT),
        "source_refs": array(LOCATOR),
        "limitations": {"const": limits},
    }
    if not pack and method == "deduplicate_source_versions":
        properties["rows"] = array(
            obj(
                {
                    "content_sha256": SHA,
                    "versions": array(
                        obj(
                            {
                                "row_id": TEXT,
                                "version_id": TEXT,
                                "url_ref": TEXT,
                                "language": TEXT,
                                "region": TEXT,
                                "source_role": {
                                    "enum": ["original", "reprint", "translation", "unknown"]
                                },
                                "published_at": {"type": ["string", "null"], "format": "date-time"},
                            }
                        )
                    ),
                }
            )
        )
    if not pack and method == "align_event_trading_day":
        properties["limitations"] = {"enum": [limits, limits + ["old_event_return_blocked"]]}
    if full:
        properties.update(
            counts=COUNTS,
            input_digest_kind={"const": "normalized_canonical_json_v1"},
            canonical_input_sha256=SHA,
            legacy_normalized_input_sha256=SHA,
            receipt_sha256=SHA,
            code_version={
                **CODE_VERSION,
                "properties": {
                    **CODE_VERSION["properties"],
                    "method_version": {"const": method_version(method)},
                },
            },
            source_locator_contract={"const": "host_frozen_snapshot_readback_required"},
        )
        if pack:
            properties["rows"] = array(obj({"component_id": {"enum": list(PACKS[method[5:]])}}))
    else:
        properties.update(row_delivery=DELIVERY, result_sha256=SHA)
        properties["rows"]["maxItems"] = 128
        if pack:
            properties["rows"] = array(
                {
                    "oneOf": [
                        obj(
                            {
                                "method": {"const": atom},
                                "receipt_sha256": SHA,
                                "result": payload(atom),
                            }
                        )
                        for atom in PACKS[method[5:]]
                    ]
                }
            )
            properties["rows"]["maxItems"] = len(PACKS[method[5:]])
    return obj(properties)


def contracts(*, version=2):
    if version == 1:
        try:
            raw = Path(__file__).with_name("pack-output-contracts-v1.json").read_bytes()
        except OSError as exc:
            log.warning("pack_historical_output_contract_unavailable")
            raise CapabilityError("历史输出合同不可用", "pack_output_schema_invalid", 409) from exc
        if (
            hashlib.sha256(raw).hexdigest()
            != "de146921f14565d590c988ab4711528759b2f7ad45c141487106d1fb470790fd"
        ):
            log.warning("pack_historical_output_contract_changed")
            raise CapabilityError("历史输出合同已变化", "pack_output_schema_invalid", 409)
        return json.loads(raw)
    if version != 2:
        log.warning("pack_output_contract_version_unknown")
        raise CapabilityError("输出合同版本未知", "pack_output_schema_invalid", 409)
    return {
        "schema": "research_pack_output_contracts_v2",
        "version": 2,
        "receipts": {pack: payload("pack:" + pack, pack=True) for pack in PACKS},
        "full_results": {
            pack: obj(
                {
                    "schema": {"const": "research_pack_full_result_v1"},
                    "schema_version": {"const": 1, "type": "integer"},
                    "root_rows_kind": {"const": "component_references"},
                    "root": payload("pack:" + pack, pack=True, full=True),
                    "components": array(
                        {"oneOf": [payload(atom, full=True) for atom in PACKS[pack]]}
                    ),
                    "counts": obj(
                        {
                            "root_output_rows": COUNT,
                            "component_output_rows": {
                                "type": "object",
                                "properties": {atom: COUNT for atom in PACKS[pack]},
                                "additionalProperties": False,
                            },
                        }
                    ),
                }
            )
            for pack in PACKS
        },
    }


def validate(receipt, full, pack_id, *, definitions=None):
    try:
        definitions = contracts() if definitions is None else definitions
        for value, schema in (
            (receipt, definitions["receipts"][pack_id]),
            (full, definitions["full_results"][pack_id]),
        ):
            require_local_schema(schema)
            if (
                next(
                    Draft202012Validator(schema, format_checker=format_checker()).iter_errors(
                        value
                    ),
                    None,
                )
                is not None
            ):
                raise ValueError("output audit schema mismatch")
        if receipt["status"] != ("partial" if full["components"] else "insufficient_data"):
            raise ValueError("limited pack status invalid")
        for component in full["components"]:
            if component["method"] == "align_event_trading_day":
                expected = (
                    BASE_LIMITS
                    + LIMITS[component["method"]]
                    + (
                        []
                        if component["metrics"]["event_date"] is None
                        else ["old_event_return_blocked"]
                    )
                )
                if component["limitations"] != expected:
                    raise ValueError("conditional audit limitation invalid")
    except (KeyError, TypeError, ValueError):
        log.warning("pack_output_schema_rejected")
        raise CapabilityError(
            "组合包审计必需字段或结构非法", "pack_output_schema_invalid", 409
        ) from None


def frozen_definitions(root, execution):
    """Resolve only the independently sealed resource manifest's exact contract.

    Legacy v1 has a fixed path; v2 declares its path/hash in the code manifest.
    Neither the returned result nor a caller supplies a schema or schema URL.
    Missing frozen bindings are rejected, including for standalone writer tests.
    """
    from .pack_native import read_regular
    from .pack_resources import MANIFEST_PATH, canonical, closure

    try:
        binding = execution["binding"]
        from .pack_resources import PACK_NAMES

        cid, version = binding["capability_id"], binding["version"]
        if (
            cid != "research-pack-" + binding["pack_id"]
            or binding["pack_id"] not in PACK_NAMES
            or type(version) is not int
            or version < 1
        ):
            raise ValueError("frozen contract identity invalid")
        prefix = f"resources/capabilities/{cid}/{version}/"
        files = execution["scope"]["file_bindings"]
        paths = {item["path"]: item["sha256"] for item in files}
        if len(paths) != len(files):
            raise ValueError("duplicate frozen file")
        raw = read_regular(root / (prefix + MANIFEST_PATH), 65536)
        if hashlib.sha256(raw).hexdigest() != paths[prefix + MANIFEST_PATH]:
            raise ValueError("frozen manifest changed")
        manifest = json.loads(raw)
        if (
            manifest["pack_id"] != binding["pack_id"]
            or manifest["closure_sha256"] != binding["closure_sha256"]
            or closure(manifest["files"]) != binding["closure_sha256"]
            or any(paths[prefix + item["path"]] != item["sha256"] for item in manifest["files"])
        ):
            raise ValueError("frozen closure changed")
        if manifest["schema"] == "research_pack_code_manifest_v1":
            contract_path, contract_version = "references/output-contracts-v1.json", 1
            if manifest["method_version"] != "1.0.0":
                raise ValueError("legacy method version changed")
        elif manifest["schema"] == "research_pack_code_manifest_v2":
            contract_path, contract_version = "references/output-contracts-v2.json", 2
            if manifest["output_contract"] != {
                "path": contract_path,
                "sha256": paths[prefix + contract_path],
            }:
                raise ValueError("contract reference changed")
            if manifest["method_version"] != method_version("pack:" + binding["pack_id"]):
                raise ValueError("method version changed")
        else:
            raise ValueError("contract version unknown")
        content = read_regular(root / (prefix + contract_path), 512 * 1024)
        if hashlib.sha256(content).hexdigest() != paths[prefix + contract_path]:
            raise ValueError("frozen contract changed")
        definitions = contracts(version=contract_version)
        records_path = "references/record-contracts.json"
        records_raw = read_regular(root / (prefix + records_path), 128 * 1024)
        if hashlib.sha256(records_raw).hexdigest() != paths[prefix + records_path]:
            raise ValueError("frozen record contract changed")
        if contract_version == 1:
            record_schema_raw = (
                Path(__file__).with_name("pack-record-contracts-v1.json").read_bytes()
            )
            if (
                hashlib.sha256(record_schema_raw).hexdigest()
                != "04f0970ff6aa798c28f5b65906f5eb5a94533882b595299f7b3f8116c804be53"
            ):
                raise ValueError("legacy record schema changed")
        else:
            from ..scenarios.packs.record_contracts import RECORD_SCHEMAS

            record_schema_raw = canonical(RECORD_SCHEMAS)
            if manifest["record_contract"] != {
                "path": records_path,
                "sha256": paths[prefix + records_path],
                "version": 2,
            }:
                raise ValueError("record contract reference changed")
        if records_raw != record_schema_raw:
            raise ValueError("unreviewed record contract")
        schemas = json.loads(record_schema_raw)
        sealed_raw = read_regular(root / execution["scope"]["input_path"], 64 * 1024 * 1024)
        if hashlib.sha256(sealed_raw).hexdigest() != binding["input_sha256"]:
            raise ValueError("frozen input changed")
        sealed = json.loads(sealed_raw)
        for kind, records in sealed["records_by_kind"].items():
            validator = Draft202012Validator(schemas[kind], format_checker=format_checker())
            if any(next(validator.iter_errors(row), None) is not None for row in records):
                raise ValueError("frozen input contract invalid")
        if content != canonical(definitions):
            raise ValueError("unreviewed output contract")
        return definitions
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        log.warning("pack_frozen_output_contract_rejected")
        raise CapabilityError("冻结输出合同无法核验", "pack_output_schema_invalid", 409) from None
