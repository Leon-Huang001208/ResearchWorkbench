"""Canonical per-field knowledge, actual native prices and execution safeguards."""

import json
from copy import deepcopy
from datetime import UTC, date, datetime

import pytest

from app.research_web.datahub.contracts import BusinessQuery
from app.research_web.datahub.snapshots import Snapshots
from app.research_web.datahub.warehouse import WarehouseBinding, WarehouseBridge
from app.research_web.event_studies.backtest import replay
from app.research_web.event_studies.contracts import Calendar
from app.research_web.market_scoring.native_inputs import SCHEMAS
from app.research_web.market_store import (
    Batch,
    DatasetIdentity,
    Fact,
    InMemoryMarketStore,
    MarketStoreService,
    RawOriginal,
    StoreScope,
)
from app.research_web.store import StoreError
from tests.research_web.test_market_scoring import proxy_for
from tests.research_web.test_market_scoring_native_inputs import host


def canonical_source(research, kind, entries, render, *, fields=None, adjustment="none"):
    raw = RawOriginal(json.dumps(entries).encode())
    service = MarketStoreService(InMemoryMarketStore(), lambda *_: research.datahub.allowed)
    scope = StoreScope("native-owner", "private", "wind", research.datahub.configuration)
    metrics = tuple(sorted({entry["metric"] for entry in entries}))
    dataset = DatasetIdentity(
        "fund_data",
        "native-SSE",
        "CN",
        "daily",
        "per-field-native-v1",
        adjustment,
        "reviewed-native-v1",
        "b" * 64,
        metrics,
    )
    facts = tuple(
        Fact(
            entry["metric"],
            date.fromisoformat(entry["day"]),
            "daily",
            json.dumps(entry["value"]),
            datetime.fromisoformat(entry["known"]),
            datetime.now(UTC),
            entry["version"],
            raw.sha256,
        )
        for entry in entries
    )
    service.commit_batch("native-owner", scope, dataset, Batch(facts, (raw,)))
    expected = tuple(sorted({fact.business_date for fact in facts}))
    binding = WarehouseBinding(
        "native-owner",
        scope,
        dataset,
        expected,
        lambda *_: None,
        render=render,
        field_metadata=fields or {metric: {"unit": "native_contract"} for metric in metrics},
        source_metadata=lambda _: {"event_input_schema": SCHEMAS[kind]},
    )
    research.datahub.warehouse = WarehouseBridge(service, lambda *_: binding)
    query = BusinessQuery(
        capability="fund_data",
        source="wind",
        purpose="backtest",
        as_of="2026-10-03T00:00:00+00:00",
        parameters={
            "dataset": kind,
            "code": "SSE",
            "start_date": str(expected[0]),
            "end_date": str(expected[-1]),
        },
    )
    result = research.datahub.warehouse.read(query, "wind", research.datahub.configuration)
    sid = research.store.create("claw", "合成逐字段已知时点")["id"]
    manifest = Snapshots(research.store).publish(
        sid,
        query,
        result,
        request_query=query,
        authorization_fingerprint=research.datahub.configuration,
    )
    return {"session_id": sid, "dataset_id": manifest["dataset_id"]}


