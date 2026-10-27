"""Inert, Host-constructed source selections for two research packs.

Private immutable receipts bind files to complete requests. They grant no source
rights: every use reopens current authorized source bytes through the old reader.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from core.observability import get_logger

from .datahub.security import directory, json_bytes, read_file, sync_directory, write_new
from .scenario_handoffs import fail, fingerprint, prepare_context, resolve_reference, selection
from .store import StoreError

log = get_logger(__name__)
PACKS = {"pack-research-prep", "pack-global-opinion"}
SCHEMA = "research-pack-source-selection/v1"
LIMIT = 256 * 1024
CONTROL = (".control", "source-selections")


class _SourceSelectionPreflightFailure(StoreError):
    """Internal marker: pure preflight failed before any prior/current publication."""


def _has_prior_selection_request(service, body, key):
    """An unreadable ledger is uncertain, never proof that publication is absent."""
    try:
        request_hash = fingerprint(_request(body))
        selection_id = fingerprint(
            {"request_sha256": request_hash, "preview_sha256": body.preview_sha256}
        )
        with directory(service.store.root) as fd:
            if ".control" not in os.listdir(fd):
                return False
        with directory(service.store.root, (".control",), private=True) as fd:
            if "source-selections" not in os.listdir(fd):
                return False
        with directory(service.store.root, CONTROL, private=True) as fd:
            names = os.listdir(fd)
        return "key-" + fingerprint(key) + ".json" in names or selection_id + ".json" in names
    except (StoreError, OSError) as exc:
        log.warning("research_source_selection_prior_state_unknown", error_type=type(exc).__name__)
        return True


def snapshot_selection_receipts(root):
    """Preserve even uncertain publication intents through the existing fence.

    The caller holds retention_lock. No source body, database, current capability
    revision or source authorization is needed to preserve historical metadata.
    """
    folder = root.joinpath(*CONTROL)
    if not folder.exists() and not folder.is_symlink():
        return {}
    files = {}
    with directory(root, CONTROL, private=True) as fd:
        for name in sorted(os.listdir(fd)):
            if not re.fullmatch(r"(?:key-)?[a-f0-9]{64}\.json", name):
                fail("source_selection_preservation_invalid", "原文选择登记文件身份不明")
            raw = read_file(fd, name, private=True, limit=LIMIT)
            try:
                if not isinstance(json.loads(raw), dict):
                    raise TypeError("receipt")
            except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
                log.warning(
                    "research_source_selection_preservation_invalid", error_type=type(exc).__name__
                )
                fail("source_selection_preservation_invalid", "原文选择登记损坏，保全拒绝")
            files["/".join((*CONTROL, name))] = hashlib.sha256(raw).hexdigest()
    return files


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class ManifestSource(Closed):
    source_session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    id: str = Field(pattern=r"^web:[a-f0-9]{24}$")
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")


class Subject(Closed):
    kind: Literal["stock", "industry", "topic"]
    identity: str = Field(min_length=1, max_length=160)
    name: str | None = Field(default=None, min_length=1, max_length=160)


class SelectionManifest(Closed):
    schema_id: Literal["research-pack-source-selection/v1"] = Field(alias="schema")
    schema_version: Literal[1]
    selection_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    scenario_id: Literal["pack-research-prep", "pack-global-opinion"]
    subject: Subject
    as_of: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    sources: list[ManifestSource] = Field(min_length=1, max_length=20)


def _read_control(service, name):
    try:
        with directory(service.store.root, CONTROL, private=True) as fd:
            value = json.loads(read_file(fd, name, private=True, limit=LIMIT))
        if not isinstance(value, dict):
            raise TypeError("record")
        return value
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        log.warning("research_source_selection_receipt_invalid", error_type=type(exc).__name__)
        fail("source_selection_receipt_invalid", "原文选择登记损坏，不能重建或覆盖")


def _write_control(service, name, record):
    raw = json_bytes(record)
    if len(raw) > LIMIT:
        fail("source_selection_limit", "原文选择登记超过大小限制", 422)
    with directory(service.store.root, CONTROL, create=True, private=True) as fd:
        write_new(fd, name, raw)
        sync_directory(fd)


def _request(body):
    handoff = body.handoff
    if (
        handoff.scenario_id not in PACKS
        or not handoff.source_session_id
        or handoff.workspace_material is not None
        or handoff.context
        or handoff.observation_id
        or handoff.comparison_observation_ids
        or handoff.scenario_inputs.get("material_ids") != handoff.dataset_ids
        or set(handoff.source_scope or []) != {"datahub", "uploads", "web"}
        or len(handoff.source_scope) != 3
    ):
        fail(
            "source_selection_request_invalid",
            "请选择两类原文研究包、真实来源会话及明确资料范围",
            422,
        )
    sources = sorted(
        [item.model_dump() for item in body.sources],
        key=lambda item: (item["source_session_id"], item["id"]),
    )
    if len({(item["source_session_id"], item["id"]) for item in sources}) != len(sources):
        fail("source_selection_duplicate", "原文引用不能重复", 422)
    return {"handoff": handoff.model_dump(mode="json"), "sources": sources}


def _sources(service, sources):
    refs = []
    for item in sources:
        metadata, _manifest, _raw = resolve_reference(
            service,
            item["source_session_id"],
            {"type": "source", "id": item["id"]},
        )
        if metadata["sha256"] != item["sha256"]:
            fail("source_selection_source_changed", "所选原文版本已变化，请重新预览")
        refs.append(metadata)
    return refs


def _safe(service, metadata):
    from .research_web_sources import capture_proof

    source = service.store.session(metadata["source_session_id"])["web_evidence"][
        metadata["reference"]["id"]
    ]
    return {
        "source_session_id": metadata["source_session_id"],
        "id": metadata["reference"]["id"],
        "title": source.get("title", "原文"),
        "sha256": metadata["sha256"],
        "acquired_at": metadata.get("acquired_at"),
        "publication_date": metadata.get("published_at"),
        "published_at": None,
        "source_host": urlsplit(source.get("url", "")).hostname,
        "language": "unknown",
        "region": "unknown",
        "source_role": "unknown",
        "capture_status": (
            "host_verified"
            if capture_proof(service.store.root, metadata["source_session_id"], source) is not None
            else "unverified"
        ),
        "upstream_completeness": "unknown",
        "state": "available",
        "selectable": True,
    }


def list_sources(service, sid):
    """Read current owned source metadata; never scan/register uploaded files."""
    from .scenario_handoffs import trusted_context

    trusted_context(service, sid, check_capabilities=False)
    session = service.store.session(sid)
    if "web" not in session.get("source_scope", []):
        fail("source_selection_scope_revoked", "来源会话未批准原文范围", 403)
    items = []
    for identifier in sorted(session.get("web_evidence", {})):
        try:
            metadata, _manifest, _raw = resolve_reference(
                service, sid, {"type": "source", "id": identifier}
            )
            items.append(_safe(service, metadata))
        except StoreError as exc:
            items.append(
                {
                    "id": identifier,
                    "source_session_id": sid,
                    "state": "unavailable",
                    "selectable": False,
                    "reason_code": exc.code,
                }
            )
    return {"schema": SCHEMA, "items": items}


def _material(request_hash, sid, raw):
    relative = "inputs/source-selections/" + request_hash + ".json"
    return relative, {
        "source_session_id": sid,
        "file_id": hashlib.sha256(relative.encode()).hexdigest()[:24],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def preview(service, body):
    """Pure qualification, with no material file and no Native session creation."""
    request = _request(body)
    handoff = body.handoff
    service.store.session(handoff.source_session_id)
    chosen = selection(service, handoff.scenario_id, handoff.scenario_inputs)
    refs = _sources(service, request["sources"])
    request_hash = fingerprint(request)
    manifest = {
        "schema": SCHEMA,
        "schema_version": 1,
        "selection_id": request_hash,
        "scenario_id": handoff.scenario_id,
        "subject": chosen["inputs"]["subject"],
        "as_of": chosen["inputs"]["as_of"],
        "request_sha256": request_hash,
        "sources": request["sources"],
    }
    SelectionManifest.model_validate(manifest)
    raw = json_bytes(manifest)
    if len(raw) > LIMIT:
        fail("source_selection_limit", "原文选择合同超过大小限制", 422)
    relative, material = _material(request_hash, handoff.source_session_id, raw)
    prepared = handoff.model_copy(
        update={
            "workspace_material": material,
            "scenario_inputs": {
                **handoff.scenario_inputs,
                "material_ids": [*handoff.dataset_ids, "file:" + material["file_id"]],
            },
        }
    )
    context = prepare_context(
        service, prepared, _workspace_reader=lambda: ({"schema": SCHEMA}, refs)
    )
    digest = fingerprint(
        {
            "request": request,
            "references": refs,
            "qualification": context["pack_qualification"],
            "capabilities": chosen["capabilities"],
        }
    )
    # The published file also binds this exact preview revision. A new explicit
    # request key may select a newer capability/source revision without replacing
    # an older immutable file with the same human research parameters.
    manifest["selection_id"] = fingerprint(
        {"request_sha256": request_hash, "preview_sha256": digest}
    )
    raw = json_bytes(manifest)
    relative, material = _material(manifest["selection_id"], handoff.source_session_id, raw)
    prepared = handoff.model_copy(
        update={
            "workspace_material": material,
            "scenario_inputs": {
                **handoff.scenario_inputs,
                "material_ids": [*handoff.dataset_ids, "file:" + material["file_id"]],
            },
        }
    )
    return {
        "schema": SCHEMA,
        "preview_sha256": digest,
        "subject": chosen["inputs"]["subject"],
        "sources": [_safe(service, ref) for ref in refs],
        "qualification": context["pack_qualification"],
        "frozen": False,
        "send_authorized": False,
    }, {
        "request": request,
        "manifest": manifest,
        "relative": relative,
        "material": material,
        "references": refs,
        "prepared": prepared,
    }


def freeze(service, body, key):
    """Publish once, then let the caller enter the existing durable handoff.

    A published selection is not a retention holder. Deletion before the old
    handoff intent is durable fails closed when prepare_context reopens sources.
    """
    from .dossiers.lock import retention_lock

    with retention_lock(service.store.root):
        prior = _has_prior_selection_request(service, body, key)
        try:
            public, plan = preview(service, body)
            if body.preview_sha256 != public["preview_sha256"]:
                fail("source_selection_preview_changed", "资料或参数已变化，请重新预览")
        except StoreError as exc:
            if prior:
                raise
            raise _SourceSelectionPreflightFailure(str(exc), exc.code, exc.status) from exc
        request_hash = plan["manifest"]["request_sha256"]
        selection_id = plan["manifest"]["selection_id"]
        key_name = "key-" + fingerprint(key) + ".json"
        folder = service.store.root.joinpath(*CONTROL)
        binding = {"request_sha256": request_hash, "preview_sha256": body.preview_sha256}
        if (folder / key_name).exists():
            if _read_control(service, key_name) != binding:
                fail("source_selection_request_conflict", "同一请求键已绑定不同资料或参数")
        else:
            _write_control(service, key_name, binding)
        receipt_name = selection_id + ".json"
        receipt = {
            key: plan[key] for key in ("request", "manifest", "relative", "material", "references")
        }
        receipt["preview_sha256"] = public["preview_sha256"]
        raw = json_bytes(plan["manifest"])
        if (folder / receipt_name).exists():
            if _read_control(service, receipt_name) != receipt:
                fail("source_selection_source_changed", "已确认的原文元数据已变化")
            # Existing intent never retries an uncertain file publication.
            if read_selection(service, plan["material"], plan["prepared"]) is None:
                fail("source_selection_write_unknown", "资料选择发布结果未知，保留原请求且不重建")
        else:
            _write_control(service, receipt_name, receipt)
            sid = plan["material"]["source_session_id"]
            with directory(
                service.store.root, ("sessions", sid, "inputs", "source-selections"), create=True
            ) as fd:
                write_new(fd, selection_id + ".json", raw)
                sync_directory(fd)
                if read_file(fd, selection_id + ".json", limit=LIMIT) != raw:
                    fail("source_selection_write_unknown", "资料选择发布结果未知，保留原请求")
            service.store.session(sid)["files"][plan["material"]["file_id"]] = plan["relative"]
            service.store.save()
            read_selection(service, plan["material"], plan["prepared"])
        log.info("research_source_selection_materialized", sources=len(plan["references"]))
        return plan["prepared"]


def read_selection(service, material, body):
    """Exact dispatch by registered path; asset bundles retain their old reader."""
    from .asset_research import Material
    from .workbench import SourceSelection

    token = Material.model_validate(material)
    session = service.store.session(token.source_session_id)
    relative = session["files"].get(token.file_id, "")
    if not relative.startswith("inputs/source-selections/"):
        return None
    if body.scenario_id not in PACKS or not re.fullmatch(
        r"inputs/source-selections/[a-f0-9]{64}\.json", relative
    ):
        fail("source_selection_route_invalid", "此资料选择仅适用于两类原文研究包", 422)
    metadata, _manifest, raw = resolve_reference(
        service, token.source_session_id, {"type": "file", "id": relative}
    )
    if len(raw) > LIMIT or metadata["sha256"] != token.sha256:
        fail("source_selection_manifest_changed", "原文选择合同已变化")
    try:
        manifest = json.loads(raw)
        SelectionManifest.model_validate(manifest)
        identifier = relative.rsplit("/", 1)[1][:-5]
        receipt = _read_control(service, identifier + ".json")
        original_request = SourceSelection.model_validate(receipt["request"])
        original = receipt["request"]["handoff"]
        replay = body.model_dump(mode="json")
        replay["workspace_material"] = None
        replay["scenario_inputs"]["material_ids"] = list(body.dataset_ids)
        if (
            raw != json_bytes(receipt["manifest"])
            or manifest.get("schema") != SCHEMA
            or manifest.get("selection_id") != identifier
            or manifest.get("request_sha256") != fingerprint(receipt["request"])
            or identifier
            != fingerprint(
                {
                    "request_sha256": manifest["request_sha256"],
                    "preview_sha256": receipt["preview_sha256"],
                }
            )
            or receipt["material"] != token.model_dump()
            or receipt["relative"] != relative
            or original != replay
        ):
            raise ValueError("binding")
    except (ValidationError, ValueError, TypeError, KeyError, UnicodeError) as exc:
        log.warning("research_source_selection_invalid", error_type=type(exc).__name__)
        fail("source_selection_manifest_invalid", "原文选择缺少匹配的Host登记或完整请求")
    refs = _sources(service, receipt["request"]["sources"])
    if refs != receipt["references"]:
        fail("source_selection_source_changed", "已确认原文的当前元数据已变化")
    current, _plan = preview(service, original_request)
    if current["preview_sha256"] != receipt["preview_sha256"]:
        fail("source_selection_preview_changed", "已确认资料的方法版本或资格发生变化，请重新选择")
    return {"schema": SCHEMA, "selection_id": identifier}, [metadata, *refs]
