"""Bounded, conditional HTTP reads for MCP Registry v0.1."""

from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import quote

import httpx

MAX_REGISTRY_RESPONSE_BYTES = 2 * 1024 * 1024
TOTAL_REGISTRY_TIMEOUT_SECONDS = 30.0


class SyncError(RuntimeError):
    def __init__(self, code: str, status: int = 502):
        super().__init__(code)
        self.code = code
        self.status = status


class RegistryHTTPClient:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._owned = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5),
            follow_redirects=False,
            headers={"Accept": "application/json", "User-Agent": "ResearchWorkbench/Registry"},
        )
        self.total_timeout = TOTAL_REGISTRY_TIMEOUT_SECONDS

    async def close(self) -> None:
        if self._owned:
            await self.client.aclose()

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        etag: str | None = None,
        authorization: str | None = None,
    ) -> tuple[int, dict[str, Any] | None, str | None]:
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        if authorization:
            headers["Authorization"] = authorization
        try:
            async with asyncio.timeout(self.total_timeout):
                async with self.client.stream(
                    "GET", url, params=params, headers=headers
                ) as response:
                    if response.status_code == 304:
                        return 304, None, etag
                    if response.status_code != 200:
                        raise SyncError("registry_http_error", 502)
                    chunks = []
                    size = 0
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > MAX_REGISTRY_RESPONSE_BYTES:
                            raise SyncError("registry_response_too_large", 502)
                        chunks.append(chunk)
                    try:
                        payload = json.loads(b"".join(chunks))
                    except (UnicodeDecodeError, ValueError) as exc:
                        raise SyncError("registry_invalid_response", 502) from exc
                    if not isinstance(payload, dict):
                        raise SyncError("registry_invalid_response", 502)
                    return 200, payload, response.headers.get("ETag")
        except TimeoutError as exc:
            raise SyncError("registry_timeout", 504) from exc
        except httpx.TimeoutException as exc:
            raise SyncError("registry_timeout", 504) from exc
        except httpx.HTTPError as exc:
            raise SyncError("registry_network_error", 502) from exc

    async def page(
        self,
        base_url: str,
        *,
        cursor: str | None,
        search: str | None,
        limit: int,
        etag: str | None,
        authorization: str | None,
    ):
        params: dict[str, Any] = {"limit": limit}
        if cursor is not None:
            params["cursor"] = cursor
        if search is not None:
            params["search"] = search
        return await self._get(
            f"{base_url}/v0.1/servers",
            params=params,
            etag=etag,
            authorization=authorization,
        )

    async def detail(
        self,
        base_url: str,
        server_name: str,
        version: str,
        *,
        etag: str | None,
        authorization: str | None,
    ):
        encoded_name = quote(server_name, safe="")
        encoded_version = quote(version, safe="")
        return await self._get(
            f"{base_url}/v0.1/servers/{encoded_name}/versions/{encoded_version}",
            etag=etag,
            authorization=authorization,
        )
