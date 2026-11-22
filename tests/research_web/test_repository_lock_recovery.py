"""Retirement is explicit, preserves exact bytes and never affects live owners."""

import os
from pathlib import Path

import pytest

from research_workbench_entrypoint.resident import repository_lock_recovery as r


def test_current_process_is_alive_and_never_signalled():
    assert r.alive(os.getpid()) is True


@pytest.mark.parametrize("pid", [None, 0, -1, True, "123"])
def test_invalid_owner_cannot_be_inferred_dead(pid):
    with pytest.raises(r.TransferBlocked):
        r.alive(pid)


@pytest.fixture
def lock(tmp_path, monkeypatch):
    project = tmp_path / "source"
    common = project / ".git"
    folder = common / "leon-engineering/git-safety"
    folder.mkdir(parents=True)
    path = folder / "repository.lock"
    raw = b'{"pid":999999,"nonce":"0123456789abcdef"}'
    path.write_bytes(raw)
    path.chmod(0o600)
    monkeypatch.setattr(r, "_common", lambda p: common)
    monkeypatch.setattr(r, "_remote", lambda p: "Leon-Huang001208/ResearchWorkbench")
    monkeypatch.setattr(r, "alive", lambda pid: False)

    class Good:
        returncode = 0

    monkeypatch.setattr(r.subprocess, "run", lambda *a, **kw: Good())
    return project, path, raw


def test_verified_retirement_preserves_backup_and_original_inode(lock, tmp_path):
    project, path, raw = lock
    inode = path.stat().st_ino
    plan = r.inspected(project)
    result = r.retire(plan, tmp_path / "backup")
    assert not path.exists()
    assert Path(result["archive"]).read_bytes() == raw
    assert Path(result["archive"]).stat().st_ino == inode
    assert (Path(result["backup"]) / "repository.lock").read_bytes() == raw


def test_new_owner_or_native_writer_is_protected(lock, tmp_path, monkeypatch):
    project, path, raw = lock
    plan = r.inspected(project)
    (project / ".git/index.lock").write_text("writer")
    with pytest.raises(r.TransferBlocked, match="native_writer"):
        r.retire(plan, tmp_path / "backup")
    assert path.read_bytes() == raw


def test_owner_becoming_live_stops_before_retirement(lock, tmp_path, monkeypatch):
    project, path, raw = lock
    plan = r.inspected(project)
    monkeypatch.setattr(r, "alive", lambda pid: True)
    with pytest.raises(r.TransferBlocked, match="owner_alive"):
        r.retire(plan, tmp_path / "backup")
    assert path.read_bytes() == raw


def test_changed_nonce_is_not_retired(lock, tmp_path):
    project, path, _raw = lock
    plan = r.inspected(project)
    path.write_text('{"pid":999999,"nonce":"fedcba9876543210"}')
    with pytest.raises(r.TransferBlocked, match="preview_changed"):
        r.retire(plan, tmp_path / "backup")
    assert path.exists()


@pytest.mark.parametrize(
    "name",
    [
        "FETCH_HEAD.lock",
        "ORIG_HEAD.lock",
        "MERGE_HEAD.lock",
        "AUTO_MERGE.lock",
        "config.worktree.lock",
        "shallow.lock",
    ],
)
def test_complete_native_lock_list_is_enforced(lock, name):
    project, path, raw = lock
    (project / ".git" / name).write_text("native writer")
    with pytest.raises(r.TransferBlocked, match="native_writer"):
        r.inspected(project)
    assert path.read_bytes() == raw


def test_second_recovery_is_excluded_without_touching_existing_fence(lock, tmp_path):
    project, path, raw = lock
    plan = r.inspected(project)
    fence = path.parent / "repository-recovery.lock"
    fence.write_text("other recovery")
    with pytest.raises(r.TransferBlocked, match="recovery_busy"):
        r.retire(plan, tmp_path / "backup")
    assert path.read_bytes() == raw and fence.read_text() == "other recovery"


def test_native_writer_appearing_during_backup_blocks_retirement(lock, tmp_path, monkeypatch):
    project, path, raw = lock
    plan = r.inspected(project)
    original = r.no_native_locks
    calls = []

    def later(common):
        calls.append(1)
        if len(calls) > 1:
            (common / "FETCH_HEAD.lock").write_text("later writer")
        return original(common)

    monkeypatch.setattr(r, "no_native_locks", later)
    with pytest.raises(r.TransferBlocked, match="native_writer"):
        r.retire(plan, tmp_path / "backup")
    assert path.read_bytes() == raw


def test_windows_owner_probe_refuses_without_signalling(monkeypatch):
    called = []
    monkeypatch.setattr(r.sys, "platform", "win32")
    monkeypatch.setattr(r.os, "kill", lambda *a: called.append(a))
    with pytest.raises(r.TransferBlocked, match="host_unsupported"):
        r.alive(123)
    assert called == []
