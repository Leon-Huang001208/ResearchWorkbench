"""Explicit Dossier-only pack read policy; no ambient permission or task rewrite."""

import copy
import hashlib
import json

from core.observability import get_logger

from .capabilities.pack_equivalence import reject, verify
from .capabilities.pack_native import read_regular
from .capabilities.pack_relocation import PACK_IDS, relocation_decision, verify_version_tree
from .capabilities.pack_resources import pack_packages
from .store import StoreError

log = get_logger(__name__)
REF_KEYS = ("id", "version", "sha256", "native_name", "resource_path")


def require_runtime_unfrozen(service):
    """The explicit reader retains the same freeze gate as normal admission."""
    if getattr(service, "plugin_runtime_frozen", False):
        log.warning("pack_dossier_read_runtime_frozen")
        raise StoreError("插件运行时切换中", "plugin_runtime_frozen", 409)


def records(service, sid):
    """Use private sealed context plus original, non-id-deduplicated receipt refs.

    Caller lineage is already checked by Dossier/trusted_context's visited chain.
    This function deliberately never calls trusted_context and cannot recurse.
    """
    row = service.store.session(sid, include_deleted=True)
    receipt = service.store.data["receipts"].get(f"{sid}:{row.get('delivery_key', '')}", {})
    refs = []
    for key in ("scenario_required_capabilities", "native_capabilities"):
        values = receipt.get(key, [])
        if not isinstance(values, list) or len({item["id"] for item in values}) != len(values):
            reject()
        refs.extend(values)
    if receipt.get("capability"):
        refs.append(receipt["capability"])
    identifier = row.get("scenario_handoff_id")
    handoff = service.store.data["handoffs"].get(identifier, {})
    context = handoff.get("scenario_context")
    is_pack = context and context.get("scenario", {}).get("contract", {}).get("pack_id")
    if not is_pack and not any(ref.get("id") in PACK_IDS for ref in refs):
        return None
    require_runtime_unfrozen(service)
    # Copying into a newly created, not-yet-sealed draft is not a historical read.
    if is_pack and handoff.get("state") != "prepared" and not refs and not context.get("pack_seal"):
        return None
    if (
        not is_pack
        or handoff.get("state") != "prepared"
        or handoff.get("session_id") != sid
        or not context.get("pack_seal")
        or context["source_scope"] != row.get("source_scope")
    ):
        reject()
    from .scenario_pack_inputs import verify_pack_seal

    verify_pack_seal(service, sid, context)
    file = handoff["context_file"]
    raw = read_regular(service.store.root / "sessions" / sid / file["path"], 65536)
    if hashlib.sha256(raw).hexdigest() != file["sha256"] or json.loads(raw)["context"] != context:
        reject()
    frozen = [{key: item[key] for key in REF_KEYS} for item in context["scenario"]["capabilities"]]
    if (
        len(frozen) != 1
        or frozen[0]["id"] != context["pack_seal"]["capability_id"]
        or frozen[0]["version"] != context["pack_seal"]["version"]
    ):
        reject()
    if (
        receipt.get("scenario_required_capabilities")
        and [
            {key: item[key] for key in REF_KEYS}
            for item in receipt["scenario_required_capabilities"]
        ]
        != frozen
    ):
        reject()
    merged = {}
    for item in [*frozen, *refs]:
        ref = {key: item[key] for key in REF_KEYS}
        if ref["id"] in merged and ref != merged[ref["id"]]:
            reject()
        merged[ref["id"]] = ref
    changed = any(
        service.capabilities.row(ref["id"])["version"] != ref["version"] for ref in merged.values()
    )
    if changed and any(cid not in PACK_IDS for cid in merged):
        reject()
    curated = dict(pack_packages())
    for cid in merged:
        if cid not in PACK_IDS:
            continue
        current = service.capabilities.row(cid)
        if service.plugins.manages_capability(cid):
            reject()
        active = current["versions"][str(current["version"])]
        _allowed, reason = relocation_decision(
            current, active, service.capabilities._draft(curated[cid])
        )
        if (
            current["status"] != "enabled"
            or reason != "current"
            or service.capabilities.data.get("pending")
            or current.get("runtime_binding", {}).get("status") == "blocked"
        ):
            reject()
        verify_version_tree(service.capabilities, current, active)
    result = []
    for ref in merged.values():
        current = service.capabilities.row(ref["id"])
        if current["version"] == ref["version"]:
            result.extend(service._effective_records([ref]))
        else:
            result.append(verify(service.capabilities, ref))
    require_runtime_unfrozen(service)
    return result


def admit_snapshot(service, sid, query, resolution, *, source_sid, dataset_id, manifest_sha256):
    """Requires actual existing snapshot identity; storage_read is never a bypass."""
    require_runtime_unfrozen(service)
    from .datahub.snapshots import Snapshots
    from .dossiers import RetainedStore

    source = service.store.session(source_sid, include_deleted=True)
    target = service.store.session(sid, include_deleted=True)
    if "datahub" not in source.get("source_scope", []) or "datahub" not in target.get(
        "source_scope", []
    ):
        reject()
    manifest = Snapshots(RetainedStore(service.store)).detail(source_sid, dataset_id)
    from .datahub.contracts import BusinessQuery

    if (
        manifest["manifest_sha256"] != manifest_sha256
        or BusinessQuery.model_validate(manifest["query"]).fingerprint() != query.fingerprint()
        or manifest.get("provider") != resolution.provider_id
    ):
        reject()
    selected = records(service, sid)
    if selected is None:
        return service._data_query_admission(sid, query, resolution)
    local = copy.copy(service.datahub)
    local.admission = None
    for owned_sid in {source_sid, sid}:
        fresh = local._authorize_query(
            owned_sid,
            query,
            provider=manifest["provider"],
            cached=True,
            authorization_fingerprint=manifest.get("authorization_fingerprint"),
            storage_read=True,
        )
        if fresh.provider_id != resolution.provider_id:
            reject()
    catalog = service.datahub.admission_catalog()
    for record in selected:
        scope = service.capabilities.data_readiness(record["id"], catalog)
        if not scope["admitted"]:
            raise StoreError("历史读取的当前资料策略不可用", "capability_data_unavailable", 409)
    service._validate_data_query_scope(query, resolution, selected, catalog)
    require_runtime_unfrozen(service)
    log.info("pack_dossier_snapshot_read_admitted session_id=%s", sid)
