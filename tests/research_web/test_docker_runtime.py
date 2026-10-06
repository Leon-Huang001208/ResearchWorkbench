"""Host runtime control uses bounded subprocesses and verified ownership."""

import json
import os
import socket
import subprocess
import signal
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint.runtime_mode import RuntimeModeStore


class RecordingRunner:
    def __init__(self):
        self.calls = []
        self.failure = None
        self.container = None
        self.on_stop = None

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        command = tuple(argv)
        if "up" in command and self.container:
            files = [argv[index + 1] for index, value in enumerate(argv[:-1]) if value == "-f"]
            if len(files) > 1:
                overlay = json.loads(Path(files[-1]).read_text())
                self.container["launch"] = overlay["services"]["research-web"]["labels"]["io.research-workbench.launch"]
        if self.failure and self.failure[0] in command:
            if isinstance(self.failure[1], Exception):
                raise self.failure[1]
            return subprocess.CompletedProcess(argv, 1, "", "SECRET error")
        output = ""
        if command[1:2] == ("info",):
            output = '"aarch64"'
        elif command[1:3] == ("image", "inspect"):
            output = json.dumps({"id": "sha256:" + "b" * 64, "runtime": "docker"})
        elif command[1:2] == ("ps",):
            output = self.container["id"] if self.container else ""
        elif command[1:3] == ("container", "inspect"):
            output = json.dumps(self.container)
        elif command[1:2] == ("stop",):
            self.container["running"] = False
            if self.on_stop:
                self.on_stop()
        elif command[1:2] == ("rm",):
            self.container = None
        return subprocess.CompletedProcess(argv, 0, output, "")


@pytest.fixture
def available_ports():
    with socket.socket() as web, socket.socket() as runtime:
        web.bind(("127.0.0.1", 0))
        runtime.bind(("127.0.0.1", 0))
        return web.getsockname()[1], runtime.getsockname()[1]


@pytest.fixture
def runtime(tmp_path, available_ports):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    record = RuntimeModeStore(home).write("docker")
    runner = RecordingRunner()
    controller = DockerRuntime(tmp_path, home, runner=runner, ports=available_ports)
    from scripts.setup_web import _docker_manifest
    (tmp_path / "requirements").mkdir()
    (tmp_path / "requirements/web.lock").write_text("locked")
    (tmp_path / "compose.yaml").write_text("services: {}")
    manifest = home / "install/docker-manifest.json"
    manifest.write_text(json.dumps(_docker_manifest(tmp_path, "sha256:" + "b" * 64)))
    manifest.chmod(0o600)
    return controller, runner, record


def owned(controller, runner):
    runner.container = {
        "id": "c" * 64,
        "image": "sha256:" + "b" * 64,
        "project": controller.project_name,
        "service": "research-web",
        "installation": controller.installation_id,
        "runtime": "docker",
        "working_dir": str(controller.project_root),
        "running": True,
        "state": "running",
        "health": "healthy",
        "ports": {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(controller.ports[0])}]},
        "mounts": [
            {"Type": "bind", "Source": str(controller.data_dir), "Destination": "/data/research-web"},
            {"Type": "bind", "Source": str(controller.state_dir), "Destination": "/state"},
            {"Type": "bind", "Source": str(controller.credential_dir), "Destination": "/run/rwb-secrets"},
            {"Type": "tmpfs", "Source": "", "Destination": "/tmp"},
            {"Type": "tmpfs", "Source": "", "Destination": "/home/rwb"},
        ],
    }


@pytest.mark.parametrize("existing", [False, True])
def test_fix1_origin_commit_failure_cleans_exact_attempt(runtime, monkeypatch, existing):
    from app.research_web.control_origin import ControlOriginError, ControlOriginTransaction
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    origin = "http://127.0.0.1:48271"
    controller.endpoint_store.publish("native", 48271, 48272, expected=None)
    load_control(controller.data_dir, origin)
    load_mcp(controller.data_dir, origin)
    original = [(controller.data_dir / ".control" / name).read_bytes()
                for name in ("datahub.json", "mcp-runtime.json")]
    if existing:
        owned(controller, runner)
        runner.container.update(running=False, state="exited", launch="existing-launch")
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def launch(argv, **kwargs):
        if "up" in argv:
            if existing:
                runner.container.update(running=True, state="running")
            else:
                owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = launch
    def refuse(self):
        raise ControlOriginError("control_origin_changed")
    monkeypatch.setattr(ControlOriginTransaction, "commit", refuse)
    report = controller.start(open_browser=False)
    assert report["issues"] == ["control_origin_changed"], report
    if existing:
        assert runner.container and not runner.container["running"]
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)
    else:
        assert runner.container is None
    assert controller.endpoint_store.read("docker") is None
    assert [(controller.data_dir / ".control" / name).read_bytes()
            for name in ("datahub.json", "mcp-runtime.json")] == original


def test_fix1_manifest_same_bytes_replacement_is_not_rollback_owned(runtime, monkeypatch):
    from scripts import setup_web
    controller, runner, current = runtime
    installer = setup_web.DockerRuntime(controller.project_root, controller.home, runner=runner)
    path = controller.home / "install/docker-manifest.json"
    manifest = setup_web._docker_manifest(controller.project_root, "sha256:" + "b" * 64)
    replacement = path.with_name("replacement.json")
    def replace_then_fail():
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(path)
        retained.append(path.stat().st_ino)
        raise RuntimeError("fixture_commit_failure")
    retained = []
    monkeypatch.setattr(installer, "_commit_candidate", replace_then_fail)
    with pytest.raises(RuntimeError, match="docker_install_summary_recovery_unverified"):
        installer._publish_selection(installer.store, current, manifest)
    assert path.stat().st_ino == retained[0]


def test_fix1_native_bridge_missing_environment_and_ledger_refuses_existing_root_listener(runtime):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, _runner, _record = runtime
    controller.data_dir.mkdir(mode=0o700)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", controller.ports[0]))
        listener.listen()
        report = NativeRuntime(controller.project_root, controller.home, ports=controller.ports).status()
        assert report["issues"] == ["runtime_ownership_unknown"], report


@pytest.mark.parametrize("replacement", ["launch", "image", "installation", "mount"])
def test_fix1_started_existing_cleanup_refuses_replaced_identity(runtime, monkeypatch, replacement):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container.update(running=False, state="exited", launch="old-launch")
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def launch(argv, **kwargs):
        if "up" in argv:
            runner.container.update(running=True, state="running")
        return runner(argv, **kwargs)
    def fail_ready(*args, **kwargs):
        if replacement == "mount":
            runner.container["mounts"][0]["Source"] = "/foreign"
        else:
            runner.container[replacement] = "foreign"
        raise ControlError("docker_services_unhealthy")
    controller.runner = launch
    monkeypatch.setattr(controller, "_wait_ready", fail_ready)
    report = controller.start(open_browser=False)
    assert "docker_rollback_unverified" in report["issues"], report
    assert runner.container["running"]
    assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls)


