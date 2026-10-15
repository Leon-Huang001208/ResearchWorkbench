"""Native DSH contract regression, deliberately independent of legacy fixtures."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest

from app.research_web import client as client_module
from app.research_web import runtime_auth as runtime_auth_module
from app.research_web.client import DSHClient, RuntimeFailure
from app.research_web.projection import project


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("failed", "failed"),
        ("complete", "completed"),
        ("snapshot", "completed"),
        ("partial", "completed"),
        ("empty", "completed"),
    ],
)
def test_datahub_domain_failure_is_not_shown_as_success(outcome, expected):
    result = project(
        [
            event(1, "tool/call", {"callId": "data", "name": "datahub_get_market_bars"}),
            event(
                2,
                "tool/result",
                {
                    "message": {
                        "source": {"callId": "data"},
                        "role": "tool",
                        "content": [{"type": "text", "text": json.dumps({"status": outcome})}],
                    }
                },
            ),
        ]
    )
    assert result["activities"][0]["status"] == expected


@pytest.mark.parametrize("payload", ["not-json", "{}", '{"status":"unknown"}', "[]"])
def test_invalid_script_result_remains_failed(payload):
    result = project(
        [
            event(1, "tool/call", {"callId": "c", "name": "research_run_script"}),
            event(
                2,
                "tool/result",
                {
                    "message": {
                        "source": {"callId": "c"},
                        "role": "tool",
                        "content": [{"type": "text", "text": payload}],
                    }
                },
            ),
        ]
    )
    assert result["activities"][0]["status"] == "failed"


@pytest.mark.parametrize("model", ["arbitrary-no-tools-model", "deepseek/deepseek-flash"])
def test_compatible_transport_does_not_certify_model_tool_admission(model):
    from app.research_web.service import ResearchService

    service = object.__new__(ResearchService)
    service.default_model = {"provider": "openai-compatible", "model": model}
    assert service._model_tools_verified() is False


@pytest.mark.parametrize("previous_plan", [False, True])
def test_native_todo_without_data_fails_closed_without_losing_session(previous_plan):
    rows = []
    if previous_plan:
        rows = [
            event(0, "turn/start", {"turn": 1}),
            event(1, "todo/write", {"todos": [{"content": "old", "status": "completed"}]}),
        ]
    rows.append({"event": {"seq": len(rows), "type": "todo/write"}})
    view = project(rows)
    assert view["research_plan"]["status"] == "invalid"
    assert view["research_plan"]["items"] == [] and view["plan"] is None
    assert view["plan_error"]


def test_native_plan_and_streamed_reasoning_coexist_in_same_session():
    view = project(
        [
            event(0, "turn/start", {"turn": 2}),
            event(1, "todo/write", {"todos": [{"content": "A", "status": "pending"}]}),
            event(
                2,
                "assistant/chunk",
                {
                    "turn": 2,
                    "step": 1,
                    "chunk": {"type": "reasoning-delta", "index": 0, "text": "thinking"},
                },
            ),
            event(
                3,
                "assistant/chunk",
                {
                    "turn": 2,
                    "step": 1,
                    "chunk": {"type": "text-delta", "index": 1, "text": "answer"},
                },
            ),
        ]
    )
    assert view["research_plan"]["items"] == [{"content": "A", "status": "pending"}]
    assert view["plan"]["todos"] == view["research_plan"]["items"]
    assert view["messages"][0]["text"] == "answer"
    assert view["messages"][0]["reasoning"] == "thinking"


@pytest.mark.parametrize(
    "reason,status", [(None, "running"), ("aborted", "cancelled"), ("completed", "completed")]
)
def test_reasoning_only_messages_survive_stream_cancel_and_completion(reason, status):
    entries = [
        event(0, "turn/start", {"turn": 2}),
        event(1, "todo/write", {"todos": [{"content": "A", "status": "pending"}]}),
        event(
            2,
            "assistant/chunk",
            {
                "turn": 2,
                "step": 1,
                "chunk": {"type": "reasoning-delta", "index": 0, "text": "thinking"},
            },
        ),
    ]
    if reason is not None:
        entries.append(event(3, "turn/end", {"turn": 2, "reason": {"kind": reason}}))
    view = project(entries)
    assert view["messages"] == [
        {"id": "assistant-2-1", "role": "assistant", "text": "", "seq": 2, "reasoning": "thinking"}
    ]
    assert view["status"] == status
    assert view["plan"]["todos"] == view["research_plan"]["items"]
    assert view["plan_history_incomplete"] is False
    assert view["usage"] == {}
    assert "delivery" not in view


def test_final_reasoning_only_message_survives_without_body():
    view = project(
        [
            event(0, "turn/start", {"turn": 1}),
            event(
                1,
                "assistant/message",
                {
                    "turn": 1,
                    "step": 1,
                    "message": {"content": [{"type": "reasoning", "text": "final thinking"}]},
                },
            ),
            event(2, "turn/end", {"turn": 1, "reason": {"kind": "completed"}}),
        ]
    )
    assert view["messages"][0]["text"] == ""
    assert view["messages"][0]["reasoning"] == "final thinking"
    assert view["status"] == "completed"


def test_confirmed_new_turn_clears_plan_without_hiding_older_history_gap():
    rows = [
        event(5, "todo/write", {"todos": [{"content": "old", "status": "completed"}]}),
        event(6, "turn/start", {"turn": 2}),
    ]
    view = project(rows)
    assert view["research_plan"] is None
    assert view["plan"] is None
    assert view["plan_history_incomplete"] is True
    assert "plan_error" not in view
    unknown_turn = project([*rows, event(8, "turn/end", {"reason": {"kind": "completed"}})])
    assert unknown_turn["research_plan"]["status"] == "incomplete"
    assert unknown_turn["plan_history_incomplete"] is True
    assert unknown_turn["plan"] is None
    conflict = project([*rows, event(6, "turn/start", {"turn": 3})])
    assert conflict["research_plan"]["status"] == "invalid"
    assert conflict["plan"] is None
    assert conflict["plan_history_incomplete"] is True


def test_native_plan_fold_preserves_mainline_shape_and_bounds():
    rows = [
        event(0, "turn/start", {"turn": 2}),
        event(1, "todo/write", {"todos": [{"content": "A", "status": "pending"}]}),
    ]
    view = project(rows)
    assert view["research_plan"] == {
        "turn": 2,
        "seq": 1,
        "status": "available",
        "history_complete": True,
        "items": [{"content": "A", "status": "pending"}],
    }
    assert view["plan"]["todos"] == view["research_plan"]["items"]
    gap = project([rows[0], event(4, "todo/write", {"todos": []})])
    assert gap["research_plan"]["status"] == "incomplete"
    assert gap["research_plan"]["items"] == [] and gap["plan"] is None
    oversized = project(
        [
            rows[0],
            event(
                1,
                "todo/write",
                {"todos": [{"content": str(index), "status": "pending"} for index in range(101)]},
            ),
        ]
    )
    assert oversized["research_plan"]["status"] == "invalid"
    assert oversized["research_plan"]["items"] == []


@pytest.mark.parametrize(
    "broken",
    [
        None,
        {},
        {"event": None},
        {"event": {"seq": 2, "data": {}}},
        {"event": {"seq": True, "type": "todo/write", "data": {"todos": []}}},
        {"event": {"seq": "bad", "type": "todo/write", "data": {"todos": []}}},
    ],
)
def test_corrupt_native_record_hides_plan_without_crashing(broken):
    view = project(
        [
            event(0, "turn/start", {"turn": 1}),
            event(
                1,
                "todo/write",
                {"todos": [{"content": "must not stay green", "status": "completed"}]},
            ),
            broken,
        ]
    )
    assert view["plan"] is None
    assert view["plan_error"]
    assert view["plan_history_incomplete"] is True


def test_native_todo_replacement_replay_and_new_turn():
    rows = [
        event(0, "turn/start", {"turn": 1}),
        event(1, "todo/write", {"todos": [{"content": "A", "status": "pending"}]}),
        event(
            2,
            "todo/write",
            {
                "todos": [
                    {"content": "B", "status": "in_progress"},
                    {"content": "C", "status": "in_progress"},
                ]
            },
        ),
    ]
    view = project(rows)
    assert view["plan"] == {
        "turn": 1,
        "seq": 2,
        "version": "1:2",
        "todos": rows[2]["event"]["data"]["todos"],
    }
    assert project([rows[2], *rows, rows[1]])["plan"] == view["plan"]
    assert view["plan_history_incomplete"] is False
    assert "plan_error" not in view
    assert project([*rows, event(3, "turn/start", {"turn": 2})])["plan"] is None
    assert project([])["plan"] is None
    assert project([event(0, "turn/start", {"turn": 8})])["plan"] is None
    assert project(rows)["plan"]["turn"] == 1  # another session fold never leaks its turn


@pytest.mark.parametrize("reason,status", [("aborted", "cancelled"), ("error", "failed")])
def test_todo_completion_does_not_override_cancel_or_failure(reason, status):
    view = project(
        [
            event(0, "turn/start", {"turn": 1}),
            event(1, "todo/write", {"todos": [{"content": "A", "status": "completed"}]}),
            event(2, "turn/end", {"turn": 1, "reason": {"kind": reason}}),
        ]
    )
    assert view["status"] == status
    assert view["plan"]["todos"][0]["status"] == "completed"
    assert "delivery" not in view


@pytest.mark.parametrize(
    "todos",
    [
        None,
        "bad",
        [{}],
        [{"content": "A", "status": "blocked"}],
        [{"content": " ", "status": "completed"}],
        [{"content": "A", "status": "completed", "id": "invented"}],
        [{"content": "A", "status": "pending"}, {"content": "A", "status": "completed"}],
    ],
)
def test_bad_native_todo_never_keeps_green_plan(todos):
    view = project(
        [
            event(0, "turn/start", {"turn": 1}),
            event(1, "todo/write", {"todos": [{"content": "A", "status": "completed"}]}),
            event(2, "todo/write", {"todos": todos}),
        ]
    )
    assert view["plan"] is None
    assert view["plan_error"] == "原生计划事件无效；当前计划无法确认。"


def test_native_todo_missing_history_and_conflicting_duplicate_are_visible():
    write = event(5, "todo/write", {"todos": [{"content": "A", "status": "pending"}]})
    view = project([write])
    assert view["plan_history_incomplete"] is True
    assert view["plan"] is None  # cannot invent a missing owning turn
    view = project([event(0, "turn/start", {"turn": 1}), write])
    assert view["plan_history_incomplete"] is True
    assert view["plan"] is None  # a missing turn/start in the gap cannot be ruled out
    recovered = project(
        [write, event(6, "turn/start", {"turn": 2}), event(7, "todo/write", {"todos": []})]
    )
    assert recovered["plan"]["turn"] == 2
    assert recovered["plan"]["todos"] == []
    assert recovered["plan_history_incomplete"] is True
    corrupt = event(5, "todo/write", {"todos": []})
    assert project([write, corrupt])["plan_error"]
    assert project([event(0, "turn/start", {"turn": 1}), event(1, "todo/write", None)])[
        "plan_error"
    ]


@pytest.mark.asyncio
async def test_native_credential_clear_uses_unset_without_secret_payload():
    def reply(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/credentials/unset"
        assert body["method"] == "credentials/unset"
        assert body["payload"] == {"args": {"ref": "RESEARCH_DSH_API_KEY"}}
        return httpx.Response(
            200, json={"type": "server-response", "rpcId": body["rpcId"], "result": {"ok": True}}
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        assert await client.rpc("credentials.unset", {"ref": "RESEARCH_DSH_API_KEY"}) == {}


@pytest.mark.asyncio
async def test_rpc_envelope_and_no_legacy_timeout():
    def reply(request):
        body = json.loads(request.content)
        assert body["type"] == "client-request"
        assert request.url.path == "/api/session/prompt"
        assert body["method"] == "session/prompt"
        assert body["payload"]["args"]["request"]["mode"] == "queue"
        assert body["payload"]["args"]["request"]["requestId"]
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"accepted": True}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        assert await client.rpc(
            "session.prompt", {"sessionId": "s", "mode": "queue", "content": []}
        ) == {"accepted": True}


@pytest.mark.asyncio
async def test_native_session_delete_uses_the_allowlisted_rpc_envelope():
    def reply(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/session/delete"
        assert body["method"] == "session/delete"
        assert body["payload"] == {"args": {"request": {"sessionId": "s"}}}
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"deletedSessionIds": ["s"]}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        assert await client.rpc("session.delete", {"sessionId": "s", "cascade": True}) == {
            "deletedSessionIds": ["s"]
        }


@pytest.mark.asyncio
async def test_rpc_rejects_wrong_correlation_and_never_falls_back():
    async with DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(
                200,
                json={
                    "type": "server-response",
                    "rpcId": "wrong",
                    "result": {"ok": True, "value": {}},
                },
            )
        ),
    ) as client:
        with pytest.raises(RuntimeFailure, match="协议"):
            await client.rpc("session.list", {})


def event(seq, kind, data):
    return {"event": {"seq": seq, "type": kind, "time": 123, "data": data}}


def test_windows_runtime_auth_does_not_apply_posix_group_mode_bits(tmp_path, monkeypatch):
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(
        json.dumps(
            {
                "authority": "127.0.0.1:3081",
                "cookie": "dsh-auth-test=value",
                "cwd": str(tmp_path.resolve()),
                "source_commit": "0" * 40,
                "version": "test",
            }
        ),
        encoding="utf-8",
    )
    auth_path.chmod(0o644)
    with monkeypatch.context() as patcher:
        patcher.setattr(
            client_module,
            "read_runtime_auth_record",
            lambda path: runtime_auth_module.read_runtime_auth_record(path, platform_name="nt"),
        )
        metadata = client_module._runtime_metadata(auth_path, "127.0.0.1:3081")

    assert metadata["cookie"] == "dsh-auth-test=value"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("authority", "127.0.0.1:9999", "目标地址"),
        ("cookie", "not-a-runtime-cookie", "Cookie"),
        ("source_commit", "not-a8530a40f", "源码版本"),
    ],
)
def test_runtime_metadata_rejects_invalid_control_values(tmp_path, field, value, message):
    record = {
        "authority": "127.0.0.1:3081",
        "cookie": "dsh-auth-test=value",
        "cwd": str(tmp_path.resolve()),
        "source_commit": "0" * 40,
        "version": "test",
    }
    record[field] = value
    auth_path = tmp_path / "auth.json"
    auth_path.write_text(json.dumps(record), encoding="utf-8")
    auth_path.chmod(0o600)

    with pytest.raises(RuntimeFailure, match=message):
        client_module._runtime_metadata(auth_path, "127.0.0.1:3081")


def test_native_chunks_replaced_by_final_message_without_duplicate():
    entries = [
        event(0, "turn/start", {"turn": 1}),
        event(1, "user/message", {"id": "u1", "content": [{"type": "text", "text": "你好"}]}),
        event(
            2,
            "assistant/chunk",
            {"turn": 1, "step": 1, "chunk": {"type": "text-delta", "index": 0, "text": "答"}},
        ),
    ]
    assert project(entries)["messages"][-1]["text"] == "答"
    entries += [
        event(
            3,
            "assistant/message",
            {"turn": 1, "step": 1, "message": {"content": [{"type": "text", "text": "答案"}]}},
        ),
        event(4, "turn/end", {"turn": 1, "reason": {"kind": "completed"}}),
    ]
    result = project(entries)
    assert [m["text"] for m in result["messages"]] == ["你好", "答案"]
    assert result["status"] == "completed"


def test_failed_or_interrupted_turn_is_never_completed():
    result = project(
        [
            event(
                1,
                "turn/end",
                {"turn": 1, "reason": {"kind": "error", "error": {"message": "model unavailable"}}},
            )
        ]
    )
    assert result["status"] == "failed"
    assert result["error"] == "model unavailable"


def test_native_timestamps_supply_duration_without_inventing_missing_time():
    entries = [
        event(1, "turn/start", {"turn": 1}),
        event(2, "tool/call", {"callId": "timed", "name": "web_search"}),
        event(3, "tool/result", {"message": {"source": {"callId": "timed"}, "content": []}}),
        event(4, "turn/end", {"reason": {"kind": "completed"}}),
    ]
    for row, timestamp in zip(entries, [1000, 1200, 2300, 3000], strict=True):
        row["event"]["time"] = timestamp
    result = project(entries)
    assert result["duration_ms"] == 2000
    assert result["activities"][0]["duration_ms"] == 1100
    for row in entries:
        row["event"].pop("time")
    assert "duration_ms" not in project(entries)
    assert "duration_ms" not in project(entries)["activities"][0]


def test_runtime_url_is_loopback_only():
    with pytest.raises(ValueError):
        DSHClient("https://example.com")


def test_native_tool_result_error_updates_matching_call():
    result = project(
        [
            event(
                1, "tool/call", {"callId": "c", "name": "research_run_script", "arguments": "{}"}
            ),
            event(
                2,
                "tool/result",
                {
                    "message": {
                        "source": {"kind": "tool", "callId": "c"},
                        "content": [
                            {
                                "type": "tool-result",
                                "toolCallId": "c",
                                "isError": True,
                                "content": [{"type": "text", "text": "permission denied"}],
                            }
                        ],
                    }
                },
            ),
        ]
    )
    assert result["activities"] == [
        {
            "id": "c",
            "type": "tool",
            "seq": 1,
            "tool": "research_run_script",
            "arguments": {},
            "result": "permission denied",
            "title": "research_run_script",
            "status": "failed",
            "detail": "permission denied",
        }
    ]


def test_script_failure_payload_is_not_shown_as_successful_execution():
    entries = [
        event(1, "tool/call", {"callId": "c", "name": "research_run_script", "arguments": "{}"}),
        event(
            2,
            "tool/result",
            {
                "message": {
                    "source": {"callId": "c"},
                    "content": [
                        {
                            "type": "tool-result",
                            "toolCallId": "c",
                            "content": [
                                {
                                    "type": "text",
                                    "text": '{"status":"failed","stderr":"PermissionError"}',
                                }
                            ],
                        }
                    ],
                }
            },
        ),
    ]
    assert project(entries)["activities"][0]["status"] == "failed"


@pytest.mark.asyncio
async def test_native_respond_receipt_does_not_require_rpc_id_echo():
    def reply(request):
        body = json.loads(request.content)
        assert request.url.path == "/api/$events/result"
        assert body["payload"] == {
            "args": {
                "clientId": "event-client",
                "eventId": "approval-rpc",
                "outcome": {"kind": "result", "value": "rejected"},
            }
        }
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": None},
            },
        )

    async with DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(reply),
    ) as client:
        client._event_client_id = "event-client"
        client._pending_events["approval-rpc"] = "approval/request"
        assert await client.respond("approval-rpc", {"outcome": "rejected"}) == {"accepted": True}


@pytest.mark.asyncio
async def test_current_gateway_cookie_is_sent_without_exposing_it_in_payloads():
    def reply(request):
        assert request.headers["cookie"] == "dsh-auth-test=value"
        body = json.loads(request.content)
        assert "dsh-auth-test" not in json.dumps(body)
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": []}},
            },
        )

    async with DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(reply),
        auth_cookie="dsh-auth-test=value",
    ) as client:
        assert await client.rpc("session.list", {}) == {"items": []}


@pytest.mark.asyncio
async def test_tabbit_plugin_bridge_is_cookie_authenticated_and_allowlisted():
    def reply(request):
        assert request.headers["cookie"] == "dsh-auth-test=value"
        assert request.url.path == "/research/tabbit/tabs"
        assert dict(request.url.params) == {"instance": "ABCDEF0123456789"}
        return httpx.Response(200, json={"tabs": []})

    async with DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(reply),
        auth_cookie="dsh-auth-test=value",
    ) as client:
        assert await client.plugin_json(
            "GET",
            "/research/tabbit/tabs",
            params={"instance": "ABCDEF0123456789"},
        ) == {"tabs": []}

        with pytest.raises(RuntimeFailure, match="未授权"):
            await client.plugin_json("GET", "/arbitrary", params={})


def test_current_remote_events_are_projected_to_the_stable_workbench_surface():
    client = DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )
    assert client._event_envelope(
        {"type": "ready", "clientId": "client-1", "host": {"home": "/tmp"}}
    ) == {"type": "connected", "channel": "host"}
    assert client._event_envelope(
        {"type": "emit", "event": "api-session/status", "args": ["s", False]}
    )["payload"] == {"type": "host/session-status", "sessionId": "s", "running": False}
    requested = client._event_envelope(
        {
            "type": "waterfall",
            "event": "approval/request",
            "eventId": "event-1",
            "agentId": "s",
            "request": {"toolName": "bash", "reason": "危险操作"},
        }
    )
    assert requested["payload"] == {
        "type": "approval/requested",
        "sessionId": "s",
        "approvalId": "event-1",
        "toolName": "bash",
        "reason": "危险操作",
    }
    resolved = client._event_envelope({"type": "cancel", "eventId": "event-1"})
    assert resolved["payload"] == {
        "type": "approval/resolved",
        "sessionId": "s",
        "approvalId": "event-1",
    }


@pytest.mark.parametrize(
    "envelope",
    [
        {
            "type": "waterfall",
            "event": "approval/request",
            "eventId": "",
            "agentId": "s",
            "request": {},
        },
        {"type": "cancel", "eventId": None},
    ],
)
def test_remote_interaction_events_reject_invalid_identifiers(envelope):
    client = DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(lambda request: httpx.Response(500)),
    )

    with pytest.raises(RuntimeFailure) as failure:
        client._event_envelope(envelope)

    assert failure.value.code == "protocol_error"


@pytest.mark.asyncio
@pytest.mark.parametrize("running,activity", [(True, "running"), (False, "inactive")])
async def test_upgraded_subagent_catalog_uses_authoritative_parent_projection_and_live_status(
    running, activity
):
    calls = []

    def reply(request):
        body = json.loads(request.content)
        calls.append((request.url.path, body["payload"]["args"]))
        if request.url.path in {"/api/session/cancel", "/api/subagents/interruptByParent"}:
            return httpx.Response(
                200,
                json={
                    "type": "server-response",
                    "rpcId": body["rpcId"],
                    "result": {"ok": True, "value": {"accepted": True}},
                },
            )
        assert request.url.path == "/api/session/list"
        items = [
            {
                "sessionId": "parent",
                "running": False,
                "projections": {
                    "values": {
                        "subagentCatalog": [
                            {
                                "id": "child",
                                "mode": "continuable",
                                "label": "worker",
                                "createdAt": 1,
                            }
                        ]
                    }
                },
            },
            {
                "sessionId": "child",
                "parentSessionId": "parent",
                "origin": "subagent",
                "running": running,
            },
        ]
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": items}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        value = await client.rpc("subagent.list", {"parentSessionId": "parent"})
        assert value["entries"][0]["id"] == "child"
        assert value["entries"][0]["kind"] == "child"
        assert value["entries"][0]["activity"] == activity
        from app.research_web.service import ResearchService

        service = object.__new__(ResearchService)
        service.client = client
        service.store = SimpleNamespace(
            data={"sessions": {"parent": {"id": "parent", "created": True}}, "receipts": {}}
        )
        service.child_parents = {}
        assert await service._interaction_owner("child") == "parent"
        if not running:
            service.capabilities = SimpleNamespace(assert_consistent=lambda: None)
            service.ensure_owned = AsyncMock()
            service.connected = {"mux", "host"}
            service.detail = AsyncMock(
                return_value={"can_cancel": False, "status": "completed", "delivery": None}
            )
            assert await service._capability_idle() is True

        service.store.session = lambda _sid: {}
        service.store.audit = lambda *_args, **_kwargs: None
        service.delivery = SimpleNamespace(current=lambda _sid: None)
        service.datahub = SimpleNamespace(cancel=AsyncMock())
        service.notify = lambda: None
        assert await service._cancel("parent") == {"accepted": True}
        assert (
            "/api/subagents/interruptByParent",
            {"parentSessionId": "parent", "childSessionId": "child", "mode": "continuable"},
        ) in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("activity_only", [False, True])
async def test_upgraded_subagent_unknown_activity_fails_closed(activity_only):
    def reply(request):
        body = json.loads(request.content)
        items = [
            {
                "sessionId": "parent",
                "running": False,
                "projections": {
                    "values": {
                        "subagentCatalog": [{"id": "child", "mode": "one-shot", "createdAt": 1}]
                    }
                },
            }
        ]
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": items}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeFailure, match="状态"):
            await client.rpc(
                "subagent.list", {"parentSessionId": "parent", "activityOnly": activity_only}
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "live",
    [
        {"parentSessionId": "foreign", "origin": "subagent", "running": False},
        {"parentSessionId": "parent", "origin": "user", "running": False},
        {"parentSessionId": "parent", "origin": "subagent", "running": "false"},
        {"parentSession": "parent", "origin": "subagent", "running": False},
    ],
)
@pytest.mark.parametrize("activity_only", [False, True])
async def test_native_child_parent_identity_and_boolean_activity_remain_required(
    live, activity_only
):
    def reply(request):
        body = json.loads(request.content)
        items = [
            {
                "sessionId": "parent",
                "running": False,
                "projections": {
                    "values": {
                        "subagentCatalog": [
                            {"id": "child", "mode": "unknown" if activity_only else "continuable"}
                        ]
                    }
                },
            },
            {"sessionId": "child", **live},
        ]
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": items}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeFailure, match="状态"):
            await client.rpc(
                "subagent.list", {"parentSessionId": "parent", "activityOnly": activity_only}
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("running", [False, True])
async def test_unknown_child_mode_can_only_supply_verified_activity(running):
    def reply(request):
        body = json.loads(request.content)
        items = [
            {
                "sessionId": "parent",
                "projections": {
                    "values": {"subagentCatalog": [{"id": "child", "mode": "unknown"}]}
                },
            },
            {
                "sessionId": "child",
                "parentSessionId": "parent",
                "origin": "subagent",
                "running": running,
            },
        ]
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": body["rpcId"],
                "result": {"ok": True, "value": {"items": items}},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        with pytest.raises(RuntimeFailure, match="状态未知"):
            await client.rpc("subagent.list", {"parentSessionId": "parent"})
        value = await client.rpc(
            "subagent.list", {"parentSessionId": "parent", "activityOnly": True}
        )
        assert value["entries"][0]["mode"] == "unknown"
        assert value["entries"][0]["activity"] == ("running" if running else "inactive")


@pytest.mark.asyncio
async def test_question_wire_failure_retains_pending_event_for_safe_retry():
    calls = []

    def reply(request):
        calls.append(json.loads(request.content))
        if len(calls) == 1:
            raise httpx.ConnectError("temporary failure", request=request)
        return httpx.Response(
            200,
            json={
                "type": "server-response",
                "rpcId": calls[-1]["rpcId"],
                "result": {"ok": True, "value": None},
            },
        )

    async with DSHClient("http://127.0.0.1:3081", transport=httpx.MockTransport(reply)) as client:
        client._event_client_id = "event-client"
        client._pending_events["question-retry"] = {
            "event": "user-questions/request",
            "sessionId": "owned",
        }
        answer = {"answer": {"answers": [{"id": "time", "custom": "15:30", "selected": []}]}}
        with pytest.raises(RuntimeFailure):
            await client.respond("question-retry", answer)
        assert "question-retry" in client._pending_events
        assert await client.respond("question-retry", answer) == {"accepted": True}
        assert "question-retry" not in client._pending_events
        with pytest.raises(RuntimeFailure, match="失效"):
            await client.respond("question-retry", answer)
        assert len(calls) == 2
        assert calls[0]["payload"]["args"]["outcome"] == calls[1]["payload"]["args"]["outcome"]


def test_native_question_history_requires_matching_successful_result():
    items = [{"id": "time", "question": "何时执行？"}]
    call = event(
        1,
        "tool/call",
        {"callId": "q", "name": "ask_user_question", "arguments": json.dumps({"questions": items})},
    )

    def result(answers, error=False):
        return event(
            2,
            "tool/result",
            {
                "message": {
                    "role": "tool",
                    "source": {"callId": "q"},
                    "isError": error,
                    "content": [{"type": "text", "text": json.dumps({"answers": answers})}],
                }
            },
        )

    answers = [{"id": "time", "selected": ["15:30"], "custom": ""}]
    assert project([call, result(answers)])["question_history"] == [
        {"id": "q", "seq": 2, "items": items, "answers": answers}
    ]
    assert project([call])["question_history"] == []
    assert project([call, result(answers, True)])["question_history"] == []
    assert (
        project([call, result([{"id": "foreign", "selected": [], "custom": "伪造"}])])[
            "question_history"
        ]
        == []
    )
    assert project([result(answers)])["question_history"] == []


def test_tool_projection_keeps_order_arguments_and_redacts_nested_secrets():
    rows = [
        event(
            7,
            "tool/result",
            {
                "message": {
                    "role": "tool",
                    "name": "web_search",
                    "source": {"callId": "x"},
                    "content": [
                        {
                            "type": "text",
                            "text": '{"nested":{"authorization":"secret","answer":42}}',
                        }
                    ],
                }
            },
        ),
        event(
            9,
            "tool/call",
            {
                "callId": "x",
                "name": "web_search",
                "arguments": '{"query":"test","nested":{"api_key":"secret"}}',
            },
        ),
    ]
    activity = project(rows)["activities"][0]
    assert activity["seq"] == 7
    assert activity["tool"] == "web_search"
    assert activity["status"] == "completed"
    assert activity["arguments"]["nested"]["api_key"] == "[REDACTED]"
    assert activity["result"]["nested"]["authorization"] == "[REDACTED]"
    assert activity["result"]["nested"]["answer"] == 42
    assert "secret" not in json.dumps(activity)


def test_automation_execution_snapshot_does_not_follow_updated_task():
    from app.research_web.service import automation_execution_context

    snapshot = {"definition_version": 1, "output_formats": ["md"]}
    run = {
        "id": "r1",
        "session_id": "s1",
        "automation_id": "a1",
        "trigger": "manual",
        "definition_version": 1,
        "definition_snapshot": snapshot,
    }
    result = automation_execution_context({"r1": run}, "s1")
    snapshot["output_formats"].append("pdf")
    assert result["definition_snapshot"]["output_formats"] == ["md"]
    assert result["definition_version"] == 1
    assert automation_execution_context({"r1": run}, "other") is None


def test_automation_followup_scope_cannot_expand_or_change_outputs():
    from app.research_web.service import automation_followup_scope
    from app.research_web.store import StoreError

    scope = {"approved_tools": ["research_run_script"]}
    context = {"definition_snapshot": {"output_formats": ["md"]}}
    assert automation_followup_scope(scope, context, None, None, None, (), (), None) == (
        ["research_run_script"],
        ["md"],
    )
    for changes in [
        ("skill", None, None, (), (), None),
        (None, None, None, ("web_search",), (), None),
        (None, None, None, (), (), ["pdf"]),
        (None, None, None, (), ("method",), None),
    ]:
        with pytest.raises(StoreError, match="批准范围"):
            automation_followup_scope(scope, context, *changes)


def test_activity_evidence_is_total_bounded_and_redacts_text_and_url_credentials():
    from app.research_web.projection import activity_value

    assert activity_value('{"api_key":"' + "x" * 40000 + '"}') == "[TRUNCATED]"
    bounded = activity_value({"rows": ["x" * 16000] * 100})
    assert len(json.dumps(bounded)) < 34000
    value = activity_value(
        "GET https://user:password@host/path?token=abc api_key=xyz Bearer secret"
    )
    assert all(secret not in value for secret in ("password", "abc", "xyz", "secret"))
    rows = [
        event(
            1,
            "tool/result",
            {
                "error": {"message": "password=secret"},
                "message": {"source": {"callId": "x"}, "content": []},
            },
        )
    ]
    assert "secret" not in json.dumps(project(rows)["activities"])


def test_activity_redacts_entire_auth_headers_and_quoted_credentials():
    from app.research_web.projection import activity_value

    examples = [
        "Authorization: Basic c3VwZXJzZWNyZXQ=",
        "Cookie: session=supersecret; csrf=othersecret",
        'password="two word secret"',
        "client_secret='long secret value'",
        "credentials=supersecret",
    ]
    result = json.dumps(activity_value({"error": examples}))
    for secret in (
        "c3VwZXJzZWNyZXQ=",
        "supersecret",
        "othersecret",
        "two word secret",
        "long secret value",
    ):
        assert secret not in result


def test_question_history_preserves_numeric_and_json_like_answer_strings():
    items = [{"id": "q1", "question": "选择日期", "options": ["null", "2026"]}]
    answers = [{"id": "q1", "selected": ["null"], "custom": "2026"}]
    rows = [
        event(
            1,
            "tool/call",
            {
                "callId": "qcall",
                "name": "ask_user_question",
                "arguments": json.dumps({"questions": items}),
            },
        ),
        event(
            2,
            "tool/result",
            {
                "message": {
                    "role": "tool",
                    "name": "ask_user_question",
                    "source": {"callId": "qcall"},
                    "content": [{"type": "text", "text": json.dumps({"answers": answers})}],
                }
            },
        ),
    ]
    result = project(rows)
    assert result["question_history"][0]["answers"] == answers
    assert result["activities"][0]["arguments"]["questions"] == items
    from app.research_web.projection import activity_value

    assert activity_value({"index": "123456", "flag": "true"}) == {
        "index": "123456",
        "flag": "true",
    }


def test_long_quoted_credentials_are_redacted_before_display_truncation():
    from app.research_web.projection import activity_value

    secret = "first " + ("rest_of_secret " * 1300)
    for suffix in ('"', ""):
        value = activity_value('password="' + secret + suffix)
        assert "rest_of_secret" not in value
        assert "first" not in value


def test_activity_evidence_byte_limit_handles_cjk_and_emoji_without_broken_characters():
    from app.research_web.projection import activity_value

    for value in ("中" * 11000, {"rows": ["中文测试" * 1200] * 40}, {"rows": ["🔬📊" * 1500] * 40}):
        result = activity_value(value)
        serialized = json.dumps(result, ensure_ascii=False).encode("utf-8")
        assert len(serialized) <= 32768
        assert "\ufffd" not in serialized.decode("utf-8")
    value = activity_value({"label": "中文🔬", "index": "123456", "answer": "2026"})
    assert value == {"label": "中文🔬", "index": "123456", "answer": "2026"}
    bounded = activity_value({"label": "中" * 7000})
    assert isinstance(bounded["label"], str)
    assert len(bounded["label"].encode("utf-8")) <= 16000
