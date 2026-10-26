"""Offline legacy control tests: temporary catalogs only, no Native or Office."""

import copy
import hashlib
import json
from dataclasses import replace

import pytest

from app.research_web.report_workflows import catalog as catalog_module
from app.research_web.report_workflows import legacy_monitoring as monitoring_module
from app.research_web.report_workflows.catalog import ReportWorkflowService
from app.research_web.report_workflows.legacy_monitoring import LegacyMonitoringExpectation, digest
from app.research_web.report_workflows.models import WorkflowError
from research_workbench_entrypoint.resident.weekly_monitoring import main, preview


@pytest.fixture
def legacy(tmp_path):
    root = tmp_path / "state"
    run_id, sid = "a" * 32, "12345678-1234-1234-1234-123456789012"
    runs = root / "report-workflows/runs"
    run = runs / run_id
    session = root / "sessions" / sid / "inputs/report-workflow"
    for folder in (run / "snapshots", session / "snapshots"):
        folder.mkdir(parents=True, mode=0o700)
    for folder in (root, root / "report-workflows", runs):
        folder.chmod(0o700)
    snapshot, context = b'{"source":"frozen"}', b'{"version":5}'
    for folder in (run, session):
        (folder / "snapshots/report-data.json").write_bytes(snapshot)
    (session / "run-context.json").write_bytes(context)
    sha = lambda raw: hashlib.sha256(raw).hexdigest()
    contract = {"cutoff": "2026-10-16", "schema_version": 3}
    row = {
        "id": run_id,
        "session_id": sid,
        "workflow_id": "huaan-etf-weekly",
        "version": 5,
        "owner_id": "owner",
        "run_ref": f"runs/{run_id}",
        "execution_purpose": "historical_acceptance",
        "status": "needs_attention",
        "research_submission_state": "unknown",
        "failure_code": "research_submission_unknown",
        "research_admission_at": 123,
        "weekly_context_sha256": sha(context),
        "dataset_snapshot_sha256": sha(snapshot),
        "weekly_data_contract": contract,
        "receipt": {"original": "preserved"},
        "collected_at": 111,
        "updated_at": 124.0,
    }
    index = root / "report-workflows/catalog.json"
    index.write_text(json.dumps({"schema_version": 1, "runs": {run_id: row}, "workflows": {}}))
    index.chmod(0o600)
    lock = index.with_name("catalog.lock")
    lock.touch(mode=0o600)
    orphan = runs / "unindexed-protected"
    orphan.mkdir()
    (orphan / "evidence").write_text("keep")
    expected = LegacyMonitoringExpectation(
        run_id, sid, 5, "owner", digest(row), sha(context), sha(snapshot), digest(contract)
    )
    owner = lambda expected: {"id": expected, "role": "admin"}
    return root, expected, owner, copy.deepcopy(row)


def act(legacy, *, apply=True, operation_id="reviewed-op-001", owner=None, expected=None):
    root, identity, authorize, _ = legacy
    catalog = ReportWorkflowService.open_for_maintenance(root)
    return catalog.end_legacy_monitoring(
        expected or identity, operation_id=operation_id, owner_check=owner or authorize, apply=apply
    )


def test_preview_no_reconcile_no_mutation(legacy):
    root, expected, owner, _ = legacy
    before = (root / "report-workflows/catalog.json").read_bytes()
    result = preview(root, expected, operation_id="reviewed-op-001", owner_check=owner)
    assert result["apply_available"] is False
    assert result["operations_idle"] == "NOT_RUN"
    assert (root / "report-workflows/catalog.json").read_bytes() == before
    assert (root / "report-workflows/runs/unindexed-protected/evidence").read_text() == "keep"


def test_preserves_evidence_and_idempotence(legacy):
    root, expected, _, original = legacy
    assert "path" not in original
    assert original["run_ref"] == f"runs/{expected.run_id}"
    frozen = {
        p: p.read_bytes()
        for p in root.rglob("*")
        if p.is_file() and p.suffix != ".lock" and p.name != "catalog.json"
    }
    receipt = act(legacy)
    assert receipt["native_cancelled"] is False
    row = ReportWorkflowService.open_for_maintenance(root).data["runs"][expected.run_id]
    for key, value in original.items():
        if key != "status":
            assert row[key] == value
    assert row["status"] == "cancelled"
    assert row["monitoring_disposition"] == "ended_by_user"
    assert act(legacy) == receipt
    assert all(p.read_bytes() == raw for p, raw in frozen.items())
    with pytest.raises(WorkflowError, match="历史"):
        act(legacy, operation_id="reviewed-op-002")