def test_compose_identity_and_minimal_environment(runtime, monkeypatch):
    controller, runner, record = runtime
    monkeypatch.setenv("API_KEY", "SECRET")
    monkeypatch.setenv("COMPOSE_FILE", "/foreign.yaml")
    assert controller.compose_prefix == (
        "docker", "compose", "--project-name", "rwb-" + record.installation_id[:12],
        "--project-directory", str(controller.project_root),
        "-f", str(controller.project_root / "compose.yaml"),
    )
    assert controller.preflight()["ok"]
    for argv, options in runner.calls:
        assert isinstance(argv, list)
        assert options["cwd"] == controller.project_root
        assert options["timeout"] > 0
        assert options["max_output"] <= 65536
        assert "API_KEY" not in options["env"]
        assert "COMPOSE_FILE" not in options["env"]
        assert "SECRET" not in json.dumps(options["env"])
        assert not any(".Config.Env" in part for part in argv)


def test_docker_doctor_allowlisted_health_and_capabilities(runtime):
    controller, runner, record = runtime
    owned(controller, runner)
    for directory in (controller.data_dir, controller.state_dir, controller.credential_dir):
        directory.mkdir(parents=True, mode=0o700)
    report = controller.doctor()
    assert report["ok"] and report["runtime_mode"] == "docker"
    assert report["engine"]["ready"] and report["compose"]["ready"]
    assert report["container"]["state"] == "running"
    assert len(report["container"]["ownership_id"]) == 64
    assert report["data"]["ready"] and report["volumes"]["verified"]
    assert report["ports"]["verified"]
    assert report["python"]["applicable"] is False
    assert report["cjpy"]["applicable"] is False
    assert report["capabilities"]["office"]["status"] == "unavailable_in_docker"
    assert report["services"]["runtime"]["pid"] is None
    assert report["dsh"]["ready"] is True
    assert report["dsh"]["build_verified"] is True
    raw = json.dumps(report)
    assert str(controller.home) not in raw and str(controller.project_root) not in raw
    assert record.installation_id not in raw
    assert "Env" not in raw and "Cookie" not in raw


@pytest.mark.parametrize("health,code", [("unhealthy", "docker_services_unhealthy"),
                                       ("starting", "docker_ready_timeout")])
def test_start_existing_unhealthy_fails_without_removing(runtime, health, code):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["health"] = health
    report = controller.start(open_browser=False, wait_timeout=0)
    assert report["issues"] == [code]
    assert not any("rm" in argv for argv, _ in runner.calls)


def test_public_start_requires_accepted_manifest(runtime):
    controller, runner, _ = runtime
    path = controller.home / "install/docker-manifest.json"
    if path.exists():
        path.unlink()
    assert controller.start(open_browser=False)["issues"] == ["docker_manifest_missing"]
    assert not any("up" in argv for argv, _ in runner.calls)


