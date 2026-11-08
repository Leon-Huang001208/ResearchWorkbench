"""Real Host/gateway HTTP contracts; all upstream and credentials are synthetic."""

import pytest
from fastapi.testclient import TestClient

from app.research_web.knowledge_backend.service import KnowledgeService
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store
from tests.research_web import test_multiuser_gateway as gateway_fixtures
from tests.research_web.test_api import NativeFixture
from tests.research_web.test_multiuser_gateway import login
from tests.research_web.test_weknora_service import Credentials, Upstream


@pytest.fixture
def gateway(tmp_path):
    yield from gateway_fixtures.server.__wrapped__(tmp_path)


@pytest.fixture
def api(tmp_path, monkeypatch):
    import keyring

    secrets = Credentials()
    monkeypatch.setenv("RESEARCH_MCP_RUNTIME_ENABLED", "0")
    monkeypatch.setenv("RESEARCH_FRAMEWORK_COLLECTORS_ENABLED", "0")
    monkeypatch.setattr(keyring, "get_password", secrets.get_password)
    monkeypatch.setattr(keyring, "set_password", secrets.set_password)
    monkeypatch.setattr(keyring, "delete_password", secrets.delete_password)
    native = NativeFixture()
    host = ResearchService(native, Store(tmp_path / "owner"))
    upstream = Upstream()
    host.knowledge = KnowledgeService(
        host.store,
        credentials=secrets,
        client_factory=upstream.factory,
        origin="https://knowledge.example.test",
    )
    with TestClient(create_app(host)) as client:
        yield client, host, upstream, native


