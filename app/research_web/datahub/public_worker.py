"""Tokenless public SDK isolation with a bounded, owned child process.

This is a lifetime boundary, not an OS sandbox. It is never used to execute
plugin code, credentialed SDKs or browser-selected commands.
"""

from __future__ import annotations

import base64
import contextlib
import json
import os
import socket
import subprocess
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
DEADLINE = 12
SOURCES = frozenset({"baostock", "akshare"})


class _BoundedPublicSocket(socket.socket):
    """Owned child only: finite socket waits and explicit EOF for guest BaoStock."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settimeout(4)

    def recv(self, *args, **kwargs):
        value = super().recv(*args, **kwargs)
        if not value:
            raise ConnectionError("public_vendor_closed_connection")
        return value


SAFE_CODES = frozenset(
    {
        "deadline",
        "vendor_unreachable",
        "missing_dependency",
        "vendor_schema_invalid",
        "data_not_equivalent",
        "data_operation_unsupported",
        "invalid_date_range",
        "invalid_asset",
        "invalid_frequency",
        "invalid_adjustment",
        "row_limit",
    }
)


def invoke_worker(source: str, query: BusinessQuery) -> Result:
    if source not in SOURCES or query.source != source:
        raise ProviderError("data_operation_unsupported")
    with tempfile.TemporaryDirectory(prefix="rwb-public-sdk-") as private:
        environment = {
            "PATH": os.pathsep.join((str(Path(sys.executable).parent), "/usr/bin", "/bin")),
            "HOME": private,
            "TMPDIR": private,
            "PYTHONUTF8": "1",
            "PYTHONUNBUFFERED": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONPATH": str(Path(__file__).resolve().parents[3]),
            "RESEARCH_RUN_MODE": "web-prod",
            "RESEARCH_PROJECT_ROOT": private,
        }
        try:
            response = subprocess.run(
                [sys.executable, "-m", "app.research_web.datahub.public_worker", source],
                input=query.model_dump_json().encode(),
                capture_output=True,
                timeout=DEADLINE,
                cwd=private,
                env=environment,
                check=False,
            )
        except subprocess.TimeoutExpired:
            # subprocess.run kills and waits for this exact owned child.
            log.warning("datahub_public_worker_deadline", source=source)
            raise ProviderError("deadline") from None
        except OSError:
            log.warning("datahub_public_worker_start_failed", source=source)
            raise ProviderError("vendor_unreachable") from None
    if response.returncode != 0 or len(response.stdout) > MAX_QUERY_BYTES * 2:
        raise ProviderError("vendor_schema_invalid")
    try:
        value = json.loads(response.stdout)
        if not value.get("ok"):
            code = value.get("code")
            raise ProviderError(code if code in SAFE_CODES else "vendor_unreachable")
        payload = value["result"]
        if set(payload) != set(Result.__dataclass_fields__):
            raise ValueError("result_schema")
        if not isinstance(payload["rows"], list) or len(payload["rows"]) > MAX_ROWS:
            raise ValueError("row_limit")
        payload["raw"] = [base64.b64decode(part, validate=True) for part in payload["raw"]]
        if sum(len(part) for part in payload["raw"]) > MAX_QUERY_BYTES:
            raise ValueError("raw_limit")
        if payload["provider_id"] != source or payload["status"] not in {
            "complete",
            "empty",
            "partial",
            "failed",
            "snapshot",
        }:
            raise ValueError("provider_identity")
        return Result(**payload)
    except ProviderError:
        raise
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise ProviderError("vendor_schema_invalid") from None


def main() -> int:
    source = sys.argv[1] if len(sys.argv) == 2 else ""
    try:
        if source not in SOURCES:
            raise ProviderError("data_operation_unsupported")
        content = sys.stdin.buffer.read(32769)
        if len(content) > 32768:
            raise ProviderError("vendor_schema_invalid")
        query = BusinessQuery.model_validate_json(content)
        if query.source != source:
            raise ProviderError("data_operation_unsupported")
        if source == "baostock":
            vars(socket)["socket"] = _BoundedPublicSocket
        if source == "akshare":
            # The SDK omits timeouts on several requests. This process contains
            # only one fixed public query, so the clamp cannot affect the Host.
            import requests

            request = requests.sessions.Session.request

            def bounded_request(session, method, url, **kwargs):
                timeout = kwargs.get("timeout")
                if isinstance(timeout, tuple):
                    kwargs["timeout"] = tuple(
                        min(value, 4) if isinstance(value, (int, float)) and value > 0 else 4
                        for value in timeout
                    )
                else:
                    kwargs["timeout"] = (
                        min(timeout, 4) if isinstance(timeout, (int, float)) and timeout > 0 else 4
                    )
                return request(session, method, url, **kwargs)

            requests.sessions.Session.request = bounded_request
        with contextlib.redirect_stdout(sys.stderr):
            if source == "baostock":
                from .providers_baostock import invoke
            else:
                from .providers_akshare import invoke_public as invoke

            result = invoke(query)
        payload = asdict(result)
        payload["raw"] = [base64.b64encode(part).decode() for part in result.raw]
        encoded = json.dumps({"ok": True, "result": payload}, ensure_ascii=False, allow_nan=False)
        if len(encoded.encode()) > MAX_QUERY_BYTES * 2:
            raise ProviderError("vendor_schema_invalid")
        print(encoded)
    except Exception as exc:  # noqa: BLE001 - never relay SDK exception text or environment.
        code = (
            str(exc)
            if isinstance(exc, ProviderError) and str(exc) in SAFE_CODES
            else "vendor_unreachable"
        )
        print(json.dumps({"ok": False, "code": code}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
