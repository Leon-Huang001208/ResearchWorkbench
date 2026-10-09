"""Native event ordering and child approval routing regressions."""

import json

import httpx
import pytest

from app.research_web.client import DSHClient, RuntimeFailure
from app.research_web.projection import project
from app.research_web.service import ResearchService
from app.research_web.store import Store, StoreError


class Events:
    def __init__(self, frames, parent=None):
        self.items, self.parent, self.replies = frames, parent, []

    async def frames(self, channel):
        for frame in self.items:
            yield frame

    async def rpc(self, method, payload):
        assert method == "subagent.list"
        return {
            "entries": (
                [{"kind": "child", "id": "child", "mode": "continuable", "activity": "running"}]
                if payload["parentSessionId"] == self.parent
                else []
            )
        }

    async def respond(self, rpc_id, value):
        self.replies.append((rpc_id, value))
        return {"accepted": True}


@pytest.mark.asyncio
async def test_todo_paginated_history_recovers_same_plan_without_submission():
    rows = [
        {"event": {"seq": seq, "type": kind, "data": data}}
        for seq, kind, data in [
            (0, "turn/start", {"turn": 1}),
            (1, "todo/write", {"todos": [{"content": "old", "status": "completed"}]}),
            (2, "turn/start", {"turn": 2}),
            (3, "todo/write", {"todos": [{"content": "current", "status": "pending"}]}),
        ]
    ]
    requests = []

    class NativeStream(DSHClient):
        async def _stream(self, endpoint, args):
            # Simulated remote boundary; history() and project() execute unchanged.
            assert endpoint == "session/follow"
            assert args["request"]["address"]["sessionId"] == "owner"
            requests.append(endpoint)
            yield {"type": "snapshot", "records": rows[2:], "cursor": 3, "hasMore": True}

    def response(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/session/page"
        assert body["payload"]["args"]["request"]["beforeSeq"] == 2
        requests.append(body["method"])
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {
                    "ok": True,
                    "value": {"records": [*rows[:2], rows[2]], "hasMore": False},
                },
            },
        )

    async with NativeStream(
        "http://127.0.0.1:3081", transport=httpx.MockTransport(response)
    ) as client:
        first = project(await client.history("owner"))
        refreshed = project(await client.history("owner"))
    assert first["plan"] == refreshed["plan"] == project(rows)["plan"]
    assert first["plan"]["turn"] == 2
    assert first["plan_history_incomplete"] is False
    assert requests == ["session/follow", "session/page"] * 2


@pytest.mark.asyncio
async def test_todo_sse_duplicate_events_are_session_owned_and_next_turn_clears(tmp_path):
    store = Store(tmp_path)
    first = store.create("fingpt", "first")["id"]
    second = store.create("claw", "second")["id"]

    def frame(sid, seq, kind, data):
        return {
            "payload": {
                "sessionId": sid,
                "type": "session/event",
                "event": {"seq": seq, "type": kind, "data": data},
            }
        }

    write = frame(first, 1, "todo/write", {"todos": [{"content": "first", "status": "pending"}]})
    native = Events(
        [
            frame(first, 0, "turn/start", {"turn": 1}),
            write,
            write,
            frame(second, 0, "turn/start", {"turn": 7}),
            frame(
                second, 1, "todo/write", {"todos": [{"content": "second", "status": "completed"}]}
            ),
            frame(first, 2, "turn/start", {"turn": 2}),
        ]
    )
    service = ResearchService(native, store)
    await service._consume("mux")
    assert len(service.events[first]) == 3
    assert project(list(service.events[first].values()))["plan"] is None
    assert project(list(service.events[second].values()))["plan"]["turn"] == 7
    assert native.replies == []


@pytest.mark.asyncio
async def test_turn_start_after_previous_end_restores_running_state(tmp_path):
    store = Store(tmp_path)
    sid = store.create("fingpt", "event ordering")["id"]
    frames = [
        {
            "payload": {
                "sessionId": sid,
                "type": "session/event",
                "event": {"seq": seq, "type": kind, "data": data},
            }
        }
        for seq, kind, data in [
            (1, "turn/end", {"turn": 1, "reason": {"kind": "completed"}}),
            (2, "turn/start", {"turn": 2}),
        ]
    ]
    service = ResearchService(Events(frames), store)
    await service._consume("mux")
    assert service.running[sid] is True


@pytest.mark.asyncio
async def test_child_approval_replayed_before_child_list_is_routed_to_owned_parent(tmp_path):
    store = Store(tmp_path)
    parent = store.create("claw", "approval owner")["id"]
    store.session(parent)["created"] = True
    other = store.create("fingpt", "unrelated")["id"]
    requested = {
        "rpcId": "request-rpc",
        "payload": {
            "sessionId": "child",
            "type": "approval/requested",
            "approvalId": "approval-1",
            "toolName": "datahub_get_fund_data",
            "reason": "query",
        },
    }
    native = Events([requested], parent)
    service = ResearchService(native, store)
    await service._consume("mux")
    assert "approval-1" in service.approvals
    with pytest.raises(StoreError):
        await service.approve(other, "approval-1", "approve")
    await service.approve(parent, "approval-1", "deny")
    assert native.replies == [
        ("request-rpc", {"sessionId": "child", "approvalId": "approval-1", "outcome": "rejected"})
    ]
    assert not service.approvals
    native.items = [
        {"payload": {"sessionId": "child", "type": "approval/resolved", "approvalId": "approval-1"}}
    ]
    await service._consume("mux")
    assert not service.approvals


@pytest.mark.asyncio
@pytest.mark.parametrize("code", ["session-not-found", "runtime_unavailable"])
async def test_offline_parent_does_not_prevent_owned_child_cancellation(tmp_path, code):
    store = Store(tmp_path)
    parent = store.create("claw", "offline parent")["id"]
    calls = []

    class Native:
        async def rpc(self, method, payload):
            calls.append((method, payload))
            if method == "session.cancel":
                raise RuntimeFailure("Parent not available", code)
            if method == "subagent.list":
                return {"entries": [{"kind": "child", "id": "child", "mode": "continuable"}]}
            return {"accepted": True}

    service = ResearchService(Native(), store)
    if code == "session-not-found":
        await service.cancel(parent)
        assert calls[-1] == (
            "subagent.interrupt",
            {"parentSessionId": parent, "childSessionId": "child", "mode": "continuable"},
        )
    else:
        with pytest.raises(RuntimeFailure):
            await service.cancel(parent)
        assert [method for method, _ in calls] == ["session.cancel"]
