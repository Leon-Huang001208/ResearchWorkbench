"""Dossier metadata and pinned originals participate in resident preservation."""

from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.research_web.dossier_preservation import snapshot_dossiers
from app.research_web.dossiers import DossierService
from app.research_web.dossiers.lock import retention_lock
from app.research_web.multiuser.preservation import compare_snapshot, snapshot
from app.research_web.store import Store
from research_workbench_entrypoint.resident.model_provider_upgrade import asset_index_snapshot


def archive(root):
    research = SimpleNamespace(store=Store(root))
    research.store.save()
    research.dossiers = DossierService(research)
    dossier = research.dossiers.create(
        {
            "title": "保全档案",
            "subject": {"kind": "theme", "key": "energy-transition", "label": "能源转型"},
            "idempotency_key": "create-0001",
        }
    )
    return research, dossier


def test_absent_archive_does_not_initialize_files(tmp_path):
    store = Store(tmp_path / "personal")
    store.save()
    before = set(store.root.rglob("*"))
    assert snapshot_dossiers(store.root) is None
    assert snapshot(store.root)["files"] == {}
    assert set(store.root.rglob("*")) == before


def test_metadata_change_and_pinned_private_original_are_detected(tmp_path):
    research, dossier = archive(tmp_path / "personal")
    raw = research.store.root / ".control/snapshots/offline/raw-0001.bin"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"original")
    before = snapshot(research.store.root)
    assert "dossiers/metadata.sqlite3" in before["files"]
    assert ".dossiers-initialized" in before["files"]
    assert ".control/snapshots/offline/raw-0001.bin" in before["files"]
    assert compare_snapshot(before, snapshot(research.store.root))["preserved"]
    research.dossiers.patch(
        dossier["id"], {"expected_revision": 1, "idempotency_key": "patch-0001", "title": "新版"}
    )
    assert not compare_snapshot(before, snapshot(research.store.root))["preserved"]
    before = snapshot(research.store.root)
    raw.write_bytes(b"changed")
    assert not compare_snapshot(before, snapshot(research.store.root))["preserved"]


def test_busy_lock_fails_closed_and_recovers(tmp_path):
    research, _dossier = archive(tmp_path / "personal")
    with retention_lock(research.store.root), ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(snapshot_dossiers, research.store.root)
        with pytest.raises(RuntimeError, match="dossier_preservation_failed"):
            future.result()
    assert snapshot_dossiers(research.store.root)["files"]


@pytest.mark.parametrize("damage", ["corrupt", "symlink", "hardlink", "folder"])
def test_damaged_metadata_fails_closed(tmp_path, damage):
    research, _dossier = archive(tmp_path / "personal")
    path = research.dossiers.metadata.path
    if damage == "corrupt":
        path.write_bytes(b"not sqlite")
    elif damage == "symlink":
        original = tmp_path / "original.sqlite3"
        path.rename(original)
        path.symlink_to(original)
    elif damage == "hardlink":
        (tmp_path / "second.sqlite3").hardlink_to(path)
    else:
        path.parent.rename(tmp_path / "lost-dossiers")
    with pytest.raises(RuntimeError, match="dossier_preservation_failed"):
        snapshot_dossiers(research.store.root)
    with pytest.raises(RuntimeError, match="preservation_snapshot_failed"):
        snapshot(research.store.root)


def test_existing_asset_preservation_protocol_covers_dossier_state(tmp_path):
    home = tmp_path / "home"
    (home / "server/users").mkdir(parents=True)
    research, dossier = archive(home / "research-web")
    before = asset_index_snapshot(home)
    assert "@dossiers" in before["primary"]
    assert asset_index_snapshot(home) == before
    research.dossiers.patch(
        dossier["id"], {"expected_revision": 1, "idempotency_key": "patch-0001", "title": "变更"}
    )
    after = asset_index_snapshot(home)
    assert before["primary"]["@dossiers"] != after["primary"]["@dossiers"]


def test_strict_readonly_snapshot_keeps_full_original_and_model_scope(tmp_path):
    research, _dossier = archive(tmp_path / "personal")
    raw = research.store.root / ".control/snapshots/offline/raw-0001.bin"
    raw.parent.mkdir(parents=True)
    raw.write_bytes(b"original")
    before = snapshot(research.store.root, create_dossier_lock=False)
    assert "dossiers/metadata.sqlite3" in before["files"]
    assert ".control/snapshots/offline/raw-0001.bin" in before["files"]
    assert before == snapshot(research.store.root)
    raw.write_bytes(b"changed")
    assert not compare_snapshot(before, snapshot(research.store.root, create_dossier_lock=False))[
        "preserved"
    ]


