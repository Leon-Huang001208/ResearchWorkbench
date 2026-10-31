"""Synthetic operator transactions: no live home, process signals or providers."""

import json
import signal
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_trial_retirement import stopped_home

from research_workbench_entrypoint import web_contract as native
from research_workbench_entrypoint.resident import model_provider_upgrade as u
from research_workbench_entrypoint.resident import trial_retirement as trial
from research_workbench_entrypoint.resident import trial_successor as successor

__all__ = ["stopped_home"]


@pytest.fixture
def retired_retry_home(stopped_home, monkeypatch):
    f = stopped_home
    f.ops.state.update(
        mode=u.TRIAL_SUCCESSOR_MODE,
        transaction=successor.TRANSACTION,
        previous=trial.PREVIOUS,
        target=trial.PAYLOAD,
    )
    record = trial.prepare(
        f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
    )
    trial.apply(f.ops)
    receipt = {
        "version": 1,
        "kind": "completed-trial-retirement",
        "mode": u.TRIAL_SUCCESSOR_MODE,
        "transaction": successor.TRANSACTION,
        "previous": trial.PREVIOUS,
        "payload": trial.PAYLOAD,
        "result": {"status": "rolled_back", "revision": trial.PREVIOUS},
        "journal": f.ops.state,
    }
    folder = f.ops.root / "trial-retirements"
    folder.mkdir(mode=0o700)
    path = folder / (successor.TRANSACTION + ".json")
    u.c.atomic(path, receipt)
    u.c.atomic(f.ops.root / "quarantine.json", {"sha": trial.PAYLOAD})
    # These unit cases isolate retry binding; full stage/CLI tests own provenance.
    monkeypatch.setattr(successor, "verify_handoff", lambda *_: None)
    return f, path, record


def test_fresh_retry_requires_completed_retirement_and_preserves_failed_marker(retired_retry_home):
    from uuid import uuid4

    f, path, _ = retired_retry_home
    marker = f.ops.root / "quarantine.json"
    original = marker.read_bytes(), marker.stat().st_ino
    retry = u.trial_successor_retry_preflight(f.ops.home, path)
    state = {
        "version": 5,
        "mode": u.TRIAL_SUCCESSOR_MODE,
        "previous": trial.PREVIOUS,
        "target": trial.PAYLOAD,
        "transaction": str(uuid4()),
        "executor_revision": "e" * 40,
        "trial_authorization_sha256": "a" * 64,
        "successor": {**retry, "authorization_sha256": "a" * 64},
    }
    u.verify_trial_successor_fresh(f.ops.home, state, {"executor_revision": "e" * 40})
    assert (marker.read_bytes(), marker.stat().st_ino) == original


@pytest.mark.parametrize("damage", ["path", "result", "new_work", "quarantine"])
def test_fresh_retry_rejects_unclosed_or_changed_objects(retired_retry_home, damage):
    f, path, _ = retired_retry_home
    if damage == "path":
        path = path.with_name("wrong.json")
    elif damage == "result":
        receipt = json.loads(path.read_bytes())
        receipt["result"]["status"] = "deployed"
        u.c.atomic(path, receipt)
    elif damage == "new_work":
        (f.data / "sessions/new-work.json").write_text("new research")
    else:
        u.c.atomic(f.ops.root / "quarantine.json", {"sha": "f" * 40})
    with pytest.raises(u.UpdateBlocked):
        u.trial_successor_retry_preflight(f.ops.home, path)


def test_fresh_retry_receipt_required_before_reading_home(tmp_path, monkeypatch):
    monkeypatch.setattr(u.c, "configured", lambda *_: pytest.fail("home was read"))
    with pytest.raises(u.UpdateBlocked, match="retry_receipt_required"):
        u.operate(tmp_path, mode=u.TRIAL_SUCCESSOR_MODE)


def test_fresh_retry_cli_forwards_exact_admission_flags(tmp_path, monkeypatch):
    (tmp_path / "logs").mkdir()
    captured = {}
    output = []
    monkeypatch.setattr(u, "print", output.append, raising=False)

    def operate(home, source, **kwargs):
        captured.update(home=home, source=source, **kwargs)
        return {"status": "deployed"}

    monkeypatch.setattr(u, "operate", operate)
    assert (
        u.main(
            [
                "apply-trial-retirement-v2",
                "--home",
                str(tmp_path),
                "--source",
                str(tmp_path),
                "--trial-terminal-receipt",
                str(tmp_path / "completed.json"),
                "--trial-manifest",
                str(tmp_path / "consent.json"),
                "--trial-manifest-sha256",
                "a" * 64,
                "--trial-backup-parent",
                str(tmp_path / "backups"),
            ]
        )
        == 0
    )
    assert json.loads(output[0])["status"] == "deployed"
    assert captured["mode"] == u.TRIAL_SUCCESSOR_MODE
    assert captured["trial_terminal_receipt"] == tmp_path / "completed.json"
    assert captured["trial_manifest_sha256"] == "a" * 64


def test_old_cli_cannot_use_new_retry_receipt(tmp_path, monkeypatch):
    (tmp_path / "logs").mkdir()
    output = []
    monkeypatch.setattr(u, "print", output.append, raising=False)
    monkeypatch.setattr(u.c, "configured", lambda *_: pytest.fail("home was read"))
    assert (
        u.main(
            [
                "apply-trial-retirement",
                "--home",
                str(tmp_path),
                "--trial-terminal-receipt",
                str(tmp_path / "completed.json"),
            ]
        )
        == 1
    )
    assert json.loads(output[0]) == {
        "status": "blocked",
        "reason": "trial_successor_retry_flags_forbidden",
    }


def test_module_cli_uses_same_guarded_operations_class_before_home_read():
    import subprocess

    code = """
import argparse, importlib, json, runpy, sys
name = 'research_workbench_entrypoint.resident.model_provider_upgrade'
def parse(self, *args, **kwargs):
    canonical = importlib.import_module(name)
    print(json.dumps({'same': canonical.Operations is sys.modules['__main__'].Operations}))
    raise SystemExit(0)
argparse.ArgumentParser.parse_args = parse
runpy.run_module(name, run_name='__main__', alter_sys=True)
"""
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[2],
        text=True,
        capture_output=True,
        timeout=15,
        check=True,
    )
    assert json.loads(result.stdout) == {"same": True}


