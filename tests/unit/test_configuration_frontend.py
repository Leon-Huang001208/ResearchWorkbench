"""系统配置中心前端静态回归测试。"""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEX_HTML = ROOT / "app" / "web" / "templates" / "index.html"
APP_JS = ROOT / "app" / "web" / "static" / "js" / "app.js"
CONFIGURATION_JS = ROOT / "app" / "web" / "static" / "js" / "configuration.js"
STYLE_CSS = ROOT / "app" / "web" / "static" / "style.css"


def test_configuration_navigation_and_five_sections_are_present():
    html = INDEX_HTML.read_text(encoding="utf-8")

    assert 'app.js?v=20260712config1' in html
    assert 'data-section="config"' in html
    assert 'id="section-config"' in html
    assert 'id="config-readiness-overview"' in html
    for section in ("llm", "zhiqiu", "ifind", "database", "advanced"):
        assert f'id="config-{section}-form"' in html
        assert f'data-config-save="{section}"' in html


def test_configuration_page_exposes_readiness_and_connection_test_controls():
    html = INDEX_HTML.read_text(encoding="utf-8")

    for category in ("overall", "llm", "zhiqiu", "ifind", "database"):
        assert f'data-readiness="{category}"' in html
    for section in ("llm", "zhiqiu", "ifind"):
        assert f'data-config-test="{section}"' in html
    assert "重启后生效" in html


def test_configuration_module_uses_expected_api_contract_and_is_initialized_by_navigation():
    app_source = APP_JS.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "import { initConfigurationPage } from './configuration.js'" in app_source
    assert "if (section === 'config') initConfigurationPage();" in app_source
    assert "export async function initConfigurationPage()" in source
    assert "apiCall('GET', '/api/config')" in source
    assert "apiCall('PUT', `/api/config/${section}`" in source
    assert "apiCall('POST', `/api/config/${section}/test`" in source


def test_dynamic_configuration_rows_support_add_remove_and_original_names():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "renderProviders" in source
    assert "renderTaskRoutes" in source
    assert "renderZhiqiuAccounts" in source
    assert "original_name" in source
    assert "data-add-provider" in source
    assert "data-add-task-route" in source
    assert "data-add-zhiqiu-account" in source
    assert "aria-label" in source


def test_configuration_secrets_are_blank_and_require_explicit_clear():
    html = INDEX_HTML.read_text(encoding="utf-8")
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert 'type="password"' in html
    assert "clear_api_key" in source
    assert "clear_password" in source
    assert "configured" in source
    assert "masked_value" not in source
    assert "localStorage" not in source
    assert "dataset.secret" not in source


def test_api_strings_are_rendered_without_inner_html():
    source = CONFIGURATION_JS.read_text(encoding="utf-8")

    assert "createElement" in source
    assert "textContent" in source
    assert "replaceChildren" in source
    assert "innerHTML" not in source


def test_configuration_styles_cover_layout_states_and_accessible_focus():
    css = STYLE_CSS.read_text(encoding="utf-8")

    assert ".configuration-layout" in css
    assert "grid-template-columns: minmax(0, 1fr) minmax(280px, 0.38fr);" in css
    assert ".config-status.ready" in css
    assert ".config-status.missing" in css
    assert ".config-status.error" in css
    assert ".config-status.restart" in css
    assert ".configuration-page :focus-visible" in css
    assert "@media (max-width: 900px)" in css
