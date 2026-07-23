"""Tests for report project folder management."""

from pathlib import Path

import pytest

from reporting.projects.project_manager import ReportProjectManager


def write_project(root: Path, name: str = "创业板50周报") -> Path:
    """Create a minimal report project folder for tests."""
    project_dir = root / name
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "data").mkdir()
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()

    (project_dir / "templates" / "report_template.docx").write_bytes(b"docx")
    (project_dir / "data" / "cyb50.xlsx").write_bytes(b"xlsx")
    (project_dir / "data" / "domestic.json").write_text("{}", encoding="utf-8")
    (project_dir / "config" / "section_config.yaml").write_text(
        "sections:\n- key: market_summary\n  title: 市场概览\n",
        encoding="utf-8",
    )
    (project_dir / "config" / "prompt_templates.md").write_text("前缀提示词", encoding="utf-8")
    (project_dir / "generated" / "2026-06-05_创业板50周报.docx").write_bytes(b"report")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                "active_word_template: templates/report_template.docx",
                "active_excel_workbook: data/cyb50.xlsx",
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
    return project_dir


def write_ppt_project(root: Path, name: str = "静态PPT模板") -> Path:
    """Create a minimal PPT report project folder for tests."""
    project_dir = root / name
    (project_dir / "templates").mkdir(parents=True)
    (project_dir / "config").mkdir()
    (project_dir / "generated").mkdir()
    (project_dir / "runs").mkdir()

    (project_dir / "templates" / "report_template.pptx").write_bytes(b"pptx")
    (project_dir / "config" / "section_config.yaml").write_text(
        "placeholders:\n  title:\n    type: static\n    value: 月度报告\n",
        encoding="utf-8",
    )
    (project_dir / "generated" / "2026-06-05_静态PPT模板.pptx").write_bytes(b"deck")
    (project_dir / "project.yaml").write_text(
        "\n".join(
            [
                f"name: {name}",
                "project_type: ppt",
                "active_ppt_template: templates/report_template.pptx",
                "section_config: config/section_config.yaml",
                "output_dir: generated",
                "run_log_dir: runs",
            ]
        ),
        encoding="utf-8",
    )
    return project_dir


def test_list_projects_reads_project_folder_assets(tmp_path: Path):
    """项目清单应从每个子文件夹读取 Word、Excel、配置和历史报告。"""
    project_dir = write_project(tmp_path)
    manager = ReportProjectManager(projects_root=tmp_path)

    projects = manager.list_projects()

    assert len(projects) == 1
    project = projects[0]
    assert project.name == "创业板50周报"
    assert project.slug == "创业板50周报"
    assert project.project_dir == project_dir
    assert project.word_template_path == project_dir / "templates" / "report_template.docx"
    assert project.excel_workbook_path == project_dir / "data" / "cyb50.xlsx"
    assert project.section_config_path == project_dir / "config" / "section_config.yaml"
    assert project.prompt_templates_path == project_dir / "config" / "prompt_templates.md"
    assert project.data_source_paths == [project_dir / "data" / "domestic.json"]
    assert project.generated_reports == [project_dir / "generated" / "2026-06-05_创业板50周报.docx"]
    assert project.project_type == "word"
    assert project.template_path == project.word_template_path


def test_list_projects_reads_ppt_project_assets(tmp_path: Path):
    """PPT 项目应解析 PPT 模板并只列出 pptx 生成产物。"""
    project_dir = write_ppt_project(tmp_path)
    manager = ReportProjectManager(projects_root=tmp_path)

    project = manager.list_projects()[0]

    assert project.name == "静态PPT模板"
    assert project.project_type == "ppt"
    assert project.ppt_template_path == project_dir / "templates" / "report_template.pptx"
    assert project.template_path == project.ppt_template_path
    assert project.word_template_path == project_dir
    assert project.generated_reports == [project_dir / "generated" / "2026-06-05_静态PPT模板.pptx"]


def test_get_project_raises_for_unknown_project(tmp_path: Path):
    """未知项目应明确报错，避免前端显示半绑定状态。"""
    write_project(tmp_path)
    manager = ReportProjectManager(projects_root=tmp_path)

    with pytest.raises(FileNotFoundError):
        manager.get_project("不存在的项目")


def test_bootstrap_cyb50_project_package_copies_confirmed_assets(tmp_path: Path):
    """创业板50默认项目包使用 report_template.docx 和 Excel 数据底稿。"""
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    (source_dir / "创业板50周报模板.docx").write_bytes(b"docx")
    (source_dir / "创业板50周报（iFind版）.xlsx").write_bytes(b"ifind")
    (source_dir / "创业板50周报（Wind版）.xlsx").write_bytes(b"wind")
    (source_dir / "创业板50周报模板.yaml").write_text(
        "name: 创业板50周报模板\nsections:\n- key: market_summary\n  title: 市场概览\n",
        encoding="utf-8",
    )
    manager = ReportProjectManager(projects_root=tmp_path / "report_projects")

    project = manager.bootstrap_cyb50_project(source_dir=source_dir)

    assert project.name == "创业板50周报"
    assert project.word_template_path.name == "report_template.docx"
    assert project.word_template_path.read_bytes() == b"docx"
    assert project.excel_workbook_path.name == "创业板50周报（iFind版）.xlsx"
    assert project.excel_workbook_path.read_bytes() == b"ifind"
    assert (project.project_dir / "data" / "创业板50周报（Wind版）.xlsx").read_bytes() == b"wind"
    assert project.section_config_path.name == "section_config.yaml"