def test_strict_readonly_lock_disappearing_at_open_never_recreates_it(tmp_path, monkeypatch):
    import os
    from pathlib import Path

    from app.research_web.dossiers import lock

    research, _dossier = archive(tmp_path / "personal")
    path = research.store.root / ".dossier-retention.lock"
    original_open = os.open
    opened = []

    def remove_at_open(target, flags, *args, **kwargs):
        if Path(target) == path:
            opened.append(flags)
            path.unlink()
        return original_open(target, flags, *args, **kwargs)

    monkeypatch.setattr(lock.os, "open", remove_at_open)
    with pytest.raises(RuntimeError, match="dossier_preservation_failed"):
        snapshot_dossiers(research.store.root, create_lock=False)
    assert len(opened) == 1
    assert not opened[0] & os.O_CREAT
    assert not path.exists()


def test_strict_snapshot_rejects_clean_wal_header_without_creating_sidecars(tmp_path):
    import sqlite3

    research, _dossier = archive(tmp_path / "personal")
    database = research.dossiers.metadata.path
    with sqlite3.connect(database) as connection:
        assert connection.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    connection.close()
    assert database.read_bytes()[18:20] == bytes([2, 2])
    assert not database.with_name(database.name + "-wal").exists()
    assert not database.with_name(database.name + "-shm").exists()

    def inventory():
        return {
            str(p.relative_to(tmp_path)): p.read_bytes() if p.is_file() else None
            for p in tmp_path.rglob("*")
        }

    before = inventory()
    rejected = False
    try:
        snapshot_dossiers(research.store.root, create_lock=False)
    except RuntimeError:
        rejected = True
    assert inventory() == before
    assert rejected, "strict observation must explicitly refuse unsupported WAL storage"


@pytest.mark.parametrize("suffix", ["-wal", "-shm", "-journal"])
def test_strict_snapshot_never_ignores_existing_sqlite_sidecars(tmp_path, suffix):
    research, _dossier = archive(tmp_path / "personal")
    database = research.dossiers.metadata.path
    database.with_name(database.name + suffix).write_bytes(b"unknown pending database state")
    before = {
        str(p.relative_to(tmp_path)): p.read_bytes() if p.is_file() else None
        for p in tmp_path.rglob("*")
    }
    with pytest.raises(RuntimeError, match="dossier_preservation_failed"):
        snapshot_dossiers(research.store.root, create_lock=False)
    assert before == {
        str(p.relative_to(tmp_path)): p.read_bytes() if p.is_file() else None
        for p in tmp_path.rglob("*")
    }


def test_strict_snapshot_validates_only_in_memory_and_keeps_all_integrity_checks(
    tmp_path, monkeypatch
):
    import sqlite3

    research, _dossier = archive(tmp_path / "personal")
    real_connect = sqlite3.connect
    opened, queries = [], []

    class MemoryConnection:
        def __init__(self, connection):
            self.connection = connection

        def execute(self, query):
            queries.append(query)
            return self.connection.execute(query)

        def deserialize(self, raw):
            return self.connection.deserialize(raw)

        def close(self):
            self.connection.close()

    def connect(path, *args, **kwargs):
        opened.append(path)
        assert path == ":memory:"
        return MemoryConnection(real_connect(path, *args, **kwargs))

    monkeypatch.setattr(sqlite3, "connect", connect)
    result = snapshot_dossiers(research.store.root, create_lock=False)
    assert opened == [":memory:"]
    assert result["files"]["dossiers/metadata.sqlite3"]
    assert {
        "SELECT owner_binding FROM identity",
        "PRAGMA user_version",
        "PRAGMA quick_check",
        "PRAGMA foreign_key_check",
    } <= set(queries)


def test_strict_snapshot_rejects_fifo_swap_before_open_without_blocking(tmp_path, monkeypatch):
    import os
    import stat
    from pathlib import Path

    from app.research_web import dossier_preservation

    research, _dossier = archive(tmp_path / "personal")
    database = research.dossiers.metadata.path
    original = database.read_bytes()
    saved = database.with_name("metadata-saved.sqlite3")
    real_open = os.open
    opened = []

    def swap_at_open(path, flags, *args, **kwargs):
        if Path(path) == database:
            opened.append(flags)
            # Baseline RED is bounded: never attempt a blocking FIFO open.
            if not flags & os.O_NONBLOCK:
                raise AssertionError("strict database open must be nonblocking")
            database.rename(saved)
            os.mkfifo(database, 0o600)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(dossier_preservation.os, "open", swap_at_open)
    with pytest.raises(RuntimeError, match="dossier_preservation_failed"):
        snapshot_dossiers(research.store.root, create_lock=False)
    assert len(opened) == 1
    assert opened[0] & os.O_NONBLOCK
    assert stat.S_ISFIFO(database.lstat().st_mode)
    assert saved.read_bytes() == original
