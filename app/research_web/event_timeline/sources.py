"""Fixed public source adapters; observations are candidates, never PIT assertions."""

import asyncio
import calendar
import csv
import io
import json
import re
import zipfile
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import urlencode

import httpx

from core.observability import get_logger

from ..store import StoreError
from .exchange_calendars import EXCHANGE_SOURCES, parse_calendar
from .relevance import candidate_relevance
from .storage import fail

log = get_logger(__name__)
CATALOG = {
    "fed_fomc": {
        "label": "Federal Reserve FOMC",
        "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
        "category": "macro",
        "history": "official_schedule_page",
        "future_supported": True,
        "occurrence_evidence": "schedule_only",
    },
    "bls_cpi": {
        "label": "BLS CPI",
        "url": "https://www.bls.gov/schedule/news_release/cpi.htm",
        "category": "macro",
        "history": "official_schedule_page",
        "future_supported": True,
        "occurrence_evidence": "schedule_only",
    },
    "bls_jobs": {
        "label": "BLS Employment Situation",
        "url": "https://www.bls.gov/schedule/news_release/empsit.htm",
        "category": "macro",
        "history": "official_schedule_page",
        "future_supported": True,
        "occurrence_evidence": "schedule_only",
    },
    "gdelt": {
        "label": "GDELT 1.0 Events",
        "url": "https://data.gdeltproject.org/events/",
        "category": "geopolitics",
        "history": "annual_archives_since_1979",
        "future_supported": False,
    },
    "ucdp": {
        "label": "UCDP GED 26.1",
        "url": "https://ucdpapi.pcr.uu.se/api/gedevents/26.1",
        "category": "war",
        "history": "versioned_events_since_1989",
        "historical_start_year": 1989,
        "historical_end_year": 2025,
        "future_supported": False,
        "requires_token": True,
        "access_status": "token_required_not_configured",
        "documentation_url": "https://ucdp.uu.se/apidocs/",
    },
}
CATALOG.update(
    {
        key: {
            **value,
            "category": "calendar",
            "history": "official_exchange_publication",
            "future_supported": True,
            "occurrence_evidence": "schedule_only",
            "manual_only": True,
        }
        for key, value in EXCHANGE_SOURCES.items()
    }
)
MAX_RESPONSE = 16 * 1024 * 1024
MAX_EXPANDED = 32 * 1024 * 1024
MAX_EVENTS = 1000
MONTHS = {name.lower(): n for n, name in enumerate(calendar.month_name) if name}
MONTHS.update({name.lower(): n for n, name in enumerate(calendar.month_abbr) if name})
MONTH_PATTERN = "(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + ")"


class ReleaseTables(HTMLParser):
    """Only known BLS regular-data release tables, never footer or body prose."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.depth = 0
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.depth += 1
            if self.depth == 1 and "regular-data" in dict(attrs).get("class", "").split():
                self.table = []
        if self.table is None or self.depth != 1:
            return
        if tag == "tr":
            self.row = []
        if tag in {"th", "td"} and self.row is not None:
            self.cell = []

    def handle_endtag(self, tag):
        if self.table is not None and self.depth == 1:
            if tag in {"th", "td"} and self.cell is not None:
                self.row.append(" ".join(" ".join(self.cell).split()))
                self.cell = None
            elif tag == "tr" and self.row is not None:
                self.table.append(self.row)
                self.row = None
            elif tag == "table":
                self.tables.append(self.table)
                self.table = None
        if tag == "table":
            self.depth = max(0, self.depth - 1)

    def handle_data(self, value):
        if self.cell is not None and self.depth == 1:
            self.cell.append(value)


class FedMeetings(HTMLParser):
    """Extract native meeting rows; minutes release dates are separate evidence."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.year = None
        self.heading = None
        self.depth = 0
        self.row = None
        self.capture = None
        self.rows = []

    def handle_starttag(self, tag, attrs):
        if tag == "h4":
            self.heading = []
        if tag != "div":
            return
        classes = dict(attrs).get("class", "").split()
        if self.row is None and "fomc-meeting" in classes:
            self.row = {"year": self.year}
            self.depth = 1
        elif self.row is not None:
            self.depth += 1
            for field in ("month", "date"):
                if "fomc-meeting__" + field in classes:
                    self.capture = {"field": field, "depth": self.depth, "text": []}

    def handle_endtag(self, tag):
        if tag == "h4" and self.heading is not None:
            header = " ".join(" ".join(self.heading).split())
            match = re.fullmatch(r"(20\d{2}) FOMC Meetings", header)
            if match:
                self.year = int(match[1])
            self.heading = None
        if tag != "div" or self.row is None:
            return
        if self.capture is not None and self.capture["depth"] == self.depth:
            self.row[self.capture["field"]] = " ".join(" ".join(self.capture["text"]).split())
            self.capture = None
        self.depth -= 1
        if self.depth == 0:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, value):
        if self.heading is not None:
            self.heading.append(value)
        if self.capture is not None:
            self.capture["text"].append(value)


