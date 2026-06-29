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
