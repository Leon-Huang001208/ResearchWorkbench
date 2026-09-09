"""Allowlisted, loopback-only compatibility bridge for the current DSH Remote API."""

from __future__ import annotations

import asyncio
import json
import os
import stat
from collections.abc import AsyncIterator
from pathlib import Path
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
        "session.delete",
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
MAX_STREAM_BYTES = 16 * 1024 * 1024


class RuntimeFailure(Exception):
    """Safe product-facing error; never includes raw credentials or HTTP body."""

    def __init__(self, message: str, code: str = "runtime_unavailable"):
        super().__init__(message)
        self.code = code


def _default_auth_path() -> Path:
    configured = os.environ.get("RESEARCH_RUNTIME_AUTH")
    if configured:
        return Path(configured).expanduser()
    data = os.environ.get("RESEARCH_DATA_HOME")
    root = Path(data).expanduser() if data else Path.home() / ".research-workbench/research-web"
    return root / "runtime/auth.json"


def _runtime_metadata(path: Path, authority: str) -> dict[str, str]:
    """Read one manager-owned authentication record through a fail-closed boundary."""
    try:
        identity = path.lstat()
        if not stat.S_ISREG(identity.st_mode) or path.is_symlink() or identity.st_mode & 0o077:
            raise RuntimeFailure("DSH 认证控制文件权限不安全", "runtime_auth_invalid")
        value = json.loads(path.read_text(encoding="utf-8"))
    except RuntimeFailure:
        raise
    except (OSError, TypeError, json.JSONDecodeError) as exc:
        raise RuntimeFailure("DSH 认证控制文件不可用", "runtime_auth_unavailable") from exc
    required = {"authority", "cookie", "cwd", "source_commit", "version"}
    if not isinstance(value, dict) or not required.issubset(value):
        raise RuntimeFailure("DSH 认证控制文件格式无效", "runtime_auth_invalid")
    if value.get("authority") != authority:
        raise RuntimeFailure("DSH 认证控制文件与目标地址不匹配", "runtime_auth_invalid")
    if any(not isinstance(value.get(key), str) or not value[key] for key in required):
        raise RuntimeFailure("DSH 认证控制文件字段无效", "runtime_auth_invalid")
    cookie = value["cookie"]
    if len(cookie) > 4096 or "\r" in cookie or "\n" in cookie or not cookie.startswith("dsh-auth-"):
        raise RuntimeFailure("DSH 认证 Cookie 无效", "runtime_auth_invalid")
    if not Path(value["cwd"]).is_absolute():
        raise RuntimeFailure("DSH 运行目录记录无效", "runtime_auth_invalid")
    commit = value["source_commit"]
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise RuntimeFailure("DSH 源码版本记录无效", "runtime_auth_invalid")
    return {key: value[key] for key in required}


