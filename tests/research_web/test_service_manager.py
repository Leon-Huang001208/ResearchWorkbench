import json
from pathlib import Path

import pytest

from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
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


def test_default_runtime_source_is_project_private(tmp_path, monkeypatch):
    monkeypatch.delenv("RESEARCH_DSH_SOURCE", raising=False)
    data_root = tmp_path / ".research-workbench" / "research-web"
    resolved = WebServiceManager(project_root=tmp_path, data_root=data_root)
    assert resolved.runtime_source == (tmp_path / ".research-workbench" / "dsh-source").resolve()


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
