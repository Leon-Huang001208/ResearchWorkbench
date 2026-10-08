"""Stdlib-only, fail-closed directory boundary for private runtime state."""

from __future__ import annotations

import logging
import os
import stat
import sys
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path

log = logging.getLogger(__name__)


class RuntimeStateError(ValueError):
    """An unsafe runtime state directory; never includes a sensitive path."""


def _identity(value: os.stat_result) -> tuple[int, ...]:
    # Creating state files changes directory size/timestamps, but not ownership.
    return value.st_dev, value.st_ino, value.st_mode, value.st_uid, value.st_gid


def _log_rejection(
    reason: str | None = None,
    *,
    phase: str = "enter",
    leaf: bool = False,
    changed: str = "none",
    parent: bool = False,
    ownership_transition: str | None = None,
) -> None:
    try:
        if reason is None:
            log.warning("runtime_state_directory_rejected")
        else:
            message = "runtime_state_directory_rejected reason=%s phase=%s scope=%s changed=%s"
            args: tuple[str, ...] = (reason, phase, "leaf" if leaf else "ancestor", changed)
            if ownership_transition is not None:
                message += " ownership_transition=%s position=%s"
                position = "leaf" if leaf else "parent" if parent else "other_ancestor"
                args += (ownership_transition, position)
            log.warning(message, *args)
    except Exception:  # noqa: BLE001 - A broken logger must not replace the security rejection.
        # A failing diagnostic handler must never replace the security rejection.
        return


def _log_identity_change(
    before: os.stat_result,
    current: os.stat_result,
    *,
    phase: str,
    leaf: bool,
    parent: bool = False,
) -> None:
    changed = ",".join(
        name
        for name, old, new in zip(
            ("dev", "ino", "mode", "uid", "gid"), _identity(before), _identity(current)
        )
        if old != new
    )
    transition = "other"
    try:
        runtime_pair = (os.getuid(), os.getgid())
        before_pair = (before.st_uid, before.st_gid)
        current_pair = (current.st_uid, current.st_gid)
        if runtime_pair != (0, 0):
            if before_pair == (0, 0) and current_pair == runtime_pair:
                transition = "root_pair_to_runtime_pair"
            elif before_pair == runtime_pair and current_pair == (0, 0):
                transition = "reverse"
    except Exception:  # noqa: BLE001 - Optional classification cannot interrupt rejection.
        # Optional ownership classification must not interfere with rejection.
        transition = "other"
    _log_rejection(
        "identity_changed",
        phase=phase,
        leaf=leaf,
        changed=changed,
        parent=parent,
        ownership_transition=transition,
    )


def _validate_directory(
    value: os.stat_result,
    *,
    leaf: bool,
    platform_name: str,
    legacy_native: bool = False,
    phase: str = "enter",
    scope_leaf: bool | None = None,
) -> None:
    scope_leaf = leaf if scope_leaf is None else scope_leaf
    if not stat.S_ISDIR(value.st_mode) or getattr(value, "st_file_attributes", 0) & 0x400:
        reason = "invalid_type" if not stat.S_ISDIR(value.st_mode) else "reparse_point"
        _log_rejection(reason, phase=phase, leaf=scope_leaf)
        raise RuntimeStateError("runtime_state_unsafe")
    if platform_name == "nt":
        return
    owner = os.getuid()
    if leaf:
        unsafe = value.st_uid != owner or bool(value.st_mode & (0o022 if legacy_native else 0o077))
    else:
        # System ancestors may be root-owned; sticky system temp directories
        # protect user-owned children. Other writable ancestors are unsafe.
        sticky_system = value.st_uid == 0 and bool(value.st_mode & stat.S_ISVTX)
        unsafe = value.st_uid not in {0, owner} or (
            bool(value.st_mode & 0o022) and not sticky_system
        )
    if unsafe:
        unsafe_owner = value.st_uid != owner if leaf else value.st_uid not in {0, owner}
        _log_rejection(
            "unsafe_owner" if unsafe_owner else "unsafe_mode", phase=phase, leaf=scope_leaf
        )
        raise RuntimeStateError("runtime_state_unsafe")


