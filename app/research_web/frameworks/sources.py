"""Bounded public-source helpers used by framework-owned collectors."""

from __future__ import annotations

import asyncio
import csv
import io
import math
import zipfile
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

import httpx

MAX_SOURCE_BYTES = 8 * 1024 * 1024
DEFAULT_HEADERS = {
    "Accept": "application/json,text/csv,*/*",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def latest_change(points: list[dict], lookback: int, *, percent: bool = False) -> float:
    if len(points) <= lookback:
        raise ValueError("series history is insufficient")
    current = float(points[-1]["value"])
    previous = float(points[-lookback - 1]["value"])
    if percent:
        if previous == 0:
            raise ValueError("series denominator is zero")
        return (current / previous - 1) * 100
    return current - previous


def zscore(values: Iterable[float]) -> float:
    cleaned = [float(value) for value in values if math.isfinite(float(value))]
    if len(cleaned) < 8:
        raise ValueError("z-score history is insufficient")
    mean = sum(cleaned) / len(cleaned)
    variance = sum((value - mean) ** 2 for value in cleaned) / len(cleaned)
    if variance <= 0:
        return 0.0
    return (cleaned[-1] - mean) / math.sqrt(variance)


async def get_bytes(client: httpx.AsyncClient, url: str) -> bytes:
    for attempt in range(3):
        try:
            response = await client.get(url, headers=DEFAULT_HEADERS)
            response.raise_for_status()
            payload = response.content
            if not payload or len(payload) > MAX_SOURCE_BYTES:
                raise ValueError("source response is empty or exceeds size limit")
            return payload
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            retryable = isinstance(exc, httpx.TransportError) or exc.response.status_code in {
                429,
                500,
                502,
                503,
                504,
            }
            if not retryable or attempt == 2:
                raise
            await asyncio.sleep(0.25 * (attempt + 1))
    raise RuntimeError("unreachable source retry state")


async def get_json(client: httpx.AsyncClient, url: str) -> dict:
    payload = await get_bytes(client, url)
    value = httpx.Response(200, content=payload).json()
    if not isinstance(value, dict):
        raise TypeError("source response is not an object")
    return value


async def get_list(client: httpx.AsyncClient, url: str) -> list[dict]:
    payload = await get_bytes(client, url)
    value = httpx.Response(200, content=payload).json()
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise TypeError("source response is not an object list")
    return value


async def fred_series(
    client: httpx.AsyncClient,
    series_id: str,
    *,
    years: int = 6,
) -> list[dict]:
    start = (datetime.now(UTC).date() - timedelta(days=366 * years)).isoformat()
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start}"
    payload = await get_bytes(client, url)
    files: list[bytes]
    if payload.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            files = [archive.read(name) for name in archive.namelist() if name.endswith(".csv")]
    else:
        files = [payload]
    points: dict[str, float] = {}
    for raw in files:
        rows = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        for row in rows:
            date = row.get("observation_date") or row.get("DATE") or ""
            raw_value = row.get(series_id)
            try:
                value = float(raw_value) if raw_value not in {None, "", "."} else math.nan
            except (TypeError, ValueError):
                continue
            if date and math.isfinite(value):
                points[date] = value
    result = [{"date": date, "value": value} for date, value in sorted(points.items())]
    if len(result) < 8:
        raise ValueError(f"FRED {series_id} history is insufficient")
    return result


async def fred_series_map(
    client: httpx.AsyncClient,
    series_ids: Iterable[str],
    *,
    years: int = 6,
    concurrency: int = 3,
) -> dict[str, list[dict]]:
    """Fetch FRED series with bounded concurrency to avoid remote resets."""

    identifiers = tuple(series_ids)
    limiter = asyncio.Semaphore(concurrency)

    async def fetch(series_id: str) -> tuple[str, list[dict]]:
        async with limiter:
            return series_id, await fred_series(client, series_id, years=years)

    return dict(await asyncio.gather(*(fetch(series_id) for series_id in identifiers)))


def source_record(
    name: str,
    url: str,
    observed_at: str,
    unit: str,
    method: str,
    *,
    proxy: bool = False,
) -> dict:
    return {
        "name": name,
        "url": url,
        "observed_at": observed_at,
        "unit": unit,
        "method": method,
        "proxy": proxy,
    }
