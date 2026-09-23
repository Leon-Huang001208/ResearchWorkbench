import json
import os
from pathlib import Path

import pytest

from app.research_web import runtime_auth as runtime_auth_module
from app.research_web import service_manager as service_manager_module
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    _is_unsafe_private_directory,
    format_doctor_status,
    format_status,
)


@pytest.fixture
def manager(tmp_path: Path) -> WebServiceManager:
    source = tmp_path / "dsh"
    source.mkdir()
    python = tmp_path / "python"
    node = tmp_path / "node"
    python.touch()
    node.touch()
    return WebServiceManager(
        project_root=tmp_path,
        data_root=tmp_path / "data" / "research-web",
        runtime_source=source,
        python=str(python),
        node=str(node),
    )


def test_process_contract_uses_brand_neutral_runtime_and_fixed_ports(manager):
    runtime, web = manager._processes()
    assert runtime.port == 3081
    assert web.port == 8088
    assert "app.research_web.launch_runtime" in runtime.command
    assert "app.research_web.main:app" in web.command
    assert runtime.signature == (
        str(manager.runtime_source / "apps/cli/lib/bin.js"),
        str(manager.data_root / "runtime/overlay.yml"),
        "3081",
    )
    assert not any(part.startswith("af" + "_") for item in (runtime, web) for part in item.command)


def test_process_contract_supports_isolated_staging_ports(manager):
    staged = WebServiceManager(
        project_root=manager.project_root,
        data_root=manager.data_root,
        runtime_source=manager.runtime_source,
        python=manager.python,
        node=manager.node,
        web_port=18088,
        runtime_port=13081,
    )

    runtime, web = staged._processes()

    assert runtime.port == 13081
    assert web.port == 18088
    assert runtime.command[runtime.command.index("--port") + 1] == "13081"
    assert runtime.command[runtime.command.index("--datahub-url") + 1] == ("http://127.0.0.1:18088")
    assert web.command[-1] == "18088"
    assert staged.web_url == "http://127.0.0.1:18088/#/fingpt"


def test_spawn_exports_the_exact_private_web_origin_for_mcp_callbacks(manager, monkeypatch):
    captured = {}
    monkeypatch.setenv("ALL_PROXY", "socks5://127.0.0.1:1080")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:18080")

    class Process:
        pid = 4321

    def popen(_command, **options):
        captured.update(options)
        return Process()

    monkeypatch.setattr(service_manager_module.subprocess, "Popen", popen)
    monkeypatch.setattr(manager, "_write_state", lambda *_args: None)

    manager._prepare_private_directories()
    manager._spawn(manager._processes()[1])

    assert captured["env"]["RESEARCH_WEB_INTERNAL_URL"] == "http://127.0.0.1:8088"
    assert "ALL_PROXY" not in captured["env"]
    assert captured["env"]["HTTPS_PROXY"] == "http://127.0.0.1:18080"


def test_default_runtime_source_is_project_private(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEARCH_DSH_SOURCE", raising=False)
    data_root = tmp_path / ".research-workbench" / "research-web"
    resolved = WebServiceManager(project_root=tmp_path, data_root=data_root)
    assert (
        resolved.runtime_source
        == (
            tmp_path
            / ".research-workbench"
            / "runtime"
            / "dsh"
            / service_manager_module.PINNED_COMMIT
        ).resolve()
    )


def test_configured_node_binary_precedes_path_lookup(tmp_path, monkeypatch):
    configured = tmp_path / "node-24"
    configured.touch()
    monkeypatch.setenv("RESEARCH_NODE_BINARY", str(configured))
    monkeypatch.setattr(service_manager_module.shutil, "which", lambda _name: "/node-25")

    resolved = WebServiceManager(project_root=tmp_path, data_root=tmp_path / "data")

    assert resolved.node == str(configured)


def test_windows_private_directory_does_not_apply_posix_group_mode_bits(tmp_path):
    private_directory = tmp_path / "private"
    private_directory.mkdir(mode=0o755)

    assert not _is_unsafe_private_directory(
        private_directory,
        private_directory.lstat(),
        platform_name="nt",
    )


def test_posix_private_directory_rejects_group_mode_bits(tmp_path):
    private_directory = tmp_path / "private"
    private_directory.mkdir(mode=0o755)

    assert _is_unsafe_private_directory(
        private_directory,
        private_directory.lstat(),
        platform_name="posix",
    )


def test_private_state_is_atomic_and_fingerprint_checked(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(manager, "_command_line", lambda pid: " ".join(process.signature))
    assert manager._owned_state(process)["pid"] == 12345
    state_path = manager._state_path(process.role)
    state = json.loads(state_path.read_text())
    state["command"].append("--tampered")
    state_path.write_text(json.dumps(state))
    with pytest.raises(ServiceManagerError, match="无法安全确认"):
        manager._owned_state(process)


def test_stale_pid_is_removed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)
    assert manager._owned_state(process) is None
    assert not manager._state_path(process.role).exists()


def test_dead_state_from_previous_checkout_is_removed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    state_path = manager._state_path(process.role)
    state = json.loads(state_path.read_text())
    state["project_root"] = "/previous/checkout"
    state_path.write_text(json.dumps(state))
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: False)

    assert manager._owned_state(process) is None
    assert not state_path.exists()


