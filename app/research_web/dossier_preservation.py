"""Read-only, fenced preservation identities for personal dossier metadata."""

from __future__ import annotations

import hashlib
import os
import stat
from pathlib import Path

from core.observability import get_logger

log = get_logger(__name__)
MAX_METADATA_BYTES = 64 * 1024 * 1024


def snapshot_dossiers(root: Path) -> dict | None:
    """No directories/DB are initialized; a busy or damaged archive fails closed."""
    folder = root / "dossiers"
    marker = root / ".dossiers-initialized"
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
        with retention_lock(root):
            store = DossierStore(root)
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
            return {"schema_version": 1, "files": files}
    except Exception as exc:
        log.error("dossier_preservation_failed", error_type=type(exc).__name__)
        raise RuntimeError("dossier_preservation_failed") from exc
