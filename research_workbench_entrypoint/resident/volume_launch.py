"""Install the macOS storage identity repair peer without changing the Native supervisor."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
import plistlib
import re
import stat
import sys
import tempfile
import zipfile
from pathlib import Path

from . import controller, volume_identity
from .admission import MaintenanceBusy, file_lock, private_root
from .evidence import UpdateBlocked

LABEL = "com.research-workbench.resident-storage-identity"
_MODULES = ("__init__", "admission", "controller", "evidence", "volume_identity", "volume_launch")
_ARCHIVE_NAME = re.compile(r"storage-identity-([0-9a-f]{64})\.pyz\Z")
log = logging.getLogger(__name__)


def _artifact() -> bytes:
    package = Path(__file__).parent
    data = io.BytesIO()
    with zipfile.ZipFile(data, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for module in _MODULES:
            archive.writestr(
                zipfile.ZipInfo(f"resident/{module}.py"), (package / f"{module}.py").read_bytes()
            )
        archive.writestr(
            zipfile.ZipInfo("__main__.py"),
            "from resident.volume_launch import main\nraise SystemExit(main())\n",
        )
    return data.getvalue()


def _already_published(path: Path, contents: bytes, error_code: str) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
        or info.st_size != len(contents)
        or path.read_bytes() != contents
    ):
        raise UpdateBlocked(error_code)
    return True


def _publish_once(path: Path, contents: bytes, error_code: str) -> None:
    if _already_published(path, contents, error_code):
        return
    descriptor, staged = tempfile.mkstemp(dir=path.parent, prefix=".storage-identity-")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        if not _already_published(path, contents, error_code):
            os.replace(staged, path)
            controller.sync_directory(path.parent)
    finally:
        Path(staged).unlink(missing_ok=True)


def _active_archive(active: Path) -> Path | None:
    try:
        link = active.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISLNK(link.st_mode) or link.st_uid != os.getuid():
        raise UpdateBlocked("resident_storage_artifact_changed")
    name = os.readlink(active)
    match = _ARCHIVE_NAME.fullmatch(name)
    if not match:
        raise UpdateBlocked("resident_storage_artifact_changed")
    archive = active.parent / name
    info = archive.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_nlink != 1
        or info.st_mode & 0o077
        or not 0 < info.st_size <= 1024 * 1024
        or controller.digest(archive) != match[1]
    ):
        raise UpdateBlocked("resident_storage_artifact_changed")
    return archive


def _activate_archive(active: Path, archive: Path) -> None:
    if _active_archive(active) == archive:
        return
    with tempfile.TemporaryDirectory(dir=active.parent, prefix=".storage-launch-") as folder:
        staged = Path(folder) / active.name
        staged.symlink_to(archive.name)
        os.replace(staged, active)
        controller.sync_directory(active.parent)


def register(home: Path, config: dict, *, supervisor_locked: bool = False) -> dict:
    if sys.platform != "darwin":
        raise UpdateBlocked("resident_macos_only")
    if supervisor_locked:
        return _register_under_supervisor(home, config)
    with file_lock(home / "resident", "supervisor.lock", exclusive=True):
        return _register_under_supervisor(home, config)


def _register_under_supervisor(home: Path, config: dict) -> dict:
    root = home / "resident"
    private_root(root)
    result = volume_identity.enroll(home, supervisor_locked=True)
    contents = _artifact()
    checksum = hashlib.sha256(contents).hexdigest()
    archive = root / f"storage-identity-{checksum}.pyz"
    artifact = root / "storage-identity.pyz"

    agents = Path.home() / "Library/LaunchAgents"
    agents.mkdir(parents=True, exist_ok=True)
    plist = agents / f"{LABEL}.plist"
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True, mode=0o700)
    payload = {
        "Label": LABEL,
        "ProgramArguments": [config["python"], str(artifact), "--home", str(home)],
        "RunAtLoad": True,
        "StartInterval": 45,
        "ProcessType": "Background",
        "WorkingDirectory": str(home),
        "StandardOutPath": str(logs / "resident-storage-identity.log"),
        "StandardErrorPath": str(logs / "resident-storage-identity-error.log"),
    }
    plist_bytes = plistlib.dumps(payload)
    _already_published(plist, plist_bytes, "resident_storage_launchagent_changed")
    _publish_once(archive, contents, "resident_storage_artifact_changed")
    _activate_archive(artifact, archive)
    _publish_once(plist, plist_bytes, "resident_storage_launchagent_changed")
    domain = f"gui/{os.getuid()}"
    controller.run(["/bin/launchctl", "enable", f"{domain}/{LABEL}"])
    try:
        controller.run(["/bin/launchctl", "bootstrap", domain, str(plist)])
    except UpdateBlocked:
        registered = controller.run(["/bin/launchctl", "print", f"{domain}/{LABEL}"])
        if str(artifact) not in registered or config["python"] not in registered:
            raise UpdateBlocked("resident_storage_registration_unverified") from None
    return {**result, "launch_agent": LABEL, "artifact_sha256": checksum}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", required=True, type=Path)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        value = volume_identity.rebind(args.home)
    except MaintenanceBusy:
        log.info("resident_storage_identity_deferred")
        return 0
    except UpdateBlocked as exc:
        log.error("resident_storage_identity_blocked reason=%s", exc)
        return 1
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        log.exception("resident_storage_identity_failed")
        return 1
    if value.get("status") != "unchanged":
        print(json.dumps(value, ensure_ascii=False))
    return 0