def test_pid_reuse_or_foreign_command_fails_closed(manager, monkeypatch):
    manager._prepare_private_directories()
    process = manager._processes()[0]
    manager._write_state(process, 12345)
    monkeypatch.setattr(manager, "_pid_exists", lambda pid: True)
    monkeypatch.setattr(manager, "_command_line", lambda pid: "python unrelated.py")
    with pytest.raises(ServiceManagerError, match="拒绝操作"):
        manager._owned_state(process)


def test_windows_command_line_probe_uses_cim_without_a_shell(manager, monkeypatch):
    captured = {}

    class Result:
        returncode = 0
        stdout = "python.exe -m app.research_web.main:app"

    def run(command, **options):
        captured.update(command=command, options=options)
        return Result()

    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    command_line = manager._command_line(4321, platform_name="nt")

    assert command_line == Result.stdout
    assert captured["command"][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert "4321" in captured["command"][4]
    assert captured["options"]["shell"] is False


def test_windows_process_tree_termination_uses_taskkill(manager, monkeypatch):
    captured = []

    class Result:
        returncode = 0

    def run(command, **options):
        captured.append((command, options))
        return Result()

    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    manager._terminate_pid(4321, force=False, platform_name="nt")
    manager._terminate_pid(4321, force=True, platform_name="nt")

    assert captured[0][0] == ["taskkill.exe", "/PID", "4321", "/T"]
    assert captured[1][0] == ["taskkill.exe", "/PID", "4321", "/T", "/F"]
    assert all(options["shell"] is False for _command, options in captured)


@pytest.mark.parametrize(("returncode", "expected"), [(0, True), (1, False)])
def test_windows_pid_probe_uses_powershell_without_os_kill(
    manager, monkeypatch, returncode, expected
):
    captured = {}

    class Result:
        def __init__(self, code):
            self.returncode = code

    def run(command, **options):
        captured.update(command=command, options=options)
        return Result(returncode)

    monkeypatch.setattr(
        service_manager_module.os,
        "kill",
        lambda *_args: pytest.fail("Windows PID probes must not call os.kill"),
    )
    monkeypatch.setattr(service_manager_module.subprocess, "run", run)

    assert manager._pid_exists(4321, platform_name="nt") is expected
    assert captured["command"][:4] == [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-Command",
    ]
    assert "4321" in captured["command"][4]
    assert captured["options"]["shell"] is False


def test_posix_zombie_is_not_treated_as_a_live_owned_process(manager, monkeypatch):
    class Result:
        returncode = 0
        stdout = "Z+"

    monkeypatch.setattr(service_manager_module.os, "kill", lambda _pid, _signal: None)
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "run",
        lambda *_args, **_kwargs: Result(),
    )

    assert manager._pid_exists(4321, platform_name="posix") is False


