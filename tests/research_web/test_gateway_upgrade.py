"""Deployment fences must win races without replacing native ownership."""

import os
import sqlite3
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident.gateway_fence import BirthFence, FenceBlocked


@pytest.fixture
def server(tmp_path):
    root = tmp_path / "server"
    root.mkdir(mode=0o700)
    (root / "users").mkdir(mode=0o700)
    (root / "run").mkdir(mode=0o700)
    primary, user = str(uuid4()), str(uuid4())
    db = sqlite3.connect(root / "accounts.sqlite3")
    db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
    db.executemany("INSERT INTO accounts VALUES (?)", [(primary,), (user,)])
    db.commit()
    db.close()
    (root / "accounts.sqlite3").chmod(0o600)
    return root, primary, user


def test_fence_blocks_database_writers_and_native_birth_after_exists_check(server):
    root, primary, user = server
    owner = root / "users" / user / "state/owner.json"
    assert not owner.exists()  # native may have passed its earlier exists check
    with BirthFence(root, primary):
        with pytest.raises(FileExistsError):
            os.open(owner, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        db = sqlite3.connect(root / "accounts.sqlite3", timeout=0)
        try:
            with pytest.raises(sqlite3.OperationalError, match="locked"):
                db.execute("BEGIN IMMEDIATE")
        finally:
            db.close()
    assert not owner.exists()


def test_native_winner_is_preserved_and_never_disposed(server):
    root, primary, user = server
    owner = root / "users" / user / "state/owner.json"
    owner.parent.mkdir(parents=True, mode=0o700)
    owner.parent.parent.chmod(0o700)
    owner.write_bytes(b"native-owner-bytes")
    owner.chmod(0o600)
    with pytest.raises(FenceBlocked, match="private_pool_not_empty"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert owner.read_bytes() == b"native-owner-bytes"


@pytest.mark.parametrize("suffix", ["-journal", "-wal", "-shm"])
def test_unknown_sqlite_sidecar_is_not_opened_or_recovered(server, suffix):
    root, primary, _ = server
    sidecar = root / ("accounts.sqlite3" + suffix)
    sidecar.write_bytes(b"unknown")
    with pytest.raises(FenceBlocked, match="database_sidecar_unknown"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert sidecar.read_bytes() == b"unknown"


def test_crash_after_publish_can_remove_only_its_own_reservation(server):
    root, primary, user = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    fence.db.rollback()
    fence.db.close()
    fence.db = None
    BirthFence.recover(root)
    assert not (root / "users" / user / "state/owner.json").exists()


def test_recovery_never_removes_a_replaced_slot(server):
    root, primary, user = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    owner = root / "users" / user / "state/owner.json"
    (owner / "reservation").unlink()
    owner.rmdir()
    owner.write_bytes(b"foreign")
    owner.chmod(0o600)
    fence.db.rollback()
    fence.db.close()
    fence.db = None
    with pytest.raises(FenceBlocked, match="reservation_changed"):
        BirthFence.recover(root)
    assert owner.read_bytes() == b"foreign"


def test_unknown_user_directory_is_deferred(server):
    root, primary, _ = server
    (root / "users" / str(uuid4())).mkdir(mode=0o700)
    with pytest.raises(FenceBlocked, match="unknown_user_directory"), BirthFence(root, primary):
        pytest.fail("must defer")


def test_another_fences_journal_is_never_recovered_on_enter_failure(server):
    root, primary, user = server
    with BirthFence(root, primary):
        journal = (root / "run/birth-fence.json").read_bytes()
        with (
            pytest.raises(FenceBlocked, match="birth_fence_recovery_required"),
            BirthFence(root, primary),
        ):
            pytest.fail("must defer")
        assert (root / "run/birth-fence.json").read_bytes() == journal
        assert (root / "users" / user / "state/owner.json").is_dir()


def test_native_wins_publication_race_without_being_removed(server, monkeypatch):
    from research_workbench_entrypoint.resident import gateway_fence as module

    root, primary, user = server
    original = module.exclusive_rename
    owner = root / "users" / user / "state/owner.json"

    def race(source, destination):
        if destination == owner:
            owner.write_bytes(b"native winner")
            owner.chmod(0o600)
        original(source, destination)

    monkeypatch.setattr(module, "exclusive_rename", race)
    with pytest.raises(FenceBlocked, match="private_pool_not_empty"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert owner.read_bytes() == b"native winner"


@pytest.mark.parametrize("name", ["auth.json", "gateway.key", "unknown.json"])
def test_no_owner_with_unknown_control_is_not_empty(server, name):
    root, primary, user = server
    state = root / "users" / user / "state"
    state.mkdir(parents=True, mode=0o700)
    state.parent.chmod(0o700)
    (state / name).write_bytes(b"private control")
    with pytest.raises(FenceBlocked, match="private_control_unknown"), BirthFence(root, primary):
        pytest.fail("must defer")
    assert (state / name).read_bytes() == b"private control"


def test_release_crash_after_marker_unlink_is_recoverable(server, monkeypatch):
    root, primary, _ = server
    fence = BirthFence(root, primary)
    fence.__enter__()
    original = type(root).rmdir
    failed = False

    def interrupted(path):
        nonlocal failed
        if path.name.startswith("birth-slot-") and not failed:
            failed = True
            raise OSError("simulated crash")
        return original(path)

    monkeypatch.setattr(type(root), "rmdir", interrupted)
    with pytest.raises(OSError, match="simulated"):
        fence.__exit__()
    BirthFence.recover(root)
    assert not (root / "run/birth-fence.json").exists()


def test_graceful_timeout_never_escalates_signal(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    command = "python -m app.research_web.multiuser.resident --root /owned"
    signature = "Tue Oct 20 12:00:00 2026 " + command
    signals = []
    monkeypatch.setattr(g, "process", lambda pid: signature)
    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "listener_pids", lambda: {123})
    monkeypatch.setattr(g, "no_children", lambda pid: None)
    monkeypatch.setattr(g.os, "kill", lambda pid, sig: signals.append(sig))
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    with pytest.raises(MaintenanceBusy, match="gateway_draining"):
        g.graceful_drain(123, signature, command, timeout=0)
    assert signals == [g.signal.SIGTERM]


def test_changed_listener_never_receives_signal(monkeypatch):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    command = "python -m app.research_web.multiuser.resident --root /owned"
    signature = "Tue Oct 20 12:00:00 2026 " + command
    monkeypatch.setattr(g, "process", lambda pid: signature)
    monkeypatch.setattr(g, "verify_signal_contract", lambda: None)
    monkeypatch.setattr(g, "listener_pids", lambda: {999})
    monkeypatch.setattr(g.os, "kill", lambda *_: pytest.fail("unknown PID must not be signalled"))
    with pytest.raises(g.UpdateBlocked, match="gateway_listener_unknown"):
        g.graceful_drain(123, signature, command)


@pytest.mark.parametrize(
    "failure", [None, "bootstrap", "wait_health", "verify_primary", "preserved"]
)
def test_candidate_success_and_every_post_switch_failure_enter_rollback(
    tmp_path, monkeypatch, failure
):
    from research_workbench_entrypoint.resident import gateway_upgrade as g

    home = tmp_path
    (home / "server/run").mkdir(parents=True, mode=0o700)
    events = []
    state = {
        "project": str(tmp_path / "project"),
        "target": "b" * 40,
        "previous": "a" * 40,
        "primary": g.PRODUCT,
        "updated": {"revision": "b" * 40},
        "before": {},
        "phase": "stopped",
    }
    monkeypatch.setattr(g, "git", lambda *_: events.append("switch"))
    monkeypatch.setattr(g, "write_config", lambda *_: events.append("config"))
    for name in ("bootstrap", "wait_health", "verify_primary", "preserved"):

        def step(*_, _name=name, **__):
            events.append(_name)
            if failure == _name:
                raise g.UpdateBlocked("injected_failure")

        monkeypatch.setattr(g, name, step)
    monkeypatch.setattr(
        g, "recover_locked", lambda *_: events.append("rollback") or {"status": "rolled_back"}
    )
    result = g.activate_gateway(home, state, tmp_path / "job.plist")
    assert result["status"] == ("rolled_back" if failure else "deployed")
    if failure:
        assert events[-1] == "rollback"
    else:
        assert not (home / "server/run/gateway-upgrade.json").exists()
        assert events == [
            "switch",
            "config",
            "bootstrap",
            "wait_health",
            "verify_primary",
            "preserved",
        ]


def test_recovery_installer_reuses_identical_qualified_artifact(tmp_path, monkeypatch):
    import json
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    home, source = tmp_path / "home", tmp_path / "source"
    (home / "server/run").mkdir(parents=True, mode=0o700)
    (home / "resident").mkdir(mode=0o700)
    (home / "resident/config.json").write_text(json.dumps({"project": str(source)}))
    (home / "Library/LaunchAgents").mkdir(parents=True)
    package = source / "research_workbench_entrypoint/resident"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    (package / "gateway_upgrade.py").write_text("# frozen test artifact")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(g, "run", lambda *_args, **_kwargs: "")
    first = g.install_recovery(home, source)
    assert g.install_recovery(home, source) == first
    (package / "gateway_upgrade.py").write_text("# changed")
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_artifact_changed"):
        g.install_recovery(home, source)


@pytest.fixture
def recovery(server, monkeypatch):
    import json
    from pathlib import Path

    from research_workbench_entrypoint.resident import gateway_upgrade as g

    root, primary, _user = server
    home = root.parent
    project = home / "project"
    project.mkdir(mode=0o700)
    agents = home / "Library/LaunchAgents"
    agents.mkdir(parents=True)
    plist = agents / (g.LABEL + ".plist")
    plist.write_bytes(b"test job identity")
    artifact = root / "run/gateway-recovery.pyz"
    artifact.write_bytes(b"frozen test operator")
    state = {
        "version": 1,
        "phase": "starting",
        "primary": g.PRODUCT,
        "previous": "a" * 40,
        "target": "b" * 40,
        "project": str(project),
        "project_identity": [project.stat().st_dev, project.stat().st_ino],
        "old_pid": 111,
        "old_signature": "old",
        "command": "exact candidate command",
        "transaction": str(uuid4()),
        "original_config": {"revision": "b" * 40},
        "fallback": {"revision": "a" * 40, "binding": {"primary_user_id": primary}},
        "updated": {"revision": "b" * 40},
        "before": {"original": "hashes"},
        "plist_sha256": g.digest(plist),
        "recovery": {"artifact_sha256": g.digest(artifact)},
    }
    (root / "resident.json").write_text(json.dumps(state["updated"]))
    (root / "run/gateway-upgrade.json").write_text(json.dumps(state))
    events, live = [], {"job": True, "pid": 222, "sha": state["target"]}
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(g, "verify_primary", lambda *_: events.append("primary_idle"))
    monkeypatch.setattr(g, "clean", lambda _p, sha: events.append("clean:" + sha[0]))
    monkeypatch.setattr(g, "no_private_processes", lambda *_: None)
    monkeypatch.setattr(g, "process", lambda pid: None if pid == 111 else "candidate")
    monkeypatch.setattr(g, "job_state", lambda: "registered" if live["job"] else None)
    monkeypatch.setattr(g, "job_pid", lambda: live["pid"])

    def drain(*_):
        events.append("drain")
        live["pid"] = None

    monkeypatch.setattr(g, "graceful_drain", drain)

    def command(argv, **_):
        assert "bootout" in argv
        events.append("bootout")
        live["job"] = False
        return ""

    monkeypatch.setattr(g, "run", command)

    def git(_p, *args):
        if args[0] == "switch":
            events.append("restore_code")
            live["sha"] = args[-1]
        return live["sha"]

    monkeypatch.setattr(g, "git", git)
    monkeypatch.setattr(g, "preserved", lambda *_: events.append("preserved"))
    monkeypatch.setattr(g, "bootstrap", lambda *_: events.append("start_fallback"))
    monkeypatch.setattr(
        g, "wait_health", lambda config, **_: events.append("health:" + config["revision"][0])
    )
    return g, home, root, state, events, live


def test_actual_rollback_restores_matching_binding_without_touching_data(recovery):
    import json

    g, home, root, state, events, _ = recovery
    business = root / "untouched-business.txt"
    business.write_bytes(b"existing session contents")
    result = g.recover_locked(home, state)
    assert result["status"] == "rolled_back"
    assert json.loads((root / "resident.json").read_text()) == state["fallback"]
    assert business.read_bytes() == b"existing session contents"
    assert events == [
        "primary_idle",
        "clean:b",
        "drain",
        "bootout",
        "clean:b",
        "restore_code",
        "preserved",
        "start_fallback",
        "health:a",
    ]
    assert not (root / "run/gateway-upgrade.json").exists()


def test_recovery_of_inflight_legacy_drain_waits_without_stopping(recovery, monkeypatch):
    g, home, _root, state, events, _ = recovery
    state["phase"] = "draining"
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy

    signature = "Tue Oct 20 12:00:00 2026 " + state["command"]
    monkeypatch.setattr(g, "process", lambda _: signature)

    def pending(*_):
        raise MaintenanceBusy("gateway_draining")

    monkeypatch.setattr(g, "graceful_drain", pending)
    with pytest.raises(MaintenanceBusy, match="gateway_draining"):
        g.recover_locked(home, state)
    assert events == ["primary_idle", "primary_idle"]


def test_recovery_after_legacy_exit_reacquires_birth_fence(recovery, monkeypatch):
    g, home, _root, state, events, live = recovery
    state["phase"] = "draining"
    live["pid"] = None
    monkeypatch.setattr(g, "bootout_after_drain", lambda _: live.update(job=False))
    assert g.recover_locked(home, state)["status"] == "rolled_back"
    assert "restore_code" in events


def test_recovery_artifact_tamper_blocks_before_process_operation(recovery):
    g, home, root, state, events, _ = recovery
    (root / "run/gateway-recovery.pyz").write_bytes(b"changed")
    with pytest.raises(g.UpdateBlocked, match="gateway_recovery_identity_changed"):
        g.recover_locked(home, state)
    assert events == []


def test_uvicorn_repeated_sigterm_never_enables_force_exit():
    import signal

    import uvicorn
    from uvicorn.server import Server

    config = uvicorn.Config(app=None)
    server = Server(config)
    server.handle_exit(signal.SIGTERM, None)
    server.handle_exit(signal.SIGTERM, None)
    assert server.should_exit is True and server.force_exit is False
    assert config.timeout_graceful_shutdown is None


def test_preparing_crash_aborts_only_owned_slots_without_stopping(recovery):
    g, home, root, state, events, _ = recovery
    state["phase"] = "preparing"
    fence = BirthFence(
        root, state["fallback"]["binding"]["primary_user_id"], transaction=state["transaction"]
    )
    fence.__enter__()
    fence.release_database()
    assert g.recover_locked(home, state)["status"] == "aborted_before_signal"
    assert events == ["primary_idle", "clean:a"]
    assert not (root / "run/birth-fence.json").exists()


@pytest.mark.parametrize("phase", ["rolling_back", "fallback_starting"])
def test_recovery_reenters_partial_rollback_without_stopping_old_service(recovery, phase):
    g, home, _root, state, events, live = recovery
    state["phase"] = phase
    live.update(job=False, pid=None, sha=state["previous"])
    if phase == "fallback_starting":
        g.write_config(home / "server/resident.json", state["fallback"])
    assert g.recover_locked(home, state)["status"] == "rolled_back"
    assert "drain" not in events


@pytest.mark.parametrize("failure", ["signal", "bootout", "journal"])
def test_every_post_signal_failure_keeps_birth_fence(recovery, monkeypatch, failure):
    g, home, root, state, _events, live = recovery
    state["phase"] = "draining"
    signature = "Tue Oct 20 12:00:00 2026 " + state["command"]
    monkeypatch.setattr(g, "process", lambda _: signature)

    def fail(*_args, **_kwargs):
        raise g.UpdateBlocked("injected_post_signal_failure")

    if failure == "signal":
        monkeypatch.setattr(g, "graceful_drain", fail)
    elif failure == "bootout":
        monkeypatch.setattr(g, "bootout_after_drain", fail)
    else:
        monkeypatch.setattr(g, "bootout_after_drain", lambda _: live.update(job=False))
        monkeypatch.setattr(g, "atomic", fail)
    with pytest.raises(g.UpdateBlocked, match="injected_post_signal_failure"):
        g.recover_locked(home, state)
    assert (root / "run/birth-fence.json").exists()
    assert list((root / "users").glob("*/state/owner.json"))


def test_real_uvicorn_drains_slow_request_after_two_sigterms(tmp_path):
    """Native subprocess evidence; no resident port, user data or model is used."""
    import concurrent.futures
    import http.client
    import signal
    import socket
    import subprocess
    import sys
    import time

    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    started = tmp_path / "request-started"
    completed = tmp_path / "request-completed"
    script = """import asyncio,sys,uvicorn
from pathlib import Path
from fastapi import FastAPI
app=FastAPI()
@app.get("/slow")
async def slow():
    Path(sys.argv[2]).write_text("started")
    await asyncio.to_thread(__import__("time").sleep, 1.5)
    Path(sys.argv[3]).write_text("completed")
    return {"completed":True}
uvicorn.run(app,host="127.0.0.1",port=int(sys.argv[1]),log_config=None,access_log=False)
"""
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(port), str(started), str(completed)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    def request():
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            connection.request("GET", "/slow")
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    try:
        deadline = time.monotonic() + 8
        while True:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                    break
            except OSError:
                assert process.poll() is None and time.monotonic() < deadline
                time.sleep(0.02)
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            pending = executor.submit(request)
            while not started.exists():
                assert time.monotonic() < deadline
                time.sleep(0.02)
            process.send_signal(signal.SIGTERM)
            time.sleep(0.05)
            process.send_signal(signal.SIGTERM)
            time.sleep(0.1)
            assert process.poll() is None and not completed.exists()
            assert pending.result(timeout=5)[0] == 200
            assert completed.read_text() == "completed"
        process.wait(timeout=5)
    finally:
        if process.poll() is None:
            process.kill()  # Only this test-owned disposable subprocess, after failure.
            process.wait(timeout=5)
