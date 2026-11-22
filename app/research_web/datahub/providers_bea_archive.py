"""Closed official GDP release catalogue, distinct from current BEA estimates."""

from __future__ import annotations

import asyncio
import hashlib
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

from .contracts import BusinessQuery
from .providers import MAX_RESPONSE_BYTES, ProviderError, Result

log = get_logger(__name__)
SCHEMA = "bea-gdp-archived-release-v1"
SERIES = "us_real_gdp_qoq_saar"
PERIOD = "2024-06-30"
# A scheduled release is not evidence of its actual publication time. Stop at
# local midnight on its announced date, before the unverified third vintage.
SUPPORTED_UNTIL = datetime(2024, 9, 26, tzinfo=ZoneInfo("America/New_York")).astimezone(UTC)


@dataclass(frozen=True)
class Release:
    identifier: str
    stage: str
    published_at: datetime
    url: str


CATALOG = (
    Release(
        "BEA24-33",
        "advance",
        datetime(2024, 7, 25, 12, 30, tzinfo=UTC),
        "https://www.bea.gov/news/2024/gross-domestic-product-second-quarter-2024-advance-estimate",
    ),
    Release(
        "BEA24-38",
        "second",
        datetime(2024, 8, 29, 12, 30, tzinfo=UTC),
        "https://www.bea.gov/news/2024/gross-domestic-product-second-estimate-corporate-profits-preliminary-estimate-second",
    ),
)
FIELDS = {
    "value": {"unit": "percent_qoq_saar", "currency": None},
    "report_period": {"unit": "quarter_end_date", "currency": None},
    "published_at": {"unit": "UTC_instant", "currency": None},
}


def validate_supported_query(query: BusinessQuery, *, storage_read=False):
    if query.capability != "factor_macro" or query.parameters != {
        "series": SERIES,
        "start_date": PERIOD,
        "end_date": PERIOD,
    }:
        raise ProviderError("bea_archive_scope_unsupported")
    if query.as_of is not None:
        if (
            not storage_read
            or query.refresh
            or not CATALOG[0].published_at <= query.as_of < SUPPORTED_UNTIL
        ):
            raise ProviderError("bea_archive_cutoff_unverified")
    elif query.purpose == "backtest":
        raise ProviderError("bea_archive_cutoff_required")


class _VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def parse_release(raw: bytes, release: Release) -> dict:
    """Bind a number to its real-GDP paragraph, stage, release ID and embargo."""
    if release not in CATALOG or not isinstance(raw, bytes) or len(raw) > MAX_RESPONSE_BYTES:
        raise ProviderError("bea_archive_schema_invalid")
    try:
        parser = _VisibleText()
        parser.feed(raw.decode("utf-8"))
        text = " ".join(" ".join(parser.parts).split())
        stamps = re.findall(
            r"EMBARGOED UNTIL RELEASE AT (\d{1,2}:\d{2}) a\.m\. (EDT|EST), "
            r"([A-Za-z]+, [A-Za-z]+ \d{1,2}, \d{4})",
            text,
        )
        if len(stamps) != 1:
            raise ValueError("release_stamp")
        clock, abbreviation, day = stamps[0]
        local = datetime.strptime(day + " " + clock, "%A, %B %d, %Y %H:%M").replace(
            tzinfo=ZoneInfo("America/New_York")
        )
        if local.tzname() != abbreviation or local.astimezone(UTC) != release.published_at:
            raise ValueError("release_stamp_identity")
        ids = re.findall(r"BEA\s+24[–—-](\d{2})\b", text)
        if ids != [release.identifier[-2:]]:
            raise ValueError("release_id")
        matches = re.findall(
            r"Real gross domestic product \(GDP\) (increased|decreased) at an annual rate of "
            r"([0-9]+(?:\.[0-9]+)?) percent in the second quarter of 2024 \(table 1\), "
            r'according to the ["“](advance|second)["”] estimate released by the U\.S\. '
            r"Bureau of Economic Analysis\.",
            text,
        )
        if len(matches) != 1 or matches[0][2] != release.stage:
            raise ValueError("gdp_identity")
        if (
            "Quarterly seasonally adjusted values are expressed at annual rates" not in text
            or "Percent changes in quarterly seasonally adjusted series are displayed at annual rates"
            not in text
        ):
            raise ValueError("saar_identity")
        direction, number, _stage = matches[0]
        value = float(number) * (-1 if direction == "decreased" else 1)
        if not math.isfinite(value):
            raise ValueError("gdp_value")
    except (ValueError, UnicodeError, OverflowError):
        log.warning("datahub_bea_release_rejected", release=release.identifier)
        raise ProviderError("bea_archive_schema_invalid") from None
    return {
        "series": SERIES,
        "report_period": PERIOD,
        "value": value,
        "unit": "percent_qoq_saar",
        "seasonal_adjustment": "seasonally_adjusted",
        "release_id": release.identifier,
        "release_stage": release.stage,
        "published_at": release.published_at.isoformat(),
        "source_url": release.url,
        "latest_scope": "reviewed_archive_catalog",
        "current_latest_verified": False,
    }


def metadata():
    return {
        "schema_version": SCHEMA,
        "provider_semantics_revision": SCHEMA,
        "upstream_id": "bea_official_release_archive",
        "availability_basis": "official_archived_release",
        "latest_scope": "reviewed_archive_catalog",
        "current_latest_verified": False,
        "catalog_complete_from": CATALOG[0].published_at.isoformat(),
        "catalog_complete_until_exclusive": SUPPORTED_UNTIL.isoformat(),
        "historical_point_in_time": False,
        "formal_backtest_eligible": False,
    }


async def fetch(query: BusinessQuery, *, transport=None):
    validate_supported_query(query)
    originals = []
    rows = []
    try:
        async with asyncio.timeout(15):
            async with httpx.AsyncClient(
                transport=transport,
                trust_env=False,
                follow_redirects=False,
                timeout=6,
            ) as client:
                for release in CATALOG:
                    async with client.stream("GET", release.url) as response:
                        if response.status_code != 200:
                            raise ProviderError("vendor_unreachable")
                        raw = bytearray()
                        async for chunk in response.aiter_bytes():
                            raw.extend(chunk)
                            if len(raw) > MAX_RESPONSE_BYTES:
                                raise ProviderError("response_limit")
                    original = bytes(raw)
                    rows.append(parse_release(original, release))
                    originals.append(original)
    except (httpx.HTTPError, TimeoutError):
        log.warning("datahub_bea_release_fetch_failed")
        raise ProviderError("vendor_unreachable") from None
    log.info("datahub_bea_release_fetched", releases=len(rows))
    return Result(
        rows=rows[-1:],
        raw=originals,
        provider_id="bea_archive",
        status="snapshot",
        source_url=CATALOG[-1].url,
        fields=FIELDS,
        pages_fetched=2,
        provider_total=1,
        pagination_complete=True,
        metadata={
            **metadata(),
            "archive_original_sha256": [hashlib.sha256(b).hexdigest() for b in originals],
        },
        limitations=[
            "Only the reviewed 2024-Q2 advance/second release catalogue, not the current revised estimate.",
            "Historical queries require a seeded warehouse and the explicitly verified cutoff interval.",
        ],
    )