@pytest.mark.parametrize(
    "field,value",
    [
        ("version", 6),
        ("owner_id", "other"),
        ("session_id", "a" * 36),
        ("research_submission_protocol", "weekly-admission-v2"),
        ("research_submission_protocol", ""),
        ("weekly_execution_scope", {}),
        ("research_submission_state", "accepted"),
        ("execution_purpose", "formal"),
    ],
)
def test_identity_and_new_protocol_refused(legacy, field, value):
    root, expected, _, _ = legacy
    path = root / "report-workflows/catalog.json"
    index = json.loads(path.read_bytes())
    index["runs"][expected.run_id][field] = value
    path.write_text(json.dumps(index))
    with pytest.raises(WorkflowError):
        act(legacy)


@pytest.mark.parametrize("target", ["attempt", "symlink", "hash", "owner", "sha"])
def test_unsafe_inputs_refused(legacy, target):
    root, expected, _, _ = legacy
    run = root / "report-workflows/runs" / expected.run_id
    if target == "attempt":
        (run / "weekly-rpc-attempt.json").write_text("{}")
    if target in {"symlink", "hash"}:
        path = run / "snapshots/report-data.json"
        if target == "hash":
            path.write_bytes(b"changed")
        else:
            original = path.with_name("outside.json")
            path.rename(original)
            path.symlink_to(original)
    with pytest.raises(WorkflowError):
        act(
            legacy,
            owner=(lambda _: None) if target == "owner" else None,
            expected=replace(expected, run_sha256="b" * 64) if target == "sha" else None,
        )


@pytest.mark.parametrize("phase", ["before", "after", "third"])
def test_save_failure_reads_back_without_rollback(legacy, monkeypatch, phase):
    root, expected, _, original = legacy
    atomic = catalog_module._atomic_json

    def fail(path, value):
        if phase == "after":
            atomic(path, value)
        elif phase == "third":
            third = copy.deepcopy(value)
            third["unknown_external_state"] = True
            atomic(path, third)
        raise OSError("fsync failure")

    monkeypatch.setattr(catalog_module, "_atomic_json", fail)
    if phase == "after":
        assert act(legacy)["disposition"] == "ended_by_user"
    else:
        with pytest.raises((OSError, WorkflowError)):
            act(legacy)
    disk = json.loads((root / "report-workflows/catalog.json").read_bytes())
    if phase == "before":
        assert disk["runs"][expected.run_id] == original
    if phase == "third":
        assert disk["unknown_external_state"] is True


def test_cli_apply_refused_before_reading(legacy, monkeypatch):
    _, expected, _, _ = legacy

    def forbidden(*args):
        raise AssertionError("apply must not open catalog")

    monkeypatch.setattr(ReportWorkflowService, "open_for_maintenance", forbidden)
    argv = [
        "--data-root",
        "/not-real",
        "--reviewed-profile",
        "weekly-legacy-monitoring-v1",
        "--operation-id",
        "reviewed-op-001",
        "--apply",
    ]
    for key, value in vars(expected).items():
        argv.extend(["--expected-" + key.replace("_", "-"), str(value)])
    assert main(argv) == 2


def test_open_never_creates_missing_root(tmp_path):
    missing = tmp_path / "missing"
    with pytest.raises(WorkflowError):
        ReportWorkflowService.open_for_maintenance(missing)
    assert not missing.exists()


def test_disabled_owner_refused(legacy):
    with pytest.raises(WorkflowError):
        act(legacy, owner=lambda owner: {"id": owner, "role": "admin", "enabled": False})


def test_existing_catalog_symlink_and_lock_change_refused(legacy):
    root, expected, owner, _ = legacy
    catalog = ReportWorkflowService.open_for_maintenance(root)
    path = root / "report-workflows/catalog.json"
    other = path.with_name("protected.json")
    path.rename(other)
    path.symlink_to(other)
    with pytest.raises(WorkflowError):
        catalog.end_legacy_monitoring(expected, operation_id="reviewed-op-001", owner_check=owner)
    path.unlink()
    other.rename(path)
    lock = path.with_name("catalog.lock")
    lock.chmod(0o664)
    with pytest.raises(WorkflowError):
        catalog.end_legacy_monitoring(expected, operation_id="reviewed-op-001", owner_check=owner)


