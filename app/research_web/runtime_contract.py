"""Strict stdlib-only runtime facts shared by bootstrap and the lightweight Host.

Logging uses bootstrap's standard logger so this module can load before any
third-party dependencies exist. Callers configure their existing logs/ handlers.
"""

from __future__ import annotations

import json
import logging
import os
import re
import stat
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, NoReturn

MAX_CONTRACT_BYTES = 16 * 1024
DEFAULT_CONTRACT_PATH = Path(__file__).absolute().parents[2] / "runtimes/research_web.json"
log = logging.getLogger(__name__)


class RuntimeContractError(RuntimeError):
    """Invalid runtime facts; code and message are stable and contain no input."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ResearchWebRuntimeContract:
    """Validated immutable facts; the JSON file is the only source of pin values."""

    python_major: int
    python_minor: int
    python_docker_image: str
    node_major: int
    node_minimum_minor: int
    node_docker_image: str
    cjpy_version: str
    cjpy_sha256: str
    dsh_remote: str
    dsh_commit: str
    dsh_pnpm: str
    dsh_closure_files: int


def _fail(suffix: str) -> NoReturn:
    raise RuntimeContractError(f"runtime_contract_{suffix}") from None


def _path_identity(path: Path) -> os.stat_result:
    # Do not resolve first: that would erase evidence of directory/file aliases.
    for component in (*reversed(path.parents), path):
        identity = component.lstat()
        if stat.S_ISLNK(identity.st_mode) or getattr(identity, "st_file_attributes", 0) & getattr(
            stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400
        ):
            _fail("unsafe_path")
    if not stat.S_ISREG(identity.st_mode) or identity.st_nlink != 1:
        _fail("unsafe_path")
    if identity.st_size > MAX_CONTRACT_BYTES:
        _fail("too_large")
    return identity


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
    # Ancestor directory entries are unrelated to the pinned contract contents.
    return (value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid)


@contextmanager
def _pin_windows_parents(path: Path) -> Iterator[None]:
    """Hold non-reparse directory handles denying writes/renames during the read."""
    try:
        import _winapi

        with ExitStack() as stack:
            parents = []
            for component in reversed(path.parents):
                # FILE_READ_ATTRIBUTES; FILE_SHARE_READ only; OPEN_EXISTING;
                # FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT.
                # Earlier ancestors are already locked before advancing.
                handle = _winapi.CreateFile(str(component), 0x80, 1, 0, 3, 0x02200000, 0)
                stack.callback(_winapi.CloseHandle, handle)
                identity = component.lstat()
                if (
                    not stat.S_ISDIR(identity.st_mode)
                    or getattr(identity, "st_file_attributes", 0) & 0x400
                ):
                    _fail("unsafe_path")
                parents.append((component, identity))
            yield
            for component, identity in parents:
                comparison = _identity if component == path.parent else _node_identity
                if comparison(component.lstat()) != comparison(identity):
                    _fail("changed")
    except (ImportError, AttributeError, OSError, TypeError):
        _fail("io")


@contextmanager
def _pin_posix_parents(path: Path) -> Iterator[int]:
    """Traverse from root using retained directory descriptors, never path aliases."""
    with ExitStack() as stack:
        parent = None
        directories = []
        for component in reversed(path.parents):
            name = str(component) if parent is None else component.name
            before = os.stat(name, dir_fd=parent, follow_symlinks=False)
            descriptor = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            stack.callback(os.close, descriptor)
            if (
                not stat.S_ISDIR(before.st_mode)
                or _node_identity(os.fstat(descriptor)) != _node_identity(before)
            ):
                _fail("changed")
            directories.append((descriptor, parent, name, before))
            parent = descriptor
        if parent is None:
            _fail("unsafe_path")
        yield parent
        for descriptor, ancestor, name, before in directories:
            comparison = _identity if descriptor == parent else _node_identity
            if (
                comparison(os.fstat(descriptor)) != comparison(before)
                or comparison(os.stat(name, dir_fd=ancestor, follow_symlinks=False))
                != comparison(before)
            ):
                _fail("changed")


def _read(path: Path) -> bytes:
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
        # A bounded read also protects against growth after the size check.
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(MAX_CONTRACT_BYTES + 1)
        if len(raw) > MAX_CONTRACT_BYTES:
            _fail("too_large")
        if (
            _identity(os.fstat(descriptor)) != _identity(before)
            or _identity(_path_identity(path)) != _identity(before)
        ):
            _fail("changed")
        return raw


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            _fail("json")
        value[key] = item
    return value


def _exact_object(value: object, keys: set[str]) -> dict[str, Any]:
    if type(value) is not dict or set(value) != keys:
        _fail("keys")
    return value


def _validate(value: object) -> ResearchWebRuntimeContract:
    root = _exact_object(value, {"schema_version", "python", "node", "cjpy", "dsh"})
    python = _exact_object(root["python"], {"major", "minor", "docker_image"})
    node = _exact_object(root["node"], {"major", "minimum_minor", "docker_image"})
    cjpy = _exact_object(root["cjpy"], {"version", "sha256"})
    dsh = _exact_object(root["dsh"], {"remote", "commit", "pnpm", "closure_files"})
    integers = (
        root["schema_version"],
        python["major"],
        python["minor"],
        node["major"],
        node["minimum_minor"],
        dsh["closure_files"],
    )
    strings = (
        python["docker_image"],
        node["docker_image"],
        cjpy["version"],
        cjpy["sha256"],
        dsh["remote"],
        dsh["commit"],
        dsh["pnpm"],
    )
    if any(type(item) is not int for item in integers) or any(
        type(item) is not str for item in strings
    ):
        _fail("type")
    # Supported schema/engine families are validation policy, not release pins.
    if integers[:5] != (1, 3, 12, 24, 0):
        _fail("unsupported")
    version = r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)"
    patterns = (
        (
            python["docker_image"],
            rf"python:{python['major']}\.{python['minor']}\.(?:0|[1-9][0-9]*)-slim-bookworm",
        ),
        (
            node["docker_image"],
            rf"node:{node['major']}\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)-bookworm-slim",
        ),
        (cjpy["version"], version),
        (cjpy["sha256"], r"[a-f0-9]{64}"),
        (dsh["commit"], r"[a-f0-9]{40}"),
        (dsh["pnpm"], version),
        (
            dsh["remote"],
            r"https://github\.com/[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9_.-]*\.git",
        ),
    )
    if dsh["closure_files"] <= 0 or any(
        re.fullmatch(pattern, item) is None for item, pattern in patterns
    ):
        _fail("value")
    return ResearchWebRuntimeContract(
        python["major"],
        python["minor"],
        python["docker_image"],
        node["major"],
        node["minimum_minor"],
        node["docker_image"],
        cjpy["version"],
        cjpy["sha256"],
        dsh["remote"],
        dsh["commit"],
        dsh["pnpm"],
        dsh["closure_files"],
    )


def load_runtime_contract(path: Path | None = None) -> ResearchWebRuntimeContract:
    """Load bounded UTF-8 JSON, rejecting aliases, replacements and invalid facts."""
    try:
        try:
            raw = _read(Path(path).absolute() if path is not None else DEFAULT_CONTRACT_PATH)
        except (OSError, ValueError, TypeError):
            raise RuntimeContractError("runtime_contract_io") from None
        try:
            text = raw.decode("utf-8")
        except UnicodeError:
            raise RuntimeContractError("runtime_contract_encoding") from None
        try:
            payload = json.loads(
                text, object_pairs_hook=_unique_object, parse_constant=lambda _: _fail("json")
            )
        except (ValueError, RecursionError):
            raise RuntimeContractError("runtime_contract_json") from None
        contract = _validate(payload)
    except RuntimeContractError as exc:
        log.warning("runtime_contract_load_failed: %s", exc.code)
        raise
    log.debug("runtime_contract_loaded")
    return contract
