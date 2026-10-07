"""Private stdlib-only persistence for the selected Research Web runtime."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import stat
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, NoReturn
from uuid import uuid4

RuntimeMode = Literal["native", "docker"]

MAX_RUNTIME_MODE_BYTES = 16 * 1024
_SCHEMA_VERSION = 1
_KEYS = {"schema_version", "mode", "installation_id", "updated_at"}
_INSTALLATION_ID = re.compile(r"[a-f0-9]{32}")
_UPDATED_AT = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{6}Z")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
log = logging.getLogger(__name__)


class RuntimeModeError(RuntimeError):
    """Stable, path-free runtime-mode failure."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class RuntimeModeRecord:
    schema_version: int
    mode: RuntimeMode
    installation_id: str
    updated_at: str | None


def _fail(suffix: str) -> NoReturn:
    raise RuntimeModeError(f"runtime_mode_{suffix}") from None


def _identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _node_identity(value: os.stat_result) -> tuple[int, ...]:
    # Directory link counts can change as entries are created on APFS. The
    # retained descriptor plus device/inode/mode prove that the directory node
    # itself remains the same while an atomic write mutates its contents.
    return (value.st_dev, value.st_ino, value.st_mode)


def _is_reparse(identity: os.stat_result) -> bool:
    return bool(getattr(identity, "st_file_attributes", 0) & _REPARSE_POINT)


def _validate_posix_private_directory(identity: os.stat_result) -> None:
    if (
        not stat.S_ISDIR(identity.st_mode)
        or identity.st_uid != os.getuid()
        or stat.S_IMODE(identity.st_mode) != 0o700
    ):
        _fail("unsafe_path")


def _validate_posix_private_file(identity: os.stat_result) -> None:
    if (
        not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
        or identity.st_uid != os.getuid()
        or stat.S_IMODE(identity.st_mode) != 0o600
    ):
        _fail("unsafe_path")


def _path_identity(path: Path) -> os.stat_result:
    """Validate every component without resolving aliases and return the leaf identity."""
    leaf: os.stat_result | None = None
    for component in (*reversed(path.parents), path):
        identity = component.lstat()
        if stat.S_ISLNK(identity.st_mode) or _is_reparse(identity):
            _fail("unsafe_path")
        if component == path:
            if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
                _fail("unsafe_path")
            if os.name == "posix":
                _validate_posix_private_file(identity)
            if identity.st_size > MAX_RUNTIME_MODE_BYTES:
                _fail("too_large")
            leaf = identity
        elif not stat.S_ISDIR(identity.st_mode):
            _fail("unsafe_path")
        elif os.name == "posix" and component == path.parent:
            _validate_posix_private_directory(identity)
    if leaf is None:
        _fail("unsafe_path")
    return leaf


def _validate_directory_chain(path: Path) -> None:
    for component in (*reversed(path.parents), path):
        identity = component.lstat()
        if (
            stat.S_ISLNK(identity.st_mode)
            or _is_reparse(identity)
            or not stat.S_ISDIR(identity.st_mode)
        ):
            _fail("unsafe_path")


def _validate_existing_prefix(path: Path, *, allow_private_repair: bool = False) -> None:
    """Reject aliases in existing ancestors even when the leaf is absent."""
    for component in (*reversed(path.parents), path):
        try:
            identity = component.lstat()
        except FileNotFoundError:
            break
        if stat.S_ISLNK(identity.st_mode) or _is_reparse(identity):
            _fail("unsafe_path")
        if component != path and not stat.S_ISDIR(identity.st_mode):
            _fail("unsafe_path")
        if os.name == "posix" and component == path.parent:
            if identity.st_uid != os.getuid():
                _fail("unsafe_path")
            if not allow_private_repair:
                _validate_posix_private_directory(identity)


