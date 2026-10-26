"""One nonblocking cross-process fence for archive pins and destructive session work."""

import asyncio
import contextvars
import os
import stat
import threading
from contextlib import contextmanager

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)
_held = contextvars.ContextVar("dossier_retention_fences", default=())


def _owner():
    try:
        task = asyncio.current_task()
    except RuntimeError:
        task = None
    return threading.get_ident(), id(task)


@contextmanager
def retention_lock(root, *, create=True):
    """Hold across native deletion awaits; a contender fails closed instead of blocking."""
    identity = str(root), _owner()
    if identity in _held.get():
        yield
        return
    descriptor = None
    token = None
    locked = False
    try:
        before = root.lstat()
        if root.is_symlink() or not stat.S_ISDIR(before.st_mode):
            raise OSError("unsafe root")
        descriptor = os.open(
            root / ".dossier-retention.lock",
            os.O_RDWR | (os.O_CREAT if create else 0) | getattr(os, "O_NOFOLLOW", 0),
            0o600,
        )
        info = os.fstat(descriptor)
        after = root.lstat()
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino)
        ):
            raise OSError("unsafe retention lock")
        if os.name == "nt":
            import msvcrt

            if info.st_size == 0:
                os.write(descriptor, b"0")
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        locked = True
        token = _held.set((*_held.get(), identity))
        yield
    except OSError as exc:
        log.warning("dossier_retention_lock_unavailable", error_type=type(exc).__name__)
        raise StoreError(
            "档案保全操作繁忙或不可用，请稍后重试", "dossier_retention_busy", 409
        ) from exc
    finally:
        if token is not None:
            _held.reset(token)
        if descriptor is not None:
            if locked:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
