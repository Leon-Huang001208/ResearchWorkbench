"""Business-only queries; no provider endpoints, paths, sessions or credentials."""

import hashlib
import json
from datetime import UTC, date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .adjustment_contract import validate_adjustment_parameters

SCHEMA_VERSION = "1.0.0"
RAW_STOCK_SEMANTICS = "cn_stock_daily_cny_share_v1"
SOURCES = {
    "fund_nav": "基金净值",
    "cls_telegraph": "财联社电报",
    "fund_profile": "基金基本资料",
    "fund_distributions": "基金分红",
    "fund_holdings": "基金披露持仓",
    "tinysoft": "天软",
    "mysql": "用户 MySQL 数据库",
}

DataCapabilityId = Literal[
    "external_data",
    "search_assets",
    "trading_calendar",
    "market_bars",
    "market_snapshot",
    "index_data",
    "financials",
    "market_activity",
    "factor_macro",
    "fund_data",
    "search_news",
    "search_announcements",
    "search_research",
    "search_web",
    "database_schema",
    "table_query",
]

DATA_CAPABILITIES: tuple[DataCapabilityId, ...] = (
    "external_data",
    "search_assets",
    "trading_calendar",
    "market_bars",
    "market_snapshot",
    "index_data",
    "financials",
    "market_activity",
    "factor_macro",
    "fund_data",
    "search_news",
    "search_announcements",
    "search_research",
    "search_web",
    "database_schema",
    "table_query",
)

CAPABILITY_PARAMETERS = {
    "external_data": {"dataset", "arguments_json", "limit"},
    "search_assets": {"query", "market", "asset_type"},
    "trading_calendar": {"market", "start_date", "end_date"},
    "market_bars": {
        "asset",
        "asset_type",
        "start_date",
        "end_date",
        "frequency",
        "adjustment",
    },
    "market_snapshot": {"assets", "asset_type", "fields"},
    "index_data": {"index", "dataset", "date"},
    "financials": {"asset", "statements", "periods"},
    "market_activity": {"asset", "dataset", "start_date", "end_date"},
    "factor_macro": {"series", "assets", "dates", "start_date", "end_date"},
    "fund_data": {"dataset", "code", "start_date", "end_date", "year", "limit"},
    "search_news": {"query", "limit", "start_date", "end_date"},
    "search_announcements": {"asset", "query", "start_date", "end_date"},
    "search_research": {"query", "document_type", "limit"},
    "search_web": {"query", "limit"},
    "database_schema": {"database", "table"},
    "table_query": {"database", "table", "columns", "filters", "order_by", "offset", "limit"},
}

BUSINESS_TOOLS = {
    capability: (
        f"datahub_{capability}" if capability.startswith("search_") else f"datahub_get_{capability}"
    )
    for capability in DATA_CAPABILITIES
}
BUSINESS_TOOLS["table_query"] = "datahub_query_table"


class DatabaseSchemaParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    database: str | None = Field(default=None, min_length=1, max_length=128)
    table: str | None = Field(default=None, min_length=1, max_length=128)

    @model_validator(mode="after")
    def ordered_scope(self):
        if self.table and not self.database:
            raise ValueError("查询表结构前必须指定数据库")
        return self


