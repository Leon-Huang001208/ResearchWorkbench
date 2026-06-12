"""Tests for report project API routes."""
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from core.interfaces.model_gateway import ModelResponse
from reporting.projects.chart_generation import GeneratedChartInfo
from reporting.projects.generation import (
    EvidenceSnippet,
    GeneratedSectionInfo,
    ReportGenerationResult,
    ReportProjectGenerationService,
)
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
        archive.writestr(
            "word/_rels/document.xml.rels",
            """<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"/>""",
        )


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
    prompt_source = "中国市场\n{{query}}\n\n要求如下：\n1. 严格依据上传文件"
    (project_dir / "config" / "prompt_templates.md").write_text(prompt_source, encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 创业板50周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/cyb50.xlsx",
                "section_config: config/section_config.yaml",
                "prompt_templates: config/prompt_templates.md",
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
    assert project["word_placeholders"] == ["title", "start_date", "content1"]
    assert project["section_config_source"] == section_yaml
    assert project["prompt_templates_source"] == prompt_source
    assert project["section_config"]["sections"][0]["placeholder"] == "content1"
    assert project["excel_sheets"][0]["name"] == "基本信息"
    assert project["excel_sheets"][0]["dimension"] == "A1:C3"
    assert project["excel_sheets"][0]["nonempty_count"] == 2
    assert "A1=日期" in project["excel_sheets"][0]["sample_cells"]


def test_docx_placeholders_keep_word_first_seen_order(tmp_path: Path, monkeypatch):
    """占位符地图应按 Word 正文首次出现顺序展示，而不是按名称排序。"""
    project_dir = tmp_path / "排序周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(
        project_dir / "templates" / "report_template.docx",
        "{{z_last}} {{a_first}} {{middle}} {{a_first}}",
    )
    write_minimal_xlsx(project_dir / "data" / "data.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 排序周报",
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

    response = client.get("/api/report-projects/排序周报")

    assert response.status_code == 200
    assert response.json()["word_placeholders"] == ["z_last", "a_first", "middle"]


def test_update_report_project_source_persists_prompt_templates(tmp_path: Path, monkeypatch):
    """源码保存应写回项目文件，而不是只保存浏览器草稿。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{ content1 }}")
    write_minimal_xlsx(project_dir / "data" / "data.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "config" / "prompt_templates.md").write_text("旧 prompt", encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/data.xlsx",
                "section_config: config/section_config.yaml",
                "prompt_templates: config/prompt_templates.md",
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

    response = client.put(
        "/api/report-projects/华安ETF周报/source",
        json={"source_kind": "prompt_templates", "content": "新 prompt\n{{query}}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["prompt_templates_source"] == "新 prompt\n{{query}}"
    assert (project_dir / "config" / "prompt_templates.md").read_text(
        encoding="utf-8"
    ) == "新 prompt\n{{query}}"


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
    assert data["preview_url"].startswith("/api/report-projects/创业板50周报/preview/")


def test_generation_service_uses_prompt_query_evidence_and_reporting_model(tmp_path: Path):
    """生成服务应把 Prompt 内置 Query 检索结果交给 reporting 模型路由生成。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{人工智能}}")
    write_minimal_xlsx(project_dir / "data" / "data.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text(
        "placeholders: {}\n", encoding="utf-8"
    )
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/data.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )
    project = ReportProjectManager(projects_root=tmp_path).get_project("华安ETF周报")

    class FakeRetriever:
        def __init__(self):
            self.query = ""

        def retrieve(self, query, *, title, params, lookback_days, limit):
            self.query = query
            assert title == "人工智能"
            assert params == {"param": "人工智能"}
            assert lookback_days == 7
            return [
                EvidenceSnippet(
                    source="ingestion:news",
                    title="AI 新闻",
                    content="人工智能产业链本周出现多条政策和产品进展。",
                    published_at="2026-06-01",
                    url="https://example.test/ai",
                )
            ]

    class FakeGateway:
        def __init__(self):
            self.messages = []
            self.task = None

        def chat(self, messages, model=None, temperature=0.7, max_tokens=None, task=None, **kwargs):
            self.messages = messages
            self.task = task
            assert task in {"reporting", "default"}
            assert "人工智能产业链本周出现多条政策和产品进展" in messages[1]["content"]
            assert "请检索本周人工智能相关新闻" in messages[1]["content"]
            return ModelResponse(
                content="我们根据提供的evidence撰写。可以写：人工智能板块本周围绕政策和产品进展延续活跃。",
                model_name="deepseek-chat",
                provider="deepseek",
                tokens_used=123,
                latency_ms=456,
            )

    retriever = FakeRetriever()
    gateway = FakeGateway()
    service = ReportProjectGenerationService(retriever=retriever, model_gateway=gateway)
    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "人工智能": {
                    "title": "人工智能",
                    "type": "prompt",
                    "prompt_template": "人工智能",
                    "max_words": 120,
                    "params": {"param": "人工智能"},
                }
            }
        },
        prompt_templates_source=(
            "## 人工智能\n\n"
            "```text\n"
            "检索 Query：请检索本周人工智能相关新闻\n\n"
            "写作要求：控制在 100 字以内，不输出投资建议。\n"
            "```"
        ),
    )

    assert retriever.query == "请检索本周人工智能相关新闻"
    assert gateway.task in {"reporting", "default"}
    assert result.placeholders["人工智能"] == "人工智能板块本周围绕政策和产品进展延续活跃。"
    assert result.sections[0].provider == "deepseek"
    assert result.sections[0].evidence_count == 1


