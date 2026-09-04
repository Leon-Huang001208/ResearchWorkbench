"""Business-only queries; no provider endpoints, paths, sessions or credentials."""

import hashlib
import json
from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "1.0.0"
SOURCES = {
    "fund_nav": "基金净值",
    "cls_telegraph": "财联社电报",
    "fund_profile": "基金基本资料",
    "fund_distributions": "基金分红",
    "fund_holdings": "基金披露持仓",
}

DataCapabilityId = Literal[
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
]

DATA_CAPABILITIES: tuple[DataCapabilityId, ...] = (
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
)

CAPABILITY_PARAMETERS = {
    "search_assets": {"query", "market", "asset_type"},
    "trading_calendar": {"market", "start_date", "end_date"},
    "market_bars": {"asset", "start_date", "end_date", "frequency", "adjustment"},
    "market_snapshot": {"assets", "fields"},
    "index_data": {"index", "dataset", "date"},
    "financials": {"asset", "statements", "periods"},
    "market_activity": {"asset", "dataset", "start_date", "end_date"},
    "factor_macro": {"series", "assets", "start_date", "end_date"},
    "fund_data": {"dataset", "code", "start_date", "end_date", "year", "limit"},
    "search_news": {"query", "limit", "start_date", "end_date"},
    "search_announcements": {"asset", "query", "start_date", "end_date"},
    "search_research": {"query", "document_type", "limit"},
    "search_web": {"query", "limit"},
}

BUSINESS_TOOLS = {
    capability: (
        f"datahub_{capability}" if capability.startswith("search_") else f"datahub_get_{capability}"
    )
    for capability in DATA_CAPABILITIES
}


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

    @model_validator(mode="after")
    def safe_parameters(self):
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
        return self

    def fingerprint(self, *, include_refresh=False):
        value = self.model_dump(exclude=set() if include_refresh else {"refresh"})
        return hashlib.sha256(
            json.dumps(["business-1.0.0", value], sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()


class InternalBusinessQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    session_id: str = Field(pattern=r"^[a-f0-9-]{36}$")
    call_id: str = Field(min_length=1, max_length=256, pattern=r"^[a-zA-Z0-9_.:-]+$")
    query: BusinessQuery
