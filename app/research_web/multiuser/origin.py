"""One stdlib-only origin contract shared by CLI preflight and HTTP boundary."""

import re
from urllib.parse import urlsplit


def validate_origin(origin: str) -> str:
    """Accept one exact HTTPS tailnet origin or a loopback development origin."""
    try:
        parsed = urlsplit(origin)
        port = parsed.port
        local = parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}
        private = (
            parsed.scheme == "https"
            and port in {None, 443}
            and re.fullmatch(
                r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.tail[a-z0-9]+\.ts\.net",
                parsed.hostname or "",
            )
        )
        if (
            parsed.username
            or parsed.password
            or parsed.path
            or parsed.query
            or parsed.fragment
            or not parsed.hostname
            or origin.endswith("/")
            or port == 0
            or parsed.netloc != parsed.netloc.lower()
            or not (local or private)
        ):
            raise ValueError("invalid origin")
    except ValueError as exc:
        raise ValueError("server_origin_invalid") from exc
    return origin
