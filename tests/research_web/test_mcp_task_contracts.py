"""Business tools preserve fixed semantics and the existing account submission."""

import asyncio
import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch
from zoneinfo import ZoneInfo

from mcp.server import MCPServer
from mcp.types import ListToolsResult

from app.research_web.datahub.contracts import stock_quote_query
from app.research_web.mcp_facade.domains import (
    DOMAINS,
    BusinessDomain,
    domain_of,
    domains,
    tools_in,
    validate_domains,
)
from app.research_web.mcp_facade.task_contracts import (
    TASKS,
    business_directory,
    business_query,
    domain_metadata,
)
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

        server = MCPServer("test")
        register_tools(server, None, None, SimpleNamespace(task_query=task_query))
        self.assertEqual(len(TASK_TOOL_ARGUMENTS), 9)
        self.assertTrue(all("request_id" in args for args in TASK_TOOL_ARGUMENTS.values()))
        self.assertEqual(
            {domain_of(name) for name in TASKS},
            {"stock_data", "fund_data", "index_data", "economic_data"},
        )
        tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        for name in TASKS:
            self.assertEqual(tools[name].meta, domain_metadata(name))
        self.assertTrue(tools["search_assets"].description.startswith("[shared]"))
        self.assertTrue(tools["get_trading_calendar"].description.startswith("[shared]"))

    def test_scope_filter_keeps_domain_groups_and_unchanged_tool_metadata(self):
        from app.research_web.mcp_facade.server import tools_only

        async def task_query(*args):
            return {}

        server = MCPServer("test")
        register_tools(server, None, None, SimpleNamespace(task_query=task_query))
        listed = ListToolsResult(
            tools=[tool for tool in asyncio.run(server.list_tools()) if tool.name in TASKS]
        )
        token = SimpleNamespace(scopes=["rwb.read", "rwb.data.query", "rwb.data.configured"])

        async def call_next(_ctx):
            return listed

        with patch("app.research_web.mcp_facade.server.get_access_token", return_value=token):
            narrowed = asyncio.run(tools_only(SimpleNamespace(method="tools/list"), call_next))
        self.assertEqual(
            [tool.name for tool in narrowed.tools],
            list(TASKS),
        )
        self.assertEqual(
            [item["id"] for item in narrowed.meta["rwb.business_domains"]],
            [
                "stock_data",
                "fund_data",
                "index_data",
                "bond_data",
                "financial_docs",
                "economic_data",
                "analytics_data",
            ],
        )
        self.assertEqual(
            narrowed.meta["rwb.business_directory_format"], "rwb.business_directory.v1"
        )
        grouped = [
            tool["name"] for item in narrowed.meta["rwb.business_domains"] for tool in item["tools"]
        ]
        self.assertEqual(sorted(grouped), sorted(TASKS))
        registered = {tool.name: tool for tool in asyncio.run(server.list_tools())}
        for item in narrowed.meta["rwb.business_domains"]:
            for entry in item["tools"]:
                tool = registered[entry["name"]]
                self.assertEqual(entry["description"], tool.description)
                self.assertEqual(entry["input_schema"], tool.input_schema)
        for tool in narrowed.tools:
            self.assertEqual(tool.meta, domain_metadata(tool.name))
            self.assertEqual(tool.input_schema["additionalProperties"], False)
            self.assertEqual(
                set(tool.input_schema["properties"]), set(TASK_TOOL_ARGUMENTS[tool.name])
            )


