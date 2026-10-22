"""Bounded AKShare provider used by DataHub business contracts only."""

from __future__ import annotations

import asyncio
import json
import math
import re
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_ROWS, ProviderError, Result, cn_stock_identity

log = get_logger(__name__)


@dataclass(frozen=True)
class _FeedNormalizer:
    normalize: Any
    upstream_id: str
    attempts: tuple[dict, ...]

    def __call__(self, rows, query):
        return self.normalize(rows, query)


DEADLINE = 15
PROBE_DEADLINE = 10
PROBE_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
PROBE_MAX_BYTES = 16 * 1024
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-akshare")
_CAPACITY = threading.BoundedSemaphore(1)
_FUTURES: set[Future] = set()
_FUTURES_LOCK = threading.Lock()


def active_futures() -> tuple[Future, ...]:
    """Witness actual SDK work independently of cancelled coroutine waiters."""
    with _FUTURES_LOCK:
        return tuple(future for future in _FUTURES if not future.done())


def _release_capacity(_future: Future) -> None:
    with _FUTURES_LOCK:
        _FUTURES.discard(_future)
    try:
        _CAPACITY.release()
    except ValueError:
        log.error("datahub_akshare_capacity_release_failed")


def _submit_work(function, *args) -> Future | None:
    if not _CAPACITY.acquire(blocking=False):
        return None
    try:
        future = _EXECUTOR.submit(function, *args)
    except Exception:
        _CAPACITY.release()
        raise
    with _FUTURES_LOCK:
        _FUTURES.add(future)
    future.add_done_callback(_release_capacity)
    return future


def _submit(query: BusinessQuery) -> Future | None:
    return _submit_work(_invoke, query)


def _invoke(query: BusinessQuery) -> Result:
    from .public_worker import invoke_worker

    return invoke_worker("akshare", query)


def _symbol(value: str) -> str:
    match = re.fullmatch(r"([0-9]{6})(?:\.(?:SH|SZ|BJ))?", value.upper())
    if not match:
        raise ProviderError("invalid_asset")
    return match.group(1)


def _market_code(symbol: str) -> str:
    if symbol.startswith(("5", "6", "9")):
        return "SH"
    if symbol.startswith(("4", "8")):
        return "BJ"
    return "SZ"


def _market_symbol(value: str) -> str:
    return _exchange_symbol(value)


def _exchange_symbol(value: str) -> str:
    match = re.fullmatch(r"([0-9]{6})(?:\.(SH|SZ|BJ))?", value.upper())
    if not match:
        raise ProviderError("invalid_asset")
    code = match.group(1)
    # An explicit suffix wins: prefix guessing sends 000300.SH to the Shenzhen
    # feed, whose payload decodes to an empty frame.
    market = (match.group(2) or _market_code(code)).lower()
    return f"{market}{code}"


SEMANTICS_REVISION = "akshare-supported-query-v5"
_FREQUENCIES = {
    "daily": "daily",
    "day": "daily",
    "1d": "daily",
    "weekly": "weekly",
    "week": "weekly",
    "1w": "weekly",
    "monthly": "monthly",
    "month": "monthly",
    "1m": "monthly",
}


def _frequency(parameters: dict) -> str:
    value = parameters.get("frequency", "daily")
    if not isinstance(value, str) or value not in _FREQUENCIES:
        raise ProviderError("invalid_frequency")
    return _FREQUENCIES[value]


def _activity_bounds(query: BusinessQuery) -> tuple[date | None, date | None]:
    bounds: list[date | None] = []
    for key in ("start_date", "end_date"):
        value = query.parameters.get(key)
        if value is None:
            bounds.append(None)
            continue
        if not isinstance(value, str):
            raise ProviderError("invalid_date_range")
        try:
            day = _date(value)
            bounds.append(date.fromisoformat(day) if day else None)
        except (ValueError, ProviderError):
            raise ProviderError("invalid_date_range") from None
    start, end = bounds
    if start is not None and end is not None and start > end:
        raise ProviderError("invalid_date_range")
    return start, end