def test_start_waits_for_delayed_health(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    monkeypatch.setattr(controller, "_ports_free", lambda: None)
    sleeps = []
    monkeypatch.setattr(time, "sleep", sleeps.append)
    health = iter(("starting", "starting", "healthy"))

    def launch(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        if argv[1:3] == ["container", "inspect"]:
            runner.container["health"] = next(health, "healthy")
        return runner(argv, **kwargs)

    controller.runner = launch
    report = controller.start(open_browser=False)
    assert report["ok"] and report["services"]["runtime"]["healthy"]
    assert sleeps == [0.25]
    up_options = next(options for argv, options in runner.calls if "up" in argv)
    assert up_options["env"]["RWB_IMAGE"] == "sha256:" + "b" * 64


@pytest.mark.parametrize("health,running,code", [
    ("unhealthy", True, "docker_services_unhealthy"),
    ("starting", False, "docker_start_failed"),
    ("starting", True, "docker_ready_timeout"),
])
@pytest.mark.parametrize("foreign_on_rollback", [False, True])
def test_start_late_failure_rolls_back_only_verified_new_container(
    runtime, monkeypatch, health, running, code, foreign_on_rollback
):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    monkeypatch.setattr(controller, "_ports_free", lambda: None)
    inspections = []

    def launch(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
            runner.container.update(health=health, running=running,
                                    state="running" if running else "exited")
        if argv[1:3] == ["container", "inspect"]:
            inspections.append(True)
            if foreign_on_rollback and len(inspections) == 3:
                runner.container["installation"] = "foreign"
        return runner(argv, **kwargs)

    controller.runner = launch
    report = controller.start(open_browser=False, wait_timeout=0)
    assert report["issues"] == ([code, "docker_rollback_failed"] if foreign_on_rollback else [code])
    removals = [argv for argv, _ in runner.calls if argv[1:2] == ["rm"]]
    assert removals == ([] if foreign_on_rollback else [["docker", "rm", "--force", "c" * 64]])
    assert controller.data_dir.is_dir() and controller.credential_dir.is_dir()


@pytest.mark.parametrize("mutation,code", [
    ("json", "docker_manifest_invalid"), ("symlink", "docker_manifest_invalid"),
    ("hardlink", "docker_manifest_invalid"), ("large", "docker_manifest_invalid"),
    ("lock", "docker_build_contract_mismatch"), ("compose", "docker_build_contract_mismatch"),
    ("dsh", "docker_build_contract_mismatch"),
])
def test_accepted_manifest_fails_closed(runtime, mutation, code):
    controller, runner, _ = runtime
    path = controller.home / "install/docker-manifest.json"
    if mutation == "json":
        path.write_text("{invalid")
    elif mutation == "large":
        path.write_text(" " * 17000)
    elif mutation in ("symlink", "hardlink"):
        other = path.with_name("other.json")
        path.rename(other)
        path.symlink_to(other) if mutation == "symlink" else os.link(other, path)
    elif mutation in ("lock", "compose"):
        (controller.project_root / ("requirements/web.lock" if mutation == "lock" else "compose.yaml")).write_text("changed")
    else:
        value = json.loads(path.read_text())
        value["dsh_commit"] = "0" * 40
        path.write_text(json.dumps(value))
    assert controller.start(open_browser=False)["issues"] == [code]
    assert not any("up" in argv for argv, _ in runner.calls)


def test_overwritten_mutable_tag_cannot_change_accepted_image(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)

    def retagged(argv, **kwargs):
        if argv[1:3] == ["image", "inspect"] and not argv[-1].startswith("sha256:"):
            return subprocess.CompletedProcess(argv, 0, json.dumps({"id": "sha256:" + "a" * 64, "runtime": "docker"}), "")
        return runner(argv, **kwargs)

    controller.runner = retagged
    assert controller.start(open_browser=False)["ok"]
    assert all(argv[-1].startswith("sha256:") for argv, _ in runner.calls
               if argv[1:3] == ["image", "inspect"])


def test_doctor_rejects_container_outside_accepted_image(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["image"] = "sha256:" + "a" * 64

    def immutable(argv, **kwargs):
        if argv[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(argv, 0, json.dumps({"id": argv[-1], "runtime": "docker"}), "")
        return runner(argv, **kwargs)

    controller.runner = immutable
    assert controller.doctor()["issues"] == ["docker_image_mismatch"]


def test_candidate_does_not_override_public_missing_manifest(runtime):
    controller, _, _ = runtime
    controller._candidate_image = "sha256:" + "b" * 64
    (controller.home / "install/docker-manifest.json").unlink()
    assert controller.start(open_browser=False)["issues"] == ["docker_manifest_missing"]


@pytest.mark.parametrize("failure", ["none", "unhealthy", "publish", "no_start", "race", "up_exit", "up_timeout"])
def test_explicit_repair_disposes_only_stopped_owned_container_and_keeps_fallback(
    runtime, monkeypatch, failure
):
    from scripts import setup_web
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container.update(running=False, state="exited")
    path = controller.home / "install/docker-manifest.json"
    previous = path.read_bytes()
    candidate_image = "sha256:" + "a" * 64
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    monkeypatch.setattr(setup_web, "port_busy", lambda port: False)

    def launch(argv, **kwargs):
        if argv[1:3] == ["image", "inspect"]:
            identity = argv[-1] if argv[-1].startswith("sha256:") else candidate_image
            return subprocess.CompletedProcess(argv, 0, json.dumps({"id": identity, "runtime": "docker"}), "")
        if "up" in argv:
            owned(installer, runner)
            runner.container.update(id="d" * 64, image=kwargs["env"]["RWB_IMAGE"])
            if failure == "unhealthy" and runner.container["image"] == candidate_image:
                runner.container["health"] = "unhealthy"
            if failure in ("up_exit", "up_timeout") and runner.container["image"] == candidate_image:
                runner(argv, **kwargs)
                if failure == "up_timeout":
                    from research_workbench_entrypoint.docker_runtime import ControlError
                    raise ControlError("runtime_command_timeout")
                return subprocess.CompletedProcess(argv, 1, "", "fixture up failure")
        if argv[1:2] == ["rm"] and "--force" not in argv and failure == "race":
            runner.container.update(running=True, state="running")
            runner.calls.append((argv, kwargs))
            return subprocess.CompletedProcess(argv, 1, "", "container is running")
        return runner(argv, **kwargs)

    installer = setup_web.DockerRuntime(controller.project_root, controller.home,
                                        runner=launch, ports=controller.ports)
    monkeypatch.setattr(installer, "_ports_free", lambda: None)
    if failure == "publish":
        def fail_publish(*args):
            raise RuntimeError("injected_publish_failure")
        monkeypatch.setattr(setup_web, "_write_docker_manifest", fail_publish)
    if failure in ("unhealthy", "publish", "race", "up_exit", "up_timeout"):
        with pytest.raises(RuntimeError):
            installer.install(repair=True)
        assert path.read_bytes() == previous
        if failure != "race":
            assert installer.start(open_browser=False)["ok"]
            assert runner.container["image"] == "sha256:" + "b" * 64
        else:
            assert runner.container["id"] == "c" * 64 and runner.container["running"]
    else:
        assert installer.install(repair=True, start=failure != "no_start")["image_id"] == candidate_image
    removals = [argv for argv, _ in runner.calls if argv[1:2] == ["rm"]]
    assert ["docker", "rm", "c" * 64] in removals
    assert not any("--force" in argv and argv[-1] == "c" * 64 for argv in removals)
    if failure == "no_start":
        assert not any("up" in argv for argv, _ in runner.calls)


def test_repair_reinspection_refuses_concurrent_start_before_rm(runtime, monkeypatch):
    from research_workbench_entrypoint.docker_runtime import ControlError
    controller, runner, record = runtime
    owned(controller, runner)
    runner.container.update(running=False, state="exited")
    original = controller._inspect
    calls = []

    def inspect(identity):
        calls.append(identity)
        if len(calls) == 2:
            runner.container.update(running=True, state="running")
        return original(identity)

    monkeypatch.setattr(controller, "_inspect", inspect)
    with pytest.raises(ControlError, match="runtime_stop_current_required"):
        controller._dispose_stopped_for_repair(record)
    assert not any(argv[1:2] == ["rm"] for argv, _ in runner.calls)


@pytest.mark.parametrize("after", ["owned", "foreign", "image", "concurrent", "unreadable", "existing", "rm_failure"])
@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_up_created_then_failed_recovers_only_this_launch(runtime, monkeypatch, after, failure):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError
    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    monkeypatch.setattr(controller, "_ports_free", lambda: None)
    if after == "existing":
        owned(controller, runner)
        runner.container.update(running=False, state="exited")
    failed = []

    def launch(argv, **kwargs):
        if "up" in argv:
            if after != "existing":
                owned(controller, runner)
            runner(argv, **kwargs)
            if after == "foreign":
                runner.container["installation"] = "foreign"
            elif after == "image":
                runner.container["image"] = "sha256:" + "a" * 64
            elif after == "concurrent":
                runner.container["launch"] = "different-launch"
            failed.append(True)
            if failure == "timeout":
                raise ControlError("runtime_command_timeout")
            return subprocess.CompletedProcess(argv, 1, "", "fixture up failure")
        if after == "unreadable" and failed and argv[1:2] == ["ps"]:
            raise ControlError("docker_status_failed")
        if after == "rm_failure" and argv[1:2] == ["rm"]:
            runner.calls.append((argv, kwargs))
            raise ControlError("docker_rollback_failed")
        return runner(argv, **kwargs)

    controller.runner = launch
    report = controller.start(open_browser=False)
    original = "runtime_command_timeout" if failure == "timeout" else "docker_start_failed"
    assert report["issues"][0] == original
    up = next(argv for argv, _ in runner.calls if "up" in argv)
    assert "--no-recreate" in up
    overlays = [up[index + 1] for index, value in enumerate(up[:-1]) if value == "-f"][1:]
    assert len(overlays) == (0 if after == "existing" else 1)
    assert all(not Path(path).exists() for path in overlays)
    removals = [argv for argv, _ in runner.calls if argv[1:2] == ["rm"]]
    if after == "owned":
        assert removals == [["docker", "rm", "--force", "c" * 64]]
        assert runner.container is None
    elif after == "rm_failure":
        assert report["issues"] == [original, "docker_rollback_failed"]
        assert len(removals) == 1 and runner.container is not None
        assert controller._created_container is None
        controller._rollback_created()
        assert len([argv for argv, _ in runner.calls if argv[1:2] == ["rm"]]) == 1
    else:
        assert removals == [] and runner.container is not None
        if after != "existing":
            assert report["issues"] == [original, "docker_rollback_unverified"]


@pytest.mark.parametrize("health", ["unhealthy", "starting", "none"])
def test_docker_doctor_fails_unhealthy_core(runtime, health):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["health"] = health
    report = controller.doctor()
    assert not report["ok"]
    assert "docker_services_unhealthy" in report["issues"]


@pytest.mark.parametrize("state", ["paused", "restarting"])
def test_docker_doctor_fails_nonrunnable_container_with_stale_health(runtime, state):
    controller, runner, _ = runtime
    owned(controller, runner)
    for path in (controller.data_dir, controller.state_dir, controller.credential_dir):
        path.mkdir(parents=True, mode=0o700)
    runner.container["state"] = state
    report = controller.doctor()
    assert not report["ok"]
    assert "docker_services_unhealthy" in report["issues"]
    assert all(not service["healthy"] for service in report["services"].values())


def test_docker_doctor_stopped_and_missing_data_not_ready(runtime):
    controller, _, _ = runtime
    report = controller.doctor()
    assert not report["ok"]
    assert "docker_container_absent" in report["issues"]
    assert "docker_data_unavailable" in report["issues"]


def test_windows_credential_mount_fails_closed_before_creation(runtime, monkeypatch):
    import research_workbench_entrypoint.docker_runtime as module
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    monkeypatch.setattr(module.sys, "platform", "win32")
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    report = controller.start(open_browser=False)
    assert report["issues"] == ["docker_credentials_acl_unverified"]
    assert not controller.credential_dir.exists()
    assert not any("up" in argv for argv, _ in runner.calls)


@pytest.mark.parametrize("tail", [-1, 10001, True])
def test_docker_log_limits_refuse_before_read(runtime, tail):
    controller, runner, _ = runtime
    assert controller.logs(tail=tail) == 1
    assert not runner.calls


def test_docker_logs_use_bounded_tail_and_explicit_follow(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    assert controller.logs(tail=17, follow=True) == 0
    argv, options = runner.calls[-1]
    assert argv[argv.index("--tail") + 1] == "17" and "--follow" in argv
    assert options["timeout"] <= 300 and options["max_output"] <= 65536


@pytest.mark.parametrize("bindings", [{}, {"8088/tcp": [{"HostIp": "0.0.0.0", "HostPort": "18088"}]},
                                      {"3081/tcp": [{"HostIp": "127.0.0.1", "HostPort": "13081"}]}])
def test_docker_doctor_refuses_wrong_port_bindings(runtime, bindings):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["ports"] = bindings
    assert "docker_ports_mismatch" in controller.doctor()["issues"]


def test_docker_logs_revalidate_immutable_container_before_read(runtime, monkeypatch):
    controller, runner, _ = runtime
    owned(controller, runner)
    original = controller._containers
    def replaced():
        values = original()
        runner.container["installation"] = "foreign"
        return values
    monkeypatch.setattr(controller, "_containers", replaced)
    assert controller.logs() == 1
    assert not any("logs" in argv for argv, _ in runner.calls)


def test_bounded_stream_redacts_credentials_split_across_chunks(tmp_path, monkeypatch):
    import io
    from research_workbench_entrypoint.docker_runtime import run_bounded
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    command = "import sys,time;sys.stdout.write('Coo');sys.stdout.flush();time.sleep(.05);print('kie: fake-secret');print('ready')"
    run_bounded([sys.executable, "-c", command], cwd=tmp_path, env={"PATH": os.defpath}, timeout=2, stream=True)
    assert "fake-secret" not in output.getvalue() and "ready" in output.getvalue()


@pytest.mark.parametrize("control", ["\x00", "\x1b", "\x07", "\x1c", "\r", "\t"])
def test_docker_stream_normalizes_controls_before_redaction(tmp_path, monkeypatch, control):
    import io
    from research_workbench_entrypoint.docker_runtime import run_bounded
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    command = "print(" + repr(f"Coo{control}kie: fake-session-value") + ")"
    run_bounded([sys.executable, "-c", command], cwd=tmp_path, env={"PATH": os.defpath}, timeout=2, stream=True)
    assert "fake-session-value" not in output.getvalue()


def test_bounded_stream_redaction_cannot_expand_output_past_cap(tmp_path, monkeypatch):
    import io
    from research_workbench_entrypoint.docker_runtime import ControlError, run_bounded
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    with pytest.raises(ControlError, match="runtime_output_limit"):
        run_bounded([sys.executable, "-c", "print('token\\n' * 150)"], cwd=tmp_path,
                    env={"PATH": os.defpath}, timeout=2, stream=True, max_output=1000)
    assert len(output.getvalue().encode()) <= 1000


@pytest.mark.parametrize("failure,code", [
    (("--version", FileNotFoundError()), "docker_cli_missing"),
    (("info", 1), "docker_daemon_unavailable"),
    (("compose", 1), "docker_compose_missing"),
    (("image", 1), "docker_build_not_ready"),
])
def test_preflight_has_safe_distinct_codes(runtime, failure, code):
    controller, runner, _ = runtime
    runner.failure = failure
    result = controller.preflight()
    assert result["issues"] == [code]
    assert "SECRET" not in json.dumps(result)


def test_unsupported_architecture(runtime):
    controller, runner, _ = runtime
    def unsupported(argv, **kwargs):
        if argv[1] == "info":
            return subprocess.CompletedProcess(argv, 0, '"s390x"', "")
        return runner(argv, **kwargs)
    controller.runner = unsupported
    assert controller.preflight()["issues"] == ["docker_architecture_unsupported"]


@pytest.mark.parametrize("port_index,code", [(0, "endpoint_port_in_use")])
def test_real_loopback_conflicts(runtime, port_index, code):
    controller, _, _ = runtime
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        ports = list(controller.ports)
        ports[port_index] = listener.getsockname()[1]
        controller.ports = tuple(ports)
        controller.requested_web_port = ports[0]
        assert controller.start()["issues"] == [code]


def test_unsafe_home_fails_before_docker(runtime):
    controller, runner, _ = runtime
    controller.home.chmod(0o777)
    assert controller.preflight()["issues"] == ["docker_data_home_unsafe"]
    assert not runner.calls


@pytest.mark.parametrize("operation", ["start", "stop", "restart", "status", "doctor", "logs"])
@pytest.mark.parametrize("field", ["project", "service", "installation", "runtime", "working_dir", "mounts"])
def test_foreign_ownership_blocks_every_action(runtime, operation, field):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container[field] = [] if field == "mounts" else "foreign"
    result = getattr(controller, operation)()
    if operation == "logs":
        assert result == 1
    else:
        assert result["issues"] == ["docker_ownership_mismatch"]
    assert not any(call[0][1] == "stop" or "up" in call[0] or "logs" in call[0] for call in runner.calls)


def test_status_safe_shape_and_stop_exact_id(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    result = controller.status()
    assert result["ok"]
    assert result["services"]["web"]["pid"] is None
    assert result["services"]["runtime"]["running"]
    assert "mounts" not in json.dumps(result)
    assert controller.stop()["ok"]
    stop = next(argv for argv, _ in runner.calls if argv[1] == "stop")
    assert stop == ["docker", "stop", "--time", "35", "c" * 64]


class Native:
    def __init__(self, running=False, close=None):
        self.running = running
        self.close = close
        self.events = []

    def preflight(self):
        self.events.append("preflight")
        return {"ok": True, "issues": []}

    def status(self):
        self.events.append("status")
        return {"ok": True, "issues": [], "services": {"web": {"running": self.running}, "runtime": {"running": self.running}}}

    def stop(self):
        self.events.append("stop")
        self.running = False
        if self.close:
            self.close()
        return {"ok": True, "issues": []}


def test_switch_preflights_before_stop_and_never_autostarts(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, runner, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    native = Native(True)
    runner.failure = ("image", 1)
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == ["docker_build_not_ready"]
    assert "stop" not in native.events
    assert store.read().mode == "native"
    runner.failure = None
    assert switch_runtime(store, "docker", controller, native)["issues"] == ["runtime_stop_current_required"]
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["ok"]
    assert store.read().mode == "docker"
    assert not any("up" in argv for argv, _ in runner.calls)


def test_switch_ignores_foreign_host_runtime_port_after_owned_native_stop(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        controller.ports = (controller.ports[0], listener.getsockname()[1])
        result = switch_runtime(store, "docker", controller, Native(True), stop_current=True, wait_timeout=0.05)
        assert result["ok"]
        assert store.read().mode == "docker"
        assert listener.getsockname()[1] == controller.ports[1]


def test_switch_does_not_stop_foreign_web_listener_for_isolated_root(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        controller.ports = (listener.getsockname()[1], controller.ports[1])
        native = Native()
        result = switch_runtime(store, "docker", controller, native, stop_current=True)
        assert result["ok"]
        assert "stop" not in native.events
        assert store.read().mode == "docker"
        assert listener.getsockname()[1] == controller.ports[0]


def test_bounded_runner_enforces_limits_and_timeout(tmp_path):
    import sys
    from research_workbench_entrypoint.docker_runtime import ControlError, run_bounded

    with pytest.raises(ControlError, match="runtime_output_limit"):
        run_bounded([sys.executable, "-c", "print('x'*100000)"], cwd=tmp_path, env={"PATH": os.defpath}, timeout=2, max_output=1000)
    with pytest.raises(ControlError, match="runtime_command_timeout"):
        run_bounded([sys.executable, "-c", "import time;time.sleep(5)"], cwd=tmp_path, env={"PATH": os.defpath}, timeout=0.05, max_output=1000)


def test_switch_refuses_other_runtime_and_rechecks_stopped(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, runner, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    owned(controller, runner)
    native = Native()
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == ["runtime_other_running"]
    assert "stop" not in native.events
    runner.container = None
    native.running = True
    native.stop = lambda: {"ok": True, "issues": []}
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == ["runtime_stop_failed"]
    assert store.read().mode == "native"


def test_unknown_native_state_is_never_stopped(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    native = Native()
    native.status = lambda: {"ok": False, "issues": ["runtime_ownership_unknown"]}
    assert switch_runtime(store, "docker", controller, native)["issues"] == ["runtime_stop_current_required"]
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == ["runtime_ownership_unknown"]
    assert "stop" not in native.events


@pytest.mark.parametrize("environment", ["missing", "broken"])
def test_native_bridge_without_venv_is_read_only(tmp_path, available_ports, environment):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    home = tmp_path / "home"
    if environment == "broken":
        python = tmp_path / ".venv/bin/python"
        python.parent.mkdir(parents=True)
        python.write_text("unowned Native executable")
    controller = NativeRuntime(tmp_path, home, ports=available_ports)
    assert controller.status()["ok"]
    assert controller.preflight()["issues"] == [
        "native_environment_missing" if environment == "missing" else "native_environment_unusable"
    ]
    assert not home.exists()


def test_duplicate_or_extra_mounts_fail_ownership(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["mounts"].append({"Source": "/foreign", "Destination": "/extra"})
    assert controller.stop()["issues"] == ["docker_ownership_mismatch"]


def test_daemon_failure_is_not_reported_as_missing_cli(runtime):
    controller, runner, _ = runtime
    def offline(argv, **kwargs):
        if argv[1] == "version":
            return subprocess.CompletedProcess(argv, 1, "28.0.0\n", "daemon offline")
        if argv[1] == "info":
            return subprocess.CompletedProcess(argv, 1, "", "offline")
        return runner(argv, **kwargs)
    controller.runner = offline
    assert controller.preflight()["issues"] == ["docker_daemon_unavailable"]


def test_logs_preserve_owned_process_exit_code(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    def log_failure(argv, **kwargs):
        if argv[1] == "logs":
            return subprocess.CompletedProcess(argv, 17, "", "")
        return runner(argv, **kwargs)
    controller.runner = log_failure
    assert controller.logs() == 17


def test_native_probe_preserves_stale_state_and_refuses_foreign_before_stop(tmp_path, monkeypatch, available_ports):
    from research_workbench_entrypoint.bootstrap import _native_probe
    from app.research_web.service_manager import WebServiceManager

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    run = home / "run"
    run.mkdir(parents=True, mode=0o700)
    manager = WebServiceManager(project_root=tmp_path, data_root=home / "research-web", web_port=available_ports[0], runtime_port=available_ports[1])
    for process in manager._processes():
        manager._write_state(process, 123456)
    monkeypatch.setattr(WebServiceManager, "_pid_exists", staticmethod(lambda pid: False))
    original = (run / "web.json").read_bytes()
    assert _native_probe("status", tmp_path, home, available_ports)["ok"]
    assert (run / "web.json").read_bytes() == original
    value = json.loads(original)
    value["project_root"] = "/foreign"
    (run / "web.json").write_text(json.dumps(value))
    stopped = []
    monkeypatch.setattr(WebServiceManager, "_stop_one", lambda *args: stopped.append(True))
    from research_workbench_entrypoint.docker_runtime import ControlError
    with pytest.raises(ControlError, match="runtime_ownership_unknown"):
        _native_probe("stop", tmp_path, home, available_ports)
    assert not stopped


def test_native_bridge_subprocess_with_temporary_home_does_not_write(tmp_path, available_ports):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "absent"
    controller = NativeRuntime(root, home, ports=available_ports)
    assert controller.status()["ok"]
    assert not home.exists()


def test_start_refuses_owned_native_even_before_listening(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native(True).status())
    assert controller.start()["issues"] == ["runtime_other_running"]
    assert not any("up" in argv for argv, _ in runner.calls)


def test_install_and_start_use_only_named_service_without_autostart(runtime):
    controller, runner, _ = runtime
    assert controller.install()["ok"]
    assert any(argv[-2:] == ["build", "research-web"] for argv, _ in runner.calls)
    assert not any("up" in argv for argv, _ in runner.calls)
    build_env = next(options["env"] for argv, options in runner.calls if "build" in argv)
    assert build_env["RWB_IMAGE"].startswith("research-workbench:build-")
    def on_up(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = on_up
    assert controller.start(open_browser=False)["services"]["web"]["running"]
    up = next(argv for argv, _ in runner.calls if "up" in argv)
    assert up[-7:] == ["up", "--detach", "--no-build", "--pull", "never", "--no-recreate", "research-web"]
    assert controller.data_dir.is_dir()
    assert controller.state_dir.is_dir()
    assert controller.credential_dir.is_dir()


def test_malformed_inspect_mounts_return_safe_error(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["mounts"][0]["Destination"] = []
    assert controller.status()["issues"] == ["docker_ownership_mismatch"]


def test_start_opens_only_verified_runtime_url(runtime, monkeypatch):
    controller, runner, _ = runtime
    owned(controller, runner)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert controller.start()["ok"]
    assert opened == [f"http://127.0.0.1:{controller.ports[0]}/#/fingpt"]
    assert controller.start(open_browser=False)["ok"]
    assert len(opened) == 1


@pytest.mark.parametrize("overflow", [False, True])
@pytest.mark.parametrize("parent_ignores_term", [False, True])
def test_bounded_runner_kills_descendants_but_not_unrelated(tmp_path, overflow, parent_ignores_term):
    from research_workbench_entrypoint.docker_runtime import ControlError, run_bounded, port_busy
    ready = tmp_path / "child.json"
    child_script = (
        "import socket,signal,time,os,json; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "s=socket.socket(); s.bind(('127.0.0.1',0)); s.listen(); "
        f"Path({str(ready)!r}).write_text(json.dumps([os.getpid(),s.getsockname()[1]])); "
        "time.sleep(30)"
    )
    script = (
        "import subprocess,sys,time,signal; from pathlib import Path; "
        + ("signal.signal(signal.SIGTERM,signal.SIG_IGN); " if parent_ignores_term else "")
        + f"p=subprocess.Popen([sys.executable,'-c',{child_script!r}]); "
        f"ready=Path({str(ready)!r})\n"
        "while not ready.exists(): time.sleep(.01)\n"
        + ("print('x'*100000,flush=True)\n" if overflow else "")
        + "time.sleep(30)\n"
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    child_pid = None
    try:
        with pytest.raises(ControlError, match="runtime_output_limit" if overflow else "runtime_command_timeout"):
            run_bounded([sys.executable, "-c", script], cwd=tmp_path,
                        env=dict(os.environ), timeout=1.5, max_output=1000)
        child_pid, port = json.loads(ready.read_text())
        assert not port_busy(port), "owned descendant remained alive after runner returned"
        assert unrelated.poll() is None
    finally:
        if child_pid is None and ready.exists():
            child_pid, _ = json.loads(ready.read_text())
        if child_pid:
            try:
                os.kill(child_pid, getattr(signal, "SIGKILL", signal.SIGTERM))
            except ProcessLookupError:
                pass
        unrelated.terminate()
        unrelated.wait(timeout=5)


@pytest.mark.skipif(os.name != "posix", reason="Real POSIX SIGINT process-session probe")
def test_bounded_runner_sigint_cleans_direct_and_descendant(tmp_path):
    from research_workbench_entrypoint.docker_runtime import port_busy

    child_ready = tmp_path / "descendant.json"
    ready = tmp_path / "owned.json"
    descendant_script = (
        "import json,os,signal,socket,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "sock=socket.socket(); sock.bind(('127.0.0.1',0)); sock.listen(); "
        f"Path({str(child_ready)!r}).write_text(json.dumps([os.getpid(),sock.getsockname()[1]])); "
        "time.sleep(30)"
    )
    command_script = (
        "import json,os,signal,socket,subprocess,sys,time; from pathlib import Path; "
        "signal.signal(signal.SIGTERM,signal.SIG_IGN); "
        "sock=socket.socket(); sock.bind(('127.0.0.1',0)); sock.listen(); "
        f"subprocess.Popen([sys.executable,'-c',{descendant_script!r}]); "
        f"child=Path({str(child_ready)!r})\n"
        "while not child.exists(): time.sleep(.01)\n"
        f"Path({str(ready)!r}).write_text(json.dumps([os.getpid(),sock.getsockname()[1],*json.loads(child.read_text())]))\n"
        "time.sleep(30)\n"
    )
    runner_script = (
        "import os,sys; from pathlib import Path; "
        "from research_workbench_entrypoint.docker_runtime import run_bounded\n"
        "try:\n"
        f" run_bounded([sys.executable,'-c',{command_script!r}],cwd=Path({str(tmp_path)!r}),env=dict(os.environ),timeout=30)\n"
        "except KeyboardInterrupt:\n"
        " print('original-interrupt',flush=True); raise SystemExit(73)\n"
    )
    runner = subprocess.Popen([sys.executable, "-c", runner_script],
                              cwd=Path(__file__).resolve().parents[2],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              start_new_session=True)
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    owned = None
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        assert ready.exists(), "owned process tree did not start"
        owned = json.loads(ready.read_text())
        assert port_busy(owned[1]) and port_busy(owned[3])
        os.kill(runner.pid, signal.SIGINT)
        stdout, stderr = runner.communicate(timeout=10)
        assert runner.returncode == 73, stderr.decode("utf-8", "replace")
        assert b"original-interrupt" in stdout
        assert not port_busy(owned[1]), "direct process remained after SIGINT"
        assert not port_busy(owned[3]), "descendant remained after SIGINT"
        with pytest.raises(ProcessLookupError):
            os.kill(owned[0], 0)  # The direct child was reaped, not left as a zombie.
        assert unrelated.poll() is None
    finally:
        if runner.poll() is None:
            runner.kill()
            runner.wait(timeout=5)
        if owned is None and ready.exists():
            owned = json.loads(ready.read_text())
        pids = [owned[0], owned[2]] if owned else []
        if child_ready.exists() and not owned:
            pids.append(json.loads(child_ready.read_text())[0])
        for pid in pids:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_bounded_runner_cleanup_error_is_visible_with_original_interrupt(tmp_path, monkeypatch, caplog):
    import research_workbench_entrypoint.docker_runtime as runtime

    class InterruptedEvent:
        def is_set(self):
            return False

        def wait(self, _seconds):
            raise KeyboardInterrupt

    def failed_cleanup(process, job):
        process.kill()
        process.wait(timeout=5)
        raise runtime.ControlError("runtime_process_tree_cleanup_failed")

    monkeypatch.setattr(runtime, "threading", SimpleNamespace(
        Event=InterruptedEvent, Thread=threading.Thread,
    ))
    monkeypatch.setattr(runtime, "_terminate_command_tree", failed_cleanup)
    with pytest.raises(KeyboardInterrupt) as caught:
        runtime.run_bounded([sys.executable, "-c", "import time;time.sleep(30)"],
                            cwd=tmp_path, env=dict(os.environ), timeout=30)
    assert "runtime_process_tree_cleanup_failed" in " ".join(caught.value.__notes__)
    assert "runtime_process_tree_cleanup_failed" in caplog.text


def test_docker_free_port_check_ignores_host_runtime_listener(runtime):
    controller, _runner, _record = runtime
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", controller.ports[1]))
        foreign.listen()
        controller._ports_free()


def test_docker_status_restores_persisted_web_endpoint(runtime):
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

    controller, runner, _record = runtime
    store = EndpointStore(controller.home)
    store.publish("docker", 48213, expected=None)
    before = store.path.read_bytes()
    restored = DockerRuntime(controller.project_root, controller.home, runner=runner)
    report = restored.status()
    assert report["url"] == "http://127.0.0.1:48213/#/fingpt"
    assert report["services"]["runtime"]["port"] == 3081
    assert store.path.read_bytes() == before


@pytest.mark.parametrize("operation", ["start", "stop"])
def test_docker_mutations_excluded_by_native_lifecycle_lock(runtime, operation):
    from app.research_web.lifecycle_lock import LifecycleLock
    controller, runner, _ = runtime
    owned(controller, runner)
    with LifecycleLock(controller.home / "run/lifecycle.lock", lambda pid: True,
                       trusted_root=controller.home):
        report = getattr(controller, operation)()
        assert report["issues"] == ["lifecycle_busy"]
    assert not any("stop" in argv or "up" in argv for argv, _ in runner.calls)


def test_docker_status_rejects_actual_mapping_mismatch(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["ports"] = {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": "1"}]}
    assert controller.status()["issues"] == ["docker_ports_mismatch"]


def test_docker_start_allocates_busy_preferred_and_publishes_only_ready(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore
    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", 0))
        foreign.listen()
        preferred = foreign.getsockname()[1]
        controller.ports = preferred, 3081
        def launch(argv, **kwargs):
            if "up" in argv:
                assert EndpointStore(controller.home).read("docker") is None
                owned(controller, runner)
            return runner(argv, **kwargs)
        controller.runner = launch
        report = controller.start(open_browser=False)
        assert report["ok"], report
        saved = EndpointStore(controller.home).read("docker")
        assert saved.web_port != preferred
        assert report["services"]["web"]["port"] == saved.web_port
        assert foreign.getsockname()[1] == preferred


@pytest.mark.parametrize("publish_failure", [False, True])
def test_docker_origin_transaction_preserves_tokens_and_rolls_back(runtime, monkeypatch, publish_failure):
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointError, EndpointStore
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    old_origin = "http://127.0.0.1:48220"
    EndpointStore(controller.home).publish("native", 48220, 48221, expected=None)
    originals = [load_control(controller.data_dir, old_origin), load_mcp(controller.data_dir, old_origin)]
    before = [(controller.data_dir / ".control" / name).read_bytes()
              for name in ("datahub.json", "mcp-runtime.json")]
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def launch(argv, **kwargs):
        if "up" in argv:
            assert load_control(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[0]["token"]
            assert load_mcp(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[1]["token"]
            owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = launch
    if publish_failure:
        def refuse(*args, **kwargs):
            raise EndpointError("endpoint_io")
        monkeypatch.setattr(controller.endpoint_store, "publish", refuse)
    report = controller.start(open_browser=False)
    assert report["ok"] is (not publish_failure), report
    if publish_failure:
        assert report["issues"] == ["endpoint_io"]
        assert runner.container is None
        assert [(controller.data_dir / ".control" / name).read_bytes()
                for name in ("datahub.json", "mcp-runtime.json")] == before
    else:
        assert load_mcp(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[1]["token"]


def test_mode_switch_final_selection_uses_shared_lifecycle_lock(runtime):
    from app.research_web.lifecycle_lock import LifecycleLock
    from research_workbench_entrypoint.bootstrap import switch_runtime
    controller, runner, _ = runtime
    with LifecycleLock(controller.home / "run/lifecycle.lock", lambda pid: True,
                       trusted_root=controller.home):
        report = switch_runtime(controller.store, "native", controller, Native())
        assert report["issues"] == ["lifecycle_busy"]
    assert controller.store.read().mode == "docker"


@pytest.mark.parametrize("failure", [None, "timeout", "replacement"])
def test_partial_controls_use_owned_no_port_guest_preparation(runtime, monkeypatch, failure):
    from app.research_web.datahub.security import load_control
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore
    from research_workbench_entrypoint.docker_runtime import ControlError
    from docker.supervisor import prepare_controls
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    origin = "http://127.0.0.1:48241"
    original = load_control(controller.data_dir, origin)
    EndpointStore(controller.home).publish("native", 48241, 48242, expected=None)
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    guest = {}
    calls = []
    def preparation_runner(argv, **kwargs):
        calls.append(argv)
        if argv[1] == "create":
            labels = dict(argv[i + 1].split("=", 1) for i, arg in enumerate(argv[:-1]) if arg == "--label")
            assert not any(arg in ("-p", "--publish", "--publish-all") for arg in argv)
            assert str(controller.credential_dir) not in " ".join(argv)
            guest.update(id="d" * 64, image="sha256:" + "b" * 64,
                installation=controller.installation_id, launch=labels["io.research-workbench.launch"],
                runtime="control-preparer", running=False, state="created", exit_code=0,
                ports={}, entrypoint=["/opt/rwb/venv/bin/python"],
                command=["/opt/rwb/docker/supervisor.py", "--prepare-controls-only", "--previous-origin", origin],
                mounts=[{"Type": "bind", "Source": str(controller.data_dir), "Destination": "/data/research-web"}]
                       + [{"Type": "tmpfs", "Source": "", "Destination": name}
                          for name in ("/state", "/run/rwb-secrets", "/tmp", "/home/rwb")])
            return subprocess.CompletedProcess(argv, 0, guest["id"], "")
        if argv[1:3] == ["container", "inspect"] and argv[-1] == "d" * 64:
            return subprocess.CompletedProcess(argv, 0, json.dumps(guest), "")
        if argv[1] == "start":
            prepare_controls(controller.data_dir, origin)
            guest.update(state="exited")
            if failure == "timeout":
                raise ControlError("runtime_command_timeout")
            if failure == "replacement":
                guest["launch"] = "foreign"
            return subprocess.CompletedProcess(argv, 0, "", "")
        if argv[1] == "rm" and argv[-1] == "d" * 64:
            guest.clear()
            return subprocess.CompletedProcess(argv, 0, "", "")
        if "up" in argv:
            assert not guest
            owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = preparation_runner
    report = controller.start(open_browser=False)
    assert report["ok"] is (failure is None), report
    expected_origin = "http://127.0.0.1:8088" if failure is None else origin
    assert load_control(controller.data_dir, expected_origin)["token"] == original["token"]
    if failure == "replacement":
        assert guest and not any(argv[1] == "rm" for argv in calls)
        assert "docker_prepare_cleanup_unverified" in report["issues"]
    else:
        assert not guest
    if failure == "timeout":
        assert report["issues"] == ["runtime_command_timeout"]


def test_docker_bind_race_retries_owned_attempt_with_three_attempt_budget(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    listeners = []
    attempts = []
    def racing(argv, **kwargs):
        if "up" in argv:
            attempts.append(controller.ports[0])
            listener = socket.socket()
            listener.bind(("127.0.0.1", controller.ports[0]))
            listener.listen()
            listeners.append(listener)
            return subprocess.CompletedProcess(argv, 1, "", "Ports are not available: bind: address already in use")
        return runner(argv, **kwargs)
    controller.runner = racing
    try:
        report = controller.start(open_browser=False)
        assert report["issues"] == ["docker_bind_race"], report
        assert len(attempts) == len(set(attempts)) == 3
        assert not controller.endpoint_store.path.exists()
    finally:
        for listener in listeners:
            listener.close()


def test_docker_stop_uses_container_exit_not_foreign_host_listener(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", controller.ports[0]))
        foreign.listen()
        report = controller.stop(wait_timeout=0)
        assert report["ok"], report
        assert not report["services"]["web"]["running"]
        assert foreign.getsockname()[1] == controller.ports[0]


def test_docker_legacy_nondefault_mapping_is_restored_readonly(runtime):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["ports"] = {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": "48269"}]}
    restored = DockerRuntime(controller.project_root, controller.home, runner=runner)
    report = restored.status()
    assert report["ok"], report
    assert report["url"] == "http://127.0.0.1:48269/#/fingpt"
    assert not restored.endpoint_store.path.exists()


def test_installer_summary_failure_restores_pending_origin_and_endpoints(runtime, monkeypatch):
    from scripts import setup_web
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    origin = "http://127.0.0.1:48271"
    EndpointStore(controller.home).publish("native", 48271, 48272, expected=None)
    original = [load_control(controller.data_dir, origin), load_mcp(controller.data_dir, origin)]
    manifest_path = controller.home / "install/docker-manifest.json"
    manifest_before = manifest_path.read_bytes()
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def launch(argv, **kwargs):
        if "up" in argv:
            owned(installer, runner)
        return runner(argv, **kwargs)
    installer = setup_web.DockerRuntime(controller.project_root, controller.home,
                                        runner=launch, ports=controller.ports)
    def refuse(*args):
        raise RuntimeError("fixture_summary_failure")
    monkeypatch.setattr(setup_web, "_write_docker_manifest", refuse)
    with pytest.raises(RuntimeError, match="fixture_summary_failure"):
        installer.install()
    assert runner.container is None
    assert manifest_path.read_bytes() == manifest_before
    assert EndpointStore(controller.home).read("docker") is None
    assert load_control(controller.data_dir, origin)["token"] == original[0]["token"]
    assert load_mcp(controller.data_dir, origin)["token"] == original[1]["token"]


def test_native_docker_native_control_roundtrip_preserves_both_tokens(runtime, monkeypatch):
    from app.research_web.service_manager import WebServiceManager
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    controller, runner, _ = runtime
    native_ports = controller.ports
    controller.data_dir.mkdir(mode=0o700)
    originals = [load_control(controller.data_dir, "http://127.0.0.1:8088"),
                 load_mcp(controller.data_dir, "http://127.0.0.1:8088")]
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def start_native():
        controller.store.write("native")
        manager = WebServiceManager(project_root=controller.project_root, data_root=controller.data_dir,
                                    web_port=native_ports[0], runtime_port=native_ports[1])
        monkeypatch.setattr(manager, "_other_runtime_quiescent", lambda: not (runner.container and runner.container["running"]))
        monkeypatch.setattr(manager, "_require_installation_ready", lambda: {"ok": True})
        monkeypatch.setattr(manager, "_start_locked", lambda **kwargs: {"product_ready": True})
        manager.start(open_browser=False)
        origin = f"http://127.0.0.1:{manager.web_port}"
        assert load_control(controller.data_dir, origin)["token"] == originals[0]["token"]
        assert load_mcp(controller.data_dir, origin)["token"] == originals[1]["token"]
        return manager
    first = start_native()
    first.stop()
    controller.store.write("docker")
    def launch(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = launch
    assert controller.start(open_browser=False)["ok"]
    assert load_control(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[0]["token"]
    assert controller.stop()["ok"]
    last = start_native()
    assert last.endpoint_store.read("docker").web_port == controller.ports[0]


def test_new_docker_attempt_never_adopts_wrong_actual_mapping_as_legacy(runtime, monkeypatch):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    previous, runner, _ = runtime
    controller = DockerRuntime(previous.project_root, previous.home, runner=runner)
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    def launch(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
            runner.container["ports"] = {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": "1"}]}
        return runner(argv, **kwargs)
    controller.runner = launch
    report = controller.start(open_browser=False)
    assert report["issues"] == ["docker_ports_mismatch"]
    assert runner.container is None
    assert controller.endpoint_store.read("docker") is None


def test_docker_malformed_control_origin_reports_stable_issue(runtime):
    from research_workbench_entrypoint.docker_runtime import ControlError
    controller, _, _ = runtime
    folder = controller.data_dir / ".control"
    folder.mkdir(parents=True, mode=0o700)
    controller.data_dir.chmod(0o700)
    for name in ("datahub.json", "mcp-runtime.json"):
        path = folder / name
        path.write_text(json.dumps({"url": {}, "token": "x" * 43, "version": 1}))
        path.chmod(0o600)
    with pytest.raises(ControlError, match="control_origin_"):
        controller._prepare_control_origin("sha256:" + "b" * 64)


def test_bounded_runner_cleanup_error_preserves_timeout_code(tmp_path, monkeypatch, caplog):
    import research_workbench_entrypoint.docker_runtime as runtime

    def failed_cleanup(process, job):
        process.kill()
        process.wait(timeout=5)
        raise runtime.ControlError("runtime_process_tree_cleanup_failed")

    monkeypatch.setattr(runtime, "_terminate_command_tree", failed_cleanup)
    with pytest.raises(runtime.ControlError) as caught:
        runtime.run_bounded([sys.executable, "-c", "import time;time.sleep(30)"],
                            cwd=tmp_path, env=dict(os.environ), timeout=.05)
    assert caught.value.code == "runtime_command_timeout"
    assert "runtime_process_tree_cleanup_failed" in " ".join(caught.value.__notes__)
    assert "runtime_process_tree_cleanup_failed" in caplog.text
