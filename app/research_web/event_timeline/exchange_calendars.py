"""Fixed exchange publications; dates are announced exceptions, not a PIT calendar."""

import calendar
import io
import json
import re
from datetime import date

from bs4 import BeautifulSoup

EXCHANGE_SOURCES = {
    "sse_trading_calendar": {
        "label": "上交所休市安排",
        "url": "https://www.sse.com.cn/disclosure/dealinstruc/closed/",
        "market": "CN",
    },
    "nyse_trading_calendar": {
        "label": "NYSE 交易日历",
        "url": "https://www.nyse.com/trade/hours-calendars",
        "market": "US",
    },
    "hkex_securities_2026": {
        "label": "港交所证券市场 2026 年休市公告",
        "url": (
            "https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/"
            "Participant-and-Members-Circulars/SEHK/2025/ce_SEHK_CT_075_2025.pdf"
        ),
        "market": "HK",
    },
    "hkex_securities_calendar": {
        "label": "港交所证券市场日历（2027 年起）",
        "url": "https://www.hkex.com.hk/news/hkex-calendar?sc_lang=en",
        "market": "HK",
    },
}
_MONTHS = {name: i for i, name in enumerate(calendar.month_name) if name}
_MONTH = "|".join(_MONTHS)
_WEEKDAY = "|".join(calendar.day_name)
_CN_DATE = r"([0-9]{1,2})月([0-9]{1,2})日(?:[（(][^）)]{1,12}[）)])?"
_STATE = {"closed": "休市", "half_day": "半日市", "reopen": "复市"}
_TZ = {"CN": "Asia/Shanghai", "US": "America/New_York", "HK": "Asia/Hong_Kong"}


def _record(source, status, day, end=None, label="", *, close_local=None, published=None):
    if end is not None and end < day:
        raise ValueError("exchange_calendar_reversed_range")
    details = EXCHANGE_SOURCES[source]
    return {
        "external_id": f"{status}:{day.isoformat()}",
        "title": f"{details['label']} · {_STATE[status]}" + (f" · {label[:120]}" if label else ""),
        "category": "calendar",
        "source_url": details["url"],
        "calendar_status": status,
        "calendar_close_local": close_local,
        "calendar_timezone": _TZ[details["market"]],
        "occurrence_start": day.isoformat(),
        "occurrence_end": end.isoformat() if end is not None and end != day else None,
        "date_precision": "day",
        "markets": [details["market"]],
        "lifecycle": "announced",
        "occurrence_evidence": "schedule_only",
        "source_published_at": published,
        "description": "交易所已公布安排；不代表实际开闭市证明或历史时点资格。",
        "formal_backtest_eligible": False,
    }


def _sse(source, raw):
    soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    events = []
    for heading in soup.select(".sse_colContent strong"):
        match = re.fullmatch(r"(20[0-9]{2})年休市安排", heading.get_text(strip=True))
        if not match:
            continue
        year = int(match[1])
        wrapper = heading.find_next_sibling("div", class_="table-responsive")
        if wrapper is None:
            raise ValueError("sse_calendar_table_missing")
        for row in wrapper.select("tr"):
            cols = row.find_all("td", recursive=False)
            if not cols:
                continue
            if len(cols) != 2:
                raise ValueError("sse_calendar_row_invalid")
            label, description = [re.sub(r"\s+", "", c.get_text()) for c in cols]
            # The annual table explicitly supplies both range endpoints and
            # resumption. Weekend exceptions are read only when separately stated.
            main = re.match(
                _CN_DATE + r"(?:至" + _CN_DATE + r")?休市[，,]" + _CN_DATE + r"起照常开市",
                description,
            )
            if main is None:
                raise ValueError("sse_calendar_announcement_unrecognized")
            a, b, c, d, e, f = main.groups()
            start = date(year, int(a), int(b))
            end = date(year, int(c), int(d)) if c and d else start
            reopen = date(year, int(e), int(f))
            if reopen <= end:
                raise ValueError("sse_calendar_reopen_invalid")
            label = label.rstrip("：:")
            events.append(_record(source, "closed", start, end, label))
            events.append(_record(source, "reopen", reopen, label=label))
            extra = re.search(r"另外[，,](.*?)为周末休市", description[main.end() :])
            if extra:
                for month, day in re.findall(_CN_DATE, extra[1]):
                    events.append(
                        _record(
                            source, "closed", date(year, int(month), int(day)), label="公告周末休市"
                        )
                    )
    return events


def _english_date(year, month, day, weekday):
    result = date(year, _MONTHS[month], int(day))
    if calendar.day_name[result.weekday()] != weekday:
        raise ValueError("exchange_calendar_weekday_mismatch")
    return result


