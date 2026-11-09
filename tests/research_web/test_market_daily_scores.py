"""Deterministic raw-measurement and explicit-operation contracts, not live-source proof."""

import asyncio
import json
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from starlette.requests import Request

from app.research_web.event_timeline import TimelineService
from app.research_web.market_scoring import initial_evidence as daily
from app.research_web.market_scoring.profiles import profile_for
from app.research_web.market_scoring.routes import (
    InitialEvidencePreview,
    preview_initial_evidence,
)
from app.research_web.store import Store, StoreError


def closes(index_id, count=350):
    profile = profile_for(index_id)
    zone = ZoneInfo(profile["timezone"])
    days = [
        (datetime.now(zone).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i))
        for i in range(count, 0, -1)
    ]
    prices = [float(i + 100) for i in range(count)]
    if index_id == "SSE":
        result = {
            "rc": 0,
            "data": {
                "code": "000001",
                "market": 1,
                "name": "上证指数",
                "klines": [
                    f"{day.date()},{p},{p},{p + 1},{p - 1},100" for day, p in zip(days, prices)
                ],
            },
        }
    else:
        result = {
            "chart": {
                "error": None,
                "result": [
                    {
                        "meta": {
                            "symbol": daily.GLOBAL_INDEXES[index_id][1],
                            "instrumentType": "INDEX",
                            "currency": profile["currency"],
                            "exchangeTimezoneName": profile["timezone"],
                            "regularMarketTime": days[-1].timestamp(),
                            "regularMarketPrice": prices[-1],
                        },
                        "timestamp": [day.timestamp() for day in days],
                        "indicators": {
                            "quote": [
                                {
                                    "open": prices,
                                    "close": prices,
                                    "high": [p + 1 for p in prices],
                                    "low": [p - 1 for p in prices],
                                    "volume": [100] * count,
                                }
                            ]
                        },
                    }
                ],
            }
        }
    return json.dumps(result).encode(), prices


def make_research(root):
    research = SimpleNamespace(
        store=Store(root), event_inputs=SimpleNamespace(activity=nullcontext)
    )
    research.event_timeline = TimelineService(research)
    return research


@pytest.mark.parametrize("index_id", daily.INDICES)
def test_long_raw_history_projects_values_without_scores(index_id):
    raw, prices = closes(index_id)
    item = daily._observation(index_id, daily.LONG_SOURCES[index_id], raw, datetime.now(UTC))
    trend, risk = item["axes"]["trend"], item["axes"]["risk"]
    assert item["normalization_observation_count"] == 329
    assert trend["value"] == pytest.approx(100 * (prices[-1] / prices[-21] - 1))
    assert risk["value"] > 0
    assert trend["status"] == risk["status"] == "NOT_ADMITTED"
    assert "host_factor_evidence_not_admitted" in trend["reasons"]
    assert all("score" not in axis for axis in item["axes"].values())


def test_short_history_raw_and_missing_sample_are_not_scored():
    now = datetime.now(UTC)
    raw, _ = closes("SP500", 100)
    trend = daily._observation("SP500", "yahoo", raw, now)["axes"]["trend"]
    assert trend["value"] is not None
    assert trend["status"] == "INSUFFICIENT_SAMPLE"
    assert "normalization_history_insufficient" in trend["reasons"]
    raw, _ = closes("SP500", 20)
    assert daily._observation("SP500", "yahoo", raw, now)["axes"]["trend"]["value"] is None


def test_mismatched_vendor_identity_and_incomplete_close_fail_closed():
    raw, _ = closes("HSI", 100)
    doc = json.loads(raw)
    series = doc["chart"]["result"][0]
    series["meta"]["currency"] = "USD"
    with pytest.raises(ValueError, match="index_identity_mismatch"):
        daily._observation("HSI", "yahoo", json.dumps(doc).encode(), datetime.now(UTC))
    series["meta"]["currency"] = "HKD"
    series["indicators"]["quote"][0]["close"][-5] = None
    assert (
        daily._observation("HSI", "yahoo", json.dumps(doc).encode(), datetime.now(UTC))["axes"][
            "trend"
        ]["value"]
        is None
    )


