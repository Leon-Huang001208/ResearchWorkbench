"""Recovery tests use a fake daemon; no actual Docker mutation is performed."""

import json
from pathlib import Path

import pytest

from research_workbench_entrypoint.builder_reconcile import (
    FORMAT,
    IMAGE,
    LABEL,
    VOLUME,
    BuilderReconcile,
)
from research_workbench_entrypoint.docker_resources import ResourceError
from research_workbench_entrypoint.iteration_cache import GIB, operation_lock


class Fake(BuilderReconcile):
    def __init__(self, root, project):
        super().__init__(root, project)
        self.container = None
        self.volume = None
        self.engine = "engine-one"
        self.endpoint = "unix://" + str(Path.home() / ".docker/run/docker.sock")
        self.inspect_text = "Name: rwb-dev-builder\nDriver: docker-container\nName: rwb-dev-builder0\nEndpoint: desktop-linux\n"
        self.inspect_text += 'Driver Options: cpu-period="100000" cpu-quota="200000" memory="3g" memory-swap="3g"\nStatus: inactive\nBuildKit daemon flags: --allow-insecure-entitlement=network.host\n'
        self.memory = 16 * GIB
        self.running = []
        self.stage = False
        self.active = False
        self.fail = None
        self.mutations = []

    def active_build(self):
        if self.active:
            raise ResourceError("builder_build_active")

    def call(self, *args, timeout=30):
        if (
            args[0] in {"create", "start", "stop"}
            or args[:2] == ("volume", "create")
            or "--bootstrap" in args
        ):
            self.mutations.append(args)
            if self.fail == args[0]:
                raise ResourceError("fake_failure")
        if args == ("context", "show"):
            return "desktop-linux"
        if args[:2] == ("context", "inspect"):
            return json.dumps(self.endpoint)
        if args == ("info", "--format", "{{json .}}"):
            return json.dumps(
                {"ID": self.engine, "OperatingSystem": "Docker Desktop", "OSType": "linux"}
            )
        if args == ("info", "--format", "{{.MemTotal}}"):
            return str(self.memory)
        if args == ("info", "--format", "{{.HTTPProxy}}"):
            return ""
        if args[:2] == ("buildx", "inspect"):
            return self.inspect_text
        if args[0] == "ps":
            if "-aq" in args:
                return self.container["Id"] if self.container else ""
            if "--filter" in args:
                return "stage" if self.stage else ""
            return "\n".join(self.running)
        if args[:2] == ("volume", "ls"):
            return VOLUME if self.volume else ""
        if args[:2] == ("volume", "inspect"):
            if "--format" not in args:
                return json.dumps(
                    [
                        {
                            "Name": VOLUME,
                            "CreatedAt": "2026-10-23",
                            "Driver": "local",
                            "Labels": self.volume,
                        }
                    ]
                )
            return json.dumps(self.volume)
        if args[:2] == ("volume", "create"):
            self.volume = {LABEL: str(self.root)}
            return VOLUME
        if args[0] == "inspect":
            if "--format" not in args:
                return json.dumps([self.container])
            if args[2] == "{{.HostConfig.Memory}}":
                return "0" if args[-1] == "unbounded" else str(GIB)
            assert args[2] == FORMAT
            return (
                self.container["Id"]
                + " "
                + (self.root / "builder.id").read_text().strip().split(" ", 1)[1]
            )
        if args[0] == "create":
            self.container = {
                "Id": "b" * 64,
                "State": {"Running": False},
                "Config": {
                    "Labels": {LABEL: str(self.root)},
                    "Cmd": ["--config", "/etc/buildkit/buildkitd.toml"],
                },
                "HostConfig": {"Privileged": True},
                "Mounts": [
                    {"Type": "volume", "Name": VOLUME, "Destination": "/var/lib/buildkit"},
                    {
                        "Type": "bind",
                        "Source": str(self.root / "buildkitd.toml"),
                        "Destination": "/etc/buildkit/buildkitd.toml",
                        "RW": False,
                    },
                ],
            }
            return self.container["Id"]
        if args[0] in {"start", "stop"}:
            self.container["State"]["Running"] = args[0] == "start"
            return self.container["Id"]
        raise AssertionError(args)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    for name in (
        "DOCKER_HOST",
        "DOCKER_CONTEXT",
        "DOCKER_TLS_VERIFY",
        "DOCKER_CERT_PATH",
        "BUILDX_BUILDER",
        "BUILDX_CONFIG",
        "DOCKER_CONFIG",
    ):
        monkeypatch.delenv(name, raising=False)
    root, project = tmp_path / "manager", tmp_path / "project"
    root.mkdir(mode=0o700)
    (project / "docker").mkdir(parents=True)
    config = "[worker.oci]\nmax-parallelism = 2\n"
    (project / "docker/buildkitd.toml").write_text(config)
    (root / "buildkitd.toml").write_text(config)
    (root / "builder.id").write_text(
        f"{'a' * 64} {IMAGE} {5 * GIB} {5 * GIB} 200000 100000 256 json-file 10m 3 {root}\n"
    )
    return Fake(root, project)