@contextmanager
def _pin_windows_parents(path: Path, *, node_only: bool = False) -> Iterator[None]:
    """Retain non-reparse Windows parent handles that deny rename/delete races."""
    try:
        import _winapi

        with ExitStack() as stack:
            parents: list[tuple[Path, os.stat_result]] = []
            for component in reversed(path.parents):
                # FILE_READ_ATTRIBUTES; FILE_SHARE_READ; OPEN_EXISTING;
                # BACKUP_SEMANTICS | OPEN_REPARSE_POINT.
                handle = _winapi.CreateFile(str(component), 0x80, 1, 0, 3, 0x02200000, 0)
                stack.callback(_winapi.CloseHandle, handle)
                identity = component.lstat()
                if not stat.S_ISDIR(identity.st_mode) or _is_reparse(identity):
                    _fail("unsafe_path")
                parents.append((component, identity))
            yield
            for component, before in parents:
                after = component.lstat()
                comparison = _node_identity if node_only else _identity
                if comparison(after) != comparison(before):
                    _fail("changed")
    except RuntimeModeError:
        raise
    except (ImportError, AttributeError, OSError, TypeError):
        _fail("io")


@contextmanager
def _pin_posix_parents(path: Path, *, node_only: bool = False) -> Iterator[int]:
    """Traverse absolute parents with retained no-follow directory descriptors."""
    with ExitStack() as stack:
        parent: int | None = None
        directories: list[tuple[int, int | None, str, os.stat_result]] = []
        for component in reversed(path.parents):
            name = str(component) if parent is None else component.name
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, descriptor)
            if not stat.S_ISDIR(before.st_mode) or _identity(os.fstat(descriptor)) != _identity(
                before
            ):
                _fail("changed")
            directories.append((descriptor, parent, name, before))
            parent = descriptor
        if parent is None:
            _fail("unsafe_path")
        yield parent
        for descriptor, ancestor, name, before in directories:
            # Retained descriptors protect the traversal identity. Unrelated
            # sibling creation in shared ancestors is not a private-file change.
            # Keep full metadata on the immediate parent for rename-and-restore.
            comparison = _identity if not node_only and descriptor == parent else _node_identity
            if comparison(os.fstat(descriptor)) != comparison(before) or comparison(
                os.stat(name, dir_fd=ancestor, follow_symlinks=False)
            ) != comparison(before):
                _fail("changed")


def _open_posix_directory(parent: int, name: str) -> tuple[int, os.stat_result]:
    before = os.stat(name, dir_fd=parent, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode) or stat.S_ISLNK(before.st_mode) or _is_reparse(before):
        _fail("unsafe_path")
    descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
    after = os.fstat(descriptor)
    if _node_identity(after) != _node_identity(before):
        os.close(descriptor)
        _fail("changed")
    return descriptor, after


@contextmanager
def _private_posix_parent(path: Path, *, strict_parent: bool = False) -> Iterator[int]:
    """Create missing private parents; strict callers never repair existing modes."""
    home = path.parent.parent
    with ExitStack() as stack:
        home_parent = stack.enter_context(_pin_posix_parents(home, node_only=True))
        try:
            os.mkdir(home.name, mode=0o700, dir_fd=home_parent)
        except FileExistsError:
            pass
        home_descriptor, home_identity = _open_posix_directory(home_parent, home.name)
        stack.callback(os.close, home_descriptor)
        if home_identity.st_uid != os.getuid():
            _fail("unsafe_path")
        if strict_parent:
            _validate_posix_private_directory(home_identity)

        try:
            os.mkdir(path.parent.name, mode=0o700, dir_fd=home_descriptor)
        except FileExistsError:
            pass
        install_descriptor, install_identity = _open_posix_directory(
            home_descriptor, path.parent.name
        )
        stack.callback(os.close, install_descriptor)
        if install_identity.st_uid != os.getuid():
            _fail("unsafe_path")
        if stat.S_IMODE(install_identity.st_mode) != 0o700:
            if strict_parent:
                _fail("unsafe_path")
            os.fchmod(install_descriptor, 0o700)
        install_identity = os.fstat(install_descriptor)
        _validate_posix_private_directory(install_identity)
        install_entry = os.stat(path.parent.name, dir_fd=home_descriptor, follow_symlinks=False)
        if _node_identity(install_entry) != _node_identity(install_identity):
            _fail("changed")

        yield install_descriptor

        current_home = os.stat(home.name, dir_fd=home_parent, follow_symlinks=False)
        current_install = os.stat(path.parent.name, dir_fd=home_descriptor, follow_symlinks=False)
        if (
            _node_identity(current_home) != _node_identity(home_identity)
            or current_home.st_uid != os.getuid()
            or _node_identity(current_install) != _node_identity(install_identity)
        ):
            _fail("changed")
        _validate_posix_private_directory(os.fstat(install_descriptor))