def test_start_is_idempotent_and_waits_for_both_services(manager, monkeypatch):
    manager._prepare_private_directories()
    ownership = {"runtime": None, "web": None}
    spawned = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_owned_state", lambda process: ownership[process.role])
    monkeypatch.setattr(manager, "_port_open", lambda port: False)

    def spawn(process):
        spawned.append(process.role)
        ownership[process.role] = {"pid": 100 + len(spawned)}
        return ownership[process.role]["pid"]

    monkeypatch.setattr(manager, "_spawn", spawn)
    monkeypatch.setattr(manager, "_wait", lambda check, timeout: True)
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": "http://127.0.0.1:8088/#/fingpt",
            "services": {
                "runtime": {"running": True, "healthy": True, "pid": 101, "port": 3081},
                "web": {"running": True, "healthy": True, "pid": 102, "port": 8088},
            },
        },
    )
    manager.start(open_browser=False)
    manager.start(open_browser=False)
    assert spawned == ["runtime", "web"]


def test_start_fails_fast_when_web_installation_is_not_ready(manager, monkeypatch):
    lock = manager.project_root / "requirements" / "web.lock"
    lock.parent.mkdir()
    lock.write_text("locked-runtime", encoding="utf-8")
    lock_sha = service_manager_module.hashlib.sha256(lock.read_bytes()).hexdigest()
    monkeypatch.setattr(
        manager,
        "_read_install_manifest",
        lambda: {
            "schema_version": 1,
            "status": "installed",
            "web_lock_sha256": lock_sha,
            "cjpy_version": service_manager_module.CJPY_VERSION,
            "cjpy_sha256": service_manager_module.CJPY_SHA256,
            "dsh_commit": service_manager_module.PINNED_COMMIT,
            "dsh_closure_sha256": "closure-ok",
        },
    )
    monkeypatch.setattr(
        manager,
        "_installed_package_versions",
        lambda: {"cjpy": None, "requests": "2.33.0", "urllib3": "2.5.0"},
    )
    monkeypatch.setattr(
        manager,
        "_dsh_build_status",
        lambda: {
            "commit": service_manager_module.PINNED_COMMIT,
            "closure_sha256": "closure-ok",
            "closure_files": 11084,
            "ready": True,
        },
    )
    monkeypatch.setattr(manager, "_executable_version", lambda _path: "safe-version")
    monkeypatch.setattr(
        manager,
        "_runtime_healthy",
        lambda: pytest.fail("installation preflight must not contact Runtime"),
    )
    monkeypatch.setattr(
        manager,
        "_web_healthy",
        lambda: pytest.fail("installation preflight must not contact Web"),
    )
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail(
            "start must not spawn services before installation preflight passes"
        ),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    message = str(captured.value)
    assert "environment_not_owned" in message
    assert "cjpy_not_ready" in message
    assert "setup-web" in message


def test_start_rolls_back_only_new_processes(manager, monkeypatch):
    manager._prepare_private_directories()
    stopped = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_ensure_startable", lambda process: True)
    monkeypatch.setattr(manager, "_spawn", lambda process: 123)
    checks = iter([True, False])
    monkeypatch.setattr(manager, "_wait", lambda check, timeout: next(checks))
    monkeypatch.setattr(manager, "_stop_one", lambda process: stopped.append(process.role))
    with pytest.raises(ServiceManagerError, match="Web 8088"):
        manager.start(open_browser=False)
    assert stopped == ["web", "runtime"]


def test_restart_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_owned_state", lambda process: {"pid": 123})
    monkeypatch.setattr(manager, "_active_research", lambda: ["session-1"])
    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart(force=False, open_browser=False)


def test_restart_runtime_keeps_web_online_and_waits_for_owned_runtime(manager, monkeypatch):
    manager._prepare_private_directories()
    runtime, web = manager._processes()
    ownership = {"runtime": {"pid": 101}, "web": {"pid": 202}}
    stopped: list[str] = []
    spawned: list[str] = []

    monkeypatch.setattr(manager, "_owned_state", lambda process: ownership[process.role])
    monkeypatch.setattr(manager, "_active_research", list)

    def stop_one(process):
        stopped.append(process.role)
        ownership[process.role] = None
        return True

    def spawn(process):
        spawned.append(process.role)
        ownership[process.role] = {"pid": 303}
        return 303

    monkeypatch.setattr(manager, "_stop_one", stop_one)
    monkeypatch.setattr(manager, "_spawn", spawn)
    monkeypatch.setattr(manager, "_port_open", lambda port: False)
    monkeypatch.setattr(manager, "_wait", lambda check, timeout: check())
    monkeypatch.setattr(manager, "_runtime_healthy", lambda: ownership["runtime"] is not None)

    result = manager.restart_runtime(force=False)

    assert stopped == [runtime.role]
    assert spawned == [runtime.role]
    assert ownership[web.role] == {"pid": 202}
    assert result == {"running": True, "healthy": True, "pid": 303, "port": 3081}


