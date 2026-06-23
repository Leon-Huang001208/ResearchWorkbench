from datetime import UTC, datetime
from pathlib import Path
import subprocess
import sys
import types

import pytest
from openpyxl import load_workbook

from services.wind_index_catalog import (
    WindIndexCatalogError,
    WindIndexCatalogEntry,
    load_wind_index_catalog,
    save_wind_index_catalog,
)
from services.wind_realtime_workbook import (
    DEFAULT_WORKBOOK_PATH,
    WindRealtimeWorkbookReader,
    WorkbookSnapshot,
    WorkbookSnapshotRow,
    build_realtime_workbook,
    payload_from_snapshot,
    parse_snapshot_rows,
    resolve_workbook_path,
    split_snapshot_movers,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


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


def test_wind_index_catalog_raises_when_existing_file_cannot_be_read(
    tmp_path, monkeypatch
):
    path = tmp_path / "wind_index_catalog.csv"
    path.write_text("code,name\n8841701.WI,GPU指数\n", encoding="utf-8")
    original_open = Path.open

    def broken_open(self, *args, **kwargs):
        if self == path:
            raise OSError("permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", broken_open)

    with pytest.raises(WindIndexCatalogError, match="Failed to load Wind index catalog"):
        load_wind_index_catalog(path)


def test_wind_index_catalog_missing_file_returns_empty_list(tmp_path):
    assert load_wind_index_catalog(tmp_path / "missing.csv") == []


def test_wind_index_catalog_raises_when_code_header_is_missing(tmp_path):
    path = tmp_path / "wind_index_catalog.csv"
    path.write_text("name,family\nGPU指数,wind_concept\n", encoding="utf-8")

    with pytest.raises(WindIndexCatalogError, match="missing required code header"):
        load_wind_index_catalog(path)


def test_wind_index_catalog_accepts_wind_code_header(tmp_path):
    path = tmp_path / "wind_index_catalog.csv"
    path.write_text(
        "wind_code,name,family,view_key,view_label\n"
        "8841701.WI,GPU指数,wind_concept,wind_hot_concept,Wind热门概念\n",
        encoding="utf-8",
    )

    entries = load_wind_index_catalog(path)

    assert len(entries) == 1
    assert entries[0].code == "8841701.WI"
    assert entries[0].view_key == "wind_hot_concept"


def test_wind_index_catalog_raises_when_file_encoding_is_invalid(tmp_path):
    path = tmp_path / "wind_index_catalog.csv"
    path.write_bytes(b"\xff\xfe\xfa")

    with pytest.raises(WindIndexCatalogError, match="Failed to load Wind index catalog"):
        load_wind_index_catalog(path)


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
    assert snapshot.message == "Wind数据可能未刷新"


def test_parse_snapshot_rows_filters_non_finite_pct_change_values():
    rows = [
        {
            "view_key": "wind_l4",
            "view_label": "Wind四级",
            "wind_code": f"{value}.WI",
            "name": value,
            "last": 1.0,
            "pct_change": value,
            "is_concept": "false",
            "source": "wind",
            "updated_at": "2026-06-22T08:29:40+00:00",
            "status": "ok",
        }
        for value in ("NaN", "inf", "-inf")
    ]

    snapshot = parse_snapshot_rows(
        rows,
        now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
    )

    assert snapshot.rows == ()
    assert snapshot.error_count == 3
    assert snapshot.status == "snapshot_invalid"


def test_parse_snapshot_rows_interprets_naive_datetime_as_shanghai_time():
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
            "updated_at": datetime(2026, 6, 22, 16, 30),
            "status": "ok",
        }
    ]

    snapshot = parse_snapshot_rows(
        rows,
        now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
    )

    assert snapshot.rows[0].updated_at.isoformat() == "2026-06-22T08:30:00+00:00"


def test_parse_snapshot_rows_interprets_naive_iso_datetime_as_shanghai_time():
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
            "updated_at": "2026-06-22T16:30:00",
            "status": "ok",
        }
    ]

    snapshot = parse_snapshot_rows(
        rows,
        now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
    )

    assert snapshot.rows[0].updated_at.isoformat() == "2026-06-22T08:30:00+00:00"


