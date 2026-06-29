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
    assert 'class="template-workbench-main-grid template-config-grid"' in html
    assert 'id="template-common-rules"' in html
    assert 'id="template-placeholder-map"' in html
    assert 'id="template-placeholder-detail-form"' in html
    assert 'id="btn-template-save-placeholder"' in html


def test_report_config_tab_uses_redesigned_editor_shell():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="template-workbench-main-grid template-config-grid"' in html
    assert 'class="template-workbench-left template-config-rail"' in html
    assert 'class="template-workbench-panel template-config-common-panel"' in html
    assert 'class="template-workbench-panel template-section-editor-panel template-config-editor-panel"' in html
    assert 'class="template-generation-hero template-config-hero"' in html
    assert 'id="btn-template-config-advanced"' in html
    assert 'id="btn-template-config-save-placeholder"' not in html
    assert 'id="btn-template-config-save-common"' not in html
    assert "configSavePlaceholderBtn" not in source
    assert "configSaveCommonBtn" not in source
    assert 'btn-template-open-placeholder-config-modal' not in source
    assert 'data-placeholder-edit-section="basic"' in source
    assert 'data-placeholder-edit-section="query"' in source
    assert 'data-placeholder-edit-section="keywords"' in source
    assert 'data-placeholder-edit-section="fixed_template"' in source
    assert 'data-placeholder-edit-section="data_fields"' in source
    assert 'data-placeholder-editor-section="basic"' in source
    assert 'data-placeholder-editor-section="query"' in source
    assert 'data-placeholder-editor-section="keywords"' in source
    assert 'data-placeholder-editor-section="fixed_template"' in source
    assert 'data-placeholder-editor-section="data_fields"' in source
    assert "setPlaceholderEditorVisibility" in source
    assert "setPlaceholderEditingSection('')" in source
    assert 'class="template-config-toolbar-meta"' in html
    assert 'class="template-config-toolbar-chips"' in html
    assert "template-config-form-section" in source
    assert "template-config-data-source-row" in source
    data_fields_start = source.index("function renderDataTemplateFieldsEditor")
    data_fields_end = source.index("function normalizeDataTemplateFieldKey", data_fields_start)
    data_fields_source = source[data_fields_start:data_fields_end]
    assert "template-config-token" not in data_fields_source
    assert "data-template-data-field-add" in source
    assert "data-template-data-field-delete" in source
    assert "data-data-template-field-key" in source
    assert "template-config-inline-action" in source
    assert "collectDataTemplateFieldsFromForms" in source
    assert "normalizeDataTemplateFieldKey" in source
    assert "template-config-title" in source
    assert "template-config-placeholder-type" in source
    assert "template-config-grid" in css
    assert "template-config-hero" in css
    assert "template-config-editor-panel" in css
    assert "template-config-data-source-row" in css
    assert ".template-data-field-add" in css
    assert ".template-data-field-delete" in css
    assert ".template-data-fields-empty" in css
    assert ".template-config-inline-action" in css
    assert "template-config-edit-trigger" in css
    assert "template-config-edit-trigger.is-editing" in css
    assert ".template-common-summary-card:hover" in css
    assert ".template-common-summary-card:focus-within" in css
    assert ".template-common-summary-card.is-editing" in css
    assert 'details.template-common-summary-card[data-common-section="generation_constraints"]:hover' in css
    assert 'details.template-common-summary-card[data-common-section="generation_constraints"]:focus-within' in css
    assert 'details.template-common-summary-card.is-editing[data-common-section="generation_constraints"]' in css
    assert '.template-common-summary-card[data-common-section="generation_constraints"] {\n    border-color: transparent;' in css
    assert "--template-config-rail-highlight-bg" in css
    assert "background: var(--template-config-rail-highlight-bg);" in css
    assert ".template-config-common-panel details.template-common-summary-card[open]:hover" in css
    assert '[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open]:hover' in css
    assert ".template-config-common-panel .template-common-summary-card > summary:hover" in css
    assert "background: transparent;" in css
    assert "var(--apple-accent)" in css
    assert ".template-config-editor-toolbar .placeholder-select-menu" in css
    assert "--placeholder-select-menu-bg: #ffffff;" in css
    assert "--placeholder-select-menu-bg: #2c2c2e;" in css
    assert "background: var(--placeholder-select-menu-bg);" in css
    assert "backdrop-filter: none;" in css
    assert "-webkit-backdrop-filter: none;" in css
    assert ".template-config-editor-toolbar .placeholder-select-option" in css
    menu_css = css[
        css.index(".template-config-editor-toolbar .placeholder-select-menu"):
        css.index(".template-config-editor-toolbar .placeholder-select-menu[hidden]")
    ]
    option_css = css[
        css.index(".template-config-editor-toolbar .placeholder-select-option"):
        css.index(".template-config-editor-toolbar .template-placeholder-actions")
    ]
    assert "color-mix" not in menu_css.split("background:", 1)[1].split(";", 1)[0]
    assert "background: transparent;" not in option_css
    final_open_reset = css.rfind(".template-config-common-panel .template-common-summary-card[open],\n.template-config-common-panel details.template-common-summary-card[data-common-section=\"generation_constraints\"],")
    final_hover = css.rfind(".template-config-common-panel .template-common-summary-card:hover,\n.template-config-common-panel details.template-common-summary-card[data-common-section=\"generation_constraints\"]:hover,")
    assert final_open_reset != -1
    assert final_hover > final_open_reset
    final_highlight_rule = css[css.rfind(".template-config-common-panel .template-common-summary-card:hover"):css.rfind(".template-config-common-panel .template-common-summary-card:hover > summary::before")]
    assert "> summary:hover" not in final_highlight_rule
    assert css.rfind('[data-theme="light"] .template-config-common-panel .template-common-summary-card:hover') > css.rfind('[data-theme="light"] .template-config-common-panel .template-common-summary-card,')
    assert css.rfind('[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open]:hover') > css.rfind('[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open],')


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


