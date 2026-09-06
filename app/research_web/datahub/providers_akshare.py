"""Bounded AKShare provider used by DataHub business contracts only."""

from __future__ import annotations

import asyncio
import json
import math
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_ROWS, ProviderError, Result

log = get_logger(__name__)
DEADLINE = 35


def _symbol(value: str) -> str:
    match = re.fullmatch(r"([0-9]{6})(?:\.(?:SH|SZ|BJ))?", value.upper())
    if not match:
        raise ProviderError("invalid_asset")
    return match.group(1)


def _market_symbol(value: str) -> str:
    symbol = _symbol(value)
    prefix = (
        "sh"
        if symbol.startswith(("5", "6", "9"))
        else "bj" if symbol.startswith(("4", "8")) else "sz"
    )
    return f"{prefix}{symbol}"


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _records(frame) -> list[dict]:
    if frame is None or not hasattr(frame, "to_dict"):
        raise ProviderError("invalid_dataframe")
    rows = frame.to_dict(orient="records")
    if not isinstance(rows, list):
        raise ProviderError("invalid_dataframe")
    return [{str(key): _clean(value) for key, value in row.items()} for row in rows[:MAX_ROWS]]


def _pick(row: dict, *names: str):
    for name in names:
        if name in row:
            return row[name]
    return None


def _date(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().replace("/", "-")
    if re.fullmatch(r"[0-9]{8}", text):
        text = f"{text[:4]}-{text[4:6]}-{text[6:]}"
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", text):
        raise ProviderError("invalid_provider_date")
    return text


def _number(value: Any) -> float | None:
    if value in (None, "", "-", "--"):
        return None
    try:
        number = float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError) as exc:
        raise ProviderError("invalid_provider_number") from exc
    if not math.isfinite(number):
        return None
    return number


def _normalize_assets(rows: list[dict], query: BusinessQuery) -> list[dict]:
    needle = str(query.parameters.get("query", "")).strip().casefold()
    asset_type = query.parameters.get("asset_type", "stock")
    normalized = []
    for row in rows:
        code = str(_pick(row, "code", "证券代码", "代码") or "").strip()
        name = str(_pick(row, "name", "证券简称", "名称") or "").strip()
        if not re.fullmatch(r"[0-9]{6}", code) or not name:
            continue
        if needle and needle not in code.casefold() and needle not in name.casefold():
            continue
        market = "SH" if code.startswith(("5", "6", "9")) else "BJ" if code.startswith(("4", "8")) else "SZ"
        normalized.append(
            {
                "asset_id": f"{code}.{market}",
                "code": code,
                "name": name,
                "market": market,
                "asset_type": asset_type,
            }
        )
    return normalized


def _normalize_bars(rows: list[dict], query: BusinessQuery) -> list[dict]:
    asset = str(query.parameters["asset"]).upper()
    normalized = []
    for row in rows:
        day = _date(_pick(row, "日期", "date"))
        if day is None:
            continue
        normalized.append(
            {
                "asset": asset,
                "date": day,
                "open": _number(_pick(row, "开盘", "open")),
                "close": _number(_pick(row, "收盘", "close")),
                "high": _number(_pick(row, "最高", "high")),
                "low": _number(_pick(row, "最低", "low")),
                "volume": _number(_pick(row, "成交量", "volume")),
                "turnover": _number(_pick(row, "成交额", "amount", "turnover")),
                "turnover_rate_pct": _number(_pick(row, "换手率", "turnover_rate")),
            }
        )
    return normalized


def _normalize_snapshot(rows: list[dict], query: BusinessQuery) -> list[dict]:
    requested = {str(value).split(".")[0] for value in query.parameters.get("assets", [])}
    normalized = []
    for row in rows:
        code = str(_pick(row, "代码", "code") or "").strip()
        if requested and code not in requested:
            continue
        if not re.fullmatch(r"[0-9]{6}", code):
            continue
        market = "SH" if code.startswith(("5", "6", "9")) else "BJ" if code.startswith(("4", "8")) else "SZ"
        normalized.append(
            {
                "asset": f"{code}.{market}",
                "name": _pick(row, "名称", "name"),
                "price": _number(_pick(row, "最新价", "price")),
                "change_pct": _number(_pick(row, "涨跌幅", "change_pct")),
                "volume": _number(_pick(row, "成交量", "volume")),
                "turnover": _number(_pick(row, "成交额", "turnover")),
                "market_cap": _number(_pick(row, "总市值", "market_cap")),
                "pe_ttm": _number(_pick(row, "市盈率-动态", "pe_ttm")),
                "as_of": _pick(row, "as_of") or datetime.now(UTC).isoformat(),
            }
        )
    return normalized


def _normalize_generic(rows: list[dict], query: BusinessQuery) -> list[dict]:
    asset = str(query.parameters.get("asset", "")).upper()
    normalized = []
    for source in rows:
        row = {"asset": asset}
        for key, value in source.items():
            row[str(key)] = value
        normalized.append(row)
    return normalized


