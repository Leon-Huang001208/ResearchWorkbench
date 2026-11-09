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
    url = urlsplit(origin)
    port = url.port
    if url.scheme == "https":
        host = validate_origin(f"https://{url.hostname}")
        expected = host + (f":{port}" if port not in (None, 443) else "")
        if port != 0 and origin == expected:
            return origin + "/api/v1/mcp-oauth/callback"
    elif port not in (None, 0, 80) and origin == f"http://127.0.0.1:{port}":
        return origin + "/api/v1/mcp-oauth/callback"
    raise ValueError("weknora_oauth_origin_invalid")


def validate_weknora_gateway(issuer: str, callback_origin: str, port: int) -> None:
    weknora_callback(callback_origin)
    if issuer == callback_origin:
        raise ValueError("weknora_oauth_origin_conflict")
    if issuer.startswith("https://"):
        hostname = urlsplit(validate_origin(issuer)).hostname
        if issuer != f"https://{hostname}":
            raise ValueError("weknora_oauth_issuer_invalid")
        if urlsplit(callback_origin).hostname == hostname:
            raise ValueError("weknora_oauth_cookie_host_conflict")
    elif (
        port == 80 or issuer != f"http://127.0.0.1:{port}" or callback_origin.startswith("https://")
    ):
        raise ValueError("weknora_oauth_requires_loopback_gateway")


def resident_execution(config: dict, *, mcp_enabled: bool) -> tuple[bool, str | None]:
    service_only = config.get("service_only", False)
    if type(service_only) is not bool:
        raise ValueError("resident_service_only_invalid")
    oauth_origin = config.get("weknora_oauth_origin")
    if "weknora_oauth_origin" in config:
        if not service_only or not mcp_enabled:
            raise ValueError("weknora_oauth_requires_service_only_mcp")
        if not isinstance(oauth_origin, str):
            raise ValueError("weknora_oauth_origin_invalid")
        try:
            validate_weknora_gateway(config["origin"], oauth_origin, config["port"])
        except (KeyError, ValueError, TypeError) as exc:
            raise ValueError("weknora_oauth_origin_invalid") from exc
    return service_only, oauth_origin
