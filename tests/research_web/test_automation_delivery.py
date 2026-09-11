import hashlib
import hmac
import json

import httpx
import pytest

from app.research_web.automation.delivery import DeliveryDispatcher, signed_webhook


def test_webhook_signature_is_stable_across_retries():
    body = {"event_id": "event-1", "status": "completed"}
    first = signed_webhook(body, "event-1", 1_700_000_000, "secret")
    second = signed_webhook(body, "event-1", 1_700_000_000, "secret")
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        b"secret",
        f"event-1.1700000000.{encoded}".encode(),
        hashlib.sha256,
    ).hexdigest()

    assert first == second
    assert first["headers"]["X-Research-Signature"] == f"sha256={expected}"


@pytest.mark.asyncio
async def test_delivery_retries_three_times_without_changing_research_status():
    attempts = []
    delays = []

    async def transport(_channel, event):
        attempts.append(event["event_id"])
        raise OSError("offline")

    async def sleep(delay):
        delays.append(delay)

    dispatcher = DeliveryDispatcher(transport=transport, sleep=sleep)
    run = {"id": "run-1", "research_status": "completed", "delivery_status": "pending"}

    result = await dispatcher.deliver(
        run,
        {"id": "channel-1", "kind": "webhook"},
        {"event_id": "event-1", "status": "completed"},
    )

    assert attempts == ["event-1"] * 4
    assert delays == [5, 30, 120]
    assert result == {"status": "failed", "attempts": 4, "failure_code": "delivery_failed"}
    assert run["research_status"] == "completed"


@pytest.mark.asyncio
async def test_http_transport_errors_follow_the_same_bounded_retry_policy():
    attempts = []

    async def transport(_channel, _event):
        attempts.append(1)
        raise httpx.ConnectError("offline")

    dispatcher = DeliveryDispatcher(
        transport=transport,
        sleep=lambda _delay: __import__("asyncio").sleep(0),
    )
    result = await dispatcher.deliver(
        {"id": "run-1", "research_status": "completed"},
        {"id": "channel-1", "kind": "webhook"},
        {"event_id": "event-1", "status": "completed"},
    )

    assert len(attempts) == 4
    assert result["status"] == "failed"
