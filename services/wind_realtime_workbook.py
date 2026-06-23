"""Wind realtime workbook snapshot reader and parser."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from core.observability import get_logger

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_WORKBOOK_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "AlphaFoundry"
    / "wind"
    / "AlphaFoundry_Wind_Realtime.xlsx"
)

SNAPSHOT_HEADERS = [
    "view_key",
    "view_label",
    "wind_code",
    "name",
    "last",
    "pct_change",
    "is_concept",
    "source",
    "updated_at",
    "status",
]


@dataclass(frozen=True)
class WorkbookSnapshotRow:
    view_key: str
    view_label: str
    wind_code: str
    name: str
    last: float | None
    pct_change: float
    is_concept: bool
    source: str
    updated_at: datetime
    status: str = "ok"


@dataclass(frozen=True)
class WorkbookSnapshot:
    rows: tuple[WorkbookSnapshotRow, ...]
    status: str
    is_stale: bool
    updated_at: datetime | None
    error_count: int = 0
    message: str = ""


def resolve_workbook_path(path: str | Path | None = None) -> Path:
    if path is None or str(path).strip() == "":
        return DEFAULT_WORKBOOK_PATH
    return Path(path).expanduser()


def parse_snapshot_rows(
    rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 60,
) -> WorkbookSnapshot:
    reference_time = _ensure_aware(now or datetime.now(UTC))
    parsed_rows: list[WorkbookSnapshotRow] = []
    error_count = 0

    for row in rows:
        try:
            status = str(row.get("status") or "ok").strip() or "ok"
            pct_change = _parse_float(row.get("pct_change"))
            if pct_change is None or status != "ok":
                error_count += 1
                logger.warning("Skipping invalid Wind snapshot row: %s", row)
                continue

            wind_code = str(row.get("wind_code") or "").strip()
            name = str(row.get("name") or "").strip()
            updated_at = _parse_datetime(row.get("updated_at"))
            if not wind_code or not name or updated_at is None:
                error_count += 1
                logger.warning("Skipping incomplete Wind snapshot row: %s", row)
                continue

            parsed_rows.append(
                WorkbookSnapshotRow(
                    view_key=str(row.get("view_key") or "").strip(),
                    view_label=str(row.get("view_label") or "").strip(),
                    wind_code=wind_code,
                    name=name,
                    last=_parse_float(row.get("last")),
                    pct_change=pct_change,
                    is_concept=_parse_bool(row.get("is_concept")),
                    source=str(row.get("source") or "wind").strip(),
                    updated_at=updated_at,
                    status=status,
                )
            )
        except (AttributeError, TypeError, ValueError) as exc:
            error_count += 1
            logger.warning("Failed to parse Wind snapshot row %s: %s", row, exc)

    updated_at = max((item.updated_at for item in parsed_rows), default=None)
    is_stale = any(
        (reference_time - item.updated_at).total_seconds() > stale_after_seconds
        for item in parsed_rows
    )
    status = "snapshot_stale" if is_stale else "ok"
    message = "Wind数据可能未刷新" if is_stale else ""
    if not parsed_rows:
        status = "snapshot_empty"
        message = "Wind快照暂无可用数据"

    return WorkbookSnapshot(
        rows=tuple(parsed_rows),
        status=status,
        is_stale=is_stale,
        updated_at=updated_at,
        error_count=error_count,
        message=message,
    )


def split_snapshot_movers(
    rows: Iterable[WorkbookSnapshotRow],
    *,
    limit: int = 10,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered_rows = [
        row for row in rows if row.view_key.strip() and row.wind_code.strip() and row.name.strip()
    ]
    up = sorted(
        (row for row in ordered_rows if row.pct_change > 0),
        key=lambda row: row.pct_change,
        reverse=True,
    )[:limit]
    down = sorted(
        (row for row in ordered_rows if row.pct_change < 0),
        key=lambda row: row.pct_change,
    )[:limit]
    return ([_row_to_mover(row) for row in up], [_row_to_mover(row) for row in down])


def _row_to_mover(row: WorkbookSnapshotRow) -> dict[str, Any]:
    return {
        "sector_id": f"wind-{row.wind_code.replace('.', '-')}",
        "name": row.name,
        "change_pct": round(row.pct_change, 2),
        "leading_stocks": [],
        "related_news_count": 0,
        "is_concept": row.is_concept,
        "source": row.source,
        "view_key": row.view_key,
        "view_label": row.view_label,
    }


def _parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "是"}


def _parse_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return _ensure_aware(value)
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(str(value).strip())
    except ValueError:
        logger.warning("Invalid Wind snapshot updated_at value: %s", value)
        return None
    return _ensure_aware(parsed)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=SHANGHAI_TZ).astimezone(UTC)
    return value.astimezone(UTC)