def test_multiannual_calendar_uses_each_announced_version_not_final_capture(tmp_path):
    research = host(tmp_path)
    entries = []
    for year, known in ((2020, "2019-12-01T00:00:00+00:00"), (2021, "2020-12-01T00:00:00+00:00")):
        sessions = [
            {
                "day": f"{year}-01-0{day}",
                "opens": f"{year}-01-0{day}T09:30:00+08:00",
                "closes": f"{year}-01-0{day}T15:00:00+08:00",
                "half_day": False,
                "known_at": known,
                "announcement_version_ref": f"calendar-{year}",
            }
            for day in ((2, 3) if year == 2020 else (4, 5))
        ]
        entries.append(
            {
                "metric": "calendar",
                "day": known[:10],
                "known": known,
                "version": f"calendar-{year}",
                "value": sessions,
            }
        )

    def render(batch):
        sessions = [session for fact in batch.facts for session in fact.value]
        return [
            {
                "calendar": {
                    "exchange": "XSHG",
                    "timezone": "Asia/Shanghai",
                    "version": "multiannual",
                    "source_ref": "native",
                    "known_at": "2026-01-01T00:00:00+00:00",
                    "sessions": sessions,
                }
            }
        ]

    source = canonical_source(research, "calendar", entries, render)
    record = research.event_inputs.register_native(
        "calendar", source, "SSE", "multiannual-calendar"
    )
    _, native, _ = research.event_inputs._record("calendar", {"id": record["id"], "revision": 1})
    calendar = research.event_inputs._calendar(record, native)
    assert calendar.known_at.year == datetime.now(UTC).year
    assert calendar.announcement_known_at is None
    assert calendar.sessions[0].known_at.year == 2019
    assert calendar.sessions[-1].known_at.year == 2020
    assert calendar.sessions[0].announcement_version_ref == "calendar-2020"


def test_proxy_identity_and_dated_rules_have_separate_actual_knowledge(tmp_path):
    research = host(tmp_path)
    original = proxy_for().model_dump(mode="json")
    rules = [
        dict(
            original["rules"][0],
            from_date="2000-01-01",
            until_date="2019-12-31",
            known_at="1999-12-01T00:00:00+00:00",
        ),
        dict(
            original["rules"][0],
            from_date="2020-01-01",
            until_date="2099-12-31",
            known_at="2019-12-01T00:00:00+00:00",
        ),
    ]
    entries = [
        {
            "metric": "proxy",
            "day": "1999-01-01",
            "known": "1999-01-01T00:00:00+00:00",
            "version": "identity-v1",
            "value": original,
        },
        {
            "metric": "proxy",
            "day": "2000-01-01",
            "known": "1999-12-01T00:00:00+00:00",
            "version": "rule-2000",
            "value": rules[0],
        },
        {
            "metric": "proxy",
            "day": "2020-01-01",
            "known": "2020-01-05T00:00:00+00:00",
            "version": "rule-2020",
            "value": rules[1],
        },
    ]

    def render(batch):
        identity = next(fact.value for fact in batch.facts if fact.source_version == "identity-v1")
        identity["rules"] = [
            fact.value for fact in batch.facts if fact.source_version != "identity-v1"
        ]
        return [
            {
                "proxy": identity,
                "identity_announcement_version_ref": "identity-v1",
                "rule_announcement_version_refs": {
                    "2000-01-01": "rule-2000",
                    "2020-01-01": "rule-2020",
                },
            }
        ]

    source = canonical_source(research, "proxy", entries, render)
    record = research.event_inputs.register_native("proxy", source, "SSE", "multirule-proxy")
    inputs = {"proxy_ref": {"id": record["id"], "revision": 1}}
    old = research.event_inputs.resolve_market_scoring_context(
        index_id="SSE", as_of="2010-01-04T16:00:00+08:00", inputs=inputs
    )
    assert old.proxy.known_at.year == 1999
    assert old.proxy.rules[0].known_at.year == 1999
    with pytest.raises(StoreError) as error:
        research.event_inputs.resolve_market_scoring_context(
            index_id="SSE", as_of="2020-01-02T16:00:00+08:00", inputs=inputs
        )
    assert error.value.code == "event_native_proxy_rule_not_known_by_cutoff"


