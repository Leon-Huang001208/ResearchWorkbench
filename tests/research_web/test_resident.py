"""Resident deployment contracts without host launchd, GitHub writes or model calls."""

import asyncio
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from research_workbench_entrypoint.resident import controller, evidence
from research_workbench_entrypoint.resident.admission import (
    MaintenanceBusy,
    admission,
    file_lock,
    research_admission,
)


@pytest.fixture
def resident(tmp_path, monkeypatch):
    root = tmp_path / "resident"
    root.mkdir(mode=0o700)
    monkeypatch.setenv("RESEARCH_RESIDENT_HOME", str(root))
    return root


def test_mutation_fence_is_cross_process_and_released_on_exit(resident):
    with file_lock(resident, "admission.lock", exclusive=True):
        command = (
            "from research_workbench_entrypoint.resident.admission import admission; "
            "\nwith admission(): pass"
        )
        result = subprocess.run([sys.executable, "-c", command], capture_output=True, check=False)
        assert result.returncode != 0
        assert b"MaintenanceBusy" in result.stderr
    with admission():
        pass


def test_inflight_request_prevents_updater_and_journal_fences_after_crash(resident):
    with (
        admission(),
        pytest.raises(MaintenanceBusy),
        file_lock(resident, "admission.lock", exclusive=True),
    ):
        pytest.fail("entered exclusive transaction with an in-flight admission")
    controller.atomic(resident / "transaction.json", {"phase": "switching"})
    with pytest.raises(MaintenanceBusy), admission():
        pytest.fail("crashed update admitted a new mutation")


@pytest.mark.asyncio
async def test_scheduled_research_waits_without_losing_accepted_work(resident):
    called = []

    @research_admission
    async def research():
        called.append(True)
        return "accepted"

    with file_lock(resident, "admission.lock", exclusive=True):
        task = asyncio.create_task(research())
        await asyncio.sleep(0.01)
        assert not called
    assert await asyncio.wait_for(task, timeout=1) == "accepted"
    assert called == [True]


def test_fence_disabled_by_default(monkeypatch):
    monkeypatch.delenv("RESEARCH_RESIDENT_HOME", raising=False)
    with admission():
        pass


def test_http_maintenance_retains_origin_guard_and_read_only_health(resident, monkeypatch):
    from fastapi.testclient import TestClient

    from app.research_web.main import create_app

    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "a" * 40)
    client = TestClient(create_app())  # no lifespan or runtime/model access
    controller.atomic(resident / "transaction.json", {"phase": "switching"})
    response = client.post("/api/research/sessions", json={})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "deployment_busy"
    assert client.get("/api/research/resident").json() == {
        "enabled": True,
        "revision": "a" * 40,
        "maintenance": True,
        "active": None,
    }
    assert client.get("/").status_code == 200
    assert (
        client.post(
            "/api/research/sessions", json={}, headers={"Origin": "https://evil.test"}
        ).status_code
        == 403
    )


def test_lock_symlink_and_hardlink_are_rejected(resident, tmp_path):
    target = tmp_path / "target"
    target.write_text("do not change")
    (resident / "admission.lock").symlink_to(target)
    with pytest.raises(OSError), admission():
        pass
    (resident / "admission.lock").unlink()
    os.link(target, resident / "admission.lock")
    with pytest.raises(RuntimeError, match="resident_lock_unsafe"), admission():
        pass
    assert target.read_text() == "do not change"


def test_compatibility_is_cumulative_and_unknown_paths_require_review():
    assert evidence.compatible(["app/research_web/ui/app.mjs", "docs/a.md"])
    for path in (
        "requirements/web.lock",
        "app/research_web/store.py",
        "services/hot/schema.sql",
        "app/research_web/new_startup.py",
        "research_workbench_entrypoint/resident/controller.py",
    ):
        assert not evidence.compatible(["app/research_web/ui/app.mjs", path])


def test_atomic_state_is_private_and_invalid_records_fail_closed(resident):
    path = resident / "state.json"
    controller.atomic(path, {"status": "ready"})
    assert path.stat().st_mode & 0o777 == 0o600
    assert evidence.read_json(path) == {"status": "ready"}
    path.write_text("[]")
    with pytest.raises(evidence.UpdateBlocked):
        evidence.read_json(path)


