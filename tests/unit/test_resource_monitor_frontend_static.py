"""Static contracts for the AlphaFoundry system center resource monitor."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _function_region(source: str, name: str, next_name: str) -> str:
    """Return a named JavaScript function through the next known declaration."""
    start = source.find(f"function {name}")
    end = source.find(f"function {next_name}", start + 1)
    assert start >= 0, f"resource-monitor.js must declare {name}()"
    assert end >= 0, f"resource-monitor.js must declare {next_name}() after {name}()"
    return source[start:end]


def test_system_center_navigation_and_semantic_dom_contract() -> None:
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")

    assert template.count('data-section="system"') == 1
    assert ">系统</span>" in template
    assert 'data-section="resource-monitor"' not in template
    assert 'data-section="config"' not in template
    assert '<section id="section-resource-monitor" class="content-section"' in template
    assert '<section id="section-config" class="content-section configuration-page"' in template
    assert template.count('data-system-tab="resource-monitor"') == 2
    assert template.count('data-system-tab="config"') == 2
    assert re.search(
        r'<button[^>]*data-system-tab="resource-monitor"[^>]*aria-controls="section-resource-monitor"',
        template,
    )
    assert re.search(
        r'<button[^>]*data-system-tab="config"[^>]*aria-controls="section-config"',
        template,
    )
    assert ">资源与异常</button>" in template
    assert ">系统配置</button>" in template
    assert re.search(
        r'<button[^>]*data-system-tab="resource-monitor"[^>]*aria-selected="true"',
        template,
    )
    assert "仅监控 AlphaFoundry API 及其子进程" in template
    for summary_key in (
        "alpha-cpu",
        "host-cpu",
        "alpha-memory",
        "host-memory",
    ):
        assert f'data-resource-summary="{summary_key}"' in template
    for auxiliary_key in ("disk", "connections", "sampled-at"):
        assert f'data-resource-summary="{auxiliary_key}"' in template
    assert "整机其他进程" not in template
    assert "resource-monitor-host-processes" not in template
    for element_id in (
        "resource-monitor-status",
        "resource-monitor-summary",
        "resource-monitor-cpu-chart",
        "resource-monitor-memory-chart",
        "resource-monitor-host-cpu-chart",
        "resource-monitor-host-memory-chart",
        "resource-monitor-processes",
        "resource-monitor-detail",
        "resource-monitor-pinned-events",
        "resource-monitor-attribution",
        "resource-monitor-event-history",
    ):
        assert f'id="{element_id}"' in template
    assert 'aria-live="polite"' in template
    assert template.count("data-resource-sort") >= 3
    for label in ("角色", "线程", "网络连接"):
        assert f">{label}<" in template


def test_system_center_navigation_preserves_monitor_lifecycle_contract() -> None:
    app_js = (ROOT / "app/web/static/js/app.js").read_text(encoding="utf-8")
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")

    assert "/static/js/app.js?v=20260806resourcecapability1" in template
    assert "/static/js/app.js?v=20260727modalhierarchy1" not in template
    assert "./resource-monitor.js?v=20260806a" in app_js
    assert "startResourceMonitoring" in app_js
    assert "stopResourceMonitoring" in app_js
    assert "function systemTarget" in app_js
    assert "function setSystemTab" in app_js
    assert "af-system-tab" in app_js
    assert "data-system-tab" in app_js
    assert "navigateTo('system', { systemTab: 'config' })" in app_js
    assert "return SYSTEM_TABS.has(requestedTab) ? requestedTab : 'resource-monitor';" in app_js
    assert "const targetSection = systemTarget(section, options.systemTab);" in app_js
    assert "if (targetSection === 'resource-monitor') startResourceMonitoring();" in app_js
    assert "if (targetSection !== 'resource-monitor') stopResourceMonitoring();" in app_js
    assert "if (savedSection === 'resource-monitor' || savedSection === 'config')" in app_js
    assert "localStorage.setItem('af-active-section', 'system');" in app_js
    initial_navigation = _function_region(app_js, "getInitialSection", "connectSSE")
    assert "localStorage.setItem('af-system-tab', savedSection);" in initial_navigation
    assert "return 'system';" in initial_navigation


def test_system_center_status_and_event_filter_contract() -> None:
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    source = (ROOT / "app/web/static/js/resource-monitor.js").read_text(encoding="utf-8")

    assert 'id="resource-monitor-status"' in template
    assert re.search(r'id="resource-monitor-status"[^>]*\bhidden\b', template)
    assert ">ok<" not in template
    assert "warming_up" not in template
    assert '<select data-resource-event-filter=' not in template
    for kind in ("status", "severity"):
        assert f'data-resource-filter-trigger="{kind}"' in template
        assert f'data-resource-filter-menu="{kind}"' in template
        assert f'data-resource-filter-label="{kind}"' in template
    assert 'aria-haspopup="listbox"' in template
    assert 'role="listbox"' in template
    assert 'aria-expanded="false"' in template
    assert "function toggleResourceEventFilter" in source
    assert "function closeResourceEventFilters" in source
    assert "function renderResourceEventFilters" in source
    assert "RESOURCE_EVENT_FILTERS" in source
    for option in (
        "['all', '全部']",
        "['open', '未确认']",
        "['acknowledged', '已确认']",
        "['resolved', '已解决']",
        "['', '全部']",
        "['critical', '严重']",
        "['warning', '警告']",
        "['info', '信息']",
    ):
        assert option in source
    assert "option.setAttribute('role', 'option');" in source
    assert "option.setAttribute('aria-selected', String(selected));" in source
    assert "codicon-check" in source
    assert source.count("closeResourceEventFilters();") >= 3
    assert "openResourceEventFilter" in source
    filter_controls = source[
        source.index("const RESOURCE_EVENT_FILTERS") : source.index("function normalizeTimestamp")
    ]
    assert "addEventListener('click'" in filter_controls
    assert "pollResourceEvents();" in filter_controls
    assert "document.addEventListener('click'" in filter_controls
    assert "trigger.contains(event.target)" in filter_controls
    assert "menu.contains(event.target)" in filter_controls
    assert re.search(
        r"!\s*trigger\.contains\(event\.target\).*?!\s*menu\.contains\(event\.target\).*?closeResourceEventFilters\(\)",
        filter_controls,
        re.DOTALL,
    )
    keyboard_handler = _function_region(source, "handleDrawerKeydown", "resizeResourceCharts")
    assert "event.key === 'Escape'" in keyboard_handler
    assert "closeResourceEventFilters()" in keyboard_handler
    event_renderer = source[
        source.index("function renderResourceEvents") : source.index("function renderEventList")
    ]
    assert "renderStatus(publicStatus(points.at(-1)?.status));" in event_renderer
    status_renderer = _function_region(source, "renderStatus", "renderSummary")
    assert "const pending = resourceEvents.filter(event => event.status !== 'resolved');" in status_renderer
    assert "const unavailable = publicStatus(code) === 'unavailable';" in status_renderer
    assert "if (!unavailable && pending.length === 0)" in status_renderer
    assert "status.hidden = true;" in status_renderer
    assert "status.textContent = '';" in status_renderer
    assert "status.hidden = false;" in status_renderer
    assert "采样暂不可用，保留上一帧数据" in status_renderer
    assert "个待处理异常" in status_renderer
    assert "ok" not in status_renderer


def test_system_center_preserves_minimal_configuration_form_and_api_contract() -> None:
    template = (ROOT / "app/web/templates/index.html").read_text(encoding="utf-8")
    source = (ROOT / "app/web/static/js/configuration.js").read_text(encoding="utf-8")

    assert '<section id="section-config" class="content-section configuration-page"' in template
    for marker in (
        "data-config-health-summary",
        'data-config-card="database"',
        'id="config-edit-modal"',
    ):
        assert marker in template
    assert "data-config-form" in source
    assert "export async function initConfigurationPage" in source
    assert "configurationApiCall('GET', '/api/config'" in source
    assert "configurationApiCall('PUT', `/api/config/${section}`, payload)" in source


def test_resource_monitor_module_handles_lifecycle_bounds_and_safe_process_dom() -> None:
    source = (ROOT / "app/web/static/js/resource-monitor.js").read_text(encoding="utf-8")

    assert "export function startResourceMonitoring" in source
    assert "export function stopResourceMonitoring" in source
    assert "const MAX_POINTS = 150;" in source
    assert "/api/system/resource-usage/history?window_seconds=300" in source
    assert "/api/system/resource-usage/host-history?hours=24" in source
    assert "/api/system/resource-usage" in source
    assert "AbortController" in source
    assert "hostHistoryController?.abort()" in source
    assert "hostCpuChart?.dispose?.()" in source
    assert "visibilitychange" in source
    assert "document.hidden" in source
    assert "setTimeout" in source
    assert "[4000, 6000, 8000, 10000]" in source
    assert "points.slice(-MAX_POINTS)" in source
    assert "textContent" in source
    assert "data-resource-sort" in source
    assert "selectedProcessPid" in source
    assert "let sortDirection = -1;" in source
    assert (
        "const value = processSortValue(left, sortKey) - processSortValue(right, sortKey);"
        in source
    )
    assert "if (sortKey !== nextKey)" in source
    assert "sortDirection = -1;" in source
    assert "已退出；保留最后一次采样信息" in source
    assert "historyVersion" in source
    assert "snapshotVersion" in source
    assert "snapshotVersion > snapshotVersionAtRequest" in source
    assert "ingestSnapshot(snapshot, 'history')" in source
    assert "if (source === 'snapshot')" in source
    assert "publicStatus(snapshot.status) === 'unavailable'" in source
    assert "未发现 AlphaFoundry 进程" in source
    assert "const DEPARTED_PROCESS_TTL_MS" in source
    assert "const MAX_DEPARTED_PROCESSES" in source
    assert "function pruneDepartedProcesses" in source
    assert "processCache.delete(pid)" in source
    assert "processTrends.delete(pid)" in source
    assert "selectedProcessPid = null" in source
    assert "resource-monitor-detail-close" in source
    assert "Escape" in source
    assert "function closeProcessDetail" in source
    assert "focus()" in source
    assert "function resizeResourceCharts" in source
    assert "resizeResourceCharts();" in source
    assert "create_time == null ? '—'" in source
    assert "已退出" in source
    assert "window.echarts" in source
    assert "innerHTML" not in source
    assert "/api/system/resource-events" in source
    assert "function renderResourceEvents" in source
    assert "function renderAttribution" in source
    assert "shared_process_estimate" in source
    assert "source_scope" in source
    assert "sourceScopeLabel(metadata.source_scope)" in source
    assert "整机容量" in source
    assert "AlphaFoundry" in source
    assert "function updateResourceEvent" in source
    assert "异常历史暂不可用，保留上一份记录" in source
    assert "function isFieldUnavailable" in source
    assert "当前平台不支持" in source
    event_builder = source[
        source.index("function createResourceEvent") : source.index("function sourceScopeLabel")
    ]
    assert "resource-event-row" in event_builder
    assert "resource-event-actions" in event_builder
    assert "item.append(actions);" in event_builder


def test_resource_monitor_styles_keep_dense_responsive_tables_and_charts() -> None:
    style = (ROOT / "app/web/static/style.css").read_text(encoding="utf-8")

    assert "#section-resource-monitor" in style
    assert "grid-template-columns: repeat(2, minmax(0, 1fr))" in style
    assert 'resource-summary-card[data-resource-scope="alpha"]' in style
    assert 'resource-summary-card[data-resource-scope="host"]' in style
    assert "@media (max-width: 900px)" in style
    assert "min-width: 900px" in style
    assert "overflow-x: auto" in style
    assert "font-family: var(--font-mono)" in style
    assert ".resource-monitor-detail.hidden" in style
    assert "position: fixed" in style
    assert "right: 0" in style
    assert ".resource-process-table th:nth-child(2)," in style
    assert ".resource-process-table td:nth-child(2)," in style
    assert "nth-child(n + 2)" not in style
    assert ".resource-process-table tbody tr:focus-visible" in style
    assert ".resource-detail-close" in style
    assert ".resource-event-critical" in style
    assert ".resource-event-filters" in style
    assert ".resource-filter-trigger" in style
    assert ".resource-filter-menu" in style
    assert ".resource-filter-option" in style
    assert ".resource-event-row" in style
    assert ".resource-event-row .resource-event-actions" in style
    assert ".resource-monitor-status[hidden]" in style
    assert re.search(
        r"@media \(max-width: 900px\)[\s\S]*?\.resource-event-row\s*\{[\s\S]*?grid-template-columns:\s*1fr",
        style,
    )
    assert 'strong[data-resource-summary="host-memory"]' in style
    assert "white-space: normal" in style
