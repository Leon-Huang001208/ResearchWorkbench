"""Private loopback AI news connection; never discovers a public fallback."""

from __future__ import annotations

import json
import logging
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

log = logging.getLogger(__name__)


class AiNewsError(RuntimeError):
    """Stable code only, without subprocess output or private configuration."""


def safe_path(path: Path) -> None:
    for part in (path, *path.parents):
        if part.is_symlink():
            raise AiNewsError("ai_news_storage_unsafe")


def private_bytes(path: Path, limit: int = 65536) -> bytes:
    safe_path(path)
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, "rb") as stream:
            info = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_size > limit
            ):
                raise AiNewsError("ai_news_storage_unsafe")
            return stream.read(limit + 1)
    except OSError:
        log.warning("ai_news_private_read_failed")
        raise AiNewsError("ai_news_not_configured") from None


def private_json(path: Path) -> dict:
    try:
        result = json.loads(private_bytes(path))
        if not isinstance(result, dict):
            raise AiNewsError("ai_news_config_invalid")
        return result
    except (ValueError, UnicodeError):
        log.warning("ai_news_config_invalid")
        raise AiNewsError("ai_news_config_invalid") from None


class AiNewsConnection:
    """Host-only endpoint and token; browser input cannot select a destination."""

    def __init__(self, endpoint: str, token_file: Path):
        parsed = urlsplit(endpoint)
        try:
            valid = (
                parsed.scheme == "http"
                and parsed.hostname == "127.0.0.1"
                and parsed.netloc == f"127.0.0.1:{parsed.port}"
                and parsed.port
                and not parsed.path
                and not parsed.query
                and not parsed.fragment
            )
        except ValueError:
            valid = False
        if not valid or not token_file.is_absolute():
            raise AiNewsError("ai_news_endpoint_invalid")
        self.endpoint = endpoint
        self.token_file = token_file

    def headers(self) -> dict[str, str]:
        try:
            token = private_bytes(self.token_file, 4096).decode("ascii").strip()
        except UnicodeError:
            raise AiNewsError("ai_news_token_invalid") from None
        if len(token) < 32 or any(c not in "0123456789abcdef" for c in token):
            raise AiNewsError("ai_news_token_invalid")
        return {"x-rwb-ai-news-token": token}
