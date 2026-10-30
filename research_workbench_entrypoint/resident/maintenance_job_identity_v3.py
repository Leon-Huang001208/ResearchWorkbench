"""Read-only exact job targets. A binding never authorizes a launchd effect.

Rehearsal records must be created by the controlled operator, separately from
research artifacts. Expected paths and hashes come from its reviewed plan, not
from the record itself. Loaded policy, port ownership, runtime closure and effect
authority remain the maintenance executor's responsibility.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal, NoReturn, cast
from uuid import UUID

from .evidence import UpdateBlocked

log = logging.getLogger(__name__)
PRODUCTION_LABEL = "com.research-workbench.multiuser-server"
REHEARSAL_LABEL_PREFIX = "com.research-workbench.maintenance-rehearsal."
REGISTRATION_FILENAME = "maintenance-job-identity-v3.json"
_SCHEMA = "rwb-maintenance-job-identity-v3"
_ISSUER = object()
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_TASK = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\Z")


def _blocked(code: str = "maintenance_job_identity_invalid") -> UpdateBlocked:
    log.warning("%s", code)
    return UpdateBlocked(code)


def _uid() -> int:
    if not all(hasattr(os, name) for name in ("getuid", "O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")):
        raise _blocked("maintenance_job_posix_identity_unavailable")
    return os.getuid()


def _path(value: Path) -> Path:
    if not isinstance(value, Path) or not value.is_absolute() or ".." in value.parts:
        raise _blocked()
    return value


def _facts(info: os.stat_result, *, directory: bool = False) -> tuple[int, ...]:
    common = (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)
    return (
        common
        if directory
        else (*common, info.st_nlink, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
    )


@contextmanager
def _directory(path: Path) -> Iterator[int]:
    """Walk with no-follow descriptors; never create a missing directory."""
    _path(path)
    _uid()
    descriptor = None
    try:
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_NONBLOCK
        descriptor = os.open(path.anchor, flags)
        for component in path.parts[1:]:
            named = os.stat(component, dir_fd=descriptor, follow_symlinks=False)
            child = os.open(component, flags, dir_fd=descriptor)
            try:
                if not stat.S_ISDIR(named.st_mode) or _facts(named, directory=True) != _facts(
                    os.fstat(child), directory=True
                ):
                    raise _blocked("maintenance_job_directory_changed")
            except BaseException:
                os.close(child)
                raise
            os.close(descriptor)
            descriptor = child
        yield descriptor
        if path.resolve(strict=True) != path or _facts(path.lstat(), directory=True) != _facts(
            os.fstat(descriptor), directory=True
        ):
            raise _blocked("maintenance_job_directory_changed")
    except UpdateBlocked:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise _blocked("maintenance_job_directory_unsafe") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


@dataclass(frozen=True)
class _DirectoryPin:
    path: Path
    facts: tuple[int, ...]
    private: bool


def _pin_directory(path: Path, *, private: bool) -> _DirectoryPin:
    with _directory(path) as descriptor:
        info = os.fstat(descriptor)
        if info.st_uid != _uid() or (
            stat.S_IMODE(info.st_mode) != 0o700 if private else bool(info.st_mode & 0o022)
        ):
            raise _blocked("maintenance_job_directory_unsafe")
        return _DirectoryPin(path, _facts(info, directory=True), private)


@dataclass(frozen=True)
class _FilePin:
    path: Path
    facts: tuple[int, ...]
    sha256: str
    limit: int
    modes: tuple[int, ...] | None
    executable: bool


def _pin_file(
    path: Path,
    *,
    limit: int,
    modes: tuple[int, ...] | None = (0o600,),
    executable: bool = False,
    expected: str | None = None,
    collect: bool = False,
) -> tuple[_FilePin, bytes]:
    _path(path)
    if expected is not None and (not isinstance(expected, str) or _SHA.fullmatch(expected) is None):
        raise _blocked()
    descriptor = None
    try:
        with _directory(path.parent) as parent:
            descriptor = os.open(
                path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent
            )
            before = os.fstat(descriptor)
            mode = stat.S_IMODE(before.st_mode)
            if (
                not stat.S_ISREG(before.st_mode)
                or before.st_uid not in ({0, _uid()} if executable else {_uid()})
                or (modes is not None and (mode not in modes or before.st_nlink != 1))
                or (executable and (mode & 0o022 or not mode & 0o111))
                or not 0 <= before.st_size <= limit
            ):
                raise _blocked("maintenance_job_file_unsafe")
            digest = hashlib.sha256()
            content = bytearray()
            count = 0
            while chunk := os.read(descriptor, min(64 * 1024, limit + 1 - count)):
                count += len(chunk)
                if count > limit:
                    raise _blocked("maintenance_job_file_unsafe")
                digest.update(chunk)
                if collect:
                    content.extend(chunk)
            after = os.fstat(descriptor)
            named = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            if (
                count != before.st_size
                or _facts(before) != _facts(after)
                or _facts(after) != _facts(named)
            ):
                raise _blocked("maintenance_job_file_changed")
            value = digest.hexdigest()
            if expected is not None and value != expected:
                raise _blocked("maintenance_job_artifact_changed")
            return _FilePin(path, _facts(after), value, limit, modes, executable), bytes(content)
    except UpdateBlocked:
        raise
    except (OSError, ValueError) as exc:
        raise _blocked("maintenance_job_file_unsafe") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _verify_file_metadata(pin: _FilePin) -> None:
    """Close the earlier-file window after all potentially long digest reads."""
    try:
        with _directory(pin.path.parent) as parent:
            named = os.stat(pin.path.name, dir_fd=parent, follow_symlinks=False)
            if _facts(named) != pin.facts:
                raise _blocked("maintenance_job_file_changed")
    except UpdateBlocked:
        raise
    except (OSError, ValueError) as exc:
        raise _blocked("maintenance_job_file_changed") from exc


@dataclass(frozen=True)
class _ExecutableReference:
    path: Path
    facts: tuple[int, ...]
    target: Path
    link: str | None


def _reference(path: Path) -> _ExecutableReference:
    """Preserve the approved venv argv path; pin its resolved binary separately."""
    _path(path)
    with _directory(path.parent) as parent:
        before = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if not (stat.S_ISREG(before.st_mode) or stat.S_ISLNK(before.st_mode)):
            raise _blocked("maintenance_job_executable_unsafe")
        target = path.resolve(strict=True)
        link = os.readlink(path.name, dir_fd=parent) if stat.S_ISLNK(before.st_mode) else None
        after = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        if _facts(before) != _facts(after):
            raise _blocked("maintenance_job_executable_changed")
        return _ExecutableReference(path, _facts(after), target, link)


def _validate_plist_target(path: Path, *, private: bool) -> None:
    """The path may be planned/absent; an existing object must not redirect it."""
    with _directory(path.parent) as parent:
        try:
            info = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != _uid()
            or info.st_nlink != 1
            or (stat.S_IMODE(info.st_mode) != 0o600 if private else bool(info.st_mode & 0o022))
        ):
            raise _blocked("maintenance_job_plist_target_unsafe")


def _json(raw: bytes) -> dict[str, Any]:
    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate key")
            result[key] = value
        return result

    def constant(_value: str) -> NoReturn:
        raise ValueError("non-finite value")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise TypeError("object required")
    return cast(dict[str, Any], value)


@dataclass(frozen=True)
class ExactJobBinding:
    """An issued, revalidatable target description, not an effect capability."""

    scope: Literal["production", "rehearsal"]
    home: Path
    label: str
    domain: str
    plist_path: Path
    port: int
    script: Path | None
    executable: Path | None
    nonce: str | None
    task_id: str | None
    script_sha256: str | None
    executable_sha256: str | None
    _directories: tuple[_DirectoryPin, ...] = field(repr=False)
    _files: tuple[_FilePin, ...] = field(repr=False)
    _reference: _ExecutableReference | None = field(repr=False)
    _issuer: object = field(repr=False, compare=False)
    _stamp: str = field(default="", repr=False)

    def _fingerprint(self) -> str:
        values = [
            self.scope,
            str(self.home),
            self.label,
            self.domain,
            str(self.plist_path),
            self.port,
            str(self.script) if self.script else None,
            str(self.executable) if self.executable else None,
            self.nonce,
            self.task_id,
            self.script_sha256,
            self.executable_sha256,
            [(str(p.path), p.facts, p.private) for p in self._directories],
            [(str(p.path), p.facts, p.sha256, p.limit, p.modes, p.executable) for p in self._files],
            repr(self._reference),
        ]
        return hashlib.sha256(json.dumps(values, separators=(",", ":")).encode()).hexdigest()

    @classmethod
    def _issue(cls, binding: ExactJobBinding) -> ExactJobBinding:
        object.__setattr__(binding, "_stamp", binding._fingerprint())
        binding.verify()
        log.info("maintenance_job_identity_bound scope=%s", binding.scope)
        return binding

    @property
    def identity_sha256(self) -> str:
        return self._stamp

    @classmethod
    def production(cls, *, home: Path) -> ExactJobBinding:
        """Only the existing current-user production root, label and port."""
        try:
            if _path(home) != Path.home() / ".research-workbench":
                raise _blocked()
            directories = (
                _pin_directory(home, private=True),
                _pin_directory(home / "server", private=True),
                _pin_directory(Path.home() / "Library/LaunchAgents", private=False),
            )
            config_pin, raw = _pin_file(
                home / "server/resident.json", limit=64 * 1024, collect=True
            )
            config = _json(raw)
            if type(config.get("port")) is not int or config["port"] != 8089:
                raise _blocked("maintenance_job_production_port_invalid")
            return cls._issue(
                cls(
                    scope="production",
                    home=home,
                    label=PRODUCTION_LABEL,
                    domain=f"gui/{_uid()}",
                    plist_path=Path.home() / "Library/LaunchAgents" / f"{PRODUCTION_LABEL}.plist",
                    port=8089,
                    script=None,
                    executable=None,
                    nonce=None,
                    task_id=None,
                    script_sha256=None,
                    executable_sha256=None,
                    _directories=directories,
                    _files=(config_pin,),
                    _reference=None,
                    _issuer=_ISSUER,
                )
            )
        except UpdateBlocked:
            raise
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise _blocked() from exc

    @classmethod
    def rehearsal(
        cls,
        *,
        root: Path,
        task_id: str,
        nonce: str,
        script: Path,
        executable: Path,
        script_sha256: str,
        executable_sha256: str,
        port: int,
    ) -> ExactJobBinding:
        """Verify an operator-registered scope against independent reviewed inputs.

        The port is a registered candidate, not a reservation. Its admission and
        live listener ownership must be rechecked by the authorized consumer.
        """
        try:
            _path(root)
            if any(
                not isinstance(value, str) or _SHA.fullmatch(value) is None
                for value in (script_sha256, executable_sha256)
            ):
                raise _blocked("maintenance_job_reviewed_hash_invalid")
            if (
                not isinstance(task_id, str)
                or len(task_id) > 96
                or _TASK.fullmatch(task_id) is None
            ):
                raise _blocked()
            if type(nonce) is not str:
                raise _blocked()
            parsed = UUID(nonce)
            if (
                str(parsed) != nonce
                or parsed.version != 4
                or type(port) is not int
                or not 49152 <= port <= 65535
            ):
                raise _blocked()
            for protected in (
                Path.home() / ".research-workbench",
                Path.home() / "Library/LaunchAgents",
            ):
                if root.is_relative_to(protected) or protected.is_relative_to(root):
                    raise _blocked("maintenance_job_rehearsal_root_protected")
            if not _path(script).is_relative_to(root):
                raise _blocked()
            directories = (
                _pin_directory(root, private=True),
                _pin_directory(root / "LaunchAgents", private=True),
            )
            marker, raw = _pin_file(root / REGISTRATION_FILENAME, limit=64 * 1024, collect=True)
            record = _json(raw)
            expected = {
                "schema": _SCHEMA,
                "task_id": task_id,
                "owner_uid": _uid(),
                "nonce": nonce,
                "root": str(root),
                "root_identity": list(directories[0].facts[:2]),
                "script": str(script),
                "script_sha256": script_sha256,
                "executable": str(_path(executable)),
                "executable_sha256": executable_sha256,
                "port": port,
            }
            if (
                record != expected
                or type(record.get("owner_uid")) is not int
                or type(record.get("port")) is not int
                or any(type(v) is not int for v in record.get("root_identity", []))
            ):
                raise _blocked("maintenance_job_registration_mismatch")
            script_pin, _ = _pin_file(
                script, limit=1024 * 1024, modes=(0o600, 0o700), expected=script_sha256
            )
            reference = _reference(executable)
            executable_pin, _ = _pin_file(
                reference.target,
                limit=256 * 1024 * 1024,
                modes=None,
                executable=True,
                expected=executable_sha256,
            )
            return cls._issue(
                cls(
                    scope="rehearsal",
                    home=root,
                    label=REHEARSAL_LABEL_PREFIX + parsed.hex,
                    domain=f"gui/{_uid()}",
                    plist_path=root
                    / "LaunchAgents"
                    / f"{REHEARSAL_LABEL_PREFIX}{parsed.hex}.plist",
                    port=port,
                    script=script,
                    executable=executable,
                    nonce=nonce,
                    task_id=task_id,
                    script_sha256=script_sha256,
                    executable_sha256=executable_sha256,
                    _directories=directories,
                    _files=(marker, script_pin, executable_pin),
                    _reference=reference,
                    _issuer=_ISSUER,
                )
            )
        except UpdateBlocked:
            raise
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
            raise _blocked() from exc

    def verify(self) -> None:
        """Fail closed on target substitution, registry drift or artifact change."""
        try:
            if (
                type(self) is not ExactJobBinding
                or self._issuer is not _ISSUER
                or self._stamp != self._fingerprint()
            ):
                raise _blocked("maintenance_job_binding_changed")
            _validate_plist_target(self.plist_path, private=self.scope == "rehearsal")
            for directory_pin in self._directories:
                if (
                    _pin_directory(directory_pin.path, private=directory_pin.private)
                    != directory_pin
                ):
                    raise _blocked("maintenance_job_directory_changed")
            for file_pin in self._files:
                current, _ = _pin_file(
                    file_pin.path,
                    limit=file_pin.limit,
                    modes=file_pin.modes,
                    executable=file_pin.executable,
                    expected=file_pin.sha256,
                )
                if current != file_pin:
                    raise _blocked("maintenance_job_file_changed")
            if self._reference is not None and _reference(self._reference.path) != self._reference:
                raise _blocked("maintenance_job_executable_changed")
            for file_pin in self._files:
                _verify_file_metadata(file_pin)
            for directory_pin in self._directories:
                if (
                    _pin_directory(directory_pin.path, private=directory_pin.private)
                    != directory_pin
                ):
                    raise _blocked("maintenance_job_directory_changed")
            _validate_plist_target(self.plist_path, private=self.scope == "rehearsal")
        except UpdateBlocked:
            raise
        except (OSError, ValueError, TypeError, AttributeError, RuntimeError) as exc:
            raise _blocked("maintenance_job_binding_changed") from exc
