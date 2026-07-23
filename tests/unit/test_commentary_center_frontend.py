"""Static wiring tests for the commentary production center frontend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
COMMENTARY_JS = ROOT / "app" / "web" / "static" / "js" / "commentary.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"


def test_commentary_center_is_independent_workspace_not_report_subtab():
    html = INDEX_HTML.read_text(encoding="utf-8")
    app_js = APP_JS.read_text(encoding="utf-8")

    assert 'data-section="commentary"' in html
    assert "<span>点评生产</span>" in html
    assert 'id="section-commentary"' in html
    assert 'id="section-templates"' in html
    assert html.index('data-section="commentary"') < html.index('data-section="templates"')
    assert "from './commentary.js" in app_js
    assert "initCommentaryCenter" in app_js
    assert "if (section === 'commentary') initCommentaryCenter();" in app_js


def test_commentary_center_page_exposes_data_evidence_judgement_and_draft_regions():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="commentary-template-list"' in html
    assert 'id="commentary-attribution-panel"' in html
    assert 'id="commentary-data-snapshot"' in html
    assert 'id="commentary-evidence-pack"' in html
    assert 'id="commentary-subjective-judgement"' in html
    assert 'id="commentary-draft-output"' in html
    assert 'id="btn-commentary-generate-draft"' in html
    assert "数据快照" in html
    assert "证据包" in html
    assert "主观判断" in html
    assert "草稿输出" in html


def test_commentary_module_defines_recipes_and_local_draft_generation():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "COMMENTARY_RECIPES" in source
    assert "每日收盘点评" in source
    assert "市场大跌归因" in source
    assert "行业板块点评" in source
    assert "海外扰动点评" in source
    assert "产品/ETF配置点评" in source
    assert "generateCommentaryDraft" in source
    assert "buildCommentaryDraft" in source
    assert 'data-confidence="confirmed"' in source
    assert 'data-confidence="reported"' in source
    assert 'data-confidence="interpretation"' in source
    assert 'data-confidence="judgement"' in source


def test_commentary_module_loads_recipe_contract_from_backend_with_fallback():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "loadCommentaryRecipes" in source
    assert "/api/commentary/recipes" in source
    assert "backendRecipes" in source
    assert "COMMENTARY_RECIPES" in source
    assert "commentary_recipes_load_failed" in source


def test_commentary_module_loads_context_pack_from_api_and_prefills_inputs():
    source = COMMENTARY_JS.read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="btn-commentary-refresh-context"' in html
    assert 'id="commentary-context-status"' in html
    assert "loadCommentaryContext" in source
    assert "/api/commentary/context?recipe_id=" in source
    assert "data_snapshot_text" in source
    assert "evidence_pack_text" in source
    assert "commentary-data-snapshot" in source
    assert "commentary-evidence-pack" in source
    assert "commentary-context-status" in source
    assert "点评上下文已更新" in source
    assert "renderAttributionSignals" in source
    assert "attribution_signals" in source
    assert "commentary_context_render_failed" in source
    assert "上下文渲染失败" in source


def test_dashboard_module_distinguishes_fetch_failure_from_render_failure():
    dashboard_js = (ROOT / "app" / "web" / "static" / "js" / "dashboard.js").read_text(
        encoding="utf-8"
    )

    assert "dashboard_fetch_failed" in dashboard_js
    assert "dashboard_render_failed" in dashboard_js
    assert "仪表盘渲染失败" in dashboard_js


def test_commentary_module_generates_draft_via_backend_api_with_local_fallback():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "bindCommentaryActions" in source
    assert ".getElementById('btn-commentary-generate-draft')" in source
    assert ".addEventListener('click', generateCommentaryDraft)" in source
    assert "/api/commentary/draft" in source
    assert "latestContextPack" in source
    assert "currentContextPromise" in source
    assert "if (isLoadingContext) await currentContextPromise;" in source
    assert "subjective_judgement" in source
    assert "renderBackendDraft" in source
    assert "draft_markdown" in source
    assert "本地兜底草稿已生成" in source


def test_commentary_module_renders_citation_verification_metadata():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "verification_status" in source
    assert "confidence_score" in source
    assert "formatCitationMeta" in source
    assert "待核验" in source


def test_commentary_module_sends_and_renders_attribution_signals():
    source = COMMENTARY_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert "formatAttributionStrength" in source
    assert "commentary-attribution-item" in source
    assert "latestContextPack?.attribution_signals" in source
    assert ".commentary-attribution-panel" in css


def test_commentary_center_has_workbench_layout_styles():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".commentary-workbench" in css
    assert ".commentary-template-list" in css
    assert ".commentary-studio-grid" in css
    assert ".commentary-draft-output" in css
    assert ".commentary-confidence-grid" in css


def test_commentary_center_exposes_evidence_driven_workbench_regions():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="commentary-workbench-toolbar"' in html
    assert 'class="commentary-command-center"' in html
    assert 'class="commentary-workflow-rail"' in html
    assert 'class="commentary-evidence-workspace"' in html
    assert 'class="commentary-draft-workspace"' in html
    assert 'class="commentary-request-preview"' in html
    assert 'id="commentary-audience-control"' in html
    assert 'id="commentary-length-control"' in html
    assert 'id="commentary-evidence-board"' in html
    assert 'id="commentary-evidence-list"' in html
    assert 'id="commentary-selected-evidence-count"' in html
    assert 'id="commentary-draft-sections"' in html
    assert 'id="commentary-quality-panel"' in html
    assert "证据工作区" in html
    assert "分段草稿" in html
    assert "生产流程" in html
    assert "生成请求预览" in html


def test_commentary_center_uses_workspace_mode_layout():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = COMMENTARY_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="commentary-workspace-tabs"' in html
    for mode in ("template", "subject", "content", "draft"):
        assert f'data-commentary-workspace="{mode}"' in html
        assert f'data-commentary-workspace-panel="{mode}"' in html

    assert "选择模板" in html
    assert "确认对象" in html
    assert "内容清单" in html
    assert "草稿生成" in html
    assert html.index('data-commentary-workspace="template"') < html.index(
        'data-commentary-workspace="subject"'
    )
    assert 'data-commentary-workspace="template">选择模板</button>' in html
    assert "switchCommentaryWorkspace" in source
    assert "switchCommentaryWorkspace(mode = 'template')" in source
    assert ".commentary-production-shell" in css
    assert ".commentary-workspace-panel.active" in css


def test_commentary_center_first_screen_focuses_on_template_selection():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-commentary-workspace="template">选择模板</button>' in html
    assert (
        'class="commentary-workspace-panel active" data-commentary-workspace-panel="template"'
        in html
    )
    assert "先选择要写哪类点评" in html
    assert "每日收盘点评" in html
    assert html.index('data-commentary-workspace-panel="template"') < html.index(
        'id="commentary-subject-panel"'
    )


def test_commentary_center_treats_commentary_target_as_template_dependent():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'id="commentary-subject-panel"' in html
    assert 'id="commentary-target-mode-control"' in html
    assert 'id="commentary-target-input"' in html
    assert 'id="commentary-target-candidate"' in html
    assert "沿用模板默认对象" in html
    assert "自动发现补充对象" in html
    assert "手动指定对象" in html
    assert "每日收盘点评可直接使用模板默认对象" in html
    assert ".commentary-subject-panel" in css
    assert ".commentary-step-hero" in css


def test_commentary_center_uses_template_then_target_then_content_checklist_before_draft():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert 'id="commentary-template-list"' in html
    assert 'id="commentary-content-checklist"' in html
    assert html.index('data-commentary-workspace-panel="template"') < html.index(
        'id="commentary-subject-panel"'
    )
    assert html.index('id="commentary-subject-panel"') < html.index(
        'id="commentary-content-checklist"'
    )
    for item in ("核心观点", "行情事实", "消息面证据", "归因解释", "风险提示", "后续观察"):
        assert item in html
    assert "readSelectedContentSections" in source
    assert "content_sections" in source


def test_commentary_center_keeps_evidence_logic_and_config_as_advanced_details():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="commentary-advanced-details"' in html
    assert "证据明细" in html
    assert "生成逻辑" in html
    assert "生成配置" in html
    assert 'id="commentary-logic-recipe"' in html
    assert 'id="commentary-logic-evidence"' in html
    assert 'id="commentary-logic-attribution"' in html
    assert 'id="commentary-logic-prompt"' in html
    assert 'id="commentary-logic-quality"' in html
    assert 'id="commentary-logic-run"' in html
    assert ".commentary-logic-workspace" in css
    assert ".commentary-logic-card" in css
    assert ".commentary-logic-chain" in css
    assert ".commentary-advanced-details" in css


def test_commentary_module_renders_generation_logic_from_current_request_state():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "renderGenerationLogic" in source
    assert "buildGenerationLogicSnapshot" in source
    assert "renderLogicList" in source
    assert "commentary-logic-recipe" in source
    assert "commentary-logic-evidence" in source
    assert "commentary-logic-attribution" in source
    assert "commentary-logic-prompt" in source
    assert "commentary-logic-quality" in source
    assert "commentary-logic-run" in source
    assert "verification_status" in source
    assert "quality gate" in source


def test_commentary_center_workflow_steps_expose_live_state_hooks():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = COMMENTARY_JS.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    for step in ("template", "subject", "content", "draft"):
        assert f'data-commentary-step="{step}"' in html
    assert html.index('data-commentary-step="template"') < html.index(
        'data-commentary-step="subject"'
    )
    assert 'data-commentary-step="template" data-step-state="active"' in html

    assert "updateCommentaryWorkflow" in source
    assert "commentary-workflow-step" in source
    assert "data-step-state" in source
    assert '.commentary-workflow-list li[data-step-state="done"]' in css
    assert '.commentary-workflow-list li[data-step-state="active"]' in css


def test_commentary_center_polishes_toolbar_and_draft_empty_state():
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert 'class="commentary-status-strip"' in html
    assert 'class="commentary-draft-title-block"' in html
    assert 'class="commentary-draft-empty-state"' in html
    assert 'class="commentary-empty-checklist"' in html
    assert "等待生成草稿" in html
    assert ".commentary-draft-empty-state" in css
    assert ".commentary-empty-checklist" in css
    assert ".commentary-workbench-toolbar" in css
    assert "grid-template-columns: minmax(160px, 0.5fr) minmax(320px, 1fr) auto" in css


def test_commentary_center_controls_match_report_workbench_style():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".commentary-workspace-tabs" in css
    assert ".commentary-workspace-tab.active" in css
    assert "background: var(--apple-control-active)" in css
    assert ".commentary-control-grid label:has(select)::after" in css
    assert ".commentary-writing-controls select" in css
    assert "appearance: none" in css
    assert "border-radius: 11px" in css
    assert ".commentary-production-shell .commentary-workflow-rail" in css
    assert "box-shadow: none" in css


def test_commentary_center_supports_auto_or_manual_commentary_target():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert 'id="commentary-target-mode-control"' in html
    assert 'id="commentary-target-input"' in html
    assert 'id="commentary-target-candidate"' in html
    assert "沿用模板默认对象" in html
    assert "自动发现补充对象" in html
    assert "手动指定对象" in html
    assert "inferCommentaryTarget" in source
    assert "renderCommentaryTargetCandidate" in source
    assert "target_mode" in source
    assert "template_default" in source
    assert "target_name" in source


def test_commentary_module_supports_selective_evidence_and_section_editing():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "selectedEvidenceKeys" in source
    assert "renderEvidenceItems" in source
    assert "toggleCommentaryEvidence" in source
    assert "selectedEvidenceItems" in source
    assert "commentary-evidence-list" in source
    assert "commentary-selected-evidence-count" in source
    assert "renderDraftSections" in source
    assert "applySectionAction" in source
    assert "commentary-section-card" in source
    assert "writing_preferences" in source


def test_commentary_module_groups_evidence_into_scannable_sections():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "groupEvidenceItems" in source
    assert "renderEvidenceGroup" in source
    assert "commentary-evidence-group" in source
    assert "消息主线" in source
    assert "行情验证" in source
    assert "研报材料" in source
    assert "判断补充" in source
    assert "formatEvidenceImpact" in source
    assert "formatEvidenceTerms" in source


def test_commentary_section_actions_call_backend_rewrite_with_local_fallback():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "rewriteCommentarySection" in source
    assert "/api/commentary/section-rewrite" in source
    assert "buildSectionRewriteRequest" in source
    assert "applyLocalSectionAction" in source
    assert "commentary_section_rewrite_failed" in source


def test_commentary_generation_runs_quality_check_after_draft():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "runCommentaryQualityCheck" in source
    assert "/api/commentary/quality-check" in source
    assert "renderQualityIssues" in source
    assert "commentary_quality_check_failed" in source
    assert "draft_markdown" in source


def test_commentary_generation_records_run_log_after_quality_check():
    source = COMMENTARY_JS.read_text(encoding="utf-8")

    assert "recordCommentaryRun" in source
    assert "/api/commentary/runs" in source
    assert "commentary_run_record_failed" in source
    assert "quality_status" in source
    assert "selected_evidence_count" in source


def test_commentary_workbench_has_compact_evidence_and_editor_styles():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".commentary-workbench-toolbar" in css
    assert ".commentary-command-center" in css
    assert ".commentary-workflow-rail" in css
    assert ".commentary-evidence-workspace" in css
    assert ".commentary-draft-workspace" in css
    assert ".commentary-request-preview" in css
    assert ".commentary-status-strip" in css
    assert ".commentary-evidence-group" in css
    assert ".commentary-evidence-board" in css
    assert ".commentary-evidence-item" in css
    assert ".commentary-section-card" in css
    assert ".commentary-editor-grid" in css
