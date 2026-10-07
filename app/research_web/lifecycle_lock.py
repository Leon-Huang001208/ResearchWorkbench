"""Exclusive, ownership-checked lock for Research Web lifecycle mutations."""

from __future__ import annotations

import json
import logging
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

try:
    import fcntl
except ImportError:  # pragma: no cover - native Windows
    fcntl = None

try:
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None

log = logging.getLogger(__name__)

_OWNER_NAME = "owner.json"
_OWNER_LIMIT_BYTES = 4096
_TOKEN_PATTERN = re.compile(r"[0-9a-f]{32}")
_REPARSE_FLAG = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def _fsync_directory(path: Path, *, platform_name: str | None = None) -> None:
    """Persist a directory entry where directory fsync is supported."""
    if (platform_name or os.name) == "nt":
        return
    handle = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(handle)
    finally:
        os.close(handle)


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
        *,
        trusted_root: Path | None = None,
    ) -> None:
        self.path = Path(os.path.abspath(path))
        self._trusted_root_explicit = trusted_root is not None
        self.trusted_root = Path(
            os.path.abspath(trusted_root if trusted_root is not None else self.path.parent)
        )
        try:
            relative = self.path.relative_to(self.trusted_root)
        except ValueError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc
        if not relative.parts:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        self.pid_exists = pid_exists
        self.pid = os.getpid() if pid is None else pid
        if type(self.pid) is not int or self.pid <= 1:
            raise LifecycleLockError("lifecycle lock owner is invalid", code="lifecycle_busy")
        self.token = uuid4().hex
        self.guard_path = self.path.with_name(f"{self.path.name}.guard")
        self._guard_handle: int | None = None
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

    @classmethod
    def _validate_existing_ancestors(
        cls,
        path: Path,
        *,
        platform_name: str | None = None,
    ) -> None:
        """Reject aliases and reparse points in every existing component."""
        platform_name = platform_name or os.name
        absolute = Path(os.path.abspath(path))
        if platform_name == "nt":
            observed: list[tuple[Path, tuple[int, int]]] = []
            current = Path(absolute.anchor)
            anchor = current.resolve(strict=True)
            for part in absolute.parts[1:]:
                current /= part
                try:
                    identity = current.lstat()
                except FileNotFoundError:
                    break
                if (
                    current.is_symlink()
                    or cls._is_reparse(identity)
                    or not stat.S_ISDIR(identity.st_mode)
                ):
                    raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
                try:
                    current.resolve(strict=True).relative_to(anchor)
                except ValueError as exc:
                    raise LifecycleLockError(
                        "lifecycle lock is busy", code="lifecycle_busy"
                    ) from exc
                observed.append((current, (identity.st_dev, identity.st_ino)))
            for component, expected in observed:
                identity = component.lstat()
                if (identity.st_dev, identity.st_ino) != expected:
                    raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
            return

        anchor = Path(absolute.anchor or os.sep)
        handle = os.open(anchor, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            for part in absolute.parts[1:]:
                flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
                try:
                    child = os.open(part, flags, dir_fd=handle)
                except FileNotFoundError:
                    break
                except OSError as exc:
                    raise LifecycleLockError(
                        "lifecycle lock is busy", code="lifecycle_busy"
                    ) from exc
                try:
                    opened = os.fstat(child)
                    named = os.stat(part, dir_fd=handle, follow_symlinks=False)
                    if (
                        not stat.S_ISDIR(opened.st_mode)
                        or stat.S_ISLNK(named.st_mode)
                        or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
                    ):
                        raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
                except Exception:
                    os.close(child)
                    raise
                os.close(handle)
                handle = child
        finally:
            os.close(handle)

    def _trusted_root_identity(self, *, platform_name: str) -> tuple[int, int]:
        try:
            before = self.trusted_root.lstat()
            if (
                self.trusted_root.is_symlink()
                or self._is_reparse(before)
                or not stat.S_ISDIR(before.st_mode)
                or (platform_name != "nt" and stat.S_IMODE(before.st_mode) != 0o700)
            ):
                raise OSError("unsafe trusted root")
            if platform_name == "nt":
                after = self.trusted_root.lstat()
                if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
                    raise OSError("trusted root changed")
                return before.st_dev, before.st_ino
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            handle = os.open(self.trusted_root, flags)
            try:
                opened = os.fstat(handle)
            finally:
                os.close(handle)
            after = self.trusted_root.lstat()
            identities = {(item.st_dev, item.st_ino) for item in (before, opened, after)}
            if len(identities) != 1:
                raise OSError("trusted root changed")
            return before.st_dev, before.st_ino
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def _prepare_default_trusted_root(self, *, platform_name: str) -> None:
        if self.trusted_root.exists():
            return
        if self._trusted_root_explicit:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        try:
            self._validate_existing_ancestors(
                self.trusted_root.parent,
                platform_name=platform_name,
            )
            self.trusted_root.mkdir(mode=0o700)
            if platform_name != "nt":
                os.chmod(self.trusted_root, 0o700)
        except (OSError, LifecycleLockError) as exc:
            if isinstance(exc, LifecycleLockError):
                raise
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def _walk_managed_parent(
        self,
        *,
        create_missing: bool,
        platform_name: str,
    ) -> None:
        self._prepare_default_trusted_root(platform_name=platform_name)
        expected_root = self._trusted_root_identity(platform_name=platform_name)
        parent = self.path.parent
        try:
            relative = parent.relative_to(self.trusted_root)
        except ValueError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

        if platform_name == "nt":
            canonical_root = self.trusted_root.resolve(strict=True)
            current = self.trusted_root
            observed: list[tuple[Path, tuple[int, int]]] = []
            for part in relative.parts:
                current /= part
                try:
                    identity = current.lstat()
                except FileNotFoundError:
                    if not create_missing:
                        raise LifecycleLockError(
                            "lifecycle lock is busy", code="lifecycle_busy"
                        ) from None
                    current.mkdir(mode=0o700)
                    identity = current.lstat()
                if (
                    current.is_symlink()
                    or self._is_reparse(identity)
                    or not stat.S_ISDIR(identity.st_mode)
                ):
                    raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
                try:
                    current.resolve(strict=True).relative_to(canonical_root)
                except ValueError as exc:
                    raise LifecycleLockError(
                        "lifecycle lock is busy", code="lifecycle_busy"
                    ) from exc
                observed.append((current, (identity.st_dev, identity.st_ino)))
            for component, expected in observed:
                identity = component.lstat()
                if (identity.st_dev, identity.st_ino) != expected:
                    raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
        else:
            flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
            handle = os.open(self.trusted_root, flags)
            try:
                for part in relative.parts:
                    try:
                        child = os.open(part, flags, dir_fd=handle)
                    except FileNotFoundError:
                        if not create_missing:
                            raise LifecycleLockError(
                                "lifecycle lock is busy", code="lifecycle_busy"
                            ) from None
                        os.mkdir(part, mode=0o700, dir_fd=handle)
                        child = os.open(part, flags, dir_fd=handle)
                        os.fchmod(child, 0o700)
                    try:
                        opened = os.fstat(child)
                        named = os.stat(part, dir_fd=handle, follow_symlinks=False)
                        if (
                            not stat.S_ISDIR(opened.st_mode)
                            or stat.S_ISLNK(named.st_mode)
                            or stat.S_IMODE(opened.st_mode) != 0o700
                            or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino)
                        ):
                            raise LifecycleLockError(
                                "lifecycle lock is busy", code="lifecycle_busy"
                            )
                    except Exception:
                        os.close(child)
                        raise
                    os.close(handle)
                    handle = child
            finally:
                os.close(handle)
        if self._trusted_root_identity(platform_name=platform_name) != expected_root:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")

    def _prepare_parent(self) -> None:
        try:
            self._walk_managed_parent(create_missing=True, platform_name=os.name)
            self._safe_directory_identity(self.path.parent)
        except LifecycleLockError:
            raise
        except OSError as exc:
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def _acquire_guard(self, *, platform_name: str | None = None) -> None:
        platform_name = platform_name or os.name
        handle: int | None = None
        created = False
        try:
            self._walk_managed_parent(create_missing=False, platform_name=platform_name)
            flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
            try:
                handle = os.open(self.guard_path, flags | os.O_CREAT | os.O_EXCL, 0o600)
                created = True
            except FileExistsError:
                handle = os.open(self.guard_path, flags)
            if created and platform_name != "nt":
                os.fchmod(handle, 0o600)
            if created:
                os.fsync(handle)
                _fsync_directory(self.guard_path.parent, platform_name=platform_name)
            before = self.guard_path.lstat()
            opened = os.fstat(handle)
            after = self.guard_path.lstat()
            identities = {(item.st_dev, item.st_ino) for item in (before, opened, after)}
            if (
                len(identities) != 1
                or self.guard_path.is_symlink()
                or self._is_reparse(before)
                or not stat.S_ISREG(before.st_mode)
                or before.st_nlink != 1
                or before.st_size > 1
                or (platform_name != "nt" and stat.S_IMODE(before.st_mode) != 0o600)
            ):
                raise OSError("unsafe lifecycle guard")
            if platform_name == "nt":
                if msvcrt is None:
                    raise OSError("native Windows locking unavailable")
                if before.st_size == 0:
                    os.write(handle, b"\0")
                    os.fsync(handle)
                os.lseek(handle, 0, os.SEEK_SET)
                msvcrt.locking(handle, msvcrt.LK_NBLCK, 1)
            else:
                if fcntl is None:
                    raise OSError("POSIX locking unavailable")
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._guard_handle = handle
        except (OSError, BlockingIOError) as exc:
            if handle is not None:
                os.close(handle)
            raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy") from exc

    def _release_guard(self, *, platform_name: str | None = None) -> None:
        handle = self._guard_handle
        if handle is None:
            return
        self._guard_handle = None
        platform_name = platform_name or os.name
        failed = False
        try:
            if platform_name == "nt":
                if msvcrt is not None:
                    os.lseek(handle, 0, os.SEEK_SET)
                    msvcrt.locking(handle, msvcrt.LK_UNLCK, 1)
            elif fcntl is not None:
                fcntl.flock(handle, fcntl.LOCK_UN)
        except OSError:
            failed = True
        try:
            os.close(handle)
        except OSError:
            failed = True
        if failed:
            raise LifecycleLockError(
                "lifecycle_lock_release_failed",
                code="lifecycle_lock_release_failed",
            )

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

    def _write_owner(self, *, platform_name: str | None = None) -> None:
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
            _fsync_directory(self.path, platform_name=platform_name)
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
        self._acquire_guard()
        try:
            if self._create():
                return self
            self._reclaim_dead_owner()
            if not self._create():
                raise LifecycleLockError("lifecycle lock is busy", code="lifecycle_busy")
            return self
        except Exception:
            try:
                self._release_guard()
            except LifecycleLockError:
                log.error("research_lifecycle_lock_release_failed")
            raise

    def assert_held(self) -> None:
        """Prove this live in-process lease before a nested lifecycle operation."""
        try:
            if (
                not self._entered
                or self._guard_handle is None
                or self.pid != os.getpid()
                or self._directory_identity != self._safe_directory_identity(self.path)
            ):
                raise OSError("lease inactive")
            guard = os.fstat(self._guard_handle)
            named = self.guard_path.lstat()
            if (
                (guard.st_dev, guard.st_ino) != (named.st_dev, named.st_ino)
                or not stat.S_ISREG(named.st_mode)
                or named.st_nlink != 1
                or named.st_size > 1
                or self._is_reparse(named)
                or (os.name != "nt" and stat.S_IMODE(named.st_mode) != 0o600)
            ):
                raise OSError("guard changed")
            owner, identity = self._read_owner(self.path)
            current = (self.path / _OWNER_NAME).lstat()
            if (
                owner["token"] != self.token
                or owner["pid"] != self.pid
                or (current.st_dev, current.st_ino, current.st_size) != identity
            ):
                raise OSError("owner changed")
        except (OSError, LifecycleLockError) as error:
            raise LifecycleLockError(
                "lifecycle lock ownership was lost", code="lifecycle_lock_ownership_lost"
            ) from error

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if not self._entered:
            try:
                self._release_guard()
            except LifecycleLockError:
                if exc_value is None:
                    raise
                log.error("research_lifecycle_lock_release_failed")
            return False
        cleanup_error: LifecycleLockError | None = None
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
                cleanup_error = error
            else:
                cleanup_error = LifecycleLockError(
                    "lifecycle lock ownership was lost",
                    code="lifecycle_lock_ownership_lost",
                )
        except OSError as error:
            cleanup_error = LifecycleLockError(
                "lifecycle lock ownership was lost",
                code="lifecycle_lock_ownership_lost",
            )
            cleanup_error.__cause__ = error
        release_error: LifecycleLockError | None = None
        try:
            self._release_guard()
        except LifecycleLockError as error:
            release_error = error
        if cleanup_error is not None:
            raise cleanup_error
        if release_error is not None:
            if exc_value is None:
                raise release_error
            log.error("research_lifecycle_lock_release_failed")
        return False