def test_report_period_placeholder_summary_does_not_show_generation_metrics():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    start = source.index("function buildPlaceholderConfigSummaryHtml")
    end = source.index("function getPlaceholderEditSectionLabels", start)
    summary_source = source[start:end]

    assert "if (type === 'report_period')" in summary_source
    report_period_branch = summary_source.split("if (type === 'report_period')", 1)[1].split("const facts = [\n        { label: '目标字数'", 1)[0]
    assert "字段类型" in report_period_branch
    assert "映射字段" in report_period_branch
    assert "template-report-period-summary-grid" in report_period_branch
    assert "template-config-report-date-field" in report_period_branch
    assert "不参与 AI 生成" in report_period_branch
    assert "getEditableCommonDefaults(template)" in report_period_branch
    assert "getCommonDefaultsDraft" not in report_period_branch
    assert "目标字数" not in report_period_branch
    assert "最大字数" not in report_period_branch
    assert "证据条数" not in report_period_branch
    assert 'data-common-rule-field="report_period.${esc(field)}"' in source
    assert '这里修改后会同步到“证据来源与时间”的共用参数。' in source
    assert "document.getElementById('template-placeholder-detail-form')" in source
    assert "boundPlaceholderCommonRule" in source


def test_common_report_period_changes_refresh_generation_summary():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    bind_start = source.index("function bindCommonRuleInputs")
    bind_end = source.index("function setCommonRuleEditingSection", bind_start)
    bind_source = source[bind_start:bind_end]
    save_start = source.index("function saveTemplateConfigEditorModal")
    save_end = source.index("function bindTemplateWorkbenchActions", save_start)
    save_source = source[save_start:save_end]

    assert "function refreshGenerationHeroMeta" in source
    assert "function refreshCommonConfigSurfaces" in source
    assert "syncEvidenceRangeFromReportDate(input.value);" in bind_source
    assert "collectCommonDefaultsDraft(template);" in bind_source
    assert "refreshCommonConfigSurfaces(template);" in bind_source
    assert "formatEvidenceScopeSummary(reportPeriod, retrieval)" in source
    assert "refreshCommonConfigSurfaces(template);" in save_source


