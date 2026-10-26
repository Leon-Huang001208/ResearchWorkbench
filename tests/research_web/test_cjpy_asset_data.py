"""Synthetic SDK fixtures for closed, metadata-checked asset tables."""

import asyncio
import sys
import threading
from copy import deepcopy
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import ProviderError
from app.research_web.datahub.providers_cjpy_assets import FACTORS, TABLES, structured_query


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_cancel_or_deadline_stops_followup_sdk_calls_without_releasing_worker(
    monkeypatch, cancel
):
    from app.research_web.datahub import providers_cjpy as provider

    entered, release = threading.Event(), threading.Event()
    calls = []

    def first():
        entered.set()
        release.wait(2)

    def query(*args):
        sdk = provider._BoundedSDK(
            SimpleNamespace(first=first, second=lambda: calls.append("second"))
        )
        sdk.first()
        sdk.second()
        return []

    monkeypatch.setattr(provider, "_sync_query", query)
    monkeypatch.setattr(provider, "DEADLINE", 0.03)
    task = asyncio.create_task(
        provider.fetch(BusinessQuery(capability="financials", parameters={}))
    )
    try:
        for _ in range(100):
            if entered.is_set():
                break
            await asyncio.sleep(0.001)
        assert entered.is_set()
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert (await task).limitations == ["deadline"]
        assert provider.active_futures()
        assert provider._submit_work(lambda: None) is None
    finally:
        release.set()
        await provider.wait_for_idle(timeout=3)
    assert calls == []


class SDK:
    def get_stocks(self, **kwargs):
        return ["SZ000001"]

    def __init__(self):
        self.calls = []
        self.tables = {
            "主要财务指标": [
                {
                    "CODE": "SZ000001",
                    "截止日": 20260630,
                    "公布日": 20260820,
                    "报告类型": "半年报",
                    "净资产收益率(%)": 0,
                    "销售毛利率(%)": 40,
                }
            ],
            "合并利润表": [
                {
                    "CODE": "SZ000001",
                    "截止日": 20260630,
                    "公布日": 20260820,
                    "报告类型": "半年报",
                    "营业收入": 0,
                    "营业总收入": 9,
                    "净利润": -2,
                    "归属于母公司所有者净利润": -1,
                }
            ],
            "金融公司利润表": [],
            "股票基本信息": [
                {
                    "CODE": "SZ000001",
                    "公司中文简称": "合成证券",
                    "股本单位": "股",
                    "申万一级行业": "申万电子",
                    "申万二级行业": "申万半导体",
                }
            ],
            "股本结构": [
                {"CODE": "SZ000001", "变动日": 20260101, "公布日": 20251201, "总股本": 100}
            ],
            "十大股东": [
                {
                    "CODE": "SZ000001",
                    "截止日": day,
                    "数据报告期": 0,
                    "股东序号": rank,
                    "名称": f"股东{rank}",
                    "股数": 1,
                    "占总股本比例(%)": ratio,
                    "性质": "流通A股",
                    "股东性质": "自然人",
                }
                for day, ratio in [(20260331, 1), (20260630, 2)]
                for rank in range(1, 11)
            ],
            "融资融券明细": [
                {
                    "CODE": "SZ000001",
                    "截止日": 20261021,
                    "融资余额": 0,
                    "融资买入额": 2,
                    "融资偿还额": 1,
                    "融券余量": 3,
                    "融券卖出量": 4,
                    "融券偿还量": 5,
                }
            ],
            "股票公告": [
                {
                    "CODE": "SZ000001",
                    "公布日": 20261021,
                    "公告类型(一级)": "公司治理",
                    "公告类型(二级)": "工作规程",
                    "公告标题": "合成公告",
                }
            ],
        }

    def list_tables(self, **kwargs):
        return [{"表名": name, "日期字段": spec["date_field"]} for name, spec in TABLES.items()]

    def list_table_fields(self, table_name, **kwargs):
        return [
            {"字段名称": name, "单位": unit} for name, unit in TABLES[table_name]["fields"].items()
        ]

    def get_table_data(self, code, table_name, fields, **kwargs):
        assert code == "SZ000001"
        self.calls.append((table_name, fields, kwargs))
        return deepcopy(self.tables[table_name])

    def list_factors(self, **kwargs):
        return [
            {"因子名称": value[0], "公式": value[1], "说明": value[2]} for value in FACTORS.values()
        ]

    def get_market_data(self, **kwargs):
        assert kwargs["rate"] == "不复权"
        return [{"代码": "SZ000001", "时间": "2026-10-21", "close": 10}]

    def list_market_fields(self, **kwargs):
        return [
            {"字段名": "vol", "单位/计算规则": "股票：股；"},
            {"字段名": "amount", "单位/计算规则": "股票：元；"},
        ]

    def get_factor_data(self, **kwargs):
        assert "repo" not in kwargs
        return [
            {
                "代码": "SZ000001",
                "截止日": "20261021",
                "名称": "合成证券",
                "PETTM": 0,
                "PBLF": 1,
                "PBMRQ": 2,
                "PSTTM": 3,
                "总股本": 100,
                "总市值": 0.1,
                "换手率": 0,
            }
        ]


