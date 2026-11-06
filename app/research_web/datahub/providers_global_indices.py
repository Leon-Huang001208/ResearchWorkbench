"""Bounded native public quotes and bars for nine selected price indices.

The registered Tencent history endpoint supplies actual quotes and unadjusted
day bars. The independently validated Yahoo parser remains available offline;
the live provider does not retry the currently HTTP403 Yahoo source.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

from ..market_indices import GLOBAL, GLOBAL_INDEXES, global_catalog

log = get_logger(__name__)
CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart/"
MAX_BYTES = 1024 * 1024
MAX_BARS = 160
TENCENT_BASE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
TENCENT_SYMBOLS = {
    "SSE": "sh000001",
    "CSI300": "sh000300",
    "CHINEXT": "sz399006",
    "SP500": "us.INX",
    "NASDAQ": "us.IXIC",
    "DJI": "us.DJI",
    "HSI": "hkHSI",
    "HSCEI": "hkHSCEI",
    "HSTECH": "hkHSTECH",
}


class GlobalIndexError(ValueError):
    """Stable non-sensitive upstream failure code."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def _number(value, *, positive=False):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GlobalIndexError("invalid_number")
    if not math.isfinite(value) or (positive and value <= 0):
        raise GlobalIndexError("invalid_number")
    return value


def _stamp(value, tz, now):
    number = _number(value, positive=True)
    if number is None:
        raise GlobalIndexError("missing_timestamp")
    try:
        stamp = datetime.fromtimestamp(number, tz)
    except (ValueError, OverflowError, OSError) as exc:
        raise GlobalIndexError("invalid_timestamp") from exc
    if stamp.year < 1990 or stamp > now + timedelta(minutes=5):
        raise GlobalIndexError("invalid_timestamp")
    return stamp


def empty_row(index_id):
    identity = next(item for item in global_catalog()["items"] if item["index_id"] == index_id)
    return {
        **identity,
        "price": None,
        "change": None,
        "change_pct": None,
        "previous_close": None,
        "as_of": None,
        "quote_trade_date": None,
        "daily_bars": [],
        "series": [],
        "partial_daily_bar": None,
        "daily_history_status": "unavailable",
        "gaps": [],
        "stale": True,
    }