def _bls_calendar(source, raw):
    parser = ReleaseTables()
    parser.feed(raw.decode("utf-8", errors="strict"))
    events = []
    date_pattern = rf"(?:(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+)?({MONTH_PATTERN})\.?\s+(\d{{1,2}})\s*,\s*(20\d{{2}})"
    for table in parser.tables:
        date_column = None
        for row in table:
            headings = [re.sub(r"[^a-z]", "", cell.lower()) for cell in row]
            if "releasedate" in headings and "releasetime" in headings:
                date_column = headings.index("releasedate")
                continue
            if date_column is None or len(row) <= date_column:
                continue
            match = re.fullmatch(date_pattern, row[date_column], re.IGNORECASE)
            if match is None:
                continue
            date = (
                datetime(int(match[3]), MONTHS[match[1].lower()], int(match[2])).date().isoformat()
            )
            events.append(_event(source, date, CATALOG[source]["label"] + " release", date))
    return events


def endpoint(source, year=None, page=0):
    if source not in CATALOG or isinstance(page, bool) or not 0 <= page <= 10000:
        fail("event_source_invalid", 422)
    current = datetime.now(UTC).year
    if year is not None and (isinstance(year, bool) or not 1990 <= year <= current):
        fail("event_source_year_invalid", 422)
    base = CATALOG[source]["url"]
    if source == "gdelt":
        if year is None:
            fail("event_source_year_required", 422)
        if year <= 2005:
            if page:
                fail("event_source_page_invalid", 422)
            return base + f"{year}.zip"
        if year <= 2012:
            if page > 11:
                fail("event_source_page_invalid", 422)
            return base + f"{year}{page + 1:02d}.zip"
        if year == 2013 and page < 3:
            return base + f"2013{page + 1:02d}.zip"
        date = (
            (datetime(2013, 4, 1, tzinfo=UTC) + timedelta(days=page - 3))
            if year == 2013
            else datetime(year, 1, 1, tzinfo=UTC) + timedelta(days=page)
        )
        if date.year != year or date.date() > datetime.now(UTC).date():
            fail("event_source_page_invalid", 422)
        return base + date.strftime("%Y%m%d") + ".export.CSV.zip"
    if source == "ucdp":
        if year is None:
            fail("event_source_year_required", 422)
        if year > CATALOG["ucdp"]["historical_end_year"]:
            fail("event_source_year_outside_declared_scope", 422)
        return (
            base
            + "?"
            + urlencode(
                {
                    "pagesize": 100,
                    "page": page + 1,
                    "StartDate": f"{year}-01-01",
                    "EndDate": f"{year}-12-31",
                }
            )
        )
    if year is not None or page:
        fail("event_source_backfill_unavailable", 422)
    return base


