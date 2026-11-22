"""Catalog size is not an ingestion limit; only pending or pinned bytes persist."""

import hashlib
import sqlite3
from types import SimpleNamespace

import pytest

from app.research_web.knowledge_backend import sync as sync_module
from app.research_web.knowledge_backend import sync_storage as storage_module
from app.research_web.store import StoreError
from tests.research_web.test_weknora_sync import service


@pytest.mark.asyncio
async def test_catalog_over_old_file_and_byte_thresholds_still_adds_changes_and_deletes(
    tmp_path, monkeypatch
):
    sync, _, inbox, _ = service(tmp_path)
    # Small byte threshold represents the former whole-catalog 64MiB gate.
    monkeypatch.setattr(sync_module, "MAX_SCAN_BYTES", 2, raising=False)
    for index in range(1001):
        (inbox / f"ignored-{index:04}.bin").write_bytes(b"x")
    (inbox / "old.txt").write_bytes(b"old")
    (inbox / "deleted.txt").write_bytes(b"deleted")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    assert {row["path"] for row in sync.current_documents()} == {"old.txt", "deleted.txt"}
    (inbox / "old.txt").write_bytes(b"changed")
    (inbox / "deleted.txt").unlink()
    (inbox / "new.txt").write_bytes(b"added")
    await sync.scan()
    await sync.scan()
    current = {row["path"]: row for row in sync.current_documents()}
    assert set(current) == {"old.txt", "new.txt"}
    assert current["old.txt"]["sha256"] == hashlib.sha256(b"changed").hexdigest()
    assert current["old.txt"]["version"] == 2


def test_collection_returns_only_metadata_and_rehashes_changed_stat_signature(
    tmp_path, monkeypatch
):
    sync, _, inbox, _ = service(tmp_path)
    path = inbox / "a.txt"
    path.write_bytes(b"original")
    original_read = sync._read_at
    reads = []

    def counted(*args, **kwargs):
        reads.append(args[1])
        return original_read(*args, **kwargs)

    monkeypatch.setattr(sync, "_read_at", counted)
    first = sync._collect(inbox)[0]["a.txt"]
    assert "content" not in first
    assert first["size"] == 8
    assert first["signature"]
    assert sync._collect(inbox)[0]["a.txt"]["sha256"] == first["sha256"]
    assert reads == ["a.txt"]
    path.write_bytes(b"different")
    assert sync._collect(inbox)[0]["a.txt"]["sha256"] == hashlib.sha256(b"different").hexdigest()
    assert reads == ["a.txt", "a.txt"]


