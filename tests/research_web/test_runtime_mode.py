"""Runtime-mode persistence stays private, strict and bootstrap-safe."""

from __future__ import annotations

import json
import logging
import multiprocessing
import os
import re
import socket
import stat
import subprocess
import sys
import threading
import traceback
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint import runtime_mode
from research_workbench_entrypoint.runtime_mode import RuntimeModeError, RuntimeModeStore


@pytest.fixture(autouse=True)
def isolated_os_native_candidate(tmp_path, monkeypatch):
    from research_workbench_entrypoint import web_bootstrap

    monkeypatch.setattr(
        web_bootstrap,
        "_standard_native_data_root",
        lambda: tmp_path / "os-user/.research-workbench/research-web",
    )


def test_native_dispatch_incomplete_environment_uses_safe_diagnostics(tmp_path, monkeypatch):
    import io

    from research_workbench_entrypoint import bootstrap

    python = tmp_path / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text("not an owned environment")
    monkeypatch.setattr(bootstrap, "native_python", lambda _root: python)
    monkeypatch.setattr(bootstrap.os, "execve", lambda *_args: pytest.fail("unowned exec"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    output = io.StringIO()
    monkeypatch.setattr(sys, "stdout", output)
    assert bootstrap.dispatch(["web", "doctor", "--json"], tmp_path) == 0
    report = json.loads(output.getvalue())
    assert report["schema_version"] == 2
    assert report["issues"] == ["python_environment_incomplete"]
    assert not report["installation_ok"]


def test_native_switch_bridge_rejects_pid_reuse_facts(tmp_path, monkeypatch):
    from app.research_web.service_diagnostics import ServiceProbe
    from app.research_web.service_manager import WebServiceManager
    from research_workbench_entrypoint import bootstrap

    monkeypatch.setattr(
        WebServiceManager,
        "_service_probes",
        lambda _self: (
            ServiceProbe(
                "runtime",
                3081,
                "valid",
                "alive",
                "foreign",
                "listening",
                "not_run",
                False,
                None,
                ("runtime_pid_reused",),
            ),
        ),
    )
    with pytest.raises(bootstrap.ControlError, match="runtime_ownership_unknown"):
        bootstrap._native_probe("status", tmp_path, tmp_path, (8088, 3081))


def _path(home: Path) -> Path:
    return home / "install" / "runtime.json"


def _payload(*, mode: str = "native", installation_id: str = "a" * 32) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": mode,
        "installation_id": installation_id,
        "updated_at": "2026-09-29T01:02:03.456789Z",
    }


def _write_payload(home: Path, payload: object) -> Path:
    path = _path(home)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    path.chmod(0o600)
    return path


def _with_uid(identity: os.stat_result, uid: int) -> SimpleNamespace:
    return SimpleNamespace(
        **{
            name: getattr(identity, name)
            for name in (
                "st_mode",
                "st_nlink",
                "st_size",
                "st_dev",
                "st_ino",
                "st_mtime_ns",
                "st_ctime_ns",
            )
        },
        st_uid=uid,
        st_file_attributes=getattr(identity, "st_file_attributes", 0),
    )


def test_missing_record_defaults_to_native_without_writing(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()

    record = RuntimeModeStore(home).read()

    assert record.schema_version == 1
    assert record.mode == "native"
    assert record.installation_id == ""
    assert record.updated_at is None
    assert not _path(home).exists()
    with pytest.raises(FrozenInstanceError):
        record.mode = "docker"
    assert not hasattr(record, "__dict__")


def test_first_write_is_private_and_generates_one_persistent_id(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    store = RuntimeModeStore(home)

    first = store.write("docker")
    second = store.write("native")

    assert first.mode == "docker"
    assert second.mode == "native"
    assert re.fullmatch(r"[a-f0-9]{32}", first.installation_id)
    assert second.installation_id == first.installation_id
    assert second.updated_at is not None
    assert stat.S_IMODE(_path(home).parent.stat().st_mode) == 0o700
    assert stat.S_IMODE(_path(home).stat().st_mode) == 0o600
    assert RuntimeModeStore(home).read() == second


def test_unrelated_ancestor_entry_change_does_not_invalidate_read(tmp_path, monkeypatch):
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    expected = store.write("native")
    original = os.open

    def concurrent_sibling(candidate, flags, *args, **kwargs):
        if Path(candidate).name == "runtime.json":
            (tmp_path / "unrelated").mkdir()
        return original(candidate, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", concurrent_sibling)
    assert store.read() == expected


def test_same_mode_switch_is_read_only(tmp_path):
    from research_workbench_entrypoint.bootstrap import switch_runtime

    home = tmp_path / "missing"
    store = RuntimeModeStore(home)
    assert switch_runtime(store, "native", None, None) == {
        "schema_version": 1,
        "ok": True,
        "issues": [],
        "mode": "native",
        "changed": False,
    }
    assert not home.exists()


def test_switch_round_trip_preserves_real_data_and_isolates_runtime_state(tmp_path, monkeypatch):
    from research_workbench_entrypoint import bootstrap

    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    record = store.write("native")
    data = home / "research-web"
    data.mkdir(mode=0o700)
    fixture = data / "research-fixture.json"
    fixture.write_text('{"session":"persisted","revision":1}')
    snapshots = []

    class OwnedController:
        ports = (18088, 13081)

        def __init__(self, root):
            self.root = root
            root.mkdir(parents=True, exist_ok=True, mode=0o700)

        def start(self):
            (self.root / "owned-state.json").write_text('{"running":true}')
            snapshots.append(json.loads(fixture.read_text()))

        def preflight(self):
            return {"ok": fixture.is_file(), "issues": []}

        def status(self):
            path = self.root / "owned-state.json"
            running = path.exists() and json.loads(path.read_text())["running"]
            return {
                "ok": True,
                "services": {role: {"running": running} for role in ("web", "runtime")},
            }

        def stop(self):
            (self.root / "owned-state.json").write_text('{"running":false}')
            return {"ok": True}

    native = OwnedController(home / "run")
    docker = OwnedController(home / "run/docker" / record.installation_id)
    monkeypatch.setattr(bootstrap, "port_busy", lambda port: False)
    native.start()
    assert not docker.status()["services"]["web"]["running"]
    assert bootstrap.switch_runtime(store, "docker", docker, native)["issues"] == [
        "runtime_stop_current_required"
    ]
    assert store.read().mode == "native"
    assert bootstrap.switch_runtime(store, "docker", docker, native, stop_current=True)["ok"]
    docker.start()
    assert not native.status()["services"]["web"]["running"]
    assert bootstrap.switch_runtime(store, "native", docker, native, stop_current=True)["ok"]
    native.start()
    assert store.read().mode == "native" and store.read().installation_id == record.installation_id
    assert snapshots == [{"session": "persisted", "revision": 1}] * 3
    assert not docker.status()["services"]["web"]["running"]


def test_conditional_mode_write_rejects_concurrent_change(tmp_path):
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    expected = store.write("native")
    changed = RuntimeModeStore(home).write("docker")
    with pytest.raises(RuntimeModeError, match="runtime_mode_changed"):
        store.write("native", expected=expected)
    assert store.read() == changed


@pytest.fixture
def native_stop_switch(tmp_path, monkeypatch):
    """Isolate bridge reports; exercise real Native public stop and socket bind checks."""
    from research_workbench_entrypoint import bootstrap

    store = RuntimeModeStore(tmp_path / "home")
    before = store.write("native")
    native = bootstrap.NativeRuntime(tmp_path, store.home, ports=(0, 0))
    state = {"running": True, "ok": True, "stop_ok": True, "stops": 0, "after_stop": None}

    def probe(operation):
        if operation == "stop":
            state["stops"] += 1
            if not state["stop_ok"]:
                return bootstrap.result("runtime_stop_failed", mode="native")
            state["running"] = False
            if state["after_stop"]:
                state["after_stop"]()
        return bootstrap.result(
            *(() if state["ok"] else ("runtime_ownership_unknown",)),
            mode="native",
            services={role: {"running": state["running"]} for role in ("web", "runtime")},
        )

    monkeypatch.setattr(native, "_probe", probe)
    docker = SimpleNamespace(
        preflight=lambda: bootstrap.result(mode="docker"),
        status=lambda: bootstrap.result(
            mode="docker", services={role: {"running": False} for role in ("web", "runtime")}
        ),
    )
    return bootstrap, store, before, native, docker, state


def test_native_stop_switch_waits_for_real_bound_socket_release(native_stop_switch, caplog):
    bootstrap, store, _, native, docker, state = native_stop_switch
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))  # Bound, deliberately not listening.
        native.ports = (bound.getsockname()[1], 0)
        release = threading.Event()
        worker = threading.Thread(target=lambda: (release.wait(0.15), bound.close()))
        state["after_stop"] = worker.start
        with caplog.at_level(logging.INFO, logger=bootstrap.__name__):
            try:
                report = bootstrap.switch_runtime(
                    store, "docker", docker, native, stop_current=True, wait_timeout=1
                )
                assert report["ok"] and bound.fileno() == -1
            finally:
                release.set()
                worker.join(timeout=2)
    assert store.read().mode == "docker"
    messages = [record.getMessage() for record in caplog.records]
    assert "runtime_switch phase=native_port_wait code=begin" in messages
    assert "runtime_switch phase=native_port_wait code=released" in messages


def test_native_stop_switch_bound_timeout_keeps_mode(native_stop_switch, caplog):
    bootstrap, store, before, native, docker, state = native_stop_switch
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        native.ports = (bound.getsockname()[1], 0)
        report = bootstrap.switch_runtime(
            store, "docker", docker, native, stop_current=True, wait_timeout=0.02
        )
        assert not report["ok"] and report["issues"] == ["runtime_stop_failed"]
        assert bound.fileno() != -1
    assert store.read() == before and state["stops"] == 1
    assert "runtime_switch phase=native_port_wait code=timeout" in caplog.messages


@pytest.mark.parametrize("budget", [-1, True, False, float("nan"), float("inf"), "1", 46, 10**1000])
def test_native_stop_switch_rejects_invalid_budget_before_stop(native_stop_switch, budget):
    bootstrap, store, before, native, docker, state = native_stop_switch
    report = bootstrap.switch_runtime(
        store, "docker", docker, native, stop_current=True, wait_timeout=budget
    )
    assert not report["ok"] and state["stops"] == 0
    assert store.read() == before


@pytest.mark.parametrize("case", ["failed_stop", "unknown", "unauthorized", "stopped"])
def test_native_stop_switch_no_wait_without_successful_owned_stop(
    native_stop_switch, monkeypatch, case
):
    bootstrap, store, before, native, docker, state = native_stop_switch
    state["stop_ok"] = case != "failed_stop"
    state["ok"] = case != "unknown"
    state["running"] = case != "stopped"
    monkeypatch.setattr(bootstrap, "port_busy", lambda _port: pytest.fail("unexpected wait"))
    report = bootstrap.switch_runtime(
        store, "docker", docker, native, stop_current=case != "unauthorized"
    )
    assert report["ok"] == (case == "stopped")
    if case != "stopped":
        assert store.read() == before
    assert state["stops"] == (1 if case == "failed_stop" else 0)


def test_native_stop_switch_rechecks_mode_after_wait(native_stop_switch):
    bootstrap, store, _, native, docker, state = native_stop_switch
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        native.ports = (bound.getsockname()[1], 0)

        def concurrent_change():
            store.write("docker")
            bound.close()

        release = threading.Event()
        worker = threading.Thread(target=lambda: (release.wait(0.15), concurrent_change()))
        state["after_stop"] = worker.start
        try:
            report = bootstrap.switch_runtime(store, "docker", docker, native, stop_current=True)
        finally:
            release.set()
            worker.join(timeout=2)
    assert report["issues"] == ["runtime_mode_changed"]


def test_native_stop_switch_wait_uses_pre_stop_ports_only(native_stop_switch, monkeypatch):
    bootstrap, store, _, native, docker, state = native_stop_switch
    native.ports = (18088, 13081)
    state["after_stop"] = lambda: setattr(native, "ports", (8088, 3081))
    checked = []
    monkeypatch.setattr(bootstrap, "port_busy", lambda port: (checked.append(port), False)[1])
    assert bootstrap.switch_runtime(store, "docker", docker, native, stop_current=True)["ok"]
    assert checked == [18088, 13081]


def test_native_stop_switch_rejects_numeric_subclass(native_stop_switch):
    bootstrap, store, before, native, docker, state = native_stop_switch

    class Budget(float):
        pass

    report = bootstrap.switch_runtime(
        store, "docker", docker, native, stop_current=True, wait_timeout=Budget(1)
    )
    assert report["issues"] == ["runtime_stop_failed"]
    assert state["stops"] == 0 and store.read() == before


@pytest.mark.parametrize("budget", [0, 0.0, 45, 45.0])
def test_native_stop_switch_accepts_bounded_numeric_budget(native_stop_switch, budget):
    bootstrap, store, _, native, docker, state = native_stop_switch
    assert bootstrap.switch_runtime(
        store, "docker", docker, native, stop_current=True, wait_timeout=budget
    )["ok"]
    assert state["stops"] == 1


def test_native_stop_switch_default_budget_is_45_seconds():
    import inspect

    from research_workbench_entrypoint.bootstrap import switch_runtime

    assert inspect.signature(switch_runtime).parameters["wait_timeout"].default == 45


def test_native_stop_switch_runtime_restart_during_wait_is_rejected(native_stop_switch):
    bootstrap, store, before, native, docker, state = native_stop_switch
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        native.ports = (bound.getsockname()[1], 0)

        def restart():
            state["running"] = True
            bound.close()

        release = threading.Event()
        worker = threading.Thread(target=lambda: (release.wait(0.15), restart()))
        state["after_stop"] = worker.start
        try:
            report = bootstrap.switch_runtime(store, "docker", docker, native, stop_current=True)
        finally:
            release.set()
            worker.join(timeout=2)
    assert report["issues"] == ["runtime_stop_failed"] and store.read() == before


@pytest.mark.parametrize("mode", ["native", "docker"])
@pytest.mark.parametrize(
    "failure,issues,reason,issue",
    [
        ("report", ["runtime_ownership_unknown"], "report_not_ok", "runtime_ownership_unknown"),
        ("report", ["native_probe_failed"], "report_not_ok", "native_probe_failed"),
        ("report", ["SECRET=/private/token?password=hunter2"], "report_not_ok", "unknown"),
        ("report", [{"secret": "hunter2"}], "report_not_ok", "unknown"),
        ("report", [], "report_not_ok", "unknown"),
        ("running", [], "still_running", "none"),
    ],
)
def test_switch_finalize_logs_only_controlled_failure_fields(
    tmp_path, caplog, mode, failure, issues, reason, issue
):
    from research_workbench_entrypoint import bootstrap

    store = RuntimeModeStore(tmp_path / "home")
    before = store.write("native")

    class Controller:
        def __init__(self, name):
            self.name = name
            self.calls = 0

        def preflight(self):
            return {"ok": True}

        def status(self):
            self.calls += 1
            failing = self.name == mode and self.calls == 2
            if failing and failure == "report":
                # Missing services must remain short-circuited by not-ok.
                return {"ok": False, "issues": issues, "detail": "SECRET=hunter2"}
            return {
                "ok": True,
                "services": {
                    role: {"running": failing and failure == "running"}
                    for role in ("web", "runtime")
                },
            }

    report = bootstrap.switch_runtime(store, "docker", Controller("docker"), Controller("native"))
    assert report == {"schema_version": 1, "ok": False, "issues": ["runtime_stop_failed"]}
    assert store.read() == before
    messages = [
        record.getMessage() for record in caplog.records if record.name == bootstrap.__name__
    ]
    assert f"runtime_switch phase=finalize mode={mode} reason={reason} issue={issue}" in messages
    assert all("hunter2" not in message and "SECRET" not in message for message in messages)


@pytest.mark.parametrize(
    "raw,code",
    [
        (b"{", "runtime_mode_json"),
        (b"\xff", "runtime_mode_encoding"),
        (b" " * (16 * 1024 + 1), "runtime_mode_too_large"),
        (b'{"schema_version":1,"schema_version":1}', "runtime_mode_json"),
        (b'{"schema_version":NaN}', "runtime_mode_json"),
        (b"[" * 2000, "runtime_mode_json"),
    ],
)
def test_rejects_invalid_or_unbounded_input(tmp_path: Path, raw: bytes, code: str) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    path.write_bytes(raw)

    with pytest.raises(RuntimeModeError, match=f"^{code}$") as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == code


@pytest.mark.parametrize("change", ["extra", "missing", "not_object"])
def test_rejects_inexact_schema(tmp_path: Path, change: str) -> None:
    home = tmp_path / "home"
    payload: object = _payload()
    if change == "extra":
        assert isinstance(payload, dict)
        payload["unexpected"] = True
    elif change == "missing":
        assert isinstance(payload, dict)
        payload.pop("updated_at")
    else:
        payload = []
    _write_payload(home, payload)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_keys$"):
        RuntimeModeStore(home).read()


@pytest.mark.parametrize(
    "key,value,code",
    [
        ("schema_version", True, "runtime_mode_type"),
        ("schema_version", 2, "runtime_mode_value"),
        ("mode", 1, "runtime_mode_type"),
        ("mode", "podman", "runtime_mode_value"),
        ("installation_id", 1, "runtime_mode_type"),
        ("installation_id", "A" * 32, "runtime_mode_value"),
        ("installation_id", "a" * 31, "runtime_mode_value"),
        ("updated_at", None, "runtime_mode_type"),
        ("updated_at", "not-a-time", "runtime_mode_value"),
        ("updated_at", "2026-99-99T01:02:03.456789Z", "runtime_mode_value"),
    ],
)
def test_rejects_invalid_field(tmp_path: Path, key: str, value: object, code: str) -> None:
    home = tmp_path / "home"
    payload = _payload()
    payload[key] = value
    _write_payload(home, payload)

    with pytest.raises(RuntimeModeError, match=f"^{code}$") as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == code


@pytest.mark.parametrize("value", ["podman", "Native", "", None, 1, True])
def test_write_rejects_unknown_mode(tmp_path: Path, value: object) -> None:
    home = tmp_path / "home"
    home.mkdir()

    with pytest.raises(RuntimeModeError, match="^runtime_mode_value$"):
        RuntimeModeStore(home).write(value)  # type: ignore[arg-type]

    assert not _path(home).exists()


def test_store_rejects_changed_installation_id(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    store = RuntimeModeStore(home)
    record = store.write("native")
    replacement_id = "b" * 32 if record.installation_id != "b" * 32 else "c" * 32
    _write_payload(home, _payload(installation_id=replacement_id))

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        store.read()


@pytest.mark.parametrize("alias", ["file_symlink", "parent_symlink", "hardlink", "directory"])
def test_rejects_aliases_and_non_regular_files(tmp_path: Path, alias: str) -> None:
    real_home = tmp_path / "real-home"
    source = _write_payload(real_home, _payload())
    home = tmp_path / "home"
    if alias == "file_symlink":
        home.mkdir()
        (home / "install").mkdir()
        _path(home).symlink_to(source)
    elif alias == "parent_symlink":
        home.symlink_to(real_home, target_is_directory=True)
    elif alias == "hardlink":
        home.mkdir()
        (home / "install").mkdir()
        os.link(source, _path(home))
    else:
        home.mkdir()
        _path(home).mkdir(parents=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


def test_write_rejects_symlinked_install_parent(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    real_install = tmp_path / "real-install"
    real_install.mkdir()
    (home / "install").symlink_to(real_install, target_is_directory=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).write("docker")

    assert not (real_install / "runtime.json").exists()


def test_missing_record_does_not_hide_symlinked_parent(tmp_path: Path) -> None:
    real_home = tmp_path / "real-home"
    real_home.mkdir()
    home = tmp_path / "home"
    home.symlink_to(real_home, target_is_directory=True)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX permission contract")
@pytest.mark.parametrize("target,mode", [("directory", 0o755), ("file", 0o644)])
def test_read_rejects_non_private_storage(tmp_path: Path, target: str, mode: int) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    (path.parent if target == "directory" else path).chmod(mode)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
@pytest.mark.parametrize("target", ["directory", "file"])
def test_read_rejects_other_uid_path_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    selected = path.parent if target == "directory" else path
    original = Path.lstat

    def lstat(candidate: Path):
        identity = original(candidate)
        if candidate == selected:
            return _with_uid(identity, os.getuid() + 1)
        return identity

    monkeypatch.setattr(Path, "lstat", lstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX ownership contract")
@pytest.mark.parametrize("target", ["directory", "file"])
def test_read_rejects_other_uid_open_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    selected = path.parent if target == "directory" else path
    selected_inode = selected.stat().st_ino
    original = os.fstat

    def fstat(descriptor: int):
        identity = original(descriptor)
        if identity.st_ino == selected_inode:
            return _with_uid(identity, os.getuid() + 1)
        return identity

    monkeypatch.setattr(os, "fstat", fstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


@pytest.mark.skipif(os.name != "posix", reason="POSIX retained descriptor contract")
def test_private_directory_chmod_uses_retained_descriptor_during_swap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    install = home / "install"
    install.mkdir()
    install.chmod(0o755)
    outside = tmp_path / "outside"
    outside.mkdir()
    outside.chmod(0o755)
    moved = home / "moved-install"
    install_inode = install.stat().st_ino
    original = os.fchmod
    attacked: list[bool] = []

    def fchmod(descriptor: int, mode: int):
        identity = os.fstat(descriptor)
        if identity.st_ino == install_inode and not attacked:
            attacked.append(True)
            install.rename(moved)
            install.symlink_to(outside, target_is_directory=True)
            try:
                return original(descriptor, mode)
            finally:
                install.unlink()
                moved.rename(install)
        return original(descriptor, mode)

    monkeypatch.setattr(os, "fchmod", fchmod)

    record = RuntimeModeStore(home).write("docker")

    assert record.mode == "docker"
    assert attacked == [True]
    assert stat.S_IMODE(install.stat().st_mode) == 0o700
    assert stat.S_IMODE(outside.stat().st_mode) == 0o755


def test_rejects_windows_reparse_attribute(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    original = Path.lstat

    def lstat(candidate: Path):
        identity = original(candidate)
        if candidate == path:
            return SimpleNamespace(
                **{
                    name: getattr(identity, name)
                    for name in (
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_dev",
                        "st_ino",
                        "st_mtime_ns",
                        "st_ctime_ns",
                    )
                },
                st_file_attributes=0x400,
            )
        return identity

    monkeypatch.setattr(Path, "lstat", lstat)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_unsafe_path$"):
        RuntimeModeStore(home).read()


def test_simulated_windows_parent_handles_reject_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    original = Path.lstat
    opened: list[int] = []
    closed: list[int] = []
    replaced = False

    def create_file(_path, access, sharing, security, disposition, flags, template):
        assert (access, sharing, security, disposition, flags, template) == (
            0x80,
            1,
            0,
            3,
            0x02200000,
            0,
        )
        handle = len(opened) + 1
        opened.append(handle)
        return handle

    def close_handle(handle):
        closed.append(handle)

    def lstat(candidate: Path):
        identity = original(candidate)
        if replaced and candidate == path.parent:
            return SimpleNamespace(
                **{
                    name: getattr(identity, name)
                    for name in (
                        "st_mode",
                        "st_nlink",
                        "st_size",
                        "st_dev",
                        "st_ino",
                        "st_mtime_ns",
                    )
                },
                st_file_attributes=0,
                st_ctime_ns=identity.st_ctime_ns + 1,
            )
        return identity

    monkeypatch.setitem(
        sys.modules,
        "_winapi",
        SimpleNamespace(CreateFile=create_file, CloseHandle=close_handle),
    )
    monkeypatch.setattr(Path, "lstat", lstat)

    with (
        pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"),
        runtime_mode._pin_windows_parents(path),
    ):
        replaced = True

    assert len(opened) == len(path.parents)
    assert closed == list(reversed(opened))


def test_public_windows_read_write_does_not_treat_mode_bits_as_acl(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    path.parent.chmod(0o755)
    path.chmod(0o644)
    store = RuntimeModeStore(home)
    fresh_store = RuntimeModeStore(home)
    opened: list[int] = []
    closed: list[int] = []
    lock_descriptors = {}
    lock_operations = []

    def create_file(_path, access, sharing, security, disposition, flags, template):
        if access == 0xC0000000:
            assert (sharing, security, disposition, flags, template) == (3, 0, 4, 0x00200000, 0)
            handle = len(opened) + 1
            opened.append(handle)
            lock_descriptors[handle] = os.open(str(_path), os.O_RDWR | os.O_CREAT, 0o600)
            return handle
        assert (access, sharing, security, disposition, flags, template) == (
            0x80,
            1,
            0,
            3,
            0x02200000,
            0,
        )
        handle = len(opened) + 1
        opened.append(handle)
        return handle

    def close_handle(handle):
        closed.append(handle)

    def transfer_handle(handle, flags):
        closed.append(handle)  # The returned fd now owns and closes this handle.
        return lock_descriptors.pop(handle)

    monkeypatch.setitem(
        sys.modules,
        "_winapi",
        SimpleNamespace(CreateFile=create_file, CloseHandle=close_handle),
    )
    monkeypatch.setitem(
        sys.modules,
        "msvcrt",
        SimpleNamespace(
            open_osfhandle=transfer_handle,
            LK_NBLCK=1,
            LK_UNLCK=0,
            locking=lambda fd, operation, size: lock_operations.append((operation, size)),
        ),
    )
    monkeypatch.setattr(runtime_mode.os, "name", "nt")
    monkeypatch.setattr(runtime_mode.os, "chmod", lambda *_args, **_kwargs: None)

    before = store.read()
    after = store.write("docker")

    assert before.mode == "native"
    assert after.mode == "docker"
    assert after.installation_id == before.installation_id
    assert fresh_store.read() == after
    assert opened
    assert sorted(closed) == sorted(opened)
    assert lock_operations == [(1, 1), (0, 1)]


@pytest.mark.skipif(os.name != "posix", reason="Exercises POSIX retained directory descriptors")
def test_rejects_parent_replacement_race(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = tmp_path / "home"
    path = _write_payload(home, _payload())
    install = path.parent
    moved = home / "moved-install"
    original = os.open
    attacked: list[bool] = []

    def swap_parent(candidate, flags, *args, **kwargs):
        if Path(candidate).name != path.name:
            return original(candidate, flags, *args, **kwargs)
        attacked.append(True)
        install.rename(moved)
        install.symlink_to(moved, target_is_directory=True)
        try:
            return original(candidate, flags, *args, **kwargs)
        finally:
            install.unlink()
            moved.rename(install)

    monkeypatch.setattr(os, "open", swap_parent)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        RuntimeModeStore(home).read()
    assert attacked == [True]


@pytest.mark.skipif(os.name != "posix", reason="Exercises POSIX atomic replacement")
def test_rejects_unsafe_destination_replacement_race(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    store = RuntimeModeStore(home)
    first = store.write("native")
    original = os.replace

    def replace_then_attack(source, destination, *args, **kwargs):
        original(source, destination, *args, **kwargs)
        destination_fd = kwargs["dst_dir_fd"]
        attacked = json.dumps(
            _payload(
                mode="docker",
                installation_id=("b" * 32 if first.installation_id != "b" * 32 else "c" * 32),
            )
        ).encode("utf-8")
        descriptor = os.open(destination, os.O_WRONLY | os.O_TRUNC, dir_fd=destination_fd)
        try:
            os.write(descriptor, attacked)
        finally:
            os.close(descriptor)

    monkeypatch.setattr(os, "replace", replace_then_attack)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_changed$"):
        store.write("docker")


def test_failed_atomic_replace_cleans_temporary_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()

    def fail_replace(*_args, **_kwargs):
        raise OSError("private filesystem detail")

    monkeypatch.setattr(os, "replace", fail_replace)

    with pytest.raises(RuntimeModeError, match="^runtime_mode_io$") as caught:
        RuntimeModeStore(home).write("docker")

    assert [item.name for item in (home / "install").iterdir()] == ["runtime.lock"]
    assert stat.S_IMODE((home / "install/runtime.lock").stat().st_mode) == 0o600
    assert "private filesystem detail" not in "".join(traceback.format_exception(caught.value))


def test_failures_log_only_operation_and_code(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    home = tmp_path / "sensitive-home"
    _write_payload(home, {"secret-content": "do-not-log"})

    with caplog.at_level(logging.WARNING), pytest.raises(RuntimeModeError) as caught:
        RuntimeModeStore(home).read()

    assert caught.value.code == "runtime_mode_keys"
    assert "operation=read" in caplog.text
    assert "code=runtime_mode_keys" in caplog.text
    assert "sensitive-home" not in caplog.text
    assert "secret-content" not in caplog.text


def test_module_import_is_stdlib_only() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-I",
            "-c",
            (
                "import sys; sys.path.insert(0, '.'); "
                "import research_workbench_entrypoint.runtime_mode; "
                "assert 'click' not in sys.modules; "
                "assert 'fastapi' not in sys.modules; "
                "assert 'structlog' not in sys.modules"
            ),
        ],
        cwd=Path(__file__).resolve().parents[2],
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr


def _interleaved_writer(home, expected, entered, release, started, finished, results, hold):
    original = os.replace
    original_load = RuntimeModeStore._load
    replaced = False

    def replace(*args, **kwargs):
        nonlocal replaced
        if hold == "replace":
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test release timeout")
        value = original(*args, **kwargs)
        replaced = True
        return value

    def load(store, *args, **kwargs):
        if hold == "readback" and replaced:
            entered.set()
            if not release.wait(10):
                raise TimeoutError("test release timeout")
        return original_load(store, *args, **kwargs)

    os.replace = replace
    RuntimeModeStore._load = load
    started.set()
    try:
        record = RuntimeModeStore(Path(home)).write("docker", expected=expected)
        results.put(("ok", record.installation_id))
    except RuntimeModeError as error:
        results.put((error.code, None))
    finally:
        finished.set()


@pytest.mark.parametrize("existing", [False, True])
def test_cross_process_writes_are_serialized_through_readback(tmp_path, existing):
    home = tmp_path / "home"
    initial = RuntimeModeStore(home).write("native") if existing else None
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    started = [context.Event(), context.Event()]
    finished = [context.Event(), context.Event()]
    results = context.Queue()
    children = [
        context.Process(
            target=_interleaved_writer,
            args=(
                str(home),
                initial,
                entered,
                release,
                started[index],
                finished[index],
                results,
                "replace" if index == 0 else "none",
            ),
        )
        for index in range(2)
    ]
    try:
        children[0].start()
        assert entered.wait(10)
        children[1].start()
        assert started[1].wait(10)
        assert not finished[1].wait(0.3), "second writer bypassed the critical section"
    finally:
        release.set()
        for child in children:
            if child.pid is not None:
                child.join(10)
                if child.is_alive():
                    child.terminate()
                    child.join(5)
    assert all(child.exitcode == 0 for child in children)
    values = [results.get(timeout=2), results.get(timeout=2)]
    if existing:
        assert sorted(value[0] for value in values) == ["ok", "runtime_mode_changed"]
    else:
        assert [value[0] for value in values] == ["ok", "ok"]
        assert values[0][1] == values[1][1] == RuntimeModeStore(home).read().installation_id


def test_cross_process_lock_covers_persisted_readback(tmp_path):
    home = tmp_path / "home"
    initial = RuntimeModeStore(home).write("native")
    context = multiprocessing.get_context("spawn")
    entered, release = context.Event(), context.Event()
    started = [context.Event(), context.Event()]
    finished = [context.Event(), context.Event()]
    results = context.Queue()
    children = [
        context.Process(
            target=_interleaved_writer,
            args=(
                str(home),
                initial,
                entered,
                release,
                started[index],
                finished[index],
                results,
                "readback" if index == 0 else "none",
            ),
        )
        for index in range(2)
    ]
    try:
        children[0].start()
        assert entered.wait(10)
        children[1].start()
        assert started[1].wait(10)
        assert not finished[1].wait(0.3), "second writer entered before readback finished"
    finally:
        release.set()
        for child in children:
            if child.pid is not None:
                child.join(10)
                if child.is_alive():
                    child.terminate()
                    child.join(5)
    assert all(child.exitcode == 0 for child in children)
    assert sorted(results.get(timeout=2)[0] for _ in children) == ["ok", "runtime_mode_changed"]


def test_higher_ancestor_rename_restore_cannot_redirect_record(tmp_path, monkeypatch):
    home = tmp_path / "home"
    expected = RuntimeModeStore(home).write("native")
    decoy = tmp_path / "decoy"
    foreign = RuntimeModeStore(decoy).write("docker")
    moved = tmp_path / "moved"
    original = os.open
    attacked = []

    def swap(candidate, flags, *args, **kwargs):
        if Path(candidate).name != "runtime.json":
            return original(candidate, flags, *args, **kwargs)
        attacked.append(True)
        home.rename(moved)
        decoy.rename(home)
        try:
            return original(candidate, flags, *args, **kwargs)
        finally:
            home.rename(decoy)
            moved.rename(home)

    monkeypatch.setattr(os, "open", swap)
    assert RuntimeModeStore(home).read() == expected
    assert expected.installation_id != foreign.installation_id
    assert attacked == [True]


@pytest.mark.parametrize("kind", ["symlink", "hardlink", "public"])
def test_write_lock_rejects_unsafe_leaf(tmp_path, kind):
    home = tmp_path / "home"
    record = RuntimeModeStore(home).write("native")
    lock = home / "install/runtime.lock"
    lock.unlink(missing_ok=True)
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"x")
    foreign.chmod(0o600)
    if kind == "symlink":
        lock.symlink_to(foreign)
    elif kind == "hardlink":
        os.link(foreign, lock)
    else:
        lock.write_bytes(b"x")
        lock.chmod(0o644)
    with pytest.raises(RuntimeModeError):
        RuntimeModeStore(home).write("docker")
    assert RuntimeModeStore(home).read() == record