class BusinessDomainTests(unittest.TestCase):
    def test_seven_domains_have_stable_order_and_expected_status(self):
        self.assertEqual(
            [item.id for item in domains()],
            [
                "stock_data",
                "fund_data",
                "index_data",
                "bond_data",
                "financial_docs",
                "economic_data",
                "analytics_data",
            ],
        )
        self.assertEqual(len(domains()), 7)
        by_id = {item.id: item for item in domains()}
        self.assertEqual(by_id["bond_data"].status, "reserved")
        self.assertEqual(by_id["analytics_data"].status, "reserved")
        self.assertEqual(by_id["financial_docs"].status, "available")
        self.assertFalse(by_id["financial_docs"].tools)

    def test_each_registered_tool_belongs_to_exactly_one_domain(self):
        owners = {tool: item.id for item in domains() for tool in item.tools}
        self.assertEqual(set(owners), set(TASKS))
        self.assertEqual(len(owners), sum(len(item.tools) for item in domains()))
        self.assertEqual(owners["get_stock_kline"], "stock_data")
        self.assertEqual(owners["get_fund_detail"], "fund_data")
        self.assertEqual(owners["get_index_quote"], "index_data")
        self.assertEqual(owners["get_economic_series"], "economic_data")
        self.assertEqual(owners["search_assets"], "stock_data")
        self.assertEqual(owners["get_trading_calendar"], "stock_data")
        for name in TASKS:
            self.assertEqual(domain_metadata(name)["rwb.business"]["domain"], owners[name])

    def test_reserved_domains_have_no_tools(self):
        for item in domains():
            if item.status == "reserved":
                self.assertEqual(item.tools, ())
                self.assertEqual(tools_in(item.id), ())

    def test_directory_groups_every_task_once_in_domain_order(self):
        directory = business_directory()
        self.assertEqual(directory["format"], "rwb.business_directory.v1")
        self.assertEqual(
            [item["id"] for item in directory["domains"]], [item.id for item in DOMAINS]
        )
        groups = {
            item["id"]: {tool["name"] for tool in item["tools"]} for item in directory["domains"]
        }
        listed = [tool["name"] for item in directory["domains"] for tool in item["tools"]]
        self.assertEqual(len(listed), len(set(listed)))
        self.assertEqual(set(listed), set(TASKS))
        for item in DOMAINS:
            self.assertEqual(groups[item.id], set(item.tools))
            for tool in item.tools:
                metadata = next(row for row in directory["domains"] if row["id"] == item.id)[
                    "tools"
                ]
                entry = next(row for row in metadata if row["name"] == tool)
                self.assertEqual(entry["capability"], TASKS[tool].capability)
                self.assertEqual(entry["description"], TASKS[tool].description)
                self.assertEqual(
                    entry["input_schema"],
                    TASKS[tool].schema.model_json_schema() | {"additionalProperties": False},
                )

    def test_directory_rejects_unknown_or_duplicate_tool_names(self):
        with self.assertRaisesRegex(ValueError, "unknown_business_tool"):
            business_directory(("get_stock_kline", "get_missing_tool"))
        with self.assertRaisesRegex(ValueError, "duplicate_business_tool"):
            business_directory(("get_stock_kline", "get_stock_kline"))

    def test_domain_catalog_with_an_unregistered_tool_fails(self):
        invalid = (
            BusinessDomain(
                id="stock_data",
                name="股票数据",
                description="测试域清单中的不存在工具。",
                tools=("get_stock_kline", "get_missing_tool"),
                status="available",
            ),
            *(item for item in DOMAINS if item.id != "stock_data"),
        )
        with self.assertRaisesRegex(ValueError, "unknown_domain_tools:get_missing_tool"):
            validate_domains(tuple(TASKS), invalid)

    def test_orphan_or_duplicate_ownership_fails_validation(self):
        orphan = (
            BusinessDomain(
                id="stock_data",
                name="股票数据",
                description="测试域清单遗漏已注册工具。",
                tools=("get_stock_kline",),
                status="available",
            ),
            *(item for item in DOMAINS if item.id != "stock_data"),
        )
        with self.assertRaisesRegex(ValueError, "unowned_business_tools"):
            validate_domains(tuple(TASKS), orphan)
        duplicated = (
            *DOMAINS,
            BusinessDomain(
                id="duplicate_data",
                name="重复域",
                description="测试跨域重复归属。",
                tools=("get_stock_kline",),
                status="available",
            ),
        )
        with self.assertRaisesRegex(ValueError, "duplicate_tool_ownership"):
            validate_domains(tuple(TASKS), duplicated)


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


