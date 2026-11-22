"""Owned BFF ingress and original report gates; no real model or credential calls."""

from app.research_web.specialists.service import ledger, quality_issues
from tests.research_web.test_api import api as _api
from tests.research_web.test_api import isolated_keyring  # noqa: F401

api = _api

BUDGET = {
    "confirmed": True,
    "max_tokens": 40000,
    "max_calls": 12,
    "max_concurrency": 2,
    "timeout_seconds": 1800,
    "max_revisions": 2,
}


def create(client):
    response = client.post("/api/research/sessions", json={"research_mode": "specialist"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def send(client, sid, budget=BUDGET, key="specialist-first-request"):
    return client.post(
        f"/api/research/sessions/{sid}/messages",
        headers={"Idempotency-Key": key},
        json={
            "text": "研究半导体行业的供需与波动风险",
            "research_mode": "specialist",
            "research_as_of": "2026-10-28",
            "specialist_budget": budget,
        },
    )


def test_specialist_requires_confirmed_budget_before_native_prompt(api):
    client, native, _ = api
    sid = create(client)
    for value in (None, {**BUDGET, "confirmed": False}, {**BUDGET, "max_concurrency": 3}):
        response = send(client, sid, value)
        assert response.status_code in {400, 422}
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_specialist_preserves_existing_unverified_model_gate(api, monkeypatch):
    client, native, service = api
    sid = create(client)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _: False)
    response = send(client, sid)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "deep_research_tools_unverified"
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_specialist_send_freezes_contract_and_idempotency(api, monkeypatch):
    client, native, service = api
    sid = create(client)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _: True)
    response = send(client, sid)
    assert response.status_code == 202, response.text
    state = ledger(service).read(sid)
    assert state["budget"] == BUDGET
    assert state["as_of_date"] == "2026-10-28"
    assert state["active_plan"]["version"] == 0
    assert quality_issues(service, sid) == ["specialist_collaboration_incomplete"]
    prompt = next(body for name, body in native.calls if name == "session.prompt")
    assert "specialist_plan" in prompt["content"][0]["text"]
    assert send(client, sid).status_code == 202
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1
    conflict = send(client, sid, {**BUDGET, "max_calls": 11})
    assert conflict.status_code in {400, 409}
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1


def test_browser_cannot_forge_native_completion_or_read_other_account(api):
    client, _, _ = api
    sid = create(client)
    response = client.post(
        "/api/research/internal/data/specialist-control",
        json={
            "session_id": sid,
            "operation": "terminal",
            "payload": {},
            "agent_id": sid,
            "call_id": "forged-terminal",
        },
    )
    assert response.status_code == 403
    assert client.get(
        "/api/research/sessions/00000000-0000-0000-0000-000000000000/specialist"
    ).status_code in {400, 404}


def test_resume_requires_existing_frozen_task_and_confirmation(api):
    client, native, _ = api
    sid = create(client)
    base = f"/api/research/sessions/{sid}/specialist/resume"
    assert client.post(base, json={"confirmed": False}).status_code == 422
    assert client.post(base, json={"confirmed": True}).status_code == 404
    assert not any(name == "session.prompt" for name, _ in native.calls)


def test_cancel_keeps_unconfirmed_state_and_partial_ledger(api, monkeypatch):
    client, _, service = api
    sid = create(client)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _: True)
    assert send(client, sid).status_code == 202
    assert client.post(f"/api/research/sessions/{sid}/cancel").status_code == 200
    state = ledger(service).read(sid)
    assert state["cancel_requested"] is True
    assert state["finalization_ready"] is False


def test_native_control_admission_freezes_route_and_deduplicates_provider_step(api, monkeypatch):
    client, native, service = api
    sid = create(client)
    monkeypatch.setattr(service, "_model_tools_verified", lambda _: True)
    assert send(client, sid).status_code == 202
    headers = {"X-Research-Data-Key": service.datahub.control["token"]}
    base = {"session_id": sid, "agent_id": sid}
    url = "/api/research/internal/data/specialist-control"
    scope = client.post(
        url,
        headers=headers,
        json={**base, "operation": "guard", "payload": {}, "call_id": "guard-first"},
    )
    assert scope.status_code == 200
    assert scope.json()["admitted"] is True
    assert scope.json()["model"] == ledger(service).read(sid)["model"]
    request = {"request_id": "native-request-one", "reserved_tokens": 1000, "turn": 1, "step": 0}
    admitted = client.post(
        url,
        headers=headers,
        json={
            **base,
            "operation": "model_request",
            "payload": request,
            "call_id": "native-admit-one",
        },
    )
    assert admitted.status_code == 200, admitted.text
    duplicate = client.post(
        url,
        headers=headers,
        json={
            **base,
            "operation": "model_request",
            "payload": {**request, "request_id": "different-request-id"},
            "call_id": "native-admit-two",
        },
    )
    assert duplicate.status_code == 409
    assert len(ledger(service).read(sid)["model_requests"]) == 1
    assert sum(name == "session.prompt" for name, _ in native.calls) == 1


def test_ordinary_passed_report_still_requires_bound_delivery(api, monkeypatch):
    from app.research_web import service as service_module

    client, _, service = api
    response = client.post("/api/research/sessions", json={"research_mode": "quick"})
    sid = response.json()["id"]
    response = client.post(
        f"/api/research/sessions/{sid}/messages",
        headers={"Idempotency-Key": "ordinary-bound-regression"},
        json={"text": "核查证据", "expected_formats": []},
    )
    assert response.status_code == 202, response.text
    service.events[sid] = {
        0: {
            "event": {
                "seq": 0,
                "type": "turn/end",
                "data": {"turn": 1, "reason": {"kind": "completed"}},
            }
        }
    }
    service.loaded.add(sid)
    service.running[sid] = False
    monkeypatch.setattr(
        service_module,
        "quality_result",
        lambda *a, **kw: {"status": "passed", "issues": [], "report": None},
    )
    monkeypatch.setattr(service_module, "quality_versions", lambda *a: [])
    monkeypatch.setattr(service_module, "report_delivery", lambda *a: {"status": "unbound"})
    detail = client.get(f"/api/research/sessions/{sid}")
    assert detail.status_code == 200, detail.text
    assert detail.json()["research_quality"]["status"] == "passed"
    assert detail.json()["status"] == "completed"
    assert detail.json()["research_accepted"] is False
