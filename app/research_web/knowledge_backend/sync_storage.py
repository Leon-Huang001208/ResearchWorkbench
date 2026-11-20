"""Private mutable directory index, separate from immutable report manifests."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import threading
from contextlib import contextmanager, nullcontext
from pathlib import Path

from core.observability import get_logger

from ..datahub.security import directory, read_file, write_new
from ..dossiers.lock import retention_lock
from ..store import StoreError
from .storage import digest, fail

log = get_logger(__name__)
FOLDER = "knowledge-sync"
DATABASE = "state.sqlite3"
MAX_DATABASE_BYTES = 256 * 1024 * 1024
# Leave headroom for the largest snapshot's rollback journal and bounded control updates.
SQLITE_RESERVE_BYTES = 17 * 1024 * 1024


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
                    yield db
                    if write:
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

    def rows(self, *, current=False, path=None):
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
            if path is not None:
                conditions.append("v.path=?")
                params.append(path)
            if conditions:
                sql += " WHERE " + " AND ".join(conditions)
            return [dict(row) for row in db.execute(sql + " ORDER BY v.path,v.version", params)]

    def observe(self, observations, present):
        with self.connection(write=True) as db:
            page_size = db.execute("PRAGMA page_size").fetchone()[0]
            extra, added = 0, set()
            for path, value in observations.items():
                if (
                    value["sha256"] not in added
                    and db.execute(
                        "SELECT 1 FROM snapshots WHERE sha256=?", (value["sha256"],)
                    ).fetchone()
                    is None
                ):
                    extra += ((len(value["content"]) + page_size - 1) // page_size) * page_size
                    added.add(value["sha256"])
                previous = db.execute(
                    "SELECT v.sha256,f.tombstone FROM files f JOIN versions v "
                    "ON v.path=f.path AND v.version=f.desired_version WHERE f.path=?",
                    (path,),
                ).fetchone()
                if previous is None or previous[0] != value["sha256"] or previous[1]:
                    extra += 4 * page_size + 2 * len(path.encode("utf-8"))
            if self.path.stat().st_size + extra + SQLITE_RESERVE_BYTES > MAX_DATABASE_BYTES:
                fail("knowledge_sync_storage_budget", 413)
            for path, value in observations.items():
                previous = db.execute(
                    "SELECT v.*,f.tombstone FROM files f JOIN versions v "
                    "ON v.path=f.path AND v.version=f.desired_version WHERE f.path=?",
                    (path,),
                ).fetchone()
                if previous and previous["sha256"] == value["sha256"] and not previous["tombstone"]:
                    db.execute("UPDATE files SET stable=MIN(stable+1,2) WHERE path=?", (path,))
                    continue
                version = previous["version"] + 1 if previous else 1
                db.execute(
                    "INSERT OR IGNORE INTO snapshots VALUES(?,?)",
                    (value["sha256"], value["content"]),
                )
                db.execute(
                    "INSERT INTO versions VALUES(?,?,?,?,?,NULL,'observing',NULL)",
                    (path, version, value["sha256"], value["md5"], len(value["content"])),
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

    def snapshot(self, sha256):
        with self.connection() as db:
            row = (
                db.execute("SELECT content FROM snapshots WHERE sha256=?", (sha256,)).fetchone()
                if db
                else None
            )
            if row is None or digest(row[0]) != sha256:
                fail("knowledge_sync_snapshot_unavailable", 404)
            return bytes(row[0])

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
                raw = read_file(fd, DATABASE, private=True, limit=MAX_DATABASE_BYTES)
            return {
                "schema_version": 1,
                "owner": self.owner,
                "files": {FOLDER + "/" + DATABASE: digest(raw)},
            }
