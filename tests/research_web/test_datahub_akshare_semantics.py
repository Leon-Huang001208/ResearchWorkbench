"""Stock feeds use different lot/rate conventions despite identical business fields."""

import asyncio
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from app.research_web.datahub import providers_akshare as provider
from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError, cn_stock_identity


class AKShareSemanticsTests(unittest.TestCase):
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
