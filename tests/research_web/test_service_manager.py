import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.research_web import lifecycle_lock as lifecycle_lock_module
from app.research_web import runtime_auth as runtime_auth_module
from app.research_web import service_diagnostics as service_diagnostics_module
from app.research_web import service_manager as service_manager_module
from app.research_web.lifecycle_lock import LifecycleLock, LifecycleLockError
from app.research_web.service_diagnostics import ServiceProbe
from app.research_web.service_manager import (
    ServiceManagerError,
    WebServiceManager,
    _is_unsafe_private_directory,
    format_doctor_status,
    format_status,
)
from research_workbench_entrypoint.web_contract import ListenerFact, ProcessFact


def _write_lock_owner(path: Path, *, pid: int, token: str = "a" * 32) -> None:
    path.mkdir(mode=0o700)
    owner = path / "owner.json"
    owner.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "pid": pid,
                "token": token,
                "started_at": time.time(),
            }
        ),
        encoding="utf-8",
    )
    owner.chmod(0o600)


def test_lifecycle_lock_rejects_live_owner_and_two_contenders(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"

    with LifecycleLock(path, lambda pid: pid == os.getpid(), pid=os.getpid()):
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
        assert set(owner) == {"schema_version", "pid", "token", "started_at"}
        assert owner["pid"] == os.getpid()
        assert len(owner["token"]) == 32
        assert path.stat().st_mode & 0o777 == 0o700
        assert path.parent.stat().st_mode & 0o777 == 0o700
        assert (path / "owner.json").stat().st_mode & 0o777 == 0o600

        with (
            pytest.raises(LifecycleLockError) as captured,
            LifecycleLock(path, lambda _pid: True, pid=os.getpid() + 1),
        ):
            pytest.fail("a live owner must exclude a second contender")

        assert captured.value.code == "lifecycle_busy"
        assert "lifecycle_busy" in str(captured.value)

    assert not path.exists()


def test_lifecycle_lock_recovers_confirmed_dead_owner_once(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)

    with LifecycleLock(path, lambda pid: pid != 424242, pid=os.getpid()):
        owner = json.loads((path / "owner.json").read_text(encoding="utf-8"))
        assert owner["pid"] == os.getpid()
        assert owner["token"] != "a" * 32

    assert list(path.parent.iterdir()) == []


@pytest.mark.parametrize(
    "owner_payload",
    [
        "{",
        json.dumps(
            {
                "schema_version": 1,
                "pid": True,
                "token": "a" * 32,
                "started_at": 0,
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "pid": 123,
                "token": "not-a-token",
                "started_at": 0,
            }
        ),
        json.dumps(
            {
                "schema_version": 1,
                "pid": 123,
                "token": "a" * 32,
                "started_at": 10**500,
            }
        ),
        "[" * 1100 + "0" + "]" * 1100,
        json.dumps({"huge": "x" * 5000}),
    ],
    ids=["malformed", "bool-pid", "bad-token", "huge-time", "deep", "oversize"],
)
def test_lifecycle_lock_treats_malformed_or_unbounded_owner_as_busy(tmp_path, owner_payload):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    path.mkdir(mode=0o700)
    owner = path / "owner.json"
    owner.write_text(owner_payload, encoding="utf-8")
    owner.chmod(0o600)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("malformed ownership must never be reclaimed")

    assert captured.value.code == "lifecycle_busy"
    assert path.exists()


def test_lifecycle_lock_rejects_alias_and_hardlinked_owner(tmp_path):
    run_root = tmp_path / "run"
    run_root.mkdir(mode=0o700)
    actual = run_root / "actual.lock"
    _write_lock_owner(actual, pid=424242)
    alias = run_root / "lifecycle.lock"
    alias.symlink_to(actual, target_is_directory=True)

    with (
        pytest.raises(LifecycleLockError, match="busy") as alias_error,
        LifecycleLock(alias, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("directory aliases are not lock ownership")
    assert alias_error.value.code == "lifecycle_busy"

    alias.unlink()
    owner = actual / "owner.json"
    os.link(owner, run_root / "owner-alias.json")
    with (
        pytest.raises(LifecycleLockError) as hardlink_error,
        LifecycleLock(actual, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("hardlinked owner files are not reclaimable")
    assert hardlink_error.value.code == "lifecycle_busy"


def test_lifecycle_lock_rejects_parent_alias_and_unexpected_lock_content(tmp_path):
    actual_parent = tmp_path / "actual"
    actual_parent.mkdir(mode=0o700)
    alias_parent = tmp_path / "alias"
    alias_parent.symlink_to(actual_parent, target_is_directory=True)

    with (
        pytest.raises(LifecycleLockError) as alias_error,
        LifecycleLock(alias_parent / "lifecycle.lock", lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("parent aliases must not redirect lifecycle ownership")
    assert alias_error.value.code == "lifecycle_busy"

    path = actual_parent / "lifecycle.lock"
    _write_lock_owner(path, pid=424242)
    (path / "unexpected").write_text("keep", encoding="utf-8")
    with (
        pytest.raises(LifecycleLockError) as content_error,
        LifecycleLock(path, lambda _pid: False, pid=os.getpid()),
    ):
        pytest.fail("unexpected lock content must not be deleted")
    assert content_error.value.code == "lifecycle_busy"
    assert (path / "owner.json").exists()
    assert (path / "unexpected").read_text(encoding="utf-8") == "keep"


def test_lifecycle_lock_exit_never_removes_replacement_owner(tmp_path):
    path = tmp_path / "run" / "lifecycle.lock"
    lock = LifecycleLock(path, lambda _pid: True, pid=os.getpid())
    lock.__enter__()
    replacement = {
        "schema_version": 1,
        "pid": os.getpid() + 1,
        "token": "b" * 32,
        "started_at": time.time(),
    }
    (path / "owner.json").write_text(json.dumps(replacement), encoding="utf-8")
    (path / "owner.json").chmod(0o600)

    with pytest.raises(LifecycleLockError) as captured:
        lock.__exit__(None, None, None)

    assert captured.value.code == "lifecycle_lock_ownership_lost"
    assert path.exists()
    assert json.loads((path / "owner.json").read_text(encoding="utf-8")) == replacement


def test_lifecycle_lock_stale_recovery_does_not_delete_raced_owner(tmp_path, monkeypatch):
    path = tmp_path / "run" / "lifecycle.lock"
    path.parent.mkdir(mode=0o700)
    _write_lock_owner(path, pid=424242)
    original_rename = lifecycle_lock_module.os.rename
    raced = False

    def race_once(source, target, *args, **kwargs):
        nonlocal raced
        if not raced and Path(source) == path:
            raced = True
            replacement = {
                "schema_version": 1,
                "pid": os.getpid(),
                "token": "c" * 32,
                "started_at": time.time(),
            }
            (path / "owner.json").write_text(json.dumps(replacement), encoding="utf-8")
            (path / "owner.json").chmod(0o600)
        return original_rename(source, target, *args, **kwargs)

    monkeypatch.setattr(lifecycle_lock_module.os, "rename", race_once)

    with (
        pytest.raises(LifecycleLockError) as captured,
        LifecycleLock(path, lambda pid: pid != 424242, pid=os.getpid() + 1),
    ):
        pytest.fail("a raced owner must not be removed")

    assert captured.value.code == "lifecycle_busy"
    remaining = list(path.parent.iterdir())
    assert remaining
    assert any(
        json.loads((item / "owner.json").read_text(encoding="utf-8"))["token"] == "c" * 32
        for item in remaining
        if item.is_dir()
    )


def _service_probe(
    role: str,
    *,
    state: str = "valid",
    process: str = "alive",
    ownership: str = "owned",
    port_state: str = "listening",
    protocol: str = "passed",
    ready: bool = True,
    pid: int | None = 101,
    issues: tuple[str, ...] = (),
) -> ServiceProbe:
    return ServiceProbe(
        role,
        3081 if role == "runtime" else 8088,
        state,
        process,
        ownership,
        port_state,
        protocol,
        ready,
        pid,
        issues,
    )


def test_service_manager_error_exposes_safe_code_role_and_string():
    error = ServiceManagerError("safe message", code="runtime_process_exited", role="runtime")

    assert str(error) == "safe message"
    assert error.code == "runtime_process_exited"
    assert error.role == "runtime"


def test_start_ready_owned_stack_is_idempotent_and_preserves_pids(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail("ready owned services must not be respawned"),
    )

    result = manager.start(open_browser=False)

    assert result["services"]["runtime"]["pid"] == 101
    assert result["services"]["web"]["pid"] == 202


def test_start_removes_dead_stale_state_then_spawns(manager, monkeypatch):
    runtime, web = manager._processes()
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    probes = {
        "runtime": _service_probe(
            "runtime",
            state="stale",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_stale",),
        ),
        "web": _service_probe("web", pid=202),
    }
    spawned: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        spawned.append(process.role)
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert spawned == [runtime.role]
    assert not manager._state_path(runtime.role).exists()
    assert probes[web.role].pid == 202


def test_start_quarantines_invalid_closed_state_and_replaces_prior_copy(manager, monkeypatch):
    runtime, _web = manager._processes()
    manager._prepare_private_directories()
    state_path = manager._state_path(runtime.role)
    state_path.write_text("{new-invalid", encoding="utf-8")
    state_path.chmod(0o600)
    quarantine = manager.run_root / "runtime.invalid.json"
    quarantine.write_text("old-invalid", encoding="utf-8")
    quarantine.chmod(0o600)
    probes = {
        "runtime": _service_probe(
            "runtime",
            state="invalid",
            process="inaccessible",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid",),
        ),
        "web": _service_probe("web", pid=202),
    }
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert not state_path.exists()
    assert quarantine.read_text(encoding="utf-8") == "{new-invalid"
    assert quarantine.stat().st_mode & 0o777 == 0o600
    assert not list(manager.run_root.glob("runtime.invalid-*.json"))


@pytest.mark.parametrize(
    "probe",
    [
        _service_probe(
            "runtime",
            state="invalid",
            process="alive",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid_live_pid",),
        ),
        _service_probe(
            "runtime",
            state="invalid",
            process="inaccessible",
            ownership="unknown",
            port_state="listening",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_invalid_port_listening",),
        ),
        _service_probe(
            "runtime",
            process="alive",
            ownership="foreign",
            ready=False,
            pid=None,
            protocol="not_run",
            issues=("runtime_pid_foreign", "runtime_port_in_use_unknown"),
        ),
        _service_probe(
            "runtime",
            process="alive",
            ownership="foreign",
            ready=False,
            pid=None,
            protocol="not_run",
            issues=("runtime_port_owner_mismatch",),
        ),
    ],
    ids=["invalid-live", "invalid-listener", "foreign-pid", "listener-mismatch"],
)
def test_start_refuses_unsafe_probe_without_killing_or_spawning(manager, monkeypatch, probe):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: probe if process.role == "runtime" else _service_probe("web", pid=202),
    )
    monkeypatch.setattr(
        manager,
        "_terminate_pid",
        lambda *_args, **_kwargs: pytest.fail("unsafe probes must never be killed"),
    )
    monkeypatch.setattr(
        manager,
        "_spawn",
        lambda _process: pytest.fail("unsafe probes must never be replaced"),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    assert captured.value.code in probe.issues
    assert captured.value.code in str(captured.value)
    assert captured.value.role == "runtime"


def test_start_rebuilds_owned_unhealthy_runtime_stack_in_dependency_order(manager, monkeypatch):
    probes = {
        "runtime": _service_probe(
            "runtime",
            protocol="failed",
            ready=False,
            pid=101,
            issues=("runtime_health_failed",),
        ),
        "web": _service_probe("web", pid=202),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(
            process.role, pid=303 if process.role == "runtime" else 404
        )
        return probes[process.role].pid

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert events == ["stop:web", "stop:runtime", "spawn:runtime", "spawn:web"]


def test_start_rebuilds_only_owned_unhealthy_web(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe(
            "web",
            protocol="failed",
            ready=False,
            pid=202,
            issues=("web_runtime_api_failed",),
        ),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    manager.start(open_browser=False)

    assert events == ["stop:web", "spawn:web"]


def test_wait_for_ready_reports_confirmed_early_exit_without_sleep(manager, monkeypatch):
    runtime = manager._processes()[0]
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            state="stale",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
            issues=("runtime_state_stale",),
        ),
    )
    monkeypatch.setattr(
        service_manager_module.time,
        "sleep",
        lambda _seconds: pytest.fail("confirmed exits must not sleep until timeout"),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=35)

    assert captured.value.code == "runtime_process_exited"
    assert captured.value.role == "runtime"


def test_wait_for_ready_times_out_with_last_stable_issue(manager, monkeypatch):
    runtime = manager._processes()[0]
    ticks = iter([0.0, 0.0, 0.2])
    monkeypatch.setattr(service_manager_module.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda _process: _service_probe(
            "runtime",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=303,
            issues=("runtime_port_closed",),
        ),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._wait_for_ready(runtime, 303, timeout=0.1)

    assert captured.value.code == "runtime_health_timeout"
    assert captured.value.role == "runtime"
    assert "runtime_port_closed" in str(captured.value)


def test_wait_for_ready_bootstraps_runtime_auth_before_authoritative_ready(manager, monkeypatch):
    runtime = manager._processes()[0]
    probes = iter(
        [
            _service_probe(
                "runtime",
                protocol="failed",
                ready=False,
                pid=303,
                issues=("runtime_health_failed",),
            ),
            _service_probe("runtime", pid=303),
        ]
    )
    bootstrapped: list[bool] = []
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(manager, "_runtime_sessions", lambda: bootstrapped.append(True) or [])
    monkeypatch.setattr(service_manager_module.time, "sleep", lambda _seconds: None)

    result = manager._wait_for_ready(runtime, 303, timeout=1)

    assert result.ready is True
    assert bootstrapped == [True]


def test_start_rollback_targets_only_process_spawned_by_this_invocation(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe(
            "web",
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    }
    rolled_back: list[tuple[str, int]] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_spawn", lambda _process: 303)

    def wait_for_ready(process, pid, *, timeout):
        if process.role == "web":
            raise ServiceManagerError("web timeout", code="web_health_timeout", role="web")
        return _service_probe("runtime", pid=pid)

    monkeypatch.setattr(manager, "_wait_for_ready", wait_for_ready)
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, pid: rolled_back.append((process.role, pid)),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)

    assert captured.value.code == "web_health_timeout"
    assert rolled_back == [("web", 303)]


def test_spawn_and_wait_rolls_back_its_exact_spawn_on_wait_failure(manager, monkeypatch):
    runtime = manager._processes()[0]
    rolled_back: list[tuple[str, int]] = []
    monkeypatch.setattr(manager, "_spawn", lambda _process: 303)
    monkeypatch.setattr(
        manager,
        "_wait_for_ready",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            ServiceManagerError(
                "runtime timeout",
                code="runtime_health_timeout",
                role="runtime",
            )
        ),
    )
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, pid: rolled_back.append((process.role, pid)),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._spawn_and_wait(runtime)

    assert captured.value.code == "runtime_health_timeout"
    assert rolled_back == [("runtime", 303)]


def test_stop_orders_web_before_runtime_and_returns_final_facts(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    stopped: list[str] = []
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def stop_owned(process, _probe):
        stopped.append(process.role)
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)

    result = manager.stop()

    assert stopped == ["web", "runtime"]
    assert result["services"]["runtime"]["running"] is False
    assert result["services"]["web"]["running"] is False


def test_stop_cleans_dead_stale_state_without_removing_runtime_auth(manager, monkeypatch):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    auth = manager._runtime_auth_path()
    auth.parent.mkdir(parents=True, exist_ok=True)
    auth.write_text("retained", encoding="utf-8")

    def probe(process):
        if process.role == "runtime":
            return _service_probe(
                "runtime",
                state="stale",
                process="missing",
                ownership="unknown",
                port_state="closed",
                protocol="not_run",
                ready=False,
                pid=None,
                issues=("runtime_state_stale",),
            )
        return _service_probe(
            "web",
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )

    monkeypatch.setattr(manager, "_probe_service", probe)

    manager.stop()

    assert not manager._state_path(runtime.role).exists()
    assert auth.read_text(encoding="utf-8") == "retained"


def test_runtime_rebuild_reports_coded_auth_cleanup_failure(manager):
    runtime = manager._processes()[0]
    manager._prepare_private_directories()
    manager._write_state(runtime, 101)
    auth = manager._runtime_auth_path()
    auth.mkdir(parents=True)
    stale = _service_probe(
        "runtime",
        state="stale",
        process="missing",
        ownership="unknown",
        port_state="closed",
        protocol="not_run",
        ready=False,
        pid=None,
        issues=("runtime_state_stale",),
    )

    with pytest.raises(ServiceManagerError) as captured:
        manager._normalize_absent_probe(runtime, stale, clear_runtime_auth=True)

    assert captured.value.code == "runtime_ownership_unverified"


def test_restart_holds_one_lock_without_calling_public_lifecycle_methods(manager, monkeypatch):
    entries = 0

    class Lock:
        def __enter__(self):
            nonlocal entries
            entries += 1

        def __exit__(self, *_args):
            return False

    monkeypatch.setattr(manager, "_lifecycle_lock", Lock)
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_service_probes", lambda: (_service_probe("runtime"), _service_probe("web"))
    )
    monkeypatch.setattr(manager, "_active_research", list)
    monkeypatch.setattr(manager, "stop", lambda: pytest.fail("restart must not call public stop"))
    monkeypatch.setattr(
        manager, "start", lambda **_kwargs: pytest.fail("restart must not call public start")
    )
    monkeypatch.setattr(manager, "_stop_locked", lambda: {"services": {}})
    monkeypatch.setattr(manager, "_start_locked", lambda **_kwargs: {"ok": True})

    assert manager.restart(force=False, open_browser=False) == {"ok": True}
    assert entries == 1


def test_restart_active_research_guard_runs_before_stop(manager, monkeypatch):
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_service_probes", lambda: (_service_probe("runtime"), _service_probe("web"))
    )
    monkeypatch.setattr(manager, "_active_research", lambda: ["session-1"])
    monkeypatch.setattr(manager, "_stop_locked", lambda: pytest.fail("guard must run first"))

    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart(force=False, open_browser=False)


def test_restart_runtime_stops_and_rebuilds_only_owned_runtime(manager, monkeypatch):
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    events: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_active_research", list)

    def stop_owned(process, _probe):
        events.append(f"stop:{process.role}")
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        events.append(f"spawn:{process.role}")
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_owned)
    monkeypatch.setattr(manager, "_spawn", spawn)

    result = manager.restart_runtime(force=False)

    assert events == ["stop:runtime", "spawn:runtime"]
    assert probes["web"].pid == 202
    assert result == {"running": True, "healthy": True, "pid": 303, "port": 3081}


def test_lifecycle_lock_contention_maps_to_coded_service_error(manager):
    path = manager.run_root / "lifecycle.lock"

    with (
        LifecycleLock(path, lambda _pid: True, pid=os.getpid()),
        pytest.raises(ServiceManagerError) as captured,
    ):
        manager.stop()

    assert captured.value.code == "lifecycle_busy"


def test_internal_probe_facts_stay_private_to_service_manager():
    assert not hasattr(service_diagnostics_module, "StateFact")
    assert not hasattr(service_diagnostics_module, "ProcessFact")
    assert service_manager_module._StateFact.__dataclass_params__.frozen is True
    assert service_manager_module._ProcessFact.__dataclass_params__.frozen is True
    assert service_manager_module._ProcessFact is not ProcessFact


def test_service_probe_public_is_safe_and_compatible():
    probe = ServiceProbe(
        role="runtime",
        port=3081,
        state="valid",
        process="alive",
        ownership="foreign",
        port_state="listening",
        protocol="not_run",
        ready=False,
        pid=4321,
        issues=("runtime_pid_foreign",),
    )

    assert probe.public(log="/safe/runtime.log") == {
        "state": "valid",
        "process": "alive",
        "ownership": "foreign",
        "port_state": "listening",
        "protocol": "not_run",
        "ready": False,
        "running": False,
        "healthy": False,
        "pid": None,
        "port": 3081,
        "issues": ["runtime_pid_foreign"],
        "log": "/safe/runtime.log",
    }


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


def _valid_state(manager: WebServiceManager, role: str, pid: int = 4321) -> tuple[object, Path]:
    manager._prepare_private_directories()
    process = next(item for item in manager._processes() if item.role == role)
    manager._write_state(process, pid)
    return process, manager._state_path(role)


def test_status_exposes_full_fact_chain(manager, monkeypatch):
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: ServiceProbe(
            role=process.role,
            port=process.port,
            state="valid",
            process="alive",
            ownership="owned",
            port_state="listening",
            protocol="passed" if process.role == "runtime" else "failed",
            ready=process.role == "runtime",
            pid=101 if process.role == "runtime" else 202,
            issues=() if process.role == "runtime" else ("web_runtime_api_failed",),
        ),
    )

    status = manager.status()

    assert status["product_ready"] is False
    assert status["warnings"] == []
    assert status["services"]["runtime"]["ready"] is True
    assert status["services"]["web"]["running"] is True
    assert status["services"]["web"]["healthy"] is False
    assert status["services"]["web"]["issues"] == ["web_runtime_api_failed"]
    assert status["services"]["runtime"]["log"].endswith("runtime.log")


def test_doctor_keeps_other_service_when_one_state_is_invalid(manager, monkeypatch):
    probes = iter(
        [
            ServiceProbe(
                "runtime",
                3081,
                "invalid",
                "inaccessible",
                "unknown",
                "closed",
                "not_run",
                False,
                None,
                ("runtime_state_invalid",),
            ),
            ServiceProbe(
                "web",
                8088,
                "valid",
                "alive",
                "owned",
                "listening",
                "passed",
                True,
                222,
                (),
            ),
        ]
    )
    monkeypatch.setattr(manager, "_probe_service", lambda _process: next(probes))
    monkeypatch.setattr(
        manager,
        "_installation_diagnosis",
        lambda: {
            "schema_version": 1,
            "ok": True,
            "issues": ["shared_issue", "runtime_state_invalid"],
        },
    )

    report = manager.doctor()

    assert report["schema_version"] == 2
    assert report["ok"] is True
    assert report["installation_ok"] is True
    assert report["product_ready"] is False
    assert report["model_ready"] is False
    assert report["issues"] == ["shared_issue", "runtime_state_invalid"]
    assert report["warnings"] == []
    assert report["services"]["runtime"]["issues"] == ["runtime_state_invalid"]
    assert report["services"]["web"]["ready"] is True
    assert "log" not in report["services"]["web"]


def test_probe_valid_owned_listener_passes_protocol_without_mutation(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    before = state_path.read_bytes()
    state = json.loads(before)
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(manager, "_protocol_health", lambda _process: True)
    monkeypatch.setattr(
        manager,
        "_terminate_pid",
        lambda *_args, **_kwargs: pytest.fail("read-only probe must never terminate"),
    )

    probe = manager._probe_service(process)

    assert probe == ServiceProbe(
        "runtime",
        3081,
        "valid",
        "alive",
        "owned",
        "listening",
        "passed",
        True,
        4321,
        (),
    )
    assert state_path.read_bytes() == before


def test_probe_dead_pid_is_stale_and_does_not_unlink_state(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("missing", None, None),
    )
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.state == "stale"
    assert probe.process == "missing"
    assert probe.ownership == "unknown"
    assert probe.protocol == "not_run"
    assert probe.ready is False
    assert "runtime_state_stale" in probe.issues
    assert state_path.exists()


def test_status_does_not_remove_stale_state(manager, monkeypatch):
    _process, state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("missing", None, None),
    )
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    status = manager.status()

    assert status["services"]["runtime"]["state"] == "stale"
    assert status["services"]["web"]["state"] == "missing"
    assert state_path.exists()


def test_runtime_probe_never_regenerates_missing_auth(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(manager, "_read_runtime_auth", lambda: None)
    monkeypatch.setattr(
        manager,
        "_write_runtime_auth",
        lambda _cookie: pytest.fail("read-only probe must not write auth"),
    )

    probe = manager._probe_service(process)

    assert probe.protocol == "failed"
    assert probe.ready is False
    assert probe.issues == ("runtime_health_failed",)


def _authoritative_process_fact(process, state: dict[str, object]) -> ProcessFact:
    return ProcessFact(
        "alive",
        " ".join(process.signature),
        None,
        tuple(process.signature),
        float(state["started_at"]),
    )


def test_probe_rejects_same_signature_pid_reuse_by_start_identity(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact(
            "alive",
            " ".join(process.signature),
            None,
            tuple(process.signature),
            float(state["started_at"]) - 60,
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: pytest.fail("reused PID must never reach protocol"),
    )

    probe = manager._probe_service(process)

    assert probe.process == "alive"
    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert probe.issues == ("runtime_pid_reused", "runtime_port_in_use_unknown")


@pytest.mark.parametrize("colliding_port", ["13081", "prefix-3081-suffix"])
def test_probe_rejects_numeric_and_embedded_signature_token_collisions(
    manager, monkeypatch, colliding_port
):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    argv = tuple(
        colliding_port if item == str(process.port) else item for item in process.signature
    )
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact("alive", " ".join(argv), None, argv, float(state["started_at"])),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )

    probe = manager._probe_service(process)

    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert "runtime_pid_foreign" in probe.issues


def test_probe_owns_exact_spaced_signature_tokens(manager, tmp_path, monkeypatch):
    project_root = tmp_path / "project with spaces"
    project_root.mkdir()
    data_root = tmp_path / "data with spaces" / "research-web"
    spaced = WebServiceManager(
        project_root=project_root,
        data_root=data_root,
        runtime_source=manager.runtime_source,
        python=manager.python,
        node=manager.node,
    )
    process, state_path = _valid_state(spaced, "web")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    argv = ("uvicorn", *process.signature, "--flag-between-signatures")
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: ProcessFact(
            "alive", "display text is not authoritative", None, argv, float(state["started_at"])
        ),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (int(state["pid"]),), None),
    )
    monkeypatch.setattr(spaced, "_protocol_health", lambda _process: True)

    probe = spaced._probe_service(process)

    assert str(project_root) in process.signature
    assert " " in str(project_root)
    assert probe.ownership == "owned"
    assert probe.ready is True


def test_probe_requires_owned_pid_to_be_the_exact_listener(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (9876,), None),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: pytest.fail("foreign listener must never reach protocol"),
    )

    probe = manager._probe_service(process)

    assert probe.process == "alive"
    assert probe.ownership == "foreign"
    assert probe.ready is False
    assert probe.issues == ("runtime_port_owner_mismatch",)


def test_probe_listener_failure_preserves_process_facts_as_unknown(manager, monkeypatch):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    monkeypatch.setattr(
        service_manager_module,
        "probe_process",
        lambda _pid: _authoritative_process_fact(process, state),
    )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("unknown", (), "listener_probe_failed"),
    )

    probe = manager._probe_service(process)

    assert probe.state == "valid"
    assert probe.process == "alive"
    assert probe.ownership == "unknown"
    assert probe.port_state == "unknown"
    assert probe.protocol == "not_run"
    assert probe.issues == ("runtime_listener_probe_failed",)


