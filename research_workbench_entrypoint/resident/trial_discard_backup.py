"""Offline, bounded evidence and backup for an explicitly approved trial retirement.

This module does not retire sessions, clear provider state, or control services.
The caller must hold the resident maintenance exclusion fence and prove idle.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path
from typing import TypedDict
from urllib.parse import quote
from uuid import UUID, uuid4

from .model_provider_upgrade import MAX_ASSET_INDEX_BYTES

log = logging.getLogger(__name__)
DB_LIMIT = 64 * 1024 * 1024
RECORD_LIMIT = 1024 * 1024
MAX_ACCOUNT_ROOTS = 64
MAX_TOTAL_BYTES = 512 * 1024 * 1024
FREE_RESERVE_BYTES = 2 * 1024 * 1024 * 1024


class _BackupFile(TypedDict):
    sha256: str
    size: int
    mode: int


class _BackupManifest(TypedDict):
    version: int
    source_seal: str
    files: dict[str, _BackupFile]


class TrialBackupBlocked(RuntimeError):
    """Safe stable reason; private bytes and paths never enter messages."""


def _directory(path: Path) -> os.stat_result:
    info = path.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
        raise TrialBackupBlocked("trial_directory_unsafe")
    return info


def _ancestors(path: Path) -> None:
    if not path.is_absolute() or ".." in path.parts:
        raise TrialBackupBlocked("trial_path_unsafe")
    for parent in reversed(path.parents):
        info = parent.lstat()
        if not stat.S_ISDIR(info.st_mode):
            raise TrialBackupBlocked("trial_path_unsafe")


def _read(path: Path, limit: int) -> tuple[bytes, dict]:
    _ancestors(path)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid != os.getuid()
                or not 0 < before.st_size <= limit
            ):
                raise TrialBackupBlocked("trial_file_unsafe_or_oversize")
            raw = stream.read(limit + 1)
            after = os.fstat(stream.fileno())
        current = path.lstat()
        original = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        if (
            original != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            or original != (current.st_dev, current.st_ino, current.st_size, current.st_mtime_ns)
            or len(raw) != before.st_size
        ):
            raise TrialBackupBlocked("trial_file_changed")
        return raw, {
            "dev": before.st_dev,
            "ino": before.st_ino,
            "size": before.st_size,
            "mode": stat.S_IMODE(before.st_mode),
            "mtime_ns": before.st_mtime_ns,
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
    except OSError as exc:
        raise TrialBackupBlocked("trial_file_unreadable") from exc


def _json(path: Path, limit: int) -> tuple[dict, bytes, dict]:
    raw, identity = _read(path, limit)
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError
        return value, raw, identity
    except (UnicodeError, ValueError, TypeError) as exc:
        raise TrialBackupBlocked("trial_json_invalid") from exc


def _accounts(db: Path) -> tuple[set[str], dict]:
    raw, identity = _read(db, DB_LIMIT)
    if not raw.startswith(b"SQLite format 3\0") or raw[18:20] != b"\x01\x01":
        raise TrialBackupBlocked("trial_account_db_unstable")
    for suffix in ("-journal", "-wal", "-shm"):
        sidecar = db.with_name(db.name + suffix)
        if sidecar.exists() or sidecar.is_symlink():
            raise TrialBackupBlocked("trial_account_db_unstable")
    try:
        connection = sqlite3.connect(
            f"file:{quote(str(db))}?mode=ro&immutable=1", uri=True, timeout=0
        )
        try:
            if connection.execute("PRAGMA quick_check").fetchone() != ("ok",):
                raise TrialBackupBlocked("trial_account_db_invalid")
            rows = connection.execute("SELECT id FROM accounts").fetchall()
        finally:
            connection.close()
        ids = {row[0] for row in rows}
        if len(ids) != len(rows) or any(str(UUID(value)) != value for value in ids):
            raise ValueError
    except (sqlite3.Error, ValueError, TypeError) as exc:
        raise TrialBackupBlocked("trial_account_mapping_unknown") from exc
    if _read(db, DB_LIMIT)[1] != identity:
        raise TrialBackupBlocked("trial_account_db_changed")
    return ids, identity


def _catalog_state(root: Path) -> tuple[dict, int]:
    folder = root / "report-workflows"
    if not folder.exists() and not folder.is_symlink():
        return {"status": "missing", "directory": "missing"}, 0
    folder_info = _directory(folder)
    directory_identity = [folder_info.st_dev, folder_info.st_ino]
    path = folder / "catalog.json"
    if not path.exists() and not path.is_symlink():
        return {"status": "missing", "directory_identity": directory_identity}, 0
    catalog, _, identity = _json(path, MAX_ASSET_INDEX_BYTES)
    workflows, runs = catalog.get("workflows"), catalog.get("runs")
    if not isinstance(workflows, dict) or not isinstance(runs, dict):
        raise TrialBackupBlocked("trial_catalog_invalid")
    return {
        "status": "present",
        "directory_identity": directory_identity,
        "identity": identity,
        "workflow_count": len(workflows),
        "run_count": len(runs),
    }, identity["size"]


def preview(home: Path) -> dict:
    """Return only identity, counts, statuses and hashes; never session/model content."""
    try:
        home = Path(home).absolute()
        _directory(home)
        server = home / "server"
        users = server / "users"
        _directory(server)
        _directory(users)
        binding, _, binding_id = _json(server / "resident.json", RECORD_LIMIT)
        primary = binding["binding"]["primary_user_id"]
        account_ids, db_id = _accounts(server / "accounts.sqlite3")
        if len(account_ids) > MAX_ACCOUNT_ROOTS:
            raise TrialBackupBlocked("trial_account_budget_exceeded")
        if str(UUID(primary)) != primary or primary not in account_ids:
            raise TrialBackupBlocked("trial_primary_mapping_unknown")
        folders = list(users.iterdir())
        if any(
            not folder.is_dir() or folder.is_symlink() or folder.name not in account_ids - {primary}
            for folder in folders
        ):
            raise TrialBackupBlocked("trial_account_mapping_unknown")
        if len({folder.name for folder in folders}) != len(folders):
            raise TrialBackupBlocked("trial_account_mapping_unknown")
        roots = [(primary, home / "research-web", "primary")]
        roots.extend(
            (account_id, users / account_id / "research-web", "account")
            for account_id in sorted(account_ids - {primary})
        )
        result = []
        total_bytes = binding_id["size"] + db_id["size"]
        for account_id, root, kind in roots:
            if not root.exists() and not root.is_symlink():
                if kind == "primary":
                    raise TrialBackupBlocked("trial_primary_root_missing")
                result.append(
                    {
                        "account_id": account_id,
                        "kind": kind,
                        "index": "missing",
                        "catalog": {"status": "missing", "directory": "missing"},
                    }
                )
                continue
            root_id = _directory(root)
            catalog, catalog_bytes = _catalog_state(root)
            total_bytes += catalog_bytes
            if total_bytes > MAX_TOTAL_BYTES:
                raise TrialBackupBlocked("trial_total_budget_exceeded")
            path = root / "index.json"
            if not path.exists() and not path.is_symlink():
                result.append(
                    {
                        "account_id": account_id,
                        "kind": kind,
                        "index": "missing",
                        "root_identity": [root_id.st_dev, root_id.st_ino],
                        "catalog": catalog,
                    }
                )
                continue
            index, _, identity = _json(path, MAX_ASSET_INDEX_BYTES)
            total_bytes += identity["size"]
            if total_bytes > MAX_TOTAL_BYTES:
                raise TrialBackupBlocked("trial_total_budget_exceeded")
            sessions = index.get("sessions")
            if not isinstance(sessions, dict) or any(
                not isinstance(sid, str) or not isinstance(row, dict)
                for sid, row in sessions.items()
            ):
                raise TrialBackupBlocked("trial_sessions_invalid")
            models = {
                key: value
                for key, value in index.items()
                if key.startswith(("model", "compatible_model"))
            }
            allowed_statuses = {
                "queued",
                "running",
                "completed",
                "failed",
                "cancelled",
                "canceled",
                "interrupted",
                "deleted",
                "missing",
            }
            statuses = {
                sid: (
                    row.get("status", "missing")
                    if row.get("status", "missing") in allowed_statuses
                    else "unknown"
                )
                for sid, row in sessions.items()
            }
            result.append(
                {
                    "account_id": account_id,
                    "kind": kind,
                    "index": "present",
                    "root_identity": [root_id.st_dev, root_id.st_ino],
                    "index_identity": identity,
                    "session_count": len(sessions),
                    "sessions": statuses,
                    "catalog": catalog,
                    "model_settings_sha256": hashlib.sha256(
                        json.dumps(
                            models, sort_keys=True, ensure_ascii=False, allow_nan=False
                        ).encode()
                    ).hexdigest(),
                }
            )
        seal_payload = {"binding": binding_id, "accounts": db_id, "roots": result}
        seal = hashlib.sha256(
            json.dumps(seal_payload, sort_keys=True, ensure_ascii=True).encode()
        ).hexdigest()
        log.info("trial_discard_preview_verified root_count=%s", len(result))
        return {
            "seal": seal,
            "binding_identity": binding_id,
            "accounts_identity": db_id,
            "total_bytes": total_bytes,
            "roots": result,
        }
    except TrialBackupBlocked:
        log.warning("trial_discard_preview_blocked")
        raise
    except (OSError, KeyError, ValueError, TypeError) as exc:
        log.warning("trial_discard_preview_invalid error_type=%s", type(exc).__name__)
        raise TrialBackupBlocked("trial_scope_unknown") from exc


def _identity(info: os.stat_result) -> tuple[int, int]:
    return info.st_dev, info.st_ino


@contextmanager
def _anchored_parent(path: Path):
    """Hold every ancestor and reject a changed path before issuing a receipt."""
    _ancestors(path / "placeholder")
    expected = _identity(_directory(path))
    opened = []
    try:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        opened.append((Path("/"), fd, _identity(os.fstat(fd))))
        current = Path("/")
        for part in path.parts[1:]:
            fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            current = current / part
            opened.append((current, fd, _identity(os.fstat(fd))))
        if opened[-1][2] != expected:
            raise TrialBackupBlocked("trial_backup_parent_changed")
        yield opened[-1][1], opened
        for item, _fd, original in opened:
            if _identity(item.lstat()) != original:
                raise TrialBackupBlocked("trial_backup_parent_changed")
    finally:
        for _, descriptor, _ in reversed(opened):
            os.close(descriptor)


def _open_child(parent_fd: int, name: str, *, create: bool) -> int:
    if not name or name in {".", ".."} or "/" in name:
        raise TrialBackupBlocked("trial_backup_name_invalid")
    if create:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
        os.fsync(parent_fd)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    info = os.fstat(fd)
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        os.close(fd)
        raise TrialBackupBlocked("trial_backup_directory_unsafe")
    return fd


def _write_new(parent_fd: int, name: str, raw: bytes, mode: int) -> None:
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
        mode,
        dir_fd=parent_fd,
    )
    try:
        view = memoryview(raw)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise TrialBackupBlocked("trial_backup_write_incomplete")
            view = view[written:]
        os.fchmod(fd, mode)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.fsync(parent_fd)


def _read_at(parent_fd: int, name: str, limit: int) -> tuple[bytes, int]:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
            raise TrialBackupBlocked("trial_backup_file_invalid")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(limit + 1)
        if len(raw) != info.st_size or _identity(
            os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        ) != _identity(info):
            raise TrialBackupBlocked("trial_backup_file_changed")
        return raw, stat.S_IMODE(info.st_mode)
    finally:
        os.close(fd)


def backup(home: Path, backup_parent: Path, expected_seal: str) -> dict:
    """Save exact owned files and prove durable byte/mode restore before receipt."""
    before = preview(home)
    if before["seal"] != expected_seal:
        raise TrialBackupBlocked("trial_preview_drift")
    home, backup_parent = Path(home).absolute(), Path(backup_parent).absolute()
    if backup_parent == home or home in backup_parent.parents or backup_parent in home.parents:
        raise TrialBackupBlocked("trial_backup_scope_unsafe")
    point_created = False
    try:
        with _anchored_parent(backup_parent) as (parent_fd, _chain):
            parent_info = os.fstat(parent_fd)
            if parent_info.st_dev != home.stat().st_dev or parent_info.st_mode & 0o077:
                raise TrialBackupBlocked("trial_backup_parent_unsafe")
            required = FREE_RESERVE_BYTES + 2 * before["total_bytes"]
            filesystem = os.fstatvfs(parent_fd)
            if filesystem.f_bavail * filesystem.f_frsize < required:
                raise TrialBackupBlocked("trial_backup_space_low")
            point_name = uuid4().hex
            point = backup_parent / point_name
            point_fd = _open_child(parent_fd, point_name, create=True)
            point_created = True
            directories = {"": point_fd}
            try:
                files = {"server/accounts.sqlite3": DB_LIMIT, "server/resident.json": RECORD_LIMIT}
                for row in before["roots"]:
                    prefix = (
                        "research-web"
                        if row["kind"] == "primary"
                        else f"server/users/{row['account_id']}/research-web"
                    )
                    if row["index"] == "present":
                        files[f"{prefix}/index.json"] = MAX_ASSET_INDEX_BYTES
                    if row["catalog"]["status"] == "present":
                        files[f"{prefix}/report-workflows/catalog.json"] = MAX_ASSET_INDEX_BYTES
                manifest: _BackupManifest = {
                    "version": 1,
                    "source_seal": expected_seal,
                    "files": {},
                }
                copied_bytes = 0
                for relative, limit in files.items():
                    raw, identity = _read(home / relative, limit)
                    copied_bytes += len(raw)
                    if copied_bytes > MAX_TOTAL_BYTES:
                        raise TrialBackupBlocked("trial_total_budget_exceeded")
                    parent_key = ""
                    for part in Path(relative).parts[:-1]:
                        key = f"{parent_key}/{part}".lstrip("/")
                        if key not in directories:
                            directories[key] = _open_child(
                                directories[parent_key], part, create=True
                            )
                        parent_key = key
                    directory_fd = directories[parent_key]
                    name = Path(relative).name
                    _write_new(directory_fd, name, raw, identity["mode"])
                    copied, copied_mode = _read_at(directory_fd, name, limit)
                    if copied != raw or copied_mode != identity["mode"]:
                        raise TrialBackupBlocked("trial_backup_copy_invalid")
                    restored_name = ".restore-" + uuid4().hex
                    _write_new(point_fd, restored_name, copied, identity["mode"])
                    restored, restored_mode = _read_at(point_fd, restored_name, limit)
                    if restored != raw or restored_mode != identity["mode"]:
                        raise TrialBackupBlocked("trial_restore_unverified")
                    os.unlink(restored_name, dir_fd=point_fd)
                    os.fsync(point_fd)
                    manifest["files"][relative] = {
                        "sha256": identity["sha256"],
                        "size": identity["size"],
                        "mode": identity["mode"],
                    }
                if preview(home)["seal"] != expected_seal:
                    raise TrialBackupBlocked("trial_preview_drift")
                encoded = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
                sealed = hashlib.sha256(encoded).hexdigest()
                _write_new(point_fd, "manifest.json", encoded, 0o600)
                manifest_read, manifest_mode = _read_at(point_fd, "manifest.json", RECORD_LIMIT)
                if manifest_read != encoded or manifest_mode != 0o600:
                    raise TrialBackupBlocked("trial_manifest_unverified")
                for relative, record in manifest["files"].items():
                    key = str(Path(relative).parent)
                    key = "" if key == "." else key
                    copied, mode = _read_at(directories[key], Path(relative).name, files[relative])
                    if (
                        hashlib.sha256(copied).hexdigest() != record["sha256"]
                        or mode != record["mode"]
                    ):
                        raise TrialBackupBlocked("trial_backup_final_read_invalid")
                for key, fd in directories.items():
                    if not key:
                        continue
                    parent_key = str(Path(key).parent)
                    parent_key = "" if parent_key == "." else parent_key
                    actual = os.stat(
                        Path(key).name,
                        dir_fd=directories[parent_key],
                        follow_symlinks=False,
                    )
                    if not stat.S_ISDIR(actual.st_mode) or _identity(actual) != _identity(
                        os.fstat(fd)
                    ):
                        raise TrialBackupBlocked("trial_backup_directory_changed")
                for fd in directories.values():
                    os.fsync(fd)
                os.fsync(parent_fd)
                if _identity(
                    os.stat(point_name, dir_fd=parent_fd, follow_symlinks=False)
                ) != _identity(os.fstat(point_fd)):
                    raise TrialBackupBlocked("trial_backup_point_changed")
                log.info("trial_discard_backup_verified file_count=%s", len(files))
                return {
                    "status": "restore_verified",
                    "backup": str(point),
                    "manifest_sha256": sealed,
                    "source_seal": expected_seal,
                    "file_count": len(files),
                }
            finally:
                for fd in reversed(list(directories.values())):
                    os.close(fd)
    except (OSError, TrialBackupBlocked) as exc:
        log.warning("trial_discard_backup_blocked error_type=%s", type(exc).__name__)
        if not point_created and isinstance(exc, TrialBackupBlocked):
            raise
        raise TrialBackupBlocked("trial_backup_incomplete") from exc
