"""Host runtime control uses bounded subprocesses and verified ownership."""

import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint.runtime_mode import RuntimeModeStore


@pytest.fixture(autouse=True)
def isolated_os_native_candidate(tmp_path, monkeypatch):
    from research_workbench_entrypoint import web_bootstrap

    monkeypatch.setattr(
        web_bootstrap,
        "_standard_native_data_root",
        lambda: tmp_path / "os-user/.research-workbench/research-web",
    )


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
                self.container["launch"] = overlay["services"]["research-web"]["labels"][
                    "io.research-workbench.launch"
                ]
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


@pytest.mark.parametrize("returncode", [0, 7])
def test_fixed_build_large_public_popen_stream_retains_tail(runtime, monkeypatch, returncode):
    import io

    from research_workbench_entrypoint.docker_runtime import ControlError, run_bounded

    controller, _runner, _record = runtime
    controller.runner = run_bounded
    payload = b"progress line\n" * 10000 + b"compiler final error detail\n"
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return SimpleNamespace(
            pid=999999,
            stdout=io.BufferedReader(io.BytesIO(payload)),
            stderr=io.BufferedReader(io.BytesIO()),
            returncode=returncode,
            poll=lambda: returncode,
            wait=lambda **kwargs: returncode,
        )

    monkeypatch.setattr(subprocess, "Popen", popen)
    argv = [*controller.compose_prefix, "build", "research-web"]
    if returncode:
        with pytest.raises(ControlError, match="docker_build_failed"):
            controller._call(argv, "docker_build_failed")
    else:
        completed = controller._call(argv, "docker_build_failed")
        assert completed.stdout.endswith("compiler final error detail\n")
    assert output.getvalue().endswith("compiler final error detail\n")
    assert calls[0][0] == argv


def test_build_budget_is_exact_argv_and_same_post_capture_guard(runtime):
    from research_workbench_entrypoint.docker_runtime import MAX_OUTPUT, ControlError

    controller, _runner, _ = runtime
    captured = []

    def large(argv, **kwargs):
        captured.append(kwargs)
        return subprocess.CompletedProcess(argv, 0, "x" * 100000, "")

    controller.runner = large
    result = controller._call(
        [*controller.compose_prefix, "build", "research-web"], "docker_build_failed"
    )
    assert len(result.stdout) == 100000
    assert captured[-1]["max_output"] == 2 * 1024 * 1024 and captured[-1]["stream"] is True
    for argv in (
        ["docker", "image", "inspect", "build"],
        [*controller.compose_prefix, "build", "other"],
    ):
        with pytest.raises(ControlError, match="runtime_output_limit"):
            controller._call(argv, "metadata_failed")
        assert captured[-1]["max_output"] == MAX_OUTPUT


def test_build_stream_omits_transport_url_without_dropping_error_detail(tmp_path, monkeypatch):
    import io

    from research_workbench_entrypoint.docker_runtime import run_bounded

    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    script = "import sys,time;sys.stdout.write('proxy error socks5');sys.stdout.flush();time.sleep(.03);print('h://host.docker.internal:29757 failed');print('compiler final error detail')"
    run_bounded(
        [sys.executable, "-c", script],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        timeout=2,
        stream=True,
    )
    assert "host.docker.internal" not in output.getvalue()
    assert "compiler final error detail" in output.getvalue()


def test_build_log_redaction_preserves_public_download_url_and_error_text():
    from research_workbench_entrypoint.docker_runtime import safe_log_text

    public = "download error https://nodejs.org/dist/v24.19.0/node-v24.19.0-headers.tar.gz failed\n"
    assert safe_log_text(public) == public
    redacted = safe_log_text(
        "proxy connection refused http://localhost:29758\nfetch failed https://user:fixture@remote.invalid/resource\n"
    )
    assert "localhost" not in redacted and "fixture" not in redacted
    assert "connection refused" in redacted and "fetch failed" in redacted


def test_large_nonzero_build_never_accepts_candidate(runtime):
    controller, runner, _ = runtime
    calls = []
    before = (controller.home / "install/docker-manifest.json").read_bytes()

    def failed(argv, **kwargs):
        calls.append((argv, kwargs))
        if "build" in argv:
            return subprocess.CompletedProcess(
                argv, 19, "progress\n" * 20000, "compiler final error detail"
            )
        return runner(argv, **kwargs)

    controller.runner = failed
    assert controller.install()["issues"] == ["docker_build_failed"]
    assert (controller.home / "install/docker-manifest.json").read_bytes() == before
    assert not any(argv[1:3] == ["image", "inspect"] for argv, kwargs in calls)


def test_two_mib_build_cap_kills_owned_descendant_not_unrelated(tmp_path):
    from research_workbench_entrypoint.docker_runtime import (
        BUILD_MAX_OUTPUT,
        ControlError,
        port_busy,
        run_bounded,
    )

    ready = tmp_path / "owned.json"
    child = (
        "import os,socket,time,json;from pathlib import Path;s=socket.socket();"
        "s.bind(('127.0.0.1',0));s.listen();"
        f"Path({str(ready)!r}).write_text(json.dumps([os.getpid(),s.getsockname()[1]]));time.sleep(30)"
    )
    script = (
        "import subprocess,sys,time;from pathlib import Path;"
        f"subprocess.Popen([sys.executable,'-c',{child!r}]);ready=Path({str(ready)!r})\n"
        "while not ready.exists():time.sleep(.01)\n"
        f"print('x'*{BUILD_MAX_OUTPUT + 10000},flush=True);time.sleep(30)"
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    try:
        with pytest.raises(ControlError, match="runtime_output_limit"):
            run_bounded(
                [sys.executable, "-c", script],
                cwd=tmp_path,
                env={"PATH": os.defpath},
                timeout=5,
                max_output=BUILD_MAX_OUTPUT,
            )
        _pid, port = json.loads(ready.read_text())
        assert not port_busy(port)
        assert unrelated.poll() is None
    finally:
        unrelated.terminate()
        unrelated.wait(timeout=5)


def test_docker_proxy_public_popen_and_shared_native_environment(runtime, monkeypatch):
    import io

    from research_workbench_entrypoint.docker_runtime import minimal_environment, run_bounded

    controller, _runner, _record = runtime
    controller.runner = run_bounded
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:29758")
    monkeypatch.setenv("HTTPS_PROXY", "https://[::1]:29759")
    monkeypatch.setenv("NO_PROXY", "example.com,10.0.0.0/8")
    for key in ("http_proxy", "https_proxy", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("API_KEY", "fixture-secret")
    monkeypatch.setenv("ALL_PROXY", "socks5h://127.0.0.1:29757")
    monkeypatch.setenv("DOCKER_HOST", "tcp://foreign:2375")
    captured = []

    def popen(argv, **kwargs):
        captured.append((argv, kwargs))
        return SimpleNamespace(
            pid=999999,
            stdout=io.BufferedReader(io.BytesIO(b"ok")),
            stderr=io.BufferedReader(io.BytesIO()),
            returncode=0,
            poll=lambda: 0,
            wait=lambda **kwargs: 0,
        )

    monkeypatch.setattr(subprocess, "Popen", popen)
    controller._call(["docker", "--version"], "docker_cli_missing")
    argv, options = captured[0]
    assert argv == ["docker", "--version"]
    assert options["env"]["HTTP_PROXY"] == "http://127.0.0.1:29758"
    assert options["env"]["HTTPS_PROXY"] == "https://[::1]:29759"
    assert "127.0.0.1" in options["env"]["NO_PROXY"]
    assert not {"API_KEY", "ALL_PROXY", "DOCKER_HOST"} & options["env"].keys()
    assert not {"HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY"} & minimal_environment().keys()


@pytest.mark.parametrize(
    "value",
    [
        "http://user:secret@127.0.0.1:80",
        "socks5h://127.0.0.1:80",
        "http://foreign:80",
        "http://127.0.0.1:0",
        "http://127.0.0.1:80/",
        "http://127.0.0.1:80?",
        "http://127.0.0.1:80#",
        "http://127.0.0.1:80\n",
        "x" * 1025,
    ],
    ids=[
        "userinfo",
        "scheme",
        "foreign",
        "zero",
        "path",
        "query",
        "fragment",
        "control",
        "oversized",
    ],
)
def test_unsafe_docker_proxy_does_not_block_owned_status_stop_but_blocks_build(
    runtime, monkeypatch, value
):
    controller, runner, _record = runtime
    owned(controller, runner)
    monkeypatch.setenv("HTTP_PROXY", value)
    monkeypatch.delenv("http_proxy", raising=False)
    assert controller.status()["ok"]
    assert controller.stop(wait_timeout=0)["ok"]
    assert not any("HTTP_PROXY" in kwargs["env"] for argv, kwargs in runner.calls)
    report = controller.install()
    assert report["issues"][0] == "docker_proxy_configuration_invalid"
    assert value not in json.dumps(report)
    assert not any("build" in argv for argv, kwargs in runner.calls)


@pytest.mark.parametrize(
    "upper,lower,valid",
    [
        (None, "http://localhost:80", True),
        ("", "", True),
        ("", "http://localhost:80", False),
        ("HTTP://LOCALHOST:080", "http://localhost:80", True),
        ("http://127.0.0.1:80", "http://127.0.0.1:81", False),
    ],
)
def test_docker_proxy_case_and_empty_contract(runtime, monkeypatch, upper, lower, valid):
    from research_workbench_entrypoint.docker_runtime import _docker_cli_proxies

    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    if upper is not None:
        monkeypatch.setenv("HTTP_PROXY", upper)
    monkeypatch.setenv("http_proxy", lower)
    env, issues = _docker_cli_proxies()
    assert (not issues) is valid
    if valid and lower:
        assert env["HTTP_PROXY"] == env["http_proxy"]
    else:
        assert "HTTP_PROXY" not in env


@pytest.mark.parametrize(
    "value,valid",
    [
        ("localhost,.example.com,*.example.net,127.0.0.1,::1,10.0.0.0/8,*", True),
        ("https://host", False),
        ("user@host", False),
        ("host:80", False),
        ("host\n", False),
        ("a," * 65, False),
        ("a" * 2049, False),
        ("10.0.0.0/99", False),
    ],
)
def test_docker_bypass_validation_and_doctor_safe_projection(runtime, monkeypatch, value, valid):
    from research_workbench_entrypoint.docker_runtime import _docker_cli_proxies

    controller, runner, _ = runtime
    owned(controller, runner)
    for directory in (controller.data_dir, controller.state_dir, controller.credential_dir):
        directory.mkdir(parents=True, mode=0o700)
    for key in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy", "NO_PROXY", "no_proxy"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("NO_PROXY", value)
    _env, issues = _docker_cli_proxies()
    assert (not issues) is valid
    report = controller.doctor()
    assert report["ok"]
    assert report["proxy"]["state"] == ("configured" if valid else "unsafe")
    assert value not in json.dumps(report)


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
            {
                "Type": "bind",
                "Source": str(controller.data_dir),
                "Destination": "/data/research-web",
            },
            {
                "Type": "bind",
                "Source": str(controller.state_dir / "logs"),
                "Destination": "/state/logs",
            },
            {
                "Type": "bind",
                "Source": str(controller.credential_dir),
                "Destination": "/run/rwb-secrets",
            },
            {"Type": "tmpfs", "Source": "", "Destination": "/tmp"},
            {"Type": "tmpfs", "Source": "", "Destination": "/home/rwb"},
            {"Type": "tmpfs", "Source": "", "Destination": "/state"},
        ],
        "tmpfs": {
            "/state": "rw,nosuid,nodev,noexec,uid=10001,gid=10001,mode=700,size=1m",
            "/tmp": "rw,nosuid,nodev,mode=1777",
            "/home/rwb": "rw,nosuid,nodev,uid=10001,gid=10001,mode=700",
        },
    }
    for mount in runner.container["mounts"]:
        mount["RW"] = True


