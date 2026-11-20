"""Administrative refusal and aggregate admission tests (not runtime evidence)."""

import argparse
import hashlib
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


def handoff_fixture(tmp_path, monkeypatch):
    manager, record, expected, calls = release_fixture(tmp_path, monkeypatch)
    record["reservation_release"] = {"completed_task": "historical-task", "archive": "old.json"}
    manage.atomic_json(manager.path("stage", "candidate"), record)
    raw = manager.path("stage", "candidate").read_bytes()
    record_digest = hashlib.sha256(raw).hexdigest()
    audit = {
        "instance": record["instance"], "container_id": expected[0],
        "image": expected[1], "source_sha": expected[2], "ledger_sha256": record_digest,
        "registration_task_status": "unknown", "business_status": "INCOMPLETE",
    }
    audit_path = tmp_path / "handoff-audit.json"
    manage.atomic_json(audit_path, audit)
    options = {
        "expected_record_sha256": record_digest, "audit_name": audit_path.name,
        "expected_audit_sha256": hashlib.sha256(audit_path.read_bytes()).hexdigest(),
        "authorization": "owner-stage-handoff",
    }
    return manager, record, expected, calls, raw, options


def test_stage_handoff_default_preview_does_not_write(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    before = {path.name: path.read_bytes() for path in tmp_path.iterdir()}
    preview = manager.owner_handoff(record, expected, **options)
    assert preview["status"] == "preview" and preview["applied"] is False
    assert len(preview["plan_sha256"]) == 64
    assert {path.name: path.read_bytes() for path in tmp_path.iterdir()} == before
    assert all(call[:3] == ("docker", "ps", "-aq") for call in calls)


def test_stage_handoff_archives_exact_bytes_and_preserves_original_claims(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    # Whitespace is part of the original ledger evidence.
    raw = b"\n" + raw + b"\n"
    manager.path("stage", "candidate").write_bytes(raw)
    options["expected_record_sha256"] = hashlib.sha256(raw).hexdigest()
    audit_path = tmp_path / options["audit_name"]
    audit = json.loads(audit_path.read_bytes())
    audit["ledger_sha256"] = options["expected_record_sha256"]
    manage.atomic_json(audit_path, audit)
    options["expected_audit_sha256"] = hashlib.sha256(audit_path.read_bytes()).hexdigest()
    preview = manager.owner_handoff(record, expected, **options)
    result = manager.owner_handoff(
        record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
    )
    saved = manager.read("stage", "candidate")
    assert result["status"] == "applied" and result["applied"] is True
    assert (tmp_path / "releases" / result["archive"]).read_bytes() == raw
    assert saved["retired"] is True
    assert saved["reservation_release"] == record["reservation_release"]
    for key in record:
        assert saved[key] == record[key]
    assert saved["reservation_handoff"]["registration_task_status"] == "unknown"
    assert saved["reservation_handoff"]["business_status"] == "INCOMPLETE"
    assert "completed_task" not in saved["reservation_handoff"]
    assert all(call[:3] == ("docker", "ps", "-aq") for call in calls)


@pytest.mark.parametrize("change", ["record", "audit", "plan", "identity", "running", "shared"])
def test_stage_handoff_refuses_drift_and_active_resources(tmp_path, monkeypatch, change):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    preview = manager.owner_handoff(record, expected, **options)
    plan_digest = preview["plan_sha256"]
    if change == "record":
        manager.path("stage", "candidate").write_bytes(raw + b"\n")
    elif change == "audit":
        (tmp_path / options["audit_name"]).write_bytes(b"{}")
    elif change == "plan":
        plan_digest = "0" * 64
    elif change == "identity":
        expected = ("d" * 64, expected[1], expected[2])
    elif change == "running":
        monkeypatch.setattr(manager, "owned", lambda _: {"State": {"Running": True, "Status": "running"}})
    elif change == "shared":
        monkeypatch.setattr(manage, "command", lambda *args: record["container_id"] + "\nforeign")
    ledger_before = manager.path("stage", "candidate").read_bytes()
    with pytest.raises(manage.Refusal, match="stage_handoff_"):
        manager.owner_handoff(record, expected, **options, apply=True, expected_plan_sha256=plan_digest)
    assert manager.path("stage", "candidate").read_bytes() == ledger_before
    assert not (tmp_path / "releases").exists()


def test_stage_handoff_rechecks_volume_references_before_commit(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    preview = manager.owner_handoff(record, expected, **options)
    references = iter([record["container_id"], record["container_id"], "foreign"])
    monkeypatch.setattr(manage, "command", lambda *args: next(references))
    with pytest.raises(manage.Refusal, match="stage_handoff_"):
        manager.owner_handoff(
            record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
        )
    assert manager.path("stage", "candidate").read_bytes() == raw


def test_stage_handoff_replay_preserves_archive(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    preview = manager.owner_handoff(record, expected, **options)
    result = manager.owner_handoff(
        record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
    )
    archive = tmp_path / "releases" / result["archive"]
    before = archive.read_bytes()
    with pytest.raises(manage.Refusal, match="stage_handoff_"):
        manager.owner_handoff(
            manager.read("stage", "candidate"), expected, **options,
            apply=True, expected_plan_sha256=preview["plan_sha256"]
        )
    assert archive.read_bytes() == before == raw
    assert len(list((tmp_path / "releases").iterdir())) == 1


def test_stage_handoff_checks_running_state_after_archive(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    preview = manager.owner_handoff(record, expected, **options)
    states = iter([False, True])
    monkeypatch.setattr(manager, "owned", lambda _: {
        "State": {"Running": next(states), "Status": "exited"}
    })
    with pytest.raises(manage.Refusal, match="stage_handoff_requires_stopped_container"):
        manager.owner_handoff(
            record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
        )
    assert manager.path("stage", "candidate").read_bytes() == raw
    assert [path.read_bytes() for path in (tmp_path / "releases").iterdir()] == [raw]


def test_stage_handoff_interrupted_commit_requires_review_before_retry(tmp_path, monkeypatch):
    manager, record, expected, calls, raw, options = handoff_fixture(tmp_path, monkeypatch)
    preview = manager.owner_handoff(record, expected, **options)
    original_writer = manage.atomic_json
    monkeypatch.setattr(manage, "atomic_json", lambda *args: (_ for _ in ()).throw(OSError("commit failed")))
    with pytest.raises(OSError, match="commit failed"):
        manager.owner_handoff(
            record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
        )
    assert manager.path("stage", "candidate").read_bytes() == raw
    archives = {path.name: path.read_bytes() for path in (tmp_path / "releases").iterdir()}
    monkeypatch.setattr(manage, "atomic_json", original_writer)
    with pytest.raises(manage.Refusal, match="stage_handoff_partial_archive_requires_review"):
        manager.owner_handoff(
            record, expected, **options, apply=True, expected_plan_sha256=preview["plan_sha256"]
        )
    changed_options = dict(options, authorization="owner-stage-handoff-retry")
    changed_preview = manager.owner_handoff(record, expected, **changed_options)
    assert changed_preview["plan_sha256"] != preview["plan_sha256"]
    with pytest.raises(manage.Refusal, match="stage_handoff_partial_archive_requires_review"):
        manager.owner_handoff(
            record, expected, **changed_options, apply=True,
            expected_plan_sha256=changed_preview["plan_sha256"],
        )
    assert {path.name: path.read_bytes() for path in (tmp_path / "releases").iterdir()} == archives
    assert manager.path("stage", "candidate").read_bytes() == raw


@pytest.mark.parametrize("extra,error", [
    ([], "handoff_identity_audit_and_authorization_required"),
    (["--completed-task", "historical-task"], "handoff_identity_audit_and_authorization_required"),
    (["--apply"], "handoff_apply_requires_plan_digest"),
    (["--expected-plan-sha256", "d" * 64], "handoff_apply_requires_plan_digest"),
])
def test_stage_handoff_cli_requires_explicit_scope(extra, error):
    arguments = [] if not extra else [
        "--expected-container", "a" * 64, "--expected-image", "sha256:" + "b" * 64,
        "--expected-source", "c" * 40, "--expected-record-sha256", "d" * 64,
        "--handoff-audit", "handoff-audit.json", "--expected-audit-sha256", "e" * 64,
        "--owner-authorization", "owner-stage-handoff",
    ]
    result = subprocess.run(
        [sys.executable, manage.__file__, "stage", "candidate", "owner-handoff", *arguments, *extra],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert error in result.stderr


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


def registration_fixture(tmp_path, monkeypatch):
    manager = manage.Manager(tmp_path, "/admin", str(tmp_path))
    labels = manager.labels("stage", "candidate")
    name = "rwb-stage-candidate-" + manager.owner[:8]
    volumes = [name + "-" + key for key in ("data", "logs", "credentials", "cache")]
    state = {"volumes": volumes, "networks": [], "users": "", "contents": "",
             "volume_labels": labels, "network_labels": labels,
             "subnet": "172.30.42.0/24", "containers": {}}
    calls = []

    def inspect(kind, _identifier):
        if kind == "image":
            return {"Architecture": "arm64", "Os": "linux", "Config": {"Labels": {
                manage.PREFIX + "runtime": "docker", "org.opencontainers.image.revision": "a" * 40,
            }}}
        if kind == "volume":
            return {"Labels": state["volume_labels"]}
        if kind == "network":
            return {"Labels": state["network_labels"], "Containers": state["containers"],
                    "IPAM": {"Config": [{"Subnet": state["subnet"]}]}}
        raise AssertionError(kind)

    def command(*args):
        calls.append(args)
        if args[:3] == ("docker", "volume", "ls"):
            return "\n".join(state["volumes"])
        if args[:3] == ("docker", "network", "ls"):
            return "\n".join(state["networks"])
        if args[:3] == ("docker", "ps", "-aq"):
            return state["users"] if any(arg.startswith("volume=") for arg in args) else ""
        if args[:2] == ("docker", "run"):
            return state["contents"]
        if args[0] == "git":
            return "c" * 40
        return ""

    monkeypatch.setattr(manager, "admission", lambda *args: None)
    monkeypatch.setattr(manage, "inspect", inspect)
    monkeypatch.setattr(manage, "command", command)
    (tmp_path / "runtimes").mkdir()
    (tmp_path / "runtimes/research_web.json").write_text(json.dumps({"dsh": {"commit": "d" * 40}}))
    arguments = argparse.Namespace(environment="stage", instance="candidate", image="sha256:" + "b" * 64,
                                   port=18099, subnet=state["subnet"], resume_registration=True)
    return manager, arguments, state, calls, name


def test_registration_resume_four_empty_volumes_creates_explicit_network(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    result = manager.register(arguments)
    assert result["volumes"] == dict(zip(("data", "logs", "credentials", "cache"), state["volumes"]))
    assert result["image"] == arguments.image and result["source_sha"] == "a" * 40
    assert manager.read("stage", "candidate") == result
    assert not any(call[:3] == ("docker", "volume", "create") for call in calls)
    network = next(call for call in calls if call[:3] == ("docker", "network", "create"))
    assert network[-3:] == ("--subnet", arguments.subnet, name)
    initializers = [call for call in calls if call[:2] == ("docker", "run")]
    assert len(initializers) == 1
    assert initializers[0][-1].index("ls -A") < initializers[0][-1].index("chown")


def test_registration_resume_reuses_verified_network(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    state["networks"] = [name]
    manager.register(arguments)
    assert not any(call[:3] == ("docker", "network", "create") for call in calls)


def test_registration_without_resume_rejects_existing_resources(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    arguments.resume_registration = False
    with pytest.raises(manage.Refusal, match="resource_unregistered"):
        manager.register(arguments)
    assert not any(call[:2] == ("docker", "run") for call in calls)
    assert not manager.path("stage", "candidate").exists()


def test_registration_explicit_subnet_preserves_new_volume_path(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    arguments.resume_registration = False
    state["volumes"] = []
    manager.register(arguments)
    assert len([call for call in calls if call[:3] == ("docker", "volume", "create")]) == 4
    network = next(call for call in calls if call[:3] == ("docker", "network", "create"))
    assert network[-3:] == ("--subnet", arguments.subnet, name)


def test_registration_existing_ledger_subnet_mismatch_preserves_record(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    manager.register(arguments)
    path = manager.path("stage", "candidate")
    before = path.read_bytes()
    arguments.subnet = "172.30.43.0/24"
    with pytest.raises(manage.Refusal, match="registration_subnet_mismatch"):
        manager.register(arguments)
    assert path.read_bytes() == before


@pytest.mark.parametrize("subnet", ["172.30.42.1/24", "2001:db8::/64"])
def test_registration_rejects_invalid_ipv4_cidr_before_mutation(tmp_path, monkeypatch, subnet):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    arguments.subnet = subnet
    with pytest.raises(manage.Refusal, match="registration_ipv4_subnet_invalid"):
        manager.register(arguments)
    assert not calls


@pytest.mark.parametrize("case,code", [
    ("missing_volume", "registration_resume_requires_all_volumes"),
    ("volume_labels", "volume_ownership_mismatch"),
    ("volume_users", "registration_volume_in_use"),
    ("network_labels", "network_ownership_mismatch"),
    ("network_users", "registration_network_in_use"),
    ("network_subnet", "registration_subnet_mismatch"),
    ("contents", "registration_volumes_not_empty"),
    ("production", "registration_resume_requires_stage_and_subnet"),
    ("no_subnet", "registration_resume_requires_stage_and_subnet"),
])
def test_registration_resume_refuses_unsafe_partial_state(tmp_path, monkeypatch, case, code):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    if case == "missing_volume":
        state["volumes"] = state["volumes"][:-1]
    elif case == "volume_labels":
        state["volume_labels"] = {}
    elif case == "volume_users":
        state["users"] = "foreign"
    elif case.startswith("network_"):
        state["networks"] = [name]
        state[{"network_labels": "network_labels", "network_users": "containers",
               "network_subnet": "subnet"}[case]] = {
            "network_labels": {}, "network_users": {"foreign": {}}, "network_subnet": "172.30.43.0/24",
        }[case]
    elif case == "contents":
        state["contents"] = "registration_volumes_not_empty"
    elif case == "production":
        arguments.environment = "prod"
    elif case == "no_subnet":
        arguments.subnet = None
    with pytest.raises(manage.Refusal, match=code):
        manager.register(arguments)
    assert not manager.path("stage", "candidate").exists()
    assert not any(call[:3] == ("docker", "volume", "create") for call in calls)


def test_registration_default_rejects_existing_resources(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    arguments.resume_registration = False
    with pytest.raises(manage.Refusal, match="resource_unregistered"):
        manager.register(arguments)
    assert not any(call[:2] == ("docker", "run") for call in calls)


def test_registration_new_instance_accepts_explicit_subnet(tmp_path, monkeypatch):
    manager, arguments, state, calls, name = registration_fixture(tmp_path, monkeypatch)
    state["volumes"] = []
    arguments.resume_registration = False
    manager.register(arguments)
    assert len([call for call in calls if call[:3] == ("docker", "volume", "create")]) == 4
    network = next(call for call in calls if call[:3] == ("docker", "network", "create"))
    assert network[-3:] == ("--subnet", arguments.subnet, name)


@pytest.mark.parametrize("option", [["--subnet", "172.30.42.0/24"], ["--resume-registration"]])
def test_registration_cli_options_are_register_only(option):
    result = subprocess.run(
        [sys.executable, manage.__file__, "stage", "candidate", "status", *option],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert "subnet_and_resume_are_registration_only" in result.stderr


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
