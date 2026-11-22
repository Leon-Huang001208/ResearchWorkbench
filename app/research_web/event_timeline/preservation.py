"""Bounded read-only inventory and explicit complete event archive backup/restore."""

import hashlib
import json
import os
import sqlite3
import stat
from pathlib import Path
from uuid import uuid4

from core.observability import get_logger
from research_workbench_entrypoint.resident.admission import admission

from ..datahub.security import directory, json_bytes, read_file, sync_directory, write_new
from ..dossiers.lock import retention_lock
from ..store import StoreError
from .storage import canonical, fail

log = get_logger(__name__)
MAX_TOTAL = 64 * 1024 * 1024


def _database(raw, owner):
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(raw)
        if (
            connection.execute("PRAGMA quick_check").fetchone()[0] != "ok"
            or connection.execute("PRAGMA user_version").fetchone()[0] != 1
            or [row[0] for row in connection.execute("SELECT owner FROM identity")] != [owner]
        ):
            fail("event_backup_integrity_invalid", 503)
        return connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    except sqlite3.Error as exc:
        log.warning("event_backup_database_invalid", error_type=type(exc).__name__)
        fail("event_backup_integrity_invalid", 503)
    finally:
        connection.close()


def _capture(store):
    if not store._state():
        return {}, 0
    files, total = {}, 0
    for current, dirs, names in os.walk(store.folder, followlinks=False):
        for name in dirs:
            path = Path(current) / name
            if not stat.S_ISDIR(path.lstat().st_mode) or path.is_symlink():
                fail("event_backup_path_unsafe", 503)
        for name in names:
            path = Path(current) / name
            relative = path.relative_to(store.folder)
            with directory(
                store.root, ("event_timeline", *relative.parts[:-1]), private=True
            ) as fd:
                raw = read_file(fd, name, private=True, limit=MAX_TOTAL)
            total += len(raw)
            if len(files) >= 5000 or total > MAX_TOTAL:
                fail("event_backup_capacity", 503)
            files[str(relative)] = raw
    count = _database(files.get("metadata.sqlite3", b""), store.owner_binding)
    return files, count


