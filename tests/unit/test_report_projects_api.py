"""Tests for report project API routes."""
import json
import threading
import time
import zipfile
from pathlib import Path
from unittest.mock import patch

import yaml
from fastapi.testclient import TestClient

from app.api.main import app
from core.interfaces.model_gateway import ModelResponse
from reporting.projects.chart_generation import GeneratedChartInfo
from reporting.projects.generation import (
    EvidenceSnippet,
    GeneratedSectionInfo,
    PromptTemplateBlock,
    RetrievalConfig,
    ReportGenerationResult,
    ReportProjectGenerationService,
    apply_report_defaults_to_placeholder,
    build_market_hotspot_messages,
    build_retrieval_config,
    filter_and_rank_evidence,
    compute_report_period,
    render_generation_constraints,
    render_writing_parameters,
)
from reporting.projects.keyword_profiles import (
    apply_keyword_profile_to_config,
    keyword_profiles_for_api,
)
from reporting.projects.project_manager import ReportProjectManager

client = TestClient(app)


def test_huaan_prompt_placeholders_use_report_level_retrieval_defaults():
    """华安周报公共检索和重排配置应放在 defaults，placeholder 只保留关键词差异。"""
    config_path = (
        Path(__file__).resolve().parents[2]
        / "report_projects"
        / "华安ETF周报"
        / "config"
        / "section_config.yaml"
    )
    source = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(source)

    assert "&id" not in source
    assert "*id" not in source

    defaults = config["defaults"]
    retrieval_defaults = defaults["retrieval"]
    assert retrieval_defaults["mode"] == "hybrid"
    assert retrieval_defaults["top_k"] == 8
    assert retrieval_defaults["candidate_k"] == 50
    assert retrieval_defaults["semantic_candidate_k"] == 100
    assert retrieval_defaults["fusion"]["method"] == "rrf"
    assert retrieval_defaults["fusion"]["keyword_weight"] == 0.65
    assert retrieval_defaults["fusion"]["semantic_weight"] == 0.35
    assert retrieval_defaults["rerank"]["enabled"] is True
    assert retrieval_defaults["rerank"]["provider"] == "llm"
    assert retrieval_defaults["rerank"]["top_n"] == 16
    assert defaults["validators"]["forbid_wind_data"] is True
    assert defaults["validators"]["no_newline"] is True

    prompt_placeholders = {
        name: item
        for name, item in config["placeholders"].items()
        if item.get("type") == "prompt"
    }

    assert prompt_placeholders
    for name, item in prompt_placeholders.items():
        retrieval = item.get("retrieval")
        assert retrieval, f"{name} missing retrieval"
        assert retrieval["keywords"], f"{name} missing retrieval keywords"
        assert "query_terms" not in retrieval
        assert "mode" not in retrieval
        assert "top_k" not in retrieval
        assert "fusion" not in retrieval
        assert "rerank" not in retrieval


def test_report_defaults_are_merged_before_building_retrieval_config():
    """生成侧应将 defaults.retrieval / defaults.validators 合并进单个占位符。"""
    section_config = {
        "defaults": {
            "query_mode": "retrieval_query_embedded",
            "validators": {
                "forbid_wind_data": True,
                "no_newline": True,
                "forbidden_phrases": ["根据文件"],
            },
            "retrieval": {
                "mode": "hybrid",
                "top_k": 8,
                "candidate_k": 50,
                "fusion": {
                    "method": "rrf",
                    "keyword_weight": 0.65,
                    "semantic_weight": 0.35,
                },
                "rerank": {"enabled": True, "provider": "llm", "top_n": 16},
            },
        }
    }
    placeholder_config = {
        "type": "prompt",
        "title": "航天",
        "retrieval": {"keywords": ["航天", "卫星"]},
    }

    merged = apply_report_defaults_to_placeholder(section_config, placeholder_config)
    retrieval_config = build_retrieval_config(merged, default_top_k=4)

    assert merged["query_mode"] == "retrieval_query_embedded"
    assert merged["validators"]["forbid_wind_data"] is True
    assert merged["validators"]["forbidden_phrases"] == ["根据文件"]
    assert retrieval_config.mode == "hybrid"
    assert retrieval_config.top_k == 8
    assert retrieval_config.candidate_k == 50
    assert retrieval_config.must_any == ["航天", "卫星"]
    assert retrieval_config.rerank_enabled is True
    assert retrieval_config.rerank_top_n == 16


