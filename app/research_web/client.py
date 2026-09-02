"""Allowlisted, loopback-only native DSH transport, never a generic RPC proxy."""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

import httpx
import websockets

from core.observability import get_logger

log = get_logger(__name__)
METHODS = frozenset(
    {
        "host.describe",
        "llm.models",
        "session.create",
        "session.list",
        "session.history",
        "session.rename",
        "session.prompt",
        "session.cancel",
        "session.models",
        "session.selectModel",
        "subagent.list",
        "subagent.history",
        "subagent.interrupt",
        "skill.list",
        "agentPreset.list",
        "credentials.set",
        "credentials.describe",
        "settings.mutate",
    }
)


class RuntimeFailure(Exception):
    """Safe product-facing error; never includes raw credentials or HTTP body."""

    def __init__(self, message: str, code: str = "runtime_unavailable"):
        super().__init__(message)
        self.code = code


class DSHClient:
    def __init__(self, url: str, *, transport: Any = None):
        parsed = urlparse(url)
        if (
            parsed.scheme != "http"
            or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username
            or parsed.password
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("DSH 只允许本机回环 HTTP 地址")
        self.url = url.rstrip("/")
        # Timeout covers command admission, not execution; never replay timed-out POSTs.
        self.http = httpx.AsyncClient(
            base_url=self.url,
            trust_env=False,
            timeout=httpx.Timeout(15, connect=3),
            transport=transport,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        await self.http.aclose()

    async def rpc(self, method: str, payload: dict) -> dict:
        if method not in METHODS:
            raise RuntimeFailure("未授权的 DSH 方法", "forbidden")
        rpc_id = str(uuid4())
        try:
            response = await self.http.post(
                f"/api/{method}",
                json={
                    "type": "client-request",
                    "rpcId": rpc_id,
                    "method": method,
                    "payload": payload,
                },
            )
            response.raise_for_status()
            body = response.json()
            if body.get("type") != "server-response" or body.get("rpcId") != rpc_id:
                raise RuntimeFailure("DSH 协议响应不匹配", "protocol_error")
            result = body["result"]
            if result.get("ok") is not True:
                code = result.get("error", {}).get("code", "runtime_error")
                log.warning("dsh_rpc_rejected", method=method, code=code)
                raise RuntimeFailure(f"DSH 拒绝请求：{code}", code)
            value = result["value"]
            if not isinstance(value, dict):
                raise RuntimeFailure("DSH 协议返回值不匹配", "protocol_error")
            return value
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("dsh_rpc_transport_failed", method=method, error_type=type(exc).__name__)
            raise RuntimeFailure("DSH 连接失败；请求未自动重发，请先检查历史再重试") from exc

    async def respond(self, rpc_id: str, value: dict) -> dict:
        try:
            response = await self.http.post(
                "/api/respond",
                json={
                    "type": "client-response",
                    "rpcId": rpc_id,
                    "result": {"ok": True, "value": value},
                },
            )
            response.raise_for_status()
            receipt = response.json()
            if receipt.get("accepted") is not True:
                raise RuntimeFailure("DSH 未接受审批响应", "approval_rejected")
            return receipt
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("dsh_approval_failed", error_type=type(exc).__name__)
            raise RuntimeFailure("审批发送失败，请等待状态同步后重试") from exc

    async def frames(self, channel: str) -> AsyncIterator[dict]:
        if channel not in {"mux", "host"}:
            raise ValueError("Unknown event channel")
        uri = self.url.replace("http:", "ws:", 1) + f"/api/events.{channel}"
        async with websockets.connect(
            uri, proxy=None, open_timeout=5, max_size=16 * 1024 * 1024
        ) as ws:
            yield {"type": "connected", "channel": channel}
            async for raw in ws:
                frame = json.loads(raw)
                if frame.get("type") != "server-request" or not isinstance(
                    frame.get("payload"), dict
                ):
                    raise RuntimeFailure("DSH 事件协议不匹配", "protocol_error")
                yield frame

    async def history(self, sid: str) -> list[dict]:
        entries: dict[int, dict] = {}
        before = None
        for _ in range(100):
            payload = {"sessionId": sid, "maxMessages": 100}
            if before is not None:
                payload["beforeSeq"] = before
            page = await self.rpc("session.history", payload)
            rows = page["events"]
            for row in rows:
                entries[row["event"]["seq"]] = row
            if not page.get("hasMore"):
                return [entries[k] for k in sorted(entries)]
            next_before = min((row["event"]["seq"] for row in rows), default=None)
            if next_before is None or next_before == before:
                raise RuntimeFailure("DSH 历史分页未前进", "protocol_error")
            before = next_before
            await asyncio.sleep(0)
        raise RuntimeFailure("历史超出当前读取上限，未截断冒充完整结果", "history_limit")