@pytest.mark.parametrize(
    "change",
    [
        "missing_state",
        "missing_tmp",
        "missing_home",
        "duplicate",
        "wrong_type",
        "wrong_source",
        "legacy_bind",
        "readonly",
        "missing_rw",
        "rw_string",
        "missing_config",
        "config_list",
        "extra_config",
        "uid",
        "gid",
        "mode",
        "size",
        "noexec",
        "unknown",
        "duplicate_option",
        "contradiction",
    ],
)
def test_private_state_mount_contract_rejects_nearest_invalid_layout(runtime, change):
    controller, runner, _ = runtime
    owned(controller, runner)
    mounts = runner.container["mounts"]
    state = mounts[-1]
    if change.startswith("missing_") and change in {"missing_state", "missing_tmp", "missing_home"}:
        destination = {
            "missing_state": "/state",
            "missing_tmp": "/tmp",
            "missing_home": "/home/rwb",
        }[change]
        mounts[:] = [item for item in mounts if item["Destination"] != destination]
        runner.container["tmpfs"].pop(destination)
    elif change == "duplicate":
        mounts.append(dict(state))
    elif change == "wrong_type":
        state["Type"] = "volume"
    elif change == "wrong_source":
        mounts[1]["Source"] = str(controller.state_dir)
    elif change == "legacy_bind":
        state.update(Type="bind", Source=str(controller.state_dir))
    elif change in {"readonly", "missing_rw", "rw_string"}:
        for item in mounts:
            if change == "missing_rw":
                item.pop("RW")
            else:
                item["RW"] = False if change == "readonly" else "true"
    elif change == "missing_config":
        runner.container.pop("tmpfs")
    elif change == "config_list":
        runner.container["tmpfs"] = list(runner.container["tmpfs"])
    elif change == "extra_config":
        runner.container["tmpfs"]["/extra"] = "rw"
    else:
        options = runner.container["tmpfs"]["/state"]
        replacements = {
            "uid": ("uid=10001", "uid=0"),
            "gid": ("gid=10001", "gid=0"),
            "mode": ("mode=700", "mode=755"),
            "size": ("size=1m", "size=2m"),
            "noexec": (",noexec", ""),
        }
        if change in replacements:
            options = options.replace(*replacements[change])
        else:
            options += {
                "unknown": ",silent",
                "duplicate_option": ",uid=10001",
                "contradiction": ",ro",
            }[change]
        runner.container["tmpfs"]["/state"] = options
    assert controller.status()["issues"] == ["docker_ownership_mismatch"]


def test_private_state_tmpfs_options_are_semantic_and_binds_writable(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["tmpfs"][
        "/state"
    ] = "size=1048576,mode=0700,gid=10001,uid=10001,noexec,nodev,nosuid,rw"
    assert controller.status()["ok"]
    runner.container["mounts"][1]["RW"] = False
    assert controller.status()["issues"] == ["docker_ownership_mismatch"]


@pytest.mark.parametrize("explicit", [[], ["/state", "/tmp", "/home/rwb"]])
def test_hostconfig_requires_all_tmpfs_when_engine_omits_mount_entries(runtime, explicit):
    # Docker 29 Engine exposes --tmpfs in HostConfig, without duplicate Mounts entries.
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["mounts"][:] = [
        item
        for item in runner.container["mounts"]
        if item["Type"] == "bind" or item["Destination"] in explicit
    ]
    assert controller.status()["ok"]
    runner.container["tmpfs"].pop("/state")
    assert controller.status()["issues"] == ["docker_ownership_mismatch"]


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
    original = [
        (controller.data_dir / ".control" / name).read_bytes()
        for name in ("datahub.json", "mcp-runtime.json")
    ]
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
    assert [
        (controller.data_dir / ".control" / name).read_bytes()
        for name in ("datahub.json", "mcp-runtime.json")
    ] == original


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


@pytest.mark.parametrize("evidence", ["unknown", "same-root", "pid-reused"])
def test_fix1_native_bridge_missing_environment_and_ledger_refuses_existing_root_listener(
    runtime, monkeypatch, evidence
):
    from research_workbench_entrypoint import bootstrap
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.web_contract import ProcessFact

    controller, _runner, _record = runtime
    controller.data_dir.mkdir(mode=0o700)
    calls = []

    def facts(pid):
        calls.append(pid)
        argv = (
            None
            if evidence == "unknown"
            else ("node", str(controller.data_dir) if evidence == "same-root" else "/foreign/data")
        )
        return ProcessFact(
            "alive", None, None, argv, float(len(calls)) if evidence == "pid-reused" else 1.0
        )

    monkeypatch.setattr(bootstrap, "probe_process", facts)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", controller.ports[0]))
        listener.listen()
        report = NativeRuntime(
            controller.project_root, controller.home, ports=controller.ports
        ).status()
        assert report["issues"] == ["runtime_ownership_unknown"], report


def test_fix2_docker_only_healthy_start_reuses_verified_container_with_real_listener(runtime):
    from research_workbench_entrypoint.web_contract import listener_pids

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    # A valid prior Native endpoint fixture isolates this genuine generic
    # listener from unrelated host product writers whose roots are unknown.
    controller.endpoint_store.publish(
        "native", controller.ports[0], controller.ports[1], expected=None
    )
    owned(controller, runner)
    identity = runner.container["id"]
    listener = socket.socket()
    port = controller.ports[0]
    before = listener_pids(port)
    try:
        if before.state == "closed":
            listener.bind(("127.0.0.1", port))
            listener.listen()
        observed = listener_pids(port)
        assert observed.state == "listening" and observed.pids
        report = controller.start(open_browser=False)
        assert report["ok"], report
        assert runner.container["id"] == identity
        assert not any("up" in argv or argv[1] in ("stop", "rm") for argv, _ in runner.calls)
        assert listener_pids(port) == observed
    finally:
        listener.close()


def test_fix2_docker_only_start_keeps_real_host3081_and_refuses_unknown_product(runtime):
    from research_workbench_entrypoint.web_contract import listener_pids, probe_process

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    listener = socket.socket()
    before = listener_pids(3081)

    def launch(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        return runner(argv, **kwargs)

    controller.runner = launch
    try:
        if before.state == "closed":
            listener.bind(("127.0.0.1", 3081))
            listener.listen()
        observed = listener_pids(3081)
        assert observed.state == "listening" and observed.pids
        facts = [probe_process(pid) for port in (8088, 3081) for pid in listener_pids(port).pids]
        product_writer = any(
            fact.argv
            and any(
                "app.research_web.main" in arg or "/apps/cli/lib/bin.js" in arg for arg in fact.argv
            )
            for fact in facts
        )
        report = controller.start(open_browser=False)
        if product_writer:
            assert report["issues"] == ["runtime_ownership_unknown"], report
            assert runner.container is None
        else:
            assert report["ok"], report
            assert runner.container and runner.container["running"]
        assert listener_pids(3081) == observed
        assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls)
    finally:
        listener.close()


def test_fix2_managed_docker_mapping_mismatch_cannot_be_adopted(runtime):
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    controller.endpoint_store.publish(
        "native", controller.ports[0], controller.ports[1], expected=None
    )
    owned(controller, runner)
    runner.container["ports"]["8088/tcp"][0]["HostPort"] = str(controller.ports[0] + 1)
    report = controller.start(open_browser=False)
    assert report["issues"] == ["docker_ports_mismatch"], report
    assert not any("up" in argv or argv[1] in ("stop", "rm") for argv, _ in runner.calls)
    assert runner.container["running"]


@pytest.fixture
def foreign_native_pair(runtime, monkeypatch):
    """Actual bounded private ledger reader with explicit fixture OS observations."""
    from test_web_bootstrap import _service_state

    from app.research_web import service_manager
    from research_workbench_entrypoint import bootstrap, web_bootstrap, web_contract
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    candidate = controller.project_root / "os-user" / ".research-workbench" / "research-web"
    candidate.mkdir(parents=True, mode=0o700)
    candidate.parent.chmod(0o700)
    records = candidate.parent / "run"
    records.mkdir(mode=0o700)
    states = {}
    processes = {}
    for role in ("web", "runtime"):
        state = _service_state(controller.project_root, candidate, role)
        path = records / (role + ".json")
        path.write_text(json.dumps(state))
        path.chmod(0o600)
        states[role] = state
        argv = tuple(state["signature"])
        processes[state["pid"]] = ProcessFact("alive", " ".join(argv), None, argv, 1.0)

    def listeners(port):
        pids = tuple(state["pid"] for state in states.values() if state["port"] == port)
        return ListenerFact("listening" if pids else "closed", pids, None)

    monkeypatch.setattr(
        web_bootstrap, "_standard_native_data_root", lambda: candidate, raising=False
    )
    for module in (web_bootstrap, bootstrap, web_contract, service_manager):
        monkeypatch.setattr(module, "listener_pids", listeners)
        monkeypatch.setattr(module, "probe_process", lambda pid: processes[pid])

    def launch(argv, **kwargs):
        if "up" in argv:
            if runner.container is None:
                owned(controller, runner)
            else:
                runner.container.update(running=True, state="running")
        return runner(argv, **kwargs)

    controller.runner = launch
    return candidate, states, processes


def test_foreign_private_pair_allows_repeated_docker_start(runtime, foreign_native_pair):
    controller, runner, _ = runtime
    first = controller.start(open_browser=False)
    assert first["ok"] is True, first
    identity = runner.container["id"]
    second = controller.start(open_browser=False)
    assert second["ok"] is True, second
    assert second["ownership"] == "verified"
    assert runner.container["id"] == identity


def test_foreign_private_pair_docker_lifecycle(runtime, foreign_native_pair):
    controller, _runner, _ = runtime
    assert controller.start(open_browser=False)["ok"] is True
    assert controller.restart(force=True, open_browser=False)["ok"] is True
    assert controller.stop()["ok"] is True
    assert controller.start(open_browser=False)["ok"] is True


@pytest.mark.parametrize(
    "change",
    [
        "same-root",
        "alias",
        "unsafe-mode",
        "missing-role",
        "malformed",
        "fifo",
        "extra-listener",
        "pid-reuse",
        "argv-change",
    ],
)
def test_foreign_private_pair_refuses_incomplete_or_unknown(
    runtime, foreign_native_pair, monkeypatch, change
):
    from research_workbench_entrypoint import bootstrap, web_bootstrap, web_contract
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    controller, runner, _ = runtime
    candidate, states, processes = foreign_native_pair
    if change == "same-root":
        monkeypatch.setattr(
            web_bootstrap, "_standard_native_data_root", lambda: controller.data_dir
        )
    elif change == "alias":
        alias = candidate.with_name("alias")
        alias.symlink_to(candidate, target_is_directory=True)
        monkeypatch.setattr(web_bootstrap, "_standard_native_data_root", lambda: alias)
    elif change == "unsafe-mode":
        candidate.chmod(0o755)
    elif change == "missing-role":
        (candidate.parent / "run/runtime.json").unlink()
    elif change == "malformed":
        (candidate.parent / "run/runtime.json").write_text("{}")
    elif change == "fifo":
        path = candidate.parent / "run/runtime.json"
        path.unlink()
        os.mkfifo(path, 0o600)
    elif change == "extra-listener":
        for module in (web_bootstrap, bootstrap, web_contract):
            original = module.listener_pids
            monkeypatch.setattr(
                module,
                "listener_pids",
                lambda port, original=original: (
                    ListenerFact("listening", (*original(port).pids, 999), None)
                    if port == 8088
                    else original(port)
                ),
            )
    else:
        pid = states["web"]["pid"]
        old = processes[pid]
        argv = old.argv if change == "pid-reuse" else (*old.argv, "changed")
        processes[pid] = ProcessFact(
            "alive", old.command_line, None, argv, 99.0 if change == "pid-reuse" else old.started_at
        )
        if change == "argv-change":
            # Keep the product-looking observation but remove its owned signature.
            processes[pid] = ProcessFact(
                "alive",
                old.command_line,
                None,
                ("uvicorn", "app.research_web.main:app", "--app-dir", "/other"),
                1.0,
            )
    report = controller.start(open_browser=False)
    assert report["issues"] == ["runtime_ownership_unknown"], report
    assert runner.container is None
    assert not any("up" in argv or argv[1] in ("stop", "rm") for argv, _ in runner.calls)


@pytest.mark.parametrize(
    "change",
    ["record", "root", "target-root", "argv", "start", "lease", "scope", "other-controller"],
)
def test_foreign_capture_never_refreshes_or_transfers(
    runtime, foreign_native_pair, monkeypatch, change
):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError, DockerRuntime
    from research_workbench_entrypoint.web_contract import ProcessFact

    controller, runner, _ = runtime
    candidate, states, processes = foreign_native_pair

    def check():
        native = NativeRuntime(controller.project_root, controller.home)
        assert controller._native_selection_safe(native, native.status())
        proof = controller._foreign_ledger
        assert proof is not None
        if change == "record":
            path = candidate.parent / "run/web.json"
            replacement = path.with_name("replacement.json")
            replacement.write_bytes(path.read_bytes())
            replacement.chmod(0o600)
            replacement.replace(path)
        elif change in ("root", "target-root"):
            root = candidate if change == "root" else controller.data_dir
            root.rename(root.with_name(root.name + "-old"))
            root.mkdir(mode=0o700)
        elif change in ("argv", "start"):
            pid = states["web"]["pid"]
            before = processes[pid]
            processes[pid] = ProcessFact(
                "alive",
                before.command_line,
                None,
                (*before.argv, "extra") if change == "argv" else before.argv,
                before.started_at + 1 if change == "start" else before.started_at,
            )
        elif change == "lease":
            controller._lifecycle_lease = object()
        elif change == "scope":
            controller._foreign_scope = object()
        else:
            other = DockerRuntime(controller.project_root, controller.home, runner=runner)
            port, listener = next(iter(proof.before[3].items()))
            assert not proof.permits(
                other, controller._foreign_scope, controller._lifecycle_lease, port, listener
            )
            return {"ok": True}
        assert not controller._foreign_safe(native)
        assert not controller._foreign_safe(native)
        raise ControlError("runtime_ownership_unknown")

    report = controller._locked_guard("fixture", check)
    if change != "other-controller":
        assert report["issues"] == ["runtime_ownership_unknown"], report
    assert controller._foreign_ledger is None
    assert runner.container is None


def test_restart_unknown_pair_refuses_before_stopping_healthy_docker(runtime, foreign_native_pair):
    controller, runner, _ = runtime
    candidate, _states, _processes = foreign_native_pair
    assert controller.start(open_browser=False)["ok"]
    identity = runner.container["id"]
    (candidate.parent / "run/runtime.json").unlink()
    calls = len(runner.calls)
    report = controller.restart(force=True, open_browser=False)
    assert report["issues"] == ["runtime_ownership_unknown"]
    assert runner.container["id"] == identity and runner.container["running"]
    assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls[calls:])


