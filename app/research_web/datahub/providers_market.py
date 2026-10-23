"""Bounded, session-free market readers using fixed public vendor contracts.

The field mappings follow the installed AKShare Eastmoney adapters.  We retain
the exchange, quote timestamp and paging evidence those DataFrames discard.
This reader deliberately does not inherit the single-asset 5,000-row limit.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

log = get_logger(__name__)
TZ = ZoneInfo("Asia/Shanghai")
QUOTE_HOST = "https://82.push2.eastmoney.com"
QUOTE_PUBLIC_PREFIX = "/webguest"
HISTORY_HOST = "https://push2his.eastmoney.com"
CALENDAR_URL = "https://finance.sina.com.cn/realstock/company/klc_td_sh.txt"
SOURCE_URL = "https://quote.eastmoney.com/center/gridlist.html#hs_a_board"
MAX_ROWS = 20_000
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_QUERY_BYTES = 32 * 1024 * 1024
PAGE_SIZE = 100
SECTIONS = frozenset({"quotes", "indices", "industry", "concept", "flows", "calendar", "members"})
# Match the vendor's current hs_a_board/sh_a_board/sz_a_board/bj_a_board
# contracts in https://quote.eastmoney.com/center/static/build/index.js.
# The legacy s:2048 Beijing pool also contains non-equity instruments.
SCOPES = {
    "SH": "m:1 t:2 f:!2,m:1 t:23 f:!2",
    "SZ": "m:0 t:6 f:!2,m:0 t:80 f:!2",
    "BJ": "m:0 t:81 s:262144 f:!2",
}
QUOTE_FIELDS = (
    "f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13,f14,f20,f21,f23,f24,f25,f26,f124,f292,f350,f351"
)
BOARD_FIELDS = "f2,f3,f6,f8,f12,f13,f14,f20,f104,f105,f128,f136,f124"
INDEXES = (
    ("000001.SH", "上证指数", "1.000001"),
    ("399001.SZ", "深证成指", "0.399001"),
    ("000016.SH", "上证50", "1.000016"),
    ("000680.SH", "科创综指", "1.000680"),
    ("399006.SZ", "创业板指", "0.399006"),
    ("399673.SZ", "创业板50", "0.399673"),
    ("000688.SH", "科创50", "1.000688"),
    ("899050.BJ", "北证50", "0.899050"),
    ("000300.SH", "沪深300", "1.000300"),
    ("000905.SH", "中证500", "1.000905"),
    ("000510.SH", "中证A500", "1.000510"),
    ("000852.SH", "中证1000", "1.000852"),
)
FLOW_FIELDS = {
    "today": ("1", "f3", "f62", "f184", "f66", "f72", "f78", "f84"),
    "5d": ("5", "f109", "f164", "f165", "f166", "f168", "f170", "f172"),
    "10d": ("10", "f160", "f174", "f175", "f176", "f178", "f180", "f182"),
}


class MarketProviderError(Exception):
    """Fixed, non-sensitive transport or contract failure."""

    def __init__(self, code: str, message: str = "行情来源暂不可用，请稍后重试。"):
        super().__init__(message)
        self.code = code
        self.message = message


def _now() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _trade_status(value: Any) -> str:
    number = _number(value)
    if number is None or number != int(number) or not 1 <= number <= 19:
        return "unknown"
    return {6: "suspended", 8: "suspended", 14: "suspended", 9: "unlisted", 7: "delisted"}.get(
        int(number), "normal"
    )


def _text(value: Any, limit: int = 120) -> str:
    if not isinstance(value, str) or len(value) > limit or any(ord(c) < 32 for c in value):
        raise MarketProviderError("market_invalid_text", "行情来源返回了无效名称。")
    return value


def _timestamp(value: Any) -> str | None:
    number = _number(value)
    if number is None or number <= 0:
        return None
    try:
        stamp = datetime.fromtimestamp(number, TZ)
    except (ValueError, OverflowError, OSError):
        return None
    if stamp.year < 1990 or stamp > datetime.now(TZ) + timedelta(minutes=5):
        return None
    return stamp.isoformat(timespec="seconds")


def _listing_date(value: Any) -> str | None:
    text = str(value)
    if not re.fullmatch(r"[0-9]{8}", text):
        return None
    try:
        return date.fromisoformat(f"{text[:4]}-{text[4:6]}-{text[6:]}").isoformat()
    except ValueError:
        return None


def _code(row: dict) -> str:
    value = row.get("f12")
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{6}", value):
        raise MarketProviderError("market_invalid_identity", "行情来源返回了无效证券身份。")
    return value


def _board_id(row: dict) -> str:
    value = row.get("f12")
    if not isinstance(value, str) or not re.fullmatch(r"BK[0-9]{4,6}", value):
        raise MarketProviderError("market_invalid_board", "行情来源返回了无效板块身份。")
    return value


def _calendar_payload(raw: bytes) -> str:
    """Parse only the vendor's data assignment and its fixed optional alias."""
    try:
        text = raw.decode("utf-8")
        match = re.fullmatch(
            r'\s*var\s+datelist\s*=\s*("[^"\r\n]*")\s*;?\s*'
            r"(?:var\s+KLC_TD_SH\s*=\s*datelist\s*;?\s*)?",
            text,
        )
        if not match:
            raise ValueError("calendar wrapper")
        encoded = json.loads(match[1])
        if not isinstance(encoded, str):
            raise TypeError("calendar payload")
        return encoded
    except (ValueError, UnicodeError, TypeError) as exc:
        raise MarketProviderError(
            "market_calendar_unavailable", "交易日历返回了无效数据。"
        ) from exc


