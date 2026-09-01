from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from core.contracts.market_home import (
    MainlineCandidateBatch,
    MainlineRank,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
    SectionStatus,
    TradingStatus,
)
from core.contracts.platform_shared import FreshnessStatus, SourceRef, SourceTier
from services.market_home_service import (
    MainlineCandidate,
    MarketHomeService,
    SnapshotConflictError,
)

SOURCE = SourceRef(
    source_id="test-market-source",
    name="Test Market Source",
    tier=SourceTier.OFFICIAL,
    content_hash="sha256:test-market-source",
)


def _section(
    key: MarketHomeSectionKey,
    *,
    available_at: datetime,
    payload: dict | None = None,
) -> MarketHomeSection:
    return MarketHomeSection(
        section_key=key,
        status=SectionStatus.READY,
        payload=payload or {"value": key.value},
        as_of=available_at,
        observed_at=available_at,
        available_at=available_at,
        source_refs=[SOURCE],
        freshness_status=FreshnessStatus.FRESH,
        quality_flags=[],
    )


class FakeMarketHomeRepository:
    def __init__(self, now: datetime) -> None:
        self.now = now
        self.failures: set[MarketHomeSectionKey] = set()
        self.sections: dict[MarketHomeSectionKey, MarketHomeSection] = {
            key: _section(key, available_at=now) for key in MarketHomeSectionKey
        }
        self.candidates: list[MainlineCandidate] = []
        self.snapshots: dict[date, list[MarketHomeSnapshot]] = {}
        self.live_calls = 0

    def read_live_section(
        self,
        section_key: MarketHomeSectionKey,
        trading_day: date,
        *,
        as_of: datetime,
    ) -> MarketHomeSection:
        self.live_calls += 1
        if section_key in self.failures:
            raise TimeoutError(section_key.value)
        return self.sections[section_key]

    def read_mainline_candidates(
        self, trading_day: date, *, as_of: datetime
    ) -> MainlineCandidateBatch:
        self.live_calls += 1
        if MarketHomeSectionKey.MARKET_MAINLINES in self.failures:
            raise TimeoutError("market_mainlines")
        section = self.sections[MarketHomeSectionKey.MARKET_MAINLINES]
        return MainlineCandidateBatch(
            candidates=self.candidates,
            missing_components=[],
            as_of=section.as_of,
            observed_at=section.observed_at,
            available_at=section.available_at,
            source_refs=section.source_refs,
            freshness_status=section.freshness_status,
            quality_flags=section.quality_flags,
        )

    def get_close_snapshots(self, trading_day: date) -> list[MarketHomeSnapshot]:
        return list(self.snapshots.get(trading_day, []))

    def insert_close_snapshots(
        self, snapshots: list[MarketHomeSnapshot]
    ) -> list[MarketHomeSnapshot]:
        day = snapshots[0].trading_day
        if day in self.snapshots:
            raise AssertionError("service attempted to mutate an immutable close snapshot")
        self.snapshots[day] = list(snapshots)
        return list(snapshots)


def test_mainline_v1_exposes_percentiles_weights_and_deterministic_ties() -> None:
    candidates = [
        MainlineCandidate("ai", "AI", 8.0, 3.0, 0.8, 2.0),
        MainlineCandidate("gold", "黄金", 2.0, 1.0, 0.4, 1.0),
        MainlineCandidate("solar", "光伏", 2.0, 1.0, 0.4, 1.0),
    ]

    ranks = MarketHomeService.rank_mainlines(candidates)

    assert [rank.theme_key for rank in ranks] == ["ai", "gold", "solar"]
    assert ranks[0].score == 100.0
    assert ranks[0].components.model_dump() == {
        "return_percentile": 100.0,
        "turnover_change_percentile": 100.0,
        "breadth_percentile": 100.0,
        "event_density_percentile": 100.0,
        "sample_size": 3,
        "formula_version": "mainline-v1",
    }
    assert ranks[1].score == ranks[2].score == 25.0
    assert all(isinstance(rank, MainlineRank) for rank in ranks)


def test_mainline_single_sample_has_defined_percentiles() -> None:
    ranks = MarketHomeService.rank_mainlines(
        [MainlineCandidate("only", "唯一主题", 1.0, 1.0, 1.0, 1.0)]
    )

    assert ranks[0].score == 100.0
    assert ranks[0].components.sample_size == 1


