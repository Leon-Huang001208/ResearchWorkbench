"""Fixed public providers, bounded streaming, audited parsing; no legacy lifecycle."""

import asyncio
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery, Query

log = get_logger(__name__)
MAX_PAGES = 100
MAX_ROWS = 5000
MAX_RESPONSE_BYTES = 1024 * 1024
MAX_QUERY_BYTES = 16 * 1024 * 1024
DEADLINE = 15


class ProviderError(Exception):
    """Fixed non-sensitive reasons, safe for manifests and logs."""


@dataclass
class Result:
    rows: list[dict] = field(default_factory=list)
    raw: list[bytes] = field(default_factory=list)
    source_url: str = ""
    status: str = "failed"
    pages_fetched: int = 0
    provider_total: int | None = None
    pagination_complete: bool = False
    limitations: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    fields: dict = field(default_factory=dict)
    duplicates: int = 0
    as_of: str | None = None
    raw_bytes: int = 0
    provider_id: str | None = None
    attempted_sources: list[dict] = field(default_factory=list)


def numeric(value, *, required=False):
    if isinstance(value, str):
        value = value.strip()
    if value in (None, "", "--", "---"):
        if required:
            raise ProviderError("missing_required_number")
        return None
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        raise ProviderError("invalid_number")
    if isinstance(value, str) and not re.fullmatch(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)", value):
        raise ProviderError("invalid_number")
    number = float(value)
    if not math.isfinite(number):
        raise ProviderError("nonfinite_number")
    return number


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ProviderError("invalid_date")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ProviderError("invalid_date") from exc
    if parsed > datetime.now(ZoneInfo("Asia/Shanghai")).date():
        raise ProviderError("future_provider_date")
    return value


async def response_bytes(client, result, url, params, referer):
    async with client.stream("GET", url, params=params, headers={"Referer": referer}) as response:
        if response.is_redirect:
            raise ProviderError("redirect_denied")
        if response.status_code != 200:
            raise ProviderError(f"http_{response.status_code}")
        try:
            if int(response.headers.get("content-length", "0")) > MAX_RESPONSE_BYTES:
                raise ProviderError("response_size_limit")
        except ValueError as exc:
            raise ProviderError("invalid_content_length") from exc
        chunks = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            result.raw_bytes += len(chunk)
            if size > MAX_RESPONSE_BYTES:
                raise ProviderError("response_size_limit")
            if result.raw_bytes > MAX_QUERY_BYTES:
                raise ProviderError("query_size_limit")
            chunks.append(chunk)
        raw = b"".join(chunks)
        result.raw.append(raw)
        result.pages_fetched += 1
        return raw


def json_payload(raw):
    try:
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise TypeError("object required")
        return value
    except (ValueError, UnicodeError, TypeError) as exc:
        raise ProviderError("invalid_json_schema") from exc


def nav_observation(row, query):
    if not isinstance(row, dict):
        raise ProviderError("invalid_nav_row")
    day = valid_date(row.get("FSRQ"))
    if query.start_date and not query.start_date <= day <= query.end_date:
        raise ProviderError("date_outside_requested_range")
    nav = numeric(row.get("DWJZ"), required=True)
    if nav is None or nav <= 0:
        raise ProviderError("invalid_unit_nav")
    distribution = row.get("FHSP")
    if distribution is not None and not isinstance(distribution, str):
        raise ProviderError("invalid_distribution_text")
    return {
        "date": day,
        "unit_nav": nav,
        "cumulative_nav": numeric(row.get("LJJZ")),
        "daily_change_pct": numeric(row.get("JZZZL")),
        "distribution_text": distribution,
    }