def test_fresh_forward_uses_quiesce_and_graceful_actions_instead_of_legacy_signals(
    tmp_path, monkeypatch
):
    state = {
        "mode": u.TRIAL_SUCCESSOR_MODE,
        "target": trial.PAYLOAD,
        "successor": {"origin": "fresh_apply", "observe_only": False},
    }
    ops = u.Operations(tmp_path, state, None, None, None)
    calls = []
    monkeypatch.setattr(
        successor, "stop_fresh_gateway", lambda owner: calls.append("gateway"), raising=False
    )
    monkeypatch.setattr(
        successor, "stop_fresh_primary", lambda owner: calls.append("primary"), raising=False
    )
    monkeypatch.setattr(ops, "idle", lambda: True)
    monkeypatch.setattr(
        ops, "retire_trial_process", lambda *_: pytest.fail("legacy signal sequence")
    )
    for action in ("stop_gateway", "stop_primary", "rollback_gateway", "rollback_primary"):
        ops.action(action, state)
    assert calls == ["gateway", "primary", "gateway", "primary"]


def test_successor_spawn_identity_and_observation_flag_commit_together(stopped_home, monkeypatch):
    from contextlib import nullcontext

    f = stopped_home
    f.ops.state.update(mode=u.TRIAL_SUCCESSOR_MODE, target=trial.PAYLOAD)
    trial.prepare(
        f.ops, f.manifest, trial.digest(f.manifest), f.safe, archive_policy="rename-only-v2"
    )
    trial.apply(f.ops)
    f.ops.state["successor"] = {"origin": "handoff", "observe_only": True}
    calls = []
    f.ops.manager._start_installed = lambda *args, **kwargs: calls.append("spawn")
    monkeypatch.setattr(u.c, "fixed_ports", lambda *_: nullcontext())
    monkeypatch.setenv("RESEARCH_RESIDENT_REVISION", "synthetic-before")

    def capture(roles):
        assert roles == ("web", "runtime")
        assert f.ops.state["successor"]["observe_only"] is False
        f.ops.state["trial_processes"] = {"web": {"pid": 12345}}
        f.ops.confirm_successor_spawn(roles)
        f.ops.checkpoint(f.ops.state, "start_primary")
        calls.append("identity-and-flag")

    monkeypatch.setattr(f.ops, "capture_trial_processes", capture)
    f.ops.start_primary(False)
    saved = json.loads((f.ops.server / "run/gateway-upgrade.json").read_bytes())
    assert saved["successor"]["observe_only"] is False
    assert saved["trial_processes"]["web"]["pid"] == 12345
    assert calls == ["spawn", "identity-and-flag"]


@pytest.mark.parametrize(
    "operation", ["check_trial_processes", "stop_gateway", "stop_trial_primary"]
)
def test_successor_unconfirmed_spawn_never_interprets_missing_probe_as_absence(
    tmp_path, monkeypatch, operation
):
    state = {
        "mode": u.TRIAL_SUCCESSOR_MODE,
        "phase": "start_primary",
        "successor": {
            "origin": "fresh_apply",
            "spawn_attempts": [{"roles": ["web", "runtime"], "status": "pending"}],
        },
    }
    ops = u.Operations(tmp_path, state, None, None, None)
    monkeypatch.setattr(
        successor,
        "stop_fresh_gateway",
        lambda *_: pytest.fail("unknown spawn mutated gateway"),
        raising=False,
    )
    monkeypatch.setattr(
        successor,
        "stop_fresh_primary",
        lambda *_: pytest.fail("unknown spawn mutated primary"),
        raising=False,
    )
    with pytest.raises(u.UpdateBlocked, match="spawn_identity_unconfirmed"):
        getattr(ops, operation)()


def test_fixed_product_is_separate_from_executor_and_old_profiles():
    assert u.previous_for(u.TRIAL_MODE) == trial.PREVIOUS
    assert u.TRIAL_PAYLOAD == trial.PAYLOAD
    assert u.TRIAL_MODE not in u.ASSET_MODES
    assert u.previous_for(u.MARKET_BREADTH_MODE) == trial.PREVIOUS


@pytest.mark.parametrize(
    "recovering,mode,kwargs,reason",
    [
        (False, u.TRIAL_MODE, {}, "authorization_required"),
        (False, u.MODE, {"trial_manifest": Path("consent.json")}, "flags_forbidden"),
        (True, u.TRIAL_MODE, {"trial_manifest_sha256": "a" * 64}, "flags_forbidden"),
    ],
)
def test_cli_authorization_rejected_before_any_home_read(
    tmp_path, monkeypatch, recovering, mode, kwargs, reason
):
    monkeypatch.setattr(u.c, "configured", lambda *_: pytest.fail("home was read"))
    with pytest.raises(u.UpdateBlocked, match=reason):
        u.operate(tmp_path, recovering=recovering, mode=mode, **kwargs)


def test_product_review_rejects_arbitrary_payload_before_git(tmp_path, monkeypatch):
    monkeypatch.setattr(u.c, "git", lambda *_: pytest.fail("git was read"))
    with pytest.raises(u.UpdateBlocked, match="product_changed"):
        u.review(tmp_path, "a" * 40, u.TRIAL_MODE)


def test_trial_idle_uses_abort_scope_without_any_activity_probe(tmp_path, monkeypatch):
    ops = u.Operations(tmp_path, {"mode": u.TRIAL_MODE}, None, None, None)
    checked = []
    monkeypatch.setattr(ops, "check_trial_processes", lambda: checked.append("identity"))
    monkeypatch.setattr(
        u, "request_json", lambda *_: pytest.fail("active null is not an idle prerequisite")
    )
    assert ops.idle() is True
    assert checked == ["identity"]


