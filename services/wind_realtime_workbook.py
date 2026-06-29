"""Wind realtime workbook snapshot reader and parser."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import time
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from openpyxl import Workbook, load_workbook

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
    "ViewRanges",
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
    "catalog_name",
    "wind_name_value",
    "last_value",
    "pct_change_value",
    "update_time_value",
    "is_concept",
    "source",
    "status",
]

HEALTH_HEADERS = ["metric", "value", "updated_at", "notes"]
VIEW_RANGE_HEADERS = [
    "view_key",
    "view_label",
    "snapshot_start_row",
    "row_count",
    "updated_at",
]
LOG_HEADERS = ["timestamp", "level", "component", "message", "details"]
ISO_NOW_FORMULA = '=TEXT(NOW(),"yyyy-mm-ddThh:mm:ss")'
MIN_ACTIVE_SLOT_COUNT = 360


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

        snapshot = self.load_view_snapshot(view_key)
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
                use_read_time_for_ok_rows=True,
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

    def load_view_snapshot(self, view_key: str) -> WorkbookSnapshot:
        """Read only the Snapshot rows for one market view when ViewRanges exists."""
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

            rows = self._read_view_rows(workbook, view_key)
            return parse_snapshot_rows(
                rows,
                stale_after_seconds=self.stale_after_seconds,
                use_read_time_for_ok_rows=True,
            )
        except Exception as exc:
            logger.error(
                "Failed to read Wind realtime workbook view %s from %s: %s",
                view_key,
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

    def _read_view_rows(self, workbook: Any, view_key: str) -> list[dict[str, Any]]:
        try:
            workbook.sheets["Snapshot"]
        except Exception:
            pass
        else:
            return self._read_snapshot_view_rows(workbook, view_key)

        try:
            workbook.sheets["ActiveSnapshot"]
        except Exception:
            pass
        else:
            return self._read_active_view_rows(workbook, view_key)

        return []

    def _read_snapshot_view_rows(self, workbook: Any, view_key: str) -> list[dict[str, Any]]:
        try:
            range_rows = _rows_from_matrix(workbook.sheets["ViewRanges"].used_range.value)
            view_range = next(
                (
                    row
                    for row in range_rows
                    if str(row.get("view_key") or "").strip() == view_key
                ),
                None,
            )
            if not view_range:
                return []

            start_row = int(float(view_range.get("snapshot_start_row") or 0))
            row_count = int(float(view_range.get("row_count") or 0))
            if start_row < 2 or row_count <= 0:
                return []

            headers = workbook.sheets["Snapshot"].range(
                (1, 1),
                (1, len(SNAPSHOT_HEADERS)),
            ).value
            raw_values = workbook.sheets["Snapshot"].range(
                (start_row, 1),
                (start_row + row_count - 1, len(SNAPSHOT_HEADERS)),
            ).value
            matrix = _matrix_rows(raw_values)
            return _rows_from_matrix([headers] + matrix)
        except Exception as exc:
            logger.warning(
                "Failed to read Wind view range %s, falling back to full Snapshot: %s",
                view_key,
                exc,
            )
            return self._rows_from_matrix(workbook.sheets["Snapshot"].used_range.value)

    def _read_active_view_rows(self, workbook: Any, view_key: str) -> list[dict[str, Any]]:
        slot_count = self._active_slot_count(workbook)
        self._activate_view(workbook, view_key, slot_count)
        headers = workbook.sheets["ActiveSnapshot"].range(
            (1, 1),
            (1, len(SNAPSHOT_HEADERS)),
        ).value
        raw_values = workbook.sheets["ActiveSnapshot"].range(
            (2, 1),
            (slot_count + 1, len(SNAPSHOT_HEADERS)),
        ).value
        return [
            row
            for row in _rows_from_matrix([headers] + _matrix_rows(raw_values))
            if str(row.get("wind_code") or "").strip()
        ]

    def _activate_view(self, workbook: Any, view_key: str, slot_count: int) -> None:
        config_sheet = workbook.sheets["Config"]
        active_sheet = workbook.sheets["ActiveRaw"]
        current_view = str(config_sheet.range("B8").value or "").strip()
        first_active_code = str(active_sheet.range("D2").value or "").strip()
        if current_view == view_key and first_active_code:
            return

        entries = [entry for entry in load_wind_index_catalog() if entry.view_key == view_key]
        if len(entries) > slot_count:
            logger.warning(
                "Wind realtime workbook active slots truncated: view=%s entries=%s slots=%s",
                view_key,
                len(entries),
                slot_count,
            )
        selected = entries[:slot_count]
        rows = [
            [
                entry.view_key,
                entry.view_label,
                entry.code,
                entry.name,
                str(entry.is_concept).lower(),
                "wind",
            ]
            for entry in selected
        ]
        rows.extend([["", "", "", "", "", ""] for _ in range(slot_count - len(rows))])
        config_sheet.range("B8").value = view_key
        active_sheet.range((2, 2), (slot_count + 1, 5)).value = [
            row[:4] for row in rows
        ]
        active_sheet.range((2, 12), (slot_count + 1, 13)).value = [
            row[4:] for row in rows
        ]

    @staticmethod
    def _active_slot_count(workbook: Any) -> int:
        try:
            rows = _rows_from_matrix(workbook.sheets["Health"].used_range.value)
            for row in rows:
                if str(row.get("metric") or "") == "active_slot_count":
                    return max(1, int(float(row.get("value") or MIN_ACTIVE_SLOT_COUNT)))
        except Exception:
            pass
        return MIN_ACTIVE_SLOT_COUNT


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


def _matrix_rows(values: Any) -> list[list[Any]]:
    if values is None:
        return []
    matrix = values if isinstance(values, (list, tuple)) else [[values]]
    if matrix and not isinstance(matrix[0], (list, tuple)):
        matrix = [matrix]
    return [list(row) if isinstance(row, (list, tuple)) else [row] for row in matrix]


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
        sheets["ViewRanges"].append(VIEW_RANGE_HEADERS)
        sheets["Health"].append(HEALTH_HEADERS)
        sheets["FormulaLog"].append(LOG_HEADERS)

        active_count = 0
        view_ranges: dict[str, dict[str, Any]] = {}
        view_counts: dict[str, int] = {}
        active_entries_by_view: dict[str, list[Any]] = {}
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

            active_count += 1
            active_entries_by_view.setdefault(entry.view_key, []).append(entry)
            current_view_count = view_counts.get(entry.view_key, 0) + 1
            view_counts[entry.view_key] = current_view_count
            view_ranges.setdefault(
                entry.view_key,
                {
                    "view_key": entry.view_key,
                    "view_label": entry.view_label,
                    "snapshot_start_row": active_count + 1,
                    "row_count": 0,
                },
            )
            view_ranges[entry.view_key]["row_count"] = current_view_count
            row_number = active_count + 1
            sheets["RealtimeRaw"].append(
                [
                    active_count,
                    entry.view_key,
                    entry.view_label,
                    entry.code,
                    entry.name,
                    "",
                    "",
                    "",
                    ISO_NOW_FORMULA,
                    str(entry.is_concept).lower(),
                    "wind",
                    (
                        f'=IF(OR(ISERROR(G{row_number}),'
                        f'ISERROR(H{row_number}),G{row_number}="",'
                        f'H{row_number}=""),"formula_error","ok")'
                    ),
                ]
            )
            sheets["Snapshot"].append(
                [
                    f"=RealtimeRaw!B{row_number}",
                    f"=RealtimeRaw!C{row_number}",
                    f"=RealtimeRaw!D{row_number}",
                    f'=IF(RealtimeRaw!F{row_number}="",RealtimeRaw!E{row_number},RealtimeRaw!F{row_number})',
                    f"=RealtimeRaw!G{row_number}",
                    f"=RealtimeRaw!H{row_number}",
                    f"=RealtimeRaw!J{row_number}",
                    f"=RealtimeRaw!K{row_number}",
                    f"=RealtimeRaw!I{row_number}",
                    f"=RealtimeRaw!L{row_number}",
                ]
            )

        for view_range in view_ranges.values():
            sheets["ViewRanges"].append(
                [
                    view_range["view_key"],
                    view_range["view_label"],
                    view_range["snapshot_start_row"],
                    view_range["row_count"],
                    generated_at,
                ]
            )
            first_row = int(view_range["snapshot_start_row"])
            view_entries = active_entries_by_view.get(str(view_range["view_key"]), [])
            codes = ",".join(entry.code for entry in view_entries)
            row_count = int(view_range["row_count"])
            if codes and row_count > 0:
                sheets["RealtimeRaw"].cell(row=first_row, column=6).value = (
                    f'=wss("{codes}","sec_name,rt_last,rt_pct_chg",'
                    f'"cols=3;rows={row_count}")'
                )

        sheets["Health"].append(["workbook_open", "true", generated_at, "文件已生成"])
        sheets["Health"].append(
            ["active_index_count", active_count, generated_at, "active 指数数量"]
        )
        sheets["Health"].append(
            ["formula_row_count", active_count, generated_at, "常驻公式行数"]
        )
        sheets["Health"].append(
            [
                "wind_formula_count",
                len(view_ranges),
                generated_at,
                "批量 Wind 公式数量，每个口径一条",
            ]
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


def prime_realtime_workbook_formulas(
    workbook_path: str | Path | None = None,
    *,
    chunk_size: int = 1,
    pause_seconds: float = 1.0,
    visible: bool = False,
    save: bool = True,
) -> int:
    """Rewrite batch Wind formulas through Excel so the Wind add-in owns refresh."""
    path = resolve_workbook_path(workbook_path).expanduser().resolve()
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")
    if not path.exists():
        raise FileNotFoundError(f"Wind realtime workbook does not exist: {path}")

    formulas = _load_batch_formula_rows(path)
    if not formulas:
        logger.warning("No Wind batch formulas to prime: %s", path)
        return 0

    try:
        import xlwings as xw
    except ImportError as exc:
        raise RuntimeError("xlwings is required to prime Wind formulas") from exc

    app = xw.apps.active or xw.App(visible=visible)
    try:
        app.visible = visible
    except Exception as exc:
        logger.debug("Unable to set Excel visibility to %s: %s", visible, exc)

    book = _find_or_open_xlwings_book(xw, path, read_only=False)
    raw = book.sheets["RealtimeRaw"]
    for index in range(0, len(formulas), chunk_size):
        batch = formulas[index : index + chunk_size]
        for row_number, formula in batch:
            raw.range((row_number, 6)).formula = formula
            logger.info("Primed Wind batch formula row %s", row_number)
        if pause_seconds:
            time.sleep(pause_seconds)

    book.app.calculate()
    time.sleep(10)
    if save:
        book.save()
    logger.info("Primed Wind realtime workbook: %s", path)
    return len(formulas)


def _load_batch_formula_rows(path: Path) -> list[tuple[int, str]]:
    workbook = load_workbook(path, data_only=False, read_only=True)
    raw_data = workbook["RealtimeRaw"]
    formulas: list[tuple[int, str]] = []
    for row in workbook["ViewRanges"].iter_rows(min_row=2, values_only=True):
        view_key, _view_label, start_row, row_count, _updated_at = row
        if not view_key or not start_row or not row_count:
            continue
        formula = raw_data.cell(row=int(start_row), column=6).value
        if formula:
            formulas.append((int(start_row), str(formula)))
    return formulas


def _find_or_open_xlwings_book(xw: Any, path: Path, *, read_only: bool) -> Any:
    for app in xw.apps:
        for candidate in app.books:
            fullname = str(getattr(candidate, "fullname", "") or "")
            if not fullname:
                continue
            try:
                if Path(fullname).expanduser().resolve() == path:
                    return candidate
            except OSError:
                if Path(fullname).expanduser() == path:
                    return candidate

    app = xw.apps.active or xw.App(visible=False)
    return app.books.open(str(path), update_links=False, read_only=read_only)


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
    use_read_time_for_ok_rows: bool = False,
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
            updated_at = (
                reference_time
                if use_read_time_for_ok_rows and status == "ok"
                else _parse_datetime(row.get("updated_at"))
            )
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
