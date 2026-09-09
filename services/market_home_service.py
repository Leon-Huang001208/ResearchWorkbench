"""Facts-only market home orchestration and transparent mainline ranking."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time
from typing import ClassVar, Protocol
from uuid import uuid4
from zoneinfo import ZoneInfo

from core.contracts.market_home import (
    MainlineCandidate,
    MainlineCandidateBatch,
    MainlineComponents,
    MainlineRank,
    MarketHomeEnvelope,
    MarketHomeInvalidationEvent,
    MarketHomeSection,
    MarketHomeSectionKey,
    MarketHomeSnapshot,
    SectionDegradation,
    SectionStatus,
    TradingStatus,
)
from core.contracts.platform_shared import FreshnessStatus, ScheduledJob
from core.observability import get_logger

logger = get_logger(__name__)


class SnapshotConflictError(RuntimeError):
    """An immutable close snapshot exists only partially or cannot be replaced."""


class SnapshotNotFoundError(LookupError):
    """No immutable close snapshot exists for the requested trading day."""


class SnapshotNotClosedError(ValueError):
    """The requested day is not eligible for close snapshot creation."""


class MarketHomeRepositoryProtocol(Protocol):
    """Storage boundary used by the market-home service."""

    def read_live_section(
        self,
        section_key: MarketHomeSectionKey,
        trading_day: date,
        *,
        as_of: datetime,
    ) -> MarketHomeSection: ...

    def read_mainline_candidates(
        self, trading_day: date, *, as_of: datetime
    ) -> MainlineCandidateBatch: ...

    def get_close_snapshots(self, trading_day: date) -> list[MarketHomeSnapshot]: ...

    def insert_close_snapshots(
        self, snapshots: list[MarketHomeSnapshot]
    ) -> list[MarketHomeSnapshot]: ...

    def list_invalidation_events(
        self, last_event_id: str | None = None, *, limit: int = 100
    ) -> list[MarketHomeInvalidationEvent]: ...

    def record_invalidation(
        self,
        section_key: MarketHomeSectionKey,
        *,
        as_of: datetime,
        idempotency_key: str,
    ) -> MarketHomeInvalidationEvent: ...

    def ensure_close_snapshot_job(self, trading_day: date) -> ScheduledJob: ...


class MarketHomeService:
    """Build live facts, immutable close snapshots, and transparent rankings."""

    SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")
    FORMULA_VERSION = "mainline-v1"
    SECTION_SLA_SECONDS: ClassVar[dict[MarketHomeSectionKey, int]] = {
        MarketHomeSectionKey.GLOBAL_CONTEXT: 60,
        MarketHomeSectionKey.A_SHARE_STATUS: 30,
        MarketHomeSectionKey.MARKET_MAINLINES: 60,
        MarketHomeSectionKey.IMPORTANT_EVENTS: 15,
        MarketHomeSectionKey.ASSET_MOVES: 30,
    }

    def __init__(
        self,
        repository: MarketHomeRepositoryProtocol,
        *,
        now_provider: Callable[[], datetime] | None = None,
        non_trading_days: set[date] | None = None,
    ) -> None:
        self.repository = repository
        self._now_provider = now_provider or (lambda: datetime.now(UTC))
        self._non_trading_days = non_trading_days or set()

    @classmethod
    def resolve_trading_status(
        cls, now: datetime, *, non_trading_days: set[date] | None = None
    ) -> TradingStatus:
        """Resolve A-share session state using an explicit Asia/Shanghai clock."""

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now must be timezone-aware")
        local = now.astimezone(cls.SHANGHAI_TZ)
        if local.weekday() >= 5 or local.date() in (non_trading_days or set()):
            return TradingStatus.NON_TRADING_DAY
        clock = local.time().replace(tzinfo=None)
        if clock < time(9, 30):
            return TradingStatus.PRE_OPEN
        if time(9, 30) <= clock < time(11, 30):
            return TradingStatus.OPEN
        if time(11, 30) <= clock < time(13, 0):
            return TradingStatus.LUNCH_BREAK
        if time(13, 0) <= clock < time(15, 0):
            return TradingStatus.OPEN
        return TradingStatus.CLOSED

    @staticmethod
    def _percentiles(values: list[float]) -> list[float]:
        """Return deterministic average-rank percentiles on a 0..100 scale."""

        if len(values) == 1:
            return [100.0]
        sorted_pairs = sorted(enumerate(values), key=lambda pair: (pair[1], pair[0]))
        result = [0.0] * len(values)
        position = 0
        while position < len(sorted_pairs):
            end = position
            value = sorted_pairs[position][1]
            while end + 1 < len(sorted_pairs) and sorted_pairs[end + 1][1] == value:
                end += 1
            average_rank = (position + end) / 2
            percentile = round(average_rank / (len(values) - 1) * 100, 6)
            for cursor in range(position, end + 1):
                result[sorted_pairs[cursor][0]] = percentile
            position = end + 1
        return result

    @classmethod
    def rank_mainlines(cls, candidates: list[MainlineCandidate]) -> list[MainlineRank]:
        """Apply mainline-v1 and expose every normalized input and weight result."""

        if not candidates:
            return []
        returns = cls._percentiles([item.return_value for item in candidates])
        turnovers = cls._percentiles([item.turnover_change for item in candidates])
        breadth = cls._percentiles([item.breadth for item in candidates])
        events = cls._percentiles([item.verified_event_density for item in candidates])
        sample_size = len(candidates)
        ranks: list[MainlineRank] = []
        for index, item in enumerate(candidates):
            score = round(
                returns[index] * 0.35
                + turnovers[index] * 0.30
                + breadth[index] * 0.25
                + events[index] * 0.10,
                6,
            )
            ranks.append(
                MainlineRank(
                    theme_key=item.theme_key,
                    label=item.label,
                    direction="leading" if score >= 50.0 else "weakening",
                    score=score,
                    components=MainlineComponents(
                        return_percentile=returns[index],
                        turnover_change_percentile=turnovers[index],
                        breadth_percentile=breadth[index],
                        event_density_percentile=events[index],
                        sample_size=sample_size,
                        formula_version=cls.FORMULA_VERSION,
                    ),
                )
            )
        return sorted(ranks, key=lambda item: (-item.score, item.theme_key))

    def get_live(self) -> MarketHomeEnvelope:
        """Read five independent live projections; one source failure degrades one section."""

        now = self._now_provider()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        local_day = now.astimezone(self.SHANGHAI_TZ).date()
        sections = [self._read_live_section(key, local_day, now) for key in MarketHomeSectionKey]
        logger.info(
            "market home live projection completed",
            trading_day=local_day.isoformat(),
            trading_status=self.resolve_trading_status(
                now, non_trading_days=self._non_trading_days
            ).value,
            unavailable_sections=sum(
                section.status == SectionStatus.UNAVAILABLE for section in sections
            ),
        )
        return MarketHomeEnvelope(
            trading_day=local_day,
            trading_status=self.resolve_trading_status(
                now, non_trading_days=self._non_trading_days
            ),
            sections=sections,
        )

    def get_live_section(self, section_key: MarketHomeSectionKey) -> MarketHomeSection:
        """Read one section for drill-down without coupling it to other section health."""

        now = self._now_provider()
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("now_provider must return a timezone-aware datetime")
        trading_day = now.astimezone(self.SHANGHAI_TZ).date()
        return self._read_live_section(section_key, trading_day, now)

    def _read_live_section(
        self, section_key: MarketHomeSectionKey, trading_day: date, now: datetime
    ) -> MarketHomeSection:
        try:
            if section_key == MarketHomeSectionKey.MARKET_MAINLINES:
                batch = self.repository.read_mainline_candidates(trading_day, as_of=now)
                ranks = self.rank_mainlines(batch.candidates)
                if not ranks and not batch.missing_components:
                    return self._unavailable_section(
                        section_key, now, "empty_sample", retryable=True
                    )
                section = MarketHomeSection(
                    section_key=section_key,
                    status=(
                        SectionStatus.PARTIAL if batch.missing_components else SectionStatus.READY
                    ),
                    payload={
                        "formula": (
                            "return_percentile*0.35 + "
                            "turnover_change_percentile*0.30 + "
                            "breadth_percentile*0.25 + "
                            "event_density_percentile*0.10"
                        ),
                        "formula_version": self.FORMULA_VERSION,
                        "leading": [
                            item.model_dump(mode="json")
                            for item in ranks
                            if item.direction == "leading"
                        ],
                        "weakening": [
                            item.model_dump(mode="json")
                            for item in ranks
                            if item.direction == "weakening"
                        ],
                    },
                    degradation=(
                        SectionDegradation(
                            error_code="mainline_components_incomplete",
                            retryable=True,
                            missing_components=batch.missing_components,
                        )
                        if batch.missing_components
                        else None
                    ),
                    as_of=batch.as_of,
                    observed_at=batch.observed_at,
                    available_at=batch.available_at,
                    source_refs=batch.source_refs,
                    freshness_status=batch.freshness_status,
                    quality_flags=batch.quality_flags,
                )
            else:
                section = self.repository.read_live_section(section_key, trading_day, as_of=now)
            return self._apply_sla(section, now)
        except TimeoutError:
            logger.warning(
                "market home section timed out",
                section_key=section_key.value,
                trading_day=trading_day.isoformat(),
            )
            return self._unavailable_section(section_key, now, "source_timeout", retryable=True)
        except Exception as exc:
            logger.exception(
                "market home section failed",
                section_key=section_key.value,
                trading_day=trading_day.isoformat(),
                error_type=type(exc).__name__,
            )
            return self._unavailable_section(section_key, now, "source_error", retryable=True)

    def _apply_sla(self, section: MarketHomeSection, now: datetime) -> MarketHomeSection:
        age_seconds = max(0.0, (now - section.available_at).total_seconds())
        if section.freshness_status != FreshnessStatus.FRESH:
            logger.info(
                "market home section projected",
                section_key=section.section_key.value,
                status=section.status.value,
                freshness_status=section.freshness_status.value,
                actual_age_seconds=round(age_seconds, 3),
                sla_seconds=self.SECTION_SLA_SECONDS[section.section_key],
            )
            return section.model_copy(update={"age_seconds": round(age_seconds, 3)})
        if age_seconds <= self.SECTION_SLA_SECONDS[section.section_key]:
            logger.info(
                "market home section projected",
                section_key=section.section_key.value,
                status=section.status.value,
                freshness_status=section.freshness_status.value,
                actual_age_seconds=round(age_seconds, 3),
                sla_seconds=self.SECTION_SLA_SECONDS[section.section_key],
            )
            return section.model_copy(update={"age_seconds": round(age_seconds, 3)})
        quality_flags = list(section.quality_flags)
        quality_flags.append(f"sla_breach:{round(age_seconds, 3)}s")
        is_partial = section.status == SectionStatus.PARTIAL
        logger.warning(
            "market home section SLA breached",
            section_key=section.section_key.value,
            status=(SectionStatus.PARTIAL if is_partial else SectionStatus.STALE).value,
            actual_age_seconds=round(age_seconds, 3),
            sla_seconds=self.SECTION_SLA_SECONDS[section.section_key],
        )
        return section.model_copy(
            update={
                "status": SectionStatus.PARTIAL if is_partial else SectionStatus.STALE,
                "age_seconds": round(age_seconds, 3),
                "freshness_status": FreshnessStatus.STALE,
                "quality_flags": quality_flags,
                "degradation": (
                    section.degradation
                    if is_partial
                    else SectionDegradation(
                        error_code="sla_breach", retryable=True, missing_components=[]
                    )
                ),
            }
        )

    @staticmethod
    def _unavailable_section(
        section_key: MarketHomeSectionKey,
        now: datetime,
        error_code: str,
        *,
        retryable: bool,
    ) -> MarketHomeSection:
        return MarketHomeSection(
            section_key=section_key,
            status=SectionStatus.UNAVAILABLE,
            payload={},
            degradation=SectionDegradation(error_code=error_code, retryable=retryable),
            as_of=now,
            observed_at=now,
            available_at=now,
            source_refs=[],
            freshness_status=FreshnessStatus.UNAVAILABLE,
            quality_flags=[error_code],
        )

    def get_snapshot(self, trading_day: date) -> list[MarketHomeSnapshot]:
        """Read historical close state from immutable snapshots only."""

        snapshots = self.repository.get_close_snapshots(trading_day)
        if not snapshots:
            raise SnapshotNotFoundError(trading_day.isoformat())
        if len(snapshots) != len(MarketHomeSectionKey):
            raise SnapshotConflictError("close snapshot is incomplete")
        return snapshots

    def list_invalidation_events(
        self, last_event_id: str | None = None
    ) -> list[MarketHomeInvalidationEvent]:
        """Read durable invalidation references for SSE replay and polling."""

        return self.repository.list_invalidation_events(last_event_id)

    def record_fact_update(
        self,
        section_key: MarketHomeSectionKey,
        *,
        as_of: datetime,
        idempotency_key: str,
    ) -> MarketHomeInvalidationEvent:
        """Write the durable section-invalidated outbox row after a fact update."""

        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")
        return self.repository.record_invalidation(
            section_key,
            as_of=as_of,
            idempotency_key=idempotency_key,
        )

    def schedule_close_snapshot(self, trading_day: date) -> ScheduledJob:
        """Ensure one persistent close-snapshot job exists for the trading day."""

        return self.repository.ensure_close_snapshot_job(trading_day)

    def create_close_snapshot(self, trading_day: date) -> list[MarketHomeSnapshot]:
        """Create the five close rows once; repeat calls return the immutable rows."""

        existing = self.repository.get_close_snapshots(trading_day)
        if existing:
            if len(existing) != len(MarketHomeSectionKey):
                raise SnapshotConflictError("close snapshot is incomplete")
            return existing
        now = self._now_provider()
        local_now = now.astimezone(self.SHANGHAI_TZ)
        if trading_day > local_now.date() or (
            trading_day == local_now.date()
            and self.resolve_trading_status(local_now, non_trading_days=self._non_trading_days)
            != TradingStatus.CLOSED
        ):
            raise SnapshotNotClosedError("trading day has not closed")
        envelope = self.get_live()
        if envelope.trading_day != trading_day:
            raise SnapshotNotClosedError("past close snapshots cannot be rebuilt from live facts")
        snapshots = [
            MarketHomeSnapshot(
                snapshot_id=str(uuid4()),
                trading_day=trading_day,
                snapshot_kind="close",
                section_key=section.section_key,
                formula_version=self.FORMULA_VERSION,
                payload=section.payload,
                input_fact_refs=[ref.source_id for ref in section.source_refs],
                as_of=section.as_of,
                observed_at=section.observed_at,
                available_at=section.available_at,
                source_refs=section.source_refs,
                freshness_status=section.freshness_status,
                quality_flags=section.quality_flags,
            )
            for section in envelope.sections
        ]
        return self.repository.insert_close_snapshots(snapshots)