def signal_ops(tmp_path, monkeypatch):
    observed = {"alive": True}
    ops = u.Operations(
        tmp_path,
        {"mode": u.TRIAL_MODE, "phase": "stop_primary", "trial_processes": {"web": {"pid": 12345}}},
        SimpleNamespace(_assert_installation_scope=lambda lease: None),
        object(),
        SimpleNamespace(retain=True),
    )
    events = []
    monkeypatch.setattr(ops, "assert_trial_control_scope", lambda: None)
    monkeypatch.setattr(
        native,
        "probe_process",
        lambda pid: SimpleNamespace(state="alive" if observed["alive"] else "missing"),
    )
    monkeypatch.setattr(ops, "check_trial_processes", lambda: events.append("revalidate"))
    monkeypatch.setattr(u.g, "no_children", lambda pid: events.append("children"))
    monkeypatch.setattr(
        ops,
        "checkpoint",
        lambda state, phase: events.append(("durable", list(state["trial_signal_intents"]))),
    )
    monkeypatch.setattr(u.os, "kill", lambda pid, number: events.append(("signal", pid, number)))
    return ops, events, observed


def test_abort_signal_has_durable_intent_and_two_identity_checks(tmp_path, monkeypatch):
    ops, events, _ = signal_ops(tmp_path, monkeypatch)
    ops.trial_signal("web", signal.SIGTERM)
    assert events == [
        "revalidate",
        "children",
        ("durable", ["web:15"]),
        "revalidate",
        "children",
        ("signal", 12345, signal.SIGTERM),
    ]
    assert ops.state["trial_outcome"] == "USER_AUTHORIZED_TRIAL_ABORT"
    with pytest.raises(u.MaintenanceBusy, match="outcome_unknown"):
        ops.trial_signal("web", signal.SIGTERM)
    assert (
        len([event for event in events if isinstance(event, tuple) and event[0] == "signal"]) == 1
    )


def test_drift_after_durable_intent_never_signals(tmp_path, monkeypatch):
    ops, events, _ = signal_ops(tmp_path, monkeypatch)

    def checkpoint(state, phase):
        def changed():
            raise u.UpdateBlocked("identity_changed")

        monkeypatch.setattr(ops, "check_trial_processes", changed)

    monkeypatch.setattr(ops, "checkpoint", checkpoint)
    ops.state["trial_signal_intents"] = ["web:15"]
    with pytest.raises(u.UpdateBlocked, match="identity_changed"):
        ops.trial_signal("web", signal.SIGKILL)
    assert not any(isinstance(event, tuple) and event[0] == "signal" for event in events)


def test_missing_original_pid_never_signals(tmp_path, monkeypatch):
    ops, events, observed = signal_ops(tmp_path, monkeypatch)
    observed["alive"] = False
    ops.trial_signal("web", signal.SIGTERM)
    assert events == ["revalidate"]


@pytest.mark.parametrize("fail", [False, True])
def test_forward_and_fault_rollback_dispatch_retirement_with_existing_transaction(
    tmp_path, monkeypatch, fail
):
    """Exercise execute + real action dispatch; synthetic service boundaries only."""
    events = []
    state = {
        "mode": u.TRIAL_MODE,
        "trial_authorization": {"approved": True},
        "trial_authorization_sha256": "a" * 64,
        "trial_backup_parent": str(tmp_path / "backup"),
        "config": {"source_common": "old"},
    }
    ops = u.Operations(tmp_path, state, None, None, None)
    monkeypatch.setattr(ops, "idle", lambda: True)
    monkeypatch.setattr(ops, "checkpoint", lambda state, phase: events.append("intent:" + phase))
    monkeypatch.setattr(ops, "stop_gateway", lambda: events.append("gateway_stop"))
    monkeypatch.setattr(ops, "stop_trial_primary", lambda: events.append("primary_stop"))

    def prepare(ops, manifest, seal, parent):
        events.append("backup")
        ops.state["trial_retirement"] = {"status": "prepared"}

    monkeypatch.setattr(trial, "prepare", prepare)
    monkeypatch.setattr(trial, "validate_retired", lambda *args, **kwargs: None)
    state["transaction"] = "synthetic-transaction"
    monkeypatch.setattr(
        trial,
        "apply",
        lambda ops, restoring=False: events.append(
            "restore_trials" if restoring else "retire_trials"
        ),
    )
    monkeypatch.setattr(
        ops, "install", lambda previous: events.append("old_wheel" if previous else "new_wheel")
    )
    monkeypatch.setattr(
        ops,
        "start_primary",
        lambda previous: events.append("old_primary" if previous else "new_primary"),
    )
    monkeypatch.setattr(
        ops,
        "start_gateway",
        lambda previous: events.append("old_gateway" if previous else "new_gateway"),
    )

    def verify(previous):
        if fail and not previous:
            raise u.UpdateBlocked("target_fault")
        events.append("verify_previous" if previous else "verify_target")

    monkeypatch.setattr(ops, "verify", verify)
    monkeypatch.setattr(ops, "finish", lambda state, result: {"status": result})
    monkeypatch.setattr(u, "validate_trial_rebind", lambda state: {"source_common": "new"})
    monkeypatch.setattr(
        u.c, "atomic", lambda path, value: events.append("config:" + value["source_common"])
    )
    assert u.execute(ops, state)["status"] == ("rolled_back" if fail else "deployed")
    assert (
        events.index("primary_stop")
        < events.index("backup")
        < events.index("retire_trials")
        < events.index("new_wheel")
        < events.index("new_primary")
    )
    if fail:
        assert (
            events.index("retire_trials")
            < events.index("old_wheel")
            < events.index("old_primary")
            < events.index("verify_previous")
        )


def test_preservation_uses_explicit_session_delta_and_keeps_original(tmp_path, monkeypatch):
    before = {
        "accounts": "account-hash",
        "primary": {
            "sessions": {"old": "hash"},
            "models_hash": "model-hash",
            "files": {"sessions/old.json": "h", "originals/report": "r"},
        },
        "private": {},
    }
    assets = {"primary": {"sessions": "s", "models": "m", "watchlists": "w"}, "private": {}}
    ops = u.Operations(
        tmp_path,
        {"mode": u.TRIAL_MODE, "before": before, "asset_index_before": assets},
        None,
        None,
        None,
    )
    observed = []
    monkeypatch.setattr(u.g, "preserved", lambda home, expected: observed.append(expected))
    monkeypatch.setattr(u, "asset_index_snapshot", lambda home: trial.asset_delta(assets))
    ops.verify_preservation(False)
    assert observed == [trial.preservation_delta(before)]
    assert before["primary"]["sessions"] == {"old": "hash"}
    assert observed[0]["primary"]["files"] == {"originals/report": "r"}
    monkeypatch.setattr(u, "asset_index_snapshot", lambda home: assets)
    ops.verify_preservation(True)
    assert observed[-1] == before


