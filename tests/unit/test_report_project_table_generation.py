"""Tests for deterministic report project table generation."""

from pathlib import Path

from openpyxl import Workbook

from reporting.projects.project_manager import ReportProject
from reporting.projects.table_generation import build_project_tables


def _write_calendar_workbook(path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "经济数据"
    sheet.append(["日期", "时间", "国家/地区", "指标名称", "重要性", "前值", "预测值", "今值"])
    sheet.append(["2026-06-15", "21:30", "美国", "6月纽约联储制造业指数", "重要", -9.2, None, None])
    sheet.append(["2026-06-16", "17:00", "欧盟", "5月欧元区CPI:同比", "重要", 2.2, None, None])
    sheet.append(["2026-06-17", "08:00", "日本", "低优先级指标", "一般", 1.0, None, None])
    workbook.save(path)


def test_build_project_tables_reads_global_calendar_from_excel(tmp_path: Path):
    """Table config should produce a Word TableSpec from a project workbook."""
    project_dir = tmp_path / "华安ETF周报"
    data_dir = project_dir / "data"
    data_dir.mkdir(parents=True)
    calendar_path = data_dir / "全球经济日历.xlsx"
    _write_calendar_workbook(calendar_path)

    project = ReportProject(
        name="华安ETF周报",
        slug="华安ETF周报",
        project_dir=project_dir,
        word_template_path=project_dir / "templates" / "report_template.docx",
        excel_workbook_path=data_dir / "周报数据.xlsx",
        section_config_path=project_dir / "config" / "section_config.yaml",
        output_dir=project_dir / "generated",
        run_log_dir=project_dir / "runs",
    )
    section_config = {
        "tables": {
            "global_investment_calendar": {
                "title": "下周全球投资日历",
                "enabled": True,
                "placeholder": "下周全球投资日历",
                "workbook": "全球经济日历.xlsx",
                "sheet": "经济数据",
                "columns": ["日期", "国家/地区", "指标名称"],
                "filter": {"column": "重要性", "equals": "重要"},
            }
        }
    }

    tables, infos = build_project_tables(project=project, section_config=section_config)

    assert len(tables) == 1
    table = tables[0]
    assert table.table_id == "global_investment_calendar"
    assert table.placeholder == "下周全球投资日历"
    assert table.headers == ["日期", "国家/地区", "指标名称"]
    assert table.rows == [
        ["2026-06-15", "美国", "6月纽约联储制造业指数"],
        ["2026-06-16", "欧盟", "5月欧元区CPI:同比"],
    ]
    assert infos == [
        {
            "table_id": "global_investment_calendar",
            "title": "下周全球投资日历",
            "workbook": "全球经济日历.xlsx",
            "sheet": "经济数据",
            "row_count": 2,
            "warnings": [],
        }
    ]
