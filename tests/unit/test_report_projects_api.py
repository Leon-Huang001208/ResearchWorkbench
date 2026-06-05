"""Tests for report project API routes."""
from pathlib import Path
import zipfile
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from reporting.projects.project_manager import ReportProjectManager


client = TestClient(app)


def write_minimal_docx(path: Path, text: str) -> None:
    """Write a tiny docx package with one document.xml body."""
    document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body>
</w:document>"""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("word/document.xml", document_xml)


def write_minimal_xlsx(path: Path) -> None:
    """Write a tiny xlsx package with workbook metadata and one sheet."""
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "xl/workbook.xml",
            """<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
                xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                <sheets><sheet name="基本信息" sheetId="1" r:id="rId1"/></sheets>
            </workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="worksheet" Target="worksheets/sheet1.xml"/>
            </Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
                <dimension ref="A1:C3"/>
                <sheetData>
                  <row r="1"><c r="A1" t="inlineStr"><is><t>日期</t></is></c></row>
                  <row r="2"><c r="B2" t="inlineStr"><is><t>创业板50</t></is></c></row>
                </sheetData>
            </worksheet>""",
        )


def test_list_report_projects_returns_project_assets(tmp_path: Path, monkeypatch):
    """报告项目接口应返回项目包资产、配置和历史报告。"""
    project_dir = tmp_path / "创业板50周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "templates" / "report_template.docx").write_bytes(b"docx")
    (project_dir / "data" / "创业板50周报（iFind版）.xlsx").write_bytes(b"xlsx")
    (project_dir / "data" / "domestic.json").write_text("{}", encoding="utf-8")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "config" / "prompt_templates.md").write_text("前缀提示词", encoding="utf-8")
    (project_dir / "generated" / "2026-06-05_创业板50周报.docx").write_bytes(b"report")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 创业板50周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/创业板50周报（iFind版）.xlsx",
                "section_config: config/section_config.yaml",
                "prompt_templates: config/prompt_templates.md",
                "data_sources:",
                "  - data/domestic.json",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )

    import app.api.routes.report_projects as report_projects_route

    monkeypatch.setattr(
        report_projects_route,
        "report_project_manager",
        ReportProjectManager(projects_root=tmp_path),
    )

    response = client.get("/api/report-projects/")

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    project = data["projects"][0]
    assert project["name"] == "创业板50周报"
    assert project["word_template_filename"] == "report_template.docx"
    assert project["excel_workbook_filename"] == "创业板50周报（iFind版）.xlsx"
    assert project["section_config_filename"] == "section_config.yaml"
    assert project["prompt_templates_filename"] == "prompt_templates.md"
    assert project["data_source_files"] == ["domestic.json"]
    assert project["generated_reports"][0]["file_name"] == "2026-06-05_创业板50周报.docx"


def test_get_report_project_returns_real_template_asset_summary(tmp_path: Path, monkeypatch):
    """项目详情应返回真实 Word 占位符、原始 section YAML 和 Excel sheet 摘要。"""
    project_dir = tmp_path / "创业板50周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(
        project_dir / "templates" / "report_template.docx",
        "标题 {{ title }} 日期 {{ start_date }} 内容 {{ content1 }}",
    )
    write_minimal_xlsx(project_dir / "data" / "cyb50.xlsx")
    section_yaml = "\n".join(
        [
            "name: 创业板50周报模板",
            "sections:",
            "- key: content1",
            "  title: 正文观点",
            "  placeholder: content1",
        ]
    )
    (project_dir / "config" / "section_config.yaml").write_text(section_yaml, encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 创业板50周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/cyb50.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )

    import app.api.routes.report_projects as report_projects_route

    monkeypatch.setattr(
        report_projects_route,
        "report_project_manager",
        ReportProjectManager(projects_root=tmp_path),
    )

    response = client.get("/api/report-projects/创业板50周报")

    assert response.status_code == 200
    project = response.json()
    assert project["word_placeholders"] == ["content1", "start_date", "title"]
    assert project["section_config_source"] == section_yaml
    assert project["section_config"]["sections"][0]["placeholder"] == "content1"
    assert project["excel_sheets"][0]["name"] == "基本信息"
    assert project["excel_sheets"][0]["dimension"] == "A1:C3"
    assert project["excel_sheets"][0]["nonempty_count"] == 2
    assert "A1=日期" in project["excel_sheets"][0]["sample_cells"]


def test_render_report_project_writes_to_project_generated_dir(tmp_path: Path, monkeypatch):
    """项目级生成应写入该项目自己的 generated 目录。"""
    project_dir = tmp_path / "创业板50周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "templates" / "report_template.docx").write_bytes(b"docx")
    (project_dir / "data" / "创业板50周报（iFind版）.xlsx").write_bytes(b"xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 创业板50周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/创业板50周报（iFind版）.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )

    import app.api.routes.report_projects as report_projects_route

    monkeypatch.setattr(
        report_projects_route,
        "report_project_manager",
        ReportProjectManager(projects_root=tmp_path),
    )

    def fake_save_from_template(output_path, template_path, sections, placeholders):
        output_path.write_bytes(b"rendered")

    with patch(
        "reporting.projections.word.WordProjection.save_from_template",
        side_effect=fake_save_from_template,
    ):
        response = client.post(
            "/api/report-projects/创业板50周报/render",
            json={"placeholders": {"market_summary_placeholder": "测试正文"}},
        )

    assert response.status_code == 200
    data = response.json()
    output_path = Path(data["file_path"])
    assert output_path.parent == project_dir / "generated"
    assert output_path.name.endswith("_创业板50周报.docx")
    assert output_path.read_bytes() == b"rendered"
    assert data["download_url"].startswith("/api/report-projects/创业板50周报/download/")


def test_upload_report_project_package_creates_project_folder(tmp_path: Path, monkeypatch):
    """上传项目包应创建 report_projects 子目录及 project.yaml。"""
    import app.api.routes.report_projects as report_projects_route

    monkeypatch.setattr(
        report_projects_route,
        "report_project_manager",
        ReportProjectManager(projects_root=tmp_path),
    )

    response = client.post(
        "/api/report-projects/upload",
        data={"project_name": "新周报"},
        files=[
            (
                "word_template",
                (
                    "report_template.docx",
                    b"docx",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ),
            ),
            (
                "excel_workbook",
                (
                    "data.xlsx",
                    b"xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                ),
            ),
            ("section_config", ("section_config.yaml", b"sections: []\n", "text/yaml")),
            ("prompt_templates", ("prompt_templates.md", b"prompt", "text/markdown")),
            ("data_files", ("domestic.json", b"{}", "application/json")),
        ],
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "新周报"
    project_dir = tmp_path / "新周报"
    assert (project_dir / "templates" / "report_template.docx").read_bytes() == b"docx"
    assert (project_dir / "data" / "data.xlsx").read_bytes() == b"xlsx"
    assert (project_dir / "config" / "section_config.yaml").read_text(encoding="utf-8")
    assert (project_dir / "config" / "prompt_templates.md").read_bytes() == b"prompt"
    assert (project_dir / "data" / "domestic.json").read_bytes() == b"{}"
    assert "prompt_templates: config/prompt_templates.md" in (
        project_dir / "project.yaml"
    ).read_text(encoding="utf-8")


def test_rename_report_project_updates_folder_and_yaml(tmp_path: Path, monkeypatch):
    """报告项目改名应同步移动目录并更新 project.yaml。"""
    project_dir = tmp_path / "旧周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "templates" / "report_template.docx").write_bytes(b"docx")
    (project_dir / "data" / "data.xlsx").write_bytes(b"xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 旧周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/data.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )

    import app.api.routes.report_projects as report_projects_route

    monkeypatch.setattr(
        report_projects_route,
        "report_project_manager",
        ReportProjectManager(projects_root=tmp_path),
    )

    response = client.patch("/api/report-projects/旧周报", json={"project_name": "新周报"})

    assert response.status_code == 200
    assert response.json()["name"] == "新周报"
    assert not project_dir.exists()
    new_project_dir = tmp_path / "新周报"
    assert (new_project_dir / "templates" / "report_template.docx").exists()
    assert "name: 新周报" in (new_project_dir / "project.yaml").read_text(encoding="utf-8")