def test_non_session_business_change_blocks_verification(tmp_path, monkeypatch):
    before = {
        "accounts": "a",
        "primary": {"sessions": {}, "models_hash": "m", "files": {}},
        "private": {},
    }
    ops = u.Operations(
        tmp_path,
        {
            "mode": u.TRIAL_MODE,
            "before": before,
            "asset_index_before": {
                "primary": {"sessions": "s", "watchlists": "original"},
                "private": {},
            },
        },
        None,
        None,
        None,
    )
    monkeypatch.setattr(u.g, "preserved", lambda *args: None)
    monkeypatch.setattr(
        u,
        "asset_index_snapshot",
        lambda home: {"primary": {"sessions": "s", "watchlists": "changed"}, "private": {}},
    )
    with pytest.raises(u.UpdateBlocked, match="non_session_data_changed"):
        ops.verify_preservation(False)


@pytest.mark.parametrize(
    "damage", [None, "birth", "argv", "signature", "image", "uid", "listener", "launchd", "root"]
)
def test_original_full_identity_and_listeners_revalidated_before_any_signal(
    tmp_path, monkeypatch, damage
):
    primary, gateway = tmp_path / "primary", tmp_path / "gateway"
    primary.mkdir()
    gateway.mkdir()
    plist = tmp_path / "gateway.plist"
    plist.write_bytes(b"synthetic-plist")
    ident = lambda p: [p.stat().st_dev, p.stat().st_ino]
    identities = {
        role: {
            "pid": n,
            "birth": 123.0,
            "argv": ["python", role],
            "signature": "original birth command",
            "image": "/synthetic/python",
            "uid": 501,
        }
        for role, n in (("web", 100), ("runtime", 101), ("gateway", 102))
    }
    state = {
        "mode": u.TRIAL_MODE,
        "target": u.TRIAL_PAYLOAD,
        "trial_authorization": {"home_identity": ident(tmp_path)},
        "primary_project": str(primary),
        "gateway_project": str(gateway),
        "primary_identity": ident(primary),
        "gateway_identity": ident(gateway),
        "gateway_plist": str(plist),
        "gateway_plist_sha256": u.c.digest(plist),
        "trial_processes": identities,
    }
    processes = [SimpleNamespace(role="web", port=3081), SimpleNamespace(role="runtime", port=8088)]
    manager = SimpleNamespace(
        _processes=lambda: processes,
        _probe_state=lambda process: SimpleNamespace(
            state="valid",
            pid=identities[process.role]["pid"],
            started_at=123.0,
            signature=(process.role,),
        ),
    )
    ops = u.Operations(tmp_path, state, manager, None, None)
    monkeypatch.setattr(u, "validate_trial_rebind", lambda state: {})
    monkeypatch.setattr(u, "verify_release_repository", lambda *args: None)
    monkeypatch.setattr(u.g, "no_private_processes", lambda server: None)
    monkeypatch.setattr(native, "probe_process", lambda pid: SimpleNamespace(state="alive"))
    monkeypatch.setattr(
        native,
        "listener_pids",
        lambda port: SimpleNamespace(
            state="listening", pids=(999 if damage == "listener" else 100 if port == 3081 else 101,)
        ),
    )
    monkeypatch.setattr(u.g, "listener_pids", lambda: {102})
    monkeypatch.setattr(u.g, "job_pid", lambda: 102)
    monkeypatch.setattr(u.g, "job_state", lambda: None if damage == "launchd" else "synthetic")
    monkeypatch.setattr(ops, "loaded_job_matches", lambda raw: True)

    def observed(pid, fact):
        identity = dict(next(value for value in identities.values() if value["pid"] == pid))
        if damage in {"birth", "argv", "signature", "image", "uid"}:
            identity[damage] = "changed"
        return identity

    monkeypatch.setattr(ops, "trial_process_identity", observed)
    if damage == "root":
        state["primary_identity"] = [0, 0]
    if damage is None:
        ops.check_trial_processes()
    else:
        with pytest.raises(u.UpdateBlocked):
            ops.check_trial_processes()


def test_trial_source_transition_is_exact_and_keeps_both_original_identities(monkeypatch):
    old = "/Users/leon/Desktop/Projects/ResearchWorkbench/.git"
    new = "/Users/leon/Developer/ResearchWorkbench-main/.git"
    config = {"source_common": old, "repository": "owner/repo", "model": "unchanged"}

    def identity(project, repository):
        common = old if str(project) == str(Path(old).parent) else new
        return {"common": common, "identity": [1, 10 if common == old else 20]}

    monkeypatch.setattr(u, "repository_identity", identity)
    transition = u.trial_rebind(Path(new).parent, config)
    state = {"config": config, "source_transition": transition}
    result = u.validate_trial_rebind(state)
    assert result == {**config, "source_common": new}
    assert config["source_common"] == old
    transition["after"]["identity"] = [1, 99]
    with pytest.raises(u.UpdateBlocked, match="transition_changed"):
        u.validate_trial_rebind(state)


