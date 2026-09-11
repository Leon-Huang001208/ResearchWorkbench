from unittest.mock import Mock

import httpx
import pytest

from app.research_web.automation.transport import DeliveryTransport


class Channels:
    def __init__(self, configuration):
        self.value = configuration

    def configuration(self, _channel_id):
        return self.value


@pytest.mark.asyncio
async def test_generic_webhook_is_hmac_signed_and_does_not_follow_redirects():
    captured = {}

    def handler(request):
        captured["request"] = request
        return httpx.Response(204)

    transport = DeliveryTransport(
        Channels(
            {
                "endpoint": "https://notify.example.test/hook",
                "secret": "secret",
            }
        ),
        http_transport=httpx.MockTransport(handler),
        now=lambda: 1_700_000_000,
    )
    event = {"event_id": "event-1", "status": "completed", "summary": "完成"}

    await transport({"id": "channel-1", "kind": "webhook"}, event)

    request = captured["request"]
    assert request.headers["X-Research-Event-Id"] == "event-1"
    assert request.headers["X-Research-Signature"].startswith("sha256=")
    assert request.url == "https://notify.example.test/hook"


@pytest.mark.asyncio
async def test_smtp_uses_starttls_and_never_returns_recipient_data():
    smtp = Mock()
    smtp.__enter__ = Mock(return_value=smtp)
    smtp.__exit__ = Mock(return_value=False)
    smtp_factory = Mock(return_value=smtp)
    transport = DeliveryTransport(
        Channels(
            {
                "smtp_host": "smtp.example.test",
                "smtp_port": 587,
                "smtp_username": "robot@example.test",
                "sender": "robot@example.test",
                "recipients": ["private@example.test"],
                "secret": "password",
            }
        ),
        smtp_factory=smtp_factory,
    )

    result = await transport(
        {"id": "channel-1", "kind": "smtp"},
        {"event_id": "event-1", "status": "completed", "summary": "完成"},
    )

    assert result is None
    smtp.starttls.assert_called_once()
    smtp.login.assert_called_once_with("robot@example.test", "password")
    smtp.send_message.assert_called_once()