def test_preview_readonly_and_restore_stopped(manager):
    preview = manager.preview()
    assert not manager.mutations
    assert "does not prove" in preview["acknowledgement"]
    result = manager.apply(preview["fingerprint"])
    assert result["status"] == "restored_stopped"
    assert not manager.container["State"]["Running"]
    assert (manager.root / "builder.id").read_text().startswith("b" * 64)
    archive = manager.root / "builder-reconcile" / preview["fingerprint"]
    assert (archive / "builder.id").read_text().startswith("a" * 64)
    assert json.loads((archive / "journal.json").read_text())["phase"] == "complete"
    mutations = list(manager.mutations)
    assert manager.apply(manager.preview()["fingerprint"])["status"] == "healthy"
    assert manager.mutations == mutations


@pytest.mark.parametrize(
    "change,code",
    [
        (lambda m: setattr(m, "endpoint", "tcp://remote:2375"), "builder_socket_changed"),
        (
            lambda m: setattr(
                m, "inspect_text", m.inspect_text.replace("docker-container", "docker")
            ),
            "builder_binding_changed",
        ),
        (
            lambda m: setattr(
                m, "inspect_text", m.inspect_text.replace("rwb-dev-builder0", "other0")
            ),
            "builder_binding_changed",
        ),
        (
            lambda m: setattr(m, "volume", {LABEL: str(m.root)}),
            "builder_resources_partially_missing",
        ),
        (lambda m: setattr(m, "memory", 6 * GIB), "builder_memory_gate"),
        (lambda m: setattr(m, "stage", True), "builder_stage_active"),
        (lambda m: setattr(m, "running", ["unbounded"]), "builder_unbounded_service"),
        (lambda m: setattr(m, "active", True), "builder_build_active"),
    ],
)
def test_failed_states_do_not_mutate(manager, change, code):
    change(manager)
    with pytest.raises(ResourceError, match=code):
        manager.preview()
    assert not manager.mutations


@pytest.mark.parametrize("field,value", [("engine", "engine-two"), ("memory", 15 * GIB)])
def test_changed_preview_rejected(manager, field, value):
    fingerprint = manager.preview()["fingerprint"]
    setattr(manager, field, value)
    with pytest.raises(ResourceError, match="builder_preview_changed"):
        manager.apply(fingerprint)
    assert not manager.mutations


def test_failure_preserves_archive_and_explicit_recovery(manager):
    fingerprint = manager.preview()["fingerprint"]
    manager.fail = "create"
    with pytest.raises(ResourceError, match="fake_failure"):
        manager.apply(fingerprint)
    assert manager.volume
    archive = manager.root / "builder-reconcile" / fingerprint
    assert json.loads((archive / "journal.json").read_text())["phase"] == "volume_created"
    manager.fail = None
    assert manager.apply(fingerprint, recover=True)["status"] == "restored_stopped"


def test_recovery_different_engine_rejected(manager):
    fingerprint = manager.preview()["fingerprint"]
    manager.fail = "create"
    with pytest.raises(ResourceError):
        manager.apply(fingerprint)
    manager.engine = "engine-two"
    before = len(manager.mutations)
    with pytest.raises(ResourceError, match="builder_recovery_binding_changed"):
        manager.apply(fingerprint, recover=True)
    assert len(manager.mutations) == before


def test_lock_busy_and_aliases(manager):
    with (
        operation_lock(manager.root),
        pytest.raises(ResourceError, match="docker_operation_busy"),
        operation_lock(manager.root),
    ):
        pytest.fail("entered busy lock")
    record = manager.root / "builder.id"
    original = record.read_text()
    record.unlink()
    target = manager.root / "other"
    target.write_text(original)
    record.symlink_to(target)
    with pytest.raises(ResourceError, match="builder_record_unsafe"):
        manager.preview()


def test_environment_override_rejected(manager, monkeypatch):
    monkeypatch.setenv("DOCKER_HOST", "unix:///other.sock")
    with pytest.raises(ResourceError, match="builder_environment_override"):
        manager.preview()


