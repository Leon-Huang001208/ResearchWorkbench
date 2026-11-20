"""Current material queries keep the authenticated session and exact cited version."""

import copy
import hashlib

import pytest

from app.research_web.knowledge_backend import models
from app.research_web.store import StoreError
from tests.research_web import test_weknora_service as fixtures


class CurrentSync:
    def __init__(self, upstream):
        self.original_bytes = upstream.original_bytes
        self.rows = [
            {
                "document_id": "d1",
                "kb_id": "kb1",
                "path": "paper.pdf",
                "version": 1,
                "sha256": hashlib.sha256(upstream.original_bytes).hexdigest(),
                "md5": hashlib.md5(upstream.original_bytes).hexdigest(),
            }
        ]

    def status(self):
        return {"configured": True, "enabled": True, "knowledge_base_id": "kb1"}

    def current_documents(self):
        return copy.deepcopy(self.rows)

    def matches_binding(self, binding):
        return binding["user_id"] == "user-a"

    def close(self):
        pass

    def snapshot(self, sha):
        assert hashlib.sha256(self.original_bytes).hexdigest() == sha
        return self.original_bytes


@pytest.fixture
async def current(tmp_path):
    service, upstream, _ = await fixtures.knowledge.__wrapped__(tmp_path)
    row = service.owner_store.create("fingpt", "Current research")
    row.update(created=True, source_scope=["uploads"])
    service.owner_store.save()
    service.sync = CurrentSync(upstream)
    return service, upstream, row["id"]


@pytest.mark.asyncio
async def test_current_query_uses_saved_ids_without_report_scope(current):
    service, upstream, sid = current
    result = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert ("search", "q", ["kb1"], ["d1"], 8) in upstream.calls
    assert not (service.store.root / "knowledge-backend/scopes").exists()
    item = result["items"][0]
    assert item["source_id"] == "knowledge:" + item["hit_id"]
    assert item["historical_eligible"] is False
    assert "document_id" not in item and "kb_id" not in item
    assert service.store.read("receipts", item["hit_id"])["session_id"] == sid


@pytest.mark.asyncio
async def test_current_query_batches_current_ids_then_ranks_global_top8(current):
    service, upstream, sid = current
    service.sync.rows = [dict(service.sync.rows[0], document_id=f"d{i}") for i in range(130)]

    async def search(query, bases, identifiers, limit):
        upstream.calls.append(("batch", identifiers))
        identifier = max(identifiers, key=lambda key: int(key[1:]))
        return [dict(upstream.hit, document_id=identifier, score=float(identifier[1:]))]

    async def chunks(identifier):
        return [dict(upstream.hit, document_id=identifier)]

    upstream.search, upstream.chunks = search, chunks
    result = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert [
        len(call[1]) for call in upstream.calls if isinstance(call, tuple) and call[0] == "batch"
    ] == [128, 2]
    assert result["items"][0]["document_version"] == 1
    receipt = service.store.read("receipts", result["items"][0]["hit_id"])
    assert receipt["document_id"] == "d129"


@pytest.mark.asyncio
async def test_current_query_rejects_foreign_or_excluded_session_before_network(current):
    service, upstream, sid = current
    upstream.calls.clear()
    for other in ("00000000-0000-0000-0000-000000000000",):
        with pytest.raises(StoreError):
            await service.current_query(models.CurrentQuery(session_id=other, query="q"))
    service.owner_store.session(sid)["source_scope"] = ["web"]
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "research_source_excluded"
    assert upstream.calls == []


@pytest.mark.asyncio
async def test_current_read_preserves_original_chunk_when_upstream_changes(current):
    service, upstream, sid = current
    hit = (await service.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]
    upstream.original_bytes = b"new version"
    upstream.hit["content"] = "new paragraph"
    result = await service.current_read(models.CurrentRead(session_id=sid, hit_id=hit["hit_id"]))
    assert result["content"] == "A cited paragraph"
    assert result["source_status"] == "changed"
    assert result["sha256"] == hit["sha256"]


@pytest.mark.asyncio
async def test_current_read_deleted_source_keeps_receipt_but_revocation_denies(current):
    service, upstream, sid = current
    hit = (await service.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]

    async def missing(_identifier):
        raise StoreError("missing", "weknora_not_found", 404)

    upstream.document = missing
    result = await service.current_read(models.CurrentRead(session_id=sid, hit_id=hit["hit_id"]))
    assert result["source_status"] == "deleted"
    upstream.active = False
    with pytest.raises(StoreError) as error:
        await service.current_read(models.CurrentRead(session_id=sid, hit_id=hit["hit_id"]))
    assert error.value.code == "weknora_auth_denied"