def validate_supported_query(query: BusinessQuery) -> None:
    """Pure semantics check shared by selection/cache admission and execution."""
    parameters = query.parameters
    if query.capability == "trading_calendar":
        start, end = _activity_bounds(query)
        if (
            parameters.get("market", "CN") != "CN"
            or start is None
            or end is None
            or start < date(1990, 12, 19)
            or (end - start).days > 1464
        ):
            raise ProviderError("invalid_date_range")
    if query.capability == "market_bars":
        if parameters.get("asset_type", "stock") not in {"stock", "index", "etf"}:
            raise ProviderError("data_not_equivalent")
        if parameters.get("asset_type", "stock") == "stock":
            cn_stock_identity(parameters.get("asset"))
        _frequency(parameters)
        if parameters.get("adjustment", "qfq") not in {"none", "qfq", "hfq"}:
            raise ProviderError("invalid_adjustment")
    if query.capability == "market_activity":
        if parameters.get("dataset") != "fund_flow":
            raise ProviderError("data_not_equivalent")
        _activity_bounds(query)
    if query.capability == "market_bars" and parameters.get("asset_type") == "index":
        if parameters.get("adjustment", "none") != "none":
            raise ProviderError("invalid_adjustment")
        if _frequency(parameters) != "daily":
            raise ProviderError("invalid_frequency")
    if query.capability == "market_snapshot":
        if parameters.get("asset_type", "stock") != "stock":
            raise ProviderError("data_not_equivalent")
        assets = parameters.get("assets")
        if not isinstance(assets, list) or not assets or len(assets) > 20:
            raise ProviderError("invalid_asset")
        identities: dict[str, str] = {}
        for asset in assets:
            if not isinstance(asset, str):
                raise ProviderError("invalid_asset")
            cn_stock_identity(asset)
            code = _symbol(asset)
            exchange = _exchange_symbol(asset)
            if code in identities and identities[code] != exchange:
                raise ProviderError("data_not_equivalent")
            identities[code] = exchange
    elif query.capability in {"market_activity", "market_bars", "financials"}:
        asset = parameters.get("asset")
        if not isinstance(asset, str):
            raise ProviderError("invalid_asset")
        _symbol(asset)
    if query.capability == "financials":
        if parameters.get("statements", ["metrics"]) not in (["metrics"], ["indicators"]):
            raise ProviderError("data_operation_unsupported")
        periods = parameters.get("periods", [])
        if type(periods) is int and 1 <= periods <= 100:
            return
        if not isinstance(periods, list) or len(periods) > 100:
            raise ProviderError("invalid_date_range")
        try:
            if any(
                not isinstance(value, str) or date.fromisoformat(value).isoformat() != value
                for value in periods
            ):
                raise ValueError("invalid_period")
        except (ValueError, TypeError):
            raise ProviderError("invalid_date_range") from None


def _slice_activity_frame(frame: Any, query: BusinessQuery) -> Any:
    """Filter provider dates before the shared row cap; unknown dates fail closed."""
    start, end = _activity_bounds(query)
    if frame is None or not hasattr(frame, "columns"):
        raise ProviderError("invalid_dataframe")
    if not frame.empty and (start is not None or end is not None):
        field = next((key for key in ("日期", "date") if key in frame.columns), None)
        if field is None:
            raise ProviderError("data_not_equivalent")

        def provider_day(value: Any) -> date:
            if isinstance(value, datetime):
                value = value.date()
            canonical = _date(value)
            if canonical is None:
                raise ProviderError("invalid_provider_date")
            try:
                return date.fromisoformat(canonical)
            except ValueError:
                raise ProviderError("invalid_provider_date") from None

        dates = frame[field].map(provider_day)
        mask = dates.map(
            lambda day: (start is None or day >= start) and (end is None or day <= end)
        )
        frame = frame[mask]
    if len(frame) > MAX_ROWS:
        raise ProviderError("row_limit")
    return frame


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
    # Keep a sentinel row so a bounded response cannot claim full coverage.
    return [{str(key): _clean(value) for key, value in row.items()} for row in rows[: MAX_ROWS + 1]]


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


def _iso_date(value: str) -> str | None:
    return f"{value[:4]}-{value[4:6]}-{value[6:]}" if re.fullmatch(r"[0-9]{8}", value) else None


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
        market = _market_code(code)
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
                "turnover": _number(_pick(row, "成交额", "amount")),
                "turnover_rate_pct": _number(_pick(row, "换手率", "turnover_rate")),
            }
        )
    return normalized


def _normalize_sina_stock_bars(rows: list[dict], query: BusinessQuery) -> list[dict]:
    normalized = _normalize_bars(rows, query)
    by_date = {_date(_pick(row, "日期", "date")): row for row in rows}
    for row in normalized:
        original = by_date[row["date"]]
        if row["turnover_rate_pct"] is None and original.get("turnover") is not None:
            ratio = _number(original["turnover"])
            row["turnover_rate_pct"] = ratio * 100 if ratio is not None else None
    return normalized


def _normalize_em_stock_bars(rows: list[dict], query: BusinessQuery) -> list[dict]:
    normalized = _normalize_bars(rows, query)
    for row in normalized:
        if row["volume"] is not None:
            row["volume"] *= 100  # Official EM stock-history volume is lots, not shares.
    return normalized


