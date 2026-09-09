# Wind Realtime Workbook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Wind realtime workbook pipeline so market sector views read pre-refreshed Excel snapshots instead of writing hundreds of Wind formulas on user click.

**Architecture:** Keep `data_sources/wind_index_catalog.csv` as the versioned index catalog, generate a local `Research Workbench_Wind_Realtime.xlsx` workbook with formula and snapshot sheets, and add a backend reader that prefers workbook snapshots for Wind views. Existing Wind formula fetching remains as a fallback, while the frontend gets 60-second silent refresh for the active market view.

**Tech Stack:** Python 3.11, `openpyxl` for workbook generation/tests, `xlwings` for reading an already-open live Excel workbook, FastAPI dashboard routes, existing `DashboardService`, vanilla JS dashboard frontend.

---

## File Structure

- Create `services/wind_realtime_workbook.py`
  - Owns workbook path resolution, snapshot dataclasses, row parsing, live workbook reading, stale/error status mapping, and view payload generation.
- Create `scripts/build_wind_realtime_workbook.py`
  - CLI script that reads `data_sources/wind_index_catalog.csv` and writes the runtime workbook.
- Modify `services/wind_index_catalog.py`
  - Preserve existing catalog behavior and support the optional `notes` column.
- Modify `services/dashboard_service.py`
  - Prefer `WindRealtimeWorkbookReader.get_view()` for Wind-backed view keys, then fallback to `WindMarketOverviewProvider`.
- Modify `app/web/static/js/dashboard.js`
  - Add 60-second silent refresh for the active market sector view and surface workbook stale/error messages.
- Create `tests/unit/test_wind_realtime_workbook.py`
  - Covers catalog-to-workbook generation, snapshot parsing, stale detection, error mapping, and view sorting.
- Modify `tests/unit/test_dashboard.py`
  - Covers workbook-first sector mover behavior and fallback to the existing Wind provider.
- Modify `tests/unit/test_desktop_shell_scaffold.py`
  - Covers the frontend refresh timer and user-facing status copy.

## Task 1: Catalog Notes and Workbook Domain Model

**Files:**
- Modify: `services/wind_index_catalog.py`
- Create: `tests/unit/test_wind_realtime_workbook.py`

- [ ] **Step 1: Write failing tests for catalog notes and snapshot parsing types**

Add this initial test file:

```python
from datetime import UTC, datetime, timedelta

from services.wind_index_catalog import load_wind_index_catalog, save_wind_index_catalog, WindIndexCatalogEntry
from services.wind_realtime_workbook import WorkbookSnapshotRow, parse_snapshot_rows, split_snapshot_movers


def test_wind_index_catalog_preserves_notes_column(tmp_path):
    path = tmp_path / "wind_index_catalog.csv"
    save_wind_index_catalog(
        [
            WindIndexCatalogEntry(
                code="8841701.WI",
                name="GPU指数",
                family="wind_concept",
                category="热门概念",
                is_active=True,
                priority=10,
                is_concept=True,
                view_key="wind_hot_concept",
                view_label="Wind热门概念",
                notes="用户截图补充",
            )
        ],
        path=path,
    )

    entries = load_wind_index_catalog(path)

    assert len(entries) == 1
    assert entries[0].code == "8841701.WI"
    assert entries[0].notes == "用户截图补充"


def test_parse_snapshot_rows_filters_bad_rows_and_marks_stale():
    now = datetime(2026, 6, 22, 8, 30, tzinfo=UTC)
    rows = [
        {
            "view_key": "wind_l4",
            "view_label": "Wind四级",
            "wind_code": "882408.WI",
            "name": "工业气体",
            "last": 1234.5,
            "pct_change": "10.82",
            "is_concept": "false",
            "source": "wind",
            "updated_at": "2026-06-22T08:29:40+00:00",
            "status": "ok",
        },
        {
            "view_key": "wind_l4",
            "view_label": "Wind四级",
            "wind_code": "882409.WI",
            "name": "特种化工",
            "last": 888.0,
            "pct_change": "#N/A",
            "is_concept": "false",
            "source": "wind",
            "updated_at": "2026-06-22T08:29:40+00:00",
            "status": "formula_error",
        },
        {
            "view_key": "wind_l4",
            "view_label": "Wind四级",
            "wind_code": "882410.WI",
            "name": "建材IV",
            "last": 777.0,
            "pct_change": "-3.25",
            "is_concept": "false",
            "source": "wind",
            "updated_at": "2026-06-22T08:27:00+00:00",
            "status": "ok",
        },
    ]

    snapshot = parse_snapshot_rows(rows, now=now, stale_after_seconds=60)

    assert [item.wind_code for item in snapshot.rows] == ["882408.WI", "882410.WI"]
    assert snapshot.error_count == 1
    assert snapshot.is_stale is True
    assert snapshot.status == "snapshot_stale"


def test_split_snapshot_movers_sorts_up_and_down():
    rows = [
        WorkbookSnapshotRow("wind_l4", "Wind四级", "A.WI", "A", 1.0, 3.0, False, "wind", datetime.now(UTC), "ok"),
        WorkbookSnapshotRow("wind_l4", "Wind四级", "B.WI", "B", 1.0, -2.0, False, "wind", datetime.now(UTC), "ok"),
        WorkbookSnapshotRow("wind_l4", "Wind四级", "C.WI", "C", 1.0, 5.0, False, "wind", datetime.now(UTC), "ok"),
    ]

    up, down = split_snapshot_movers(rows, limit=2)

    assert [item["name"] for item in up] == ["C", "A"]
    assert [item["name"] for item in down] == ["B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py -q
```