def test_placeholder_select_syncs_state_when_previous_selection_is_missing():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    start = source.index("function renderTemplatePlaceholderMap")
    end = source.index("function renderMappingSummary", start)
    map_source = source[start:end]

    assert "const normalizedNames = names.map(name => normalizePlaceholderName(name)).filter(Boolean);" in map_source
    assert "const currentName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);" in map_source
    assert "normalizedNames.includes(currentName)" in map_source
    assert "currentTemplateState.selectedPlaceholderName = selectedName;" in map_source
    assert "currentTemplateState.selectedPlaceholderName = '';" in map_source
    assert 'class="placeholder-picker"' in map_source
    assert 'class="placeholder-select placeholder-select-button"' in map_source
    assert 'class="placeholder-select-option"' in map_source
    assert "setPlaceholderPickerValue(selectedName);" in map_source
    assert "window.requestAnimationFrame(reconcilePlaceholderPickerAndDetail);" in map_source
    assert "window.setTimeout(reconcilePlaceholderPickerAndDetail, 50);" in map_source


def test_placeholder_detail_syncs_from_picker_before_rendering():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    start = source.index("function selectTemplatePlaceholder")
    end = source.index("function getSelectedPlaceholderMapping", start)
    select_source = source[start:end]

    assert "function syncSelectedPlaceholderFromPicker()" in source
    assert "function reconcilePlaceholderPickerAndDetail()" in source
    assert "function getRenderedPlaceholderSummaryName()" in source
    assert "function startPlaceholderPickerSync()" in source
    assert "function getPlaceholderPickerValue()" in source
    assert "function setPlaceholderPickerValue(name)" in source
    assert "function togglePlaceholderPickerMenu()" in source
    assert "function closePlaceholderPickerMenu()" in source
    assert "document.getElementById('template-placeholder-select')" in source
    assert "currentTemplateState.selectedPlaceholderName = selectedName;" in source
    assert "const name = syncSelectedPlaceholderFromPicker();" in source
    assert "picker.addEventListener('click'" in source
    assert "option.addEventListener('click'" in source
    assert "selectTemplatePlaceholder(option.dataset.placeholderName || '');" in source
    assert "startPlaceholderPickerSync();" in source
    assert "window.setInterval(() => {" in source
    assert "const renderedName = getRenderedPlaceholderSummaryName();" in source
    assert "currentTemplateState.selectedPlaceholderName = pickerName;" in source
    assert "setPlaceholderPickerValue(normalizedName);" in select_source
    assert "label.textContent = normalizedName;" in source
    assert "renderTemplatePlaceholderMap(" not in select_source


def test_keyword_profile_change_keeps_config_modal_scoped_to_keywords():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function isPlaceholderConfigEditorModalOpen()" in source
    assert "function refreshKeywordProfilePreview(input, template)" in source
    assert "field === 'retrieval.keyword_profile_select' && isPlaceholderConfigEditorModalOpen()" in source
    assert "refreshKeywordProfilePreview(input, template);" in source
    assert "renderSelectedPlaceholderDetail(template);" in source
    assert "modalState.parentNode.isConnected" in source
    assert "modalState.contentNode.remove();" in source


def test_config_modal_does_not_auto_select_first_number_input():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "btn-template-config-editor-modal-close" in source
    assert "closeBtn?.focus?.({ preventScroll: true })" in source
    assert "const firstField = body.querySelector('input, textarea, select, button');" not in source
    assert 'input[type="number"] {' in css
    assert 'appearance: textfield;' in css
    assert 'input[type="number"]::-webkit-inner-spin-button' in css
    assert '-webkit-appearance: none;' in css


def test_data_template_fields_only_render_for_composite_market_review_placeholders():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "const supportsDataTemplate = type === 'composite_market_review';" in source
    assert "includeDefaults: supportsDataTemplate" in source
    assert "function getDataTemplateFields(mapping = {}, { includeDefaults = true } = {})" in source
    assert "...(includeDefaults && !hasExplicitFields ? getDefaultDataTemplateFields(mapping) : {})" in source
    assert "const hasExplicitFields = Object.prototype.hasOwnProperty.call(component, 'fields');" in source
    assert "const dataTemplateFields = getDataTemplateFields(mapping);" not in source


def test_prompt_placeholders_keep_writing_structure_entry_even_when_empty():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "const writingSteps = splitLines(writingStructureText);" in source
    assert '${isPromptLike ? `' in source
    assert 'data-placeholder-edit-section="writing"' in source
    assert "writingSteps.length ? `${writingSteps.length} 步` : '未配置'" in source
    assert "未单独配置写作步骤，点击这里添加生成正文的结构和表达边界。" in source
    assert ".template-config-readable-section .template-config-empty-note" in css


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
