"""Wind realtime workbook snapshot reader and parser."""

from __future__ import annotations

import math
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from openpyxl import Workbook, load_workbook

from core.observability import get_logger
from core.settings.paths import default_wind_workbook_path
from services.wind_index_catalog import MARKET_VIEW_LABELS, load_wind_index_catalog

logger = get_logger(__name__)
SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")

DEFAULT_WORKBOOK_PATH = default_wind_workbook_path()
"""Wind 实时工作簿默认路径（跨平台，导入时按当前平台解析）。

可被环境变量 ``ALPHAFOUNDRY_WIND_WORKBOOK_PATH`` 覆盖，详见
:func:`resolve_workbook_path`。保留为模块级常量以兼容历史导入
（``wind_workbook_manager`` 与 ``scripts/prime_wind_realtime_workbook``）。
"""

# 工作簿路径环境变量覆盖
WIND_WORKBOOK_PATH_ENV = "ALPHAFOUNDRY_WIND_WORKBOOK_PATH"

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
WIND_WSS_FORMULA_BATCH_SIZE = 25


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
                (row for row in range_rows if str(row.get("view_key") or "").strip() == view_key),
                None,
            )
            if not view_range:
                return []

            start_row = int(float(view_range.get("snapshot_start_row") or 0))
            row_count = int(float(view_range.get("row_count") or 0))
            if start_row < 2 or row_count <= 0:
                return []

            headers = (
                workbook.sheets["Snapshot"]
                .range(
                    (1, 1),
                    (1, len(SNAPSHOT_HEADERS)),
                )
                .value
            )
            raw_values = (
                workbook.sheets["Snapshot"]
                .range(
                    (start_row, 1),
                    (start_row + row_count - 1, len(SNAPSHOT_HEADERS)),
                )
                .value
            )
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
        headers = (
            workbook.sheets["ActiveSnapshot"]
            .range(
                (1, 1),
                (1, len(SNAPSHOT_HEADERS)),
            )
            .value
        )
        raw_values = (
            workbook.sheets["ActiveSnapshot"]
            .range(
                (2, 1),
                (slot_count + 1, len(SNAPSHOT_HEADERS)),
            )
            .value
        )
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
        active_sheet.range((2, 2), (slot_count + 1, 5)).value = [row[:4] for row in rows]
        active_sheet.range((2, 12), (slot_count + 1, 13)).value = [row[4:] for row in rows]

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
    """解析 Wind 实时工作簿路径。

    优先级：
        1. 显式参数 ``path``（非空）
        2. 环境变量 ``ALPHAFOUNDRY_WIND_WORKBOOK_PATH``
        3. 当前平台规范默认路径（见 :func:`core.settings.paths.default_wind_workbook_path`）
    """
    if path is not None and str(path).strip() != "":
        return Path(path).expanduser()
    env_path = os.environ.get(WIND_WORKBOOK_PATH_ENV)
    if env_path and env_path.strip():
        return Path(env_path).expanduser()
    return DEFAULT_WORKBOOK_PATH


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
        sheets["Config"].append(["expected_update_seconds", "60", "超过该秒数视为数据可能过期"])
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
        active_rows_by_view: dict[str, list[tuple[Any, int]]] = {}
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
            active_rows_by_view.setdefault(entry.view_key, []).append((entry, row_number))
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
                        f"=IF(OR(ISERROR(G{row_number}),"
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

        wind_formula_count = 0
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
            view_rows = active_rows_by_view.get(str(view_range["view_key"]), [])
            for offset in range(0, len(view_rows), WIND_WSS_FORMULA_BATCH_SIZE):
                batch = view_rows[offset : offset + WIND_WSS_FORMULA_BATCH_SIZE]
                if not batch:
                    continue
                first_row = batch[0][1]
                codes = ",".join(entry.code for entry, _row_number in batch)
                row_count = len(batch)
                # Use =wss() without the @ dynamic-array prefix.
                # The @-prefix triggers Excel's dynamic-array spill engine,
                # which the Wind WDF.Addin blocks when Excel is driven via
                # COM automation (raises 0x800A03EC).  The plain =wss() with
                # cols/rows parameters writes into the pre-allocated slot range
                # and works correctly in both interactive and COM sessions.
                sheets["RealtimeRaw"].cell(row=first_row, column=6).value = (
                    f'=wss("{codes}","sec_name,rt_last,rt_pct_chg",' f'"cols=3;rows={row_count}")'
                )
                wind_formula_count += 1

        sheets["Health"].append(["workbook_open", "true", generated_at, "文件已生成"])
        sheets["Health"].append(["active_index_count", active_count, generated_at, "active 指数数量"])
        sheets["Health"].append(["formula_row_count", active_count, generated_at, "常驻公式行数"])
        sheets["Health"].append(
            [
                "wind_formula_count",
                wind_formula_count,
                generated_at,
                "批量 Wind 公式数量，每个口径可按代码数量拆分多条",
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

    expected_health_metrics = _load_workbook_health_metrics(path)
    book = _find_or_open_xlwings_book(
        xw,
        path,
        read_only=False,
        expected_health_metrics=expected_health_metrics,
    )
    raw = book.sheets["RealtimeRaw"]
    primed_count = 0
    # Maximum seconds to poll for Wind to fill G-column (rt_last) after writing a formula.
    # 500-code batches can take up to ~90s; we poll in 5s ticks and give up gracefully.
    _POLL_INTERVAL = 5.0
    _POLL_MAX_SECONDS = 120.0
    # Retry budget for COM-busy errors when writing a formula.
    _MAX_WRITE_RETRIES = 10
    _RETRY_PAUSE = 10.0

    for index in range(0, len(formulas), chunk_size):
        batch = formulas[index : index + chunk_size]
        for row_number, formula in batch:
            # ── Write the formula (with COM-busy retries) ──────────────────────
            wrote_ok = False
            for attempt in range(_MAX_WRITE_RETRIES):
                try:
                    raw.range((row_number, 6)).formula = formula
                    wrote_ok = True
                    break
                except Exception as exc:
                    if attempt < _MAX_WRITE_RETRIES - 1:
                        logger.info(
                            "Wind formula write busy, retrying in %.0fs: row=%s attempt=%s/%s error=%s",
                            _RETRY_PAUSE,
                            row_number,
                            attempt + 1,
                            _MAX_WRITE_RETRIES,
                            exc,
                        )
                        time.sleep(_RETRY_PAUSE)
                    else:
                        logger.warning(
                            "Wind formula priming stopped because Excel is busy after %s retries: "
                            "primed=%s total=%s row=%s error=%s",
                            _MAX_WRITE_RETRIES,
                            primed_count,
                            len(formulas),
                            row_number,
                            exc,
                        )
                        return primed_count
            if not wrote_ok:
                continue

            primed_count += 1
            logger.info("Primed Wind batch formula row %s", row_number)

            # ── Poll until Wind fills the G-column (rt_last / col 7) ─────────
            # The Wind WDF.Addin holds a COM re-entry lock while it fetches data
            # for the current =wss() batch.  We must wait for it to finish before
            # writing the next formula, otherwise the next write raises 0x800A03EC.
            # Polling on G (rt_last) is more reliable than a fixed sleep because
            # the actual fetch time depends on the number of codes in the batch
            # and the Wind server's response time (typically 10–90 s for 500 codes).
            t_write = time.monotonic()
            got_data = False
            while time.monotonic() - t_write < _POLL_MAX_SECONDS:
                try:
                    g_val = raw.range((row_number, 7)).value
                    if g_val is not None and g_val != "":
                        try:
                            if float(g_val) > 0:
                                got_data = True
                                break
                        except (TypeError, ValueError):
                            pass
                except Exception:
                    pass
                time.sleep(_POLL_INTERVAL)

            elapsed = time.monotonic() - t_write
            if got_data:
                logger.info(
                    "Wind batch formula computed: row=%s elapsed=%.0fs G=%s",
                    row_number,
                    elapsed,
                    raw.range((row_number, 7)).value,
                )
            else:
                logger.warning(
                    "Wind batch formula did not fill G-column in %.0fs: row=%s — continuing anyway",
                    _POLL_MAX_SECONDS,
                    row_number,
                )

    try:
        book.app.calculate()
    except Exception as exc:
        logger.warning("Unable to force Wind workbook calculation after priming: %s", exc)
    time.sleep(10)
    if save:
        try:
            book.save()
        except Exception as exc:
            logger.warning("Unable to save Wind workbook after priming: %s", exc)
    logger.info("Primed Wind realtime workbook: %s", path)
    return primed_count


def _load_batch_formula_rows(path: Path) -> list[tuple[int, str]]:
    workbook = load_workbook(path, data_only=False, read_only=True)
    raw_data = workbook["RealtimeRaw"]
    formulas: list[tuple[int, str]] = []
    for row in raw_data.iter_rows(min_row=2, min_col=6, max_col=6):
        cell = row[0]
        formula = cell.value
        if not formula:
            continue
        formula_text = str(formula)
        normalized = formula_text.lower()
        if normalized.startswith("=wss(") or normalized.startswith("=@wss("):
            formulas.append((int(cell.row), formula_text))
    return formulas


def _find_or_open_xlwings_book(
    xw: Any,
    path: Path,
    *,
    read_only: bool,
    expected_health_metrics: dict[str, str] | None = None,
) -> Any:
    for app in xw.apps:
        for candidate in app.books:
            fullname = str(getattr(candidate, "fullname", "") or "")
            if not fullname:
                continue
            try:
                if Path(fullname).expanduser().resolve() == path:
                    if not _open_workbook_health_matches(
                        candidate,
                        expected_health_metrics,
                    ):
                        _close_stale_xlwings_book(candidate)
                        continue
                    return candidate
            except OSError:
                if Path(fullname).expanduser() == path:
                    if not _open_workbook_health_matches(
                        candidate,
                        expected_health_metrics,
                    ):
                        _close_stale_xlwings_book(candidate)
                        continue
                    return candidate

    app = xw.apps.active or xw.App(visible=False)
    try:
        app.display_alerts = False
    except Exception as exc:
        logger.debug("Unable to suppress Excel alerts: %s", exc)
    # xlRepairFile=2 suppresses the Excel 16 "repair/Protected View" COM dialog
    # that otherwise blocks Workbooks.Open in headless COM sessions (0x800A03EC).
    XL_REPAIR_FILE = 2
    try:
        raw_wb = app.api.Workbooks.Open(
            str(path),
            UpdateLinks=0,
            ReadOnly=read_only,
            CorruptLoad=XL_REPAIR_FILE,
        )
        return xw.Book(raw_wb.FullName)
    except Exception as exc:
        logger.debug(
            "COM open with CorruptLoad failed (%s); falling back to xlwings books.open", exc
        )
        return app.books.open(str(path), update_links=False, read_only=read_only)


def _load_workbook_health_metrics(path: Path) -> dict[str, str]:
    try:
        workbook = load_workbook(path, data_only=False, read_only=True)
        rows = _rows_from_matrix(list(workbook["Health"].iter_rows(values_only=True)))
    except Exception as exc:
        logger.debug("Unable to load Wind workbook health metrics from %s: %s", path, exc)
        return {}
    return _health_metrics_from_rows(rows)


def _open_workbook_health_matches(
    book: Any,
    expected_health_metrics: dict[str, str] | None,
) -> bool:
    if not expected_health_metrics:
        return True
    try:
        actual = _health_metrics_from_rows(
            _rows_from_matrix(book.sheets["Health"].used_range.value)
        )
    except Exception as exc:
        logger.debug("Unable to inspect open Wind workbook health: %s", exc)
        return False

    for key in ("active_index_count", "formula_row_count", "wind_formula_count"):
        expected = expected_health_metrics.get(key)
        if expected is not None and actual.get(key) != expected:
            logger.info(
                "Open Wind workbook health metric changed: metric=%s expected=%s actual=%s",
                key,
                expected,
                actual.get(key),
            )
            return False
    return True


def _health_metrics_from_rows(rows: list[dict[str, Any]]) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for row in rows:
        metric = str(row.get("metric") or "").strip()
        if not metric:
            continue
        value = row.get("value")
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        metrics[metric] = str(value)
    return metrics


def _close_stale_xlwings_book(book: Any) -> None:
    try:
        book.close()
    except Exception as exc:
        logger.debug("Unable to close stale open Wind workbook: %s", exc)


def payload_from_snapshot(
    snapshot: WorkbookSnapshot,
    *,
    view_key: str,
    limit: int,
    view_label: str,
    cache_ttl_seconds: int = 60,
) -> dict[str, Any]:
    rows = [row for row in snapshot.rows if row.view_key == view_key]
    active_codes = _active_catalog_codes_for_view(view_key)
    catalog_filtered_count = 0
    if active_codes:
        unfiltered_count = len(rows)
        rows = [row for row in rows if row.wind_code.strip().upper() in active_codes]
        catalog_filtered_count = unfiltered_count - len(rows)
    up, down = split_snapshot_movers(rows, limit=limit)
    has_real_data = bool(rows)
    cache_hit = has_real_data and snapshot.status in {"ok", "snapshot_stale"}

    payload = {
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
    if catalog_filtered_count:
        payload["catalog_filtered_count"] = catalog_filtered_count
    return payload


def _active_catalog_codes_for_view(view_key: str) -> set[str]:
    try:
        return {
            entry.code.strip().upper()
            for entry in load_wind_index_catalog()
            if entry.view_key == view_key and entry.is_active
        }
    except Exception as exc:
        logger.debug("Unable to load active Wind catalog codes for %s: %s", view_key, exc)
        return set()


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
            if _is_wind_placeholder_text(name):
                error_count += 1
                logger.warning("Skipping Wind placeholder snapshot row: %s", row)
                continue
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
        message = "Wind快照暂无数据，请确认Wind插件已登录"

    return WorkbookSnapshot(
        rows=tuple(parsed_rows),
        status=status,
        is_stale=is_stale,
        updated_at=updated_at,
        error_count=error_count,
        message=message,
    )


def _is_wind_placeholder_text(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized in {
        "fetching",
        "fetching...",
        "loading",
        "loading...",
        "nan",
        "#n/a",
        "#value!",
    }


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
        "name": _format_index_display_name(row.name),
        "change_pct": round(row.pct_change, 2),
        "leading_stocks": [],
        "related_news_count": 0,
        "is_concept": row.is_concept,
        "source": row.source,
        "view_key": row.view_key,
        "view_label": row.view_label,
    }


def _format_index_display_name(name: str) -> str:
    stripped = str(name or "").strip()
    return stripped.removesuffix("指数")


def _parse_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    if not isinstance(value, (str, int, float, bytes)):
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