@pytest.mark.asyncio
async def test_observing_and_published_unpinned_versions_do_not_keep_raw(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    (inbox / "a.txt").write_bytes(b"original")
    sha = hashlib.sha256(b"original").hexdigest()
    await sync.configure("kb1", True)
    await sync.scan()
    with pytest.raises(StoreError) as missing:
        sync.snapshot(sha)
    assert missing.value.code == "knowledge_sync_snapshot_unavailable"
    await sync.scan()
    assert sync.current_documents()[0]["sha256"] == sha
    assert upstream.uploads[0][1] == b"original"
    with pytest.raises(StoreError):
        sync.snapshot(sha)


@pytest.mark.asyncio
async def test_receipt_pin_survives_source_change_deletion_and_restart(tmp_path):
    sync, upstream, inbox, _ = service(tmp_path)
    path = inbox / "a.txt"
    path.write_bytes(b"original")
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    old_sha = sync.current_documents()[0]["sha256"]
    sync.pin_snapshot(old_sha, upstream.originals["d1"])
    sync.pin_snapshot(old_sha, upstream.originals["d1"])
    path.write_bytes(b"changed")
    await sync.scan()
    await sync.scan()
    new_sha = sync.current_documents()[0]["sha256"]
    assert new_sha != old_sha
    with pytest.raises(StoreError):
        sync.snapshot(new_sha)
    path.unlink()
    await sync.scan()
    sync.close()
    resumed, _, _, _ = service(tmp_path, upstream)
    assert resumed.current_documents() == []
    assert resumed.snapshot(old_sha) == b"original"
    assert len(resumed.history("a.txt")) == 2
    with pytest.raises(StoreError) as invalid:
        resumed.pin_snapshot(old_sha, b"wrong bytes")
    assert invalid.value.code == "knowledge_sync_snapshot_invalid"
    assert resumed.snapshot(old_sha) == b"original"


@pytest.mark.asyncio
@pytest.mark.parametrize("uncertain", [False, True])
async def test_pending_and_uncertain_upload_raw_survives_restart_exactly(tmp_path, uncertain):
    sync, upstream, inbox, _ = service(tmp_path)
    raw = b"exact uploaded snapshot"
    sha = hashlib.sha256(raw).hexdigest()
    (inbox / "a.txt").write_bytes(raw)
    upstream.parse_status = "processing"
    upstream.timeout_after_upload = uncertain
    await sync.configure("kb1", True)
    await sync.scan()
    await sync.scan()
    assert sync.snapshot(sha) == raw
    sync.close()
    resumed, _, _, _ = service(tmp_path, upstream)
    assert resumed.snapshot(sha) == raw
    upstream.documents["d1"]["parse_status"] = "completed"
    await resumed.scan()
    assert len(upstream.uploads) == 1
    with pytest.raises(StoreError):
        resumed.snapshot(sha)


@pytest.mark.asyncio
async def test_preservation_streams_database_without_whole_file_read(tmp_path, monkeypatch):
    sync, _, _, _ = service(tmp_path)
    await sync.configure("kb1", True)

    def forbidden(*args, **kwargs):
        pytest.fail("preservation must stream the SQLite file")

    monkeypatch.setattr(storage_module, "read_file", forbidden, raising=False)
    proof = sync.preservation()
    assert (
        proof["files"]["knowledge-sync/state.sqlite3"]
        == hashlib.sha256(sync.store.path.read_bytes()).hexdigest()
    )


@pytest.mark.asyncio
async def test_pin_growth_checks_real_disk_floor_without_replacing_old_pin(tmp_path, monkeypatch):
    sync, _, _, _ = service(tmp_path)
    await sync.configure("kb1", True)
    old_raw = b"accepted"
    old_sha = hashlib.sha256(old_raw).hexdigest()
    sync.pin_snapshot(old_sha, old_raw)
    monkeypatch.setattr(storage_module.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    new_raw = b"new"
    with pytest.raises(StoreError) as denied:
        sync.pin_snapshot(hashlib.sha256(new_raw).hexdigest(), new_raw)
    assert denied.value.code == "knowledge_sync_disk_space_insufficient"
    assert denied.value.status == 507
    assert sync.snapshot(old_sha) == old_raw


@pytest.mark.asyncio
async def test_legacy_snapshot_without_pin_table_survives_first_write_and_receipt_freeze(
    tmp_path, monkeypatch
):
    from app.research_web.knowledge_backend import models
    from app.research_web.knowledge_backend.sync import KnowledgeSyncService
    from tests.research_web.test_weknora_current import current as current_fixture

    backend, upstream, sid = await current_fixture.__wrapped__(tmp_path, monkeypatch)
    hit = (await backend.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]
    raw = upstream.original_bytes
    inbox = tmp_path / "legacy-inbox"
    inbox.mkdir()
    legacy = KnowledgeSyncService(backend.store.root, backend._authorized, default_root=inbox)
    await legacy.configure("kb1", True)
    # Construct only this test's A2 schema: raw existed before pin metadata did.
    with sqlite3.connect(legacy.store.path) as db:
        db.execute("DROP TABLE snapshot_pins")
        db.execute("INSERT INTO snapshots VALUES(?,?)", (hit["sha256"], raw))
    backend.sync = KnowledgeSyncService(backend.store.root, backend._authorized, default_root=inbox)
    assert backend.sync.snapshot(hit["sha256"]) == raw
    backend.sync.store.save_config(backend.sync.store.config())
    frozen = await backend.current_freeze(
        models.CurrentFreeze(session_id=sid, hit_ids=[hit["hit_id"]])
    )
    assert backend.store.original(frozen["id"], hit["sha256"]) == raw
    with sqlite3.connect(backend.sync.store.path) as db:
        assert db.execute("SELECT sha256 FROM snapshot_pins").fetchall() == [(hit["sha256"],)]
