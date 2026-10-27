"""Read-only, fenced preservation identities for personal dossier metadata."""

from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from core.observability import get_logger

log = get_logger(__name__)
MAX_METADATA_BYTES = 64 * 1024 * 1024


def _strict_integrity(store) -> None:
    """Validate bounded rollback bytes in memory; never open disk with SQLite.

    Even SQLite mode=ro may create WAL/SHM files. WAL and recovery sidecars are
    not accepted or ignored: strict inspection cannot certify those formats.
    """
    if not store._safe(create=False):
        raise ValueError("dossier_preservation_database_missing")

    def no_sidecars():
        if any(
            (store.folder / (store.path.name + suffix)).exists()
            or (store.folder / (store.path.name + suffix)).is_symlink()
            for suffix in ("-wal", "-shm", "-journal")
        ):
            raise ValueError("dossier_preservation_sqlite_sidecar_unverified")

    no_sidecars()
    descriptor = os.open(
        store.path,
        os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
    )
    with os.fdopen(descriptor, "rb") as stream:
        before = os.fstat(stream.fileno())
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or not 0 < before.st_size <= MAX_METADATA_BYTES
        ):
            raise ValueError("dossier_preservation_file_unsafe")
        raw = stream.read(MAX_METADATA_BYTES + 1)
        after = os.fstat(stream.fileno())
    current = store.path.lstat()
    fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
    if len(raw) != before.st_size or any(
        getattr(before, key) != getattr(after, key) or getattr(before, key) != getattr(current, key)
        for key in fields
    ):
        raise ValueError("dossier_preservation_file_changed")
    if raw[:16] != b"SQLite format 3\x00" or raw[18:20] != b"\x01\x01":
        raise ValueError("dossier_preservation_sqlite_format_unverified")
    no_sidecars()
    with closing(sqlite3.connect(":memory:")) as connection:
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.deserialize(raw)
        connection.execute("PRAGMA query_only=ON")
        store._validate_database(connection)
        if (
            connection.execute("PRAGMA quick_check").fetchall()[0][0] != "ok"
            or connection.execute("PRAGMA foreign_key_check").fetchone()
        ):
            raise ValueError("dossier_preservation_integrity_failed")
    no_sidecars()


def snapshot_dossiers(root: Path, *, create_lock: bool = True) -> dict | None:
    """No directories/DB are initialized; strict observers cannot create a lock.

    Existing deployment callers retain create_lock=True. Read-only maintenance
    inspection passes False through to retention_lock's no-O_CREAT open.
    """
    folder = root / "dossiers"
    marker = root / ".dossiers-initialized"
    has_dossiers = folder.exists() or folder.is_symlink() or marker.exists() or marker.is_symlink()
    from .dossiers.lock import retention_lock
    from .research_web_sources import snapshot_capture_proofs
    from .scenario_source_selection import snapshot_selection_receipts

    if not has_dossiers:
        # No Dossier database is initialized for source-proof-only accounts.
        try:
            proof_folder = root / ".control/source-captures"
            selection_folder = root / ".control/source-selections"
            if not any(
                path.exists() or path.is_symlink() for path in (proof_folder, selection_folder)
            ):
                files = snapshot_capture_proofs(root)
                return {"schema_version": 1, "files": files} if files else None
            with retention_lock(root, create=create_lock):
                files = snapshot_capture_proofs(root)
                files.update(snapshot_selection_receipts(root))
                return {"schema_version": 1, "files": files} if files else None
        except Exception as exc:
            log.error("dossier_preservation_failed", error_type=type(exc).__name__)
            raise RuntimeError("dossier_preservation_failed") from exc
    if (
        not folder.exists()
        and not folder.is_symlink()
        and not marker.exists()
        and not marker.is_symlink()
    ):
        return None
    try:
        from .dossiers.lock import retention_lock
        from .dossiers.storage import DossierStore

        if root.resolve() != root.absolute() or folder.is_symlink() or not folder.is_dir():
            raise ValueError("dossier_preservation_path_unsafe")
        with retention_lock(root, create=create_lock):
            store = DossierStore(root)
            if not create_lock:
                _strict_integrity(store)
            else:
                with store.connection() as connection:
                    if connection is None:
                        raise ValueError("dossier_preservation_database_missing")
                    if (
                        connection.execute("PRAGMA quick_check").fetchall()[0][0] != "ok"
                        or connection.execute("PRAGMA foreign_key_check").fetchone()
                    ):
                        raise ValueError("dossier_preservation_integrity_failed")
            files = {}
            for path in [marker, *sorted(folder.rglob("*"))]:
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    continue
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_size > MAX_METADATA_BYTES
                ):
                    raise ValueError("dossier_preservation_file_unsafe")
                descriptor = os.open(
                    path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                )
                with os.fdopen(descriptor, "rb") as stream:
                    opened = os.fstat(stream.fileno())
                    if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
                        info.st_dev,
                        info.st_ino,
                    ):
                        raise ValueError("dossier_preservation_file_changed")
                    digest = hashlib.sha256()
                    total = 0
                    for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                        total += len(chunk)
                        if total > MAX_METADATA_BYTES:
                            raise ValueError("dossier_preservation_budget_exceeded")
                        digest.update(chunk)
                    after = os.fstat(stream.fileno())
                current = path.lstat()
                if (after.st_size, after.st_mtime_ns, after.st_ino, after.st_dev) != (
                    info.st_size,
                    info.st_mtime_ns,
                    info.st_ino,
                    info.st_dev,
                ) or (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
                    raise ValueError("dossier_preservation_file_changed")
                files[path.relative_to(root).as_posix()] = digest.hexdigest()
            files.update(snapshot_capture_proofs(root))
            files.update(snapshot_selection_receipts(root))
            return {"schema_version": 1, "files": files}
    except Exception as exc:
        log.error("dossier_preservation_failed", error_type=type(exc).__name__)
        raise RuntimeError("dossier_preservation_failed") from exc