def test_generation_constraints_and_writing_parameters_are_rendered_separately():
    """共用生成约束和单段写作参数应分层进入 prompt。"""
    config = {
        "generation_constraints": [
            "严格依据上传材料和 evidence，不添加外部知识或虚构数据",
            "生成一段正文，不输出换行符",
        ],
        "target_words": 250,
        "max_words": 320,
        "min_news_count": 5,
    }

    constraints = render_generation_constraints(config)
    writing_parameters = render_writing_parameters(config)

    assert "严格依据上传材料和 evidence" in constraints
    assert "生成一段正文，不输出换行符" in constraints
    assert "目标字数" not in constraints
    assert "至少使用" not in constraints
    assert "目标字数：约 250 字" in writing_parameters
    assert "最大字数：不超过 320 字" in writing_parameters
    assert "至少使用 5 条 evidence/news 信息" in writing_parameters


def test_market_hotspot_prompt_uses_component_structure_without_metadata():
    """A股市场回顾续写 prompt 应使用固定开头和后续结构，不暴露项目元信息。"""
    project = ReportProjectManager(projects_root=Path("report_projects")).get_project(
        "华安ETF周报"
    )
    template = build_market_template_for_test()
    config = {
        "generation_constraints": [
            "严格依据上传材料和 evidence，不添加外部知识或虚构数据",
            "生成一段正文，不输出换行符",
        ],
        "target_words": 250,
        "max_words": 320,
        "min_news_count": 5,
        "components": [
            {
                "name": "市场热点与趋势判断",
                "type": "llm_writing",
                "writing_structure": [
                    "接在固定开头之后，概括本周市场热点板块或概念",
                    "描述板块轮动特征",
                ],
            }
        ],
    }

    messages = build_market_hotspot_messages(
        project=project,
        placeholder="A股市场回顾",
        title="A股市场回顾",
        template=template,
        data_sentence=(
            "本周A股市场整体呈现分化趋势，主要指数表现不一：沪深300涨0.19%。"
            "交易面，A股市场本周日均成交额在2.40万亿左右，市场投资热情回落。"
        ),
        params={},
        max_words=320,
        config=config,
        evidence=[
            EvidenceSnippet(
                source="ingestion:news",
                title="热点",
                content="算力硬件、新能源和商业航天反复活跃。",
                published_at="2026-06-05",
            )
        ],
    )

    assert len(messages) == 1
    prompt = messages[0]["content"]
    assert prompt.index("生成约束：") < prompt.index("写作参数：")
    assert "固定开头：" in prompt
    assert "续写要求：" in prompt
    assert "接在固定开头之后，概括本周市场热点板块或概念" in prompt
    assert "请只输出固定开头之后的续写正文" in prompt
    assert "项目：" not in prompt
    assert "Word 占位符" not in prompt
    assert "段落标题" not in prompt
    assert "检索 Query" not in prompt
    assert "配置参数" not in prompt


def build_market_template_for_test():
    return PromptTemplateBlock(
        title="A股市场回顾",
        retrieval_query="请检索市场热点",
        writing_requirements="旧写作要求",
        raw_text="旧模板",
    )


def test_keyword_profiles_are_available_for_report_project_workbench():
    """项目详情应返回可复用关键词 profile，供新模板占位符初始化检索词。"""
    profiles = keyword_profiles_for_api()

    assert "人工智能" in profiles
    assert "AI" in profiles["人工智能"]["keywords"]
    assert profiles["人工智能"]["query"]
    assert profiles["人工智能"]["threshold"] > 0

    response = client.get("/api/report-projects/")
    assert response.status_code == 200
    projects = response.json()["projects"]
    assert projects
    assert "人工智能" in projects[0]["keyword_profiles"]