def test_idempotence_does_not_hide_changed_evidence(legacy):
    root, expected, _, _ = legacy
    act(legacy)
    path = root / "report-workflows/catalog.json"
    value = json.loads(path.read_bytes())
    value["runs"][expected.run_id]["failure_code"] = "changed"
    path.write_text(json.dumps(value))
    with pytest.raises(WorkflowError):
        act(legacy)


def test_save_success_must_read_back_intended(legacy, monkeypatch):
    monkeypatch.setattr(ReportWorkflowService, "_save", lambda self: None)
    with pytest.raises(WorkflowError) as error:
        act(legacy)
    assert error.value.code == "weekly_monitoring_save_indeterminate"


@pytest.mark.parametrize(
    "reference",
    [
        None,
        "",
        "/runs/" + "a" * 32,
        "runs/../" + "a" * 32,
        "runs/" + "b" * 32,
        "runs\\\\" + "a" * 32,
        "./runs/" + "a" * 32,
    ],
)
def test_run_ref_must_be_exact_catalog_identity(legacy, reference):
    root, expected, _, _ = legacy
    path = root / "report-workflows/catalog.json"
    index = json.loads(path.read_bytes())
    row = index["runs"][expected.run_id]
    row["run_ref"] = reference
    path.write_text(json.dumps(index))
    expected = replace(expected, run_sha256=digest(row))
    before = path.read_bytes()
    with pytest.raises(WorkflowError) as error:
        act(legacy, expected=expected)
    assert error.value.code == "weekly_monitoring_identity_changed"
    assert path.read_bytes() == before


@pytest.mark.parametrize("path_value", [None, "runs/" + "a" * 32, "/unrelated/path"])
def test_dual_run_ref_and_path_conflict_refused(legacy, path_value):
    root, expected, _, _ = legacy
    path = root / "report-workflows/catalog.json"
    index = json.loads(path.read_bytes())
    row = index["runs"][expected.run_id]
    row["path"] = path_value
    path.write_text(json.dumps(index))
    with pytest.raises(WorkflowError) as error:
        act(legacy, expected=replace(expected, run_sha256=digest(row)))
    assert error.value.code == "weekly_monitoring_identity_changed"


def test_optional_legacy_path_must_agree_with_run_ref(legacy):
    root, expected, _, _ = legacy
    path = root / "report-workflows/catalog.json"
    index = json.loads(path.read_bytes())
    row = index["runs"][expected.run_id]
    row["path"] = str(root / "report-workflows/runs" / expected.run_id)
    path.write_text(json.dumps(index))
    receipt = act(legacy, expected=replace(expected, run_sha256=digest(row)))
    assert receipt["native_cancelled"] is False


def test_committed_but_directory_sync_unconfirmed_is_not_success(legacy, monkeypatch):
    root, expected, _, _ = legacy
    atomic = catalog_module._atomic_json

    def uncertain(path, value):
        atomic(path, value)
        raise OSError("initial directory sync unknown")

    def unavailable(_catalog):
        raise OSError("directory fsync unavailable")

    monkeypatch.setattr(catalog_module, "_atomic_json", uncertain)
    monkeypatch.setattr(monitoring_module, "_sync_catalog_directory", unavailable)
    for _ in range(2):
        with pytest.raises(WorkflowError) as error:
            act(legacy)
        assert error.value.code == "weekly_monitoring_committed_unconfirmed"
    disk = json.loads((root / "report-workflows/catalog.json").read_bytes())
    assert disk["runs"][expected.run_id]["monitoring_disposition"] == "ended_by_user"


def test_original_empty_0644_lock_is_accepted_without_chmod(legacy):
    root, expected, owner, _ = legacy
    lock = root / "report-workflows/catalog.lock"
    lock.chmod(0o644)
    before = lock.stat()
    result = preview(root, expected, operation_id="reviewed-op-001", owner_check=owner)
    after = lock.stat()
    assert result["status"] == "dry_run"
    assert (before.st_dev, before.st_ino, before.st_mode, before.st_size) == (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
    )
    assert after.st_mode & 0o777 == 0o644


