"""The explicitly reviewed model upgrade must be fenced and reversible."""

import json
import plistlib
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
from research_workbench_entrypoint.resident.admission import MaintenanceBusy
from research_workbench_entrypoint.resident.gateway_fence import BirthFence


class Operations:
    def __init__(self, *, busy=False, fail=None):
        self.busy, self.fail = busy, fail
        self.events = []

    def idle(self):
        self.events.append("idle")
        return not self.busy

    def checkpoint(self, state, phase):
        self.events.append("journal:" + phase)
        state["phase"] = phase

    def action(self, name, state):
        self.events.append(name)
        if name == self.fail:
            raise RuntimeError("synthetic_failure")

    def finish(self, state, result):
        self.events.append("finish:" + result)
        return {"status": result, "preserved": True}


def test_running_or_unknown_never_journals_or_stops():
    ops = Operations(busy=True)
    assert upgrade.execute(ops, {})["status"] == "deferred"
    assert ops.events == ["idle"]


def test_success_persists_intent_before_every_effect():
    ops = Operations()
    assert upgrade.execute(ops, {})["status"] == "deployed"
    assert ops.events[-1] == "finish:deployed"
    for i, event in enumerate(ops.events):
        if event in upgrade.FORWARD:
            assert ops.events[i - 1] == "journal:" + event


@pytest.mark.parametrize("failed", upgrade.FORWARD)
def test_every_forward_failure_restores_both_services(failed):
    ops = Operations(fail=failed)
    assert upgrade.execute(ops, {})["status"] == "rolled_back"
    assert "restore_sources_and_wheel" in ops.events
    assert "verify_previous" in ops.events
    assert ops.events[-1] == "finish:rolled_back"


@pytest.mark.parametrize("phase", upgrade.FORWARD + upgrade.BACKWARD)
def test_interrupted_phase_always_recovers_the_previous_version(phase):
    ops = Operations()
    result = upgrade.execute(ops, {"phase": phase}, recovering=True)
    assert result["status"] == "rolled_back"
    assert not any(step in ops.events for step in upgrade.FORWARD if step != "stop_gateway")


@pytest.mark.parametrize("failed", upgrade.BACKWARD)
def test_failed_rollback_retains_recovery_not_success(failed):
    ops = Operations(fail=failed)
    assert upgrade.execute(ops, {}, recovering=True)["status"] == "recovery_required"
    assert not any(e.startswith("finish:") for e in ops.events)


def test_activity_becoming_unknown_before_rollback_keeps_fence():
    ops = Operations(busy=True)
    assert upgrade.execute(ops, {}, recovering=True)["status"] == "recovery_required"
    assert ops.events == ["idle"]


def test_busy_during_signal_drain_does_not_retry_or_force_stop():
    class BusyDrain(Operations):
        def action(self, name, state):
            super().action(name, state)
            if name == "stop_gateway":
                raise MaintenanceBusy("synthetic_drain_pending")

    ops = BusyDrain()
    assert upgrade.execute(ops, {})["status"] == "recovery_required"
    assert ops.events.count("stop_gateway") == 1
    assert "restore_sources_and_wheel" not in ops.events


def test_real_birth_fence_reservations_are_not_native_owners(tmp_path):
    server = tmp_path / "server"
    server.mkdir(mode=0o700)
    users = [str(uuid4()), str(uuid4())]
    (server / "users").mkdir(mode=0o700)
    for user in users:
        (server / "users" / user).mkdir(mode=0o700)
        (server / "users" / user / "state").mkdir(mode=0o700)
    with sqlite3.connect(server / "accounts.sqlite3") as db:
        db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
        db.executemany("INSERT INTO accounts VALUES (?)", [(x,) for x in users])
    (server / "accounts.sqlite3").chmod(0o600)
    with BirthFence(server, users[0]) as fence:
        assert upgrade.reserved_owners(server, fence.transaction) is True
        assert len(list((server / "users").glob("*/state/owner.json"))) == 2
        marker = server / "users" / users[0] / "state/owner.json/reservation"
        marker.write_text("foreign")
        assert upgrade.reserved_owners(server, fence.transaction) is False
        marker.write_text(fence.transaction)
        assert upgrade.reserved_owners(server, str(uuid4())) is False
    assert upgrade.reserved_owners(server, fence.transaction) is True


def test_real_native_owner_is_never_ignored(tmp_path):
    owner = tmp_path / "users" / str(uuid4()) / "state/owner.json"
    owner.parent.mkdir(parents=True)
    owner.write_text("{}")
    assert upgrade.reserved_owners(tmp_path, str(uuid4())) is False


