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
