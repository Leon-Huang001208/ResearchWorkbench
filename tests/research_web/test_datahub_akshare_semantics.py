"""Stock feeds use different lot/rate conventions despite identical business fields."""

import asyncio
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx
import pandas as pd

from app.research_web.datahub import providers_akshare as provider
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError, cn_stock_identity


class ChinaMacroTests(unittest.TestCase):
    def request(self, series="cpi", **updates):
        return BusinessQuery(
            capability="factor_macro",
            source="akshare",
            parameters={
                "series": series,
                "start_date": "2026-09-01",
                "end_date": "2026-09-30",
                **updates,
            },
        )

    def replay(self, series, body=None):
        name = "money_supply" if series == "m2" else series
        raw = (
            (Path(__file__).parent / f"fixtures/china_macro_{name}.json").read_bytes()
            if body is None
            else json.dumps(body).encode()
        )
        original = httpx.Client

        def handler(request):
            self.assertEqual(request.url.host, "datacenter-web.eastmoney.com")
            self.assertEqual(request.url.params["pageNumber"], "1")
            self.assertEqual(request.url.params["pageSize"], "2000")
            return httpx.Response(200, content=raw)

        with (
            patch.dict(sys.modules, {"akshare": SimpleNamespace()}),
            patch.object(
                provider.httpx,
                "Client",
                side_effect=lambda **kwargs: original(
                    transport=httpx.MockTransport(handler), **kwargs
                ),
            ),
        ):
            return provider.invoke_public(self.request(series)), raw

    def test_four_actual_envelopes_preserve_raw_period_and_semantics(self):
        for series in ("cpi", "gdp", "pmi", "m2"):
            with self.subTest(series=series):
                result, raw = self.replay(series)
                self.assertEqual(result.status, "snapshot")
                self.assertEqual(len(result.rows), 1)
                self.assertEqual(result.raw, [raw])
                self.assertEqual(result.rows[0]["date"], "2026-09-30")
                self.assertEqual(
                    result.rows[0]["reference_period"], "2026-Q3" if series == "gdp" else "2026-09"
                )
                self.assertEqual(result.metadata["schema_version"], "akshare-china-macro-v1")
                self.assertFalse(result.metadata["formal_backtest_eligible"])
                if series == "gdp":
                    self.assertEqual(result.rows[0]["aggregation"], "year_to_date")
                    self.assertEqual(result.rows[0]["DOMESTICL_PRODUCT_BASE"], 1071071.2)
                if series == "m2":
                    self.assertEqual(result.fields["BASIC_CURRENCY"]["unit"], "CNY_100million")

    def test_invalid_contracts_rejected_without_http(self):
        for values in (
            {"series": "money_supply"},
            {"series": "unknown"},
            {"start_date": "2026-9-1"},
            {"start_date": "2026-10-01"},
            {"assets": ["000001.SZ"]},
            {"end_date": None},
            {"start_date": "20260901"},
            {"start_date": "2026/09/01"},
            {"start_date": "2026-02-30"},
            {"start_date": True},
        ):
            with (
                self.subTest(values=values),
                patch.object(
                    provider.httpx, "Client", side_effect=AssertionError("must not fetch")
                ),
                self.assertRaises(ProviderError),
            ):
                provider.invoke_public(self.request(**values))

    def test_bad_envelopes_and_values_fail_without_coercion(self):
        original = json.loads(
            (Path(__file__).parent / "fixtures/china_macro_cpi.json").read_bytes()
        )
        for body in (
            {},
            {"success": True, "code": 0, "result": None},
            {**original, "success": False},
            {**original, "code": True},
            {**original, "result": {**original["result"], "count": 1}},
        ):
            with self.subTest(body=str(body)[:60]), self.assertRaises(ProviderError):
                self.replay("cpi", body)
        for field, value in (
            ("TIME", "2026年08月份"),
            ("REPORT_DATE", "2026-09-02 00:00:00"),
            ("NATIONAL_BASE", "oops"),
        ):
            body = json.loads(json.dumps(original))
            body["result"]["data"][0][field] = value
            with self.subTest(field=field), self.assertRaises(ProviderError):
                self.replay("cpi", body)
        body = json.loads(json.dumps(original))
        body["result"]["data"][0]["NATIONAL_BASE"] = None
        result, _ = self.replay("cpi", body)
        self.assertEqual(result.status, "partial")
        self.assertIsNone(result.rows[0]["NATIONAL_BASE"])
        body["result"]["data"][0]["NATIONAL_BASE"] = 0
        result, _ = self.replay("cpi", body)
        self.assertEqual(result.status, "snapshot")
        self.assertEqual(result.rows[0]["NATIONAL_BASE"], 0)
        del body["result"]["data"][0]["NATIONAL_BASE"]
        with self.assertRaises(ProviderError):
            self.replay("cpi", body)

    def test_native_freeze_restore_preserves_every_series(self):
        import base64
        from datetime import UTC, datetime

        from app.research_web.datahub.research_snapshot_store import SnapshotSeries
        from app.research_web.market_store import (
            FrozenSnapshot,
            InMemoryMarketStore,
            MarketStoreError,
            MarketStoreService,
            StoreScope,
        )

        for name in ("cpi", "gdp", "pmi", "m2"):
            with self.subTest(series=name):
                result, raw = self.replay(name)
                request = self.request(name)
                scope = StoreScope("alice", "public", "akshare", "a" * 64)
                service = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
                native = SnapshotSeries(service, "alice", scope)
                stamp = datetime(2026, 10, 23, tzinfo=UTC)
                native._now = lambda stamp=stamp: stamp
                self.assertIsNotNone(native.ingest(request, result))
                captured = request.model_copy(update={"as_of": stamp})
                read = native.read(captured)
                self.assertEqual(read.rows, result.rows)
                self.assertEqual(read.metadata["schema_version"], "akshare-china-macro-v1")
                frozen = FrozenSnapshot.load(read.raw[0])
                envelope = json.loads(
                    base64.b64decode(json.loads(frozen.payload)["batch"]["originals"][0]["base64"])
                )
                self.assertEqual(base64.b64decode(envelope["payloads"][0]["base64"]), raw)
                replacement = MarketStoreService(InMemoryMarketStore(), lambda *_: True)
                replacement.export_restore("alice", scope, frozen.export())
                again = SnapshotSeries(replacement, "alice", scope).read(captured)
                self.assertEqual(again.rows, read.rows)
                self.assertEqual(again.fields, read.fields)
                from dataclasses import replace

                for rejected in (
                    replace(result, metadata={}),
                    replace(result, pagination_complete=False),
                    replace(result, rows=[{**result.rows[0], "NATIONAL_BASE": None}]),
                    replace(result, status="partial"),
                ):
                    self.assertIsNone(native.ingest(request, rejected))
                with self.assertRaises(MarketStoreError):
                    native.dataset(request.model_copy(update={"purpose": "backtest"}))

    def test_broker_and_partial_pages_empty_range(self):
        from app.research_web.datahub.broker import resolve
        from app.research_web.datahub.research_snapshot_store import SnapshotSeries
        from app.research_web.market_store import (
            InMemoryMarketStore,
            MarketStoreService,
            StoreScope,
        )

        with patch("app.research_web.datahub.catalog.find_spec", return_value=object()):
            self.assertEqual(resolve(self.request()).provider_id, "akshare")
        body = json.loads((Path(__file__).parent / "fixtures/china_macro_cpi.json").read_bytes())
        body["result"]["pages"] = 2
        body["result"]["count"] = 2001
        with self.assertRaises(ProviderError):
            self.replay("cpi", body)
        original = httpx.Client
        raw = (Path(__file__).parent / "fixtures/china_macro_cpi.json").read_bytes()
        with (
            patch.dict(sys.modules, {"akshare": SimpleNamespace()}),
            patch.object(
                provider.httpx,
                "Client",
                side_effect=lambda **kwargs: original(
                    transport=httpx.MockTransport(lambda _: httpx.Response(200, content=raw)),
                    **kwargs,
                ),
            ),
        ):
            request = self.request(start_date="1990-01-01", end_date="1990-01-31")
            result = provider.invoke_public(request)
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.rows, [])
        native = SnapshotSeries(
            MarketStoreService(InMemoryMarketStore(), lambda *_: True),
            "alice",
            StoreScope("alice", "public", "akshare", "a" * 64),
        )
        self.assertIsNone(native.ingest(request, result))

    def test_macro_host_schema_is_independent_without_authorization_change(self):
        from app.research_web.datahub.research_snapshot_store import SnapshotSeries
        from app.research_web.datahub.research_warehouse import ResearchWarehouse
        from app.research_web.market_store import InMemoryMarketStore

        profile = {"enabled": True, "id": "public", "configuration": {}, "owner": "alice"}
        host = SimpleNamespace(
            owner="alice",
            _profile=lambda: profile,
            _secret=lambda _: "fixture",
            _factory=lambda *_: InMemoryMarketStore(),
        )
        native, request = ResearchWarehouse._snapshot_series(
            host, self.request(), "akshare", "a" * 64
        )
        legacy = SnapshotSeries(
            native.service,
            "alice",
            native.scope,
            schema_identity="datahub-provider-native-v1:" + "a" * 64,
            units_identity="vendor-fields-retained-unverified-v1",
        )
        self.assertEqual(native.scope, legacy.scope)
        self.assertTrue(native.schema_identity.endswith(":akshare-china-macro-v1"))
        self.assertEqual(native.units_identity, "akshare-china-macro-v1")
        self.assertNotEqual(native.dataset(request), legacy.dataset(request))

    def test_macro_new_cache_rejects_old_schema_but_old_receipt_is_readable(self):
        from tempfile import TemporaryDirectory

        from app.research_web.datahub import DataHub
        from app.research_web.datahub.providers import Result
        from app.research_web.store import Store

        async def exercise(root):
            store = Store(Path(root))
            sid = store.create("claw", "macro schema")["id"]
            hub = DataHub(store)
            calls = []
            request = self.request()
            raw = (Path(__file__).parent / "fixtures/china_macro_cpi.json").read_bytes()
            original = httpx.Client

            def handle(request):
                calls.append(request)
                return httpx.Response(200, content=raw)

            old = Result(
                provider_id="akshare",
                status="snapshot",
                rows=[{"date": "2026-09-30", "NATIONAL_BASE": 999}],
                raw=[b"old"],
                metadata={"schema_version": "old-macro"},
            )
            with patch("app.research_web.datahub.catalog.find_spec", return_value=object()):
                saved = hub.snapshots.publish(
                    sid,
                    request,
                    old,
                    request_query=request,
                    authorization_fingerprint=hub.source_configuration_digest("akshare"),
                )
                hub.snapshots.receipt(
                    sid,
                    "old-call",
                    {
                        "status": "completed",
                        "fingerprint": request.fingerprint(include_refresh=True),
                        "dataset_id": saved["dataset_id"],
                        "cache_hit": False,
                    },
                )
                try:
                    with (
                        patch.dict(sys.modules, {"akshare": SimpleNamespace()}),
                        patch.object(provider, "_invoke", provider.invoke_public),
                        patch.object(
                            provider.httpx,
                            "Client",
                            side_effect=lambda **kwargs: original(
                                transport=httpx.MockTransport(handle), **kwargs
                            ),
                        ),
                    ):
                        self.assertEqual(
                            (await hub.query(sid, "old-call", request))["dataset_id"],
                            saved["dataset_id"],
                        )
                        self.assertEqual(calls, [])
                        new = await hub.query(sid, "new-call", request)
                        self.assertNotEqual(new["dataset_id"], saved["dataset_id"])
                        self.assertEqual(len(calls), 1)
                        self.assertEqual(
                            (await hub.query(sid, "cache", request))["dataset_id"],
                            new["dataset_id"],
                        )
                        self.assertEqual(len(calls), 1)
                finally:
                    await hub.close()

        with TemporaryDirectory() as root:
            asyncio.run(exercise(root))