@pytest.mark.parametrize("phase,role", [("start_primary", "web"), ("start_gateway", "gateway")])
def test_spawn_before_durable_pid_stays_unknown_without_respawn_or_losing_backups(
    tmp_path, monkeypatch, phase, role
):
    import json
    from contextlib import ExitStack

    from research_workbench_entrypoint.resident.admission import file_lock

    root, run = tmp_path / "resident", tmp_path / "server/run"
    root.mkdir(mode=0o700)
    run.mkdir(parents=True, mode=0o700)
    archive = tmp_path / "original-trials.archive"
    archive.write_bytes(b"exact original trial bytes")
    backup = tmp_path / "configuration.backup"
    backup.write_bytes(b"exact account and model backup bytes")
    state = {
        "version": 4,
        "mode": u.TRIAL_MODE,
        "phase": phase,
        "trial_processes": {
            role: {"pid": 100, "signature": "original full birth and argv signature"}
        },
        "trial_retirement": {"backup": str(backup), "archive": str(archive)},
    }
    (root / "transaction.json").write_text(json.dumps({"phase": "switching"}))
    journal = run / "gateway-upgrade.json"
    journal.write_text(json.dumps(state))
    journal.chmod(0o600)
    ops = u.Operations(tmp_path, state, None, None, SimpleNamespace(retain=True))
    observed = SimpleNamespace(state="alive", started_at=200.0, argv=("synthetic", "new-child"))
    monkeypatch.setattr(
        ops, "idle", lambda: ops.trial_unknown(role, observed, observed_pids=(101,))
    )
    monkeypatch.setattr(
        ops,
        "action",
        lambda *args: pytest.fail("unknown process cannot trigger start, install or archive"),
    )
    monkeypatch.setattr(
        u,
        "request_json",
        lambda *args: pytest.fail("unknown window cannot send a model or native request"),
    )
    with ExitStack() as stack:
        for directory, name in (
            (root, "supervisor.lock"),
            (root, "admission.lock"),
            (run, "operator.lock"),
        ):
            stack.enter_context(file_lock(directory, name, exclusive=True))
        for _ in range(2):
            assert u.execute(ops, state, recovering=True) == {"status": "recovery_required"}
            saved = json.loads(journal.read_text())
            assert saved["phase"] == phase
            assert saved["trial_processes"][role]["pid"] == 100
            assert saved["trial_unknown_observation"] == {
                "role": role,
                "phase": phase,
                "expected_pid": 100,
                "observed_pids": [101],
                "observed_state": "alive",
                "observed_birth": 200.0,
                "observed_argv_sha256": saved["trial_unknown_observation"]["observed_argv_sha256"],
                "disposition": "UNKNOWN_MANUAL_RECONCILIATION_REQUIRED",
            }
            assert ops.fence.retain is True
            assert archive.read_bytes() == b"exact original trial bytes"
            assert backup.read_bytes() == b"exact account and model backup bytes"


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "legal_term",
        "before_stop",
        "archive",
        "archive_persistent",
        "install",
        "after_durable_target_start",
    ],
)
def test_transaction_uses_real_offline_archive_backup_and_fault_restore(
    stopped_home, monkeypatch, fault
):
    import json

    f = stopped_home
    ops = f.ops
    original = (f.data / "index.json").read_bytes()
    accounts = (ops.server / "accounts.sqlite3").read_bytes()
    state = ops.state
    state.update(
        trial_authorization=f.manifest,
        trial_authorization_sha256=trial.digest(f.manifest),
        trial_backup_parent=str(f.safe),
        before=u.g.preservation(ops.home),
        asset_index_before=u.asset_index_snapshot(ops.home),
    )
    events = []

    def scoped_idle():
        trial.stopped(ops)
        return True

    monkeypatch.setattr(ops, "idle", scoped_idle)

    def gateway_stop():
        trial.stopped(ops)
        events.append("stop_gateway")
        if fault == "legal_term":
            value = json.loads((f.data / "index.json").read_bytes())
            value["sessions"]["trial"]["status"] = "interrupted"
            (f.data / "index.json").write_text(json.dumps(value))
        if fault == "before_stop" and events.count("stop_gateway") == 1:
            raise u.MaintenanceBusy("synthetic_stop_boundary")

    monkeypatch.setattr(ops, "stop_gateway", gateway_stop)
    monkeypatch.setattr(ops, "stop_trial_primary", lambda: trial.stopped(ops))

    def install(previous):
        trial.stopped(ops)
        events.append("old_wheel" if previous else "new_wheel")
        if not previous and fault == "install":
            raise OSError("synthetic_install_fault")

    monkeypatch.setattr(ops, "install", install)
    monkeypatch.setattr(u, "validate_trial_rebind", lambda state: state["config"])
    if fault in {"archive", "archive_persistent"}:
        archive_directory = trial._archive_directory
        injected = False

        def archive(*args, **kwargs):
            nonlocal injected
            result = archive_directory(*args, **kwargs)
            if not kwargs.get("restoring", False) and (
                not injected or fault == "archive_persistent"
            ):
                injected = True
                raise OSError("synthetic_fault_after_real_archive_rename")
            return result

        monkeypatch.setattr(trial, "_archive_directory", archive)

    def start_primary(previous):
        trial.validate_retired(
            ops.home, state["trial_retirement"], transaction=state["transaction"]
        )
        if not previous:
            state["synthetic_durable_target_pid"] = 12345
            ops.checkpoint(state, "start_primary")
        events.append("old_primary" if previous else "new_primary")

    monkeypatch.setattr(ops, "start_primary", start_primary)

    def start_gateway(previous):
        trial.validate_retired(
            ops.home, state["trial_retirement"], transaction=state["transaction"]
        )
        events.append("old_gateway" if previous else "new_gateway")

    monkeypatch.setattr(ops, "start_gateway", start_gateway)

    def verify(previous):
        ops.verify_preservation(previous)
        if not previous and fault == "after_durable_target_start":
            assert state["synthetic_durable_target_pid"] == 12345
            raise OSError("synthetic_fault_after_durable_target_identity")

    monkeypatch.setattr(ops, "verify", verify)
    monkeypatch.setattr(ops, "finish", lambda state, result: {"status": result})
    result = u.execute(ops, state)
    if fault == "before_stop":
        assert result == {"status": "recovery_required"}
        assert not list(f.safe.iterdir())
        result = u.execute(ops, state, recovering=True)
    if fault == "archive_persistent":
        assert result == {"status": "recovery_required"}
        assert "new_primary" not in events and "old_primary" not in events
        assert Path(state["trial_retirement"]["backup"]["backup"]).is_dir()
        monkeypatch.setattr(trial, "_archive_directory", archive_directory)
        result = u.execute(ops, state, recovering=True)
    assert result["status"] == ("deployed" if fault in (None, "legal_term") else "rolled_back")
    assert (ops.server / "accounts.sqlite3").read_bytes() == accounts
    assert json.loads((f.data / "index.json").read_bytes())["sessions"] == {}
    assert list((f.data / "sessions").iterdir()) == []
    assert state["trial_retirement"]["status"] == "retired_offline"
    assert state["trial_retirement"]["native_cleanup"] == "UNKNOWN"
    assert (f.data / "index.json").read_bytes() != original
    assert state["trial_retirement"]["data_retirement_committed"] is True
    assert Path(state["trial_retirement"]["backup"]["backup"]).is_dir()


