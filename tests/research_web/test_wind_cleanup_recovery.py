"""No lifecycle side effects are available from Wind recovery inspection."""

import copy

import pytest

from research_workbench_entrypoint.resident.evidence import UpdateBlocked

CHECKS = {
    "research_tasks",
    "approvals",
    "questions",
    "source_requests",
    "automation_runs",
    "history_jobs",
    "sdk_aggregate",
    "wind_api",
    "market",
    "reports",
    "datahub_tasks",
    "storage",
    "asset_directory",
    "asset_tasks",
    "directory_tasks",
}


def observation():
    checks = dict.fromkeys(CHECKS, False)
    checks["sdk_aggregate"] = None
    sources = {
        source: {"running": False, "cleanup_unconfirmed": False}
        for source in ("akshare", "baostock", "tinysoft", "wind")
    }
    sources["wind"]["cleanup_unconfirmed"] = True
    return {
        "enabled": True,
        "revision": "a" * 40,
        "active": None,
        "maintenance": False,
        "activity_witness": {
            "schema": "resident-activity-v1",
            "checks": checks,
            "sources": sources,
        },
    }


def test_poison_done_is_only_narrow_observation_not_idle_or_recovery():
    from research_workbench_entrypoint.resident.wind_cleanup_recovery import validate_host_witness

    before = observation()
    assert validate_host_witness(before, "a" * 40) is None
    assert before == observation()


@pytest.mark.parametrize(
    "mutation",
    [
        lambda v: v.pop("activity_witness"),
        lambda v: v["activity_witness"]["sources"]["wind"].update(running=True),
        lambda v: v["activity_witness"]["sources"]["wind"].update(running=None),
        lambda v: v["activity_witness"]["sources"]["tinysoft"].update(running=None),
        lambda v: v["activity_witness"]["checks"].update(market=None),
        lambda v: v["activity_witness"]["checks"].update(research_tasks=True),
        lambda v: v["activity_witness"]["checks"].pop("reports"),
        lambda v: v["activity_witness"]["checks"].update(extra=False),
        lambda v: v["activity_witness"]["sources"]["wind"].update(cleanup_unconfirmed=False),
        lambda v: v.update(active=False),
        lambda v: v.update(active=True),
        lambda v: v.update(revision="b" * 40),
    ],
)
def test_old_host_running_mixed_or_unknown_is_rejected(mutation):
    from research_workbench_entrypoint.resident.wind_cleanup_recovery import validate_host_witness

    value = copy.deepcopy(observation())
    mutation(value)
    with pytest.raises(UpdateBlocked):
        validate_host_witness(value, "a" * 40)


def test_inspect_has_no_apply_or_lifecycle_entry_point():
    from research_workbench_entrypoint.resident import wind_cleanup_recovery as recovery

    assert not hasattr(recovery, "apply")
    assert not hasattr(recovery, "recover")


@pytest.fixture
def inspected_home(tmp_path, monkeypatch):
    import hashlib
    import json
    import sqlite3
    import subprocess
    from types import SimpleNamespace

    from app.research_web.multiuser import resident_binding
    from app.research_web.service_manager import WebServiceManager
    from research_workbench_entrypoint.resident import wind_cleanup_recovery as recovery

    home = tmp_path / "home"
    project = tmp_path / "project"
    primary, disabled = (
        "00000000-0000-0000-0000-000000000001",
        "00000000-0000-0000-0000-000000000002",
    )
    for folder in (
        home,
        home / "resident",
        home / "install",
        home / "server",
        home / "server/users",
        home / "server/users" / primary,
        home / "server/users" / disabled,
        home / "research-web",
        project,
    ):
        folder.mkdir(mode=0o700, parents=True, exist_ok=True)

    def write(path, value):
        path.write_text(json.dumps(value))
        path.chmod(0o600)

    def git(*args):
        return subprocess.check_output(
            ["/usr/bin/git", "-c", "core.hooksPath=/dev/null", "-C", str(project), *args], text=True
        ).strip()

    git("init", "-q")
    git(
        "-c",
        "user.name=Offline Test",
        "-c",
        "user.email=offline@example.invalid",
        "commit",
        "--allow-empty",
        "-qm",
        "fixture",
    )
    expected = git("rev-parse", "HEAD")
    artifact = home / "resident/controller.pyz"
    artifact.write_bytes(b"immutable fixture: never executed")
    artifact.chmod(0o600)
    info = project.stat()
    write(
        home / "resident/config.json",
        {
            "project": str(project),
            "project_identity": [info.st_dev, info.st_ino],
            "node": "/bin/sh",
            "python": "/bin/sh",
            "artifact": str(artifact),
            "artifact_sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
            "web_port": 18088,
            "runtime_port": 13081,
        },
    )
    # /bin/sh can resolve through a system alias; use its exact canonical path.
    from pathlib import Path

    config_path = home / "resident/config.json"
    config = json.loads(config_path.read_text())
    config.update(node=str(Path("/bin/sh").resolve()), python=str(Path("/bin/sh").resolve()))
    write(config_path, config)
    write(home / "install/manifest.json", {"status": "installed", "code_commit": expected})
    write(home / "server/resident.json", {"binding": {"primary_user_id": primary}})
    write(home / "research-web/index.json", {"sessions": {}, "automation_runs": {}})
    database = home / "server/accounts.sqlite3"
    with sqlite3.connect(database) as db:
        db.execute("CREATE TABLE accounts(id TEXT PRIMARY KEY, enabled INTEGER)")
        db.executemany("INSERT INTO accounts VALUES (?, ?)", [(primary, 1), (disabled, 0)])
    database.chmod(0o600)
    value = observation()
    value["revision"] = expected
    calls = []

    def get_json(port, path):
        calls.append(path)
        if path.endswith("resident"):
            return copy.deepcopy(value)
        if path.endswith("runtime"):
            return {"connected": True, "owned_runtime": True, "health_check_passed": True}
        if path.endswith("market"):
            return {"inflight": []}
        pytest.fail("unexpected endpoint")

    monkeypatch.setattr(resident_binding, "get_json", get_json)
    monkeypatch.setattr(
        WebServiceManager,
        "status",
        lambda self: {
            "services": {role: {"ready": True, "running": True} for role in ("web", "runtime")}
        },
    )
    monkeypatch.setattr(
        WebServiceManager, "_service_probes", lambda self: (SimpleNamespace(role="runtime"),)
    )
    monkeypatch.setattr(WebServiceManager, "_active_research_read_only", lambda self, p: [])
    return recovery, home, expected, value, calls, write, disabled