def test_status_no_model_or_secret_and_settings_binding_string_contract(api):
    client, host, _, native = api
    assert not client.get("/api/research/knowledge").json()["configured"]
    response = client.post(
        "/api/research/knowledge/binding",
        json={"token": "user-jwt-a", "workspace_id": "101"},
        headers={"X-Research-User-Action": "?1"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["workspace_id"] == "101"
    assert "user-jwt-a" not in response.text
    assert not any(call[0] == "session.prompt" for call in native.calls)
    assert "user-jwt-a" not in (host.store.root / "knowledge-backend/binding.json").read_text()


def test_binding_invalid_request_never_echoes_token(api):
    client, _, _, _ = api
    for workspace in (101, "bad", None):
        response = client.post(
            "/api/research/knowledge/binding",
            json={"token": "secret-canary", "workspace_id": workspace},
            headers={"X-Research-User-Action": "?1"},
        )
        assert response.status_code == 422
        assert "secret-canary" not in response.text


def test_explicit_binding_and_cross_origin_guard(api):
    client, host, _, _ = api
    body = {"token": "user-jwt-a", "workspace_id": "101"}
    assert client.post("/api/research/knowledge/binding", json=body).status_code == 403
    assert (
        client.post(
            "/api/research/knowledge/binding",
            json=body,
            headers={"X-Research-User-Action": "?1", "Origin": "https://attacker.test"},
        ).status_code
        == 403
    )
    assert host.knowledge.status()["configured"] is False


def test_callback_requires_data_key_and_scope_but_cannot_create_or_freeze(api):
    client, host, _, _ = api
    assert client.post("/api/research/internal/data/knowledge-query", json={}).status_code == 403
    key = host.datahub.control["token"]
    response = client.post(
        "/api/research/internal/data/knowledge-query",
        json={"query": "q", "knowledge_base_ids": ["kb1"]},
        headers={"X-Research-Data-Key": key},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "knowledge_scope_required"
    for name in ("knowledge-scope", "knowledge-binding", "knowledge-freeze"):
        assert (
            client.post(
                "/api/research/internal/data/" + name, json={}, headers={"X-Research-Data-Key": key}
            ).status_code
            == 404
        )


def test_body_budget_precedes_secret_processing(api):
    client, host, _, _ = api
    response = client.post(
        "/api/research/knowledge/binding",
        content=b"x" * 65537,
        headers={"X-Research-User-Action": "?1", "Content-Type": "application/json"},
    )
    assert response.status_code == 413
    assert host.knowledge.status()["configured"] is False


def test_authenticated_gateway_routes_knowledge_by_cookie_not_owner(gateway):
    browser, _, _, users, forwarded = gateway
    _, alice, bob = users
    assert browser.get("/api/research/knowledge").status_code == 401
    login(browser)
    response = browser.get(
        "/api/research/knowledge", headers={"Authorization": "Bearer forged", "X-Tenant-ID": bob.id}
    )
    assert response.status_code == 200
    assert response.json()["owner"] == alice.id
    assert "authorization" not in forwarded[-1].headers
    assert "x-tenant-id" not in forwarded[-1].headers
    browser.post("/api/server/logout")
    login(browser, "bobby", "a safe bobby password")
    assert browser.get("/api/research/knowledge").json()["owner"] == bob.id


def test_native_knowledge_grant_is_explicit_once_and_revocable(api):
    from hashlib import sha256

    from tests.research_web.test_weknora_service import approved

    client, host, upstream, native = api
    action = {"X-Research-User-Action": "?1"}
    assert (
        client.post(
            "/api/research/knowledge/binding",
            json={"token": "user-jwt-a", "workspace_id": "101"},
            headers=action,
        ).status_code
        == 200
    )
    scope = client.post(
        "/api/research/knowledge/scopes", json=approved().model_dump(), headers=action
    ).json()
    sid = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    other = client.post("/api/research/sessions", json={"mode": "fingpt"}).json()["id"]
    copied_helper = host.store.directory(sid) / "resources" / "research_helpers.py"
    assert copied_helper.is_file()
    assert getattr(copied_helper.stat(), "st_flags", 0) == 0
    endpoint = f"/api/research/sessions/{sid}/messages"
    submission = {"text": "读取资料分块", "knowledge_scope_id": scope["id"]}
    headers = {"Idempotency-Key": "one-native-knowledge-turn"}
    assert client.post(endpoint, json=submission, headers=headers).status_code == 403

    callback = "/api/research/internal/data/knowledge-tool"
    key = {"X-Research-Data-Key": host.datahub.control["token"]}
    search = {"session_id": sid, "operation": "search", "query": "source"}
    assert client.post(callback, json=search).status_code == 403
    assert client.post(callback, json=search, headers=key).status_code == 403

    started = client.post(endpoint, json=submission, headers=headers | action)
    assert started.status_code == 202, started.text
    assert client.post(endpoint, json=submission, headers=headers | action).status_code == 202
    assert sum(method == "session.prompt" for method, _ in native.calls) == 1
    assert host.store.receipt(sid, headers["Idempotency-Key"])["knowledge_scope_id"] == scope["id"]
    assert (
        client.post(
            endpoint, json={"text": "follow up"}, headers={"Idempotency-Key": "separate-followup"}
        ).status_code
        == 409
    )
    assert client.post(f"/api/research/sessions/{sid}/upgrade").status_code == 409

    prompt = next(payload for method, payload in native.calls if method == "session.prompt")
    native_events = [
        {"event": {"seq": 1, "type": "turn/start", "data": {"turn": 1}}},
        {
            "event": {
                "seq": 2,
                "type": "user/message",
                "data": {"content": prompt["content"], "source": {"rpcId": prompt["requestId"]}},
            }
        },
    ]

    async def history(requested_sid):
        return native_events if requested_sid == sid else []

    native.history = history
    native.running.update({sid, other})
    assert (
        client.post(callback, json=search | {"session_id": other}, headers=key).status_code == 403
    )
    assert (
        client.post(callback, json=search | {"scope_id": scope["id"]}, headers=key).status_code
        == 422
    )
    hit = client.post(callback, json=search, headers=key).json()["items"][0]
    assert "content" not in hit
    assert ("search", "source", ["kb1"], ["d1"], 8) in upstream.calls
    read = {"session_id": sid, "operation": "read", "document_id": "d1", "chunk_id": "c1"}
    chunk = client.post(callback, json=read, headers=key).json()
    assert chunk["content"] == upstream.hit["content"]
    assert chunk["original_sha256"] == sha256(upstream.original_bytes).hexdigest()
    assert chunk["content_sha256"] == sha256(chunk["content"].encode()).hexdigest()
    assert (
        client.post(callback, json=read | {"document_id": "outside"}, headers=key).status_code
        == 403
    )

    native_events.append({"event": {"seq": 3, "type": "turn/end", "data": {"turn": 1}}})
    assert client.post(callback, json=read, headers=key).status_code == 403
    native_events.pop()

    upstream.download_allowed = False
    assert client.post(callback, json=read, headers=key).status_code == 403
    upstream.download_allowed = True
    native.running.remove(sid)
    assert client.post(callback, json=read, headers=key).status_code == 403
    native.running.add(sid)
    assert client.post(f"/api/research/sessions/{sid}/cancel").status_code == 200
    assert client.post(callback, json=read, headers=key).status_code == 403


@pytest.mark.asyncio
async def test_scope_checks_exact_native_request_and_rechecks_after_await():
    from types import SimpleNamespace

    from app.research_web.knowledge_backend.routes import active_scope
    from app.research_web.store import StoreError

    sid = "session"
    row = {"knowledge_single_turn": True, "delivery_key": "key"}
    delivery = {"task_id": "approved", "status": "pending"}
    receipt = {"knowledge_scope_id": "scope", "status": "accepted", "delivery": delivery}
    entries = [
        {"event": {"type": "turn/start", "data": {"turn": 1}}},
        {"event": {"type": "user/message", "data": {"source": {"rpcId": "different"}}}},
    ]
    cancel_during_observation = False

    async def owned():
        return None

    async def history(_):
        return entries

    async def rpc(*_):
        if cancel_during_observation:
            delivery["cancel_request"] = {"requested_at": 1}
        return {"items": [{"sessionId": sid, "running": True}]}

    host = SimpleNamespace(
        ensure_owned=owned,
        store=SimpleNamespace(session=lambda _: row, data={"receipts": {"session:key": receipt}}),
        client=SimpleNamespace(history=history, rpc=rpc),
        connected={"mux", "host"},
    )
    with pytest.raises(StoreError, match="资料操作") as mismatch:
        await active_scope(host, sid)
    assert mismatch.value.code == "knowledge_native_turn_unverified"
    entries[1]["event"]["data"]["source"]["rpcId"] = "approved"
    assert await active_scope(host, sid) == "scope"
    cancel_during_observation = True
    with pytest.raises(StoreError, match="资料操作") as cancelled:
        await active_scope(host, sid)
    assert cancelled.value.code == "knowledge_run_not_authorized"
