"""Bounded same-origin management bridge for the owned original AIHOT engine."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

from core.observability import get_logger
from research_workbench_entrypoint.ai_news_manager import AiNewsManager
from research_workbench_entrypoint.ai_news_transport import AiNewsError

from .aihot_routes import AihotReader

log = get_logger(__name__)
ACTIONS = frozenset(
    {
        "source.create",
        "source.update",
        "source.detail",
        "source.list",
        "source.preview",
        "content.list",
        "content.detail",
        "content.visibility",
        "content.override",
        "runs",
        "settings",
        "models",
        "audit",
        "budget.update",
        "model.update",
        "settings.contact-qr",
        "receipt.release",
        "processing.requeue",
    }
)
LIMIT = 2 * 1024 * 1024
FeedKind = Literal["selected", "selected-full", "all", "daily", "weekly", "monthly"]
FEEDS = {
    "selected": "/feed.xml",
    "selected-full": "/feed/full.xml",
    "all": "/feed/all.xml",
    "daily": "/feed/daily.xml",
    "weekly": "/feed/weekly.xml",
    "monthly": "/feed/monthly.xml",
}
PUBLIC_URL = re.compile(r"(https?://[^\s<>\"']+)")
LOCAL_PATH = re.compile(
    r"file://[^\s<>\"')\]]+|"
    r"(?<![A-Za-z0-9:/])/(?:Users|home|private|var|tmp|Volumes)/[^\s<>\"')\]]+|"
    r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s<>\"')\]]+"
)


def redact(value, depth=0):
    """Remove backend secrets and local paths before public management projection."""
    if depth > 32:
        raise AiNewsError("ai_news_response_invalid")
    if isinstance(value, list):
        return [redact(item, depth + 1) for item in value]
    if isinstance(value, str):
        # Protect publisher URLs as complete tokens; redact local paths in diagnostics around them.
        return "".join(
            part if index % 2 else LOCAL_PATH.sub("[private path]", part)
            for index, part in enumerate(PUBLIC_URL.split(value))
        )
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        folded = key.lower().replace("_", "").replace("-", "")
        if any(
            word in folded
            for word in ("password", "secret", "token", "apikey", "authorization", "cookie")
        ):
            result[key] = "[redacted]"
        elif folded in {"datadir", "tokenfile", "projectroot", "home", "configpath", "endpoint"}:
            result[key] = "[private]"
        else:
            result[key] = redact(item, depth + 1)
    return result


class AiNewsService:
    def __init__(self, manager: AiNewsManager):
        self.manager = manager
        self.reader = AihotReader(connection=manager.connection)
        self._slots = asyncio.Semaphore(4)

    async def _request(self, path: str, body=None):
        try:
            connection = self.manager.connection()
            headers = {"Accept": "application/json", **connection.headers()}
            async with asyncio.timeout(20):
                async with (
                    self._slots,
                    httpx.AsyncClient(
                        timeout=15, follow_redirects=False, trust_env=False
                    ) as client,
                    client.stream(
                        "GET" if body is None else "POST",
                        connection.endpoint + path,
                        headers=headers,
                        **({"json": body} if body is not None else {}),
                    ) as response,
                ):
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(data) + len(chunk) > LIMIT:
                            raise AiNewsError("ai_news_response_limit")
                        data.extend(chunk)
                    if response.status_code != 200:
                        if response.status_code in {400, 403, 404, 409, 422}:
                            raise HTTPException(
                                response.status_code,
                                detail={"code": "ai_news_control_rejected"},
                            )
                        raise AiNewsError("ai_news_service_unavailable")
                    if (
                        response.headers.get("content-type", "").split(";", 1)[0]
                        != "application/json"
                    ):
                        raise AiNewsError("ai_news_response_invalid")
                    value = json.loads(data)
                    if not isinstance(value, dict):
                        raise AiNewsError("ai_news_response_invalid")
                    return redact(value)
        except (AiNewsError, httpx.HTTPError, TimeoutError, ValueError, TypeError):
            log.warning("ai_news_bridge_failed")
            raise HTTPException(
                503, detail={"code": "ai_news_not_ready", "message": "AI 资讯自主服务尚未就绪。"}
            ) from None

    async def read(self, path: str):
        if path != "/internal/rwb/status":
            raise HTTPException(400, detail={"code": "ai_news_operation_invalid"})
        return await self._request(path)

    async def feed(self, kind: FeedKind, public_origin: str) -> bytes:
        if kind not in FEEDS:
            raise HTTPException(404, detail={"code": "ai_news_feed_unknown"})
        origin = urlsplit(public_origin)
        if (
            origin.scheme not in {"http", "https"}
            or not origin.netloc
            or origin.username
            or origin.password
            or origin.query
            or origin.fragment
            or origin.path
        ):
            raise HTTPException(400, detail={"code": "ai_news_origin_invalid"})
        try:
            connection = self.manager.connection()
            async with (
                asyncio.timeout(20),
                self._slots,
                httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False) as client,
                client.stream(
                    "GET", connection.endpoint + FEEDS[kind], headers=connection.headers()
                ) as response,
            ):
                if response.status_code != 200 or response.headers.get("content-type", "").split(
                    ";", 1
                )[0] not in {"application/rss+xml", "application/xml", "text/xml"}:
                    raise AiNewsError("ai_news_feed_unavailable")
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(data) + len(chunk) > LIMIT:
                        raise AiNewsError("ai_news_feed_limit")
                    data.extend(chunk)
            if (
                b"<!DOCTYPE" in data.upper()
                or b"<!ENTITY" in data.upper()
                or b"<?xml-stylesheet" in data.lower()
            ):
                raise AiNewsError("ai_news_feed_invalid")
            text = data.decode("utf-8")
            for feed_kind, path in FEEDS.items():
                text = text.replace(
                    connection.endpoint + path,
                    public_origin + "/api/research/ai-news/feeds/" + feed_kind + ".xml",
                )
            text = text.replace(connection.endpoint + "/items/", public_origin + "/#/aihot/item/")
            text = text.replace(connection.endpoint, public_origin)
            log.info("ai_news_feed_read_completed", kind=kind)
            return text.encode("utf-8")
        except (AiNewsError, httpx.HTTPError, TimeoutError, UnicodeError):
            log.warning("ai_news_feed_failed")
            raise HTTPException(503, detail={"code": "ai_news_feed_unavailable"}) from None

    async def status(self):
        status = await asyncio.to_thread(self.manager.status)
        if status.get("state") == "running":
            try:
                status["engine"] = await self.read("/internal/rwb/status")
            except HTTPException:
                status["state"] = "degraded"
                status["code"] = "ai_news_engine_unavailable"
        return status

    async def control(self, action: str, payload: dict):
        if action not in ACTIONS or not isinstance(payload, dict):
            log.warning("ai_news_control_denied")
            raise HTTPException(403, detail={"code": "ai_news_control_denied"})
        if len(json.dumps(payload, ensure_ascii=False).encode()) > 65536:
            raise HTTPException(413, detail={"code": "ai_news_request_limit"})
        return await self._request("/internal/rwb/control", {"action": action, "input": payload})


def create_ai_news_service(project: Path, home: Path, credentials=None):
    """No I/O, credentials access, subprocesses or database connection at startup."""
    return AiNewsService(AiNewsManager(project, home, credentials))