def _read_bytes(path: Path) -> tuple[bytes, os.stat_result]:
    before = _path_identity(path)
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    with ExitStack() as stack:
        if os.name == "nt":
            stack.enter_context(_pin_windows_parents(path))
            descriptor = os.open(path, flags)
        else:
            parent = stack.enter_context(_pin_posix_parents(path))
            _validate_posix_private_directory(os.fstat(parent))
            descriptor = os.open(path.name, flags, dir_fd=parent)
        stack.callback(os.close, descriptor)
        if os.name == "posix":
            _validate_posix_private_file(os.fstat(descriptor))
        if _identity(os.fstat(descriptor)) != _identity(before):
            _fail("changed")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_RUNTIME_MODE_BYTES + 1)
        if len(raw) > MAX_RUNTIME_MODE_BYTES:
            _fail("too_large")
        if _identity(os.fstat(descriptor)) != _identity(before) or _identity(
            _path_identity(path)
        ) != _identity(before):
            _fail("changed")
    return raw, before


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail("json")
        value[key] = item
    return value


def _validate(payload: object) -> RuntimeModeRecord:
    if type(payload) is not dict or set(payload) != _KEYS:
        _fail("keys")
    value: dict[str, Any] = payload
    if (
        type(value["schema_version"]) is not int
        or type(value["mode"]) is not str
        or type(value["installation_id"]) is not str
        or type(value["updated_at"]) is not str
    ):
        _fail("type")
    if value["schema_version"] != _SCHEMA_VERSION or value["mode"] not in ("native", "docker"):
        _fail("value")
    if _INSTALLATION_ID.fullmatch(value["installation_id"]) is None:
        _fail("value")
    if _UPDATED_AT.fullmatch(value["updated_at"]) is None:
        _fail("value")
    try:
        # Validate UTC wire syntax only; the resulting naive datetime never escapes.
        datetime.strptime(value["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ")  # noqa: DTZ007
    except ValueError:
        _fail("value")
    return RuntimeModeRecord(
        schema_version=_SCHEMA_VERSION,
        mode=value["mode"],
        installation_id=value["installation_id"],
        updated_at=value["updated_at"],
    )


def _decode(raw: bytes) -> RuntimeModeRecord:
    try:
        text = raw.decode("utf-8")
    except UnicodeError:
        _fail("encoding")
    try:
        payload = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=lambda _: _fail("json"),
        )
    except RuntimeModeError:
        raise
    except (ValueError, RecursionError):
        _fail("json")
    return _validate(payload)


def _same_identity(current: os.stat_result | None, expected: os.stat_result | None) -> bool:
    if current is None or expected is None:
        return current is expected
    return _identity(current) == _identity(expected)


def _leaf_identity(path: Path) -> os.stat_result | None:
    try:
        return _path_identity(path)
    except FileNotFoundError:
        return None


