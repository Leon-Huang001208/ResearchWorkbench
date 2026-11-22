from __future__ import annotations

import json
import os
import plistlib
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint.resident import controller
from research_workbench_entrypoint.resident import volume_identity as volume
from research_workbench_entrypoint.resident.admission import MaintenanceBusy, file_lock
from research_workbench_entrypoint.resident.evidence import UpdateBlocked


@pytest.fixture
def resident(tmp_path, monkeypatch):
    home = tmp_path.resolve() / "rwb"
    project = tmp_path.resolve() / "project"
    data = home / "research-web"
    for directory in (project, data, home / "resident", home / "install"):
        directory.mkdir(mode=0o700, parents=True)
    home.chmod(0o700)
    artifact = home / "resident/controller.pyz"
    artifact.write_bytes(b"original frozen controller")
    artifact.chmod(0o600)
    revision = "a" * 40
    native = {
        "schema_version": 1,
        "project": str(project),
        "project_identity": [100, project.stat().st_ino],
        "artifact": str(artifact),
        "artifact_sha256": controller.digest(artifact),
        "web_port": 8088,
        "runtime_port": 3081,
        "baseline": revision,
    }
    gateway = {
        "version": 1,
        "port": 8089,
        "origin": "https://host.tail123.ts.net",
        "binding": {
            "primary_user_id": "62b9a197-1eef-46eb-86cc-3f752f487ab5",
            "home": str(home),
            "project": str(project),
            "project_identity": list(native["project_identity"]),
            "data_identity": [100, data.stat().st_ino],
            "revision": revision,
            "web_port": 8088,
            "runtime_port": 3081,
        },
    }
    controller.atomic(home / "resident/config.json", native)
    controller.atomic(
        home / "install/manifest.json", {"status": "installed", "code_commit": revision}
    )
    monkeypatch.setattr(controller, "git", lambda *args: revision)

    mount = {"device": 100, "uuid": "da16e9a4-51a5-46b3-8c86-d0fc16f7aab8"}

    def observe(path):
        info = path.lstat()
        return (
            {
                "path": str(path),
                "volume_uuid": mount["uuid"],
                "mount_point": "/System/Volumes/Data",
                "uid": os.getuid(),
                "inode": info.st_ino,
                "birthtime_ns": info.st_mtime_ns,
            },
            [mount["device"], info.st_ino],
        )

    monkeypatch.setattr(volume, "_observe_directory", observe)
    return home, project, data, gateway, mount


def read(path):
    return json.loads(path.read_bytes())


def attach(home, gateway):
    (home / "server/run").mkdir(mode=0o700, parents=True, exist_ok=True)
    (home / "server").chmod(0o700)
    controller.atomic(home / "server/resident.json", gateway)


def test_fresh_install_enrolls_without_gateway_and_never_writes_when_unchanged(resident):
    home, _, _, _, _ = resident
    with file_lock(home / "resident", "supervisor.lock", exclusive=True):
        assert volume.enroll(home, supervisor_locked=True)["status"] == "enrolled"
        anchor = home / "resident/volume-identity.json"
        before = anchor.stat().st_ino
        assert volume.rebind(home)["status"] == "unchanged"
    assert anchor.stat().st_ino == before
    assert not (home / "server").exists()


def test_reboot_rebinds_native_and_gateway_even_when_attached_after_enrollment(resident):
    home, _, _, gateway, mount = resident
    volume.enroll(home)
    attach(home, gateway)
    mount["device"] = 101
    assert volume.rebind(home) == {
        "status": "rebound",
        "changed": ["gateway", "native"],
    }
    gateway["binding"]["project_identity"][0] = 101
    gateway["binding"]["data_identity"][0] = 101
    assert read(home / "server/resident.json") == gateway
    assert read(home / "resident/config.json")["project_identity"][0] == 101
    assert (home / "resident/controller.pyz").read_bytes() == b"original frozen controller"


def test_rebind_resumes_when_interrupted_between_atomic_records(resident, monkeypatch):
    home, _, _, gateway, mount = resident
    attach(home, gateway)
    volume.enroll(home)
    mount["device"] = 101
    original = controller.atomic

    def crash_after_gateway(path, body):
        if path == home / "resident/config.json":
            raise OSError("interrupted")
        original(path, body)

    with monkeypatch.context() as patch:
        patch.setattr(controller, "atomic", crash_after_gateway)
        with pytest.raises(UpdateBlocked, match="resident_volume_rebind_failed"):
            volume.rebind(home)
    assert read(home / "server/resident.json")["binding"]["project_identity"][0] == 101
    assert read(home / "resident/config.json")["project_identity"][0] == 100
    assert volume.rebind(home) == {"status": "rebound", "changed": ["native"]}


