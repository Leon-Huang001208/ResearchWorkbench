"""Operator-owned upstream origin validation without credentials or network access."""

import ipaddress
from urllib.parse import urlsplit

from core.observability import get_logger

from ..store import StoreError

log = get_logger(__name__)


def checked_origin(value: str) -> str:
    try:
        parsed = urlsplit(value)
        if (
            not isinstance(value, str)
            or len(value) > 2048
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
    except (ValueError, TypeError, AttributeError):
        log.warning("knowledge_origin_invalid")
        raise StoreError("资料服务地址配置无效", "knowledge_origin_invalid", 422) from None