def run(sdk, capability="financials", **parameters):
    identity = {} if capability == "market_snapshot" else {"asset": "000001.SZ"}
    return structured_query(
        BusinessQuery(
            capability=capability, source="tinysoft", parameters={**identity, **parameters}
        ),
        sdk,
        "client",
        "synthetic-token",
    )


class TurnoverSDK(SDK):
    def get_factor_data(self, *, code, date, factors, client):
        assert code == "SZ000001" and factors == ["换手率"] and client == "client"
        assert isinstance(date, list) and len(date) <= 32
        return [
            {"代码": code, "截止日": d.replace("-", ""), "换手率": 0 if i == 0 else 8.5}
            for i, d in enumerate(date)
        ]


def test_chip_turnover_closed_contract_keeps_zero_dates_units_and_raw_evidence():
    result = run(
        TurnoverSDK(),
        "market_activity",
        dataset="chip_turnover",
        dates=["2026-01-05", "2026-01-06"],
    )
    assert result.rows == [
        {"asset": "000001.SZ", "date": "2026-01-05", "turnover_rate_pct": 0},
        {"asset": "000001.SZ", "date": "2026-01-06", "turnover_rate_pct": 8.5},
    ]
    assert result.fields["turnover_rate_pct"]["unit"] == "percent"
    assert result.metadata["chip_turnover_contract"]["version"] == "chip-turnover-1"
    assert len(result.raw) >= 2


@pytest.mark.parametrize(
    "dates",
    [
        [],
        ["2026-01-05"] * 2,
        ["not-a-date"],
        ["2026-01-06", "2026-01-05"],
        [f"2026-01-{i:02d}" for i in range(1, 34)],
    ],
)
def test_chip_turnover_rejects_unbounded_or_ambiguous_date_requests(dates):
    with pytest.raises((ProviderError, ValueError)):
        run(TurnoverSDK(), "market_activity", dataset="chip_turnover", dates=dates)


@pytest.mark.parametrize(
    "mutation", ["identity", "duplicate", "missing", "boolean", "negative", "definition"]
)
def test_chip_turnover_rejects_bad_identity_coverage_number_or_definition(mutation):
    sdk = TurnoverSDK()
    original = sdk.get_factor_data
    if mutation == "definition":
        definitions = sdk.list_factors()
        sdk.list_factors = lambda **kwargs: [
            {**r, "公式": "unverified"} if r["因子名称"] == "换手率" else r for r in definitions
        ]
    else:

        def data(**kwargs):
            rows = original(**kwargs)
            if mutation == "identity":
                rows[0]["代码"] = "SH600519"
            if mutation == "duplicate":
                rows.append(dict(rows[0]))
            if mutation == "missing":
                rows.pop()
            if mutation == "boolean":
                rows[0]["换手率"] = False
            if mutation == "negative":
                rows[0]["换手率"] = -1
            return rows

        sdk.get_factor_data = data
    with pytest.raises(ProviderError):
        run(sdk, "market_activity", dataset="chip_turnover", dates=["2026-01-05", "2026-01-06"])


