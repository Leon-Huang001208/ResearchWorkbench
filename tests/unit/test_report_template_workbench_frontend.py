"""Static wiring tests for the report template workbench frontend."""

import json
import subprocess
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
    assert "Excel 底稿映射" not in html


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
    assert (
        'class="template-workbench-panel template-section-editor-panel template-config-editor-panel"'
        in html
    )
    assert 'class="template-generation-hero template-config-hero"' in html
    assert 'id="btn-template-config-advanced"' in html
    assert 'id="btn-template-config-save-placeholder"' not in html
    assert 'id="btn-template-config-save-common"' not in html
    assert "configSavePlaceholderBtn" not in source
    assert "configSaveCommonBtn" not in source
    assert "btn-template-open-placeholder-config-modal" not in source
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
    assert "template-config-toolbar-chips" in html
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
    assert (
        'details.template-common-summary-card[data-common-section="generation_constraints"]:hover'
        in css
    )
    assert (
        'details.template-common-summary-card[data-common-section="generation_constraints"]:focus-within'
        in css
    )
    assert (
        'details.template-common-summary-card.is-editing[data-common-section="generation_constraints"]'
        in css
    )
    assert (
        '.template-common-summary-card[data-common-section="generation_constraints"] {\n    border-color: transparent;'
        in css
    )
    assert "--template-config-rail-highlight-bg" in css
    assert "background: var(--template-config-rail-highlight-bg);" in css
    assert ".template-config-common-panel details.template-common-summary-card[open]:hover" in css
    assert (
        '[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open]:hover'
        in css
    )
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
        css.index(".template-config-editor-toolbar .placeholder-select-menu") : css.index(
            ".template-config-editor-toolbar .placeholder-select-menu[hidden]"
        )
    ]
    option_css = css[
        css.index(".template-config-editor-toolbar .placeholder-select-option") : css.index(
            ".template-config-editor-toolbar .template-placeholder-actions"
        )
    ]
    assert "color-mix" not in menu_css.split("background:", 1)[1].split(";", 1)[0]
    assert "background: transparent;" not in option_css
    final_open_reset = css.rfind(
        '.template-config-common-panel .template-common-summary-card[open],\n.template-config-common-panel details.template-common-summary-card[data-common-section="generation_constraints"],'
    )
    final_hover = css.rfind(
        '.template-config-common-panel .template-common-summary-card:hover,\n.template-config-common-panel details.template-common-summary-card[data-common-section="generation_constraints"]:hover,'
    )
    assert final_open_reset != -1
    assert final_hover > final_open_reset
    final_highlight_rule = css[
        css.rfind(".template-config-common-panel .template-common-summary-card:hover") : css.rfind(
            ".template-config-common-panel .template-common-summary-card:hover > summary::before"
        )
    ]
    assert "> summary:hover" not in final_highlight_rule
    assert css.rfind(
        '[data-theme="light"] .template-config-common-panel .template-common-summary-card:hover'
    ) > css.rfind(
        '[data-theme="light"] .template-config-common-panel .template-common-summary-card,'
    )
    assert css.rfind(
        '[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open]:hover'
    ) > css.rfind(
        '[data-theme="light"] .template-config-common-panel details.template-common-summary-card[open],'
    )


def test_report_config_summary_dom_contract_collapses_low_frequency_sections_and_keeps_edit_entries():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    helper_start = source.index("function buildConfigCollapsibleSection")
    helper_end = source.index("function buildPlaceholderConfigSummaryHtml", helper_start)
    helper_source = source[helper_start:helper_end]
    summary_start = helper_end
    summary_end = source.index("function getPlaceholderEditSectionLabels", summary_start)
    summary_source = source[summary_start:summary_end]

    # Task 1 verifies only the DOM contract; Task 3 owns the visual styling.
    assert '<details class="template-config-collapsible-section"' in helper_source
    assert "<summary>" in helper_source
    assert 'class="template-config-collapsible-body"' in helper_source
    for edit_section in ("keywords", "fixed_template", "data_fields", "writing"):
        section_marker = f"editSection: '{edit_section}'"
        section_position = summary_source.index(section_marker)
        helper_position = summary_source.rfind(
            "buildConfigCollapsibleSection({", 0, section_position
        )

        assert helper_position != -1
        assert section_marker in summary_source[helper_position:section_position + len(section_marker)]
        assert f'data-placeholder-edit-section="{edit_section}"' in helper_source


def test_report_config_summary_prioritizes_missing_query_or_keywords_without_losing_edit_entries():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    caller_start = source.index("function renderSelectedPlaceholderDetail")
    caller_end = source.index("function buildPlaceholderConfigSummaryHtml", caller_start)
    caller_source = source[caller_start:caller_end]
    start = source.index("function buildPlaceholderConfigSummaryHtml")
    end = source.index("function getPlaceholderEditSectionLabels", start)
    summary_source = source[start:end]
    raw_query_start = source.index("function getConfiguredSemanticRetrievalQueryForPlaceholder")
    raw_query_end = source.index("function getSemanticRetrievalQueryForPlaceholder", raw_query_start)
    raw_query_source = source[raw_query_start:raw_query_end]
    display_query_end = source.index("function extractPromptTemplateLabel", raw_query_end)
    display_query_source = source[raw_query_end:display_query_end]

    assert "const rawSemanticQuery = getConfiguredSemanticRetrievalQueryForPlaceholder(" in caller_source
    assert "const semanticQueryDisplay = getSemanticRetrievalQueryForPlaceholder(" in caller_source
    assert "rawSemanticQuery," in caller_source
    assert "semanticQueryDisplay," in caller_source
    assert "rawSemanticQuery = String(rawSemanticQuery ?? '');" in summary_source
    assert "semanticQueryDisplay: providedSemanticQueryDisplay = ''," in summary_source
    assert "const semanticQueryDisplay = String(providedSemanticQueryDisplay ?? '');" in summary_source
    assert "const queryNeedsAttention = usesEvidence && !rawSemanticQuery.trim();" in summary_source
    assert "const keywordsNeedAttention = usesEvidence && !queryNeedsAttention && keywordList.length === 0;" in summary_source
    assert "return promptName ||" not in raw_query_source
    assert "return '';" in raw_query_source
    assert "return promptName || normalizePlaceholderName(placeholderName) || '未配置语义 Query';" in display_query_source
    assert "open: queryNeedsAttention" in summary_source
    assert "template-config-next-action" in summary_source
    assert "补充语义 Query，明确系统应召回哪些材料。" in summary_source
    assert "选择关键词预设包，或添加自定义关键词。" in summary_source
    assert summary_source.index("${queryNeedsAttention ? `") < summary_source.index(
        "` : keywordsNeedAttention ? `"
    ) < summary_source.index("` : ''}")

    # Missing-config guidance must add an entry point instead of replacing existing editors.
    for edit_section in ("basic", "query", "keywords", "fixed_template", "data_fields", "writing"):
        assert f'data-placeholder-edit-section="{edit_section}"' in source


