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
    assert "data-confidence=\"confirmed\"" in source
    assert "data-confidence=\"reported\"" in source
    assert "data-confidence=\"interpretation\"" in source
    assert "data-confidence=\"judgement\"" in source


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