def test_launchagent_is_after_login_and_uses_pinned_artifact(tmp_path, monkeypatch):
    home = tmp_path / "product"
    home.mkdir(mode=0o700)
    user = tmp_path / "user"
    user.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    common = tmp_path / "common"
    common.mkdir()
    node = home / "toolchain/node-v24.19.0-darwin-arm64/bin/node"
    node.parent.mkdir(parents=True)
    node.write_text("fixture")
    node.chmod(0o700)
    (home / "install").mkdir(mode=0o700)
    controller.atomic(home / "install/manifest.json", {"code_commit": "a" * 40})
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: user)
    monkeypatch.setattr(controller.shutil, "which", lambda _: "/usr/bin/true")

    def git(_project, *args):
        if "--git-common-dir" in args:
            return str(common)
        return "" if args[0] == "status" else "a" * 40

    monkeypatch.setattr(controller, "git", git)
    commands = []
    monkeypatch.setattr(controller, "run", lambda argv, **_: commands.append(argv))
    assert (
        controller.install(home, project, tmp_path, "https://mini.tail123.ts.net")["status"]
        == "installed"
    )
    import plistlib

    plist = user / "Library/LaunchAgents/com.research-workbench.resident.plist"
    value = plistlib.loads(plist.read_bytes())
    assert value["RunAtLoad"] is True and value["StartInterval"] == 60
    assert value["ProgramArguments"][1] == str(home / "resident/controller.pyz")
    assert "sudo" not in str(value) and "KeepAlive" not in value
    assert commands[0][:2] == ["/bin/launchctl", "enable"]
    assert commands[1][:3] == ["/bin/launchctl", "bootstrap", f"gui/{os.getuid()}"]
    assert controller.configured(home)[1]["baseline"] == "a" * 40
    before = (home / "resident/controller.pyz").read_bytes()

    def failed_bootstrap(argv, **_):
        if argv[1] in {"bootstrap", "print"}:
            raise evidence.UpdateBlocked("fixture_bootstrap_failed")

    monkeypatch.setattr(controller, "run", failed_bootstrap)
    with pytest.raises(evidence.UpdateBlocked, match="fixture_bootstrap_failed"):
        controller.install(home, project, tmp_path, "https://mini.tail123.ts.net")
    monkeypatch.setattr(controller, "run", lambda argv, **_: commands.append(argv))
    assert (
        controller.install(home, project, tmp_path, "https://mini.tail123.ts.net")["status"]
        == "installed"
    )
    assert (home / "resident/controller.pyz").read_bytes() == before


def test_disable_defers_instead_of_terminating_inflight_transaction(resident, monkeypatch):
    commands = []
    monkeypatch.setattr(controller, "run", lambda argv, **_: commands.append(argv))
    with file_lock(resident, "supervisor.lock", exclusive=True):
        assert controller.main(["disable", "--home", str(resident.parent)]) == 0
    assert commands == []
    controller.atomic(resident / "transaction.json", {"phase": "switching"})
    assert controller.main(["disable", "--home", str(resident.parent)]) == 1
    assert commands == []
    assert (resident / "transaction.json").exists()


def test_boot_recovery_precedes_github_and_failed_recovery_never_updates(resident, monkeypatch):
    home = resident.parent
    controller.atomic(resident / "transaction.json", {"phase": "switching"})
    monkeypatch.setattr(controller, "configured", lambda _: (resident, {}))
    monkeypatch.setattr(controller, "environment", lambda *_: None)
    calls = []

    def bridge(_home, _config, operation):
        calls.append(operation)
        return {"status": "blocked"}

    monkeypatch.setattr(controller, "bridge", bridge)
    result = controller.tick(home)
    assert result["status"] == "blocked"
    assert calls == ["recover"]


def test_offline_check_keeps_current_service_running(resident, monkeypatch):
    config = {"gh": "/gh", "source_common": "/common", "repository": "owner/repo"}
    monkeypatch.setattr(controller, "configured", lambda _: (resident, config))
    monkeypatch.setattr(controller, "environment", lambda *_: None)
    calls = []
    monkeypatch.setattr(
        controller,
        "bridge",
        lambda *_: calls.append("ensure") or {"status": "ready", "sha": "a" * 40},
    )
    monkeypatch.setattr(
        controller.GitHubEvidence,
        "latest",
        lambda _: (_ for _ in ()).throw(evidence.UpdateBlocked("offline")),
    )
    result = controller.tick(resident.parent)
    assert result["status"] == "waiting" and result["deployed"] == "a" * 40
    assert calls == ["ensure"]


