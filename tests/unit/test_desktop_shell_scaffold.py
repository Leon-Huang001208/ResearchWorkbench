"""Static wiring tests for the Research Workbench desktop shell scaffold."""

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
TAURI_CONFIG = ROOT / "src-tauri" / "tauri.conf.json"
TAURI_LIB = ROOT / "src-tauri" / "src" / "lib.rs"
PACKAGE_JSON = ROOT / "package.json"
BOOTSTRAP_JS = ROOT / "desktop" / "dist" / "bootstrap.js"
BOOTSTRAP_HTML = ROOT / "desktop" / "dist" / "index.html"
LAUNCHER = ROOT / "scripts" / "desktop" / "backend_launcher.py"
RUN_BACKEND_SH = ROOT / "scripts" / "desktop" / "run_backend.sh"
RUN_PREVIEW_JS = ROOT / "scripts" / "desktop" / "run_preview.js"
RESTART_APP_SH = ROOT / "scripts" / "desktop" / "restart_app.sh"
PATCH_MACOS_AUTOMATION_SH = ROOT / "scripts" / "desktop" / "patch_macos_automation_permissions.sh"
BUILD_SIDECAR_SH = ROOT / "scripts" / "desktop" / "build_sidecar.sh"
BUILD_SIDECAR_PY = ROOT / "scripts" / "desktop" / "build_sidecar.py"
PREPARE_SIDECAR = ROOT / "scripts" / "desktop" / "prepare_tauri_sidecar.py"
WRITE_RELEASE_CONFIG = ROOT / "scripts" / "desktop" / "write_tauri_release_config.py"
DESKTOP_RELEASE_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-release.yml"
DESKTOP_VERIFY_WORKFLOW = ROOT / ".github" / "workflows" / "desktop-verify.yml"
MACOS_ARM_SIDECAR = ROOT / "src-tauri" / "binaries" / "research-workbench-backend-aarch64-apple-darwin"
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

    assert config["productName"] == "Research Workbench"
    assert config["build"]["devUrl"] == "http://127.0.0.1:8765"
    assert "node scripts/desktop/run_backend.js" in config["build"]["beforeDevCommand"]
    assert config["build"]["frontendDist"] == "../desktop/dist"
    assert config["bundle"]["targets"] == "all"
    assert config["bundle"]["icon"] == [
        "icons/icon.png",
        "icons/icon.icns",
        "icons/icon.ico",
    ]
    assert "binaries/research-workbench-backend" in config["bundle"]["externalBin"]
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
    assert "if (reportConfigFile)" in script


def test_windows_icon_is_available_for_tauri_resource_generation():
    assert WINDOWS_ICON.exists()
    assert WINDOWS_ICON.read_bytes().startswith(b"\x00\x00\x01\x00")


def test_tauri_rust_shell_starts_backend_sidecar():
    source = TAURI_LIB.read_text(encoding="utf-8")

    assert 'const BACKEND_SIDECAR: &str = "research-workbench-backend";' in source
    assert "cfg!(dev)" in source
    assert "app.shell().sidecar(BACKEND_SIDECAR)" in source
    assert "beforeDevCommand starts the backend" in source
    assert "start_backend_sidecar" in source
    assert "stop_backend_sidecar" in source
    assert "RESEARCH_DESKTOP_PORT" in source
    assert "backend_port()" in source
    assert "tauri_plugin_shell::init()" in source


def test_macos_arm_sidecar_shim_invokes_python_launcher():
    source = MACOS_ARM_SIDECAR.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "RESEARCH_PROJECT_ROOT" in source
    assert "dev-project-root" in source
    assert "resolve_project_root" in source
    assert "scripts/desktop/run_backend.sh" in source
    assert '"$@"' in source
    git_mode = subprocess.run(
        ["git", "ls-files", "--stage", "--", str(MACOS_ARM_SIDECAR.relative_to(ROOT))],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=True,
    ).stdout.split(maxsplit=1)[0]
    assert git_mode == "100755"


def test_desktop_backend_shell_selects_python_runtime():
    source = RUN_BACKEND_SH.read_text(encoding="utf-8")

    assert "RESEARCH_PYTHON" in source
    assert "python3.11" in source
    assert "anaconda3/bin/python" in source
    assert "backend_launcher.py" in source
    assert 'cd "$REPO_ROOT"' in source


