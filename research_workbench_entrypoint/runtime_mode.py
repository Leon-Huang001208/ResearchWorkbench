"""Private stdlib-only persistence for the selected Research Web runtime."""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import stat
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
            if os.name == "posix" and stat.S_IMODE(identity.st_mode) != 0o600:
                _fail("unsafe_path")
            if identity.st_size > MAX_RUNTIME_MODE_BYTES:
                _fail("too_large")
            leaf = identity
        elif not stat.S_ISDIR(identity.st_mode):
            _fail("unsafe_path")
        elif (
            os.name == "posix"
            and component == path.parent
            and stat.S_IMODE(identity.st_mode) != 0o700
        ):
            _fail("unsafe_path")
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


def _validate_existing_prefix(path: Path) -> None:
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
        comparison = _node_identity if node_only else _identity
        for descriptor, ancestor, name, before in directories:
            if comparison(os.fstat(descriptor)) != comparison(before) or comparison(
                os.stat(name, dir_fd=ancestor, follow_symlinks=False)
            ) != comparison(before):
                _fail("changed")


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
            descriptor = os.open(path.name, flags, dir_fd=parent)
        stack.callback(os.close, descriptor)
        if _identity(os.fstat(descriptor)) != _identity(before):
            _fail("changed")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_RUNTIME_MODE_BYTES + 1)
        if len(raw) > MAX_RUNTIME_MODE_BYTES:
            _fail("too_large")
        if (
            _identity(os.fstat(descriptor)) != _identity(before)
            or _identity(_path_identity(path)) != _identity(before)
        ):
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
        datetime.strptime(value["updated_at"], "%Y-%m-%dT%H:%M:%S.%fZ")
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
    return identity


def _write_all(descriptor: int, raw: bytes) -> None:
    offset = 0
    while offset < len(raw):
        written = os.write(descriptor, raw[offset:])
        if written <= 0:
            _fail("io")
        offset += written


def _atomic_write_posix(path: Path, raw: bytes, expected: os.stat_result | None) -> None:
    temporary = f".runtime.json.{secrets.token_hex(16)}.tmp"
    with _pin_posix_parents(path, node_only=True) as parent:
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
            _write_all(descriptor, raw)
            os.fsync(descriptor)
            os.close(descriptor)
            descriptor = None
            if not _same_identity(_leaf_identity_at(parent, path.name), expected):
                _fail("changed")
            os.replace(temporary, path.name, src_dir_fd=parent, dst_dir_fd=parent)
            os.fsync(parent)
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
            os.chmod(temporary, 0o600)
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

    def _load(self) -> tuple[RuntimeModeRecord, os.stat_result | None]:
        try:
            self.path.lstat()
        except FileNotFoundError:
            _validate_existing_prefix(self.path)
            return RuntimeModeRecord(_SCHEMA_VERSION, "native", "", None), None
        raw, identity = _read_bytes(self.path)
        record = _decode(raw)
        if self._installation_id is not None and record.installation_id != self._installation_id:
            _fail("changed")
        self._installation_id = record.installation_id
        return record, identity

    def _ensure_private_directory(self) -> None:
        self.home.mkdir(mode=0o700, exist_ok=True)
        _validate_directory_chain(self.home)
        self.path.parent.mkdir(mode=0o700, exist_ok=True)
        _validate_directory_chain(self.path.parent)
        os.chmod(self.path.parent, 0o700)
        if stat.S_IMODE(self.path.parent.stat().st_mode) != 0o700:
            _fail("unsafe_path")

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

    def write(self, mode: RuntimeMode) -> RuntimeModeRecord:
        try:
            if type(mode) is not str or mode not in ("native", "docker"):
                _fail("value")
            current, before = self._load()
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
            self._ensure_private_directory()
            if os.name == "nt":
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