def _leaf_identity_at(parent: int, name: str) -> os.stat_result | None:
    try:
        identity = os.stat(name, dir_fd=parent, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if (
        stat.S_ISLNK(identity.st_mode)
        or _is_reparse(identity)
        or not stat.S_ISREG(identity.st_mode)
        or identity.st_nlink != 1
    ):
        _fail("unsafe_path")
    _validate_posix_private_file(identity)
    return identity


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            _fail("io")
        offset += written


def _atomic_write_posix(
    path: Path, raw: bytes, expected: os.stat_result | None, *, strict_parent: bool = False
) -> os.stat_result:
    """Publish privately and return identity proven against the retained write FD.

    Strict callers create their directory separately and never repair permissions.
    A publication/readback failure is ambiguous; callers must not adopt a later
    path read as proof that the published file still belongs to this write.
    """
    temporary = f".runtime.json.{secrets.token_hex(16)}.tmp"
    parent_context = (
        _pin_posix_parents(path, node_only=True) if strict_parent else _private_posix_parent(path)
    )
    with parent_context as parent:
        _validate_posix_private_directory(os.fstat(parent))
        if not _same_identity(_leaf_identity_at(parent, path.name), expected):
            _fail("changed")
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=parent,
            )
            os.fchmod(descriptor, 0o600)
            _validate_posix_private_file(os.fstat(descriptor))
            _write_all(descriptor, raw)
            os.fsync(descriptor)
            if not _same_identity(_leaf_identity_at(parent, path.name), expected):
                _fail("changed")
            os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
            published = os.fstat(descriptor)
            if not _same_identity(_leaf_identity_at(parent, path.name), published):
                _fail("changed")
            return published
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                os.unlink(temporary, dir_fd=parent)
            except FileNotFoundError:
                pass


def _atomic_write_windows(path: Path, raw: bytes, expected: os.stat_result | None) -> None:
    temporary = path.parent / f".runtime.json.{secrets.token_hex(16)}.tmp"
    with _pin_windows_parents(path, node_only=True):
        if not _same_identity(_leaf_identity(path), expected):
            _fail("changed")
        descriptor: int | None = None
        try:
            descriptor = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0),
                0o600,
            )
            _write_all(descriptor, raw)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            if not _same_identity(_leaf_identity(path), expected):
                _fail("changed")
            os.replace(temporary, path)
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


