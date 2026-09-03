"""Explicit cancellation can fail delivery closed without inventing native terminal events."""

import copy

import pytest
from fastapi.testclient import TestClient
from test_delivery import delivery_api as delivery_api  # noqa: PLC0414
from test_delivery import detail, submit

from app.research_web.client import RuntimeFailure
from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store


def stalled(api, monkeypatch):
    _, native, service, sid = api
    assert submit(api, ["md"]).status_code == 202
    delivery = service.delivery.current(sid)
    state = {
        "entries": [
            {"event": {"seq": 492, "type": "user/message", "data": {"content": delivery["marker"]}}}
        ],
        "parents": [{"sessionId": sid, "running": False}],
        "children": [],
        "parent_available": True,
        "cancel": {"accepted": True},
        "history_error": False,
        "diagnostics": [],
        "reads": 0,
    }
    original = native.rpc

    async def rpc(method, payload):
        if method == "session.list":
            return {"items": state["parents"], "diagnostics": state["diagnostics"]}
        if method == "subagent.list":
            return {"entries": state["children"], "parentAvailable": state["parent_available"]}
        if method == "subagent.history":
            return {"events": [], "hasMore": False}
        if method == "session.cancel":
            native.calls.append((method, payload))
            return state["cancel"]
        return await original(method, payload)

    async def history(_sid):
        state["reads"] += 1
        if state["history_error"]:
            raise RuntimeFailure("history incomplete", "history_limit")
        return copy.deepcopy(state["entries"])

    monkeypatch.setattr(native, "rpc", rpc)
    monkeypatch.setattr(native, "history", history)
    service.events[sid] = {492: copy.deepcopy(state["entries"][0])}
    service.running[sid] = False
    service.loaded.add(sid)
    return state


def cancel(api):
    client, _, _, sid = api
    return client.post(f"/api/research/sessions/{sid}/cancel", json={})


def test_explicit_cancel_finalizes_missing_terminal_as_verification_failed_only(
    delivery_api, monkeypatch
):
    from app.research_web import sandbox

    _, native, service, sid = delivery_api
    state = stalled(delivery_api, monkeypatch)
    service.errors[sid] = "native turn/end serialization error"
    before = detail(delivery_api)
    assert before["delivery"]["status"] == "pending" and before["can_recheck_stop"]
    assert submit(delivery_api, [], key="delivery-two").status_code == 503

    def forbidden(*args):
        raise AssertionError("missing terminal event must never parse files")

    monkeypatch.setattr(sandbox, "run_script", forbidden)
    assert cancel(delivery_api).status_code == 200
    result = detail(delivery_api)
    assert result["status"] == "failed" and not result["can_cancel"]
    assert result["delivery"]["status"] == "verification_failed"
    assert result["delivery"]["failure_code"] == "cancel_terminal_event_missing"
    assert result["delivery"]["files"] == [] and result["delivery"]["missing_formats"] == ["md"]
    assert "终止事件" in result["delivery"]["reasons"][0]
    assert state["reads"] > 0
    assert not any(entry["event"]["type"] == "turn/end" for entry in service.events[sid].values())
    saved = Store(service.store.root).receipt(sid, "delivery-one")["delivery"]
    assert saved["cancel_request"]["task_id"] == saved["task_id"]
    assert saved["status"] == "verification_failed"
    assert submit(delivery_api, ["md"]).status_code == 202
    assert len([call for call in native.calls if call[0] == "session.prompt"]) == 1
    assert submit(delivery_api, [], key="delivery-two").status_code == 202
    newer = detail(delivery_api)
    assert newer["status"] == "running" and not newer.get("error")
    assert newer["delivery"][
        "status"
    ] == "pending" and "cancel_request" not in service.delivery.current(sid)