def test_desktop_restart_script_reopens_installed_app_and_checks_health():
    source = RESTART_APP_SH.read_text(encoding="utf-8")

    assert source.startswith("#!/usr/bin/env bash")
    assert "RESEARCH_APP_PATH" in source
    assert "patch_macos_automation_permissions.sh" in source
    assert "/Applications/Research Workbench.app" in source
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
    assert "RESEARCH_APP_PATH" in source
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
    assert "research-workbench-backend-{triple}" in source
    assert "aarch64-apple-darwin" in source
    assert '"build" / "desktop-sidecar" / "dist"' in source
    assert '"app",' in source
    assert '"reporting",' in source
    assert '"data_layer",' in source
    assert 'COLLECT_DATA = ["akshare", "vectorbt"]' in source
    assert 'args.extend(["--collect-submodules", module])' in source
    assert 'args.extend(["--collect-data", package])' in source
    assert 'REPO_ROOT / "app" / "web"' in source
    assert 'REPO_ROOT / "reporting" / "templates"' in source
    assert 'REPO_ROOT / "report_projects"' in source
    assert "os.pathsep" in source


def test_prepare_sidecar_copies_generated_binary_to_tauri_binaries():
    source = PREPARE_SIDECAR.read_text(encoding="utf-8")

    assert "DIST_DIR / executable_name" in source
    assert 'REPO_ROOT / "src-tauri" / "binaries"' in source
    assert "shutil.copy2(source, destination)" in source
    assert "stat.S_IXUSR" in source


def test_release_config_uses_updater_secret_and_latest_json_endpoint(monkeypatch):
    module = load_module("write_tauri_release_config", WRITE_RELEASE_CONFIG)
    monkeypatch.delenv("RESEARCH_UPDATER_ENDPOINT", raising=False)

    config = module.release_config("public-key", module.DEFAULT_ENDPOINT)

    assert config["bundle"]["createUpdaterArtifacts"] is True
    assert config["plugins"]["updater"]["pubkey"] == "public-key"
    assert config["plugins"]["updater"]["endpoints"] == [module.DEFAULT_ENDPOINT]


def test_backend_launcher_allows_project_root_override(monkeypatch):
    monkeypatch.setenv("RESEARCH_PROJECT_ROOT", "/tmp/research_workbench")
    launcher = load_launcher_module()

    assert launcher.PROJECT_ROOT == Path("/tmp/research_workbench")


