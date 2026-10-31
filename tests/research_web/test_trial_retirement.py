"""Synthetic stopped homes only: no live launchd, provider or model operations."""

import json
import sqlite3
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident import model_provider_upgrade as upgrade
from research_workbench_entrypoint.resident import trial_discard_backup as backup
from research_workbench_entrypoint.resident import trial_retirement as trial
from research_workbench_entrypoint.resident.admission import file_lock
from research_workbench_entrypoint.resident.evidence import UpdateBlocked


@pytest.fixture
def stopped_home(tmp_path, monkeypatch):
    home = tmp_path.resolve() / "synthetic-home"
    server, root = home / "server", home / "resident"
    for path in (server / "run", server / "users", root):
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    primary = str(uuid4())
    with sqlite3.connect(server / "accounts.sqlite3") as db:
        db.execute("CREATE TABLE accounts (id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO accounts VALUES (?)", (primary,))
    (server / "resident.json").write_text(json.dumps({"binding": {"primary_user_id": primary}}))
    data = home / "research-web"
    data.mkdir()
    original = {
        "sessions": {"trial": {"status": "running"}},
        "models": {"provider": "keep"},
        "watchlists": ["keep"],
        "provider_config": {"Wind": "keep"},
    }
    (data / "index.json").write_text(json.dumps(original))
    for directory in (data / "sessions", data / "runtime/home/sessions"):
        directory.mkdir(parents=True)
        (directory / "trial.json").write_text('{"historical":"never resend"}')
    safe = tmp_path.resolve() / "safe-backups"
    safe.mkdir(mode=0o700)
    lease = object()
    probes = [
        SimpleNamespace(role=role, process="missing", port_state="closed")
        for role in ("web", "runtime")
    ]

    def assert_scope(value):
        assert value is lease

    manager = SimpleNamespace(
        _assert_installation_scope=assert_scope, _service_probes=lambda: probes
    )
    state = {
        "mode": trial.MODE,
        "transaction": str(uuid4()),
        "config": {"web_port": 3081, "runtime_port": 8088},
    }

    class FixtureOperations(upgrade.Operations):
        def checkpoint(self, state, phase):
            state["phase"] = phase
            upgrade.c.atomic(server / "run/gateway-upgrade.json", state)

    ops = FixtureOperations(home, state, manager, lease, SimpleNamespace(retain=True))
    upgrade.c.atomic(root / "transaction.json", {"phase": "switching"})
    monkeypatch.setattr(upgrade.g, "no_private_processes", lambda _server: None)
    monkeypatch.setattr(upgrade.g, "job_state", lambda: None)
    monkeypatch.setattr(upgrade.g, "listener_pids", lambda: set())
    monkeypatch.setattr(upgrade, "ports_are_free", lambda _ports: True)
    info = home.stat()
    manifest = {
        "version": 1,
        "profile": trial.MODE,
        "previous": trial.PREVIOUS,
        "payload": trial.PAYLOAD,
        "home_identity": [info.st_dev, info.st_ino],
        "inventory_seal": backup.preview(home)["seal"],
        "scope_sha256": trial.digest(trial.scope_snapshot(home)),
        "authorization": trial.CONSENT,
        "scope": "all_historical_rwb_trial_sessions",
        "wind_cleanup": "UNKNOWN_ACCEPTED_NO_NATIVE_ACK",
        "preserve": ["accounts", "models", "non_session_business_data"],
    }
    with ExitStack() as stack:
        for directory, name in (
            (root, "supervisor.lock"),
            (root, "admission.lock"),
            (server / "run", "operator.lock"),
        ):
            stack.enter_context(file_lock(directory, name, exclusive=True))
        yield SimpleNamespace(
            ops=ops, manifest=manifest, safe=safe, data=data, original=original, probes=probes
        )


