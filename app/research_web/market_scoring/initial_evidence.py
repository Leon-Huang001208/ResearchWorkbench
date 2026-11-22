"""Explicit, account-owned observations for the three default dashboard indices.

A verified price history can provide transparent raw measurements. It does not
grant that provider a DataHub factor binding or a historical availability receipt.
"""

from __future__ import annotations

import asyncio
import json
import math
from datetime import UTC, date, datetime, time
from itertools import pairwise
from statistics import pstdev
from threading import BoundedSemaphore
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import httpx

from core.observability import get_logger

from ..datahub.providers_global_indices import (
    CHART_BASE,
    MAX_BYTES,
    TENCENT_BASE,
    TENCENT_SYMBOLS,
    parse_chart,
    parse_tencent_chart,
)
from ..market_indices import GLOBAL_INDEXES
from ..store import StoreError
from .engine import digest, stamp
from .profiles import AXES, PROFILE_VERSION, profile_for

log = get_logger(__name__)
INDICES = ("SSE", "SP500", "HSI")
LONG_SOURCES = {"SSE": "eastmoney", "SP500": "yahoo", "HSI": "yahoo"}
EASTMONEY_HISTORY = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
VERSION = "market-daily-evidence-v1"
KIND = "market_daily_evidence"
INTENT = {"version": VERSION, "indices": list(INDICES)}
LONG_MAX_BARS = 600
WINDOW = 20
_IMPORT_SLOT = BoundedSemaphore(1)


def source_url(index_id, provider):
    if provider == "eastmoney" and index_id == "SSE":
        return (
            EASTMONEY_HISTORY
            + "?"
            + urlencode(
                {
                    "secid": "1.000001",
                    "klt": "101",
                    "fqt": "0",
                    "lmt": "350",
                    "end": "20500101",
                    "fields1": "f1,f2,f3,f4,f5,f6",
                    "fields2": "f51,f52,f53,f54,f55,f56",
                }
            )
        )
    if provider == "yahoo" and index_id in {"SP500", "HSI"}:
        return CHART_BASE + quote(GLOBAL_INDEXES[index_id][1], safe="") + "?range=2y&interval=1d"
    if provider == "tencent" and index_id in INDICES:
        return (
            TENCENT_BASE + "?param=" + quote(TENCENT_SYMBOLS[index_id] + ",day,,,100,qfq", safe=",")
        )
    raise ValueError("source_identity_unknown")