def github_fixture(tmp_path, monkeypatch, *, tree_mismatch=False, review_head=None):
    common = tmp_path / "common"
    delivery = common / "leon-engineering/deliveries"
    review = common / "leon-engineering/git-safety/reviews"
    delivery.mkdir(parents=True)
    review.mkdir(parents=True)
    head, target = "a" * 40, "b" * 40
    (delivery / "task.json").write_text(
        json.dumps(
            {
                "remoteCommit": target,
                "integrationCommit": head,
                "status": "cleaned",
                "mode": "pr",
                "ci": {"status": "passed"},
                "verification": {"status": "passed"},
                "pullRequest": {"number": 123},
            }
        )
    )
    (review / "task.json").write_text(
        json.dumps({"status": "PASS", "reviewedCommit": review_head or head})
    )
    instance = evidence.GitHubEvidence(Path("/gh"), "owner/repo", common)

    def api(endpoint):
        if endpoint.startswith("pulls/"):
            return {
                "merged": True,
                "merge_commit_sha": target,
                "head": {"sha": head},
                "base": {"ref": "master"},
            }
        if endpoint.startswith("git/commits/"):
            tree = "wrong" if tree_mismatch and endpoint.endswith(head) else "tree"
            return {"tree": {"sha": tree}}
        if "/jobs?" in endpoint:
            return {"jobs": [{"id": 7, "conclusion": "success", "labels": ["macos-14"]}]}
        return {"workflow_runs": [{"id": 1, "status": "completed", "conclusion": "success"}]}

    monkeypatch.setattr(instance, "api", api)
    monkeypatch.setattr(
        evidence,
        "run",
        lambda _: "[command]/usr/bin/git log -1 --format=%H\n2026-10-15T00:00:00Z " + head,
    )
    return instance, target


def test_eligibility_requires_matching_review_and_actual_ci_tree(tmp_path, monkeypatch):
    instance, target = github_fixture(tmp_path, monkeypatch)
    assert instance.qualify(target)["sha"] == target


def test_green_ci_for_other_tree_is_rejected(tmp_path, monkeypatch):
    instance, target = github_fixture(tmp_path, monkeypatch, tree_mismatch=True)
    with pytest.raises(evidence.UpdateBlocked, match="resident_ci_tree_mismatch"):
        instance.qualify(target)


def test_stale_review_is_rejected(tmp_path, monkeypatch):
    instance, target = github_fixture(tmp_path, monkeypatch, review_head="c" * 40)
    with pytest.raises(evidence.UpdateBlocked, match="resident_reviewed_delivery_missing"):
        instance.qualify(target)