def test_actual_offline_apply_resume_restore(stopped_home):
    f = stopped_home
    (f.data / "sessions/empty.jsonl").write_bytes(b"")
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    account_bytes = (f.ops.server / "accounts.sqlite3").read_bytes()
    original_bytes = (f.data / "index.json").read_bytes()
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    result = trial.apply(f.ops)
    assert result["status"] == "retired_offline"
    assert result["native_cleanup"] == "UNKNOWN"
    expected = {**f.original, "sessions": {}}
    assert json.loads((f.data / "index.json").read_bytes()) == expected
    assert list((f.data / "sessions").iterdir()) == []
    assert list((f.data / "runtime/home/sessions").iterdir()) == []
    trial.validate_retired(f.ops.home, result, transaction=f.ops.state["transaction"])
    assert trial.apply(f.ops)["status"] == "retired_offline"
    assert trial.apply(f.ops, restoring=True)["status"] == "restored"
    assert (f.data / "index.json").read_bytes() == original_bytes
    assert (f.ops.server / "accounts.sqlite3").read_bytes() == account_bytes
    assert (f.data / "sessions/trial.json").is_file()
    assert (f.data / "sessions/empty.jsonl").read_bytes() == b""
    assert trial.apply(f.ops, restoring=True)["status"] == "restored"


def test_v2_actual_retirement_preserves_config_and_resumes(stopped_home):
    f = stopped_home
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    accounts = (f.ops.server / "accounts.sqlite3").read_bytes()
    record = trial.prepare(
        f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
    )
    assert record["version"] == 2
    trial.validate_record(record)
    trial.apply(f.ops)
    trial.validate_retired(f.ops.home, record, transaction=f.ops.state["transaction"])
    assert trial.apply(f.ops)["status"] == "retired_offline"
    assert (f.ops.server / "accounts.sqlite3").read_bytes() == accounts
    assert json.loads((f.data / "index.json").read_bytes()) == {**f.original, "sessions": {}}
    trial.apply(f.ops, restoring=True)
    assert (f.data / "sessions/trial.json").is_file()


def test_v2_oversized_journal_rejected_before_backup(stopped_home):
    f = stopped_home
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    f.ops.state["synthetic_large_field"] = "x" * 16_000_000
    with pytest.raises(UpdateBlocked, match="journal_oversized"):
        trial.prepare(
            f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
        )
    assert list(f.safe.iterdir()) == []
    assert "trial_retirement" not in f.ops.state


def test_v2_rejects_hardlinked_trial_file_before_backup(stopped_home):
    import os

    f = stopped_home
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    os.link(f.data / "sessions/trial.json", f.data / "sessions/alias.json")
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    with pytest.raises(UpdateBlocked, match="hardlink"):
        trial.prepare(
            f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
        )
    assert list(f.safe.iterdir()) == []


def test_v2_policy_cannot_be_selected_by_old_operator(stopped_home):
    f = stopped_home
    with pytest.raises(UpdateBlocked, match="policy_mode_mismatch"):
        trial.prepare(
            f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
        )
    assert list(f.safe.iterdir()) == []


def test_v2_rename_budget_covers_large_aggregate_without_raising_copy_cap():
    original_copy_cap = backup.MAX_TOTAL_BYTES
    plan = [
        {
            "directories": [
                {"files": {str(i): {"size": 60000} for i in range(6000)}} for _ in range(2)
            ]
        }
    ]
    trial._archive_budget(plan, trial.ARCHIVE_POLICY_V2)
    assert original_copy_cap == backup.MAX_TOTAL_BYTES == 512 * 1024**2
    plan[0]["directories"][0]["files"]["0"]["size"] = 2 * 1024**3
    with pytest.raises(UpdateBlocked, match="archive_budget_exceeded"):
        trial._archive_budget(plan, trial.ARCHIVE_POLICY_V2)


def test_v2_real_sparse_archives_exceed_old_aggregate_without_copying(stopped_home):
    """Real filesystem reads/rename, with sparse fixtures avoiding disk allocation."""
    f = stopped_home
    sources = []
    for folder in (f.data / "sessions", f.data / "runtime/home/sessions"):
        for number in range(8):
            path = folder / f"sparse-{number}.bin"
            with path.open("wb") as stream:
                stream.truncate(40 * 1024**2)
            sources.append((path, path.stat().st_ino))
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    with pytest.raises(UpdateBlocked, match="archive_budget_exceeded"):
        trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert "trial_retirement" not in f.ops.state
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    record = trial.prepare(
        f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
    )
    assert (
        sum(
            value["size"]
            for row in record["plan"]
            for directory in row["directories"]
            for value in directory["files"].values()
        )
        > backup.MAX_TOTAL_BYTES
    )
    trial.apply(f.ops)
    trial.validate_retired(f.ops.home, record, transaction=f.ops.state["transaction"])
    for path, inode in sources:
        archived = path.parent.with_name(".trial-retired-" + f.ops.state["transaction"]) / path.name
        assert archived.stat().st_ino == inode
        assert archived.stat().st_size == 40 * 1024**2
        assert not path.exists()


