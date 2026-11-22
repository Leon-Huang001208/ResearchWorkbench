"""Explicit stale managed-lock retirement, never an automatic delivery fallback."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import stat
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from .delivery_transfer import (
    MaintenanceParser,
    TransferBlocked,
    _common,
    _identity,
    _no_links,
    _read,
    _remote,
)

log = logging.getLogger(__name__)


def alive(pid):
    if sys.platform == "win32":
        raise TransferBlocked("lock_host_unsupported")
    if type(pid) is not int or pid <= 0:
        raise TransferBlocked("lock_owner_invalid")
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        raise TransferBlocked("lock_owner_unknown") from None


def no_native_locks(common):
    names = [
        "index.lock",
        "HEAD.lock",
        "ORIG_HEAD.lock",
        "FETCH_HEAD.lock",
        "MERGE_HEAD.lock",
        "AUTO_MERGE.lock",
        "config.lock",
        "config.worktree.lock",
        "packed-refs.lock",
        "shallow.lock",
        "gc.pid",
    ]
    native = [common / n for n in names if (common / n).exists()]
    for base in ["refs", "worktrees", "objects"]:
        if (common / base).is_dir():
            native.extend((common / base).rglob("*.lock"))
    if native:
        raise TransferBlocked("lock_native_writer_present")


@contextmanager
def recovery_fence(common):
    folder = common / "leon-engineering/git-safety"
    _no_links(folder)
    fence = folder / "repository-recovery.lock"
    try:
        fd = os.open(fence, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    except FileExistsError as exc:
        raise TransferBlocked("lock_recovery_busy") from exc
    info = os.fstat(fd)
    nonce = uuid4().hex
    try:
        with os.fdopen(fd, "w") as stream:
            json.dump({"pid": os.getpid(), "nonce": nonce}, stream)
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        current = fence.lstat()
        if (
            fence.is_symlink()
            or [current.st_dev, current.st_ino] != [info.st_dev, info.st_ino]
            or json.loads(_read(fence)).get("nonce") != nonce
        ):
            raise TransferBlocked("lock_recovery_fence_changed")
        fence.unlink()


def inspected(project):
    project = Path(project).absolute()
    _remote(project)
    common = _common(project)
    _identity(common)
    lock = common / "leon-engineering/git-safety/repository.lock"
    raw = _read(lock)
    info = lock.stat()
    owner = json.loads(raw)
    if not isinstance(owner.get("nonce"), str) or not 16 <= len(owner["nonce"]) <= 64:
        raise TransferBlocked("lock_owner_invalid")
    if alive(owner.get("pid")):
        raise TransferBlocked("lock_owner_alive")
    try:
        r = subprocess.run(
            [
                "/usr/bin/git",
                "--no-optional-locks",
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "-C",
                str(project),
                "fsck",
                "--full",
                "--no-reflogs",
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        raise TransferBlocked("lock_integrity_READ_TIMEOUT") from None
    if r.returncode:
        raise TransferBlocked("lock_integrity_failed")
    no_native_locks(common)
    if (
        alive(owner["pid"])
        or _read(lock) != raw
        or [lock.stat().st_dev, lock.stat().st_ino] != [info.st_dev, info.st_ino]
    ):
        raise TransferBlocked("lock_changed")
    body = {
        "schema_version": 1,
        "project": str(project),
        "common": str(common),
        "common_identity": _identity(common),
        "lock_identity": [info.st_dev, info.st_ino],
        "lock_sha256": hashlib.sha256(raw).hexdigest(),
        "pid": owner["pid"],
        "nonce": owner["nonce"],
        "mode": stat.S_IMODE(info.st_mode),
    }
    body["seal"] = hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest()
    return body


def retire(plan, backup_root):
    with recovery_fence(Path(plan["common"])):
        return _retire_locked(plan, backup_root)


def _retire_locked(plan, backup_root):
    current = inspected(plan["project"])
    if current != plan:
        raise TransferBlocked("lock_preview_changed")
    common = Path(plan["common"])
    lock = common / "leon-engineering/git-safety/repository.lock"
    raw = _read(lock)
    backup_root = Path(backup_root).absolute()
    _no_links(backup_root)
    backup_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    if backup_root.stat().st_uid != os.getuid() or backup_root.stat().st_mode & 0o077:
        raise TransferBlocked("lock_backup_unsafe")
    point = backup_root / uuid4().hex
    point.mkdir(mode=0o700)
    backup = point / "repository.lock"
    with backup.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    backup.chmod(plan["mode"])
    # Perform a real restore/readback outside .git before touching the lock.
    with tempfile.TemporaryDirectory(prefix="restore-", dir=point) as temp:
        restored = Path(temp) / "repository.lock"
        restored.write_bytes(backup.read_bytes())
        restored.chmod(plan["mode"])
        if restored.read_bytes() != raw or stat.S_IMODE(restored.stat().st_mode) != plan["mode"]:
            raise TransferBlocked("lock_restore_unverified")
    record = point / "manifest.json"
    record.write_text(json.dumps({"status": "restore_verified", "plan": plan}))
    record.chmod(0o600)
    with record.open("rb") as f:
        os.fsync(f.fileno())
    no_native_locks(common)
    if (
        alive(plan["pid"])
        or _read(lock) != raw
        or [lock.stat().st_dev, lock.stat().st_ino] != plan["lock_identity"]
    ):
        raise TransferBlocked("lock_changed")
    archive_dir = common / "leon-engineering/git-safety/retired-locks"
    _no_links(archive_dir)
    archive_dir.mkdir(mode=0o700, exist_ok=True)
    archived = archive_dir / (plan["lock_sha256"] + "." + uuid4().hex + ".json")
    os.rename(lock, archived)
    if (
        archived.read_bytes() != raw
        or [archived.stat().st_dev, archived.stat().st_ino] != plan["lock_identity"]
    ):
        raise TransferBlocked("lock_retirement_identity_changed")
    fd = os.open(archive_dir.parent, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    record.write_text(json.dumps({"status": "retired", "plan": plan, "archive": str(archived)}))
    record.chmod(0o600)
    log.info("resident_stale_repository_lock_retired")
    return {
        "status": "retired",
        "backup": str(point),
        "archive": str(archived),
        "lock_sha256": plan["lock_sha256"],
    }


def main():
    parser = MaintenanceParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("operation", choices=["preview", "apply"])
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--expected-seal")
    parser.add_argument("--backup-root", type=Path)
    args = parser.parse_args()
    try:
        plan = inspected(args.project)
        if args.operation == "preview":
            print(json.dumps(plan))
            return 0
        if args.expected_seal != plan["seal"] or args.backup_root is None:
            raise TransferBlocked("lock_explicit_preview_required")
        print(json.dumps(retire(plan, args.backup_root)))
        return 0
    except (TransferBlocked, OSError, ValueError) as exc:
        log.warning(
            "resident_stale_repository_lock_blocked", extra={"error_type": type(exc).__name__}
        )
        print(
            json.dumps(
                {
                    "status": "blocked",
                    "code": (
                        str(exc) if isinstance(exc, TransferBlocked) else "lock_recovery_io_failed"
                    ),
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