def test_frozen_backend_launcher_resolves_project_root_from_pyinstaller_bundle(
    monkeypatch, tmp_path
):
    bundle_root = tmp_path / "_MEI12345"
    bundle_root.mkdir()
    monkeypatch.delenv("RESEARCH_PROJECT_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle_root), raising=False)

    launcher = load_launcher_module()

    assert launcher.PROJECT_ROOT == bundle_root


def test_package_json_exposes_desktop_commands():
    package = json.loads(PACKAGE_JSON.read_text(encoding="utf-8"))

    assert package["scripts"]["tauri"] == "tauri"
    assert package["scripts"]["desktop:dev"] == "tauri dev"
    assert package["scripts"]["desktop:preview"] == "node scripts/desktop/run_preview.js"
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


def test_desktop_preview_launcher_uses_isolated_port_and_runtime_data():
    source = RUN_PREVIEW_JS.read_text(encoding="utf-8")

    assert "const DEFAULT_PORT = 8766;" in source
    assert "RESEARCH_DESKTOP_DATA_DIR" in source
    assert "--use-stable-data" in source
    assert "RESEARCH_PREVIEW" in source
    assert "RESEARCH_DESKTOP_PORT" in source
    assert "mkdtemp" in source
    assert "--config" in source
    assert '"worktree", "list", "--porcelain"' in source
    assert "beforeDevCommand" in source
    assert "devUrl" in source
    assert "csp" in source


def test_desktop_release_workflow_builds_platform_matrix_and_draft_release():
    source = DESKTOP_RELEASE_WORKFLOW.read_text(encoding="utf-8")
    verify_source = (ROOT / ".github" / "workflows" / "desktop-verify.yml").read_text(
        encoding="utf-8"
    )

    assert "macos-14" in source
    assert "windows-2022" in source
    assert "ubuntu-22.04" not in source
    assert "aarch64-apple-darwin" in source
    assert "x86_64-pc-windows-msvc" in source
    assert "python scripts/desktop/build_sidecar.py" in source
    assert "python scripts/desktop/prepare_tauri_sidecar.py" in source
    assert "Verify Windows sidecar" in source
    assert "cargo fetch --locked" in source
    assert "tauri-apps/tauri-action@v0" in source
    assert "releaseDraft: true" in source
    assert "TAURI_UPDATER_PUBKEY" in source
    assert "TAURI_SIGNING_PRIVATE_KEY" in source
    assert "setuptools<81" in source
    assert "setuptools<81" in verify_source


def test_desktop_verify_workflow_runs_for_master_desktop_changes():
    source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")

    assert "  push:\n    branches:\n      - master" in source
    assert "src-tauri/**" in source
    assert "scripts/desktop/**" in source


def test_desktop_verify_smokes_setup_required_on_both_native_runners():
    source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")

    assert source.count("Smoke test setup-required sidecar /health") == 2
    assert source.count("--expected-persistence-status setup_required") == 2
    assert source.count("--port 8766") == 2
    assert "postgresql+psycopg://postgres:postgres@127.0.0.1:1/research_workbench" in source
    assert "research-workbench-desktop-setup-smoke" in source
    assert "build/desktop-sidecar/setup-smoke.log" in source
    for path_filter in (
        "app/api/main.py",
        "app/api/routes/setup.py",
        "app/api/configuration_models.py",
        "app/web/**",
        "services/database_readiness.py",
        "workers/watchdog.py",
        "docs/desktop_packaging.md",
    ):
        assert source.count(path_filter) == 2


def test_windows_pgvector_smoke_builds_a_native_extension():
    """Windows runners use a Windows-only Moby Docker engine.

    The smoke test must therefore run PostgreSQL and pgvector natively instead
    of attempting to run pgvector's Linux-only container image.
    """
    source = DESKTOP_VERIFY_WORKFLOW.read_text(encoding="utf-8")

    assert "choco install postgresql16" in source
    assert "--execution-timeout 1200" in source
    assert '$chocoParameters = "/Password:postgres /Port:${{ matrix.postgres_port }}"' in source
    assert "--params $chocoParameters" in source
    assert '--params "\'/Password:postgres' not in source
    assert "nmake /F Makefile.win install" in source
    assert "CREATE EXTENSION IF NOT EXISTS vector;" in source
    assert "PGPASSWORD = 'postgres'" in source
    assert "pgvector/pgvector:pg16" not in source


def test_desktop_runtime_dependencies_include_fastapi_multipart_support():
    source = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "python-multipart" in source


def test_desktop_bootstrap_waits_for_backend_health():
    html = BOOTSTRAP_HTML.read_text(encoding="utf-8")
    source = BOOTSTRAP_JS.read_text(encoding="utf-8")

    assert "Research Workbench" in html
    assert "DEFAULT_BACKEND_URL = 'http://127.0.0.1:8765'" in source
    assert "fetch(`${baseUrl}/health`" in source
    assert "window.location.replace(`${baseUrl}/`)" in source
    assert "retry-button" in source


def test_desktop_workbench_uses_phase_one_visual_baseline():
    html = (ROOT / "app" / "web" / "templates" / "index.html").read_text(encoding="utf-8")
    css = (ROOT / "app" / "web" / "static" / "style.css").read_text(encoding="utf-8")
    js = (ROOT / "app" / "web" / "static" / "js" / "app.js").read_text(encoding="utf-8")

    assert "desktop-brand" in html
    assert "本地投研工作台" in html
    assert "市场研究" in html
    assert "资产观察" in html
    assert "报告生产" in html
    assert "<h4>全球热点新闻</h4>" in html
    assert "<h4>上涨板块概念</h4>" in html
    assert "<h4>下跌板块概念</h4>" in html
    assert "market-sector-view-selector" in html
    assert html.count("market-sector-view-selector") == 1
    assert "market-sector-select-menu" in html
    assert "market-sector-view-tabs" not in html
    assert "Wind热门概念" in html
    assert "中信三级" not in html
    assert "申万三级" not in html
    assert "同花顺行业" not in html
    assert "market-pulse-board" in html
    assert "market-scope-tabs" in html
    assert "market-index-grid" in html
    assert "market-refresh-btn" not in html
    assert "实时行情" not in html
    assert "market-auto-refresh-indicator" not in html
    assert 'id="btn-commentary-auto-refresh"' in html
    assert "自动刷新" in html
    assert "market-breadth-bar" in html
    assert "market-ai-brief" in html
    assert "market-heatmap-card" in html
    assert "market-heatmap-grid" in html
    assert "Wind热门概念矩阵" in html
    assert "颜色表示涨跌方向，描边表示涨跌强度" in html
    assert "面积代表热度" not in html
    assert "A股全图" not in html
    assert "switchMarketHeatmapScope('all')" not in html
    assert "switchMarketHeatmapScope('concept')" in html
    assert "switchMarketHeatmapScope('sector')" in html
    assert '<h4 id="market-heatmap-title">Wind热门概念矩阵</h4>' in html
    assert '<span id="market-heatmap-subtitle">颜色表示涨跌方向，描边表示涨跌强度</span>' in html
    assert "market-shortcuts" not in html
    assert "🌍 全球热点新闻" not in html
    assert "📈 上涨板块概念" not in html
    assert "📉 下跌板块概念" not in html
    assert "全球热点新闻 (Top 10)" not in html
    assert "今日上涨板块概念 (Top 10)" not in html
    assert "今日下跌板块概念 (Top 10)" not in html
    assert 'href="/static/style.css?v=' in html
    assert '<script type="module" src="/static/js/app.js?v=' in html
    assert "asset-observe-mode-tabs" in html
    assert 'data-asset-mode="theme"' in html
    assert "asset-topic-result" in html
    assert "概念指数走势" in html
    assert "成分股 / 龙头贡献" in html
    assert "market-companion-row" not in html
    assert '<small id="market-session-date" class="market-session-date">--</small>' in html
    assert "market-flow-summary" not in html
    assert "大盘资金净流入" not in html
    assert "--desktop-sidebar-width: 220px" in css
    assert "--brand-red: #d71920" in css
    assert "Desktop Visual System Phase 1" in css
    assert "Apple Desktop Market Dashboard Iteration" in css
    assert "Apple Desktop Content Refinement" in css
    assert "Apple Desktop Material Polish" in css
    assert "Apple Desktop Full Surface Migration" in css
    assert "Apple Desktop Light Theme Tokens" in css
    assert "Apple Desktop Expanded Sector Lists" in css
    assert "Apple Desktop Equal Height Market Sections" in css
    assert "Apple Desktop Hide Legacy Status Bar" in css
    assert "minmax(560px, 1.55fr)" in css
    assert "--apple-blue: #0a84ff" in css
    assert "--apple-control: rgba(118,118,128,0.28)" in css
    assert "--market-up-red: #ff453a" in css
    assert "--market-down-green: #30d158" in css
    assert "#section-dashboard .news-summary" in css
    assert ".content-section.active" in css
    assert ".content-section:not(#section-dashboard) .section-title" in css
    assert ".card, .summary-card, .dashboard-card, .panel-card" in css
    assert ".data-table-wrap, table" in css
    assert ".tabs, .dash-tabs" in css
    assert "scrollbar-color: var(--apple-scroll-thumb) transparent" in css
    assert '[data-theme="light"] {' in css
    assert "--apple-bg: #f5f5f7" in css
    assert "--apple-window: #fbfbfd" in css
    assert "--apple-surface: #ffffff" in css
    assert '[data-theme="light"] body' in css
    assert '[data-theme="dark"] body' in css
    assert "#section-dashboard .sectors-up-section .sector-list" in css
    assert "max-height: none" in css
    assert "overflow-y: visible" in css
    assert "align-items: stretch" in css
    assert "#section-dashboard .sectors-up-section," in css
    assert "height: 100%" in css
    assert "display: none" in css
    assert "height: 100vh" in css
    assert "Apple Desktop News Ranking Badges" in css
    assert "Apple Market Home Command Center" in css
    assert "#section-dashboard .market-pulse-board" in css
    assert "#section-dashboard .market-pulse-main" in css
    assert "#section-dashboard .market-session-date" in css
    assert "#section-dashboard .market-heatmap-grid" in css
    assert "#section-dashboard .market-breadth-bar" in css
    assert "#section-dashboard .news-item:first-child .news-rank" in css
    assert "--news-rank-first: #c9342f" in css
    assert "--news-rank-default: var(--apple-accent)" in css
    assert "20260618-desktop-phase1" in js
    assert "dashboard.js?v=20260703theme1" in js
    assert "asset.js?v=20260811research1" in js
    assert "openThemeObservation" in js
    dashboard_js = (ROOT / "app" / "web" / "static" / "js" / "dashboard.js").read_text(
        encoding="utf-8"
    )
    assert "中信三级" in dashboard_js
    assert "申万三级" in dashboard_js
    assert "同花顺行业" in dashboard_js
    assert '<span class="news-rank">${idx + 1}</span>' in dashboard_js
    assert '<span class="news-rank">#${idx + 1}</span>' not in dashboard_js
    assert "renderMarketCommandCenter(mo)" in dashboard_js
    assert "function renderMarketCommandCenter" in dashboard_js
    assert "refreshMarketOverviewOnly" in dashboard_js
    assert "/api/market-home/live?force_refresh=" in dashboard_js
    assert "toast('行情刷新失败'" in dashboard_js
    assert "loadDashboard({ silent: !options.manual })" not in dashboard_js
    assert "renderMarketHeatmap" in dashboard_js
    assert "switchMarketHeatmapScope" in dashboard_js
    assert "activeMarketHeatmapScope = 'concept'" in dashboard_js
    assert "key: 'all'" not in dashboard_js
    assert "label: 'A股全图'" not in dashboard_js
    assert "getMarketSectorViewsForActiveScope" in dashboard_js
    assert "updateMarketHeatmapCopy" in dashboard_js
    assert "function getMarketHeatmapIntensityClass" in dashboard_js
    assert "Math.abs(Number(change) || 0)" in dashboard_js
    assert "openAssetThemeObservation" in dashboard_js
    assert "data-heatmap-rank" in dashboard_js
    asset_js = (ROOT / "app" / "web" / "static" / "js" / "asset.js").read_text(encoding="utf-8")
    assert "function openThemeObservation" in asset_js
    assert "function switchAssetObserveMode" in asset_js
    assert "THEME_OBSERVATION_PRESETS" in asset_js
    assert "asset-topic-trend-chart" in asset_js
    assert "机器人ETF南方" in asset_js
    assert ".commentary-config-workspace > .commentary-request-preview" in css
    assert "grid-row: span 2" in css
    assert "renderMarketMiniCards" not in dashboard_js
    assert "formatMarketMiniSignedValue" not in dashboard_js
    assert "renderCapCompareMarkup" not in dashboard_js
    assert "stock-picker" not in dashboard_js
    assert "ipo-calendar" not in dashboard_js
    assert "hot-list" not in dashboard_js
    assert "market-review" not in dashboard_js
    assert "涨跌停对比" not in html
    assert "昨日涨停表现" not in html
    assert "大小盘对比" not in html
    assert "上一日成交额" in dashboard_js
    assert "较上一日此时" not in dashboard_js
    assert "今日实时成交额" in dashboard_js
    assert "setMarketFlowValue" not in dashboard_js
    assert "market-flow-value" not in dashboard_js
    assert "market-index-grid" in dashboard_js
    assert "getPrimaryMarketIndices(indices)" in dashboard_js
    assert "indices.slice(0, 3)" not in dashboard_js
    assert "中证全指" not in dashboard_js
    assert "深证100" not in dashboard_js
    assert "中证红利" not in dashboard_js
    assert "上证50" in dashboard_js
    assert "创业板50" in dashboard_js
    assert "科创50" in dashboard_js
    assert "北证50" in dashboard_js
    assert (
        "'上证指数',\n        '深证成指',\n        '科创综指',\n        '创业板指',\n        '中证A500',\n        '北证50',\n        '上证50',\n        '沪深300',\n        '科创50',\n        '创业板50',\n        '中证500',\n        '中证1000'"
        in dashboard_js
    )
    assert "return preferred;" in dashboard_js
    assert "中证2000" not in dashboard_js
    assert "科创创业50" not in dashboard_js
    service_py = (ROOT / "services" / "dashboard_service.py").read_text(encoding="utf-8")
    assert '("sh000016", "上证50")' in service_py
    assert '("sz399673", "创业板50")' in service_py
    assert '("sh000688", "科创50")' in service_py
    assert "中证2000" not in service_py
    assert "科创创业50" not in service_py
    assert "csindex_daily" not in service_py
    assert "sz399330" not in service_py
    assert "sh000015" not in service_py
    assert "em000985" not in service_py
    assert "stock_fund_flow_industry" not in service_py
    assert "stock_zt_pool_em" not in service_py
    assert "stock_zt_pool_dtgc_em" not in service_py
    assert "stock_zt_pool_previous_em" not in service_py
    assert "previousTurnover" in service_py
    assert "stock_zh_index_daily_tx" not in service_py
    assert "_format_turnover_yuan" in service_py
    assert "万亿" in service_py
    assert "中证A500" in dashboard_js
    assert "is-trading" in dashboard_js
    assert "classList.toggle('is-trading'" in dashboard_js
    assert ".market-index-card.is-down" in css
    assert "repeat(6, minmax(148px, 1fr))" in css
    assert ".market-index-card:nth-child(-n + 5)" not in css
    assert "grid-column: span 6" not in css
    assert "grid-column: span 5" not in css
    assert "market-mini-grid" not in css
    assert "market-mini-card" not in css
    assert "market-mini-value" not in css
    assert "market-flow-summary" not in css
    assert "data-market-mode" not in html
    assert "market-mode-tabs" not in html
    assert "handleMarketMode" not in dashboard_js
    assert "rgba(48,209,88,0.16)" in css
    assert "4090.48" not in dashboard_js
    assert "16030.70" not in dashboard_js
    assert "2030" not in dashboard_js
    assert "3400" not in dashboard_js
    assert "3.33万亿" not in dashboard_js
    assert "等待实时刷新" in dashboard_js
    assert "toggleMarketSectorMenu" in dashboard_js
    assert "market-sector-select-button" in dashboard_js
    assert "let activeMarketSectorView = 'wind_hot_concept'" in dashboard_js
    assert "MARKET_SECTOR_REQUEST_TIMEOUT_MS = 90000" in dashboard_js
    assert "MARKET_REFRESH_INTERVAL_MS = 30000" in dashboard_js
    assert "getMarketSessionInfo().isTrading" in dashboard_js
    assert "MARKET_SECTOR_LIST_LIMIT = 10" in dashboard_js
    assert "MARKET_HEATMAP_ITEM_LIMIT = 60" in dashboard_js
    assert "MARKET_SECTOR_FETCH_LIMIT = 30" in dashboard_js
    assert "primeMarketSectorViewRequest(activeMarketSectorView)" in dashboard_js
    assert "...previousViews" in dashboard_js
    assert "sectors.slice(0, MARKET_SECTOR_LIST_LIMIT)" in dashboard_js
    assert "/api/dashboard/sector-movers" not in dashboard_js
    assert "force_refresh=${forceRefresh ? 'true' : 'false'}" in dashboard_js
    assert "hasFreshSectorData" in dashboard_js
    assert "if (force && !hasFreshSectorData && current) return" in dashboard_js
    assert "marketSectorViewRequestCache.delete(viewKey)" in dashboard_js
    assert (
        "ensureMarketSectorViewLoaded(activeMarketSectorView, { force: true, silent: true })"
        in dashboard_js
    )
    assert "combined.slice(0, MARKET_HEATMAP_ITEM_LIMIT)" in dashboard_js
    assert "return { up: [], down: [] }" in dashboard_js
    assert "/api/market-home/live" in dashboard_js
    assert "const savedTheme = localStorage.getItem('rwb-theme')" in js
    assert "localStorage.setItem('rwb-theme', savedTheme || 'dark')" in js
    assert "localStorage.setItem('rwb-theme', 'dark')" not in js
    assert "applyTheme(document.documentElement.getAttribute('data-theme') || 'dark')" in js
    assert (
        "applyColorScheme(document.documentElement.getAttribute('data-color-scheme') || 'claude')"
        in js
    )


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


def test_desktop_launcher_sets_runtime_mode_before_database_probe_import(tmp_path):
    """An unavailable database must keep the desktop sidecar in setup mode."""
    script = f"""
import importlib.util
from pathlib import Path

launcher_path = Path({str(LAUNCHER)!r})
spec = importlib.util.spec_from_file_location("desktop_backend_launcher_subprocess", launcher_path)
launcher = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(launcher)

def capture_runtime_mode(_host, _port, _reload):
    from app.api.main import RUNTIME_CONTEXT
    print(f"runtime_mode={{RUNTIME_CONTEXT.mode}}")

launcher.run_backend = capture_runtime_mode
raise SystemExit(launcher.main(["--log-dir", {str(tmp_path / "logs")!r}]))
"""
    environment = os.environ.copy()
    for key in (
        "RESEARCH_DESKTOP",
        "RESEARCH_RUN_MODE",
        "RESEARCH_BACKEND_URL",
        "RESEARCH_DESKTOP_URL",
        "RESEARCH_DESKTOP_DATA_DIR",
        "RESEARCH_CONFIG_FILE",
    ):
        environment.pop(key, None)

    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "runtime_mode=desktop" in result.stdout


def test_legacy_roaming_env_migrates_without_overwriting(monkeypatch, tmp_path):
    launcher = load_launcher_module()
    legacy_env = tmp_path / "Roaming" / "Research Workbench" / ".env"
    legacy_env.parent.mkdir(parents=True)
    legacy_env.write_text("DATABASE_URL=postgresql+psycopg://legacy\n", encoding="utf-8")
    data_dir = tmp_path / "Local" / "Research Workbench"

    monkeypatch.setattr(launcher.platform, "system", lambda: "Windows")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    launcher._migrate_legacy_roaming_env(data_dir)

    assert (data_dir / ".env").read_text(encoding="utf-8") == legacy_env.read_text(encoding="utf-8")

    (data_dir / ".env").write_text("DATABASE_URL=postgresql+psycopg://new\n", encoding="utf-8")
    launcher._migrate_legacy_roaming_env(data_dir)
    assert "postgresql+psycopg://new" in (data_dir / ".env").read_text(encoding="utf-8")


@pytest.mark.parametrize("host", ["0.0.0.0", "::1"])
def test_desktop_launcher_rejects_hosts_not_supported_by_ipv4_runtime(host):
    launcher = load_launcher_module()

    with pytest.raises(ValueError, match="仅允许监听"):
        launcher._require_loopback_host(host)


def test_desktop_launcher_refuses_to_kill_unknown_port_owner(monkeypatch):
    launcher = load_launcher_module()

    class OccupiedSocket:
        def settimeout(self, _timeout):
            pass

        def connect_ex(self, _address):
            return 0

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    monkeypatch.setattr(launcher.socket, "socket", lambda *_args: OccupiedSocket())
    calls = []
    monkeypatch.setattr(launcher.subprocess, "run", lambda *args, **kwargs: calls.append(args))

    assert launcher._kill_stale_process_on_port("127.0.0.1", 8765) is False
    assert calls == []


def isolate_desktop_launcher_environment(monkeypatch, launcher):
    """Register launcher-owned environment keys for pytest cleanup."""
    launcher_keys = {
        "RESEARCH_DESKTOP_DATA_DIR",
        "RESEARCH_DESKTOP",
        "RESEARCH_RUN_MODE",
        "RESEARCH_BACKEND_URL",
        "RESEARCH_DESKTOP_URL",
        "LOG_DIR",
        "OBJECT_STORAGE_PATH",
        "PDF_MARKDOWN_DIR",
        "PDF_RAW_TEXT_DIR",
        "RESEARCH_DEV",
        "RESEARCH_PREVIEW",
    }
    for line in launcher.desktop_env_template().splitlines():
        key, separator, _value = line.partition("=")
        if separator and not key.lstrip().startswith("#"):
            launcher_keys.add(key.strip())
    for key in launcher_keys:
        monkeypatch.delenv(key, raising=False)


@pytest.mark.parametrize("database_url", ["", "postgresql+psycopg://"])
def test_frozen_backend_launcher_keeps_setup_mode_for_missing_or_invalid_postgresql_url(
    monkeypatch, tmp_path, database_url
):
    launcher = load_launcher_module()
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher, "desktop_data_dir", lambda: tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)

    data_dir = launcher.apply_frozen_desktop_defaults()

    assert data_dir == tmp_path
    assert (tmp_path / ".env").exists()
    assert not (tmp_path / "research_workbench.db").exists()
    assert "sqlite" not in (tmp_path / ".env").read_text(encoding="utf-8")


