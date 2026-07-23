"""Update Huaan ETF weekly chart workbook through Microsoft Excel.

This script intentionally uses Excel/xlwings instead of editing the xlsx zip
package directly. Excel is stricter than openpyxl about chart XML, so chart
source changes should be saved by Excel itself.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.observability import get_logger  # noqa: E402

logger = get_logger(__name__)

WORKBOOK_PATH = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "data" / "周报图表.xlsx"
BACKUP_DIR = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "data" / "backups"


def _connect_excel():
    try:
        import xlwings as xw
    except Exception as exc:  # pragma: no cover - environment dependent
        raise RuntimeError("xlwings is required for Excel-native workbook updates") from exc

    apps = list(xw.apps)
    if apps:
        app = apps[0]
        owns_app = False
        logger.info("Connected to running Excel", pid=app.pid)
    else:
        app = xw.App(visible=True, add_book=False)
        owns_app = True
        logger.info("Started Excel", pid=app.pid)
    return xw, app, owns_app


def _open_or_get_workbook(app, workbook_path: Path):
    target = str(workbook_path.resolve())
    for book in app.books:
        if str(Path(book.fullname).resolve()) == target:
            logger.info("Using already open workbook", workbook=book.name)
            return book, False
    book = app.books.open(
        target,
        update_links=False,
        read_only=False,
        ignore_read_only_recommended=True,
        add_to_mru=False,
    )
    logger.info("Opened workbook", workbook=book.name)
    return book, True


def _last_data_row(sheet, columns: Iterable[str]) -> int:
    last = 1
    for column in columns:
        row = sheet.range(f"{column}{sheet.cells.last_cell.row}").end("up").row
        last = max(last, int(row))
    return last


def _set_series_formulas(chart, formulas: list[str]) -> None:
    series_items = chart.api[1].series_collection()
    if len(series_items) < len(formulas):
        raise RuntimeError(
            f"Chart {chart.name} has {len(series_items)} series, expected {len(formulas)}"
        )
    for series, formula in zip(series_items, formulas):
        logger.info("Updating chart series", chart=chart.name, formula=formula)
        series.formula.set(formula)


def _set_display_blanks_as_span(chart) -> None:
    # 3 = xlInterpolated / connect data points with line.
    chart.api[1].display_blanks_as.set(3)


def _update_gold_sheet(book) -> None:
    sheet = book.sheets["伦敦金_Au9999"]
    chart = sheet.charts[0]
    last_row = _last_data_row(sheet, ["A", "B", "C"])
    _set_series_formulas(
        chart,
        [
            f'=SERIES("伦敦金(美元/盎司)",伦敦金_Au9999!$A$3:$A${last_row},伦敦金_Au9999!$B$3:$B${last_row},1)',
            f'=SERIES("黄金Au9999(右, 元/克)",伦敦金_Au9999!$A$3:$A${last_row},伦敦金_Au9999!$C$3:$C${last_row},2)',
        ],
    )
    _set_display_blanks_as_span(chart)
    sheet.range("E:G").api.delete()
    chart.left = sheet.range("E4").left
    chart.top = sheet.range("E4").top
    logger.info("Updated gold chart sheet", sheet=sheet.name, last_row=last_row)


def _update_oil_sheet(book) -> None:
    sheet = book.sheets["期货结算价(连续)_布伦特原油"]
    chart = sheet.charts[0]
    last_row = _last_data_row(sheet, ["A", "B", "C"])
    quoted_sheet = "'期货结算价(连续)_布伦特原油'"
    _set_series_formulas(
        chart,
        [
            f'=SERIES("布伦特原油",{quoted_sheet}!$A$3:$A${last_row},{quoted_sheet}!$B$3:$B${last_row},1)',
            f'=SERIES("WTI原油",{quoted_sheet}!$A$3:$A${last_row},{quoted_sheet}!$C$3:$C${last_row},2)',
        ],
    )
    _set_display_blanks_as_span(chart)
    sheet.range("E:G").api.delete()
    chart.left = sheet.range("E4").left
    chart.top = sheet.range("E4").top
    logger.info("Updated oil chart sheet", sheet=sheet.name, last_row=last_row)


def update_huaan_chart_workbook(workbook_path: Path = WORKBOOK_PATH) -> Path:
    """Update chart sources and remove duplicate right-side data ranges."""
    workbook_path = workbook_path.resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    backup_path = BACKUP_DIR / f"{workbook_path.stem}.before_excel_update{workbook_path.suffix}"
    shutil.copy2(workbook_path, backup_path)
    logger.info("Backed up workbook", backup=str(backup_path))

    _xw, app, owns_app = _connect_excel()
    opened_by_script = False
    try:
        book, opened_by_script = _open_or_get_workbook(app, workbook_path)
        _update_gold_sheet(book)
        _update_oil_sheet(book)
        book.save(str(workbook_path))
        logger.info("Saved workbook through Excel", workbook=str(workbook_path))
        if opened_by_script:
            book.close()
    finally:
        if owns_app:
            app.quit()
    return backup_path


if __name__ == "__main__":
    backup = update_huaan_chart_workbook()
    print(f"updated: {WORKBOOK_PATH}")
    print(f"backup: {backup}")
