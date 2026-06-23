"""Static wiring tests for the report template workbench frontend."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
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
    assert 'id="btn-template-download-report"' not in html
    assert 'id="btn-template-preview-report"' not in html
    assert 'id="btn-template-open-output-folder"' not in html
    assert 'data-template-report-action="preview"' in html
    assert 'data-template-report-action="folder"' in html
    assert 'data-template-report-action="download"' in html
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


def test_report_workbench_uses_separate_generation_preview_log_tabs_without_changing_config():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-template-detail-mode="generation">生成<' in html
    assert 'data-template-detail-mode="config">配置<' in html
    assert 'data-template-detail-mode="preview">预览<' in html
    assert 'data-template-detail-mode="logs">日志<' not in html
    assert 'id="btn-template-show-run-log"' in html
    assert 'data-template-detail-mode="both"' not in html
    assert 'id="template-generation-workflow"' in html
    assert 'id="template-generation-preview-panel"' in html
    assert 'id="template-generation-log-panel"' in html
    assert 'id="btn-template-open-output-folder"' not in html

    # The config tab stays on the original parameter editor structure.
    assert 'id="template-advanced-maintenance" data-template-detail-panel="config" open' in html
    assert 'class="template-workbench-main-grid"' in html
    assert 'id="template-common-rules"' in html
    assert 'id="template-placeholder-map"' in html
    assert 'id="template-placeholder-detail-form"' in html
    assert 'id="btn-template-save-placeholder"' in html


def test_report_generation_page_is_reduced_to_progress_and_single_output():
    html = INDEX_HTML.read_text(encoding="utf-8")

    generation = html.split('id="template-generation-overview"', 1)[1].split(
        'id="template-advanced-maintenance"', 1
    )[0]

    assert 'id="template-generation-flow-list"' in generation
    assert 'id="template-recent-generation-panel"' in generation
    assert generation.count('id="template-recent-generation-panel"') == 1
    assert 'template-generation-step-panel' not in generation
    assert 'id="template-generation-param-grid"' not in generation
    assert 'template-generation-prompt-summary' not in generation
    assert 'template-generation-live-events' not in generation
    assert 'id="template-project-check-details"' not in generation
    assert '生成前检查' not in generation


def test_templates_js_populates_report_workbench():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderReportGenerationCenter" in source
    assert "renderGenerationHero" in source
    assert "renderGenerationStepContext" in source
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
    assert "selectedGeneratedReportFile" in source
    assert "selectGeneratedReport" in source
    assert "data-template-generated-report" in source
    assert "data-template-report-action" in source
    assert "btn-template-download-report" not in source
    assert "data-template-open-preview" not in source
    assert "data-template-open-output-folder" not in source
    assert "data-template-preview-open-folder" not in source
    assert "selectTemplatePlaceholder" in source
    assert "renderSelectedPlaceholderDetail" in source
    assert "renderSelectedSourceFragment" in source
    assert "buildSelectedPlaceholderYamlFragment" in source
    assert "buildUpdatedSectionConfigSource" in source
    assert "template-placeholder-detail-form" in source
    assert "btn-template-save-placeholder" in source
    assert "run_log_url" in source
    assert "lastReportRunLog" in source
    assert "buildTemplateLogRows" in source
    assert "evidence_count" in source


def test_templates_js_separates_report_generation_preview_logs_and_output_folder_action():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "['generation', 'config', 'preview', 'logs']" in source
    assert "template-generation-preview-panel" in source
    assert "template-generation-log-panel" in source
    assert "renderTemplatePreviewPanel" in source
    assert "renderTemplateLogPanel" in source
    assert "openReportProjectOutputFolder" in source
    assert "/open-folder" in source
    assert "openReportProjectOutputFolder(project.slug, selectedReport.file_name)" in source
    assert "?file_name=${encodeURIComponent(fileName)}" in source
    assert "data-template-report-action=\"folder\"" in INDEX_HTML.read_text(encoding="utf-8")
    assert "selectedGeneratedReportFile" in source
    assert "btn-template-show-run-log" in source


def test_report_generation_history_scrolls_inside_output_panel():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "#template-recent-generation-panel" in css
    assert ".template-recent-generation-card" in css
    assert ".template-generated-report-list" in css
    assert "overflow-y: auto" in css
    assert "max-height: clamp(" in css
    assert "scrollbar-gutter: stable" in css


def test_templates_list_keeps_report_projects_when_legacy_template_api_fails():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "let templateData = { templates: [] };" in source
    assert "Failed to load legacy templates" in source
    assert "mergeTemplatesWithReportProjects(" in source
    assert "templateData.templates || []" in source
    assert "currentTemplateState.reportProjects || []" in source
    assert "document.getElementById('templates-grid')" in source
    assert "document.getElementById('template-list')" not in source


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

    assert 'data-placeholder-field="type"' in source
    assert 'data-placeholder-field="target_words"' in source
    assert 'data-placeholder-field="max_words"' in source
    assert 'data-placeholder-field="min_news_count"' in source
    assert 'data-placeholder-field="retrieval.keyword_profile_select"' in source
    assert 'data-placeholder-field="retrieval.custom_keywords"' in source
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
    assert "自定义关键词（一行一个）" in source
    assert "排除词（逗号或换行分隔）" not in source
    assert "placeholder-field-rerank-enabled" not in source
    assert "placeholder-field-rerank-top-n" not in source
    assert "placeholder-field-rerank-min-score" not in source


def test_placeholder_editor_keeps_derived_fields_in_advanced_drawer():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "placeholder-field-title" not in source
    assert "placeholder-field-prompt-template" not in source
    assert 'id="template-advanced-placeholder-form"' in html
    assert 'id="btn-template-advanced-config"' in html
    assert "draft.title = draft.title || inferPlaceholderTitle(name);" in source
    assert 'data-placeholder-field="title"' in source
    assert 'data-placeholder-field="prompt_template"' in source
    assert "resolvePromptTemplateName(name, template.report_project)" in source


def test_workbench_keeps_section_mapping_and_prompt_source_separate():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "btn-template-source-section" in source
    assert "btn-template-source-prompt" in source
    assert "switchTemplateSourceKind" in source
    assert "activeSourceKind" in source
    assert "Markdown Prompt" in source
    assert "YAML 占位符映射" in source
    assert "buildSelectedPlaceholderYamlFragment" in source
    assert "buildUpdatedPromptTemplatesSource" in source


def test_prompt_template_preview_supports_retrieval_query_and_strips_code_fences():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "stripMarkdownCodeFence" in source
    assert "extractPromptTemplateLabel" in source
    assert "getPromptTemplateBlock" in source
    assert "replacePromptTemplateLabel" in source
    assert "检索 Query" in source


def test_placeholder_form_does_not_duplicate_prompt_preview():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert '<div class="placeholder-detail-section-title">Prompt / Query</div>' not in source
    assert "placeholder-prompt-preview" not in source
    assert "当前片段源码" in INDEX_HTML.read_text(encoding="utf-8")


def test_placeholder_form_hides_fields_that_do_not_apply_to_selected_type():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "buildSimplePlaceholderFieldsHtml" in source
    assert "if (isPromptLike)" in source
    assert "if (type === 'excel_commodity_market_review')" in source
    assert "if (type === 'report_period')" in source
    assert "if (type === 'excel_cell' || type === 'excel_range')" in source
    assert "if (type === 'static_text')" in source
    assert 'data-visible-for="' not in source
    assert "placeholder-detail-field-hidden" not in source


def test_workbench_uses_current_placeholder_mapping_draft_for_status():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "getStoredPlaceholderMappings" in source
    assert "buildDraftPlaceholderMappings" in source
    assert "getCurrentPlaceholderMappings" in source
    assert "const mappings = getCurrentPlaceholderMappings(template);" in source
    assert "getEditablePlaceholderMappings(template)" in source
    assert "currentTemplateState.placeholderMappingDrafts" in source


def test_placeholder_map_does_not_truncate_word_placeholders():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "names.map(name =>" in source
    assert "names.slice(0, 8)" not in source


def test_placeholder_mapping_connects_word_prompt_and_query_source():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "resolvePromptTemplateName" in source
    assert "inferQuerySource" in source
    assert "applyKeywordModeDraft" in source
    assert "getSelectedKeywordProfileName" in source
    assert "inferKeywordMode" in source
    assert "keyword_profiles" in source
    assert "keyword_profile" in source
    assert "keywords" in source
    assert "prompt_template: type === 'prompt' ? resolvePromptTemplateName(key, project) : undefined" in source
    assert "query_source: type === 'prompt' && !usesEmbeddedPromptQueries(project) ? inferQuerySource(key, project) : undefined" in source
    assert "renderMappingSummary" in source
    assert "prompt_template" in source
    assert "query_source" in source


def test_embedded_query_mode_uses_prompt_template_without_json_source():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "usesEmbeddedPromptQueries" in source
    assert "query_mode: retrieval_query_embedded" in source
    assert "检索来源：${querySource || '模板内置'}" in source
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


def test_common_generation_constraints_preserve_commas():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "field === 'generation_constraints'" in source
    assert "value = splitLines(input.value);" in source
    assert "value = splitDelimitedList(input.value);" in source
    assert "field === 'generation_constraints'\n            || field === 'hard_constraints.forbidden_phrases'" not in source


def test_initial_load_uses_navigation_to_activate_content_section():
    source = APP_JS.read_text(encoding="utf-8")

    assert "function getInitialSection()" in source
    assert "localStorage.getItem('af-active-section')" in source
    assert "localStorage.setItem('af-active-section', section)" in source
    assert "navigateTo(getInitialSection());" in source
    assert "loadDashboard();\n    startCrawlFeedPolling();\n    startWorkersPolling();" not in source


def test_template_cards_do_not_reference_module_state_inline():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert 'onclick="selectTemplate(' in source
    assert 'onclick="!isEditMode' not in source


def test_placeholder_yaml_preserves_prompt_writing_structure_and_period_fields():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "const placeholders = getTemplateWorkbenchPlaceholders(template);" in source
    assert ".filter(placeholder => !isSystemDatePlaceholder(placeholder))" not in source
    assert "field === 'components.llm_writing.writing_structure'" in source
    assert "draft.writing_structure = structure;" in source
    assert "lines.push('    writing_structure:');" in source
    assert "writingStructure.forEach(item => lines.push(`    - ${item}`));" in source
    assert "if (isSystemDatePlaceholder(name)) return 'report_period';" in source


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
    assert "min-height: 720px" in css
    assert "flex: 1 1 auto" in css
    assert ".template-source-editor" in css
    assert ".template-mapping-table" in css
    assert "iphone-icon-wiggle" not in css
    assert ".iphone-template-wrapper.dragging .iphone-app-icon" in css
    assert ".iphone-template-wrapper.dragging" in css
    assert "position: fixed" in css
    assert ".iphone-template-name-input" in css
    assert ".template-log-console" in css
    assert ".template-log-context" in css
    assert ".template-generation-log-row" in css


def test_report_generation_page_uses_apple_refinement_instead_of_market_red_cards():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "Apple Report Generation Workspace Refinement" in css
    assert "Apple Report Word Preview" in css
    assert "#template-workbench-summary" in css
    assert ".template-generation-flow-step.done .step-index" in css
    assert "var(--report-flow-complete)" in css
    assert "background: var(--success);" not in css.split(
        ".template-generation-flow-step.done .step-index", 1
    )[1].split("}", 1)[0]
    assert "#template-workbench-summary {\n    border: 0;" in css
    assert ".template-generation-flow-panel,\n.template-generation-step-panel {\n    border: 0;" in css
    assert ".template-generation-hero {\n    align-items: flex-start;" in css
    assert '[data-theme="light"] .template-generation-hero {\n    background: transparent;' in css
    assert ".template-generation-actions small {\n    display: none;" in css
    assert ".template-preview-frame.word-preview-shell" in css


def test_template_detail_icon_follows_active_color_scheme():
    css = STYLE_CSS.read_text(encoding="utf-8")

    detail_icon_block = css.split(".template-icon-large {", 1)[1].split("}", 1)[0]
    assert "background: var(--accent);" in detail_icon_block
    assert ".template-icon-large.docx" not in css
    assert ".template-icon-large.pptx" not in css
    assert ".template-icon-large.excel" not in css
