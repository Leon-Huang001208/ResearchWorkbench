"""Dependency-free facade switch and fixed transport limits, shared with Doctor."""

import os

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