def test_generation_service_skips_static_and_excel_placeholders(tmp_path: Path):
    """日期、Excel 等非正文占位符不应进入 LLM 生成。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{开始日期}}{{人工智能}}")
    write_minimal_xlsx(project_dir / "data" / "data.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("placeholders: {}\n", encoding="utf-8")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/data.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )
    project = ReportProjectManager(projects_root=tmp_path).get_project("华安ETF周报")

    class FakeRetriever:
        calls = []

        def retrieve(self, query, *, title, params, lookback_days, limit):
            self.calls.append(title)
            return [
                EvidenceSnippet(
                    source="news",
                    title="AI",
                    content="人工智能行业本周有进展。",
                )
            ]

    class FakeGateway:
        def chat(self, **kwargs):
            return ModelResponse(
                content="人工智能行业本周延续活跃。",
                model_name="deepseek-chat",
                provider="deepseek",
                tokens_used=10,
                latency_ms=20,
            )

    retriever = FakeRetriever()
    service = ReportProjectGenerationService(retriever=retriever, model_gateway=FakeGateway())
    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "开始日期": {"title": "开始日期", "type": "static_text"},
                "数据表": {"title": "数据表", "type": "excel_range", "source": "Sheet1!A1:B2"},
                "人工智能": {"title": "人工智能", "type": "prompt", "prompt_template": "人工智能"},
            }
        },
        prompt_templates_source="## 人工智能\n检索 Query：AI\n\n写作要求：周报口吻",
    )

    assert retriever.calls == ["人工智能"]
    assert result.placeholders == {"人工智能": "人工智能行业本周延续活跃。"}
    assert [section.placeholder for section in result.sections] == ["人工智能"]


def test_render_report_project_generates_from_config_and_writes_generation_log(
    tmp_path: Path, monkeypatch
):
    """render 接口应默认从配置生成占位符并记录证据/模型信息。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    (project_dir / "templates" / "report_template.docx").write_bytes(b"docx")
    (project_dir / "data" / "data.xlsx").write_bytes(b"xlsx")
    (project_dir / "config" / "section_config.yaml").write_text(
        "\n".join(
            [
                "placeholders:",
                "  人工智能:",
                "    title: 人工智能",
                "    prompt_template: 人工智能",
            ]
        ),
        encoding="utf-8",
    )
    (project_dir / "config" / "prompt_templates.md").write_text(
        "## 人工智能\n检索 Query：AI\n\n写作要求：周报口吻",
        encoding="utf-8",
    )
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/data.xlsx",
                "section_config: config/section_config.yaml",
                "prompt_templates: config/prompt_templates.md",
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

    class FakeGenerationService:
        def generate_placeholders(self, **kwargs):
            assert kwargs["project"].name == "华安ETF周报"
            assert kwargs["manual_placeholders"] == {}
            assert kwargs["lookback_days"] == 7
            return ReportGenerationResult(
                placeholders={"人工智能": "AI 生成段落"},
                sections=[
                    GeneratedSectionInfo(
                        placeholder="人工智能",
                        title="人工智能",
                        prompt_template="人工智能",
                        retrieval_query="AI",
                        evidence_count=2,
                        model_name="deepseek-chat",
                        provider="deepseek",
                        tokens_used=88,
                    )
                ],
            )

    monkeypatch.setattr(
        report_projects_route,
        "report_generation_service",
        FakeGenerationService(),
    )

    class FakeChartService:
        def generate_and_embed(self, **kwargs):
            return [
                GeneratedChartInfo(
                    chart_id="industry_weekly_performance",
                    title="申万一级行业周涨跌幅",
                    workbook="周报图表.xlsx",
                    source_chart="xl/charts/chart2.xml",
                    replace_kind="chart_to_image",
                    point_count=31,
                    warnings=["图表缓存数值全为 0，请确认 Excel/Wind 已刷新并保存"],
                )
            ]

    monkeypatch.setattr(
        report_projects_route,
        "report_chart_service",
        FakeChartService(),
    )

    captured = {}

    def fake_save_from_template(output_path, template_path, sections, placeholders):
        captured["placeholders"] = placeholders
        output_path.write_bytes(b"rendered")

    with patch(
        "reporting.projections.word.WordProjection.save_from_template",
        side_effect=fake_save_from_template,
    ):
        response = client.post("/api/report-projects/华安ETF周报/render", json={})

    assert response.status_code == 200
    data = response.json()
    assert captured["placeholders"]["人工智能"] == "AI 生成段落"
    assert captured["placeholders"]["开始日期"]
    assert captured["placeholders"]["结束日期"]
    assert data["generated_placeholder_count"] == 3
    assert data["evidence_count"] == 2
    assert "图表缓存数值全为 0" in data["warnings"][0]
    run_files = list((project_dir / "runs").glob("*.json"))
    assert len(run_files) == 1
    run_record = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert run_record["generation"]["sections"][0]["provider"] == "deepseek"
    assert run_record["generation"]["sections"][0]["retrieval_query"] == "AI"
    assert run_record["charts"][0]["chart_id"] == "industry_weekly_performance"


def test_preview_report_project_file_returns_docx_html(tmp_path: Path, monkeypatch):
    """生成后的 Word 文件应能在网页端转换为轻量 HTML 预览。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{人工智能}}")
    write_minimal_xlsx(project_dir / "data" / "data.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text("sections: []\n", encoding="utf-8")
    (project_dir / "generated" / "preview.docx").write_bytes(
        (project_dir / "templates" / "report_template.docx").read_bytes()
    )
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
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

    response = client.get("/api/report-projects/华安ETF周报/preview/preview.docx")

    assert response.status_code == 200
    assert "docx-preview-page" in response.text
    assert "{{人工智能}}" in response.text


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