def test_foreign_pair_normal_native_bridge_uses_existing_manager_reader(
    runtime, foreign_native_pair, monkeypatch
):
    from test_web_bootstrap import _write_owned_interpreter

    from app.research_web import service_manager
    from research_workbench_entrypoint import bootstrap, web_bootstrap

    controller, _runner, _ = runtime
    _write_owned_interpreter(controller.project_root, valid_marker=True)
    monkeypatch.setattr(service_manager, "listener_pids", web_bootstrap.listener_pids)
    monkeypatch.setattr(service_manager, "probe_process", web_bootstrap.probe_process)
    calls = []

    def bridge(argv, **kwargs):
        calls.append(argv)
        report = bootstrap._native_probe(
            argv[-5], Path(argv[-4]), Path(argv[-3]), (int(argv[-2]), int(argv[-1]))
        )
        return subprocess.CompletedProcess(argv, 0, json.dumps(report), "")

    native = bootstrap.NativeRuntime(controller.project_root, controller.home, runner=bridge)
    report = native.status()
    assert report["ok"] and all(not service["running"] for service in report["services"].values())
    assert calls and native._foreign_ports == {8088, 3081}
    with service_manager.WebServiceManager(
        project_root=controller.project_root, data_root=controller.data_dir
    )._lifecycle_lock():
        pass


def test_first_native_switch_requires_actual_installation_preflight(runtime, foreign_native_pair):
    from research_workbench_entrypoint.bootstrap import NativeRuntime, switch_runtime

    controller, runner, _ = runtime
    assert controller.start(open_browser=False)["ok"]
    identity = runner.container["id"]
    native = NativeRuntime(controller.project_root, controller.home)
    assert native.preflight()["issues"] == ["native_environment_missing"]
    report = switch_runtime(controller.store, "native", controller, native, stop_current=True)
    assert report["issues"] == ["native_environment_missing"]
    assert runner.container["id"] == identity and runner.container["running"]
    assert controller.store.read().mode == "docker"


@pytest.mark.parametrize("lock_matches", [True, False])
def test_installed_native_switch_uses_pair_reader_preflight_and_mode_cas(
    runtime, foreign_native_pair, monkeypatch, lock_matches
):
    """Coherent installation facts fixture, not an actual Native/DSH installation."""
    import hashlib

    from test_web_bootstrap import _write_owned_interpreter

    from app.research_web import service_manager
    from research_workbench_entrypoint import bootstrap

    controller, runner, _ = runtime
    assert controller.start(open_browser=False)["ok"]
    identity = runner.container["id"]
    _write_owned_interpreter(controller.project_root, valid_marker=True)
    node = controller.project_root / "fixture-node"
    node.write_text("fixture executable fact")
    monkeypatch.setenv("RESEARCH_NODE_BINARY", str(node))
    closure = "fixture-verified-closure"
    manifest = {
        "schema_version": 1,
        "status": "installed",
        "web_lock_sha256": (
            hashlib.sha256(
                (controller.project_root / "requirements/web.lock").read_bytes()
            ).hexdigest()
            if lock_matches
            else "mismatch"
        ),
        "cjpy_version": service_manager.CJPY_VERSION,
        "cjpy_sha256": service_manager.CJPY_SHA256,
        "dsh_commit": service_manager.PINNED_COMMIT,
        "dsh_closure_sha256": closure,
    }
    path = controller.home / "install/manifest.json"
    path.write_text(json.dumps(manifest))
    path.chmod(0o600)
    build_lock = controller.data_dir / "runtime/build-lock.json"
    build_lock.parent.mkdir(mode=0o700)
    build_lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager.PINNED_COMMIT,
                "closure_sha256": closure,
                "closure_files": 17,
                "mode": "build",
            }
        )
    )
    build_lock.chmod(0o600)
    # Only underlying installed-package, Node-version and accepted DSH asset
    # facts are fixtures. The actual manager combines manifest/lock/marker and
    # validates build-lock.json; neither preflight nor Native.status is mocked.
    monkeypatch.setattr(
        service_manager.WebServiceManager,
        "_installed_package_versions",
        lambda _self: {
            "cjpy": service_manager.CJPY_VERSION,
            "requests": "fixture",
            "urllib3": "fixture",
        },
    )
    monkeypatch.setattr(
        service_manager.WebServiceManager,
        "_executable_version",
        staticmethod(
            lambda executable: "v24.19.0" if executable == str(node) else "Python 3.12.13"
        ),
    )
    monkeypatch.setattr(
        service_manager.WebServiceManager,
        "_dsh_build_status",
        lambda _self: {
            "commit": service_manager.PINNED_COMMIT,
            "ready": True,
            "closure_sha256": closure,
            "closure_files": 17,
        },
    )
    events = []

    def bridge(argv, **kwargs):
        operation = argv[-5]
        report = bootstrap._native_probe(
            operation, Path(argv[-4]), Path(argv[-3]), (int(argv[-2]), int(argv[-1]))
        )
        events.append((operation, report["ok"]))
        return subprocess.CompletedProcess(argv, 0, json.dumps(report), "")

    native = bootstrap.NativeRuntime(controller.project_root, controller.home, runner=bridge)
    preflight = native.preflight()
    assert preflight["ok"] is lock_matches, preflight
    runner.on_stop = lambda: events.append(("docker-stop", True))
    original_write = controller.store.write

    def write(mode, **kwargs):
        if mode == "native":
            assert not runner.container["running"]
            assert controller._foreign_ledger is not None
            assert controller._foreign_safe(native)
            events.append(("mode-cas", True))
        return original_write(mode, **kwargs)

    monkeypatch.setattr(controller.store, "write", write)
    calls_before = len(runner.calls)
    report = bootstrap.switch_runtime(
        controller.store, "native", controller, native, stop_current=True
    )
    if lock_matches:
        assert report["ok"] and report["changed"] and report["mode"] == "native", report
        assert controller.store.read().mode == "native"
        assert not runner.container["running"]
        assert (
            events.index(("preflight", True))
            < events.index(("docker-stop", True))
            < events.index(("mode-cas", True))
        )
        assert [argv for argv, _ in runner.calls[calls_before:] if argv[1] == "stop"] == [
            ["docker", "stop", "--time", "35", identity]
        ]
    else:
        assert preflight["issues"] == ["web_lock_mismatch"]
        assert report["issues"] == ["web_lock_mismatch"]
        assert runner.container["running"] and controller.store.read().mode == "docker"
        assert ("docker-stop", True) not in events and ("mode-cas", True) not in events
    assert runner.container["id"] == identity
    assert not any("up" in argv or argv[1] == "rm" for argv, _ in runner.calls[calls_before:])


