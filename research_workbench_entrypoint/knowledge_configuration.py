"""Stdlib-only non-secret knowledge origin, shared by dispatch and cold Doctor."""

from __future__ import annotations

import ipaddress
import logging
import os
from urllib.parse import urlsplit

log = logging.getLogger(__name__)


def knowledge_origin() -> str | None:
    """Read one non-secret operator origin, never a broad environment prefix."""
    value = os.environ.get("RESEARCH_WEKNORA_ORIGIN", "")
    if not value:
        return None
    try:
        parsed = urlsplit(value)
        if (
            len(value) > 2048
            or any(ord(char) < 33 or ord(char) > 126 for char in value)
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path not in {"", "/"}
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("origin")
        _port = parsed.port
        if parsed.scheme == "http":
            if (
                parsed.hostname != "localhost"
                and not ipaddress.ip_address(parsed.hostname).is_loopback
            ):
                raise ValueError("transport")
        elif parsed.scheme != "https":
            raise ValueError("transport")
        return value.rstrip("/")
    except (ValueError, TypeError):
        log.warning("multiuser_knowledge_origin_invalid")
        raise ValueError("knowledge_origin_invalid") from None
