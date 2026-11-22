"""Server-only direct relocation facts, revalidated for Dossier reads only."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path

from core.observability import get_logger

from . import pack_dependencies
from .models import CapabilityError
from .pack_relocation import (
    CONTENT_FIELDS,
    PACK_IDS,
    _static_files,
    record_tree_hash,
    runtime_from,
    verify_relocation_pair,
)
from .pack_resources import MANIFEST_PATH, canonical, verify_pack_manifest
from .packages import decode_file

log = get_logger(__name__)
POLICY = "direct_pack_runtime_prefix_read_v1"


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def reject():
    log.warning("pack_read_equivalence_rejected")
    raise CapabilityError("历史组合包只读等价事实无法核验", "pack_read_equivalence_invalid", 409)


def normalized_runtime(value):
    result = copy.deepcopy(value)
    prefix = Path(result.pop("environment"))
    result.pop("python")
    for dependency in result["dependencies"]:
        dependency["origin"] = Path(dependency["origin"]).relative_to(prefix).as_posix()
    return result


def facts(catalog, cid, previous, current, *, check_current=True):
    """Recompute direct endpoint facts; never walks or composes a certificate chain."""
    row = catalog.row(cid)
    if (
        cid not in PACK_IDS
        or row["source"] != "builtin"
        or row["kind"] != "skill"
        or row.get("origin") is not None
        or type(previous) is not int
        or type(current) is not int
        or not 1 <= previous < current
    ):
        reject()
    left, right = row["versions"][str(previous)], row["versions"][str(current)]
    allowed, reason = verify_relocation_pair(left, right)
    if not allowed and reason != "current":
        reject()
    if runtime_from(right) != pack_dependencies.runtime_identity():
        reject()
    if check_current:
        if (
            catalog.data.get("pending")
            or row["status"] != "enabled"
            or row["version"] != current
            or row.get("has_draft")
        ):
            reject()
        if any(row["draft"].get(key) != right.get(key) for key in CONTENT_FIELDS) or {
            item["path"]: decode_file(item) for item in row["draft"]["files"]
        } != {item["path"]: decode_file(item) for item in right["files"]}:
            reject()
        record_tree_hash(catalog, cid, current, right, native=True)
    old_manifest, new_manifest = verify_pack_manifest(left["files"]), verify_pack_manifest(
        right["files"]
    )
    manifest_bytes = lambda record: decode_file(
        next(item for item in record["files"] if item["path"] == MANIFEST_PATH)
    )
    value = {
        "schema": "pack_read_equivalence_v1",
        "policy": POLICY,
        "operation": "dossier_snapshot_read",
        "issuer": "rwb_catalog_relocation_v1",
        "owner_binding": digest(str(catalog.data_root)),
        "capability_id": cid,
        "source": "builtin",
        "kind": "skill",
        "origin": None,
        "from_version": previous,
        "to_version": current,
        "from_record_sha256": digest(left),
        "to_record_sha256": digest(right),
        "from_tree_sha256": record_tree_hash(catalog, cid, previous, left),
        "to_tree_sha256": record_tree_hash(catalog, cid, current, right),
        "from_manifest_sha256": hashlib.sha256(manifest_bytes(left)).hexdigest(),
        "to_manifest_sha256": hashlib.sha256(manifest_bytes(right)).hexdigest(),
        "from_closure_sha256": old_manifest["closure_sha256"],
        "to_closure_sha256": new_manifest["closure_sha256"],
        "from_runtime_sha256": digest(runtime_from(left)),
        "to_runtime_sha256": digest(runtime_from(right)),
        "equivalent_runtime_sha256": digest(normalized_runtime(runtime_from(right))),
        "static_resources_sha256": digest(
            {path: hashlib.sha256(raw).hexdigest() for path, raw in _static_files(right).items()}
        ),
    }
    value["publication_identity"] = digest(
        {
            key: value[key]
            for key in (
                "capability_id",
                "from_version",
                "to_version",
                "from_record_sha256",
                "to_record_sha256",
            )
        }
    )
    value["digest"] = digest(value)
    return value


def issue_for_publication(catalog, cid, versions, current):
    """Called inside the existing pending activation transaction, before its save."""
    issued = {}
    for previous in versions:
        # Every retained endpoint is independently compared to the new target.
        # A broken/non-equivalent retained endpoint aborts publication; no chain.
        value = facts(catalog, cid, previous, current, check_current=False)
        issued[value["digest"]] = value
    return issued


def verify(catalog, frozen):
    try:
        cid, previous = frozen["id"], frozen["version"]
        row = catalog.row(cid)
        if row.get("runtime_binding", {}).get("status") == "blocked":
            reject()
        old = row["versions"][str(previous)]
        expected = {
            "id": cid,
            "version": previous,
            "sha256": old["compiled_sha256"],
            "native_name": old["native_name"],
            "resource_path": f"resources/capabilities/{cid}/{previous}",
        }
        if frozen != expected:
            reject()
        value = facts(catalog, cid, previous, row["version"])
        actual = catalog.data.get("pack_read_equivalences", {}).get(value["digest"])
        if actual != value:
            reject()
        return {**row["versions"][str(row["version"])], "id": cid}
    except (CapabilityError, OSError, ValueError, TypeError, KeyError, StopIteration):
        reject()