def test_foreign_pair_native_scope_captures_and_rechecks_before_spawn(
    runtime, foreign_native_pair, monkeypatch
):
    from app.research_web import service_manager
    from research_workbench_entrypoint import web_bootstrap

    controller, _runner, _ = runtime
    candidate, _states, _processes = foreign_native_pair
    monkeypatch.setattr(service_manager, "listener_pids", web_bootstrap.listener_pids)
    monkeypatch.setattr(service_manager, "probe_process", web_bootstrap.probe_process)
    manager = service_manager.WebServiceManager(
        project_root=controller.project_root, data_root=controller.data_dir
    )
    with manager._lifecycle_lock():
        assert manager._native_quiescent()
        assert manager._foreign_ledger is not None
        manager._assert_foreign_observation()
        path = candidate.parent / "run/web.json"
        replacement = path.with_name("replacement.json")
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(path)
        with pytest.raises(service_manager.ServiceManagerError, match="runtime_ownership_unknown"):
            manager._spawn(manager._processes()[0])
    assert manager._foreign_ledger is None and manager._foreign_scope is None


@pytest.mark.parametrize("change", ["root", "record", "pid", "target-record"])
def test_owned_bridge_child_facts_cannot_authorize_changed_parent(
    runtime, foreign_native_pair, monkeypatch, change
):
    from test_web_bootstrap import _write_owned_interpreter

    from app.research_web import service_manager
    from research_workbench_entrypoint import bootstrap, web_bootstrap
    from research_workbench_entrypoint.web_contract import ProcessFact

    controller, runner, _ = runtime
    candidate, states, processes = foreign_native_pair
    _write_owned_interpreter(controller.project_root, valid_marker=True)
    monkeypatch.setattr(service_manager, "listener_pids", web_bootstrap.listener_pids)
    monkeypatch.setattr(service_manager, "probe_process", web_bootstrap.probe_process)

    def bridge(argv, **kwargs):
        report = bootstrap._native_probe(
            argv[-5], Path(argv[-4]), Path(argv[-3]), (int(argv[-2]), int(argv[-1]))
        )
        assert report["ok"]
        if change == "root":
            candidate.rename(candidate.with_name("old-root"))
            candidate.mkdir(mode=0o700)
        elif change == "record":
            path = candidate.parent / "run/web.json"
            replacement = path.with_name("replacement.json")
            replacement.write_bytes(path.read_bytes())
            replacement.chmod(0o600)
            replacement.replace(path)
        elif change == "pid":
            pid = states["web"]["pid"]
            old = processes[pid]
            processes[pid] = ProcessFact(
                "alive", old.command_line, None, old.argv, old.started_at + 1
            )
        else:
            path = controller.home / "run/web.json"
            path.write_text("{}")
            path.chmod(0o600)
        return subprocess.CompletedProcess(argv, 0, json.dumps(report), "")

    def check():
        native = bootstrap.NativeRuntime(controller.project_root, controller.home, runner=bridge)
        report = native.status()
        assert not controller._native_selection_safe(native, report)
        return {"ok": True}

    assert controller._locked_guard("fixture", check)["ok"]
    assert runner.container is None


@pytest.mark.parametrize("boundary", ["control", "spawn"])
def test_target_unknown_record_refuses_after_foreign_capture(
    runtime, foreign_native_pair, monkeypatch, boundary
):
    controller, runner, _ = runtime
    original = controller._prepare_control_origin

    def prepare(image):
        if boundary == "spawn":
            result = original(image)
        path = controller.home / "run/web.json"
        path.write_text("{}")
        path.chmod(0o600)
        return result if boundary == "spawn" else original(image)

    monkeypatch.setattr(controller, "_prepare_control_origin", prepare)
    report = controller.start(open_browser=False)
    assert report["issues"][0] == "runtime_ownership_unknown", report
    assert not any("up" in argv for argv, _ in runner.calls)
    assert runner.container is None


def test_readonly_foreign_facts_and_external_lease_do_not_grant_write_scope(
    runtime, foreign_native_pair
):
    from app.research_web.lifecycle_lock import LifecycleLock
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, _runner, _ = runtime
    native = NativeRuntime(controller.project_root, controller.home)
    report = native.status()
    assert report["ok"] and native._foreign_hint is not None
    assert controller._foreign_ledger is None
    assert not controller._native_selection_safe(native, report)
    with LifecycleLock(
        controller.home / "run/lifecycle.lock", controller._pid_exists, trusted_root=controller.home
    ) as lease:
        controller._lifecycle_lease = lease
        try:
            assert not controller._native_selection_safe(native, report)
            assert controller._foreign_ledger is None
        finally:
            controller._lifecycle_lease = None


def test_foreign_lease_loss_refuses_even_if_lock_contents_are_restored(
    runtime, foreign_native_pair
):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, _runner, _ = runtime

    def check():
        native = NativeRuntime(controller.project_root, controller.home)
        assert controller._native_selection_safe(native, native.status())
        path = controller.home / "run/lifecycle.lock/owner.json"
        original = path.read_bytes()
        value = json.loads(original)
        value["token"] = "f" * 32
        try:
            path.write_text(json.dumps(value))
            assert not controller._foreign_safe(native)
        finally:
            path.write_bytes(original)
        assert not controller._foreign_safe(native)
        return {"ok": True}

    assert controller._locked_guard("fixture", check)["ok"]


@pytest.mark.parametrize("proof", [True, False, {}, (True,)])
def test_foreign_boolean_or_tuple_is_not_a_proof(runtime, foreign_native_pair, proof):
    controller, _runner, _ = runtime

    def check():
        controller._foreign_attempted = True
        controller._foreign_ledger = proof
        assert not controller._foreign_safe()
        return {"ok": True}

    assert controller._locked_guard("fixture", check)["ok"]


def test_foreign_manager_rejects_new_owned_looking_target_record(runtime, foreign_native_pair):
    from test_web_bootstrap import _service_state

    from app.research_web.service_manager import ServiceManagerError, WebServiceManager

    controller, _runner, _ = runtime
    manager = WebServiceManager(project_root=controller.project_root, data_root=controller.data_dir)
    with manager._lifecycle_lock():
        assert manager._native_quiescent()
        state = _service_state(controller.project_root, controller.data_dir, "web")
        path = controller.home / "run/web.json"
        path.write_text(json.dumps(state))
        path.chmod(0o600)
        with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
            manager._assert_foreign_observation()


def test_foreign_switch_rechecks_target_slot_before_mode_write(
    runtime, foreign_native_pair, monkeypatch
):
    from research_workbench_entrypoint.bootstrap import NativeRuntime, switch_runtime

    controller, runner, _ = runtime
    controller.store.write("native")
    owned(controller, runner)
    runner.container.update(running=False, state="exited")
    original = NativeRuntime.status
    calls = []

    def status(native):
        report = original(native)
        calls.append(report)
        if len(calls) == 3:
            path = controller.home / "run/web.json"
            path.write_text("{}")
            path.chmod(0o600)
        return report

    monkeypatch.setattr(NativeRuntime, "status", status)
    native = NativeRuntime(controller.project_root, controller.home, ports=controller.ports)
    report = switch_runtime(controller.store, "docker", controller, native, stop_current=True)
    assert report["issues"] == ["runtime_ownership_unknown"], report
    assert controller.store.read().mode == "native"
    assert not runner.container["running"]
    assert not any("up" in argv or argv[1] in ("stop", "rm") for argv, _ in runner.calls)


@pytest.fixture
def foreign_spawn_scope(runtime, foreign_native_pair, monkeypatch):
    from app.research_web import service_manager
    from research_workbench_entrypoint import bootstrap, web_bootstrap, web_contract
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    controller, _runner, _ = runtime
    _candidate, _states, processes = foreign_native_pair
    manager = service_manager.WebServiceManager(
        project_root=controller.project_root,
        data_root=controller.data_dir,
        web_port=controller.ports[0],
        runtime_port=controller.ports[1],
    )
    process = manager._processes()[1]
    listeners = {}
    original_listener = web_bootstrap.listener_pids

    def observe(port):
        return listeners.get(port, original_listener(port))

    for module in (service_manager, bootstrap, web_bootstrap, web_contract):
        monkeypatch.setattr(module, "listener_pids", observe)

    class Child:
        pid = 778899
        returncode = None

        def poll(self):
            return self.returncode

        def wait(self, **kwargs):
            self.returncode = 0
            return 0

    child = Child()

    def popen(argv, **kwargs):
        processes[child.pid] = ProcessFact(
            "alive", "fixture-owned-child", None, tuple(argv), time.time()
        )
        listeners[process.port] = ListenerFact("listening", (child.pid,), None)
        return child

    monkeypatch.setattr(service_manager.subprocess, "Popen", popen)
    monkeypatch.setattr(manager, "_protocol_health", lambda _process: True)
    with manager._lifecycle_lock():
        manager._prepare_private_directories()
        manager._active_spawn_attempt = []
        assert manager._native_quiescent()
        yield manager, process, child, processes, listeners


@pytest.mark.parametrize("boundary", ["after-popen", "second-registration"])
def test_foreign_spawn_lock_loss_reaps_exact_child(foreign_spawn_scope, monkeypatch, boundary):
    from app.research_web import service_manager

    manager, process, child, _processes, _listeners = foreign_spawn_scope
    original = manager._record_attempt_spawn
    terminated = []
    calls = []

    def register(*args, **kwargs):
        calls.append(True)
        if len(calls) == (1 if boundary == "after-popen" else 2):
            raise service_manager.LifecycleLockError("lost", code="lifecycle_lock_ownership_lost")
        return original(*args, **kwargs)

    monkeypatch.setattr(manager, "_record_attempt_spawn", register)
    monkeypatch.setattr(
        manager, "_terminate_failed_spawn", lambda actual: terminated.append(actual)
    )
    with pytest.raises(service_manager.LifecycleLockError, match="lost"):
        manager._spawn_and_wait(process)
    assert terminated == [child]


@pytest.mark.parametrize("change", ["record-inode", "argv", "start", "listener"])
def test_foreign_spawn_observation_rejects_record_or_process_changes(foreign_spawn_scope, change):
    from app.research_web.service_manager import ServiceManagerError
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    manager, process, child, processes, listeners = foreign_spawn_scope
    assert manager._spawn_and_wait(process) == child.pid
    manager._assert_foreign_observation()
    if change == "record-inode":
        path = manager._state_path(process.role)
        replacement = path.with_name("same-content.json")
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(path)
    elif change == "listener":
        listeners[process.port] = ListenerFact("listening", (child.pid, 998877), None)
    else:
        old = processes[child.pid]
        processes[child.pid] = ProcessFact(
            "alive",
            old.command_line,
            None,
            (*old.argv, "extra") if change == "argv" else old.argv,
            old.started_at + 1 if change == "start" else old.started_at,
        )
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()


def test_foreign_spawn_changed_record_refuses_rollback(foreign_spawn_scope, monkeypatch):
    from app.research_web.service_manager import ServiceManagerError

    manager, process, child, _processes, _listeners = foreign_spawn_scope
    manager._spawn_and_wait(process)
    path = manager._state_path(process.role)
    replacement = path.with_name("same-content.json")
    replacement.write_bytes(path.read_bytes())
    replacement.chmod(0o600)
    replacement.replace(path)
    terminated = []

    def unexpected(*args, **kwargs):
        terminated.append(args)
        raise ServiceManagerError("unexpected-stop")

    monkeypatch.setattr(manager, "_terminate_pid", unexpected)
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._rollback_spawned(process, child.pid)
    assert not terminated


