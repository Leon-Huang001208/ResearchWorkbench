"""Public SDK process boundary never inherits account credentials or user commands."""

import json
import subprocess
import unittest
from dataclasses import asdict
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError, Result
from app.research_web.datahub.public_worker import invoke_worker


class PublicWorkerTests(unittest.TestCase):
    def test_guest_socket_reports_eof_instead_of_looping_forever(self):
        import socket

        from app.research_web.datahub.public_worker import _BoundedPublicSocket

        first, second = socket.socketpair()
        bounded = _BoundedPublicSocket(fileno=first.detach())
        try:
            second.close()
            self.assertEqual(bounded.gettimeout(), 4)
            with self.assertRaises(ConnectionError):
                bounded.recv(1024)
        finally:
            bounded.close()
            second.close()

    def query(self):
        return BusinessQuery(
            capability="trading_calendar",
            source="baostock",
            parameters={"start_date": "2025-01-02", "end_date": "2025-01-02"},
        )

    def test_fixed_module_private_home_and_no_inherited_secrets(self):
        def run(command, **kwargs):
            self.assertEqual(
                command[1:], ["-m", "app.research_web.datahub.public_worker", "baostock"]
            )
            self.assertEqual(kwargs["cwd"], kwargs["env"]["HOME"])
            self.assertNotIn("WIND_PASSWORD", kwargs["env"])
            self.assertLessEqual(kwargs["timeout"], 12)
            payload = asdict(Result(provider_id="baostock", status="complete"))
            return SimpleNamespace(
                returncode=0, stdout=json.dumps({"ok": True, "result": payload}).encode()
            )

        with (
            patch.dict("os.environ", {"WIND_PASSWORD": "fixture-secret"}),
            patch("app.research_web.datahub.public_worker.subprocess.run", run),
        ):
            self.assertEqual(invoke_worker("baostock", self.query()).status, "complete")

    def test_timeout_and_wrong_source_fail_closed(self):
        with (
            patch(
                "app.research_web.datahub.public_worker.subprocess.run",
                side_effect=subprocess.TimeoutExpired("owned", 12),
            ),
            self.assertRaisesRegex(ProviderError, "deadline"),
        ):
            invoke_worker("baostock", self.query())
        with self.assertRaisesRegex(ProviderError, "data_operation_unsupported"):
            invoke_worker("user-command", self.query())

    def test_malformed_response_never_reaches_result(self):
        with (
            patch(
                "app.research_web.datahub.public_worker.subprocess.run",
                return_value=SimpleNamespace(returncode=0, stdout=b'{"ok":true,"result":{}}'),
            ),
            self.assertRaisesRegex(ProviderError, "vendor_schema_invalid"),
        ):
            invoke_worker("baostock", self.query())