@pytest.mark.parametrize("case", ["group_write", "nonempty", "symlink", "shared_parent"])
def test_existing_lock_unsafe_variants_refused(legacy, case):
    root, _, _, _ = legacy
    lock = root / "report-workflows/catalog.lock"
    if case == "group_write":
        lock.chmod(0o664)
    elif case == "nonempty":
        lock.write_bytes(b"0")
    elif case == "symlink":
        target = lock.with_name("original.lock")
        lock.rename(target)
        lock.symlink_to(target)
    elif case == "shared_parent":
        lock.parent.chmod(0o755)
    with pytest.raises(WorkflowError):
        ReportWorkflowService.open_for_maintenance(root)


@pytest.mark.parametrize("stage", ["before_open", "after_open", "before_reload"])
def test_maintenance_lock_replacement_refused(legacy, monkeypatch, stage):
    root, expected, owner, _ = legacy
    catalog = ReportWorkflowService.open_for_maintenance(root)
    lock = root / "report-workflows/catalog.lock"
    replacement = lock.with_name("replacement.lock")
    replacement.touch(mode=0o600)
    original_open = monitoring_module.os.open

    def swap():
        replacement.replace(lock)

    if stage == "before_reload":
        swap()
        with pytest.raises(WorkflowError):
            catalog._reload()
        return

    def swapping_open(path, *args, **kwargs):
        if path == lock:
            if stage == "before_open":
                swap()
            fd = original_open(path, *args, **kwargs)
            if stage == "after_open":
                swap()
            return fd
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(monitoring_module.os, "open", swapping_open)
    before = catalog.index.read_bytes()
    with pytest.raises(WorkflowError):
        catalog.end_legacy_monitoring(expected, operation_id="reviewed-op-001", owner_check=owner)
    assert catalog.index.read_bytes() == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("run_id", "b" * 32),
        ("session_id", "other-session"),
        ("version", 6),
        ("version", 5.0),
        ("owner_id", "other-owner"),
        ("profile", "other-profile"),
        ("operation_id", "other-operation"),
        ("expected_run_sha256", "b" * 64),
        ("disposition", "completed"),
        ("native_cancelled", True),
        ("native_cancelled", 0),
        ("ended_at", 0),
        ("ended_at", -1),
        ("ended_at", "123"),
        ("ended_at", True),
        ("ended_at", float("nan")),
        ("ended_at", float("inf")),
        ("ended_at", 100),
        ("ended_at", 10**1000),
        ("previous_control.status", "cancelled"),
        ("previous_control.monitoring_disposition", "ended_by_user"),
        ("previous_control.updated_at", 125),
        ("previous_control.updated_at", 124),
        ("previous_control.updated_at", None),
        ("previous_control.extra", "unknown"),
        ("extra", "unknown"),
    ],
)
def test_existing_receipt_tampering_refused_without_write(legacy, field, value):
    root, expected, _, _ = legacy
    act(legacy)
    path = root / "report-workflows/catalog.json"
    index = json.loads(path.read_bytes())
    receipt = index["runs"][expected.run_id]["monitoring_end_receipt"]
    parts = field.split(".")
    if len(parts) == 2:
        receipt[parts[0]][parts[1]] = value
    else:
        receipt[field] = value
    path.write_text(json.dumps(index))
    before = path.read_bytes()
    with pytest.raises(WorkflowError):
        act(legacy)
    assert path.read_bytes() == before


@pytest.mark.parametrize("changed", ["owner", "snapshot", "claim"])
def test_existing_receipt_still_revalidates_live_guards(legacy, changed):
    root, expected, _, _ = legacy
    act(legacy)
    path = root / "report-workflows/catalog.json"
    run = root / "report-workflows/runs" / expected.run_id
    if changed == "snapshot":
        (run / "snapshots/report-data.json").write_bytes(b"changed")
    elif changed == "claim":
        (run / "weekly-rpc-attempt.json").write_text("{}")
    before = path.read_bytes()
    owner = (lambda _: None) if changed == "owner" else None
    with pytest.raises(WorkflowError):
        act(legacy, owner=owner)
    assert path.read_bytes() == before
