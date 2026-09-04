"""Native DSH contract regression, deliberately independent of legacy fixtures."""

import json

import httpx
import pytest

from app.research_web.client import DSHClient, RuntimeFailure
from app.research_web.projection import project


@pytest.mark.asyncio
async def test_rpc_envelope_and_no_legacy_timeout():
    def reply(request):
        body = json.loads(request.content)
        assert body["type"] == "client-request"
        assert body["method"] == "session.prompt"
        assert body["payload"]["mode"] == "queue"
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
            await client.rpc("host.describe", {})


def event(seq, kind, data):
    return {"event": {"seq": seq, "type": kind, "time": 123, "data": data}}


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
            event(1, "tool/call", {"callId": "c", "name": "research_run_script", "arguments": "{}"}),
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
    async with DSHClient(
        "http://127.0.0.1:3081",
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"accepted": True})),
    ) as client:
        assert await client.respond("approval-rpc", {"outcome": "rejected"}) == {"accepted": True}