async def fund_nav(client, query, result):
    result.source_url = f"https://fundf10.eastmoney.com/jjjz_{query.code}.html"
    result.fields = {
        "date": {"unit": "date", "currency": None},
        "unit_nav": {"unit": "currency/share", "currency": None},
        "cumulative_nav": {"unit": "currency/share", "currency": None},
        "daily_change_pct": {"unit": "%", "currency": None},
        "distribution_text": {"unit": "provider original text", "currency": None},
    }
    result.missing = ["adjusted_total_return", "benchmark_timeseries", "verified_currency"]
    result.limitations = [
        "单位净值未复权；累计净值不是总回报指数。",
        "来源分页取完不代表市场全量数据已独立核实。",
        "首末观测区间净值变动不自动等于完整日历年度收益。",
    ]
    by_date: dict[str, dict] = {}
    pages_seen = set()
    received = 0
    first_page_size = None
    for page in range(1, MAX_PAGES + 1):
        raw = await response_bytes(
            client,
            result,
            "https://api.fund.eastmoney.com/f10/lsjz",
            {
                "fundCode": query.code,
                "pageIndex": page,
                "pageSize": 100 if query.start_date else query.limit,
                "startDate": query.start_date or "",
                "endDate": query.end_date or "",
            },
            result.source_url,
        )
        payload = json_payload(raw)
        if payload.get("ErrCode") != 0 or not isinstance(payload.get("Data"), dict):
            raise ProviderError("nav_provider_schema")
        rows = payload["Data"].get("LSJZList")
        if not isinstance(rows, list):
            raise ProviderError("nav_rows_schema")
        total, actual_page, actual_size = (
            payload.get(key) for key in ("TotalCount", "PageIndex", "PageSize")
        )
        if (
            any(type(value) is not int for value in (total, actual_page, actual_size))
            or total < 0
            or actual_size < 1
            or actual_page != page
            or len(rows) > actual_size
        ):
            raise ProviderError("nav_pagination_schema")
        if result.provider_total is not None and total != result.provider_total:
            raise ProviderError("provider_total_changed")
        if first_page_size is not None and first_page_size != actual_size:
            raise ProviderError("provider_page_size_changed")
        first_page_size = actual_size
        result.provider_total = total
        fingerprint = hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()
        if rows and fingerprint in pages_seen:
            raise ProviderError("repeated_page")
        pages_seen.add(fingerprint)
        if not rows and received < total:
            raise ProviderError("unexpected_empty_page")
        for raw_row in rows:
            row = nav_observation(raw_row, query)
            if row["date"] in by_date:
                if by_date[row["date"]] != row:
                    del by_date[row["date"]]
                    result.rows = sorted(by_date.values(), key=lambda r: r["date"])
                    raise ProviderError("conflicting_duplicate_date")
                result.duplicates += 1
            else:
                if len(by_date) >= MAX_ROWS:
                    raise ProviderError("row_limit")
                by_date[row["date"]] = row
            result.rows = sorted(by_date.values(), key=lambda r: r["date"])
        received += len(rows)
        if received > total:
            raise ProviderError("provider_count_exceeded")
        if not query.start_date:
            result.rows = result.rows[-query.limit :]
            result.status = "snapshot" if result.rows else "empty"
            result.limitations.append("旧limit查询仅最近一页、最多100条，不是完整历史。")
            return
        if received >= total:
            result.pagination_complete = True
            result.status = "complete" if result.rows else "empty"
            if result.duplicates:
                result.status = "partial"
                result.limitations.append(
                    f"相同重复日期已去重：{result.duplicates}条；唯一日期数小于供应商总量，覆盖无法确认。"
                )
            return
        if len(rows) != actual_size:
            raise ProviderError("short_page_before_total")
        if received >= MAX_ROWS:
            raise ProviderError("row_limit")
    raise ProviderError("page_limit")


