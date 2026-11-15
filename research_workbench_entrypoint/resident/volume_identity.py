"""Preserve the frozen native and gateway identity contract across APFS remounts."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import plistlib
import stat
import subprocess
import sys
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from . import controller
from .admission import file_lock
from .evidence import SHA, UpdateBlocked

log = logging.getLogger(__name__)
ANCHOR_NAME = "volume-identity.json"
_DATA_VOLUME = Path("/System/Volumes/Data")
_RECORD_LIMIT = 1_000_000


def _present(path: Path) -> bool:
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _directory(path: Path, *, private: bool = False) -> os.stat_result:
    info = path.lstat()
    if (
        not path.is_absolute()
        or path.resolve(strict=True) != path
        or not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or (private and info.st_mode & 0o077)
    ):
        raise UpdateBlocked("resident_volume_directory_unverified")
    return info


def _private_bytes(path: Path) -> bytes:
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or info.st_nlink != 1
                or info.st_mode & 0o077
                or info.st_size > _RECORD_LIMIT
            ):
                raise ValueError
            data = stream.read(_RECORD_LIMIT + 1)
            if len(data) != info.st_size:
                raise ValueError
            return data
    except (OSError, ValueError) as exc:
        raise UpdateBlocked("resident_volume_record_invalid") from exc


def _record(path: Path) -> dict:
    try:
        value = json.loads(_private_bytes(path))
        if not isinstance(value, dict):
            raise TypeError
        return value
    except (ValueError, TypeError) as exc:
        raise UpdateBlocked("resident_volume_record_invalid") from exc


def _mount_for(path: Path, device: int) -> Path:
    # macOS firmlinks expose data-volume paths under /Users and /private.
    if _DATA_VOLUME.is_dir() and _DATA_VOLUME.stat().st_dev == device:
        return _DATA_VOLUME
    mount = next((parent for parent in (path, *path.parents) if parent.is_mount()), None)
    if mount is None or mount.stat().st_dev != device:
        raise UpdateBlocked("resident_apfs_volume_unverified")
    return mount


def _observe_directory(path: Path) -> tuple[dict, list[int]]:
    if sys.platform != "darwin":
        raise UpdateBlocked("resident_volume_identity_macos_only")
    info = _directory(path)
    try:
        mount = _mount_for(path, info.st_dev)
        payload = subprocess.check_output(
            ["/usr/sbin/diskutil", "info", "-plist", str(mount)],
            timeout=5,
        )
        if len(payload) > 65_536:
            raise ValueError
        volume = plistlib.loads(payload)
        if volume["MountPoint"] != str(mount) or mount.stat().st_dev != info.st_dev:
            raise ValueError
        filesystem = volume["FilesystemType"]
        if not isinstance(filesystem, str) or not filesystem:
            raise ValueError
        if filesystem != "apfs":
            raise UpdateBlocked("resident_volume_not_apfs")
        raw_uuid = volume["VolumeUUID"]
        if not isinstance(raw_uuid, str):
            raise TypeError
        volume_uuid = UUID(raw_uuid)
        birthtime_ns = int(info.st_birthtime * 1_000_000_000)
        after = path.lstat()
        if (
            volume_uuid.int == 0
            or birthtime_ns <= 0
            or (after.st_dev, after.st_ino, after.st_uid, after.st_birthtime)
            != (info.st_dev, info.st_ino, info.st_uid, info.st_birthtime)
        ):
            raise ValueError
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, KeyError) as exc:
        raise UpdateBlocked("resident_apfs_volume_unverified") from exc
    return {
        "path": str(path),
        "volume_uuid": str(volume_uuid),
        "mount_point": str(mount),
        "uid": info.st_uid,
        "inode": info.st_ino,
        "birthtime_ns": birthtime_ns,
    }, [info.st_dev, info.st_ino]


def _identity(saved, current: list[int]) -> list[int]:
    if (
        type(saved) is not list
        or len(saved) != 2
        or any(type(value) is not int or value <= 0 for value in saved)
        or saved[1] != current[1]
    ):
        raise UpdateBlocked("resident_volume_directory_identity_changed")
    return saved


def _native_records(home: Path) -> tuple[dict, str]:
    _directory(home / "install", private=True)
    config = _record(home / "resident/config.json")
    manifest = _record(home / "install/manifest.json")
    artifact = home / "resident/controller.pyz"
    if (
        type(config.get("schema_version")) is not int
        or config["schema_version"] != 1
        or config["artifact"] != str(artifact)
        or config["artifact_sha256"] != hashlib.sha256(_private_bytes(artifact)).hexdigest()
        or manifest["status"] != "installed"
        or not SHA.fullmatch(manifest["code_commit"])
        or config["web_port"] != 8088
        or config["runtime_port"] != 3081
    ):
        raise UpdateBlocked("resident_volume_native_unverified")
    return config, manifest["code_commit"]


def _gateway_record(home: Path, native: dict, revision: str) -> dict | None:
    server = home / "server"
    if not _present(server):
        return None
    _directory(server, private=True)
    path = server / "resident.json"
    if not _present(path):
        return None
    _directory(server / "run", private=True)
    gateway = _record(path)
    binding = gateway["binding"]
    primary = binding["primary_user_id"]
    if (
        type(gateway.get("version")) is not int
        or gateway["version"] != 1
        or gateway["port"] != 8089
        or not isinstance(primary, str)
        or str(UUID(primary)) != primary
        or binding["home"] != str(home)
        or binding["project"] != native["project"]
        or binding["revision"] != revision
        or binding["web_port"] != native["web_port"]
        or binding["runtime_port"] != native["runtime_port"]
    ):
        raise UpdateBlocked("resident_volume_gateway_unverified")
    return gateway


@dataclass(frozen=True)
class _Snapshot:
    anchor: dict | None
    observed: dict
    native: dict
    gateway: dict | None
    project_identity: list[int]
    data_identity: list[int]
    changed: list[str]


def _snapshot(home: Path, *, enrolling: bool) -> _Snapshot:
    _directory(home, private=True)
    _directory(home / "resident", private=True)
    anchor_path = home / "resident" / ANCHOR_NAME
    anchor = _record(anchor_path) if _present(anchor_path) else None
    if anchor is None and not enrolling:
        raise UpdateBlocked("resident_volume_identity_not_enrolled")

    native, revision = _native_records(home)
    project_path = Path(native["project"])
    project, project_identity = _observe_directory(project_path)
    data, data_identity = _observe_directory(home / "research-web")
    observed = {"version": 1, "project": project, "data": data}
    if anchor is not None and json.dumps(anchor, sort_keys=True) != json.dumps(
        observed, sort_keys=True
    ):
        raise UpdateBlocked("resident_volume_stable_identity_changed")
    if controller.git(project_path, "rev-parse", "HEAD") != revision:
        raise UpdateBlocked("resident_volume_native_unverified")

    changed = []
    gateway = _gateway_record(home, native, revision)
    if gateway is not None:
        binding = gateway["binding"]
        old_project = _identity(binding["project_identity"], project_identity)
        old_data = _identity(binding["data_identity"], data_identity)
        if old_project != project_identity or old_data != data_identity:
            changed.append("gateway")
    if _identity(native["project_identity"], project_identity) != project_identity:
        changed.append("native")
    return _Snapshot(anchor, observed, native, gateway, project_identity, data_identity, changed)


@contextmanager
def _mutation_scope(home: Path, *, supervisor_locked: bool):
    resident = home / "resident"
    run = home / "server/run"
    with ExitStack() as stack:
        if not supervisor_locked:
            stack.enter_context(file_lock(resident, "supervisor.lock", exclusive=True))
        stack.enter_context(file_lock(resident, "admission.lock", exclusive=True))
        operator_locked = _present(run)
        if operator_locked:
            stack.enter_context(file_lock(run, "operator.lock", exclusive=True))
        for path in (
            resident / "transaction.json",
            run / "gateway-upgrade.json",
            run / "gateway-source-rehome.json",
            run / "model-upgrade.json",
            run / "cutover.json",
            run / "birth-fence.json",
        ):
            if _present(path):
                raise UpdateBlocked("resident_volume_transaction_pending")
        yield operator_locked


def _validate_enrollment(state: _Snapshot) -> None:
    if state.changed:
        raise UpdateBlocked("resident_volume_enrollment_identity_changed")


def _require_current_locks(state: _Snapshot, operator_locked: bool) -> None:
    if state.gateway is not None and not operator_locked:
        raise UpdateBlocked("resident_volume_gateway_appeared")


def enroll(home: Path, *, supervisor_locked: bool = False) -> dict:
    """Record stable identities only while the original device/inode pairs match."""
    try:
        state = _snapshot(home, enrolling=True)
        _validate_enrollment(state)
        if state.anchor is not None:
            return {"status": "unchanged"}
        with _mutation_scope(home, supervisor_locked=supervisor_locked) as operator_locked:
            state = _snapshot(home, enrolling=True)
            _require_current_locks(state, operator_locked)
            _validate_enrollment(state)
            if state.anchor is not None:
                return {"status": "unchanged"}
            controller.atomic(home / "resident" / ANCHOR_NAME, state.observed)
        log.info("resident_volume_identity_enrolled")
        return {"status": "enrolled"}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise UpdateBlocked("resident_volume_enrollment_failed") from exc


def rebind(home: Path) -> dict:
    """Repair only device numbers; an interrupted update is safe to retry."""
    try:
        before = _snapshot(home, enrolling=False)
        if not before.changed:
            return {"status": "unchanged", "changed": []}
        with _mutation_scope(home, supervisor_locked=False) as operator_locked:
            state = _snapshot(home, enrolling=False)
            _require_current_locks(state, operator_locked)
            if before.observed != state.observed:
                raise UpdateBlocked("resident_volume_stable_identity_changed")
            # Let the old gateway load its new binding before publishing a
            # matching native device number (the frozen tick then can proceed).
            if state.gateway is not None and "gateway" in state.changed:
                binding = state.gateway["binding"]
                binding["project_identity"] = state.project_identity
                binding["data_identity"] = state.data_identity
                controller.atomic(home / "server/resident.json", state.gateway)
            if "native" in state.changed:
                state.native["project_identity"] = state.project_identity
                controller.atomic(home / "resident/config.json", state.native)
        if state.changed:
            log.info("resident_volume_identity_rebound records=%s", ",".join(state.changed))
        return {"status": "rebound" if state.changed else "unchanged", "changed": state.changed}
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise UpdateBlocked("resident_volume_rebind_failed") from exc