@pytest.mark.parametrize("database_url", ["", "postgresql+psycopg://"])
def test_desktop_launcher_skips_watchdogs_when_database_url_is_missing_or_invalid(
    monkeypatch, tmp_path, database_url
):
    from services import database_readiness

    launcher = load_launcher_module()
    calls = []
    readiness_codes = []
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setattr(launcher, "desktop_data_dir", lambda: tmp_path)
    monkeypatch.setenv("DATABASE_URL", database_url)
    original_probe = database_readiness.probe_postgresql

    def probe(database_url):
        readiness = original_probe(database_url)
        readiness_codes.append(readiness.code.value)
        return readiness

    monkeypatch.setattr(database_readiness, "probe_postgresql", probe)
    monkeypatch.setattr(
        launcher,
        "_start_knowledge_worker",
        lambda *_args: calls.append("knowledge_worker"),
    )
    monkeypatch.setattr(
        launcher,
        "_start_crawl_scheduler",
        lambda *_args: calls.append("crawl_scheduler"),
    )
    monkeypatch.setattr(
        launcher,
        "run_backend",
        lambda host, port, reload: calls.append(("run_backend", host, port, reload)),
    )

    assert launcher.main(["--log-dir", str(tmp_path / "logs")]) == 0

    assert readiness_codes in (["invalid_url"], ["connection_failed"])
    assert (tmp_path / ".env").exists()
    assert not (tmp_path / "research_workbench.db").exists()
    assert calls == [("run_backend", "127.0.0.1", 8765, False)]