class AKShareSemanticsTests(unittest.TestCase):
    def test_real_rc100_null_never_becomes_successful_cache_or_native_capture(self):
        from tempfile import TemporaryDirectory

        from app.research_web.datahub import DataHub
        from app.research_web.datahub.research_snapshot_store import SnapshotSeries
        from app.research_web.market_store import (
            InMemoryMarketStore,
            MarketStoreService,
            StoreScope,
        )
        from app.research_web.store import Store

        async def exercise(root):
            request = BusinessQuery(
                capability="market_activity",
                source="akshare",
                parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
            )
            store = Store(Path(root))
            sid = store.create("claw", "rc100")["id"]
            hub = DataHub(store)
            calls = []
            original = httpx.Client

            def failed(**_):
                raise OSError("offline sdk failure")

            def handler(request):
                calls.append(request)
                return httpx.Response(
                    200,
                    json={
                        "rc": 100,
                        "rt": 1,
                        "svr": 177617587,
                        "lt": 1,
                        "full": 1,
                        "dlmkts": "",
                        "dsc": "0",
                        "data": None,
                    },
                )

            try:
                with (
                    patch.dict(
                        sys.modules, {"akshare": SimpleNamespace(stock_individual_fund_flow=failed)}
                    ),
                    patch.object(provider, "_invoke", provider.invoke_public),
                    patch("app.research_web.datahub.catalog.find_spec", return_value=object()),
                    patch.object(
                        provider.httpx,
                        "Client",
                        side_effect=lambda **kwargs: original(
                            transport=httpx.MockTransport(handler), **kwargs
                        ),
                    ),
                ):
                    for call in ("first", "second"):
                        summary = await hub.query(sid, call, request)
                        self.assertEqual(summary["status"], "failed")
                        self.assertFalse(summary["cache_hit"])
                    result = await provider.fetch(request)
                    series = SnapshotSeries(
                        MarketStoreService(InMemoryMarketStore(), lambda *_: True),
                        "alice",
                        StoreScope("alice", "public", "akshare", "a" * 64),
                    )
                    self.assertIsNone(series.ingest(request, result))
                    self.assertEqual(result.raw, [])
                    self.assertEqual(len(calls), 3)
            finally:
                await hub.close()

        with TemporaryDirectory() as root:
            asyncio.run(exercise(root))

    def test_fund_flow_failure_guest_keeps_raw_and_never_claims_history(self):
        raw = (Path(__file__).parent / "fixtures/fund_flow_guest.json").read_bytes()

        def failed(**_kwargs):
            raise OSError("synthetic sdk failure")

        original = httpx.Client
        calls = []

        def handle(request):
            calls.append(request)
            self.assertEqual(request.url.host, "82.push2.eastmoney.com")
            self.assertEqual(request.url.params["secid"], "0.000001")
            self.assertEqual(request.url.params["ut"], "b2884a393a59ad64002292a3e90d46a5")
            self.assertNotIn("secid2", request.url.params)
            return httpx.Response(200, content=raw)

        with (
            patch.dict(
                sys.modules, {"akshare": SimpleNamespace(stock_individual_fund_flow=failed)}
            ),
            patch.object(
                provider.httpx,
                "Client",
                side_effect=lambda **kwargs: original(
                    transport=httpx.MockTransport(handle), **kwargs
                ),
            ),
        ):
            request = BusinessQuery(
                capability="market_activity",
                source="akshare",
                parameters={
                    "asset": "000001.SZ",
                    "dataset": "fund_flow",
                    "start_date": "2026-10-19",
                    "end_date": "2026-10-20",
                },
            )
            result = provider.invoke_public(request)
            self.assertEqual(result.status, "partial")
            self.assertEqual(result.rows, [])
            self.assertEqual(result.raw, [raw])
            self.assertEqual(result.provider_total, 1)
            self.assertIn("fund_flow_history_coverage_unverified", result.missing)
            latest = provider.invoke_public(
                request.model_copy(
                    update={"parameters": {"asset": "000001.SZ", "dataset": "fund_flow"}}
                )
            )
            self.assertEqual(latest.status, "snapshot")
            self.assertEqual(latest.rows[0]["date"], "2026-10-22")
            self.assertEqual(latest.rows[0]["main_net"], -81654384.0)
            self.assertIsNone(latest.fields["main_net"]["unit"])
            self.assertEqual(latest.metadata["upstream_id"], "eastmoney")
            self.assertFalse(latest.metadata["independent_source"])
            self.assertFalse(latest.metadata["historical_point_in_time"])
            self.assertEqual(len(calls), 2)

    def test_fund_flow_guest_single_day_hit_remains_partial(self):
        raw = (Path(__file__).parent / "fixtures/fund_flow_guest.json").read_bytes()
        original = httpx.Client
        with patch.object(
            provider.httpx,
            "Client",
            side_effect=lambda **kwargs: original(
                transport=httpx.MockTransport(lambda _: httpx.Response(200, content=raw)), **kwargs
            ),
        ):
            request = BusinessQuery(
                capability="market_activity",
                source="akshare",
                parameters={
                    "asset": "000001.SZ",
                    "dataset": "fund_flow",
                    "start_date": "2026-10-22",
                    "end_date": "2026-10-22",
                },
            )
            result = provider._materialize(request, *provider._fund_flow_guest(request))
            self.assertEqual(result.status, "partial")
            self.assertEqual(len(result.rows), 1)
            self.assertIn("fund_flow_history_coverage_unverified", result.missing)

    def test_fund_flow_guest_rejects_invalid_envelopes_identity_and_dates(self):
        source = json.loads((Path(__file__).parent / "fixtures/fund_flow_guest.json").read_bytes())
        request = BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
        )
        payloads = [None, {}, {"rc": 0, "data": None}]
        for change in (
            {"code": "600000"},
            {"market": 1},
            {"market": False},
            {"klines": []},
            {"klines": ["invalid"]},
            {"klines": [source["data"]["klines"][0]] * 2},
            {"klines": [source["data"]["klines"][0].replace("2026-10-22", "2099-01-01")]},
            {"klines": [source["data"]["klines"][0].replace("-81654384.0", "NaN")]},
        ):
            payloads.append({**source, "data": {**source["data"], **change}})
        payloads += [{**source, "rc": False}, {**source, "rc": 1}]
        original = httpx.Client
        for payload in payloads:
            with (
                self.subTest(payload=payload),
                patch.object(
                    provider.httpx,
                    "Client",
                    side_effect=lambda payload=payload, **kwargs: original(
                        transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload)),
                        **kwargs,
                    ),
                ),
                self.assertRaisesRegex(ProviderError, "vendor_schema_invalid"),
            ):
                provider._fund_flow_guest(request)

    def test_fund_flow_guest_http_failure_limits_and_history_are_closed(self):
        request = BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
        )
        original = httpx.Client

        def timeout(_):
            raise httpx.ReadTimeout("synthetic")

        for handle in (
            lambda _: httpx.Response(302, headers={"location": "https://untrusted.invalid"}),
            lambda _: httpx.Response(500),
            timeout,
        ):
            with (
                patch.object(
                    provider.httpx,
                    "Client",
                    side_effect=lambda handle=handle, **kwargs: original(
                        transport=httpx.MockTransport(handle), **kwargs
                    ),
                ),
                self.assertRaisesRegex(ProviderError, "vendor_unreachable"),
            ):
                provider._fund_flow_guest(request)
        with (
            patch.object(provider, "MAX_RESPONSE_BYTES", 8),
            patch.object(
                provider.httpx,
                "Client",
                side_effect=lambda **kwargs: original(
                    transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * 9)),
                    **kwargs,
                ),
            ),
            self.assertRaisesRegex(ProviderError, "vendor_schema_invalid"),
        ):
            provider._fund_flow_guest(request)
        for update in (
            {"purpose": "backtest"},
            {"as_of": pd.Timestamp("2026-10-22", tz="UTC").to_pydatetime()},
        ):
            with (
                patch.object(
                    provider.httpx, "Client", side_effect=AssertionError("must not access guest")
                ),
                self.assertRaisesRegex(ProviderError, "data_not_equivalent"),
            ):
                provider._fund_flow_guest(request.model_copy(update=update))

    def test_successful_sdk_fund_flow_never_accesses_guest(self):
        request = BusinessQuery(
            capability="market_activity",
            source="akshare",
            parameters={"asset": "000001.SZ", "dataset": "fund_flow"},
        )
        package = SimpleNamespace(
            stock_individual_fund_flow=lambda **_: pd.DataFrame(
                [{"日期": "2026-10-22", "主力净流入-净额": 1}]
            )
        )
        with (
            patch.dict(sys.modules, {"akshare": package}),
            patch.object(
                provider, "_fund_flow_guest", side_effect=AssertionError("SDK success cannot retry")
            ),
        ):
            self.assertEqual(provider.invoke_public(request).status, "complete")

    def test_wind_disguised_stock_rejected_before_submitting_adapter(self):
        from app.research_web.datahub import providers_wind

        for asset in ("000001.SH", "510050.SH", "600000.SZ", "000001.BJ"):
            for capability, parameters in (
                (
                    "market_bars",
                    {
                        "asset": asset,
                        "asset_type": "stock",
                        "start_date": "2025-01-02",
                        "end_date": "2025-01-03",
                    },
                ),
                ("market_snapshot", {"assets": [asset], "asset_type": "stock"}),
            ):
                with (
                    self.subTest(asset=asset, capability=capability),
                    patch.object(
                        providers_wind,
                        "_submit",
                        side_effect=AssertionError("adapter_must_not_run"),
                    ) as submit,
                ):
                    result = asyncio.run(
                        providers_wind.fetch(
                            BusinessQuery(
                                capability=capability, source="wind", parameters=parameters
                            )
                        )
                    )
                    self.assertEqual(result.status, "failed")
                    self.assertEqual(result.limitations, ["data_not_equivalent"])
                    submit.assert_not_called()

    def test_shared_identity_allows_only_reviewed_stock_code_families(self):
        for value, expected in (
            ("600000.SH", "600000.SH"),
            ("000001.SZ", "000001.SZ"),
            ("600519", "600519.SH"),
            ("300750", "300750.SZ"),
        ):
            self.assertEqual(cn_stock_identity(value), expected)
        for value in ("510050", "399001.SZ", "900001.SH", "800001.BJ", None):
            with self.assertRaisesRegex(ProviderError, "^data_not_equivalent$"):
                cn_stock_identity(value)

    def test_stock_identity_rejects_index_etf_and_wrong_exchange_before_sdk(self):
        for asset in ("000001.SH", "510050.SH", "600000.SZ", "000001.BJ"):
            for capability, parameters in (
                ("market_bars", {"asset": asset, "asset_type": "stock"}),
                ("market_snapshot", {"assets": [asset], "asset_type": "stock"}),
                ("market_activity", {"asset": asset, "dataset": "fund_flow"}),
            ):
                with (
                    self.subTest(asset=asset, capability=capability),
                    self.assertRaisesRegex(ProviderError, "^data_not_equivalent$"),
                ):
                    provider.validate_supported_query(
                        BusinessQuery(
                            capability=capability, source="akshare", parameters=parameters
                        )
                    )

    def test_valid_stock_and_explicit_native_index_etf_contracts_remain_valid(self):
        for asset in ("600000.SH", "000001.SZ", "600519"):
            provider.validate_supported_query(self.query(asset=asset))
            provider.validate_supported_query(
                BusinessQuery(
                    capability="market_snapshot",
                    source="akshare",
                    parameters={"assets": [asset], "asset_type": "stock"},
                )
            )
        for asset, asset_type in (("000001.SH", "index"), ("510050.SH", "etf")):
            provider.validate_supported_query(self.query(asset=asset, asset_type=asset_type))

    def test_financial_summary_filters_period_and_rejects_full_statement_claim(self):
        query = BusinessQuery(
            capability="financials",
            source="akshare",
            parameters={"asset": "000001.SZ", "statements": ["metrics"], "periods": ["2024-12-31"]},
        )
        provider.validate_supported_query(query)
        rows = provider._normalize_financials(
            [{"报告期": "2024-12-31", "净利润": 1}, {"报告期": "2025-03-31", "净利润": 2}], query
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["净利润"], 1)
        with self.assertRaises(ProviderError):
            provider.validate_supported_query(
                query.model_copy(
                    update={"parameters": {**query.parameters, "statements": ["balance_sheet"]}}
                )
            )

    def test_row_limit_reports_partial_and_cannot_publish_complete_coverage(self):
        frame = pd.DataFrame([{"value": index} for index in range(provider.MAX_ROWS + 1)])
        result = provider._materialize(self.query(), frame, lambda rows, _query: rows)
        self.assertEqual(len(result.rows), provider.MAX_ROWS)
        self.assertEqual(result.status, "partial")
        self.assertFalse(result.pagination_complete)
        self.assertIn("remaining_provider_rows", result.missing)

    def test_raw_daily_sina_failure_uses_independent_eastmoney_with_same_units(self):
        def failed(**_kwargs):
            raise OSError("fixture vendor detail")

        package = SimpleNamespace(
            stock_zh_a_daily=failed,
            stock_zh_a_hist=lambda **kwargs: pd.DataFrame(
                [
                    {
                        "日期": "2025-01-02",
                        "开盘": 10,
                        "收盘": 11,
                        "最高": 12,
                        "最低": 9,
                        "成交量": 100,
                        "成交额": 110000,
                    }
                ]
            ),
        )
        with patch.dict(sys.modules, {"akshare": package}):
            result = provider.invoke_public(self.query())
        self.assertEqual(result.rows[0]["volume"], 10000)
        self.assertEqual(result.metadata["upstream_id"], "eastmoney")
        self.assertEqual(
            [item["status"] for item in result.metadata["upstream_attempts"]],
            ["failed", "complete"],
        )

    def test_calendar_proves_whole_range_and_keeps_nontrading_days(self):
        query = BusinessQuery(
            capability="trading_calendar",
            source="akshare",
            parameters={"market": "CN", "start_date": "2025-01-03", "end_date": "2025-01-06"},
        )
        package = SimpleNamespace(
            tool_trade_date_hist_sina=lambda: [
                {"trade_date": "2025-01-02"},
                {"trade_date": "2025-01-03"},
                {"trade_date": "2025-01-06"},
                {"trade_date": "2025-01-07"},
            ]
        )
        with patch.dict(sys.modules, {"akshare": package}):
            result = provider.invoke_public(query)
        self.assertEqual([row["is_trading_day"] for row in result.rows], [True, False, False, True])
        self.assertEqual(len(result.rows), 4)

    def query(self, **parameters):
        return BusinessQuery(
            capability="market_bars",
            source="akshare",
            parameters={
                "asset": "000001.SZ",
                "asset_type": "stock",
                "frequency": "daily",
                "adjustment": "none",
                **parameters,
            },
        )

    def test_sina_turnover_ratio_is_not_cash_amount(self):
        rows = [{"date": "2025-01-02", "close": 10, "volume": 100, "turnover": 0.02}]
        _, normalize = self.invoke(SimpleNamespace(stock_zh_a_daily=lambda **_: rows))
        result = normalize(rows, self.query())
        self.assertIsNone(result[0]["turnover"])
        self.assertEqual(result[0]["turnover_rate_pct"], 2)
        self.assertEqual(result[0]["volume"], 100)

    def test_weekly_em_lots_convert_to_shares_and_request_has_timeout(self):
        called = {}

        def history(**kwargs):
            called.update(kwargs)
            return []

        _, normalize = self.invoke(SimpleNamespace(stock_zh_a_hist=history), frequency="1w")
        rows = normalize(
            [{"日期": "2025-01-03", "成交量": 100, "成交额": 1000}], self.query(frequency="1w")
        )
        self.assertEqual(rows[0]["volume"], 10000)
        self.assertEqual(called["period"], "weekly")
        self.assertLessEqual(called["timeout"], provider.DEADLINE)

    def invoke(self, package, **parameters):
        with patch.dict(sys.modules, {"akshare": package}):
            return provider._invoke_sdk(self.query(**parameters))

    def test_unknown_asset_type_or_frequency_rejected_before_sdk(self):
        for parameters in ({"asset_type": "crypto"}, {"frequency": "arbitrary"}):
            with self.assertRaises(ProviderError):
                provider.validate_supported_query(self.query(**parameters))