def price_source(research, *, adjustment="none", unknown=False):
    days = ("2026-10-01", "2026-10-02")
    base = [
        {
            "day": day,
            "index_id": "SSE",
            "role": "proxy",
            "asset": proxy_for().symbol,
            "unit": "CNY/share",
            "open": 100,
            "close": 100,
            "split": 1,
            "dividend": 1,
            "suspended": i == 1,
        }
        for i, day in enumerate(days)
    ]
    if unknown:
        base[-1]["suspended"] = "unknown"
    entries = []
    for row in base:
        for metric in ("open", "close", "split", "dividend", "suspended"):
            at = "07:00:00" if metric == "close" else "01:00:00"
            entries.append(
                {
                    "metric": metric,
                    "day": row["day"],
                    "known": row["day"] + "T" + at + "+00:00",
                    "version": metric + "-" + row["day"],
                    "value": row[metric],
                }
            )

    def render(batch):
        values = deepcopy(base)
        for row in values:
            for fact in batch.facts:
                if fact.business_date.isoformat() == row["day"]:
                    row[fact.metric] = fact.value
        return values

    source = canonical_source(
        research,
        "prices",
        entries,
        render,
        fields={"open": {"unit": "CNY/share"}, "close": {"unit": "CNY/share"}},
        adjustment=adjustment,
    )
    return source, base


def test_native_suspension_reaches_real_replay_and_main_index_cannot_be_proxy(tmp_path):
    research = host(tmp_path)
    source, original = price_source(research)
    record = research.event_inputs.register_native(
        "prices", source, "SSE", "suspended-native-prices"
    )
    ref = {"id": record["id"], "revision": 1}
    saved, native, _ = research.event_inputs._record("prices", ref)
    bars, _ = research.event_inputs._prices(saved, native)
    assert bars[-1]["suspended"] is True
    calendar = Calendar.model_validate(
        {
            "exchange": "XSHG",
            "timezone": "Asia/Shanghai",
            "version": "native",
            "source_ref": "native",
            "known_at": "2026-01-01T00:00:00+00:00",
            "sessions": [
                {
                    "day": row["day"],
                    "opens": row["day"] + "T09:30:00+08:00",
                    "closes": row["day"] + "T15:00:00+08:00",
                }
                for row in original
            ],
        }
    )
    result = replay(calendar, proxy_for(), bars, {original[0]["day"]: "1"})
    assert not result["fills"]
    with pytest.raises(StoreError) as error:
        research.event_inputs.resolve_event_study_bundle(ref)
    assert error.value.code == "event_native_main_bundle_must_be_index"


def test_unknown_trade_status_and_adjusted_feed_are_not_raw_proxy_prices(tmp_path):
    research = host(tmp_path)
    source, _ = price_source(research, unknown=True)
    with pytest.raises(StoreError) as error:
        research.event_inputs.register_native("prices", source, "SSE", "unknown-native-status")
    assert error.value.code == "event_native_proxy_trade_status_unknown"
    source, _ = price_source(research, adjustment="qfq")
    with pytest.raises(StoreError) as error:
        research.event_inputs.register_native("prices", source, "SSE", "adjusted-native-prices")
    assert error.value.code == "event_native_proxy_price_basis_unverified_or_adjusted"


def test_logical_unadjusted_query_cannot_hide_nested_adjusted_provider_query(tmp_path):
    research = host(tmp_path)
    original, _ = price_source(research)
    snapshots = Snapshots(research.store)
    previous = snapshots.detail(original["session_id"], original["dataset_id"])
    result = research.datahub.warehouse.read(
        BusinessQuery.model_validate(previous["query"]), "wind", research.datahub.configuration
    )
    logical = BusinessQuery(
        capability="market_bars",
        source="wind",
        parameters={
            "asset": proxy_for().symbol,
            "asset_type": "fund",
            "frequency": "daily",
            "adjustment": "none",
            "start_date": "2026-10-01",
            "end_date": "2026-10-02",
        },
    )
    provider = logical.model_copy(
        update={"parameters": {**logical.parameters, "adjustment": "qfq"}}
    )
    sid = research.store.create("claw", "合成逻辑与提供方口径冲突")["id"]
    manifest = snapshots.publish(
        sid,
        provider,
        result,
        request_query=logical,
        authorization_fingerprint=research.datahub.configuration,
    )
    with pytest.raises(StoreError) as error:
        research.event_inputs.register_native(
            "prices",
            {"session_id": sid, "dataset_id": manifest["dataset_id"]},
            "SSE",
            "nested-provider-adjustment",
        )
    assert error.value.code == "event_native_proxy_price_basis_unverified_or_adjusted"