def test_desktop_launcher_starts_watchdogs_when_database_is_ready(monkeypatch, tmp_path):
    from services import database_readiness

    launcher = load_launcher_module()
    calls = []
    database_urls = []
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@127.0.0.1/db")
    monkeypatch.setattr(launcher, "apply_frozen_desktop_defaults", lambda: tmp_path)
    monkeypatch.setattr(
        database_readiness,
        "probe_postgresql",
        lambda database_url: database_urls.append(database_url)
        or SimpleNamespace(ready=True, code=SimpleNamespace(value="ready")),
    )
    monkeypatch.setattr(
        launcher,
        "_start_knowledge_worker",
        lambda *_args: calls.append("knowledge_worker"),
    )
    monkeypatch.setattr(
        launcher,
        "_start_crawl_scheduler",
        lambda *_args: calls.append("crawl_scheduler"),
    )
    monkeypatch.setattr(
        launcher,
        "run_backend",
        lambda host, port, reload: calls.append(("run_backend", host, port, reload)),
    )

    assert launcher.main(["--log-dir", str(tmp_path / "logs")]) == 0

    assert database_urls == ["postgresql+psycopg://user:password@127.0.0.1/db"]
    assert calls == [
        "knowledge_worker",
        "crawl_scheduler",
        ("run_backend", "127.0.0.1", 8765, False),
    ]


