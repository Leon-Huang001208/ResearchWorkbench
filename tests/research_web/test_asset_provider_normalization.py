"""Chinese source columns retain raw evidence and acquire explicit projections."""

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers_akshare import _normalize_activity, _normalize_financials


def test_fund_flow_maps_real_net_columns_without_inventing_gross_flows():
    query = BusinessQuery(
        capability="market_activity", parameters={"asset": "603986.SH", "dataset": "fund_flow"}
    )
    source = {
        "日期": "2026-10-21",
        "主力净流入-净额": 0,
        "超大单净流入-净额": -2,
        "大单净流入-净额": 3,
        "中单净流入-净额": 4,
        "小单净流入-净额": -5,
    }
    row = _normalize_activity([source], query)[0]
    assert [
        row[name] for name in ["main_net", "super_net", "large_net", "medium_net", "small_net"]
    ] == [0, -2, 3, 4, -5]
    assert row["主力净流入-净额"] == 0
    assert "main_inflow" not in row and "main_outflow" not in row and "flow_partition" not in row


def test_financial_source_units_period_and_zero_are_normalized_without_pe_invention():
    query = BusinessQuery(
        capability="financials", parameters={"asset": "603986.SH", "statements": ["indicators"]}
    )
    source = {
        "报告期": "20260630",
        "营业总收入": "1.2亿元",
        "净利润": "0元",
        "净资产收益率": "0%",
        "销售毛利率": "50%",
        "PE": 10,
    }
    row = _normalize_financials([source], query)[0]
    assert row["report_period"] == "2026-06-30"
    assert row["revenue"] == 120000000 and row["net_profit"] == 0
    assert row["roe"] == 0 and row["gross_profit_margin"] == 50
    assert row["营业总收入"] == "1.2亿元" and "pe_ttm" not in row


def test_financial_unqualified_money_does_not_receive_an_assumed_unit():
    query = BusinessQuery(capability="financials", parameters={"asset": "603986.SH"})
    row = _normalize_financials(
        [{"报告期": "2026-06-30", "营业总收入": 123, "净利润": False}], query
    )[0]
    assert row.get("revenue") is None and row["营业总收入"] == 123
    assert row.get("net_profit") is None and row["净利润"] is None
