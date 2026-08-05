"""Static contracts for the AlphaFoundry resource monitoring workbench page."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_resource_monitor_navigation_and_semantic_dom_contract() -> None:
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")

    assert 'data-section="resource-monitor"' in template
    assert ">系统监控</span>" in template
    assert '<section id="section-resource-monitor" class="content-section"' in template
    assert "仅监控 AlphaFoundry API 及其子进程" in template
    for element_id in (
        "resource-monitor-status",
        "resource-monitor-summary",
        "resource-monitor-cpu-chart",
        "resource-monitor-memory-chart",
        "resource-monitor-processes",
        "resource-monitor-detail",
    ):
        assert f'id="{element_id}"' in template
    assert 'aria-live="polite"' in template
    assert template.count("data-resource-sort") >= 3


def test_resource_monitor_module_cache_and_navigation_lifecycle_contract() -> None:
    app_js = (ROOT / "app/web/static/js/app.js").read_text(encoding="utf-8")

    assert "./resource-monitor.js?v=20260805a" in app_js
    assert "startResourceMonitoring" in app_js
    assert "stopResourceMonitoring" in app_js
    assert "if (section === 'resource-monitor') startResourceMonitoring();" in app_js
    assert "if (section !== 'resource-monitor') stopResourceMonitoring();" in app_js


def test_resource_monitor_module_handles_lifecycle_bounds_and_safe_process_dom() -> None:
    source = (ROOT / "app/web/static/js/resource-monitor.js").read_text(encoding="utf-8")

    assert "export function startResourceMonitoring" in source
    assert "export function stopResourceMonitoring" in source
    assert "const MAX_POINTS = 150;" in source
    assert "/api/system/resource-usage/history?window_seconds=300" in source
    assert "/api/system/resource-usage" in source
    assert "AbortController" in source
    assert "visibilitychange" in source
    assert "document.hidden" in source
    assert "setTimeout" in source
    assert "[4000, 6000, 8000, 10000]" in source
    assert "points.slice(-MAX_POINTS)" in source
    assert "textContent" in source
    assert "data-resource-sort" in source
    assert "selectedPid" in source
    assert "已退出" in source
    assert "window.echarts" in source
    assert "innerHTML" not in source


def test_resource_monitor_styles_keep_dense_responsive_tables_and_charts() -> None:
    style = (ROOT / "app/web/static/style.css").read_text(encoding="utf-8")

    assert "#section-resource-monitor" in style
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in style
    assert "@media (max-width: 900px)" in style
    assert "min-width: 760px" in style
    assert "overflow-x: auto" in style
    assert "font-family: var(--font-mono)" in style
