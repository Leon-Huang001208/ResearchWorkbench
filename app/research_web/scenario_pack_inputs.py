"""Host-only deterministic snapshot qualification and immutable input sealing.

Caller parameters choose research scope. Authority always comes from current
account-owned source readback, never row/provider/coverage claims in a request.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .scenarios.packs import METHODS, OPTIONAL, PACKS, REQUIRED_COVERAGE
from .scenarios.packs.contracts import PackError, instant, validate_inputs
from .store import StoreError

log = get_logger(__name__)


def fail(code):
    log.warning("research_pack_inputs_rejected", code=code)
    raise StoreError("组合包输入或来源资格无法核验", code, 409)


@dataclass(frozen=True)
class QualifiedPackInput:
    input: dict
    references: tuple[dict, ...]
    transformations: tuple[dict, ...]
    missing: tuple[dict, ...]
    status: str


def qualify_pack_materials(service, pack_id, values, references):
    """Read selected originals again. Map only verified BaoStock prices and owned Host web captures.

    Unknown providers/kinds/units/financial dates remain explicit gaps. In particular
    no pagination flag, uploaded JSON field or acquisition clock certifies coverage.
    """
    from .scenario_handoffs import resolve_reference, validate_dates

    if pack_id not in PACKS:
        fail("pack_unknown")
    scope = values.get("research_scope", {})
    if not isinstance(scope, dict) or set(scope) - {"cutoff_at", "methods"}:
        fail("pack_scope_invalid")
    supplied = scope.get("methods", {})
    if not isinstance(supplied, dict) or set(supplied) - set(PACKS[pack_id]):
        fail("pack_scope_invalid")
    for method, parameters in supplied.items():
        if (
            not isinstance(parameters, dict)
            or "category_coverage" in parameters
            or set(parameters) - (METHODS[method][2] | OPTIONAL.get(method, set()))
        ):
            fail("pack_scope_invalid")
    records, missing, checked, transforms = {}, [], [], []
    source_versions_seen = set()
    cutoff = None
    try:
        cutoff = instant(scope.get("cutoff_at"))
        if cutoff.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() != values["as_of"]:
            fail("pack_cutoff_mismatch")
    except (ValueError, TypeError):
        missing.append({"code": "cutoff_timezone_required"})
    needed = set().union(*(METHODS[method][1] for method in PACKS[pack_id]))
    for reference in references:
        metadata, manifest, raw = resolve_reference(
            service, reference["source_session_id"], reference["reference"], expected=reference
        )
        checked.append(metadata)
        if reference["reference"]["type"] == "source" and "source-version" in needed:
            from .scenario_source_versions import project_source_version

            source_identity = (metadata["source_session_id"], metadata["reference"]["id"])
            if source_identity in source_versions_seen:
                transforms.append(
                    {
                        "mapping": "owned-source-reference-deduplicate-v1",
                        "source_session_id": metadata["source_session_id"],
                        "source_id": metadata["reference"]["id"],
                        "source_sha256": metadata["sha256"],
                    }
                )
                continue
            source_versions_seen.add(source_identity)
            record, transformation, gaps = project_source_version(
                service, metadata, raw, cutoff, values["as_of"]
            )
            missing.extend(gaps)
            if record is not None:
                records.setdefault("source-version", []).append(record)
                transforms.append(transformation)
            continue
        if reference["reference"]["type"] != "dataset":
            missing.append(
                {"code": "material_schema_unsupported", "id": reference["reference"]["id"]}
            )
            continue
        validate_dates(manifest, raw, values["as_of"])
        did = reference["reference"]["id"]
        if not (
            "daily-price" in needed
            and manifest.get("provider") == "baostock"
            and manifest.get("capability") == "market_bars"
        ):
            missing.append({"code": "dataset_mapping_unsupported", "id": did})
            continue
        from .datahub.providers_baostock import SEMANTICS_REVISION
        from .datahub.security import directory, read_file

        native = manifest.get("provider_metadata", {})
        originals = manifest.get("raw_files", [])
        if (
            not isinstance(native, dict)
            or not isinstance(originals, list)
            or native.get("provider_semantics_revision") != SEMANTICS_REVISION
            or native.get("upstream_id") != "baostock"
            or len(originals) != 1
        ):
            missing.append({"code": "provider_original_mapping_unverified", "id": did})
            continue
        try:
            with directory(
                service.store.root,
                (".control", "snapshots", reference["source_session_id"], did),
                private=True,
            ) as fd:
                original_raw = read_file(
                    fd, originals[0]["name"], private=True, limit=64 * 1024 * 1024
                )
            if (
                hashlib.sha256(original_raw).hexdigest() != originals[0]["sha256"]
                or len(original_raw) != originals[0]["size"]
            ):
                fail("pack_original_changed")
            native_rows = json.loads(original_raw)
            if not isinstance(native_rows, list):
                fail("pack_original_schema_invalid")
        except (KeyError, ValueError, TypeError):
            fail("pack_original_schema_invalid")
        field = manifest.get("fields", {}).get("close", {})
        query = manifest.get("query", {}).get("parameters", {})
        native_asset = query.get("asset")
        asset = native_asset.upper() if isinstance(native_asset, str) else native_asset
        if (
            field != {"unit": "currency_per_share", "currency": "CNY"}
            or query.get("adjustment", "none") != "none"
        ):
            missing.append({"code": "price_unit_or_adjustment_unverified", "id": did})
            continue
        if (
            not isinstance(asset, str)
            or asset != values["subject"]["identity"]
            or asset.rsplit(".", 1)[-1] not in {"SH", "SZ"}
        ):
            fail("pack_security_mismatch")
        try:
            observed = instant(manifest["retrieved_at"])
        except (KeyError, ValueError, TypeError):
            missing.append({"code": "source_observation_instant_unknown", "id": did})
            continue
        if cutoff is None or observed > cutoff:
            missing.append({"code": "source_observed_after_cutoff", "id": did})
            continue
        try:
            rows = json.loads(raw)
        except (ValueError, TypeError):
            fail("pack_source_schema_invalid")
        if not isinstance(rows, list) or len(rows) != manifest["row_count"]:
            fail("pack_source_count_mismatch")
        if len(native_rows) < len(rows):
            fail("pack_original_count_mismatch")
        if len(native_rows) > len(rows):
            missing.append({"code": "source_rows_truncated", "id": did})
        for index, row in enumerate(rows):
            if (
                not isinstance(row, dict)
                or row.get("asset") != asset
                or row.get("adjustment") != "none"
                or type(row.get("trading_status")) is not bool
            ):
                missing.append({"code": "price_row_semantics_unknown", "id": did, "row": index})
                continue
            original = native_rows[index]
            try:
                code, market = asset.rsplit(".", 1)
                if (
                    not isinstance(original, dict)
                    or original["code"] != market.lower() + "." + code
                    or original["date"] != row.get("date")
                    or original["adjustflag"] != "3"
                    or original["tradestatus"] not in {"0", "1"}
                    or (original["tradestatus"] == "1") != row["trading_status"]
                    or float(original["close"]) != row.get("close")
                ):
                    fail("pack_original_row_mismatch")
            except (KeyError, ValueError, TypeError, OverflowError):
                fail("pack_original_row_mismatch")
            record = {
                "kind": "daily-price",
                "row_id": f"{did}:{index}",
                "origin": {
                    "locator": {
                        "source_ref": metadata["sha256"],
                        "resource_id": did,
                        "record_id": str(index),
                        "location": f"/{index}",
                    },
                    "observed_at": manifest["retrieved_at"],
                    "published_at": None,
                },
                "security": {
                    "security_id": asset,
                    "market": asset.rsplit(".", 1)[-1],
                    "asset_class": "equity",
                    "currency": "CNY",
                },
                "session_date": row.get("date"),
                "close": row.get("close"),
                "unit": "CNY_per_share",
                "adjustment": "none",
                "tradable": row["trading_status"],
            }
            try:
                validate_inputs({"daily-price": [record]}, {"as_of": scope["cutoff_at"]})
            except PackError:
                missing.append({"code": "price_row_contract_invalid", "id": did, "row": index})
                continue
            records.setdefault("daily-price", []).append(record)
        transforms.append(
            {
                "mapping": "baostock-market-bars-v1",
                "dataset_id": did,
                "source_sha256": metadata["sha256"],
                "manifest_sha256": metadata["manifest_sha256"],
                "raw_files": manifest.get("raw_files", []),
                "unit_mapping": {"currency_per_share:CNY": "CNY_per_share"},
                "security_mapping": "baostock_explicit_asset_uppercase_v1",
                "publication_time": "unknown_preserved",
                "historical_pit": "NOT_RUN",
            }
        )
    for kind in sorted(needed - set(records)):
        missing.append({"code": "required_kind_missing", "kind": kind})
    missing.extend(
        {"code": "source_coverage_unverified", "component": component}
        for component in REQUIRED_COVERAGE[pack_id]
    )
    parameters = {"as_of": scope.get("cutoff_at"), **supplied}
    if records:
        try:
            validate_inputs(records, {"as_of": scope["cutoff_at"]})
        except PackError:
            fail("pack_aggregate_input_invalid")
    if pack_id in {"research-prep", "global-opinion", "expectation-gap", "short-sentiment"}:
        for method in PACKS[pack_id]:
            if not METHODS[method][2]:
                parameters.setdefault(method, {})
    result = QualifiedPackInput(
        {
            "schema": "research_pack_input_v1",
            "pack_id": pack_id,
            "records_by_kind": records,
            "parameters": parameters,
            "source_coverage": {},
        },
        tuple(checked),
        tuple(transforms),
        tuple(missing),
        "partial" if records else "blocked",
    )
    log.info(
        "research_pack_materials_qualified pack_id=%s status=%s records=%d gaps=%d",
        pack_id,
        result.status,
        sum(map(len, records.values())),
        len(missing),
    )
    return result


def seal_pack_inputs(service, sid, handoff_id, context):
    """Seal after copying evidence; no hash includes itself or its descriptor."""
    from .capabilities.pack_resources import canonical, verify_pack_manifest
    from .datahub.security import directory, read_file, sync_directory, write_new
    from .scenario_handoffs import fingerprint

    pack_id = context["scenario"]["contract"]["pack_id"]
    qualified = qualify_pack_materials(
        service, pack_id, context["scenario"]["inputs"], context["references"]
    )
    data = canonical(qualified.input)
    if len(data) > 64 * 1024 * 1024:
        fail("pack_input_limit")
    if hashlib.sha256(data).hexdigest() != context["pack_qualification"]["input_sha256"]:
        fail("pack_qualification_changed")
    selected = service.capabilities.selection("research-pack-" + pack_id)
    version = service.capabilities.row(selected["id"])["versions"][str(selected["version"])]
    code = verify_pack_manifest(version["files"])
    if (
        code is None
        or code["pack_id"] != pack_id
        or code["closure_sha256"] != context["pack_qualification"]["closure_sha256"]
    ):
        fail("pack_code_unverified")
    manifest = {
        "schema": "research_pack_input_manifest_v1",
        "handoff_id": handoff_id,
        "session_id": sid,
        "pack_id": pack_id,
        "capability_id": selected["id"],
        "version": selected["version"],
        "closure_sha256": code["closure_sha256"],
        "input_sha256": hashlib.sha256(data).hexdigest(),
        "input_bytes": len(data),
        "context_sha256": fingerprint(context),
        "references_sha256": fingerprint(context["references"]),
        "qualification": context["pack_qualification"],
    }
    manifest_raw = canonical(manifest)
    parts = ("sessions", sid, "inputs", "scenarios", handoff_id)
    with directory(service.store.root, parts, create=True) as fd:
        for name, content in (("input.json", data), ("manifest.json", manifest_raw)):
            write_new(fd, name, content)
            if read_file(fd, name, limit=64 * 1024 * 1024) != content:
                fail("pack_input_changed")
            os.chmod(name, 0o400, dir_fd=fd, follow_symlinks=False)
        sync_directory(fd)
    return {
        "input_path": f"inputs/scenarios/{handoff_id}/input.json",
        "manifest_path": f"inputs/scenarios/{handoff_id}/manifest.json",
        "manifest_sha256": hashlib.sha256(manifest_raw).hexdigest(),
        **{
            key: manifest[key]
            for key in (
                "input_sha256",
                "input_bytes",
                "context_sha256",
                "closure_sha256",
                "capability_id",
                "version",
                "pack_id",
            )
        },
    }


def verify_pack_seal(service, sid, context):
    """A private handoff record owns this descriptor; JSON declarations do not."""
    from .capabilities.pack_native import read_regular
    from .scenario_handoffs import fingerprint

    seal = context.get("pack_seal")
    if not seal:
        fail("pack_input_unsealed")
    try:
        root = service.store.root / "sessions" / sid
        raw = read_regular(root / seal["input_path"], 64 * 1024 * 1024)
        manifest_raw = read_regular(root / seal["manifest_path"], 65536)
        manifest = json.loads(manifest_raw)
        base = {key: value for key, value in context.items() if key != "pack_seal"}
        if (
            hashlib.sha256(raw).hexdigest() != seal["input_sha256"]
            or len(raw) != seal["input_bytes"]
            or hashlib.sha256(manifest_raw).hexdigest() != seal["manifest_sha256"]
            or fingerprint(base) != seal["context_sha256"]
            or manifest["context_sha256"] != seal["context_sha256"]
            or manifest["references_sha256"] != fingerprint(context["references"])
            or any(
                manifest[key] != seal[key]
                for key in (
                    "input_sha256",
                    "input_bytes",
                    "closure_sha256",
                    "capability_id",
                    "version",
                    "pack_id",
                )
            )
        ):
            fail("pack_input_changed")
    except (OSError, ValueError, KeyError, TypeError):
        fail("pack_input_changed")
    return seal
