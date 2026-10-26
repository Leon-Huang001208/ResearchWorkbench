"""Authorization metadata checks must not rotate tokens, fetch data or echo secrets."""

import asyncio
import json
import unittest

import httpx
import pytest

from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_external import credentials, verify_quantapi_authorization

POLICY = {
    "user_type": "free",
    "user_type_cn": "免费版",
    "qps_limit": {},
    "request_data_limit": {},
    "data_volume_limit": {},
    "data_range_limit": {},
}


class SyntheticConnections:
    def __init__(self, secret):
        self.secret = secret

    def read_source_secret(self, source):
        assert source == "ext_ths"
        return self.secret


@pytest.mark.asyncio
async def test_authorization_has_total_deadline_and_disables_proxies_redirects(monkeypatch):
    original_client, original_timeout = httpx.AsyncClient, asyncio.timeout
    client_options, deadlines = [], []

    def client(**kwargs):
        client_options.append(kwargs)
        return original_client(**kwargs)

    def timeout(delay):
        deadlines.append(delay)
        return original_timeout(delay)

    monkeypatch.setattr(httpx, "AsyncClient", client)
    monkeypatch.setattr(asyncio, "timeout", timeout)
    await verify_quantapi_authorization(
        SyntheticConnections("synthetic-access"),
        transport=httpx.MockTransport(lambda request: httpx.Response(200, json=POLICY)),
    )
    assert deadlines == [12]
    assert client_options[0]["trust_env"] is False
    assert client_options[0]["follow_redirects"] is False
    assert client_options[0]["timeout"] == 8


@pytest.mark.asyncio
@pytest.mark.parametrize("both", [False, True])
async def test_access_authorization_uses_only_fixed_metadata_get(both):
    calls = []
    config = {"access_token": "synthetic-access"}
    if both:
        config["refresh_token"] = "synthetic-refresh"

    def handle(request):
        calls.append(request)
        assert request.method == "GET"
        assert (
            str(request.url)
            == "https://quantapi.51ifind.com/ds_service_basic/api/v1/get_limit_policy"
        )
        assert request.headers["access_token"] == "synthetic-access"
        assert "refresh_token" not in request.headers
        return httpx.Response(200, json=POLICY)

    result = await verify_quantapi_authorization(
        SyntheticConnections(json.dumps(config) if both else "synthetic-access"),
        transport=httpx.MockTransport(handle),
    )
    assert len(calls) == 1
    assert result["status"] == "authenticated"
    assert result["data_queries"] == 0
    assert result["data_permission_verified"] is False
    assert result["token_rotated"] is False
    assert "synthetic" not in json.dumps(result)
    assert "free" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "secret",
    [
        None,
        "",
        " ",
        "{",
        "[]",
        "{}",
        '{"access_token":123}',
        '{"refresh_token":true}',
        json.dumps({"access_token": "x" * 4097}),
        "x" * 16385,
        '{"access_token":"has space"}',
    ],
)
async def test_invalid_credentials_fail_before_network(secret):
    calls = []

    def handle(request):
        calls.append(request)
        raise AssertionError("Invalid credentials must not reach the vendor")

    with pytest.raises(ProviderError, match="^(blocked_config|vendor_auth_failed)$"):
        await verify_quantapi_authorization(
            SyntheticConnections(secret), transport=httpx.MockTransport(handle)
        )
    assert not calls


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"data": POLICY},
        {"errorcode": 0, "data": {"access_token": "synthetic-access"}},
        {**POLICY, "user_type": ""},
        {**POLICY, "qps_limit": []},
        {**POLICY, "errorcode": -1},
        {**POLICY, "qps_limit": {"message": "synthetic-access"}},
    ],
)
async def test_invalid_or_reflecting_policy_is_never_authenticated(payload):
    with pytest.raises(ProviderError, match="^vendor_auth_failed$"):
        await verify_quantapi_authorization(
            SyntheticConnections("synthetic-access"),
            transport=httpx.MockTransport(lambda request: httpx.Response(200, json=payload)),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [401, 403, 500])
