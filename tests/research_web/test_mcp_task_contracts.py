"""Business tools preserve fixed semantics and the existing account submission."""

import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from mcp.server import MCPServer

from app.research_web.mcp_facade.task_contracts import TASKS, business_query
from app.research_web.mcp_facade.tools import TASK_TOOL_ARGUMENTS, register_tools


class BusinessContractTests(unittest.TestCase):
    def test_current_day_is_not_claimed_as_final_history(self):
        today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
        with self.assertRaises(ValueError):
            business_query(
                "get_stock_kline",
                {
                    "request_id": "today-bar",
                    "asset": "600519.SH",
                    "start_date": today,
                    "end_date": today,
                },
            )

    def test_kline_fills_internal_identity(self):
        key, query = business_query(
            "get_stock_kline",
            {
                "request_id": "k1",
                "asset": "600519.SH",
                "start_date": "2026-01-01",
                "end_date": "2026-01-30",
            },
        )
        self.assertEqual(key, "k1")
        self.assertEqual(query.capability, "market_bars")
        self.assertEqual(query.source, "auto")
        self.assertEqual(query.parameters["asset_type"], "stock")
        self.assertEqual(query.parameters["adjustment"], "none")

    def test_caller_cannot_supply_a_source(self):
        with self.assertRaises(ValueError):
            business_query(
                "get_stock_quote", {"request_id": "q", "assets": ["600519.SH"], "source": "wind"}
            )

    def test_wrong_market_identity_is_rejected(self):
        with self.assertRaises(ValueError):
            business_query("get_stock_quote", {"request_id": "q", "assets": ["600519.SZ"]})

    def test_duplicate_assets_are_rejected(self):
        with self.assertRaises(ValueError):
            business_query("get_stock_quote", {"request_id": "q", "assets": ["600519.SH"] * 2})

    def test_cashflow_requires_one_quarter(self):
        with self.assertRaises(ValueError):
            business_query(
                "get_stock_financials",
                {"request_id": "f", "asset": "600519.SH", "dataset": "cash_flow", "periods": 4},
            )
        _, q = business_query(
            "get_stock_financials",
            {
                "request_id": "f",
                "asset": "600519.SH",
                "dataset": "cash_flow",
                "periods": ["2025-12-31"],
            },
        )
        self.assertEqual(q.parameters["statements"], ["cash_flow"])

    def test_income_period_limit_not_silently_truncated(self):
        with self.assertRaises(ValueError):
            business_query(
                "get_stock_financials",
                {
                    "request_id": "f",
                    "asset": "600519.SH",
                    "dataset": "income_statement",
                    "periods": 9,
                },
            )

    def test_index_maps_to_native_single_index(self):
        _, q = business_query("get_index_quote", {"request_id": "i", "index": "000300.SH"})
        self.assertEqual(q.parameters, {"index": "000300.SH", "dataset": "quotes"})

    def test_default_quote_only_requests_price(self):
        _, q = business_query("get_stock_quote", {"request_id": "q", "assets": ["600519.SH"]})
        self.assertEqual(q.parameters["fields"], ["price"])

    def test_reversed_dates_are_rejected(self):
        with self.assertRaises(ValueError):
            business_query(
                "get_trading_calendar",
                {"request_id": "c", "start_date": "2026-02-01", "end_date": "2026-01-01"},
            )

    def test_unverified_adjustment_is_not_claimed(self):
        with self.assertRaises(ValueError):
            business_query(
                "get_stock_kline",
                {
                    "request_id": "k1",
                    "asset": "600519.SH",
                    "start_date": "2026-01-01",
                    "end_date": "2026-01-30",
                    "adjustment": "qfq",
                },
            )

    def test_sdk_registers_business_tool_schemas(self):
        async def task_query(*args):
            return {}

        register_tools(MCPServer("test"), None, None, SimpleNamespace(task_query=task_query))
        self.assertEqual(len(TASK_TOOL_ARGUMENTS), 9)
        self.assertTrue(all("request_id" in args for args in TASK_TOOL_ARGUMENTS.values()))
        self.assertEqual(
            {v[0] for v in TASKS.values()},
            {"stock_data", "fund_data", "index_data", "economic_data", "shared"},
        )


