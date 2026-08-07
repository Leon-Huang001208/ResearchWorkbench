from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
FUNDS_JS = ROOT / "app" / "web" / "static" / "js" / "funds.js"


def test_fund_intelligence_nav_and_section_are_present():
    template = INDEX_HTML.read_text(encoding="utf-8")

    assert 'data-section="funds"' in template
    assert "基金情报" in template
    assert 'id="section-funds"' in template
    assert 'id="fund-symbol"' in template
    assert 'id="fund-portfolio-input"' in template
    assert 'id="fund-ingest-rows"' in template


def test_fund_panel_is_wired_into_app_entrypoint():
    app_js = APP_JS.read_text(encoding="utf-8")

    assert "from './funds.js" in app_js
    assert "window.initFundsPanel = initFundsPanel" in app_js
    navigation = app_js[
        app_js.index("function navigateTo(section, options = {})") : app_js.index(
            "window.navigateTo = navigateTo;"
        )
    ]
    assert "if (targetSection === 'funds') initFundsPanel();" in navigation


def test_funds_module_calls_backend_contracts():
    funds_js = FUNDS_JS.read_text(encoding="utf-8")

    assert "export function initFundsPanel" in funds_js
    assert "/api/funds/${encodeURIComponent(symbol)}" in funds_js
    assert "/api/funds/${encodeURIComponent(symbol)}/exposure" in funds_js
    assert "/api/funds/portfolio/exposure" in funds_js
    assert "/api/funds/ingest" in funds_js