def test_missing_retrieval_keywords_are_filled_from_keyword_profile():
    """占位符未显式写关键词时，生成侧应从 keyword_profiles 继承检索关键词。"""
    config = {
        "title": "人工智能",
        "type": "prompt",
        "prompt_template": "人工智能",
        "retrieval": {"mode": "hybrid"},
    }

    enriched = apply_keyword_profile_to_config("人工智能", config)
    retrieval_config = build_retrieval_config(enriched, default_top_k=8)

    assert "人工智能" in retrieval_config.must_any
    assert "AI" in retrieval_config.must_any
    assert enriched["retrieval"]["keyword_profile"] == "人工智能"
    assert enriched["retrieval"]["keywords"]
    assert "query_terms" not in enriched["retrieval"]


def test_explicit_keyword_profile_fills_keywords_when_keywords_are_missing():
    """配置了 keyword_profile 但未写 keywords 时，应从指定 profile 展开关键词。"""
    config = {
        "title": "自定义标题",
        "type": "prompt",
        "retrieval": {"keyword_profile": "航天"},
    }

    enriched = apply_keyword_profile_to_config("自定义标题", config)
    retrieval_config = build_retrieval_config(enriched, default_top_k=8)

    assert "航天" in retrieval_config.must_any
    assert enriched["retrieval"]["keyword_profile"] == "航天"
    assert enriched["retrieval"]["keywords"]


def test_compute_report_period_uses_report_date_and_week_monday():
    """报告周期结束日取报告日，开始日取同周周一。"""
    period = compute_report_period("2026-06-05")

    assert period.start_date == "2026-06-01"
    assert period.end_date == "2026-06-05"


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


def write_market_review_xlsx(path: Path) -> None:
    """Write cached market data used by composite market review generation."""
    from openpyxl import Workbook

    workbook = Workbook()
    date_sheet = workbook.active
    date_sheet.title = "日期"
    date_sheet.append(["本周五", "上周五"])
    date_sheet.append(["2026-06-05", "2026-05-29"])

    domestic = workbook.create_sheet("国内")
    domestic.append(["指数代码", "指数名称", "周内涨跌幅"])
    domestic.append(["000300.SH", "沪深300", 0.86])
    domestic.append(["000905.SH", "中证500", 0.41])
    domestic.append(["000852.SH", "中证1000", -0.04])
    domestic.append(["399673.SZ", "创业板50", -0.42])
    domestic.append(["000688.SH", "科创50", 2.13])

    turnover = workbook.create_sheet("市场成交")
    turnover.append(["指数代码", "本周日均成交额", "上周日均成交额"])
    turnover.append(["000985.CSI", 2.55, 2.30])

    workbook.save(path)


def write_global_calendar_xlsx(path: Path) -> None:
    """Write a cached global economic calendar workbook."""
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "经济数据"
    sheet.append(["日期", "时间", "国家/地区", "指标名称", "重要性", "前值", "预测值", "今值"])
    sheet.append(["2026-06-15", "21:30", "美国", "6月纽约联储制造业指数", "重要", -9.2, None, None])
    sheet.append(["2026-06-16", "17:00", "欧盟", "5月欧元区CPI:同比", "重要", 2.2, None, None])
    sheet.append(["2026-06-17", "08:00", "日本", "低优先级指标", "一般", 1.0, None, None])
    workbook.save(path)


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
    (project_dir / "data" / "周报图表.xlsx").write_bytes(b"chart")
    (project_dir / "data" / "周报页眉.png").write_bytes(b"png")
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
    assert [asset["file_name"] for asset in project["data_assets"]] == [
        "创业板50周报（iFind版）.xlsx",
        "周报图表.xlsx",
        "domestic.json",
        "周报页眉.png",
    ]
    assert project["data_assets"][0]["kind"] == "primary_excel"
    assert project["data_assets"][1]["kind"] == "workbook"
    assert project["data_assets"][2]["kind"] == "query_json"
    assert project["data_assets"][3]["kind"] == "image"
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

    def fake_save_from_template(output_path, template_path, sections, placeholders, **kwargs):
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

        def retrieve(self, query, *, title, params, lookback_days, limit, report_period=None):
            self.query = query
            assert title == "人工智能"
            assert params == {"param": "人工智能"}
            assert lookback_days == 7
            assert report_period is not None
            assert report_period.start_date
            assert report_period.end_date
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


