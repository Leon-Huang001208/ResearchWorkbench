"""Business tools translate fixed contracts, never caller-selected providers."""

from dataclasses import dataclass
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from core.observability import get_logger

from ..datahub.contracts import BusinessQuery, stock_kline_query, stock_quote_query
from ..datahub.providers import ProviderError, cn_stock_identity
from .domains import DOMAINS, domain, domain_of, validate_domains

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
    dataset: Literal[
        "fund_flow", "margin_trading", "holder_count", "holder_data", "holder_details"
    ] = Field(
        description="holder_count=股东户数；holder_data=前十名股东合计；holder_details=前十名股东明细，不可互相替代。"
    )
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
    index: str = Field(
        pattern=r"^(?:000[0-9]{3}\.SH|93[0-9]{4}\.SH|399[0-9]{3}\.SZ)$",
        description="当前沪深指数范围：000/93开头的.SH、399开头的.SZ；只取最新快照，不接受历史日期。",
    )


class EconomicSeries(TaskArguments):
    series: Literal["cn_cpi", "cn_gdp", "cn_pmi", "cn_m2"] = Field(
        description="CPI当月同比NATIONAL_SAME/GDP累计同比SUM_SAME/制造业PMI MAKE_INDEX/M2同比BASIC_CURRENCY_SAME；返回原生列及字段字典。"
    )
    start_date: str
    end_date: str


class SearchAssets(TaskArguments):
    query: str = Field(min_length=1, max_length=128)
    asset_type: Literal["stock"] = "stock"
    market: Literal["CN"] = "CN"


class TradingCalendar(TaskArguments):
    market: Literal["CN"] = "CN"
    start_date: str
    end_date: str


@dataclass(frozen=True)
class TaskContract:
    """A registered business tool; the catalog domain is derived from ``domains.py``."""

    name: str
    capability: str
    schema: type[TaskArguments]
    description: str
    legacy_domain: str

    @property
    def domain(self) -> str:
        return domain_of(self.name)

    def __iter__(self):
        # Preserve the historical 4-tuple values, including the legacy "shared"
        # catalog prefix, for the existing registration and unpacking callers.
        # ``for name, (domain, _, schema, description) in TASKS.items()``.
        yield self.legacy_domain
        yield self.capability
        yield self.schema
        yield self.description

    def __getitem__(self, index):
        return tuple(self)[index]

    def __len__(self):
        return 4


def _contract(name: str, capability: str, schema: type[TaskArguments], description: str):
    return TaskContract(
        name=name,
        capability=capability,
        schema=schema,
        description=description,
        legacy_domain=(
            "shared" if name in {"search_assets", "get_trading_calendar"} else domain_of(name)
        ),
    )


TASKS = {
    name: _contract(name, capability, schema, description)
    for name, capability, schema, description in (
        (
            "get_stock_kline",
            "market_bars",
            StockKline,
            "获取截至昨日的单只沪深 A 股不复权日 K 线及真实成交量额；当日数据使用get_stock_quote，复权尚未开放。",
        ),
        (
            "get_stock_quote",
            "market_snapshot",
            StockQuote,
            "获取最多20只 A 股最新可得行情快照，注明来源时间精度。",
        ),
        (
            "get_stock_financials",
            "financials",
            StockFinancials,
            "获取财务摘要、披露利润表、盈利指标或现金流比率，不能将比率当作现金流量表。",
        ),
        (
            "get_stock_activity",
            "market_activity",
            StockActivity,
            "获取个股资金流、两融或股东数据。资金流/两融须起止日期且相差少于60天；holder_count是户数，holder_data/details是前十名股东，仅最新报告期。",
        ),
        (
            "get_fund_detail",
            "fund_data",
            FundDetail,
            "获取基金净值、档案、分红或已披露持仓。",
        ),
        (
            "get_index_quote",
            "index_data",
            IndexQuote,
            "获取单个沪深指数最新可得快照；不接受历史日期或区间 K 线。",
        ),
        (
            "get_economic_series",
            "factor_macro",
            EconomicSeries,
            "获取中国CPI全国当月同比、GDP累计同比、制造业PMI或M2同比；必填起止日期，返回原生列及字段字典。",
        ),
        (
            "search_assets",
            "search_assets",
            SearchAssets,
            "按名称或代码查A股身份；当前不支持基金或指数身份检索，不是条件选股。",
        ),
        (
            "get_trading_calendar",
            "trading_calendar",
            TradingCalendar,
            "查询权威已发布的开市与休市日期，未知日历不能推断。",
        ),
    )
}

