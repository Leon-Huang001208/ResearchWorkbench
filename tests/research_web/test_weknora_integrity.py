"""Regression cases from independent review of report-source binding."""

import asyncio

import pytest

from app.research_web.knowledge_backend import models
from app.research_web.knowledge_backend.service import KnowledgeService
from app.research_web.knowledge_backend.storage import KnowledgeStore
from app.research_web.store import Store, StoreError
from tests.research_web import test_weknora_service as service_fixtures
from tests.research_web.test_weknora_service import approved


@pytest.fixture(autouse=True)
def stable_storage_capacity(monkeypatch):
    from app.research_web.knowledge_backend import storage

    monkeypatch.setattr(storage, "_available_bytes", lambda root: 100 * 1024**3, raising=False)


@pytest.fixture
async def knowledge(tmp_path, monkeypatch):
    return await service_fixtures.knowledge.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.asyncio
async def test_edited_chunk_requires_new_approval_for_all_report_reads(knowledge):
    service, upstream, _ = knowledge
    scope = await service.create_scope(approved())
    upstream.hit["content"] = "new claim inserted after report approval"
    for operation in (
        service.search(models.Search(query="q", knowledge_base_ids=["kb1"], scope_id=scope["id"])),
        service.read(models.Read(document_id="d1", scope_id=scope["id"])),
        service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]})),
    ):
        with pytest.raises(StoreError) as error:
            await operation
        assert error.value.code == "knowledge_chunks_changed"


def test_manifest_budget_rejected_before_any_staging_directory(tmp_path):
    store = Store(tmp_path / "owner")
    with pytest.raises(StoreError) as error:
        KnowledgeStore(store.root).create("evidence", {"content": "中" * 100000})
    assert error.value.code == "knowledge_manifest_budget"
    assert not (store.root / "knowledge-backend").exists()


def test_bad_operator_origin_never_returns_credentials(tmp_path):
    for value in (
        "https://user:password@host",
        "https://host?token=secret",
        "https://host/#secret",
    ):
        result = KnowledgeService(Store(tmp_path / "owner"), origin=value).status()
        assert result["management_url"] is None
        assert result["enabled"] is False
        assert "secret" not in str(result) and "password" not in str(result)


@pytest.mark.asyncio
async def test_total_business_deadline_does_not_publish_scope(knowledge, monkeypatch):
    from app.research_web.knowledge_backend import service as module

    service, upstream, _ = knowledge

    async def slow(_identifier):
        await asyncio.sleep(1)

    monkeypatch.setattr(module, "OPERATION_TIMEOUT", 0.005)
    upstream.original = slow
    with pytest.raises(StoreError) as error:
        await service.create_scope(approved())
    assert error.value.code == "knowledge_operation_timeout"
    assert not (service.store.root / "knowledge-backend/scopes").exists()


@pytest.mark.asyncio
async def test_business_preservation_includes_binding_and_frozen_original(knowledge):
    from app.research_web.multiuser.preservation import snapshot

    service, _, _ = knowledge
    Store(service.store.root).save()
    scope = await service.create_scope(approved())
    evidence = await service.freeze(models.Freeze(scope_id=scope["id"], chunks={"d1": ["c1"]}))
    value = snapshot(service.store.root, create_dossier_lock=False)
    assert "knowledge-backend/binding.json" in value["files"]
    assert any(evidence["id"] in name and name.endswith(".bin") for name in value["files"])
    original = (
        service.store.root
        / "knowledge-backend/evidence"
        / evidence["id"]
        / (evidence["documents"][0]["sha256"] + ".bin")
    )
    original.write_bytes(b"tampered")
    with pytest.raises(RuntimeError, match="preservation_snapshot_failed"):
        snapshot(service.store.root, create_dossier_lock=False)


def test_orphan_staging_is_unknown_to_doctor(tmp_path):
    from app.research_web.knowledge_backend.diagnostics import knowledge_diagnostic

    store = Store(tmp_path / "owner")
    (store.root / "knowledge-backend").mkdir(mode=0o700)
    assert knowledge_diagnostic(store.root)["state"] == "needs_attention"


@pytest.mark.asyncio
async def test_maintenance_fence_precedes_remote_reads_and_evidence_writes(
    knowledge, tmp_path, monkeypatch
):
    from research_workbench_entrypoint.resident.admission import file_lock

    service, upstream, _ = knowledge
    home = tmp_path / "resident"
    monkeypatch.setenv("RESEARCH_RESIDENT_HOME", str(home))
    upstream.calls.clear()
    with file_lock(home, "admission.lock", exclusive=True), pytest.raises(StoreError) as error:
        await service.create_scope(approved())
    assert error.value.code == "knowledge_maintenance_busy"
    assert upstream.calls == []
    assert not (service.store.root / "knowledge-backend/scopes").exists()


