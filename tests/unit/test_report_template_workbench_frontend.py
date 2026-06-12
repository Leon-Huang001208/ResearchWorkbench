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
    assert 'id="template-placeholder-detail-form"' in html
    assert 'id="btn-template-save-placeholder"' in html
    assert 'id="template-selected-placeholder-title"' in html
    assert 'id="template-source-editor"' in html
    assert 'id="btn-template-source-section"' in html
    assert 'id="btn-template-source-prompt"' in html
    assert 'id="template-excel-mapping"' in html
    assert 'id="template-validation-preview"' in html
    assert 'id="btn-template-save-source"' in html
    assert 'id="btn-template-edit-source"' in html
    assert "readonly" in html
    assert 'id="btn-template-generate-report"' in html
    assert 'id="btn-template-download-report"' in html
    assert 'id="btn-back-to-templates" class="btn-secondary" onclick="goBackToTemplates()"' in html
    assert 'id="btn-edit-templates" class="iphone-nav-btn" onclick="toggleEditMode()"' in html
    assert (
        'id="btn-new-template" class="iphone-nav-btn iphone-upload-btn" onclick="openUploadModal()"'
        in html
    )
    assert 'id="project-word-template-input"' in html
    assert 'id="project-excel-workbook-input"' in html
    assert 'id="project-section-config-input"' in html
    assert 'id="project-prompt-templates-input"' in html
    assert 'id="project-data-files-input"' in html
    assert 'class="tabs template-legacy-tabs hidden"' in html
    assert "占位符配置详情" in html
    assert "当前片段源码" in html
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
    assert 'onpointerdown="handleTemplatePointerDown(event)"' in source
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
    assert "selectWorkbenchPlaceholder" in source
    assert "renderSelectedPlaceholderEditor" in source
    assert "saveSelectedPlaceholderConfig" in source
    assert "buildSelectedPlaceholderYaml" in source
    assert "replacePlaceholderYamlBlock" in source
    assert "template-placeholder-detail-form" in source
    assert "btn-template-save-placeholder" in source
    assert "run_log_url" in source
    assert "loadRenderedReportEvidence" in source
    assert "Evidence 检索调试" in source
    assert "Rerank" in source
    assert "rerank_score" in source
    assert "rerank_reason" in source


def test_report_workbench_uses_report_project_real_asset_summary():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "getTemplateWorkbenchSections" in source
    assert "getTemplateWorkbenchPlaceholders" in source
    assert "project?.word_placeholders" in source
    assert "project?.section_config?.sections" in source
    assert "project?.section_config_source" in source
    assert "project?.prompt_templates_source" in source
    assert "getTemplateWorkbenchSource" in source
    assert "buildPlaceholderMappingConfigYaml" in source
    assert "getPlaceholderMappings" in source
    assert "placeholder_mappings" not in source
    assert "placeholders:" in source
    assert "setTemplateSourceEditing" in source
    assert "/source" in source
    assert "source_kind" in source
    assert "project?.excel_sheets" in source
    assert "buildCyb50ExcelMappingRows" not in source


def test_placeholder_editor_exposes_only_per_placeholder_generation_fields():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "placeholder-field-type" in source
    assert "placeholder-field-target-words" in source
    assert "placeholder-field-max-words" in source
    assert "placeholder-field-min-news-count" in source
    assert "placeholder-field-keyword-profile" in source
    assert "placeholder-field-keywords" in source
    assert "placeholder-field-must-any" not in source
    assert "placeholder-field-forbid-wind-data" not in source
    assert "placeholder-field-forbid-daily-data" not in source
    assert "placeholder-field-require-source-for-numbers" not in source
    assert "placeholder-field-no-newline" not in source
    assert "placeholder-field-forbidden-phrases" not in source
    assert "placeholder-field-forbid-entities" not in source
    assert "placeholder-field-retrieval-mode" not in source
    assert "placeholder-field-top-k" not in source
    assert "placeholder-field-candidate-k" not in source
    assert "placeholder-field-semantic-candidate-k" not in source
    assert "placeholder-field-exclude" not in source
    assert "检索关键词（逗号或换行分隔）" in source
    assert "排除词（逗号或换行分隔）" not in source
    assert "placeholder-field-rerank-enabled" not in source
    assert "placeholder-field-rerank-top-n" not in source
    assert "placeholder-field-rerank-min-score" not in source


def test_placeholder_editor_hides_derived_title_and_prompt_template_fields():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "placeholder-field-title" not in source
    assert "placeholder-field-prompt-template" not in source
    assert "title: original.title || inferPlaceholderTitle(selectedName)" in source
    assert (
        "const promptTemplate = original.prompt_template || resolvePromptTemplateName(selectedName, template.report_project || null);"
        in source
    )