validate_domains(tuple(TASKS))


def _schema_document(schema: type[TaskArguments]) -> dict:
    document = schema.model_json_schema()
    document.setdefault("properties", {})
    document["additionalProperties"] = False
    return document


def business_directory(
    tool_names: tuple[str, ...] | list[str] | None = None,
    registered_tools: dict | None = None,
) -> dict:
    """Return the seven-domain catalog with every registered tool and its metadata."""

    selected = tuple(TASKS) if tool_names is None else tuple(tool_names)
    unknown = sorted(set(selected) - set(TASKS))
    if unknown:
        log.error("business_directory_tool_unknown", tools=",".join(unknown))
        raise ValueError("unknown_business_tool")
    if len(set(selected)) != len(selected):
        raise ValueError("duplicate_business_tool")
    by_domain = {item.id: [] for item in DOMAINS}
    for name in selected:
        task = TASKS[name]
        registered = (registered_tools or {}).get(name)
        metadata = (
            {
                "name": registered.name,
                "capability": task.capability,
                "description": registered.description,
                "input_schema": registered.input_schema,
            }
            if registered is not None
            else {
                "name": name,
                "capability": task.capability,
                "description": task.description,
                "input_schema": _schema_document(task.schema),
            }
        )
        by_domain[domain_of(name)].append(metadata)
    return {
        "format": "rwb.business_directory.v1",
        "domains": [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "status": item.status,
                "tools": by_domain[item.id],
            }
            for item in DOMAINS
        ],
    }


def domain_metadata(tool: str) -> dict:
    """Per-tool discovery metadata without changing the tool's input JSON Schema."""

    owner = domain(domain_of(tool))
    return {
        "rwb.business": {
            "domain": owner.id,
            "domain_name": owner.name,
            "domain_status": owner.status,
        }
    }


def business_query(name: str, arguments: dict) -> tuple[str, BusinessQuery]:
    if name not in TASKS:
        raise ValueError("unknown_business_tool")
    _, capability, schema, _ = TASKS[name]
    values = schema.model_validate(arguments).model_dump(exclude_none=True)
    request_id = values.pop("request_id")
    if capability == "market_bars":
        return request_id, stock_kline_query(
            values["asset"], values["start_date"], values["end_date"]
        )
    if capability == "market_snapshot":
        # Same shared-contract path as ``get_stock_kline``: identity, count and
        # field membership are validated once, in ``datahub.contracts``.
        return request_id, stock_quote_query(values["assets"], values.get("fields"))
    for key in ("start_date", "end_date", "date"):
        if key in values and date.fromisoformat(values[key]).isoformat() != values[key]:
            raise ValueError("invalid_date_range")
    start, end = values.get("start_date"), values.get("end_date")
    if start and end and start > end:
        raise ValueError("invalid_date_range")
    if capability in {"market_bars", "financials", "market_activity"}:
        stock_identity(values["asset"])
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
    if capability == "factor_macro":
        values["series"] = {
            "cn_cpi": "cpi",
            "cn_gdp": "gdp",
            "cn_pmi": "pmi",
            "cn_m2": "m2",
        }[values["series"]]
    source = "auto"
    if capability == "market_activity":
        if values["dataset"] in {"fund_flow", "margin_trading"}:
            if not start or not end:
                raise ValueError("activity_window_required")
            if (date.fromisoformat(end) - date.fromisoformat(start)).days >= 60:
                raise ValueError("workload_too_large")
        elif start or end:
            raise ValueError("holder_history_not_supported")
        if values["dataset"] == "holder_count":
            values["dataset"], source = "holder_data", "wind"
        elif values["dataset"] in {"holder_data", "holder_details"}:
            source = "tinysoft"
    log.info("mcp_business_query_validated", tool=name, capability=capability)
    return request_id, BusinessQuery(
        capability=capability,
        source=source,
        parameters=values,
    )