def test_parse_snapshot_rows_reports_empty_snapshot_message():
    snapshot = parse_snapshot_rows([], now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC))

    assert snapshot.rows == ()
    assert snapshot.status == "snapshot_empty"
    assert snapshot.message == "Wind快照暂无可用数据"
    assert snapshot.is_stale is False


def test_parse_snapshot_rows_reports_invalid_when_all_rows_fail():
    snapshot = parse_snapshot_rows(
        [
            {
                "view_key": "wind_l4",
                "view_label": "Wind四级",
                "wind_code": "882408.WI",
                "name": "工业气体",
                "last": 1234.5,
                "pct_change": "#N/A",
                "is_concept": "false",
                "source": "wind",
                "updated_at": "2026-06-22T16:30:00",
                "status": "formula_error",
            }
        ],
        now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
    )

    assert snapshot.rows == ()
    assert snapshot.error_count == 1
    assert snapshot.status == "snapshot_invalid"
    assert "解析失败" in snapshot.message


def test_resolve_workbook_path_uses_default_for_blank_path():
    assert resolve_workbook_path("") == DEFAULT_WORKBOOK_PATH


def test_split_snapshot_movers_sorts_up_and_down():
    rows = [
        WorkbookSnapshotRow(
            "wind_l4",
            "Wind四级",
            "A.WI",
            "A",
            1.0,
            3.0,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
        WorkbookSnapshotRow(
            "wind_l4",
            "Wind四级",
            "B.WI",
            "B",
            1.0,
            -2.0,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
        WorkbookSnapshotRow(
            "wind_l4",
            "Wind四级",
            "C.WI",
            "C",
            1.0,
            5.125,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
        WorkbookSnapshotRow(
            "",
            "Wind四级",
            "D.WI",
            "D",
            1.0,
            8.0,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
        WorkbookSnapshotRow(
            "wind_l4",
            "Wind四级",
            "",
            "E",
            1.0,
            9.0,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
        WorkbookSnapshotRow(
            "wind_l4",
            "Wind四级",
            "F.WI",
            "",
            1.0,
            10.0,
            False,
            "wind",
            datetime.now(UTC),
            "ok",
        ),
    ]

    up, down = split_snapshot_movers(rows, limit=2)

    assert [item["name"] for item in up] == ["C", "A"]
    assert [item["name"] for item in down] == ["B"]
    assert up[0] == {
        "sector_id": "wind-C-WI",
        "name": "C",
        "change_pct": 5.12,
        "leading_stocks": [],
        "related_news_count": 0,
        "is_concept": False,
        "source": "wind",
        "view_key": "wind_l4",
        "view_label": "Wind四级",
    }
    assert "pct_change" not in up[0]


def test_rows_from_matrix_converts_headers_and_skips_empty_rows(tmp_path):
    reader = WindRealtimeWorkbookReader(workbook_path=tmp_path / "live.xlsx")
    values = [
        ["view_key", "name", "pct_change"],
        ["wind_l4", "工业气体", 10.82],
        [None, None, None],
        ["wind_l4", "特种化工", -3.25],
    ]

    rows = reader._rows_from_matrix(values)

    assert rows == [
        {"view_key": "wind_l4", "name": "工业气体", "pct_change": 10.82},
        {"view_key": "wind_l4", "name": "特种化工", "pct_change": -3.25},
    ]


def test_rows_from_matrix_handles_scalar_one_dimensional_and_tuple_values(tmp_path):
    reader = WindRealtimeWorkbookReader(workbook_path=tmp_path / "live.xlsx")

    assert reader._rows_from_matrix("only") == []
    assert reader._rows_from_matrix(["view_key", "name"]) == []
    assert reader._rows_from_matrix(
        (
            ("view_key", "name"),
            ("wind_l4", "工业气体"),
        )
    ) == [{"view_key": "wind_l4", "name": "工业气体"}]


def test_payload_from_snapshot_filters_view_and_sorts_with_status_source_message():
    snapshot = WorkbookSnapshot(
        rows=(
            WorkbookSnapshotRow(
                "wind_l4",
                "Wind四级",
                "A.WI",
                "A",
                1.0,
                3.0,
                False,
                "wind",
                datetime(2026, 6, 22, 8, 29, tzinfo=UTC),
            ),
            WorkbookSnapshotRow(
                "wind_l4",
                "Wind四级",
                "B.WI",
                "B",
                1.0,
                -2.0,
                False,
                "wind",
                datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
            ),
            WorkbookSnapshotRow(
                "wind_l4",
                "Wind四级",
                "C.WI",
                "C",
                1.0,
                5.0,
                False,
                "wind",
                datetime(2026, 6, 22, 8, 28, tzinfo=UTC),
            ),
            WorkbookSnapshotRow(
                "wind_l3",
                "Wind三级",
                "D.WI",
                "D",
                1.0,
                9.0,
                False,
                "wind",
                datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
            ),
        ),
        status="snapshot_stale",
        is_stale=True,
        updated_at=datetime(2026, 6, 22, 8, 30, tzinfo=UTC),
        error_count=2,
        message="Wind数据可能未刷新",
    )

    payload = payload_from_snapshot(
        snapshot,
        view_key="wind_l4",
        limit=2,
        view_label="Wind四级",
    )

    assert payload["view_key"] == "wind_l4"
    assert payload["view_label"] == "Wind四级"
    assert [item["name"] for item in payload["up"]] == ["C", "A"]
    assert [item["name"] for item in payload["down"]] == ["B"]
    assert payload["has_real_data"] is True
    assert payload["cache_hit"] is True
    assert payload["cache_ttl_seconds"] == 60
    assert payload["status"] == "snapshot_stale"
    assert payload["message"] == "Wind数据可能未刷新"
    assert payload["source"] == "wind_realtime_workbook"
    assert payload["updated_at"] == "2026-06-22T08:30:00+00:00"
    assert payload["error_count"] == 2


def test_reader_get_view_returns_workbook_missing_payload(tmp_path):
    reader = WindRealtimeWorkbookReader(workbook_path=tmp_path / "missing.xlsx")

    payload = reader.get_view("wind_l4", limit=3)

    assert payload["view_key"] == "wind_l4"
    assert payload["view_label"] == "Wind四级"
    assert payload["status"] == "workbook_missing"
    assert payload["has_real_data"] is False
    assert payload["up"] == []
    assert payload["down"] == []
    assert payload["message"]
    assert payload["source"] == "wind_realtime_workbook"
    assert payload["cache_hit"] is False


def test_reader_load_snapshot_reports_workbook_not_open(tmp_path, monkeypatch):
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "xlwings", types.SimpleNamespace(apps=[]))

    reader = WindRealtimeWorkbookReader(
        workbook_path=workbook_path,
        stale_after_seconds=100000,
    )
    snapshot = reader.load_snapshot()

    assert snapshot.status == "workbook_not_open"
    assert snapshot.message


def test_reader_load_snapshot_reports_xlwings_unavailable(tmp_path, monkeypatch):
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")
    monkeypatch.setitem(sys.modules, "xlwings", None)

    reader = WindRealtimeWorkbookReader(
        workbook_path=workbook_path,
        stale_after_seconds=100000,
    )
    snapshot = reader.load_snapshot()

    assert snapshot.status == "xlwings_unavailable"
    assert snapshot.message


def test_reader_find_open_workbook_does_not_match_same_name_wrong_path(tmp_path):
    target = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    wrong_dir = tmp_path / "wrong"
    wrong_dir.mkdir()
    wrong_path = wrong_dir / "AlphaFoundry_Wind_Realtime.xlsx"
    target.write_text("target", encoding="utf-8")
    wrong_path.write_text("wrong", encoding="utf-8")
    book = types.SimpleNamespace(fullname=str(wrong_path), name=target.name)
    xw = types.SimpleNamespace(apps=[types.SimpleNamespace(books=[book])])

    reader = WindRealtimeWorkbookReader(workbook_path=target)

    assert reader._find_open_workbook(xw) is None


def test_reader_find_open_workbook_does_not_match_name_without_fullname(tmp_path):
    target = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    target.write_text("target", encoding="utf-8")
    book = types.SimpleNamespace(fullname="", name=target.name)
    xw = types.SimpleNamespace(apps=[types.SimpleNamespace(books=[book])])

    reader = WindRealtimeWorkbookReader(workbook_path=target)

    assert reader._find_open_workbook(xw) is None


def test_reader_load_snapshot_reads_matching_workbook(tmp_path, monkeypatch):
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")
    values = [
        ["view_key", "view_label", "wind_code", "name", "last", "pct_change", "is_concept", "source", "updated_at", "status"],
        ["wind_l4", "Wind四级", "882408.WI", "工业气体", 1234.5, 10.82, "false", "wind", "2026-06-22T16:30:00", "ok"],
    ]
    snapshot_sheet = types.SimpleNamespace(
        used_range=types.SimpleNamespace(value=values)
    )
    book = types.SimpleNamespace(
        fullname=str(workbook_path),
        name=workbook_path.name,
        sheets={"Snapshot": snapshot_sheet},
    )
    monkeypatch.setitem(
        sys.modules,
        "xlwings",
        types.SimpleNamespace(apps=[types.SimpleNamespace(books=[book])]),
    )

    reader = WindRealtimeWorkbookReader(
        workbook_path=workbook_path,
        stale_after_seconds=100000,
    )
    snapshot = reader.load_snapshot()

    assert snapshot.status == "ok"
    assert snapshot.rows[0].name == "工业气体"
    assert snapshot.rows[0].updated_at.isoformat() == "2026-06-22T08:30:00+00:00"


def test_reader_load_snapshot_reports_read_error(tmp_path, monkeypatch):
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    workbook_path.write_text("placeholder", encoding="utf-8")
    book = types.SimpleNamespace(
        fullname=str(workbook_path),
        name=workbook_path.name,
        sheets={},
    )
    monkeypatch.setitem(
        sys.modules,
        "xlwings",
        types.SimpleNamespace(apps=[types.SimpleNamespace(books=[book])]),
    )

    reader = WindRealtimeWorkbookReader(workbook_path=workbook_path)
    snapshot = reader.load_snapshot()

    assert snapshot.status == "workbook_read_error"
    assert snapshot.error_count == 1


def test_build_realtime_workbook_creates_expected_sheets_and_formulas(tmp_path):
    catalog_path = tmp_path / "wind_index_catalog.csv"
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
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

    result = build_realtime_workbook(
        catalog_path=catalog_path,
        workbook_path=workbook_path,
    )

    assert result == workbook_path
    wb = load_workbook(workbook_path, data_only=False)
    assert wb.sheetnames == [
        "README",
        "Config",
        "IndexCatalog",
        "RealtimeRaw",
        "Snapshot",
        "Health",
        "FormulaLog",
    ]
    assert wb["RealtimeRaw"]["E2"].value == '=@s_info_name("8841701.WI")'
    assert wb["RealtimeRaw"]["F2"].value == '=@wss("8841701.WI","rt_last")'
    assert wb["RealtimeRaw"]["G2"].value == '=@wss("8841701.WI","rt_pct_chg")'
    assert wb["RealtimeRaw"]["H2"].value == '=TEXT(NOW(),"yyyy-mm-ddThh:mm:ss")'
    assert wb["Snapshot"]["A1"].value == "view_key"


def test_build_realtime_workbook_rejects_empty_catalog(tmp_path):
    catalog_path = tmp_path / "wind_index_catalog.csv"
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"
    save_wind_index_catalog([], path=catalog_path)

    with pytest.raises(RuntimeError, match="Wind index catalog is empty"):
        build_realtime_workbook(
            catalog_path=catalog_path,
            workbook_path=workbook_path,
        )

    assert not workbook_path.exists()


def test_build_wind_realtime_workbook_cli_uses_project_catalog_from_any_cwd(tmp_path):
    script_path = PROJECT_ROOT / "scripts" / "build_wind_realtime_workbook.py"
    workbook_path = tmp_path / "AlphaFoundry_Wind_Realtime.xlsx"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--output",
            str(workbook_path),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert str(workbook_path) in result.stdout
    wb = load_workbook(workbook_path, data_only=False)
    assert wb["Health"]["B3"].value == 272