@pytest.fixture
def finish_home(stopped_home, monkeypatch):
    import json
    import sqlite3
    from uuid import uuid4

    from research_workbench_entrypoint.resident import trial_discard_backup as backup

    f = stopped_home
    ops, state = f.ops, f.ops.state
    ops.home.chmod(0o700)
    ops.server.chmod(0o700)
    private_user = str(uuid4())
    with sqlite3.connect(ops.server / "accounts.sqlite3") as database:
        database.execute("INSERT INTO accounts VALUES (?)", (private_user,))
    (ops.server / "accounts.sqlite3").chmod(0o600)
    private = ops.server / "users" / private_user / "research-web"
    private.mkdir(parents=True, mode=0o700)
    private.parent.chmod(0o700)
    (private / "index.json").write_text(json.dumps({"sessions": {}, "models": {"keep": True}}))
    gateway_value = json.loads((ops.server / "resident.json").read_bytes())
    gateway_value.update(origin="http://synthetic.invalid", revision=u.TRIAL_PREVIOUS)
    (ops.server / "resident.json").write_text(json.dumps(gateway_value))
    f.manifest["inventory_seal"] = backup.preview(ops.home)["seal"]
    f.manifest["scope_sha256"] = trial.digest(trial.scope_snapshot(ops.home))
    state["config"].update(
        artifact=str(ops.root / "controller.pyz"),
        artifact_sha256=u.CONTROLLER_SHA256,
        node="synthetic-node",
        private_origin="https://synthetic.invalid",
    )
    state["primary_project"] = str(ops.home / "synthetic-project")
    state["model_before"] = {
        "provider": "synthetic",
        "model": "synthetic",
        "credential_configured": False,
        "credential_storage": "not_required",
    }
    f.private_user = private_user
    before = u.g.preservation(ops.home)
    assets = u.asset_index_snapshot(ops.home)
    previous, target = u.TRIAL_PREVIOUS, u.TRIAL_PAYLOAD
    old_wheel, new_wheel = ops.root / "old.whl", ops.root / "new.whl"
    old_wheel.write_bytes(b"synthetic old wheel")
    new_wheel.write_bytes(b"synthetic new wheel")
    state.update(
        previous=previous,
        target=target,
        executor_revision="e" * 40,
        source_transition={
            "before": {"common": "synthetic-old"},
            "after": {"common": "synthetic-new"},
        },
        before=before,
        asset_index_before=assets,
        trial_authorization=f.manifest,
        trial_authorization_sha256=trial.digest(f.manifest),
        trial_backup_parent=str(f.safe),
        new_wheel={"path": str(new_wheel), "sha256": u.c.digest(new_wheel)},
        old_wheel={"path": str(old_wheel), "sha256": u.c.digest(old_wheel)},
        manifest={"code_commit": previous},
        proof={"synthetic_exact_product_evidence": target},
        reviewed={"product_tree": "synthetic-reviewed-tree"},
        accepted={"target": previous},
        candidate_before={},
    )
    state["config"]["baseline"] = previous
    state["gateway_config"] = json.loads((ops.server / "resident.json").read_bytes())
    monkeypatch.setattr(u, "validate_trial_rebind", lambda state: state["config"])
    u.c.atomic(ops.root / "config.json", state["config"])
    u.c.atomic(ops.home / "install/manifest.json", state["manifest"])
    u.c.atomic(ops.root / "accepted.json", state["accepted"])
    u.c.atomic(ops.root / "candidate.json", state["candidate_before"])
    candidate = {
        key: state[key]
        for key in ("previous", "target", "new_wheel", "old_wheel", "manifest", "proof")
    }
    u.c.atomic(ops.root / "transaction.json", {**candidate, "phase": "switching"})
    trial.prepare(ops, f.manifest, trial.digest(f.manifest), f.safe)
    trial.apply(ops)
    return f


@pytest.mark.parametrize("result", ["deployed", "rolled_back"])
def test_real_finish_archives_full_receipt_before_removing_journals(finish_home, result):
    import hashlib
    import json

    f = finish_home
    state, ops = f.ops.state, f.ops
    finished = ops.finish(state, result)
    path = Path(finished["trial_completion_receipt"]["path"])
    raw = path.read_bytes()
    receipt = json.loads(raw)
    assert path.parent == ops.root / "trial-retirements"
    assert path.name == state["transaction"] + ".json"
    assert path.stat().st_mode & 0o777 == 0o600
    assert receipt["journal"] == {
        key: value for key, value in state.items() if key != "trial_terminal_intent"
    }
    assert receipt["executor_revision"] == state["executor_revision"]
    assert receipt["payload"] == u.TRIAL_PAYLOAD
    assert receipt["previous"] == u.TRIAL_PREVIOUS
    assert receipt["result"]["status"] == result
    assert receipt["journal"]["source_transition"] == state["source_transition"]
    assert finished["trial_completion_receipt"]["sha256"] == hashlib.sha256(raw).hexdigest()
    assert not (ops.root / "transaction.json").exists()
    assert not (ops.server / "run/gateway-upgrade.json").exists()
    archived = receipt["journal"]["trial_retirement"]
    trial.validate_retired(ops.home, archived, transaction=state["transaction"])
    point = Path(archived["backup"]["backup"])
    assert (
        hashlib.sha256((point / "manifest.json").read_bytes()).hexdigest()
        == archived["backup"]["manifest_sha256"]
    )
    expected = finished.copy()
    expected.pop("trial_completion_receipt")
    original_inode = path.stat().st_ino
    assert ops.archive_trial_completion(state, expected) == finished["trial_completion_receipt"]
    assert path.read_bytes() == raw and path.stat().st_ino == original_inode