def test_restart_runtime_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_owned_state", lambda process: {"pid": 123})
    monkeypatch.setattr(manager, "_active_research", lambda: ["session-1"])

    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart_runtime(force=False)


def test_stop_never_targets_unowned_process(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_owned_state", lambda process: None)
    monkeypatch.setattr(manager, "status", lambda: {"url": "x", "services": {}})
    kill_calls = []
    monkeypatch.setattr("os.killpg", lambda *args: kill_calls.append(args))
    manager.stop()
    assert kill_calls == []


def test_status_formatter_is_concise():
    value = {
        "url": "http://127.0.0.1:8088/#/fingpt",
        "services": {
            "runtime": {"running": True, "healthy": True, "pid": 10, "port": 3081},
            "web": {"running": False, "healthy": False, "pid": None, "port": 8088},
        },
    }
    rendered = format_status(value)
    assert "runtime: healthy" in rendered
    assert "web: stopped" in rendered
    assert "8088/#/fingpt" in rendered


def test_doctor_output_is_safe_and_reports_the_installation_contract(manager, monkeypatch):
    environment = manager.project_root / ".venv"
    environment.mkdir()
    (environment / ".rwb-web-environment.json").write_text(
        json.dumps({"schema_version": 1, "owner": "research-workbench-web-installer"}),
        encoding="utf-8",
    )
    lock = manager.project_root / "requirements" / "web.lock"
    lock.parent.mkdir()
    lock.write_text("locked-runtime", encoding="utf-8")
    lock_sha = service_manager_module.hashlib.sha256(lock.read_bytes()).hexdigest()
    install_root = manager.data_root.parent / "install"
    install_root.mkdir(parents=True)
    (install_root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "status": "installed",
                "web_lock_sha256": lock_sha,
                "cjpy_version": "0.5.2",
                "cjpy_sha256": "d8c6820a718ae5f79061b54815473dd3ecd3be73cd808634fbac5bc1c385bd94",
                "dsh_commit": service_manager_module.PINNED_COMMIT,
                "dsh_closure_sha256": "closure-ok",
                "CJ_KEY": "must-never-escape",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(manager, "_executable_version", lambda _path: "safe-version")
    monkeypatch.setattr(
        manager,
        "_installed_package_versions",
        lambda: {"cjpy": "0.5.2", "requests": "2.33.0", "urllib3": "2.5.0"},
    )
    monkeypatch.setattr(
        manager,
        "_dsh_build_status",
        lambda: {
            "commit": service_manager_module.PINNED_COMMIT,
            "closure_sha256": "closure-ok",
            "closure_files": 11084,
            "ready": True,
        },
    )
    monkeypatch.setattr(
        manager,
        "status",
        lambda: {
            "url": manager.web_url,
            "services": {
                "runtime": {"running": True, "healthy": True, "pid": 111, "port": 3081},
                "web": {"running": True, "healthy": True, "pid": 222, "port": 8088},
            },
        },
    )
    runtime_lock = manager.data_root / "runtime" / "build-lock.json"
    runtime_lock.parent.mkdir(parents=True)
    runtime_lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    runtime_lock.chmod(0o600)

    report = manager.doctor()
    serialized = json.dumps(report, ensure_ascii=False)

    assert report["ok"] is True
    assert report["python"]["lock_matches_manifest"] is True
    assert report["cjpy"]["version"] == "0.5.2"
    assert report["services"]["web"] == {"port": 8088, "running": True, "healthy": True}
    assert str(manager.project_root) not in serialized
    assert "must-never-escape" not in serialized
    rendered = format_doctor_status(report)
    assert "CJPY: 0.5.2" in rendered
    assert "DSH: ready" in rendered

    runtime_lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "stale-closure",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    stale = manager.doctor()
    assert stale["ok"] is False
    assert "dsh_runtime_lock_mismatch" in stale["issues"]


def test_dsh_build_status_uses_the_private_install_attestation(manager, monkeypatch):
    monkeypatch.setattr(
        service_manager_module.subprocess,
        "check_output",
        lambda *_args, **_kwargs: service_manager_module.PINNED_COMMIT,
    )
    monkeypatch.setattr(
        service_manager_module,
        "calculate_build_closure",
        lambda _source: ("local-closure", 11084),
    )
    monkeypatch.setattr(
        manager,
        "_read_install_manifest",
        lambda: {
            "schema_version": 1,
            "dsh_commit": service_manager_module.PINNED_COMMIT,
            "dsh_closure_sha256": "local-closure",
            "dsh_closure_files": 11084,
        },
    )
    (manager.runtime_source / "apps" / "cli" / "lib").mkdir(parents=True)
    (manager.runtime_source / "apps" / "cli" / "lib" / "bin.js").touch()

    assert manager._dsh_build_status()["ready"] is True

    monkeypatch.setattr(
        service_manager_module,
        "calculate_build_closure",
        lambda _source: ("tampered-closure", 11084),
    )
    assert manager._dsh_build_status()["ready"] is False


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_linked_runtime_directory(manager):
    manager._prepare_private_directories()
    external = manager.project_root / "external-runtime"
    external.mkdir()
    (external / "build-lock.json").write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    (manager.data_root / "runtime").symlink_to(external, target_is_directory=True)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_linked_data_parent(manager):
    external_parent = manager.project_root / "external-data"
    runtime = external_parent / manager.data_root.name / "runtime"
    runtime.mkdir(parents=True)
    lock = runtime / "build-lock.json"
    lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    lock.chmod(0o600)
    manager.data_root.parent.symlink_to(external_parent, target_is_directory=True)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


@pytest.mark.skipif(os.name == "nt", reason="symlink creation is not guaranteed on Windows CI")
def test_runtime_build_lock_reader_rejects_a_preexisting_data_parent_alias(tmp_path):
    external_parent = tmp_path / "external-data"
    runtime = external_parent / "research-web" / "runtime"
    runtime.mkdir(parents=True)
    lock = runtime / "build-lock.json"
    lock.write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    lock.chmod(0o600)
    alias = tmp_path / "data-alias"
    alias.symlink_to(external_parent, target_is_directory=True)
    source = tmp_path / "dsh"
    source.mkdir()
    python = tmp_path / "python"
    python.touch()
    node = tmp_path / "node"
    node.touch()
    manager = WebServiceManager(
        project_root=tmp_path,
        data_root=alias / "research-web",
        runtime_source=source,
        python=str(python),
        node=str(node),
    )

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


def test_runtime_build_lock_reader_requires_an_integer_file_count(manager):
    manager._prepare_private_directories()
    runtime = manager.data_root / "runtime"
    runtime.mkdir()
    (runtime / "build-lock.json").write_text(
        json.dumps(
            {
                "source_commit": service_manager_module.PINNED_COMMIT,
                "closure_sha256": "closure-ok",
                "closure_files": 11084.0,
                "mode": "build",
            }
        ),
        encoding="utf-8",
    )
    (runtime / "build-lock.json").chmod(0o600)

    assert (
        manager._runtime_build_lock_matches(
            {"closure_sha256": "closure-ok", "closure_files": 11084}
        )
        is False
    )


def test_package_version_probe_preserves_present_packages_when_one_is_missing(manager, monkeypatch):
    class Result:
        returncode = 0
        stdout = json.dumps({"cjpy": None, "requests": "2.34.2", "urllib3": "2.8.0"})

    monkeypatch.setattr(
        service_manager_module.subprocess, "run", lambda *_args, **_kwargs: Result()
    )

    assert manager._installed_package_versions() == {
        "cjpy": None,
        "requests": "2.34.2",
        "urllib3": "2.8.0",
    }


def test_runtime_health_exchanges_cookie_and_writes_private_auth(manager, monkeypatch):
    manager._prepare_private_directories()
    (manager.runtime_source / "package.json").write_text(
        json.dumps({"version": "0.1.3-alpha.2"}), encoding="utf-8"
    )
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda token: "dsh-auth-test=value")
    requests = []

    def request(port, method, path, payload=None, extra_headers=None):
        requests.append((port, method, path, payload, extra_headers))
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {"ok": True, "value": {"items": []}},
        }

    monkeypatch.setattr(manager, "_json_request", request)

    assert manager._runtime_healthy() is True
    auth_path = manager._runtime_auth_path()
    assert auth_path.stat().st_mode & 0o777 == 0o600
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    assert auth["cookie"] == "dsh-auth-test=value"
    assert auth["authority"] == "127.0.0.1:3081"
    assert requests[0][0:3] == (3081, "POST", "/api/session/list")
    assert requests[0][3]["payload"] == {"args": {"_request": {}}}
    assert requests[0][4] == {"Cookie": "dsh-auth-test=value"}


