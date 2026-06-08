"""Tests for report project chart generation and DOCX embedding."""
import re
import shutil
import xml.etree.ElementTree as ET
import zipfile
from io import BytesIO
from pathlib import Path

from openpyxl.utils.cell import column_index_from_string
from PIL import Image

from reporting.projects.chart_generation import (
    GeneratedChartImage,
    GeneratedChartInfo,
    embed_chart_images_in_docx,
    read_excel_chart_series,
    read_worksheet_chart_series,
    sync_native_chart_parts,
)
from reporting.projects.project_manager import ReportProjectManager


def tiny_png(color: tuple[int, int, int]) -> bytes:
    """Return a tiny PNG image."""
    buffer = BytesIO()
    Image.new("RGB", (12, 8), color).save(buffer, format="PNG")
    return buffer.getvalue()


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


def test_embed_chart_images_replaces_media_and_chart_drawing(tmp_path: Path):
    """图表图片应直接写入 docx 包，且可重复更新已替换过的模板。"""
    source = Path("report_projects/华安ETF周报/templates/report_template.docx")
    output = tmp_path / "report.docx"
    shutil.copy2(source, output)

    images = [
        GeneratedChartImage(
            chart_id="gold_price",
            title="黄金价格走势",
            image_bytes=tiny_png((220, 180, 20)),
            replace={"kind": "media", "target": "word/media/image1.png"},
            info=GeneratedChartInfo(
                chart_id="gold_price",
                title="黄金价格走势",
                workbook="",
                source_chart="",
                replace_kind="media",
                point_count=1,
                warnings=[],
            ),
        ),
        GeneratedChartImage(
            chart_id="industry_weekly_performance",
            title="申万一级行业周涨跌幅",
            image_bytes=tiny_png((40, 120, 220)),
            replace={"kind": "chart_to_image", "chart_relationship_id": "rId8"},
            info=GeneratedChartInfo(
                chart_id="industry_weekly_performance",
                title="申万一级行业周涨跌幅",
                workbook="",
                source_chart="",
                replace_kind="chart_to_image",
                point_count=1,
                warnings=[],
            ),
        ),
    ]

    embed_chart_images_in_docx(output, images)

    with zipfile.ZipFile(output) as archive:
        assert archive.read("word/media/image1.png") == images[0].image_bytes
        assert (
            archive.read("word/media/generated_industry_weekly_performance.png")
            == images[1].image_bytes
        )
        document_xml = archive.read("word/document.xml").decode("utf-8")
        rels_xml = archive.read("word/_rels/document.xml.rels").decode("utf-8")

    assert "generated_industry_weekly_performance.png" in rels_xml
    assert "rId8" not in document_xml
    assert "rId8" not in rels_xml


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
