"""Release identities and refusal before any Docker or writer mutation."""

import gzip
import hashlib
import io
import json
import tarfile
import time
from copy import deepcopy
from types import SimpleNamespace

import pytest

from docker import release
from docker.manage import Refusal


def test_stream_hash_and_immutable_release_record(tmp_path):
    archive = tmp_path / "artifact.tar"
    archive.write_bytes(b"standard archive fixture")
    assert release.sha256_file(archive).startswith("sha256:")
    release.write_once(tmp_path / "release.json", {"id": "r0"})
    with pytest.raises(Refusal, match="record_already_sealed"):
        release.write_once(tmp_path / "release.json", {"id": "r1"})
    assert json.loads((tmp_path / "release.json").read_text()) == {"id": "r0"}


def test_archive_binds_config_identity_before_docker_load(tmp_path):
    config = json.dumps(
        {
            "os": "linux",
            "architecture": "arm64",
            "config": {"Labels": {}},
            "rootfs": {"diff_ids": []},
        }
    ).encode()
    image = "sha256:" + hashlib.sha256(config).hexdigest()
    archive = tmp_path / "image.tar"
    config_name = image[7:] + ".json"
    manifest = [{"Config": config_name, "Layers": [], "RepoTags": ["fixture:r0"]}]
    with tarfile.open(archive, "w") as stream:
        for name, payload in (
            (config_name, config),
            ("manifest.json", json.dumps(manifest).encode()),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            stream.addfile(info, io.BytesIO(payload))
    assert release.archive_identity(archive, image)["config_digest"] == image
    with pytest.raises(Refusal, match="archive_image_identity_mismatch"):
        release.archive_identity(archive, "sha256:" + "a" * 64)
    with tarfile.open(archive, "a") as stream:
        payload = json.dumps(manifest + manifest).encode()
        info = tarfile.TarInfo("manifest.json")
        info.size = len(payload)
        stream.addfile(info, io.BytesIO(payload))
    with pytest.raises(Refusal):
        release.archive_identity(archive, image)


@pytest.mark.parametrize("failure", ["gzip_tail", "member_alias"])
def test_archive_rejects_hidden_content_and_normalized_duplicates(tmp_path, failure):
    layer = b"first"
    encoded = (
        gzip.compress(layer) + gzip.compress(b"unexpected") if failure == "gzip_tail" else layer
    )
    config = json.dumps(
        {
            "os": "linux",
            "architecture": "arm64",
            "config": {"Labels": {}},
            "rootfs": {"diff_ids": ["sha256:" + hashlib.sha256(layer).hexdigest()]},
        }
    ).encode()
    image = "sha256:" + hashlib.sha256(config).hexdigest()
    config_name = image[7:] + ".json"
    entries = [
        (config_name, config),
        ("layer.tar", encoded),
        ("manifest.json", json.dumps([{"Config": config_name, "Layers": ["layer.tar"]}]).encode()),
    ]
    if failure == "member_alias":
        entries.append(("./manifest.json", b"[]"))
    path = tmp_path / "image.tar"
    with tarfile.open(path, "w") as stream:
        for name, payload in entries:
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            stream.addfile(info, io.BytesIO(payload))
    with pytest.raises(Refusal):
        release.archive_identity(path, image)


def test_manifest_platform_role_and_format_refuse_before_deploy():
    value = {"platform": "linux/arm64", "compatibility": release.CONTRACT.copy()}
    release.check_compatibility(value, value)
    for field, replacement in [("platform", "linux/amd64"), ("compatibility", {"data": "v999"})]:
        changed = {**value, field: replacement}
        with pytest.raises(Refusal):
            release.check_compatibility(value, changed)


def test_acceptance_binds_seal_controller_and_expiry():
    sealed = {"release_id": "r0", "seal": "sha256:seal", "controller_hash": "sha256:control"}
    receipt = {**sealed, "status": "PASS", "expires_at": time.time() + 30}
    release.check_acceptance(sealed, receipt)
    for change in (
        {"seal": "sha256:other"},
        {"status": "FAIL"},
        {"expires_at": 0},
        {"controller_hash": "sha256:other"},
    ):
        with pytest.raises(Refusal):
            release.check_acceptance(sealed, {**receipt, **change})


def test_plan_rejects_tamper_stale_state_and_expiration(tmp_path):
    store = release.ReleaseStore(tmp_path, "/admin", "/worktree")
    record = {"environment": "prod", "instance": "g2b-rehearsal", "purpose": "rehearsal"}
    plan = {
        "target_hash": release.canonical_hash(record),
        "expires_at": time.time() + 30,
        "environment": "prod",
        "instance": "g2b-rehearsal",
    }
    store.check_target_plan(plan, record)
    with pytest.raises(Refusal, match="stale_plan"):
        store.check_target_plan(plan, {**record, "image": "changed"})
    with pytest.raises(Refusal, match="plan_expired"):
        store.check_target_plan({**plan, "expires_at": 0}, record)
    with pytest.raises(Refusal):
        store.check_target_plan(plan, {**record, "purpose": "daily"})


@pytest.mark.parametrize("failure", ["final_ledger", "status", "end_reply"])
def test_failure_after_resume_never_stops_newly_admitted_tasks(tmp_path, monkeypatch, failure):
    store = release.ReleaseStore(tmp_path, "/admin", "/worktree")
    old = {
        "release_id": "r0",
        "seal": "old",
        "controller_hash": "old-control",
        "local_image_id": "old-image",
        "platform": "linux/arm64",
        "compatibility": release.CONTRACT,
    }
    new = {
        **old,
        "release_id": "r1",
        "seal": "new",
        "controller_hash": "new-control",
        "local_image_id": "new-image",
    }
    (tmp_path / "releases/r1").mkdir(parents=True)
    receipt = {**new, "status": "PASS", "expires_at": time.time() + 30}
    (tmp_path / "releases/r1/acceptance.json").write_text(json.dumps(receipt))
    record = {
        "environment": "prod",
        "instance": "g2b-rehearsal",
        "purpose": "rehearsal",
        "container_id": "old-container",
        "image": "old-image",
        "accepted_release": "r0",
        "accepted_history": ["r0"],
        "volumes": {key: key for key in range(5)},
        "model_store_state": "ready",
    }
    plan = {
        "id": "a" * 32,
        "environment": "prod",
        "instance": "g2b-rehearsal",
        "action": "deploy",
        "to_release": "r1",
        "controller_release": "r1",
        "controller_hash": "new-control",
        "release_seal": "new",
        "local_image_id": "new-image",
        "acceptance_hash": release.canonical_hash(receipt),
        "target_hash": release.canonical_hash(record),
        "expires_at": time.time() + 30,
    }
    stopped = []
    resumed = []
    store.manager = SimpleNamespace(
        read=lambda *args: deepcopy(record),
        verify_resources=lambda value: None,
        owned=lambda value: {"State": {"Running": True}},
        path=lambda *args: tmp_path / "ledger.json",
        stop=lambda value: stopped.append(True),
    )
    monkeypatch.setattr(store, "bound_controller", lambda identity: new)
    monkeypatch.setattr(store, "verify", lambda identity: old if identity == "r0" else new)
    monkeypatch.setattr(
        store,
        "_switch",
        lambda value, image: value.update(
            image=image["local_image_id"], container_id="new-container"
        ),
    )
    monkeypatch.setattr(store, "probe", lambda *args: True)

    def control(value, action, transaction):
        if action == "end":
            resumed.append(True)  # Concurrent new request is now permitted.
            if failure == "end_reply":
                raise Refusal("reply_unknown")
        return {"maintenance": action != "end", "idle": True}

    def atomic(path, value):
        if value.get("deployment", {}).get("state") == "accepted" and failure == "final_ledger":
            raise OSError("fsync")

    def status(value):
        if failure == "status":
            raise Refusal("status_unknown")
        return value

    monkeypatch.setattr(store, "control", control)
    monkeypatch.setattr(store, "status", status)
    monkeypatch.setattr(release.manage, "atomic_json", atomic)
    with pytest.raises(Refusal, match="RECOVERY_REQUIRED"):
        store.apply("r1", plan)
    assert resumed and stopped == []