def test_generation_service_renders_structured_generation_constraints(tmp_path: Path):
    """字数、新闻条数和禁用规则应由 section_config 参数进入最终模型消息。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{A股市场回顾}}")
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
        def retrieve(self, query, **kwargs):
            return [
                EvidenceSnippet(
                    source="ingestion:news",
                    title="市场热点",
                    content="CPO、算力、先进封装、机器人和新能源方向均有新闻事实。",
                    published_at="2026-06-05",
                )
            ]

    class FakeGateway:
        def chat(self, messages, model=None, temperature=0.7, max_tokens=None, task=None, **kwargs):
            message = messages[-1]["content"]
            assert "生成约束：" in message
            assert "写作参数：" in message
            assert "目标字数：约 100 字" in message
            assert "最大字数：不超过 150 字" in message
            assert "至少使用 5 条 evidence/news 信息" in message
            assert "不得使用 Wind 数据" in message
            assert "不得使用日度数据" in message
            assert "使用数据或数值时必须说明来源" in message
            assert "生成一段正文，不输出换行符" in message
            assert "禁止出现这些短语：根据文件、据报道、数据显示" in message
            assert "禁止提及这些实体类别：指数名称、公司名称、证券机构、个股名称、ETF名称" in message
            assert "控制在 100-150 字" not in message
            return ModelResponse(
                content="本周市场热点依次为 CPO、算力、先进封装，板块呈现快速轮动特征。",
                model_name="deepseek-chat",
                provider="deepseek",
                tokens_used=88,
                latency_ms=120,
            )

    service = ReportProjectGenerationService(
        retriever=FakeRetriever(), model_gateway=FakeGateway()
    )

    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "A股市场回顾": {
                    "title": "A股市场回顾",
                    "type": "prompt",
                    "prompt_template": "A股市场回顾",
                    "target_words": 100,
                    "max_words": 150,
                    "min_news_count": 5,
                    "validators": {
                        "forbid_wind_data": True,
                        "forbid_daily_data": True,
                        "require_source_for_numbers": True,
                        "no_newline": True,
                        "forbidden_phrases": ["根据文件", "据报道", "数据显示"],
                        "forbid_entities": [
                            "指数名称",
                            "公司名称",
                            "证券机构",
                            "个股名称",
                            "ETF名称",
                        ],
                    },
                }
            }
        },
        prompt_templates_source=(
            "## A股市场回顾\n\n"
            "```text\n"
            "检索 Query：请基于上传的全部新闻内容，找出本周市场热点板块和概念。\n\n"
            "写作格式：本周市场热点依次为【列出市场热点板块/概念】。\n"
            "```"
        ),
    )

    assert "本周市场热点依次为 CPO、算力、先进封装" in result.placeholders["A股市场回顾"]


def test_generation_service_fills_report_period_placeholders(tmp_path: Path):
    """报告周期占位符应由生成上下文自动填充，不进入 LLM。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(
        project_dir / "templates" / "report_template.docx",
        "{{开始日期}} {{结束日期}}",
    )
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

    class FailRetriever:
        def retrieve(self, **kwargs):
            raise AssertionError("report_period placeholders should not retrieve evidence")

    class FailGateway:
        def chat(self, **kwargs):
            raise AssertionError("report_period placeholders should not call model")

    service = ReportProjectGenerationService(
        retriever=FailRetriever(), model_gateway=FailGateway()
    )

    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "开始日期": {"title": "开始日期", "type": "report_period", "field": "start_date"},
                "结束日期": {"title": "结束日期", "type": "report_period", "field": "end_date"},
            }
        },
        prompt_templates_source="",
        report_date="2026-06-05",
    )

    assert result.placeholders == {
        "开始日期": "2026-06-01",
        "结束日期": "2026-06-05",
    }


