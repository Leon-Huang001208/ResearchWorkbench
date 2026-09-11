"""Bounded Automation delivery transports without response-body disclosure."""

from __future__ import annotations

import asyncio
import json
import smtplib
import ssl
import time
from email.message import EmailMessage
from typing import Any

import httpx

from .delivery import signed_webhook
from .models import AutomationError


class DeliveryTransport:
    """Resolve secret channel configuration only at the outbound boundary."""

    def __init__(
        self,
        channels,
        *,
        http_transport: httpx.AsyncBaseTransport | None = None,
        smtp_factory=smtplib.SMTP,
        now=time.time,
    ) -> None:
        self.channels = channels
        self.http_transport = http_transport
        self.smtp_factory = smtp_factory
        self.now = now

    async def __call__(self, channel: dict, event: dict) -> None:
        configuration = self.channels.configuration(channel["id"])
        if channel["kind"] == "smtp":
            await asyncio.to_thread(self._smtp, configuration, event)
            return
        await self._webhook(channel["kind"], configuration, event)

    @staticmethod
    def _message(event: dict) -> str:
        values = [f"研究任务状态：{event.get('status') or 'unknown'}"]
        if event.get("summary"):
            values.append(str(event["summary"]))
        if event.get("session_url"):
            values.append(str(event["session_url"]))
        return "\n\n".join(values)

    async def _webhook(self, kind: str, configuration: dict, event: dict) -> None:
        endpoint = configuration.get("endpoint")
        if not endpoint:
            raise AutomationError("交付地址未配置", "delivery_channel_unconfigured", 409)
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if kind == "webhook":
            secret = configuration.get("secret")
            if not secret:
                raise AutomationError(
                    "Webhook 签名秘密未配置", "delivery_channel_unconfigured", 409
                )
            signed = signed_webhook(event, event["event_id"], int(self.now()), secret)
            body = signed["body"]
            headers = signed["headers"]
        else:
            message = self._message(event)
            payloads: dict[str, dict[str, Any]] = {
                "feishu": {"msg_type": "text", "content": {"text": message}},
                "wecom": {"msgtype": "text", "text": {"content": message}},
                "dingtalk": {"msgtype": "text", "text": {"content": message}},
            }
            try:
                payload = payloads[kind]
            except KeyError as exc:
                raise AutomationError("未知交付渠道", "delivery_kind_invalid", 422) from exc
            body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        async with httpx.AsyncClient(
            transport=self.http_transport,
            follow_redirects=False,
            trust_env=False,
            timeout=httpx.Timeout(15, connect=5),
        ) as client:
            response = await client.post(endpoint, content=body.encode("utf-8"), headers=headers)
            response.raise_for_status()

    def _smtp(self, configuration: dict, event: dict) -> None:
        message = EmailMessage()
        message["Subject"] = f"Research Workbench · {event.get('status') or 'unknown'}"
        message["From"] = configuration["sender"]
        message["To"] = ", ".join(configuration["recipients"])
        message.set_content(self._message(event))
        with self.smtp_factory(
            configuration["smtp_host"], configuration["smtp_port"], timeout=15
        ) as smtp:
            smtp.starttls(context=ssl.create_default_context())
            username = configuration.get("smtp_username")
            secret = configuration.get("secret")
            if username and secret:
                smtp.login(username, secret)
            smtp.send_message(message)
