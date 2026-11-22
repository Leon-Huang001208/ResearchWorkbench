"""Approved Native knowledge uses the current opaque-hit interface, not model scope IDs."""

import asyncio
import copy
from types import SimpleNamespace

import pytest

from app.research_web.knowledge_backend import models
from app.research_web.knowledge_backend.routes import active_scope
from app.research_web.store import StoreError
from tests.research_web import test_weknora_service as fixtures


@pytest.fixture
async def formal(tmp_path, monkeypatch):
    service, upstream, _ = await fixtures.knowledge.__wrapped__(tmp_path, monkeypatch)
    scope = await service.create_scope(fixtures.approved())
    row = service.owner_store.create("fingpt", "Approved research")
    sid = row["id"]
    row.update(created=True, source_scope=["uploads"])
    delivery = {"task_id": "native-request", "status": "pending"}
    service.owner_store.reserve(
        sid,
        "approved-key",
        "a" * 64,
        delivery,
        knowledge_scope_id=scope["id"],
        knowledge_request_digest="b" * 64,
    )
    service.owner_store.receipt(sid, "approved-key", "accepted")
    events = [
        {"event": {"type": "turn/start", "data": {"turn": 1}}},
        {"event": {"type": "user/message", "data": {"source": {"rpcId": "native-request"}}}},
    ]
    native = {"sessionId": sid, "running": True}

    async def owned():
        return None

    async def history(requested):
        assert requested == sid
        return events

    async def rpc(method, _):
        assert method == "session.list"
        return {"items": [native]}

    host = SimpleNamespace(
        store=service.owner_store,
        knowledge=service,
        connected={"mux", "host"},
        ensure_owned=owned,
        client=SimpleNamespace(history=history, rpc=rpc),
    )
    return service, upstream, host, sid, scope, delivery, events, native


async def query(f):
    service, _, host, sid, *_ = f
    return await service.current_query(
        models.CurrentQuery(session_id=sid, query="source"), host=host, caller_session_id=sid
    )


async def read(f, hit_id):
    service, _, host, sid, *_ = f
    return await service.current_read(
        models.CurrentRead(session_id=sid, hit_id=hit_id), host=host, caller_session_id=sid
    )


@pytest.mark.asyncio
async def test_approved_scope_returns_opaque_hits_without_sync_configuration(formal):
    service, upstream, _, sid, scope, *_ = formal
    assert not service.sync.status().get("configured")
    item = (await query(formal))["items"][0]
    assert item["session_id"] == sid and len(item["hit_id"]) == 64
    assert item["historical_eligible"] is False
    assert not {"document_id", "kb_id", "knowledge_scope_id", "native_grant"} & item.keys()
    receipt = service.store.read("receipts", item["hit_id"])
    assert receipt["knowledge_scope_id"] == scope["id"]
    assert receipt["native_grant"][1:] == ["native-request", "b" * 64, "a" * 64]
    result = await read(formal, item["hit_id"])
    assert result["content"] == upstream.hit["content"]
    assert result["source_id"] == "knowledge:" + item["hit_id"]


@pytest.mark.asyncio
@pytest.mark.parametrize("caller", [None, "native-child", "different-root"])
async def test_formal_scope_requires_trusted_actual_native_root_caller(formal, caller):
    service, upstream, host, sid, *_ = formal
    upstream.calls.clear()
    with pytest.raises(StoreError) as error:
        await service.current_query(
            models.CurrentQuery(session_id=sid, query="q"), host=host, caller_session_id=caller
        )
    assert error.value.code == "knowledge_run_not_authorized"
    assert upstream.calls == []


@pytest.mark.asyncio
async def test_formal_session_cannot_use_ordinary_current_service_path(formal):
    service, upstream, _, sid, *_ = formal
    upstream.calls.clear()
    with pytest.raises(StoreError) as error:
        await service._current_query(models.CurrentQuery(session_id=sid, query="q"))
    assert error.value.code == "knowledge_run_not_authorized"
    assert upstream.calls == []


@pytest.mark.asyncio
async def test_formal_caller_cannot_select_an_ordinary_session_to_bypass_scope(formal):
    service, upstream, host, sid, *_ = formal
    other = service.owner_store.create("fingpt", "Unapproved current query")["id"]
    service.owner_store.session(other).update(created=True, source_scope=["uploads"])
    upstream.calls.clear()
    with pytest.raises(StoreError) as error:
        await service.current_query(
            models.CurrentQuery(session_id=other, query="q"), host=host, caller_session_id=sid
        )
    assert error.value.code == "knowledge_run_not_authorized"
    assert upstream.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["cancel", "digest", "turn", "child"])
async def test_grant_and_native_turn_are_rechecked_after_upstream_await(formal, mutation):
    service, upstream, _, sid, _, delivery, events, native = formal
    original = upstream.search

    async def changed(*args, **kwargs):
        result = await original(*args, **kwargs)
        if mutation == "cancel":
            delivery["cancel_request"] = {"requested_at": 1}
        elif mutation == "digest":
            service.owner_store.receipt(sid, "approved-key")["knowledge_request_digest"] = "c" * 64
        elif mutation == "turn":
            events.append({"event": {"type": "turn/end", "data": {"turn": 1}}})
        else:
            native["parentSessionId"] = "unexpected-parent"
        return result

    upstream.search = changed
    with pytest.raises(StoreError) as error:
        await query(formal)
    assert error.value.status == 403
    assert not (service.store.root / "knowledge-backend/receipts").exists()


