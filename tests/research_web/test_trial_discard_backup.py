"""Offline trial backup proofs. Fixtures never point at a resident home."""

import json
import os
import shutil
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from research_workbench_entrypoint.resident.trial_discard_backup import (
    TrialBackupBlocked,
    backup,
    preview,
)


def _fixture(tmp_path: Path):
    tmp_path = tmp_path.resolve()
    home = tmp_path / "synthetic-home"
    server = home / "server"
    users = server / "users"
    users.mkdir(parents=True)
    primary, secondary = str(uuid4()), str(uuid4())
    db = server / "accounts.sqlite3"
    with sqlite3.connect(db) as connection:
        connection.execute("CREATE TABLE accounts (id TEXT PRIMARY KEY)")
        connection.executemany("INSERT INTO accounts VALUES (?)", [(primary,), (secondary,)])
    (server / "resident.json").write_text(json.dumps({"binding": {"primary_user_id": primary}}))
    main = home / "research-web"
    private = users / secondary / "research-web"
    main.mkdir()
    private.mkdir(parents=True)
    (main / "index.json").write_text(
        json.dumps(
            {
                "sessions": {"old-sid": {"status": "running", "secret": "hidden"}},
                "model_provider": {"credential": "hidden-key"},
            }
        )
    )
    (private / "index.json").write_text(
        json.dumps({"sessions": {"second": {"status": "completed"}}})
    )
    safe = tmp_path / "protected-backups"
    safe.mkdir(mode=0o700)
    return home, safe, secondary


def test_multiuser_preview_and_restorable_backup(tmp_path):
    home, safe, secondary = _fixture(tmp_path)
    before = preview(home)
    assert len(before["roots"]) == 2
    assert before["roots"][0]["sessions"] == {"old-sid": "running"}
    assert "hidden" not in json.dumps(before)
    assert before["roots"][1]["account_id"] == secondary
    result = backup(home, safe, before["seal"])
    assert result["status"] == "restore_verified"
    point = Path(result["backup"])
    assert (point / "server/accounts.sqlite3").read_bytes() == (
        home / "server/accounts.sqlite3"
    ).read_bytes()
    assert (point / "research-web/index.json").read_bytes() == (
        home / "research-web/index.json"
    ).read_bytes()
    private_index = Path("server/users") / secondary / "research-web/index.json"
    assert (point / private_index).read_bytes() == (home / private_index).read_bytes()
    assert result["manifest_sha256"] and (point / "manifest.json").is_file()


def test_changed_index_refused_before_backup(tmp_path):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    path = home / "research-web/index.json"
    path.write_text(path.read_text().replace("running", "completed"))
    with pytest.raises(TrialBackupBlocked, match="trial_preview_drift"):
        backup(home, safe, seal)
    assert list(safe.iterdir()) == []


def test_dirty_database_and_unknown_mapping_refused(tmp_path):
    home, _, _ = _fixture(tmp_path)
    (home / "server/accounts.sqlite3-wal").write_bytes(b"dirty")
    with pytest.raises(TrialBackupBlocked, match="trial_account_db_unstable"):
        preview(home)
    (home / "server/accounts.sqlite3-wal").unlink()
    (home / "server/users" / str(uuid4())).mkdir()
    with pytest.raises(TrialBackupBlocked, match="trial_account_mapping_unknown"):
        preview(home)


def test_large_index_and_symlink_refused(tmp_path, monkeypatch):
    home, _, secondary = _fixture(tmp_path)
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    monkeypatch.setattr(module, "MAX_ASSET_INDEX_BYTES", 32)
    with pytest.raises(TrialBackupBlocked, match="trial_file_unsafe_or_oversize"):
        preview(home)
    monkeypatch.setattr(module, "MAX_ASSET_INDEX_BYTES", 64 * 1024 * 1024)
    path = home / "server/users" / secondary / "research-web/index.json"
    path.unlink()
    path.symlink_to(home / "research-web/index.json")
    with pytest.raises(TrialBackupBlocked):
        preview(home)


def test_missing_private_index_is_explicit(tmp_path):
    home, _, secondary = _fixture(tmp_path)
    (home / "server/users" / secondary / "research-web/index.json").unlink()
    state = preview(home)
    assert state["roots"][1]["index"] == "missing"


