"""Native event ordering and child approval routing regressions."""

import pytest

from app.research_web.client import RuntimeFailure
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