@pytest.mark.parametrize("stage", ["state", "process", "listener", "protocol"])
def test_probe_stage_errors_preserve_already_observed_facts(manager, monkeypatch, stage):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if stage == "state":
        monkeypatch.setattr(
            manager, "_probe_state", lambda _process: (_ for _ in ()).throw(OSError())
        )
    else:
        monkeypatch.setattr(
            service_manager_module,
            "probe_process",
            lambda _pid: (
                (_ for _ in ()).throw(OSError())
                if stage == "process"
                else _authoritative_process_fact(process, state)
            ),
        )
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: (
            (_ for _ in ()).throw(OSError())
            if stage == "listener"
            else ListenerFact("listening", (int(state["pid"]),), None)
        ),
    )
    monkeypatch.setattr(
        manager,
        "_protocol_health",
        lambda _process: ((_ for _ in ()).throw(OSError()) if stage == "protocol" else True),
    )

    probe = manager._probe_service(process)

    if stage == "state":
        assert probe.state == "invalid"
        assert probe.process == "inaccessible"
        assert probe.port_state == "listening"
    elif stage == "process":
        assert probe.state == "valid"
        assert probe.process == "inaccessible"
        assert probe.port_state == "listening"
    elif stage == "listener":
        assert probe.state == "valid"
        assert probe.process == "alive"
        assert probe.ownership == "unknown"
        assert probe.port_state == "unknown"
    else:
        assert probe.state == "valid"
        assert probe.process == "alive"
        assert probe.ownership == "owned"
        assert probe.port_state == "listening"
        assert probe.protocol == "failed"
    assert probe.ready is False
    assert any(issue.startswith("runtime_") for issue in probe.issues)


