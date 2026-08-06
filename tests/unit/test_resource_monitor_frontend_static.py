"""Static contracts for the AlphaFoundry system center resource monitor."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _function_body(source: str, name: str) -> str:
    """Return a balanced JavaScript function body without relying on declaration order."""
    match = re.search(rf"\bfunction\s+{re.escape(name)}\s*\([^)]*\)\s*\{{", source)
    assert match, f"resource-monitor.js must declare {name}()"
    depth = 1
    index = match.end()
    quote = None
    while index < len(source) and depth:
        character = source[index]
        if quote:
            if character == "\\":
                index += 1
            elif character == quote:
                quote = None
        elif character in {"'", '"', "`"}:
            quote = character
        elif character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        index += 1
    assert depth == 0, f"resource-monitor.js has an unclosed {name}() function"
    return source[match.start():index]


def _media_blocks(source: str, query: str) -> list[str]:
    """Return balanced CSS media blocks that match one query."""
    blocks = []
    for match in re.finditer(rf"@media\s*\(\s*{re.escape(query)}\s*\)\s*\{{", source):
        depth = 1
        index = match.end()
        while index < len(source) and depth:
            if source[index] == "{":
                depth += 1
            elif source[index] == "}":
                depth -= 1
            index += 1
        assert depth == 0, f"CSS media block {query!r} must be balanced"
        blocks.append(source[match.end():index - 1])
    assert blocks, f"CSS must declare @media ({query})"
    return blocks


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
    assert "本机资源、异常与运行配置" in template
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

    assert "startResourceMonitoring" in app_js
    assert "stopResourceMonitoring" in app_js
    assert "function systemTarget" in app_js
    assert "function setSystemTab" in app_js
    assert "af-system-tab" in app_js
    assert "data-system-tab" in app_js
    assert re.search(
        r"navigateTo\(\s*['\"]system['\"]\s*,\s*\{\s*systemTab:\s*['\"]config['\"]\s*}\s*\)",
        app_js,
    )
    assert re.search(
        r"if\s*\(\s*(?P<saved>\w+)\s*===\s*['\"]resource-monitor['\"]\s*\|\|\s*(?P=saved)\s*===\s*['\"]config['\"]\s*\)",
        app_js,
    )
    assert re.search(r"localStorage\.setItem\(['\"]af-active-section['\"]\s*,\s*['\"]system['\"]\s*\)", app_js)
    system_router = _function_body(app_js, "systemTarget")
    assert re.search(
        r"return\s+SYSTEM_TABS\.has\(\s*\w+\s*\)\s*\?\s*\w+\s*:\s*['\"]resource-monitor['\"]",
        system_router,
    )
    target_section = re.search(
        r"(?:const|let)\s+(?P<target>\w+)\s*=\s*systemTarget\(\s*section\s*,\s*options\.systemTab\s*\)",
        app_js,
    )
    assert target_section
    assert re.search(
        rf"if\s*\(\s*{target_section.group('target')}\s*===\s*['\"]resource-monitor['\"]\s*\)\s*startResourceMonitoring\(\)",
        app_js,
    )
    assert re.search(
        rf"if\s*\(\s*{target_section.group('target')}\s*!==\s*['\"]resource-monitor['\"]\s*\)\s*stopResourceMonitoring\(\)",
        app_js,
    )
    initial_navigation = _function_body(app_js, "getInitialSection")
    assert re.search(r"localStorage\.setItem\(['\"]af-system-tab['\"]\s*,\s*\w+\s*\)", initial_navigation)
    assert "return 'system';" in initial_navigation
    initial_navigation = re.search(
        r"const\s+(?P<section>\w+)\s*=\s*getInitialSection\(\);\s*"
        r"const\s+initialSystemTab\s*=\s*localStorage\.getItem\('af-system-tab'\);[\s\S]*?"
        r"navigateTo\(\s*(?P=section)\s*,\s*\{\s*systemTab:\s*initialSystemTab\s*}\s*\)",
        app_js,
    )
    assert initial_navigation
    assert re.search(
        r"\[data-system-tab\][\s\S]*?addEventListener\(['\"]click['\"][\s\S]*?navigateTo\(\s*['\"]system['\"]\s*,\s*\{\s*systemTab:\s*\w+\.dataset\.systemTab",
        app_js,
    )


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
    assert re.search(r"\w+\.setAttribute\(['\"]role['\"]\s*,\s*['\"]option['\"]\)", source)
    assert re.search(r"\w+\.setAttribute\(['\"]aria-selected['\"]\s*,\s*String\([^)]*\)\)", source)
    assert "codicon-check" in source
    filter_renderer = _function_body(source, "renderResourceEventFilters")
    assert "addEventListener('click'" in filter_renderer
    assert "pollResourceEvents();" in filter_renderer
    assert "closeResourceEventFilters();" in filter_renderer
    filter_state = re.search(
        r"(?:const|let)\s+(?P<state>\w+)\s*=\s*\{\s*status\s*:\s*['\"]all['\"]",
        source,
    )
    assert filter_state
    assert re.search(
        rf"{filter_state.group('state')}\[[^]]+\]\s*=\s*[^;]+;[\s\S]*?renderResourceEventFilters\(\);[\s\S]*?pollResourceEvents\(\);[\s\S]*?closeResourceEventFilters\(\);",
        filter_renderer,
        re.DOTALL,
    )
    controls = _function_body(source, "bindControls")
    assert re.search(
        r"document\.addEventListener\(['\"]click['\"][\s\S]*?!\s*\w*trigger\w*\.contains\(event\.target\)\s*&&\s*!\s*\w*menu\w*\.contains\(event\.target\)[\s\S]*?closeResourceEventFilters\(\)",
        controls,
        re.DOTALL,
    )
    keyboard_handler = _function_body(source, "handleDrawerKeydown")
    assert "event.key === 'Escape'" in keyboard_handler
    assert "closeResourceEventFilters()" in keyboard_handler
    event_renderer = _function_body(source, "renderResourceEvents")
    assert "renderStatus(publicStatus(points.at(-1)?.status));" in event_renderer
    status_renderer = _function_body(source, "renderStatus")
    status_element = re.search(
        r"(?:const|let)\s+(?P<element>\w+)\s*=\s*document\.getElementById\(['\"]resource-monitor-status['\"]\)",
        status_renderer,
    )
    assert status_element
    pending_match = re.search(
        r"(?:const|let)\s+(?P<pending>\w+)\s*=\s*resourceEvents\.filter\([^)]*status\s*!==\s*['\"]resolved['\"]",
        status_renderer,
    )
    unavailable_match = re.search(
        r"(?:const|let)\s+(?P<unavailable>\w+)\s*=\s*publicStatus\(code\)\s*===\s*['\"]unavailable['\"]",
        status_renderer,
    )
    assert pending_match and unavailable_match
    hidden_branch = re.search(
        rf"if\s*\(\s*!\s*{unavailable_match.group('unavailable')}\s*&&\s*{pending_match.group('pending')}\.length\s*===\s*0\s*\)\s*\{{(?P<body>[\s\S]*?)\}}",
        status_renderer,
    )
    assert hidden_branch
    assert f"{status_element.group('element')}.hidden = true;" in hidden_branch.group("body")
    assert f"{status_element.group('element')}.textContent = '';" in hidden_branch.group("body")
    assert "return;" in hidden_branch.group("body")
    assert f"{status_element.group('element')}.hidden = false;" in status_renderer
    assert "采样暂不可用，保留上一帧数据" in status_renderer
    assert "个待处理异常" in status_renderer
    assert not re.search(
        rf"{status_element.group('element')}\.textContent\s*=\s*publicStatus\(",
        status_renderer,
    )
    assert not re.search(r"['\"`](?:ok|degraded)['\"`]", status_renderer)


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
    event_builder = _function_body(source, "createResourceEvent")
    assert "resource-event-row" in event_builder
    assert "resource-event-info" in event_builder
    assert "resource-event-actions" in event_builder
    event_root = re.search(
        r"(?:const|let)\s+(?P<root>\w+)\s*=\s*document\.createElement\([^)]*\)",
        event_builder,
    )
    info_container = re.search(
        r"(?P<info>\w+)\.(?:className\s*=\s*['\"][^'\"]*resource-event-info|classList\.add\([^)]*['\"]resource-event-info)",
        event_builder,
    )
    action_container = re.search(
        r"(?P<actions>\w+)\.(?:className\s*=\s*['\"][^'\"]*resource-event-actions|classList\.add\([^)]*['\"]resource-event-actions)",
        event_builder,
    )
    assert event_root and info_container and action_container
    assert re.search(
        rf"{event_root.group('root')}\.(?:className\s*=\s*['\"][^'\"]*resource-event-row|classList\.add\([^)]*['\"]resource-event-row)",
        event_builder,
    )
    append_calls = re.findall(
        rf"{event_root.group('root')}\.(?:append|appendChild)\((?P<children>[^;]+)\);",
        event_builder,
    )
    assert any(info_container.group("info") in children for children in append_calls)
    assert any(action_container.group("actions") in children for children in append_calls)


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
    assert ".resource-event-row .resource-event-info" in style
    assert ".resource-event-row .resource-event-actions" in style
    assert ".resource-monitor-status[hidden]" in style
    mobile_blocks = _media_blocks(style, "max-width: 900px")
    assert any(
        re.search(r"\.resource-event-row\s*\{[^}]*grid-template-columns:\s*1fr", block)
        and re.search(
            r"\.resource-event-row\s+\.resource-event-actions\s*\{[^}]*(?:justify-self:\s*end|justify-content:\s*flex-end)",
            block,
        )
        for block in mobile_blocks
    )
    assert 'strong[data-resource-summary="host-memory"]' in style
    assert "white-space: normal" in style