@pytest.mark.asyncio
async def test_active_material_read_keeps_resident_shared_lease(knowledge, tmp_path, monkeypatch):
    from research_workbench_entrypoint.resident.admission import MaintenanceBusy, file_lock

    service, upstream, _ = knowledge
    home = tmp_path / "resident"
    monkeypatch.setenv("RESEARCH_RESIDENT_HOME", str(home))
    entered, released = asyncio.Event(), asyncio.Event()

    async def delayed_bases():
        entered.set()
        await released.wait()
        return []

    upstream.knowledge_bases = delayed_bases
    pending = asyncio.create_task(service.bases())
    await entered.wait()
    try:
        with pytest.raises(MaintenanceBusy), file_lock(home, "admission.lock", exclusive=True):
            pass
    finally:
        released.set()
        await pending
    with file_lock(home, "admission.lock", exclusive=True):
        pass


@pytest.mark.asyncio
async def test_binding_budget_preserves_previous_readable_binding(knowledge):
    service, _, _ = knowledge
    previous = service.store.binding()
    oversized = {**previous, "retained_credentials": ["a" * 32] * 1000}
    with pytest.raises(StoreError) as error:
        service.store.save_binding(oversized)
    assert error.value.code == "knowledge_binding_budget"
    assert service.store.binding() == previous


@pytest.mark.asyncio
async def test_more_than1000_receipts_remain_writable_readable_and_preserved(knowledge):
    from app.research_web.knowledge_backend.storage import canonical, digest

    service, _, _ = knowledge
    folder = service.store.root / "knowledge-backend/receipts"
    folder.mkdir(mode=0o700)
    identifiers = []
    for index in range(1001):
        manifest = {
            "schema": 1,
            "owner": service.store.owner,
            "kind": "receipts",
            "payload": {"counter": index},
            "files": {},
        }
        raw = canonical(manifest)
        identifier = digest(raw)
        path = folder / identifier
        path.mkdir(mode=0o700)
        (path / "manifest.json").write_bytes(raw)
        (path / "manifest.json").chmod(0o600)
        identifiers.append(identifier)
    assert service.store.read("receipts", identifiers[0])["counter"] == 0
    added = service.store.create("receipts", {"counter": 1001})
    assert len(list(service.store.records("receipts"))) == 1002
    proof = service.store.preservation()
    assert f"knowledge-backend/receipts/{added['id']}/manifest.json" in proof["files"]


@pytest.mark.asyncio
async def test_history_preservation_hashes_originals_without_cumulative_read_budget(
    knowledge, monkeypatch
):
    from app.research_web.knowledge_backend import storage

    service, _, _ = knowledge
    for index in range(9):
        raw = f"body {index}".encode()
        sha = storage.digest(raw)
        service.store.create("evidence", {"documents": [{"sha256": sha}]}, {sha + ".bin": raw})
    read = storage.read_file
    body_reads = []

    class LargeAccountingBytes(bytes):
        def __len__(self):
            return 8 * 1024 * 1024

    def counted(fd, name, **kwargs):
        raw = read(fd, name, **kwargs)
        if name.endswith(".bin"):
            body_reads.append(name)
            return LargeAccountingBytes(raw)
        return raw

    monkeypatch.setattr(storage, "read_file", counted)
    proof = service.store.preservation()
    assert len([name for name in proof["files"] if name.endswith(".bin")]) == 9
    assert body_reads == []


@pytest.mark.asyncio
async def test_record_transaction_and_disk_floor_failures_do_not_damage_history(
    knowledge, monkeypatch
):
    from app.research_web.knowledge_backend import storage

    service, _, _ = knowledge
    old = service.store.create("receipts", {"counter": 0})
    monkeypatch.setattr(storage, "TRANSACTION_LIMIT", 16, raising=False)
    contents = (b"first original", b"second original")
    with pytest.raises(StoreError) as failure:
        service.store.create(
            "evidence", {}, {storage.digest(raw) + ".bin": raw for raw in contents}
        )
    assert failure.value.code == "knowledge_evidence_budget"
    monkeypatch.setattr(storage, "TRANSACTION_LIMIT", 32 * 1024 * 1024, raising=False)
    monkeypatch.setattr(storage, "ORIGINAL_LIMIT", 8, raising=False)
    raw = b"oversized"
    with pytest.raises(StoreError) as failure:
        service.store.create("evidence", {}, {storage.digest(raw) + ".bin": raw})
    assert failure.value.code == "knowledge_original_budget"
    monkeypatch.setattr(storage, "_available_bytes", lambda root: 0, raising=False)
    with pytest.raises(StoreError) as failure:
        service.store.create("receipts", {"counter": 1})
    assert failure.value.code == "knowledge_storage_insufficient"
    assert service.store.read("receipts", old["id"])["counter"] == 0