@pytest.mark.parametrize(
    "missing",
    [
        "no_request",
        "unknown_receipt",
        "pending_receipt",
        "no_marker",
        "wrong_marker",
        "later_task",
        "parent_running",
        "parent_absent",
        "parent_unknown",
        "parent_not_boolean",
        "parent_duplicate",
        "child_running",
        "child_unknown",
        "child_diagnostic",
        "diagnostics",
        "approval",
        "question",
        "mux_only",
        "host_only",
        "history_incomplete",
        "cancel_not_accepted",
        "parent_unavailable",
        "old_intent",
    ],
)
def test_missing_any_reconciliation_evidence_keeps_delivery_pending(
    delivery_api, monkeypatch, missing
):
    _, _, service, sid = delivery_api
    state = stalled(delivery_api, monkeypatch)
    if missing in {"unknown_receipt", "pending_receipt"}:
        service.store.receipt(sid, "delivery-one", missing.split("_")[0])
    elif missing == "no_marker":
        state["entries"] = []
    elif missing == "wrong_marker":
        state["entries"][0]["event"]["data"]["content"] = "[AF_TASK:" + "0" * 24 + "]"
    elif missing == "later_task":
        state["entries"].append(
            {"event": {"seq": 493, "type": "user/message", "data": {"content": "newer task"}}}
        )
    elif missing == "parent_unavailable":
        state["parent_available"] = False
    elif missing.startswith("parent_"):
        if missing == "parent_absent":
            state["parents"] = []
        elif missing == "parent_duplicate":
            state["parents"] *= 2
        else:
            state["parents"][0]["running"] = {
                "parent_running": True,
                "parent_unknown": None,
                "parent_not_boolean": 0,
            }[missing]
    elif missing.startswith("child_"):
        state["children"] = [
            {
                "id": "child",
                "kind": "child",
                "mode": "continuable",
                "activity": {
                    "child_running": "running",
                    "child_unknown": "unknown",
                    "child_diagnostic": "inactive",
                }[missing],
            }
        ]
        if missing == "child_diagnostic":
            state["children"][0]["kind"] = "diagnostic"
    elif missing == "diagnostics":
        state["diagnostics"] = [{"error": "unreadable session"}]
    elif missing == "approval":
        service.approvals["approval"] = {"sessionId": sid, "toolName": "af_run_script"}
    elif missing == "question":
        service.questions["question"] = {"sessionId": sid, "questions": []}
    elif missing in {"mux_only", "host_only"}:
        service.connected = {missing.split("_")[0]}
    elif missing == "history_incomplete":
        state["history_error"] = True
    elif missing == "cancel_not_accepted":
        state["cancel"] = {"accepted": False}
    elif missing == "old_intent":
        service.delivery.current(sid)["cancel_request"] = {
            "accepted": True,
            "task_id": "old",
            "key": "delivery-one",
            "marker": "old",
        }
    if missing not in {"no_request", "old_intent"}:
        response = cancel(delivery_api)
        assert response.status_code in {200, 503}
    assert service.delivery.current(sid)["status"] in {"pending", "admission_unknown"}
    if missing != "history_incomplete":
        assert detail(delivery_api)["delivery"]["status"] in {"pending", "admission_unknown"}


def test_cancel_request_survives_restart_but_requires_fresh_idle_proof(delivery_api, monkeypatch):
    _, native, service, sid = delivery_api
    state = stalled(delivery_api, monkeypatch)
    state["parents"][0]["running"] = True
    assert cancel(delivery_api).status_code == 200
    assert service.delivery.current(sid)["status"] == "pending"
    state["parents"][0]["running"] = False
    restored = ResearchService(native, Store(service.store.root))
    with TestClient(create_app(restored)) as client:
        restored.connected = {"mux", "host"}
        result = client.get(f"/api/research/sessions/{sid}").json()
        assert result["delivery"]["status"] == "verification_failed"
        assert result["status"] == "failed"
        assert not any(
            event["event"]["type"] == "turn/end" for event in restored.events[sid].values()
        )


def test_real_cancel_terminal_keeps_native_cancelled_and_normal_delivery(delivery_api, monkeypatch):
    _, _, service, sid = delivery_api
    state = stalled(delivery_api, monkeypatch)
    service.delivery.current(sid)["required_formats"] = []
    state["entries"].append(
        {"event": {"seq": 493, "type": "turn/end", "data": {"reason": {"kind": "aborted"}}}}
    )
    assert cancel(delivery_api).status_code == 200
    result = detail(delivery_api)
    assert result["status"] == "cancelled"
    assert result["delivery"]["status"] == "not_required"
    assert "failure_code" not in result["delivery"]


@pytest.mark.parametrize("kind", ["turn/start", "turn/end"])
def test_new_mux_event_during_idle_rpc_invalidates_old_history(delivery_api, monkeypatch, kind):
    _, native, service, sid = delivery_api
    stalled(delivery_api, monkeypatch)
    service.delivery.current(sid)["required_formats"] = []
    original = native.rpc
    fired = False

    async def rpc(method, payload):
        nonlocal fired
        result = await original(method, payload)
        if method == "session.list" and not fired:
            fired = True
            service.events[sid][493] = {
                "event": {"seq": 493, "type": kind, "data": {"reason": {"kind": "aborted"}}}
            }
            service.running[sid] = kind == "turn/start"
        return result

    monkeypatch.setattr(native, "rpc", rpc)
    assert cancel(delivery_api).status_code == 200
    result = detail(delivery_api)
    assert "failure_code" not in result["delivery"]
    assert result["status"] == ("running" if kind == "turn/start" else "cancelled")
    assert result["delivery"]["status"] == ("pending" if kind == "turn/start" else "not_required")
