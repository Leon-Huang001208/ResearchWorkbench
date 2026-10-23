"""Bounded AKShare provider used by DataHub business contracts only."""

from __future__ import annotations

import asyncio
import json
import math
import re
import threading
import time
from calendar import monthrange
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_RESPONSE_BYTES, MAX_ROWS, ProviderError, Result, cn_stock_identity

log = get_logger(__name__)


@dataclass(frozen=True)
class _FeedNormalizer:
    normalize: Any
    upstream_id: str
    attempts: tuple[dict, ...]
    raw: bytes | None = None
    source_url: str | None = None
    limited_history: bool = False
    provider_total: int | None = None

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


SEMANTICS_REVISION = "akshare-supported-query-v6"
FUND_FLOW_GUEST_URL = "https://82.push2.eastmoney.com/webguest/api/qt/stock/fflow/daykline/get"
CHINA_MACRO_SCHEMA = "akshare-china-macro-v1"
SINA_FINANCIAL_SCHEMA = "akshare-sina-financial-disclosure-v1"
FUND_FLOW_SCHEMA = "akshare-eastmoney-fund-flow-provenance-v1"
SINA_FINANCIAL_URL = (
    "https://quotes.sina.cn/cn/api/openapi.php/CompanyFinanceService.getFinanceReport2022"
)
CHINA_MACRO_URL = "https://datacenter-web.eastmoney.com/api/data/v1/get"
CHINA_MACRO_CONTRACTS = {
    "cpi": (
        "RPT_ECONOMY_CPI",
        "REPORT_DATE,TIME,NATIONAL_SAME,NATIONAL_BASE,NATIONAL_SEQUENTIAL,NATIONAL_ACCUMULATE,CITY_SAME,CITY_BASE,CITY_SEQUENTIAL,CITY_ACCUMULATE,RURAL_SAME,RURAL_BASE,RURAL_SEQUENTIAL,RURAL_ACCUMULATE",
    ),
    "gdp": (
        "RPT_ECONOMY_GDP",
        "REPORT_DATE,TIME,DOMESTICL_PRODUCT_BASE,FIRST_PRODUCT_BASE,SECOND_PRODUCT_BASE,THIRD_PRODUCT_BASE,SUM_SAME,FIRST_SAME,SECOND_SAME,THIRD_SAME",
    ),
    "pmi": ("RPT_ECONOMY_PMI", "REPORT_DATE,TIME,MAKE_INDEX,MAKE_SAME,NMAKE_INDEX,NMAKE_SAME"),
    "m2": (
        "RPT_ECONOMY_CURRENCY_SUPPLY",
        "REPORT_DATE,TIME,BASIC_CURRENCY,BASIC_CURRENCY_SAME,BASIC_CURRENCY_SEQUENTIAL,CURRENCY,CURRENCY_SAME,CURRENCY_SEQUENTIAL,FREE_CASH,FREE_CASH_SAME,FREE_CASH_SEQUENTIAL",
    ),
}


@dataclass(frozen=True)
class _MacroNormalizer:
    raw: bytes
    source_url: str
    provider_total: int
    pages_complete: bool
    series: str

    def __call__(self, rows, _query):
        return rows


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
    if query.capability == "factor_macro":
        if (
            set(parameters) != {"series", "start_date", "end_date"}
            or not isinstance(parameters.get("series"), str)
            or parameters.get("series") not in CHINA_MACRO_CONTRACTS
        ):
            raise ProviderError("data_not_equivalent")
        _macro_bounds(query)
        if query.purpose == "backtest" or query.as_of is not None:
            raise ProviderError("data_not_equivalent")
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
        if query.purpose == "backtest" or query.as_of is not None:
            log.info("datahub_fund_flow_pit_rejected", reason="historical_vintage_unavailable")
            raise ProviderError("data_not_equivalent")
        if parameters.get("dataset") != "fund_flow":
            raise ProviderError("data_not_equivalent")
        _activity_bounds(query)
        cn_stock_identity(parameters.get("asset"))
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
        if parameters.get("statements") == ["income_statement"]:
            _validate_income_statement(query)
            return
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
                "pe_ttm": _number(_pick(row, "pe_ttm")),
                "pe_dynamic": _number(_pick(row, "市盈率-动态", "pe_dynamic")),
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
        for output, source in {
            "main_net": "主力净流入-净额",
            "super_net": "超大单净流入-净额",
            "large_net": "大单净流入-净额",
            "medium_net": "中单净流入-净额",
            "small_net": "小单净流入-净额",
        }.items():
            value = row.get(source)
            row[output] = None if isinstance(value, bool) else _number(value)
    return normalized