def _authority(raw, owner):
    """The restored state must retain every current decision and idempotency receipt."""
    _database(raw, owner)
    connection = sqlite3.connect(":memory:")
    try:
        connection.deserialize(raw)
        tables = {
            row[0]
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        return {
            name: (
                {canonical(list(row)) for row in connection.execute(f"SELECT * FROM {name}")}
                if name in tables
                else set()
            )
            for name in ("records", "requests", "claims", "range_claims")
        }
    finally:
        connection.close()


def export_manifest(store, *, create_lock=False):
    """Never creates locks, SQLite sidecars, directories or missing markers."""
    if not store._state():
        return {
            "status": "not_initialized",
            "owner_binding": store.owner_binding,
            "files": [],
            "record_count": 0,
        }
    with retention_lock(store.root, create=create_lock):
        files, count = _capture(store)
        rows = [
            {"path": name, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
            for name, raw in sorted(files.items())
        ]
        value = {
            "status": "initialized",
            "schema": "event-backup-v1",
            "owner_binding": store.owner_binding,
            "marker_sha256": hashlib.sha256(store.marker_bytes).hexdigest(),
            "files": rows,
            "record_count": count,
            "qualification_reconciliation_required": store.qualification_status()["required"],
        }
        return {**value, "sha256": hashlib.sha256(canonical(value).encode()).hexdigest()}


def backup_to(store, destination):
    destination = Path(destination).absolute()
    protected = store.root.resolve()
    try:
        resolved = destination.resolve(strict=False)
    except (OSError, RuntimeError):
        fail("event_backup_target_invalid")
    overlaps = (
        resolved == protected
        or resolved.is_relative_to(protected)
        or protected.is_relative_to(resolved)
    )
    if (
        overlaps
        or destination.exists()
        or destination.is_symlink()
        or destination.parent.resolve() != destination.parent
    ):
        fail("event_backup_target_invalid")
    with admission(), retention_lock(store.root):
        files, count = _capture(store)
        if not files:
            fail("event_record_not_found", 404)
        manifest = export_manifest(store)
        destination.mkdir(mode=0o700)
        for relative, raw in files.items():
            parts = Path(relative).parts
            with directory(destination, parts[:-1], create=True, private=True) as fd:
                write_new(fd, parts[-1], raw)
                sync_directory(fd)
        with directory(destination) as fd:
            write_new(fd, "backup-manifest.json", json_bytes(manifest))
            sync_directory(fd)
        log.info("event_backup_created", sha256=manifest["sha256"], record_count=count)
        return manifest


def restore_from(store, source, *, expected_sha256):
    source = Path(source).absolute()
    with directory(source) as fd:
        manifest = json.loads(
            read_file(fd, "backup-manifest.json", private=True, limit=1024 * 1024)
        )
    core = {key: value for key, value in manifest.items() if key != "sha256"}
    if (
        hashlib.sha256(canonical(core).encode()).hexdigest() != expected_sha256
        or manifest.get("sha256") != expected_sha256
        or manifest.get("owner_binding") != store.owner_binding
        or manifest.get("schema") != "event-backup-v1"
        or len(manifest.get("files", [])) > 5000
    ):
        fail("event_backup_identity_invalid")
    files, total = {}, 0
    for row in manifest["files"]:
        parts = Path(row["path"]).parts
        if (
            not parts
            or Path(row["path"]).is_absolute()
            or any(part in {".", ".."} for part in parts)
            or row["path"] in files
        ):
            fail("event_backup_path_unsafe")
        with directory(source, parts[:-1], private=True) as fd:
            raw = read_file(fd, parts[-1], private=True, limit=MAX_TOTAL)
        total += len(raw)
        if (
            total > MAX_TOTAL
            or len(raw) != row["size"]
            or hashlib.sha256(raw).hexdigest() != row["sha256"]
        ):
            fail("event_backup_integrity_invalid")
        files[row["path"]] = raw
    _database(files.get("metadata.sqlite3", b""), store.owner_binding)
    with admission(), retention_lock(store.root):
        with directory(store.root) as fd:
            if (store.marker.exists() or store.marker.is_symlink()) and read_file(
                fd, store.marker.name, private=True, limit=512
            ) != store.marker_bytes:
                fail("event_owner_invalid")
        current_unknown = False
        try:
            if store._state():
                with directory(store.root, ("event_timeline",), private=True) as fd:
                    current_raw = read_file(fd, "metadata.sqlite3", private=True, limit=MAX_TOTAL)
                current = _authority(current_raw, store.owner_binding)
                restored = _authority(files["metadata.sqlite3"], store.owner_binding)
                if any(not values.issubset(restored[name]) for name, values in current.items()):
                    fail("event_restore_history_rollback")
            else:
                current_unknown = True
        except StoreError as exc:
            if exc.code not in {"event_storage_uninitialized", "event_backup_integrity_invalid"}:
                raise
            current_unknown = True
        if current_unknown or manifest.get("qualification_reconciliation_required") is True:
            store.mark_reconciliation_required()
        staging = "event-timeline-restore-" + uuid4().hex
        previous = None
        for relative, raw in files.items():
            parts = Path(relative).parts
            with directory(store.root, (staging, *parts[:-1]), create=True, private=True) as fd:
                write_new(fd, parts[-1], raw)
        if store.folder.exists() or store.folder.is_symlink():
            if store.folder.is_symlink() or not stat.S_ISDIR(store.folder.lstat().st_mode):
                fail("event_storage_unsafe")
            previous = "event-timeline-previous-" + uuid4().hex
            os.rename(store.folder, store.root / previous)
        installed = False
        try:
            os.rename(store.root / staging, store.folder)
            installed = True
            with directory(store.root) as fd:
                if not store.marker.exists():
                    write_new(fd, store.marker.name, store.marker_bytes)
                elif (
                    read_file(fd, store.marker.name, private=True, limit=512) != store.marker_bytes
                ):
                    fail("event_owner_invalid")
                sync_directory(fd)
            result = export_manifest(store)
        except Exception as exc:
            log.error("event_restore_failed", error_type=type(exc).__name__)
            if installed:
                os.rename(store.folder, store.root / staging)
            if previous is not None:
                os.rename(store.root / previous, store.folder)
            raise
        log.info("event_backup_restored", sha256=result["sha256"])
        return {**result, "previous_directory": previous}
