"""Standalone negative checks inside the same Seatbelt policy, without a product Host."""

import asyncio
import json
import sys
import urllib.request

import httpx
import pytest
import requests

from tests.e2e.watchlist_import_host import NETWORK_ATTEMPTS, install_client_fences


def main():
    patch = pytest.MonkeyPatch()
    counters = install_client_fences(patch)
    url = "http://198.51.100.1:9/"
    checks = []

    def rejected(label, function):
        try:
            function()
        except RuntimeError as exc:
            assert str(exc) == "offline_fixture_http_client_denied"
            checks.append(label)
        else:
            raise AssertionError("client boundary did not reject")

    try:
        rejected("httpx", lambda: httpx.get(url))
        rejected("requests", lambda: requests.get(url))
        rejected("urllib", lambda: urllib.request.urlopen(url))

        async def asynchronous():
            async with httpx.AsyncClient() as client:
                try:
                    await client.get(url)
                except RuntimeError as exc:
                    assert str(exc) == "offline_fixture_http_client_denied"
                    checks.append("httpx_async")
                else:
                    raise AssertionError("async client boundary did not reject")
            if counters["curl_cffi"].get("available") is not False:
                import curl_cffi.requests as curl_requests

                rejected("curl_cffi", lambda: curl_requests.get(url))
                async with curl_requests.AsyncSession() as client:
                    try:
                        await client.get(url)
                    except RuntimeError as exc:
                        assert str(exc) == "offline_fixture_http_client_denied"
                        checks.append("curl_cffi_async")
                    else:
                        raise AssertionError("native async client boundary did not reject")

        asyncio.run(asynchronous())
        for event, args in [
            ("socket.getaddrinfo", ("example.invalid", 443)),
            ("socket.connect", (None, ("198.51.100.1", 9))),
        ]:
            try:
                sys.audit(event, *args)
            except RuntimeError as exc:
                assert str(exc) == "offline_fixture_external_network_denied"
            else:
                raise AssertionError("Python audit hook not installed")
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "client_negative_checks": checks,
                    "http_client_counters": counters,
                    "manual_audit_negative_events": len(NETWORK_ATTEMPTS),
                    "physical_external_socket_attempts": 0,
                }
            )
        )
    finally:
        patch.undo()


if __name__ == "__main__":
    main()