@pytest.mark.parametrize("change", ["policy", "version", "late_hardlink"])
def test_v2_resume_does_not_accept_changed_policy_or_file_alias(stopped_home, change):
    import os

    f = stopped_home
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    record = trial.prepare(
        f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
    )
    if change == "policy":
        record["archive_policy"]["max_entries"] += 1
    elif change == "version":
        record["version"] = 1
    else:
        os.link(f.data / "sessions/trial.json", f.data / "outside-trial.json")
    with pytest.raises(UpdateBlocked):
        trial.apply(f.ops)
    assert json.loads((f.data / "index.json").read_bytes()) == f.original


def test_v2_manifest_limit_and_entry_limit_are_independent():
    plan = [{"directories": [{"files": {"x" * (8 * 1024**2): {"size": 0}}}]}]
    with pytest.raises(UpdateBlocked, match="manifest_budget_exceeded"):
        trial._archive_budget(plan, trial.ARCHIVE_POLICY_V2)
    plan = [{"directories": [{"files": {str(i): {"size": 0} for i in range(32769)}}]}]
    with pytest.raises(UpdateBlocked, match="archive_budget_exceeded"):
        trial._archive_budget(plan, trial.ARCHIVE_POLICY_V2)


def test_v2_manifest_accounts_for_future_replacement_identity_before_copy(
    stopped_home, monkeypatch
):
    f = stopped_home
    f.ops.state["mode"] = trial.SUCCESSOR_MODE
    real_budget = trial._archive_budget
    observed = []

    def boundary_budget(plan, policy):
        real_budget(plan, policy)
        identities = [d["replacement_identity"] for row in plan for d in row["directories"]]
        observed.append(identities)
        if any(identity is not None for identity in identities):
            raise UpdateBlocked("trial_retirement_manifest_budget_exceeded")

    monkeypatch.setattr(trial, "_archive_budget", boundary_budget)
    with pytest.raises(UpdateBlocked, match="manifest_budget_exceeded"):
        trial.prepare(
            f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
        )
    assert len(observed) == 2
    assert all(value is None for value in observed[0])
    assert all(value is not None for value in observed[1])
    assert list(f.safe.iterdir()) == []
    assert not list(f.data.glob(".trial-*"))


@pytest.mark.parametrize(
    "field,value",
    [
        ("authorization", "idle"),
        ("wind_cleanup", "PASS"),
        ("payload", "0" * 40),
        ("scope", "selected"),
    ],
)
def test_explicit_consent_is_exact(stopped_home, field, value):
    f = stopped_home
    bad = {**f.manifest, field: value}
    with pytest.raises(UpdateBlocked, match="consent_mismatch"):
        trial.prepare(f.ops, bad, trial.digest(bad), f.safe)
    assert list(f.safe.iterdir()) == []


@pytest.mark.parametrize("boundary", ["writer", "port", "gateway", "lease", "birth"])
def test_writer_boundary_cannot_be_declared_idle(stopped_home, monkeypatch, boundary):
    f = stopped_home
    if boundary == "writer":
        f.probes[0].process = "alive"
    elif boundary == "port":
        monkeypatch.setattr(upgrade, "ports_are_free", lambda _ports: False)
    elif boundary == "gateway":
        monkeypatch.setattr(upgrade.g, "job_state", lambda: "running")
    elif boundary == "lease":
        f.ops.lease = object()
    else:
        f.ops.fence.retain = False
    with pytest.raises((UpdateBlocked, AssertionError)):
        trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert list(f.safe.iterdir()) == []