class _Reader:
    def __init__(self, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> None:
        self.client = client
        self.semaphore = semaphore
        self.pages = 0
        self.raw_bytes = 0

    async def raw(self, url: str, params: dict | None = None) -> bytes:
        async with (
            self.semaphore,
            self.client.stream(
                "GET",
                url,
                params=params,
                headers={
                    "Referer": "https://quote.eastmoney.com/",
                    "User-Agent": "ResearchWorkbench/1.0",
                },
            ) as response,
        ):
            if response.is_redirect:
                raise MarketProviderError("market_redirect_denied")
            if response.status_code != 200:
                raise MarketProviderError("market_upstream_http")
            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                self.raw_bytes += len(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES or self.raw_bytes > MAX_QUERY_BYTES:
                    raise MarketProviderError("market_response_limit", "行情数据超过安全读取上限。")
            self.pages += 1
            return bytes(chunks)

    async def json(self, path: str, params: dict, *, history: bool = False) -> dict:
        base = HISTORY_HOST if history else QUOTE_HOST + QUOTE_PUBLIC_PREFIX
        raw = await self.raw(base + path, params)
        try:
            payload = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise MarketProviderError("market_invalid_json") from exc
        if not isinstance(payload, dict):
            raise MarketProviderError("market_invalid_schema")
        return payload


class MarketProvider:
    """An owned HTTP client, bounded section reads, and exact cancellation."""

    def __init__(
        self, *, transport=None, client: httpx.AsyncClient | None = None, deadline: float = 60
    ):
        self._owned = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(10, connect=5),
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        )
        self._semaphore = asyncio.Semaphore(3)
        self._deadline = deadline
        self._closed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        await self.close()

    async def close(self) -> None:
        self._closed = True
        if self._owned:
            await self._client.aclose()

    async def fetch(
        self,
        section: str,
        *,
        board_id: str | None = None,
        kind: str = "industry",
        period: str = "today",
    ) -> dict:
        if (
            section not in SECTIONS
            or kind not in {"industry", "concept"}
            or period not in FLOW_FIELDS
        ):
            raise MarketProviderError("market_invalid_request", "不支持的行情查询参数。")
        if section == "members" and (
            not isinstance(board_id, str) or not re.fullmatch(r"BK[0-9]{4,6}", board_id)
        ):
            raise MarketProviderError("market_invalid_request", "板块代码无效。")
        if self._closed:
            raise MarketProviderError("market_closed")
        started = _now()
        reader = _Reader(self._client, self._semaphore)
        try:
            async with asyncio.timeout(self._deadline):
                if section == "quotes":
                    result = await self._quotes(reader)
                elif section == "indices":
                    result = await self._indices(reader)
                elif section in {"industry", "concept"}:
                    result = await self._boards(reader, section)
                elif section == "flows":
                    result = await self._flows(reader, kind, period)
                elif section == "members":
                    result = await self._members(reader, board_id or "", kind)
                else:
                    result = await self._calendar(reader)
        except asyncio.CancelledError:
            log.info("market_provider_cancelled", section=section)
            raise
        except (TimeoutError, httpx.TimeoutException) as exc:
            log.warning("market_provider_failed", section=section, code="market_timeout")
            raise MarketProviderError("market_timeout", "行情采集超时，已保留上一份数据。") from exc
        except httpx.HTTPError as exc:
            log.warning("market_provider_failed", section=section, code="market_network_error")
            raise MarketProviderError("market_network_error") from exc
        except MarketProviderError as exc:
            log.warning("market_provider_failed", section=section, code=exc.code)
            raise
        result.update(started_at=started, retrieved_at=_now(), pages_fetched=reader.pages)
        log.info(
            "market_provider_read",
            section=section,
            rows=len(result["rows"]),
            complete=result["complete"],
        )
        return result

    @staticmethod
    def _result(rows: list[dict], total: int, issues: list[str], **extra) -> dict:
        stamps = [stamp for row in rows if isinstance(stamp := row.get("as_of"), str)]
        result: dict[str, Any] = {
            "rows": rows,
            "summary": {},
            "provider": "eastmoney",
            "source_url": SOURCE_URL,
            "as_of": max(stamps) if stamps else None,
            "provider_total": total,
            "pagination_complete": not issues,
            "complete": not issues,
            "missing": {},
            "limitations": list(dict.fromkeys(issues)),
        }
        if stamps:
            result["quote_time_range"] = {"min": min(stamps), "max": max(stamps)}
        result.update(extra)
        return result

    async def _paginate(
        self, reader: _Reader, scope: str, fields: str, extra: dict | None = None
    ) -> tuple[list[dict], int, list[str]]:
        params = {
            "pn": 1,
            "pz": PAGE_SIZE,
            "po": "0",
            "np": "1",
            "fltt": "2",
            "invt": "2",
            "fid": "f12",
            "fs": scope,
            "fields": fields,
            "ut": "bd1d9ddb04089700cf9c27f6f7426281",
            **(extra or {}),
        }
        total = None
        collected: dict[tuple, dict] = {}
        issues = []
        received = 0
        for page in range(1, math.ceil(MAX_ROWS / PAGE_SIZE) + 1):
            params["pn"] = page
            try:
                payload = await reader.json("/api/qt/clist/get", params)
                data = payload.get("data")
                if not isinstance(data, dict) or isinstance(data.get("total"), bool):
                    raise MarketProviderError("market_invalid_schema")
                current_total = data.get("total")
                if not isinstance(current_total, int) or current_total < 0:
                    raise MarketProviderError("market_invalid_total")
                if current_total > MAX_ROWS:
                    raise MarketProviderError("market_row_limit", "行情股票池超过独立容量上限。")
                if total is None:
                    total = current_total
                elif total != current_total:
                    issues.append("采集期间来源总数发生变化，未认证完整覆盖。")
                rows = data.get("diff")
                if isinstance(rows, dict):
                    rows = list(rows.values())
                if rows is None and current_total == 0:
                    rows = []
                if not isinstance(rows, list) or len(rows) > PAGE_SIZE:
                    raise MarketProviderError("market_invalid_rows")
                if any(not isinstance(row, dict) for row in rows):
                    raise MarketProviderError("market_invalid_row")
            except (MarketProviderError, httpx.HTTPError) as exc:
                if total is None:
                    raise
                code = exc.code if isinstance(exc, MarketProviderError) else "market_network_error"
                issues.append(f"分页未完成（{code}），已取得数据仅供部分覆盖查看。")
                break
            received += len(rows)
            for row in rows:
                key = (row.get("f13"), row.get("f12"))
                if key in collected:
                    issues.append("来源分页含重复证券，未认证完整覆盖。")
                collected[key] = row
            expected = min(PAGE_SIZE, max(0, total - (page - 1) * PAGE_SIZE))
            if len(rows) != expected:
                issues.append("来源分页缺失或长度不符，未认证完整覆盖。")
            if not rows or page * PAGE_SIZE >= total:
                break
        if total is None:
            raise MarketProviderError("market_invalid_schema")
        if len(collected) != total or received != total:
            issues.append("唯一证券数与来源总数不一致，未认证完整覆盖。")
        return list(collected.values()), total, list(dict.fromkeys(issues))

    @staticmethod
    def _quote(row: dict, exchange: str) -> dict:
        code = _code(row)
        if row.get("f13") != (1 if exchange == "SH" else 0):
            raise MarketProviderError("market_exchange_mismatch")
        board = (
            "beijing"
            if exchange == "BJ"
            else (
                "star"
                if exchange == "SH" and code.startswith(("688", "689"))
                else "chinext" if exchange == "SZ" and code.startswith(("300", "301")) else "main"
            )
        )
        mapping = {
            "price": "f2",
            "change_pct": "f3",
            "change": "f4",
            "amount": "f6",
            "amplitude_pct": "f7",
            "turnover_rate_pct": "f8",
            "pe_dynamic": "f9",
            "volume_ratio": "f10",
            "change_5m_pct": "f11",
            "total_market_cap": "f20",
            "float_market_cap": "f21",
            "pb": "f23",
            "change_60d_pct": "f24",
            "change_ytd_pct": "f25",
            "limit_up_price": "f350",
            "limit_down_price": "f351",
        }
        result: dict[str, Any] = {name: _number(row.get(field)) for name, field in mapping.items()}
        lots = _number(row.get("f5"))
        result.update(
            asset=f"{code}.{exchange}",
            code=code,
            name=_text(row.get("f14")),
            exchange=exchange,
            board=board,
            volume=lots * 100 if lots is not None else None,
            as_of=_timestamp(row.get("f124")),
            listing_date=_listing_date(row.get("f26")),
            trade_status=_trade_status(row.get("f292")),
            price_basis="quote",
            source_closed=row.get("f292") == 5,
        )
        if result["trade_status"] == "suspended" and result["price"] is not None:
            result["price_basis"] = "suspended_reference"
        return result

    async def _quote_details(
        self, reader: _Reader, rows: list[dict], trade_date: str | None
    ) -> int:
        """Fill only missing fields from bounded, identity/date-matched vendor details."""
        pending = [
            row
            for row in rows
            if row.get("amount") is None
            or row.get("volume") is None
            or row.get("trade_status") != "unlisted"
            and (row.get("price") is None or row.get("change_pct") is None)
        ]
        repaired = 0

        async def one(row):
            nonlocal repaired
            try:
                payload = await reader.json(
                    "/api/qt/stock/get",
                    {
                        "secid": ("1." if row["exchange"] == "SH" else "0.") + row["code"],
                        "fltt": "2",
                        "fields": "f43,f47,f48,f57,f58,f59,f60,f86,f169,f170,f292,f301",
                    },
                )
                detail = payload.get("data")
                if (
                    not isinstance(detail, dict)
                    or detail.get("f57") != row["code"]
                    or detail.get("f58") != row["name"]
                ):
                    raise MarketProviderError("market_detail_identity_mismatch")
                stamp = _timestamp(detail.get("f86"))
                if (
                    not stamp
                    or stamp[:10] != trade_date
                    or not row.get("as_of")
                    or row["as_of"][:10] != trade_date
                ):
                    raise MarketProviderError("market_detail_date_mismatch")
                changed = []
                if row.get("trade_status") in {"normal", "unknown"}:
                    for key, field in [("change", "f169"), ("change_pct", "f170")]:
                        value = _number(detail.get(field))
                        if row.get(key) is None and value is not None:
                            row[key] = value
                            changed.append(key)
                for key, field, factor in [("amount", "f48", 1), ("volume", "f47", 100)]:
                    value = _number(detail.get(field))
                    if row.get(key) is None and value is not None and value >= 0:
                        row[key] = value * factor
                        changed.append(key)
                if row.get("price") is None and row.get("trade_status") != "unlisted":
                    price, basis = _number(detail.get("f43")), (
                        "suspended_reference" if row.get("trade_status") == "suspended" else "quote"
                    )
                    if (price is None or price <= 0) and row.get("trade_status") == "suspended":
                        last, digits = _number(detail.get("f301")), _number(detail.get("f59"))
                        price = (
                            last / 10 ** int(digits)
                            if last
                            and digits is not None
                            and digits == int(digits)
                            and 0 <= digits <= 6
                            else None
                        )
                        basis = "last_traded_reference"
                        if price is None or price <= 0:
                            price, basis = _number(detail.get("f60")), "previous_close_reference"
                    if price is not None and price > 0:
                        row["price"], row["price_basis"] = price, basis
                        changed.append("price")
                if changed:
                    row["quote_detail"] = {
                        "provider": "eastmoney",
                        "source_url": QUOTE_HOST + QUOTE_PUBLIC_PREFIX + "/api/qt/stock/get",
                        "as_of": stamp,
                        "retrieved_at": _now(),
                        "fields": changed,
                    }
                    repaired += 1
            except (MarketProviderError, httpx.HTTPError) as exc:
                log.warning(
                    "market_quote_detail_unavailable",
                    asset=row["asset"],
                    code=(
                        exc.code if isinstance(exc, MarketProviderError) else "market_network_error"
                    ),
                )

        try:
            async with asyncio.timeout(10):
                await asyncio.gather(*(one(row) for row in pending[:100]))
        except TimeoutError:
            log.warning("market_quote_details_timeout", attempted=min(100, len(pending)))
        return repaired

    async def _quotes(self, reader: _Reader) -> dict:
        async def one(exchange, scope):
            try:
                raw, total, issues = await self._paginate(reader, scope, QUOTE_FIELDS)
                rows = [self._quote(row, exchange) for row in raw]
                if total == 0:
                    issues.append(f"{exchange} 来源股票池为空，未认证市场覆盖。")
                return exchange, rows, total, issues
            except (MarketProviderError, httpx.HTTPError) as exc:
                code = exc.code if isinstance(exc, MarketProviderError) else "market_network_error"
                return exchange, [], 0, [f"{exchange} 市场采集失败（{code}）。"]

        scopes = await asyncio.gather(*(one(exchange, scope) for exchange, scope in SCOPES.items()))
        rows = [row for _, items, _, _ in scopes for row in items]
        issues = [issue for _, _, _, scope_issues in scopes for issue in scope_issues]
        if len(rows) > MAX_ROWS:
            raise MarketProviderError("market_row_limit")
        if len({row["asset"] for row in rows}) != len(rows):
            issues.append("跨市场证券身份重复，未认证完整覆盖。")
        missing_time = sum(row["as_of"] is None for row in rows)
        if missing_time:
            issues.append("部分证券未提供有效行情时间；覆盖完整不表示时点全部有效。")
        # Missing timestamps affect temporal quality, but not whether every source
        # page was obtained.  Separate that from missing pages in the manifest.
        result = self._result(rows, sum(item[2] for item in scopes), issues)
        result["summary"]["scopes"] = {
            exchange: {
                "provider_total": total,
                "received": len(items),
                "complete": not scope_issues,
            }
            for exchange, items, total, scope_issues in scopes
        }
        trade_date = result["as_of"][:10] if result["as_of"] else None
        for row in rows:
            if row["listing_date"] and trade_date and row["listing_date"] > trade_date:
                row["trade_status"] = "unlisted"
            if row["trade_status"] == "unlisted":
                row["price"], row["price_basis"] = None, "unlisted"
        result["summary"]["detail_repaired"] = await self._quote_details(reader, rows, trade_date)
        missing_quotes = sum(
            (row["price"] is None or row["change_pct"] is None)
            and row["trade_status"] not in {"suspended", "unlisted"}
            for row in rows
        )
        previous_date = sum(
            row["as_of"] is not None and row["as_of"][:10] != trade_date for row in rows
        )
        result["quote_trade_date"] = trade_date
        upcoming = sum(row["trade_status"] == "unlisted" for row in rows)
        result["summary"]["upcoming_count"] = upcoming
        result["temporal_complete"] = not missing_time and not previous_date and bool(trade_date)
        for row in rows:
            row["stale"] = row["as_of"] is None or row["as_of"][:10] != trade_date
            upper, lower, price = (
                row.get(name) for name in ("limit_up_price", "limit_down_price", "price")
            )
            row["limit_status"] = "unknown"
            if row["trade_status"] in {"suspended", "unlisted", "delisted"}:
                row["limit_status"] = "not_applicable"
            elif (
                row["trade_status"] == "normal"
                and not row["stale"]
                and price is not None
                and upper is not None
                and lower is not None
                and 0 < lower < upper
                and lower <= price <= upper
            ):
                row["limit_status"] = (
                    "up" if price == upper else "down" if price == lower else "none"
                )
        result["missing"] = {
            "quote": missing_quotes,
            "as_of": missing_time,
            "quote_date": previous_date,
            "halt_status": sum(row["trade_status"] == "unknown" for row in rows),
            "amount": sum(
                row["amount"] is None and row["trade_status"] != "unlisted" for row in rows
            ),
            "price_limit_status": sum(row["limit_status"] == "unknown" for row in rows),
        }
        result["limitations"].extend(
            [
                "股票池为东方财富沪深北A股口径；分页完整性不等于交易所目录已独立核验。",
                "交易状态采用东财官网f292映射；停牌和未上市单列，不计平盘。停牌参考价按单股接口f301最后价格或f60昨收标注；不代表当日成交。",
                "缺失成交额仅用同身份、同日单股接口的真实值补取；0与空值区分。补取最多100只、10秒，与全市场快照同批留证；失败保留缺口。",
                "涨跌停以同批f350涨停价/f351跌停价与有效现价逐股比较，不以固定涨跌幅判断；限价缺失、非正值或冲突时记未知，停牌/未上市单列。未核实无价格限制的证券不推断为普通未涨跌停。",
                "成交量按来源手数换算为股，成交额和市值单位为人民币元；PE为动态口径。",
            ]
        )
        if previous_date:
            result["limitations"].append(
                "部分报价属于较早交易日，保留原行与日期；广度计入未知，不发布混合日期的成交额。"
            )
        if upcoming:
            result["limitations"].append(
                f"来源A股目录包含待上市/未上市{upcoming}只；状态取自f292，具体上市日期仅在来源f26提供时显示；不补造当日报价。"
            )
        if result["complete"]:
            result["summary"].update(self._statistics(rows, trade_date))
            result["summary"]["quote_trade_date"] = trade_date
        return result

    @staticmethod
    def _statistics(rows: list[dict], trade_date: str | None = None) -> dict:
        current = [
            row
            for row in rows
            if row.get("as_of")
            and row["as_of"][:10] == trade_date
            and row.get("trade_status") not in {"suspended", "unlisted", "delisted"}
            and not (row.get("listing_date") and trade_date and row["listing_date"] > trade_date)
        ]
        valid = [
            row for row in current if row["price"] is not None and row["change_pct"] is not None
        ]
        suspended = sum(row.get("trade_status") == "suspended" for row in rows)
        unlisted = sum(
            row.get("trade_status") == "unlisted"
            or bool(row.get("listing_date") and trade_date and row["listing_date"] > trade_date)
            for row in rows
        )
        breadth = {
            "up": sum(row["change_pct"] > 0 for row in valid),
            "down": sum(row["change_pct"] < 0 for row in valid),
            "flat": sum(row["change_pct"] == 0 for row in valid),
            "unknown": len(rows) - len(valid) - suspended - unlisted,
            "suspended": suspended,
            "unlisted": unlisted,
            "total": len(rows),
        }
        bounds = [-math.inf, -10, -7, -5, -3, 0, 3, 5, 7, 10, math.inf]
        labels = [
            "<-10%",
            "-10~-7%",
            "-7~-5%",
            "-5~-3%",
            "-3~0%",
            "0~3%",
            "3~5%",
            "5~7%",
            "7~10%",
            ">=10%",
        ]
        histogram = [
            {"label": label, "count": sum(low <= row["change_pct"] < high for row in valid)}
            for label, low, high in zip(labels, bounds, bounds[1:])
        ]
        ordered = sorted(valid, key=lambda row: (row["change_pct"], row["asset"]))
        amount_pool = [
            row
            for row in rows
            if row.get("trade_status") != "unlisted"
            and not (row.get("listing_date") and trade_date and row["listing_date"] > trade_date)
        ]
        amounts = [
            row["amount"]
            for row in amount_pool
            if row["amount"] is not None and row.get("as_of") and row["as_of"][:10] == trade_date
        ]
        amount = math.fsum(amounts) if len(amounts) == len(amount_pool) and amount_pool else None
        return {
            **breadth,
            "breadth": breadth,
            "histogram": histogram,
            "amount": amount,
            "amount_missing": len(amount_pool) - len(amounts),
            "amount_scope_count": len(amount_pool),
            "amount_pool_hash": hashlib.sha256(
                "\n".join(sorted(row["asset"] for row in amount_pool)).encode()
            ).hexdigest(),
            "closing_snapshot": bool(amount_pool)
            and all(
                row.get("source_closed") or row.get("trade_status") == "suspended"
                for row in amount_pool
            )
            and amount is not None,
            "limit_up": (
                sum(row.get("limit_status") == "up" for row in rows)
                if any(row.get("limit_status") in {"up", "down", "none"} for row in rows)
                else None
            ),
            "limit_down": (
                sum(row.get("limit_status") == "down" for row in rows)
                if any(row.get("limit_status") in {"up", "down", "none"} for row in rows)
                else None
            ),
            "limit_unknown": sum(row.get("limit_status", "unknown") == "unknown" for row in rows),
            "limit_covered": sum(row.get("limit_status") in {"up", "down", "none"} for row in rows),
            "gainers": ordered[-10:][::-1],
            "losers": ordered[:10],
        }

    async def _boards(self, reader: _Reader, kind: str) -> dict:
        raw, total, issues = await self._paginate(
            reader, "m:90 t:2 f:!50" if kind == "industry" else "m:90 t:3 f:!50", BOARD_FIELDS
        )
        rows = [
            {
                "board_id": _board_id(row),
                "name": _text(row.get("f14")),
                "kind": kind,
                "change_pct": _number(row.get("f3")),
                "amount": _number(row.get("f6")),
                "total_market_cap": _number(row.get("f20")),
                "up_count": _number(row.get("f104")),
                "down_count": _number(row.get("f105")),
                "leader_name": row.get("f128") if isinstance(row.get("f128"), str) else None,
                "leader_change_pct": _number(row.get("f136")),
                "as_of": _timestamp(row.get("f124")),
            }
            for row in raw
        ]
        result = self._result(rows, total, issues)
        result["summary"] = {"kind": kind}
        result["limitations"].append(
            "东方财富行业/概念分类，保留来源 f:!50 成员过滤口径，不等同Wind或申万分类。"
        )
        return result

    async def _flows(self, reader: _Reader, kind: str, period: str) -> dict:
        stat, change, main, ratio, super_, large, medium, small = FLOW_FIELDS[period]
        fields = f"f12,f14,f124,{change},{main},{ratio},{super_},{large},{medium},{small}"
        raw, total, issues = await self._paginate(
            reader, "m:90 t:2" if kind == "industry" else "m:90 t:3", fields, {"stat": stat}
        )
        rows = [
            {
                "board_id": _board_id(row),
                "name": _text(row.get("f14")),
                "kind": kind,
                "period": period,
                "as_of": _timestamp(row.get("f124")),
                **{
                    name: _number(row.get(field))
                    for name, field in {
                        "change_pct": change,
                        "main_net": main,
                        "main_ratio_pct": ratio,
                        "super_net": super_,
                        "large_net": large,
                        "medium_net": medium,
                        "small_net": small,
                    }.items()
                },
            }
            for row in raw
        ]
        result = self._result(rows, total, issues)
        result["summary"] = {"kind": kind, "period": period}
        result["limitations"].append(
            "资金按东方财富订单分类口径，主力为来源的大单与超大单口径，非Wind机构资金。"
        )
        try:
            result["summary"]["market_flow"] = await self._market_flow(reader)
        except (MarketProviderError, httpx.HTTPError) as exc:
            log.warning(
                "market_flow_unavailable",
                code=exc.code if isinstance(exc, MarketProviderError) else "market_network_error",
            )
            result["summary"]["market_flow"] = {
                "rows": [],
                "provider": "eastmoney",
                "source_url": QUOTE_HOST + QUOTE_PUBLIC_PREFIX + "/api/qt/stock/fflow/daykline/get",
                "retrieved_at": _now(),
                "complete": False,
                "missing": {"market_flow": 1},
            }
            result["missing"]["market_flow"] = 1
            result["limitations"].append("沪深大盘日线资金流暂不可用；板块资金仍按本次返回展示。")
        return result

    async def _market_flow(self, reader: _Reader) -> dict:
        payload = await reader.json(
            "/api/qt/stock/fflow/daykline/get",
            {
                "lmt": "30",
                "klt": "101",
                "secid": "1.000001",
                "secid2": "0.399001",
                "fields1": "f1,f2,f3,f7",
                "fields2": ",".join(f"f{n}" for n in range(51, 66)),
                "ut": "b2884a393a59ad64002292a3e90d46a5",
            },
            history=False,
        )
        data = payload.get("data")
        lines = data.get("klines") if isinstance(data, dict) else None
        if not isinstance(lines, list) or not lines or len(lines) > 100:
            raise MarketProviderError("market_invalid_flow_history")
        rows: list[dict[str, Any]] = []
        for line in lines:
            parts = line.split(",") if isinstance(line, str) else []
            if len(parts) != 15:
                raise MarketProviderError("market_invalid_flow_history")
            try:
                day = date.fromisoformat(parts[0]).isoformat()
            except ValueError as exc:
                raise MarketProviderError("market_invalid_flow_history") from exc
            if (
                day > datetime.now(TZ).date().isoformat()
                or rows
                and day <= rows[-1]["date"]
                or any(_number(value) is None for value in parts[1:6])
            ):
                raise MarketProviderError("market_invalid_flow_history")
            rows.append(
                {
                    "date": day,
                    "main_net": _number(parts[1]),
                    "small_net": _number(parts[2]),
                    "medium_net": _number(parts[3]),
                    "large_net": _number(parts[4]),
                    "super_net": _number(parts[5]),
                }
            )
        return {
            "provider": "eastmoney",
            "source_url": QUOTE_HOST + QUOTE_PUBLIC_PREFIX + "/api/qt/stock/fflow/daykline/get",
            "retrieved_at": _now(),
            "trade_date": rows[-1]["date"],
            "row_count": len(rows),
            "provider_total": len(rows),
            "complete": True,
            "name": "沪深大盘资金流",
            "scope": "SH+SZ",
            "frequency": "daily",
            "rows": rows,
            "limitations": [
                f"来源实际返回{len(rows)}个交易日；不承诺请求的30日全部可用。仅沪深口径，不含北交所；日线不是盘中资金分时。"
            ],
        }

    async def _members(self, reader: _Reader, board_id: str, kind: str) -> dict:
        raw, total, issues = await self._paginate(reader, f"b:{board_id} f:!50", "f12,f13,f14")
        rows = []
        for row in raw:
            if row.get("f13") not in {0, 1}:
                raise MarketProviderError("market_invalid_member_identity")
            rows.append({"code": _code(row), "market": row["f13"], "name": _text(row.get("f14"))})
        result = self._result(rows, total, issues)
        result["summary"] = {"board_id": board_id, "kind": kind}
        result["limitations"].append(
            "来源成员采用 f:!50 过滤，未独立证明全部成分；证券身份须与同批沪深北股票池相交。"
        )
        return result

    async def _indices(self, reader: _Reader) -> dict:
        async def one(asset, name, secid):
            row = {
                "asset": asset,
                "code": asset.split(".")[0],
                "name": name,
                "price": None,
                "change": None,
                "change_pct": None,
                "as_of": None,
                "series": [],
            }
            issues = []
            try:
                payload = await reader.json(
                    "/api/qt/stock/get",
                    {
                        "secid": secid,
                        "fltt": "2",
                        "invt": "2",
                        "fields": "f43,f57,f58,f60,f86,f169,f170",
                    },
                )
                data = payload.get("data")
                if not isinstance(data, dict) or data.get("f57") != row["code"]:
                    raise MarketProviderError("market_index_unavailable")
                row.update(
                    price=_number(data.get("f43")),
                    change=_number(data.get("f169")),
                    change_pct=_number(data.get("f170")),
                    as_of=_timestamp(data.get("f86")),
                )
                previous_close = _number(data.get("f60"))
                row["series"] = await self._index_series(
                    reader, secid, row["code"], previous_close, row["as_of"]
                )
                if row["price"] is None or row["as_of"] is None:
                    issues.append(f"{name}缺报价或有效行情时间。")
                if not row["series"]:
                    issues.append(f"{name}未提供当日分时。")
                if previous_close is None or previous_close <= 0:
                    issues.append(f"{name}缺昨收，分时涨跌幅未计算。")
            except (MarketProviderError, httpx.HTTPError) as exc:
                code = exc.code if isinstance(exc, MarketProviderError) else "market_network_error"
                issues.append(f"{name}行情或分时不可用（{code}）。")
            return row, issues

        values = await asyncio.gather(*(one(*item) for item in INDEXES))
        rows = [row for row, _ in values]
        issues = [issue for _, row_issues in values for issue in row_issues]
        dates = [row["as_of"][:10] for row in rows if row["as_of"]]
        trade_date = max(dates) if dates else None
        old_dates = 0
        for row in rows:
            row["stale"] = row["as_of"] is None or row["as_of"][:10] != trade_date
            if row["as_of"] and row["stale"]:
                old_dates += 1
                row["series"] = []
        if old_dates:
            issues.append("指数报价存在不同交易日；较早日期的分时已排除，不与当前日叠加。")
        missing = sum(row["price"] is None for row in rows)
        result = self._result(rows, len(INDEXES), issues)
        result["quote_trade_date"] = trade_date
        result["temporal_complete"] = (
            not old_dates and bool(trade_date) and all(row["as_of"] for row in rows)
        )
        result["missing"] = {
            "indices": missing,
            "intraday": sum(not row["series"] for row in rows),
            "quote_date": old_dates,
        }
        result["limitations"].append(
            "分时涨跌幅按同指数真实昨收归一化；缺失时不补线，不混合交易日。"
        )
        return result

    async def _index_series(
        self,
        reader: _Reader,
        secid: str,
        code: str,
        previous_close: float | None,
        quote_time: str | None,
    ) -> list[dict]:
        payload = await reader.json(
            "/api/qt/stock/trends2/get",
            {
                "secid": secid,
                "ndays": "1",
                "iscr": "0",
                "fields1": "f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13",
                "fields2": "f51,f52,f53,f54,f55,f56,f57,f58",
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict) or data.get("code") != code:
            raise MarketProviderError("market_index_series_identity")
        trends = data.get("trends")
        if not isinstance(trends, list) or len(trends) > 500:
            raise MarketProviderError("market_invalid_intraday")
        rows = []
        day = None
        previous_time = None
        for trend in trends:
            parts = trend.split(",") if isinstance(trend, str) else []
            if len(parts) != 8:
                raise MarketProviderError("market_invalid_intraday")
            try:
                stamp = datetime.fromisoformat(parts[0]).replace(tzinfo=TZ)
            except ValueError as exc:
                raise MarketProviderError("market_invalid_intraday") from exc
            if quote_time is None or stamp.date() != datetime.fromisoformat(quote_time).date():
                raise MarketProviderError("market_intraday_trade_date")
            if (
                day is not None
                and stamp.date() != day
                or previous_time is not None
                and stamp <= previous_time
            ):
                raise MarketProviderError("market_intraday_order")
            day, previous_time = stamp.date(), stamp
            price = _number(parts[2])
            pct = (
                (price / previous_close - 1) * 100
                if price is not None and previous_close is not None and previous_close > 0
                else None
            )
            rows.append(
                {"time": stamp.isoformat(timespec="seconds"), "price": price, "change_pct": pct}
            )
        return rows

    async def _calendar(self, reader: _Reader) -> dict:
        raw = await reader.raw(CALENDAR_URL)
        dates = await asyncio.to_thread(self._decode_calendar, raw)
        result = self._result([], len(dates), [], provider="sina", source_url=CALENDAR_URL)
        result["as_of"] = dates[-1] if dates else None
        result["summary"] = {
            "trading_dates": dates,
            "validity_until": dates[-1] if dates else None,
            "valid_until": dates[-1] if dates else None,
        }
        if not dates or dates[-1] < datetime.now(TZ).date().isoformat():
            result["complete"] = False
            result["limitations"].append("来源日历未覆盖当前日期，交易状态未知；仅保留手动刷新。")
        return result

    @staticmethod
    def _decode_calendar(raw: bytes) -> list[str]:
        try:
            import py_mini_racer
            from akshare.stock.cons import hk_js_decode

            encoded = _calendar_payload(raw)
            with py_mini_racer.MiniRacer() as context:
                context.eval(hk_js_decode, timeout=1000)
                values = context.call("d", encoded, timeout=1000)
            if not isinstance(values, list) or not 1 <= len(values) <= 50_000:
                raise ValueError("calendar rows")
            days = sorted({date.fromisoformat(str(value)[:10]).isoformat() for value in values})
            return days
        # Optional JS engines expose their own exception classes.
        except Exception as exc:
            log.warning("market_calendar_decode_failed", error_type=type(exc).__name__)
            raise MarketProviderError(
                "market_calendar_unavailable", "交易日历暂不可用，交易状态未知。"
            ) from exc
