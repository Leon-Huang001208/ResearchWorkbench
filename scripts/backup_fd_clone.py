"""Narrow optional Darwin clone bridge; only inherited FDs 3/4 are accepted.

The caller retains source-path race checks, complete byte verification, capacity
admission and backup certification. This helper never falls back or removes data.
"""

from __future__ import annotations

import ctypes
import errno
import json
import logging
import os
import stat
import sys
from typing import Any

LOGGER = logging.getLogger("rwb.backup_fd_clone")
SOURCE_FD = 3
DIRECTORY_FD = 4
CLONE_NOFOLLOW = 0x0001
CLONE_NOOWNERCOPY = 0x0002
ACL_TYPE_EXTENDED = 0x00000100
ACL_FIRST_ENTRY = 0
FACT_KEYS = ("dev", "ino", "uid", "gid", "mode", "nlink", "size", "mtimeNs", "ctimeNs")


class Refusal(Exception):
    """A stable, non-sensitive outcome before any copy attempt."""

    def __init__(self, status: str, code: str):
        super().__init__(code)
        self.status = status
        self.code = code


def facts(value: os.stat_result) -> dict[str, str]:
    """Losslessly represent the same identity/state fields as Node bigint stat."""
    values = (
        value.st_dev,
        value.st_ino,
        value.st_uid,
        value.st_gid,
        value.st_mode,
        value.st_nlink,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )
    return dict(zip(FACT_KEYS, map(str, values), strict=True))


def validate_request(request: Any) -> tuple[str, dict[str, str]]:
    if not isinstance(request, dict) or set(request) != {"name", "expectedSource"}:
        raise Refusal("error", "CLONE_REQUEST_INVALID")
    name = request["name"]
    if (
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or "/" in name
        or "\x00" in name
        or len(os.fsencode(name)) > 255
    ):
        raise Refusal("error", "CLONE_NAME_INVALID")
    expected = request["expectedSource"]
    if (
        not isinstance(expected, dict)
        or set(expected) != set(FACT_KEYS)
        or any(
            not isinstance(value, str) or not value.isascii() or not value.isdecimal()
            for value in expected.values()
        )
    ):
        raise Refusal("error", "CLONE_SOURCE_FACTS_INVALID")
    return name, expected


def system_library() -> Any:
    if sys.platform != "darwin":
        raise Refusal("unsupported", "CLONE_PLATFORM_UNSUPPORTED")
    try:
        library = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        signatures = {
            "fclonefileat": (
                [ctypes.c_int, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint32],
                ctypes.c_int,
            ),
            "flistxattr": (
                [ctypes.c_int, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int],
                ctypes.c_ssize_t,
            ),
            "acl_get_fd_np": ([ctypes.c_int, ctypes.c_int], ctypes.c_void_p),
            "acl_get_entry": (
                [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)],
                ctypes.c_int,
            ),
            "acl_valid": ([ctypes.c_void_p], ctypes.c_int),
            "acl_free": ([ctypes.c_void_p], ctypes.c_int),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(library, name)
            function.argtypes = arguments
            function.restype = result
        return library
    except (OSError, AttributeError) as error:
        raise Refusal("unsupported", "CLONE_CAPABILITY_UNAVAILABLE") from error


def require_plain_metadata(library: Any, fd: int) -> None:
    """Reject rather than inherit ACLs, xattrs or flags into a private payload."""
    value = os.fstat(fd)
    if getattr(value, "st_flags", None) != 0:
        raise Refusal("unsupported", "CLONE_FLAGS_UNSUPPORTED")
    count = library.flistxattr(fd, None, 0, 0)
    if count != 0:
        raise Refusal("unsupported", "CLONE_XATTR_UNSUPPORTED")
    ctypes.set_errno(0)
    acl = library.acl_get_fd_np(fd, ACL_TYPE_EXTENDED)
    if not acl:
        # Darwin reports ENOENT for an absent extended ACL. The live descriptor
        # and an unchanged fstat distinguish this from a missing path/object.
        if ctypes.get_errno() == errno.ENOENT and facts(os.fstat(fd)) == facts(value):
            return
        raise Refusal("unsupported", "CLONE_ACL_UNVERIFIED")
    try:
        if library.acl_valid(acl) != 0:
            raise Refusal("unsupported", "CLONE_ACL_UNVERIFIED")
        entry = ctypes.c_void_p()
        ctypes.set_errno(0)
        result = library.acl_get_entry(acl, ACL_FIRST_ENTRY, ctypes.byref(entry))
        # Darwin returns 0 for an entry and -1/EINVAL when the valid ACL is empty.
        if result == 0:
            raise Refusal("unsupported", "CLONE_ACL_UNSUPPORTED")
        if result != -1 or ctypes.get_errno() != errno.EINVAL or entry.value:
            raise Refusal("unsupported", "CLONE_ACL_UNVERIFIED")
    finally:
        if library.acl_free(acl) != 0:
            raise Refusal("unsupported", "CLONE_ACL_UNVERIFIED")


