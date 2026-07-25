"""Refresh the Huaan ETF gap report through Excel + Wind add-in.

This script intentionally uses Excel/xlwings. It does not call Wind MCP or
network APIs directly; all Wind data is refreshed by formulas inside Excel.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.observability import get_logger  # noqa: E402

logger = get_logger(__name__)

DEFAULT_WORKBOOK = (
    PROJECT_ROOT / "outputs" / "etf_gap_report_20260702" / "华安基金ETF缺口_Wind插件公式版_近五年PE分位.xlsx"
)


def _close_without_saving(book: Any) -> None:
    try:
        book.api.Close(SaveChanges=False)
    except Exception:
        book.close()


def _connect_excel(visible: bool):
    try:
        import xlwings as xw
    except Exception as exc:
        raise RuntimeError("xlwings is required; run with Anaconda Python") from exc

    apps = list(xw.apps)
    if apps:
        app = apps[0]
        logger.info("Connected to running Excel", pid=app.pid)
    else:
        app = xw.App(visible=visible, add_book=False)
        logger.info("Started Excel", pid=app.pid)
    try:
        app.visible = visible
    except Exception as exc:
        logger.debug("Unable to set Excel visibility", error=str(exc))
    return xw, app


def _open_or_get_workbook(app: Any, workbook_path: Path, *, reopen: bool):
    target = workbook_path.expanduser().resolve()
    for book in app.books:
        fullname = str(getattr(book, "fullname", "") or "")
        if not fullname:
            continue
        try:
            if Path(fullname).expanduser().resolve() == target:
                if reopen:
                    logger.info(
                        "Closing open workbook before reopening from disk", workbook=book.name
                    )
                    _close_without_saving(book)
                    break
                logger.info("Using already open workbook", workbook=book.name)
                return book
        except Exception:
            if Path(fullname).expanduser() == target:
                if reopen:
                    logger.info(
                        "Closing open workbook before reopening from disk", workbook=book.name
                    )
                    _close_without_saving(book)
                    break
                logger.info("Using already open workbook", workbook=book.name)
                return book

    book = app.books.open(
        str(target),
        update_links=False,
        read_only=False,
        ignore_read_only_recommended=True,
        add_to_mru=False,
    )
    logger.info("Opened workbook", workbook=book.name)
    return book


def _cell_value(sheet: Any, address: str) -> Any:
    try:
        return sheet.range(address).api.Value2
    except Exception as exc:
        logger.debug("Unable to read cell", sheet=sheet.name, address=address, error=str(exc))
        return None


def _numeric(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value)
    except Exception:
        return None


def _status(book: Any) -> dict[str, Any]:
    summary = book.sheets["Summary"]
    raw = book.sheets["Raw ETF + Wind"]
    coverage = book.sheets["Index Coverage"]
    return {
        "candidate_count": _cell_value(summary, "B7"),
        "pe_available_count": _cell_value(summary, "D7"),
        "raw_first_index_code": _cell_value(raw, "M2"),
        "raw_first_status": _cell_value(raw, "P2"),
        "coverage_first_index_code": _cell_value(coverage, "A2"),
        "coverage_first_pe_percentile": _cell_value(coverage, "J2"),
        "coverage_first_status": _cell_value(coverage, "M2"),
    }


def _calculate(app: Any, book: Any) -> None:
    try:
        app.calculate()
        return
    except Exception as exc:
        logger.warning("app.calculate failed; trying workbook API", error=str(exc))
    try:
        book.api.Application.CalculateFullRebuild()
    except Exception as exc:
        logger.warning("CalculateFullRebuild failed", error=str(exc))


def refresh_workbook(
    workbook_path: Path,
    *,
    visible: bool,
    max_wait_seconds: int,
    poll_seconds: int,
    save: bool,
    reopen: bool,
) -> dict[str, Any]:
    _xw, app = _connect_excel(visible=visible)
    book = _open_or_get_workbook(app, workbook_path, reopen=reopen)

    logger.info("Starting Excel calculation", workbook=book.name)
    _calculate(app, book)

    started = time.monotonic()
    last_status: dict[str, Any] = {}
    while True:
        elapsed = time.monotonic() - started
        last_status = _status(book)
        logger.info("Refresh status", elapsed_seconds=round(elapsed, 1), **last_status)

        raw_ready = (
            bool(last_status.get("raw_first_index_code"))
            and last_status.get("raw_first_status") == "ok"
        )
        pe_ready = (_numeric(last_status.get("pe_available_count")) or 0) > 0
        candidate_ready = last_status.get("candidate_count") is not None
        if raw_ready and pe_ready and candidate_ready:
            break
        if elapsed >= max_wait_seconds:
            logger.warning("Timed out waiting for Wind formulas", max_wait_seconds=max_wait_seconds)
            break
        time.sleep(max(1, poll_seconds))
        _calculate(app, book)

    if save:
        logger.info("Saving workbook", workbook=book.name)
        book.save()
    return last_status


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh ETF gap report via Excel Wind add-in.")
    parser.add_argument("--workbook", type=Path, default=DEFAULT_WORKBOOK)
    parser.add_argument("--visible", action="store_true", help="Show Excel while refreshing.")
    parser.add_argument("--max-wait", type=int, default=900, help="Maximum seconds to wait.")
    parser.add_argument("--poll", type=int, default=30, help="Polling interval in seconds.")
    parser.add_argument("--no-save", action="store_true", help="Do not save after refreshing.")
    parser.add_argument(
        "--reopen", action="store_true", help="Close an open copy and reopen from disk first."
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    workbook_path = args.workbook.expanduser().resolve()
    if not workbook_path.exists():
        raise FileNotFoundError(workbook_path)
    status = refresh_workbook(
        workbook_path,
        visible=args.visible,
        max_wait_seconds=args.max_wait,
        poll_seconds=args.poll,
        save=not args.no_save,
        reopen=args.reopen,
    )
    print(json.dumps(status, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
