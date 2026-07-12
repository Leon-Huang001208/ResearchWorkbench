"""Tests for report project chart generation and DOCX embedding."""
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import yaml
from openpyxl.utils.cell import column_index_from_string

from reporting.projects.chart_generation import (
    ReportProjectChartService,
    read_excel_chart_series,
    read_worksheet_chart_series,
    sync_native_chart_parts,
)
from reporting.projects.project_manager import ReportProjectManager


def test_reads_huaan_excel_chart_cache_series():
    """华安周报图表应能直接从 Excel chart cache 读取黄金/原油序列。"""
    workbook = Path("report_projects/华安ETF周报/data/周报图表.xlsx")

    gold = read_excel_chart_series(workbook, "xl/charts/chart2.xml")
    oil = read_excel_chart_series(workbook, "xl/charts/chart3.xml")

    assert [series.name for series in gold] == ["伦敦金(美元/盎司)", "黄金Au9999(右, 元/克)"]
    assert [series.name for series in oil] == ["布伦特原油", "WTI原油"]
    assert len(gold[0].values) > 1000
    assert len(oil[0].values) > 1000


def test_reads_gold_series_from_left_worksheet_and_drops_blank_rows():
    """黄金图应能读取左侧 Wind 数据区，并自动过滤节假日空值行。"""
    workbook = Path("report_projects/华安ETF周报/data/周报图表.xlsx")

    series = read_worksheet_chart_series(
        workbook,
        {
            "sheet": "伦敦金_Au9999",
            "start_row": 3,
            "category_column": "A",
            "series": [
                {"name": "伦敦金(美元/盎司)", "column": "B"},
                {"name": "黄金Au9999(右, 元/克)", "column": "C"},
            ],
        },
    )

    assert [item.name for item in series] == ["伦敦金(美元/盎司)", "黄金Au9999(右, 元/克)"]
    assert len(series[0].values) == len(series[1].values)
    assert len(series[0].values) > 1000
    assert "2017-01-02" not in {str(value)[:10] for value in series[0].categories}


def test_reads_oil_series_from_left_worksheet_and_drops_blank_rows():
    """原油图应能读取左侧 Wind 数据区，并自动过滤任一序列为空的日期。"""
    workbook = Path("report_projects/华安ETF周报/data/周报图表.xlsx")

    series = read_worksheet_chart_series(
        workbook,
        {
            "sheet": "期货结算价(连续)_布伦特原油",
            "start_row": 3,
            "category_column": "A",
            "series": [
                {"name": "布伦特原油", "column": "B"},
                {"name": "WTI原油", "column": "C"},
            ],
        },
    )

    assert [item.name for item in series] == ["布伦特原油", "WTI原油"]
    assert len(series[0].values) == len(series[1].values)
    assert len(series[0].values) > 1000
    assert "40196" not in {str(value) for value in series[0].categories}


def test_huaan_chart_workbook_uses_left_wind_data_without_duplicate_ranges():
    """黄金和原油 Excel 图表应直接引用左侧 Wind 数据区，不保留右侧复制区。"""
    workbook = Path("report_projects/华安ETF周报/data/周报图表.xlsx")

    with zipfile.ZipFile(workbook) as archive:
        gold_chart = archive.read("xl/charts/chart2.xml").decode("utf-8")
        oil_chart = archive.read("xl/charts/chart3.xml").decode("utf-8")
        assert "$E$" not in gold_chart and "$F$" not in gold_chart and "$G$" not in gold_chart
        assert "$E$" not in oil_chart and "$F$" not in oil_chart and "$G$" not in oil_chart
        assert "伦敦金_Au9999!$A$3:$A$2451" in gold_chart
        assert "'期货结算价(连续)_布伦特原油'!$A$3:$A$4242" in oil_chart

        namespace = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        for worksheet in ["xl/worksheets/sheet2.xml", "xl/worksheets/sheet3.xml"]:
            root = ET.fromstring(archive.read(worksheet))
            copied_cells_with_values = []
            for cell in root.findall(".//main:sheetData/main:row/main:c", namespace):
                match = re.match(r"([A-Z]+)(\d+)", cell.attrib.get("r", ""))
                if not match or not 5 <= column_index_from_string(match.group(1)) <= 7:
                    continue
                has_value = (
                    cell.find("main:v", namespace) is not None
                    or cell.find("main:f", namespace) is not None
                    or cell.find("main:is", namespace) is not None
                )
                if has_value:
                    copied_cells_with_values.append(cell.attrib.get("r"))
            assert copied_cells_with_values == []


def test_huaan_native_chart_template_skips_png_embedding(tmp_path: Path):
    """原生图表模板生成时应保留 Word chart，不再回退为 PNG。"""
    manager = ReportProjectManager()
    project = manager.get_project("华安ETF周报")
    source = project.word_template_path
    output = tmp_path / "report.docx"
    shutil.copy2(source, output)

    section_config = yaml.safe_load(
        (project.project_dir / "config" / "section_config.yaml").read_text()
    )
    infos = ReportProjectChartService().generate_and_embed(
        project=project,
        section_config=section_config,
        docx_path=output,
    )

    with zipfile.ZipFile(output) as archive:
        document_xml = archive.read("word/document.xml")
        assert document_xml.count(b"<c:chart") == 3
        assert document_xml.count(b"<a:blip") == 0
        assert "word/header1.xml" in archive.namelist()
        assert "word/footer1.xml" in archive.namelist()
        assert not document_xml.count(b"generated_industry_weekly_performance")

    assert {info.replace_kind for info in infos} == {"native_chart"}


def test_huaan_first_chart_is_below_figure_caption():
    """第一张行业图应位于“图1”标题下方，而不是标题上方。"""
    manager = ReportProjectManager()
    project = manager.get_project("华安ETF周报")
    namespace = {
        "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
        "c": "http://schemas.openxmlformats.org/drawingml/2006/chart",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }

    with zipfile.ZipFile(project.word_template_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    body = root.find("w:body", namespace)
    assert body is not None
    paragraphs = [child for child in list(body) if child.tag.endswith("}p")]
    caption_index = None
    chart_index = None
    for index, paragraph in enumerate(paragraphs):
        text = "".join(
            text_node.text or "" for text_node in paragraph.findall(".//w:t", namespace)
        ).strip()
        chart = paragraph.find(".//c:chart", namespace)
        if text == "图1：申万一级各板块表现":
            caption_index = index
        if chart is not None and chart.get(f"{{{namespace['r']}}}id") == "rId8":
            chart_index = index

    assert caption_index is not None
    assert chart_index is not None
    assert caption_index < chart_index


def test_sync_native_chart_parts_copies_excel_chart_xml(tmp_path: Path):
    """生成时应把 Excel 原生图表 XML 同步进 Word chart part。"""
    manager = ReportProjectManager()
    project = manager.get_project("华安ETF周报")
    output = tmp_path / "report_template.docx"
    shutil.copy2(project.word_template_path, output)

    sync_native_chart_parts(
        project,
        {
            "gold_price": {
                "enabled": True,
                "workbook": "周报图表.xlsx",
                "source_chart": "xl/charts/chart2.xml",
                "native_chart_part": "word/charts/chart2.xml",
            }
        },
        output,
    )

    with zipfile.ZipFile(project.project_dir / "data" / "周报图表.xlsx") as workbook:
        expected = workbook.read("xl/charts/chart2.xml")
    with zipfile.ZipFile(output) as document:
        assert document.read("word/charts/chart2.xml") == expected