def test_foreign_spawn_closed_to_owned_listener_is_one_time_binding(
    foreign_spawn_scope, monkeypatch
):
    from app.research_web import service_manager
    from research_workbench_entrypoint.web_contract import ListenerFact

    manager, process, child, _processes, listeners = foreign_spawn_scope
    original = service_manager.subprocess.Popen

    def pending(*args, **kwargs):
        actual = original(*args, **kwargs)
        listeners[process.port] = ListenerFact("closed", (), None)
        return actual

    monkeypatch.setattr(service_manager.subprocess, "Popen", pending)
    monkeypatch.setattr(
        service_manager.time,
        "sleep",
        lambda _delay: listeners.__setitem__(
            process.port, ListenerFact("listening", (child.pid,), None)
        ),
    )
    assert manager._spawn_and_wait(process) == child.pid
    witness = manager._foreign_started[(process.role, child.pid)]
    baseline = witness["facts"]
    assert witness["phase"] == "bound" and baseline[1].pids == (child.pid,)
    manager._record_attempt_spawn(process, child.pid)
    assert witness["facts"] is baseline
    listeners[process.port] = ListenerFact("closed", (), None)
    with pytest.raises(service_manager.ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()
    listeners[process.port] = baseline[1]
    with pytest.raises(service_manager.ServiceManagerError, match="runtime_ownership_unknown"):
        manager._record_attempt_spawn(process, child.pid)
    assert witness["facts"] is baseline


def test_foreign_spawn_unknown_rollback_keeps_original_health_error(
    foreign_spawn_scope, monkeypatch
):
    from app.research_web.service_manager import ServiceManagerError

    manager, process, child, _processes, _listeners = foreign_spawn_scope
    original = manager._wait_for_ready

    def fail(*args, **kwargs):
        original(*args, **kwargs)
        path = manager._state_path(process.role)
        replacement = path.with_name("same-content.json")
        replacement.write_bytes(path.read_bytes())
        replacement.chmod(0o600)
        replacement.replace(path)
        raise ServiceManagerError("web_health_timeout", code="web_health_timeout")

    terminated = []
    monkeypatch.setattr(manager, "_wait_for_ready", fail)
    monkeypatch.setattr(manager, "_terminate_pid", lambda *args, **kwargs: terminated.append(args))
    with pytest.raises(ServiceManagerError) as caught:
        manager._spawn_and_wait(process)
    assert caught.value.code == "web_health_timeout"
    assert not terminated and child.poll() is None


def test_foreign_unknown_target_slot_removal_does_not_restore_manager_capability(
    foreign_spawn_scope, monkeypatch
):
    from app.research_web.service_manager import ServiceManagerError

    manager, process, child, _processes, _listeners = foreign_spawn_scope
    manager._spawn_and_wait(process)
    unknown = manager._state_path("runtime")
    unknown.write_text("{}")
    unknown.chmod(0o600)
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()
    unknown.unlink()
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()
    signalled = []
    monkeypatch.setattr(manager, "_terminate_pid", lambda *args, **kwargs: signalled.append(args))
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._rollback_spawned(process, child.pid)
    assert not signalled and child.poll() is None


def test_foreign_unknown_target_slot_removal_does_not_restore_docker_rollback(
    runtime, foreign_native_pair
):
    from research_workbench_entrypoint.docker_runtime import ControlError

    controller, runner, _ = runtime

    def check():
        assert controller.start(open_browser=False)["ok"]
        assert controller._created_container is not None
        unknown = controller.home / "run/runtime.json"
        unknown.write_text("{}")
        unknown.chmod(0o600)
        assert not controller._foreign_safe()
        unknown.unlink()
        assert not controller._foreign_safe()
        with pytest.raises(ControlError, match="docker_rollback_failed"):
            controller._rollback_created()
        assert runner.container["running"]
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)
        return {"ok": True}

    assert controller._locked_guard("fixture", check)["ok"]


def test_foreign_target_slot_io_failure_never_restores_same_scope(
    runtime, foreign_native_pair, monkeypatch
):
    from research_workbench_entrypoint.docker_runtime import ControlError

    controller, runner, _ = runtime
    original = Path.lstat
    failing = {"enabled": False}
    target = controller.home / "run/runtime.json"

    def lstat(path):
        if path == target and failing["enabled"]:
            raise PermissionError("fixture target observation I/O")
        return original(path)

    monkeypatch.setattr(Path, "lstat", lstat)

    def check():
        assert controller.start(open_browser=False)["ok"]
        failing["enabled"] = True
        report = controller._guard("fixture_io", controller._foreign_safe)
        assert report["issues"] == ["docker_io"]
        failing["enabled"] = False
        assert not controller._foreign_safe()
        with pytest.raises(ControlError, match="docker_rollback_failed"):
            controller._rollback_created()
        assert runner.container["running"]
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)
        return {"ok": True}

    assert controller._locked_guard("fixture", check)["ok"]


def test_foreign_exact_owned_stop_keeps_legitimate_exit_valid(foreign_spawn_scope, monkeypatch):
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    manager, process, child, processes, listeners = foreign_spawn_scope
    manager._spawn_and_wait(process)

    def terminate(pid, **kwargs):
        assert pid == child.pid
        child.returncode = 0
        processes[pid] = ProcessFact("missing", None, None)
        listeners[process.port] = ListenerFact("closed", (), None)

    monkeypatch.setattr(manager, "_terminate_pid", terminate)
    assert manager._stop_owned_probe(process, manager._probe_service(process))
    manager._assert_foreign_observation()
    assert manager._foreign_started[(process.role, child.pid)]["phase"] == "stopped"
    assert not manager._foreign_ledger._invalid


def test_foreign_unexplained_exit_cannot_restore_scope_when_facts_reappear(foreign_spawn_scope):
    from app.research_web.service_manager import ServiceManagerError
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    manager, process, child, processes, listeners = foreign_spawn_scope
    manager._spawn_and_wait(process)
    before = processes[child.pid], listeners[process.port]
    child.returncode = 1
    processes[child.pid] = ProcessFact("missing", None, None)
    listeners[process.port] = ListenerFact("closed", (), None)
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()
    # Explicit adversarial OS/child fixture reversal: observed failure is not a
    # new permission baseline, even if later facts again look identical.
    child.returncode = None
    processes[child.pid], listeners[process.port] = before
    with pytest.raises(ServiceManagerError, match="runtime_ownership_unknown"):
        manager._assert_foreign_observation()


@pytest.mark.parametrize("default_only", [False, True])
def test_fix3_missing_environment_other_checkout_can_share_env_data_root(
    runtime, monkeypatch, default_only
):
    from research_workbench_entrypoint import bootstrap
    from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact

    controller, _runner, _record = runtime
    controller.data_dir.mkdir(mode=0o700)
    monkeypatch.setenv("RESEARCH_DATA_HOME", str(controller.data_dir))
    argv = ("python", "-m", "uvicorn", "app.research_web.main:app", "--app-dir", "/other/checkout")
    monkeypatch.setattr(
        bootstrap,
        "listener_pids",
        lambda port: (
            ListenerFact("listening", (456,), None)
            if not default_only or port == 8088
            else ListenerFact("closed", (), None)
        ),
    )
    monkeypatch.setattr(
        bootstrap, "probe_process", lambda pid: ProcessFact("alive", None, None, argv, 123.0)
    )
    report = bootstrap.NativeRuntime(
        controller.project_root, controller.home, ports=controller.ports
    ).status()
    assert report["issues"] == ["runtime_ownership_unknown"], report


@pytest.mark.parametrize("replacement", ["launch", "image", "installation", "mount"])
def test_fix1_started_existing_cleanup_refuses_replaced_identity(runtime, monkeypatch, replacement):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
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
        "docker",
        "compose",
        "--project-name",
        "rwb-" + record.installation_id[:12],
        "--project-directory",
        str(controller.project_root),
        "-f",
        str(controller.project_root / "compose.yaml"),
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
    from research_workbench_entrypoint.platform_capabilities import (
        platform_capabilities,
    )

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
    assert report["volumes"]["state"] == "tmpfs"
    assert report["ports"]["verified"]
    assert report["python"]["applicable"] is False
    assert report["cjpy"]["applicable"] is False
    assert report["capabilities"]["office"]["status"] == "unavailable_in_docker"
    assert report["capabilities"] == platform_capabilities("docker")
    assert report["services"]["runtime"]["pid"] is None
    assert report["dsh"]["ready"] is True
    assert report["dsh"]["build_verified"] is True
    raw = json.dumps(report)
    assert str(controller.home) not in raw and str(controller.project_root) not in raw
    assert record.installation_id not in raw
    assert "Env" not in raw and "Cookie" not in raw


@pytest.mark.parametrize(
    "health,code",
    [("unhealthy", "docker_services_unhealthy"), ("starting", "docker_ready_timeout")],
)
def test_start_existing_unhealthy_fails_without_removing(runtime, health, code):
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    controller.endpoint_store.publish("native", *controller.ports, expected=None)
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


@pytest.mark.parametrize(
    "health,running,code",
    [
        ("unhealthy", True, "docker_services_unhealthy"),
        ("starting", False, "docker_start_failed"),
        ("starting", True, "docker_ready_timeout"),
    ],
)
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
            runner.container.update(
                health=health, running=running, state="running" if running else "exited"
            )
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


@pytest.mark.parametrize(
    "mutation,code",
    [
        ("json", "docker_manifest_invalid"),
        ("symlink", "docker_manifest_invalid"),
        ("hardlink", "docker_manifest_invalid"),
        ("large", "docker_manifest_invalid"),
        ("lock", "docker_build_contract_mismatch"),
        ("compose", "docker_build_contract_mismatch"),
        ("dsh", "docker_build_contract_mismatch"),
    ],
)
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
        (
            controller.project_root
            / ("requirements/web.lock" if mutation == "lock" else "compose.yaml")
        ).write_text("changed")
    else:
        value = json.loads(path.read_text())
        value["dsh_commit"] = "0" * 40
        path.write_text(json.dumps(value))
    assert controller.start(open_browser=False)["issues"] == [code]
    assert not any("up" in argv for argv, _ in runner.calls)


def test_overwritten_mutable_tag_cannot_change_accepted_image(runtime):
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    controller.endpoint_store.publish("native", *controller.ports, expected=None)
    owned(controller, runner)

    def retagged(argv, **kwargs):
        if argv[1:3] == ["image", "inspect"] and not argv[-1].startswith("sha256:"):
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"id": "sha256:" + "a" * 64, "runtime": "docker"}), ""
            )
        return runner(argv, **kwargs)

    controller.runner = retagged
    assert controller.start(open_browser=False)["ok"]
    assert all(
        argv[-1].startswith("sha256:")
        for argv, _ in runner.calls
        if argv[1:3] == ["image", "inspect"]
    )


def test_doctor_rejects_container_outside_accepted_image(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["image"] = "sha256:" + "a" * 64

    def immutable(argv, **kwargs):
        if argv[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"id": argv[-1], "runtime": "docker"}), ""
            )
        return runner(argv, **kwargs)

    controller.runner = immutable
    assert controller.doctor()["issues"] == ["docker_image_mismatch"]


