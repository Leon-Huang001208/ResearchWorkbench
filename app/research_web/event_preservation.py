"""Read-only identities for account-local event, trial and score evidence."""

import hashlib
import sqlite3
import stat
from contextlib import closing
from pathlib import Path

from core.observability import get_logger

from .datahub.security import directory, read_file
from .dossiers.lock import retention_lock
from .event_timeline.storage import RecordStore
from .store import StoreError

log = get_logger(__name__)
MAX_FILE = 64 * 1024 * 1024
MAX_TOTAL = 512 * 1024 * 1024


def snapshot_events(root: Path, *, create_lock: bool = True) -> dict | None:
    """Never initialize metadata; inspect SQLite in memory to avoid recovery writes."""
    root = Path(root)
    records = RecordStore(root)
    if not any(
        path.exists() or path.is_symlink()
        for path in (records.marker, records.folder, records.qualification_marker)
    ):
        return None
    try:
        with retention_lock(root, create=create_lock):
            records.qualification_status()
            if root.resolve() != root.absolute() or not records._state():
                raise ValueError("event_preservation_uninitialized")
            with directory(records.folder, private=True) as fd:
                database = read_file(fd, records.path.name, private=True, limit=MAX_FILE)
            if database[:16] != b"SQLite format 3\x00" or database[18:20] != b"\x01\x01":
                raise ValueError("event_preservation_sqlite_format")
            with closing(sqlite3.connect(":memory:")) as connection:
                connection.deserialize(database)
                connection.execute("PRAGMA query_only=ON")
                if (
                    connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]
                    or connection.execute("PRAGMA foreign_key_check").fetchone()
                    or connection.execute("SELECT owner FROM identity").fetchall()
                    != [(records.owner_binding,)]
                ):
                    raise ValueError("event_preservation_integrity")
            files = {}
            total = 0
            protected = [records.marker]
            if records.qualification_marker.exists() or records.qualification_marker.is_symlink():
                protected.append(records.qualification_marker)
            for path in [*protected, *sorted(records.folder.rglob("*"))]:
                info = path.lstat()
                if stat.S_ISDIR(info.st_mode):
                    if path.is_symlink():
                        raise ValueError("event_preservation_symlink")
                    continue
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > MAX_FILE:
                    raise ValueError("event_preservation_unsafe_file")
                with directory(path.parent, private=True) as fd:
                    raw = read_file(fd, path.name, private=True, limit=MAX_FILE)
                after = path.lstat()
                fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
                if any(getattr(info, field) != getattr(after, field) for field in fields):
                    raise ValueError("event_preservation_changed")
                total += len(raw)
                if total > MAX_TOTAL:
                    raise ValueError("event_preservation_budget")
                files[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
            if files.get("event_timeline/metadata.sqlite3") != hashlib.sha256(database).hexdigest():
                raise ValueError("event_preservation_changed")
            return {"schema_version": 1, "files": files}
    except (OSError, ValueError, sqlite3.Error, RuntimeError, StoreError) as exc:
        log.error("event_preservation_failed", error_type=type(exc).__name__)
        raise RuntimeError("event_preservation_failed") from exc