def test_held_locks_required(stopped_home):
    path = stopped_home.safe / "unheld.lock"
    path.write_bytes(b"")
    path.chmod(0o600)
    with pytest.raises(UpdateBlocked, match="lock_not_held"):
        trial._held(path)


def test_actual_crash_after_archive_rename_resumes(stopped_home, monkeypatch):
    f = stopped_home
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    original_replace = trial._replace

    def interrupted(*args):
        raise OSError("synthetic power loss")

    monkeypatch.setattr(trial, "_replace", interrupted)
    with pytest.raises(OSError):
        trial.apply(f.ops)
    assert list((f.data / "sessions").iterdir()) == []
    assert json.loads((f.data / "index.json").read_bytes())["sessions"]
    monkeypatch.setattr(trial, "_replace", original_replace)
    assert trial.apply(f.ops)["status"] == "retired_offline"


def test_archive_drift_blocks_resume(stopped_home):
    f = stopped_home
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    (f.data / "sessions/trial.json").write_text("changed")
    with pytest.raises(UpdateBlocked, match="archive_changed"):
        trial.apply(f.ops)


def test_backup_drift_and_path_escape_refused(stopped_home):
    f = stopped_home
    record = trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    record["plan"][0]["directories"][0]["relative"] = "../outside"
    record["plan_sha256"] = trial.digest({"plan": record["plan"]})
    with pytest.raises(UpdateBlocked, match="plan_invalid"):
        trial.apply(f.ops)
    record["plan"][0]["directories"][0]["relative"] = "research-web/sessions"
    record["plan_sha256"] = trial.digest({"plan": record["plan"]})
    point = Path(record["backup"]["backup"])
    (point / "research-web/index.json").write_text("{}")
    with pytest.raises(UpdateBlocked, match="backup_changed"):
        trial.apply(f.ops)


def test_directory_appearing_after_prepare_blocks(stopped_home):
    f = stopped_home
    absent = f.data / "runtime/home/sessions"
    (absent / "trial.json").unlink()
    absent.rmdir()
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    absent.mkdir()
    with pytest.raises(UpdateBlocked, match="directory_state_unknown"):
        trial.apply(f.ops)


def test_symlink_archive_source_refused(stopped_home):
    f = stopped_home
    path = f.data / "sessions/link"
    path.symlink_to(f.data / "index.json")
    with pytest.raises((backup.TrialBackupBlocked, RuntimeError, UpdateBlocked)):
        trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert json.loads((f.data / "index.json").read_text())["sessions"]


def test_scope_projections_do_not_overwrite_original():
    before = {
        "primary": {
            "sessions": {"s": "hash"},
            "files": {
                "sessions/a": "s",
                "runtime/home/sessions/b": "r",
                ".control/snapshots/x": "keep",
            },
            "models_hash": "keep",
        },
        "private": {},
        "accounts": "keep",
    }
    expected = trial.preservation_delta(before)
    assert expected["primary"]["sessions"] == {}
    assert expected["primary"]["files"] == {".control/snapshots/x": "keep"}
    assert before["primary"]["sessions"] == {"s": "hash"}
    assets = {"primary": {"sessions": "old", "watchlists": "keep"}, "private": {}}
    assert trial.asset_delta(assets)["primary"] == {
        "sessions": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
        "watchlists": "keep",
    }
    assert assets["primary"]["sessions"] == "old"


def test_recreated_directory_does_not_discard_new_work_on_rollback(stopped_home):
    f = stopped_home
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    trial.apply(f.ops)
    fresh = f.data / "sessions"
    (fresh / "new.json").write_text("new work protected")
    with pytest.raises(UpdateBlocked, match="replacement_changed"):
        trial.apply(f.ops, restoring=True)
    assert (fresh / "new.json").read_text() == "new work protected"


def test_swapped_empty_replacement_inode_is_not_adopted(stopped_home):
    f = stopped_home
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    trial.apply(f.ops)
    fresh = f.data / "sessions"
    fresh.rename(f.data / "other-protected-directory")
    fresh.mkdir()
    with pytest.raises(UpdateBlocked, match="directory_changed"):
        trial.apply(f.ops, restoring=True)
    assert fresh.is_dir()
    assert (f.data / "other-protected-directory").is_dir()


