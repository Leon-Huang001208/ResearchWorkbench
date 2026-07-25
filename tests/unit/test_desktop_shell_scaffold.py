"""Static wiring tests for the AlphaFoundry desktop shell scaffold."""

import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TAURI_CONFIG = ROOT / "src-tauri" / "tauri.conf.json"
TAURI_LIB = ROOT / "src-tauri" / "src" / "lib.rs"
PACKAGE_JSON = ROOT / "package.json"
BOOTSTRAP_JS = ROOT / "desktop" / "dist" / "bootstrap.js"
BOOTSTRAP_HTML = ROOT / "desktop" / "dist" / "index.html"
LAUNCHER = ROOT / "scripts" / "desktop" / "backend_launcher.py"
RUN_BACKEND_SH = ROOT / "scripts" / "desktop" / "run_backend.sh"
RESTART_APP_SH = ROOT / "scripts" / "desktop" / "restart_app.sh"
PATCH_MACOS_AUTOMATION_SH = ROOT / "scripts" / "desktop" / "patch_macos_automation_permissions.sh"
BUILD_SIDECAR_SH = ROOT / "scripts" / "desktop" / "build_sidecar.sh"
BUILD_SIDECAR_PY = ROOT / "scripts" / "desktop" / "build_sidecar.py"
PREPARE_SIDECAR = ROOT / "scripts" / "desktop" / "prepare_tauri_sidecar.py"
WRITE_RELEASE_CONFIG = ROOT / "scripts" / "desktop" / "write_tauri_release_config.py"
DESKTOP_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"
MACOS_ARM_SIDECAR = ROOT / "src-tauri" / "binaries" / "alphafoundry-backend-aarch64-apple-darwin"
MACOS_ICON = ROOT / "src-tauri" / "icons" / "icon.icns"
WINDOWS_ICON = ROOT / "src-tauri" / "icons" / "icon.ico"


