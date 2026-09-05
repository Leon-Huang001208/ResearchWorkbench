"""Transaction-coupled market-home invalidation helpers for fact repositories."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from core.contracts.market_home import (
    MarketHomeInvalidationEvent,
    MarketHomeSectionKey,
)
from core.observability import get_logger
from data_layer.repositories.market_home_repository import MarketHomeRepository

logger = get_logger(__name__)


def aware_utc(value: datetime) -> datetime:
    """Normalize legacy naive writer timestamps without changing aware instants."""

    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def record_market_home_fact_update(
    db: Session,
    section_keys: Iterable[MarketHomeSectionKey],
    *,
    as_of: datetime,
    idempotency_key: str,
) -> list[MarketHomeInvalidationEvent]:
    """Flush idempotent outbox rows in the caller's uncommitted fact transaction."""

    if not idempotency_key.strip():
        raise ValueError("idempotency_key is required")
    normalized_as_of = aware_utc(as_of)
    repository = MarketHomeRepository(db)
    events = [
        repository.record_invalidation(
            section_key,
            as_of=normalized_as_of,
            idempotency_key=idempotency_key,
        )
        for section_key in sorted(set(section_keys), key=lambda item: item.value)
    ]
    logger.info(
        "market home fact update invalidations flushed",
        idempotency_key=idempotency_key,
        section_keys=[event.section_key.value for event in events],
        as_of=normalized_as_of.isoformat(),
    )
    return events