def test_status_keeps_other_service_when_one_probe_stage_errors(manager, monkeypatch):
    original = manager._probe_state

    def state_probe(process):
        if process.role == "runtime":
            raise OSError("private detail")
        return original(process)

    monkeypatch.setattr(manager, "_probe_state", state_probe)
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    status = manager.status()

    assert status["services"]["runtime"]["state"] == "invalid"
    assert status["services"]["runtime"]["issues"] == ["runtime_state_probe_failed"]
    assert status["services"]["web"]["state"] == "missing"
    assert status["services"]["web"]["issues"] == []
    assert "private detail" not in json.dumps(status)


@pytest.mark.parametrize(
    ("process_fact", "expected_process", "ownership", "issue"),
    [
        (
            ProcessFact(
                "alive",
                "python unrelated.py",
                None,
                ("python", "unrelated.py"),
                1.0,
            ),
            "alive",
            "foreign",
            "runtime_pid_foreign",
        ),
        (
            ProcessFact("alive", None, None),
            "inaccessible",
            "unknown",
            "runtime_process_inaccessible",
        ),
        (
            ProcessFact("inaccessible", None, "process_access_denied"),
            "inaccessible",
            "unknown",
            "runtime_process_inaccessible",
        ),
    ],
)
def test_probe_distinguishes_foreign_and_unknown_processes(
    manager, monkeypatch, process_fact, expected_process, ownership, issue
):
    process, _state_path = _valid_state(manager, "runtime")
    monkeypatch.setattr(service_manager_module, "probe_process", lambda _pid: process_fact)
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.process == expected_process
    assert probe.ownership == ownership
    assert issue in probe.issues
    assert probe.pid is None