@pytest.mark.asyncio
async def test_formal_read_rechecks_approved_original_and_live_library(formal):
    _, upstream, *_ = formal
    hit = (await query(formal))["items"][0]["hit_id"]
    raw = upstream.original_bytes
    upstream.original_bytes = b"changed original"
    with pytest.raises(StoreError) as error:
        await read(formal, hit)
    assert error.value.code == "knowledge_original_changed"
    upstream.original_bytes = raw

    async def revoked():
        return []

    upstream.knowledge_bases = revoked
    with pytest.raises(StoreError) as error:
        await read(formal, hit)
    assert error.value.code == "knowledge_library_access_revoked"


@pytest.mark.asyncio
async def test_formal_read_rejects_real_rebinding_during_final_native_observation(formal):
    service, _, host, sid, scope, *_ = formal
    hit = (await query(formal))["items"][0]["hit_id"]
    before = service.store.binding()
    entered, proceed = asyncio.Event(), asyncio.Event()
    original_rpc, calls = host.client.rpc, 0

    async def blocked_rpc(method, payload):
        nonlocal calls
        calls += 1
        if calls == 2:
            entered.set()
            await proceed.wait()
        return await original_rpc(method, payload)

    host.client.rpc = blocked_rpc
    reading = asyncio.create_task(read(formal, hit))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        # Exercise the actual bind/credential persistence path, not a mocked read.
        await service.bind("user-jwt-replacement", "101")
        assert service.store.binding()["credential_ref"] != before["credential_ref"]
        assert service.owner_store.receipt(sid, "approved-key")["knowledge_scope_id"] == scope["id"]
    finally:
        proceed.set()
    with pytest.raises(StoreError) as error:
        await asyncio.wait_for(reading, 2)
    assert error.value.code == "knowledge_binding_changed"


@pytest.mark.asyncio
async def test_formal_read_rejects_hit_from_another_session(formal):
    service, *_ = formal
    item = (await query(formal))["items"][0]
    row = service.store.read("receipts", item["hit_id"])
    row.pop("id")
    row["session_id"] = "00000000-0000-0000-0000-000000000000"
    foreign = service.store.create("receipts", row)
    with pytest.raises(StoreError) as error:
        await read(formal, foreign["id"])
    assert error.value.code == "knowledge_hit_session_mismatch"


@pytest.mark.asyncio
async def test_formal_scope_supports_multiple_approved_libraries_without_current_fallback(formal):
    service, upstream, _, _, _, _, _, _ = formal
    original_meta = upstream.document
    original_chunks = upstream.chunks

    async def bases():
        return [{"id": "kb1"}, {"id": "kb2"}]

    async def meta(identifier):
        return {**await original_meta(identifier), "kb_id": "kb2" if identifier == "d2" else "kb1"}

    async def chunks(identifier):
        return [
            {**row, "document_id": identifier, "kb_id": "kb2" if identifier == "d2" else "kb1"}
            for row in await original_chunks(identifier)
        ]

    async def search(_query, libraries, documents, limit):
        assert libraries == ["kb1", "kb2"] and documents == ["d1", "d2"] and limit == 8
        return [*await chunks("d1"), *await chunks("d2")]

    upstream.knowledge_bases, upstream.document, upstream.chunks = bases, meta, chunks
    body = fixtures.approved()
    second = copy.deepcopy(body.documents[0])
    second.document_id = "d2"
    body.documents.append(second)
    scope = await service.create_scope(body)
    service.owner_store.receipt(formal[3], "approved-key")["knowledge_scope_id"] = scope["id"]
    upstream.search = search
    result = await query(formal)
    assert len(result["items"]) == 2
    assert len({row["hit_id"] for row in result["items"]}) == 2


@pytest.mark.asyncio
async def test_missing_native_request_digest_does_not_authorize_scope(formal):
    service, _, host, sid, *_ = formal
    service.owner_store.receipt(sid, "approved-key").pop("knowledge_request_digest")
    with pytest.raises(StoreError) as error:
        await active_scope(host, sid)
    assert error.value.code == "knowledge_run_not_authorized"


@pytest.mark.asyncio
async def test_formal_registered_sources_do_not_require_single_current_library(formal):
    service, _, _, sid, _, delivery, *_ = formal
    hit = (await query(formal))["items"][0]
    delivery["status"] = "completed"
    sources = service.registered_sources(sid)
    assert len(sources) == 1 and sources[0]["id"] == hit["source_id"]
    assert sources[0]["historical_eligible"] is False
    assert sources[0]["admission"] == {"report_admitted": False}
    with pytest.raises(StoreError) as error:
        await read(formal, hit["hit_id"])
    assert error.value.code == "knowledge_run_not_authorized"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["ordinary", "request", "scope", "original"])
async def test_formal_registered_sources_only_index_the_exact_approved_receipt(formal, mutation):
    service, _, _, sid, *_ = formal
    hit = (await query(formal))["items"][0]
    row = service.store.read("receipts", hit["hit_id"])
    row.pop("id")
    if mutation == "ordinary":
        row.pop("purpose")
    elif mutation == "request":
        row["native_grant"][1] = "different-request"
    elif mutation == "scope":
        row["knowledge_scope_id"] = "f" * 64
    else:
        row["sha256"] = "f" * 64
    polluted = service.store.create("receipts", row)
    sources = service.registered_sources(sid)
    assert [item["id"] for item in sources] == [hit["source_id"]]
    assert all(item["id"] != "knowledge:" + polluted["id"] for item in sources)