Expected: FAIL because `services.wind_realtime_workbook` does not exist and `WindIndexCatalogEntry.notes` is not defined.

- [ ] **Step 3: Add `notes` to the catalog entry and CSV IO**

Modify `services/wind_index_catalog.py`:

```python
@dataclass(frozen=True)
class WindIndexCatalogEntry:
    code: str
    name: str = ""
    family: str = "wind_concept"
    category: str = "热门概念"
    is_active: bool = True
    priority: int = 0
    is_concept: bool = True
    view_key: str = ""
    view_label: str = ""
    notes: str = ""
```

In `load_wind_index_catalog`, pass:

```python
notes=str(row.get("notes") or "").strip(),
```

In `save_wind_index_catalog`, add `"notes"` to `fieldnames` and write:

```python
"notes": entry.notes,
```

- [ ] **Step 4: Create the workbook snapshot domain module**

Create `services/wind_realtime_workbook.py`:

```python
"""Wind realtime workbook snapshot reader and parser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from core.observability import get_logger

logger = get_logger(__name__)

DEFAULT_WORKBOOK_PATH = (
    Path.home()
    / "Library"
    / "Application Support"
    / "Research Workbench"
    / "wind"
    / "Research Workbench_Wind_Realtime.xlsx"
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


def resolve_workbook_path(raw_path: str | Path | None = None) -> Path:
    return Path(raw_path).expanduser() if raw_path else DEFAULT_WORKBOOK_PATH


def _float_value(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool_value(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "是"}


def _datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def parse_snapshot_rows(
    raw_rows: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_after_seconds: int = 60,
) -> WorkbookSnapshot:
    current = now or datetime.now(UTC)
    parsed_rows: list[WorkbookSnapshotRow] = []
    error_count = 0
    newest: datetime | None = None

    for raw in raw_rows:
        status = str(raw.get("status") or "").strip().lower()
        pct_change = _float_value(raw.get("pct_change"))
        updated_at = _datetime_value(raw.get("updated_at"))
        if status != "ok" or pct_change is None or updated_at is None:
            error_count += 1
            continue
        newest = updated_at if newest is None or updated_at > newest else newest
        parsed_rows.append(
            WorkbookSnapshotRow(
                view_key=str(raw.get("view_key") or "").strip(),
                view_label=str(raw.get("view_label") or "").strip(),
                wind_code=str(raw.get("wind_code") or "").strip().upper(),
                name=str(raw.get("name") or "").strip(),
                last=_float_value(raw.get("last")),
                pct_change=pct_change,
                is_concept=_bool_value(raw.get("is_concept")),
                source=str(raw.get("source") or "wind").strip() or "wind",
                updated_at=updated_at,
                status="ok",
            )
        )

    if not parsed_rows:
        return WorkbookSnapshot(tuple(), "snapshot_empty", False, newest, error_count, "Wind快照暂无可用数据")

    stale = newest is None or (current - newest).total_seconds() > stale_after_seconds
    status = "snapshot_stale" if stale else "ok"
    message = "Wind数据可能未刷新" if stale else ""
    return WorkbookSnapshot(tuple(parsed_rows), status, stale, newest, error_count, message)


def split_snapshot_movers(rows: Iterable[WorkbookSnapshotRow], limit: int) -> tuple[list[dict], list[dict]]:
    items = [
        {
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
        for row in rows
        if row.view_key and row.wind_code and row.name
    ]
    up = sorted([item for item in items if item["change_pct"] > 0], key=lambda item: item["change_pct"], reverse=True)[:limit]
    down = sorted([item for item in items if item["change_pct"] < 0], key=lambda item: item["change_pct"])[:limit]
    return up, down
```

