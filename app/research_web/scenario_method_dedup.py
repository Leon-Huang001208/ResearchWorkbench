"""Host-only C2 preprocessing of currently authorized owned-method originals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from core.observability import get_logger

from .capabilities.pack_dependencies import runtime_identity
from .capabilities.pack_resources import CORE_FILES, canonical
from .scenario_source_versions import project_source_version
from .scenarios.packs import execute_atom_bundle
from .scenarios.packs.contracts import PackError, instant, method_version
from .store import StoreError

log = get_logger(__name__)
METHOD = "deduplicate_source_versions"


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def cutoff_instant(value, as_of):
    if value is None:
        return None
    try:
        cutoff = instant(value)
        if cutoff.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() != as_of:
            raise ValueError("day mismatch")
        return cutoff
    except (PackError, ValueError, TypeError) as exc:
        log.warning("research_method_cutoff_rejected")
        raise StoreError(
            "资料截止时刻必须含时区且与北京时间截止日一致", "method_cutoff_invalid", 409
        ) from exc


def build_artifact(service, sid, cid, values, originals):
    """Run the public atom once; freeze its exact receipt and full-result bytes."""
    cutoff = cutoff_instant(values.get("cutoff_at"), values["as_of"])
    if cutoff is None:
        return None
    records, source_set, gaps = [], [], []
    seen = set()
    for metadata, raw in originals:
        reference = metadata["reference"]
        key = (metadata["source_session_id"], reference["type"], reference["id"])
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "source_id": metadata["source_session_id"] + ":" + reference["id"],
            "reference": reference,
            "source_session_id": metadata["source_session_id"],
            "target_session_id": sid,
            "owner_sha256": digest(str(service.store.root)),
            "sha256": metadata["sha256"],
            "locator": f"bytes:0-{len(raw)}",
            "published_at": metadata.get("published_at"),
            "observed_at": metadata.get("acquired_at"),
            "version_id": None,
            "transformation": None,
        }
        record, transformation, missing = project_source_version(
            service, metadata, raw, cutoff, values["as_of"]
        )
        gaps.extend(missing)
        if record is not None:
            records.append(record)
            entry.update(version_id=record["version_id"], transformation=transformation)
        source_set.append(entry)
    # Stable order also preserves the atom's legacy normalized (unsorted) digest
    # across a canonical frozen JSON round trip. Never substitute the body hash.
    inputs = json.loads(canonical({"source-version": records}))
    parameters = {"as_of": cutoff.isoformat()}
    bundle = execute_atom_bundle(METHOD, inputs, parameters)
    core = Path(__file__).parent / "scenarios" / "packs"
    core_files = {
        name: hashlib.sha256((core / name).read_bytes()).hexdigest() for name in CORE_FILES
    }
    result = {
        "schema": "research_method_c2_dedup_v1",
        "producer": "host-c2-preprocess",
        "method_id": cid,
        "method": METHOD,
        "method_version": method_version(METHOD),
        "cutoff_at": parameters["as_of"],
        "as_of": values["as_of"],
        "projector": "host-web-capture-source-version-v2",
        "projector_sha256": hashlib.sha256(
            Path(__file__).with_name("scenario_source_versions.py").read_bytes()
        ).hexdigest(),
        "core_sha256": digest(core_files),
        "dependency_closure_sha256": digest(runtime_identity()),
        "source_set": source_set,
        "source_set_sha256": digest(source_set),
        "records": inputs,
        "parameters": parameters,
        "input_sha256": digest({"records": inputs, "parameters": parameters}),
        "projection_gaps": gaps,
        "receipt": bundle.receipt,
        "full_result": bundle.full_result.canonical_json.decode("utf-8"),
        "full_result_sha256": bundle.full_result.sha256,
        "full_result_bytes": bundle.full_result.byte_count,
    }
    log.info(
        "research_owned_method_c2_preprocessed sources=%d projected=%d",
        len(source_set),
        len(records),
    )
    return result