def test_generation_service_builds_composite_market_review_from_excel_and_evidence(
    tmp_path: Path,
):
    """A股市场回顾应先用 Excel 真实数据生成固定句，再用 evidence 生成热点句。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{A股市场回顾}}")
    write_market_review_xlsx(project_dir / "data" / "周报数据.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text(
        "placeholders: {}\n", encoding="utf-8"
    )
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                "name: 华安ETF周报",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/周报数据.xlsx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )
    project = ReportProjectManager(projects_root=tmp_path).get_project("华安ETF周报")

    class FakeRetriever:
        def retrieve(self, query, *, title, params, lookback_days, limit, report_period=None):
            assert "市场热点" in query
            assert title == "A股市场回顾"
            assert report_period is not None
            return [
                EvidenceSnippet(
                    source="ingestion:news",
                    title="CPO 新闻",
                    content="CPO、算力租赁和先进封装本周活跃，AI 光模块需求受到关注。",
                    published_at="2026-06-03",
                )
            ]

    class FakeGateway:
        def chat(self, messages, model=None, temperature=0.7, max_tokens=None, task=None, **kwargs):
            prompt = messages[-1]["content"]
            assert "固定开头：" in prompt
            assert "续写要求：" in prompt
            assert "请只输出固定开头之后的续写正文" in prompt
            assert "沪深300" in prompt
            return ModelResponse(
                content="本周市场热点依次为 CPO、算力租赁、先进封装，板块呈现快速轮动特征。",
                model_name="deepseek-chat",
                provider="deepseek",
                tokens_used=66,
                latency_ms=100,
            )

    service = ReportProjectGenerationService(
        retriever=FakeRetriever(), model_gateway=FakeGateway()
    )

    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "A股市场回顾": {
                    "title": "A股市场回顾",
                    "type": "composite_market_review",
                    "prompt_template": "A股市场回顾",
                    "data_source": {
                        "workbook": "周报数据.xlsx",
                        "domestic_sheet": "国内",
                        "turnover_sheet": "市场成交",
                    },
                    "max_words": 180,
                }
            }
        },
        prompt_templates_source=(
            "## A股市场回顾\n"
            "检索 Query：请基于上传的全部新闻内容，找出本周所有的市场热点板块和概念。\n\n"
            "写作要求：概括本周 A 股市场热点、板块轮动和风格变化。"
        ),
        report_date="2026-06-05",
    )

    content = result.placeholders["A股市场回顾"]
    assert "沪深300涨0.86%" in content
    assert "中证500涨0.41%" in content
    assert "中证1000跌0.04%" in content
    assert "创业板50跌0.42%" in content
    assert "科创50涨2.13%" in content
    assert "本周日均成交额在2.55万亿左右" in content
    assert "较上周放大" in content
    assert "本周市场热点依次为 CPO、算力租赁、先进封装" in content
    assert result.sections[0].prompt_template == "A股市场回顾"
    assert result.sections[0].evidence_count == 1


def test_filter_and_rank_evidence_applies_must_any_exclude_and_scores():
    """第一阶段检索配置应过滤明显无关 evidence，并按关键词相关度排序。"""
    snippets = [
        EvidenceSnippet(
            source="ingestion:cls",
            title="世贸组织：全球货物贸易保持韧性",
            content="人工智能相关电子元件需求上升。",
            published_at="2026-06-05",
        ),
        EvidenceSnippet(
            source="ingestion:zq",
            title="商业航天卫星应用政策落地",
            content="商业航天、卫星互联网和运载火箭产业化加速。",
            published_at="2026-06-05",
        ),
        EvidenceSnippet(
            source="ingestion:zq",
            title="私募基金监管新规",
            content="私募基金风险防范。",
            published_at="2026-06-05",
        ),
    ]

    ranked = filter_and_rank_evidence(
        snippets,
        RetrievalConfig(
            must_any=["商业航天", "卫星", "火箭"],
            exclude=["私募基金"],
            min_keyword_score=1.0,
        ),
    )

    assert [item.title for item in ranked] == ["商业航天卫星应用政策落地"]
    assert ranked[0].keyword_score >= 3
    assert ranked[0].matched_terms == ["商业航天", "卫星", "火箭"]


def test_build_retrieval_config_reads_nested_query_terms():
    """工作台生成的 retrieval.query_terms 配置应被生成器正确读取。"""
    config = {
        "retrieval": {
            "mode": "hybrid",
            "top_k": 6,
            "candidate_k": 30,
            "min_keyword_score": 1,
            "fusion": {
                "method": "rrf",
                "keyword_weight": 0.65,
                "semantic_weight": 0.35,
                "rrf_k": 50,
                "semantic_candidate_k": 80,
            },
            "rerank": {
                "enabled": True,
                "provider": "llm",
                "top_n": 12,
                "min_score": 40,
            },
            "query_terms": {
                "must_any": ["航天", "商业航天", "卫星"],
                "exclude": ["私募基金"],
            },
        }
    }

    retrieval_config = build_retrieval_config(config, default_top_k=8)

    assert retrieval_config.mode == "hybrid"
    assert retrieval_config.top_k == 6
    assert retrieval_config.candidate_k == 30
    assert retrieval_config.must_any == ["航天", "商业航天", "卫星"]
    assert retrieval_config.exclude == ["私募基金"]
    assert retrieval_config.min_keyword_score == 1
    assert retrieval_config.fusion_method == "rrf"
    assert retrieval_config.keyword_weight == 0.65
    assert retrieval_config.semantic_weight == 0.35
    assert retrieval_config.rrf_k == 50
    assert retrieval_config.semantic_candidate_k == 80
    assert retrieval_config.rerank_enabled is True
    assert retrieval_config.rerank_provider == "llm"
    assert retrieval_config.rerank_top_n == 12
    assert retrieval_config.min_rerank_score == 40


def test_build_retrieval_config_prefers_flat_keywords():
    """新工作台配置使用 retrieval.keywords，生成器应直接读取。"""
    config = {
        "retrieval": {
            "keywords": ["电力设备", "新能源", "光伏"],
            "query_terms": {"must_any": ["旧关键词"]},
        }
    }

    retrieval_config = build_retrieval_config(config, default_top_k=8)

    assert retrieval_config.must_any == ["电力设备", "新能源", "光伏"]


def test_hybrid_filter_and_rank_fuses_keyword_and_semantic_scores():
    """Hybrid 模式应记录语义分、融合分和排名，便于调试 evidence 来源。"""
    snippets = [
        EvidenceSnippet(
            source="ingestion:zq",
            title="商业航天卫星发射提速",
            content="商业航天和卫星互联网订单增加。",
            published_at="2026-06-06",
        ),
        EvidenceSnippet(
            source="ingestion:cls",
            title="海南打造火箭链和航天产业体系",
            content="火箭链、卫星链和航天+产业体系加快建设。",
            published_at="2026-06-05",
        ),
        EvidenceSnippet(
            source="ingestion:cls",
            title="消费电子新品发布",
            content="手机和耳机新品发布。",
            published_at="2026-06-05",
        ),
    ]

    ranked = filter_and_rank_evidence(
        snippets,
        RetrievalConfig(
            mode="hybrid",
            must_any=["商业航天", "卫星", "火箭", "航天"],
            semantic_weight=0.4,
            keyword_weight=0.6,
        ),
        query="商业航天 卫星 火箭",
    )

    assert [item.title for item in ranked] == [
        "商业航天卫星发射提速",
        "海南打造火箭链和航天产业体系",
    ]
    assert ranked[0].retrieval_rank == 1
    assert ranked[1].retrieval_rank == 2
    assert ranked[0].retrieval_score is not None
    assert ranked[0].semantic_score is not None
    assert ranked[0].retrieval_method == "hybrid_rrf"


def test_generation_service_reranks_evidence_with_llm(tmp_path: Path):
    """启用 rerank 后，应先取更多候选，再按模型返回顺序选入最终 prompt。"""
    project_dir = tmp_path / "华安ETF周报"
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()
    write_minimal_docx(project_dir / "templates" / "report_template.docx", "{{航天}}")
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
            self.limit = None

        def retrieve(
            self,
            query,
            *,
            title,
            params,
            lookback_days,
            limit,
            report_period=None,
            retrieval_config=None,
        ):
            self.limit = limit
            return [
                EvidenceSnippet(source="test", title="弱相关", content="行业泛泛而谈"),
                EvidenceSnippet(source="test", title="强相关", content="商业航天卫星火箭发射提速"),
                EvidenceSnippet(source="test", title="一般相关", content="航天产业政策更新"),
            ]

    class FakeGateway:
        def __init__(self):
            self.calls = []

        def chat(self, messages, model=None, temperature=0.7, max_tokens=None, task=None, **kwargs):
            self.calls.append(messages)
            if "证据候选" in messages[-1]["content"]:
                return ModelResponse(
                    content='[{"index":2,"score":96,"reason":"最贴合商业航天"}, {"index":3,"score":62,"reason":"产业政策相关"}]',
                    model_name="deepseek-chat",
                    provider="deepseek",
                    tokens_used=30,
                    latency_ms=1.0,
                )
            return ModelResponse(
                content="重排后生成正文",
                model_name="deepseek-chat",
                provider="deepseek",
                tokens_used=50,
                latency_ms=1.0,
            )

    retriever = FakeRetriever()
    gateway = FakeGateway()
    service = ReportProjectGenerationService(retriever=retriever, model_gateway=gateway)

    result = service.generate_placeholders(
        project=project,
        section_config={
            "placeholders": {
                "航天": {
                    "title": "航天",
                    "prompt_template": "航天",
                    "evidence_limit": 1,
                    "retrieval": {
                        "mode": "hybrid",
                        "top_k": 1,
                        "rerank": {"enabled": True, "provider": "llm", "top_n": 3},
                    },
                }
            }
        },
        prompt_templates_source="## 航天\n检索 Query：商业航天 卫星 火箭\n写作要求：简洁",
        report_date="2026-06-05",
    )

    assert retriever.limit == 3
    assert result.placeholders["航天"] == "重排后生成正文"
    assert result.sections[0].evidence_count == 1
    assert result.sections[0].evidence[0].title == "强相关"
    assert result.sections[0].evidence[0].rerank_rank == 1
    assert result.sections[0].evidence[0].rerank_score == 96
    assert result.sections[0].evidence[0].rerank_reason == "最贴合商业航天"


def test_generation_service_generates_independent_prompt_sections_concurrently(tmp_path: Path):
    """多个普通 prompt section 应按有界并发生成，并保持输出顺序稳定。"""
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
        def retrieve(self, query, *, title, params, lookback_days, limit, report_period=None):
            return [EvidenceSnippet(source="test", title=title, content=f"{title} evidence")]

    class ConcurrentGateway:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def chat(self, messages, model=None, temperature=0.7, max_tokens=None, task=None, **kwargs):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)
            try:
                time.sleep(0.05)
                title = messages[1]["content"].split("段落标题：", 1)[1].split("\n", 1)[0]
                return ModelResponse(
                    content=f"{title}正文",
                    model_name="deepseek-chat",
                    provider="deepseek",
                    tokens_used=10,
                    latency_ms=50,
                )
            finally:
                with self.lock:
                    self.active -= 1

    gateway = ConcurrentGateway()
    service = ReportProjectGenerationService(
        retriever=FakeRetriever(),
        model_gateway=gateway,
        max_parallel_sections=4,
    )
    placeholders = {
        f"段落{i}": {
            "title": f"段落{i}",
            "type": "prompt",
            "prompt_template": f"段落{i}",
        }
        for i in range(1, 5)
    }

    result = service.generate_placeholders(
        project=project,
        section_config={"placeholders": placeholders},
        prompt_templates_source="\n\n".join(
            f"## 段落{i}\n检索 Query：段落{i}\n\n写作要求：短句" for i in range(1, 5)
        ),
    )

    assert gateway.max_active > 1
    assert list(result.placeholders) == ["段落1", "段落2", "段落3", "段落4"]
    assert [section.placeholder for section in result.sections] == [
        "段落1",
        "段落2",
        "段落3",
        "段落4",
    ]


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
    write_global_calendar_xlsx(project_dir / "data" / "全球经济日历.xlsx")
    (project_dir / "config" / "section_config.yaml").write_text(
        "\n".join(
            [
                "placeholders:",
                "  人工智能:",
                "    title: 人工智能",
                "    prompt_template: 人工智能",
                "tables:",
                "  global_investment_calendar:",
                "    title: 下周全球投资日历",
                "    enabled: true",
                "    placeholder: 下周全球投资日历",
                "    workbook: 全球经济日历.xlsx",
                "    sheet: 经济数据",
                "    columns:",
                "      - 日期",
                "      - 国家/地区",
                "      - 指标名称",
                "    filter:",
                "      column: 重要性",
                "      equals: 重要",
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
            assert kwargs["report_date"] == "2026-06-05"
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
                        evidence=[
                            EvidenceSnippet(
                                source="ingestion:cls",
                                title="AI 新闻",
                                content="AI 产业链本周有新增证据。",
                                published_at="2026-06-05",
                                keyword_score=3.0,
                                semantic_score=0.8,
                                retrieval_score=0.02,
                                retrieval_rank=1,
                                retrieval_method="hybrid_rrf",
                                rerank_score=90.0,
                                rerank_rank=1,
                                rerank_reason="相关",
                                matched_terms=["AI"],
                            )
                        ],
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

    def fake_save_from_template(output_path, template_path, sections, placeholders, **kwargs):
        captured["placeholders"] = placeholders
        captured["tables"] = kwargs["tables"]
        output_path.write_bytes(b"rendered")

    with patch(
        "reporting.projections.word.WordProjection.save_from_template",
        side_effect=fake_save_from_template,
    ):
        response = client.post(
            "/api/report-projects/华安ETF周报/render",
            json={"report_date": "2026-06-05"},
        )

    assert response.status_code == 200
    data = response.json()
    assert captured["placeholders"] == {"人工智能": "AI 生成段落"}
    assert captured["tables"][0].title == "下周全球投资日历"
    assert captured["tables"][0].headers == ["日期", "国家/地区", "指标名称"]
    assert captured["tables"][0].rows == [
        ["2026-06-15", "美国", "6月纽约联储制造业指数"],
        ["2026-06-16", "欧盟", "5月欧元区CPI:同比"],
    ]
    assert data["generated_placeholder_count"] == 1
    assert data["evidence_count"] == 2
    assert data["run_log_url"].startswith("/api/report-projects/华安ETF周报/runs/")
    assert "图表缓存数值全为 0" in data["warnings"][0]
    run_files = list((project_dir / "runs").glob("*.json"))
    assert len(run_files) == 1
    run_record = json.loads(run_files[0].read_text(encoding="utf-8"))
    assert run_record["generation"]["sections"][0]["provider"] == "deepseek"
    assert run_record["generation"]["sections"][0]["retrieval_query"] == "AI"
    assert run_record["generation"]["sections"][0]["evidence"][0] == {
        "source": "ingestion:cls",
        "title": "AI 新闻",
        "content": "AI 产业链本周有新增证据。",
        "published_at": "2026-06-05",
        "url": None,
        "keyword_score": 3.0,
        "semantic_score": 0.8,
        "retrieval_score": 0.02,
        "retrieval_rank": 1,
        "retrieval_method": "hybrid_rrf",
        "rerank_score": 90.0,
        "rerank_rank": 1,
        "rerank_reason": "相关",
        "matched_terms": ["AI"],
    }
    assert run_record["charts"][0]["chart_id"] == "industry_weekly_performance"
    assert run_record["tables"][0] == {
        "table_id": "global_investment_calendar",
        "title": "下周全球投资日历",
        "workbook": "全球经济日历.xlsx",
        "sheet": "经济数据",
        "row_count": 2,
        "warnings": [],
    }
    assert run_record["report_period"] == {
        "start_date": "2026-06-01",
        "end_date": "2026-06-05",
    }

    run_response = client.get(data["run_log_url"])
    assert run_response.status_code == 200
    assert run_response.json()["generation"]["sections"][0]["evidence"][0]["title"] == "AI 新闻"


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
    assert "charset=utf-8" in response.headers["content-type"]
    assert '<meta charset="utf-8">' in response.text
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