def test_candidate_does_not_override_public_missing_manifest(runtime):
    controller, _, _ = runtime
    controller._candidate_image = "sha256:" + "b" * 64
    (controller.home / "install/docker-manifest.json").unlink()
    assert controller.start(open_browser=False)["issues"] == ["docker_manifest_missing"]


@pytest.mark.parametrize(
    "failure", ["none", "unhealthy", "publish", "no_start", "race", "up_exit", "up_timeout"]
)
def test_explicit_repair_disposes_only_stopped_owned_container_and_keeps_fallback(
    runtime, monkeypatch, failure
):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from scripts import setup_web

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
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
            return subprocess.CompletedProcess(
                argv, 0, json.dumps({"id": identity, "runtime": "docker"}), ""
            )
        if "up" in argv:
            owned(installer, runner)
            runner.container.update(id="d" * 64, image=kwargs["env"]["RWB_IMAGE"])
            if failure == "unhealthy" and runner.container["image"] == candidate_image:
                runner.container["health"] = "unhealthy"
            if (
                failure in ("up_exit", "up_timeout")
                and runner.container["image"] == candidate_image
            ):
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

    installer = setup_web.DockerRuntime(
        controller.project_root, controller.home, runner=launch, ports=controller.ports
    )
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
        assert (
            installer.install(repair=True, start=failure != "no_start")["image_id"]
            == candidate_image
        )
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


@pytest.mark.parametrize(
    "after", ["owned", "foreign", "image", "concurrent", "unreadable", "existing", "rm_failure"]
)
@pytest.mark.parametrize("failure", ["exit", "timeout"])
def test_up_created_then_failed_recovers_only_this_launch(runtime, monkeypatch, after, failure):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError

    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    monkeypatch.setattr(controller, "_ports_free", lambda: None)
    if after == "existing":
        controller.data_dir.mkdir(mode=0o700)
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


@pytest.mark.parametrize("ownership", ["absent", "verified", "invalid"])
def test_doctor_volume_types_follow_private_state_contract_without_creating_paths(
    runtime, ownership
):
    controller, runner, _ = runtime
    if ownership != "absent":
        owned(controller, runner)
    if ownership == "invalid":
        runner.container["tmpfs"]["/state"] = "rw,mode=755"
    report = controller.doctor()
    assert report["schema_version"] == 1
    assert report["volumes"] == {
        "verified": ownership == "verified",
        "data": "bind",
        "state": "tmpfs",
        "logs": "bind",
        "credentials": "bind",
    }
    assert not (controller.state_dir / "logs").exists()
    assert not any("up" in argv or argv[1] in ("start", "stop", "rm") for argv, _ in runner.calls)


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


@pytest.mark.parametrize(
    "bindings",
    [
        {},
        {"8088/tcp": [{"HostIp": "0.0.0.0", "HostPort": "18088"}]},
        {"3081/tcp": [{"HostIp": "127.0.0.1", "HostPort": "13081"}]},
    ],
)
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
    run_bounded(
        [sys.executable, "-c", command],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        timeout=2,
        stream=True,
    )
    assert "fake-secret" not in output.getvalue() and "ready" in output.getvalue()


@pytest.mark.parametrize("control", ["\x00", "\x1b", "\x07", "\x1c", "\r", "\t"])
def test_docker_stream_normalizes_controls_before_redaction(tmp_path, monkeypatch, control):
    import io

    from research_workbench_entrypoint.docker_runtime import run_bounded

    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    command = "print(" + repr(f"Coo{control}kie: fake-session-value") + ")"
    run_bounded(
        [sys.executable, "-c", command],
        cwd=tmp_path,
        env={"PATH": os.defpath},
        timeout=2,
        stream=True,
    )
    assert "fake-session-value" not in output.getvalue()


def test_bounded_stream_redaction_cannot_expand_output_past_cap(tmp_path, monkeypatch):
    import io

    from research_workbench_entrypoint.docker_runtime import ControlError, run_bounded

    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    with pytest.raises(ControlError, match="runtime_output_limit"):
        run_bounded(
            [sys.executable, "-c", "print('token\\n' * 150)"],
            cwd=tmp_path,
            env={"PATH": os.defpath},
            timeout=2,
            stream=True,
            max_output=1000,
        )
    assert len(output.getvalue().encode()) <= 1000


@pytest.mark.parametrize(
    "failure,code",
    [
        (("--version", FileNotFoundError()), "docker_cli_missing"),
        (("info", 1), "docker_daemon_unavailable"),
        (("compose", 1), "docker_compose_missing"),
        (("image", 1), "docker_build_not_ready"),
    ],
)
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
@pytest.mark.parametrize(
    "field", ["project", "service", "installation", "runtime", "working_dir", "mounts"]
)
def test_foreign_ownership_blocks_every_action(runtime, operation, field):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container[field] = [] if field == "mounts" else "foreign"
    result = getattr(controller, operation)()
    if operation == "logs":
        assert result == 1
    else:
        assert result["issues"] == ["docker_ownership_mismatch"]
    assert not any(
        call[0][1] == "stop" or "up" in call[0] or "logs" in call[0] for call in runner.calls
    )


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
        self.ports = (8088, 3081)

    def preflight(self):
        self.events.append("preflight")
        return {"ok": True, "issues": []}

    def status(self):
        self.events.append("status")
        return {
            "ok": True,
            "issues": [],
            "services": {"web": {"running": self.running}, "runtime": {"running": self.running}},
        }

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
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == [
        "docker_build_not_ready"
    ]
    assert "stop" not in native.events
    assert store.read().mode == "native"
    runner.failure = None
    assert switch_runtime(store, "docker", controller, native)["issues"] == [
        "runtime_stop_current_required"
    ]
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
        result = switch_runtime(
            store, "docker", controller, Native(True), stop_current=True, wait_timeout=0.05
        )
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
        run_bounded(
            [sys.executable, "-c", "print('x'*100000)"],
            cwd=tmp_path,
            env={"PATH": os.defpath},
            timeout=2,
            max_output=1000,
        )
    with pytest.raises(ControlError, match="runtime_command_timeout"):
        run_bounded(
            [sys.executable, "-c", "import time;time.sleep(5)"],
            cwd=tmp_path,
            env={"PATH": os.defpath},
            timeout=0.05,
            max_output=1000,
        )