def gateway_ops(tmp_path, monkeypatch):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    plist = tmp_path / "gateway.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": ["/python"]}))
    ops.server = tmp_path
    ops.state = {
        "gateway_plist": str(plist),
        "gateway_plist_sha256": upgrade.c.digest(plist),
        "gateway_project": "/gateway",
        "gateway_command": "/python -m gateway",
    }
    monkeypatch.setattr(upgrade.g, "no_private_processes", lambda _root: None)
    return ops, f"path = {plist}\nprogram = /python\nworking directory = /gateway\n"


def test_loaded_no_pid_job_is_booted_out_and_proved_retired(tmp_path, monkeypatch):
    ops, raw = gateway_ops(tmp_path, monkeypatch)
    live = {"loaded": True}
    monkeypatch.setattr(upgrade.g, "job_state", lambda: raw if live["loaded"] else None)
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: None)
    monkeypatch.setattr(upgrade.g, "listener_pids", lambda: set())
    monkeypatch.setattr(upgrade.g, "bootout_after_drain", lambda _p: live.update(loaded=False))
    ops.stop_gateway()
    assert live["loaded"] is False


def test_loaded_no_pid_unknown_job_never_receives_signal(tmp_path, monkeypatch):
    ops, raw = gateway_ops(tmp_path, monkeypatch)
    monkeypatch.setattr(upgrade.g, "job_state", lambda: raw.replace("/python", "/unknown"))
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: None)
    monkeypatch.setattr(upgrade.g, "listener_pids", lambda: set())
    monkeypatch.setattr(
        upgrade.g, "bootout_after_drain", lambda _p: pytest.fail("must not stop unknown job")
    )
    with pytest.raises(MaintenanceBusy, match="process_unknown"):
        ops.stop_gateway()


def test_apply_executor_must_come_from_the_reviewed_source(tmp_path):
    with pytest.raises(upgrade.UpdateBlocked, match="executor_unverified"):
        upgrade.validate_executor(tmp_path, "a" * 40)


def test_older_frozen_executor_cannot_consume_new_transaction(tmp_path, monkeypatch):
    old, new = tmp_path / "old.pyz", tmp_path / "new.pyz"
    monkeypatch.setattr(upgrade, "__file__", str(old) + "/resident/model_provider_upgrade.py")
    monkeypatch.setattr(upgrade.sys, "argv", [str(old)])
    state = {"recovery": {"artifact": str(new), "sha256": "a" * 64}}
    with pytest.raises(upgrade.UpdateBlocked, match="other_model_recovery_version"):
        upgrade.validate_executor(tmp_path, "a" * 40, state)


def test_gateway_intent_is_durable_before_primary_journal(tmp_path, monkeypatch):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.root = tmp_path / "resident"
    ops.server = tmp_path / "server"
    ops.fence = SimpleNamespace(retain=False)
    state = {k: {} for k in ["new_wheel", "old_wheel", "manifest", "proof"]}
    state.update(
        previous=upgrade.PREVIOUS,
        target="a" * 40,
        config={"private_origin": "https://fixture.tail.ts.net"},
    )
    events = []
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(upgrade, "verify_private_fence", lambda _origin: events.append("https503"))
    monkeypatch.setattr(upgrade.g, "write_upgrade_journal", lambda _p, _s: events.append("gateway"))
    monkeypatch.setattr(upgrade.c, "atomic", lambda _p, _s: events.append("primary"))
    ops.checkpoint(state, "prepared")
    assert events == ["gateway", "https503", "primary"]
    assert ops.fence.retain is True


def test_gateway_only_crash_retains_birth_fence_without_claiming_primary_intent(
    tmp_path, monkeypatch
):
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.root = tmp_path / "resident"
    ops.server = tmp_path / "server"
    ops.fence = SimpleNamespace(retain=False)
    state = {k: {} for k in ["new_wheel", "old_wheel", "manifest", "proof"]}
    state.update(
        previous=upgrade.PREVIOUS,
        target="a" * 40,
        config={"private_origin": "https://fixture.tail.ts.net"},
    )
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(upgrade.g, "write_upgrade_journal", lambda _p, _s: None)
    monkeypatch.setattr(
        upgrade, "verify_private_fence", lambda _origin: (_ for _ in ()).throw(SystemExit("crash"))
    )
    monkeypatch.setattr(
        upgrade.c, "atomic", lambda _p, _s: pytest.fail("primary must not be written")
    )
    with pytest.raises(SystemExit):
        ops.checkpoint(state, "prepared")
    assert ops.fence.retain is True


