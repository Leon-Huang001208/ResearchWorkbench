"""Administrative refusal and aggregate admission tests (not runtime evidence)."""

import argparse
import json
import subprocess
import sys
from copy import deepcopy

import pytest

from docker import manage


def release_fixture(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    record = {"environment": "stage", "instance": "candidate", "container_id": "a" * 64,
              "image": "sha256:" + "b" * 64, "source_sha": "c" * 40,
              "memory": 2 * manage.GIB, "labels": manager.labels("stage", "candidate"),
              "volumes": {"data": "preserved-data", "credentials": "preserved-secret"}}
    manage.atomic_json(manager.path("stage", "candidate"), record)
    monkeypatch.setattr(manager, "owned", lambda _: {"State": {"Running": False, "Status": "exited"}})
    calls = []
    monkeypatch.setattr(manage, "command", lambda *args: calls.append(args) or record["container_id"])
    expected = (record["container_id"], record["image"], record["source_sha"])
    return manager, record, expected, calls


def test_stage_release_preserves_container_volumes_and_original_record(tmp_path, monkeypatch):
    manager, record, expected, calls = release_fixture(tmp_path, monkeypatch)
    result = manager.release_stage(record, expected, "completed-hot-task")
    saved = manager.read("stage", "candidate")
    assert saved["retired"] is True
    assert saved["container_id"] == record["container_id"]
    assert saved["volumes"] == record["volumes"]
    assert json.loads((tmp_path / "releases" / result["archive"]).read_text()) == record
    assert all(call[:3] == ("docker", "ps", "-aq") for call in calls)
    assert (tmp_path / "releases" / result["archive"]).stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize("case,code", [
    ("running", "stage_release_requires_stopped_container"),
    ("identity", "stage_release_identity_mismatch"),
    ("production", "only_stage_reservation_release_allowed"),
    ("shared", "stage_release_volume_in_use"),
    ("archive_alias", "stage_release_archive_alias"),
    ("changed_ledger", "stage_release_ledger_changed"),
])
def test_stage_release_refuses_unsafe_target(tmp_path, monkeypatch, case, code):
    manager, record, expected, calls = release_fixture(tmp_path, monkeypatch)
    before = manager.path("stage", "candidate").read_bytes()
    if case == "running":
        monkeypatch.setattr(manager, "owned", lambda _: {"State": {"Running": True}})
    elif case == "identity":
        expected = ("other", expected[1], expected[2])
    elif case == "production":
        record["environment"] = "prod"
    elif case == "shared":
        monkeypatch.setattr(manage, "command", lambda *args: "another-container")
    elif case == "archive_alias":
        (tmp_path / "releases").symlink_to(tmp_path / "outside")
    elif case == "changed_ledger":
        record["memory"] = 1
    with pytest.raises(manage.Refusal, match=code):
        manager.release_stage(record, expected, "completed-hot-task")
    assert manager.path("stage", "candidate").read_bytes() == before
    assert all(call[:3] == ("docker", "ps", "-aq") for call in calls)


def test_stage_release_archive_failure_keeps_reservation(tmp_path, monkeypatch):
    manager, record, expected, calls = release_fixture(tmp_path, monkeypatch)
    before = manager.path("stage", "candidate").read_bytes()
    monkeypatch.setattr(manage, "atomic_json", lambda *args: (_ for _ in ()).throw(OSError("archive failed")))
    with pytest.raises(OSError, match="archive failed"):
        manager.release_stage(record, expected, "completed-hot-task")
    assert manager.path("stage", "candidate").read_bytes() == before
    assert all(call[:3] == ("docker", "ps", "-aq") for call in calls)


def test_stage_release_replay_is_refused_without_changing_archive(tmp_path, monkeypatch):
    manager, record, expected, _calls = release_fixture(tmp_path, monkeypatch)
    result = manager.release_stage(record, expected, "completed-hot-task")
    archive = tmp_path / "releases" / result["archive"]
    original = archive.read_bytes()
    with pytest.raises(manage.Refusal, match="stage_reservation_already_released"):
        manager.release_stage(manager.read("stage", "candidate"), expected, "completed-hot-task")
    assert archive.read_bytes() == original
    assert len(list((tmp_path / "releases").iterdir())) == 1


def test_stage_release_rechecks_running_state_before_commit(tmp_path, monkeypatch):
    manager, record, expected, _calls = release_fixture(tmp_path, monkeypatch)
    states = iter([False, False, True])
    monkeypatch.setattr(manager, "owned", lambda _: {"State": {"Running": next(states), "Status": "exited"}})
    with pytest.raises(manage.Refusal, match="stage_release_requires_stopped_container"):
        manager.release_stage(record, expected, "completed-hot-task")
    assert "retired" not in manager.read("stage", "candidate")


def test_stage_release_cli_requires_explicit_identity():
    result = subprocess.run(
        [sys.executable, manage.__file__, "stage", "candidate", "release-reservation"],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert "release_identity_and_completed_task_required" in result.stderr


def test_model_provisioning_rejects_running_stage_without_secret_operations(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    monkeypatch.setattr(manager, "verify_resources", lambda record: None)
    monkeypatch.setattr(manager, "owned", lambda record: {"State": {"Running": True}})
    with pytest.raises(manage.Refusal, match="stop_stage_before_model_initialization"):
        manager.enable_model_credentials({"environment": "stage", "container_id": "owned"})


def test_partial_model_initialization_is_never_reset(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    monkeypatch.setattr(manager, "verify_resources", lambda record: None)
    monkeypatch.setattr(
        manage,
        "inspect",
        lambda *args: {"Config": {"Labels": {manage.PREFIX + "model-credentials": "aes-gcm-v1"}}},
    )
    record = {
        "environment": "stage",
        "container_id": None,
        "image": "fixed",
        "model_instance": "a" * 32,
        "model_store_state": "initializing",
    }
    with pytest.raises(manage.Refusal, match="model_store_initialization_incomplete"):
        manager.enable_model_credentials(record)


def test_pool_counts_stopped_reservations_and_controller_margin(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/private/admin", "/worktree")
    monkeypatch.setattr(manage, "command", lambda *args: "")
    for index in range(2):
        (tmp_path / f"prod-person-{index}.json").write_text(
            json.dumps({"memory": 2 * manage.GIB, "container_id": None})
        )
    with pytest.raises(manage.Refusal, match="environment_pool_exceeded"):
        manager.admission("prod", 2 * manage.GIB)
    manager.admission("prod", manage.GIB)


def test_unregistered_environment_container_refuses_admission(tmp_path, monkeypatch):
    monkeypatch.setattr(manage, "command", lambda *args: "alien")
    monkeypatch.setattr(manage, "inspect", lambda *args: {"Id": "unknown"})
    with pytest.raises(manage.Refusal, match="unregistered_environment_container"):
        manage.Manager(tmp_path, "/admin", "/worktree").admission("stage", manage.GIB)


@pytest.mark.parametrize("field", ["Image", "HostConfig", "Mounts", "Config", "Id"])
def test_changed_container_authority_never_stops_or_adopts(tmp_path, monkeypatch, field):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    original = {"Id": "owned", "Image": "sha256:one", "Config": {}, "HostConfig": {}, "Mounts": []}
    changed = deepcopy(original)
    changed[field] = "changed"
    monkeypatch.setattr(manager, "verify_resources", lambda record: None)
    monkeypatch.setattr(manage, "inspect", lambda *args: changed)
    commands = []
    monkeypatch.setattr(manage, "command", lambda *args: commands.append(args))
    with pytest.raises(manage.Refusal, match="container_ownership_mismatch"):
        manager.stop({"container_id": "owned", "projection": original})
    assert commands == []


def test_mutable_image_rejected_before_resource_creation(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    monkeypatch.setattr(manager, "admission", lambda *args: None)
    with pytest.raises(manage.Refusal, match="immutable_image_id_required"):
        manager.register(
            argparse.Namespace(
                environment="stage", instance="candidate", image="latest", port=18088
            )
        )


def test_ledger_alias_rejected(tmp_path):
    (tmp_path / "stage-candidate.json").symlink_to(tmp_path / "unknown")
    with pytest.raises(manage.Refusal, match="ledger_alias"):
        manage.Manager(tmp_path, "/admin", "/worktree").read("stage", "candidate")


def test_resource_label_mismatch_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(manage, "inspect", lambda *args: {"Labels": {}})
    with pytest.raises(manage.Refusal, match="volume_ownership_mismatch"):
        manage.Manager(tmp_path, "/admin", "/worktree").verify_resources(
            {"volumes": {"data": "foreign"}, "labels": {"owner": "expected"}}
        )


def test_stage_cannot_start_during_cold_build(tmp_path, monkeypatch):
    monkeypatch.setattr(manage, "command", lambda *args: "builder-running")
    with pytest.raises(manage.Refusal, match="cold_build_active"):
        manage.Manager(tmp_path, "/admin", "/worktree").up({"environment": "stage"})


def test_docker_materialized_oom_default_preserves_identity():
    container = {
        "Id": "owned",
        "Image": "fixed",
        "Config": {},
        "Mounts": [],
        "HostConfig": {"OomKillDisable": None},
    }
    expected = manage.identity_projection(container)
    container["HostConfig"]["OomKillDisable"] = False
    assert manage.identity_projection(container) == expected
    container["HostConfig"]["OomKillDisable"] = True
    assert manage.identity_projection(container) != expected


def test_docker_materialized_empty_dns_preserves_only_default_identity():
    container = {"Id": "owned", "Image": "sha256:one", "Config": {},
                 "Mounts": [], "HostConfig": {"Dns": None}}
    expected = manage.identity_projection(container)
    container["HostConfig"]["Dns"] = []
    assert manage.identity_projection(container) == expected
    container["HostConfig"]["Dns"] = ["8.8.8.8"]
    assert manage.identity_projection(container) != expected


def test_cleanup_cannot_mutate_production(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(manage, "command", lambda *args: calls.append(args))
    with pytest.raises(manage.Refusal, match="only_dev_cleanup_allowed"):
        manage.Manager(tmp_path, "/admin", "/worktree").cleanup({"environment": "prod"})
    assert calls == []


def test_cleanup_requires_stopped_owned_dev(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", "/worktree")
    monkeypatch.setattr(manager, "verify_resources", lambda record: None)
    monkeypatch.setattr(manager, "owned", lambda record: {"State": {"Running": True}})
    calls = []
    monkeypatch.setattr(manage, "command", lambda *args: calls.append(args))
    with pytest.raises(manage.Refusal, match="stop_dev_before_cleanup"):
        manager.cleanup({"environment": "dev", "container_id": "owned"})
    assert calls == []


def test_retired_development_reservation_is_reusable(tmp_path, monkeypatch):
    (tmp_path / "dev-old.json").write_text(json.dumps({"memory": 3 * manage.GIB, "retired": True}))
    monkeypatch.setattr(manage, "command", lambda *args: "")
    manage.Manager(tmp_path, "/admin", "/worktree").admission("dev", 3 * manage.GIB)


@pytest.mark.parametrize("environment,image", [("prod", "sha256:" + "a" * 64), ("stage", "latest")])
def test_candidate_refresh_never_promotes_production_or_mutable_tag(
    tmp_path, monkeypatch, environment, image
):
    calls = []
    monkeypatch.setattr(manage, "command", lambda *args: calls.append(args))
    with pytest.raises(manage.Refusal, match="only_stage_immutable_replace_allowed"):
        manage.Manager(tmp_path, "/admin", "/worktree").replace_stage_image(
            {"environment": environment}, image
        )
    assert calls == []


def pre_model_candidate():
    volumes = {key: 'owned-' + key for key in ('data', 'logs', 'credentials', 'cache', 'model_key')}
    container = {
        'Id': 'owned', 'Image': 'sha256:' + 'a' * 64, 'Name': '/owned-stage',
        'Config': {'Env': []}, 'State': {'Running': False, 'Status': 'exited'},
        'NetworkSettings': {'Networks': {'owned-network': {}}},
        'HostConfig': {'Memory': 2 * manage.GIB, 'MemorySwap': 2 * manage.GIB,
                       'NanoCpus': 2_000_000_000, 'PidsLimit': 256, 'ReadonlyRootfs': True},
        'Mounts': [{'Destination': target, 'Name': volumes[key], 'RW': True}
                   for key, target in {'data': '/data/research-web', 'logs': '/state/logs',
                                       'credentials': '/run/rwb-secrets', 'cache': '/cache'}.items()],
    }
    record = {'environment': 'stage', 'instance': 'candidate', 'container_id': 'owned',
              'name': 'owned-stage', 'network': 'owned-network', 'memory': 2 * manage.GIB,
              'image': container['Image'], 'model_instance': 'b' * 32,
              'model_store_state': 'ready', 'volumes': volumes,
              'projection': deepcopy(container)}
    return record, container


def test_explicit_replace_of_stopped_pre_model_candidate_preserves_all_volumes(tmp_path, monkeypatch):
    record, container = pre_model_candidate()
    manager = manage.Manager(tmp_path, '/admin', '/worktree')
    image = 'sha256:' + 'c' * 64
    replacement = {'Id': image, 'Architecture': 'arm64', 'Os': 'linux',
                   'Config': {'Labels': {manage.PREFIX + 'runtime': 'docker',
                                        manage.PREFIX + 'model-credentials': 'aes-gcm-v1'}}}
    monkeypatch.setattr(manager, 'verify_resources', lambda record: None)
    monkeypatch.setattr(manage, 'inspect', lambda kind, name: container if kind == 'container'
                        else replacement if name == image else {'Config': {'Labels': {}}})
    calls = []
    monkeypatch.setattr(manage, 'command', lambda *args, **kwargs: calls.append(args))
    original_volumes = deepcopy(record['volumes'])
    with pytest.raises(manage.Refusal, match='model_master_mount_mismatch'):
        manager.owned(record)
    manager.replace_stage_image(record, image)
    assert calls == [('docker', 'rm', 'owned')]
    assert record['volumes'] == original_volumes
    assert record['previous_image'] == container['Image']
    assert record['image'] == image and record['container_id'] is None


@pytest.mark.parametrize('mutation', ['running', 'encrypted_image', 'model_env', 'wrong_projection', 'initializing'])
def test_pre_model_replace_refuses_unsafe_candidate(tmp_path, monkeypatch, mutation):
    record, container = pre_model_candidate()
    manager = manage.Manager(tmp_path, '/admin', '/worktree')
    image = 'sha256:' + 'c' * 64
    labels = {manage.PREFIX + 'runtime': 'docker', manage.PREFIX + 'model-credentials': 'aes-gcm-v1'}
    if mutation == 'running':
        container['State'].update(Running=True, Status='running')
    elif mutation == 'model_env':
        container['Config']['Env'] = ['RWB_MODEL_BACKEND=docker-encrypted']
        record['projection'] = deepcopy(container)
    elif mutation == 'wrong_projection':
        container['Image'] = 'foreign'
    elif mutation == 'initializing':
        record['model_store_state'] = 'initializing'
    monkeypatch.setattr(manager, 'verify_resources', lambda record: None)
    monkeypatch.setattr(manage, 'inspect', lambda kind, name: container if kind == 'container' else
                        {'Id': image, 'Architecture': 'arm64', 'Os': 'linux', 'Config': {'Labels': labels}}
                        if name == image else {'Config': {'Labels': labels if mutation == 'encrypted_image' else {}}})
    calls = []
    monkeypatch.setattr(manage, 'command', lambda *args, **kwargs: calls.append(args))
    with pytest.raises(manage.Refusal):
        manager.replace_stage_image(record, image)
    assert calls == []