def _normalize_snapshot(rows: list[dict], query: BusinessQuery) -> list[dict]:
    requested = {
        _symbol(str(value)): f"{_symbol(str(value))}.{_exchange_symbol(str(value))[:2].upper()}"
        for value in query.parameters.get("assets", [])
    }
    normalized = []
    for row in rows:
        code = str(_pick(row, "代码", "code") or "").strip()
        if requested and code not in requested:
            continue
        if not re.fullmatch(r"[0-9]{6}", code):
            continue
        market = _market_code(code)
        normalized.append(
            {
                "asset": requested.get(code, f"{code}.{market}"),
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


def _normalize_activity(rows: list[dict], query: BusinessQuery) -> list[dict]:
    normalized = _normalize_generic(rows, query)
    for row in normalized:
        day = _date(_pick(row, "日期", "date"))
        if day is None:
            raise ProviderError("data_not_equivalent")
        try:
            date.fromisoformat(day)
        except ValueError:
            raise ProviderError("invalid_provider_date") from None
        row["date"] = day
    return normalized


def _normalize_financials(rows: list[dict], query: BusinessQuery) -> list[dict]:
    periods = query.parameters.get("periods", [])
    if type(periods) is int:
        dated = []
        for row in rows:
            period = _date(_pick(row, "报告期", "report_period"))
            if period is None:
                raise ProviderError("vendor_schema_invalid")
            try:
                parsed = date.fromisoformat(period)
            except (ValueError, TypeError):
                raise ProviderError("vendor_schema_invalid") from None
            dated.append((parsed, row))
        rows = [row for _period, row in sorted(dated, key=lambda item: item[0])[-periods:]]
    elif periods:
        selected = []
        for row in rows:
            period = _date(_pick(row, "报告期", "report_period"))
            if period is None:
                raise ProviderError("vendor_schema_invalid")
            if period in periods:
                selected.append(row)
        rows = selected
    normalized = _normalize_generic(rows, query)
    return [
        {
            key: None if key != "asset" and isinstance(value, bool) else value
            for key, value in row.items()
        }
        for row in normalized
    ]


def _invoke_sdk(query: BusinessQuery):
    validate_supported_query(query)
    import akshare as ak

    capability = query.capability
    parameters = query.parameters
    if capability == "trading_calendar":
        from pandas import DataFrame

        frame = ak.tool_trade_date_hist_sina()
        records = frame.to_dict(orient="records") if hasattr(frame, "to_dict") else list(frame)
        if not records or len(records) > 20000:
            raise ProviderError("vendor_schema_invalid")
        try:
            days = set()
            for row in records:
                day = _date(row["trade_date"])
                if day is None:
                    raise ValueError("invalid_calendar_day")
                days.add(date.fromisoformat(day))
        except (ValueError, TypeError, KeyError):
            raise ProviderError("vendor_schema_invalid") from None
        start, end = _activity_bounds(query)
        if start is None or end is None or min(days) > start or max(days) < end:
            raise ProviderError("vendor_schema_invalid")
        rows = [
            {
                "date": (start + timedelta(days=index)).isoformat(),
                "market": "CN",
                "is_trading_day": start + timedelta(days=index) in days,
            }
            for index in range((end - start).days + 1)
        ]
        return DataFrame(rows), lambda values, _query: values
    if capability == "search_assets":
        return ak.stock_info_a_code_name(), _normalize_assets
    if capability == "market_bars":
        frequency = _frequency(parameters)
        adjustment = parameters.get("adjustment", "qfq")
        asset_type = str(parameters.get("asset_type", "stock"))
        start_date = str(parameters.get("start_date", "")).replace("-", "")
        end_date = str(parameters.get("end_date", "")).replace("-", "")
        # Index and ETF codes must not fall through to the stock endpoint: it
        # maps bare codes into the stock pool and returns wrong instruments.
        if asset_type == "index":
            symbol = _exchange_symbol(str(parameters["asset"]))
            frame = None
            # Public index feeds throttle bursts; one bounded retry plus an
            # alternate feed keeps the query inside the provider deadline.
            for attempt in range(2):
                if attempt:
                    time.sleep(1.5)
                try:
                    candidate = ak.stock_zh_index_daily(symbol=symbol)
                except Exception:  # noqa: BLE001 - upstream HTML or shape drift
                    log.warning("datahub_akshare_index_feed_failed", attempt=attempt + 1)
                    continue
                if candidate is not None and not candidate.empty and "date" in candidate.columns:
                    frame = candidate
                    break
            if frame is None:
                try:
                    candidate = ak.stock_zh_index_daily_em(symbol=symbol)
                except Exception:  # noqa: BLE001 - upstream busy payloads
                    log.warning("datahub_akshare_index_fallback_failed")
                    candidate = None
                if candidate is not None and not candidate.empty and "date" in candidate.columns:
                    frame = candidate
            if frame is None:
                raise ProviderError("vendor_unreachable")
            start_iso, end_iso = _iso_date(start_date), _iso_date(end_date)
            # Full history arrives in one frame; slice before the row cap would
            # drop the newest dates.
            if not frame.empty and start_iso and end_iso:
                dates = frame["date"].astype(str)
                frame = frame[(dates >= start_iso) & (dates <= end_iso)]
            return frame, _normalize_bars
        if asset_type == "etf":
            frame = ak.fund_etf_hist_em(
                symbol=_symbol(str(parameters["asset"])),
                period=frequency,
                start_date=start_date,
                end_date=end_date,
                adjust="" if adjustment == "none" else adjustment,
            )
            return frame, _normalize_bars
        if frequency == "daily":
            try:
                frame = ak.stock_zh_a_daily(
                    symbol=_exchange_symbol(str(parameters["asset"])),
                    start_date=start_date,
                    end_date=end_date,
                    adjust="" if adjustment == "none" else adjustment,
                )
                return frame, _FeedNormalizer(
                    _normalize_sina_stock_bars,
                    "sina",
                    ({"upstream": "sina", "status": "complete"},),
                )
            except Exception as exc:
                if adjustment != "none":
                    raise
                log.warning("datahub_sina_raw_fallback", error_type=type(exc).__name__)
                frame = ak.stock_zh_a_hist(
                    symbol=_symbol(str(parameters["asset"])),
                    period="daily",
                    start_date=start_date,
                    end_date=end_date,
                    adjust="",
                    timeout=4,
                )
                return frame, _FeedNormalizer(
                    _normalize_em_stock_bars,
                    "eastmoney",
                    (
                        {"upstream": "sina", "status": "failed"},
                        {"upstream": "eastmoney", "status": "complete"},
                    ),
                )
        return (
            ak.stock_zh_a_hist(
                symbol=_symbol(str(parameters["asset"])),
                period=frequency,
                start_date=start_date,
                end_date=end_date,
                adjust="" if adjustment == "none" else adjustment,
                timeout=10,
            ),
            _normalize_em_stock_bars,
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
            ak.stock_financial_abstract_ths(
                symbol=_symbol(str(parameters["asset"])), indicator="按报告期"
            ),
            _normalize_financials,
        )
    if capability == "market_activity":
        symbol = _symbol(str(parameters["asset"]))
        market = _exchange_symbol(str(parameters["asset"]))[:2]
        frame = ak.stock_individual_fund_flow(stock=symbol, market=market)
        return _slice_activity_frame(frame, query), _normalize_activity
    raise ProviderError("capability_not_implemented")


async def _fetch_probe_payload() -> bytes:
    timeout = httpx.Timeout(8, connect=3)
    async with (
        httpx.AsyncClient(timeout=timeout, trust_env=False, follow_redirects=False) as client,
        client.stream("GET", PROBE_URL) as response,
    ):
        response.raise_for_status()
        payload = bytearray()
        async for chunk in response.aiter_bytes():
            payload.extend(chunk)
            if len(payload) > PROBE_MAX_BYTES:
                raise ProviderError("response_too_large")
    return bytes(payload)


async def _probe_remote() -> int:
    """Probe AKShare's fixed Sina calendar upstream with a cancellable stream."""

    try:
        import akshare  # noqa: F401 - dependency presence is part of probe readiness.
    except ImportError as exc:
        raise ProviderError("blocked_dependency") from exc
    payload = await _fetch_probe_payload()
    if not payload.startswith(b'var datelist="') or not payload.rstrip().endswith(
        b'";var KLC_TD_SH=datelist;'
    ):
        raise ProviderError("vendor_schema_invalid")
    return 1


def _probe_failure_code(exc: Exception) -> str:
    if isinstance(exc, ProviderError):
        code = str(exc)
        return code if re.fullmatch(r"[a-z0-9_]{1,64}", code) else "probe_failed"
    if isinstance(exc, TimeoutError):
        return "deadline"
    if isinstance(exc, ImportError):
        return "blocked_dependency"
    if isinstance(exc, OSError) or type(exc).__name__ in {
        "ConnectTimeout",
        "ConnectionError",
        "HTTPStatusError",
        "ProxyError",
        "ReadTimeout",
        "SSLError",
    }:
        return "vendor_unreachable"
    return "probe_failed"


def _materialize(query, frame, normalizer):
    result = Result(provider_id="akshare")
    result.source_url = "https://akshare.akfamily.xyz/"
    result.limitations = [
        "AKShare 是公开聚合库；上游字段与可用性可能变化。",
        "当前快照不代表交易所级实时行情。",
    ]
    source_rows = _records(frame)
    result.rows = normalizer(source_rows[:MAX_ROWS], query)
    result.pages_fetched = 1
    result.provider_total = len(source_rows)
    result.pagination_complete = len(source_rows) <= MAX_ROWS
    result.status = (
        ("complete" if result.pagination_complete else "partial") if result.rows else "empty"
    )
    if not result.pagination_complete:
        result.limitations.append("provider_response_row_limit")
        result.missing.append("remaining_provider_rows")
    result.as_of = max(
        (
            str(row.get("date") or row.get("as_of"))
            for row in result.rows
            if row.get("date") or row.get("as_of")
        ),
        default=None,
    )
    result.raw = [json.dumps(source_rows, ensure_ascii=False, default=str).encode()]
    result.raw_bytes = len(result.raw[0])
    if query.parameters.get("asset_type") in {"index", "etf"} and result.rows:
        result.limitations.append("volume_unit_not_verified")
    fields = {key for row in result.rows for key in row}
    for field in fields:
        unit = None
        currency = None
        if query.parameters.get("asset_type") == "index" and field in {
            "open",
            "close",
            "high",
            "low",
        }:
            unit = "points"
        elif field in {"open", "close", "high", "low", "price", "turnover", "market_cap"}:
            if (
                query.capability == "market_bars"
                and query.parameters.get("asset_type", "stock") == "stock"
            ):
                unit = "currency" if field == "turnover" else "currency_per_share"
            else:
                unit = "CNY"
            currency = "CNY"
        elif field.endswith("_pct"):
            unit = "percent" if query.capability == "market_bars" else "%"
        elif field == "volume":
            unit = (
                "provider_defined"
                if query.parameters.get("asset_type") in {"index", "etf"}
                else "share"
            )
        result.fields[field] = {"unit": unit, "currency": currency}
    result.metadata["provider_semantics_revision"] = SEMANTICS_REVISION
    if query.capability == "market_bars" and query.parameters.get("asset_type", "stock") == "stock":
        result.metadata["upstream_id"] = getattr(normalizer, "upstream_id", None) or (
            "sina" if _frequency(query.parameters) == "daily" else "eastmoney"
        )
        if isinstance(normalizer, _FeedNormalizer):
            result.metadata["upstream_attempts"] = list(normalizer.attempts)
    return result


def invoke_public(query: BusinessQuery) -> Result:
    return _materialize(query, *_invoke_sdk(query))


async def fetch(query: BusinessQuery) -> Result:
    result = Result(provider_id="akshare")
    result.source_url = "https://akshare.akfamily.xyz/"
    result.limitations = [
        "AKShare 是公开聚合库；上游字段与可用性可能变化。",
        "当前快照不代表交易所级实时行情。",
    ]
    try:
        future = _submit(query)
    except Exception as exc:  # noqa: BLE001 - executor/provider submission can fail arbitrarily.
        result.status = "failed"
        result.limitations.append("provider_error")
        log.warning("datahub_akshare_submit_failed", error_type=type(exc).__name__)
        return result
    if future is None:
        result.status = "failed"
        result.limitations.append("provider_busy")
        log.warning("datahub_akshare_busy", capability=query.capability)
        return result
    try:
        async with asyncio.timeout(DEADLINE):
            payload = await asyncio.shield(asyncio.wrap_future(future))
            if isinstance(payload, Result):
                return payload
            frame, normalizer = payload
            return _materialize(query, frame, normalizer)
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
    return result


async def probe() -> dict:
    if not _CAPACITY.acquire(blocking=False):
        log.info("datahub_akshare_probe_busy")
        return {"health": "unavailable", "failure_code": "provider_busy"}
    try:
        async with asyncio.timeout(PROBE_DEADLINE):
            row_count = await _probe_remote()
            return {
                "health": "healthy" if row_count else "degraded",
                "failure_code": None,
            }
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - probe must contain arbitrary HTTP/provider failures.
        failure_code = _probe_failure_code(exc)
        log.warning(
            "datahub_akshare_probe_failed",
            failure_code=failure_code,
            error_type=type(exc).__name__,
        )
        return {"health": "unavailable", "failure_code": failure_code}
    finally:
        try:
            _CAPACITY.release()
        except ValueError:
            log.error("datahub_akshare_probe_capacity_release_failed")