class ProviderContractTests(unittest.TestCase):
    def test_each_macro_alias_passes_the_existing_provider_contract(self):
        from app.research_web.datahub.providers_akshare import validate_supported_query

        for public in ["cn_cpi", "cn_gdp", "cn_pmi", "cn_m2"]:
            with self.subTest(series=public):
                _, q = business_query(
                    "get_economic_series",
                    {
                        "request_id": "macro",
                        "series": public,
                        "start_date": "2025-01-01",
                        "end_date": "2025-12-31",
                    },
                )
                validate_supported_query(q)
                self.assertEqual(q.parameters["series"], public[3:])
        with self.assertRaises(ValueError):
            business_query("get_economic_series", {"request_id": "macro", "series": "cn_cpi"})

    def test_financial_quarters_match_the_existing_baostock_contract(self):
        from app.research_web.datahub.providers_baostock import validate_supported_query

        for dataset in ["profitability", "cash_flow"]:
            _, q = business_query(
                "get_stock_financials",
                {
                    "request_id": "financial",
                    "asset": "600519.SH",
                    "dataset": dataset,
                    "periods": ["2025-12-31"],
                },
            )
            validate_supported_query(q)

    def test_activity_rejects_missing_window_and_unimplemented_dataset(self):
        base = {"request_id": "activity", "asset": "600519.SH"}
        for dataset in ["fund_flow", "margin_trading", "block_trade"]:
            with self.subTest(dataset=dataset), self.assertRaises(ValueError):
                business_query("get_stock_activity", {**base, "dataset": dataset})

    def test_shareholder_count_cannot_be_replaced_by_top_ten_holdings(self):
        base = {"request_id": "holders", "asset": "600519.SH"}
        _, count = business_query("get_stock_activity", {**base, "dataset": "holder_count"})
        _, top10 = business_query("get_stock_activity", {**base, "dataset": "holder_data"})
        self.assertEqual((count.source, count.parameters["dataset"]), ("wind", "holder_data"))
        self.assertEqual((top10.source, top10.parameters["dataset"]), ("tinysoft", "holder_data"))

    def test_index_does_not_advertise_unsupported_historical_dates_or_stocks(self):
        for args in [{"index": "000300.SH", "date": "2025-12-31"}, {"index": "600519.SH"}]:
            with self.assertRaises(ValueError):
                business_query("get_index_quote", {"request_id": "index", **args})

    def test_search_does_not_return_stocks_for_a_fund_request(self):
        with self.assertRaises(ValueError):
            business_query(
                "search_assets", {"request_id": "search", "query": "000001", "asset_type": "fund"}
            )

    def resolve_quote(self, fields, assets=None, tinysoft=False):
        from app.research_web.datahub.broker import resolve

        _, q = business_query(
            "get_stock_quote",
            {"request_id": "quote", "assets": assets or ["600519.SH"], "fields": fields},
        )
        with patch(
            "app.research_web.datahub.catalog._dependency_status", return_value=(True, None)
        ):
            return resolve(
                q,
                environ={},
                connection_statuses={
                    "wind": {"configured": True, "preferred_adapter": "excel"},
                    "tinysoft": {"configured": tinysoft, "secret_configured": tinysoft},
                },
            )

    def test_wind_quote_translates_public_price_to_native_close(self):
        r = self.resolve_quote(["price"])
        self.assertEqual(r.provider_id, "wind")
        self.assertEqual(r.query.parameters["fields"], ["close"])
        from app.research_web.datahub.providers_wind import _requested_output_fields

        self.assertIn("price", _requested_output_fields(r.query))

    def test_amount_does_not_use_wind_turnover_rate(self):
        r = self.resolve_quote(["turnover"])
        self.assertEqual(r.provider_id, "akshare")

    def test_batch_quotes_skip_the_single_asset_tinysoft_binding(self):
        r = self.resolve_quote(["price"], ["600519.SH", "000001.SZ"], tinysoft=True)
        self.assertEqual(r.provider_id, "wind")

    def test_calendar_parameters_match_the_existing_provider(self):
        from app.research_web.datahub.providers_akshare import validate_supported_query

        _, q = business_query(
            "get_trading_calendar",
            {"request_id": "calendar", "start_date": "2025-01-01", "end_date": "2025-12-31"},
        )
        validate_supported_query(q)

    def test_fund_dataset_translates_through_the_existing_broker(self):
        from app.research_web.datahub.broker import resolve

        _, q = business_query(
            "get_fund_detail", {"request_id": "fund", "code": "000001", "dataset": "nav"}
        )
        r = resolve(q, environ={})
        self.assertEqual(r.query.source, "fund_nav")