def destination_present(name: str) -> bool:
    try:
        os.stat(name, dir_fd=DIRECTORY_FD, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def clone(request: Any) -> dict[str, Any]:
    """Attempt at most one clone; any uncertain effect is preserved as unknown."""
    attempted = False
    target_fd = None
    try:
        name, expected = validate_request(request)
        library = system_library()
        source = os.fstat(SOURCE_FD)
        directory = os.fstat(DIRECTORY_FD)
        if (
            not stat.S_ISREG(source.st_mode)
            or source.st_nlink != 1
            or source.st_uid != os.getuid()
            or source.st_mode & 0o7000
            or facts(source) != expected
        ):
            raise Refusal("error", "CLONE_SOURCE_INVALID")
        if (
            not stat.S_ISDIR(directory.st_mode)
            or directory.st_uid != os.getuid()
            or stat.S_IMODE(directory.st_mode) != 0o700
        ):
            raise Refusal("error", "CLONE_DIRECTORY_NOT_PRIVATE")
        if destination_present(name):
            raise Refusal("error", "CLONE_TARGET_EXISTS")
        require_plain_metadata(library, SOURCE_FD)
        require_plain_metadata(library, DIRECTORY_FD)
        if facts(os.fstat(SOURCE_FD)) != expected:
            raise Refusal("error", "CLONE_SOURCE_CHANGED")
        attempted = True
        ctypes.set_errno(0)
        result = library.fclonefileat(
            SOURCE_FD, DIRECTORY_FD, os.fsencode(name), CLONE_NOFOLLOW | CLONE_NOOWNERCOPY
        )
        syscall_errno = ctypes.get_errno()
        if result != 0:
            if destination_present(name):
                return {"status": "unknown", "code": "CLONE_EFFECT_UNVERIFIED"}
            if syscall_errno in {errno.ENOTSUP, errno.ENOSYS, errno.EXDEV}:
                return {"status": "unsupported", "code": "CLONE_FILESYSTEM_UNSUPPORTED"}
            return {"status": "error", "code": "CLONE_SYSCALL_FAILED", "errno": syscall_errno}
        target_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=DIRECTORY_FD)
        target = os.fstat(target_fd)
        if (
            not stat.S_ISREG(target.st_mode)
            or target.st_nlink != 1
            or target.st_uid != os.getuid()
            or (target.st_dev, target.st_ino) == (source.st_dev, source.st_ino)
        ):
            raise Refusal("unknown", "CLONE_TARGET_INVALID")
        require_plain_metadata(library, target_fd)
        os.fchmod(target_fd, 0o600)
        require_plain_metadata(library, SOURCE_FD)
        require_plain_metadata(library, DIRECTORY_FD)
        if facts(os.fstat(SOURCE_FD)) != expected:
            raise Refusal("unknown", "CLONE_SOURCE_CHANGED")
        target = os.fstat(target_fd)
        current = os.stat(name, dir_fd=DIRECTORY_FD, follow_symlinks=False)
        if facts(current) != facts(target):
            raise Refusal("unknown", "CLONE_TARGET_CHANGED")
        return {
            "status": "cloned",
            "code": "CLONE_CREATED_UNVERIFIED",
            "target": facts(target),
        }
    except Refusal as error:
        return {"status": "unknown" if attempted else error.status, "code": error.code}
    except (OSError, ValueError, TypeError, UnicodeError):
        return {
            "status": "unknown" if attempted else "error",
            "code": "CLONE_EFFECT_UNVERIFIED" if attempted else "CLONE_PREFLIGHT_FAILED",
        }
    finally:
        if target_fd is not None:
            os.close(target_fd)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(name)s %(message)s")
    try:
        raw = sys.stdin.buffer.read(4097)
        if len(raw) > 4096 or sys.argv[1:]:
            raise ValueError("request")
        result = clone(json.loads(raw))
    except (ValueError, TypeError, OSError):
        result = {"status": "error", "code": "CLONE_REQUEST_INVALID"}
    LOGGER.info("status=%s code=%s", result["status"], result["code"])
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