- [ ] **Step 5: Run tests to verify they pass**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/wind_index_catalog.py services/wind_realtime_workbook.py tests/unit/test_wind_realtime_workbook.py
git commit -m "feat: add wind realtime workbook snapshot model"
```

## Task 2: Workbook Generation Script

**Files:**
- Modify: `services/wind_realtime_workbook.py`
- Create: `scripts/build_wind_realtime_workbook.py`
- Modify: `tests/unit/test_wind_realtime_workbook.py`

- [ ] **Step 1: Add failing tests for workbook generation**

Append to `tests/unit/test_wind_realtime_workbook.py`:

```python
from openpyxl import load_workbook

from services.wind_realtime_workbook import build_realtime_workbook


def test_build_realtime_workbook_creates_expected_sheets_and_formulas(tmp_path):
    catalog_path = tmp_path / "wind_index_catalog.csv"
    workbook_path = tmp_path / "Research Workbench_Wind_Realtime.xlsx"
    save_wind_index_catalog(
        [
            WindIndexCatalogEntry(
                code="8841701.WI",
                name="GPU指数",
                view_key="wind_hot_concept",
                view_label="Wind热门概念",
                is_concept=True,
            )
        ],
        path=catalog_path,
    )

    result = build_realtime_workbook(catalog_path=catalog_path, workbook_path=workbook_path)

    assert result == workbook_path
    wb = load_workbook(workbook_path, data_only=False)
    assert wb.sheetnames == ["README", "Config", "IndexCatalog", "RealtimeRaw", "Snapshot", "Health", "FormulaLog"]
    assert wb["RealtimeRaw"]["E2"].value == '=@s_info_name("8841701.WI")'
    assert wb["RealtimeRaw"]["F2"].value == '=@wss("8841701.WI","rt_last")'
    assert wb["RealtimeRaw"]["G2"].value == '=@wss("8841701.WI","rt_pct_chg")'
    assert wb["Snapshot"]["A1"].value == "view_key"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py::test_build_realtime_workbook_creates_expected_sheets_and_formulas -q
```

Expected: FAIL because `build_realtime_workbook` is not defined.

- [ ] **Step 3: Implement workbook generation**

Add to `services/wind_realtime_workbook.py`:

```python
from openpyxl import Workbook

from services.wind_index_catalog import load_wind_index_catalog

WORKBOOK_SHEETS = ["README", "Config", "IndexCatalog", "RealtimeRaw", "Snapshot", "Health", "FormulaLog"]
RAW_HEADERS = [
    "row_id", "view_key", "view_label", "wind_code",
    "name_formula", "last_formula", "pct_change_formula", "update_time_formula",
    "name_value", "last_value", "pct_change_value", "update_time_value", "status",
]
CATALOG_HEADERS = [
    "row_id", "view_key", "view_label", "wind_code", "name",
    "is_active", "is_concept", "priority", "source_family", "notes",
]
HEALTH_HEADERS = ["metric", "value", "updated_at", "notes"]
LOG_HEADERS = ["timestamp", "level", "component", "message", "details"]


