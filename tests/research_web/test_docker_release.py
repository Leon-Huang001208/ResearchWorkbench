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


def test_frozen_format_inventory_uses_existing_repository_sources():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    assert all((root / name).is_file() for name in release.FORMAT_SOURCES)


def test_release_uses_canonical_dsh_and_seals_hot_migrations():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    runtime = json.loads((root / "runtimes/research_web.json").read_text())
    assert release.CONTRACT["dsh"] == runtime["dsh"]["commit"]
    inventory = release.format_source_hashes(root)
    migrations = sorted((root / "services/hot/migrations").glob("*.sql"))
    assert migrations
    assert all(str(p.relative_to(root)) in inventory for p in migrations)
    assert "services/hot/package.json" in inventory


def test_hot_format_inventory_refuses_missing_or_changed_migrations(tmp_path):
    for name in release.FORMAT_SOURCES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture")
    with pytest.raises(Refusal, match="release_hot_format_inventory_missing"):
        release.format_source_hashes(tmp_path)
    migration = tmp_path / "services/hot/migrations/0001-test.sql"
    migration.parent.mkdir(parents=True)
    migration.write_text("SELECT 1;")
    first = release.format_source_hashes(tmp_path)
    migration.write_text("SELECT 2;")
    second = release.format_source_hashes(tmp_path)
    old = {
        "platform": "linux/arm64",
        "compatibility": release.CONTRACT,
        "format_source_hashes": first,
    }
    with pytest.raises(Refusal, match="release_format_compatibility_unknown"):
        release.check_compatibility(old, {**old, "format_source_hashes": second})


def test_sealed_runtime_contract_rejects_invalid_or_alias_input(tmp_path):
    contract = tmp_path / "runtime-contract.json"
    contract.write_text(json.dumps({"dsh": {"commit": release.CONTRACT["dsh"]}}))
    assert release.load_runtime_contract(contract)["dsh"]["commit"] == release.CONTRACT["dsh"]
    contract.write_text(json.dumps({"dsh": {"commit": "unknown"}}))
    with pytest.raises(Refusal, match="release_runtime_contract_invalid"):
        release.load_runtime_contract(contract)
    alias = tmp_path / "alias.json"
    alias.symlink_to(contract)
    with pytest.raises(Refusal, match="release_runtime_contract_invalid"):
        release.load_runtime_contract(alias)


def test_sealed_controller_reads_its_own_runtime_contract_without_project_imports(tmp_path):
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    control = tmp_path / "control"
    control.mkdir()
    for name in ("release.py", "manage.py"):
        (control / name).write_bytes((root / "docker" / name).read_bytes())
    (control / "runtime-contract.json").write_bytes(
        (root / "runtimes/research_web.json").read_bytes()
    )
    script = "import sys,json;sys.path.insert(0,sys.argv[1]);import release;print(json.dumps(release.CONTRACT))"
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(control)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout) == release.CONTRACT
    (control / "runtime-contract.json").unlink()
    missing = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(control)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert missing.returncode != 0
    assert "release_runtime_contract_invalid" in missing.stderr


def test_frozen_image_contains_current_hot_payload_without_starting_it():
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    dockerfile = (root / "docker/Dockerfile.release").read_text()
    assert "FROM node-runtime AS hot-builder" in dockerfile
    assert "COPY services/hot/migrations ./migrations" in dockerfile
    assert "COPY --from=hot-builder /opt/rwb/services/hot /opt/rwb/services/hot" in dockerfile
    assert "npm ci --omit=dev --ignore-scripts" in dockerfile


def test_archive_freeze_restores_public_source_directory_traversal(tmp_path):
    import os
    import stat

    archive = tmp_path / "source.tar"
    with tarfile.open(archive, "w") as stream:
        directory = tarfile.TarInfo("app/datahub")
        directory.type = tarfile.DIRTYPE
        directory.mode = 0o775
        stream.addfile(directory)
        file = tarfile.TarInfo("app/datahub/contracts.py")
        file.size = 4
        file.mode = 0o664
        stream.addfile(file, io.BytesIO(b"pass"))
    source = tmp_path / "frozen"
    source.mkdir(mode=0o700)
    prior = os.umask(0o077)
    try:
        release.freeze_source_archive(archive, source)
    finally:
        os.umask(prior)
    assert stat.S_IMODE((source / "app/datahub").stat().st_mode) == 0o755
    assert stat.S_IMODE((source / "app/datahub/contracts.py").stat().st_mode) == 0o644


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


def test_registry_selection_pins_arm64_manifest_without_publishing(tmp_path, monkeypatch):
    store = release.ReleaseStore(tmp_path, "/admin", "/worktree")
    path = tmp_path / "releases/r1"
    path.mkdir(parents=True)
    image = "sha256:" + "1" * 64
    monkeypatch.setattr(
        store, "bound_controller", lambda _: {"seal": "sealed", "local_image_id": image}
    )
    (path / "registry-descriptor.json").write_text(json.dumps({"digest": "sha256:" + "a" * 64}))
    raw = {
        "manifests": [
            {"digest": "sha256:" + "b" * 64, "platform": {"os": "linux", "architecture": "arm64"}},
            {"digest": "sha256:" + "c" * 64, "platform": {"os": "linux", "architecture": "amd64"}},
        ]
    }
    (path / "registry-raw-manifest.json").write_text(json.dumps(raw))
    selected = store.registry_selection("r1")
    assert selected["manifest_digest"] == "sha256:" + "b" * 64
    assert selected["index_digest"] == "sha256:" + "a" * 64
    assert selected["pull_reference"].endswith("@sha256:" + "b" * 64)
    raw["manifests"] = [raw["manifests"][1]]
    (path / "registry-raw-manifest.json").write_text(json.dumps(raw))
    with pytest.raises(Refusal, match="registry_platform_manifest_ambiguous"):
        store.registry_selection("r1")


def test_seal_distinguishes_daemon_identity_from_config_digest(tmp_path, monkeypatch):
    store = release.ReleaseStore(tmp_path, "/admin", "/worktree")
    path = tmp_path / "releases/r1"
    path.mkdir(parents=True)
    for name in ("source", "control", "dsh"):
        (path / name).mkdir()
    prepared = {
        "release_id": "r1",
        "frozen_tree_hash": release.tree_hash(path / "source"),
        "controller_hash": release.tree_hash(path / "control"),
        "dsh_payload_hash": release.tree_hash(path / "dsh"),
    }
    (path / "prepared.json").write_text(json.dumps(prepared))
    config, image = "sha256:" + "a" * 64, "sha256:" + "b" * 64
    (path / "build-metadata.json").write_text(
        json.dumps({"containerimage.config.digest": config, "containerimage.digest": image})
    )
    for name in ("python", "node"):
        (path / ("base-" + name + ".json")).write_text(json.dumps({"digest": image}))
    (path / "image.tar").write_bytes(b"unit-only")
    monkeypatch.setattr(release.manage, "inspect", lambda kind, reference: {"Id": image})
    monkeypatch.setattr(
        release, "archive_identity", lambda archive, expected, identity: {"config_digest": expected}
    )
    monkeypatch.setattr(
        store, "verify", lambda *args, **kwargs: json.loads((path / "release.json").read_text())
    )
    value = store.seal("r1")
    assert value["local_image_id"] == image
    assert value["config_digest"] == config
    assert value["archive_identity"]["config_digest"] == config


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
