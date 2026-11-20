"""Account-bound, content-addressed evidence using the existing private IO boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import NoReturn
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..datahub.security import (
    atomic_json,
    directory,
    json_bytes,
    make_directory,
    read_file,
    rename_directory,
    sync_directory,
    write_new,
)
from ..dossiers.lock import retention_lock
from ..store import StoreError

log = get_logger(__name__)
FOLDER = "knowledge-backend"
SHA = re.compile(r"[a-f0-9]{64}\Z")
MANIFEST_LIMIT = 256 * 1024
BINDING_LIMIT = 16 * 1024
RECORD_LIMIT = 1000
KINDS = {"scopes", "evidence", "receipts"}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode()


def fail(code: str, status: int = 409) -> NoReturn:
    log.warning("knowledge_backend_rejected", code=code)
    raise StoreError("资料操作未完成，请核对授权、版本和原件", code, status)


class KnowledgeStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.owner = digest(str(self.root).encode())

    def binding(self) -> dict | None:
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return None
        with directory(self.root, (FOLDER,), private=True) as fd:
            if "binding.json" not in os.listdir(fd):
                return None
            try:
                value = json.loads(read_file(fd, "binding.json", private=True, limit=BINDING_LIMIT))
            except (ValueError, UnicodeError):
                fail("knowledge_binding_invalid")
        if (
            not isinstance(value, dict)
            or value.get("owner") != self.owner
            or value.get("schema") != 1
        ):
            fail("knowledge_binding_invalid")
        return value

    def check_binding_budget(self, value: dict) -> None:
        payload = {**value, "schema": 1, "owner": self.owner}
        if len(json_bytes(payload)) > BINDING_LIMIT:
            fail("knowledge_binding_budget", 413)

    def save_binding(self, value: dict) -> None:
        self.check_binding_budget(value)
        payload = {**value, "schema": 1, "owner": self.owner}
        with (
            admission(),
            retention_lock(self.root),
            directory(self.root, (FOLDER,), create=True, private=True) as fd,
        ):
            atomic_json(fd, "binding.json", payload)

    def connection(self) -> dict:
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return {}
        with directory(self.root, (FOLDER,), private=True) as fd:
            if "connection.json" not in os.listdir(fd):
                return {}
            try:
                value = json.loads(
                    read_file(fd, "connection.json", private=True, limit=BINDING_LIMIT)
                )
            except (ValueError, UnicodeError):
                fail("knowledge_connection_invalid")
        if not isinstance(value, dict) or value.get("owner") != self.owner:
            fail("knowledge_connection_invalid")
        return value

    def save_connection(self, value: dict) -> None:
        binding = self.binding()
        if binding is None:
            return
        identity = {key: binding[key] for key in ("origin", "user_id", "workspace_id")}
        with (
            admission(),
            retention_lock(self.root),
            directory(self.root, (FOLDER,), private=True) as fd,
        ):
            atomic_json(
                fd, "connection.json", {**identity, **value, "owner": self.owner, "schema": 1}
            )

    def create(self, kind: str, payload: dict, files: dict[str, bytes] | None = None) -> dict:
        if kind not in KINDS:
            fail("knowledge_namespace_invalid")
        files = files or {}
        if sum(map(len, files.values())) > 32 * 1024 * 1024:
            fail("knowledge_evidence_budget", 413)
        if any(not re.fullmatch(r"[a-f0-9]{64}\.bin", name) for name in files):
            fail("knowledge_file_invalid")
        manifest = {
            "schema": 1,
            "owner": self.owner,
            "kind": kind,
            "payload": payload,
            "files": {name: digest(raw) for name, raw in sorted(files.items())},
        }
        raw = canonical(manifest)
        if len(raw) > MANIFEST_LIMIT:
            fail("knowledge_manifest_budget", 413)
        identifier = digest(raw)
        with (
            admission(),
            retention_lock(self.root),
            directory(self.root, (FOLDER, kind), create=True, private=True) as fd,
        ):
            identifiers = os.listdir(fd)
            if identifier in identifiers:
                return self.read(kind, identifier)
            if len(identifiers) >= RECORD_LIMIT:
                fail("knowledge_record_budget", 413)
            proof = self.preservation()
            existing_bytes = 0
            for relative in (proof or {}).get("files", {}):
                parts = relative.split("/")
                with directory(self.root, tuple(parts[:-1]), private=True) as parent:
                    existing_bytes += len(
                        read_file(parent, parts[-1], private=True, limit=8 * 1024 * 1024)
                    )
            if existing_bytes + len(raw) + sum(map(len, files.values())) > 64 * 1024 * 1024:
                fail("knowledge_preservation_budget", 413)
            temporary = "pending-" + uuid4().hex
            make_directory(fd, temporary)
            # A failed or interrupted staging directory is retained as recovery evidence.
            with directory(self.root, (FOLDER, kind, temporary), private=True) as staging:
                for name, content in files.items():
                    write_new(staging, name, content)
                write_new(staging, "manifest.json", raw)
                sync_directory(staging)
            rename_directory(fd, temporary, identifier)
            sync_directory(fd)
        log.info("knowledge_evidence_committed", kind=kind, file_count=len(files))
        return self.read(kind, identifier)

    def read(self, kind: str, identifier: str) -> dict:
        if kind not in KINDS or not isinstance(identifier, str) or not SHA.fullmatch(identifier):
            fail("knowledge_record_not_found", 404)
        try:
            with directory(self.root, (FOLDER, kind, identifier), private=True) as fd:
                raw = read_file(fd, "manifest.json", private=True, limit=MANIFEST_LIMIT)
                value = json.loads(raw)
                if (
                    digest(raw) != identifier
                    or value.get("owner") != self.owner
                    or value.get("schema") != 1
                    or value.get("kind") != kind
                ):
                    fail("knowledge_evidence_integrity")
                if not isinstance(value.get("files"), dict):
                    fail("knowledge_evidence_integrity")
                for name, sha in value["files"].items():
                    if (
                        not re.fullmatch(r"[a-f0-9]{64}\.bin", name)
                        or digest(read_file(fd, name, private=True, limit=8 * 1024 * 1024)) != sha
                    ):
                        fail("knowledge_evidence_integrity")
                if set(os.listdir(fd)) != {"manifest.json", *value["files"]}:
                    fail("knowledge_evidence_integrity")
        except (OSError, ValueError, UnicodeError, TypeError, AttributeError):
            fail("knowledge_evidence_unavailable")
        return {"id": identifier, "manifest_sha256": identifier, **value["payload"]}

    def original(self, identifier: str, sha: str) -> bytes:
        record = self.read("evidence", identifier)
        if sha not in {item["sha256"] for item in record["documents"]}:
            fail("knowledge_file_not_found", 404)
        with directory(self.root, (FOLDER, "evidence", identifier), private=True) as fd:
            return read_file(fd, sha + ".bin", private=True, limit=8 * 1024 * 1024)

    def records(self, kind):
        if kind not in KINDS:
            fail("knowledge_namespace_invalid")
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return []
        with directory(self.root, (FOLDER,), private=True) as fd:
            if kind not in os.listdir(fd):
                return []
        with directory(self.root, (FOLDER, kind), private=True) as fd:
            identifiers = sorted(os.listdir(fd))
        if len(identifiers) > RECORD_LIMIT:
            fail("knowledge_preservation_budget", 413)
        return [self.read(kind, key) for key in identifiers]

    def preservation(self, *, create_lock=True):
        """Bounded exact proof; interrupted staging is unknown, never disposable."""
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return None
        files, total = {}, 0
        with retention_lock(self.root, create=create_lock):
            if self.binding() is None:
                fail("knowledge_preservation_unknown")
            with directory(self.root, (FOLDER,), private=True) as fd:
                names = set(os.listdir(fd))
                if names - {"binding.json", "connection.json", *KINDS}:
                    fail("knowledge_preservation_unknown")
                for name in names & {"binding.json", "connection.json"}:
                    raw = read_file(fd, name, private=True, limit=16384)
                    total += len(raw)
                    files[FOLDER + "/" + name] = digest(raw)
                if "connection.json" in names:
                    self.connection()
                for kind in sorted(names & KINDS):
                    with directory(self.root, (FOLDER, kind), private=True) as records:
                        identifiers = os.listdir(records)
                    if len(identifiers) > RECORD_LIMIT:
                        fail("knowledge_preservation_budget")
                    for identifier in sorted(identifiers):
                        self.read(kind, identifier)
                        with directory(
                            self.root, (FOLDER, kind, identifier), private=True
                        ) as record:
                            for name in os.listdir(record):
                                raw = read_file(record, name, private=True, limit=8 * 1024 * 1024)
                                total += len(raw)
                                if total > 64 * 1024 * 1024:
                                    fail("knowledge_preservation_budget")
                                files[f"{FOLDER}/{kind}/{identifier}/{name}"] = digest(raw)
        return {"schema_version": 1, "files": files}