def _fund_flow_guest(query):
    """Same Eastmoney upstream, single bounded response; never historical coverage."""
    from pandas import DataFrame

    if query.purpose == "backtest" or query.as_of is not None:
        raise ProviderError("data_not_equivalent")
    identity = cn_stock_identity(query.parameters["asset"])
    code, exchange = identity.split(".")
    if exchange not in {"SH", "SZ"}:
        raise ProviderError("data_not_equivalent")
    market = 1 if exchange == "SH" else 0
    params = {
        "secid": f"{market}.{code}",
        "klt": "101",
        "lmt": "30",
        "fields1": "f1,f2,f3,f7",
        "fields2": ",".join(f"f{index}" for index in range(51, 66)),
        "ut": "b2884a393a59ad64002292a3e90d46a5",
    }
    try:
        with (
            httpx.Client(timeout=4, trust_env=False, follow_redirects=False) as client,
            client.stream("GET", FUND_FLOW_GUEST_URL, params=params) as response,
        ):
            if response.status_code != 200:
                log.warning("datahub_fund_flow_guest_http_failed", status=response.status_code)
                raise ProviderError("vendor_unreachable")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    log.warning("datahub_fund_flow_guest_response_limit")
                    raise ProviderError("vendor_schema_invalid")
        payload = json.loads(raw)
        data = payload["data"]
        if (
            type(payload.get("rc")) is not int
            or payload["rc"] != 0
            or data.get("code") != code
            or type(data.get("market")) is not int
            or data["market"] != market
        ):
            raise ValueError("identity_mismatch")
        lines = data["klines"]
        if not isinstance(lines, list) or not lines or len(lines) > MAX_ROWS:
            raise ValueError("invalid_lines")
        rows = []
        previous = None
        names = (
            "日期",
            "主力净流入-净额",
            "小单净流入-净额",
            "中单净流入-净额",
            "大单净流入-净额",
            "超大单净流入-净额",
            *(f"f{index}" for index in range(57, 66)),
        )
        for line in lines:
            parts = line.split(",") if isinstance(line, str) else []
            if len(parts) != 15:
                raise ValueError("invalid_line")
            day = date.fromisoformat(parts[0])
            if (
                day.isoformat() != parts[0]
                or day > datetime.now(UTC).date()
                or previous is not None
                and day <= previous
            ):
                raise ValueError("invalid_day")
            values = [float(value) for value in parts[1:]]
            if any(not math.isfinite(value) for value in values):
                raise ValueError("invalid_numeric")
            rows.append(dict(zip(names, [parts[0], *values], strict=True)))
            previous = day
        normalizer = _FeedNormalizer(
            _normalize_activity,
            "eastmoney",
            (
                {"upstream": "eastmoney", "endpoint": "akshare_sdk", "status": "failed"},
                {"upstream": "eastmoney", "endpoint": "webguest", "status": "snapshot"},
            ),
            raw=bytes(raw),
            source_url=str(httpx.URL(FUND_FLOW_GUEST_URL).copy_merge_params(params)),
            limited_history=True,
            provider_total=len(rows),
        )
        log.info("datahub_fund_flow_guest_received", rows=len(rows))
        return _slice_activity_frame(DataFrame(rows), query), normalizer
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        log.warning("datahub_fund_flow_guest_invalid")
        raise ProviderError("vendor_schema_invalid") from None
    except httpx.HTTPError:
        log.warning("datahub_fund_flow_guest_unreachable")
        raise ProviderError("vendor_unreachable") from None