async def _download(url):
    async with (
        httpx.AsyncClient(timeout=8, trust_env=False, follow_redirects=False) as client,
        client.stream(
            "GET",
            url,
            headers={
                "User-Agent": "ResearchWorkbench/1.0 public-event-research",
                "Accept-Encoding": "identity",
            },
        ) as response,
    ):
        if response.status_code != 200:
            fail("event_source_http_failed", 502)
        chunks, size = [], 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_RESPONSE:
                fail("event_source_response_limit", 502)
            chunks.append(chunk)
        return b"".join(chunks)


async def fetch(source, year=None, page=0):
    url = endpoint(source, year, page)
    if CATALOG[source].get("requires_token"):
        fail("event_source_credentials_required", 409)
    try:
        raw = await asyncio.wait_for(_download(url), 18)
        return url, raw
    except (OSError, TimeoutError, httpx.HTTPError, StoreError) as exc:
        log.warning("event_source_fetch_failed", source=source, error_type=type(exc).__name__)
        raise StoreError(
            "公开事件来源本次不可用，检查点已保留", "event_source_unavailable", 502
        ) from exc


def _event(source, identifier, title, start, end=None, **extra):
    date = datetime.strptime(start[:10], "%Y-%m-%d").date()
    schedule_only = CATALOG[source].get("occurrence_evidence") == "schedule_only"
    return {
        "external_id": str(identifier),
        "title": title[:300],
        "category": CATALOG[source]["category"],
        "occurrence_start": start,
        "occurrence_end": end,
        "date_precision": "day",
        **candidate_relevance(source),
        "lifecycle": (
            "announced" if schedule_only or date > datetime.now(UTC).date() else "occurred"
        ),
        "occurrence_evidence": "schedule_only" if schedule_only else "upstream_claim",
        "description": "来源机器记录／公开日程，尚待人工确认；市场相关性为待核验候选。",
        "source_published_at": None,
        "formal_backtest_eligible": False,
        **extra,
    }


def _calendar(source, raw):
    if source in {"bls_cpi", "bls_jobs"}:
        return list({event["external_id"]: event for event in _bls_calendar(source, raw)}.values())
    parser = FedMeetings()
    parser.feed(raw.decode("utf-8", errors="strict"))
    events = []
    for row in parser.rows:
        month_match = re.fullmatch(
            rf"({MONTH_PATTERN})(?:\s*/\s*({MONTH_PATTERN}))?", row.get("month", ""), re.IGNORECASE
        )
        days = re.fullmatch(
            r"(\d{1,2})(?:\s*[-–]\s*(\d{1,2}))?(?:\s*\*|\s*\([^)]{1,100}\))*", row.get("date", "")
        )
        if row["year"] is None or month_match is None or days is None:
            fail("event_source_fed_row_invalid", 502)
        year, month = row["year"], MONTHS[month_match[1].lower()]
        end_month = MONTHS[(month_match[2] or month_match[1]).lower()]
        start = datetime(year, month, int(days[1])).date().isoformat()
        end = (
            datetime(year + (end_month < month), end_month, int(days[2] or days[1]))
            .date()
            .isoformat()
        )
        notation = "notation vote" in row["date"].lower()
        unscheduled = "unscheduled" in row["date"].lower()
        event_type = (
            "fomc_notation_vote"
            if notation
            else "fomc_unscheduled_meeting" if unscheduled else "fomc_meeting"
        )
        title = (
            "FOMC notation vote"
            if notation
            else "FOMC unscheduled meeting" if unscheduled else "FOMC meeting"
        )
        events.append(
            _event(
                source,
                start,
                title,
                start,
                end,
                event_type=event_type,
                source_date_label=row["date"],
            )
        )
    return list({event["external_id"]: event for event in events}.values())


