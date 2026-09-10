import json
from pathlib import Path

import pytest

from app.research_web import runtime_auth as runtime_auth_module
from app.research_web import service_manager as service_manager_module
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    _is_unsafe_private_directory,
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


def test_default_runtime_source_is_project_private(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEARCH_DSH_SOURCE", raising=False)
    data_root = tmp_path / ".research-workbench" / "research-web"
    resolved = WebServiceManager(project_root=tmp_path, data_root=data_root)
    assert resolved.runtime_source == (tmp_path / ".research-workbench" / "dsh-source").resolve()


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


def test_start_is_idempotent_and_waits_for_both_services(manager, monkeypatch):
    manager._prepare_private_directories()
    ownership = {"runtime": None, "web": None}
    spawned = []
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


def test_start_rolls_back_only_new_processes(manager, monkeypatch):
    manager._prepare_private_directories()
    stopped = []
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