def test_index_missing_root_native_history_is_retired(stopped_home):
    f = stopped_home
    secondary = str(uuid4())
    with sqlite3.connect(f.ops.server / "accounts.sqlite3") as db:
        db.execute("INSERT INTO accounts VALUES (?)", (secondary,))
    secondary_root = f.ops.server / "users" / secondary / "research-web"
    directory = secondary_root / "runtime/home/sessions"
    directory.mkdir(parents=True)
    (directory / "trial.json").write_text("orphan historical native session")
    f.manifest["inventory_seal"] = backup.preview(f.ops.home)["seal"]
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    result = trial.apply(f.ops)
    assert result["plan"][1]["index_present"] is False
    assert not (secondary_root / "index.json").exists()
    assert list(directory.iterdir()) == []
    trial.apply(f.ops, restoring=True)
    assert (directory / "trial.json").is_file()


def test_pre_signal_authorization_allows_only_trial_termination_deltas(stopped_home):
    f = stopped_home
    initial_seal = f.manifest["inventory_seal"]
    trial.authorize(f.ops.home, f.manifest, trial.digest(f.manifest))
    f.ops.state["before"] = upgrade.g.preservation(f.ops.home)
    index = json.loads((f.data / "index.json").read_text())
    index["sessions"]["trial"].update(
        status="interrupted", updated_at=123, failure_code="service_stopped"
    )
    (f.data / "index.json").write_text(json.dumps(index))
    assert backup.preview(f.ops.home)["seal"] != initial_seal
    record = trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert record["backup"]["source_seal"] != initial_seal
    assert record["authorization"]["inventory_seal"] == initial_seal
    assert (
        trial.preservation_baseline(f.ops.state["before"], record) == record["stopped_preservation"]
    )
    trial.apply(f.ops)
    trial.validate_retired(f.ops.home, record, transaction=f.ops.state["transaction"])
    trial.apply(f.ops, restoring=True)
    restored = json.loads((f.data / "index.json").read_text())
    assert restored["sessions"]["trial"]["status"] == "interrupted"


@pytest.mark.parametrize(
    "change", ["new_sid", "native_sid", "account", "model", "watchlist", "session_payload"]
)
def test_pre_signal_scope_rejects_unrelated_changes(stopped_home, change):
    f = stopped_home
    trial.authorize(f.ops.home, f.manifest, trial.digest(f.manifest))
    index = json.loads((f.data / "index.json").read_text())
    if change == "new_sid":
        index["sessions"]["another"] = {"status": "running"}
    elif change == "native_sid":
        (f.data / "runtime/home/sessions/new-session.json").write_text("new native work")
    elif change == "account":
        with sqlite3.connect(f.ops.server / "accounts.sqlite3") as db:
            db.execute("INSERT INTO accounts VALUES (?)", (str(uuid4()),))
    elif change == "model":
        index["models"]["provider"] = "changed"
    elif change == "watchlist":
        index["watchlists"].append("new")
    else:
        index["sessions"]["trial"]["prompt"] = "different request"
    (f.data / "index.json").write_text(json.dumps(index))
    with pytest.raises(UpdateBlocked, match="consent_mismatch"):
        trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert list(f.safe.iterdir()) == []


