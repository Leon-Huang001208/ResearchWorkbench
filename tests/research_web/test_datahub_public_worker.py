"""Public SDK process boundary never inherits account credentials or user commands."""

import json
import subprocess
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError, Result
from app.research_web.datahub.public_worker import invoke_worker


class PublicWorkerTests(unittest.TestCase):
    def test_actual_child_ignores_system_and_explicit_proxies_without_changing_host(self):
        """Real requests settings must be direct in the owned child, even on macOS."""
        import requests

        parent_request = requests.sessions.Session.request
        for explicit in (False, True):
            with self.subTest(explicit_proxy=explicit):
                bootstrap = f"""
import sys, types, requests, pandas as pd
requests.sessions.get_environ_proxies = lambda *a, **kw: {{'https': 'http://fixture.invalid:9'}}
netrc_calls = []
def no_netrc(*a, **kw): netrc_calls.append(True); return None
requests.sessions.get_netrc_auth = no_netrc
def send(session, request, **kwargs):
    assert kwargs['proxies'] == {{}}, 'proxy selected for anonymous SDK'
    assert session.trust_env is False, 'system proxy policy inherited'
    assert not netrc_calls, 'anonymous worker must not read netrc'
    assert kwargs['timeout'] == 4
    response = requests.Response(); response.status_code = 200; response._content = b'{{}}'
    return response
requests.sessions.Session.send = send
ak = types.ModuleType('akshare')
def fetch(**kwargs):
    options = {{'proxies': {{'https': 'http://explicit.invalid:9'}}}} if {explicit!r} else {{}}
    requests.get('https://push2his.eastmoney.com/api/qt/stock/fflow/daykline/get', **options)
    return pd.DataFrame([{{'日期':'2026-06-30','主力净流入-净额':0,
        '超大单净流入-净额':1,'大单净流入-净额':-1,
        '中单净流入-净额':2,'小单净流入-净额':-2}}])
ak.stock_individual_fund_flow = fetch
sys.modules['akshare'] = ak
from app.research_web.datahub import providers_akshare
def no_guest(query): raise AssertionError('proxy defect must not be hidden by guest fallback')
providers_akshare._fund_flow_guest = no_guest
sys.argv = ['offline-public-worker', 'akshare']
from app.research_web.datahub.public_worker import main
raise SystemExit(main())
"""
                original = subprocess.run

                def run(command, _original=original, _bootstrap=bootstrap, **kwargs):
                    return _original([command[0], "-c", _bootstrap], **kwargs)

                query = BusinessQuery(
                    capability="market_activity",
                    source="akshare",
                    parameters={"asset": "600600.SH", "dataset": "fund_flow"},
                )
                with patch("app.research_web.datahub.public_worker.subprocess.run", run):
                    result = invoke_worker("akshare", query)
                self.assertEqual(result.rows[0]["main_net"], 0)
                self.assertIs(requests.sessions.Session.request, parent_request)

    def test_actual_akshare_child_serializes_offline_guest_result(self):
        """Run real child/codec; SDK and HTTP alone are controlled offline fixtures."""
        source = (Path(__file__).parent / "fixtures/fund_flow_guest.json").read_bytes()
        bootstrap = f"""
import sys, types, httpx
ak = types.ModuleType("akshare")
def failure(**kwargs): raise OSError("offline sdk failure")
ak.stock_individual_fund_flow = failure
sys.modules["akshare"] = ak
original = httpx.Client
httpx.Client = lambda **kwargs: original(transport=httpx.MockTransport(lambda request: httpx.Response(200,content={source!r})),**kwargs)
sys.argv = ["offline-public-worker", "akshare"]
from app.research_web.datahub.public_worker import main
raise SystemExit(main())
"""
        original = subprocess.run

        def run(command, **kwargs):
            self.assertEqual(
                command[1:], ["-m", "app.research_web.datahub.public_worker", "akshare"]
            )
            return original([command[0], "-c", bootstrap], **kwargs)

        request = BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
        )
        with patch("app.research_web.datahub.public_worker.subprocess.run", run):
            result = invoke_worker("akshare", request)
        self.assertEqual(result.status, "snapshot")
        self.assertEqual(result.raw, [source])
        self.assertFalse(result.metadata["formal_backtest_eligible"])

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