def test_preview_no_write_explicit_save_idempotent_and_account_bound(tmp_path, monkeypatch):
    research = make_research(tmp_path / "personal")
    other = make_research(tmp_path / "other")
    calls = []

    async def fake_collect():
        calls.append(True)
        result = []
        for index_id in daily.INDICES:
            provider = daily.LONG_SOURCES[index_id]
            raw, _ = closes(index_id)
            row = daily._observation(index_id, provider, raw, datetime.now(UTC))
            result.append((index_id, provider, raw, row, []))
        return result

    monkeypatch.setattr(daily, "collect", fake_collect)
    assert daily.read_initial(research)["items"][0]["axes"]["trend"]["status"] == "NOT_IMPORTED"
    preview = asyncio.run(daily.collect_initial(research, None, preview=True))
    assert preview["preview"] is True
    assert not research.event_timeline.records.path.exists()
    saved = asyncio.run(daily.collect_initial(research, "test-initial-0001"))
    assert asyncio.run(daily.collect_initial(research, "test-initial-0001")) == saved
    assert len(calls) == 2
    assert saved == daily.read_initial(research)
    assert saved["research_attempts"][0]["status"] == "NOT_IMPORTED"
    reference = saved["items"][0]["axes"]["trend"]["source_ref"]
    with pytest.raises(StoreError):
        other.event_timeline.read_evidence(reference)
    raw_path = research.event_timeline.records.folder / "evidence" / reference["id"] / "raw.bin"
    raw_path.write_bytes(b"corrupt")
    axis = daily.read_initial(research)["items"][0]["axes"]["trend"]
    assert axis["value"] is None and axis["reasons"] == ["original_missing_or_changed"]


def test_preview_requires_explicit_action_before_any_work():
    request = Request({"type": "http", "headers": []})
    with pytest.raises(StoreError) as rejected:
        asyncio.run(preview_initial_evidence(InitialEvidencePreview(), request))
    assert rejected.value.code == "market_score_user_action_required"


def test_existing_current_inputs_use_original_score_gate(tmp_path):
    research = make_research(tmp_path / "personal")
    store = research.event_timeline.records
    now = datetime.now(UTC)
    old = now - timedelta(days=3)
    store.create(
        "factor_inputs",
        {
            "index_id": "SSE",
            "profile_version": daily.PROFILE_VERSION,
            "bundle": {"as_of": now.isoformat()},
        },
        "current-fixture-0001",
    )
    store.create(
        "factor_inputs",
        {
            "index_id": "SP500",
            "profile_version": daily.PROFILE_VERSION,
            "bundle": {"as_of": old.isoformat()},
        },
        "old-fixture-0001",
    )
    requests = []

    def run_initial_if_qualified(body):
        requests.append(body)

    research.market_scores = SimpleNamespace(run_initial_if_qualified=run_initial_if_qualified)
    attempts = daily._attempt_current_runs(research)
    assert [item["status"] for item in attempts] == ["NOT_ADMITTED", "NOT_IMPORTED", "NOT_IMPORTED"]
    assert len(requests) == 1 and requests[0]["index_id"] == "SSE"
    assert requests[0]["as_of"] == now.isoformat()
    assert requests[0]["validation_id"] is None and requests[0]["overlay_ids"] == []


def test_archive_midnight_does_not_promote_previously_partial_bar():
    raw, _ = closes("HSI", 25)
    payload = json.loads(raw)
    zone = ZoneInfo("Asia/Hong_Kong")
    observed = datetime.now(zone).replace(hour=12, minute=0, second=0, microsecond=0)
    series = payload["chart"]["result"][0]
    series["timestamp"][-1] = observed.timestamp()
    known = observed + timedelta(days=1)
    projected = daily._observation(
        "HSI",
        "yahoo",
        json.dumps(payload).encode(),
        known,
        observed_market_date=observed.date().isoformat(),
    )
    assert projected["closed_bar_count"] == 24
    assert projected["as_of"] < observed.date().isoformat()
    assert projected["known_at"] == known.isoformat()