def _gdelt(raw, offset):
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        files = archive.infolist()
        if len(files) != 1 or files[0].file_size > MAX_EXPANDED or files[0].flag_bits & 1:
            fail("event_source_archive_invalid", 502)
        with archive.open(files[0]) as stream:
            content = stream.read(MAX_EXPANDED + 1)
        if len(content) > MAX_EXPANDED:
            fail("event_source_archive_limit", 502)
    events = []
    next_offset = None
    for position, row in enumerate(
        csv.reader(io.StringIO(content.decode("utf-8")), delimiter="\t")
    ):
        if position < offset:
            continue
        if len(row) not in {57, 58} or not re.fullmatch(r"\d{8}", row[1]):
            continue
        date = datetime.strptime(row[1], "%Y%m%d").date().isoformat()
        if date < "1990-01-01":
            continue
        event_code = row[26] if len(row) > 26 else "unknown"
        native_codes = {
            "Actor1Geo_CountryCode": row[37],
            "Actor2Geo_CountryCode": row[44],
            "ActionGeo_CountryCode": row[51],
        }
        relevance = candidate_relevance(
            "gdelt",
            actor_codes=(row[7], row[17]),
            event_code=event_code,
            root_code=row[28],
            native_codes=native_codes,
        )
        events.append(
            _event(
                "gdelt",
                row[0],
                f"GDELT {event_code}: {row[6]} → {row[16]}",
                date,
                original_fields=row,
                source_article_url=row[-1] if row[-1].startswith("http") else None,
                **relevance,
            )
        )
        if len(events) >= MAX_EVENTS:
            next_offset = position + 1
            break
    return events, next_offset


def parse(source, raw, *, offset=0, page=0):
    """Return explicit candidates and coverage, never infer completeness from HTTP 200."""
    try:
        next_offset, next_page = None, None
        if source == "gdelt":
            events, next_offset = _gdelt(raw, offset)
        elif source == "ucdp":
            payload = json.loads(raw)
            rows = payload.get("Result", payload.get("result", []))
            if not isinstance(rows, list):
                fail("event_source_payload_invalid", 502)
            next_page = payload.get("NextPage")
            if not isinstance(next_page, int):
                next_page = None
            total_pages = payload.get("TotalPages")
            total_count = payload.get("TotalCount")
            if (
                isinstance(total_pages, int)
                and not isinstance(total_pages, bool)
                and page + 1 < total_pages
            ) or (
                isinstance(total_count, int)
                and not isinstance(total_count, bool)
                and (page + 1) * 100 < total_count
            ):
                next_page = page + 1
            events = []
            for row in rows[:MAX_EVENTS]:
                start, end = str(row.get("date_start", ""))[:10], str(row.get("date_end", ""))[:10]
                if start < "1990-01-01":
                    continue
                precision = row.get("date_prec")
                exact = not isinstance(precision, bool) and precision in {1, "1"} and start == end
                relevance = candidate_relevance(
                    source,
                    violence_type=row.get("type_of_violence"),
                    native_codes=row.get("country_id"),
                )
                events.append(
                    _event(
                        source,
                        row["id"],
                        str(
                            row.get("conflict_name")
                            or row.get("country")
                            or "UCDP organized violence"
                        ),
                        start,
                        end or None,
                        original_fields=row,
                        source_date_precision=precision,
                        date_precision=(
                            "day" if exact else "interval" if end and end != start else "unknown"
                        ),
                        exact_occurrence_date=start if exact else None,
                        event_time_eligible=exact,
                        **relevance,
                    )
                )
        elif source in {"fed_fomc", "bls_cpi", "bls_jobs"}:
            events = _calendar(source, raw)
        elif source in EXCHANGE_SOURCES:
            events = parse_calendar(source, raw)
        else:
            fail("event_source_invalid", 422)
    except (ValueError, KeyError, TypeError, UnicodeError, zipfile.BadZipFile, OSError) as exc:
        log.warning("event_source_parse_failed", source=source, error_type=type(exc).__name__)
        raise StoreError("来源结构不符合已审核解析合同", "event_source_parse_failed", 502) from exc
    if not events:
        fail("event_source_no_verified_events", 502)
    return {
        "events": events[:MAX_EVENTS],
        "bounded": len(events) >= MAX_EVENTS,
        "coverage": "partial_page",
        "historical_pit": False,
        "source": source,
        "next_offset": next_offset,
        "next_page": next_page,
    }