def test_runtime_sessions_returns_authoritative_session_list(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )
    requests = []

    def request(port, method, path, payload=None, extra_headers=None):
        requests.append((port, method, path, payload, extra_headers))
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {
                "ok": True,
                "value": {
                    "items": [
                        {"sessionId": "idle-parent", "running": False},
                        {"sessionId": "running-child", "running": True},
                    ]
                },
            },
        }

    monkeypatch.setattr(manager, "_json_request", request)

    assert manager._runtime_sessions() == [
        {"sessionId": "idle-parent", "running": False},
        {"sessionId": "running-child", "running": True},
    ]
    assert requests[0][0:3] == (3081, "POST", "/api/session/list")
    assert requests[0][3]["type"] == "client-request"
    assert requests[0][3]["method"] == "session/list"
    assert requests[0][3]["payload"] == {"args": {"_request": {}}}
    assert requests[0][4] == {"Cookie": "dsh-auth-test=value"}


@pytest.mark.parametrize(
    "response",
    [
        {
            "type": "client-response",
            "rpcId": None,
            "result": {"ok": True, "value": {"items": []}},
        },
        {
            "type": "server-response",
            "rpcId": "mismatched",
            "result": {"ok": True, "value": {"items": []}},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": False, "value": {"items": []}},
        },
        {"type": "server-response", "rpcId": None, "result": []},
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": []},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": {}},
        },
        {
            "type": "server-response",
            "rpcId": None,
            "result": {"ok": True, "value": {"items": {}}},
        },
    ],
)
def test_runtime_sessions_rejects_invalid_protocol_response(manager, monkeypatch, response):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )

    def request(_port, _method, _path, payload=None, _extra_headers=None):
        value = dict(response)
        if value.get("rpcId") is None:
            value["rpcId"] = payload["rpcId"]
        return value

    monkeypatch.setattr(manager, "_json_request", request)

    with pytest.raises(ServiceManagerError, match="DSH 会话状态响应无效"):
        manager._runtime_sessions()
    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


