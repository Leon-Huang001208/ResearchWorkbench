"""Independent Automation delivery attempts with stable signed webhook events."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from collections.abc import Awaitable, Callable
from typing import Any

from core.observability import get_logger

log = get_logger(__name__)
RETRY_DELAYS = (5, 30, 120)


def signed_webhook(body: dict[str, Any], event_id: str, timestamp: int, secret: str) -> dict:
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    signature = hmac.new(
        secret.encode("utf-8"),
        f"{event_id}.{timestamp}.{canonical}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return {
        "body": canonical,
        "headers": {
            "Content-Type": "application/json",
            "X-Research-Event-Id": event_id,
            "X-Research-Timestamp": str(timestamp),
            "X-Research-Signature": f"sha256={signature}",
        },
    }


class DeliveryDispatcher:
    """Retry delivery separately from the immutable research outcome."""

    def __init__(
        self,
        *,
        transport: Callable[[dict, dict], Awaitable[None]],
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.transport = transport
        self.sleep = sleep

    async def deliver(self, run: dict, channel: dict, event: dict) -> dict:
        for attempt in range(1, len(RETRY_DELAYS) + 2):
            try:
                await self.transport(channel, event)
                log.info(
                    "automation_delivery_succeeded",
                    status="delivered",
                    attempt=attempt,
                )
                return {"status": "delivered", "attempts": attempt, "failure_code": None}
            except Exception as exc:  # noqa: BLE001 - transports expose backend errors.
                log.warning(
                    "automation_delivery_attempt_failed",
                    status="retrying" if attempt <= len(RETRY_DELAYS) else "failed",
                    error_type=type(exc).__name__,
                    attempt=attempt,
                )
                if attempt > len(RETRY_DELAYS):
                    return {
                        "status": "failed",
                        "attempts": attempt,
                        "failure_code": "delivery_failed",
                    }
                await self.sleep(RETRY_DELAYS[attempt - 1])
        raise RuntimeError("delivery_retry_state_invalid")
