"""Private immutable source bytes with server-owned provenance and hash revalidation."""

import hashlib
import json
import re

from core.observability import get_logger

from ..datahub.security import directory, json_bytes, read_file, sync_directory, write_new
from ..dossiers.lock import retention_lock
from ..store import StoreError
from .storage import fail, now

log = get_logger(__name__)
MAX_BYTES = 16 * 1024 * 1024


class EvidenceArchive:
    def __init__(self, records):
        self.records = records

    def archive(self, raw, *, source, url, metadata=None, guard=None):
        if (
            not isinstance(raw, bytes)
            or not raw
            or len(raw) > MAX_BYTES
            or not re.fullmatch("[A-Za-z0-9_.-]{1,100}", source)
        ):
            fail("event_evidence_invalid", 422)
        if not isinstance(url, str) or len(url) > 4000:
            fail("event_evidence_invalid", 422)
        if guard is not None:
            guard()
        with retention_lock(self.records.root), self.records.connection(write=True, guard=guard):
            digest = hashlib.sha256(raw).hexdigest()
            identity = json_bytes(
                {"source": source, "url": url, "metadata": metadata or {}, "sha256": digest}
            )
            identifier = hashlib.sha256(identity).hexdigest()[:32]
            folder = self.records.folder / "evidence" / identifier
            if folder.exists() or folder.is_symlink():
                with directory(
                    self.records.root, ("event_timeline", "evidence", identifier), private=True
                ) as fd:
                    previous = read_file(fd, "manifest.json", private=True, limit=128 * 1024)
                ref = {
                    "id": identifier,
                    "sha256": digest,
                    "manifest_sha256": hashlib.sha256(previous).hexdigest(),
                }
                self.read(ref)
                return ref
            manifest = {
                "schema": "event-evidence-v1",
                "id": identifier,
                "source": source,
                "url": url,
                "owner_binding": self.records.owner_binding,
                "sha256": digest,
                "size": len(raw),
                "first_observed": now(),
                "metadata": metadata or {},
            }
            manifest_bytes = json_bytes(manifest)
            if len(manifest_bytes) > 128 * 1024:
                fail("event_evidence_invalid", 422)
            with directory(
                self.records.root,
                ("event_timeline", "evidence", identifier),
                create=True,
                private=True,
            ) as fd:
                if guard is not None:
                    guard()
                write_new(fd, "raw.bin", raw)
                if guard is not None:
                    guard()
                write_new(fd, "manifest.json", manifest_bytes)
                sync_directory(fd)
        log.info("event_evidence_archived", source=source, sha256=digest)
        return {
            "id": identifier,
            "sha256": digest,
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
        }

    def read(self, reference):
        if (
            not isinstance(reference, dict)
            or not re.fullmatch("[a-f0-9]{32}", str(reference.get("id", "")))
            or not re.fullmatch("[a-f0-9]{64}", str(reference.get("sha256", "")))
        ):
            fail("event_evidence_reference_invalid", 422)
        self.records._state()
        try:
            with directory(
                self.records.root, ("event_timeline", "evidence", reference["id"]), private=True
            ) as fd:
                encoded = read_file(fd, "manifest.json", private=True, limit=128 * 1024)
                manifest = json.loads(encoded)
                raw = read_file(fd, "raw.bin", private=True, limit=MAX_BYTES)
            if (
                manifest.get("schema") != "event-evidence-v1"
                or manifest.get("owner_binding") != self.records.owner_binding
                or manifest.get("id") != reference["id"]
                or manifest.get("size") != len(raw)
                or manifest.get("sha256") != reference["sha256"]
                or hashlib.sha256(raw).hexdigest() != reference["sha256"]
                or (
                    reference.get("manifest_sha256") is not None
                    and reference["manifest_sha256"] != hashlib.sha256(encoded).hexdigest()
                )
            ):
                fail("event_evidence_changed")
            return {"bytes": raw, "manifest": manifest}
        except (ValueError, OSError, StoreError) as exc:
            log.warning("event_evidence_unavailable", error_type=type(exc).__name__)
            raise StoreError(
                "事件原件缺失、变化或归属不匹配", "event_evidence_unavailable", 409
            ) from exc
