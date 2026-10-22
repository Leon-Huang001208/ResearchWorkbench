"""Explicit authorization exchange must not rotate tokens, fetch data or echo secrets."""

import json
import unittest

import httpx

from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_external import verify_quantapi_authorization


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

    async def test_plain_access_token_cannot_be_misreported_as_verified(self):
        class Connections:
            def read_source_secret(self, _source):
                return "synthetic-access"

        with self.assertRaisesRegex(ProviderError, "refresh_token_required"):
            await verify_quantapi_authorization(Connections())

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