@pytest.mark.parametrize("failure", ["publish", "conflict", "backup_changed"])
def test_real_finish_receipt_failure_preserves_active_journals_and_never_claims_success(
    finish_home, monkeypatch, failure
):
    f = finish_home
    ops, state = f.ops, f.ops.state
    path = ops.root / "trial-retirements" / (state["transaction"] + ".json")
    foreign = b"unrelated immutable transaction receipt"
    if failure == "publish":
        monkeypatch.setattr(
            u.os,
            "link",
            lambda *args, **kwargs: (_ for _ in ()).throw(
                OSError("synthetic atomic publish failure")
            ),
        )
    elif failure == "conflict":
        path.parent.mkdir(mode=0o700)
        path.write_bytes(foreign)
        path.chmod(0o600)
    else:
        point = Path(state["trial_retirement"]["backup"]["backup"])
        (point / "research-web/index.json").write_bytes(b"corrupted backup")
    with pytest.raises(u.UpdateBlocked):
        ops.finish(state, "deployed")
    assert (ops.root / "transaction.json").is_file()
    assert (ops.server / "run/gateway-upgrade.json").is_file()
    assert not (ops.server / "run/model-upgrade-result.json").exists()
    assert not (ops.root / "state.json").exists()
    if failure == "conflict":
        assert path.read_bytes() == foreign


@pytest.mark.parametrize("result", ["deployed", "rolled_back"])
@pytest.mark.parametrize("boundary", ["primary_journal", "gateway_journal"])
def test_terminal_receipt_crash_recovery_only_finishes_original_result(
    finish_home, monkeypatch, result, boundary
):
    import json

    ops, state = finish_home.ops, finish_home.ops.state
    selected = (
        ops.root / "transaction.json"
        if boundary == "primary_journal"
        else ops.server / "run/gateway-upgrade.json"
    )
    real_unlink = Path.unlink
    injected = False

    def unlink(path, *args, **kwargs):
        nonlocal injected
        if path == selected and not injected:
            injected = True
            raise OSError("synthetic crash after durable terminal receipt")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(OSError):
        ops.finish(state, result)
    receipt_path = ops.root / "trial-retirements" / (state["transaction"] + ".json")
    original_bytes, original_inode = receipt_path.read_bytes(), receipt_path.stat().st_ino
    resumed = u.g.read_upgrade_journal(ops.server / "run/gateway-upgrade.json")
    assert resumed["trial_terminal_intent"]["result"] == result
    monkeypatch.setattr(
        ops,
        "action",
        lambda *args: pytest.fail("terminal recovery cannot reverse, install or spawn"),
    )
    monkeypatch.setattr(
        ops, "idle", lambda: pytest.fail("terminal recovery must precede abort/reverse admission")
    )
    monkeypatch.setattr(
        u, "request_json", lambda *args: pytest.fail("synthetic recovery cannot submit any request")
    )

    def verify(previous):
        assert previous is (result == "rolled_back")
        trial.validate_retired(
            ops.home, resumed["trial_retirement"], transaction=resumed["transaction"]
        )
        ops.verify_preservation(previous)

    monkeypatch.setattr(ops, "verify", verify)
    from research_workbench_entrypoint.resident.gateway_fence import BirthFence

    primary = state["gateway_config"]["binding"]["primary_user_id"]
    with BirthFence(ops.server, primary, transaction=state["transaction"]) as owned_fence:
        ops.fence = owned_fence
        ops._trial_owned_birth_journal = json.loads(owned_fence.journal.read_bytes())
        returned = u.execute(ops, resumed, recovering=True)
    assert returned["status"] == result
    assert returned["trial_completion_receipt"]["path"] == str(receipt_path)
    assert receipt_path.read_bytes() == original_bytes
    assert receipt_path.stat().st_ino == original_inode
    assert not (ops.root / "transaction.json").exists()
    assert not (ops.server / "run/gateway-upgrade.json").exists()
    assert (
        json.loads((ops.server / "run/model-upgrade-result.json").read_bytes())["status"] == result
    )


@pytest.mark.parametrize("damage", ["bytes", "transaction", "physical"])
def test_terminal_recovery_rejects_tampering_or_physical_mismatch(finish_home, monkeypatch, damage):
    import json

    ops, state = finish_home.ops, finish_home.ops.state
    selected = ops.root / "transaction.json"
    real_unlink = Path.unlink

    def unlink(path, *args, **kwargs):
        if path == selected:
            raise OSError("synthetic crash before cleanup")
        return real_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)
    with pytest.raises(OSError):
        ops.finish(state, "deployed")
    receipt_path = ops.root / "trial-retirements" / (state["transaction"] + ".json")
    if damage == "bytes":
        receipt_path.write_bytes(receipt_path.read_bytes() + b" ")
    elif damage == "transaction":
        value = json.loads(receipt_path.read_bytes())
        value["transaction"] = "00000000-0000-0000-0000-000000000000"
        receipt_path.write_text(json.dumps(value))
    monkeypatch.setattr(
        ops,
        "action",
        lambda *args: pytest.fail("invalid terminal evidence cannot invoke reverse or start"),
    )

    def verify(previous):
        if damage == "physical":
            raise u.UpdateBlocked("synthetic_running_revision_mismatch")
        pytest.fail("receipt tampering must fail before physical verification")

    monkeypatch.setattr(ops, "verify", verify)
    assert u.execute(ops, state, recovering=True) == {"status": "recovery_required"}
    assert selected.exists()
    assert (ops.server / "run/gateway-upgrade.json").exists()
    assert ops.fence.retain is True