def test_desktop_launcher_skips_crawl_scheduler_when_autostart_is_disabled(monkeypatch, tmp_path):
    from services import database_readiness

    launcher = load_launcher_module()
    calls = []
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://user:password@127.0.0.1/db")
    monkeypatch.setenv("RESEARCH_CRAWLER_AUTOSTART", "0")
    monkeypatch.setattr(launcher, "apply_frozen_desktop_defaults", lambda: tmp_path)
    monkeypatch.setattr(
        database_readiness,
        "probe_postgresql",
        lambda _database_url: SimpleNamespace(ready=True, code=SimpleNamespace(value="ready")),
    )
    monkeypatch.setattr(
        launcher,
        "_start_knowledge_worker",
        lambda *_args: calls.append("knowledge_worker"),
    )
    monkeypatch.setattr(
        launcher,
        "_start_crawl_scheduler",
        lambda *_args: calls.append("crawl_scheduler"),
    )
    monkeypatch.setattr(
        launcher,
        "run_backend",
        lambda host, port, reload: calls.append(("run_backend", host, port, reload)),
    )

    assert launcher.main(["--log-dir", str(tmp_path / "logs")]) == 0

    assert calls == ["knowledge_worker", ("run_backend", "127.0.0.1", 8765, False)]


def test_desktop_preview_launcher_skips_background_workers(monkeypatch, tmp_path):
    from services import database_readiness

    launcher = load_launcher_module()
    calls = []
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setenv("RESEARCH_PREVIEW", "1")
    monkeypatch.setattr(launcher, "apply_frozen_desktop_defaults", lambda: tmp_path)
    monkeypatch.setattr(
        database_readiness,
        "probe_postgresql",
        lambda _database_url: SimpleNamespace(ready=True, code=SimpleNamespace(value="ready")),
    )
    monkeypatch.setattr(
        launcher,
        "_start_knowledge_worker",
        lambda *_args: calls.append("knowledge_worker"),
    )
    monkeypatch.setattr(
        launcher,
        "_start_crawl_scheduler",
        lambda *_args: calls.append("crawl_scheduler"),
    )
    monkeypatch.setattr(
        launcher,
        "run_backend",
        lambda host, port, reload: calls.append(("run_backend", host, port, reload)),
    )

    assert launcher.main(["--log-dir", str(tmp_path / "logs")]) == 0

    assert calls == [("run_backend", "127.0.0.1", 8765, False)]