def _invoke(query: BusinessQuery):
    import akshare as ak

    capability = query.capability
    parameters = query.parameters
    if capability == "search_assets":
        return ak.stock_info_a_code_name(), _normalize_assets
    if capability == "market_bars":
        adjustment = parameters.get("adjustment", "qfq")
        if parameters.get("frequency", "daily") == "daily":
            return (
                ak.stock_zh_a_daily(
                    symbol=_market_symbol(str(parameters["asset"])),
                    start_date=str(parameters.get("start_date", "")).replace("-", ""),
                    end_date=str(parameters.get("end_date", "")).replace("-", ""),
                    adjust="" if adjustment == "none" else adjustment,
                ),
                _normalize_bars,
            )
        return (
            ak.stock_zh_a_hist(
                symbol=_symbol(str(parameters["asset"])),
                period=parameters.get("frequency", "daily"),
                start_date=str(parameters.get("start_date", "")).replace("-", ""),
                end_date=str(parameters.get("end_date", "")).replace("-", ""),
                adjust="" if adjustment == "none" else adjustment,
            ),
            _normalize_bars,
        )
    if capability == "market_snapshot":
        import pandas as pd

        snapshots = []
        for asset in parameters.get("assets", [])[:20]:
            frame = ak.stock_zh_a_daily(
                symbol=_market_symbol(str(asset)),
                start_date=(datetime.now(UTC) - timedelta(days=14)).strftime("%Y%m%d"),
                end_date=datetime.now(UTC).strftime("%Y%m%d"),
                adjust="qfq",
            )
            if frame is None or frame.empty:
                continue
            latest = frame.iloc[-1].to_dict()
            symbol = _symbol(str(asset))
            snapshots.append(
                {
                    "代码": symbol,
                    "名称": None,
                    "最新价": latest.get("close"),
                    "涨跌幅": None,
                    "成交量": latest.get("volume"),
                    "成交额": latest.get("amount"),
                    "总市值": None,
                    "市盈率-动态": None,
                    "as_of": _date(latest.get("date")),
                }
            )
        return pd.DataFrame(snapshots), _normalize_snapshot
    if capability == "financials":
        return (
            ak.stock_financial_abstract_ths(symbol=_symbol(str(parameters["asset"])), indicator="按报告期"),
            _normalize_generic,
        )
    if capability == "market_activity":
        symbol = _symbol(str(parameters["asset"]))
        market = "sh" if symbol.startswith("6") else "bj" if symbol.startswith(("4", "8")) else "sz"
        return ak.stock_individual_fund_flow(stock=symbol, market=market), _normalize_generic
    raise ProviderError("capability_not_implemented")


async def fetch(query: BusinessQuery) -> Result:
    result = Result(provider_id="akshare")
    result.source_url = "https://akshare.akfamily.xyz/"
    result.limitations = [
        "AKShare 是公开聚合库；上游字段与可用性可能变化。",
        "当前快照不代表交易所级实时行情。",
    ]
    try:
        async with asyncio.timeout(DEADLINE):
            frame, normalizer = await asyncio.to_thread(_invoke, query)
            source_rows = _records(frame)
            result.rows = normalizer(source_rows, query)
            result.pages_fetched = 1
            result.provider_total = len(source_rows)
            result.pagination_complete = len(source_rows) <= MAX_ROWS
            result.status = "complete" if result.rows else "empty"
            result.as_of = max(
                (str(row.get("date") or row.get("as_of")) for row in result.rows if row.get("date") or row.get("as_of")),
                default=None,
            )
            result.raw = [json.dumps(source_rows, ensure_ascii=False, default=str).encode()]
            result.raw_bytes = len(result.raw[0])
    except asyncio.CancelledError:
        log.info("datahub_akshare_cancelled", capability=query.capability)
        raise
    except TimeoutError:
        result.status = "failed"
        result.limitations.append("deadline")
    except Exception as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        result.status = "partial" if result.rows else "failed"
        reason = str(exc) if isinstance(exc, ProviderError) else "provider_error"
        result.limitations.append(reason)
        log.warning(
            "datahub_akshare_incomplete",
            capability=query.capability,
            error_type=type(exc).__name__,
        )
    fields = {key for row in result.rows for key in row}
    for field in fields:
        unit = None
        currency = None
        if field in {"open", "close", "high", "low", "price", "turnover", "market_cap"}:
            unit = "CNY"
            currency = "CNY"
        elif field.endswith("_pct"):
            unit = "%"
        elif field == "volume":
            unit = "share"
        result.fields[field] = {"unit": unit, "currency": currency}
    return result


async def probe() -> dict:
    try:
        async with asyncio.timeout(DEADLINE):
            frame, _ = await asyncio.to_thread(
                _invoke,
                BusinessQuery(capability="search_assets", source="akshare", parameters={"query": ""}),
            )
            return {"health": "healthy" if len(_records(frame)) else "degraded", "failure_code": None}
    except Exception as exc:
        if isinstance(exc, asyncio.CancelledError):
            raise
        return {"health": "unavailable", "failure_code": "probe_failed"}
