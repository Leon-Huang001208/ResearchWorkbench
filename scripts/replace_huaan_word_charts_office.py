"""Replace Huaan weekly report chart images using native Excel -> Word paste.

This script intentionally drives Microsoft Excel and Microsoft Word instead of
editing the docx zip package. Office creates the chart parts and relationships,
which is much safer than hand-writing OOXML chart relationships.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from core.observability import get_logger

    logger = get_logger(__name__)
except Exception:  # pragma: no cover - repair script should run outside app env.
    import logging

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    logger = logging.getLogger(__name__)

WORD_TEMPLATE = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "templates" / "report_template.docx"
CHART_WORKBOOK = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "data" / "周报图表.xlsx"
BACKUP_DIR = PROJECT_ROOT / "report_projects" / "华安ETF周报" / "templates" / "backups"

CHART_REPLACEMENTS = [
    {
        "word_inline_shape_index": 3,
        "excel_sheet": "期货结算价(连续)_布伦特原油",
        "excel_chart": "图表 1",
        "label": "crude_oil_price",
    },
    {
        "word_inline_shape_index": 2,
        "excel_sheet": "伦敦金_Au9999",
        "excel_chart": "图表 2",
        "label": "gold_price",
    },
    {
        "word_inline_shape_index": 1,
        "excel_sheet": "申万一级行业指数",
        "excel_chart": "图表 2",
        "label": "industry_weekly_performance",
    },
]


def _run_osascript(script: str, timeout: int = 60) -> str:
    result = subprocess.run(
        ["osascript"],
        input=script,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"osascript failed ({result.returncode}): {result.stderr.strip()}")
    return result.stdout.strip()


def _apple_quote(value: Path | str) -> str:
    text = str(value)
    return text.replace("\\", "\\\\").replace('"', '\\"')


def _wait_for_word_document(path: Path) -> None:
    """Grant file access when Word asks for macOS sandbox permission."""
    target = _apple_quote(path)
    script = f"""
tell application "System Events"
    if exists process "Microsoft Word" then
        tell process "Microsoft Word"
            set frontmost to true
            repeat 4 times
                if exists window "Grant File Access" then
                    click button "Select..." of window "Grant File Access"
                    delay 0.5
                    keystroke "g" using {{command down, shift down}}
                    delay 0.2
                    keystroke "{target}"
                    delay 0.2
                    key code 36
                    delay 0.5
                    key code 36
                    delay 1
                end if
            end repeat
        end tell
    end if
end tell
"""
    _run_osascript(script, timeout=20)


def _open_word_document(path: Path) -> None:
    script = f"""
set docAlias to POSIX file "{_apple_quote(path)}" as alias
tell application "Microsoft Word"
    activate
    open docAlias
    delay 4
end tell
"""
    _run_osascript(script, timeout=30)
    _wait_for_word_document(path)
    opened = _run_osascript(
        """
tell application "Microsoft Word"
    if (count of documents) = 0 then
        return "documents=0"
    end if
    return "documents=" & (count of documents) & ", inline=" & (count of inline shapes of active document)
end tell
""",
        timeout=20,
    )
    if "documents=0" in opened:
        raise RuntimeError(f"Word did not open document: {path}")
    logger.info("Opened Word document", status=opened)


def _open_excel_workbook(path: Path) -> None:
    script = f"""
tell application "Microsoft Excel"
    activate
    open workbook workbook file name "{_apple_quote(path)}"
    delay 2
end tell
"""
    try:
        _run_osascript(script, timeout=20)
    except RuntimeError:
        # Excel returns parameter errors when the workbook is already open in
        # some Mac builds. In that case xlwings/Excel state is still usable.
        logger.info("Excel workbook may already be open", workbook=str(path))


def _replace_one_chart(index: int, sheet: str, chart: str, label: str) -> None:
    logger.info(
        "Replacing Word chart image through Office clipboard",
        label=label,
        sheet=sheet,
        chart=chart,
        inline_shape_index=index,
    )
    script = f"""
tell application "Microsoft Excel"
    activate
    set wb to active workbook
    activate object worksheet "{sheet}" of wb
    delay 0.5
    select chart object "{chart}" of worksheet "{sheet}" of wb
end tell
delay 0.5
tell application "System Events"
    tell process "Microsoft Excel"
        keystroke "c" using {{command down}}
    end tell
end tell
delay 1
tell application "Microsoft Word"
    activate
    select inline shape {index} of active document
end tell
delay 0.5
tell application "System Events"
    tell process "Microsoft Word"
        key code 51
        delay 0.5
        keystroke "v" using {{command down}}
    end tell
end tell
delay 2
tell application "Microsoft Word"
    return "inline=" & (count of inline shapes of active document) & ", shapes=" & (count of shapes of active document)
end tell
"""
    status = _run_osascript(script, timeout=30)
    logger.info("Replaced chart", label=label, status=status)


def replace_charts_with_office(
    source_docx: Path = WORD_TEMPLATE,
    output_docx: Path | None = None,
    workbook: Path = CHART_WORKBOOK,
) -> Path:
    """Create a Word document whose chart placeholders are native Office charts."""
    source_docx = source_docx.resolve()
    workbook = workbook.resolve()
    if not source_docx.exists():
        raise FileNotFoundError(source_docx)
    if not workbook.exists():
        raise FileNotFoundError(workbook)

    if output_docx is None:
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        backup = BACKUP_DIR / f"{source_docx.stem}.before_office_chart_paste{source_docx.suffix}"
        if not backup.exists():
            shutil.copy2(source_docx, backup)
            logger.info("Backed up Word template", backup=str(backup))
        output_docx = source_docx
    else:
        output_docx = output_docx.resolve()
        shutil.copy2(source_docx, output_docx)

    _open_excel_workbook(workbook)
    _open_word_document(output_docx)
    for item in CHART_REPLACEMENTS:
        _replace_one_chart(
            index=int(item["word_inline_shape_index"]),
            sheet=str(item["excel_sheet"]),
            chart=str(item["excel_chart"]),
            label=str(item["label"]),
        )
    _run_osascript(
        """
tell application "Microsoft Word"
    save active document
    set docName to name of active document
    close active document saving no
    return docName
end tell
""",
        timeout=30,
    )
    time.sleep(1)
    logger.info("Saved Word document with native charts", docx=str(output_docx))
    return output_docx


if __name__ == "__main__":
    target = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else None
    result = replace_charts_with_office(output_docx=target)
    print(result)