@pytest.fixture
def transaction(resident, monkeypatch):
    from app.research_web import service_manager

    home = resident.parent
    project = home / "project"
    project.mkdir()
    config = {
        "project": str(project),
        "node": "/node",
        "web_port": 8088,
        "runtime_port": 3081,
        "private_origin": "https://mini.tail123.ts.net",
    }
    candidate = {"previous": "a" * 40, "target": "b" * 40, "manifest": {"code_commit": "a" * 40}}
    for field in ("old_wheel", "new_wheel"):
        path = resident / "artifacts" / field / "test.whl"
        path.parent.mkdir(parents=True)
        path.write_bytes(field.encode())
        candidate[field] = {"path": str(path), "sha256": controller.digest(path)}
    controller.atomic(resident / "candidate.json", candidate)
    (home / "research-web").mkdir(mode=0o700)
    controller.atomic(home / "research-web/index.json", {"automation_runs": {}})
    (home / "install").mkdir(mode=0o700)
    controller.atomic(home / "install/manifest.json", candidate["manifest"])
    data = home / "research-web/keep.txt"
    data.write_text("research and settings remain")
    events = []
    state = {"sha": candidate["previous"], "active": False, "fail": True, "rollback_fail": False}

    class Manager:
        @contextmanager
        def _installation_start_scope(self):
            events.append("lease_acquired")
            yield "same-lease"
            events.append("lease_released")

        def _service_probes(self):
            return [SimpleNamespace(role="runtime")]

        def _active_research_read_only(self, _):
            return ["active-session"] if state["active"] else []

        def _stop_locked(self):
            assert (resident / "transaction.json").is_file()
            events.append("stop")

        def _start_installed(self, lease, **_):
            assert lease == "same-lease"
            events.append("start:" + state["sha"])
            if state["sha"] == candidate["target"] and state["fail"]:
                raise RuntimeError("injected startup failure")
            if state["sha"] == candidate["previous"] and state["rollback_fail"]:
                raise RuntimeError("injected rollback failure")

        def status(self):
            return {
                "services": {
                    role: {"running": True, "healthy": True, "port": port}
                    for role, port in (("web", 8088), ("runtime", 3081))
                }
            }

    monkeypatch.setattr(service_manager, "WebServiceManager", lambda **_: Manager())
    monkeypatch.setattr(controller, "configured", lambda _: (resident, config))
    monkeypatch.setattr(controller, "environment", lambda *_: None)
    monkeypatch.setattr(controller, "clean", lambda *_: None)
    monkeypatch.setattr(controller, "wait_ports", lambda *_: None)

    def git(_root, *arguments):
        if arguments[:1] == ("switch",):
            state["sha"] = arguments[-1]
            events.append("checkout:" + state["sha"])
        return state["sha"]

    monkeypatch.setattr(controller, "git", git)
    monkeypatch.setattr(
        controller, "run", lambda arguments, **_: events.append("pip:" + arguments[-1])
    )

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, *_):
            return json.dumps(
                {
                    "enabled": True,
                    "revision": state["sha"],
                    "active": state.get("host_active", False),
                }
            ).encode()

    class Opener:
        def open(self, url, **_):
            response = Response()
            if not url.endswith("resident"):
                response.read = lambda *_: b"<!doctype html>"
            return response

    import urllib.request

    monkeypatch.setattr(urllib.request, "build_opener", lambda *_: Opener())
    return home, resident, state, events, candidate, data


def test_candidate_failure_restores_code_wheel_manifest_and_preserves_data(transaction):
    home, root, state, events, candidate, data = transaction
    result = controller.bridge_main(home, "deploy")
    assert result == {"status": "rolled_back", "sha": candidate["previous"]}
    assert state["sha"] == candidate["previous"]
    assert events.count("stop") == 2
    assert "pip:" + candidate["old_wheel"]["path"] in events
    assert evidence.read_json(home / "install/manifest.json") == candidate["manifest"]
    assert not (root / "transaction.json").exists()
    assert evidence.read_json(root / "quarantine.json")["sha"] == candidate["target"]
    assert data.read_text() == "research and settings remain"


def test_active_native_research_never_stops_or_writes_journal(transaction):
    home, root, state, events, *_ = transaction
    state["active"] = True
    assert controller.bridge_main(home, "deploy")["status"] == "deferred"
    assert "stop" not in events
    assert not (root / "transaction.json").exists()


def test_queued_automation_defers_even_when_native_idle(transaction):
    home, _root, _state, events, *_ = transaction
    controller.atomic(
        home / "research-web/index.json", {"automation_runs": {"r": {"research_status": "queued"}}}
    )
    assert controller.bridge_main(home, "deploy")["status"] == "deferred"
    assert "stop" not in events


def test_pending_host_admission_defers_even_when_native_idle(transaction):
    home, root, state, events, *_ = transaction
    state["host_active"] = True
    assert controller.bridge_main(home, "deploy")["status"] == "deferred"
    assert "stop" not in events
    assert not (root / "transaction.json").exists()


def test_failed_recovery_leaves_durable_journal_and_fence(transaction):
    home, root, state, _events, candidate, _ = transaction
    state["rollback_fail"] = True
    controller.atomic(root / "transaction.json", {**candidate, "phase": "switching"})
    with pytest.raises(RuntimeError, match="injected rollback failure"):
        controller.bridge_main(home, "recover")
    assert (root / "transaction.json").exists()
    with pytest.raises(MaintenanceBusy), admission():
        pytest.fail("failed rollback admitted mutations")


def test_interrupted_update_recovers_previous_without_starting_candidate(transaction):
    home, root, state, events, candidate, _ = transaction
    state["sha"] = candidate["target"]
    controller.atomic(root / "transaction.json", {**candidate, "phase": "switching"})
    assert controller.bridge_main(home, "recover")["status"] == "rolled_back"
    assert "start:" + candidate["target"] not in events
    assert state["sha"] == candidate["previous"]