class RuntimeModeStore:
    """Read and atomically persist the selected runtime under a private home."""

    def __init__(self, home: Path) -> None:
        self.home = Path(home).absolute()
        self.path = self.home / "install" / "runtime.json"
        self._installation_id: str | None = None

    def _load(
        self, *, allow_missing_private_repair: bool = False
    ) -> tuple[RuntimeModeRecord, os.stat_result | None]:
        try:
            self.path.lstat()
        except FileNotFoundError:
            _validate_existing_prefix(self.path, allow_private_repair=allow_missing_private_repair)
            return RuntimeModeRecord(_SCHEMA_VERSION, "native", "", None), None
        raw, identity = _read_bytes(self.path)
        record = _decode(raw)
        if self._installation_id is not None and record.installation_id != self._installation_id:
            _fail("changed")
        self._installation_id = record.installation_id
        return record, identity

    def _ensure_windows_directories(self) -> None:
        with _pin_windows_parents(self.home, node_only=True):
            self.home.mkdir(mode=0o700, exist_ok=True)
            _validate_directory_chain(self.home)
        with _pin_windows_parents(self.path.parent, node_only=True):
            self.path.parent.mkdir(mode=0o700, exist_ok=True)
            _validate_directory_chain(self.path.parent)

    @contextmanager
    def _write_lock(self, *, strict_parent: bool = False) -> Iterator[None]:
        """Retain one private, never-unlinked lock inode through readback.

        POSIX flock serializes independent descriptors/processes. Windows uses
        a byte lock on a no-reparse handle opened without delete sharing, so the
        locked file cannot be replaced while any writer retains its handle.
        Read-only operations never enter this context or create a lock file.
        strict_parent keeps existing POSIX parent permissions unchanged.
        """
        lock_path = self.path.with_name("runtime.lock")
        with ExitStack() as stack:
            if os.name == "nt":
                import _winapi
                import msvcrt

                self._ensure_windows_directories()
                stack.enter_context(_pin_windows_parents(lock_path, node_only=True))
                # GENERIC_READ | GENERIC_WRITE, share read/write but not delete,
                # OPEN_ALWAYS, FILE_FLAG_OPEN_REPARSE_POINT.
                handle = _winapi.CreateFile(str(lock_path), 0xC0000000, 3, 0, 4, 0x00200000, 0)
                try:
                    descriptor = msvcrt.open_osfhandle(
                        handle, os.O_RDWR | getattr(os, "O_BINARY", 0)
                    )
                except BaseException:
                    _winapi.CloseHandle(handle)
                    raise
                stack.callback(os.close, descriptor)

                def acquire() -> None:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)

                def release() -> None:
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)

                def entry() -> os.stat_result:
                    return _path_identity(lock_path)

            else:
                import fcntl

                parent = stack.enter_context(
                    _private_posix_parent(self.path, strict_parent=strict_parent)
                )
                descriptor = os.open(
                    lock_path.name, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600, dir_fd=parent
                )
                stack.callback(os.close, descriptor)

                def acquire() -> None:
                    fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)

                def release() -> None:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)

                def entry() -> os.stat_result:
                    identity = _leaf_identity_at(parent, lock_path.name)
                    if identity is None:
                        _fail("changed")
                    return identity

            def verify() -> None:
                opened = os.fstat(descriptor)
                current = entry()
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or opened.st_nlink != 1
                    or opened.st_size not in (0, 1)
                    or _node_identity(opened) != _node_identity(current)
                ):
                    _fail("unsafe_path")
                if os.name == "posix":
                    _validate_posix_private_file(opened)

            verify()
            deadline = time.monotonic() + 10
            while True:
                try:
                    acquire()
                    break
                except OSError as error:
                    import errno

                    if error.errno not in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                        raise
                    if time.monotonic() >= deadline:
                        _fail("lock_timeout")
                    time.sleep(0.02)
            stack.callback(release)
            verify()
            if os.name == "nt" and os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"\0")
                os.fsync(descriptor)
            yield
            verify()

    @staticmethod
    def _log_failure(operation: str, error: RuntimeModeError) -> None:
        log.warning("runtime_mode operation=%s code=%s", operation, error.code)

    def read(self) -> RuntimeModeRecord:
        try:
            record, _ = self._load()
        except RuntimeModeError as error:
            self._log_failure("read", error)
            raise
        except (OSError, TypeError, ValueError):
            error = RuntimeModeError("runtime_mode_io")
            self._log_failure("read", error)
            raise error from None
        log.debug("runtime_mode operation=read code=ok")
        return record

    def write(
        self, mode: RuntimeMode, *, expected: RuntimeModeRecord | None = None
    ) -> RuntimeModeRecord:
        try:
            if type(mode) is not str or mode not in ("native", "docker"):
                _fail("value")
            with self._write_lock():
                return self._write_locked(mode, expected=expected)
        except RuntimeModeError as error:
            self._log_failure("write", error)
            raise
        except (OSError, TypeError, ValueError):
            error = RuntimeModeError("runtime_mode_io")
            self._log_failure("write", error)
            raise error from None

    def _write_locked(
        self, mode: RuntimeMode, *, expected: RuntimeModeRecord | None
    ) -> RuntimeModeRecord:
        try:
            current, before = self._load(allow_missing_private_repair=True)
            if expected is not None and current != expected:
                _fail("changed")
            installation_id = current.installation_id or uuid4().hex
            updated_at = datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
            expected = RuntimeModeRecord(_SCHEMA_VERSION, mode, installation_id, updated_at)
            raw = (
                json.dumps(
                    {
                        "schema_version": expected.schema_version,
                        "mode": expected.mode,
                        "installation_id": expected.installation_id,
                        "updated_at": expected.updated_at,
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            if os.name == "nt":
                self._ensure_windows_directories()
                _atomic_write_windows(self.path, raw, before)
            else:
                _atomic_write_posix(self.path, raw, before)
            self._installation_id = installation_id
            persisted, _ = self._load()
            if persisted != expected:
                _fail("changed")
        except RuntimeModeError as error:
            self._log_failure("write", error)
            raise
        except (OSError, TypeError, ValueError):
            error = RuntimeModeError("runtime_mode_io")
            self._log_failure("write", error)
            raise error from None
        log.debug("runtime_mode operation=write code=ok")
        return persisted