def test_desktop_launcher_skips_watchdogs_when_probe_fails(monkeypatch, tmp_path):
    from services import database_readiness

    launcher = load_launcher_module()
    calls = []
    isolate_desktop_launcher_environment(monkeypatch, launcher)
    monkeypatch.setattr(launcher, "apply_frozen_desktop_defaults", lambda: tmp_path)
    monkeypatch.setattr(
        database_readiness,
        "probe_postgresql",
        lambda _database_url: (_ for _ in ()).throw(RuntimeError("database unavailable")),
    )
    monkeypatch.setattr(
        launcher,
        "_start_knowledge_worker",
        lambda *_args: calls.append("knowledge_worker"),
    )
    monkeypatch.setattr(
        launcher,
        "_start_crawl_scheduler",
        lambda *_args: calls.append("crawl_scheduler"),
    )
    monkeypatch.setattr(
        launcher,
        "run_backend",
        lambda host, port, reload: calls.append(("run_backend", host, port, reload)),
    )

    assert launcher.main(["--log-dir", str(tmp_path / "logs")]) == 0

    assert calls == [("run_backend", "127.0.0.1", 8765, False)]


def test_sidecar_packages_default_industry_graphs():
    build_sidecar = load_module("desktop_build_sidecar", BUILD_SIDECAR_PY)

    assert (
        ROOT / "data" / "industry_graphs",
        Path("data") / "industry_graphs",
    ) in build_sidecar.PROJECT_DATA
