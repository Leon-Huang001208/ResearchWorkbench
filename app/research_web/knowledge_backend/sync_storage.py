"""Private mutable directory index, separate from immutable report manifests."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sqlite3
import stat
import threading
from contextlib import contextmanager, nullcontext
from pathlib import Path

from core.observability import get_logger

from ..datahub.security import directory, write_new
from ..dossiers.lock import retention_lock
from ..store import StoreError
from .client import ORIGINAL_LIMIT
from .storage import SHA, digest, fail

log = get_logger(__name__)
FOLDER = "knowledge-sync"
DATABASE = "state.sqlite3"
MIN_INTERNAL_FREE_BYTES = 10 * 1024**3
MIN_EXTERNAL_FREE_BYTES = 2 * 1024**3
CONTROL_PEAK_BYTES = 64 * 1024


class SyncStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.path = self.root / FOLDER / DATABASE
        self.owner = digest(str(self.root).encode())
        self.lock = threading.RLock()
        # A copied account store must fail before a query can observe its state.
        with self.connection() as db:
            if db is not None:
                db.execute("SELECT 1 FROM versions LIMIT 1")

    def _safe(self):
        info = self.path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (os.name != "nt" and (info.st_uid != os.getuid() or info.st_mode & 0o077))
        ):
            fail("knowledge_sync_storage_unsafe", 503)
        return info

    def _admit(self, growth=0):
        floor = (
            MIN_INTERNAL_FREE_BYTES
            if self.root.stat().st_dev == Path("/").stat().st_dev
            else MIN_EXTERNAL_FREE_BYTES
        )
        # Include rollback-journal/control growth; no catalog or history byte limit.
        if shutil.disk_usage(self.root).free - growth - CONTROL_PEAK_BYTES < floor:
            fail("knowledge_sync_disk_space_insufficient", 507)

    def _prune_unpinned(self, db):
        eligible = (
            "sha256 NOT IN (SELECT sha256 FROM snapshot_pins) "
            "AND NOT EXISTS(SELECT 1 FROM versions v JOIN files f ON f.path=v.path "
            "WHERE v.sha256=snapshots.sha256 AND v.version=f.desired_version AND f.tombstone=0 "
            "AND v.state IN ('uploading','uncertain','pending'))"
        )
        reclaiming = db.execute(
            "SELECT COALESCE(SUM(length(content)),0) FROM snapshots WHERE " + eligible
        ).fetchone()[0]
        if reclaiming:
            self._admit(reclaiming)
            db.execute("DELETE FROM snapshots WHERE " + eligible)

    @contextmanager
    def connection(self, *, write=False):
        db = None
        fence = (
            retention_lock(self.root, create=write)
            if write or (self.root / ".dossier-retention.lock").exists()
            else nullcontext()
        )
        with self.lock, fence:
            try:
                if write:
                    self._admit()
                with directory(self.root, private=True) as fd:
                    exists = FOLDER in os.listdir(fd)
                if not exists and not write:
                    yield None
                    return
                with directory(self.root, (FOLDER,), create=write, private=True) as fd:
                    created = DATABASE not in os.listdir(fd)
                    if created:
                        if not write:
                            fail("knowledge_sync_storage_uninitialized", 503)
                        write_new(fd, DATABASE, b"")
                    before = self._safe()
                    mode = "rw" if write else "ro"
                    db = sqlite3.connect(self.path.as_uri() + "?mode=" + mode, uri=True, timeout=5)
                    after = self._safe()
                    if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                        fail("knowledge_sync_storage_changed", 503)
                    db.row_factory = sqlite3.Row
                    db.execute("PRAGMA foreign_keys=ON")
                    db.execute("PRAGMA synchronous=FULL")
                    if created:
                        db.executescript(
                            "CREATE TABLE identity(owner TEXT NOT NULL);"
                            "CREATE TABLE settings(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);"
                            "CREATE TABLE snapshots(sha256 TEXT PRIMARY KEY,content BLOB NOT NULL);"
                            "CREATE TABLE files(path TEXT PRIMARY KEY,desired_version INTEGER NOT NULL,"
                            "current_version INTEGER,stable INTEGER NOT NULL,tombstone INTEGER NOT NULL DEFAULT 0);"
                            "CREATE TABLE versions(path TEXT NOT NULL,version INTEGER NOT NULL,"
                            "sha256 TEXT NOT NULL,md5 TEXT NOT NULL,size INTEGER NOT NULL,"
                            "document_id TEXT,state TEXT NOT NULL,error TEXT,PRIMARY KEY(path,version));"
                            "PRAGMA user_version=1;"
                        )
                        db.execute("INSERT INTO identity VALUES(?)", (self.owner,))
                        db.commit()
                    if db.execute("PRAGMA user_version").fetchone()[0] != 1 or [
                        row[0] for row in db.execute("SELECT owner FROM identity")
                    ] != [self.owner]:
                        fail("knowledge_sync_owner_invalid", 503)
                    if write:
                        db.execute("BEGIN IMMEDIATE")
                        had_pins = db.execute(
                            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshot_pins'"
                        ).fetchone()
                        db.execute(
                            "CREATE TABLE IF NOT EXISTS snapshot_pins(sha256 TEXT PRIMARY KEY REFERENCES snapshots(sha256))"
                        )
                        if not created and not had_pins:
                            # A2 receipts predate explicit pins; preserve every existing original.
                            self._admit(
                                db.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0] * 1024
                            )
                            db.execute("INSERT INTO snapshot_pins SELECT sha256 FROM snapshots")
                    yield db
                    if write:
                        self._prune_unpinned(db)
                        db.commit()
            except StoreError:
                if db is not None:
                    db.rollback()
                raise
            except (sqlite3.Error, OSError, ValueError) as exc:
                if db is not None:
                    db.rollback()
                log.error("knowledge_sync_storage_failed", error_type=type(exc).__name__)
                fail("knowledge_sync_storage_unavailable", 503)
            finally:
                if db is not None:
                    db.close()

    def config(self):
        with self.connection() as db:
            row = db.execute("SELECT payload FROM settings WHERE id=1").fetchone() if db else None
            return json.loads(row[0]) if row else None

    def save_config(self, value):
        with self.connection(write=True) as db:
            db.execute(
                "INSERT INTO settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                (json.dumps(value, ensure_ascii=False, allow_nan=False),),
            )

    def rows(self, *, current=False, path=None, desired=False, sha256=None):
        with self.connection() as db:
            if db is None:
                return []
            sql = (
                "SELECT v.*,f.tombstone,f.stable,f.current_version,f.desired_version "
                "FROM versions v JOIN files f ON f.path=v.path"
            )
            conditions, params = [], []
            if current:
                conditions.extend(["f.tombstone=0", "v.version=f.current_version"])
            if desired:
                conditions.append("v.version=f.desired_version")
            if path is not None:
                conditions.append("v.path=?")
                params.append(path)
            if sha256 is not None:
                conditions.append("v.sha256=?")
                params.append(sha256)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            return [dict(row) for row in db.execute(sql + " ORDER BY v.path,v.version", params)]

    def observe(self, observations, present):
        with self.connection(write=True) as db:
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            extra = 0
            for path, value in observations.items():
                previous = db.execute(
                    "SELECT v.sha256,f.tombstone FROM files f JOIN versions v "
                    "ON v.path=f.path AND v.version=f.desired_version WHERE f.path=?",
                    (path,),
                ).fetchone()
                if previous is None or previous[0] != value["sha256"] or previous[1]:
                    extra += 4 * page_size + 4 * len(path.encode("utf-8"))
            self._admit(extra * 2)
            for path, value in observations.items():
                previous = db.execute(
                    "SELECT v.*,f.tombstone FROM files f JOIN versions v "
                    "ON v.path=f.path AND v.version=f.desired_version WHERE f.path=?",
                    (path,),
                ).fetchone()
                if previous and previous["sha256"] == value["sha256"] and not previous["tombstone"]:
                    db.execute("UPDATE files SET stable=2 WHERE path=? AND stable<2", (path,))
                    continue
                version = previous["version"] + 1 if previous else 1
                db.execute(
                    "INSERT INTO versions VALUES(?,?,?,?,?,NULL,'observing',NULL)",
                    (path, version, value["sha256"], value["md5"], value["size"]),
                )
                db.execute(
                    "INSERT INTO files VALUES(?,?,NULL,1,0) ON CONFLICT(path) DO UPDATE SET "
                    "desired_version=excluded.desired_version,stable=1,tombstone=0",
                    (path, version),
                )
            # Called only after an entire root walk succeeds; unsupported present files stay visible.
            for row in db.execute("SELECT path FROM files WHERE tombstone=0").fetchall():
                if row[0] not in present:
                    db.execute(
                        "UPDATE files SET tombstone=1,current_version=NULL WHERE path=?", row
                    )

    def update(self, row, *, state, document_id=None, error=None, promote=False):
        with self.connection(write=True) as db:
            desired = db.execute(
                "SELECT desired_version,tombstone FROM files WHERE path=?", (row["path"],)
            ).fetchone()
            if desired is None or desired[0] != row["version"] or desired[1]:
                return False
            db.execute(
                "UPDATE versions SET state=?,document_id=COALESCE(?,document_id),error=? "
                "WHERE path=? AND version=? AND sha256=?",
                (state, document_id, error, row["path"], row["version"], row["sha256"]),
            )
            if promote:
                db.execute(
                    "UPDATE files SET current_version=? WHERE path=? AND desired_version=? AND tombstone=0",
                    (row["version"], row["path"], row["version"]),
                )
            return True

    @staticmethod
    def _checked_raw(sha256, raw):
        if (
            not isinstance(sha256, str)
            or not SHA.fullmatch(sha256)
            or not isinstance(raw, bytes)
            or not 0 < len(raw) <= ORIGINAL_LIMIT
            or digest(raw) != sha256
        ):
            fail("knowledge_sync_snapshot_invalid", 422)

    def stage(self, row, raw):
        self._checked_raw(row["sha256"], raw)
        with self.connection(write=True) as db:
            desired = db.execute(
                "SELECT desired_version,tombstone FROM files WHERE path=?", (row["path"],)
            ).fetchone()
            if desired is None or desired[0] != row["version"] or desired[1]:
                return False
            if len(raw) != row["size"] or hashlib.md5(raw).hexdigest() != row["md5"]:
                fail("knowledge_sync_snapshot_invalid", 422)
            self._admit(2 * len(raw))
            db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?)", (row["sha256"], raw))
            db.execute(
                "UPDATE versions SET state='uploading',error=NULL WHERE path=? AND version=?",
                (row["path"], row["version"]),
            )
            return True

    def pin_snapshot(self, sha256, raw):
        self._checked_raw(sha256, raw)
        with self.connection() as db:
            pins = (
                db is not None
                and db.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshot_pins'"
                ).fetchone()
            )
            if (
                pins
                and db.execute("SELECT 1 FROM snapshot_pins WHERE sha256=?", (sha256,)).fetchone()
            ):
                if self._raw(db, sha256) != raw:
                    fail("knowledge_sync_snapshot_invalid", 422)
                return
        with self.connection(write=True) as db:
            self._admit(2 * len(raw))
            db.execute("INSERT OR IGNORE INTO snapshots VALUES(?,?)", (sha256, raw))
            if self._raw(db, sha256) != raw:
                fail("knowledge_sync_snapshot_invalid", 422)
            db.execute("INSERT OR IGNORE INTO snapshot_pins VALUES(?)", (sha256,))

    @staticmethod
    def _raw(db, sha256):
        length = (
            db.execute("SELECT length(content) FROM snapshots WHERE sha256=?", (sha256,)).fetchone()
            if db
            else None
        )
        if length is None:
            return None
        if not 0 < length[0] <= ORIGINAL_LIMIT:
            fail("knowledge_sync_snapshot_invalid", 422)
        raw = bytes(
            db.execute("SELECT content FROM snapshots WHERE sha256=?", (sha256,)).fetchone()[0]
        )
        if digest(raw) != sha256:
            fail("knowledge_sync_snapshot_invalid", 422)
        return raw

    def staged_snapshot(self, sha256):
        with self.connection() as db:
            return self._raw(db, sha256)

    def snapshot(self, sha256):
        raw = self.staged_snapshot(sha256)
        if raw is None:
            fail("knowledge_sync_snapshot_unavailable", 404)
        return raw

    def preservation(self):
        fence = (
            retention_lock(self.root, create=False)
            if (self.root / ".dossier-retention.lock").exists()
            else nullcontext()
        )
        with self.lock, fence:
            with self.connection() as db:
                if db is None:
                    return None
                if db.execute("PRAGMA quick_check").fetchall()[0][0] != "ok":
                    fail("knowledge_sync_storage_integrity", 503)
            with directory(self.root, (FOLDER,), private=True) as fd:
                if set(os.listdir(fd)) != {DATABASE}:
                    fail("knowledge_sync_recovery_required", 503)
                before = self._safe()
                handle = os.open(DATABASE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                try:
                    opened = os.fstat(handle)
                    if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                        fail("knowledge_sync_storage_changed", 503)
                    sha, length = hashlib.sha256(), 0
                    while chunk := os.read(handle, 1024 * 1024):
                        sha.update(chunk)
                        length += len(chunk)
                    after = os.fstat(handle)
                    current = self._safe()

                    def identity(info):
                        return (
                            info.st_dev,
                            info.st_ino,
                            info.st_mode,
                            info.st_nlink,
                            info.st_size,
                            info.st_mtime_ns,
                            info.st_ctime_ns,
                        )

                    if (
                        length != before.st_size
                        or identity(before) != identity(after)
                        or identity(before) != identity(current)
                        or set(os.listdir(fd)) != {DATABASE}
                    ):
                        fail("knowledge_sync_storage_changed", 503)
                finally:
                    os.close(handle)
            return {
                "schema_version": 1,
                "owner": self.owner,
                "files": {FOLDER + "/" + DATABASE: sha.hexdigest()},
            }