def prepare_real_operate_terminal(f, monkeypatch, result, damage=None):
    import json
    from contextlib import contextmanager

    from app.research_web import service_manager

    # Model only the operator's macOS admission; native fence code keeps the host sys.
    monkeypatch.setattr(u, "sys", SimpleNamespace(**{**vars(sys), "platform": "darwin"}))
    ops, state = f.ops, f.ops.state
    primary = ops.root / "transaction.json"
    unlink = Path.unlink

    def crash(path, *args, **kwargs):
        if path == primary:
            raise OSError("synthetic crash before terminal cleanup")
        return unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", crash)
    with pytest.raises(OSError):
        ops.finish(state, result)
    monkeypatch.setattr(Path, "unlink", unlink)
    previous = result == "rolled_back"
    u.c.atomic(ops.server / "resident.json", u.gateway_configuration(state, previous))
    monkeypatch.setattr(u.c, "configured", lambda home: (ops.root, state["config"]))
    monkeypatch.setattr(u.c, "environment", lambda *args: None)
    # The synthetic source/controller evidence is outside this filesystem-fence test.
    monkeypatch.setattr(u, "validate_state", lambda *args, **kwargs: None)
    revision = state["previous"] if previous else state["target"]
    monkeypatch.setattr(
        u.c,
        "clean",
        lambda project, sha: None if sha == revision else pytest.fail("wrong revision"),
    )

    @contextmanager
    def held_lock(directory, name, *, exclusive):
        assert exclusive is True
        trial._held(directory / name)
        yield

    @contextmanager
    def lease():
        yield ops.lease

    monkeypatch.setattr(u, "file_lock", held_lock)
    monkeypatch.setattr(ops.manager, "_installation_start_scope", lease, raising=False)
    monkeypatch.setattr(service_manager, "WebServiceManager", lambda **kwargs: ops.manager)
    monkeypatch.setattr(
        u.Operations,
        "idle",
        lambda self: pytest.fail("terminal resume must not run abort admission"),
    )
    monkeypatch.setattr(
        u.Operations,
        "action",
        lambda *args: pytest.fail("terminal resume cannot reverse/start or install"),
    )
    marker = ops.server / "users" / f.private_user / "state/owner.json/reservation"

    def get(url):
        if url.endswith("/api/research/resident"):
            return {"enabled": True, "revision": revision}
        if url.endswith("/api/server/health"):
            return {"revision": revision, "deployment_fenced": True}
        if url.endswith("/api/research/runtime"):
            return {**state["model_before"], "connected": True, "health_check_passed": True}
        if url.endswith("/api/research/model-profiles"):
            if damage == "owner":
                marker.write_text("foreign-owner-token")
            elif damage == "journal":
                birth = ops.server / "run/birth-fence.json"
                value = json.loads(birth.read_bytes())
                value["transaction"] = "00000000-0000-0000-0000-000000000000"
                birth.write_text(json.dumps(value))
            return {"items": [{**state["model_before"], "active": True}]}
        pytest.fail("unexpected request, no model/native work is authorized")

    monkeypatch.setattr(u, "request_json", get)

    class Connection:
        def __init__(self, *args, **kwargs):
            pass

        def request(self, method, path, **kwargs):
            assert (method, path) == ("GET", "/api/server/health")

        def getresponse(self):
            payload = {
                "status": "ready",
                "revision": revision,
                "primary_last_verified": True,
                "deployment_fenced": True,
            }
            return SimpleNamespace(status=200, read=lambda limit: json.dumps(payload).encode())

        def close(self):
            pass

    monkeypatch.setattr(u.g.http.client, "HTTPConnection", Connection)
    return marker


@pytest.mark.parametrize("result", ["deployed", "rolled_back"])
def test_real_operate_terminal_resume_releases_its_new_birth_fence(
    finish_home, monkeypatch, result
):
    from uuid import uuid4

    from research_workbench_entrypoint.resident.gateway_fence import BirthFence

    f = finish_home
    marker = prepare_real_operate_terminal(f, monkeypatch, result)
    receipt = f.ops.root / "trial-retirements" / (f.ops.state["transaction"] + ".json")
    original, inode = receipt.read_bytes(), receipt.stat().st_ino
    returned = u.operate(f.ops.home, recovering=True)
    assert returned["status"] == result
    assert receipt.read_bytes() == original and receipt.stat().st_ino == inode
    assert not (f.ops.server / "run/birth-fence.json").exists()
    assert not marker.parent.exists()
    assert not list((f.ops.server / "run").glob("birth-slot-*"))
    primary = f.ops.state["gateway_config"]["binding"]["primary_user_id"]
    with BirthFence(f.ops.server, primary, transaction=str(uuid4())):
        assert marker.exists()
    assert not marker.parent.exists()
    assert not (f.ops.server / "run/birth-fence.json").exists()


@pytest.mark.parametrize("damage", ["owner", "journal"])
def test_real_operate_terminal_resume_protects_changed_birth_ownership(
    finish_home, monkeypatch, damage
):
    f = finish_home
    marker = prepare_real_operate_terminal(f, monkeypatch, "deployed", damage)
    returned = u.operate(f.ops.home, recovering=True)
    assert returned == {"status": "recovery_required"}
    assert (f.ops.root / "transaction.json").exists()
    assert (f.ops.server / "run/gateway-upgrade.json").exists()
    assert (f.ops.server / "run/birth-fence.json").exists()
    assert marker.exists()
    if damage == "owner":
        assert marker.read_text() == "foreign-owner-token"


def test_real_operate_fixture_sys_proxy_preserves_native_host(finish_home, monkeypatch):
    from research_workbench_entrypoint.resident import gateway_fence

    prepare_real_operate_terminal(finish_home, monkeypatch, "deployed")
    assert u.sys is not sys
    assert u.sys.platform == "darwin"
    assert u.g.sys is sys and gateway_fence.sys is sys
    assert u.sys.prefix is sys.prefix
    assert u.sys.path is sys.path
    assert u.sys.argv is sys.argv
    assert u.sys.modules is sys.modules


@pytest.mark.parametrize("platform", ["linux", "win32"])
def test_production_non_macos_admission_still_refuses_before_home_read(
    tmp_path, monkeypatch, platform
):
    from research_workbench_entrypoint.resident import gateway_fence

    real_platform = sys.platform
    monkeypatch.setattr(u, "sys", SimpleNamespace(**{**vars(sys), "platform": platform}))
    monkeypatch.setattr(
        u.c,
        "configured",
        lambda *args: pytest.fail("non-macOS admission must reject before reading home"),
    )
    with pytest.raises(u.UpdateBlocked, match="^model_upgrade_macos_only$"):
        u.operate(tmp_path, recovering=True)
    assert sys.platform == real_platform
    assert u.g.sys is sys and gateway_fence.sys is sys