def test_switch_refuses_other_runtime_and_rechecks_stopped(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, runner, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    owned(controller, runner)
    native = Native()
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == [
        "runtime_other_running"
    ]
    assert "stop" not in native.events
    runner.container = None
    native.running = True
    native.stop = lambda: {"ok": True, "issues": []}
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == [
        "runtime_stop_failed"
    ]
    assert store.read().mode == "native"


def test_unknown_native_state_is_never_stopped(runtime):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _, _ = runtime
    store = RuntimeModeStore(controller.home)
    store.write("native")
    native = Native()
    native.status = lambda: {"ok": False, "issues": ["runtime_ownership_unknown"]}
    assert switch_runtime(store, "docker", controller, native)["issues"] == [
        "runtime_stop_current_required"
    ]
    assert switch_runtime(store, "docker", controller, native, stop_current=True)["issues"] == [
        "runtime_ownership_unknown"
    ]
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


def test_private_runtime_tmpfs_is_owned_and_host_control_state_is_retained(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    for directory in (
        controller.home / "run",
        controller.home / "run/docker",
        controller.state_dir,
    ):
        directory.mkdir(mode=0o700)
    control = controller.state_dir / "control-fixture.json"
    control.write_text("installation-control")
    assert controller.stop()["ok"]
    assert control.read_text() == "installation-control"


@pytest.mark.parametrize(
    "platform,expected_timeout", [("darwin", 120), ("linux", 10), ("win32", 10)]
)
def test_stop_default_wait_keeps_real_nonlistening_reservation_until_host_deadline(
    runtime, monkeypatch, platform, expected_timeout
):
    from research_workbench_entrypoint import docker_runtime as control

    controller, runner, _ = runtime
    owned(controller, runner)
    elapsed = [0.0]
    monkeypatch.setattr(control.sys, "platform", platform)
    monkeypatch.setattr(
        control,
        "time",
        SimpleNamespace(
            monotonic=lambda: elapsed[0],
            sleep=lambda interval: elapsed.__setitem__(0, elapsed[0] + interval),
        ),
    )
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", controller.ports[0]))
        assert control.port_busy(controller.ports[0])
        assert controller.stop()["issues"] == ["runtime_ports_not_released"]
        assert expected_timeout <= elapsed[0] < expected_timeout + 0.1
        assert control.port_busy(controller.ports[0])
    assert not any(argv[1] == "rm" for argv, _ in runner.calls)


@pytest.mark.parametrize("explicit_timeout", [None, 0, 5])
def test_macos_stop_waits_for_delayed_release_but_honors_explicit_timeout(
    runtime, monkeypatch, explicit_timeout
):
    from research_workbench_entrypoint import docker_runtime as control

    controller, runner, _ = runtime
    owned(controller, runner)
    elapsed = [0.0]
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", controller.ports[0]))

        def wait(interval):
            elapsed[0] += interval
            if elapsed[0] >= 12:
                reservation.close()

        monkeypatch.setattr(control.sys, "platform", "darwin")
        monkeypatch.setattr(
            control, "time", SimpleNamespace(monotonic=lambda: elapsed[0], sleep=wait)
        )
        options = {} if explicit_timeout is None else {"wait_timeout": explicit_timeout}
        report = controller.stop(**options)
        if explicit_timeout is None:
            assert report["ok"]
            assert 12 <= elapsed[0] < 12.1
        else:
            assert report["issues"] == ["runtime_ports_not_released"]
            assert explicit_timeout <= elapsed[0] < explicit_timeout + 0.1
            assert control.port_busy(controller.ports[0])


@pytest.mark.parametrize("mounts_listed", [False, True])
def test_engine_tmpfs_mount_projection_accepts_complete_or_host_config_only(runtime, mounts_listed):
    controller, runner, _ = runtime
    owned(controller, runner)
    if not mounts_listed:
        runner.container["mounts"] = [
            item for item in runner.container["mounts"] if item["Type"] == "bind"
        ]
    assert controller.status()["ok"]
    assert controller.doctor()["volumes"]["verified"]


@pytest.mark.parametrize(
    "mutation",
    ["partial", "extra", "duplicate", "alias", "missing_options", "foreign_uid", "public_mode"],
)
def test_host_config_only_tmpfs_rejects_partial_or_unsafe_projection(runtime, mutation):
    controller, runner, _ = runtime
    owned(controller, runner)
    state = next(item for item in runner.container["mounts"] if item["Destination"] == "/state")
    runner.container["mounts"] = [
        item for item in runner.container["mounts"] if item["Type"] == "bind"
    ]
    if mutation in {"partial", "extra", "duplicate", "alias"}:
        runner.container["mounts"].append(state)
        if mutation == "extra":
            state["Destination"] = "/foreign"
        elif mutation == "duplicate":
            runner.container["mounts"].append(dict(state))
        elif mutation == "alias":
            state["Destination"] = "/state/."
    elif mutation == "missing_options":
        runner.container["tmpfs"].pop("/state")
    else:
        original, changed = (
            ("uid=10001", "uid=0") if mutation == "foreign_uid" else ("mode=700", "mode=755")
        )
        runner.container["tmpfs"]["/state"] = runner.container["tmpfs"]["/state"].replace(
            original, changed
        )
    assert controller.stop()["issues"] == ["docker_ownership_mismatch"]
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in runner.calls)


@pytest.mark.parametrize(
    "mutation",
    [
        "state_bind",
        "state_volume",
        "state_source",
        "missing_state",
        "duplicate_state",
        "missing_options",
        "foreign_uid",
        "foreign_gid",
        "public_mode",
        "missing_nosuid",
        "missing_nodev",
        "readonly",
        "duplicate_option",
        "extra_option",
        "extra_tmpfs",
        "invalid_options",
    ],
)
def test_runtime_tmpfs_contract_rejects_unsafe_ownership_without_mutation(runtime, mutation):
    controller, runner, _ = runtime
    owned(controller, runner)
    state = next(item for item in runner.container["mounts"] if item["Destination"] == "/state")
    options = runner.container["tmpfs"]
    if mutation in {"state_bind", "state_volume"}:
        state["Type"] = "bind" if mutation == "state_bind" else "volume"
        state["Source"] = str(controller.state_dir)
    elif mutation == "state_source":
        state["Source"] = "/foreign"
    elif mutation == "missing_state":
        runner.container["mounts"].remove(state)
    elif mutation == "duplicate_state":
        runner.container["mounts"].append(dict(state))
    elif mutation == "missing_options":
        options.pop("/state")
    elif mutation == "extra_tmpfs":
        options["/foreign"] = "rw"
    elif mutation == "invalid_options":
        options["/state"] = []
    else:
        replacements = {
            "foreign_uid": ("uid=10001", "uid=0"),
            "foreign_gid": ("gid=10001", "gid=0"),
            "public_mode": ("mode=700", "mode=755"),
            "missing_nosuid": ("nosuid,", ""),
            "missing_nodev": ("nodev,", ""),
            "readonly": ("rw,", "ro,"),
            "duplicate_option": ("rw,", "rw,rw,"),
            "extra_option": ("rw,", "rw,exec,"),
        }
        options["/state"] = options["/state"].replace(*replacements[mutation])
    assert controller.stop()["issues"] == ["docker_ownership_mismatch"]
    assert not any(argv[1] in {"stop", "rm"} for argv, _ in runner.calls)


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


def test_native_probe_preserves_stale_state_and_refuses_foreign_before_stop(
    tmp_path, monkeypatch, available_ports
):
    from app.research_web import service_manager as manager_module
    from app.research_web.service_manager import WebServiceManager
    from research_workbench_entrypoint.bootstrap import _native_probe
    from research_workbench_entrypoint.web_contract import ListenerFact

    monkeypatch.setattr(
        manager_module, "listener_pids", lambda port: ListenerFact("closed", (), None)
    )

    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    run = home / "run"
    run.mkdir(parents=True, mode=0o700)
    manager = WebServiceManager(
        project_root=tmp_path,
        data_root=home / "research-web",
        web_port=available_ports[0],
        runtime_port=available_ports[1],
    )
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


@pytest.mark.parametrize("stage", ["precheck", "child", "postcheck"])
def test_native_bridge_status_logs_existing_rejection_stage(
    tmp_path, available_ports, monkeypatch, caplog, stage
):
    from research_workbench_entrypoint import bootstrap

    home = tmp_path / "home"
    (home / "research-web").mkdir(parents=True, mode=0o700)
    monkeypatch.setattr(bootstrap, "native_python", lambda root: Path(sys.executable))
    monkeypatch.setattr(
        bootstrap, "classify_python_environment", lambda root: SimpleNamespace(issue=None)
    )
    child = {
        "ok": stage != "child",
        "issues": ["SECRET=hunter2"] if stage == "child" else [],
        "services": {role: {"running": False} for role in ("web", "runtime")},
    }
    calls = []
    safety_checks = []

    def runner(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, json.dumps(child), "SECRET stderr")

    controller = bootstrap.NativeRuntime(tmp_path, home, runner=runner, ports=available_ports)

    def safe(root):
        safety_checks.append(root)
        return stage != "precheck" and not (stage == "postcheck" and len(safety_checks) == 2)

    monkeypatch.setattr(controller, "_missing_ledger_listeners_safe", safe)
    report = controller.status()
    if stage == "child":
        assert report == child
    else:
        assert report == {
            "schema_version": 1,
            "ok": False,
            "issues": ["runtime_ownership_unknown"],
            "mode": "native",
        }
    assert len(safety_checks) == (2 if stage == "postcheck" else 1)
    assert len(calls) == (0 if stage == "precheck" else 1)
    if calls:
        assert calls[0][1]["timeout"] == 40
    messages = [
        record.getMessage() for record in caplog.records if record.name == bootstrap.__name__
    ]
    code = "report_not_ok" if stage == "child" else "runtime_ownership_unknown"
    assert f"native_probe phase=status_{stage} code={code}" in messages
    assert all("SECRET" not in message and "hunter2" not in message for message in messages)


def test_native_bridge_subprocess_with_temporary_home_does_not_write(tmp_path, available_ports):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.web_contract import listener_pids, probe_process

    root = Path(__file__).resolve().parents[2]
    home = tmp_path / "absent"
    controller = NativeRuntime(root, home, ports=available_ports)
    facts = [probe_process(pid) for port in (8088, 3081) for pid in listener_pids(port).pids]
    product_writer = any(
        fact.argv
        and any("app.research_web.main" in arg or "apps/cli/lib/bin.js" in arg for arg in fact.argv)
        for fact in facts
    )
    report = controller.status()
    if product_writer:
        assert report["issues"] == ["runtime_ownership_unknown"], report
    else:
        assert report["ok"], report
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
    assert up[-7:] == [
        "up",
        "--detach",
        "--no-build",
        "--pull",
        "never",
        "--no-recreate",
        "research-web",
    ]
    assert controller.data_dir.is_dir()
    assert controller.state_dir.is_dir()
    assert (controller.state_dir / "logs").stat().st_mode & 0o777 == 0o700
    assert controller.credential_dir.is_dir()


def test_malformed_inspect_mounts_return_safe_error(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["mounts"][0]["Destination"] = []
    assert controller.status()["issues"] == ["docker_ownership_mismatch"]


@pytest.mark.parametrize("kind", ["alias", "mode", "foreign"])
def test_private_host_logs_refuse_unsafe_existing_child(runtime, monkeypatch, kind):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    (controller.home / "run").mkdir(mode=0o700)
    controller.state_dir.mkdir(parents=True, mode=0o700)
    logs = controller.state_dir / "logs"
    if kind == "alias":
        logs.symlink_to(controller.state_dir, target_is_directory=True)
    else:
        logs.mkdir(mode=0o700)
        if kind == "mode":
            logs.chmod(0o755)
        else:
            original = Path.lstat

            def foreign(path):
                info = original(path)
                if path == logs:
                    values = list(info)
                    values[4] += 9876
                    return os.stat_result(values)
                return info

            monkeypatch.setattr(Path, "lstat", foreign)
    assert controller.start(open_browser=False)["issues"] == ["docker_data_home_unsafe"]
    assert not any("up" in argv for argv, _ in runner.calls)


def test_private_host_logs_creation_preserves_legacy_runtime(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, runner, _ = runtime
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())
    (controller.home / "run").mkdir(mode=0o700)
    controller.state_dir.mkdir(parents=True, mode=0o700)
    legacy = controller.state_dir / "runtime"
    legacy.mkdir(parents=True, mode=0o700)
    record = legacy / "auth.json"
    record.write_bytes(b"legacy-auth-retained")
    record.chmod(0o600)
    before = record.stat()

    def on_up(argv, **kwargs):
        if "up" in argv:
            owned(controller, runner)
        return runner(argv, **kwargs)

    controller.runner = on_up
    assert controller.start(open_browser=False)["ok"]
    assert record.read_bytes() == b"legacy-auth-retained"
    assert record.stat().st_ino == before.st_ino
    assert (controller.state_dir / "logs").stat().st_mode & 0o777 == 0o700


def test_start_opens_only_verified_runtime_url(runtime, monkeypatch):
    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    controller.endpoint_store.publish("native", *controller.ports, expected=None)
    owned(controller, runner)
    opened = []
    monkeypatch.setattr("webbrowser.open", lambda url: opened.append(url) or True)
    assert controller.start()["ok"]
    assert opened == [f"http://127.0.0.1:{controller.ports[0]}/#/fingpt"]
    assert controller.start(open_browser=False)["ok"]
    assert len(opened) == 1


@pytest.mark.parametrize("overflow", [False, True])
@pytest.mark.parametrize("parent_ignores_term", [False, True])
def test_bounded_runner_kills_descendants_but_not_unrelated(
    tmp_path, overflow, parent_ignores_term
):
    from research_workbench_entrypoint.docker_runtime import ControlError, port_busy, run_bounded

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
        with pytest.raises(
            ControlError, match="runtime_output_limit" if overflow else "runtime_command_timeout"
        ):
            run_bounded(
                [sys.executable, "-c", script],
                cwd=tmp_path,
                env=dict(os.environ),
                timeout=1.5,
                max_output=1000,
            )
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
    runner = subprocess.Popen(
        [sys.executable, "-c", runner_script],
        cwd=Path(__file__).resolve().parents[2],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    unrelated = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    owned = None
    try:
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
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


def test_bounded_runner_cleanup_error_is_visible_with_original_interrupt(
    tmp_path, monkeypatch, caplog
):
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

    monkeypatch.setattr(
        runtime,
        "threading",
        SimpleNamespace(
            Event=InterruptedEvent,
            Thread=threading.Thread,
        ),
    )
    monkeypatch.setattr(runtime, "_terminate_command_tree", failed_cleanup)
    with pytest.raises(KeyboardInterrupt) as caught:
        runtime.run_bounded(
            [sys.executable, "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout=30,
        )
    assert "runtime_process_tree_cleanup_failed" in " ".join(caught.value.__notes__)
    assert "runtime_process_tree_cleanup_failed" in caplog.text


def test_docker_free_port_check_ignores_host_runtime_listener(runtime):
    controller, _runner, _record = runtime
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", controller.ports[1]))
        foreign.listen()
        controller._ports_free()


def test_docker_status_restores_persisted_web_endpoint(runtime):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore

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
    with LifecycleLock(
        controller.home / "run/lifecycle.lock", lambda pid: True, trusted_root=controller.home
    ):
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
def test_docker_origin_transaction_preserves_tokens_and_rolls_back(
    runtime, monkeypatch, publish_failure
):
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointError, EndpointStore

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
    old_origin = "http://127.0.0.1:48220"
    EndpointStore(controller.home).publish("native", 48220, 48221, expected=None)
    originals = [
        load_control(controller.data_dir, old_origin),
        load_mcp(controller.data_dir, old_origin),
    ]
    before = [
        (controller.data_dir / ".control" / name).read_bytes()
        for name in ("datahub.json", "mcp-runtime.json")
    ]
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())

    def launch(argv, **kwargs):
        if "up" in argv:
            assert (
                load_control(controller.data_dir, "http://127.0.0.1:8088")["token"]
                == originals[0]["token"]
            )
            assert (
                load_mcp(controller.data_dir, "http://127.0.0.1:8088")["token"]
                == originals[1]["token"]
            )
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
        assert [
            (controller.data_dir / ".control" / name).read_bytes()
            for name in ("datahub.json", "mcp-runtime.json")
        ] == before
    else:
        assert (
            load_mcp(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[1]["token"]
        )


def test_mode_switch_final_selection_uses_shared_lifecycle_lock(runtime):
    from app.research_web.lifecycle_lock import LifecycleLock
    from research_workbench_entrypoint.bootstrap import switch_runtime

    controller, _runner, _ = runtime
    with LifecycleLock(
        controller.home / "run/lifecycle.lock", lambda pid: True, trusted_root=controller.home
    ):
        report = switch_runtime(controller.store, "native", controller, Native())
        assert report["issues"] == ["lifecycle_busy"]
    assert controller.store.read().mode == "docker"


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "timeout",
        "replacement",
        "tmpfs_missing",
        "tmpfs_type",
        "uid",
        "gid",
        "mode",
        "unknown",
        "duplicate_option",
        "readonly",
        "extra",
        "shadow",
        "bind_source",
        "duplicate_mount",
        "missing_rw",
    ],
)
@pytest.mark.parametrize("explicit_tmpfs", [False, True])
def test_partial_controls_use_owned_no_port_guest_preparation(
    runtime, monkeypatch, failure, explicit_tmpfs
):
    from app.research_web.datahub.security import load_control
    from docker.supervisor import prepare_controls
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import ControlError
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore

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
            labels = dict(
                argv[i + 1].split("=", 1) for i, arg in enumerate(argv[:-1]) if arg == "--label"
            )
            assert not any(arg in ("-p", "--publish", "--publish-all") for arg in argv)
            assert str(controller.credential_dir) not in " ".join(argv)
            guest.update(
                id="d" * 64,
                image="sha256:" + "b" * 64,
                installation=controller.installation_id,
                launch=labels["io.research-workbench.launch"],
                runtime="control-preparer",
                running=False,
                state="created",
                exit_code=0,
                ports={},
                entrypoint=["/opt/rwb/venv/bin/python"],
                command=[
                    "/opt/rwb/docker/supervisor.py",
                    "--prepare-controls-only",
                    "--previous-origin",
                    origin,
                ],
                mounts=[
                    {
                        "Type": "bind",
                        "Source": str(controller.data_dir),
                        "Destination": "/data/research-web",
                        "RW": True,
                    }
                ]
                + (
                    [
                        {"Type": "tmpfs", "Source": "", "Destination": name, "RW": True}
                        for name in ("/state", "/run/rwb-secrets", "/tmp", "/home/rwb")
                    ]
                    if explicit_tmpfs
                    else []
                ),
                tmpfs={
                    name: "rw,nosuid,nodev,uid=10001,gid=10001,mode=700"
                    for name in ("/state", "/run/rwb-secrets", "/tmp", "/home/rwb")
                },
            )
            if failure == "tmpfs_missing":
                guest["tmpfs"].pop("/state")
            elif failure == "tmpfs_type":
                guest["tmpfs"] = list(guest["tmpfs"])
            elif failure in {"uid", "gid", "mode"}:
                old, new = {
                    "uid": ("uid=10001", "uid=0"),
                    "gid": ("gid=10001", "gid=0"),
                    "mode": ("mode=700", "mode=755"),
                }[failure]
                guest["tmpfs"]["/state"] = guest["tmpfs"]["/state"].replace(old, new)
            elif failure in {"unknown", "duplicate_option"}:
                guest["tmpfs"]["/state"] += ",silent" if failure == "unknown" else ",uid=10001"
            elif failure == "extra":
                guest["tmpfs"]["/extra"] = guest["tmpfs"]["/state"]
            elif failure == "readonly":
                guest["mounts"][0]["RW"] = False
            elif failure == "missing_rw":
                guest["mounts"][0].pop("RW")
            elif failure == "bind_source":
                guest["mounts"][0]["Source"] = "/foreign"
            elif failure == "duplicate_mount":
                guest["mounts"].append(dict(guest["mounts"][0]))
            elif failure == "shadow":
                guest["mounts"].append(
                    {"Type": "volume", "Source": "", "Destination": "/state", "RW": True}
                )
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
    if failure not in {None, "timeout"}:
        assert guest and not any(argv[1] == "rm" for argv in calls)
        assert "docker_prepare_cleanup_unverified" in report["issues"]
    else:
        assert not guest
    if failure == "timeout":
        assert report["issues"] == ["runtime_command_timeout"]


def test_docker_bind_race_retries_owned_attempt_with_three_attempt_budget(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, runner, _ = runtime
    controller.data_dir.mkdir(mode=0o700)
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
            return subprocess.CompletedProcess(
                argv, 1, "", "Ports are not available: bind: address already in use"
            )
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


@pytest.mark.parametrize("persisted", [False, True])
def test_docker_absent_stop_is_noop_and_keeps_external_web_listener(
    runtime, monkeypatch, persisted
):
    from research_workbench_entrypoint import docker_runtime as control

    controller, runner, before = runtime
    if persisted:
        controller.endpoint_store.publish("docker", controller.ports[0], expected=None)
        controller = control.DockerRuntime(controller.project_root, controller.home, runner=runner)
    endpoint = controller.endpoint_store.read("docker")
    inspected_ports = []
    real_busy = control.port_busy

    def observe(port):
        inspected_ports.append(port)
        return real_busy(port)

    monkeypatch.setattr(control, "port_busy", observe)
    with socket.socket() as external:
        external.bind(("127.0.0.1", controller.ports[0]))
        external.listen()
        report = controller.stop(wait_timeout=0)
        assert report["ok"] and report["ownership"] == "absent", report
        assert not any(service["running"] for service in report["services"].values())
        assert external.getsockname()[1] == controller.ports[0]
        assert inspected_ports == []
        assert runner.container is None
        assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls)
        assert controller.store.read() == before
        assert controller.endpoint_store.read("docker") == endpoint


def test_docker_stop_refuses_wrong_mapping_before_stopping_owned_container(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    runner.container["ports"]["8088/tcp"][0]["HostIp"] = "0.0.0.0"
    report = controller.stop(wait_timeout=0)
    assert report["issues"] == ["docker_ports_mismatch"], report
    assert runner.container["running"]
    assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls)


@pytest.mark.parametrize("legacy", [False, True])
def test_docker_stop_rechecks_mapping_before_mutation(runtime, legacy):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

    controller, runner, _ = runtime
    owned(controller, runner)
    if legacy:
        controller = DockerRuntime(controller.project_root, controller.home, runner=runner)
    inspected = []

    def changed_mapping(argv, **kwargs):
        if argv[1:3] == ["container", "inspect"]:
            inspected.append(True)
            if len(inspected) == 2:
                binding = runner.container["ports"]["8088/tcp"][0]
                binding["HostPort"] = str(int(binding["HostPort"]) + 1)
        return runner(argv, **kwargs)

    controller.runner = changed_mapping
    report = controller.stop(wait_timeout=0)
    assert report["issues"] == ["docker_ports_mismatch"], report
    assert runner.container["running"]
    assert not any(argv[1] in ("stop", "rm") for argv, _ in runner.calls)
    assert not controller.endpoint_store.path.exists()


def test_docker_stop_legacy_mapping_waits_for_actual_dynamic_host_port(runtime):
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

    controller, runner, before = runtime
    owned(controller, runner)
    with socket.socket() as reservation:
        reservation.bind(("127.0.0.1", 0))
        actual = reservation.getsockname()[1]
        assert actual != 8088
        runner.container["ports"] = {"8088/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(actual)}]}
        legacy = DockerRuntime(controller.project_root, controller.home, runner=runner)
        assert legacy.endpoint_snapshot is None and legacy.ports[0] == 8088
        report = legacy.stop(wait_timeout=0)
        assert report["issues"] == ["runtime_ports_not_released"], report
        assert legacy.ports[0] == actual
        assert not runner.container["running"]
        assert reservation.getsockname()[1] == actual
        assert not legacy.endpoint_store.path.exists()
        assert legacy.store.read() == before
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)


def test_docker_stop_does_not_wait_for_unpublished_runtime_port(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", controller.ports[1]))
        foreign.listen()
        report = controller.stop(wait_timeout=0)
        assert report["ok"], report
        assert not runner.container["running"]
        assert foreign.getsockname()[1] == controller.ports[1]
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)


def test_docker_stop_keeps_foreign_listener_and_refuses_unreleased_host_port(runtime):
    controller, runner, _ = runtime
    owned(controller, runner)
    with socket.socket() as foreign:
        foreign.bind(("127.0.0.1", controller.ports[0]))
        foreign.listen()
        report = controller.stop(wait_timeout=0)
        assert report["issues"] == ["runtime_ports_not_released"], report
        assert not runner.container["running"]
        assert foreign.getsockname()[1] == controller.ports[0]
        assert not any(argv[1] == "rm" for argv, _ in runner.calls)


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
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.runtime_endpoints import EndpointStore
    from scripts import setup_web

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

    installer = setup_web.DockerRuntime(
        controller.project_root, controller.home, runner=launch, ports=controller.ports
    )

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
    from app.research_web import service_manager as manager_module
    from research_workbench_entrypoint.web_contract import ListenerFact

    monkeypatch.setattr(
        manager_module, "listener_pids", lambda port: ListenerFact("closed", (), None)
    )
    from app.research_web.datahub.security import load_control
    from app.research_web.mcp_runtime.control import load_control as load_mcp
    from app.research_web.service_manager import WebServiceManager
    from research_workbench_entrypoint.bootstrap import NativeRuntime

    controller, runner, _ = runtime
    native_ports = controller.ports
    controller.data_dir.mkdir(mode=0o700)
    originals = [
        load_control(controller.data_dir, "http://127.0.0.1:8088"),
        load_mcp(controller.data_dir, "http://127.0.0.1:8088"),
    ]
    monkeypatch.setattr(NativeRuntime, "status", lambda self: Native().status())

    def start_native():
        controller.store.write("native")
        manager = WebServiceManager(
            project_root=controller.project_root,
            data_root=controller.data_dir,
            web_port=native_ports[0],
            runtime_port=native_ports[1],
        )
        monkeypatch.setattr(
            manager,
            "_other_runtime_quiescent",
            lambda: not (runner.container and runner.container["running"]),
        )
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
    assert (
        load_control(controller.data_dir, "http://127.0.0.1:8088")["token"] == originals[0]["token"]
    )
    assert controller.stop()["ok"]
    last = start_native()
    assert last.endpoint_store.read("docker").web_port == controller.ports[0]


def test_new_docker_attempt_never_adopts_wrong_actual_mapping_as_legacy(runtime, monkeypatch):
    from research_workbench_entrypoint.bootstrap import NativeRuntime
    from research_workbench_entrypoint.docker_runtime import DockerRuntime

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
        runtime.run_bounded(
            [sys.executable, "-c", "import time;time.sleep(30)"],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout=0.05,
        )
    assert caught.value.code == "runtime_command_timeout"
    assert "runtime_process_tree_cleanup_failed" in " ".join(caught.value.__notes__)
    assert "runtime_process_tree_cleanup_failed" in caplog.text