@pytest.mark.asyncio
async def test_current_read_rejects_cross_session_receipt(current):
    service, _, sid = current
    hit = (await service.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]
    other = service.owner_store.create("fingpt", "Other")
    other["created"] = True
    with pytest.raises(StoreError) as error:
        await service.current_read(models.CurrentRead(session_id=other["id"], hit_id=hit["hit_id"]))
    assert error.value.code == "knowledge_hit_session_mismatch"


@pytest.mark.asyncio
async def test_current_freeze_uses_receipt_bytes_and_never_grants_pit(current):
    service, upstream, sid = current
    original = upstream.original_bytes
    hit = (await service.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]
    upstream.original_bytes = b"replacement"
    result = await service.current_freeze(
        models.CurrentFreeze(session_id=sid, hit_ids=[hit["hit_id"]])
    )
    assert service.store.original(result["id"], hit["sha256"]) == original
    assert result["historical_eligible"] is False
    assert result["excerpts"][0]["content"] == "A cited paragraph"


@pytest.mark.asyncio
async def test_current_query_rejects_sync_hash_drift_and_kb_revoke(current):
    service, upstream, sid = current
    upstream.original_bytes = b"changed without directory sync"
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "knowledge_current_version_changed"

    async def denied():
        return []

    upstream.knowledge_bases = denied
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "knowledge_library_access_revoked"


@pytest.mark.asyncio
async def test_current_query_deduplicates_copies_of_same_verified_document(current):
    service, upstream, sid = current
    service.sync.rows.append(dict(service.sync.rows[0], path="duplicate.pdf"))
    result = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert len(result["items"]) == 1
    assert ("search", "q", ["kb1"], ["d1"], 8) in upstream.calls


@pytest.mark.asyncio
async def test_current_query_revocation_before_commit_publishes_no_receipt(current):
    service, upstream, sid = current
    original_chunks = upstream.chunks

    async def revoke(identifier):
        result = await original_chunks(identifier)
        upstream.active = False
        return result

    upstream.chunks = revoke
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "weknora_auth_denied"
    assert not (service.store.root / "knowledge-backend/receipts").exists()
    assert service.status()["connectivity"] == "authentication_required"


@pytest.mark.asyncio
async def test_current_query_sync_change_before_commit_publishes_no_receipt(current):
    service, upstream, sid = current
    original_chunks = upstream.chunks

    async def supersede(identifier):
        result = await original_chunks(identifier)
        service.sync.rows[0]["version"] = 2
        return result

    upstream.chunks = supersede
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "knowledge_current_version_changed"
    assert not (service.store.root / "knowledge-backend/receipts").exists()


@pytest.mark.asyncio
async def test_current_read_retains_chunk_when_reparse_is_pending(current):
    service, upstream, sid = current
    hit = (await service.current_query(models.CurrentQuery(session_id=sid, query="q")))["items"][0]
    original_document = upstream.document

    async def pending(identifier):
        return {**(await original_document(identifier)), "parse_status": "pending"}

    upstream.document = pending
    result = await service.current_read(models.CurrentRead(session_id=sid, hit_id=hit["hit_id"]))
    assert result["source_status"] == "changed" and result["content"] == "A cited paragraph"


@pytest.mark.asyncio
async def test_current_query_keeps_published_version_while_new_desired_version_is_pending(current):
    service, upstream, sid = current
    original_chunks = upstream.chunks

    async def pending(identifier):
        result = await original_chunks(identifier)
        service.sync.rows[0].update(desired_version=2, stable=1)
        return result

    upstream.chunks = pending
    result = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert result["items"][0]["document_version"] == 1
    hit = result["items"][0]["hit_id"]
    read = await service.current_read(models.CurrentRead(session_id=sid, hit_id=hit))
    assert read["source_status"] == "current"


@pytest.mark.asyncio
async def test_doctor_reports_last_verified_connection_without_new_network(current):
    from app.research_web.knowledge_backend.diagnostics import knowledge_diagnostic

    service, upstream, _ = current
    upstream.calls.clear()
    result = knowledge_diagnostic(service.store.root)
    assert result["connectivity"] == "verified" and result["last_verified_at"] is not None
    assert upstream.calls == []


@pytest.mark.asyncio
async def test_receipt_count_admission_preserves_readable_budget_and_idempotence(
    current, monkeypatch
):
    from app.research_web.knowledge_backend import storage

    service, upstream, sid = current
    monkeypatch.setattr(storage, "RECORD_LIMIT", 2, raising=False)
    first = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    upstream.hit["chunk_id"] = "c2"
    second = await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert (await service.current_query(models.CurrentQuery(session_id=sid, query="q"))) == second
    upstream.hit["chunk_id"] = "c3"
    with pytest.raises(StoreError) as error:
        await service.current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "knowledge_record_budget"
    assert len(service.store.records("receipts")) == 2
    assert service.store.preservation() is not None
    assert service.store.read("receipts", first["items"][0]["hit_id"])