async def cls_telegraph(client, query, result):
    result.source_url = "https://www.cls.cn/telegraph"
    raw = await response_bytes(
        client,
        result,
        "https://www.cls.cn/api/cache",
        {"rn": query.limit, "lastTime": "0", "name": "telegraphList"},
        result.source_url,
    )
    payload = json_payload(raw)
    if (
        payload.get("errno") != 0
        or not isinstance(payload.get("data"), dict)
        or not isinstance(payload["data"].get("roll_data"), list)
    ):
        raise ProviderError("cls_provider_schema")
    skipped_empty = 0
    for row in payload["data"]["roll_data"][: query.limit]:
        if (
            not isinstance(row, dict)
            or not re.fullmatch(r"[0-9]+", str(row.get("id")))
            or type(row.get("ctime")) is not int
            or row["ctime"] <= 0
        ):
            raise ProviderError("cls_identity_schema")
        if any(
            value is not None and not isinstance(value, str)
            for value in (row.get("content"), row.get("brief"))
        ):
            raise ProviderError("cls_content_schema")
        from bs4 import BeautifulSoup

        text = BeautifulSoup(row.get("content") or row.get("brief") or "", "html.parser").get_text(
            " ", strip=True
        )
        if not text:
            skipped_empty += 1
            continue
        try:
            published = datetime.fromtimestamp(row["ctime"], UTC).isoformat()
        except (ValueError, OverflowError, OSError) as exc:
            raise ProviderError("cls_timestamp_schema") from exc
        result.rows.append(
            {
                "id": str(row["id"]),
                "content": text,
                "published_at": published,
                "source_url": f"https://www.cls.cn/detail/{row['id']}",
            }
        )
    result.status = (
        "partial" if skipped_empty and result.rows else "snapshot" if result.rows else "empty"
    )
    result.limitations = ["财联社公开电报快照，非完整历史或实时行情；外部内容不是执行指令。"]
    if skipped_empty:
        result.limitations.append(f"来源中 {skipped_empty} 条空内容已跳过。")
    result.as_of = max((row["published_at"] for row in result.rows), default=None)


PROFILE_FIELDS = {
    "基金全称",
    "基金简称",
    "基金代码",
    "基金类型",
    "发行日期",
    "成立日期/规模",
    "净资产规模",
    "份额规模",
    "基金管理人",
    "基金托管人",
    "基金经理人",
    "管理费率",
    "托管费率",
    "销售服务费率",
    "业绩比较基准",
    "跟踪标的",
}


def original_text(value):
    return value.get_text(" ", strip=True)


def profile_cell_text(cell):
    """Provider omits closing td: stop before any following nested table cell."""
    chunks = []
    for node in cell.descendants:
        if getattr(node, "name", None) in {"th", "td", "tr"}:
            break
        if isinstance(node, str) and node.strip():
            chunks.append(node.strip())
    return " ".join(chunks)