@pytest.mark.parametrize(
    "asset,asset_type", [("000001.SH", "stock"), ("000001.SZ", "index"), ("510300.SH", "etf")]
)
def test_closed_stock_data_rejects_indexes_and_funds(asset, asset_type):
    with pytest.raises(ProviderError, match="tinysoft_asset_type_unsupported"):
        run(SDK(), "market_snapshot", assets=[asset], asset_type=asset_type)


def test_financial_tables_join_only_same_report_and_publication_and_keep_zero():
    sdk = SDK()
    result = run(sdk, statements=["indicators"], periods=[])
    row = result.rows[-1]
    assert row["report_period"] == "2026-06-30"
    assert row["roe"] == 0 and row["revenue"] == 0 and row["net_profit"] == -2
    assert row["gross_profit_margin"] == 40
    assert result.fields["revenue"]["unit"] == "元"
    assert result.fields["revenue"]["currency"] is None
    assert result.fields["roe"]["unit"] == "percent"
    assert all("start" not in call[2] for call in sdk.calls)


def test_mismatched_publications_do_not_silently_combine_financial_versions():
    sdk = SDK()
    sdk.tables["合并利润表"][0]["公布日"] = 20260821
    result = run(sdk, statements=["indicators"], periods=[])
    assert not any(
        row.get("roe") is not None and row.get("revenue") is not None for row in result.rows
    )


def test_future_disclosures_are_excluded_and_metadata_unit_drift_is_rejected():
    sdk = SDK()
    sdk.tables["主要财务指标"][0]["公布日"] = 20990101
    result = run(sdk, statements=["indicators"], periods=[])
    assert not any(row.get("roe") is not None for row in result.rows)
    sdk.list_table_fields = lambda *args, **kwargs: [
        {"字段名称": name, "单位": "万元"} for name in TABLES["合并利润表"]["fields"]
    ]
    with pytest.raises(ProviderError):
        run(sdk, statements=["indicators"], periods=[])


def test_holder_details_select_latest_report_and_compare_only_same_holder():
    result = run(SDK(), "market_activity", dataset="holder_details")
    assert len(result.rows) == 10
    assert result.rows[0]["shareholder_name"] == "股东1"
    assert result.rows[0]["share_ratio"] == 2
    assert result.rows[0]["change_ratio"] == 1
    assert result.rows[0]["is_state_owned"] is False
    assert result.fields["change_ratio"]["unit"] == "百分点"


def test_holder_identity_conflict_is_not_dropped_or_filled_with_zero():
    sdk = SDK()
    sdk.tables["十大股东"].append({**sdk.tables["十大股东"][-1], "名称": "另一个人"})
    with pytest.raises(ProviderError, match="conflict"):
        run(sdk, "market_activity", dataset="holder_details")
    sdk = SDK()
    sdk.tables["十大股东"][-1]["名称"] = "新进入股东"
    assert run(sdk, "market_activity", dataset="holder_details").rows[-1]["change_ratio"] is None


def test_margin_stock_units_and_industry_classification_remain_explicit():
    sdk = SDK()
    margin = run(
        sdk,
        "market_activity",
        dataset="margin_trading",
        start_date="2026-10-01",
        end_date="2026-10-21",
    )
    assert margin.rows[0]["financing_balance"] == 0
    assert margin.fields["securities_lending_volume"]["unit"] == "share"
    industry = run(sdk, "market_activity", dataset="industry")
    assert industry.rows[0]["sw_level_1"] == "申万电子"
    assert industry.rows[0].get("industry_pe") is None


