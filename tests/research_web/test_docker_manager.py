"""Administrative refusal and aggregate admission tests (not runtime evidence)."""

import argparse
import json
from copy import deepcopy

import pytest

from docker import manage


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
