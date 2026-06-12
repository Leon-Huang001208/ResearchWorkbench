"""Static wiring tests for the report template workbench frontend."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
TEMPLATES_JS = ROOT / "app" / "web" / "static" / "js" / "templates.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
DASHBOARD_REPO = ROOT / "data_layer" / "repositories" / "dashboard_data.py"


def test_template_detail_has_report_workbench_regions():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-workbench-summary"' in html
    assert 'id="template-section-config-editor"' in html
    assert 'id="template-common-rules"' in html
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
    assert "当前片段源码" in html
    assert "Excel 底稿映射" in html


def test_template_detail_prioritizes_weekly_report_generation_center():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-generation-center"' in html
    assert "周报生成" in html
    assert "生成本周报告" in html
    assert 'id="template-generation-health"' in html
    assert 'id="template-generation-action-hint"' in html
    assert 'id="template-generation-period"' in html
    assert 'id="template-generation-lookback"' in html
    assert 'id="template-generation-status-strip"' in html
    assert 'id="template-generation-step-data"' in html
    assert 'id="template-generation-step-content"' in html
    assert 'id="template-generation-step-output"' in html
    assert 'id="template-recent-generation-panel"' in html
    assert 'id="template-generation-readiness-panel"' in html
    assert 'id="template-advanced-maintenance"' in html
    assert "高级配置" in html
    assert "占位符、Prompt、检索策略和 YAML 片段" in html
    assert 'id="detail-template-name"' not in html
    assert 'id="detail-template-version"' not in html
    assert 'id="detail-template-title"' not in html
    assert 'class="card template-info-card"' not in html
    assert "v1.0" not in html
    assert "报告模板工作台" not in html
    assert "Word 占位符、Excel 底稿、Section 配置统一维护" not in html


def test_app_boots_to_templates_without_dashboard_polling():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = APP_JS.read_text(encoding="utf-8")
    init_block = source[source.index("document.addEventListener('DOMContentLoaded'") :]

    assert 'data-section="templates" title="模板管理"' in html
    assert 'id="section-dashboard" class="content-section"' in html
    assert "navigateTo('templates')" in init_block
    assert "loadDashboard();" not in init_block
    assert "startCrawlFeedPolling();" not in init_block
    assert "connectSSE();" not in init_block
    assert "disconnectSSE" in source


def test_crawl_feed_query_has_sqlite_json_fallback():
    source = DASHBOARD_REPO.read_text(encoding="utf-8")
    crawl_feed_block = source[source.index("def get_recent_crawled_documents") :]

    assert 'dialect_name == "sqlite"' in crawl_feed_block
    assert 'func.json_extract(DocumentV1DB.timeliness, "$.publish_time")' in crawl_feed_block
    assert 'func.json_extract_path_text(DocumentV1DB.timeliness, "publish_time")' in crawl_feed_block


def test_templates_js_populates_report_workbench():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderReportGenerationCenter" in source
    assert "renderAdvancedMaintenance" in source
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
    assert "selectTemplatePlaceholder" in source
    assert "renderSelectedPlaceholderDetail" in source
    assert "btn-template-save-placeholder" in source
    assert "data-placeholder-name" in source
    assert "data-placeholder-field" in source
    assert "updateTemplateSourceFromPlaceholderDraft" in source


def test_templates_js_renders_generation_center_and_reuses_advanced_workbench():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderReportGenerationCenter" in source
    assert "buildGenerationReadiness" in source
    assert "renderGenerationHero" in source
    assert "renderGenerationStatusStrip" in source
    assert "renderProjectCheckSummary" in source
    assert "renderRecentGenerationPanel" in source
    assert "REPORT_GENERATION_STEPS" in source
    assert "renderReportGenerationProgressCard" in source
    assert "renderReportGenerationFailure" in source
    assert "getReportGenerationErrorHint" in source
    assert "getReportGenerationErrorTarget" in source
    assert "handleTemplateCheckAction" in source
    assert "data-template-check-action" in source
    assert "template-check-action" in source
    assert "openUploadModalForField" in source
    assert "template-focus-highlight" in source
    assert "btn-template-generation-open-config" in source
    assert "btn-template-generation-retry" in source
    assert "renderReportFromTemplate({ inlineProgress: true })" in source
    assert "renderAdvancedMaintenance" in source
    assert "template-generation-period" in source
    assert "template-generation-lookback" in source
    assert "最近生成" in source
    assert "尚未生成" in source


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


def test_workbench_keeps_section_mapping_and_prompt_source_separate():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "btn-template-source-section" in source
    assert "btn-template-source-prompt" in source
    assert "switchTemplateSourceKind" in source
    assert "activeSourceKind" in source
    assert "Markdown Prompt" in source
    assert "YAML 占位符映射" in source


def test_workbench_source_panel_shows_selected_placeholder_fragment():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "renderSelectedSourceFragment" in source
    assert "buildSelectedPlaceholderYamlFragment" in source
    assert "buildPlaceholderYamlEntry" in source
    assert "getPromptTemplateFragment" in source
    assert "getSelectedPromptTemplateName" in source
    assert "sourceEditor.dataset.placeholderName" in source
    assert "sourceEditor.dataset.promptTemplateName" in source
    assert "renderSelectedSourceFragment(template);" in source
    assert "switchTemplateSourceKind(sourceKind)" in source
    assert "sourceEditor.value = getPromptTemplateFragment(source.content, promptName);" in source
    assert "sourceEditor.value = buildSelectedPlaceholderYamlFragment(" in source


def test_workbench_source_save_merges_fragment_back_to_full_project_file():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "buildSourceContentForSave" in source
    assert "buildUpdatedPromptTemplatesSource" in source
    assert "buildUpdatedSectionConfigSource(template, getEditablePlaceholderMappings(template))" in source
    assert "content: sourceEditor.value" not in source
    assert "buildSourceContentForSave(template, sourceEditor.dataset.sourceKind || 'local_draft', sourceEditor.value)" in source


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


def test_advanced_placeholder_selector_drives_single_placeholder_detail():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'id="template-placeholder-select"' in source
    assert "placeholder-selected-card" in source
    assert "bindPlaceholderMapRows" in source
    assert "select.addEventListener('change'" in source
    assert "renderSelectedPlaceholderDetail(template)" in source
    assert ".placeholder-select" in css
    assert ".placeholder-selected-card" in css
    assert ".template-placeholder-detail-form" in css
    assert "buildUpdatedSectionConfigSource" in source
    assert "buildPlaceholderMappingsBlock" in source
    assert "isSystemDatePlaceholder" in source
    assert ".filter(placeholder => !isSystemDatePlaceholder(placeholder))" in source


def test_advanced_workbench_exposes_common_defaults_and_target_words():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert "renderCommonGenerationRules" in source
    assert "template-common-rules" in source
    left_panel = html[html.index('<div class="template-workbench-left">') : html.index('<div class="template-workbench-panel template-section-editor-panel"')]
    right_panel = html[html.index('<div class="template-workbench-panel template-section-editor-panel"') :]
    assert 'id="template-common-rules"' in left_panel
    assert 'id="template-common-rules"' not in right_panel
    assert "共用 Prompt 约束" in source
    assert "检索策略" in source
    assert "证据重排" in source
    assert "启用 DeepSeek/LLM 重排" not in source
    assert "按当前占位符 Prompt 的相关性排序" in source
    assert "template-common-summary-card" in source
    assert "template-common-summary-title" in source
    assert "template-common-rule-editor" in source
    assert "template-rerank-editor" in source
    assert "template-weight-meter" in source
    assert "formatRulePercent" in source
    assert "getHardConstraintPromptText" in source
    assert "getFirstLine" in source
    assert 'data-common-rule-field="hard_constraints.prompt_text"' in source
    assert 'data-common-rule-field="hard_constraints.no_wind_data"' not in source
    assert 'data-common-rule-field="hard_constraints.no_baidu_data"' not in source
    assert 'data-common-rule-field="hard_constraints.require_number_source"' not in source
    assert 'data-common-rule-field="hard_constraints.single_paragraph"' not in source
    assert 'data-common-rule-field="hard_constraints.forbidden_phrases"' not in source
    assert 'data-common-rule-field="hard_constraints.forbidden_entity_categories"' not in source
    assert 'data-common-rule-field="retrieval.mode"' in source
    assert 'data-common-rule-field="retrieval.top_k"' in source
    assert 'data-common-rule-field="retrieval.keyword_candidates"' in source
    assert 'data-common-rule-field="retrieval.semantic_candidates"' in source
    assert 'data-common-rule-field="retrieval.keyword_weight"' in source
    assert 'data-common-rule-field="retrieval.semantic_weight"' in source
    assert 'data-common-rule-field="rerank.enabled"' in source
    assert 'data-common-rule-field="rerank.candidates"' in source
    assert 'data-common-rule-field="rerank.min_score"' in source
    assert 'data-placeholder-field="max_words"' in source
    assert 'data-placeholder-field="retrieval.keywords"' in source
    assert "getPlaceholderRetrievalKeywords" in source
    assert "splitDelimitedList" in source
    assert "inferPlaceholderKeywords" in source
    assert "'人工智能': ['CPO', '算力', '人工智能', '大模型', '先进封装']" in source
    assert "buildDefaultsBlock" in source
    assert "insertTopLevelBlockBefore" in source
    assert "继承 defaults: 共用 Prompt 约束 / 检索配置 / Rerank" in source
    assert "hard_constraints:" in source
    assert "prompt_text: |" in source
    assert "retrieval:" in source
    assert "rerank:" in source
    assert ".template-common-rules-grid" in css
    assert ".template-common-rule-card" in css
    assert ".template-common-summary-card > summary" in css
    assert ".template-common-rule-editor" in css
    assert ".template-rerank-editor" in css
    assert ".template-rerank-toggle" in css
    assert ".template-weight-meter" in css
    assert ".template-generation-health" in css
    assert ".template-result-main" in css
    assert ".template-project-check-panel > summary" in css
    assert "template-result-empty" in source
    assert "template-result-main" in source


def test_placeholder_mapping_connects_word_prompt_and_query_source():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "resolvePromptTemplateName" in source
    assert "inferQuerySource" in source
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
    assert "flex: 1 1 auto" in css
    assert ".template-source-editor" in css
    assert ".template-mapping-table" in css
    assert "iphone-icon-wiggle" not in css
    assert ".iphone-template-wrapper.dragging .iphone-app-icon" in css
    assert ".iphone-template-wrapper.dragging" in css
    assert "position: fixed" in css
    assert ".iphone-template-name-input" in css


def test_weekly_report_generation_center_styles_exist():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".template-generation-center" in css
    assert ".template-generation-hero" in css
    assert ".template-generation-actions" in css
    assert ".template-generation-status-strip" in css
    assert ".template-generation-step" in css
    assert ".template-generation-progress" in css
    assert ".template-generation-progress-steps" in css
    assert ".template-generation-error-card" in css
    assert ".template-generation-error-actions" in css
    assert ".template-check-action" in css
    assert ".template-focus-highlight" in css
    assert "@keyframes template-focus-pulse" in css
    assert ".template-generation-panels" in css
    assert ".template-recent-generation-card" in css
    assert ".template-advanced-maintenance" in css
    assert ".template-advanced-maintenance[open]" in css


def test_template_detail_icon_follows_active_color_scheme():
    css = STYLE_CSS.read_text(encoding="utf-8")

    detail_icon_block = css.split(".template-icon-large {", 1)[1].split("}", 1)[0]
    assert "background: var(--accent);" in detail_icon_block
    assert ".template-icon-large.docx" not in css
    assert ".template-icon-large.pptx" not in css
    assert ".template-icon-large.excel" not in css
