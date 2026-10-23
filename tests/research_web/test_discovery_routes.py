"""Real Host routing, explicit consent and original quality contracts; no model calls."""

import copy
from uuid import uuid4

import pytest
from test_api import api, isolated_keyring
from test_discovery import ARTICLE, EVENT

__all__ = ["api", "isolated_keyring"]
ACTION = {"X-Research-User-Action": "?1"}


@pytest.fixture
def discovery_api(api, monkeypatch):
    client, native, service = api
    known = {}
    original = native.rpc

    async def rpc(method, payload):
        if method == "session.create":
            known[payload["sessionId"]] = {
                "sessionId": payload["sessionId"],
                "cwd": payload["cwd"],
                "running": False,
            }
        if method == "session.list":
            native.calls.append((method, payload))
            return {"items": list(known.values())}
        return await original(method, payload)

    async def reader(path, params=None):
        if path == "/intelligence":
            return {"reading": [copy.deepcopy(EVENT)], "cache_stale": True, "as_of": None}
        return {"event": copy.deepcopy(EVENT), "articles": [copy.deepcopy(ARTICLE)]}

    monkeypatch.setattr(native, "rpc", rpc)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _sid: True)
    service.discovery.reader = reader
    return client, native, service


def prepare_body(client, mode="fingpt"):
    response = client.get("/api/research/discovery/feed")
    assert response.status_code == 200, response.text
    feed = response.json()
    theme = feed["themes"][0]
    return {
        "request_id": str(uuid4()),
        "feed_id": feed["feed_id"],
        "horizon": "medium",
        "theme_id": theme["id"],
        "material_ids": [theme["materials"][0]["id"]],
        "target_mode": mode,
        "question": "核查事件的来源、反证、传导和失效条件。",
    }


def test_feed_and_history_are_read_only_and_do_not_create_sessions(discovery_api):
    client, native, service = discovery_api
    before = set(service.store.data)
    response = client.get("/api/research/discovery/feed")
    assert response.json()["stale"] is True
    assert client.get("/api/research/discovery/handoffs").json() == {"items": []}
    assert client.get("/api/research/discovery/tracks").json()["items"] == []
    assert not service.store.data["sessions"]
    assert set(service.store.data) == before
    assert not any(name in {"session.create", "session.prompt"} for name, _ in native.calls)


