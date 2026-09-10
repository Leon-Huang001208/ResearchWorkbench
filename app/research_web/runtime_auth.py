"""Cross-platform, fail-closed reads for the private DSH runtime control file."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any

MAX_RUNTIME_AUTH_BYTES = 4096


class RuntimeAuthFileError(ValueError):
    """The runtime control path failed structural or identity validation."""


def _is_unsafe_identity(path: Path, identity: os.stat_result, *, platform_name: str) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    is_reparse_point = bool(getattr(identity, "st_file_attributes", 0) & reparse_flag)
    return (
        not stat.S_ISREG(identity.st_mode)
        or path.is_symlink()
        or is_reparse_point
        or identity.st_nlink != 1
        or identity.st_size > MAX_RUNTIME_AUTH_BYTES
        or (platform_name != "nt" and bool(identity.st_mode & 0o077))
    )


def _identity(identity: os.stat_result) -> tuple[int, int, int]:
    return identity.st_dev, identity.st_ino, identity.st_size


def read_runtime_auth_record(path: Path, *, platform_name: str | None = None) -> Any:
    """Read one bounded control record without trusting path aliases or replacements."""
    resolved_platform = platform_name or os.name
    before = path.lstat()
    if _is_unsafe_identity(path, before, platform_name=resolved_platform):
        raise RuntimeAuthFileError("unsafe runtime auth control")

    with path.open("rb") as stream:
        opened = os.fstat(stream.fileno())
        if _identity(opened) != _identity(before) or _is_unsafe_identity(
            path, opened, platform_name=resolved_platform
        ):
            raise RuntimeAuthFileError("runtime auth control changed before open")
        raw = stream.read(MAX_RUNTIME_AUTH_BYTES + 1)

    after = path.lstat()
    if (
        len(raw) > MAX_RUNTIME_AUTH_BYTES
        or _identity(after) != _identity(before)
        or _is_unsafe_identity(path, after, platform_name=resolved_platform)
    ):
        raise RuntimeAuthFileError("runtime auth control changed during read")
    return json.loads(raw.decode("utf-8"))
