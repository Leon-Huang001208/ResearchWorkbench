from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

from reporting.projects.project_manager import ReportProject
from reporting.projects.run import ReportProjectRunService
from services.report_workbook_refresh import ReportWorkbookRefreshService


class FakeRange:
    def __init__(self, values):
        self.values = list(values)
        self.read_count = 0

    @property
    def value(self):
        index = min(self.read_count, len(self.values) - 1)
        self.read_count += 1
        return self.values[index]


class FakeSheet:
    def __init__(self, cells):
        self.cells = cells

    def range(self, address):
        return self.cells[address]


class FakeBook:
    def __init__(self, path: Path, sheets):
        self.fullname = str(path)
        self.name = path.name
        self.sheets = sheets
        self.save_count = 0
        self.api = SimpleNamespace(
            RefreshAll=lambda: None,
            Application=SimpleNamespace(CalculateFullRebuild=lambda: None),
        )

    def save(self):
        self.save_count += 1


class FakeApp:
    def __init__(self, book):
        self.books = [book]
        self.calculate_count = 0

    def calculate(self):
        self.calculate_count += 1


def make_project(tmp_path: Path, *, timeout_seconds: float = 5) -> ReportProject:
    workbook = tmp_path / "data.xlsx"
    workbook.write_bytes(b"xlsx")
    return ReportProject(
        name="测试周报",
        slug="测试周报",
        project_dir=tmp_path,
        word_template_path=tmp_path / "template.docx",
        excel_workbook_path=workbook,
        section_config_path=tmp_path / "section.yaml",
        output_dir=tmp_path / "generated",
        run_log_dir=tmp_path / "runs",
        config={
            "excel_refresh": {
                "enabled": True,
                "timeout_seconds": timeout_seconds,
                "poll_seconds": 0,
                "minimum_wait_seconds": 0,
                "stable_polls": 2,
                "date_cell": "日期!A2",
                "required_cells": ["黄金!C2", "石油!D2"],
            }
        },
    )


def test_refresh_waits_for_today_and_stable_wind_values_then_saves(tmp_path: Path):
    project = make_project(tmp_path)
    book = FakeBook(
        project.excel_workbook_path,
        {
            "日期": FakeSheet({"A2": FakeRange([datetime(2026, 6, 14), datetime(2026, 7, 12), datetime(2026, 7, 12)])}),
            "黄金": FakeSheet({"C2": FakeRange([4218.97, 4615.52, 4615.52])}),
            "石油": FakeSheet({"D2": FakeRange([86.8, 63.87, 63.87])}),
        },
    )
    app = FakeApp(book)
    clock = iter([0.0, 0.1, 0.2, 0.3, 0.4])

    result = ReportWorkbookRefreshService(
        excel_apps=lambda: [app],
        sleep=lambda _seconds: None,
        monotonic=lambda: next(clock),
        today=lambda: date(2026, 7, 12),
    ).refresh(project=project)

    assert result.refreshed is True
    assert result.values["日期!A2"] == datetime(2026, 7, 12)
    assert result.values["黄金!C2"] == 4615.52
    assert result.values["石油!D2"] == 63.87
    assert app.calculate_count >= 2
    assert book.save_count == 1


def test_refresh_timeout_raises_and_does_not_save_stale_workbook(tmp_path: Path):
    project = make_project(tmp_path, timeout_seconds=0.2)
    book = FakeBook(
        project.excel_workbook_path,
        {
            "日期": FakeSheet({"A2": FakeRange([datetime(2026, 6, 14)])}),
            "黄金": FakeSheet({"C2": FakeRange([4218.97])}),
            "石油": FakeSheet({"D2": FakeRange([86.8])}),
        },
    )
    app = FakeApp(book)
    clock = iter([0.0, 0.1, 0.21, 0.3])

    service = ReportWorkbookRefreshService(
        excel_apps=lambda: [app],
        sleep=lambda _seconds: None,
        monotonic=lambda: next(clock),
        today=lambda: date(2026, 7, 12),
    )

    with pytest.raises(RuntimeError, match="Wind 数据刷新超时"):
        service.refresh(project=project)

    assert book.save_count == 0


def test_report_run_service_enables_workbook_refresh_by_default():
    service = ReportProjectRunService()

    assert isinstance(service.workbook_refresh_service, ReportWorkbookRefreshService)
