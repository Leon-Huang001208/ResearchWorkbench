"""Cross-process deployment fence; disabled unless explicitly enabled by the resident job.

The updater takes EX before the lifecycle lock. Requests and research admission
take SH until the native acknowledgement. The journal also fences after a crash.
No scheduler, credentials, or research payloads are stored here.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import os
import stat
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger(__name__)


class MaintenanceBusy(RuntimeError):
    """The resident transaction has fenced new mutations."""


def private_root(root: Path) -> None:
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise RuntimeError("resident_directory_unsafe")
    if root.resolve() != root.absolute():
        raise RuntimeError("resident_directory_symlink")


@contextmanager
def file_lock(root: Path, name: str, *, exclusive: bool):
    import fcntl

    private_root(root)
    fd = os.open(root / name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
        ):
            raise RuntimeError("resident_lock_unsafe")
        try:
            fcntl.flock(fd, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MaintenanceBusy("resident_busy") from exc
        yield
    finally:
        os.close(fd)


@contextmanager
def admission(*, root: Path | None = None):
    setting = os.environ.get("RESEARCH_RESIDENT_HOME")
    if root is None and not setting:
        yield
        return
    if root is None:
        assert setting is not None
        root = Path(setting)
    with file_lock(root, "admission.lock", exclusive=False):
        if (root / "transaction.json").exists():
            raise MaintenanceBusy("resident_recovery_pending")
        yield


def research_admission(function):
    """Also covers scheduled/Hot/model-test callers that bypass HTTP middleware."""

    @functools.wraps(function)
    async def guarded(*args, **kwargs):
        while True:
            try:
                with admission():
                    return await function(*args, **kwargs)
            except MaintenanceBusy:
                # Keep accepted scheduled work pending, rather than mark it failed.
                log.debug("resident_research_admission_waiting")
                await asyncio.sleep(0.25)

    return guarded


def diagnostic(home: Path) -> dict:
    """Read-only, path-free Doctor projection; never poll GitHub or launch services."""
    import json

    path = home / "resident/state.json"
    if not path.exists():
        return {"status": "not_installed", "boot_boundary": "user_login"}
    try:
        info = path.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_mode & 0o077
            or info.st_size > 8192
        ):
            raise ValueError("unsafe_state")
        value = json.loads(path.read_text())
        status = value.get("status")
        if status not in {
            "installed",
            "ready",
            "waiting",
            "deferred",
            "deployed",
            "rolled_back",
            "blocked",
            "disabled",
            "retry_requested",
        }:
            raise ValueError("invalid_state")
        return {
            "status": status,
            "boot_boundary": "user_login",
            "checked_at": value.get("checked_at"),
        }
    except (OSError, ValueError, AttributeError):
        log.warning("resident_diagnostic_unavailable")
        return {"status": "unknown", "boot_boundary": "user_login"}