def test_probe_listener_without_owned_service_is_not_ready(manager, monkeypatch):
    process = manager._processes()[0]
    monkeypatch.setattr(
        service_manager_module,
        "listener_pids",
        lambda _port: ListenerFact("listening", (9999,), None),
    )

    probe = manager._probe_service(process)

    assert probe.state == "missing"
    assert probe.port_state == "listening"
    assert probe.protocol == "not_run"
    assert probe.ready is False
    assert probe.issues == ("runtime_port_in_use_unknown",)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda state: "{",
        lambda state: json.dumps({**state, "extra": True}),
        lambda state: json.dumps({**state, "pid": "4321"}),
        lambda state: json.dumps({**state, "fingerprint": "0" * 64}),
        lambda state: json.dumps({**state, "signature": ["wrong"]}),
        lambda state: json.dumps({**state, "project_root": "/wrong"}),
        lambda state: json.dumps({**state, "data_root": "/wrong"}),
        lambda state: json.dumps({**state, "role": "web"}),
        lambda state: json.dumps({**state, "port": 9999}),
        lambda state: json.dumps({**state, "started_at": 10**500}),
        lambda state: "[" * 1100 + "0" + "]" * 1100,
        lambda state: json.dumps({"huge": "x" * (65 * 1024)}),
    ],
    ids=[
        "malformed-json",
        "wrong-keys",
        "wrong-types",
        "fingerprint",
        "signature",
        "project-root",
        "data-root",
        "role",
        "port",
        "huge-started-at",
        "deep-json",
        "oversize",
    ],
)
def test_probe_rejects_adversarial_state_without_throwing_or_mutating(manager, monkeypatch, mutate):
    process, state_path = _valid_state(manager, "runtime")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state_path.write_text(mutate(state), encoding="utf-8")
    before = state_path.read_bytes()
    monkeypatch.setattr(
        service_manager_module, "listener_pids", lambda _port: ListenerFact("closed", (), None)
    )

    probe = manager._probe_service(process)

    assert probe.state == "invalid"
    assert probe.process in {"inaccessible", "missing"}
    assert probe.ownership == "unknown"
    assert probe.issues == ("runtime_state_invalid",)
    assert state_path.read_bytes() == before