def test_current_selection_is_read_only_and_can_be_frozen(discovery_api):
    client, native, service = discovery_api
    body = prepare_body(client)
    before = copy.deepcopy(service.store.data)
    selected = client.get(
        "/api/research/discovery/selection",
        params={key: body[key] for key in ("feed_id", "theme_id", "horizon")},
    )
    assert selected.status_code == 200, selected.text
    preview = selected.json()
    assert preview["feed_id"] != body["feed_id"]
    assert service.store.data == before
    assert not any(name in {"session.create", "session.prompt"} for name, _ in native.calls)
    theme = preview["themes"][0]
    response = client.post(
        "/api/research/discovery/prepare",
        json={
            **body,
            "feed_id": preview["feed_id"],
            "theme_id": theme["id"],
            "material_ids": [item["id"] for item in theme["materials"]],
        },
        headers=ACTION,
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "snapshot_ready"
    assert not any(name == "session.prompt" for name, _ in native.calls)
    rejected = client.get(
        "/api/research/discovery/selection",
        params={"feed_id": str(uuid4()), "theme_id": body["theme_id"], "horizon": "medium"},
    )
    assert rejected.status_code == 409


@pytest.mark.parametrize("mode", ["fingpt", "claw"])
def test_two_step_real_host_handoff_uses_same_quality_gate(discovery_api, mode):
    client, native, service = discovery_api
    body = prepare_body(client, mode)
    denied = client.post("/api/research/discovery/prepare", json=body)
    assert denied.status_code == 403
    response = client.post("/api/research/discovery/prepare", json=body, headers=ACTION)
    assert response.status_code == 200, response.text
    prepared = response.json()
    assert prepared["state"] == "snapshot_ready"
    assert prepared["execution_started"] is False
    assert not any(name == "session.prompt" for name, _ in native.calls)
    recovered = client.get(f"/api/research/discovery/requests/{body['request_id']}")
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["handoff_id"] == prepared["handoff_id"]
    rows = client.get("/api/research/discovery/handoffs").json()["items"]
    assert isinstance(rows, list) and len(rows) == 1
    execute = f"/api/research/discovery/handoffs/{prepared['handoff_id']}/execute"
    response = client.post(execute, json={"request_id": str(uuid4())}, headers=ACTION)
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "running", response.json()
    sid = prepared["session_id"]
    receipt = next(
        value
        for key, value in service.store.data["receipts"].items()
        if key.startswith(sid + ":") and value.get("research_contract")
    )
    assert receipt["research_contract"]["as_of"] == prepared["cutoff"]
    assert receipt["research_contract"]["mode"] == "deep"
    assert len(receipt["research_contract"]["requirements"]) >= 4
    assert receipt.get("quality_last_result", {}).get("status") != "passed"
    again = client.post(execute, json={"request_id": str(uuid4())}, headers=ACTION)
    assert again.status_code == 200
    assert len([1 for name, _ in native.calls if name == "session.prompt"]) == 1


def test_strict_inputs_do_not_accept_owner_url_or_permissions(discovery_api):
    client, native, _ = discovery_api
    body = prepare_body(client)
    for extra in [{"owner": "other"}, {"url": "https://example.com"}, {"source_scope": ["web"]}]:
        response = client.post(
            "/api/research/discovery/prepare", json={**body, **extra}, headers=ACTION
        )
        assert response.status_code == 422
    response = client.post(
        "/api/research/discovery/tracks",
        json={
            "request_id": str(uuid4()),
            "feed_id": body["feed_id"],
            "horizon": "medium",
            "theme_id": body["theme_id"],
            "condition": "观察新证据",
            "frequency": "daily",
            "time": "08:30",
            "mcp_tools": ["arbitrary"],
        },
        headers=ACTION,
    )
    assert response.status_code == 422
    assert not any(name in {"session.create", "session.prompt"} for name, _ in native.calls)


def test_generic_composer_cannot_bypass_unready_discovery_session(discovery_api):
    client, native, service = discovery_api
    body = prepare_body(client)
    prepared = client.post("/api/research/discovery/prepare", json=body, headers=ACTION).json()
    row = service.store.session(prepared["session_id"])
    row["discovery_creation_state"] = "configuration_required"
    service.store.save()
    response = client.post(
        f"/api/research/sessions/{row['id']}/messages",
        json={"text": "不能跳过准备", "expected_formats": []},
        headers={"Idempotency-Key": "discovery-not-ready"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "discovery_session_not_ready"
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_tenant_tracking_requires_manager_flag_and_keeps_general_api_denied(monkeypatch):
    import asyncio

    from starlette.requests import Request

    from app.research_web import tenant_policy
    from app.research_web.service import ResearchService

    monkeypatch.setenv("RWB_TENANT_MODE", "1")
    monkeypatch.setenv("RESEARCH_AUTOMATIONS_ENABLED", "0")
    monkeypatch.delenv("RWB_DISCOVERY_TRACKING_ENABLED", raising=False)
    assert ResearchService.discovery_tracking_allowed() is False
    monkeypatch.setenv("RWB_DISCOVERY_TRACKING_ENABLED", "1")
    assert ResearchService.discovery_tracking_allowed() is True
    monkeypatch.setattr(tenant_policy, "_gateway_key", lambda: "fixture-gateway")
    for path, denied in [
        ("/api/research/automations", True),
        ("/api/research/sessions/id/automation-drafts", True),
        ("/api/research/discovery/feed", False),
    ]:
        request = Request(
            {
                "type": "http",
                "path": path,
                "method": "GET",
                "headers": [(b"x-rwb-tenant-gateway-key", b"fixture-gateway")],
            }
        )
        result = asyncio.run(tenant_policy.check_request(request))
        assert (result is not None) is denied