@contextmanager
def runtime_state_directory(
    path: Path, *, create: bool = False, native_data_root: Path | None = None
) -> Iterator[Path]:
    """Validate and pin every ancestor before state access, then recheck identity.

    POSIX walks with no-follow directory descriptors. Windows holds directory
    handles denying deletion/rename and rejects reparse points without claiming
    that POSIX mode bits prove ACL safety. Missing directories are only created
    on an explicitly writable path, each with private permissions. Only the
    canonical Native data/runtime leaf may retain legacy read/execute bits,
    protected by its pinned, current-user-owned 0700 immediate data parent.
    """
    path = path.absolute()
    if ".." in path.parts:
        raise RuntimeStateError("runtime_state_unsafe")
    native = native_data_root.absolute() if native_data_root is not None else None
    legacy_native = False
    body_error = None
    missing_is_expected = False
    try:
        native_layout = (
            native is not None and path == native / "runtime" and native == native.resolve()
        )
        with ExitStack() as stack:
            records = []
            parent = None
            for component in (*reversed(path.parents), path):
                name = str(component) if parent is None else component.name
                try:
                    before = component.lstat()
                except FileNotFoundError:
                    if not create:
                        missing_is_expected = True
                        raise
                    if sys.platform == "win32":
                        component.mkdir(mode=0o700)
                    else:
                        os.mkdir(name, mode=0o700, dir_fd=parent)
                    before = component.lstat()
                if (
                    component == path
                    and native_layout
                    and os.name != "nt"
                    and before.st_mode & 0o077
                ):
                    # The immediate parent was already checked and pinned.
                    _validate_directory(
                        records[-1][2], leaf=True, platform_name=os.name, scope_leaf=False
                    )
                    if stat.S_IMODE(records[-1][2].st_mode) != 0o700:
                        _log_rejection("unsafe_mode", phase="enter", leaf=False)
                        raise RuntimeStateError("runtime_state_unsafe")
                    legacy_native = True
                _validate_directory(
                    before,
                    leaf=component == path,
                    platform_name=os.name,
                    legacy_native=legacy_native,
                )
                if sys.platform == "win32":
                    import _winapi

                    handle = _winapi.CreateFile(str(component), 0x80, 3, 0, 3, 0x02200000, 0)
                    stack.callback(_winapi.CloseHandle, handle)
                    descriptor = None
                else:
                    descriptor = os.open(
                        name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent
                    )
                    stack.callback(os.close, descriptor)
                    opened = os.fstat(descriptor)
                    if _identity(opened) != _identity(before):
                        _log_identity_change(
                            before,
                            opened,
                            phase="open_fd",
                            leaf=component == path,
                            parent=component == path.parent,
                        )
                        raise RuntimeStateError("runtime_state_unsafe")
                named = component.lstat()
                if _identity(named) != _identity(before):
                    _log_identity_change(
                        before,
                        named,
                        phase="enter",
                        leaf=component == path,
                        parent=component == path.parent,
                    )
                    raise RuntimeStateError("runtime_state_unsafe")
                records.append((component, descriptor, before))
                parent = descriptor

            def verify(phase: str) -> None:
                for component, descriptor, before in records:
                    current = component.lstat()
                    _validate_directory(
                        current,
                        leaf=component == path or (legacy_native and component == native),
                        platform_name=os.name,
                        legacy_native=legacy_native and component == path,
                        phase=phase,
                        scope_leaf=component == path,
                    )
                    if _identity(current) != _identity(before):
                        _log_identity_change(
                            before,
                            current,
                            phase=phase,
                            leaf=component == path,
                            parent=component == path.parent,
                        )
                        raise RuntimeStateError("runtime_state_unsafe")
                    if descriptor is not None:
                        opened = os.fstat(descriptor)
                        if _identity(opened) != _identity(before):
                            _log_identity_change(
                                before,
                                opened,
                                phase=phase,
                                leaf=component == path,
                                parent=component == path.parent,
                            )
                            raise RuntimeStateError("runtime_state_unsafe")

            verify("pre_yield")
            try:
                yield path
            except BaseException as exc:
                body_error = exc
                raise
            finally:
                verify("post_yield")
    except FileNotFoundError as exc:
        if missing_is_expected or exc is body_error:
            raise
        _log_rejection()
        raise RuntimeStateError("runtime_state_unsafe") from exc
    except (OSError, ValueError, RuntimeError, ImportError, AttributeError) as exc:
        if exc is body_error:
            raise
        _log_rejection()
        raise RuntimeStateError("runtime_state_unsafe") from exc
