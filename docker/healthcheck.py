"""Bounded authenticated container probes; standalone checks never write state."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from app.research_web.runtime_state import runtime_state_directory
from app.research_web.service_manager import ServiceManagerError, WebServiceManager
from core.observability import get_logger

log = get_logger(__name__)
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class ContainerHealth(WebServiceManager):
    """Reuse Native auth/session validation, with no Native lifecycle operations.

    A launch token is supplied only by the supervisor. Without one, inherited
    session validation cannot exchange credentials or write an auth record.
    Network I/O has one total deadline, including headers and streamed bodies.
    """

    def __init__(self, *, timeout: float, launch_token: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.deadline = time.monotonic() + timeout
        self.launch_token = launch_token

    def _runtime_launch_token(self):
        return self.launch_token

    def _request(self, port, method, path, payload=None, headers=None):
        async def request():
            async with httpx.AsyncClient(trust_env=False, follow_redirects=False) as client:
                # HTTP debug/INFO logs include URLs and headers. These private
                # synchronous probes expose only our stable status event.
                network_logs = [logging.getLogger(name) for name in logging.Logger.manager.loggerDict
                                if name == "httpx" or name.startswith("httpcore")]
                previous = [(logger, logger.disabled) for logger in network_logs]
                for logger, _ in previous:
                    logger.disabled = True
                try:
                    async with client.stream(
                        method, f"http://127.0.0.1:{port}{path}", json=payload, headers=headers
                    ) as response:
                        chunks = bytearray()
                        async for chunk in response.aiter_bytes():
                            chunks.extend(chunk)
                            if len(chunks) > MAX_RESPONSE_BYTES:
                                raise ServiceManagerError("probe_response_limit")
                        return response.status_code, response.headers, bytes(chunks)
                finally:
                    for logger, disabled in previous:
                        logger.disabled = disabled

        async def bounded():
            return await asyncio.wait_for(request(), max(.001, self.deadline - time.monotonic()))

        try:
            if time.monotonic() >= self.deadline:
                raise ServiceManagerError("probe_timeout")
            return asyncio.run(bounded())
        except (OSError, ValueError, httpx.HTTPError, TimeoutError) as exc:
            raise ServiceManagerError("probe_failed") from exc

    def _json_request(self, port, method, path, payload=None, extra_headers=None):
        status, _, raw = self._request(port, method, path, payload, extra_headers)
        try:
            value = json.loads(raw)
            if not 200 <= status < 300 or not isinstance(value, dict):
                raise ValueError("invalid response")
            return value
        except (ValueError, UnicodeError) as exc:
            raise ServiceManagerError("probe_invalid_response") from exc

    def _exchange_runtime_cookie(self, token):
        # Same token exchange contract as Native, using this probe's total budget.
        try:
            status, headers, _ = self._request(self.runtime_port, "GET", f"/?token={token}")
            cookie = headers.get("Set-Cookie", "").split(";", 1)[0]
            if (
                status == 303 and cookie.startswith("dsh-auth-")
                and "\r" not in cookie and "\n" not in cookie and len(cookie) <= 4096
            ):
                return cookie
        except ServiceManagerError:
            return None
        return None


def check(state_root: Path, data_root: Path, runtime_port=3081, web_port=8088, *, timeout=3.0):
    """Return zero only for authenticated DSH sessions and a connected Web Host."""
    try:
        with runtime_state_directory(state_root):
            probe = ContainerHealth(
                timeout=timeout, data_root=data_root, runtime_state_root=state_root,
                runtime_port=runtime_port, web_port=web_port,
            )
            if probe._runtime_healthy() and probe._web_healthy():
                return 0
    except (OSError, ValueError, RuntimeError):
        pass  # CLI exposes only a stable failure code, never auth/path/response data.
    log.warning("container_health", role="stack", state="unhealthy", code="health_failed")
    return 1


def main():
    return check(
        Path(os.environ.get("RWB_RUNTIME_STATE", "/state")),
        Path(os.environ.get("RWB_DATA_ROOT", "/data/research-web")),
    )


if __name__ == "__main__":
    raise SystemExit(main())
