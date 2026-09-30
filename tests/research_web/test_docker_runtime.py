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
            output = "c" * 64 if self.container else ""
        elif command[1:3] == ("container", "inspect"):
            output = json.dumps(self.container)
        elif command[1:2] == ("stop",):
            self.container["running"] = False
            if self.on_stop:
                self.on_stop()
        return subprocess.CompletedProcess(argv, 0, output, "")


@pytest.fixture
def runtime(tmp_path):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    record = RuntimeModeStore(home).write("docker")
    runner = RecordingRunner()
    controller = DockerRuntime(tmp_path, home, runner=runner, ports=(18088, 13081))
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
    raw = json.dumps(report)
    assert str(controller.home) not in raw and str(controller.project_root) not in raw
    assert record.installation_id not in raw
    assert "Env" not in raw and "Cookie" not in raw


@pytest.mark.parametrize("health", ["unhealthy", "starting", "none"])
def test_docker_doctor_fails_unhealthy_core(runtime, health):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["health"] = health
    report = controller.doctor()
    assert not report["ok"]
    assert "docker_services_unhealthy" in report["issues"]


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


@pytest.mark.parametrize("port_index,code", [(0, "docker_port_8088_occupied"), (1, "docker_port_3081_conflict")])
def test_real_loopback_conflicts(runtime, port_index, code):
    controller, _, _ = runtime
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        ports = list(controller.ports)
        ports[port_index] = listener.getsockname()[1]
        controller.ports = tuple(ports)
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


def test_switch_waits_both_real_ports_and_keeps_mode_on_timeout(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        controller.ports = (18088, listener.getsockname()[1])
        result = switch_runtime(store, "docker", controller, Native(True), stop_current=True, wait_timeout=0.05)
        assert result["issues"] == ["runtime_ports_not_released"]
        assert store.read().mode == "native"
        native = Native(True, listener.close)
        assert switch_runtime(store, "docker", controller, native, stop_current=True, wait_timeout=0.1)["ok"]


def test_switch_refuses_unknown_port_even_with_stop_flag(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        controller.ports = (listener.getsockname()[1], 13081)
        native = Native()
        result = switch_runtime(store, "docker", controller, native, stop_current=True)
        assert result["issues"] == ["runtime_ownership_unknown"]
        assert "stop" not in native.events
        assert store.read().mode == "native"


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


def test_native_bridge_without_venv_is_read_only(tmp_path):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    home = tmp_path / "home"
    controller = NativeRuntime(tmp_path, home, ports=(18088, 13081))
    assert controller.status()["ok"]
    assert controller.preflight()["issues"] == ["native_environment_missing"]
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


def test_native_probe_preserves_stale_state_and_refuses_foreign_before_stop(tmp_path, monkeypatch):
    from research_workbench_entrypoint.bootstrap import _native_probe
    from app.research_web.service_manager import WebServiceManager

    home = tmp_path / "home"
    run = home / "run"
    run.mkdir(parents=True, mode=0o700)
    manager = WebServiceManager(project_root=tmp_path, data_root=home / "research-web", web_port=18088, runtime_port=13081)
    for process in manager._processes():
        manager._write_state(process, 123456)
    monkeypatch.setattr(WebServiceManager, "_pid_exists", staticmethod(lambda pid: False))
    original = (run / "web.json").read_bytes()
    assert _native_probe("status", tmp_path, home, (18088, 13081))["ok"]
    assert (run / "web.json").read_bytes() == original
    value = json.loads(original)
    value["project_root"] = "/foreign"
    (run / "web.json").write_text(json.dumps(value))
    stopped = []
    monkeypatch.setattr(WebServiceManager, "_stop_one", lambda *args: stopped.append(True))
    from research_workbench_entrypoint.docker_runtime import ControlError
    with pytest.raises(ControlError, match="runtime_ownership_unknown"):
        _native_probe("stop", tmp_path, home, (18088, 13081))
    assert not stopped


def test_native_bridge_subprocess_with_temporary_home_does_not_write(tmp_path):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "absent"
    controller = NativeRuntime(root, home, ports=(18088, 13081))
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
    def on_up(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        return runner(argv, **kwargs)
    controller.runner = on_up
    assert controller.start(open_browser=False)["services"]["web"]["running"]
    up = next(argv for argv, _ in runner.calls if "up" in argv)
    assert up[-6:] == ["up", "--detach", "--no-build", "--pull", "never", "research-web"]
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