def _macro_bounds(query):
    try:
        values = [query.parameters[key] for key in ("start_date", "end_date")]
        if any(not isinstance(value, str) for value in values):
            raise TypeError("date_type")
        start, end = (date.fromisoformat(value) for value in values)
        if start.isoformat() != values[0] or end.isoformat() != values[1] or start > end:
            raise ValueError("date_range")
        return start, end
    except (TypeError, ValueError, KeyError):
        log.warning("datahub_china_macro_request_invalid")
        raise ProviderError("invalid_date_range") from None


def _china_macro(query):
    """Closed SDK-equivalent requests retain the envelope the SDK discards."""
    from pandas import DataFrame

    series = query.parameters["series"]
    report, columns = CHINA_MACRO_CONTRACTS[series]
    params = {
        "columns": columns,
        "pageNumber": "1",
        "pageSize": "2000",
        "sortColumns": "REPORT_DATE",
        "sortTypes": "-1",
        "source": "WEB",
        "client": "WEB",
        "reportName": report,
        "p": "1",
        "pageNo": "1",
        "pageNum": "1",
    }
    try:
        with (
            httpx.Client(timeout=4, trust_env=False, follow_redirects=False) as client,
            client.stream("GET", CHINA_MACRO_URL, params=params) as response,
        ):
            if response.status_code != 200:
                raise ProviderError("vendor_unreachable")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise ValueError("response_limit")
        payload = json.loads(raw)
        if (
            payload.get("success") is not True
            or type(payload.get("code")) is not int
            or payload["code"] != 0
        ):
            raise ValueError("vendor_rejected")
        envelope = payload["result"]
        observations = envelope["data"]
        pages = envelope["pages"]
        count = envelope["count"]
        if (
            type(pages) is not int
            or type(count) is not int
            or count < 0
            or pages != max(1, (count + 1999) // 2000)
            or not isinstance(observations, list)
            or len(observations) != min(count, 2000)
        ):
            raise ValueError("pagination_invalid")
        start, end = _macro_bounds(query)
        rows = []
        previous = None
        numeric = set(columns.split(",")) - {"TIME", "REPORT_DATE"}
        for original in observations:
            if not isinstance(original, dict) or set(original) != set(columns.split(",")):
                raise ValueError("columns_mismatch")
            stamp = datetime.strptime(original["REPORT_DATE"], "%Y-%m-%d %H:%M:%S")
            pattern = (
                r"(\d{4})年第1(?:-([234]))?季度" if series == "gdp" else r"(\d{4})年(\d{2})月份"
            )
            match = re.fullmatch(pattern, original["TIME"])
            if match is None:
                raise ValueError("reference_period_invalid")
            year = int(match[1])
            position = int(match[2] or 1)
            month = position * 3 if series == "gdp" else position
            day = date(year, month, monthrange(year, month)[1])
            if (
                day > datetime.now(UTC).date()
                or stamp.strftime("%Y-%m-%d %H:%M:%S") != original["REPORT_DATE"]
                or stamp != datetime(year, month, 1)
                or previous is not None
                and day >= previous
            ):
                raise ValueError("reference_label_mismatch")
            for field in numeric:
                value = original[field]
                if value is not None and (
                    type(value) not in {int, float} or not math.isfinite(value)
                ):
                    raise ValueError("numeric_invalid")
            if start <= day <= end:
                rows.append(
                    {
                        **original,
                        "series": series,
                        "date": day.isoformat(),
                        "reference_period": (
                            f"{year}-Q{position}" if series == "gdp" else f"{year}-{month:02d}"
                        ),
                        "aggregation": "year_to_date" if series == "gdp" else "period",
                    }
                )
            previous = day
        normalizer = _MacroNormalizer(
            bytes(raw),
            str(httpx.URL(CHINA_MACRO_URL).copy_merge_params(params)),
            count,
            pages == 1,
            series,
        )
        log.info(
            "datahub_china_macro_received",
            series=series,
            rows=len(rows),
            provider_rows=len(observations),
        )
        return DataFrame(rows), normalizer
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        log.warning("datahub_china_macro_invalid", series=series)
        raise ProviderError("vendor_schema_invalid") from None
    except httpx.HTTPError:
        log.warning("datahub_china_macro_unreachable", series=series)
        raise ProviderError("vendor_unreachable") from None


def _explicit_money(value):
    if isinstance(value, bool) or value is None or value in ("", "--", "-"):
        return None
    if value == 0 or value == "0":
        return 0.0
    text = str(value).strip().replace(",", "")
    match = re.fullmatch(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(亿元|万元|元|亿|万)", text)
    if not match:
        return None  # A bare source amount does not establish its quantity scale.
    return float(match[1]) * {"亿元": 1e8, "亿": 1e8, "万元": 1e4, "万": 1e4, "元": 1}[match[2]]


def _validate_income_statement(query):
    parameters = query.parameters
    asset = parameters.get("asset")
    if (
        set(parameters) - {"asset", "statements", "periods"}
        or not isinstance(asset, str)
        or re.fullmatch(r"[0-9]{6}\.(SH|SZ)", asset) is None
        or cn_stock_identity(asset) != asset
        or query.purpose == "backtest"
        or query.as_of is not None
    ):
        raise ProviderError("data_not_equivalent")
    periods = parameters.get("periods", [])
    if type(periods) is int and 1 <= periods <= 8:
        return
    if not isinstance(periods, list) or len(periods) > 8:
        raise ProviderError("invalid_date_range")
    try:
        if len(set(periods)) != len(periods):
            raise ValueError("duplicate_period")
        for value in periods:
            parsed = date.fromisoformat(value)
            if parsed.isoformat() != value or (parsed.month, parsed.day) not in {
                (3, 31),
                (6, 30),
                (9, 30),
                (12, 31),
            }:
                raise ValueError("invalid_period")
    except (ValueError, TypeError):
        raise ProviderError("invalid_date_range") from None


def _sina_day(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{8}", value) is None:
        raise ValueError("invalid_day")
    parsed = date(int(value[:4]), int(value[4:6]), int(value[6:]))
    if parsed > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ValueError("future_day")
    return parsed


@dataclass(frozen=True)
class _FinancialNormalizer:
    raw: bytes
    source_url: str
    provider_total: int
    captured_periods: tuple[str, ...]

    def __call__(self, rows, _query):
        return rows


def _financial_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _financial_json_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite_json_number")
    return number


def _sina_income_statement(query):
    """One reviewed eight-period capture inside the existing public worker."""
    from pandas import DataFrame

    params = {
        "paperCode": _exchange_symbol(query.parameters["asset"]),
        "source": "lrb",
        "type": "0",
        "page": "1",
        "num": "8",
    }
    try:
        with (
            httpx.Client(timeout=4, trust_env=False, follow_redirects=False) as client,
            client.stream("GET", SINA_FINANCIAL_URL, params=params) as response,
        ):
            if response.status_code != 200:
                log.warning("datahub_sina_financial_http_failed", status=response.status_code)
                raise ProviderError("vendor_unreachable")
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_RESPONSE_BYTES:
                    log.warning("datahub_sina_financial_response_limit")
                    raise ProviderError("vendor_schema_invalid")
        payload = json.loads(
            raw,
            object_pairs_hook=_financial_json_object,
            parse_float=_financial_json_float,
            parse_constant=_financial_json_float,
        )
        result = payload["result"]
        if type(result["status"]["code"]) is not int or result["status"]["code"] != 0:
            raise ValueError("invalid_status")
        data = result["data"]
        count = data["report_count"]
        if not isinstance(count, str) or re.fullmatch(r"[0-9]+", count) is None:
            raise ValueError("invalid_count")
        total = int(count)
        dates, reports = data["report_date"], data["report_list"]
        if (
            not isinstance(dates, list)
            or not 1 <= len(dates) <= 8
            or not isinstance(reports, dict)
            or total < len(dates)
        ):
            raise ValueError("invalid_reports")
        rows, periods = [], []
        for entry in dates:
            key = entry["date_value"]
            period = _sina_day(key)
            if (period.month, period.day) not in {(3, 31), (6, 30), (9, 30), (12, 31)}:
                raise ValueError("invalid_period")
            if type(entry["date_type"]) is not int or entry["date_type"] != period.month // 3:
                raise ValueError("period_type_conflict")
            if key in periods:
                raise ValueError("duplicate_period")
            periods.append(key)
            report = reports[key]
            if report["rType"] != "合并期末" or report["rCurrency"] != "CNY":
                raise ValueError("report_identity_conflict")
            publication = report.get("publish_date")
            publication_day = _sina_day(publication) if publication not in (None, "") else None
            if publication_day is not None and publication_day < period:
                raise ValueError("publication_period_conflict")
            if (
                publication_day is not None
                and publication_day > datetime.now(ZoneInfo("Asia/Shanghai")).date()
            ):
                raise ValueError("future_publication")
            updated = report["update_time"]
            if type(updated) is not int or not 0 < updated <= int(time.time()):
                raise ValueError("invalid_supplier_update")
            items = report["data"]
            if not isinstance(items, list) or not items or len(items) > MAX_ROWS:
                raise ValueError("invalid_items")
            seen = set()
            for item in items:
                field = item["item_field"]
                if (
                    not isinstance(field, str)
                    or not field
                    or field in seen
                    or not isinstance(item["item_title"], str)
                    or not item["item_title"]
                    or item["item_source"] != "lrb"
                ):
                    raise ValueError("invalid_item_identity")
                seen.add(field)
                value = item["item_value"]
                if value is not None and (
                    isinstance(value, bool)
                    or not isinstance(value, (str, int, float))
                    or isinstance(value, str)
                    and re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value) is None
                    or not math.isfinite(float(value))
                ):
                    raise ValueError("invalid_item_value")
            rows.append(
                {
                    **report,
                    "asset": query.parameters["asset"],
                    "report_period": period.isoformat(),
                    "report_date": entry,
                    "publication_date": publication_day.isoformat() if publication_day else None,
                    "publication_precision": "date" if publication_day else "unknown",
                    "supplier_update_time": updated,
                }
            )
        if set(periods) != set(reports):
            raise ValueError("period_report_conflict")
        requested = query.parameters.get("periods", [])
        if type(requested) is int:
            rows = sorted(rows, key=lambda row: row["report_period"], reverse=True)[:requested]
        elif requested:
            rows = [row for row in rows if row["report_period"] in requested]
        normalizer = _FinancialNormalizer(
            bytes(raw),
            str(httpx.URL(SINA_FINANCIAL_URL).copy_merge_params(params)),
            total,
            tuple(_sina_day(key).isoformat() for key in periods),
        )
        log.info("datahub_sina_financial_received", rows=len(rows), captured=len(periods))
        return DataFrame(rows), normalizer
    except (ValueError, TypeError, KeyError, AttributeError, OverflowError):
        log.warning("datahub_sina_financial_invalid")
        raise ProviderError("vendor_schema_invalid") from None
    except httpx.HTTPError:
        log.warning("datahub_sina_financial_unreachable")
        raise ProviderError("vendor_unreachable") from None


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
    normalized = [
        {
            key: None if key != "asset" and isinstance(value, bool) else value
            for key, value in row.items()
        }
        for row in normalized
    ]
    for row in normalized:
        period = _pick(row, "报告期", "report_period", "报告日期", "截止日期")
        if period is not None:
            row["report_period"] = _date(period)
        row["revenue"] = _explicit_money(_pick(row, "营业总收入", "营业收入", "营收"))
        row["net_profit"] = _explicit_money(_pick(row, "净利润"))
        row["roe"] = _number(_pick(row, "净资产收益率", "净资产收益率(%)"))
        row["gross_profit_margin"] = _number(_pick(row, "销售毛利率", "毛利率", "销售毛利率(%)"))
    return normalized


def _invoke_sdk(query: BusinessQuery):
    validate_supported_query(query)
    import akshare as ak

    capability = query.capability
    parameters = query.parameters
    if capability == "factor_macro":
        return _china_macro(query)
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
        if parameters.get("statements") == ["income_statement"]:
            return _sina_income_statement(query)
        return (
            ak.stock_financial_abstract_ths(
                symbol=_symbol(str(parameters["asset"])), indicator="按报告期"
            ),
            _normalize_financials,
        )
    if capability == "market_activity":
        symbol = _symbol(str(parameters["asset"]))
        market = _exchange_symbol(str(parameters["asset"]))[:2]
        try:
            frame = ak.stock_individual_fund_flow(stock=symbol, market=market)
        except Exception as exc:  # noqa: BLE001 - fixed SDK boundary.
            log.warning("datahub_fund_flow_sdk_failed", error_type=type(exc).__name__)
            return _fund_flow_guest(query)
        return _slice_activity_frame(frame, query), _FeedNormalizer(
            _normalize_activity,
            "eastmoney",
            ({"upstream": "eastmoney", "endpoint": "akshare_sdk", "status": "snapshot"},),
        )
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
    # These already validated JSON reports contain dynamic nested item dictionaries;
    # the generic dataframe cleaner intentionally stringifies such objects.
    source_rows = (
        frame.to_dict(orient="records")
        if isinstance(normalizer, _FinancialNormalizer)
        else _records(frame)
    )
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
        elif field in {"revenue", "net_profit"}:
            unit = "元"
        elif field in {"roe", "gross_profit_margin"}:
            aliases = (
                ["净资产收益率", "净资产收益率(%)"]
                if field == "roe"
                else ["销售毛利率", "毛利率", "销售毛利率(%)"]
            )
            present = [
                (key, row[key])
                for row in result.rows
                for key in aliases
                if row.get(key) is not None
            ]
            explicit = bool(present) and all(
                isinstance(value, str) and "%" in value or key.endswith("(%)")
                for key, value in present
            )
            unit = "percent" if explicit else None
        result.fields[field] = {"unit": unit, "currency": currency}
    if query.capability == "market_activity" and result.rows:
        result.limitations.append(
            "资金字段保留来源净额；没有真实流入流出和完整构成时不生成饼图，未验证的净额单位保持未知。"
        )
    result.metadata["provider_semantics_revision"] = SEMANTICS_REVISION
    if isinstance(normalizer, _FinancialNormalizer):
        result.raw = [normalizer.raw]
        result.raw_bytes = len(normalizer.raw)
        result.source_url = normalizer.source_url
        result.provider_total = normalizer.provider_total
        result.pagination_complete = normalizer.provider_total == len(normalizer.captured_periods)
        result.status = "snapshot"
        result.metadata.update(
            {
                "schema_version": SINA_FINANCIAL_SCHEMA,
                "provider_semantics_revision": SINA_FINANCIAL_SCHEMA,
                "upstream_id": "sina",
                "transport": "direct_http_in_public_worker",
                "availability_basis": "first_observed",
                "observed_at": datetime.now(UTC).isoformat(),
                "historical_point_in_time": False,
                "formal_backtest_eligible": False,
                "revision_policy": "first_observed_not_historical_vintage",
                "field_dictionary_evidence": {
                    "schema_version": SINA_FINANCIAL_SCHEMA,
                    "endpoint": SINA_FINANCIAL_URL,
                    "statement": "lrb",
                    "unit_status": "unverified",
                    "currency_field": "rCurrency",
                    "publication_field": "publish_date",
                    "publication_precision": "date",
                    "supplier_update_field": "update_time",
                },
            }
        )
        result.fields = {
            field: {"unit": None, "currency": None, "semantic": "provider_native"}
            for field in result.fields
        }
        result.limitations.extend(
            [
                "single_response_not_complete_history",
                "financial_item_units_unverified",
                "date_precision_not_publication_instant",
                "historical_vintage_unverified",
            ]
        )
        requested = query.parameters.get("periods", [])
        missing_periods = (
            len(result.rows) < requested
            if type(requested) is int
            else bool(set(requested) - {row["report_period"] for row in result.rows})
        )
        if missing_periods:
            result.status = "partial"
            result.missing.append("requested_report_periods_missing")
        if any(row["publication_precision"] != "date" for row in result.rows):
            result.status = "partial"
            result.missing.append("publication_date_missing")
        if any(
            not any(item["item_value"] is not None for item in row["data"]) for row in result.rows
        ):
            result.status = "partial"
            result.missing.append("financial_numeric_values_missing")
    if query.capability == "market_activity" and isinstance(normalizer, _FeedNormalizer):
        result.metadata.update(
            {
                "schema_version": FUND_FLOW_SCHEMA,
                "provider_semantics_revision": FUND_FLOW_SCHEMA,
                "upstream_id": "eastmoney",
                "transport": "webguest" if normalizer.limited_history else "akshare_sdk",
                "upstream_attempts": list(normalizer.attempts),
                "independent_source": False,
                "availability_basis": "first_observed",
                "historical_point_in_time": False,
                "formal_backtest_eligible": False,
                "observed_at": datetime.now(UTC).isoformat(),
                "revision_policy": "first_observed_not_historical_vintage",
            }
        )
        result.limitations.extend(
            [
                "fund_flow_units_unverified",
                "fund_flow_definition_unverified",
                "same_eastmoney_upstream_not_independent_source",
            ]
        )
    if isinstance(normalizer, _MacroNormalizer):
        result.raw = [normalizer.raw]
        result.raw_bytes = len(normalizer.raw)
        result.source_url = normalizer.source_url
        result.provider_total = normalizer.provider_total
        result.pagination_complete = normalizer.pages_complete
        result.status = "snapshot"
        result.metadata.update(
            {
                "schema_version": CHINA_MACRO_SCHEMA,
                "provider_semantics_revision": CHINA_MACRO_SCHEMA,
                "upstream_id": "eastmoney",
                "availability_basis": "first_observed",
                "formal_backtest_eligible": False,
                "historical_point_in_time": False,
                "revision_policy": "first_observed_not_historical_vintage",
            }
        )
        result.limitations.extend(
            [
                "single_response_not_complete_history",
                "reference_period_not_publication_date",
                "native_macro_units_not_cross_source_equivalent",
            ]
        )
        for field in result.fields:
            semantic = "provider_native"
            if field.endswith("_SAME"):
                semantic = (
                    "year_to_date_year_over_year_change"
                    if normalizer.series == "gdp"
                    else "year_over_year_change"
                )
            elif field.endswith("_SEQUENTIAL"):
                semantic = "month_over_month_change"
            elif normalizer.series == "cpi" and field.endswith("_ACCUMULATE"):
                semantic = "year_to_date_index_level"
            elif field.endswith("_INDEX") or normalizer.series == "cpi" and field.endswith("_BASE"):
                semantic = "index_level"
            elif normalizer.series == "gdp" and field.endswith("_BASE"):
                semantic = "year_to_date_amount"
            elif field in {"REPORT_DATE", "TIME"}:
                semantic = "vendor_reference_label_not_publication"
            elif field == "date":
                semantic = "derived_reference_period_end"
            unit = (
                "CNY_100million"
                if normalizer.series == "m2"
                and field in {"BASIC_CURRENCY", "CURRENCY", "FREE_CASH"}
                else None
            )
            result.fields[field] = {
                "unit": unit,
                "currency": "CNY" if unit else None,
                "semantic": semantic,
            }
        if not result.rows or not normalizer.pages_complete:
            result.status = "partial"
            result.missing.append("macro_response_coverage_unverified")
        if any(value is None for row in result.rows for value in row.values()):
            result.status = "partial"
            result.missing.append("macro_values_missing")
    if isinstance(normalizer, _FeedNormalizer) and normalizer.limited_history:
        result.source_url = normalizer.source_url
        result.raw = [normalizer.raw]
        result.raw_bytes = len(normalizer.raw)
        result.status = "snapshot"
        result.provider_total = normalizer.provider_total
        result.pagination_complete = False
        result.metadata.update(
            {
                "upstream_id": "eastmoney",
                "upstream_attempts": list(normalizer.attempts),
                "independent_source": False,
                "availability_basis": "first_observed",
                "historical_point_in_time": False,
                "formal_backtest_eligible": False,
                "observed_at": datetime.now(UTC).isoformat(),
            }
        )
        result.limitations.extend(
            [
                "single_response_not_complete_history",
                "fund_flow_units_unverified",
                "same_eastmoney_upstream_not_independent_source",
            ]
        )
        if any(value is not None for value in _activity_bounds(query)):
            result.status = "partial"
            result.missing.append("fund_flow_history_coverage_unverified")
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
        reason = _probe_failure_code(exc)
        if reason == "probe_failed":
            reason = "provider_error"
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
