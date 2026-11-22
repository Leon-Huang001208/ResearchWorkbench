"""Fail-closed empty-pool bootstrap for gateways predating deployment admission.

No native owner is forged. An exclusively published directory occupies its birth
slot, making the native O_EXCL owner creation fail before any child can spawn.
The SQLite lock covers every account, including disabled accounts and old tokens.
"""

from __future__ import annotations

import ctypes
import errno
import json
import logging
import os
import sqlite3
import stat
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

from .admission import private_root
from .controller import atomic, sync_directory
from .evidence import UpdateBlocked, read_json

log = logging.getLogger(__name__)


class FenceBlocked(UpdateBlocked):
    """Stable codes only; account identities and content are never logged."""


def exclusive_rename(source: Path, destination: Path) -> None:
    """Atomic no-replace publication; never fall back to overwriting rename."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        function = libc.renamex_np
        function.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        args = (os.fsencode(source), os.fsencode(destination), 0x00000004)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        function = libc.renameat2
        function.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        args = (-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise FenceBlocked("exclusive_publish_unavailable")
    function.restype = ctypes.c_int
    if function(*args):
        code = ctypes.get_errno()
        if code in {errno.EEXIST, errno.ENOTEMPTY}:
            raise FenceBlocked("private_pool_not_empty")
        raise FenceBlocked("exclusive_publish_failed")


def identity(path: Path) -> list[int]:
    info = path.lstat()
    return [info.st_dev, info.st_ino]


class BirthFence:
    """Hold until the old gateway has exited and its launchd job is removed.

    This is a birth fence, NOT a request drain. The caller must also fence the
    primary and wait for graceful uvicorn shutdown, with no forced timeout kill.
    """

    def __init__(
        self, root: Path, primary: str, *, resume: bool = False, transaction: str | None = None
    ):
        self.root, self.primary = root, primary
        self.db = None
        self.journal = root / "run/birth-fence.json"
        self.resume, self.retain = resume, False
        self.owns_journal = False
        self.transaction = transaction or str(uuid4())

    def __enter__(self):
        try:
            private_root(self.root)
            private_root(self.root / "run")
            private_root(self.root / "users")
            if not self.resume and (self.journal.exists() or self.journal.is_symlink()):
                raise FenceBlocked("birth_fence_recovery_required")
            path = self.root / "accounts.sqlite3"
            info = path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise FenceBlocked("database_identity_unknown")
            db_identity = identity(path)
            # Do not open a potentially hot journal and trigger SQLite recovery.
            for suffix in ("-wal", "-shm", "-journal"):
                sidecar = self.root / (path.name + suffix)
                if sidecar.exists() or sidecar.is_symlink():
                    raise FenceBlocked("database_sidecar_unknown")
            self.db = sqlite3.connect(f"file:{quote(str(path))}?mode=rw", uri=True, timeout=0)
            self.db.execute("BEGIN EXCLUSIVE")
            if identity(path) != db_identity:
                raise FenceBlocked("database_identity_changed")
            if self.db.execute("PRAGMA journal_mode").fetchone()[0] != "delete":
                raise FenceBlocked("database_mode_unknown")
            if self.resume:
                self.recover(self.root, expected=self.transaction)
            users = [row[0] for row in self.db.execute("SELECT id FROM accounts")]
            if not users or len(users) > 128 or self.primary not in users:
                raise FenceBlocked("account_set_unknown")
            if any(str(UUID(uid)) != uid for uid in users):
                raise FenceBlocked("account_set_unknown")
            if any(child.name not in users for child in (self.root / "users").iterdir()):
                raise FenceBlocked("unknown_user_directory")
            value = {"version": 1, "transaction": self.transaction, "slots": []}
            claim = self.root / "run" / ("birth-claim-" + str(uuid4()))
            descriptor = os.open(claim, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            try:
                with os.fdopen(descriptor, "w") as stream:
                    json.dump(value, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                exclusive_rename(claim, self.journal)
                self.owns_journal = True
                sync_directory(self.journal.parent)
            finally:
                claim.unlink(missing_ok=True)
            for uid in users:
                folder = self.root / "users" / uid
                if uid == self.primary and not folder.exists():
                    continue
                private_root(folder)
                private_root(folder / "state")
                owner = folder / "state/owner.json"
                if owner.exists() or owner.is_symlink():
                    raise FenceBlocked("private_pool_not_empty")
                for control in (folder / "state").iterdir():
                    info = control.lstat()
                    if (
                        control.name not in {"build-lock.json", "overlay.yml"}
                        or not stat.S_ISREG(info.st_mode)
                        or info.st_nlink != 1
                        or info.st_uid != os.getuid()
                        or info.st_mode & 0o077
                    ):
                        raise FenceBlocked("private_control_unknown")
                # Persist inode and token BEFORE publication. An interrupted rename
                # can be recovered from either location without guessing ownership.
                stage = self.root / "run" / ("birth-slot-" + str(uuid4()))
                stage.mkdir(mode=0o700)
                marker = stage / "reservation"
                descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(descriptor, "w") as stream:
                    stream.write(value["transaction"])
                    stream.flush()
                    os.fsync(stream.fileno())
                sync_directory(stage)
                value["slots"].append(
                    {"user": uid, "stage": stage.name, "identity": identity(stage)}
                )
                atomic(self.journal, value)
                exclusive_rename(stage, owner)
                sync_directory(owner.parent)
                sync_directory(stage.parent)
            log.info("gateway_birth_fence_acquired count=%d", len(value["slots"]))
            return self
        except Exception:
            self.__exit__(*sys.exc_info())
            raise

    def release_database(self):
        """Only after old gateway process/threads have fully retired."""
        if self.db is not None:
            self.db.rollback()  # This transaction never writes business rows.
            self.db.close()
            self.db = None

    def __exit__(self, *_):
        try:
            if self.owns_journal and not self.retain:
                self.recover(self.root, expected=self.transaction)
        finally:
            self.release_database()

    @staticmethod
    def recover(root: Path, *, expected: str | None = None):
        journal = root / "run/birth-fence.json"
        if not journal.exists():
            return
        value = read_json(journal)
        if expected is not None and value.get("transaction") != expected:
            raise FenceBlocked("reservation_transaction_changed")
        if value.get("version") != 1 or str(UUID(value["transaction"])) != value["transaction"]:
            raise FenceBlocked("reservation_journal_invalid")
        for slot in value["slots"]:
            if str(UUID(slot["user"])) != slot["user"]:
                raise FenceBlocked("reservation_journal_invalid")
            if not slot["stage"].startswith("birth-slot-") or "/" in slot["stage"]:
                raise FenceBlocked("reservation_journal_invalid")
            stage = root / "run" / slot["stage"]
            owner = root / "users" / slot["user"] / "state/owner.json"
            unpublished = stage.exists()
            for path in (stage, owner):
                if not path.exists() and not path.is_symlink():
                    continue
                # A native winner at owner is protected when our stage still exists.
                if path == owner and unpublished:
                    continue
                if (
                    path.resolve() != path.absolute()
                    or not stat.S_ISDIR(path.lstat().st_mode)
                    or identity(path) != slot["identity"]
                ):
                    raise FenceBlocked("reservation_changed")
                names = sorted(p.name for p in path.iterdir())
                if names != ["reservation"] and not (slot.get("releasing") and names == []):
                    raise FenceBlocked("reservation_changed")
                if names and (
                    (path / "reservation").is_symlink()
                    or (path / "reservation").read_text() != value["transaction"]
                ):
                    raise FenceBlocked("reservation_changed")
                if path == owner:
                    exclusive_rename(owner, stage)
                    sync_directory(owner.parent)
                    sync_directory(stage.parent)
                    path = stage
                slot["releasing"] = True
                atomic(journal, value)
                (path / "reservation").unlink(missing_ok=True)
                path.rmdir()
                sync_directory(path.parent)
        journal.unlink()
        sync_directory(journal.parent)
        log.info("gateway_birth_fence_released")
