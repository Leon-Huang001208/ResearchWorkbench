"""Account-bound, content-addressed evidence using the existing private IO boundary."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
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
ORIGINAL_LIMIT = 8 * 1024 * 1024
TRANSACTION_LIMIT = 32 * 1024 * 1024
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


def _available_bytes(root):
    return shutil.disk_usage(root).free


def _disk_floor(root):
    system_devices = {Path("/").stat().st_dev}
    if Path("/private/var").exists():
        system_devices.add(Path("/private/var").stat().st_dev)
    return (10 if root.stat().st_dev in system_devices else 2) * 1024**3


def _file_digest(fd, name, *, limit):
    """Hash one private regular file with fixed memory and no path/link traversal."""
    descriptor = None
    try:
        if not name or name in {".", ".."} or "/" in name or "\\" in name:
            fail("knowledge_evidence_integrity")
        before = None
        if isinstance(fd, Path):
            path = fd / name
            before = path.lstat()
            if path.is_symlink() or getattr(before, "st_file_attributes", 0) & 0x400:
                fail("knowledge_evidence_integrity")
            descriptor = os.open(path, os.O_RDONLY)
        else:
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > limit
            or (os.name != "nt" and (info.st_mode & 0o077 or info.st_uid != os.getuid()))
            or (before is not None and (before.st_dev, before.st_ino) != (info.st_dev, info.st_ino))
        ):
            fail("knowledge_evidence_integrity")
        result, total = hashlib.sha256(), 0
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = None
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                total += len(block)
                if total > limit:
                    fail("knowledge_evidence_integrity")
                result.update(block)
            after = os.fstat(stream.fileno())
        if total != info.st_size or (info.st_size, info.st_mtime_ns, info.st_ctime_ns) != (
            after.st_size,
            after.st_mtime_ns,
            after.st_ctime_ns,
        ):
            fail("knowledge_evidence_integrity")
        return result.hexdigest()
    except OSError:
        fail("knowledge_evidence_unavailable")
    finally:
        if descriptor is not None:
            os.close(descriptor)


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
        if sum(map(len, files.values())) > TRANSACTION_LIMIT:
            fail("knowledge_evidence_budget", 413)
        if any(len(raw) > ORIGINAL_LIMIT for raw in files.values()):
            fail("knowledge_original_budget", 413)
        if any(not re.fullmatch(r"[a-f0-9]{64}\.bin", name) for name in files):
            fail("knowledge_file_invalid")
        file_hashes = {name: digest(raw) for name, raw in sorted(files.items())}
        if any(name[:-4] != sha for name, sha in file_hashes.items()):
            fail("knowledge_file_invalid")
        manifest = {
            "schema": 1,
            "owner": self.owner,
            "kind": kind,
            "payload": payload,
            "files": file_hashes,
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
            if self.binding() is None:
                fail("knowledge_preservation_unknown")
            if any(not SHA.fullmatch(key) for key in identifiers):
                fail("knowledge_preservation_unknown")
            try:
                if _available_bytes(self.root) - len(raw) - sum(
                    map(len, files.values())
                ) < _disk_floor(self.root):
                    fail("knowledge_storage_insufficient", 507)
            except OSError:
                fail("knowledge_storage_unavailable", 503)
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

    def _record(self, kind: str, identifier: str):
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
                        or name[:-4] != sha
                        or _file_digest(fd, name, limit=ORIGINAL_LIMIT) != sha
                    ):
                        fail("knowledge_evidence_integrity")
                if set(os.listdir(fd)) != {"manifest.json", *value["files"]}:
                    fail("knowledge_evidence_integrity")
        except (OSError, ValueError, UnicodeError, TypeError, AttributeError):
            fail("knowledge_evidence_unavailable")
        return (
            {"id": identifier, "manifest_sha256": identifier, **value["payload"]},
            {"manifest.json": identifier, **value["files"]},
        )

    def read(self, kind: str, identifier: str) -> dict:
        return self._record(kind, identifier)[0]

    def original(self, identifier: str, sha: str) -> bytes:
        record = self.read("evidence", identifier)
        if sha not in {item["sha256"] for item in record["documents"]}:
            fail("knowledge_file_not_found", 404)
        with directory(self.root, (FOLDER, "evidence", identifier), private=True) as fd:
            return read_file(fd, sha + ".bin", private=True, limit=ORIGINAL_LIMIT)

    def records(self, kind):
        if kind not in KINDS:
            fail("knowledge_namespace_invalid")
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return
        with directory(self.root, (FOLDER,), private=True) as fd:
            if kind not in os.listdir(fd):
                return
        with directory(self.root, (FOLDER, kind), private=True) as fd:
            identifiers = sorted(os.listdir(fd))
        for key in identifiers:
            yield self.read(kind, key)

    def preservation(self, *, create_lock=True):
        """Stream exact file proofs; interrupted staging remains recovery evidence."""
        with directory(self.root, private=True) as fd:
            if FOLDER not in os.listdir(fd):
                return None
        files = {}
        with retention_lock(self.root, create=create_lock):
            if self.binding() is None:
                fail("knowledge_preservation_unknown")
            with directory(self.root, (FOLDER,), private=True) as fd:
                names = set(os.listdir(fd))
                if names - {"binding.json", "connection.json", *KINDS}:
                    fail("knowledge_preservation_unknown")
                for name in names & {"binding.json", "connection.json"}:
                    raw = read_file(fd, name, private=True, limit=16384)
                    files[FOLDER + "/" + name] = digest(raw)
                if "connection.json" in names:
                    self.connection()
                for kind in sorted(names & KINDS):
                    with directory(self.root, (FOLDER, kind), private=True) as records:
                        identifiers = os.listdir(records)
                    for identifier in sorted(identifiers):
                        _, hashes = self._record(kind, identifier)
                        for name, sha in hashes.items():
                            files[f"{FOLDER}/{kind}/{identifier}/{name}"] = sha
        return {"schema_version": 1, "files": files}
