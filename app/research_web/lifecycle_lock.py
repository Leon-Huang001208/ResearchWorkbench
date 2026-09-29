"""Exclusive, ownership-checked lock for Research Web lifecycle mutations."""

from __future__ import annotations

import json
import math
import os
import re
import stat
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Self
from uuid import uuid4

from core.observability import get_logger

log = get_logger(__name__)

_OWNER_NAME = "owner.json"
_OWNER_LIMIT_BYTES = 4096
_TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


class LifecycleLockError(RuntimeError):
    """Safe lifecycle-lock failure with a stable machine-readable code."""

    def __init__(self, message: str, *, code: str) -> None:
        safe_message = message if code in message else f"{code}: {message}"
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message


class LifecycleLock:
    """Serialize lifecycle mutations using an atomic private directory lock."""

    def __init__(
        self,
        path: Path,
        pid_exists: Callable[[int], bool],
        pid: int | None = None,
    ) -> None:
        self.path = Path(path)
        self.pid_exists = pid_exists
        self.pid = os.getpid() if pid is None else pid
        if type(self.pid) is not int or self.pid <= 1:
            raise LifecycleLockError("lifecycle lock owner is invalid", code="lifecycle_busy")
        self.token = uuid4().hex
        self._directory_identity: tuple[int, int] | None = None
        self._entered = False

    @staticmethod
    def _is_reparse(identity: os.stat_result) -> bool:
        return bool(getattr(identity, "st_file_attributes", 0) & _REPARSE_FLAG)

    @classmethod
    def _safe_directory_identity(
        cls,
        path: Path,
        *,
        require_private_mode: bool = True,
    ) -> tuple[int, int]:
        identity = path.lstat()
        if (
            path.is_symlink()
            or cls._is_reparse(identity)
            or not stat.S_ISDIR(identity.st_mode)
            or (
                os.name != "nt" and require_private_mode and stat.S_IMODE(identity.st_mode) != 0o700
            )
        ):
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        return identity.st_dev, identity.st_ino

    def _prepare_parent(self) -> None:
        parent = self.path.parent
        try:
            missing: list[Path] = []
            cursor = parent
            while not cursor.exists():
                missing.append(cursor)
                cursor = cursor.parent
            for directory in reversed(missing):
                directory.mkdir(mode=0o700)
                if os.name != "nt":
                    os.chmod(directory, 0o700)
            self._safe_directory_identity(parent, require_private_mode=False)
            if os.name != "nt":
                os.chmod(parent, 0o700)
            self._safe_directory_identity(parent)
        except LifecycleLockError:
            raise
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    @classmethod
    def _read_owner(cls, directory: Path) -> tuple[dict[str, object], tuple[int, int, int]]:
        cls._safe_directory_identity(directory)
        owner = directory / _OWNER_NAME
        handle: int | None = None
        try:
            with os.scandir(directory) as entries:
                names = []
                for entry in entries:
                    names.append(entry.name)
                    if len(names) > 1:
                        raise ValueError("unexpected lock content")
            if names != [_OWNER_NAME]:
                raise ValueError("unexpected lock content")
            before = owner.lstat()
            if (
                owner.is_symlink()
                or cls._is_reparse(before)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > _OWNER_LIMIT_BYTES
                or (os.name != "nt" and stat.S_IMODE(before.st_mode) != 0o600)
            ):
                raise ValueError("unsafe owner")
            flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
            handle = os.open(owner, flags)
            opened = os.fstat(handle)
            raw = os.read(handle, _OWNER_LIMIT_BYTES + 1)
            after = owner.lstat()
            identities = {
                (item.st_dev, item.st_ino, item.st_size) for item in (before, opened, after)
            }
            if len(identities) != 1 or len(raw) > _OWNER_LIMIT_BYTES:
                raise ValueError("owner changed")
            value = json.loads(raw.decode("utf-8"))
        except (
            OSError,
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            RecursionError,
        ) as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc
        finally:
            if handle is not None:
                os.close(handle)
        valid = (
            type(value) is dict
            and set(value) == {"schema_version", "pid", "token", "started_at"}
            and type(value.get("schema_version")) is int
            and value["schema_version"] == 1
            and type(value.get("pid")) is int
            and value["pid"] > 1
            and type(value.get("token")) is str
            and _TOKEN_PATTERN.fullmatch(value["token"]) is not None
            and type(value.get("started_at")) in {int, float}
            and 0 <= value["started_at"] <= 253_402_300_799
            and math.isfinite(value["started_at"])
        )
        if not valid:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        return value, (after.st_dev, after.st_ino, after.st_size)

    def _write_owner(self) -> None:
        payload = {
            "schema_version": 1,
            "pid": self.pid,
            "token": self.token,
            "started_at": time.time(),
        }
        name: str | None = None
        try:
            fd, name = tempfile.mkstemp(prefix="owner-", dir=self.path)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=True, separators=(",", ":"))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(name, 0o600)
            os.replace(name, self.path / _OWNER_NAME)
            directory_handle = os.open(self.path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_handle)
            finally:
                os.close(directory_handle)
        except OSError as exc:
            if name is not None:
                try:
                    Path(name).unlink(missing_ok=True)
                except OSError:
                    log.warning("research_lifecycle_lock_temp_cleanup_failed")
            try:
                (self.path / _OWNER_NAME).unlink(missing_ok=True)
                self.path.rmdir()
            except OSError:
                log.warning("research_lifecycle_lock_create_cleanup_failed")
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def _create(self) -> bool:
        try:
            os.mkdir(self.path, mode=0o700)
        except FileExistsError:
            return False
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc
        try:
            if os.name != "nt":
                os.chmod(self.path, 0o700)
            self._directory_identity = self._safe_directory_identity(self.path)
            self._write_owner()
        except Exception:
            try:
                (self.path / _OWNER_NAME).unlink(missing_ok=True)
                self.path.rmdir()
            except OSError:
                log.warning("research_lifecycle_lock_create_cleanup_failed")
            raise
        self._entered = True
        log.info("research_lifecycle_lock_acquired")
        return True

    def _restore_raced_lock(self, stale: Path) -> None:
        try:
            if not self.path.exists():
                os.rename(stale, self.path)
        except OSError:
            log.warning("research_lifecycle_lock_race_restore_failed")

    def _reclaim_dead_owner(self) -> None:
        try:
            owner, _identity = self._read_owner(self.path)
            alive = self.pid_exists(int(owner["pid"]))
        except LifecycleLockError:
            raise
        except Exception as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc
        if type(alive) is not bool or alive:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        token = str(owner["token"])
        stale = self.path.with_name(f".{self.path.name}.stale-{uuid4().hex}")
        try:
            os.rename(self.path, stale)
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc
        try:
            moved, owner_identity = self._read_owner(stale)
            if moved["token"] != token:
                self._restore_raced_lock(stale)
                raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
            owner_path = stale / _OWNER_NAME
            before = owner_path.lstat()
            if (before.st_dev, before.st_ino, before.st_size) != owner_identity:
                raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
            owner_path.unlink()
            stale.rmdir()
            log.info("research_lifecycle_stale_lock_reclaimed")
        except LifecycleLockError:
            raise
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def __enter__(self) -> Self:
        self._prepare_parent()
        if self._create():
            return self
        self._reclaim_dead_owner()
        if not self._create():
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if not self._entered:
            return False
        try:
            if self._directory_identity != self._safe_directory_identity(self.path):
                raise LifecycleLockError(
                    "lifecycle lock ownership was lost",
                    code="lifecycle_lock_ownership_lost",
                )
            owner, owner_identity = self._read_owner(self.path)
            if owner["token"] != self.token:
                raise LifecycleLockError(
                    "lifecycle lock ownership was lost",
                    code="lifecycle_lock_ownership_lost",
                )
            owner_path = self.path / _OWNER_NAME
            current = owner_path.lstat()
            if (current.st_dev, current.st_ino, current.st_size) != owner_identity:
                raise LifecycleLockError(
                    "lifecycle lock ownership was lost",
                    code="lifecycle_lock_ownership_lost",
                )
            owner_path.unlink()
            self.path.rmdir()
            self._entered = False
            log.info("research_lifecycle_lock_released")
        except LifecycleLockError as error:
            if error.code == "lifecycle_lock_ownership_lost":
                raise
            raise LifecycleLockError(
                "lifecycle lock ownership was lost",
                code="lifecycle_lock_ownership_lost",
            ) from error
        except OSError as error:
            raise LifecycleLockError(
                "lifecycle lock ownership was lost",
                code="lifecycle_lock_ownership_lost",
            ) from error
        return False
