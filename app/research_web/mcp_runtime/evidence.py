"""Freeze MCP originals in the existing session Snapshot store, never a body ledger."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from uuid import UUID

from core.observability import get_logger

from ..datahub.security import directory, json_bytes, read_file
from ..datahub.snapshots import Snapshots, csv_bytes
from ..store import StoreError
from .authorization import _arguments_hash, _canonical_bytes
from .seek_alpha import assess_result

log = get_logger(__name__)
MAX_RESULT_BYTES = 2 * 1024 * 1024


def raw_result(result):
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json")
    if not isinstance(result, dict):
        raise StoreError("MCP 返回格式无效", "mcp_result_invalid", 502)
    try:
        raw = _canonical_bytes(result, maximum=MAX_RESULT_BYTES, error_code="mcp_result_too_large")
    except Exception as exc:
        raise StoreError("MCP 返回格式无效或过大", "mcp_result_invalid", 502) from exc
    return json.loads(raw), raw


class _RetainedReadStore:
    """Keep soft-deleted source evidence readable after Host authorization."""

    def __init__(self, store):
        self.root = store.root
        self.original = store

    def session(self, sid):
        return self.original.session(sid, include_deleted=True)


class MCPResultEvidence:
    def __init__(self, store, *, retained=False):
        self.store = _RetainedReadStore(store) if retained else store
        self.snapshots = Snapshots(self.store)

    @staticmethod
    def dataset_id(session_id, call_id):
        return str(
            UUID(hashlib.sha256((session_id + "\0mcp\0" + call_id).encode()).hexdigest()[:32])
        )

    def freeze(self, request, result, *, endpoint, cost_state=None):
        sid = request["session_id"]
        self.store.session(sid)
        value, raw = raw_result(result)
        digest = hashlib.sha256(raw).hexdigest()
        did = self.dataset_id(sid, request["call_id"])
        call_digest = hashlib.sha256(request["call_id"].encode()).hexdigest()
        with directory(
            self.store.root, (".control", "snapshots", sid), create=True, private=True
        ) as folder:
            committed = did in os.listdir(folder)
        if committed:
            manifest = self.snapshots.detail(sid, did)
            binding = manifest.get("provider_metadata", {})
            if (
                binding.get("result_sha256") != digest
                or binding.get("arguments_sha256") != _arguments_hash(request["arguments"])
                or any(
                    binding.get(key) != request[key]
                    for key in ("installation_id", "version", "tool_name", "schema_sha256")
                )
            ):
                raise StoreError("MCP 调用身份冲突", "mcp_call_identity_conflict", 409)
            return {"dataset_id": did, "result_sha256": digest}
        now = datetime.now(UTC).isoformat()
        pending_path = self.store.root / ".control" / "snapshots" / sid / (".pending-" + did)
        if pending_path.exists() or pending_path.is_symlink():
            with directory(
                self.store.root, (".control", "snapshots", sid, ".pending-" + did), private=True
            ) as folder:
                pending = json.loads(read_file(folder, "manifest.json", private=True))
                if pending["provider_metadata"]["result_sha256"] != digest:
                    raise StoreError("MCP 暂存原件不一致", "mcp_evidence_invalid", 409)
                now = pending["retrieved_at"]
                cost_state = pending["provider_metadata"]["cost_state"]
        assessment = assess_result(value)
        binding = {
            "installation_id": request["installation_id"],
            "version": request["version"],
            "tool_name": request["tool_name"],
            "schema_sha256": request["schema_sha256"],
            "arguments_sha256": _arguments_hash(request["arguments"]),
            "call_id_sha256": call_digest,
            "result_sha256": digest,
            "source_published_at": None,
            "retrieved_at": now,
            "cost_state": cost_state,
            "admission": assessment,
        }
        rows = [{"result": value}]
        public = {"rows.json": json_bytes(rows), "rows.csv": csv_bytes(rows)}
        manifest = {
            "id": did,
            "dataset_id": did,
            "name": "MCP " + request["tool_name"],
            "source": "mcp",
            "provider": request["installation_id"],
            "capability": "mcp_tool_result",
            "schema_version": 1,
            "snapshot_kind": "mcp_evidence",
            "status": "snapshot",
            "as_of": None,
            "retrieved_at": now,
            "source_url": endpoint,
            "row_count": 1,
            "provider_total": 1,
            "pages_fetched": 1,
            "pagination_complete": True,
            "duplicates_removed": 0,
            "attempted_sources": [],
            "coverage": "single MCP response; source coverage not independently verified",
            "quality_accepted": False,
            "missing": [],
            "fields": {},
            "limitations": assessment["issues"],
            "provider_metadata": binding,
            "query": {
                key: request[key]
                for key in ("installation_id", "version", "tool_name", "schema_sha256")
            },
            "provider_query": {"arguments_sha256": binding["arguments_sha256"]},
            "query_fingerprint": call_digest,
            "files": [
                {
                    "name": name,
                    "path": f"inputs/datasets/{did}/{name}",
                    "sha256": hashlib.sha256(content).hexdigest(),
                    "size": len(content),
                }
                for name, content in public.items()
            ],
            "raw_files": [
                {
                    "name": "raw-0001.bin",
                    "path": f".control/snapshots/{sid}/{did}/raw-0001.bin",
                    "sha256": digest,
                    "size": len(raw),
                }
            ],
        }
        public["manifest.json"] = json_bytes(manifest)
        private = {"raw-0001.bin": raw, "manifest.json": public["manifest.json"]}
        # Deterministic id + recover=True retains staged originals on storage failure.
        self.snapshots._publish_files(sid, did, manifest, public, private, recover=True)
        log.info("mcp_result_frozen", session_id=sid, dataset_id=did, status="clue")
        return {"dataset_id": did, "result_sha256": digest}

    def read(self, session_id, dataset_id):
        manifest = self.snapshots.detail(session_id, dataset_id)
        with directory(
            self.store.root, (".control", "snapshots", session_id, dataset_id), private=True
        ) as folder:
            raw = read_file(folder, "raw-0001.bin", private=True, limit=MAX_RESULT_BYTES)
        if hashlib.sha256(raw).hexdigest() != manifest["provider_metadata"]["result_sha256"]:
            raise StoreError("MCP 原件hash不一致", "mcp_evidence_invalid", 409)
        return {
            "result": json.loads(raw),
            "manifest": manifest,
            "evidence": {
                "dataset_id": dataset_id,
                "result_sha256": hashlib.sha256(raw).hexdigest(),
            },
        }

    def recover(self, request, *, endpoint, cost_state=None):
        sid, did = request["session_id"], self.dataset_id(request["session_id"], request["call_id"])
        self.store.session(sid)
        parts = (".control", "snapshots", sid)
        for name in (did, ".pending-" + did):
            try:
                with directory(self.store.root, (*parts, name), private=True) as folder:
                    raw = read_file(folder, "raw-0001.bin", private=True, limit=MAX_RESULT_BYTES)
            except (OSError, StoreError):
                continue
            try:
                value = json.loads(raw)
                reference = self.freeze(request, value, endpoint=endpoint, cost_state=cost_state)
                return value, reference
            except (ValueError, TypeError) as exc:
                log.warning("mcp_result_recovery_invalid", error_type=type(exc).__name__)
                raise StoreError("MCP 快照恢复失败", "mcp_evidence_invalid", 409) from exc
        raise StoreError("原始响应尚不可恢复，禁止重发", "mcp_call_result_unknown", 409)
