"""Fail-closed execution profile for private, authenticated user backends."""

from __future__ import annotations

import hmac
import json
import os
import stat
from pathlib import Path

from starlette.responses import JSONResponse

from core.observability import get_logger

from .mcp_registry.service import RegistryError
from .store import StoreError

log = get_logger(__name__)
GATEWAY_HEADER = "X-RWB-Tenant-Gateway-Key"
_CALLBACKS = frozenset(
    {
        "/api/research/internal/data/business-query",
        "/api/research/internal/data/skill-preflight",
        "/api/research/internal/data/research-quality",
        "/api/research/internal/data/research-source",
        "/api/research/internal/data/research-source/cancel",
        "/api/research/internal/data/cancel",
        "/api/research/internal/data/model-connection",
        "/api/research/internal/data/document-operation",
    }
)
_BLOCKED = (
    "/api/research/ai-news",
    "/api/research/aihot",
    "/api/research/runtime/tabbit",
    "/api/research/local-integrations",
    "/api/research/integrations",
    "/api/research/mcp",
    "/api/research/automations",
    "/api/research/automation-runs",
    "/api/research/delivery-channels",
    "/api/research/data/connections",
    "/api/research/hot",
    "/api/research/operations",
    "/api/research/resident",
    "/api/research/report-projects",
    "/api/research/report-runs",
    "/api/research/report-workflows",
)


def enabled() -> bool:
    """Only a manager-supplied explicit profile activates this boundary."""
    return os.environ.get("RWB_TENANT_MODE") == "1"


def enforce_document_mode(mode: str) -> None:
    """Guard the execution entry point, including independently signed callbacks."""
    if enabled() and mode != "file":
        log.warning("tenant_native_document_denied")
        raise StoreError("服务器模式只允许文件式文档操作", "server_capability_disabled", 403)


def enforce_model_configuration(value: object) -> None:
    """The initial server profile never accepts user-selected upstream endpoints."""
    if (
        not isinstance(value, dict)
        or value.get("provider") != "deepseek-official"
        or any(key in value for key in ("base_url", "protocol", "credential_mode"))
    ):
        raise StoreError("服务器模式仅允许官方模型连接", "server_capability_disabled", 403)


def _gateway_key() -> str:
    path = Path(os.environ.get("RWB_TENANT_GATEWAY_KEY_FILE", ""))
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("gateway_key_unavailable")
    for parent in path.parents:
        if parent.is_symlink():
            raise ValueError("gateway_key_unavailable")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        value = os.fstat(descriptor)
        if (
            not stat.S_ISREG(value.st_mode)
            or value.st_uid != os.getuid()
            or value.st_nlink != 1
            or stat.S_IMODE(value.st_mode) != 0o600
        ):
            raise ValueError("gateway_key_unavailable")
        raw = os.read(descriptor, 129)
        if not 32 <= len(raw) <= 128:
            raise ValueError("gateway_key_unavailable")
        return raw.decode("ascii")
    finally:
        os.close(descriptor)


def _denied(code="server_capability_disabled") -> JSONResponse:
    log.warning("tenant_request_denied", code=code)
    return JSONResponse(
        {"error": {"code": code, "message": "服务器模式不允许此操作"}}, status_code=403
    )


async def check_request(request) -> JSONResponse | None:
    """Authenticate every backend route before product handlers see the request."""
    if not enabled():
        return None
    path = request.url.path
    if path.startswith("/api/research/internal/"):
        if (
            path
            in {
                "/api/research/internal/plugin-runtime/freeze",
                "/api/research/internal/plugin-runtime/unfreeze",
                "/api/research/internal/plugin-runtime/commit",
                "/api/research/internal/plugin-runtime/rollback",
            }
            and request.method == "POST"
        ):
            try:
                if not hmac.compare_digest(request.headers.get(GATEWAY_HEADER, ""), _gateway_key()):
                    return _denied("tenant_backend_auth_denied")
            except (OSError, ValueError, UnicodeError, TypeError):
                return _denied("tenant_backend_auth_denied")
            # Fixed router verifies one-use path/body/actor/generation proof.
            return None
        if path == "/api/research/internal/mcp/tools/call" and request.method == "POST":
            try:
                request.app.state.research.mcp_runtime.authenticate_internal(
                    request.headers.get("X-Research-MCP-Key")
                )
            except StoreError:
                return _denied("tenant_backend_auth_denied")
            except (RegistryError, ValueError, RuntimeError, AttributeError, TypeError) as exc:
                log.warning("tenant_mcp_callback_denied", error_type=type(exc).__name__)
                return _denied("tenant_backend_auth_denied")
            return None
        if path not in _CALLBACKS:
            return _denied()
        if not request.app.state.research.datahub.authenticate(
            request.headers.get("X-Research-Data-Key")
        ):
            return _denied("tenant_backend_auth_denied")
        if path.endswith("/skill-preflight"):
            try:
                body = await request.json()
                if body.get("native_name") is not None:
                    names = {
                        row["native_name"]
                        for row in request.app.state.research.capabilities.list()["items"]
                        if row["builtin"] and row["enabled"]
                    }
                    if body[
                        "native_name"
                    ] not in names and not request.app.state.research.plugins.native_authorized(
                        body["native_name"], body.get("session_id")
                    ):
                        return _denied()
            except (StoreError, ValueError, TypeError, KeyError, AttributeError):
                return _denied()
        return None
    try:
        provided = request.headers.get(GATEWAY_HEADER, "")
        if len(provided) > 128 or not hmac.compare_digest(provided, _gateway_key()):
            return _denied("tenant_backend_auth_denied")
    except (OSError, ValueError, UnicodeError, TypeError):
        return _denied("tenant_backend_auth_denied")
    if any(path == item or path.startswith(item + "/") for item in _BLOCKED):
        return _denied()
    if any(
        part in {"tabbit-access", "tabbit-tabs", "automation-drafts"} for part in path.split("/")
    ):
        return _denied()
    if path.startswith("/api/research/data/") and (
        "/configuration" in path or "/probes" in path or "/migrations" in path
    ):
        return _denied()
    if path.startswith("/api/research/capabilities") and request.method not in {"GET", "HEAD"}:
        return _denied()
    if (path == "/api/research/runtime/model" and request.method == "PUT") or (
        path.startswith("/api/research/model-profiles")
        and request.method in {"POST", "PUT"}
        and not path.endswith("/activate")
    ):
        try:
            enforce_model_configuration(await request.json())
        except (StoreError, ValueError, UnicodeError, json.JSONDecodeError):
            return _denied()
    return None