def build_realtime_workbook(catalog_path: str | Path, workbook_path: str | Path | None = None) -> Path:
    output_path = resolve_workbook_path(workbook_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    entries = load_wind_index_catalog(catalog_path)

    wb = Workbook()
    wb.remove(wb.active)
    sheets = {name: wb.create_sheet(name) for name in WORKBOOK_SHEETS}

    sheets["README"]["A1"] = "Research Workbench Wind Realtime Workbook"
    sheets["README"]["A2"] = "Open this workbook in Excel and log in to Wind before using Wind market views."

    sheets["Config"].append(["key", "value", "description"])
    sheets["Config"].append(["refresh_enabled", "true", "是否启用实时刷新"])
    sheets["Config"].append(["expected_update_seconds", "60", "超过该秒数视为数据可能过期"])
    sheets["Config"].append(["formula_version", "1", "公式模板版本"])
    sheets["Config"].append(["last_generated_at", datetime.now(UTC).isoformat(), "工作簿最后生成时间"])
    sheets["Config"].append(["timezone", "Asia/Shanghai", "时间区域"])
    sheets["Config"].append(["data_owner", "Research Workbench", "数据维护方"])

    sheets["IndexCatalog"].append(CATALOG_HEADERS)
    sheets["RealtimeRaw"].append(RAW_HEADERS)
    sheets["Snapshot"].append(SNAPSHOT_HEADERS)
    sheets["Health"].append(HEALTH_HEADERS)
    sheets["FormulaLog"].append(LOG_HEADERS)

    active_row = 2
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
                "=NOW()",
                f'=E{active_row}',
                f'=F{active_row}',
                f'=G{active_row}',
                f'=H{active_row}',
                f'=IF(OR(ISERROR(F{active_row}),ISERROR(G{active_row})),"formula_error","ok")',
            ]
        )
        sheets["Snapshot"].append(
            [
                f"=RealtimeRaw!B{active_row}",
                f"=RealtimeRaw!C{active_row}",
                f"=RealtimeRaw!D{active_row}",
                f"=RealtimeRaw!I{active_row}",
                f"=RealtimeRaw!J{active_row}",
                f"=RealtimeRaw!K{active_row}",
                str(entry.is_concept).lower(),
                "wind",
                f"=RealtimeRaw!L{active_row}",
                f"=RealtimeRaw!M{active_row}",
            ]
        )
        active_row += 1

    sheets["Health"].append(["workbook_open", "true", datetime.now(UTC).isoformat(), "文件已生成"])
    sheets["Health"].append(["active_index_count", active_row - 2, datetime.now(UTC).isoformat(), "active 指数数量"])

    for sheet in sheets.values():
        sheet.freeze_panes = "A2"

    wb.save(output_path)
    return output_path
```

- [ ] **Step 4: Add CLI script**

Create `scripts/build_wind_realtime_workbook.py`:

```python
#!/usr/bin/env python3
"""Build the local Wind realtime workbook from the versioned index catalog."""

from __future__ import annotations

import argparse
from pathlib import Path

from services.wind_index_catalog import DEFAULT_WIND_INDEX_CATALOG_PATH
from services.wind_realtime_workbook import DEFAULT_WORKBOOK_PATH, build_realtime_workbook


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build Research Workbench Wind realtime workbook")
    parser.add_argument("--catalog", default=str(DEFAULT_WIND_INDEX_CATALOG_PATH))
    parser.add_argument("--output", default=str(DEFAULT_WORKBOOK_PATH))
    return parser