def test_actual_gateway_health_field_is_used(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from app.research_web.multiuser.accounts import AccountStore
    from app.research_web.multiuser.gateway import create_gateway

    class Pool:
        deployment_path = tmp_path / "deployment.json"

        async def health(self):
            return {"status": "ready", "revision": "a" * 40, "primary_last_verified": True}

        async def close(self):
            pass

    Pool.deployment_path.write_text("{}")
    app = create_gateway(AccountStore(tmp_path / "accounts"), Pool(), origin="http://localhost")
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/server/health").json()
        assert client.get("/").status_code == 503
    assert response["deployment_fenced"] is True and "resident_fenced" not in response
    ops = upgrade.Operations.__new__(upgrade.Operations)
    ops.home = tmp_path
    ops.server = tmp_path / "server"
    ops.server.mkdir()
    (ops.server / "resident.json").write_text("{}")
    ops.state = {
        "target": "a" * 40,
        "config": {"private_origin": "http://localhost", "web_port": 8088},
        "before": {},
        "model_before": {"provider": "fixture", "model": "fixture", "credential_configured": False},
    }
    monkeypatch.setattr(upgrade.g, "verify_primary", lambda *_: None)
    monkeypatch.setattr(upgrade.g, "health", lambda *_a, **_k: None)
    monkeypatch.setattr(upgrade.g, "preserved", lambda *_: None)
    monkeypatch.setattr(upgrade, "model_metadata", lambda _config: ops.state["model_before"])
    monkeypatch.setattr(
        upgrade,
        "request_json",
        lambda url: (
            {"items": [{"active": True, **ops.state["model_before"]}]}
            if url.endswith("/model-profiles")
            else response
        ),
    )
    ops.verify(False)


def test_immutable_old_controller_cannot_clear_primary_journal_under_gateway_fence(
    tmp_path, monkeypatch
):
    """Execute the actual installed controller module, not the mutable new source."""
    import contextlib
    import hashlib
    import importlib.machinery
    import importlib.util
    import urllib.error

    import app.research_web.service_manager as manager_module

    fixture = (
        Path(__file__).parents[1]
        / "fixtures/research_web/model_provider_original_controller.py.txt"
    )
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == upgrade.CONTROLLER_MODULE_SHA256
    loader = importlib.machinery.SourceFileLoader(
        "research_workbench_entrypoint.resident.original_controller_fixture", str(fixture)
    )
    spec = importlib.util.spec_from_loader(loader.name, loader)
    original = importlib.util.module_from_spec(spec)
    loader.exec_module(original)
    home = tmp_path.resolve()
    root = home / "resident"
    root.mkdir(mode=0o700)
    project = home / "project"
    for p in [root / "artifacts", home / "install", home / "server/run", project]:
        p.mkdir(parents=True, exist_ok=True, mode=0o700)
    wheel = root / "artifacts/old.whl"
    wheel.write_bytes(b"fixture")
    record = {
        "previous": upgrade.PREVIOUS,
        "target": "b" * 40,
        "manifest": {"status": "installed", "code_commit": "b" * 40},
        "new_wheel": {"path": str(wheel), "sha256": original.digest(wheel)},
        "old_wheel": {"path": str(wheel), "sha256": original.digest(wheel)},
    }
    original.atomic(root / "transaction.json", record)
    original.atomic(home / "server/run/gateway-upgrade.json", {"version": 4, "mode": upgrade.MODE})
    code = {"revision": "b" * 40}
    events = []

    class Manager:
        def __init__(self, **_kwargs):
            pass

        def _installation_start_scope(self):
            return contextlib.nullcontext(object())

        def _stop_locked(self):
            events.append("old-stop-primary")

        def _start_installed(self, *_args, **_kwargs):
            events.append("old-start-primary")

        def status(self):
            return {
                "services": {
                    "web": {"running": True, "healthy": True, "port": 8088},
                    "runtime": {"running": True, "healthy": True, "port": 3081},
                }
            }

    def git(_project, *args):
        if args[:2] == ("rev-parse", "HEAD"):
            return code["revision"]
        if args[:2] == ("switch", "--detach"):
            code["revision"] = args[2]
            return ""
        pytest.fail("unexpected frozen Git call")

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def read(self, *_):
            return b"<html>actual local primary fixture</html>"

    class Opener:
        def open(self, url, **_kwargs):
            if url.startswith("https://fixture.tail.ts.net"):
                assert (home / "server/run/gateway-upgrade.json").exists()
                raise urllib.error.HTTPError(url, 503, "server_maintenance", {}, None)
            return Response()

    monkeypatch.setattr(manager_module, "WebServiceManager", Manager)
    monkeypatch.setattr(
        original,
        "configured",
        lambda _h: (
            root,
            {
                "project": str(project),
                "web_port": 8088,
                "runtime_port": 3081,
                "node": "/node",
                "private_origin": "https://fixture.tail.ts.net",
            },
        ),
    )
    monkeypatch.setattr(original, "environment", lambda *_: None)
    monkeypatch.setattr(original, "git", git)
    monkeypatch.setattr(original, "clean", lambda *_: None)
    monkeypatch.setattr(original, "run", lambda *_a, **_k: None)
    monkeypatch.setattr(original, "fixed_ports", lambda *_: contextlib.nullcontext())
    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "test-sentinel")
    with pytest.raises(urllib.error.HTTPError):
        original.bridge_main(home, "recover")
    assert code["revision"] == upgrade.PREVIOUS
    assert events == ["old-stop-primary", "old-start-primary"]
    assert (root / "transaction.json").exists()
    assert (home / "server/run/gateway-upgrade.json").exists()
    # The new recovery accepts the known previous primary and still restores both roles.
    recovery = Operations()
    assert (
        upgrade.execute(recovery, {"phase": "start_gateway"}, recovering=True)["status"]
        == "rolled_back"
    )