def test_workbench_keeps_section_mapping_and_prompt_source_separate():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "btn-template-source-section" in source
    assert "btn-template-source-prompt" in source
    assert "switchTemplateSourceKind" in source
    assert "activeSourceKind" in source
    assert "Markdown Prompt" in source
    assert "YAML 当前占位符片段" in source


def test_prompt_preview_supports_writing_format_and_strips_code_fences():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "stripPromptCodeFence" in source
    assert "extractPromptLabel(body, '写作格式')" in source
    assert "写作要求|写作格式" in source


def test_placeholder_form_does_not_duplicate_prompt_preview():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert '<div class="placeholder-detail-section-title">Prompt / Query</div>' not in source
    assert "placeholder-prompt-preview" not in source
    assert "当前片段源码" in INDEX_HTML.read_text(encoding="utf-8")


def test_placeholder_form_hides_fields_that_do_not_apply_to_selected_type():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "updatePlaceholderFieldVisibility" in source
    assert 'data-visible-for="prompt composite_market_review"' in source
    assert 'data-visible-for="report_period"' in source
    assert 'data-visible-for="static_text excel_cell excel_range"' in source
    assert "placeholder-detail-field-hidden" in source


def test_workbench_uses_current_placeholder_mapping_draft_for_status():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "getStoredPlaceholderMappings" in source
    assert "buildDraftPlaceholderMappings" in source
    assert "getCurrentPlaceholderMappings" in source
    assert "const placeholderMappings = getCurrentPlaceholderMappings(template);" in source
    assert (
        "const placeholderMappings = getCurrentPlaceholderMappings(getCurrentWorkbenchTemplate() || {});"
        in source
    )


def test_placeholder_map_does_not_truncate_word_placeholders():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "names.map(name =>" in source
    assert "names.slice(0, 8)" not in source


def test_placeholder_mapping_connects_word_prompt_and_query_source():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "resolvePromptTemplateName" in source
    assert "inferQuerySource" in source
    assert "buildKeywordRetrievalDraft" in source
    assert "resolveKeywordProfileForPlaceholder" in source
    assert "keyword_profiles" in source
    assert "keyword_profile" in source
    assert "keywords" in source
    assert (
        "prompt_template: ${mapping.prompt_template || resolvePromptTemplateName(key, project)}"
        in source
    )
    assert "query_source: ${mapping.query_source || inferQuerySource(key, project)}" in source
    assert "renderMappingSummary" in source
    assert "prompt_template" in source
    assert "query_source" in source


def test_embedded_query_mode_uses_prompt_template_without_json_source():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "usesEmbeddedPromptQueries" in source
    assert "query_mode: retrieval_query_embedded" in source
    assert "检索 Query: 模板内置" in source
    assert "resolvePromptTemplateName(key, project)" in source
    assert "if (!usesEmbeddedPromptQueries(project)) {" in source


def test_prompt_template_view_uses_generated_library_when_reference_is_raw():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "buildPromptTemplateLibraryMarkdown" in source
    assert "shouldUsePromptTemplateLibraryDraft" in source
    assert "Markdown Prompt（模板库草稿）" in source


def test_report_project_placeholders_skip_legacy_template_placeholder_api():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "currentTemplateState.selectedReportProject?.word_placeholders" in source
    assert "使用项目包解析出的 Word 占位符" in source


def test_template_cards_do_not_reference_module_state_inline():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert 'onclick="selectTemplate(' in source
    assert 'onclick="!isEditMode' not in source


def test_template_upload_action_lives_in_top_toolbar():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert '<div class="iphone-dock">' not in html
    assert 'class="iphone-dock-item"' not in html
    assert ".iphone-dock" not in css
    assert ".iphone-dock-item" not in css
    assert ".iphone-upload-btn" in css


def test_report_template_workbench_styles_exist():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".template-workbench-main-grid" in css
    assert ".template-section-editor-panel .template-source-editor" in css
    assert ".template-section-editor-panel {\n    display: flex" in css
    assert "min-height: calc(100vh - 260px)" in css
    assert "flex: 1 1 420px" in css
    assert ".template-source-editor" in css
    assert ".template-mapping-table" in css
    assert "iphone-icon-wiggle" not in css
    assert ".iphone-template-wrapper.dragging .iphone-app-icon" in css
    assert ".iphone-template-wrapper.dragging" in css
    assert "position: fixed" in css
    assert ".iphone-template-name-input" in css
    assert ".evidence-debug-shell" in css
    assert ".evidence-debug-section" in css


def test_template_detail_icon_follows_active_color_scheme():
    css = STYLE_CSS.read_text(encoding="utf-8")

    detail_icon_block = css.split(".template-icon-large {", 1)[1].split("}", 1)[0]
    assert "background: var(--accent);" in detail_icon_block
    assert ".template-icon-large.docx" not in css
    assert ".template-icon-large.pptx" not in css
    assert ".template-icon-large.excel" not in css
