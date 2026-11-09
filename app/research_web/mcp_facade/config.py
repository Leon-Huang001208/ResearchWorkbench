"""Dependency-free facade switch and fixed transport limits, shared with Doctor."""

import os
from urllib.parse import urlsplit

from ..multiuser.origin import validate_origin

REQUEST_BYTES = 64 * 1024
RESPONSE_BYTES = 256 * 1024
MATERIAL_BYTES = 4 * 1024 * 1024
PROTOCOL = "2025-11-25"
MACHINE_PATHS = frozenset(
    {
        "/mcp",
        "/authorize",
        "/token",
        "/revoke",
        "/.well-known/oauth-authorization-server",
        "/.well-known/oauth-protected-resource/mcp",
    }
)


def enabled(override: bool | None = None) -> bool:
    """Only explicit 1 enables production; tests can supply an explicit bool."""
    return override if override is not None else os.environ.get("RWB_MCP_READONLY_ENABLED") == "1"


def weknora_callback(origin: str) -> str:
    """Build the one callback allowed for an explicitly configured WeKnora host."""
    url = urlsplit(validate_origin(origin))
    if url.port in {None, 80} or origin != f"http://127.0.0.1:{url.port}":
        raise ValueError("weknora_oauth_origin_invalid")
    return origin + "/api/v1/mcp-oauth/callback"
