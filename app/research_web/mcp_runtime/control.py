"""Independent private loopback control token for the MCP runtime."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
from pathlib import Path

from app.research_web.datahub.security import (
    checked_url,
    directory,
    json_bytes,
    read_file,
    write_new,
)
from app.research_web.store import StoreError
from core.observability import get_logger

log = get_logger(__name__)
TOKEN = re.compile(r"^[A-Za-z0-9_-]{43,128}$")
CONTROL_FILE = "mcp-runtime.json"


class ControlError(RuntimeError):
    """A stable MCP private-control configuration failure."""


def _parse(raw: bytes, expected_url: str) -> dict[str, str | int]:
    try:
        value = json.loads(raw)
        if (
            not isinstance(value, dict)
            or value.get("version") != 1
            or not isinstance(value.get("token"), str)
            or TOKEN.fullmatch(value["token"]) is None
            or value.get("url") != expected_url
        ):
            raise ValueError("invalid MCP control")
        checked_url(value["url"])
        return value
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, StoreError) as exc:
        raise ControlError("mcp_control_invalid") from exc


def load_control(data_root: Path, url: str) -> dict[str, str | int]:
    """Create once or securely read the MCP runtime's dedicated control record."""
    try:
        normalized_url = checked_url(url)
        root = Path(data_root)
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        with directory(root, (".control",), create=True, private=True) as folder:
            names = os.listdir(folder)
            if CONTROL_FILE not in names:
                value = {
                    "version": 1,
                    "token": secrets.token_urlsafe(32),
                    "url": normalized_url,
                }
                try:
                    write_new(folder, CONTROL_FILE, json_bytes(value))
                except StoreError:
                    if CONTROL_FILE not in os.listdir(folder):
                        raise
            raw = read_file(folder, CONTROL_FILE, private=True, limit=4096)
        return _parse(raw, normalized_url)
    except ControlError:
        raise
    except (OSError, StoreError) as exc:
        log.warning("mcp_control_load_failed", error_type=type(exc).__name__)
        raise ControlError("mcp_control_unavailable") from exc


def authenticate(control: dict[str, object], presented: object) -> bool:
    """Compare fixed-size token digests so malformed values also take a constant-time path."""
    expected = control.get("token") if isinstance(control, dict) else None
    expected_text = expected if isinstance(expected, str) else "invalid-control-token"
    presented_text = presented if isinstance(presented, str) and len(presented) <= 512 else ""
    expected_digest = hashlib.sha256(expected_text.encode("utf-8")).digest()
    presented_digest = hashlib.sha256(presented_text.encode("utf-8")).digest()
    return (
        isinstance(expected, str)
        and isinstance(presented, str)
        and hmac.compare_digest(expected_digest, presented_digest)
    )
