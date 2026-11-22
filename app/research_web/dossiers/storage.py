"""Lazy per-user SQLite metadata and append-only revisions, with atomic retention pins."""

import hashlib
import json
import os
import re
import sqlite3
import stat
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..datahub.security import directory, read_file, sync_directory, write_new
from ..store import StoreError
from .lock import retention_lock

log = get_logger(__name__)


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def now():
    return datetime.now(UTC).isoformat()


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise StoreError("研究档案不存在", "dossier_not_found", 404)
    return value


class DossierStore:
    def __init__(self, root):
        self.root = root
        self.folder = root / "dossiers"
        self.path = self.folder / "metadata.sqlite3"
        self.owner_binding = hashlib.sha256(str(root).encode()).hexdigest()
        self.marker = root / ".dossiers-initialized"
        self._marker_bytes = canonical(
            {"format": "rwb-dossiers-initialized-v1", "owner_binding": self.owner_binding}
        ).encode("utf-8")
        self.marker_size = len(self._marker_bytes)
        self.marker_sha256 = hashlib.sha256(self._marker_bytes).hexdigest()

    def _marker_info(self, folder):
        return (
            os.stat(self.marker.name, dir_fd=folder, follow_symlinks=False)
            if isinstance(folder, int)
            else self.marker.lstat()
        )

    def _marked(self):
        """Read-only, bounded root marker validation; absence never creates it."""
        try:
            with directory(self.root) as folder:
                try:
                    before = self._marker_info(folder)
                except FileNotFoundError:
                    return False
                if (
                    not stat.S_ISREG(before.st_mode)
                    or before.st_nlink != 1
                    or before.st_size != self.marker_size
                    or getattr(before, "st_file_attributes", 0)
                    & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
                    or os.name != "nt"
                    and (before.st_uid != os.getuid() or before.st_mode & 0o077)
                ):
                    raise ValueError("unsafe initialization marker")
                raw = read_file(folder, self.marker.name, private=True, limit=self.marker_size)
                after = self._marker_info(folder)
                if (
                    (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
                    or len(raw) != self.marker_size
                    or hashlib.sha256(raw).hexdigest() != self.marker_sha256
                ):
                    raise ValueError("initialization marker changed")
                return True
        except (StoreError, OSError, ValueError) as exc:
            log.error("dossier_initialization_marker_invalid", error_type=type(exc).__name__)
            raise StoreError(
                "档案初始化标记不可安全核验，已停止操作", "dossier_marker_invalid", 503
            ) from exc

    def _ensure_marker(self):
        """Persist protection before the first metadata directory or transaction exists."""
        with admission(), retention_lock(self.root):
            if self._marked():
                return
            try:
                with directory(self.root) as folder:
                    # O_EXCL, private mode and file fsync are enforced by write_new.
                    # A partial marker is retained and fails closed after a write error.
                    write_new(folder, self.marker.name, self._marker_bytes)
                    sync_directory(folder)
                self._marked()
                log.info(
                    "dossier_initialization_protection_recorded", marker_sha256=self.marker_sha256
                )
            except (StoreError, OSError) as exc:
                log.error(
                    "dossier_initialization_marker_write_failed", error_type=type(exc).__name__
                )
                raise StoreError(
                    "档案初始化保护标记未完成，已停止操作", "dossier_marker_invalid", 503
                ) from exc

    def _uninitialized(self):
        log.error("dossier_database_missing_or_empty")
        raise StoreError(
            "档案库缺失或为空；读写与永久删除已停止，请通过已核验备份显式恢复",
            "dossier_storage_uninitialized",
            503,
        )

    def _safe(self, create=False, *, allow_uninitialized=False):
        marked = self._marked()
        created = False
        if not self.folder.exists():
            if self.folder.is_symlink():
                raise StoreError("档案存储路径不安全", "dossier_storage_unsafe", 409)
            if marked and not allow_uninitialized:
                self._uninitialized()
            if not create:
                return False
            self._ensure_marker()
            marked = True
            self.folder.mkdir(mode=0o700)
            created = True
        info = self.folder.lstat()
        if (
            self.folder.is_symlink()
            or not stat.S_ISDIR(info.st_mode)
            or (os.name != "nt" and stat.S_IMODE(info.st_mode) & 0o077)
        ):
            raise StoreError("档案存储路径不安全", "dossier_storage_unsafe", 409)
        for path in (self.path, self.folder / "metadata.sqlite3-journal"):
            if path.is_symlink():
                raise StoreError("档案存储路径不安全", "dossier_storage_unsafe", 409)
            if path.exists():
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise StoreError("档案存储路径不安全", "dossier_storage_unsafe", 409)
        exists = self.path.exists()
        if (
            not created
            and not allow_uninitialized
            and (not exists or self.path.stat().st_size == 0)
        ):
            self._uninitialized()
        if create and not marked:
            self._ensure_marker()
        return exists

    @contextmanager
    def connection(self, write=False):
        connection = None
        try:
            exists = self._safe(create=write)
            initialized = exists and self.path.stat().st_size > 0
            if exists and not initialized:
                self._uninitialized()
            if not initialized and not write:
                yield None
                return
            connection = sqlite3.connect(
                self.path.as_uri()
                + ("?mode=rw" if exists and write else "?mode=rwc" if write else "?mode=ro"),
                uri=True,
                timeout=0,
            )
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            if initialized:
                self._validate_database(connection)
            if write:
                os.chmod(self.path, 0o600)
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS dossiers (id TEXT PRIMARY KEY, title TEXT NOT NULL, subject TEXT NOT NULL, revision INTEGER NOT NULL, archived INTEGER NOT NULL, updated_at TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, dossier_id TEXT NOT NULL REFERENCES dossiers(id), revision INTEGER NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(dossier_id, revision))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS evidence (id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL REFERENCES dossiers(id), source_session_id TEXT NOT NULL, identity TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(dossier_id, identity))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS retention (dossier_id TEXT NOT NULL REFERENCES dossiers(id), source_session_id TEXT NOT NULL, evidence_id TEXT NOT NULL REFERENCES evidence(id), PRIMARY KEY(dossier_id, evidence_id))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS links (id TEXT PRIMARY KEY, dossier_id TEXT NOT NULL REFERENCES dossiers(id), payload TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS requests (scope TEXT NOT NULL, key TEXT NOT NULL, digest TEXT NOT NULL, response TEXT NOT NULL, PRIMARY KEY(scope, key))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS identity (owner_binding TEXT NOT NULL)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS handoffs (id TEXT PRIMARY KEY,dossier_id TEXT NOT NULL REFERENCES dossiers(id),response TEXT NOT NULL,session_id TEXT)"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS versions (dossier_id TEXT NOT NULL REFERENCES dossiers(id),revision INTEGER NOT NULL,metadata TEXT NOT NULL,PRIMARY KEY(dossier_id,revision))"
                )
                if not initialized:
                    connection.execute("INSERT INTO identity VALUES(?)", (self.owner_binding,))
                    connection.execute("PRAGMA user_version=1")
            # Only this first writer may see its own zero-byte file before the
            # schema transaction commits. Later callers must never recreate it.
            if not self._safe(allow_uninitialized=not exists):
                self._uninitialized()
            yield connection
            if write:
                connection.commit()
        except sqlite3.Error as exc:
            if connection is not None:
                connection.rollback()
            log.error("dossier_database_failed", error_type=type(exc).__name__)
            code = (
                "dossier_revision_conflict"
                if isinstance(exc, sqlite3.OperationalError) and "locked" in str(exc)
                else "dossier_storage_unavailable"
            )
            raise StoreError(
                "档案事务未完成，请重新读取后重试", code, 409 if code.endswith("conflict") else 503
            ) from exc
        except OSError as exc:
            log.error("dossier_storage_failed", error_type=type(exc).__name__)
            raise StoreError("档案存储不可用", "dossier_storage_unavailable", 503) from exc
        finally:
            if connection is not None:
                connection.close()

    def _validate_database(self, connection):
        try:
            owners = connection.execute("SELECT owner_binding FROM identity").fetchall()
            if (
                connection.execute("PRAGMA user_version").fetchone()[0] != 1
                or len(owners) != 1
                or owners[0][0] != self.owner_binding
            ):
                raise StoreError(
                    "档案数据不属于当前账户根或版本不兼容", "dossier_storage_identity_mismatch", 409
                )
        except sqlite3.DatabaseError as exc:
            raise StoreError(
                "档案数据库身份不可核验", "dossier_storage_identity_mismatch", 409
            ) from exc

    def _row(self, connection, did):
        identifier(did)
        row = (
            connection.execute("SELECT * FROM dossiers WHERE id=?", (did,)).fetchone()
            if connection
            else None
        )
        if row is None:
            raise StoreError("研究档案不存在", "dossier_not_found", 404)
        return row

    def _detail(self, connection, did, *, at_revision=None):
        row = self._row(connection, did)
        result = dict(row)
        result.update(subject=json.loads(row["subject"]), archived=bool(row["archived"]))
        latest = {}
        evidence_ids, link_ids = set(), set()
        for event in connection.execute(
            "SELECT * FROM events WHERE dossier_id=? AND revision<=? ORDER BY revision",
            (did, at_revision or row["revision"]),
        ):
            payload = json.loads(event["payload"])
            if payload.get("evidence_id"):
                evidence_ids.add(payload["evidence_id"])
            if payload.get("link_id"):
                link_ids.add(payload["link_id"])
            records = (
                [payload]
                if event["kind"] == "record"
                else payload.get("records", []) if event["kind"] == "scan" else []
            )
            for value in records:
                latest[value["id"]] = {
                    **value,
                    "revision": event["revision"],
                    "created_at": event["created_at"],
                }
        result["records"] = list(latest.values())
        result["evidence"] = [
            value
            for item in connection.execute(
                "SELECT payload FROM evidence WHERE dossier_id=? ORDER BY rowid", (did,)
            )
            if not (value := json.loads(item["payload"])).get("link_only")
            and (at_revision is None or value["id"] in evidence_ids)
        ]
        result["links"] = [
            value
            for item in connection.execute(
                "SELECT payload FROM links WHERE dossier_id=? ORDER BY rowid", (did,)
            )
            if (value := json.loads(item["payload"]))
            and (at_revision is None or value["id"] in link_ids)
        ]
        result["tracking"] = {"enabled": False, "eligible": False, "reason": "manual_scan_required"}
        if at_revision is not None:
            version = connection.execute(
                "SELECT metadata FROM versions WHERE dossier_id=? AND revision=?",
                (did, at_revision),
            ).fetchone()
            if version is None:
                raise StoreError("档案历史版本缺失", "dossier_version_missing", 409)
            result.update(json.loads(version[0]))
            return result
        if connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='dossier_aux'"
        ).fetchone():
            aux = connection.execute(
                "SELECT payload FROM dossier_aux WHERE dossier_id=?", (did,)
            ).fetchone()
            if aux:
                try:
                    value = json.loads(aux[0])
                    if not isinstance(value, dict):
                        raise TypeError("invalid aux metadata")
                    for key in ("scan", "tracking"):
                        if key in value:
                            if not isinstance(value[key], dict):
                                raise ValueError("invalid aux projection")
                            result[key] = value[key]
                except (ValueError, TypeError) as exc:
                    log.error("dossier_aux_invalid", dossier_id=did)
                    raise StoreError(
                        "档案扫描或跟踪状态不可读取", "dossier_aux_invalid", 409
                    ) from exc
        return result

    def get(self, did):
        with self.connection() as connection:
            return self._detail(connection, did)

    def list(self, include_archived=False, limit=50, cursor=None):
        limit = min(max(int(limit), 1), 100)
        offset = int(cursor or 0)
        if offset < 0 or offset > 100000:
            raise StoreError("分页参数非法", "dossier_cursor_invalid", 422)
        with self.connection() as connection:
            if connection is None:
                return {"items": [], "next_cursor": None}
            rows = connection.execute(
                "SELECT * FROM dossiers WHERE (? OR archived=0) ORDER BY updated_at DESC,id LIMIT ? OFFSET ?",
                (int(include_archived), limit + 1, offset),
            ).fetchall()
            items = [
                {
                    **dict(row),
                    "subject": json.loads(row["subject"]),
                    "archived": bool(row["archived"]),
                }
                for row in rows[:limit]
            ]
            return {
                "items": items,
                "next_cursor": str(offset + limit) if len(rows) > limit else None,
            }

    def timeline(self, did, *, kind=None, state=None, limit=100, cursor=None):
        limit = min(max(int(limit), 1), 200)
        offset = int(cursor or 0)
        if offset < 0 or offset > 100000:
            raise StoreError("分页参数非法", "dossier_cursor_invalid", 422)
        with self.connection() as connection:
            self._row(connection, did)
            rows = connection.execute(
                "SELECT * FROM events WHERE dossier_id=? ORDER BY revision DESC", (did,)
            )
            items = []
            for row in rows:
                value = {**dict(row), "payload": json.loads(row["payload"])}
                if kind and value["payload"].get("kind", row["kind"]) != kind:
                    continue
                if state and value["payload"].get("state") != state:
                    continue
                items.append(value)
                if len(items) >= offset + limit + 1:
                    break
            return {
                "items": items[offset : offset + limit],
                "next_cursor": str(offset + limit) if len(items) > offset + limit else None,
            }

    def _append_event(self, connection, did, revision, kind, payload):
        connection.execute(
            "INSERT INTO events(dossier_id,revision,kind,payload,created_at) VALUES(?,?,?,?,?)",
            (did, revision, kind, canonical(payload), now()),
        )

    def mutate(self, did, request, operation, callback, *, revalidate=None):
        scope = did or "create"
        digest = hashlib.sha256(
            canonical({"operation": operation, "request": request}).encode()
        ).hexdigest()
        with admission(), retention_lock(self.root), self.connection(write=True) as connection:
            previous = connection.execute(
                "SELECT * FROM requests WHERE scope=? AND key=?",
                (scope, request["idempotency_key"]),
            ).fetchone()
            if previous:
                if previous["digest"] != digest:
                    raise StoreError(
                        "幂等键已用于其他档案请求", "dossier_idempotency_conflict", 409
                    )
                response = json.loads(previous["response"])
                if response.get("_dossier_response"):
                    response = self._detail(
                        connection, response["_dossier_response"], at_revision=response["revision"]
                    )
                if revalidate is not None:
                    revalidate(response)
                return response
            if did:
                row = self._row(connection, did)
                if row["revision"] != request["expected_revision"]:
                    raise StoreError(
                        "档案已被其他操作修订，请刷新后重试", "dossier_revision_conflict", 409
                    )
                revision = row["revision"] + 1
            else:
                did, revision = uuid4().hex, 1
                connection.execute(
                    "INSERT INTO dossiers VALUES(?,?,?,?,?,?)",
                    (did, request["title"], canonical(request["subject"]), revision, 0, now()),
                )
            response, event = callback(connection, did, revision)
            self._append_event(connection, did, revision, operation, event)
            connection.execute(
                "UPDATE dossiers SET revision=?,updated_at=? WHERE id=?", (revision, now(), did)
            )
            if response is None:
                response = self._detail(connection, did)
                # Replay rebuilds immutable record/evidence/link views; do not
                # duplicate every earlier opinion in every idempotency receipt.
                metadata = {
                    key: value
                    for key, value in response.items()
                    if key not in {"records", "evidence", "links"}
                }
                connection.execute(
                    "INSERT INTO versions VALUES(?,?,?)", (did, revision, canonical(metadata))
                )
                saved_response = {"_dossier_response": did, "revision": revision}
            else:
                saved_response = response
            connection.execute(
                "INSERT INTO requests VALUES(?,?,?,?)",
                (scope, request["idempotency_key"], digest, canonical(saved_response)),
            )
        log.info(
            "dossier_revision_committed", dossier_id=did, revision=revision, operation=operation
        )
        return response

    def backup_to(self, destination):
        """Explicit consistent SQLite snapshot. Original evidence bytes remain in their source roots."""
        from pathlib import Path

        destination = Path(destination)
        if destination.exists() or destination.is_symlink() or not destination.parent.is_dir():
            raise StoreError("备份目标必须为新的受控文件", "dossier_backup_target_invalid", 409)
        with admission(), retention_lock(self.root), self.connection() as source:
            if source is None:
                raise StoreError("尚无档案可备份", "dossier_not_found", 404)
            target = None
            try:
                descriptor = os.open(
                    destination,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    0o600,
                )
                os.close(descriptor)
                target = sqlite3.connect(destination)
                source.backup(target)
                target.close()
                target = None
                with destination.open("rb") as stream:
                    os.fsync(stream.fileno())
                    digest = hashlib.file_digest(stream, "sha256").hexdigest()
            except (OSError, sqlite3.Error) as exc:
                log.error("dossier_backup_failed", error_type=type(exc).__name__)
                raise StoreError("档案一致快照备份失败", "dossier_backup_failed", 503) from exc
            finally:
                if target is not None:
                    target.close()
        log.info("dossier_backup_created", sha256=digest)
        return {"sha256": digest, "evidence_copied": False, "format": "sqlite-metadata-v1"}

    def restore_from(self, source_path, *, expected_sha256, verify_evidence):
        """Validate metadata, all pins and originals before atomically replacing the old pointer."""
        from pathlib import Path

        source_path = Path(source_path)
        if not re.fullmatch(r"[a-f0-9]{64}", expected_sha256 or ""):
            raise StoreError("恢复摘要非法", "dossier_restore_invalid", 422)
        staging = None
        with admission(), retention_lock(self.root):
            try:
                info = source_path.lstat()
                if (
                    source_path.is_symlink()
                    or not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_size > 64 * 1024 * 1024
                ):
                    raise StoreError("恢复文件不安全", "dossier_restore_invalid", 409)
                with source_path.open("rb") as stream:
                    if hashlib.file_digest(stream, "sha256").hexdigest() != expected_sha256:
                        raise StoreError("恢复摘要不匹配", "dossier_restore_invalid", 409)
                with sqlite3.connect(source_path.as_uri() + "?mode=ro", uri=True) as source:
                    source.row_factory = sqlite3.Row
                    self._validate_database(source)
                    if (
                        source.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                        or source.execute("PRAGMA foreign_key_check").fetchone()
                    ):
                        raise StoreError("恢复数据库完整性检查失败", "dossier_restore_invalid", 409)
                    pins = source.execute(
                        "SELECT evidence_id,source_session_id,dossier_id FROM retention"
                    ).fetchall()
                    evidence = source.execute(
                        "SELECT id,dossier_id,source_session_id,payload FROM evidence"
                    ).fetchall()
                    if {
                        (item["id"], item["source_session_id"], item["dossier_id"])
                        for item in evidence
                    } != {
                        (pin["evidence_id"], pin["source_session_id"], pin["dossier_id"])
                        for pin in pins
                    }:
                        raise StoreError("恢复保全引用不完整", "dossier_restore_invalid", 409)
                    for item in evidence:
                        verify_evidence(json.loads(item["payload"]))
                    # Source identity, pins and originals were all verified
                    # above. Explicit recovery alone may replace a lost target.
                    self._safe(create=True, allow_uninitialized=True)
                    descriptor, temporary = tempfile.mkstemp(prefix=".restore-", dir=self.folder)
                    os.close(descriptor)
                    staging = Path(temporary)
                    target = sqlite3.connect(staging)
                    try:
                        source.backup(target)
                    finally:
                        target.close()
                with staging.open("rb") as stream:
                    os.fsync(stream.fileno())
                os.replace(staging, self.path)
                staging = None
                log.info(
                    "dossier_backup_restored", sha256=expected_sha256, evidence_count=len(evidence)
                )
            except (OSError, sqlite3.Error, ValueError, KeyError) as exc:
                log.error("dossier_restore_failed", error_type=type(exc).__name__)
                raise StoreError(
                    "档案恢复失败，原数据库保持不变", "dossier_restore_failed", 503
                ) from exc
            finally:
                if staging is not None:
                    staging.unlink(missing_ok=True)

    def retained_by(self, sid):
        with self.connection() as connection:
            if connection is None:
                return []
            return [
                row[0]
                for row in connection.execute(
                    "SELECT DISTINCT dossier_id FROM retention WHERE source_session_id=?", (sid,)
                )
            ]

    def assert_deletable(self, sid):
        retained = self.retained_by(sid)
        if retained:
            log.warning("dossier_session_delete_denied", session_id=sid, dossier_ids=retained)
            raise StoreError(
                "会话被研究档案保留，不能永久删除：" + ", ".join(retained),
                "dossier_evidence_retained",
                409,
            )
