"""Wind realtime workbook snapshot reader and parser."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from openpyxl import Workbook

from core.observability import get_logger
from services.wind_index_catalog import MARKET_VIEW_LABELS, load_wind_index_catalog

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

WORKBOOK_SHEETS = [
    "README",
    "Config",
    "IndexCatalog",
    "RealtimeRaw",
    "Snapshot",
    "Health",
    "FormulaLog",
]

CATALOG_HEADERS = [
    "row_id",
    "view_key",
    "view_label",
    "wind_code",
    "name",
    "is_active",
    "is_concept",
    "priority",
    "source_family",
    "notes",
]

RAW_HEADERS = [
    "row_id",
    "view_key",
    "view_label",
    "wind_code",
    "name_formula",
    "last_formula",
    "pct_change_formula",
    "update_time_formula",
    "name_value",
    "last_value",
    "pct_change_value",
    "update_time_value",
    "status",
]

HEALTH_HEADERS = ["metric", "value", "updated_at", "notes"]
LOG_HEADERS = ["timestamp", "level", "component", "message", "details"]
ISO_NOW_FORMULA = '=TEXT(NOW(),"yyyy-mm-ddThh:mm:ss")'


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


class WindRealtimeWorkbookReader:
    """Read Wind snapshot data from an already-open realtime workbook."""

    def __init__(
        self,
        workbook_path: str | Path | None = None,
        *,
        stale_after_seconds: int = 60,
    ) -> None:
        self.workbook_path = resolve_workbook_path(workbook_path)
        self.stale_after_seconds = stale_after_seconds

    def get_view(self, view_key: str, limit: int = 10) -> dict[str, Any]:
        view_label = MARKET_VIEW_LABELS.get(view_key, view_key)
        if not self.workbook_path.exists():
            logger.warning("Wind realtime workbook missing: %s", self.workbook_path)
            return _status_payload(
                view_key=view_key,
                view_label=view_label,
                limit=limit,
                status="workbook_missing",
                message=f"Wind实时工作簿不存在: {self.workbook_path}",
                cache_ttl_seconds=self.stale_after_seconds,
            )

        snapshot = self.load_snapshot()
        return payload_from_snapshot(
            snapshot,
            view_key=view_key,
            limit=limit,
            view_label=view_label,
            cache_ttl_seconds=self.stale_after_seconds,
        )

    def load_snapshot(self) -> WorkbookSnapshot:
        try:
            import xlwings as xw
        except ImportError:
            logger.warning("xlwings is unavailable for Wind realtime workbook reads")
            return WorkbookSnapshot(
                rows=(),
                status="xlwings_unavailable",
                is_stale=False,
                updated_at=None,
                message="xlwings不可用，无法读取已打开的Wind实时工作簿",
            )

        try:
            workbook = self._find_open_workbook(xw)
            if workbook is None:
                logger.warning("Wind realtime workbook is not open: %s", self.workbook_path)
                return WorkbookSnapshot(
                    rows=(),
                    status="workbook_not_open",
                    is_stale=False,
                    updated_at=None,
                    message="Wind实时工作簿未在Excel中打开",
                )

            values = workbook.sheets["Snapshot"].used_range.value
            rows = self._rows_from_matrix(values)
            return parse_snapshot_rows(
                rows,
                stale_after_seconds=self.stale_after_seconds,
            )
        except Exception as exc:
            logger.error(
                "Failed to read Wind realtime workbook snapshot %s: %s",
                self.workbook_path,
                exc,
            )
            return WorkbookSnapshot(
                rows=(),
                status="workbook_read_error",
                is_stale=False,
                updated_at=None,
                error_count=1,
                message=f"读取Wind实时工作簿失败: {exc}",
            )

    def _find_open_workbook(self, xw: Any) -> Any | None:
        target = self.workbook_path.expanduser()
        try:
            target_resolved = target.resolve()
        except OSError:
            target_resolved = target

        for app in xw.apps:
            for book in app.books:
                fullname = str(getattr(book, "fullname", "") or "")
                if fullname:
                    try:
                        if Path(fullname).expanduser().resolve() == target_resolved:
                            return book
                    except OSError:
                        if Path(fullname).expanduser() == target:
                            return book
        return None

    def _rows_from_matrix(self, values: Any) -> list[dict[str, Any]]:
        return _rows_from_matrix(values)


def _rows_from_matrix(values: Any) -> list[dict[str, Any]]:
    if values is None:
        return []
    matrix = values if isinstance(values, (list, tuple)) else [[values]]
    if matrix and not isinstance(matrix[0], (list, tuple)):
        matrix = [matrix]
    if not matrix:
        return []

    headers = [str(value or "").strip() for value in matrix[0]]
    rows: list[dict[str, Any]] = []
    for raw_row in matrix[1:]:
        if raw_row is None:
            continue
        cells = raw_row if isinstance(raw_row, (list, tuple)) else [raw_row]
        if not any(cell not in (None, "") for cell in cells):
            continue
        row = {
            header: cells[index] if index < len(cells) else None
            for index, header in enumerate(headers)
            if header
        }
        if row:
            rows.append(row)
    return rows


def resolve_workbook_path(path: str | Path | None = None) -> Path:
    if path is None or str(path).strip() == "":
        return DEFAULT_WORKBOOK_PATH
    return Path(path).expanduser()


def build_realtime_workbook(
    catalog_path: str | Path,
    workbook_path: str | Path | None = None,
) -> Path:
    output_path = resolve_workbook_path(workbook_path)
    generated_at = datetime.now(UTC).isoformat()

    try:
        entries = load_wind_index_catalog(catalog_path)
        if not entries:
            raise ValueError(f"Wind index catalog is empty: {catalog_path}")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        workbook = Workbook()
        workbook.remove(workbook.active)
        sheets = {name: workbook.create_sheet(name) for name in WORKBOOK_SHEETS}

        sheets["README"]["A1"] = "AlphaFoundry Wind Realtime Workbook"
        sheets["README"][
            "A2"
        ] = "Open this workbook in Excel and log in to Wind before using Wind market views."

        sheets["Config"].append(["key", "value", "description"])
        sheets["Config"].append(["refresh_enabled", "true", "是否启用实时刷新"])
        sheets["Config"].append(
            ["expected_update_seconds", "60", "超过该秒数视为数据可能过期"]
        )
        sheets["Config"].append(["formula_version", "1", "公式模板版本"])
        sheets["Config"].append(["last_generated_at", generated_at, "工作簿最后生成时间"])
        sheets["Config"].append(["timezone", "Asia/Shanghai", "时间区域"])
        sheets["Config"].append(["data_owner", "AlphaFoundry", "数据维护方"])

        sheets["IndexCatalog"].append(CATALOG_HEADERS)
        sheets["RealtimeRaw"].append(RAW_HEADERS)
        sheets["Snapshot"].append(SNAPSHOT_HEADERS)
        sheets["Health"].append(HEALTH_HEADERS)
        sheets["FormulaLog"].append(LOG_HEADERS)

        raw_row_number = 2
        active_count = 0
        for row_id, entry in enumerate(entries, start=1):
            sheets["IndexCatalog"].append(
                [
                    row_id,
                    entry.view_key,
                    entry.view_label,
                    entry.code,
                    entry.name,
                    str(entry.is_active).lower(),
                    str(entry.is_concept).lower(),
                    entry.priority,
                    entry.family,
                    entry.notes,
                ]
            )
            if not entry.is_active:
                continue

            sheets["RealtimeRaw"].append(
                [
                    row_id,
                    entry.view_key,
                    entry.view_label,
                    entry.code,
                    f'=@s_info_name("{entry.code}")',
                    f'=@wss("{entry.code}","rt_last")',
                    f'=@wss("{entry.code}","rt_pct_chg")',
                    ISO_NOW_FORMULA,
                    f"=E{raw_row_number}",
                    f"=F{raw_row_number}",
                    f"=G{raw_row_number}",
                    f"=H{raw_row_number}",
                    (
                        f'=IF(OR(ISERROR(F{raw_row_number}),'
                        f'ISERROR(G{raw_row_number})),"formula_error","ok")'
                    ),
                ]
            )
            sheets["Snapshot"].append(
                [
                    f"=RealtimeRaw!B{raw_row_number}",
                    f"=RealtimeRaw!C{raw_row_number}",
                    f"=RealtimeRaw!D{raw_row_number}",
                    f"=RealtimeRaw!I{raw_row_number}",
                    f"=RealtimeRaw!J{raw_row_number}",
                    f"=RealtimeRaw!K{raw_row_number}",
                    str(entry.is_concept).lower(),
                    "wind",
                    f"=RealtimeRaw!L{raw_row_number}",
                    f"=RealtimeRaw!M{raw_row_number}",
                ]
            )
            active_count += 1
            raw_row_number += 1

        sheets["Health"].append(["workbook_open", "true", generated_at, "文件已生成"])
        sheets["Health"].append(
            ["active_index_count", active_count, generated_at, "active 指数数量"]
        )
        for sheet in sheets.values():
            sheet.freeze_panes = "A2"

        workbook.save(output_path)
    except Exception as exc:
        logger.error(
            "Failed to build Wind realtime workbook from %s to %s: %s",
            catalog_path,
            output_path,
            exc,
        )
        raise RuntimeError(f"Failed to build Wind realtime workbook: {exc}") from exc

    logger.info(
        "Built Wind realtime workbook: path=%s catalog=%s active_count=%s",
        output_path,
        catalog_path,
        active_count,
    )
    return output_path


def payload_from_snapshot(
    snapshot: WorkbookSnapshot,
    *,
    view_key: str,
    limit: int,
    view_label: str,
    cache_ttl_seconds: int = 60,
) -> dict[str, Any]:
    rows = [row for row in snapshot.rows if row.view_key == view_key]
    up, down = split_snapshot_movers(rows, limit=limit)
    has_real_data = bool(rows)
    cache_hit = has_real_data and snapshot.status in {"ok", "snapshot_stale"}

    return {
        "view_key": view_key,
        "view_label": view_label,
        "up": up,
        "down": down,
        "has_real_data": has_real_data,
        "fetched_at": datetime.now(UTC).isoformat(),
        "cache_hit": cache_hit,
        "cache_ttl_seconds": cache_ttl_seconds,
        "status": snapshot.status,
        "message": snapshot.message,
        "source": "wind_realtime_workbook",
        "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
        "error_count": snapshot.error_count,
    }


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
    if not parsed_rows and error_count > 0:
        status = "snapshot_invalid"
        message = "Wind快照全部解析失败，请检查Excel公式或Wind刷新状态"
    elif not parsed_rows:
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


def _status_payload(
    *,
    view_key: str,
    view_label: str,
    limit: int,
    status: str,
    message: str,
    cache_ttl_seconds: int,
) -> dict[str, Any]:
    snapshot = WorkbookSnapshot(
        rows=(),
        status=status,
        is_stale=False,
        updated_at=None,
        message=message,
    )
    payload = payload_from_snapshot(
        snapshot,
        view_key=view_key,
        limit=limit,
        view_label=view_label,
        cache_ttl_seconds=cache_ttl_seconds,
    )
    payload["has_real_data"] = False
    return payload


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