@pytest.mark.parametrize("bad", ["redirect", "primary-html", "network", "wrong-status"])
def test_private_root_must_really_be_fenced_without_redirect(monkeypatch, bad):
    import urllib.error

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

    class Opener:
        def open(self, *_a, **_k):
            if bad == "network":
                raise urllib.error.URLError("synthetic")
            if bad != "primary-html":
                raise urllib.error.HTTPError(
                    "https://fixture/", 301 if bad == "redirect" else 502, "synthetic", {}, None
                )
            return Response()

    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    with pytest.raises((upgrade.UpdateBlocked, urllib.error.URLError)):
        upgrade.verify_private_fence("https://fixture")


def test_private_fence_accepts_only_503(monkeypatch):
    import urllib.error

    class Opener:
        def open(self, *_a, **_k):
            raise urllib.error.HTTPError("https://fixture/", 503, "synthetic", {}, None)

    monkeypatch.setattr(upgrade.urllib.request, "build_opener", lambda *_: Opener())
    upgrade.verify_private_fence("https://fixture")


@pytest.fixture
def real_operations(tmp_path, monkeypatch):
    """Run real journals, reservations, configuration and operation methods; fake OS effects."""
    import hashlib

    import app.research_web.multiuser.resident_binding as binding_module

    home = tmp_path.resolve()
    root, server = home / "resident", home / "server"
    primary, gateway = home / "primary", home / "gateway"
    for p in (root, server, primary, gateway, home / "research-web"):
        p.mkdir(mode=0o700)
    (server / "run").mkdir(mode=0o700)
    (server / "users").mkdir(mode=0o700)
    uid = str(uuid4())
    for p in (server / "users" / uid, server / "users" / uid / "state"):
        p.mkdir(mode=0o700)
    with sqlite3.connect(server / "accounts.sqlite3") as db:
        db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO accounts VALUES (?)", (uid,))
    (server / "accounts.sqlite3").chmod(0o600)
    upgrade.c.atomic(home / "research-web/index.json", {"automation_runs": {}})
    body = home / "research-web/keep.txt"
    body.write_bytes(b"private fixture remains intact")
    expected_body = hashlib.sha256(body.read_bytes()).hexdigest()
    config = {
        "project": str(primary),
        "baseline": "known",
        "web_port": 8088,
        "runtime_port": 3081,
        "node": "/node",
        "private_origin": "https://fixture.tail.ts.net",
        "source_common": str(home / ".git"),
    }
    binding = {
        "primary_user_id": uid,
        "home": str(home),
        "project": str(primary),
        "revision": upgrade.PREVIOUS,
        "web_port": 8088,
        "runtime_port": 3081,
        "project_identity": [1, 2],
        "data_identity": [3, 4],
    }
    gw = {
        "project": str(gateway),
        "revision": upgrade.PREVIOUS,
        "binding": binding,
        "origin": config["private_origin"],
    }
    manifest = {"code_commit": upgrade.PREVIOUS, "status": "installed"}
    accepted = {"target": upgrade.PREVIOUS, "sentinel": "previous-accepted"}
    for path, value in (
        (root / "config.json", config),
        (server / "resident.json", gw),
        (home / "install/manifest.json", manifest),
        (root / "accepted.json", accepted),
        (root / "candidate.json", accepted),
    ):
        upgrade.c.atomic(path, value)
    plist = home / "gateway.plist"
    plist.write_bytes(plistlib.dumps({"ProgramArguments": ["/python"]}))
    wheel = root / "old.whl"
    wheel.write_bytes(b"fixture wheel")
    state = {
        "version": 4,
        "mode": upgrade.MODE,
        "phase": "prepared",
        "transaction": str(uuid4()),
        "previous": upgrade.PREVIOUS,
        "target": "b" * 40,
        "primary_project": str(primary),
        "gateway_project": str(gateway),
        "config": config,
        "gateway_config": gw,
        "gateway_plist": str(plist),
        "gateway_plist_sha256": upgrade.c.digest(plist),
        "gateway_command": "/python -m gateway",
        "manifest": manifest,
        "accepted": accepted,
        "candidate_before": accepted,
        "before": {"body": expected_body},
        "new_wheel": {"path": str(wheel), "sha256": upgrade.c.digest(wheel)},
        "old_wheel": {"path": str(wheel), "sha256": upgrade.c.digest(wheel)},
        "proof": {"qualified": True},
        "reviewed": {"fixture": "blob"},
    }
    state["model_before"] = {
        "provider": "deepseek-official",
        "model": "deepseek-flash",
        "credential_configured": True,
        "credential_storage": "system_keychain",
    }
    system = {
        "primary": upgrade.PREVIOUS,
        "gateway": upgrade.PREVIOUS,
        "running": True,
        "loaded": True,
        "pid": 900001,
        "active": False,
        "fail": None,
        "failed": False,
        "events": [],
    }

    def job():
        return (
            f"path = {plist}\nprogram = /python\nworking directory = {gateway}\n"
            if system["loaded"]
            else None
        )

    monkeypatch.setattr(upgrade.g, "job_state", job)
    monkeypatch.setattr(upgrade.g, "job_pid", lambda: system["pid"] if system["loaded"] else None)
    monkeypatch.setattr(
        upgrade.g,
        "listener_pids",
        lambda: {system["pid"]} if system["loaded"] and system["pid"] else set(),
    )
    monkeypatch.setattr(
        upgrade.g, "process", lambda _pid: "Wed Oct 21 10:00:00 2026 /python -m gateway"
    )
    monkeypatch.setattr(upgrade.g, "native_image", lambda _pid: Path("/python"))
    monkeypatch.setattr(upgrade.g, "no_children", lambda _pid: None)
    monkeypatch.setattr(upgrade.g, "no_private_processes", lambda _root: None)

    def drain(*_args):
        assert (server / "run/gateway-upgrade.json").exists()
        system["events"].append("SIGTERM")
        system["pid"] = None

    monkeypatch.setattr(upgrade.g, "graceful_drain", drain)
    monkeypatch.setattr(
        upgrade.g, "bootout_after_drain", lambda _p: system.update(loaded=False, pid=None)
    )
    monkeypatch.setattr(upgrade.g, "bootstrap", lambda _p: system.update(loaded=True, pid=900002))

    def git(project, *args):
        role = "primary" if Path(project) == primary else "gateway"
        if args == ("rev-parse", "HEAD"):
            return system[role]
        if args[:2] == ("switch", "--detach"):
            assert not system["loaded"] and not system["running"]
            system[role] = args[2]
            return ""
        pytest.fail("unexpected fixture Git operation")

    monkeypatch.setattr(upgrade.c, "git", git)
    monkeypatch.setattr(
        upgrade.c,
        "clean",
        lambda project, sha: (
            None if git(project, "rev-parse", "HEAD") == sha else pytest.fail("dirty source")
        ),
    )

    def install(*_args, **_kwargs):
        assert not system["loaded"] and not system["running"]
        system["events"].append("pip-no-deps")

    monkeypatch.setattr(upgrade.c, "run", install)
    monkeypatch.setattr(upgrade, "verify_serve", lambda _origin: None)
    monkeypatch.setattr(
        upgrade,
        "verify_private_fence",
        lambda _origin: (
            None
            if (server / "run/gateway-upgrade.json").exists()
            else pytest.fail("no global fence")
        ),
    )
    monkeypatch.setattr(upgrade, "ports_are_free", lambda _ports: True)
    import contextlib

    monkeypatch.setattr(upgrade.c, "fixed_ports", lambda *_args: contextlib.nullcontext())

    def health(value, *, fenced):
        assert system["loaded"] and value["revision"] == system["gateway"]
        assert fenced is True and (server / "run/gateway-upgrade.json").exists()

    monkeypatch.setattr(upgrade.g, "health", health)
    monkeypatch.setattr(upgrade.g, "wait_health", health)

    def verify_primary(_home, sha):
        assert system["running"] and system["primary"] == sha and not system["active"]

    monkeypatch.setattr(upgrade.g, "verify_primary", verify_primary)
    monkeypatch.setattr(
        upgrade.g,
        "preserved",
        lambda *_args: (
            None
            if hashlib.sha256(body.read_bytes()).hexdigest() == expected_body
            else pytest.fail("data changed")
        ),
    )

    def request(url):
        if url.endswith("/api/research/runtime"):
            return {"connected": True, "health_check_passed": True, **state["model_before"]}
        if url.endswith("/api/research/model-profiles"):
            return {"items": [{"active": True, **state["model_before"]}]}
        if url.endswith("/api/server/health"):
            return {
                "revision": system["gateway"],
                "deployment_fenced": (server / "run/gateway-upgrade.json").exists(),
            }
        return {"enabled": True, "revision": system["primary"], "active": system["active"]}

    monkeypatch.setattr(upgrade, "request_json", request)
    fake_binding = SimpleNamespace(
        verify=lambda: {"revision": system["primary"]},
        public_config=lambda: {
            **binding,
            "revision": system["primary"],
            "project_identity": tuple(binding["project_identity"]),
            "data_identity": tuple(binding["data_identity"]),
        },
    )
    monkeypatch.setattr(
        binding_module.LegacyBinding, "discover", classmethod(lambda *_args: fake_binding)
    )

    class Manager:
        def status(self):
            return {
                "services": {
                    role: {"running": system["running"], "healthy": system["running"]}
                    for role in ("web", "runtime")
                }
            }

        def _service_probes(self):
            return [SimpleNamespace(role="runtime")]

        def _active_research_read_only(self, _runtime):
            return system["active"] is not False

        def _stop_locked(self):
            assert not system["active"] and (root / "transaction.json").exists()
            system["running"] = False

        def _start_installed(self, *_args, **_kwargs):
            assert (root / "transaction.json").exists()
            system["running"] = True

    class CheckedOperations(upgrade.Operations):
        def action(self, name, record):
            assert record["phase"] == name
            super().action(name, record)
            if system["fail"] == name and not system["failed"]:
                system["failed"] = True
                raise RuntimeError("synthetic after-effect failure")

    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "test-sentinel")
    return (
        home,
        state,
        system,
        lambda fence: CheckedOperations(home, state, Manager(), object(), fence),
        uid,
    )