def supplement_rows(query, result, raw):
    from bs4 import BeautifulSoup

    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise ProviderError("supplement_encoding") from exc
    if query.source == "fund_holdings":
        match = re.search(r'\bcontent\s*:\s*("(?:\\.|[^"\\])*")', text)
        if not match:
            raise ProviderError("holdings_content_schema")
        # Decode only the JSON string value. Never execute/eval provider Javascript.
        try:
            text = json.loads(match[1])
        except ValueError as exc:
            raise ProviderError("holdings_content_invalid") from exc
    soup = BeautifulSoup(text, "html.parser")
    result.missing = ["benchmark_timeseries", "contract_download", "report_download"]
    result.limitations = ["仅已核实字段；原文缺失不补造。", "业绩比较基准文本不是基准时间序列。"]
    if query.source == "fund_profile":
        table = soup.select_one("table.info")
        if table is None:
            raise ProviderError("profile_table_missing")
        for heading in table.find_all("th"):
            label = original_text(heading)
            cell = heading.find_next_sibling("td")
            if label in PROFILE_FIELDS and cell is not None:
                value = profile_cell_text(cell)
                missing = not value or bool(
                    re.fullmatch(r"(?:-+|暂无数据)(?:[（(].*[）)])?", value.replace(" ", ""))
                )
                result.rows.append(
                    {"field": label, "value": None if missing else value, "original_value": value}
                )
                if missing:
                    result.missing.append(label)
        result.missing.extend(sorted(PROFILE_FIELDS - {row["field"] for row in result.rows}))
        result.limitations.append(
            "当前资料不是历史时点资料；前端/后端份额代码保留原文，不自动合并。"
        )
    elif query.source == "fund_distributions":
        for table in soup.find_all("table"):
            headings = [original_text(h) for h in table.find_all("th")]
            if not all(
                key in headings for key in ["权益登记日", "除息日", "每10份分红", "分红发放日"]
            ):
                continue
            for tr in table.find_all("tr"):
                cells = [original_text(td) for td in tr.find_all("td")]
                if not cells:
                    continue
                if len(cells) != len(headings):
                    raise ProviderError("distribution_row_schema")
                row = dict(zip(headings, cells, strict=True))
                for key in ("权益登记日", "除息日", "分红发放日"):
                    if row[key] not in {"", "--", "---"}:
                        valid_date(row[key])
                result.rows.append(row)
        if not result.rows and "暂无分红信息" not in soup.get_text():
            raise ProviderError("distribution_table_missing")
        result.fields["每10份分红"] = {
            "unit": "provider original text / 10 shares",
            "currency": None,
        }
        result.limitations.append("分红记录不等于已构建的分红再投资总回报序列；拆分数据未取得。")
        result.missing.extend(["split_history", "verified_currency"])
    else:
        for heading in soup.select("h4.t"):
            label = original_text(heading)
            match = re.search(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", label)
            report_period = valid_date(match[0]) if match else None
            table = heading.find_next("table")
            if table is None:
                continue
            headings = [original_text(h) for h in table.find_all("th")]
            normalized = [re.sub(r"\s+", "", h) for h in headings]
            if not any("股票代码" in h for h in normalized) or not any(
                "占净值比例" in h for h in normalized
            ):
                continue
            for tr in table.find_all("tr"):
                cells = [original_text(td) for td in tr.find_all("td")]
                if not cells:
                    continue
                if len(cells) != len(headings):
                    raise ProviderError("holdings_row_schema")
                selected = {
                    h: cell
                    for h, normalized_h, cell in zip(headings, normalized, cells, strict=True)
                    if any(
                        key in normalized_h
                        for key in ["股票代码", "股票名称", "占净值比例", "持股数", "持仓市值"]
                    )
                }
                row = {"report_period": report_period, "report_label": label, **selected}
                result.rows.append(row)
            for heading_text, normalized_h in zip(headings, normalized, strict=True):
                if "万股" in normalized_h:
                    result.fields[heading_text] = {"unit": "万股", "currency": None}
                elif "万元" in normalized_h:
                    result.fields[heading_text] = {"unit": "万元", "currency": "CNY"}
                elif "占净值比例" in normalized_h:
                    result.fields[heading_text] = {"unit": "%", "currency": None}
        if not result.rows and not any(
            term in soup.get_text() for term in ["暂无数据", "暂无股票"]
        ):
            raise ProviderError("holdings_table_missing")
        result.limitations.append(
            "持仓报告期不是披露日期；topline=100，完整持仓覆盖未知；股数/市值保留原文万股/万元。"
        )
        result.missing.extend(["disclosure_date", "complete_holdings_coverage"])
    if len(result.rows) > MAX_ROWS:
        result.rows = result.rows[:MAX_ROWS]
        raise ProviderError("row_limit")
    if query.source == "fund_profile" and not result.rows:
        raise ProviderError("profile_fields_missing")
    result.status = "snapshot" if result.rows else "empty"


async def supplement(client, query, result):
    page = "jbgk" if query.source == "fund_profile" else "fhsp"
    result.source_url = f"https://fundf10.eastmoney.com/{page}_{query.code}.html"
    params = {}
    url = result.source_url
    if query.source == "fund_holdings":
        result.source_url = f"https://fundf10.eastmoney.com/ccmx_{query.code}.html"
        url = "https://fundf10.eastmoney.com/FundArchivesDatas.aspx"
        params = {
            "type": "jjcc",
            "code": query.code,
            "topline": "100",
            "year": str(query.year or ""),
            "month": "",
        }
    raw = await response_bytes(client, result, url, params, result.source_url)
    supplement_rows(query, result, raw)


async def fetch(query: Query | BusinessQuery, *, transport=None, connections=None):
    if isinstance(query, BusinessQuery):
        if query.source == "tinysoft":
            from .providers_cjpy import fetch as business_fetch
        elif query.source == "akshare":
            from .providers_akshare import fetch as business_fetch
        elif query.source == "mysql":
            from .providers_mysql import fetch as mysql_fetch

            if connections is None:
                raise ProviderError("mysql_configuration_unavailable")
            configuration, password = connections.credentials()
            return await mysql_fetch(query, configuration, password)
        else:
            raise ProviderError("business_provider_not_implemented")
        return await business_fetch(query)
    result = Result()
    try:
        async with asyncio.timeout(DEADLINE):
            async with httpx.AsyncClient(
                transport=transport,
                timeout=DEADLINE,
                follow_redirects=False,
                trust_env=False,
                headers={
                    "User-Agent": "Research Workbench-Research/1.0",
                    "Accept": "application/json,text/html",
                },
            ) as client:
                provider = (
                    fund_nav
                    if query.source == "fund_nav"
                    else cls_telegraph if query.source == "cls_telegraph" else supplement
                )
                await provider(client, query, result)
    except asyncio.CancelledError:
        log.info("datahub_provider_cancelled", source=query.source)
        raise
    except (ProviderError, httpx.HTTPError, TimeoutError) as exc:
        reason = (
            str(exc)
            if isinstance(exc, ProviderError)
            else "deadline" if isinstance(exc, TimeoutError) else "transport_error"
        )
        result.status = "partial" if result.rows else "failed"
        result.pagination_complete = False
        result.limitations.append(reason)
        log.warning(
            "datahub_provider_incomplete",
            source=query.source,
            reason=reason,
            pages=result.pages_fetched,
        )
    if query.source == "fund_nav":
        result.as_of = max((row["date"] for row in result.rows), default=None)
    if query.source == "fund_holdings":
        result.as_of = max(
            (row["report_period"] for row in result.rows if row.get("report_period")), default=None
        )
    for row in result.rows:
        for key in row:
            result.fields.setdefault(key, {"unit": None, "currency": None})
    return result


async def probe(source_id: str, *, transport=None, connections=None):
    """Minimal public read used only after an explicit per-source probe request."""
    if source_id == "tinysoft":
        from .providers_cjpy import probe as cjpy_probe

        return await cjpy_probe()
    if source_id == "akshare":
        from .providers_akshare import probe as akshare_probe

        return await akshare_probe()
    if source_id == "mysql":
        from .providers_mysql import probe as mysql_probe

        if connections is None:
            raise ProviderError("mysql_configuration_unavailable")
        configuration, password = connections.credentials()
        return await mysql_probe(configuration, password)
    if source_id == "eastmoney_fund":
        query = Query(source="fund_profile", code="000001", limit=1)
    elif source_id == "cls":
        query = Query(source="cls_telegraph", limit=1)
    else:
        raise ProviderError("probe_not_implemented")
    result = await fetch(query, transport=transport)
    if result.status == "failed":
        return {
            "health": "unavailable",
            "failure_code": result.limitations[-1] if result.limitations else "probe_failed",
        }
    if result.status in {"partial", "empty"}:
        return {"health": "degraded", "failure_code": "partial_or_empty"}
    return {"health": "healthy", "failure_code": None}