def parse_chart(payload, index_id, *, now=None):
    """Validate provider identity, ascending local dates and genuine unadjusted OHLCV."""
    row = empty_row(index_id)
    now = now or datetime.now(UTC)
    tz = ZoneInfo(row["timezone"])
    now = now.astimezone(tz)
    try:
        envelope = payload["chart"]
        results = envelope["result"]
        if envelope.get("error") or not isinstance(results, list) or len(results) != 1:
            raise GlobalIndexError("index_unavailable")
        result = results[0]
        meta = result["meta"]
        if (
            meta["symbol"] != row["source_symbol"]
            or meta["instrumentType"] != "INDEX"
            or meta["currency"] != row["currency"]
            or meta["exchangeTimezoneName"] != row["timezone"]
        ):
            raise GlobalIndexError("index_identity_mismatch")
        timestamps = result["timestamp"]
        quotes = result["indicators"]["quote"]
        if not isinstance(timestamps, list) or not 1 <= len(timestamps) <= MAX_BARS:
            raise GlobalIndexError("invalid_series_shape")
        if not isinstance(quotes, list) or len(quotes) != 1:
            raise GlobalIndexError("invalid_series_shape")
        values = quotes[0]
        if any(
            not isinstance(values.get(key), list) or len(values[key]) != len(timestamps)
            for key in ("open", "high", "low", "close", "volume")
        ):
            raise GlobalIndexError("invalid_series_shape")
        bars = []
        last_date = ""
        for position, value in enumerate(timestamps):
            stamp = _stamp(value, tz, now)
            day = stamp.date().isoformat()
            if day <= last_date:
                raise GlobalIndexError("nonascending_local_dates")
            last_date = day
            bar = {"date": day, "timestamp": stamp.isoformat(timespec="seconds")}
            for key in ("open", "high", "low", "close", "volume"):
                bar[key] = _number(values[key][position], positive=key != "volume")
            if bar["volume"] is not None and bar["volume"] < 0:
                raise GlobalIndexError("invalid_volume")
            prices = [bar[key] for key in ("open", "high", "low", "close")]
            if all(price is not None for price in prices) and not (
                bar["low"]
                <= min(bar["open"], bar["close"])
                <= max(bar["open"], bar["close"])
                <= bar["high"]
            ):
                raise GlobalIndexError("invalid_ohlc")
            if any(bar[key] is None for key in ("open", "high", "low", "close", "volume")):
                row["gaps"].append({"code": "ohlcv_incomplete", "date": day})
            # Conservative close policy: today's bar is always separate, even
            # after local session close, until the next local calendar date.
            if day == now.date().isoformat():
                row["partial_daily_bar"] = bar
            else:
                bars.append(bar)
        row["daily_bars"] = bars
        quote_time = _stamp(meta["regularMarketTime"], tz, now)
        row.update(
            price=_number(meta.get("regularMarketPrice"), positive=True),
            as_of=quote_time.isoformat(timespec="seconds"),
            quote_trade_date=quote_time.date().isoformat(),
        )
        # chartPreviousClose describes the range's start, NOT last session.
        previous = [bar for bar in bars if bar["date"] < row["quote_trade_date"]]
        row["previous_close"] = previous[-1]["close"] if previous else None
        if row["price"] is not None and row["previous_close"]:
            row["change"] = row["price"] - row["previous_close"]
            row["change_pct"] = row["change"] / row["previous_close"] * 100
        if row["price"] is None:
            row["gaps"].append({"code": "quote_unavailable"})
        if len(bars) < 20:
            row["gaps"].append({"code": "history_less_than_20_closed_bars"})
        source = {
            "provider": "yahoo",
            "source_symbol": row["source_symbol"],
            "source_url": CHART_BASE
            + quote(row["source_symbol"], safe="")
            + "?range=3mo&interval=1d",
            "retrieved_at": now.isoformat(timespec="seconds"),
            "currency": row["currency"],
            "timezone": row["timezone"],
            "price_unit": "index_points",
            "volume_unit": "source_reported_volume",
            "volume_semantics": "vendor_index_volume_not_tradeable_index_shares",
            "return_basis": "price_index",
            "adjustment": "unadjusted",
            "usage": "personal_reference_only_recheck_terms_before_redistribution",
            "historical_pit_verified": False,
            "availability_basis": "first_observed",
            "response_sha256": hashlib.sha256(
                json.dumps(payload, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
        }
        row.update(
            source=source,
            daily_source=dict(source),
            daily_history_status="partial" if row["gaps"] else "ready",
            last_closed_bar=bars[-1] if bars else None,
            stale=quote_time.date() < now.date(),
        )
        return row
    except GlobalIndexError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise GlobalIndexError("invalid_chart_schema") from exc


async def fetch_global_indices(client, semaphore):
    """One bounded Tencent native price-index request per fixed identity."""
    started = datetime.now(UTC).isoformat(timespec="seconds")

    async def one(index_id):
        symbol = TENCENT_SYMBOLS[index_id]
        row = empty_row(index_id)
        row["source_symbol"] = symbol
        try:
            async with (
                semaphore,
                client.stream(
                    "GET",
                    TENCENT_BASE,
                    params={"param": symbol + ",day,,,100,qfq"},
                    headers={"User-Agent": "Mozilla/5.0 ResearchWorkbench personal reference"},
                ) as response,
            ):
                response.raise_for_status()
                raw = bytearray()
                async for chunk in response.aiter_bytes():
                    raw.extend(chunk)
                    if len(raw) > MAX_BYTES:
                        raise GlobalIndexError("response_limit")
            row = parse_tencent_chart(json.loads(raw), index_id)
        except asyncio.CancelledError:
            raise
        except (httpx.HTTPError, GlobalIndexError, ValueError, TypeError) as exc:
            code = (
                exc.code
                if isinstance(exc, GlobalIndexError)
                else (
                    "source_http_error"
                    if isinstance(exc, httpx.HTTPStatusError)
                    else (
                        "source_timeout"
                        if isinstance(exc, httpx.TimeoutException)
                        else (
                            "source_connection_error"
                            if isinstance(exc, httpx.ConnectError)
                            else (
                                "source_invalid_json"
                                if isinstance(exc, ValueError)
                                else "source_unavailable"
                            )
                        )
                    )
                )
            )
            row["gaps"] = [
                {
                    "code": code,
                    "provider": "tencent",
                    "source_symbol": symbol,
                    "source_url": TENCENT_BASE,
                    "error_type": type(exc).__name__,
                    "http_status": (
                        exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                    ),
                }
            ]
            log.warning("global_index_unavailable", index_id=index_id, code=code)
        return row

    rows = await asyncio.gather(*(one(index_id) for index_id in GLOBAL_INDEXES))
    complete = all(not row["gaps"] for row in rows)
    log.info(
        "global_indices_read",
        rows=len(rows),
        available=sum(row["price"] is not None for row in rows),
    )
    return {
        "index_set": GLOBAL,
        "catalog_version": GLOBAL,
        "rows": rows,
        "summary": {},
        "provider": "tencent",
        "source_url": "https://gu.qq.com/",
        "started_at": started,
        "retrieved_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "as_of": max(
            (row["as_of"] for row in rows if row["as_of"]),
            key=datetime.fromisoformat,
            default=None,
        ),
        "provider_total": 9,
        "pagination_complete": True,
        "complete": complete,
        "missing": {
            "indices": sum(row["price"] is None for row in rows),
            "daily_history": sum(len(row["daily_bars"]) < 20 for row in rows),
        },
        "limitations": [
            "个人参考公开源；历史按首次取得保存，不证明历史PIT。",
            "今日原生日线单列；缺失OHLCV不补值；各市场日期独立。",
        ],
    }


def _tencent_number(value):
    if value in (None, "", "-"):
        return None
    if isinstance(value, bool):
        raise GlobalIndexError("invalid_number")
    try:
        return _number(float(value))
    except (ValueError, TypeError, OverflowError) as exc:
        raise GlobalIndexError("invalid_number") from exc


def parse_tencent_chart(payload, index_id, *, now=None):
    """Validate Tencent's envelope and native identity before shared OHLC checks.

    day is [date,open,close,high,low,source_volume]; only unadjusted `day`
    is accepted, even though the registered endpoint has a qfq request flag.
    """
    symbol = TENCENT_SYMBOLS[index_id]
    identity = empty_row(index_id)
    tz = ZoneInfo(identity["timezone"])
    try:
        if not isinstance(payload, dict):
            raise GlobalIndexError("invalid_tencent_schema")
        if payload.get("code") != 0 or set(payload["data"]) != {symbol}:
            raise GlobalIndexError("index_identity_mismatch")
        data = payload["data"][symbol]
        qt = data["qt"][symbol]
        if not isinstance(qt, list) or len(qt) < 33 or qt[2] != symbol[2:]:
            raise GlobalIndexError("index_identity_mismatch")
        stamp_format = {"CN": "%Y%m%d%H%M%S", "US": "%Y-%m-%d %H:%M:%S", "HK": "%Y/%m/%d %H:%M:%S"}[
            identity["market"]
        ]
        quote_time = datetime.strptime(qt[30], stamp_format).replace(tzinfo=tz)
        bars = data["day"]
        if not isinstance(bars, list) or not 1 <= len(bars) <= MAX_BARS:
            raise GlobalIndexError("invalid_series_shape")
        timestamps = []
        values = {key: [] for key in ("open", "high", "low", "close", "volume")}
        for bar in bars:
            if (
                not isinstance(bar, list)
                or len(bar) != 6
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", bar[0])
            ):
                raise GlobalIndexError("invalid_series_shape")
            timestamps.append(datetime.strptime(bar[0], "%Y-%m-%d").replace(tzinfo=tz).timestamp())
            for key, position in (
                ("open", 1),
                ("close", 2),
                ("high", 3),
                ("low", 4),
                ("volume", 5),
            ):
                values[key].append(_tencent_number(bar[position]))
        # This is an internal validation envelope, not provider evidence. Its
        # synthetic metadata is replaced by the actual Tencent provenance below.
        normalized = {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "symbol": GLOBAL_INDEXES[index_id][1],
                            "instrumentType": "INDEX",
                            "currency": identity["currency"],
                            "exchangeTimezoneName": identity["timezone"],
                            "regularMarketPrice": _tencent_number(qt[3]),
                            "regularMarketTime": quote_time.timestamp(),
                        },
                        "timestamp": timestamps,
                        "indicators": {"quote": [values]},
                    }
                ],
            }
        }
        row = parse_chart(normalized, index_id, now=now)
        previous = _tencent_number(qt[4])
        if previous is None or previous <= 0:
            row["gaps"].append({"code": "previous_close_unavailable"})
        else:
            if row["previous_close"] is not None and abs(row["previous_close"] - previous) > max(
                0.02, previous * 0.00001
            ):
                row["gaps"].append({"code": "quote_history_close_mismatch"})
            row["previous_close"] = previous
            row["change"] = _tencent_number(qt[31])
            row["change_pct"] = _tencent_number(qt[32])
            if row["change"] is None or row["change_pct"] is None:
                row["gaps"].append({"code": "quote_change_unavailable"})
        source = dict(
            row["source"],
            provider="tencent",
            source_symbol=symbol,
            source_url=TENCENT_BASE + "?param=" + quote(symbol + ",day,,,100,qfq", safe=","),
            response_sha256=hashlib.sha256(
                json.dumps(payload, sort_keys=True, allow_nan=False).encode()
            ).hexdigest(),
            source_fields={
                "quote": "qt[3,4,30,31,32]",
                "daily": "day[date,open,close,high,low,volume]",
            },
            index_identity_basis="fixed_vendor_symbol_and_returned_qt_code",
            returned_vendor_symbol=qt[2],
            currency_basis="fixed_index_identity",
            timezone_basis="fixed_vendor_market_contract",
            daily_timestamp_basis="source_local_date_bucket_at_midnight",
            volume_unit="source_reported_volume",
            volume_unit_verified=False,
        )
        row.update(
            source_symbol=symbol,
            source=source,
            daily_source=dict(source),
            daily_history_status="partial" if row["gaps"] else "ready",
        )
        return row
    except GlobalIndexError:
        raise
    except (KeyError, IndexError, TypeError, ValueError, OverflowError) as exc:
        raise GlobalIndexError("invalid_tencent_schema") from exc
