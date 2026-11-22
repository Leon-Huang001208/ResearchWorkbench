"""Bounded images from the owned AIHOT engine; browser credentials stay local."""

import asyncio
import hashlib
import re
from collections import OrderedDict
from urllib.parse import parse_qs, urlsplit

import httpx
from fastapi import HTTPException
from fastapi.responses import Response

from core.observability import get_logger
from research_workbench_entrypoint.ai_news_transport import AiNewsConnection, AiNewsError

log = get_logger(__name__)
IMAGE_LIMIT = 4 * 1024 * 1024


class AihotMedia:
    """Project upstream signed image paths into an opaque same-origin allowlist."""

    def __init__(self, connection=None):
        self.connection = connection
        self.urls: OrderedDict[str, str] = OrderedDict()
        self.slots = asyncio.Semaphore(4)

    def _image(self, value: str) -> str | None:
        if self.connection is None or not isinstance(value, str) or len(value) > 8192:
            return None
        try:
            connection: AiNewsConnection = self.connection()
        except AiNewsError:
            return None
        parsed = urlsplit(value)
        if (
            parsed.path != "/api/img-proxy"
            or (parsed.scheme and parsed.scheme != "http")
            or parsed.fragment
            or parsed.username
            or parsed.password
            or (parsed.netloc and value.split("/api/", 1)[0] != connection.endpoint)
        ):
            return None
        query = parse_qs(parsed.query)
        if not all(len(query.get(k, [])) == 1 for k in ("u", "mode", "exp", "sig")):
            return None
        if not re.fullmatch(r"[a-f0-9]{16,128}", query["sig"][0]) or not query["exp"][0].isdigit():
            return None
        url = connection.endpoint + parsed.path + "?" + parsed.query
        key = hashlib.sha256(url.encode()).hexdigest()
        self.urls[key] = url
        self.urls.move_to_end(key)
        while len(self.urls) > 4096:
            self.urls.popitem(last=False)
        return "/api/research/aihot/media/" + key

    def project(self, value):
        if isinstance(value, list):
            return [self.project(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in {"sourceIconUrl", "iconUrl", "avatarUrl", "fullUrl", "poster"} or (
                key == "url" and isinstance(item, str) and "/api/img-proxy?" in item
            ):
                result[key] = self._image(item)
            elif key in {"srcSet", "iconSrcSet", "sourceIconSrcSet", "avatarSrcSet"}:
                choices = []
                if isinstance(item, str):
                    for choice in item.split(","):
                        parts = choice.strip().rsplit(" ", 1)
                        if len(parts) == 2 and re.fullmatch(r"\d+w", parts[1]):
                            url = self._image(parts[0])
                            if url:
                                choices.append(url + " " + parts[1])
                result[key] = ", ".join(choices) or None
            else:
                result[key] = self.project(item)
        return result

    async def read(self, key: str) -> Response:
        url = self.urls.get(key)
        if url is None:
            raise HTTPException(404, detail={"code": "aihot_image_not_found"})
        self.urls.move_to_end(key)
        try:
            if self.connection is None:
                raise AiNewsError("ai_news_not_configured")
            connection = self.connection()
            if not url.startswith(connection.endpoint + "/api/img-proxy?"):
                raise AiNewsError("ai_news_endpoint_changed")
            headers = {"User-Agent": "ResearchWorkbench-AIHOT/1.0", **connection.headers()}
            async with asyncio.timeout(12):
                async with (
                    self.slots,
                    httpx.AsyncClient(
                        timeout=12, follow_redirects=False, trust_env=False
                    ) as client,
                    client.stream("GET", url, headers=headers) as response,
                ):
                    mime = response.headers.get("content-type", "").split(";", 1)[0]
                    if response.status_code != 200 or mime not in {
                        "image/png",
                        "image/jpeg",
                        "image/webp",
                        "image/gif",
                        "image/avif",
                        "image/x-icon",
                        "image/vnd.microsoft.icon",
                    }:
                        raise ValueError("image unavailable")
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        if len(content) + len(chunk) > IMAGE_LIMIT:
                            raise ValueError("image too large")
                        content.extend(chunk)
                    log.info("aihot_image_read_completed")
                    return Response(
                        bytes(content),
                        media_type=mime,
                        headers={
                            "Cache-Control": "private, max-age=300",
                            "X-Content-Type-Options": "nosniff",
                        },
                    )
        except (httpx.HTTPError, TimeoutError, ValueError, AiNewsError) as exc:
            log.warning("aihot_image_read_failed", code="image_unavailable")
            raise HTTPException(502, detail={"code": "aihot_image_unavailable"}) from exc
