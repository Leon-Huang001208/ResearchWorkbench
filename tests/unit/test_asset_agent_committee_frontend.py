"""Static wiring tests for asset Agent committee frontend."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
ASSET_JS = ROOT / "app" / "web" / "static" / "js" / "asset.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"


def test_asset_page_has_agent_committee_panel():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'id="asset-agent-committee-card"' in html
    assert 'id="asset-agent-committee-status"' in html
    assert 'id="asset-agent-committee-summary"' in html
    assert 'id="asset-agent-committee-views"' in html
    assert "多 Agent 委员会" in html


def test_asset_js_fetches_and_renders_agent_committee():
    source = ASSET_JS.read_text(encoding="utf-8")

    assert "'/api/assets/agent-committee'" in source
    assert "loadAssetAgentCommittee" in source
    assert "renderAssetAgentCommittee" in source
    assert "renderAssetAgentCommitteeError" in source


def test_asset_committee_styles_exist():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".asset-agent-committee-card" in css
    assert ".agent-committee-view-grid" in css
    assert ".agent-view-card" in css