def test_never_enrolls_from_already_stale_records(resident):
    home, _, _, gateway, mount = resident
    attach(home, gateway)
    mount["device"] = 101
    with pytest.raises(UpdateBlocked, match="resident_volume_identity_not_enrolled"):
        volume.rebind(home)
    with pytest.raises(UpdateBlocked, match="resident_volume_enrollment_identity_changed"):
        volume.enroll(home)
    assert not (home / "resident/volume-identity.json").exists()
    assert read(home / "server/resident.json") == gateway


@pytest.mark.parametrize("change", ["volume", "replaced-directory", "binding", "journal"])
def test_rebind_rejects_drift_outside_device_number(resident, change):
    home, _, data, gateway, mount = resident
    attach(home, gateway)
    volume.enroll(home)
    mount["device"] = 101
    if change == "volume":
        mount["uuid"] = "4a52ced2-b56f-45d2-9936-edab4cad30e7"
    elif change == "replaced-directory":
        data.rename(data.with_name("preserved-data"))
        data.mkdir(mode=0o700)
    elif change == "binding":
        gateway["binding"]["revision"] = "b" * 40
        attach(home, gateway)
    elif change == "journal":
        (home / "server/run/gateway-upgrade.json").symlink_to(home / "missing")
    with pytest.raises(UpdateBlocked):
        volume.rebind(home)
    assert read(home / "resident/config.json")["project_identity"][0] == 100
    assert read(home / "server/resident.json") == gateway


def test_rebind_defers_when_operator_lock_is_held(resident):
    home, _, _, gateway, mount = resident
    attach(home, gateway)
    volume.enroll(home)
    mount["device"] = 101
    with (
        file_lock(home / "server/run", "operator.lock", exclusive=True),
        pytest.raises(MaintenanceBusy, match="resident_busy"),
    ):
        volume.rebind(home)
    assert read(home / "resident/config.json")["project_identity"][0] == 100


def test_rebind_defers_when_gateway_appears_after_lock_selection(resident, monkeypatch):
    home, _, _, gateway, mount = resident
    volume.enroll(home)
    mount["device"] = 101
    original = volume._mutation_scope

    @contextmanager
    def attach_during_scope(*args, **kwargs):
        with original(*args, **kwargs) as operator_locked:
            assert operator_locked is False
            attach(home, gateway)
            yield operator_locked

    monkeypatch.setattr(volume, "_mutation_scope", attach_during_scope)
    with pytest.raises(UpdateBlocked, match="resident_volume_gateway_appeared"):
        volume.rebind(home)
    assert read(home / "resident/config.json")["project_identity"][0] == 100
    assert read(home / "server/resident.json") == gateway


def test_confirmed_non_apfs_distinguishes_local_legacy_install(tmp_path, monkeypatch):
    mount = tmp_path.resolve()
    monkeypatch.setattr(volume, "sys", SimpleNamespace(platform="darwin"))
    monkeypatch.setattr(volume, "_mount_for", lambda *_args: mount)
    monkeypatch.setattr(
        volume.subprocess,
        "check_output",
        lambda *_args, **_kwargs: plistlib.dumps(
            {"MountPoint": str(mount), "FilesystemType": "hfs"}
        ),
    )
    with pytest.raises(UpdateBlocked, match="resident_volume_not_apfs"):
        volume._observe_directory(mount)


@pytest.mark.skipif(sys.platform != "darwin", reason="requires the macOS diskutil APFS probe")
def test_live_apfs_witness_on_temporary_directory(tmp_path):
    project = tmp_path.resolve()
    result = subprocess.run(
        ["/usr/sbin/diskutil", "info", "-plist", "/System/Volumes/Data"],
        capture_output=True,
        check=False,
        timeout=5,
    )
    mount = Path("/System/Volumes/Data")
    if result.returncode or project.stat().st_dev != mount.stat().st_dev:
        pytest.skip("temporary directory is outside the internal macOS data volume")
    stable, observed = volume._observe_directory(project)
    assert stable["path"] == str(project)
    assert stable["mount_point"] == str(mount)
    assert stable["birthtime_ns"] > 0
    assert observed == [project.stat().st_dev, project.stat().st_ino]
