"""Lazy account-bound append-only records; public routes never expose this store."""

import hashlib
import json
import os
import re
import sqlite3
import stat
import threading
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..datahub.security import directory, read_file, sync_directory, write_new
from ..dossiers.lock import retention_lock
from ..store import StoreError

log = get_logger(__name__)
KINDS = frozenset(
    {
        "event",
        "report",
        "freeze",
        "source_job",
        "source_schedule",
        "coverage",
        "study",
        "admission",
        "score",
        "market_daily_evidence",
        "protocol",
        "calendar",
        "trial",
        "holdout",
        "proxy",
        "prices",
        "factor_profile",
        "factor_inputs",
        "validation_batch",
        "study_run",
        "score_inputs",
        "evidence_bundle",
        "claim",
    }
)


def canonical(value):
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    )


def now():
    return datetime.now(UTC).isoformat()


def fail(code, status=409):
    log.warning("event_timeline_rejected", code=code)
    raise StoreError("事件资料操作未完成，请核对版本、权限与原件", code, status)


class RecordStore:
    def __init__(self, root):
        self.root = Path(root)
        self.folder = self.root / "event_timeline"
        self.path = self.folder / "metadata.sqlite3"
        self.marker = self.root / ".event-timeline-initialized"
        self.owner_binding = hashlib.sha256(str(self.root).encode()).hexdigest()
        self.marker_bytes = canonical(
            {"format": "rwb-events-v1", "owner_binding": self.owner_binding}
        ).encode()
        self.qualification_marker = self.root / ".event-qualification-reconciliation-required"
        self.qualification_marker_bytes = canonical(
            {
                "format": "rwb-event-qualification-reconciliation-v1",
                "owner_binding": self.owner_binding,
            }
        ).encode()
        self._local = threading.local()

    def _kind(self, kind):
        if kind not in KINDS:
            fail("event_namespace_invalid", 422)

    def qualification_status(self):
        required = self.qualification_marker.exists() or self.qualification_marker.is_symlink()
        if required:
            with directory(self.root) as fd:
                if (
                    read_file(fd, self.qualification_marker.name, private=True, limit=512)
                    != self.qualification_marker_bytes
                ):
                    fail("event_qualification_marker_invalid", 503)
        return {
            "required": required,
            "code": "qualification_reconciliation_required" if required else None,
        }

    def mark_reconciliation_required(self):
        """Monotonic restore barrier; no browser or generic-record override exists."""
        with admission(), retention_lock(self.root):
            if not self.qualification_status()["required"]:
                with directory(self.root) as fd:
                    write_new(fd, self.qualification_marker.name, self.qualification_marker_bytes)
                    sync_directory(fd)
                log.warning("event_qualification_reconciliation_required")

    @staticmethod
    def _identifier(identifier):
        if not isinstance(identifier, str) or not re.fullmatch("[a-f0-9]{32}", identifier):
            fail("event_record_not_found", 404)

    def _safe_file(self, path):
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077))
        ):
            fail("event_storage_unsafe")
        return info

    def _state(self):
        with directory(self.root) as fd:
            marked = self.marker.exists() or self.marker.is_symlink()
            if (
                marked
                and read_file(fd, self.marker.name, private=True, limit=512) != self.marker_bytes
            ):
                fail("event_owner_invalid")
        if not marked:
            if self.folder.exists() or self.folder.is_symlink():
                fail("event_storage_uninitialized", 503)
            return False
        if not self.folder.exists():
            fail("event_storage_uninitialized", 503)
        with directory(self.root, ("event_timeline",), private=True):
            if not self.path.exists():
                fail("event_storage_uninitialized", 503)
            info = self._safe_file(self.path)
            if not info.st_size:
                fail("event_storage_uninitialized", 503)
            for suffix in ("-wal", "-shm", "-journal"):
                if self.path.with_name(self.path.name + suffix).exists():
                    fail("event_storage_recovery_required", 503)
        return True

    @contextmanager
    def connection(self, write=False, *, guard=None):
        connection = None
        previous_connection = getattr(self._local, "connection", None)
        try:
            exists = self._state()
            if not exists and not write:
                yield None
                return
            if not exists:
                with directory(self.root) as fd:
                    write_new(fd, self.marker.name, self.marker_bytes)
                    sync_directory(fd)
                with directory(self.root, ("event_timeline",), create=True, private=True) as fd:
                    write_new(fd, "metadata.sqlite3", b"")
            before = self._safe_file(self.path)
            connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=0)
            connection.row_factory = sqlite3.Row
            after = self._safe_file(self.path)
            if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                fail("event_storage_changed", 503)
            connection.execute("PRAGMA foreign_keys=ON")
            if write:
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
            if not exists:
                connection.executescript(
                    "CREATE TABLE identity(owner TEXT NOT NULL); CREATE TABLE records(kind TEXT NOT NULL,id TEXT NOT NULL,revision INTEGER NOT NULL,payload TEXT NOT NULL,created_at TEXT NOT NULL,PRIMARY KEY(kind,id,revision)); CREATE TABLE requests(kind TEXT NOT NULL,key TEXT NOT NULL,digest TEXT NOT NULL,response TEXT NOT NULL,PRIMARY KEY(kind,key)); CREATE TABLE claims(kind TEXT NOT NULL,identity TEXT NOT NULL,PRIMARY KEY(kind,identity)); PRAGMA user_version=1;"
                )
                connection.execute("INSERT INTO identity VALUES(?)", (self.owner_binding,))
            elif connection.execute("PRAGMA user_version").fetchone()[0] != 1 or [
                row[0] for row in connection.execute("SELECT owner FROM identity")
            ] != [self.owner_binding]:
                fail("event_owner_invalid")
            if write:
                self._local.connection = connection
            yield connection
            if write:
                if guard is not None:
                    guard()
                connection.commit()
                log.info("event_timeline_transaction_committed")
        except (sqlite3.Error, OSError, ValueError, TypeError) as exc:
            if connection is not None:
                connection.rollback()
            log.error("event_timeline_storage_failed", error_type=type(exc).__name__)
            raise StoreError(
                "事件存储不可用，未提交本次变更", "event_storage_unavailable", 503
            ) from exc
        except StoreError:
            if connection is not None:
                connection.rollback()
            raise
        finally:
            self._local.connection = previous_connection
            if connection is not None:
                connection.close()

    @staticmethod
    def _decode(row):
        if row is None:
            fail("event_record_not_found", 404)
        return {"id": row["id"], "revision": row["revision"], "payload": json.loads(row["payload"])}

    def _get(self, conn, kind, identifier, revision=None):
        if conn is None:
            fail("event_record_not_found", 404)
        if revision is None:
            row = conn.execute(
                "SELECT * FROM records WHERE kind=? AND id=? ORDER BY revision DESC LIMIT 1",
                (kind, identifier),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT * FROM records WHERE kind=? AND id=? AND revision=?",
                (kind, identifier, revision),
            ).fetchone()
        return self._decode(row)

    def revision_recorded_at(self, kind, identifier, revision):
        """Server transaction time for one immutable revision, never a caller field."""
        self._kind(kind)
        self._identifier(identifier)
        if type(revision) is not int or revision < 1:
            fail("event_revision_invalid", 422)
        with self.connection() as connection:
            if connection is None:
                fail("event_record_not_found", 404)
            row = connection.execute(
                "SELECT created_at FROM records WHERE kind=? AND id=? AND revision=?",
                (kind, identifier, revision),
            ).fetchone()
            if row is None:
                fail("event_record_not_found", 404)
            return row["created_at"]

    def get(self, kind, identifier, revision=None):
        self._kind(kind)
        self._identifier(identifier)
        active = getattr(self._local, "connection", None)
        if active is not None:
            return self._get(active, kind, identifier, revision)
        with self.connection() as conn:
            return self._get(conn, kind, identifier, revision)

    def versions(self, kind, identifier):
        self._kind(kind)
        self._identifier(identifier)
        with self.connection() as conn:
            self._get(conn, kind, identifier)
            return [
                self._decode(row)
                for row in conn.execute(
                    "SELECT * FROM records WHERE kind=? AND id=? ORDER BY revision DESC",
                    (kind, identifier),
                )
            ]

    def list(self, kind, limit=100, cursor=None):
        self._kind(kind)
        if (
            not isinstance(limit, int)
            or isinstance(limit, bool)
            or not 1 <= limit <= 200
            or (cursor is not None and not re.fullmatch("[0-9]{1,9}", str(cursor)))
        ):
            fail("event_cursor_invalid", 422)
        offset = int(cursor or 0)
        with self.connection() as conn:
            if conn is None:
                return {"items": [], "next_cursor": None}
            rows = conn.execute(
                "SELECT r.* FROM records r JOIN (SELECT id,MAX(revision) revision FROM records WHERE kind=? GROUP BY id) latest ON r.id=latest.id AND r.revision=latest.revision WHERE r.kind=? ORDER BY r.created_at,r.id LIMIT ? OFFSET ?",
                (kind, kind, limit + 1, offset),
            ).fetchall()
            return {
                "items": [self._decode(row) for row in rows[:limit]],
                "next_cursor": str(offset + limit) if len(rows) > limit else None,
            }

    def create(self, kind, payload, idempotency_key, *, guard=None):
        return self.batch([{"kind": kind, "payload": payload}], idempotency_key, guard=guard)[0]

    def update(self, kind, identifier, payload, expected_revision, idempotency_key, *, guard=None):
        return self.batch(
            [
                {
                    "kind": kind,
                    "id": identifier,
                    "payload": payload,
                    "expected_revision": expected_revision,
                }
            ],
            idempotency_key,
            guard=guard,
        )[0]

    def cached(self, scope, idempotency_key, intent):
        with self.connection() as conn:
            if conn is None:
                return None
            row = conn.execute(
                "SELECT * FROM requests WHERE kind=? AND key=?", (scope, idempotency_key)
            ).fetchone()
            if row is None:
                return None
            if row["digest"] != hashlib.sha256(canonical(intent).encode()).hexdigest():
                fail("event_idempotency_conflict")
            return json.loads(row["response"])

    def batch(self, operations, idempotency_key, *, intent=None, scope=None, guard=None):
        if (
            not isinstance(operations, list)
            or not 1 <= len(operations) <= 200
            or not isinstance(idempotency_key, str)
            or not 8 <= len(idempotency_key) <= 256
        ):
            fail("event_mutation_invalid", 422)
        for op in operations:
            self._kind(op.get("kind"))
            limit = (
                16 * 1024 * 1024
                if op["kind"] in {"prices", "calendar", "factor_inputs", "study_run", "freeze"}
                else 1024 * 1024
            )
            if (
                not isinstance(op.get("payload"), dict)
                or len(canonical(op["payload"]).encode()) > limit
            ):
                fail("event_payload_invalid", 422)
            if op.get("id") is not None:
                self._identifier(op["id"])
            if op.get("new_id") is not None:
                self._identifier(op["new_id"])
                if op.get("id") is not None:
                    fail("event_mutation_invalid", 422)
        digest = hashlib.sha256(
            canonical(operations if intent is None else intent).encode()
        ).hexdigest()
        scope = scope or (operations[0]["kind"] if len(operations) == 1 else "batch")
        with (
            admission(),
            retention_lock(self.root),
            self.connection(write=True, guard=guard) as conn,
        ):
            old = conn.execute(
                "SELECT * FROM requests WHERE kind=? AND key=?", (scope, idempotency_key)
            ).fetchone()
            if old:
                if old["digest"] != digest:
                    fail("event_idempotency_conflict")
                return json.loads(old["response"])
            result = []
            for op in operations:
                identifier, revision = op.get("id") or op.get("new_id") or uuid4().hex, 1
                if (
                    op.get("new_id") is not None
                    and conn.execute(
                        "SELECT 1 FROM records WHERE kind=? AND id=?", (op["kind"], identifier)
                    ).fetchone()
                ):
                    fail("event_record_exists")
                if op.get("id"):
                    previous = self._get(conn, op["kind"], identifier)
                    if isinstance(op.get("expected_revision"), bool) or previous[
                        "revision"
                    ] != op.get("expected_revision"):
                        fail("event_revision_conflict")
                    revision = previous["revision"] + 1
                    if op.get("check_only"):
                        result.append(previous)
                        continue
                conn.execute(
                    "INSERT INTO records VALUES(?,?,?,?,?)",
                    (op["kind"], identifier, revision, canonical(op["payload"]), now()),
                )
                result.append({"id": identifier, "revision": revision, "payload": op["payload"]})
            conn.execute(
                "INSERT INTO requests VALUES(?,?,?,?)",
                (scope, idempotency_key, digest, canonical(result)),
            )
            return result

    def claim_once(self, kind, identity, payload):
        self._kind(kind)
        if kind == "holdout" and self.qualification_status()["required"]:
            fail("qualification_reconciliation_required")
        if (
            not isinstance(identity, str)
            or not 1 <= len(identity) <= 512
            or not isinstance(payload, dict)
        ):
            fail("event_claim_invalid", 422)
        with admission(), retention_lock(self.root), self.connection(write=True) as conn:
            if kind == "holdout" and self.qualification_status()["required"]:
                fail("qualification_reconciliation_required")
            if conn.execute(
                "SELECT 1 FROM claims WHERE kind=? AND identity=?", (kind, identity)
            ).fetchone():
                fail("event_claim_conflict")
            conn.execute("INSERT INTO claims VALUES(?,?)", (kind, identity))
            identifier = uuid4().hex
            conn.execute(
                "INSERT INTO records VALUES(?,?,?,?,?)",
                (kind, identifier, 1, canonical(payload), now()),
            )
            return {"id": identifier, "revision": 1, "payload": payload}

    def claim_study_ranges(self, ranges, key):
        """Reserve inclusive holdout ranges across processes; a new key never reopens."""
        if (
            not isinstance(ranges, list)
            or not 1 <= len(ranges) <= 100
            or not isinstance(key, str)
            or not 8 <= len(key) <= 256
        ):
            fail("event_range_claim_invalid", 422)
        for row in ranges:
            if (
                set(row) != {"scope", "start", "end", "phase", "batch_id"}
                or row["phase"] not in {"viewed", "sealed", "opened"}
                or not all(
                    isinstance(row[name], str) and 1 <= len(row[name]) <= 200
                    for name in ("scope", "batch_id")
                )
            ):
                fail("event_range_claim_invalid", 422)
            try:
                start = datetime.strptime(row["start"], "%Y-%m-%d")
                end = datetime.strptime(row["end"], "%Y-%m-%d")
            except (ValueError, TypeError):
                fail("event_range_claim_invalid", 422)
            if end < start:
                fail("event_range_claim_invalid", 422)
        if (
            any(row["phase"] in {"sealed", "opened"} for row in ranges)
            and self.qualification_status()["required"]
        ):
            fail("qualification_reconciliation_required")
        digest = hashlib.sha256(canonical(ranges).encode()).hexdigest()
        with admission(), retention_lock(self.root), self.connection(write=True) as conn:
            if (
                any(row["phase"] in {"sealed", "opened"} for row in ranges)
                and self.qualification_status()["required"]
            ):
                fail("qualification_reconciliation_required")
            old = conn.execute(
                "SELECT * FROM requests WHERE kind='range-claim' AND key=?", (key,)
            ).fetchone()
            if old:
                if old["digest"] != digest:
                    fail("event_idempotency_conflict")
                return json.loads(old["response"])
            conn.execute(
                "CREATE TABLE IF NOT EXISTS range_claims(scope TEXT NOT NULL,start TEXT NOT NULL,end TEXT NOT NULL,phase TEXT NOT NULL,batch_id TEXT NOT NULL)"
            )
            for row in ranges:
                matches = conn.execute(
                    "SELECT * FROM range_claims WHERE scope=? AND start<=? AND end>=?",
                    (row["scope"], row["end"], row["start"]),
                ).fetchall()
                own = [
                    dict(value)
                    for value in matches
                    if value["batch_id"] == row["batch_id"]
                    and value["start"] == row["start"]
                    and value["end"] == row["end"]
                ]
                if row["phase"] == "viewed" and all(
                    value["phase"] == "viewed" for value in matches
                ):
                    pass
                elif any(value["batch_id"] != row["batch_id"] for value in matches):
                    fail("event_holdout_range_reused")
                if row["phase"] == "opened":
                    if not any(value["phase"] == "sealed" for value in own) or any(
                        value["phase"] == "opened" for value in own
                    ):
                        fail("event_holdout_range_reused")
                elif (
                    matches
                    and row["phase"] != "viewed"
                    or row["phase"] == "viewed"
                    and any(value["phase"] != "viewed" for value in matches)
                ):
                    fail("event_holdout_range_reused")
                conn.execute(
                    "INSERT INTO range_claims VALUES(?,?,?,?,?)",
                    tuple(row[name] for name in ("scope", "start", "end", "phase", "batch_id")),
                )
            result = {"ranges": ranges, "claim_sha256": digest}
            conn.execute(
                "INSERT INTO requests VALUES(?,?,?,?)",
                ("range-claim", key, digest, canonical(result)),
            )
            return result

    def export_manifest(self, *, create_lock=False):
        from .preservation import export_manifest

        return export_manifest(self, create_lock=create_lock)

    snapshot = export_manifest

    def backup_to(self, destination):
        from .preservation import backup_to

        return backup_to(self, destination)

    def restore_from(self, source, *, expected_sha256):
        from .preservation import restore_from

        return restore_from(self, source, expected_sha256=expected_sha256)