def test_real_binding_and_all_account_inspection_is_read_only_and_still_blocked(inspected_home):
    recovery, home, expected, _value, calls, _write, _disabled = inspected_home
    before = {str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()}
    result = recovery.inspect(home, expected)
    assert result["status"] == "blocked"
    assert result["ordinary_idle_certified"] is False
    assert result["recovery_implemented"] is False
    assert result["account_count"] == 2  # Disabled accounts are included.
    assert calls.count("/api/research/resident") == 2
    assert "/api/research/market" in calls
    assert before == {
        str(p.relative_to(home)): p.read_bytes() for p in home.rglob("*") if p.is_file()
    }
    assert not (home / "server/run").exists()


def test_disabled_account_persisted_activity_is_not_ignored(inspected_home):
    recovery, home, expected, _value, _calls, write, disabled = inspected_home
    root = home / "server/users" / disabled / "research-web"
    root.mkdir(mode=0o700)
    write(root / "index.json", {"sessions": {}, "automations": {"job": {"enabled": True}}})
    with pytest.raises(UpdateBlocked, match="background_active_or_unknown"):
        recovery.inspect(home, expected)


def test_old_host_without_witness_is_rejected_through_real_binding(inspected_home):
    recovery, home, expected, value, _calls, _write, _disabled = inspected_home
    value.pop("activity_witness")
    with pytest.raises(UpdateBlocked, match="activity_unverified"):
        recovery.inspect(home, expected)
    assert not (home / "server/run").exists()


def test_missing_installation_does_not_create_directories(tmp_path):
    from research_workbench_entrypoint.resident import wind_cleanup_recovery as recovery

    home = tmp_path / "absent"
    with pytest.raises(UpdateBlocked):
        recovery.inspect(home, "a" * 40)
    assert not home.exists()


@pytest.mark.parametrize("native", [None, ["active-research"]])
def test_real_binding_native_busy_or_unknown_is_rejected(inspected_home, monkeypatch, native):
    from app.research_web.service_manager import WebServiceManager

    recovery, home, expected, _value, _calls, _write, _disabled = inspected_home
    monkeypatch.setattr(WebServiceManager, "_active_research_read_only", lambda self, probe: native)
    with pytest.raises(UpdateBlocked, match="native_active_or_unknown"):
        recovery.inspect(home, expected)


def test_existing_journal_is_read_only_rejected(inspected_home):
    recovery, home, expected, _value, _calls, write, _disabled = inspected_home
    path = home / "resident/transaction.json"
    write(path, {"phase": "switching"})
    before = path.read_bytes()
    with pytest.raises(UpdateBlocked, match="existing_recovery_pending"):
        recovery.inspect(home, expected)
    assert path.read_bytes() == before


def test_missing_active_field_is_not_explicit_null():
    from research_workbench_entrypoint.resident.wind_cleanup_recovery import validate_host_witness

    value = observation()
    value.pop("active")
    with pytest.raises(UpdateBlocked, match="activity_unverified"):
        validate_host_witness(value, "a" * 40)


def test_existing_dossiers_missing_lock_never_creates_any_home_path(inspected_home):
    recovery, home, expected, _value, _calls, _write, _disabled = inspected_home
    dossiers = home / "research-web/dossiers"
    dossiers.mkdir(mode=0o700)
    (dossiers / "existing-original.bin").write_bytes(b"preserved original")

    def contents():
        return {
            str(p.relative_to(home)): p.read_bytes() if p.is_file() else None
            for p in home.rglob("*")
        }

    before = contents()
    with pytest.raises(UpdateBlocked):
        recovery.inspect(home, expected)
    assert contents() == before
    assert not (home / "research-web/.dossier-retention.lock").exists()