@pytest.mark.asyncio
async def test_retired_real_restart_interfaces_do_not_schedule_old_trials(
    stopped_home, monkeypatch
):
    from app.research_web.automation.service import AutomationService
    from app.research_web.report_workflows.catalog import ReportWorkflowService
    from app.research_web.report_workflows.runtime import ReportWorkflowRuntime
    from app.research_web.store import Store

    f = stopped_home
    monkeypatch.delenv("RESEARCH_RESIDENT_HOME", raising=False)
    index = json.loads((f.data / "index.json").read_text())
    index.update(
        report_runs={
            "store-report": {"session_id": "trial", "workflow_id": "weekly", "status": "running"}
        },
        report_schedules={
            "schedule": {
                "workflow_id": "weekly",
                "enabled": True,
                "next_run_at": "2000-01-01T00:00:00+00:00",
            }
        },
        automations={
            "auto": {"id": "auto", "enabled": True, "next_run_at": "2000-01-01T00:00:00+00:00"}
        },
        automation_runs={
            "auto-run": {
                "id": "auto-run",
                "automation_id": "auto",
                "session_id": "trial",
                "research_status": "running",
                "delivery_status": "pending",
            }
        },
    )
    (f.data / "index.json").write_text(json.dumps(index))
    Store(f.data).save()
    catalog_path = f.data / "report-workflows/catalog.json"
    catalog_path.parent.mkdir()
    catalog = {
        "schema_version": 1,
        "workflows": {
            "weekly": {
                "id": "weekly",
                "status": "enabled",
                "schedule": {"enabled": True, "next_run_at": "2000-01-01T00:00:00+00:00"},
            }
        },
        "runs": {
            "workflow-run": {
                "id": "workflow-run",
                "workflow_id": "weekly",
                "session_id": "trial",
                "weekly_data_contract": True,
                "status": "running",
            }
        },
    }
    catalog_path.write_text(json.dumps(catalog))
    original_catalog, original_index = (
        catalog_path.read_bytes(),
        (f.data / "index.json").read_bytes(),
    )
    f.manifest["inventory_seal"] = backup.preview(f.ops.home)["seal"]
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    record = trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    trial.apply(f.ops)
    retired_index = json.loads((f.data / "index.json").read_text())
    retired_catalog = json.loads(catalog_path.read_text())
    assert retired_index["automation_runs"]["auto-run"]["research_status"] == "interrupted"
    assert retired_index["report_runs"]["store-report"]["status"] == "cancelled"
    assert retired_index["automations"]["auto"]["enabled"] is False
    assert retired_catalog["runs"]["workflow-run"]["monitoring_disposition"] == "ended_by_user"
    assert retired_catalog["workflows"]["weekly"]["schedule"]["enabled"] is False
    assert upgrade.asset_index_snapshot(f.ops.home) == trial.asset_delta(
        record["stopped_asset_index"], record
    )

    def forbidden(*_args, **_kwargs):
        pytest.fail("retired producer attempted execution or model replay")

    service = SimpleNamespace(create=forbidden, send=forbidden, detail=forbidden)
    automation = AutomationService(
        Store(f.data),
        research=service,
        scheduler=False,
        executor=forbidden,
        resume_executor=forbidden,
    )
    await automation.start()
    await automation.tick()
    assert automation.tasks == {}
    await automation.close()
    workflow = ReportWorkflowRuntime(service, ReportWorkflowService(f.data), None)
    await workflow._recover_weekly_runs()
    await workflow.tick()
    assert workflow.tasks == {}
    await workflow.close()
    trial.validate_retired(f.ops.home, record, transaction=f.ops.state["transaction"])
    trial.apply(f.ops, restoring=True)
    assert catalog_path.read_bytes() == original_catalog
    assert (f.data / "index.json").read_bytes() == original_index
    with pytest.raises(UpdateBlocked, match="not_committed"):
        trial.validate_retired(f.ops.home, record, transaction=f.ops.state["transaction"])


@pytest.mark.parametrize(
    "namespace",
    [
        "report_runs",
        "report_schedules",
        "automations",
        "automation_runs",
        "discovery_tracks",
        "catalog",
    ],
)
def test_unlinked_active_producer_blocks_before_retirement(stopped_home, namespace):
    f = stopped_home
    if namespace == "catalog":
        path = f.data / "report-workflows/catalog.json"
        path.parent.mkdir()
        path.write_text('{"workflows":{"unknown":{"schedule":{"enabled":true}}},"runs":{}}')
    else:
        index = json.loads((f.data / "index.json").read_text())
        index[namespace] = {
            "trial-producer": {"enabled": True, "status": "running", "research_status": "running"}
        }
        (f.data / "index.json").write_text(json.dumps(index))
    f.manifest["inventory_seal"] = backup.preview(f.ops.home)["seal"]
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(f.ops.home))
    with pytest.raises(UpdateBlocked, match="producer_scope_unknown"):
        trial.prepare(f.ops, f.manifest, trial.digest(f.manifest), f.safe)
    assert (f.data / "sessions/trial.json").is_file()
    assert "trial_retirement" not in f.ops.state