def main() -> int:
    args = build_parser().parse_args()
    path = build_realtime_workbook(
        catalog_path=Path(args.catalog).expanduser(),
        workbook_path=Path(args.output).expanduser(),
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Run tests and script check**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py -q
/Users/leon/opt/anaconda3/bin/python scripts/build_wind_realtime_workbook.py --catalog data_sources/wind_index_catalog.csv --output /tmp/Research Workbench_Wind_Realtime.xlsx
```

Expected: tests PASS, script prints `/tmp/Research Workbench_Wind_Realtime.xlsx`.

- [ ] **Step 6: Commit**

```bash
git add services/wind_realtime_workbook.py scripts/build_wind_realtime_workbook.py tests/unit/test_wind_realtime_workbook.py
git commit -m "feat: generate wind realtime workbook"
```

## Task 3: Live Workbook Reader and API Payload

**Files:**
- Modify: `services/wind_realtime_workbook.py`
- Modify: `tests/unit/test_wind_realtime_workbook.py`

- [ ] **Step 1: Add failing tests for payload generation and workbook missing**

Append:

```python
from services.wind_realtime_workbook import WindRealtimeWorkbookReader


def test_reader_get_view_returns_error_payload_when_workbook_missing(tmp_path):
    reader = WindRealtimeWorkbookReader(workbook_path=tmp_path / "missing.xlsx")

    payload = reader.get_view("wind_l4", limit=10)

    assert payload["view_key"] == "wind_l4"
    assert payload["has_real_data"] is False
    assert payload["status"] == "workbook_missing"
    assert payload["up"] == []
    assert payload["down"] == []


def test_reader_payload_from_snapshot_rows_sorts_and_includes_status():
    reader = WindRealtimeWorkbookReader(workbook_path="/tmp/not-used.xlsx")
    snapshot = parse_snapshot_rows(
        [
            {"view_key": "wind_l4", "view_label": "Wind四级", "wind_code": "A.WI", "name": "A", "last": 1, "pct_change": 2, "is_concept": "false", "source": "wind", "updated_at": "2026-06-22T08:30:00+00:00", "status": "ok"},
            {"view_key": "wind_l4", "view_label": "Wind四级", "wind_code": "B.WI", "name": "B", "last": 1, "pct_change": -3, "is_concept": "false", "source": "wind", "updated_at": "2026-06-22T08:30:00+00:00", "status": "ok"},
        ],
        now=datetime(2026, 6, 22, 8, 30, 30, tzinfo=UTC),
        stale_after_seconds=60,
    )

    payload = reader.payload_from_snapshot(snapshot, "wind_l4", limit=5, view_label="Wind四级")

    assert payload["status"] == "ok"
    assert payload["has_real_data"] is True
    assert payload["up"][0]["name"] == "A"
    assert payload["down"][0]["name"] == "B"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py::test_reader_get_view_returns_error_payload_when_workbook_missing tests/unit/test_wind_realtime_workbook.py::test_reader_payload_from_snapshot_rows_sorts_and_includes_status -q
```

Expected: FAIL because `WindRealtimeWorkbookReader` is not defined.

- [ ] **Step 3: Implement reader class**

Add to `services/wind_realtime_workbook.py`:

```python
from services.wind_index_catalog import MARKET_VIEW_LABELS


class WindRealtimeWorkbookReader:
    def __init__(self, workbook_path: str | Path | None = None, stale_after_seconds: int = 60):
        self.workbook_path = resolve_workbook_path(workbook_path)
        self.stale_after_seconds = stale_after_seconds

    def get_view(self, view_key: str, limit: int = 10) -> dict[str, Any]:
        label = MARKET_VIEW_LABELS.get(view_key, view_key)
        if not self.workbook_path.exists():
            return self._empty_payload(view_key, label, "workbook_missing", "Wind实时工作簿不存在")
        try:
            snapshot = self.load_snapshot()
        except RuntimeError as exc:
            return self._empty_payload(view_key, label, str(exc), self._message_for_status(str(exc)))
        return self.payload_from_snapshot(snapshot, view_key, limit, label)

    def load_snapshot(self) -> WorkbookSnapshot:
        rows = self._read_open_workbook_snapshot_rows()
        return parse_snapshot_rows(rows, stale_after_seconds=self.stale_after_seconds)

    def _read_open_workbook_snapshot_rows(self) -> list[dict[str, Any]]:
        try:
            import xlwings as xw
        except Exception as exc:
            raise RuntimeError("xlwings_unavailable") from exc

        target_name = self.workbook_path.name
        for app in xw.apps:
            for book in app.books:
                try:
                    if Path(book.fullname).resolve() == self.workbook_path.resolve() or book.name == target_name:
                        sheet = book.sheets["Snapshot"]
                        values = sheet.used_range.value or []
                        return self._rows_from_matrix(values)
                except Exception:
                    continue
        raise RuntimeError("workbook_not_open")

    @staticmethod
    def _rows_from_matrix(values: list[Any]) -> list[dict[str, Any]]:
        if not values:
            return []
        header = [str(cell or "").strip() for cell in values[0]]
        rows: list[dict[str, Any]] = []
        for line in values[1:]:
            if not line or not any(cell not in (None, "") for cell in line):
                continue
            rows.append({header[idx]: line[idx] if idx < len(line) else None for idx in range(len(header))})
        return rows

    def payload_from_snapshot(
        self,
        snapshot: WorkbookSnapshot,
        view_key: str,
        limit: int,
        view_label: str,
    ) -> dict[str, Any]:
        matching = [row for row in snapshot.rows if row.view_key == view_key]
        up, down = split_snapshot_movers(matching, limit)
        has_real_data = bool(up or down)
        status = snapshot.status if has_real_data else "snapshot_empty"
        return {
            "view_key": view_key,
            "view_label": view_label,
            "up": up,
            "down": down,
            "has_real_data": has_real_data,
            "fetched_at": datetime.now(UTC).timestamp(),
            "cache_hit": False,
            "cache_ttl_seconds": 60.0,
            "status": status,
            "message": snapshot.message,
            "source": "wind_workbook",
            "updated_at": snapshot.updated_at.isoformat() if snapshot.updated_at else None,
            "error_count": snapshot.error_count,
        }

    @staticmethod
    def _empty_payload(view_key: str, view_label: str, status: str, message: str) -> dict[str, Any]:
        return {
            "view_key": view_key,
            "view_label": view_label,
            "up": [],
            "down": [],
            "has_real_data": False,
            "fetched_at": 0.0,
            "cache_hit": False,
            "cache_ttl_seconds": 60.0,
            "status": status,
            "message": message,
            "source": "wind_workbook",
            "updated_at": None,
            "error_count": 0,
        }

    @staticmethod
    def _message_for_status(status: str) -> str:
        messages = {
            "workbook_not_open": "请打开 Research Workbench Wind 实时工作簿",
            "xlwings_unavailable": "xlwings 不可用，无法连接 Excel",
            "snapshot_empty": "Wind快照暂无可用数据",
        }
        return messages.get(status, "Wind实时工作簿不可用")
```

- [ ] **Step 4: Run tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/wind_realtime_workbook.py tests/unit/test_wind_realtime_workbook.py
git commit -m "feat: read wind realtime workbook snapshots"
```

## Task 4: Dashboard Service Integration

**Files:**
- Modify: `services/dashboard_service.py`
- Modify: `tests/unit/test_dashboard.py`

- [ ] **Step 1: Add failing tests for workbook-first behavior**

Append to `tests/unit/test_dashboard.py`:

```python
@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.WindMarketOverviewProvider")
def test_get_market_sector_view_prefers_wind_workbook_snapshot(mock_wind_provider_cls, mock_reader_cls):
    _market_sector_cache.clear()
    mock_reader = mock_reader_cls.return_value
    mock_reader.get_view.return_value = {
        "view_key": "wind_l4",
        "view_label": "Wind四级",
        "up": [{"name": "工业气体", "change_pct": 10.82}],
        "down": [{"name": "黄金", "change_pct": -3.0}],
        "has_real_data": True,
        "fetched_at": 123.0,
        "cache_hit": False,
        "cache_ttl_seconds": 60.0,
        "status": "ok",
        "message": "",
        "source": "wind_workbook",
    }

    service = DashboardService(Mock())
    result = service.get_market_sector_view("wind_l4", limit=10)

    assert result["source"] == "wind_workbook"
    assert result["up"][0]["name"] == "工业气体"
    mock_reader.get_view.assert_called_once_with("wind_l4", limit=10)
    mock_wind_provider_cls.assert_not_called()


@patch("services.dashboard_service.WindRealtimeWorkbookReader")
@patch("services.dashboard_service.WindMarketOverviewProvider")
def test_get_market_sector_view_falls_back_when_workbook_has_no_real_data(mock_wind_provider_cls, mock_reader_cls):
    _market_sector_cache.clear()
    mock_reader_cls.return_value.get_view.return_value = {
        "view_key": "wind_l4",
        "view_label": "Wind四级",
        "up": [],
        "down": [],
        "has_real_data": False,
        "status": "workbook_not_open",
        "message": "请打开 Research Workbench Wind 实时工作簿",
        "source": "wind_workbook",
    }
    mock_provider = mock_wind_provider_cls.return_value
    mock_provider.seeds = []
    mock_provider.get_grouped_movers.return_value = {
        "views": {"wind_l4": {"up": [{"name": "Fallback", "change_pct": 1.0}], "down": []}},
        "has_real_data": True,
        "fetched_at": 456.0,
    }

    service = DashboardService(Mock())
    result = service.get_market_sector_view("wind_l4", limit=10)

    assert result["up"][0]["name"] == "Fallback"
    assert result["status"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_dashboard.py::test_get_market_sector_view_prefers_wind_workbook_snapshot tests/unit/test_dashboard.py::test_get_market_sector_view_falls_back_when_workbook_has_no_real_data -q
```

Expected: FAIL because `WindRealtimeWorkbookReader` is not imported/integrated.

- [ ] **Step 3: Integrate reader into DashboardService**

Modify imports in `services/dashboard_service.py`:

```python
from services.wind_realtime_workbook import WindRealtimeWorkbookReader
```

In `get_market_sector_view`, before constructing `WindMarketOverviewProvider`, add:

```python
        workbook_payload = WindRealtimeWorkbookReader().get_view(
            normalized_view,
            limit=normalized_limit,
        )
        if workbook_payload.get("has_real_data"):
            self._set_cached_market_sector_payload(cache_key, workbook_payload)
            return self._copy_market_sector_payload(workbook_payload)
        logger.info(
            "Wind workbook unavailable for %s: status=%s message=%s",
            normalized_view,
            workbook_payload.get("status"),
            workbook_payload.get("message"),
        )
```

When building the fallback Wind provider payload, include status fields:

```python
            "status": "ok" if bool(grouped_movers.get("has_real_data")) else workbook_payload.get("status", "snapshot_empty"),
            "message": "" if bool(grouped_movers.get("has_real_data")) else workbook_payload.get("message", ""),
            "source": "wind_formula_fallback" if bool(grouped_movers.get("has_real_data")) else "wind_workbook",
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_dashboard.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add services/dashboard_service.py tests/unit/test_dashboard.py
git commit -m "feat: prefer wind workbook for market sector views"
```

## Task 5: Frontend Silent Refresh and Status Messaging

**Files:**
- Modify: `app/web/static/js/dashboard.js`
- Modify: `tests/unit/test_desktop_shell_scaffold.py`

- [ ] **Step 1: Add failing static assertions**

In `tests/unit/test_desktop_shell_scaffold.py`, inside `test_desktop_workbench_uses_phase_one_visual_baseline`, add:

```python
    assert "MARKET_SECTOR_SILENT_REFRESH_MS = 60000" in dashboard_js
    assert "scheduleActiveMarketSectorRefresh" in dashboard_js
    assert "clearMarketSectorRefreshTimer" in dashboard_js
    assert "renderMarketSectorStatus" in dashboard_js
    assert "Wind 数据可能未刷新" in dashboard_js
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_desktop_shell_scaffold.py::test_desktop_workbench_uses_phase_one_visual_baseline -q
```

Expected: FAIL because the refresh timer/status functions are not present.

- [ ] **Step 3: Implement 60-second silent refresh**

Modify `app/web/static/js/dashboard.js` near current market sector globals:

```javascript
const MARKET_SECTOR_SILENT_REFRESH_MS = 60000;
let marketSectorRefreshTimer = null;
```

Add functions:

```javascript
function clearMarketSectorRefreshTimer() {
    if (marketSectorRefreshTimer) clearInterval(marketSectorRefreshTimer);
    marketSectorRefreshTimer = null;
}

function scheduleActiveMarketSectorRefresh() {
    clearMarketSectorRefreshTimer();
    marketSectorRefreshTimer = setInterval(() => {
        ensureMarketSectorViewLoaded(activeMarketSectorView, {
            silent: true,
            force: true,
        });
    }, MARKET_SECTOR_SILENT_REFRESH_MS);
}

function renderMarketSectorStatus(data = {}) {
    const message = data.message || '';
    if (!message) return '';
    const staleCopy = message.includes('未刷新') ? 'Wind 数据可能未刷新' : message;
    return `<li class="empty-state">${esc(staleCopy)}</li>`;
}
```

Modify `renderMarketOverview` after `scheduleMarketSectorPrefetch();`:

```javascript
    scheduleActiveMarketSectorRefresh();
```

Modify `ensureMarketSectorViewLoaded` to support force refresh:

```javascript
    const force = Boolean(options.force);
    const current = latestMarketOverview.sector_views?.[viewKey];
    if (!force && (current?.up?.length || 0) + (current?.down?.length || 0) > 0) return;
```

After the API call in `ensureMarketSectorViewLoaded`, store metadata:

```javascript
        latestMarketOverview.sector_view_status = latestMarketOverview.sector_view_status || {};
        latestMarketOverview.sector_view_status[viewKey] = {
            status: data.status || 'ok',
            message: data.message || '',
            source: data.source || '',
            updated_at: data.updated_at || null,
        };
```

Modify `renderSectorList` empty branch:

```javascript
        const statusMarkup = renderMarketSectorStatus(
            latestMarketOverview?.sector_view_status?.[activeMarketSectorView] || {}
        );
        container.innerHTML = statusMarkup || `<li class="empty-state">${esc(getActiveMarketSectorView().label)}暂无数据</li>`;
```

- [ ] **Step 4: Run frontend checks**

Run:

```bash
node --check app/web/static/js/dashboard.js
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_desktop_shell_scaffold.py::test_desktop_workbench_uses_phase_one_visual_baseline -q
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add app/web/static/js/dashboard.js tests/unit/test_desktop_shell_scaffold.py
git commit -m "feat: refresh market sector view silently"
```

## Task 6: End-to-End Verification

**Files:**
- No planned source changes unless verification exposes defects.

- [ ] **Step 1: Run unit and syntax checks**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python -m py_compile services/wind_realtime_workbook.py services/wind_index_catalog.py services/dashboard_service.py
node --check app/web/static/js/dashboard.js
/Users/leon/opt/anaconda3/bin/python -m pytest tests/unit/test_wind_realtime_workbook.py tests/unit/test_dashboard.py tests/unit/test_desktop_shell_scaffold.py -q
```

Expected: all commands exit 0.

- [ ] **Step 2: Generate a workbook in `/tmp`**

Run:

```bash
/Users/leon/opt/anaconda3/bin/python scripts/build_wind_realtime_workbook.py --catalog data_sources/wind_index_catalog.csv --output /tmp/Research Workbench_Wind_Realtime.xlsx
```

Expected: command prints `/tmp/Research Workbench_Wind_Realtime.xlsx`; the file exists and contains the expected sheets.

- [ ] **Step 3: Restart the backend**

Run:

```bash
lsof -nP -iTCP:8765 -sTCP:LISTEN || true
```

If a Python process is listening on 8765, stop it:

```bash
kill -TERM <PID>
```

Start backend:

```bash
RESEARCH_PYTHON=/Users/leon/opt/anaconda3/bin/python bash scripts/desktop/run_backend.sh --host 127.0.0.1 --port 8765
```

Expected: backend logs `Uvicorn running on http://127.0.0.1:8765`.

- [ ] **Step 4: Verify dashboard remains fast**

Run:

```bash
NO_PROXY=127.0.0.1,localhost /usr/bin/time -p curl -sS -m 8 'http://127.0.0.1:8765/api/dashboard' > /tmp/rwb_dashboard.json
```

Expected: exits 0; `real` time is under 3 seconds on a warm backend.

- [ ] **Step 5: Verify Wind workbook unavailable status is explicit**

Run with the runtime workbook not open:

```bash
NO_PROXY=127.0.0.1,localhost curl -sS -m 8 'http://127.0.0.1:8765/api/dashboard/sector-movers?view_key=wind_l4&limit=10' > /tmp/rwb_wind_l4.json
/Users/leon/opt/anaconda3/bin/python - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/rwb_wind_l4.json').read_text())
print(payload.get("status"), payload.get("message"), len(payload.get("up", [])), len(payload.get("down", [])))
PY
```

Expected: either workbook snapshot data is returned if the workbook is open, or fallback data is returned from the current Wind provider; if neither is available, `status` is one of `workbook_missing`, `workbook_not_open`, or `snapshot_empty` with a non-empty `message`.

- [ ] **Step 6: Commit verification fixes or finish**

If verification required code fixes:

```bash
git add <changed-files>
git commit -m "fix: stabilize wind realtime workbook integration"
```

If no fixes were required, do not create an empty commit.

## Self-Review

- Spec coverage: The plan covers CSV source maintenance, workbook generation, Snapshot/Health reading, backend payload integration, frontend 60-second silent refresh, error states, and verification.
- Placeholder scan: No placeholder markers or vague “add handling” steps are intentionally left in this plan.
- Type consistency: `WorkbookSnapshotRow`, `WorkbookSnapshot`, `WindRealtimeWorkbookReader`, `build_realtime_workbook`, and payload fields are introduced before downstream tasks use them.