def test_snapshot_distinguishes_pb_bases_and_keeps_same_day_share_evidence():
    result = run(
        SDK(),
        "market_snapshot",
        assets=["000001.SZ"],
        fields=["pe_ttm", "pb", "pb_mrq", "ps_ttm", "total_shares"],
    )
    row = result.rows[0]
    assert (row["pe_ttm"], row["pb"], row["pb_mrq"], row["ps_ttm"]) == (0, 1, 2, 3)
    assert row["date"] == "2026-10-21" and row["total_shares"] == 100
    assert result.fields["pb"]["basis"] == "PBLF"
    assert result.fields["total_shares"]["unit"] == "share"
    assert row["market_cap"] == 0.1 and result.fields["market_cap"]["unit"] == "万元"
    assert result.fields["market_cap"]["currency"] is None


def test_events_are_source_titles_and_types_without_generated_impacts():
    result = run(
        SDK(), "market_activity", dataset="events", start_date="2026-10-01", end_date="2026-10-21"
    )
    assert result.rows[0]["summary"] == "合成公告"
    assert result.rows[0]["event_type"] == "工作规程"
    assert result.rows[0]["publish_date"] == "2026-10-21"
    assert "impact_direction" not in result.rows[0]


def test_structured_queries_reject_foreign_assets_and_secret_reflection():
    sdk = SDK()
    sdk.tables["股票基本信息"][0]["CODE"] = "SH600519"
    with pytest.raises(ProviderError, match="identity"):
        run(sdk, "market_activity", dataset="industry")
    sdk = SDK()
    sdk.tables["股票基本信息"][0]["申万一级行业"] = "synthetic-token"
    with pytest.raises(ProviderError, match="credential_reflection"):
        run(sdk, "market_activity", dataset="industry")


@pytest.mark.asyncio
async def test_full_directory_more_than_5000_names_uses_bounded_serial_batches(monkeypatch):
    from app.research_web.datahub import providers_cjpy as provider

    sdk = SDK()
    batches = []
    sdk.get_stocks = lambda **kwargs: [f"SZ{code:06d}" for code in range(5501)]
    definitions = sdk.list_factors()
    sdk.list_factors = lambda **kwargs: [
        *definitions,
        {
            "因子名称": "复权因子",
            "公式": "stock_Adjust_ForwardPriceFactor_Cal(EndT,firstday(), 1)",
            "说明": "",
        },
        {"因子名称": "上市日期", "公式": "datetostr(Firstday())", "说明": ""},
    ]

    def names(**kwargs):
        batches.append(len(kwargs["code"]))
        return [
            {
                "代码": code,
                "名称": f"合成{code}",
                "截止日": kwargs["date"].replace("-", ""),
                "上市日期": "2000-01-01",
            }
            for code in kwargs["code"]
        ]

    sdk.get_factor_data = names
    monkeypatch.setitem(sys.modules, "cjpy", sdk)
    monkeypatch.setattr(provider, "_client", lambda token: SimpleNamespace(close=lambda: None))
    result = await provider.fetch_directory("synthetic-token")
    assert result["total_count"] == 5501
    assert len(result["items"]) == 5501 and result["items"][-1]["asset"] == "005500.SZ"
    assert batches == [500] * 11 + [1]
    assert not provider.active_futures()


@pytest.mark.asyncio
async def test_actual_broker_and_provider_dispatch_structured_data(monkeypatch):
    from app.research_web.datahub import catalog
    from app.research_web.datahub import providers_cjpy as provider
    from app.research_web.datahub.broker import resolve

    sdk = SDK()
    monkeypatch.setattr(catalog, "_dependency_status", lambda *_: (True, None))
    monkeypatch.setitem(sys.modules, "cjpy", sdk)
    monkeypatch.setattr(provider, "_client", lambda token: SimpleNamespace(close=lambda: None))
    request = BusinessQuery(
        capability="financials",
        parameters={"asset": "000001.SZ", "statements": ["indicators"], "periods": []},
    )
    resolution = resolve(
        request,
        environ={},
        connection_statuses={"tinysoft": {"configured": True, "secret_configured": True}},
    )
    assert resolution.provider_id == "tinysoft"
    result = await provider.fetch(resolution.query, token="synthetic-token")
    assert result.status == "complete" and result.rows[0]["revenue"] == 0
    assert len(result.raw) > 2 and result.metadata["asset_table_contract"]