class TableFilter(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    column: str = Field(min_length=1, max_length=128)
    operator: Literal["eq", "ne", "lt", "lte", "gt", "gte", "in", "between", "is_null", "not_null"]
    value: Any = None

    @model_validator(mode="after")
    def valid_value(self):
        if self.operator == "in" and (
            not isinstance(self.value, list) or not 1 <= len(self.value) <= 100
        ):
            raise ValueError("IN 必须包含 1 到 100 个值")
        if self.operator == "between" and (
            not isinstance(self.value, list) or len(self.value) != 2
        ):
            raise ValueError("BETWEEN 必须包含两个值")
        if self.operator not in {"in", "between", "is_null", "not_null"} and isinstance(
            self.value, (dict, list)
        ):
            raise ValueError("比较值必须是标量")
        return self


class TableOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    column: str = Field(min_length=1, max_length=128)
    direction: Literal["asc", "desc"] = "asc"


class TableQueryParameters(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    database: str = Field(min_length=1, max_length=128)
    table: str = Field(min_length=1, max_length=128)
    columns: list[str] = Field(min_length=1, max_length=200)
    filters: list[TableFilter] = Field(default_factory=list, max_length=20)
    order_by: list[TableOrder] = Field(default_factory=list, max_length=5)
    offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=500, ge=1, le=5000)


class Query(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Literal[
        "fund_nav", "cls_telegraph", "fund_profile", "fund_distributions", "fund_holdings"
    ]
    code: str | None = Field(default=None, pattern=r"^[0-9]{6}$")
    limit: int = Field(default=30, ge=1, le=100, strict=True)
    start_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    end_date: str | None = Field(default=None, pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    year: int | None = Field(default=None, ge=1990, strict=True)
    refresh: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def valid_business_query(self):
        if (self.source == "cls_telegraph") != (self.code is None):
            raise ValueError("基金代码必填；资讯不接受基金代码")
        if bool(self.start_date) != bool(self.end_date):
            raise ValueError("起止日期必须成对")
        if self.start_date and self.end_date:
            start, end = date.fromisoformat(self.start_date), date.fromisoformat(self.end_date)
            if (
                self.source != "fund_nav"
                or start > end
                or end > datetime.now(ZoneInfo("Asia/Shanghai")).date()
            ):
                raise ValueError("日期范围非法或包含未来")
            if (end.year - start.year, end.month, end.day) > (10, start.month, start.day):
                raise ValueError("日期范围最多十年")
        if self.year is not None and (
            self.source != "fund_holdings"
            or self.year > datetime.now(ZoneInfo("Asia/Shanghai")).year
        ):
            raise ValueError("持仓年份非法")
        return self

    def fingerprint(self, *, include_refresh=False):
        value = self.model_dump(exclude=set() if include_refresh else {"refresh"})
        return hashlib.sha256(
            json.dumps([SCHEMA_VERSION, value], sort_keys=True).encode()
        ).hexdigest()


class InternalCancel(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    call_id: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:-]+$")


class BusinessQuery(BaseModel):
    """Stable DSH-facing request; provider selection stays inside DataHub."""

    model_config = ConfigDict(extra="forbid")

    capability: DataCapabilityId
    source: str = Field(default="auto", min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    allow_fallback: bool = Field(default=False, strict=True)
    parameters: dict[str, Any] = Field(default_factory=dict)
    refresh: bool = Field(default=False, strict=True)
    purpose: Literal["display", "research", "backtest"] = "research"
    quality: Literal["strict", "allow_stale"] = "strict"
    as_of: datetime | None = None
    required_semantics: Literal["cn_stock_daily_cny_share_v1"] | None = None

    @model_validator(mode="after")
    def safe_parameters(self):
        if self.required_semantics is not None:
            from .providers import ProviderError, cn_stock_identity

            if (
                self.capability != "market_bars"
                or self.parameters.get("asset_type") != "stock"
                or self.parameters.get("frequency") != "daily"
                or self.parameters.get("adjustment") != "none"
            ):
                raise ValueError("规范原始日线合同仅支持明确沪深股票daily/none")
            try:
                cn_stock_identity(self.parameters.get("asset"))
            except ProviderError as exc:
                raise ValueError("规范原始日线合同证券身份非法") from exc
        if self.quality == "allow_stale" and self.purpose != "display":
            raise ValueError("只有展示查询可以显式接受陈旧数据")
        if self.as_of is not None and self.as_of.tzinfo is None:
            raise ValueError("历史时点必须包含时区")
        if self.as_of is not None and self.as_of > datetime.now(UTC):
            raise ValueError("历史时点不能位于未来")
        if self.purpose == "backtest" and self.as_of is None:
            raise ValueError("正式回测必须明确历史时点")
        if len(self.parameters) > 20:
            raise ValueError("业务参数过多")
        forbidden = {
            "url",
            "headers",
            "credential",
            "credentials",
            "api_key",
            "token",
            "module",
            "path",
        }
        if forbidden.intersection(self.parameters):
            raise ValueError("业务参数不能包含地址、凭据、模块或路径")
        unexpected = set(self.parameters).difference(CAPABILITY_PARAMETERS[self.capability])
        if unexpected:
            raise ValueError("业务参数不属于该数据能力")
        encoded = json.dumps(self.parameters, ensure_ascii=False, sort_keys=True, default=str)
        if len(encoded.encode()) > 32 * 1024:
            raise ValueError("业务参数过大")
        if self.capability == "database_schema":
            DatabaseSchemaParameters.model_validate(self.parameters)
        elif self.capability == "table_query":
            TableQueryParameters.model_validate(self.parameters)
            if self.source not in {"auto", "mysql"}:
                raise ValueError("表查询仅支持已配置的 MySQL 来源")
        elif self.capability == "factor_macro":
            if self.source == "tinysoft":
                validate_adjustment_parameters(self.parameters)
            elif "dates" in self.parameters and self.source != "auto":
                raise ValueError("显式日期因子查询仅支持天软")
        return self

    def fingerprint(self, *, include_refresh=False):
        value = self.model_dump(exclude=set() if include_refresh else {"refresh"})
        # Existing receipts are immutable: default policy retains the v1 digest.
        for key, default in (
            ("purpose", "research"),
            ("quality", "strict"),
            ("as_of", None),
            ("required_semantics", None),
        ):
            if value.get(key) == default:
                value.pop(key, None)
        if self.as_of is not None:
            value["as_of"] = self.as_of.isoformat()
        return hashlib.sha256(
            json.dumps(["business-1.0.0", value], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


class InternalBusinessQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    call_id: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:-]+$")
    query: BusinessQuery