def test_report_config_current_section_save_feedback_contract():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    detail_start = source.index("function renderSelectedPlaceholderDetail")
    detail_end = source.index("function bindPlaceholderSummaryEditActions", detail_start)
    detail_source = source[detail_start:detail_end]
    feedback_start = source.index("function renderPlaceholderSaveFeedback")
    feedback_end = source.index("function renderSelectedPlaceholderDetail", feedback_start)
    feedback_source = source[feedback_start:feedback_end]
    save_start = source.index("async function saveCurrentSectionConfig")
    save_end = source.index("function handleTemplateCheckAction", save_start)
    save_source = source[save_start:save_end]

    assert 'id="template-config-save-feedback"' in detail_source
    assert "function renderPlaceholderSaveFeedback(message, tone = 'success')" in source
    assert "feedbackEl.textContent = message || '';" in feedback_source
    assert "feedbackEl.hidden = !message;" in feedback_source
    assert "feedbackEl.dataset.tone = tone;" in feedback_source
    assert "renderPlaceholderSaveFeedback('已保存当前段落。');" in save_source
    assert ".template-config-save-feedback {" in css
    assert '.template-config-save-feedback[data-tone="success"]::before' in css


def test_report_config_summary_next_actions_render_from_real_query_state():
    script = r"""
const fs = require('fs');
const vm = require('vm');
const source = fs.readFileSync(process.argv[1], 'utf8');

function extract(startMarker, endMarker) {
    const start = source.indexOf(startMarker);
    const end = source.indexOf(endMarker, start);
    if (start === -1 || end === -1) throw new Error(`Unable to extract ${startMarker}`);
    return source.slice(start, end);
}

const sandbox = {
    esc: (value) => String(value ?? ''),
    isParagraphPlaceholderType: () => true,
    isParagraphMode: () => true,
    getParagraphMode: () => 'evidence_grounded_generation',
    getParagraphModeLabel: () => '正文段落',
    isDataTemplateParagraphMode: () => false,
    usesEvidenceParagraphMode: () => true,
    isReportPeriodFieldPlaceholder: () => false,
    splitLines: (value) => String(value ?? '').split('\n').map((item) => item.trim()).filter(Boolean),
    inferDefaultTargetWords: () => 250,
    buildConfigEnhancementBadges: () => '',
    buildKeywordGroupsInlineBadges: () => '',
    resolvePromptTemplateName: () => '',
    extractPromptTemplateLabel: () => '',
    normalizePlaceholderName: () => '占位符兜底'
};
vm.createContext(sandbox);
vm.runInContext(extract('function buildConfigCollapsibleSection', 'function buildPlaceholderConfigSummaryHtml'), sandbox);
vm.runInContext(extract('function buildPlaceholderConfigSummaryHtml', 'function getPlaceholderEditSectionLabels'), sandbox);
vm.runInContext(extract('function getConfiguredSemanticRetrievalQueryForPlaceholder', 'function getSemanticRetrievalQueryForPlaceholder'), sandbox);
vm.runInContext(extract('function getSemanticRetrievalQueryForPlaceholder', 'function extractPromptTemplateLabel'), sandbox);

function render(rawSemanticQuery, semanticQueryDisplay, retrievalKeywords) {
    return sandbox.buildPlaceholderConfigSummaryHtml({
        name: '市场回顾',
        type: 'paragraph',
        paragraphMode: 'evidence_grounded_generation',
        mapping: {},
        minNewsCount: 7,
        dataTemplateFields: {},
        rawSemanticQuery,
        semanticQueryDisplay,
        retrievalKeywords,
        template: {}
    });
}

function actionSections(html) {
    return [...html.matchAll(/class="template-config-next-action[^\"]*"[^>]*data-placeholder-edit-section="([^\"]+)"/g)]
        .map((match) => match[1]);
}

function queryIsOpen(html) {
    return /<details class="template-config-collapsible-section" open>[\s\S]*?<strong>语义 Query<\/strong>/.test(html);
}

const missingQuery = render('', '市场回顾', 'AI');
const missingKeywords = render('召回市场热点', '召回市场热点', '');
const complete = render('召回市场热点', '召回市场热点', 'AI\n消费');
const sourceQuery = sandbox.getConfiguredSemanticRetrievalQueryForPlaceholder(
    {},
    { query_mode: 'query_source', query_source: '项目新闻索引' },
    '市场回顾'
);
const querySourceOnly = render(sourceQuery, 'Query 来源：项目新闻索引', 'AI');
const camelCaseMapping = { queryMode: 'query_source', querySource: '旧版项目新闻索引' };
const camelCaseRawQuery = sandbox.getConfiguredSemanticRetrievalQueryForPlaceholder(
    {},
    camelCaseMapping,
    '市场回顾'
);
const camelCaseDisplayQuery = sandbox.getSemanticRetrievalQueryForPlaceholder(
    {},
    camelCaseMapping,
    '市场回顾'
);
const camelCaseQuerySource = render(camelCaseRawQuery, camelCaseDisplayQuery, 'AI');

console.log(JSON.stringify({
    missingQuery: { actions: actionSections(missingQuery), queryOpen: queryIsOpen(missingQuery) },
    missingKeywords: { actions: actionSections(missingKeywords), queryOpen: queryIsOpen(missingKeywords) },
    complete: { actions: actionSections(complete), queryOpen: queryIsOpen(complete) },
    querySourceOnly: { rawQuery: sourceQuery, actions: actionSections(querySourceOnly), queryOpen: queryIsOpen(querySourceOnly) },
    camelCaseQuerySource: {
        rawQuery: camelCaseRawQuery,
        displayQuery: camelCaseDisplayQuery,
        actions: actionSections(camelCaseQuerySource),
        queryOpen: queryIsOpen(camelCaseQuerySource),
        rendersSource: camelCaseQuerySource.includes('旧版项目新闻索引')
    }
}));
"""

    result = subprocess.run(
        ["node", "-e", script, str(TEMPLATES_JS)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    rendered = json.loads(result.stdout)

    assert rendered["missingQuery"] == {"actions": ["query"], "queryOpen": True}
    assert rendered["missingKeywords"] == {"actions": ["keywords"], "queryOpen": False}
    assert rendered["complete"] == {"actions": [], "queryOpen": False}
    assert rendered["querySourceOnly"] == {
        "rawQuery": "项目新闻索引",
        "actions": [],
        "queryOpen": False,
    }
    assert rendered["camelCaseQuerySource"] == {
        "rawQuery": "旧版项目新闻索引",
        "displayQuery": "Query 来源：旧版项目新闻索引",
        "actions": [],
        "queryOpen": False,
        "rendersSource": True,
    }


def test_report_config_collapsible_summary_styles_prioritize_scanability_and_mobile_use():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".template-config-collapsible-section {" in css
    assert ".template-config-collapsible-section > summary {" in css
    assert "min-height: 52px;" in css
    assert ".template-config-collapsible-section > summary::-webkit-details-marker" in css
    assert ".template-config-collapsible-section > summary::after" in css
    assert ".template-config-collapsible-section[open] > summary::after" in css
    assert ".template-config-collapsible-body {" in css
    assert ".template-config-collapsible-section .template-config-inline-action" in css
    assert ".template-config-next-action {" in css
    assert "border-left: 3px solid var(--apple-accent);" in css
    assert ".template-config-next-action:focus-visible" in css
    assert "[data-theme=\"light\"] .template-config-collapsible-section" in css
    assert "[data-theme=\"light\"] .template-config-next-action" in css
    assert "@media (max-width: 900px)" in css
    assert ".template-config-collapsible-section > summary {\n        grid-template-columns: minmax(0, 1fr) auto;" in css
    assert ".template-config-next-action {\n        align-items: flex-start;" in css


def test_report_config_mobile_summary_keeps_a_visible_disclosure_cue():
    css = STYLE_CSS.read_text(encoding="utf-8")
    mobile_start = css.index(
        "@media (max-width: 900px) {\n    .template-config-collapsible-section > summary {"
    )
    mobile_end = css.index("\n}\n\n/* Dynamic Excel variables", mobile_start)
    mobile_css = css[mobile_start:mobile_end]

    assert ".template-config-collapsible-section > summary::after {" in mobile_css
    assert "display: none;" not in mobile_css
    assert "width: 6px;" in mobile_css
    assert ".template-config-collapsible-section[open] > summary::after" in css


def test_report_generation_page_is_reduced_to_progress_and_single_output():
    html = INDEX_HTML.read_text(encoding="utf-8")

    generation = html.split('id="template-generation-overview"', 1)[1].split(
        'id="template-advanced-maintenance"', 1
    )[0]

    assert 'id="template-generation-flow-list"' in generation
    assert 'id="template-recent-generation-panel"' in generation
    assert generation.count('id="template-recent-generation-panel"') == 1
    assert "template-generation-step-panel" not in generation
    assert 'id="template-generation-param-grid"' not in generation
    assert "template-generation-prompt-summary" not in generation
    assert "template-generation-live-events" not in generation
    assert 'id="template-project-check-details"' not in generation
    assert "生成前检查" not in generation


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


def test_templates_js_uses_background_report_generation_jobs():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "/render-jobs`" in source
    assert "pollReportGenerationJob" in source
    assert "job.status === 'completed'" in source
    assert "job.status === 'failed'" in source
    assert "completed_sections" in source
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
    assert "loadPreviewManifest" in source
    assert "renderTemplateLogPanel" in source
    assert "openReportProjectOutputFolder" in source
    assert "/open-folder" in source
    assert "openReportProjectOutputFolder(project.slug, selectedReport.file_name)" in source
    assert "?file_name=${encodeURIComponent(fileName)}" in source
    assert 'data-template-report-action="folder"' in INDEX_HTML.read_text(encoding="utf-8")
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

    assert "Promise.allSettled" in source
    assert "Failed to load legacy templates" in source
    assert "mergeTemplatesWithReportProjects(" in source
    assert "legacyResult.status === 'fulfilled'" in source
    assert "reportProjectsResult.status === 'fulfilled'" in source
    assert "currentTemplateState.reportProjects" in source
    assert "document.getElementById('templates-grid')" in source
    assert "document.getElementById('template-list')" not in source


def test_templates_list_exposes_source_failures_instead_of_empty_state():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "Promise.allSettled" in source
    assert "templateListStatus" in source
    assert "两个模板来源均加载失败" in source
    assert "报告项目加载失败" in source
    assert "模板库加载失败" in source
    assert "renderTemplateListStatus" in source
    assert "showEmptyState" in source


def test_templates_keep_legacy_details_and_upload_success_when_project_refresh_fails():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "Failed to load report projects for template details" in source
    assert "报告项目已创建，但模板列表刷新失败" in source
    assert "await loadReportProjectsList();" in source
    assert "closeUploadModal();" in source


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
    assert 'data-placeholder-field="max_words"' not in source
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

    assert "isReportPeriodFieldPlaceholder(mapping.type || type, mapping, name)" in summary_source
    report_period_branch = summary_source.split(
        "isReportPeriodFieldPlaceholder(mapping.type || type, mapping, name))", 1
    )[1].split("const facts = isParagraphPlaceholderType", 1)[0]
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
    assert "这里修改后会同步到“证据来源与时间”的共用参数。" in source
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

    assert (
        "const normalizedNames = names.map(name => normalizePlaceholderName(name)).filter(Boolean);"
        in map_source
    )
    assert (
        "const currentName = normalizePlaceholderName(currentTemplateState.selectedPlaceholderName);"
        in map_source
    )
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


def test_placeholder_picker_only_shows_selected_placeholder_not_full_config_table():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    start = source.index("function renderTemplatePlaceholderMap")
    end = source.index("function renderMappingSummary", start)
    map_source = source[start:end]

    assert 'class="placeholder-picker"' in map_source
    assert 'class="placeholder-select placeholder-select-button"' in map_source
    assert 'class="placeholder-select-option"' in map_source
    assert 'class="placeholder-config-table"' not in map_source
    assert 'class="placeholder-config-row placeholder-map-row' not in map_source
    assert "getCurrentPlaceholderMappings(getCurrentWorkbenchTemplate() || {})" not in map_source
    assert "placeholder-config-type" not in map_source
    assert "placeholder-config-source" not in map_source
    assert "placeholder-config-status" not in map_source
    assert ".placeholder-config-table" not in css
    assert ".placeholder-config-row" not in css
    assert ".placeholder-config-type" not in css


def test_placeholder_basic_panel_exposes_type_selector_and_type_specific_parameters():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function renderPlaceholderOutputShapeSelect" in source
    assert 'data-placeholder-output-shape-select="true"' in source
    assert 'data-placeholder-field="type"' in source
    assert "renderPlaceholderOutputShapeSelect(type, typeOptions)" in source
    assert "renderFieldPlaceholderEditor" in source
    assert "renderStaticTextPlaceholderEditor" in source
    assert "renderTableOrChartPlaceholderEditor" in source
    assert "来源类型" in source
    assert "插入方式" in source
    assert "固定文案" in source
    assert "Excel 来源 / 区域" in source


def test_placeholder_type_selector_uses_purpose_cards_not_dropdown():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    start = source.index("function renderPlaceholderOutputShapeSelect")
    end = source.index("function renderFieldPlaceholderEditor", start)
    selector_source = source[start:end]

    assert "这个占位符要替换成什么？" in selector_source
    assert 'class="placeholder-purpose-grid"' in selector_source
    assert 'data-placeholder-output-shape-option="${esc(option.value)}"' in selector_source
    assert (
        'type="hidden" data-placeholder-field="type" data-placeholder-output-shape-select="true"'
        in selector_source
    )
    assert "<select" not in selector_source
    assert "写一段话" in selector_source
    assert "日期、数字、单个值" in selector_source
    assert "不生成，只替换文字" in selector_source
    assert "插入 Excel 区域" in selector_source
    assert "插入图表或图片" in selector_source
    assert "bindPlaceholderPurposeCards(template);" in source
    assert ".placeholder-purpose-card" in css


def test_keyword_profile_change_keeps_config_modal_scoped_to_keywords():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function isPlaceholderConfigEditorModalOpen()" in source
    assert "function refreshKeywordProfilePreview(input, template)" in source
    assert (
        "field === 'retrieval.keyword_profile_select' && isPlaceholderConfigEditorModalOpen()"
        in source
    )
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
    assert "appearance: textfield;" in css
    assert 'input[type="number"]::-webkit-inner-spin-button' in css
    assert "-webkit-appearance: none;" in css


def test_data_template_fields_only_render_for_composite_market_review_placeholders():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert (
        "const supportsDataTemplate = isDataTemplateParagraphMode(storedType, paragraphMode);"
        in source
    )
    assert "includeDefaults: supportsDataTemplate" in source
    assert "function getDataTemplateFields(mapping = {}, { includeDefaults = true } = {})" in source
    assert (
        "...(includeDefaults && !hasExplicitFields ? getDefaultDataTemplateFields(mapping) : {})"
        in source
    )
    assert (
        "const hasExplicitFields = Object.prototype.hasOwnProperty.call(component, 'fields');"
        in source
    )
    assert "const dataTemplateFields = getDataTemplateFields(mapping);" not in source


def test_paragraph_placeholder_uses_mode_instead_of_parallel_ai_types():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function getParagraphMode" in source
    assert "function isParagraphPlaceholderType" in source
    assert "function isDataTemplateParagraphMode" in source
    assert 'data-placeholder-field="mode"' in source
    assert "数据说明段落" in source
    assert "根据材料撰写" in source
    assert "数据说明 + 材料续写" in source
    assert "{ value: 'paragraph', label: '正文段落' }" in source
    assert "{ value: 'field', label: '短字段' }" in source
    assert "{ value: 'static_text', label: '固定文案' }" in source
    assert "{ value: 'static_text', label: '固定文本' }" not in source


def test_placeholder_type_resolution_prefers_explicit_type_before_legacy_mode():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    helper = source[
        source.index("function getCanonicalPlaceholderType") : source.index(
            "function isParagraphMode"
        )
    ]

    assert "if (normalized) {" in helper
    assert "if (isParagraphMode(mapping?.mode)) return 'paragraph';" in helper
    assert helper.index("if (normalized) {") < helper.index(
        "if (isParagraphMode(mapping?.mode)) return 'paragraph';"
    )
    assert "getCanonicalPlaceholderType(mapping.type || inferPlaceholderType" not in source
    assert "getCanonicalPlaceholderType(draft.type || inferPlaceholderType" not in source
    assert "const draftType = draft.type || inferPlaceholderType(name);" not in source
    assert "const draftType = draft.type || inferPlaceholderType(placeholderName);" not in source
    assert source.count("const rawDraftType = draft.type || '';") == 4
    assert (
        source.count(
            "const draftType = getCanonicalPlaceholderType(rawDraftType, draft) || inferPlaceholderType(name);"
        )
        == 3
    )
    assert (
        "const draftType = getCanonicalPlaceholderType(rawDraftType, draft) "
        "|| inferPlaceholderType(placeholderName);"
    ) in source
    assert source.count("getParagraphMode(rawDraftType || draftType, draft, name);") == 3
    assert "getParagraphMode(rawDraftType || draftType, draft, placeholderName);" in source
    assert "const storedType = stored.type || '';" in source
    assert source.count("const storedType = mapping.type || '';") >= 2


def test_placeholder_type_helpers_execute_legacy_mode_resolution_rules():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    helper_block = source[
        source.index("function getCanonicalPlaceholderType") : source.index(
            "function getPlaceholderSourceKind"
        )
    ]
    cases = [
        {"type": "field", "mapping": {"mode": "evidence_ai"}, "placeholderName": "标题"},
        {
            "type": "static_text",
            "mapping": {"mode": "data_template"},
            "placeholderName": "说明",
        },
        {"type": "prompt", "mapping": {}, "placeholderName": "正文"},
        {"type": "composite_market_review", "mapping": {}, "placeholderName": "市场回顾"},
        {"type": "", "mapping": {"mode": "evidence_ai"}, "placeholderName": "历史正文"},
    ]
    runner = "\n".join(
        [
            f"const cases = {json.dumps(cases)};",
            "const results = (() => {",
            helper_block,
            "return cases.map(({ type, mapping, placeholderName }) => ({",
            "  canonicalType: getCanonicalPlaceholderType(type, mapping),",
            "  paragraphMode: getParagraphMode(type, mapping, placeholderName)",
            "}));",
            "})();",
            "process.stdout.write(JSON.stringify(results));",
        ]
    )

    result = subprocess.run(
        ["node", "--input-type=commonjs", "--eval", runner],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == [
        {"canonicalType": "field", "paragraphMode": ""},
        {"canonicalType": "static_text", "paragraphMode": ""},
        {"canonicalType": "paragraph", "paragraphMode": "evidence_ai"},
        {"canonicalType": "paragraph", "paragraphMode": "data_template_plus_evidence_ai"},
        {"canonicalType": "paragraph", "paragraphMode": "evidence_ai"},
    ]


def test_non_paragraph_types_ignore_preserved_legacy_paragraph_modes():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    paragraph_mode_source = source[
        source.index("function getParagraphMode") : source.index(
            "function getParagraphModeLabel"
        )
    ]
    detail_source = source[
        source.index("function renderSelectedPlaceholderDetail") : source.index(
            "function buildSimplePlaceholderFieldsHtml"
        )
    ]

    assert "const canonicalType = getCanonicalPlaceholderType(type, mapping);" in paragraph_mode_source
    assert "if (canonicalType !== 'paragraph') return '';" in paragraph_mode_source
    assert paragraph_mode_source.index("if (canonicalType !== 'paragraph') return '';") < paragraph_mode_source.index(
        "if (isParagraphMode(mapping?.mode)) return mapping.mode;"
    )
    assert "const paragraphMode = getParagraphMode(storedType, mapping, name);" in detail_source
    assert "const isPromptLike = usesEvidenceParagraphMode(storedType, paragraphMode);" in detail_source
    assert "const supportsDataTemplate = isDataTemplateParagraphMode(storedType, paragraphMode);" in detail_source


def test_placeholder_types_are_output_shapes_with_separate_sources():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "{ value: 'paragraph', label: '正文段落' }" in source
    assert "{ value: 'field', label: '短字段' }" in source
    assert "{ value: 'static_text', label: '固定文案' }" in source
    assert "{ value: 'table', label: '表格' }" in source
    assert "{ value: 'chart', label: '图表 / 图片' }" in source
    assert "{ value: 'config_text', label: '可配置文案' }" not in source
    assert "{ value: 'report_period', label: '报告日期' }" not in source
    assert "report_period: '短字段（旧：报告日期）'" in source
    assert "excel_cell: '短字段（旧：Excel 单元格取值）'" in source
    assert "excel_range: '短字段（旧：Excel 区域取值）'" in source
    assert "config_text: '固定文案（旧：可配置文案）'" in source
    assert "chart: '图表 / 图片'" in source
    assert "table: '表格'" in source


def test_prompt_placeholders_keep_writing_structure_entry_even_when_empty():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "const writingSteps = splitLines(writingStructureText);" in source
    assert "${isPromptLike ? `" in source
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
    assert "data-placeholder-field=" in source
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
    assert "if (isParagraphPlaceholderType(type, mapping))" in source
    assert "if (type === 'excel_commodity_market_review')" in source
    assert "if (isReportPeriodFieldPlaceholder(mapping.type || type, mapping, name))" in source
    assert "if (isExcelFieldPlaceholder(mapping.type || type, mapping, name))" in source
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


def test_generation_preflight_checks_each_placeholder_and_can_focus_it():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function buildPlaceholderReadinessItems(template, placeholders)" in source
    assert "function getPlaceholderReadinessIssue(mapping, placeholderName)" in source
    assert "缺少 Prompt 模板或语义 Query" in source
    assert "缺少 Excel 来源" in source
    assert "缺少固定文案" in source
    assert "缺少表格来源" in source
    assert "缺少图表来源" in source
    assert "data-template-placeholder-name=\"${esc(item.placeholderName || '')}\"" in source
    assert 'data-template-check-action="focus-placeholder"' in source
    assert "selectTemplatePlaceholder(placeholderName);" in source
    assert "openPlaceholderConfigEditorModal(template, item.editorSection || 'basic')" in source
    assert ".validation-item.placeholder-issue" in css


def test_placeholder_configuration_uses_three_state_readiness():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function getPlaceholderLifecycleStatus(template, mapping, placeholderName)" in source
    assert "state: 'missing'" in source
    assert "state: 'confirm'" in source
    assert "state: 'ready'" in source
    assert "缺配置" in source
    assert "需确认" in source
    assert "可生成" in source
    assert "getPlaceholderReadinessIssue(mapping, placeholderName)" in source
    assert "healthEl.classList.toggle('confirm'" in source
    assert "healthEl.classList.toggle('missing'" in source
    assert ".template-config-toolbar-meta.confirm" in css
    assert ".template-config-toolbar-meta.missing" in css


def test_placeholder_configuration_wizard_navigation_stays_single_placeholder():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'id="template-placeholder-wizard-progress"' in html
    assert 'id="btn-template-prev-placeholder"' in html
    assert 'id="btn-template-next-incomplete-placeholder"' in html
    assert 'id="btn-template-save-next-placeholder"' in html
    assert "function buildPlaceholderWizardState(template)" in source
    assert "function selectAdjacentTemplatePlaceholder(direction, incompleteOnly = false)" in source
    assert "function renderPlaceholderWizardControls(template)" in source
    assert "上一个" in html
    assert "下一个未完成" in html
    assert "保存并下一个" in html
    assert ".placeholder-wizard-controls" in css
    assert 'class="placeholder-config-table"' not in source


def test_placeholder_configurator_uses_original_embedded_grid_layout():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="template-workbench-main-grid template-config-grid"' in html
    assert 'class="template-workbench-left template-config-rail"' in html
    assert 'class="template-workbench-panel template-config-common-panel"' in html
    assert 'id="template-common-rules"' in html
    assert 'id="template-project-check-details"' in html
    assert 'id="template-section-config-editor"' in html
    config_start = html.index('class="template-workbench-main-grid template-config-grid"')
    editor_start = html.index('id="template-section-config-editor"', config_start)
    editor_end = html.index('id="template-config-editor-modal"', editor_start)
    rail_html = html[config_start:editor_start]
    editor_html = html[editor_start:editor_end]
    assert 'class="template-workbench-panel placeholder-configurator-rail-panel"' not in rail_html
    assert 'id="template-placeholder-map"' not in rail_html
    assert 'id="template-placeholder-map"' in editor_html
    assert 'class="template-placeholder-status-strip"' in editor_html
    assert "placeholder-issue-queue placeholder-issue-queue-inline" in editor_html
    assert "选择占位符" in html
    assert 'id="template-placeholder-progress-bar"' in html
    assert "预检问题" in html
    assert 'id="template-placeholder-issue-list"' in html
    assert 'id="template-placeholder-issue-count"' in html
    assert "function renderPlaceholderIssueQueue(template, placeholderReadiness)" in source
    assert "renderPlaceholderIssueQueue(template, placeholderReadiness);" in source
    assert 'data-template-check-action="focus-placeholder"' in source
    assert ".placeholder-configurator-rail-panel" in css
    assert ".template-placeholder-status-strip" in css
    assert ".placeholder-issue-queue-inline" in css
    assert ".placeholder-issue-queue.is-empty" in css
    assert ".template-placeholder-progress-bar" in css
    assert ".placeholder-issue-queue-item" in css
    assert 'class="template-placeholder-wizard-shell"' not in html
    assert ".template-placeholder-wizard-shell" not in css


def test_placeholder_toolbar_has_three_zones_and_incomplete_only_next_actions():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="template-config-editor-selector template-config-toolbar-zone"' in html
    assert 'class="template-config-toolbar-chips template-config-toolbar-zone"' in html
    assert 'class="template-placeholder-actions template-config-toolbar-zone"' in html
    assert ".template-config-toolbar-zone" in css
    assert ".template-config-toolbar-zone + .template-config-toolbar-zone::before" in css
    assert ".template-placeholder-actions.has-incomplete #btn-template-save-next-placeholder" in css
    assert ".template-placeholder-actions.is-complete #btn-template-save-next-placeholder" in css
    assert (
        ".template-placeholder-status-strip.is-complete #btn-template-next-incomplete-placeholder"
        in css
    )

    assert "const hasIncomplete = state.incompleteItems.length > 0;" in source
    assert "actionsEl.classList.toggle('has-incomplete', hasIncomplete);" in source
    assert "actionsEl.classList.toggle('is-complete', !hasIncomplete);" in source
    assert "statusStripEl.classList.toggle('has-incomplete', hasIncomplete);" in source
    assert "statusStripEl.classList.toggle('is-complete', !hasIncomplete);" in source
    assert "nextIncompleteBtn.hidden = !hasIncomplete;" in source
    assert "saveNextBtn.hidden = !hasIncomplete;" in source
    assert "saveNextBtn.disabled = !state.totalCount || !hasIncomplete;" in source


def test_config_page_uses_compact_left_nav_and_lighter_detail_blocks():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "/* Compact config navigation polish */" in css
    compact_nav = css[css.index("/* Compact config navigation polish */") :]
    assert ".template-config-common-panel .template-common-summary-card > summary" in compact_nav
    assert "min-height: 54px;" in compact_nav
    assert "grid-template-columns: 22px minmax(0, 1fr) minmax(44px, auto);" in compact_nav
    assert ".template-config-common-panel .template-common-rules" in compact_nav
    assert "gap: 7px;" in compact_nav

    assert "/* Lighter placeholder detail blocks */" in css
    detail_polish = css[css.index("/* Lighter placeholder detail blocks */") :]
    assert ".template-config-editor-panel .template-placeholder-detail-form" in detail_polish
    assert "gap: 10px;" in detail_polish
    assert (
        ".template-config-editor-panel .template-placeholder-detail-form > label" in detail_polish
    )
    assert "border-color: rgba(255,255,255,0.065);" in detail_polish
    assert "background: rgba(255,255,255,0.030);" in detail_polish
    assert ".template-config-editor-panel .template-keyword-summary" in detail_polish
    assert "min-height: 44px;" in detail_polish


def test_placeholder_wizard_visual_order_and_picker_menu_are_closed_by_default():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")
    start = source.index("formEl.innerHTML = `")
    end = source.index("if (advancedFormEl)", start)
    form_source = source[start:end]

    assert form_source.index("${editorHtml}") < form_source.index(
        "buildPlaceholderConfigSummaryHtml"
    )
    assert ".placeholder-configurator-rail-panel .placeholder-select-menu[hidden]" in css
    assert "display: none !important;" in css
    assert ".placeholder-configurator-rail-panel .placeholder-select-option" in css
    assert ".placeholder-configurator-rail-panel .template-placeholder-map::after" in css
    assert "placeholder-purpose-card .codicon" not in css


def test_placeholder_config_keeps_common_and_advanced_config_in_main_page():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    config_start = html.index('class="template-workbench-main-grid template-config-grid"')
    config_end = html.index('id="template-config-editor-modal"', config_start)
    config_html = html[config_start:config_end]

    assert 'id="btn-template-config-advanced"' in html
    assert 'id="btn-template-advanced-config"' in config_html
    assert 'id="template-common-rules"' in config_html
    assert 'id="template-project-check-details"' in config_html
    assert 'id="template-placeholder-detail-form"' in config_html
    assert 'class="template-placeholder-wizard-shell"' not in html

    assert 'class="placeholder-purpose-card-icon codicon' not in source
    assert 'class="placeholder-field-source-tabs"' not in source
    assert 'class="placeholder-field-preview-card"' not in source
    assert 'class="placeholder-wizard-current-card"' not in source

    assert ".template-placeholder-wizard-shell" not in css
    assert ".placeholder-wizard-stage" not in css
    assert ".placeholder-wizard-footer-actions" not in css
    assert ".placeholder-purpose-card-icon" not in css
    assert ".placeholder-field-source-tabs" not in css


def test_save_placeholder_can_confirm_and_jump_to_next_incomplete():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "markSelectedPlaceholderConfirmed(template);" in source
    assert "saveCurrentSectionConfig({" in source
    assert "jumpToNextIncomplete = false" in source
    assert "if (jumpToNextIncomplete) {" in source
    assert "selectAdjacentTemplatePlaceholder(1, true);" in source
    assert "savePlaceholderNextBtn.addEventListener('click'" in source
    assert "successMessage: '占位符配置已保存，已跳到下一个未完成项'" in source


def test_upload_enters_first_configuration_mode_for_new_template():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function enterFirstPlaceholderConfigurationMode(project)" in source
    assert "await enterFirstPlaceholderConfigurationMode(data);" in source
    assert "setStoredTemplateDetailMode('config');" in source
    assert "applyTemplateDetailMode('config');" in source
    assert "selectFirstActionablePlaceholder(template);" in source
    assert "首次配置：请逐个确认占位符用途和来源" in source


def test_generate_report_blocks_when_placeholder_preflight_has_issues():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert (
        "function getTemplateGenerationPreflight(template = getCurrentWorkbenchTemplate())"
        in source
    )
    assert "function blockReportGenerationForPreflight(preflight)" in source
    assert "const preflight = getTemplateGenerationPreflight(template);" in source
    assert "if (!preflight.ok) {" in source
    assert "blockReportGenerationForPreflight(preflight);" in source
    assert "return;" in source
    assert "请先处理生成预检中的占位符配置问题" in source
    assert (
        "renderTemplateValidationPreview(template, preflight.sections, preflight.placeholders);"
        in source
    )
    assert "placeholderReadiness: placeholderReadiness" in source
    assert (
        "contentOk = passedChecks === validationChecks.length && placeholderIssueCount === 0"
        in source
    )


def test_generation_preflight_prefers_backend_compiled_plan():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "function getCompiledReportPlan(template)" in source
    assert "function buildCompiledPlanReadinessItems(compiledPlan)" in source
    assert "const compiledPlan = getCompiledReportPlan(template);" in source
    assert "const compiledPlanItems = buildCompiledPlanReadinessItems(compiledPlan);" in source
    assert (
        "compiledPlanItems.length ? compiledPlanItems : buildPlaceholderReadinessItems(template, placeholders)"
        in source
    )
    assert "readiness.compiledPlan?.warnings" in source
    assert "后端计划" in source


def test_generation_preflight_groups_prompt_evidence_and_output_assets():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert (
        "function buildPreflightReviewGroups(readiness, checks, placeholderReadiness, context)"
        in source
    )
    assert "function renderPreflightReviewGroup(group)" in source
    assert "Prompt 覆盖" in source
    assert "Evidence 覆盖" in source
    assert "输出资产" in source
    assert "compiledPlan?.placeholders" in source
    assert "prompt_found === false" in source
    assert "retrieval_ready === false" in source
    assert "deterministic === true" in source
    assert ".template-preflight-group" in css
    assert ".template-preflight-group-title" in css


def test_generation_preflight_surfaces_prioritized_task_queue_and_evidence_samples():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function buildEvidencePreviewRows(readiness)" in source
    assert "function getRunLogEvidenceSamples(runLog)" in source
    assert "function buildPreflightTaskQueue" not in source
    assert "function renderPreflightTaskQueue" not in source
    assert "Evidence 抽样" in source
    assert "matched_terms" in source
    assert "retrieval_config?.must_any" in source
    assert ".template-evidence-sample" in css


def test_report_config_check_uses_collapsed_summary_and_on_demand_details():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="template-project-check-summary"' in html
    assert 'id="template-project-check-status"' in html
    assert 'id="template-project-check-actions"' in html
    assert 'id="template-validation-details"' in html
    start = html.index('id="template-project-check-details"')
    assert ' open' not in html[start:html.index('>', start)]


def test_generation_preflight_uses_ready_summary_and_blocker_actions():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function buildPreflightDisplayModel(" in source
    assert "state: 'ready'" in source
    assert "state: 'blocked'" in source
    assert "function renderPreflightSummary(" in source
    assert "function renderPreflightActions(" in source
    assert "actions.slice(0, 3)" in source
    assert "function buildPreflightReviewGroups(" in source
    assert ".template-project-check-actions" in css
    assert ".template-validation-details" in css


def test_report_generation_surfaces_current_issue_settings_bar():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function bindHeroMetaInputs()" in source
    assert "报告日期" in source
    assert "证据窗口" in source
    assert "template-generation-period-input" in source
    assert "template-generation-lookback-input" in source
    assert ".template-generation-meta-input" in css


def test_report_generation_delivery_check_card_and_repair_return_path():
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "function buildDeliveryCheckRows(runResult, runLog, latestReport, readiness)" in source
    assert "function renderDeliveryCheckCard(runResult, runLog, latestReport, readiness)" in source
    assert "交付检查" in source
    assert "生成段落" in source
    assert "缺失段落" in source
    assert "Evidence 总数" in source
    assert "Warnings" in source
    assert "空占位符" in source
    assert "图表/表格" in source
    assert "setStoredTemplateDetailMode" in source
    assert ".template-delivery-check-card" in css


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
    assert (
        "const needsEvidenceDefaults = type === 'paragraph' && usesEvidenceParagraphMode(storedType, paragraphMode);"
        in source
    )
    assert "stored.prompt_template || resolvePromptTemplateName(key, project)" in source
    assert "stored.query_source || inferQuerySource(key, project)" in source
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
    assert "project?.ppt_placeholders" in source
    assert "使用项目包解析出的 Word 占位符" in source


def test_report_project_upload_supports_ppt_template_projects():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = TEMPLATES_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'id="project-type-select"' in html
    assert '<select id="project-type-select"' not in html
    assert 'type="hidden" id="project-type-select"' in html
    assert 'data-project-type-option="word"' in html
    assert 'data-project-type-option="ppt"' in html
    assert 'id="project-ppt-template-input"' in html
    assert 'accept=".pptx"' in html
    assert "project-ppt-template-input" in source
    assert "setReportProjectUploadType" in source
    assert "data-project-type-option" in source
    assert "project_type" in source
    assert "formData.append('project_type', projectType);" in source
    assert "formData.append('ppt_template', pptFile);" in source
    assert "请选择 PPT 模板" in source
    assert ".upload-project-type-control" in css
    assert ".upload-project-type-option.active" in css


def test_common_generation_constraints_preserve_commas():
    source = TEMPLATES_JS.read_text(encoding="utf-8")

    assert "field === 'generation_constraints'" in source
    assert "value = splitLines(input.value);" in source
    assert "value = splitDelimitedList(input.value);" in source
    assert (
        "field === 'generation_constraints'\n            || field === 'hard_constraints.forbidden_phrases'"
        not in source
    )


def test_initial_load_uses_navigation_to_activate_content_section():
    source = APP_JS.read_text(encoding="utf-8")

    assert "function getInitialSection()" in source
    assert "localStorage.getItem('af-active-section')" in source
    assert "localStorage.setItem('af-active-section', section)" in source
    assert "navigateTo(getInitialSection());" in source
    assert (
        "loadDashboard();\n    startCrawlFeedPolling();\n    startWorkersPolling();" not in source
    )


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
    assert "if (isSystemDatePlaceholder(name)) return 'field';" in source
    assert "lines.push(`    mode: ${paragraphMode}`);" in source
    assert "lines.push('    format: date');" in source
    assert "lines.push('    source:');" in source
    assert "lines.push('      kind: report_period');" in source
    assert "lines.push('    insert:');" in source
    assert "replace_placeholder" in source


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
    assert (
        "background: var(--success);"
        not in css.split(".template-generation-flow-step.done .step-index", 1)[1].split("}", 1)[0]
    )
    assert "#template-workbench-summary {\n    border: 0;" in css
    assert ".template-generation-flow-panel {\n    border: 0;" in css
    assert ".template-generation-step-panel {\n    border: 0;" in css
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
