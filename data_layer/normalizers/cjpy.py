"""Lossless CJPY source rows plus conservative, typed fact normalization."""

from __future__ import annotations

import math
import re
from datetime import date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

from core.contracts.datahub import CATALOG_DATASETS
from core.observability import get_logger

logger = get_logger(__name__)
SHANGHAI = ZoneInfo("Asia/Shanghai")
ADJUSTMENTS = {
    "前复权": "forward",
    "后复权": "backward",
    "不复权": "none",
    "forward": "forward",
    "backward": "backward",
    "none": "none",
}


def canonical_code(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    match = re.fullmatch(r"(SH|SZ|BJ|OF)(\d{6})", text)
    if match:
        return f"{match[2]}.{match[1]}"
    return text if re.fullmatch(r"\d{6}\.(SH|SZ|BJ|OF)", text) else None


def json_value(value: Any) -> Any:
    """Strict JSON projection; the original response remains in the raw artifact."""
    if isinstance(value, dict):
        return {str(k): json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def parse_time(value: Any, clock: Any = None) -> datetime:
    text = str(value).strip()
    if re.fullmatch(r"\d{8}", text):
        parsed = datetime.strptime(text, "%Y%m%d")
    else:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if clock is not None:
        clock_text = str(clock).strip()
        if re.fullmatch(r"\d{6}", clock_text):
            clock_text = f"{clock_text[:2]}:{clock_text[2:4]}:{clock_text[4:]}"
        parsed = datetime.combine(parsed.date(), time.fromisoformat(clock_text))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI)


def first(row: dict, *keys: str) -> Any:
    return next((row[k] for k in keys if row.get(k) is not None and row[k] != ""), None)


def normalize_row(dataset: str, row: dict, params: dict, observed_at: datetime) -> dict:
    """Never infer a financial unit, historical publication time, or asset class."""
    flags: list[str] = []
    source = json_value(row)
    if any(isinstance(v, float) and not math.isfinite(v) for v in row.values()):
        flags.append("non_finite_value")
    symbol = canonical_code(first(row, "code", "CODE", "代码", "证券代码", "value"))
    supplied_codes = [canonical_code(row[k]) for k in ("code", "CODE", "代码", "证券代码") if row.get(k)]
    requested = {canonical_code(c) for c in params.get("codes", [])}
    if (
        dataset != "index_constituents"
        and supplied_codes
        and (
            len(set(supplied_codes)) > 1
            or (requested and any(code not in requested for code in supplied_codes))
        )
    ):
        flags.append("asset_code_mismatch")
    if symbol is None and len(params.get("codes", [])) == 1 and dataset != "index_constituents":
        symbol = canonical_code(params["codes"][0])
    if (
        dataset not in CATALOG_DATASETS
        and dataset not in {"trading_days", "macro_data"}
        and symbol is None
    ):
        flags.append("unresolved_asset_code")
    date_value = first(
        row, params.get("date_field", "date"), "trade_date", "日期", "截止日", "时间", "time", "公布日", "报告期"
    )
    if dataset == "trading_days":
        date_value = row.get("value")
    if dataset in {"index_constituents", "stock_list", "fund_list", "codes"}:
        date_value = params.get("date")
        if date_value == "all":
            date_value = None
            flags.append("unbounded_universe_date")
        elif date_value is None:
            date_value = observed_at.astimezone(SHANGHAI).date().isoformat()
    as_of = observed_at
    if params.get("date_field") == "__observed_at__":
        date_value = observed_at.isoformat()
    if date_value is not None:
        try:
            as_of = parse_time(
                date_value, row.get("time") if date_value != row.get("time") else None
            )
        except (ValueError, TypeError):
            flags.append("invalid_date")
    elif dataset in {"daily_quotes", "factor_data", "table_data", "macro_data"}:
        flags.append("missing_business_date")
    if dataset == "daily_quotes" and date_value is not None:
        start, end = params.get("start_date"), params.get("end_date")
        if (start and as_of.date() < date.fromisoformat(start)) or (
            end and as_of.date() > date.fromisoformat(end)
        ):
            flags.append("outside_requested_range")
        if as_of > observed_at:
            flags.append("future_observation")
    if dataset == "factor_data" and date_value is not None:
        dates = params.get("dates") or ([params["date"]] if params.get("date") else [])
        if dates and as_of.date() not in {date.fromisoformat(x) for x in dates}:
            flags.append("outside_requested_dates")
    payload = {"source_fields": source}
    units = dict(params.get("column_units", {}))
    cycle = params.get("cycle", "day")
    cycle = "day" if cycle == "D" else cycle
    if dataset == "daily_quotes":
        adjustment = ADJUSTMENTS.get(params.get("rate", "前复权"))
        if adjustment is None:
            flags.append("unknown_adjustment")
        if cycle not in {"day", "D"} and not (
            row.get("time") or (date_value and ("T" in str(date_value) or ":" in str(date_value)))
        ):
            flags.append("missing_intraday_time")
        for key, aliases in {
            "open": ("open", "开盘价"),
            "high": ("high", "最高价"),
            "low": ("low", "最低价"),
            "close": ("close", "price", "收盘价"),
            "volume": ("vol", "volume", "成交量"),
            "amount": ("amount", "成交额"),
        }.items():
            value = first(source, *aliases)
            if value is not None:
                try:
                    value = float(value)
                    if not math.isfinite(value):
                        raise ValueError("nonfinite")
                except (ValueError, TypeError):
                    flags.append(f"invalid_{key}")
                    value = None
            payload[key] = value
        if payload["close"] is None:
            flags.append("missing_close")
        if (
            payload.get("high") is not None
            and payload.get("low") is not None
            and payload["high"] < payload["low"]
        ):
            flags.append("invalid_ohlc")
        for key in ("open", "high", "low", "close", "volume", "amount"):
            if payload[key] is not None and payload[key] < 0:
                flags.append(f"negative_{key}")
        for key in ("open", "close"):
            if payload[key] is not None and (
                (payload["high"] is not None and payload[key] > payload["high"])
                or (payload["low"] is not None and payload[key] < payload["low"])
            ):
                flags.append("invalid_ohlc")
        payload.update(cycle=cycle, adjustment=adjustment, trade_date=as_of.date().isoformat())
        # Stock-specific units are assigned only after canonical identity validation.
        payload["missing_reasons"] = {
            key: "source_missing"
            for key in ("open", "high", "low", "close", "volume", "amount")
            if payload[key] is None
        }
    elif dataset in {"factor_data", "table_data", "macro_data"}:
        # Numeric columns require verified catalog units or explicitly reviewed import units.
        date_keys = {
            "date",
            "trade_date",
            "日期",
            "截止日",
            "time",
            "时间",
            "公布日",
            "报告期",
            "变动日",
            "CODE",
            "code",
            "代码",
            "证券代码",
            params.get("date_field"),
        }
        for key, value in source.items():
            if (
                key not in date_keys
                and isinstance(value, (float, int))
                and not isinstance(value, bool)
                and not units.get(key)
            ):
                flags.append(f"missing_unit:{key}")
    if flags:
        logger.warning("cjpy row quarantined", dataset=dataset, flags=flags)
    return {
        "symbol": symbol,
        "as_of": as_of,
        "observed_at": observed_at,
        "available_at": observed_at,
        "freshness_status": "quarantined" if flags else "fresh",
        "quality_flags": sorted(set(flags)),
        "payload": payload,
        "units": units,
    }
