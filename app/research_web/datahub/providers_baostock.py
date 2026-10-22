"""Closed anonymous BaoStock adapter; raw SH/SZ daily bars only."""

from __future__ import annotations

import asyncio
import json
import re
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import date

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_QUERY_BYTES, MAX_ROWS, ProviderError, Result, numeric, valid_date

log = get_logger(__name__)
SEMANTICS_REVISION = "baostock-raw-sh-sz-v1"
FIELDS = "date,code,open,high,low,close,volume,amount,adjustflag,tradestatus,pctChg"
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="datahub-baostock")
_CAPACITY = threading.BoundedSemaphore(1)
_LOCK = threading.Lock()
_FUTURES: set[Future] = set()


def active_futures():
    with _LOCK:
        return tuple(future for future in _FUTURES if not future.done())


def _asset(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", value.upper()):
        raise ProviderError("invalid_asset")
    code, market = value.upper().split(".")
    if (market == "SH" and not code.startswith("6")) or (
        market == "SZ" and not code.startswith(("00", "30"))
    ):
        raise ProviderError("data_not_equivalent")
    return f"{market.lower()}.{code}"


def _bounds(parameters):
    try:
        start, end = date.fromisoformat(valid_date(parameters["start_date"])), date.fromisoformat(
            valid_date(parameters["end_date"])
        )
    except (KeyError, ValueError, TypeError):
        raise ProviderError("invalid_date_range") from None
    if start > end or (end - start).days > 1464:
        raise ProviderError("invalid_date_range")
    return start.isoformat(), end.isoformat()


def validate_supported_query(query: BusinessQuery):
    parameters = query.parameters
    if query.capability == "market_bars":
        _asset(parameters.get("asset"))
        if parameters.get("asset_type", "stock") != "stock":
            raise ProviderError("data_not_equivalent")
        if parameters.get("adjustment", "none") != "none":
            raise ProviderError("invalid_adjustment")
        if parameters.get("frequency", "daily") not in {"daily", "day", "1d"}:
            raise ProviderError("invalid_frequency")
        _bounds(parameters)
    elif query.capability == "trading_calendar":
        if parameters.get("market", "CN") not in {"CN", "A股", "沪深A股"}:
            raise ProviderError("data_not_equivalent")
        _bounds(parameters)
    elif query.capability == "search_assets":
        if parameters.get("asset_type", "stock") != "stock" or parameters.get(
            "market", "CN"
        ) not in {"CN", "A股", "沪深A股"}:
            raise ProviderError("data_not_equivalent")
        text = parameters.get("query", "")
        if not isinstance(text, str) or len(text) > 128:
            raise ProviderError("invalid_asset")
    else:
        raise ProviderError("data_operation_unsupported")


def _records(response, expected):
    if getattr(response, "error_code", None) != "0":
        raise ProviderError("vendor_unreachable")
    fields = getattr(response, "fields", None)
    if (
        not isinstance(fields, list)
        or set(fields) != set(expected)
        or len(set(fields)) != len(fields)
    ):
        raise ProviderError("vendor_schema_invalid")
    rows: list[dict] = []
    size = 0
    while response.next():
        values = response.get_row_data()
        if len(values) != len(fields):
            raise ProviderError("vendor_schema_invalid")
        row = dict(zip(fields, values, strict=True))
        size += len(json.dumps(row, ensure_ascii=False).encode())
        if len(rows) >= 20000 or size > MAX_QUERY_BYTES:
            raise ProviderError("row_limit")
        rows.append(row)
    if getattr(response, "error_code", None) != "0":
        raise ProviderError("vendor_unreachable")
    return rows


def invoke(query: BusinessQuery, *, sdk=None) -> Result:
    validate_supported_query(query)
    owned = sdk is None
    if owned:
        try:
            from importlib import import_module

            sdk = import_module("baostock")
        except ImportError:
            raise ProviderError("missing_dependency") from None
    logged_in = False
    try:
        if owned:
            if sdk.login().error_code != "0":
                raise ProviderError("vendor_unreachable")
            logged_in = True
        parameters = query.parameters
        if query.capability == "market_bars":
            code = _asset(parameters["asset"])
            start, end = _bounds(parameters)
            raw = _records(
                sdk.query_history_k_data_plus(
                    code=code,
                    fields=FIELDS,
                    start_date=start,
                    end_date=end,
                    frequency="d",
                    adjustflag="3",
                ),
                FIELDS.split(","),
            )
            rows = []
            for row in raw:
                if row["code"] != code or row["adjustflag"] != "3":
                    raise ProviderError("data_not_equivalent")
                if row["tradestatus"] not in {"0", "1"}:
                    raise ProviderError("vendor_schema_invalid")
                day = valid_date(row["date"])
                if not start <= day <= end:
                    raise ProviderError("vendor_schema_invalid")
                rows.append(
                    {
                        "asset": parameters["asset"].upper(),
                        "date": day,
                        **{
                            key: numeric(row[key], required=True)
                            for key in ["open", "high", "low", "close", "volume"]
                        },
                        "turnover": numeric(row["amount"]),
                        "change_pct": numeric(row["pctChg"]),
                        "trading_status": row["tradestatus"] == "1",
                        "adjustment": "none",
                    }
                )
            fields: dict = {
                key: {"unit": "currency_per_share", "currency": "CNY"}
                for key in ["open", "high", "low", "close"]
            }
            fields.update(
                volume={"unit": "share", "currency": None},
                turnover={"unit": "currency", "currency": "CNY"},
                change_pct={"unit": "percent", "currency": None},
            )
        elif query.capability == "trading_calendar":
            start, end = _bounds(parameters)
            raw = _records(
                sdk.query_trade_dates(start_date=start, end_date=end),
                ["calendar_date", "is_trading_day"],
            )
            rows = []
            for row in raw:
                day = valid_date(row["calendar_date"])
                if not start <= day <= end or row["is_trading_day"] not in {"0", "1"}:
                    raise ProviderError("vendor_schema_invalid")
                rows.append(
                    {"date": day, "market": "CN", "is_trading_day": row["is_trading_day"] == "1"}
                )
            fields = {}
        else:
            raw = _records(
                sdk.query_stock_basic(),
                ["code", "code_name", "ipoDate", "outDate", "type", "status"],
            )
            text = parameters.get("query", "").casefold()
            rows = []
            for row in raw:
                if row["type"] != "1":
                    continue
                market, separator, code = row["code"].partition(".")
                asset = f"{code}.{market.upper()}"
                if not separator:
                    raise ProviderError("vendor_schema_invalid")
                try:
                    _asset(asset)
                except ProviderError:
                    continue  # B shares and other unsupported classes are not A stocks.
                if text and not any(
                    text in str(value).casefold()
                    for value in (asset, row["code"], row["code_name"])
                ):
                    continue
                rows.append(
                    {
                        "asset": asset,
                        "name": row["code_name"],
                        "asset_type": "stock",
                        "market": "CN",
                        "listing_date": valid_date(row["ipoDate"]) if row["ipoDate"] else None,
                        "delisting_date": valid_date(row["outDate"]) if row["outDate"] else None,
                        "listing_status": row["status"],
                    }
                )
            fields = {}
        total = len(rows)
        return Result(
            rows=rows[:MAX_ROWS],
            raw=[json.dumps(raw, ensure_ascii=False).encode()],
            source_url="https://github.com/zxygithub/baostock",
            provider_id="baostock",
            status="partial" if total > MAX_ROWS else ("complete" if rows else "empty"),
            provider_total=total,
            pages_fetched=1,
            pagination_complete=total <= MAX_ROWS,
            fields=fields,
            limitations=["历史返回不等于历史当时可得；复权因子与发布时间未推定。"],
            metadata={
                "provider_semantics_revision": SEMANTICS_REVISION,
                "upstream_id": "baostock",
                "historical_point_in_time": False,
                "redistribution_rights": "unverified",
            },
        )
    finally:
        if logged_in:
            try:
                sdk.logout()
            except Exception as exc:  # noqa: BLE001 - redact unstable vendor logout failures.
                log.warning("baostock_guest_logout_failed", error_type=type(exc).__name__)


async def fetch(query: BusinessQuery) -> Result:
    validate_supported_query(query)
    if not _CAPACITY.acquire(blocking=False):
        return Result(status="failed", limitations=["provider_busy"], provider_id="baostock")
    from .public_worker import invoke_worker

    def done(future):
        with _LOCK:
            _FUTURES.discard(future)
        _CAPACITY.release()

    try:
        future = _EXECUTOR.submit(invoke_worker, "baostock", query)
    except Exception:  # noqa: BLE001 - preserve capacity if the owned executor rejects work.
        _CAPACITY.release()
        raise ProviderError("provider_error") from None
    with _LOCK:
        _FUTURES.add(future)
    future.add_done_callback(done)
    wrapped = asyncio.wrap_future(future)

    def observe(completed):
        if not completed.cancelled():
            completed.exception()

    wrapped.add_done_callback(observe)
    try:
        return await asyncio.shield(wrapped)
    except asyncio.CancelledError:
        log.info("baostock_provider_cancelled")
        raise
    except ProviderError as exc:
        return Result(status="failed", limitations=[str(exc)], provider_id="baostock")