def _parse_eastmoney(payload, now):
    if not isinstance(payload, dict) or payload.get("rc") != 0:
        raise ValueError("source_error")
    item = payload["data"]
    if item["code"] != "000001" or type(item["market"]) is not int or item["market"] != 1:
        raise ValueError("source_identity_mismatch")
    if item.get("name") not in {"上证指数", "上证综指"}:
        raise ValueError("source_identity_mismatch")
    lines = item["klines"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 350:
        raise ValueError("source_history_shape")
    bars, previous = [], None
    today = now.astimezone(ZoneInfo("Asia/Shanghai")).date()
    for line in lines:
        if not isinstance(line, str):
            raise TypeError("source_history_shape")
        day, opening, close, high, low, volume = line.split(",")
        parsed = date.fromisoformat(day)
        if parsed.isoformat() != day or (previous and parsed <= previous) or parsed > today:
            raise ValueError("source_date_invalid")
        previous = parsed
        opening, close, high, low, volume = map(float, (opening, close, high, low, volume))
        if not all(map(math.isfinite, (opening, close, high, low, volume))) or not (
            0 < low <= min(opening, close) <= max(opening, close) <= high and volume >= 0
        ):
            raise ValueError("source_ohlc_invalid")
        if parsed < today:
            bars.append({"date": day, "close": close})
    return bars


def _closed_bars(index_id, provider, raw, known_at):
    source_url(index_id, provider)
    data = json.loads(raw)
    if provider == "eastmoney":
        return _parse_eastmoney(data, known_at)
    if provider == "yahoo":
        return parse_chart(data, index_id, now=known_at, max_bars=LONG_MAX_BARS)["daily_bars"]
    return parse_tencent_chart(data, index_id, now=known_at)["daily_bars"]


def _axis(value=None, status="NOT_IMPORTED", *reasons, unit=None, source=None, source_ref=None):
    return {
        "value": value,
        "unit": unit,
        "status": status,
        "reasons": list(reasons),
        "source": source,
        "source_ref": source_ref,
    }


def _empty(index_id, status="NOT_IMPORTED", reason="initial_evidence_not_imported"):
    profile = profile_for(index_id)
    return {
        "index_id": index_id,
        "as_of": None,
        "known_at": None,
        "axes": {
            axis: _axis(None, status, reason, unit=profile["axes"][axis]["unit"]) for axis in AXES
        },
        "attempts": [],
    }


def _observation(index_id, provider, raw, known_at, reference=None, observed_market_date=None):
    zone = ZoneInfo(profile_for(index_id)["timezone"])
    if observed_market_date is None:
        observed_market_date = known_at.astimezone(zone).date().isoformat()
    day = date.fromisoformat(observed_market_date)
    if day.isoformat() != observed_market_date or day > known_at.astimezone(zone).date():
        raise ValueError("source_observation_date_invalid")
    # A response collected before local midnight cannot gain a completed bar
    # merely because its archive write completed on the next market date.
    parse_at = min(known_at, datetime.combine(day, time.max, tzinfo=zone))
    bars = _closed_bars(index_id, provider, raw, parse_at)
    # Never skip an incomplete interior close and calculate a multi-session
    # return as though it were a single day's return.
    usable = []
    for bar in bars:
        if bar["close"] is None:
            usable.clear()
        else:
            usable.append(bar)
    row = _empty(index_id, "NOT_IMPORTED", "qualified_factor_input_not_imported")
    row["as_of"] = bars[-1]["date"] if bars else None
    row["known_at"] = known_at.isoformat()
    row["observed_market_date"] = observed_market_date
    row["closed_bar_count"] = len(bars)
    row["observed_close_sample_count"] = len(usable)
    row["normalization_observation_count"] = max(0, len(usable) - WINDOW - 1)
    source = {
        "provider": provider,
        "url": source_url(index_id, provider),
        "symbol": (
            TENCENT_SYMBOLS[index_id]
            if provider == "tencent"
            else "1.000001" if provider == "eastmoney" else GLOBAL_INDEXES[index_id][1]
        ),
    }
    for axis in ("trend", "risk"):
        definition = profile_for(index_id)["axes"][axis]
        reasons = ["host_factor_evidence_not_admitted"]
        if provider not in definition["providers"]:
            reasons.insert(0, "provider_not_in_frozen_profile")
        if row["normalization_observation_count"] < definition["minimum_observations"]:
            reasons.append("normalization_history_insufficient")
        value = None
        if len(usable) >= WINDOW + 1:
            closes = [bar["close"] for bar in usable[-WINDOW - 1 :]]
            returns = [100 * (right / left - 1) for left, right in pairwise(closes)]
            value = 100 * (closes[-1] / closes[0] - 1) if axis == "trend" else pstdev(returns)
            if not math.isfinite(value):
                raise ValueError("source_metric_non_finite")
        else:
            reasons.append("closed_price_history_insufficient")
        status = (
            "INSUFFICIENT_SAMPLE"
            if value is None or "normalization_history_insufficient" in reasons
            else "NOT_ADMITTED"
        )
        row["axes"][axis] = {
            **_axis(
                value,
                status,
                *reasons,
                unit=definition["unit"],
                source=source,
                source_ref=reference,
            ),
            "metric": definition["metric"],
            "window_start": usable[-WINDOW - 1]["date"] if value is not None else None,
            "window_end": usable[-1]["date"] if value is not None else None,
            "sample_count": row["normalization_observation_count"],
            "minimum_samples": definition["minimum_observations"],
            "calculation": (
                "最近20段相邻已取得收盘价：末价／首价 − 1；交易日连续性未核实"
                if axis == "trend"
                else "最近20段相邻已取得收盘价收益的总体标准差，不年化；交易日连续性未核实"
            ),
        }
    return row


async def _fetch(client, url):
    async with asyncio.timeout(10):
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            raw = bytearray()
            async for chunk in response.aiter_bytes():
                raw.extend(chunk)
                if len(raw) > MAX_BYTES:
                    raise ValueError("response_limit")
    return bytes(raw)


async def _collect_one(client, index_id):
    attempts = []
    for provider in (LONG_SOURCES[index_id], "tencent"):
        url = source_url(index_id, provider)
        try:
            raw = await _fetch(client, url)
            observed = datetime.now(UTC)
            row = _observation(index_id, provider, raw, observed)
            if row["axes"]["trend"]["value"] is None and provider != "tencent":
                attempts.append({"provider": provider, "url": url, "status": "INSUFFICIENT_SAMPLE"})
                continue
        except (
            httpx.HTTPError,
            TimeoutError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
        ) as exc:
            code = (
                "source_http_unavailable"
                if isinstance(exc, httpx.HTTPStatusError)
                else "source_unavailable_or_invalid"
            )
            attempts.append(
                {"provider": provider, "url": url, "status": "SOURCE_UNAVAILABLE", "reason": code}
            )
            log.warning(
                "market_daily_source_failed", index_id=index_id, provider=provider, code=code
            )
            continue
        attempts.append({"provider": provider, "url": url, "status": "OBSERVED"})
        return index_id, provider, raw, row, attempts
    row = _empty(index_id, "SOURCE_UNAVAILABLE", "price_sources_unavailable")
    return index_id, None, None, row, attempts


async def collect():
    async with httpx.AsyncClient(
        timeout=8,
        follow_redirects=False,
        headers={
            "User-Agent": "Mozilla/5.0 ResearchWorkbench personal reference",
            "Referer": "https://quote.eastmoney.com/",
        },
    ) as client:
        return await asyncio.gather(*(_collect_one(client, index_id) for index_id in INDICES))


def _metadata(index_id, observed_market_date):
    return {
        "kind": VERSION,
        "index_id": index_id,
        "observed_market_date": observed_market_date,
    }


def _project(events, payload):
    rows = {}
    for item in payload["records"]:
        index_id = item["index_id"]
        ref = item["source_ref"]
        if ref is None:
            row = _empty(index_id, "SOURCE_UNAVAILABLE", "price_sources_unavailable")
        else:
            try:
                original = events.read_evidence(ref)
                manifest = original["manifest"]
                provider = manifest["source"]
                known_at = datetime.fromisoformat(manifest["first_observed"])
                metadata = manifest["metadata"]
                observed_market_date = metadata["observed_market_date"]
                if (
                    metadata != _metadata(index_id, observed_market_date)
                    or manifest.get("url") != source_url(index_id, provider)
                    or known_at.tzinfo is None
                    or known_at > datetime.now(UTC)
                ):
                    raise ValueError("source_manifest_binding_invalid")
                row = _observation(
                    index_id, provider, original["bytes"], known_at, ref, observed_market_date
                )
            except (StoreError, ValueError, KeyError, TypeError, AttributeError) as exc:
                log.warning(
                    "market_daily_evidence_unavailable",
                    index_id=index_id,
                    error_type=type(exc).__name__,
                )
                row = _empty(index_id, "NOT_ADMITTED", "original_missing_or_changed")
        row["attempts"] = item["attempts"]
        rows[index_id] = row
    return {
        "items": [rows.get(index_id) or _empty(index_id) for index_id in INDICES],
        "research_attempts": payload.get("research_attempts", []),
        "production_enabled": False,
    }


def read_initial(research):
    events = research.event_timeline
    cursor, latest = None, None
    for _ in range(20):
        page = events.records.list(KIND, 200, cursor)
        if page["items"]:
            latest = page["items"][-1]
        cursor = page.get("next_cursor")
        if cursor is None:
            break
    else:
        log.warning("market_daily_evidence_scan_limit")
        return {
            "items": [_empty(i, "NOT_ADMITTED", "evidence_scan_incomplete") for i in INDICES],
            "production_enabled": False,
        }
    if latest is None:
        return {"items": [_empty(i) for i in INDICES], "production_enabled": False}
    return _project(events, latest["payload"])


def _cached(events, key):
    return events.records.cached(KIND, key, INTENT)


def _attempt_current_runs(research):
    """Only existing, current-day registered inputs may reach the v1 engine."""
    store = research.event_timeline.records
    choices = {}
    cutoff, cursor = datetime.now(UTC), None
    zones = {index_id: ZoneInfo(profile_for(index_id)["timezone"]) for index_id in INDICES}
    for _ in range(8):
        # Factor bundles can contain a sizable native matrix. Bound the
        # per-page footprint as well as the history scan.
        page = store.list("factor_inputs", 8, cursor)
        for record in page["items"]:
            payload = record["payload"]
            index_id = payload.get("index_id")
            if index_id not in zones or payload.get("profile_version") != PROFILE_VERSION:
                continue
            bundle = payload.get("bundle")
            if not isinstance(bundle, dict):
                continue
            series = bundle.get("series", [bundle])
            if not isinstance(series, list) or len(series) > 20000:
                continue
            zone = zones[index_id]
            for item in series:
                try:
                    at = stamp(item.get("as_of"))
                except (AttributeError, TypeError, ValueError):
                    continue
                if at > cutoff or at.astimezone(zone).date() != cutoff.astimezone(zone).date():
                    continue
                candidate = (at, record["id"], item["as_of"])
                if index_id not in choices or candidate > choices[index_id]:
                    choices[index_id] = candidate
        cursor = page.get("next_cursor")
        if cursor is None:
            break
    else:
        log.warning("market_daily_factor_scan_limit")
        return [
            {"index_id": i, "status": "NOT_ADMITTED", "reason": "input_scan_incomplete"}
            for i in INDICES
        ]
    attempts = []
    for index_id in INDICES:
        if index_id not in choices:
            attempts.append(
                {
                    "index_id": index_id,
                    "status": "NOT_IMPORTED",
                    "reason": "current_factor_inputs_not_imported",
                }
            )
            continue
        _, inputs_id, as_of = choices[index_id]
        body = {
            "index_id": index_id,
            "as_of": as_of,
            "inputs_id": inputs_id,
            "validation_id": None,
            "overlay_ids": [],
        }
        body["idempotency_key"] = "daily-initial:" + digest(body)
        try:
            current = research.market_scores.run_initial_if_qualified(body)
        except StoreError as exc:
            log.warning("market_daily_research_run_rejected", index_id=index_id, code=exc.code)
            attempts.append({"index_id": index_id, "status": "NOT_ADMITTED", "reason": exc.code})
            continue
        if current is None:
            attempts.append(
                {
                    "index_id": index_id,
                    "status": "NOT_ADMITTED",
                    "reason": "no_qualified_current_axis",
                }
            )
        else:
            attempts.append(
                {
                    "index_id": index_id,
                    "status": "RUN_SAVED",
                    "run_id": current["id"],
                    "as_of": as_of,
                }
            )
    return attempts


def _persist(research, key, captures):
    events = research.event_timeline
    cached = _cached(events, key)
    if cached:
        return _project(events, cached[0]["payload"])
    records = []
    for index_id, provider, raw, observed, attempts in captures:
        ref = (
            events.archive_evidence(
                raw,
                source=provider,
                url=source_url(index_id, provider),
                metadata=_metadata(index_id, observed["observed_market_date"]),
            )
            if raw is not None
            else None
        )
        records.append({"index_id": index_id, "source_ref": ref, "attempts": attempts})
    research_attempts = _attempt_current_runs(research)
    saved = events.records.batch(
        [
            {
                "kind": KIND,
                "payload": {
                    "version": VERSION,
                    "records": records,
                    "research_attempts": research_attempts,
                },
            }
        ],
        key,
        intent=INTENT,
        scope=KIND,
    )[0]
    log.info("market_daily_evidence_saved", id=saved["id"])
    return _project(events, saved["payload"])


async def collect_initial(research, key, *, preview=False):
    from starlette.concurrency import run_in_threadpool

    if not _IMPORT_SLOT.acquire(blocking=False):
        raise StoreError("已有首批评分资料操作在进行", "market_daily_evidence_busy", 429)
    try:
        with research.event_inputs.activity():
            if not preview:
                cached = await run_in_threadpool(_cached, research.event_timeline, key)
                if cached:
                    return await run_in_threadpool(
                        _project, research.event_timeline, cached[0]["payload"]
                    )
            captures = await collect()
            if preview:
                return {
                    "items": [{**row, "attempts": attempts} for _, _, _, row, attempts in captures],
                    "preview": True,
                    "production_enabled": False,
                }
            return await run_in_threadpool(_persist, research, key, captures)
    finally:
        _IMPORT_SLOT.release()
