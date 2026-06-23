from datetime import UTC, datetime
from pathlib import Path

import pytest

from services.wind_index_catalog import (
    WindIndexCatalogError,
    WindIndexCatalogEntry,
    load_wind_index_catalog,
    save_wind_index_catalog,
)
from services.wind_realtime_workbook import (
    DEFAULT_WORKBOOK_PATH,
    WorkbookSnapshotRow,
    parse_snapshot_rows,
    resolve_workbook_path,
    split_snapshot_movers,
)


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
    assert snapshot.status == "snapshot_empty"


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


def test_parse_snapshot_rows_reports_empty_snapshot_message():
    snapshot = parse_snapshot_rows([], now=datetime(2026, 6, 22, 8, 30, tzinfo=UTC))

    assert snapshot.rows == ()
    assert snapshot.status == "snapshot_empty"
    assert snapshot.message == "Wind快照暂无可用数据"
    assert snapshot.is_stale is False


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