@pytest.mark.parametrize(
    "items",
    [
        [None],
        [{}],
        [{"sessionId": "", "running": False}],
        [{"sessionId": "x", "running": "yes"}],
    ],
)
def test_runtime_sessions_rejects_invalid_session_items(manager, monkeypatch, items):
    monkeypatch.setattr(
        manager,
        "_read_runtime_auth",
        lambda: {"cookie": "dsh-auth-test=value"},
    )

    def request(_port, _method, _path, payload=None, _extra_headers=None):
        return {
            "type": "server-response",
            "rpcId": payload["rpcId"],
            "result": {"ok": True, "value": {"items": items}},
        }

    monkeypatch.setattr(manager, "_json_request", request)

    with pytest.raises(ServiceManagerError, match="DSH 会话状态响应无效"):
        manager._runtime_sessions()
    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_sessions_fails_closed_when_auth_is_unavailable(manager, monkeypatch):
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: None)
    monkeypatch.setattr(
        manager,
        "_json_request",
        lambda *_args, **_kwargs: pytest.fail("request must not run without auth"),
    )

    with pytest.raises(ServiceManagerError, match="DSH 认证不可用"):
        manager._runtime_sessions()


@pytest.mark.parametrize(
    "package_content",
    [None, b"{", b"{}", b"[]", b"\xff"],
    ids=["missing", "malformed-json", "missing-version", "wrong-type", "invalid-utf8"],
)
def test_runtime_auth_regeneration_fails_closed_for_invalid_package_metadata(
    manager, monkeypatch, package_content
):
    manager._prepare_private_directories()
    if package_content is not None:
        (manager.runtime_source / "package.json").write_bytes(package_content)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_auth_regeneration_fails_closed_when_tempfile_creation_fails(manager, monkeypatch):
    manager._prepare_private_directories()
    (manager.runtime_source / "package.json").write_text(
        json.dumps({"version": "0.1.3-alpha.2"}), encoding="utf-8"
    )
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    def fail_mkstemp(*_args, **_kwargs):
        raise OSError("tempfile unavailable")

    monkeypatch.setattr(service_manager_module.tempfile, "mkstemp", fail_mkstemp)

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_auth_regeneration_preserves_service_manager_fail_closed_contract(
    manager, monkeypatch
):
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(manager, "_runtime_launch_token", lambda: "t" * 43)
    monkeypatch.setattr(manager, "_exchange_runtime_cookie", lambda _token: "dsh-auth-test=value")

    def fail_write(_cookie):
        raise ServiceManagerError("无法写入 DSH 认证控制文件")

    monkeypatch.setattr(manager, "_write_runtime_auth", fail_write)

    assert manager._runtime_healthy() is False
    with pytest.raises(ServiceManagerError) as captured:
        manager._active_research()
    assert str(captured.value) == "无法核对活动研究；未执行重启，可显式使用 --force"