def _nyse(source, raw):
    soup = BeautifulSoup(raw.decode("utf-8"), "html.parser")
    events, tables = [], 0
    for table in soup.find_all("table"):
        rows = [
            [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"], recursive=False)]
            for row in table.find_all("tr")
        ]
        if not rows or not rows[0] or rows[0][0] != "Holiday":
            continue
        if len(rows[0]) < 2 or any(not re.fullmatch("20[0-9]{2}", v) for v in rows[0][1:]):
            raise ValueError("nyse_calendar_year_header_invalid")
        tables += 1
        years = [int(v) for v in rows[0][1:]]
        for row in rows[1:]:
            if len(row) != len(years) + 1:
                raise ValueError("nyse_calendar_row_invalid")
            for year, cell in zip(years, row[1:]):
                if re.fullmatch(r"[—–-]\**", cell):
                    continue
                match = re.fullmatch(
                    rf"({_WEEKDAY}),\s+({_MONTH})\s+([0-9]{{1,2}})(?:\s*\([^()]+\))?\s*\**",
                    cell,
                )
                if not match:
                    raise ValueError("nyse_calendar_date_unrecognized")
                weekday, month, day = match.groups()
                events.append(
                    _record(
                        source, "closed", _english_date(year, month, day, weekday), label=row[0]
                    )
                )
    if tables != 1 or not events:
        raise ValueError("nyse_calendar_table_missing_or_ambiguous")
    for node in soup.find_all(
        string=lambda value: value and "Each market will close early at " in value
    ):
        if node.parent.name in {"script", "style"}:
            continue
        # Only equity closure time, excluding the options/extended session time.
        early = re.match(
            r"\**\s*Each market will close early at 1:00 p\.m\. \(1:15 p\.m\. for eligible options\) on (.+)",
            str(node).strip(),
        )
        if not early:
            raise ValueError("nyse_early_close_unrecognized")
        dates = re.findall(
            rf"({_WEEKDAY}),\s+({_MONTH})\s+([0-9]{{1,2}}),\s+(20[0-9]{{2}})", early[1]
        )
        if not dates:
            raise ValueError("nyse_early_close_date_missing")
        for weekday, month, day, year in dates:
            events.append(
                _record(
                    source,
                    "half_day",
                    _english_date(int(year), month, day, weekday),
                    close_local="13:00",
                )
            )
    return events


def _hkex_pdf(source, raw):
    import pdfplumber
    from pdfminer.pdfexceptions import PDFException

    try:
        with pdfplumber.open(io.BytesIO(raw)) as document:
            if not 1 <= len(document.pages) <= 4:
                raise ValueError("hkex_pdf_page_budget")
            content = "\n".join(page.extract_text() or "" for page in document.pages)
    except (PDFException, TypeError, KeyError, OSError, RuntimeError) as exc:
        raise ValueError("hkex_pdf_unreadable") from exc
    if (
        "Hong Kong Securities Market Holiday Schedule for Year 2026" not in content
        or "CT/075/25" not in content
        or "02/06/2025" not in content
        or "Securities Market is closed on Saturdays, Sundays and Public Holidays" not in content
    ):
        raise ValueError("hkex_pdf_identity_unverified")
    before, separator, after = content.partition(
        "The following trading days are half-day trading day"
    )
    if not separator:
        raise ValueError("hkex_pdf_half_day_section_missing")
    events = []
    for day, month, weekday, label in re.findall(
        rf"(?m)^([0-9]{{1,2}}) ({_MONTH}) 2026 ({_WEEKDAY}) (.+)$", before
    ):
        events.append(
            _record(
                source,
                "closed",
                _english_date(2026, month, day, weekday),
                label=label,
                published="2025-06-02",
            )
        )
    if not events:
        raise ValueError("hkex_pdf_holidays_missing")
    for day, month, weekday, label in re.findall(
        rf"(?m)^([0-9]{{1,2}}) ({_MONTH}) 2026 \(({_WEEKDAY})\)\s*-\s*(.+)$", after
    ):
        events.append(
            _record(
                source,
                "half_day",
                _english_date(2026, month, day, weekday),
                label=label,
                published="2025-06-02",
            )
        )
    if not any(event["calendar_status"] == "half_day" for event in events):
        raise ValueError("hkex_pdf_half_day_dates_missing")
    return events


def _hkex_html(source, raw):
    # Read the bounded embedded data, not arbitrary JavaScript. Entries for
    # Stock Connect, settlements and derivatives-only operations are excluded.
    matches = re.findall(r"var calendarDataSource\s*=\s*'(\{[^\r\n]*?\})';", raw.decode("utf-8"))
    if len(matches) != 1:
        raise ValueError("hkex_calendar_data_missing")
    rows = json.loads(matches[0])["monthly"]
    if not isinstance(rows, list) or len(rows) > 10000:
        raise ValueError("hkex_calendar_row_budget")
    events = []
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("hkex_calendar_row_invalid")
        label = row.get("name", "")
        if not isinstance(label, str):
            raise TypeError("hkex_calendar_name_invalid")
        if (
            row.get("holidayIcon") == "HongKongPublicHolidays"
            and row.get("description") == "Hong Kong Market is closed"
        ):
            status = "closed"
        elif row.get("activityIcon") == "SecuritiesandDerivatives" and label.startswith(
            "Half-Day Trading Day - Afternoon Session is Closed on "
        ):
            status = "half_day"
        else:
            continue
        first, last = date.fromisoformat(row["startdate"]), date.fromisoformat(row["enddate"])
        if first.year >= 2027:
            events.append(_record(source, status, first, last, label))
    return events


def parse_calendar(source, raw):
    parsers = {
        "sse_trading_calendar": _sse,
        "nyse_trading_calendar": _nyse,
        "hkex_securities_2026": _hkex_pdf,
        "hkex_securities_calendar": _hkex_html,
    }
    results = {}
    for event in parsers[source](source, raw):
        key = event["external_id"]
        old = results.get(key)
        if old is not None and old != event:
            raise ValueError("exchange_calendar_duplicate_conflict")
        results[key] = event
    return list(results.values())
