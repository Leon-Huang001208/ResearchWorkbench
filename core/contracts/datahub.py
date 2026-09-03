"""Bounded, credential-free DataHub query and ingestion contracts."""

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

DATASETS = {
    "universes": ("证券板块目录", "list_universes", ()),
    "code_mappings": ("代码映射", "list_code_mappings", ()),
    "market_fields": ("行情字段", "list_market_fields", ()),
    "tables": ("数据表目录", "list_tables", ()),
    "table_fields": ("表字段", "list_table_fields", ("table_name",)),
    "factors": ("因子目录", "list_factors", ()),
    "macro_tables": ("宏观表目录", "list_macro_tables", ()),
    "macro_indicators": ("宏观指标目录", "list_macro_indicators", ()),
    "codes": ("板块证券", "get_codes", ("universe",)),
    "stock_list": ("股票列表", "get_stocks", ()),
    "fund_list": ("基金列表", "get_funds", ()),
    "index_constituents": ("指数成分", "get_index_constituents", ("codes", "date")),
    "trading_days": ("交易日", "get_trading_days", ("start_date", "end_date")),
    "daily_quotes": ("日线／分钟行情", "get_market_data", ("codes", "start_date", "end_date")),
    "factor_data": ("因子截面", "get_factor_data", ("codes", "factors")),
    "table_data": ("结构化表格", "get_table_data", ("codes", "table_name")),
    "macro_data": ("宏观时间序列", "get_macro_data", ("indicator",)),
}
CATALOG_DATASETS = frozenset(
    {
        "universes",
        "code_mappings",
        "market_fields",
        "tables",
        "table_fields",
        "factors",
        "macro_tables",
        "macro_indicators",
    }
)
PARAMETERS = frozenset(
    {
        "codes",
        "start_date",
        "end_date",
        "date",
        "dates",
        "cycle",
        "rate",
        "fields",
        "factors",
        "repo",
        "table_name",
        "universe",
        "indicator",
        "column_units",
        "date_field",
    }
)


class DataHubSyncRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: Literal["cjpy"] = "cjpy"
    dataset: str
    params: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(min_length=1, max_length=128, default=None)

    @model_validator(mode="after")
    def check_parameters(self):
        self.params = {key: value for key, value in self.params.items() if value is not None}
        if self.dataset not in DATASETS:
            raise ValueError("Unknown CJPY dataset")
        if set(self.params) - PARAMETERS:
            raise ValueError("Unsupported query parameter")
        for key in DATASETS[self.dataset][2]:
            if not self.params.get(key):
                raise ValueError(f"{key} is required")
        for key in ("codes", "factors", "fields", "dates"):
            value = self.params.get(key)
            if value is not None and (
                not isinstance(value, list)
                or not value
                or len(value) > 1000
                or any(not isinstance(x, str) or not x.strip() or len(x) > 1000 for x in value)
            ):
                raise ValueError(f"{key} must be a non-empty string list of at most 1000 items")
        for key in ("start_date", "end_date", "date"):
            value = self.params.get(key)
            if value is not None and not (
                key == "date" and value == "all" and self.dataset == "stock_list"
            ):
                if not isinstance(value, str):
                    raise ValueError(f"Invalid {key}")
                date.fromisoformat(value)
        for value in self.params.get("dates") or []:
            date.fromisoformat(value)
        start, end = self.params.get("start_date"), self.params.get("end_date")
        if start and end and date.fromisoformat(start) > date.fromisoformat(end):
            raise ValueError("start_date must not follow end_date")
        if self.dataset == "factor_data" and not (
            self.params.get("dates") or self.params.get("date")
        ):
            raise ValueError("factor_data requires date or dates")
        for key in ("repo", "column_units"):
            value = self.params.get(key)
            if value is not None and (
                not isinstance(value, dict)
                or any(
                    not isinstance(k, str) or not isinstance(v, str) or not v.strip()
                    for k, v in value.items()
                )
            ):
                raise ValueError(f"{key} must map names to non-empty strings")
        for key in ("cycle", "rate", "table_name", "universe", "indicator", "date_field"):
            value = self.params.get(key)
            if value is not None and (
                not isinstance(value, str) or not value.strip() or len(value) > 1000
            ):
                raise ValueError(f"Invalid {key}")
        return self


class DataHubQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    source: Literal["cjpy"] = "cjpy"
    dataset: str
    snapshot_id: str | None = None
    fact_id: str | None = None
    symbol: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    cycle: str | None = None
    adjustment: Literal["forward", "backward", "none"] | None = None
    table_name: str | None = None
    indicator: str | None = None
    fields: list[str] | None = Field(default=None, max_length=100)
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def known_dataset(self):
        if self.dataset not in DATASETS:
            raise ValueError("Unknown dataset")
        if self.symbol is not None and not re.fullmatch(
            r"(?i)(?:(?:SH|SZ|BJ|OF)\d{6}|\d{6}\.(?:SH|SZ|BJ|OF))", self.symbol
        ):
            raise ValueError("Symbol must include its market")
        if self.snapshot_id is not None and not re.fullmatch(r"[a-f0-9]{64}", self.snapshot_id):
            raise ValueError("Invalid snapshot ID")
        if self.fact_id is not None and not re.fullmatch(r"[a-f0-9]{64}:\d+", self.fact_id):
            raise ValueError("Invalid fact ID")
        if (
            self.fact_id
            and self.snapshot_id
            and not self.fact_id.startswith(self.snapshot_id + ":")
        ):
            raise ValueError("Conflicting fact and snapshot IDs")
        for value in (self.start_date, self.end_date):
            if value is not None:
                date.fromisoformat(value)
        if (
            self.start_date
            and self.end_date
            and date.fromisoformat(self.start_date) > date.fromisoformat(self.end_date)
        ):
            raise ValueError("Invalid date range")
        return self


class DataHubCitationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    run_id: str = Field(min_length=1, max_length=160)
    project_id: str = Field(min_length=1, max_length=160)
    workspace_id: str = Field(min_length=1, max_length=160)
    dataset: str
    fact_id: str
