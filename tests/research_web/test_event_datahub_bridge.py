"""Real snapshot/archive boundaries; fixtures are synthetic, not vendor acceptance."""

import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.providers import Result
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.event_datahub_bridge import (
    CalendarReference,
    ImportReference,
    available_sources,
    import_calendar,
    import_reference,
    normalize_rows,
)
from app.research_web.event_diagnostics import event_diagnostic
from app.research_web.event_preservation import snapshot_events
from app.research_web.event_studies.contracts import StudyError
from app.research_web.event_studies.service import StudyService
from app.research_web.event_timeline import TimelineService
from app.research_web.store import Store, StoreError


def host(root):
    research = SimpleNamespace(store=Store(root))
    research.event_timeline = TimelineService(research)
    return research


def publish(research, *, asset_type="index", calendar=False):
    sid = research.store.create("claw", "合成指数日线")["id"]
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(14)]
    params = (
        {"market": "CN", "start_date": "2026-01-01", "end_date": "2026-01-14"}
        if calendar
        else {
            "asset": "000001.SH",
            "asset_type": asset_type,
            "frequency": "day",
            "start_date": "2026-01-01",
            "end_date": "2026-01-14",
        }
    )
    query = BusinessQuery(
        capability="trading_calendar" if calendar else "market_bars",
        source="akshare",
        parameters=params,
    )
    rows = (
        [{"date": str(day), "market": "CN", "is_trading_day": day.weekday() < 5} for day in days]
        if calendar
        else [
            {"date": str(day), "open": str(100 + i), "close": str(101 + i)}
            for i, day in enumerate(days)
            if day.weekday() < 5
        ]
    )
    result = Result(
        rows=rows,
        raw=[json.dumps(rows).encode()],
        status="complete",
        pagination_complete=True,
        provider_id="akshare",
        source_url="https://example.test/synthetic-index",
    )
    manifest = Snapshots(research.store).publish(sid, query, result)
    return sid, manifest["dataset_id"]


def test_real_snapshot_registration_is_idempotent_and_never_grants_pit(tmp_path):
    research = host(tmp_path / "owner")
    sid, did = publish(research)
    reference = ImportReference(session_id=sid, dataset_id=did, index_id="SSE")
    record = import_reference(research, reference, "bridge-register-01")
    assert import_reference(research, reference, "bridge-register-01") == record
    assert record["payload"]["historical_eligible"] is False
    raw = research.event_timeline.read_evidence(record["payload"]["evidence_ref"])["bytes"]
    assert json.loads(raw)["rows"][0]["close"] == "101"
    assert available_sources(research)["items"][0]["index_id"] == "SSE"
    assert snapshot_events(research.store.root)["files"]


def test_stock_code_collision_other_owner_and_tampered_rows_are_rejected(tmp_path):
    research = host(tmp_path / "one")
    sid, did = publish(research, asset_type="stock")
    with pytest.raises(StoreError, match="资料无法登记"):
        import_reference(
            research,
            ImportReference(session_id=sid, dataset_id=did, index_id="SSE"),
            "bridge-reject-01",
        )
    other = host(tmp_path / "two")
    with pytest.raises(StoreError):
        import_reference(
            other,
            ImportReference(session_id=sid, dataset_id=did, index_id="SSE"),
            "bridge-reject-02",
        )
    sid, did = publish(research)
    path = research.store.directory(sid) / "inputs" / "datasets" / did / "rows.json"
    path.write_bytes(b"[]")
    with pytest.raises(StoreError):
        import_reference(
            research,
            ImportReference(session_id=sid, dataset_id=did, index_id="SSE"),
            "bridge-reject-03",
        )


def test_duplicate_dates_boolean_prices_and_conflicting_native_aliases_rejected():
    for rows in [
        [{"date": "2026-01-01", "close": True}, {"date": "2026-01-02", "close": 2}],
        [{"date": "2026-01-01", "close": 1}, {"date": "2026-01-01", "close": 2}],
        [{"date": "2026-01-01", "close": 1, "Close": 2}, {"date": "2026-01-02", "close": 2}],
    ]:
        with pytest.raises(StoreError):
            normalize_rows(json.dumps(rows).encode())


def test_calendar_attachment_preserves_assumptions_and_original_evidence(tmp_path):
    research = host(tmp_path / "one")
    sid, did = publish(research)
    prices = import_reference(
        research,
        ImportReference(session_id=sid, dataset_id=did, index_id="SSE"),
        "prices-import-01",
    )
    sid, did = publish(research, calendar=True)
    request = CalendarReference(
        session_id=sid,
        dataset_id=did,
        bundle_ref={"id": prices["id"], "revision": prices["revision"]},
    )
    attached = import_calendar(research, request, "calendar-import-01")
    assert attached["revision"] == 2
    assert attached["payload"]["calendar_verified"] is False
    assert import_calendar(research, request, "calendar-import-01") == attached
    calendar = research.event_timeline.records.get(
        "calendar", attached["payload"]["calendar_ref"]["id"]
    )
    evidence = research.event_timeline.read_evidence(calendar["payload"]["evidence_ref"])
    assert evidence["manifest"]["metadata"]["session_times"].startswith("standard_hours_assumption")
    assert research.event_timeline.read_evidence(evidence["manifest"]["metadata"]["original"])[
        "bytes"
    ]


def test_doctor_is_read_only_and_corrupt_metadata_fails_closed(tmp_path):
    research = host(tmp_path / "one")
    before = sorted(
        str(path.relative_to(research.store.root)) for path in research.store.root.rglob("*")
    )
    assert event_diagnostic(research.store.root)["state"] == "not_initialized"
    assert before == sorted(
        str(path.relative_to(research.store.root)) for path in research.store.root.rglob("*")
    )
    research.event_timeline.records.create("study", {"title": "synthetic"}, "doctor-write-01")
    research.event_timeline.records.path.write_bytes(b"corrupt")
    assert event_diagnostic(research.store.root)["metadata_integrity"] == "unverified"


def test_reopening_gap_cannot_claim_return_already_realized_before_next_open(tmp_path):
    research = host(tmp_path / "one")
    record = research.event_timeline.records.create(
        "study",
        {
            "spec": {
                "title": "复市跳空描述统计",
                "role": "calendar_overlay",
                "index_id": "SSE",
                "profile_version": "market-six-axis-v1",
                "family": "holiday",
                "direction": 1,
                "rule": "reopening_gap",
                "bundle_ref": {"id": "a" * 32, "revision": 1},
                "hypothesis": "fixed-reopening-gap",
            }
        },
        "reopening-study-01",
    )
    with pytest.raises(StudyError, match="reopening_gap_requires_pre_closure_execution"):
        StudyService(research).seal([record["id"]], "reopening-seal-01")
    assert research.event_timeline.records.list("validation_batch")["items"] == []