def test_runtime_healthy_reuses_runtime_sessions(manager, monkeypatch):
    calls = []
    monkeypatch.setattr(manager, "_runtime_sessions", lambda: calls.append(True) or [])

    assert manager._runtime_healthy() is True
    assert calls == [True]

    def fail():
        raise ServiceManagerError("DSH 会话状态响应无效")

    monkeypatch.setattr(manager, "_runtime_sessions", fail)
    assert manager._runtime_healthy() is False


def test_active_research_uses_all_authoritative_runtime_sessions(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_runtime_sessions",
        lambda: [
            {"sessionId": "idle-parent", "running": False},
            {"sessionId": "running-child", "running": True},
            {"sessionId": "unknown-running", "running": True},
        ],
    )

    assert manager._active_research() == ["running-child", "unknown-running"]


def test_runtime_auth_fails_closed_for_foreign_authority(manager):
    manager._prepare_private_directories()
    auth_path = manager._runtime_auth_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(
        json.dumps(
            {
                "authority": "127.0.0.1:9999",
                "cookie": "dsh-auth-test=value",
                "cwd": str((manager.data_root / "runtime/work").resolve()),
                "source_commit": "c919b2a460753859665db3f60143d525fb9140cf",
                "version": "0.1.3-alpha.2",
            }
        ),
        encoding="utf-8",
    )
    auth_path.chmod(0o600)

    assert manager._read_runtime_auth() is None


def test_windows_runtime_auth_reader_does_not_apply_posix_group_mode_bits(manager, monkeypatch):
    manager._prepare_private_directories()
    auth_path = manager._runtime_auth_path()
    auth_path.parent.mkdir(parents=True, exist_ok=True)
    auth_path.write_text(
        json.dumps(
            {
                "authority": "127.0.0.1:3081",
                "cookie": "dsh-auth-test=value",
                "cwd": str((manager.data_root / "runtime/work").resolve()),
                "source_commit": "c919b2a460753859665db3f60143d525fb9140cf",
                "version": "0.1.3-alpha.2",
            }
        ),
        encoding="utf-8",
    )
    auth_path.chmod(0o644)
    with monkeypatch.context() as patcher:
        patcher.setattr(
            service_manager_module,
            "read_runtime_auth_record",
            lambda path: runtime_auth_module.read_runtime_auth_record(path, platform_name="nt"),
        )
        auth = manager._read_runtime_auth()

    assert auth["cookie"] == "dsh-auth-test=value"