async def test_vendor_rejection_never_exchanges_or_reflects(status):
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(status, text="synthetic-access synthetic-refresh")

    with pytest.raises(ProviderError, match="^vendor_auth_failed$"):
        await verify_quantapi_authorization(
            SyntheticConnections(
                json.dumps(
                    {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}
                )
            ),
            transport=httpx.MockTransport(handle),
        )
    assert len(calls) == 1 and calls[0].method == "GET"


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["redirect", "size", "timeout", "invalid_json"])
async def test_metadata_network_boundaries(failure, monkeypatch):
    def handle(request):
        if failure == "redirect":
            return httpx.Response(
                302, headers={"location": "https://example.invalid/synthetic-access"}
            )
        if failure == "timeout":
            raise httpx.ReadTimeout("synthetic-access", request=request)
        if failure == "invalid_json":
            return httpx.Response(200, text="synthetic-access{")
        return httpx.Response(200, content=b"x" * 65)

    monkeypatch.setattr("app.research_web.datahub.providers_external.MAX_RESPONSE_BYTES", 64)
    reason = {"redirect": "redirect_denied", "size": "response_size_limit"}.get(
        failure, "vendor_auth_failed"
    )
    with pytest.raises(ProviderError, match=f"^{reason}$"):
        await verify_quantapi_authorization(
            SyntheticConnections("synthetic-access"), transport=httpx.MockTransport(handle)
        )


class QuantAPIAuthorizationTests(unittest.IsolatedAsyncioTestCase):
    async def test_refresh_exchange_has_no_data_call_or_secret_in_output(self):
        class Connections:
            def read_source_secret(self, source):
                assert source == "ext_ths"
                return json.dumps({"refresh_token": "synthetic-refresh"})

        calls = []

        def handle(request):
            calls.append(request.url.path)
            self.assertEqual(request.headers["refresh_token"], "synthetic-refresh")
            return httpx.Response(
                200, json={"errorcode": 0, "data": {"access_token": "synthetic-access"}}
            )

        result = await verify_quantapi_authorization(
            Connections(), transport=httpx.MockTransport(handle)
        )
        self.assertEqual(calls, ["/api/v1/get_access_token"])
        self.assertEqual(result["data_queries"], 0)
        self.assertFalse(result["token_rotated"])
        self.assertFalse(result["data_permission_verified"])
        self.assertNotIn("synthetic", json.dumps(result))

    async def test_plain_access_token_must_be_checked_and_rejection_is_safe(self):
        class Connections:
            def read_source_secret(self, _source):
                return "synthetic-access"

        calls = []

        def handle(request):
            calls.append(request)
            return httpx.Response(401, text="synthetic-access")

        with self.assertRaisesRegex(ProviderError, "vendor_auth_failed"):
            await verify_quantapi_authorization(
                Connections(), transport=httpx.MockTransport(handle)
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].method, "GET")
        self.assertEqual(
            str(calls[0].url),
            "https://quantapi.51ifind.com/ds_service_basic/api/v1/get_limit_policy",
        )

    async def test_data_credentials_prefer_existing_access_without_exchange(self):
        class Connections:
            def read_source_secret(self, _source):
                return json.dumps(
                    {"access_token": "synthetic-access", "refresh_token": "synthetic-refresh"}
                )

        def handle(_request):
            self.fail("Existing access token must not trigger an exchange")

        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            token, sensitive = await credentials(client, "ext_ths", Connections())
        self.assertEqual(token, "synthetic-access")
        self.assertIn("synthetic-refresh", sensitive)

    async def test_rejected_refresh_does_not_echo_vendor_text(self):
        class Connections:
            def read_source_secret(self, _source):
                return json.dumps({"refresh_token": "synthetic-refresh"})

        with self.assertRaisesRegex(ProviderError, "vendor_auth_failed"):
            await verify_quantapi_authorization(
                Connections(),
                transport=httpx.MockTransport(
                    lambda request: httpx.Response(
                        200, json={"errorcode": -1, "errmsg": "synthetic-refresh", "data": {}}
                    )
                ),
            )
