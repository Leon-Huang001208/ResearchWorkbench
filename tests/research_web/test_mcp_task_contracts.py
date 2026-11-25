"""Business tools preserve fixed semantics and the existing account submission."""

import unittest
from datetime import datetime
from types import SimpleNamespace
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
        _, q = business_query(
            "get_index_quote", {"request_id": "i", "index": "000300.SH", "date": "2026-01-05"}
        )
        self.assertEqual(
            q.parameters, {"index": "000300.SH", "date": "2026-01-05", "dataset": "quotes"}
        )

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