def test_restore_corruption_refuses_receipt(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    original = module._write_new

    def corrupt(directory_fd, name, raw, mode):
        if name.startswith(".restore-"):
            raw = b"corrupt"
        return original(directory_fd, name, raw, mode)

    monkeypatch.setattr(module, "_write_new", corrupt)
    with pytest.raises(TrialBackupBlocked, match="trial_backup_incomplete"):
        backup(home, safe, seal)
    assert len(list(safe.iterdir())) == 1  # Protected partial backup remains for inspection.


def test_index_larger_than_legacy_limit_is_supported(tmp_path):
    home, _, _ = _fixture(tmp_path)
    path = home / "research-web/index.json"
    path.write_text(json.dumps({"sessions": {}, "padding": "x" * (32 * 1024 * 1024)}))
    state = preview(home)
    assert state["roots"][0]["index_identity"]["size"] > 32 * 1024 * 1024


def test_backup_parent_symlink_ancestor_refused(tmp_path):
    home, _, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    target = tmp_path.resolve() / "target"
    target.mkdir(mode=0o700)
    alias = tmp_path.resolve() / "alias"
    alias.symlink_to(target, target_is_directory=True)
    child = alias / "protected"
    child.mkdir(mode=0o700)
    with pytest.raises(TrialBackupBlocked):
        backup(home, child, seal)
    assert list(child.iterdir()) == []


def test_account_and_aggregate_budgets_refused(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    monkeypatch.setattr(module, "MAX_ACCOUNT_ROOTS", 1)
    with pytest.raises(TrialBackupBlocked, match="trial_account_budget_exceeded"):
        preview(home)
    monkeypatch.setattr(module, "MAX_ACCOUNT_ROOTS", 64)
    monkeypatch.setattr(module, "MAX_TOTAL_BYTES", 100)
    with pytest.raises(TrialBackupBlocked, match="trial_total_budget_exceeded"):
        preview(home)
    assert list(safe.iterdir()) == []


def test_low_free_space_refused_before_point_creation(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    monkeypatch.setattr(module.os, "fstatvfs", lambda _fd: SimpleNamespace(f_bavail=1, f_frsize=1))
    with pytest.raises(TrialBackupBlocked, match="trial_backup_space_low"):
        backup(home, safe, seal)
    assert list(safe.iterdir()) == []


def test_space_budget_uses_pinned_parent_after_path_swap(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    original_identity = (safe.stat().st_dev, safe.stat().st_ino)
    moved = tmp_path.resolve() / "moved-space-parent"
    outside = tmp_path.resolve() / "outside-space-parent"
    outside.mkdir(mode=0o700)
    observed = []

    def low_space_on_pinned_fd(fd):
        observed.append((os.fstat(fd).st_dev, os.fstat(fd).st_ino))
        safe.rename(moved)
        safe.symlink_to(outside, target_is_directory=True)
        return SimpleNamespace(f_bavail=1, f_frsize=1)

    monkeypatch.setattr(module.os, "fstatvfs", low_space_on_pinned_fd)
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _path: (_ for _ in ()).throw(AssertionError("path probe"))
    )
    with pytest.raises(TrialBackupBlocked, match="trial_backup_space_low"):
        backup(home, safe, seal)
    assert observed == [original_identity]
    assert list(outside.iterdir()) == []
    assert list(moved.iterdir()) == []


def test_directory_sync_failure_refuses_receipt(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    original = os.fsync

    def fail_directory(fd):
        if os.path.isdir(f"/dev/fd/{fd}"):
            raise OSError("directory sync failure")
        return original(fd)

    monkeypatch.setattr(module.os, "fsync", fail_directory)
    with pytest.raises(TrialBackupBlocked):
        backup(home, safe, seal)


def test_backup_parent_swap_refuses_receipt_and_does_not_write_new_target(tmp_path, monkeypatch):
    home, safe, _ = _fixture(tmp_path)
    seal = preview(home)["seal"]
    import research_workbench_entrypoint.resident.trial_discard_backup as module

    moved = tmp_path.resolve() / "moved"
    outside = tmp_path.resolve() / "outside"
    outside.mkdir(mode=0o700)
    original = module._write_new
    swapped = False

    def swap(directory_fd, name, raw, mode):
        nonlocal swapped
        if not swapped:
            safe.rename(moved)
            safe.symlink_to(outside, target_is_directory=True)
            swapped = True
        return original(directory_fd, name, raw, mode)

    monkeypatch.setattr(module, "_write_new", swap)
    with pytest.raises(TrialBackupBlocked):
        backup(home, safe, seal)
    assert list(outside.iterdir()) == []
    assert len(list(moved.iterdir())) == 1
