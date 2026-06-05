"""Static wiring tests for the report template workbench frontend."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
TEMPLATES_JS = ROOT / "app" / "web" / "static" / "js" / "templates.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"


def test_template_detail_has_report_workbench_regions():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-workbench-summary"' in html
    assert 'id="template-section-config-editor"' in html
    assert 'id="template-source-editor"' in html
    assert 'id="template-excel-mapping"' in html
    assert 'id="template-validation-preview"' in html
    assert 'id="btn-template-save-source"' in html
    assert 'id="btn-template-generate-report"' in html
    assert 'id="btn-template-download-report"' in html
    assert 'id="btn-back-to-templates" class="btn-secondary" onclick="goBackToTemplates()"' in html
    assert 'id="btn-edit-templates" class="iphone-nav-btn" onclick="toggleEditMode()"' in html
    assert 'id="btn-new-template" class="iphone-dock-item" onclick="openUploadModal()"' in html
    assert 'id="project-word-template-input"' in html
    assert 'id="project-excel-workbook-input"' in html
    assert 'id="project-section-config-input"' in html
    assert 'id="project-prompt-templates-input"' in html
    assert 'id="project-data-files-input"' in html
    assert 'class="tabs template-legacy-tabs hidden"' in html
    assert "Section 配置源码" in html
    assert "Excel 底稿映射" in html


def test_templates_js_populates_report_workbench():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderTemplateWorkbench" in source
    assert "loadReportProjectsList" in source
    assert "/api/report-projects/" in source
    assert "/api/report-projects/upload" in source
    assert "mergeTemplatesWithReportProjects" in source
    assert "renderReportProject" in source
    assert "saveTemplateInlineName" in source
    assert "/api/report-projects/${encodeURIComponent(project.slug)}" in source
    assert "iphone-template-name-input" in source
    assert "handleTemplatePointerDown" in source
    assert "onpointerdown=\"handleTemplatePointerDown(event)\"" in source
    assert "pointerDragState" in source
    assert "download_url" in source
    assert "buildTemplateConfigYaml" in source
    assert "buildExcelMappingRows" in source
    assert "report_project" in source
    assert "forbidden_terms" in source
    assert "investment_advice_policy" in source
    assert "template-source-editor" in source
    assert "btn-template-generate-report" in source
    assert "btn-template-download-report" in source


def test_report_workbench_uses_report_project_real_asset_summary():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "getTemplateWorkbenchSections" in source
    assert "getTemplateWorkbenchPlaceholders" in source
    assert "project?.word_placeholders" in source
    assert "project?.section_config?.sections" in source
    assert "project?.section_config_source" in source
    assert "project?.excel_sheets" in source
    assert "buildCyb50ExcelMappingRows" not in source


def test_report_project_placeholders_skip_legacy_template_placeholder_api():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "currentTemplateState.selectedReportProject?.word_placeholders" in source
    assert "使用项目包解析出的 Word 占位符" in source


def test_template_cards_do_not_reference_module_state_inline():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert 'onclick="selectTemplate(' in source
    assert "onclick=\"!isEditMode" not in source


def test_report_template_workbench_styles_exist():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".template-workbench-main-grid" in css
    assert ".template-section-editor-panel .template-source-editor" in css
    assert ".template-section-editor-panel {\n    display: flex" in css
    assert "flex: 1 1 auto" in css
    assert ".template-source-editor" in css
    assert ".template-mapping-table" in css
    assert "iphone-icon-wiggle" not in css
    assert ".iphone-template-wrapper.dragging .iphone-app-icon" in css
    assert ".iphone-template-wrapper.dragging" in css
    assert "position: fixed" in css
    assert ".iphone-template-name-input" in css