@pytest.mark.parametrize(
    ("local_time", "expected"),
    [
        (
            datetime(2026, 9, 1, 9, 29, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.PRE_OPEN,
        ),
        (
            datetime(2026, 9, 1, 9, 30, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.OPEN,
        ),
        (
            datetime(2026, 9, 1, 11, 30, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.LUNCH_BREAK,
        ),
        (
            datetime(2026, 9, 1, 13, 0, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.OPEN,
        ),
        (
            datetime(2026, 9, 1, 15, 0, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.CLOSED,
        ),
        (
            datetime(2026, 9, 5, 10, 0, tzinfo=MarketHomeService.SHANGHAI_TZ),
            TradingStatus.NON_TRADING_DAY,
        ),
    ],
)
def test_trading_status_uses_asia_shanghai_boundaries(
    local_time: datetime, expected: TradingStatus
) -> None:
    assert MarketHomeService.resolve_trading_status(local_time) == expected


def test_live_home_degrades_only_the_failed_section_and_keeps_five_sections() -> None:
    now = datetime(2026, 9, 1, 10, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    repo.failures.add(MarketHomeSectionKey.IMPORTANT_EVENTS)
    repo.candidates = [MainlineCandidate("gold", "黄金", 1.0, 1.0, 1.0, 1.0)]

    envelope = MarketHomeService(repo, now_provider=lambda: now).get_live()

    assert len(envelope.sections) == 5
    by_key = {section.section_key: section for section in envelope.sections}
    failed = by_key[MarketHomeSectionKey.IMPORTANT_EVENTS]
    assert failed.status == SectionStatus.UNAVAILABLE
    assert failed.freshness_status == FreshnessStatus.UNAVAILABLE
    assert failed.payload == {}
    assert failed.degradation is not None
    assert failed.degradation.error_code == "source_timeout"
    assert all(
        section.status == SectionStatus.READY
        for key, section in by_key.items()
        if key != MarketHomeSectionKey.IMPORTANT_EVENTS
    )


def test_mainline_quality_failure_is_partial_and_names_missing_component() -> None:
    now = datetime(2026, 9, 1, 10, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    repo.candidates = [MainlineCandidate("gold", "黄金", 1, 1, 1, 1)]
    original = repo.read_mainline_candidates

    def partial_batch(trading_day: date, *, as_of: datetime) -> MainlineCandidateBatch:
        batch = original(trading_day, as_of=as_of)
        return batch.model_copy(
            update={
                "missing_components": [
                    "solar:return:freshness:quarantined",
                    "ai:verified_event_density:future_available_at",
                ]
            }
        )

    repo.read_mainline_candidates = partial_batch  # type: ignore[method-assign]

    envelope = MarketHomeService(repo, now_provider=lambda: now).get_live()
    mainline = next(
        section
        for section in envelope.sections
        if section.section_key == MarketHomeSectionKey.MARKET_MAINLINES
    )

    assert mainline.status == SectionStatus.PARTIAL
    assert mainline.degradation is not None
    assert mainline.degradation.error_code == "mainline_components_incomplete"
    assert mainline.degradation.missing_components == [
        "solar:return:freshness:quarantined",
        "ai:verified_event_density:future_available_at",
    ]


def test_mainline_missing_components_remain_partial_when_batch_is_also_stale() -> None:
    now = datetime(2026, 9, 1, 10, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now - timedelta(seconds=61))
    repo.candidates = [MainlineCandidate("gold", "黄金", 1, 1, 1, 1)]
    original = repo.read_mainline_candidates

    def stale_partial_batch(trading_day: date, *, as_of: datetime) -> MainlineCandidateBatch:
        return original(trading_day, as_of=as_of).model_copy(
            update={"missing_components": ["solar:return:freshness:quarantined"]}
        )

    repo.read_mainline_candidates = stale_partial_batch  # type: ignore[method-assign]

    mainline = MarketHomeService(repo, now_provider=lambda: now).get_live_section(
        MarketHomeSectionKey.MARKET_MAINLINES
    )

    assert mainline.status == SectionStatus.PARTIAL
    assert mainline.freshness_status == FreshnessStatus.STALE
    assert mainline.degradation is not None
    assert mainline.degradation.missing_components == ["solar:return:freshness:quarantined"]
    assert any(flag.startswith("sla_breach:") for flag in mainline.quality_flags)


@pytest.mark.parametrize(
    ("section_key", "age_seconds", "expected"),
    [
        (MarketHomeSectionKey.A_SHARE_STATUS, 31, FreshnessStatus.STALE),
        (MarketHomeSectionKey.ASSET_MOVES, 30, FreshnessStatus.FRESH),
        (MarketHomeSectionKey.MARKET_MAINLINES, 61, FreshnessStatus.STALE),
        (MarketHomeSectionKey.GLOBAL_CONTEXT, 60, FreshnessStatus.FRESH),
        (MarketHomeSectionKey.IMPORTANT_EVENTS, 16, FreshnessStatus.STALE),
    ],
)
def test_section_sla_is_applied_independently(
    section_key: MarketHomeSectionKey,
    age_seconds: int,
    expected: FreshnessStatus,
) -> None:
    now = datetime(2026, 9, 1, 2, 0, tzinfo=UTC)
    repo = FakeMarketHomeRepository(now)
    repo.sections[section_key] = _section(
        section_key, available_at=now - timedelta(seconds=age_seconds)
    )
    if section_key == MarketHomeSectionKey.MARKET_MAINLINES:
        repo.candidates = [MainlineCandidate("gold", "黄金", 1, 1, 1, 1)]

    envelope = MarketHomeService(repo, now_provider=lambda: now).get_live()
    actual = next(item for item in envelope.sections if item.section_key == section_key)

    assert actual.freshness_status == expected
    assert actual.status == (
        SectionStatus.STALE if expected == FreshnessStatus.STALE else SectionStatus.READY
    )
    assert actual.age_seconds == float(age_seconds)


def test_historical_read_never_calls_live_provider() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    day = now.date()
    repo.snapshots[day] = [
        MarketHomeSnapshot(
            snapshot_id=f"snapshot-{key.value}",
            trading_day=day,
            snapshot_kind="close",
            section_key=key,
            formula_version="mainline-v1",
            payload={"section": key.value},
            input_fact_refs=[],
            as_of=now,
            observed_at=now,
            available_at=now,
            source_refs=[SOURCE],
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )
        for key in MarketHomeSectionKey
    ]

    snapshots = MarketHomeService(repo, now_provider=lambda: now).get_snapshot(day)

    assert len(snapshots) == 5
    assert repo.live_calls == 0


def test_close_snapshot_is_immutable_and_idempotent() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    repo.candidates = [MainlineCandidate("gold", "黄金", 1, 1, 1, 1)]
    service = MarketHomeService(repo, now_provider=lambda: now)

    first = service.create_close_snapshot(now.date())
    live_calls_after_first = repo.live_calls
    second = service.create_close_snapshot(now.date())

    assert [item.snapshot_id for item in first] == [item.snapshot_id for item in second]
    assert repo.live_calls == live_calls_after_first


def test_close_snapshot_preserves_unavailable_section_without_fake_provenance() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    repo.candidates = [MainlineCandidate("gold", "黄金", 1, 1, 1, 1)]
    repo.failures.add(MarketHomeSectionKey.IMPORTANT_EVENTS)

    snapshots = MarketHomeService(repo, now_provider=lambda: now).create_close_snapshot(now.date())
    unavailable = next(
        item for item in snapshots if item.section_key == MarketHomeSectionKey.IMPORTANT_EVENTS
    )

    assert unavailable.freshness_status == FreshnessStatus.UNAVAILABLE
    assert unavailable.source_refs == []
    assert unavailable.quality_flags == ["source_timeout"]


def test_partial_close_snapshot_is_reported_as_conflict() -> None:
    now = datetime(2026, 9, 1, 16, 0, tzinfo=MarketHomeService.SHANGHAI_TZ)
    repo = FakeMarketHomeRepository(now)
    repo.snapshots[now.date()] = [
        MarketHomeSnapshot(
            snapshot_id="partial",
            trading_day=now.date(),
            snapshot_kind="close",
            section_key=MarketHomeSectionKey.GLOBAL_CONTEXT,
            formula_version="mainline-v1",
            payload={},
            input_fact_refs=[],
            as_of=now,
            observed_at=now,
            available_at=now,
            source_refs=[SOURCE],
            freshness_status=FreshnessStatus.FRESH,
            quality_flags=[],
        )
    ]

    with pytest.raises(SnapshotConflictError):
        MarketHomeService(repo, now_provider=lambda: now).create_close_snapshot(now.date())


def test_unavailable_section_has_no_fabricated_source_but_ready_requires_one() -> None:
    unavailable = MarketHomeSection(
        section_key=MarketHomeSectionKey.GLOBAL_CONTEXT,
        status=SectionStatus.UNAVAILABLE,
        payload={},
        as_of=datetime(2026, 9, 1, tzinfo=UTC),
        observed_at=datetime(2026, 9, 1, tzinfo=UTC),
        available_at=datetime(2026, 9, 1, tzinfo=UTC),
        source_refs=[],
        freshness_status=FreshnessStatus.UNAVAILABLE,
        quality_flags=["source_timeout"],
    )

    assert unavailable.source_refs == []
    with pytest.raises(ValueError, match="source_refs"):
        MarketHomeSection(
            **{
                **unavailable.model_dump(),
                "status": SectionStatus.READY,
                "freshness_status": FreshnessStatus.FRESH,
            }
        )
