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