def test_import_does_not_load_runtime_feature_graph():
    project_root = Path(__file__).resolve().parents[2]
    script = """
import sys

import app.research_web.service_manager

assert "app.research_web.launch_runtime" not in sys.modules
assert "app.research_web.capabilities.packages" not in sys.modules
assert "app.research_web.mcp_runtime.routes" not in sys.modules
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=project_root,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr or completed.stdout


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
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    spawned = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])

    def spawn(process):
        spawned.append(process.role)
        pid = 100 + len(spawned)
        probes[process.role] = _service_probe(process.role, pid=pid)
        return pid

    monkeypatch.setattr(manager, "_spawn", spawn)
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
    probes = {
        role: _service_probe(
            role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        for role in ("runtime", "web")
    }
    stopped: list[str] = []
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_spawn", lambda _process: 123)

    def wait_for_ready(process, pid, *, timeout):
        if process.role == "web":
            raise ServiceManagerError("Web timeout", code="web_health_timeout", role="web")
        return _service_probe(process.role, pid=pid)

    monkeypatch.setattr(manager, "_wait_for_ready", wait_for_ready)
    monkeypatch.setattr(
        manager,
        "_rollback_spawned",
        lambda process, _pid: stopped.append(process.role),
    )
    with pytest.raises(ServiceManagerError) as captured:
        manager.start(open_browser=False)
    assert captured.value.code == "web_health_timeout"
    assert stopped == ["web", "runtime"]


def test_restart_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager,
        "_service_probes",
        lambda: (_service_probe("runtime", pid=123), _service_probe("web", pid=456)),
    )
    monkeypatch.setattr(manager, "_active_research", lambda: ["session-1"])
    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart(force=False, open_browser=False)


def test_restart_runtime_keeps_web_online_and_waits_for_owned_runtime(manager, monkeypatch):
    manager._prepare_private_directories()
    runtime, web = manager._processes()
    probes = {
        "runtime": _service_probe("runtime", pid=101),
        "web": _service_probe("web", pid=202),
    }
    stopped: list[str] = []
    spawned: list[str] = []

    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(manager, "_probe_service", lambda process: probes[process.role])
    monkeypatch.setattr(manager, "_active_research", list)

    def stop_one(process, _probe):
        stopped.append(process.role)
        probes[process.role] = _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        )
        return True

    def spawn(process):
        spawned.append(process.role)
        probes[process.role] = _service_probe(process.role, pid=303)
        return 303

    monkeypatch.setattr(manager, "_stop_owned_probe", stop_one)
    monkeypatch.setattr(manager, "_spawn", spawn)

    result = manager.restart_runtime(force=False)

    assert stopped == [runtime.role]
    assert spawned == [runtime.role]
    assert probes[web.role].pid == 202
    assert result == {"running": True, "healthy": True, "pid": 303, "port": 3081}


def test_restart_runtime_refuses_active_research_without_force(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(manager, "_installation_diagnosis", lambda: {"ok": True, "issues": []})
    monkeypatch.setattr(
        manager, "_probe_service", lambda process: _service_probe(process.role, pid=123)
    )
    monkeypatch.setattr(manager, "_active_research", lambda: ["session-1"])

    with pytest.raises(ServiceManagerError, match="活动研究"):
        manager.restart_runtime(force=False)


def test_stop_never_targets_unowned_process(manager, monkeypatch):
    manager._prepare_private_directories()
    monkeypatch.setattr(
        manager,
        "_probe_service",
        lambda process: _service_probe(
            process.role,
            state="missing",
            process="missing",
            ownership="unknown",
            port_state="closed",
            protocol="not_run",
            ready=False,
            pid=None,
        ),
    )
    kill_calls = []
    monkeypatch.setattr("os.killpg", lambda *args: kill_calls.append(args))
    manager.stop()
    assert kill_calls == []


def test_status_formatter_is_concise():
    value = {
        "url": "http://127.0.0.1:8088/#/fingpt",
        "services": {
            "runtime": {
                "state": "valid",
                "process": "alive",
                "ownership": "owned",
                "port_state": "listening",
                "protocol": "passed",
                "ready": True,
                "running": True,
                "healthy": True,
                "pid": 10,
                "port": 3081,
                "issues": [],
            },
            "web": {
                "state": "missing",
                "process": "missing",
                "ownership": "unknown",
                "port_state": "closed",
                "protocol": "not_run",
                "ready": False,
                "running": False,
                "healthy": False,
                "pid": None,
                "port": 8088,
                "issues": ["web_state_missing"],
            },
        },
    }
    rendered = format_status(value)
    assert "runtime: healthy" in rendered
    assert "web: stopped" in rendered
    assert "state=valid" in rendered
    assert "ownership=owned" in rendered
    assert "protocol=passed" in rendered
    assert "web_state_missing" in rendered
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
        "_service_probes",
        lambda: (
            ServiceProbe(
                "runtime", 3081, "valid", "alive", "owned", "listening", "passed", True, 111, ()
            ),
            ServiceProbe(
                "web", 8088, "valid", "alive", "owned", "listening", "passed", True, 222, ()
            ),
        ),
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
    assert report["schema_version"] == 2
    assert report["installation_ok"] is True
    assert report["product_ready"] is True
    assert report["model_ready"] is False
    assert report["services"]["web"]["port"] == 8088
    assert report["services"]["web"]["running"] is True
    assert report["services"]["web"]["healthy"] is True
    assert "log" not in report["services"]["web"]
    assert str(manager.project_root) not in serialized
    assert "must-never-escape" not in serialized
    rendered = format_doctor_status(report)
    assert "Installation: ready" in rendered
    assert "Product: ready" in rendered
    assert "Model: not ready" in rendered
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