@pytest.mark.parametrize("failed", [None, *upgrade.FORWARD])
def test_real_operation_methods_converge_and_preserve_data(real_operations, failed):
    home, state, system, make, uid = real_operations
    system["fail"] = failed
    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        result = upgrade.execute(make(fence), state)
    expected = state["target"] if failed is None else upgrade.PREVIOUS
    assert result["status"] == ("deployed" if failed is None else "rolled_back")
    assert system["primary"] == system["gateway"] == expected
    assert system["running"] and system["loaded"]
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()
    assert not (home / "server/run/birth-fence.json").exists()
    assert json.loads((home / "install/manifest.json").read_text())["code_commit"] == expected


def test_real_activity_in_gateway_only_window_blocks_all_effects(real_operations):
    home, state, system, make, _uid = real_operations
    upgrade.g.write_upgrade_journal(home / "server/run/gateway-upgrade.json", state)
    system["active"] = True
    result = upgrade.execute(make(None), state, recovering=True)
    assert result["status"] == "recovery_required"
    assert system["events"] == []
    assert not (home / "resident/transaction.json").exists()
    assert (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("crash_after", upgrade.FORWARD)
def test_new_recovery_resumes_real_reservations_after_each_interruption(
    real_operations, crash_after
):
    home, state, system, make, uid = real_operations
    with (
        pytest.raises(SystemExit),
        BirthFence(home / "server", uid, transaction=state["transaction"]) as fence,
    ):
        ops = make(fence)
        original = ops.action

        def crash(name, record):
            original(name, record)
            if name == crash_after:
                raise SystemExit("synthetic process interruption")

        ops.action = crash
        upgrade.execute(ops, state)
    saved = upgrade.g.read_upgrade_journal(home / "server/run/gateway-upgrade.json")
    resume = (home / "server/run/birth-fence.json").exists()
    with BirthFence(home / "server", uid, resume=resume, transaction=saved["transaction"]) as fence:
        ops = make(fence)
        ops.state = saved
        result = upgrade.execute(ops, saved, recovering=True)
    assert result["status"] == "rolled_back"
    assert system["primary"] == system["gateway"] == upgrade.PREVIOUS
    assert system["running"] and system["loaded"]
    assert not (home / "resident/transaction.json").exists()
    assert not (home / "server/run/gateway-upgrade.json").exists()


@pytest.mark.parametrize("name", ["config", "gateway", "manifest", "journal"])
def test_unknown_configuration_never_gets_overwritten(real_operations, name):
    home, state, _system, _make, _uid = real_operations
    paths = {
        "config": home / "resident/config.json",
        "gateway": home / "server/resident.json",
        "manifest": home / "install/manifest.json",
        "journal": home / "resident/transaction.json",
    }
    p = paths[name]
    upgrade.c.atomic(p, {"foreign": "preserve this record"})
    raw = p.read_bytes()
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.validate_configuration(home, state)
    assert p.read_bytes() == raw


@pytest.mark.parametrize(
    "configured,storage,accepted",
    [
        (True, "system_keychain", True),
        (False, "system_keychain", True),
        (None, "not_required", True),
        (None, "unknown", False),
    ],
)
def test_model_metadata_never_resolves_or_logs_key_values(
    monkeypatch, configured, storage, accepted
):
    response = {
        "connected": True,
        "health_check_passed": True,
        "provider": "deepseek-official",
        "model": "deepseek-flash",
        "credential_configured": configured,
        "credential_storage": storage,
        "ignored": "not retained",
    }
    monkeypatch.setattr(upgrade, "request_json", lambda _u: response)
    if accepted:
        assert set(upgrade.model_metadata({"web_port": 8088})) == {
            "provider",
            "model",
            "credential_configured",
            "credential_storage",
        }
    else:
        with pytest.raises(MaintenanceBusy):
            upgrade.model_metadata({"web_port": 8088})


@pytest.mark.parametrize("changed", ["root", "extra-api", "funnel", "tls"])
def test_serve_changes_cannot_bypass_private_root_gate(monkeypatch, changed):
    value = {
        "Web": {
            "fixture.tail.ts.net:443": {
                "Handlers": {
                    "/": {"Proxy": "http://127.0.0.1:8089"},
                    "/collections": {"Proxy": "http://127.0.0.1:8769"},
                }
            }
        },
        "TCP": {"443": {"HTTPS": True}},
    }
    if changed == "root":
        value["Web"]["fixture.tail.ts.net:443"]["Handlers"]["/"]["Proxy"] = "http://127.0.0.1:8088"
    if changed == "extra-api":
        value["Web"]["fixture.tail.ts.net:443"]["Handlers"]["/api"] = {
            "Proxy": "http://127.0.0.1:8088"
        }
    if changed == "funnel":
        value["AllowFunnel"] = {"fixture.tail.ts.net:443": True}
    if changed == "tls":
        value["TCP"]["443"]["HTTPS"] = False
    monkeypatch.setattr(upgrade.g, "run", lambda _args: json.dumps(value))
    with pytest.raises(upgrade.UpdateBlocked, match="private_route_unknown"):
        upgrade.verify_serve("https://fixture.tail.ts.net")


def test_existing_collections_route_is_preserved(monkeypatch):
    value = {
        "Web": {
            "fixture.tail.ts.net:443": {
                "Handlers": {
                    "/": {"Proxy": "http://127.0.0.1:8089"},
                    "/collections": {"Proxy": "http://127.0.0.1:8769"},
                }
            }
        },
        "TCP": {"443": {"HTTPS": True}},
    }
    original = json.dumps(value, sort_keys=True)
    monkeypatch.setattr(upgrade.g, "run", lambda _args: json.dumps(value))
    upgrade.verify_serve("https://fixture.tail.ts.net")
    assert json.dumps(value, sort_keys=True) == original


def test_retention_cannot_purge_existing_deleted_history_during_deployment(tmp_path):
    import time

    upgrade.c.atomic(
        tmp_path / "research-web/index.json",
        {"sessions": {"fixture": {"deleted_at": time.time() - 31 * 86400}}},
    )
    with pytest.raises(upgrade.UpdateBlocked, match="retention_due"):
        upgrade.verify_retention(tmp_path)


@pytest.mark.parametrize("bad", ["dependency", "payload", "mode", "workflow"])
def test_exact_profile_rejects_unreviewed_business_or_installation_changes(
    monkeypatch, tmp_path, bad
):
    monkeypatch.setattr(upgrade.c, "clean", lambda *_: None)
    path = (
        "requirements/web.lock"
        if bad == "dependency"
        else ("app/research_web/service.py" if bad in ["payload", "mode"] else upgrade.WORKFLOW)
    )

    def git(_root, *args):
        if args[0] == "merge-base":
            return ""
        if args[0] == "diff":
            return f"{upgrade.MODULE}\n{upgrade.TEST}\n{path}"
        if args[0] == "rev-parse":
            return "b" * 40 if args[-1].startswith("f" * 40) and bad != "mode" else "a" * 40
        if args[0] == "ls-tree":
            return (
                ("100755" if args[1] == "f" * 40 else "100644")
                + " blob "
                + "a" * 40
                + "\t"
                + args[-1]
            )
        if args[0] == "show":
            return (
                "unreviewed"
                if args[-1].startswith("f" * 40)
                else "tests/research_web/test_gateway_upgrade.py"
            )
        pytest.fail("unexpected profile query")

    monkeypatch.setattr(upgrade.c, "git", git)
    with pytest.raises(upgrade.UpdateBlocked):
        upgrade.review(tmp_path, "f" * 40)


@pytest.mark.parametrize(
    "point",
    [
        "accepted",
        "candidate",
        "baseline",
        "config",
        "result",
        "record",
        "root-unlink",
        "root-sync",
        "gate-unlink",
        "gate-sync",
    ],
)
@pytest.mark.parametrize("after", [False, True])
def test_finish_failure_never_signals_again_in_same_stack(
    real_operations, monkeypatch, point, after
):
    home, state, system, make, uid = real_operations
    atomic, unlink, sync, record = (
        upgrade.c.atomic,
        Path.unlink,
        upgrade.c.sync_directory,
        upgrade.c.record,
    )
    fired = False

    def interrupt(operation, effect, *args, **kwargs):
        nonlocal fired
        selected = operation == point and not fired
        if selected and not after:
            fired = True
            raise OSError("fixture finish interruption")
        value = effect(*args, **kwargs)
        if selected:
            fired = True
            raise OSError("fixture finish interruption after effect")
        return value

    def write(path, value):
        names = {
            "accepted.json": "accepted",
            "candidate.json": "candidate",
            "config.json": "config",
            "model-upgrade-result.json": "result",
        }
        kind = "baseline" if path.parent.name == "baseline-reviews" else names.get(path.name)
        return interrupt(kind, atomic, path, value)

    def remove(path, *args, **kwargs):
        kind = (
            "root-unlink"
            if path == home / "resident/transaction.json"
            else ("gate-unlink" if path == home / "server/run/gateway-upgrade.json" else None)
        )
        return interrupt(kind, unlink, path, *args, **kwargs)

    def flush(path):
        # Inject only once source verification and startup have finished.
        final = (home / "server/run/model-upgrade-result.json").exists()
        kind = (
            (
                "root-sync"
                if path == home / "resident"
                else "gate-sync" if path == home / "server/run" else None
            )
            if final
            else None
        )
        return interrupt(kind, sync, path)

    with BirthFence(home / "server", uid, transaction=state["transaction"]) as fence:
        ops = make(fence)
        # Patch only finish, to retain real forward method behavior.
        original = ops.finish

        def finish(value, result):
            monkeypatch.setattr(upgrade.c, "atomic", write)
            monkeypatch.setattr(Path, "unlink", remove)
            monkeypatch.setattr(upgrade.c, "sync_directory", flush)
            monkeypatch.setattr(
                upgrade.c, "record", lambda *a, **kw: interrupt("record", record, *a, **kw)
            )
            return original(value, result)

        ops.finish = finish
        result = upgrade.execute(ops, state)
    assert fired and result["status"] == "completion_unknown"
    assert system["events"].count("SIGTERM") == 1
    assert system["primary"] == system["gateway"] == state["target"]
    monkeypatch.undo()


@pytest.mark.parametrize(
    "boundary", ["publish-journal", "stage-recorded", "owner-published", "releasing"]
)
def test_preparing_intent_recovers_partial_birth_fence(real_operations, monkeypatch, boundary):
    from research_workbench_entrypoint.resident import gateway_fence as module

    home, state, system, make, uid = real_operations
    monkeypatch.setattr(upgrade.g, "preservation", lambda _home: state["before"])
    make(None).prepare_fence(state)
    assert (
        json.loads((home / "server/run/gateway-upgrade.json").read_text())["phase"] == "preparing"
    )
    original_atomic, original_rename = module.atomic, module.exclusive_rename

    def write(path, value):
        original_atomic(path, value)
        if boundary == "stage-recorded" and path.name == "birth-fence.json" and value["slots"]:
            raise SystemExit("fixture kill after stage journal")
        if (
            boundary == "releasing"
            and path.name == "birth-fence.json"
            and any(s.get("releasing") for s in value["slots"])
        ):
            raise SystemExit("fixture kill during release")

    def rename(source, destination):
        original_rename(source, destination)
        if boundary == "publish-journal" and destination.name == "birth-fence.json":
            raise SystemExit("fixture kill after birth journal")
        if boundary == "owner-published" and destination.name == "owner.json":
            raise SystemExit("fixture kill after owner publish")

    monkeypatch.setattr(module, "atomic", write)
    monkeypatch.setattr(module, "exclusive_rename", rename)
    fence = BirthFence(home / "server", uid, transaction=state["transaction"])
    with pytest.raises(SystemExit):
        fence.__enter__()
        fence.__exit__(None, None, None)
    fence.release_database()
    monkeypatch.setattr(module, "atomic", original_atomic)
    monkeypatch.setattr(module, "exclusive_rename", original_rename)
    BirthFence.recover(home / "server", expected=state["transaction"])
    assert not (home / "server/run/birth-fence.json").exists()
    assert not list((home / "server/users").glob("*/state/owner.json"))
    assert make(None).idle() is True
    assert system["events"] == []
