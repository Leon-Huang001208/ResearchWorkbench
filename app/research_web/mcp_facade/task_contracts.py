"""Business tools translate fixed contracts, never caller-selected providers."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from ..datahub.contracts import BusinessQuery
from ..datahub.providers import ProviderError, cn_stock_identity

log = get_logger(__name__)


def stock_identity(value):
    try:
        if cn_stock_identity(value) != value:
            raise ValueError("invalid_asset")
    except ProviderError:
        raise ValueError("invalid_asset") from None


class TaskArguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    request_id: str = Field(pattern=r"^[A-Za-z0-9_.:-]{1,64}$")


class StockKline(TaskArguments):
    asset: str
    start_date: str
    end_date: str
    frequency: Literal["daily"] = "daily"
    adjustment: Literal["none"] = "none"


class StockQuote(TaskArguments):
    assets: list[str] = Field(min_length=1, max_length=20)
    fields: list[
        Literal["price", "change_pct", "volume", "turnover", "pe_ttm", "pb", "total_shares"]
    ] = Field(default_factory=lambda: ["price"])


class StockFinancials(TaskArguments):
    asset: str
    dataset: Literal["summary", "income_statement", "profitability", "cash_flow"]
    periods: list[str] | int | None = None


class StockActivity(TaskArguments):
    asset: str
    dataset: Literal["fund_flow", "margin_trading", "holder_data", "holder_details", "block_trade"]
    start_date: str | None = None
    end_date: str | None = None


class FundDetail(TaskArguments):
    code: str = Field(pattern=r"^[0-9]{6}$")
    dataset: Literal["nav", "profile", "distributions", "holdings"]
    start_date: str | None = None
    end_date: str | None = None
    year: int | None = Field(default=None, ge=1990)
    limit: int = Field(default=30, ge=1, le=100)


class IndexQuote(TaskArguments):
    index: str = Field(pattern=r"^[A-Za-z0-9]{1,12}\.[A-Z]{2,4}$")
    date: str | None = None


class EconomicSeries(TaskArguments):
    series: Literal["cn_cpi", "cn_gdp", "cn_pmi", "cn_m2"]
    start_date: str | None = None
    end_date: str | None = None


class SearchAssets(TaskArguments):
    query: str = Field(min_length=1, max_length=128)
    asset_type: Literal["stock", "fund", "index"] = "stock"
    market: Literal["CN"] = "CN"


class TradingCalendar(TaskArguments):
    market: Literal["CN"] = "CN"
    start_date: str
    end_date: str


TASKS = {
    "get_stock_kline": (
        "stock_data",
        "market_bars",
        StockKline,
        "获取截至昨日的单只沪深 A 股不复权日 K 线及真实成交量额；当日数据使用get_stock_quote，复权尚未开放。",
    ),
    "get_stock_quote": (
        "stock_data",
        "market_snapshot",
        StockQuote,
        "获取最多20只 A 股最新可得行情快照，注明来源时间精度。",
    ),
    "get_stock_financials": (
        "stock_data",
        "financials",
        StockFinancials,
        "获取财务摘要、披露利润表、盈利指标或现金流比率，不能将比率当作现金流量表。",
    ),
    "get_stock_activity": (
        "stock_data",
        "market_activity",
        StockActivity,
        "获取个股资金流、两融、股东或大宗交易，按 dataset 区分口径。",
    ),
    "get_fund_detail": (
        "fund_data",
        "fund_data",
        FundDetail,
        "获取基金净值、档案、分红或已披露持仓。",
    ),
    "get_index_quote": (
        "index_data",
        "index_data",
        IndexQuote,
        "获取单个指数单日快照；不提供指数区间 K 线。",
    ),
    "get_economic_series": (
        "economic_data",
        "factor_macro",
        EconomicSeries,
        "获取 CPI同比、GDP累计同比、制造业PMI或M2同比。",
    ),
    "search_assets": (
        "shared",
        "search_assets",
        SearchAssets,
        "按名称或代码查证券身份；不是条件选股。",
    ),
    "get_trading_calendar": (
        "shared",
        "trading_calendar",
        TradingCalendar,
        "查询权威已发布的开市与休市日期，未知日历不能推断。",
    ),
}


def business_query(name: str, arguments: dict) -> tuple[str, BusinessQuery]:
    if name not in TASKS:
        raise ValueError("unknown_business_tool")
    _, capability, schema, _ = TASKS[name]
    values = schema.model_validate(arguments).model_dump(exclude_none=True)
    request_id = values.pop("request_id")
    for key in ("start_date", "end_date", "date"):
        if key in values and date.fromisoformat(values[key]).isoformat() != values[key]:
            raise ValueError("invalid_date_range")
    start, end = values.get("start_date"), values.get("end_date")
    if start and end and start > end:
        raise ValueError("invalid_date_range")
    if capability in {"market_bars", "financials", "market_activity"}:
        stock_identity(values["asset"])
    if capability in {"market_bars", "market_snapshot"}:
        values["asset_type"] = "stock"
    if capability == "market_snapshot":
        assets = values["assets"]
        if len(set(assets)) != len(assets):
            raise ValueError("invalid_asset")
        for asset in assets:
            stock_identity(asset)
    if capability == "financials":
        dataset = values.pop("dataset")
        if dataset != "summary":
            values["statements"] = [dataset]
        periods = values.get("periods")
        if dataset in {"profitability", "cash_flow"} and (
            not isinstance(periods, list) or len(periods) != 1
        ):
            raise ValueError("financial_period_required")
        if dataset == "income_statement" and (
            (type(periods) is int and not 1 <= periods <= 8)
            or (isinstance(periods, list) and len(periods) > 8)
        ):
            raise ValueError("financial_period_limit")
    if capability == "index_data":
        values["dataset"] = "quotes"
    if (
        capability == "market_bars"
        and end
        and end > datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    ):
        raise ValueError("future_provider_date")
    if (
        capability == "market_bars"
        and end == datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    ):
        raise ValueError("daily_history_requires_prior_session")
    log.info("mcp_business_query_validated", tool=name, capability=capability)
    return request_id, BusinessQuery(
        capability=capability,
        parameters=values,
        required_semantics=("cn_stock_daily_cny_share_v1" if capability == "market_bars" else None),
    )