class DSHClient:
    """Translate the stable Workbench call surface to slash-namespaced Typert RPC."""

    def __init__(
        self,
        url: str,
        *,
        transport: Any = None,
        auth_cookie: str | None = None,
        auth_path: Path | None = None,
    ):
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
        self.metadata: dict[str, str] = {}
        if auth_cookie is None and transport is None:
            self.metadata = _runtime_metadata(auth_path or _default_auth_path(), parsed.netloc)
            auth_cookie = self.metadata["cookie"]
        headers = {"Cookie": auth_cookie} if auth_cookie else None
        self.http = httpx.AsyncClient(
            base_url=self.url,
            headers=headers,
            trust_env=False,
            timeout=httpx.Timeout(15, connect=3),
            transport=transport,
        )
        self._cookie = auth_cookie
        self._event_client_id: str | None = None
        self._pending_events: dict[str, dict[str, str] | str] = {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    async def close(self):
        await self.http.aclose()

    @staticmethod
    def _wire_call(method: str, payload: dict) -> tuple[str, dict]:
        if method in {"llm.models", "session.models"}:
            return "session/modelCatalog", {}
        if method == "session.list":
            return "session/list", {"_request": payload}
        if method in {
            "session.create",
            "session.rename",
            "session.cancel",
            "session.selectModel",
        }:
            return method.replace(".", "/"), {"request": payload}
        if method == "session.delete":
            return "session/delete", {"request": {"sessionId": payload.get("sessionId")}}
        if method == "session.prompt":
            request = {**payload}
            request.setdefault("requestId", str(uuid4()))
            return "session/prompt", {"request": request}
        if method == "subagent.list":
            return "subagents/list", payload
        if method == "subagent.interrupt":
            return "subagents/interruptByParent", payload
        if method == "skill.list":
            return "skills/list", {"request": payload}
        if method == "agentPreset.list":
            return "agentPresets/list", {}
        if method in {"credentials.set", "credentials.describe", "settings.mutate"}:
            return method.replace(".", "/"), payload
        raise RuntimeFailure("未授权的 DSH 方法", "forbidden")

    async def _rpc_wire(self, endpoint: str, args: dict) -> dict:
        rpc_id = str(uuid4())
        try:
            response = await self.http.post(
                f"/api/{endpoint}",
                json={
                    "type": "client-request",
                    "rpcId": rpc_id,
                    "method": endpoint,
                    "payload": {"args": args},
                },
            )
            response.raise_for_status()
            body = response.json()
            if body.get("type") != "server-response" or body.get("rpcId") != rpc_id:
                raise RuntimeFailure("DSH 协议响应不匹配", "protocol_error")
            result = body["result"]
            if result.get("ok") is not True:
                code = result.get("error", {}).get("code", "runtime_error")
                log.warning("dsh_rpc_rejected", method=endpoint, code=code)
                raise RuntimeFailure(f"DSH 拒绝请求：{code}", code)
            value = result.get("value")
            if value is None:
                return {}
            if not isinstance(value, dict):
                raise RuntimeFailure("DSH 协议返回值不匹配", "protocol_error")
            return value
        except RuntimeFailure:
            raise
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            log.warning("dsh_rpc_transport_failed", method=endpoint, error_type=type(exc).__name__)
            raise RuntimeFailure("DSH 连接失败；请求未自动重发，请先检查历史再重试") from exc

    async def rpc(self, method: str, payload: dict) -> dict:
        if method not in METHODS:
            raise RuntimeFailure("未授权的 DSH 方法", "forbidden")
        if method == "host.describe":
            await self._rpc_wire("session/list", {"_request": {}})
            if not self.metadata:
                return {"cwd": "", "version": "test", "provider": "DSH"}
            return {
                "cwd": self.metadata["cwd"],
                "version": self.metadata["version"],
                "provider": "DSH",
                "source_commit": self.metadata["source_commit"],
            }
        if method == "session.history":
            return await self._history_opening(
                {"kind": "session", "sessionId": payload["sessionId"]},
                int(payload.get("maxMessages", 100)),
            )
        if method == "subagent.history":
            address = {
                "kind": "subagent",
                "parentSessionId": payload["parentSessionId"],
                "childSessionId": payload["childSessionId"],
                "mode": payload["mode"],
            }
            return await self._history_opening(address, int(payload.get("maxMessages", 100)))
        endpoint, args = self._wire_call(method, payload)
        value = await self._rpc_wire(endpoint, args)
        if method == "credentials.describe":
            return {"credentials": value}
        return value

    async def respond(self, rpc_id: str, value: dict) -> dict:
        client_id = self._event_client_id
        pending = self._pending_events.get(rpc_id)
        event = pending if isinstance(pending, str) else (pending or {}).get("event")
        if not client_id or event not in {"approval/request", "user-questions/request"}:
            raise RuntimeFailure("DSH 交互请求已失效", "interaction_expired")
        answer = value.get("outcome") if event == "approval/request" else value.get("answer")
        await self._rpc_wire(
            "$events/result",
            {
                "clientId": client_id,
                "eventId": rpc_id,
                "outcome": {"kind": "result", "value": answer},
            },
        )
        return {"accepted": True}

    async def _stream(self, endpoint: str, args: dict) -> AsyncIterator[dict]:
        uri = self.url.replace("http:", "ws:", 1) + "/api/remote.mux"
        stream_id = str(uuid4())
        headers = {"Cookie": self._cookie} if self._cookie else None
        try:
            async with websockets.connect(
                uri,
                proxy=None,
                additional_headers=headers,
                open_timeout=5,
                max_size=MAX_STREAM_BYTES,
            ) as ws:
                await ws.send(
                    json.dumps(
                        {
                            "type": "open",
                            "streamId": stream_id,
                            "endpoint": endpoint,
                            "payload": {"args": args},
                        }
                    )
                )
                try:
                    async for raw in ws:
                        frame = json.loads(raw)
                        if not isinstance(frame, dict) or frame.get("streamId") != stream_id:
                            continue
                        if frame.get("type") == "item":
                            value = frame.get("value")
                            if not isinstance(value, dict):
                                raise RuntimeFailure("DSH 流式响应格式无效", "protocol_error")
                            yield value
                        elif frame.get("type") == "error":
                            error = (
                                frame.get("error") if isinstance(frame.get("error"), dict) else {}
                            )
                            raise RuntimeFailure(
                                "DSH 流式请求失败",
                                str(error.get("code", "runtime_error")),
                            )
                        elif frame.get("type") == "end":
                            return
                        else:
                            raise RuntimeFailure("DSH 流式响应格式无效", "protocol_error")
                finally:
                    if ws.close_code is None:
                        await ws.send(json.dumps({"type": "cancel", "streamId": stream_id}))
        except RuntimeFailure:
            raise
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            log.warning("dsh_stream_failed", endpoint=endpoint, error_type=type(exc).__name__)
            raise RuntimeFailure("DSH 事件连接失败", "runtime_unavailable") from exc

    def _event_envelope(self, value: dict) -> dict | None:
        kind = value.get("type")
        if kind == "ready":
            client_id = value.get("clientId")
            if not isinstance(client_id, str) or not client_id:
                raise RuntimeFailure("DSH 事件握手无效", "protocol_error")
            self._event_client_id = client_id
            return {"type": "connected", "channel": "host"}
        if kind == "emit":
            event = value.get("event")
            args = value.get("args")
            if not isinstance(args, list):
                raise RuntimeFailure("DSH 事件参数无效", "protocol_error")
            if event == "api-session/status" and len(args) == 2:
                return {
                    "type": "server-request",
                    "payload": {
                        "type": "host/session-status",
                        "sessionId": args[0],
                        "running": args[1],
                    },
                }
            if event == "api-session/error" and len(args) == 2:
                return {
                    "type": "server-request",
                    "payload": {
                        "type": "host/agent-error",
                        "sessionId": args[0],
                        "message": args[1],
                    },
                }
            if (
                event in {"api-session/activity", "api-session/added", "api-session/removed"}
                and args
            ):
                session_id = args[0].get("sessionId") if isinstance(args[0], dict) else args[0]
                return {
                    "type": "server-request",
                    "payload": {"type": "host/session-activity", "sessionId": session_id},
                }
            return None
        if kind == "waterfall":
            event_id, event, session_id = (
                value.get("eventId"),
                value.get("event"),
                value.get("agentId"),
            )
            request = value.get("request")
            if not all(isinstance(item, str) and item for item in (event_id, event, session_id)):
                raise RuntimeFailure("DSH 交互事件标识无效", "protocol_error")
            if not isinstance(request, dict):
                raise RuntimeFailure("DSH 交互事件内容无效", "protocol_error")
            self._pending_events[event_id] = {"event": event, "sessionId": session_id}
            if event == "approval/request":
                payload = {
                    **request,
                    "type": "approval/requested",
                    "sessionId": session_id,
                    "approvalId": event_id,
                }
            elif event == "user-questions/request":
                payload = {
                    **request,
                    "type": "question/requested",
                    "sessionId": session_id,
                }
            else:
                return None
            return {"type": "server-request", "rpcId": event_id, "payload": payload}
        if kind == "cancel":
            event_id = value.get("eventId")
            pending = self._pending_events.pop(event_id, None)
            event = pending if isinstance(pending, str) else (pending or {}).get("event")
            session_id = "" if isinstance(pending, str) else (pending or {}).get("sessionId", "")
            if event == "approval/request":
                payload = {
                    "type": "approval/resolved",
                    "sessionId": session_id,
                    "approvalId": event_id,
                }
            elif event == "user-questions/request":
                payload = {
                    "type": "question/resolved",
                    "sessionId": session_id,
                    "questionRpcId": event_id,
                }
            else:
                return None
            return {"type": "server-request", "payload": payload}
        return None

    async def frames(self, channel: str) -> AsyncIterator[dict]:
        if channel not in {"mux", "host"}:
            raise ValueError("Unknown event channel")
        endpoint = "$events" if channel == "host" else "session/control"
        connected = False
        async for value in self._stream(endpoint, {}):
            if channel == "mux":
                if not connected:
                    connected = True
                    yield {"type": "connected", "channel": "mux"}
                continue
            envelope = self._event_envelope(value)
            if envelope is not None:
                yield envelope

    async def _history_opening(self, address: dict, max_messages: int) -> dict:
        if max_messages < 1 or max_messages > 1000:
            raise RuntimeFailure("DSH 历史读取数量无效", "protocol_error")
        async for value in self._stream(
            "session/follow", {"request": {"address": address, "maxMessages": max_messages}}
        ):
            if value.get("type") != "snapshot":
                raise RuntimeFailure("DSH 历史流缺少起始快照", "protocol_error")
            records = value.get("records")
            cursor = value.get("cursor")
            if not isinstance(records, list) or not isinstance(cursor, int):
                raise RuntimeFailure("DSH 历史快照格式无效", "protocol_error")
            return {
                "events": records,
                "hasMore": value.get("hasMore") is True,
                "cursor": cursor,
            }
        raise RuntimeFailure("DSH 历史流提前结束", "protocol_error")

    async def history(self, sid: str) -> list[dict]:
        address = {"kind": "session", "sessionId": sid}
        opening = await self._history_opening(address, 100)
        entries = {
            row["event"]["seq"]: row
            for row in opening["events"]
            if isinstance(row, dict) and isinstance(row.get("event"), dict)
        }
        before = min(entries, default=None)
        for _ in range(100):
            if not opening.get("hasMore"):
                return [entries[key] for key in sorted(entries)]
            if before is None:
                raise RuntimeFailure("DSH 历史分页未前进", "protocol_error")
            page = await self._rpc_wire(
                "session/page",
                {
                    "request": {
                        "address": address,
                        "throughSeq": opening["cursor"],
                        "beforeSeq": before,
                        "maxMessages": 100,
                    }
                },
            )
            rows = page.get("records")
            if not isinstance(rows, list):
                raise RuntimeFailure("DSH 历史分页格式无效", "protocol_error")
            for row in rows:
                if isinstance(row, dict) and isinstance(row.get("event"), dict):
                    entries[row["event"]["seq"]] = row
            next_before = min(
                (
                    row["event"]["seq"]
                    for row in rows
                    if isinstance(row, dict) and isinstance(row.get("event"), dict)
                ),
                default=None,
            )
            if page.get("hasMore") is not True:
                return [entries[key] for key in sorted(entries)]
            if next_before is None or next_before >= before:
                raise RuntimeFailure("DSH 历史分页未前进", "protocol_error")
            before = next_before
            await asyncio.sleep(0)
        raise RuntimeFailure("历史超出当前读取上限，未截断冒充完整结果", "history_limit")