def load_launcher_module():
    spec = importlib.util.spec_from_file_location("desktop_backend_launcher", LAUNCHER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_tauri_config_wraps_existing_fastapi_workbench():
    config = json.loads(TAURI_CONFIG.read_text(encoding="utf-8"))

    assert config["productName"] == "AlphaFoundry"
    assert config["build"]["devUrl"] == "http://127.0.0.1:8765"
    assert "node scripts/desktop/run_backend.js" in config["build"]["beforeDevCommand"]
    assert config["build"]["frontendDist"] == "../desktop/dist"
    assert config["bundle"]["targets"] == "all"
    assert config["bundle"]["icon"] == [
        "icons/icon.png",
        "icons/icon.icns",
        "icons/icon.ico",
    ]
    assert "binaries/alphafoundry-backend" in config["bundle"]["externalBin"]
    assert "http://127.0.0.1:8765" in config["app"]["security"]["csp"]


def test_macos_icon_is_available_for_tauri_resource_generation():
    assert MACOS_ICON.exists()
    assert MACOS_ICON.read_bytes().startswith(b"icns")


def test_web_favicon_uses_current_black_gold_app_icon():
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    favicon = ROOT / "app" / "web" / "static" / "favicon.png"
    app_icon = ROOT / "src-tauri" / "icons" / "icon.png"

    assert favicon.exists()
    assert favicon.read_bytes() == app_icon.read_bytes()
    assert '<link rel="icon" type="image/png" href="/static/favicon.png?v=20260621a">' in html
    assert '<link rel="apple-touch-icon" href="/static/favicon.png?v=20260621a">' in html
    assert "data:image/svg+xml" not in html
    assert "desktop-brand-icon" in html
    assert 'desktop-brand-mark">A</div>' not in html

    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert ".desktop-brand-icon" in css
    assert "object-fit: cover" in css


def test_report_project_upload_modal_treats_non_word_assets_as_optional():
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    script = (ROOT / "app" / "web" / "static" / "js" / "templates.js").read_text(encoding="utf-8")

    assert "upload-required-card" in html
    assert "upload-optional-grid" in html
    assert "Word 模板" in html
    assert "必需" in html
    assert "可选材料" in html
    assert 'data-file-label="project-word-template-input"' in html
    assert 'data-file-label="project-excel-workbook-input"' in html
    assert "请至少选择 Word 模板、Excel 底稿和 Section 配置" not in script
    assert "if (projectType === 'word' && !wordFile)" in script
    assert "if (projectType === 'ppt' && !pptFile)" in script
    assert "if (excelFile)" in script
    assert "if (sectionFile)" in script


def test_windows_icon_is_available_for_tauri_resource_generation():
    assert WINDOWS_ICON.exists()
    assert WINDOWS_ICON.read_bytes().startswith(b"\x00\x00\x01\x00")


def test_tauri_rust_shell_starts_backend_sidecar():
    source = TAURI_LIB.read_text(encoding="utf-8")

    assert 'const BACKEND_SIDECAR: &str = "alphafoundry-backend";' in source
    assert "cfg!(dev)" in source
    assert "app.shell().sidecar(BACKEND_SIDECAR)" in source
    assert "beforeDevCommand starts the backend" in source
    assert "start_backend_sidecar" in source
    assert "stop_backend_sidecar" in source
    assert "tauri_plugin_shell::init()" in source


def test_macos_arm_sidecar_shim_invokes_python_launcher():
    source = MACOS_ARM_SIDECAR.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "ALPHAFOUNDRY_PROJECT_ROOT" in source
    assert "dev-project-root" in source
    assert "resolve_project_root" in source
    assert "scripts/desktop/run_backend.sh" in source
    assert '"$@"' in source


def test_desktop_backend_shell_selects_python_runtime():
    source = RUN_BACKEND_SH.read_text(encoding="utf-8")

    assert "ALPHAFOUNDRY_PYTHON" in source
    assert "python3.11" in source
    assert "anaconda3/bin/python" in source
    assert "backend_launcher.py" in source
    assert 'cd "$REPO_ROOT"' in source


def test_desktop_restart_script_reopens_installed_app_and_checks_health():
    source = RESTART_APP_SH.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "ALPHAFOUNDRY_APP_PATH" in source
    assert "patch_macos_automation_permissions.sh" in source
    assert "/Applications/AlphaFoundry.app" in source
    assert "127.0.0.1:8765" in source
    assert "desktop-restart.log" in source
    assert "src-tauri/icons/icon.icns" in source
    assert "cmp -s" in source
    assert "lsregister" in source
    assert "killall Dock" in source
    assert "osascript" in source
    assert 'open "$APP_PATH"' in source
    assert "curl --silent --show-error --fail" in source
    assert "http_proxy=" in source


def test_macos_automation_permission_patch_script_sets_apple_events_usage():
    source = PATCH_MACOS_AUTOMATION_SH.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "ALPHAFOUNDRY_APP_PATH" in source
    assert "NSAppleEventsUsageDescription" in source
    assert "Microsoft Excel" in source
    assert "/usr/libexec/PlistBuddy" in source
    assert "codesign --force --deep --sign -" in source
    assert "Info.plist" in source


def test_sidecar_build_script_uses_pyinstaller_and_tauri_naming():
    shell = BUILD_SIDECAR_SH.read_text(encoding="utf-8")
    source = BUILD_SIDECAR_PY.read_text(encoding="utf-8")

    assert "build_sidecar.py" in shell
    assert "PyInstaller" in source
    assert "--onefile" in source
    assert "alphafoundry-backend-{triple}" in source
    assert "aarch64-apple-darwin" in source
    assert '"build" / "desktop-sidecar" / "dist"' in source
    assert "backend_launcher.py" in source
    assert '"app",' in source
    assert '"reporting",' in source
    assert '"data_layer",' in source
    assert 'COLLECT_DATA = ["akshare", "vectorbt"]' in source
    assert 'REPO_ROOT / "app" / "web"' in source
    assert 'REPO_ROOT / "reporting" / "templates"' in source
    assert 'REPO_ROOT / "report_projects"' in source


def test_prepare_sidecar_copies_generated_binary_to_tauri_binaries():
    source = PREPARE_SIDECAR.read_text(encoding="utf-8")

    assert "DIST_DIR / executable_name" in source
    assert 'REPO_ROOT / "src-tauri" / "binaries"' in source
    assert "shutil.copy2(source, destination)" in source
    assert "stat.S_IXUSR" in source


def test_release_config_uses_updater_secret_and_latest_json_endpoint(monkeypatch):
    module = load_module("write_tauri_release_config", WRITE_RELEASE_CONFIG)
    monkeypatch.delenv("ALPHAFOUNDRY_UPDATER_ENDPOINT", raising=False)

    config = module.release_config("public-key", module.DEFAULT_ENDPOINT)

    assert config["bundle"]["createUpdaterArtifacts"] is True
    assert config["plugins"]["updater"]["pubkey"] == "public-key"
    assert config["plugins"]["updater"]["endpoints"] == [module.DEFAULT_ENDPOINT]


def test_backend_launcher_allows_project_root_override(monkeypatch):
    monkeypatch.setenv("ALPHAFOUNDRY_PROJECT_ROOT", "/tmp/alphafoundry")
    launcher = load_launcher_module()

    assert str(launcher.PROJECT_ROOT) == "/tmp/alphafoundry"


def test_package_json_exposes_desktop_commands():
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package["scripts"]["tauri"] == "tauri"
    assert package["scripts"]["desktop:dev"] == "tauri dev"
    assert package["scripts"]["desktop:build"] == "tauri build"
    assert package["scripts"]["desktop:sidecar"] == "python scripts/desktop/build_sidecar.py"
    assert (
        package["scripts"]["desktop:prepare-sidecar"]
        == "python scripts/desktop/prepare_tauri_sidecar.py"
    )
    assert package["scripts"]["desktop:release-config"] == (
        "python scripts/desktop/write_tauri_release_config.py"
    )
    assert package["scripts"]["desktop:restart"] == "bash scripts/desktop/restart_app.sh"
    assert "@tauri-apps/cli" in package["devDependencies"]


def test_desktop_release_workflow_builds_platform_matrix_and_draft_release():
    source = DESKTOP_RELEASE_WORKFLOW.read_text(encoding="utf-8")

    assert "macos-latest" in source
    assert "windows-latest" not in source
    assert "ubuntu-22.04" not in source
    assert "python scripts/desktop/build_sidecar.py" in source
    assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
    assert "Free Linux runner disk space" in source
    assert "cargo fetch --locked" in source
    assert "tauri-apps/tauri-action@v0" in source
    assert "releaseDraft: true" in source
    assert "TAURI_UPDATER_PUBKEY" in source
    assert "TAURI_SIGNING_PRIVATE_KEY" in source


def test_desktop_bootstrap_waits_for_backend_health():
    html = BOOTSTRAP_HTML.read_text(encoding="utf-8")
    source = BOOTSTRAP_JS.read_text(encoding="utf-8")

    assert "AlphaFoundry" in html
    assert "DEFAULT_BACKEND_URL = 'http://127.0.0.1:8765'" in source
    assert "fetch(`${baseUrl}/health`" in source
    assert "window.location.replace(`${baseUrl}/`)" in source
    assert "retry-button" in source


def test_desktop_workbench_uses_phase_one_visual_baseline():
    """The desktop workbench keeps the current market and asset entry surfaces."""
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    app_js = (ROOT / "app" / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    dashboard_js = (ROOT / "app" / "web" / "static" / "js" / "dashboard.js").read_text(
        encoding="utf-8"
    )

    assert "desktop-brand" in html
    assert "本地投研工作台" in html
    assert "market-sector-view-selector" in html
    assert "market-heatmap-grid" in html
    assert "Wind热门概念矩阵" in html
    assert 'data-asset-mode="theme"' in html
    assert "app.js?v=20260722flowfix" in html
    assert "dashboard.js?v=20260703theme1" in app_js
    assert "asset.js?v=20260703theme1" in app_js
    assert "renderMarketCommandCenter" in dashboard_js
    assert "switchMarketHeatmapScope" in dashboard_js
    assert "activeMarketHeatmapScope = 'concept'" in dashboard_js
    assert "openAssetThemeObservation" in dashboard_js
    assert "--desktop-sidebar-width: 220px" in css
    assert '[data-theme="light"] {' in css


def test_dashboard_news_items_hide_source_badges_and_use_compact_today_time():
    source = (ROOT / "app" / "web" / "static" / "js" / "dashboard.js").read_text(encoding="utf-8")

    assert "formatNewsTimestamp(n.published_at)" in source
    assert "function formatNewsTimestamp" in source
    assert "isSameLocalDate" in source
    assert "toLocaleTimeString" in source
    assert "toLocaleDateString" in source
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    assert "justify-content: flex-end" in css
    assert "news-source-tag" not in source
    assert "${esc(n.source)}" not in source
    assert "news-symbols" not in source
    assert "related_symbols" not in source


def test_apple_desktop_theme_tokens_drive_light_mode_and_color_scheme():
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")

    dark_tokens = css.split("/* ─── Apple Desktop Material Polish", 1)[1].split(
        "/* ─── Apple Desktop Light Theme Tokens", 1
    )[0]
    light_tokens = css.split("/* ─── Apple Desktop Light Theme Tokens", 1)[1].split(
        '[data-theme="dark"] body', 1
    )[0]
    full_surface = css.split("/* ─── Apple Desktop Full Surface Migration", 1)[1].split(
        "/* Apple Desktop Live Monitor Redesign */", 1
    )[0]
    live_monitor = css.split("/* Apple Desktop Live Monitor Redesign */", 1)[1]

    assert "--apple-accent: var(--accent);" in dark_tokens
    assert "--apple-accent-light: var(--accent-light);" in dark_tokens
    assert "--apple-focus-ring: color-mix(in srgb, var(--accent) 18%, transparent);" in dark_tokens
    assert "--apple-accent: var(--accent);" in light_tokens
    assert "--apple-accent-light: var(--accent-light);" in light_tokens
    assert "--apple-focus-ring: color-mix(in srgb, var(--accent) 16%, transparent);" in light_tokens

    assert "background: var(--apple-accent);" in full_surface
    assert "background: var(--apple-accent-light);" in full_surface
    assert "color: var(--apple-accent-text);" in full_surface
    assert "border-color: var(--apple-accent-ring);" in full_surface
    assert "0 0 0 3px var(--apple-focus-ring)" in full_surface
    assert "background: var(--apple-accent-light);" in live_monitor
    assert "color: var(--apple-accent-text);" in live_monitor
    assert "border-color: var(--apple-accent-ring);" in live_monitor
    assert "background: var(--apple-accent);" in live_monitor


def test_light_theme_overrides_monitor_and_shared_surfaces():
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert "Apple Desktop Light Surface Overrides" in css
    light_surface = css.split("/* ─── Apple Desktop Light Surface Overrides", 1)[1].split(
        "/* Apple Desktop Live Monitor Redesign */", 1
    )[0]

    assert '[data-theme="light"] #section-dashboard .monitor-status-strip' in light_surface
    assert '[data-theme="light"] #section-dashboard .monitor-panel' in light_surface
    assert '[data-theme="light"] #section-dashboard .monitor-event-item' in light_surface
    assert '[data-theme="light"] #section-dashboard .monitor-event-detail-card' in light_surface
    assert '[data-theme="light"] #section-dashboard .monitor-health-card' in light_surface
    assert (
        '[data-theme="light"] #section-dashboard .monitor-health-panel .worker-row' in light_surface
    )
    assert '[data-theme="light"] .card' in light_surface
    assert '[data-theme="light"] input' in light_surface

    assert "--apple-panel-bg: #ffffff;" in light_surface
    assert "--apple-panel-bg-soft: #f5f5f7;" in light_surface
    assert "--apple-row-bg: #fbfbfd;" in light_surface
    assert "--apple-row-hover: #f2f2f7;" in light_surface
    assert "--apple-shadow-light" in light_surface
    assert "rgba(28,28,30,0.72)" not in light_surface
    assert "rgba(84,84,88" not in light_surface


def test_light_theme_market_news_copy_is_readable():
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")

    assert "--apple-readable-secondary: #4f5661;" in css
    assert "--apple-readable-tertiary: #5f636b;" in css
    assert '[data-theme="light"] #section-dashboard .news-summary' in css
    assert '[data-theme="light"] #section-dashboard .news-meta' in css
    assert '[data-theme="light"] #section-dashboard .news-time' in css

    readable_news = css.split("/* ─── Apple Desktop Light News Readability", 1)[1].split(
        "/* Apple Desktop Live Monitor Redesign */", 1
    )[0]
    assert "color: var(--apple-readable-secondary);" in readable_news
    assert "color: var(--apple-readable-tertiary);" in readable_news
    assert "font-weight: 650;" in readable_news
    assert "font-weight: 700;" in readable_news
    assert "color: #b4b4ba;" not in readable_news
    assert "color: #7c7c82;" not in readable_news


def test_live_monitor_uses_unified_feed_with_legacy_template_retained():
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    app_js = (ROOT / "app" / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    monitor_js = (ROOT / "app" / "web" / "static" / "js" / "monitor.js").read_text(encoding="utf-8")

    assert 'id="live-monitor-board"' in html
    assert 'id="monitor-source-list"' in html
    assert 'data-monitor-source="all"' in html
    assert 'id="monitor-feed-list"' in html
    assert 'id="monitor-feed-title"' in html
    assert 'id="monitor-health-panel"' in html
    assert 'class="monitor-status-strip"' in html
    assert 'class="live-monitor-summary"' not in html
    assert 'id="monitor-event-detail"' in html
    assert 'data-monitor-detail-tab="event"' in html
    assert 'data-monitor-detail-tab="system"' in html
    assert '<template id="legacy-live-monitor-template">' in html
    assert 'class="crawl-feed-row legacy-live-monitor"' in html
    assert "Apple Desktop Live Monitor Redesign" in css
    assert "#section-dashboard .monitor-status-strip" in css
    assert "#section-dashboard .live-monitor-board" in css
    assert "height: clamp(520px, calc(100vh - 220px), 760px)" in css
    assert "height: calc(100vh - 132px)" not in css
    assert "#section-dashboard .monitor-feed-list" in css
    assert "overscroll-behavior: contain" in css
    assert "#section-dashboard .monitor-source-row.active" in css
    assert "#section-dashboard .monitor-event-item" in css
    assert "#section-dashboard .monitor-event-item.selected" in css
    assert "#section-dashboard .monitor-detail-tabs" in css
    assert "#section-dashboard .monitor-health-card" in css
    assert "monitor.js?v=20260714a" in app_js
    assert "activeMonitorSource" in monitor_js
    assert "activeMonitorItemKey" in monitor_js
    assert "renderUnifiedMonitorFeed" in monitor_js
    assert "renderMonitorEventDetail" in monitor_js
    assert "handleMonitorEventClick" in monitor_js
    assert "handleMonitorSourceClick" in monitor_js
    assert "data-monitor-source" in monitor_js
    assert "data-monitor-item-key" in monitor_js
    assert "<p>${esc(summaryText(item))}</p>" not in monitor_js
    assert "function summaryText" not in monitor_js
    assert "sourceTodayCount(state, source)" in monitor_js
    assert "state.totalToday || state.items.length" not in monitor_js


def test_desktop_backend_launcher_defaults_and_logging(tmp_path):
    launcher = load_launcher_module()
    parser = launcher.build_parser()
    args = parser.parse_args([])

    assert args.host == "127.0.0.1"
    assert args.port == 8765
    assert launcher.PROJECT_ROOT == ROOT

    log_file = launcher.configure_launcher_logging(tmp_path)

    assert log_file == tmp_path / "desktop-backend.log"
    assert log_file.exists()


def test_frozen_backend_launcher_requires_postgresql(monkeypatch, tmp_path):
    """Frozen desktop startup requires an explicit PostgreSQL configuration."""
    launcher = load_launcher_module()
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setenv("ALPHAFOUNDRY_DESKTOP_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("LOG_DIR", raising=False)

    data_dir = launcher.apply_frozen_desktop_defaults()

    assert data_dir == tmp_path
    assert (
        os.environ["DATABASE_URL"]
        == "postgresql+psycopg://user:password@127.0.0.1:5432/alphafoundry"
    )
    assert os.environ["LOG_DIR"] == str(tmp_path / "logs")
    assert (tmp_path / "logs").is_dir()