def test_running_healthy_builder_refused(manager):
    manager.apply(manager.preview()["fingerprint"])
    manager.container["State"]["Running"] = True
    before = len(manager.mutations)
    with pytest.raises(ResourceError, match="builder_running"):
        manager.preview()
    assert len(manager.mutations) == before


@pytest.mark.parametrize("target", ["container", "volume"])
def test_foreign_same_name_resources_refused(manager, target):
    manager.apply(manager.preview()["fingerprint"])
    if target == "container":
        manager.container["Config"]["Labels"] = {LABEL: "other-manager"}
    else:
        manager.volume = {LABEL: "other-manager"}
    before = len(manager.mutations)
    with pytest.raises(ResourceError, match="builder_resource_identity_changed"):
        manager.preview()
    assert len(manager.mutations) == before


def test_failed_bootstrap_recovery_stops_only_created_container(manager):
    fingerprint = manager.preview()["fingerprint"]
    original_call = manager.call

    def fail_bootstrap(*args, **kwargs):
        if "--bootstrap" in args:
            raise ResourceError("bootstrap_failed")
        return original_call(*args, **kwargs)

    manager.call = fail_bootstrap
    with pytest.raises(ResourceError, match="bootstrap_failed"):
        manager.apply(fingerprint)
    assert manager.container["State"]["Running"]
    manager.call = original_call
    assert manager.apply(fingerprint, recover=True)["status"] == "restored_stopped"
    stops = [args for args in manager.mutations if args[0] == "stop"]
    assert all(args[-1] == "b" * 64 for args in stops)


def test_failed_transaction_without_identity_never_adopts_resource(manager):
    fingerprint = manager.preview()["fingerprint"]
    manager.fail = "create"
    with pytest.raises(ResourceError):
        manager.apply(fingerprint)
    manager.fail = None
    manager.call("create")
    before = len(manager.mutations)
    with pytest.raises(ResourceError, match="builder_recovery_unknown_resources"):
        manager.apply(fingerprint, recover=True)
    assert len(manager.mutations) == before


@pytest.mark.parametrize(
    "process",
    [
        "docker --context desktop-linux buildx build --builder rwb-dev-builder .",
        "docker --context desktop-linux build .",
        "docker buildx --builder rwb-dev-builder build .",
        "docker -H unix:///var/run/docker.sock build .",
        "/usr/local/lib/docker/cli-plugins/docker-buildx --builder rwb-dev-builder bake",
        "docker --context=desktop-linux buildx build .",
    ],
)
def test_real_process_probe_detects_global_options(manager, monkeypatch, process):
    from types import SimpleNamespace

    monkeypatch.setattr(
        "research_workbench_entrypoint.builder_reconcile.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=process),
    )
    with pytest.raises(ResourceError, match="builder_build_active"):
        BuilderReconcile.active_build(manager)


def test_process_probe_ignores_own_shell_command_text(manager, monkeypatch):
    from types import SimpleNamespace

    process = '/bin/bash -lc python -c "probe docker --context desktop-linux buildx build"'
    monkeypatch.setattr(
        "research_workbench_entrypoint.builder_reconcile.subprocess.run",
        lambda *args, **kwargs: SimpleNamespace(stdout=process),
    )
    BuilderReconcile.active_build(manager)


@pytest.mark.parametrize("changed", ["volume", "record", "stage", "capacity", "active"])
def test_recover_validates_all_gates_before_stop(manager, changed):
    fingerprint = manager.preview()["fingerprint"]
    original_call = manager.call

    def fail_bootstrap(*args, **kwargs):
        if "--bootstrap" in args:
            raise ResourceError("bootstrap_failed")
        return original_call(*args, **kwargs)

    manager.call = fail_bootstrap
    with pytest.raises(ResourceError, match="bootstrap_failed"):
        manager.apply(fingerprint)
    manager.call = original_call
    assert manager.container["State"]["Running"]
    if changed == "volume":
        # Same labels, different creation identity must be rejected before stop.
        original_volume_identity = manager.volume_identity
        manager.volume_identity = lambda: {**original_volume_identity(), "CreatedAt": "changed"}
    elif changed == "record":
        record = manager.root / "builder.id"
        record.write_text(record.read_text().replace("a" * 64, "c" * 64))
    elif changed == "stage":
        manager.stage = True
    elif changed == "capacity":
        manager.memory = 6 * GIB
    else:
        manager.active = True
    before = list(manager.mutations)
    with pytest.raises(ResourceError):
        manager.apply(fingerprint, recover=True)
    assert manager.mutations == before
    assert manager.container["State"]["Running"]