class StockQuoteContractTests(unittest.TestCase):
    """The snapshot tool must share one contract with the asset page."""

    def test_quote_contract_fixes_capability_and_identity(self):
        q = stock_quote_query(["600519.SH", "000001.SZ"], ["price", "change_pct"])
        self.assertEqual(q.capability, "market_snapshot")
        self.assertEqual(q.parameters["asset_type"], "stock")
        self.assertEqual(q.parameters["assets"], ["600519.SH", "000001.SZ"])
        self.assertEqual(q.parameters["fields"], ["price", "change_pct"])

    def test_quote_contract_defaults_to_price_only(self):
        q = stock_quote_query(["600519.SH"])
        self.assertEqual(q.parameters["fields"], ["price"])

    def test_quote_contract_rejects_bad_input(self):
        for assets, fields in (
            ([], None),
            (["600519.SH"] * 2, None),
            (["600519"], None),
            (["600519.SH"], []),
            (["600519.SH"], ["close"]),
            (["600519.SH"], ["price", "price"]),
        ):
            with self.subTest(assets=assets, fields=fields), self.assertRaises(ValueError):
                stock_quote_query(assets, fields)

    def test_quote_contract_caps_asset_count(self):
        with self.assertRaises(ValueError):
            stock_quote_query(["600519.SH"] * 21)
        q = stock_quote_query([f"{code:06d}.SH" for code in range(600000, 600000 + 20)])
        self.assertEqual(len(q.parameters["assets"]), 20)

    def test_mcp_tool_uses_the_shared_quote_contract(self):
        request_id, q = business_query(
            "get_stock_quote",
            {"request_id": "quote", "assets": ["600519.SH"], "fields": ["price", "pb"]},
        )
        expected = stock_quote_query(["600519.SH"], ["price", "pb"])
        self.assertEqual(request_id, "quote")
        self.assertEqual(q.capability, expected.capability)
        self.assertEqual(q.parameters, expected.parameters)

    def test_mcp_tool_still_rejects_bad_assets(self):
        with self.assertRaises(ValueError):
            business_query("get_stock_quote", {"request_id": "q", "assets": ["600519"]})


class AkshareSnapshotDerivedFieldTests(unittest.TestCase):
    """The snapshot path must fill derivable fields instead of returning null."""

    def test_change_pct_and_market_cap_are_derived_from_daily_bars(self):
        from datetime import date

        import pandas as pd

        from app.research_web.datahub import providers_akshare

        frame = pd.DataFrame(
            [
                {
                    "date": date(2026, 11, 25),
                    "close": 1475.0,
                    "volume": 1.0,
                    "amount": 2.0,
                    "outstanding_share": 1_000.0,
                },
                {
                    "date": date(2026, 11, 26),
                    "close": 1469.0,
                    "volume": 3.0,
                    "amount": 4.0,
                    "outstanding_share": 1_000.0,
                },
            ]
        )
        query = stock_quote_query(["600519.SH"], ["price", "change_pct"])

        with patch("akshare.stock_zh_a_daily", create=True, return_value=frame):
            rows, _ = providers_akshare._invoke_sdk(query)

        self.assertEqual(len(rows), 1)
        row = rows.iloc[0].to_dict()
        self.assertEqual(row["涨跌幅"], -0.4068)
        self.assertEqual(row["总市值"], 1_469_000.0)
        self.assertEqual(row["最新价"], 1469.0)

    def test_missing_prior_close_does_not_invent_a_change(self):
        from datetime import date

        import pandas as pd

        from app.research_web.datahub import providers_akshare

        frame = pd.DataFrame(
            [
                {
                    "date": date(2026, 11, 26),
                    "close": 1469.0,
                    "volume": 3.0,
                    "amount": 4.0,
                    "outstanding_share": None,
                }
            ]
        )
        query = stock_quote_query(["600519.SH"], ["price"])

        with patch("akshare.stock_zh_a_daily", create=True, return_value=frame):
            rows, _ = providers_akshare._invoke_sdk(query)

        row = rows.iloc[0].to_dict()
        self.assertIsNone(row["涨跌幅"])
        self.assertIsNone(row["总市值"])
