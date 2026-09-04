/* ============================================================
   Research Workbench — Resource Monitor
   Restricted to the local API process and its child processes.
   ============================================================ */

import { apiCall, getChartColors } from './core.js';

const MAX_POINTS = 150;
const POLL_INTERVAL_MS = 2000;
const HOST_HISTORY_REFRESH_MS = 60 * 1000;
const BACKOFF_DELAYS = [4000, 6000, 8000, 10000];
const DEPARTED_PROCESS_TTL_MS = 5 * 60 * 1000;
const MAX_DEPARTED_PROCESSES = 50;
const PUBLIC_STATUSES = new Set(['warming_up', 'ok', 'degraded', 'unavailable']);
const RESOURCE_EVENT_FILTERS = {
    status: [['all', '全部'], ['open', '待处理'], ['acknowledged', '已确认'], ['resolved', '已解决']],
    severity: [['', '全部'], ['critical', '严重'], ['warning', '警告'], ['info', '信息']],
};

let isMonitoring = false;
let pollTimer = null;
let snapshotController = null;
let historyController = null;
let hostHistoryController = null;
let eventController = null;
let hostHistoryTimer = null;
let failureCount = 0;
let historyVersion = 0;
let snapshotVersion = 0;
let lastFailureAt = null;
let retryDelay = null;
let resourceEvents = [];
let eventFailure = false;
let visibilityListenerAttached = false;
let resizeListenerAttached = false;
let keyboardListenerAttached = false;
let filterOutsideListenerAttached = false;
let resourceFilterOutsideListener = null;
let cpuChart = null;
let memoryChart = null;
let hostCpuChart = null;
let hostMemoryChart = null;
let points = [];
let hostHistoryPoints = [];
let hostHistoryFailure = false;
let hostHistoryVersion = 0;
let selectedProcessPid = null;
let processTreeUnavailable = false;
let sortKey = 'cpu';
let sortDirection = -1;
let resourceEventFilterState = { status: 'all', severity: '' };
let openResourceEventFilter = null;
let resourceFilterFocusFrame = null;
const processCache = new Map();
const processTrends = new Map();

export function startResourceMonitoring() {
    stopResourceMonitoring();
    isMonitoring = true;
    bindControls();
    attachVisibilityListener();
    attachResizeListener();
    attachKeyboardListener();
    renderResourceEventFilters();
    resizeResourceCharts();
    if (!canPoll()) {
        renderStatus('warming_up');
        return;
    }
    loadInitialHistory();
    loadHostHistory();
    pollResourceEvents();
    pollSnapshot();
}

export function stopResourceMonitoring() {
    isMonitoring = false;
    clearPollTimer();
    clearHostHistoryTimer();
    abortRequests();
    disposeResourceCharts();
    if (visibilityListenerAttached) {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        visibilityListenerAttached = false;
    }
    if (keyboardListenerAttached) {
        document.removeEventListener('keydown', handleDrawerKeydown);
        keyboardListenerAttached = false;
    }
    clearResourceEventFilterFocusFrame();
    closeResourceEventFilters({ restoreFocus: false });
    if (filterOutsideListenerAttached) {
        document.removeEventListener('click', resourceFilterOutsideListener);
        filterOutsideListenerAttached = false;
        resourceFilterOutsideListener = null;
    }
}

function canPoll() {
    return isMonitoring
        && !document.hidden
        && document.getElementById('section-resource-monitor')?.classList.contains('active');
}

function clearPollTimer() {
    if (pollTimer !== null) {
        clearTimeout(pollTimer);
        pollTimer = null;
    }
}

function clearHostHistoryTimer() {
    if (hostHistoryTimer !== null) {
        clearTimeout(hostHistoryTimer);
        hostHistoryTimer = null;
    }
}

function abortRequests() {
    snapshotController?.abort();
    historyController?.abort();
    hostHistoryController?.abort();
    eventController?.abort();
    snapshotController = null;
    historyController = null;
    hostHistoryController = null;
    eventController = null;
}

function attachVisibilityListener() {
    if (visibilityListenerAttached) return;
    document.addEventListener('visibilitychange', handleVisibilityChange);
    visibilityListenerAttached = true;
}

function attachResizeListener() {
    if (resizeListenerAttached) return;
    window.addEventListener('resize', () => {
        if (!isMonitoring) return;
        resizeResourceCharts();
    });
    resizeListenerAttached = true;
}

function attachKeyboardListener() {
    if (keyboardListenerAttached) return;
    document.addEventListener('keydown', handleDrawerKeydown);
    keyboardListenerAttached = true;
}

function handleDrawerKeydown(event) {
    if (event.key === 'Escape') {
        if (openResourceEventFilter !== null) {
            closeResourceEventFilters();
            return;
        }
        if (selectedProcessPid !== null) closeProcessDetail();
    }
}

function resizeResourceCharts() {
    cpuChart?.resize();
    memoryChart?.resize();
    hostCpuChart?.resize();
    hostMemoryChart?.resize();
}

function disposeResourceCharts() {
    cpuChart?.dispose?.();
    memoryChart?.dispose?.();
    hostCpuChart?.dispose?.();
    hostMemoryChart?.dispose?.();
    cpuChart = null;
    memoryChart = null;
    hostCpuChart = null;
    hostMemoryChart = null;
}

function handleVisibilityChange() {
    if (document.hidden) {
        clearPollTimer();
        clearHostHistoryTimer();
        abortRequests();
        return;
    }
    if (canPoll()) {
        resizeResourceCharts();
        loadInitialHistory();
        loadHostHistory();
        pollResourceEvents();
        pollSnapshot();
    }
}

function scheduleHostHistoryRefresh() {
    clearHostHistoryTimer();
    if (!canPoll()) return;
    hostHistoryTimer = setTimeout(loadHostHistory, HOST_HISTORY_REFRESH_MS);
}

function schedulePoll(delay) {
    clearPollTimer();
    if (!canPoll()) return;
    pollTimer = setTimeout(pollSnapshot, delay);
}

async function loadInitialHistory() {
    if (!canPoll()) return;
    historyController?.abort();
    const controller = new AbortController();
    const requestedHistoryVersion = ++historyVersion;
    const snapshotVersionAtRequest = snapshotVersion;
    historyController = controller;
    try {
        const history = await apiCall(
            'GET',
            '/api/system/resource-usage/history?window_seconds=300',
            null,
            { signal: controller.signal, retries: 0 },
        );
        if (
            controller.signal.aborted
            || !canPoll()
            || requestedHistoryVersion !== historyVersion
            || snapshotVersion > snapshotVersionAtRequest
        ) return;
        const snapshots = Array.isArray(history?.points) ? history.points : [];
        snapshots.forEach(snapshot => ingestSnapshot(snapshot, 'history'));
        renderAll();
    } catch (error) {
        if (!isAbortError(error)) logRequestFailure('history', error);
    } finally {
        if (historyController === controller) historyController = null;
    }
}

async function loadHostHistory() {
    if (!canPoll()) return;
    hostHistoryController?.abort();
    const controller = new AbortController();
    const requestedHistoryVersion = ++hostHistoryVersion;
    hostHistoryController = controller;
    try {
        const history = await apiCall(
            'GET',
            '/api/system/resource-usage/host-history?hours=24',
            null,
            { signal: controller.signal, retries: 0 },
        );
        if (
            controller.signal.aborted
            || !canPoll()
            || requestedHistoryVersion !== hostHistoryVersion
        ) return;
        hostHistoryPoints = (Array.isArray(history?.points) ? history.points : [])
            .filter(point => point && typeof point === 'object')
            .map(point => ({
                sampled_at: normalizeTimestamp(point.sampled_at),
                host: point.host && typeof point.host === 'object' ? point.host : {},
                alpha: point.alpha && typeof point.alpha === 'object' ? point.alpha : {},
            }))
            .sort((left, right) => left.sampled_at.localeCompare(right.sampled_at));
        hostHistoryFailure = false;
        renderCharts();
        renderHostHistoryStatus();
    } catch (error) {
        if (!isAbortError(error)) {
            logRequestFailure('host-history', error);
            hostHistoryFailure = true;
            renderCharts();
            renderHostHistoryStatus();
        }
    } finally {
        if (hostHistoryController === controller) hostHistoryController = null;
        if (!controller.signal.aborted) scheduleHostHistoryRefresh();
    }
}

async function pollSnapshot() {
    if (!canPoll()) return;
    clearPollTimer();
    snapshotController?.abort();
    const controller = new AbortController();
    snapshotController = controller;
    try {
        const snapshot = await apiCall(
            'GET',
            '/api/system/resource-usage',
            null,
            { signal: controller.signal, retries: 0 },
        );
        if (controller.signal.aborted || !canPoll()) return;
        ingestSnapshot(snapshot, 'snapshot');
        failureCount = 0;
        lastFailureAt = null;
        retryDelay = null;
        renderAll();
        pollResourceEvents();
        schedulePoll(POLL_INTERVAL_MS);
    } catch (error) {
        if (isAbortError(error)) return;
        logRequestFailure('snapshot', error);
        const delay = BACKOFF_DELAYS[Math.min(failureCount, BACKOFF_DELAYS.length - 1)];
        failureCount += 1;
        lastFailureAt = new Date();
        retryDelay = delay;
        renderStatus('unavailable');
        schedulePoll(delay);
    } finally {
        if (snapshotController === controller) snapshotController = null;
    }
}

async function pollResourceEvents() {
    if (!canPoll()) return;
    eventController?.abort();
    const controller = new AbortController();
    eventController = controller;
    const filters = resourceEventFilters();
    const query = new URLSearchParams({ days: '90', status: filters.status });
    if (filters.severity) query.set('severity', filters.severity);
    try {
        const response = await apiCall(
            'GET',
            `/api/system/resource-events?${query.toString()}`,
            null,
            { signal: controller.signal, retries: 0 },
        );
        if (controller.signal.aborted || !canPoll()) return;
        resourceEvents = Array.isArray(response?.items) ? response.items : [];
        eventFailure = false;
        renderResourceEvents();
    } catch (error) {
        if (!isAbortError(error)) {
            logRequestFailure('resource-events', error);
            eventFailure = true;
            renderResourceEvents();
        }
    } finally {
        if (eventController === controller) eventController = null;
    }
}

function isAbortError(error) {
    return error?.name === 'AbortError';
}

function logRequestFailure(operation, error) {
    console.warn('[resource-monitor] request failed', {
        operation,
        errorType: error?.name || 'UnknownError',
    });
}

function ingestSnapshot(snapshot, source) {
    if (!snapshot || typeof snapshot !== 'object') return;
    if (source === 'snapshot') snapshotVersion += 1;
    const sampledAt = normalizeTimestamp(snapshot.sampled_at);
    const point = { ...snapshot, sampled_at: sampledAt };
    const matchingIndex = points.findIndex(existing => existing.sampled_at === sampledAt);
    if (matchingIndex >= 0) points[matchingIndex] = point;
    else points.push(point);
    points.sort((left, right) => left.sampled_at.localeCompare(right.sampled_at));
    points = points.slice(-MAX_POINTS);

    if (source === 'snapshot' && publicStatus(snapshot.status) === 'unavailable') {
        processTreeUnavailable = true;
        processCache.clear();
        processTrends.clear();
        selectedProcessPid = null;
        return;
    }

    if (source === 'snapshot') processTreeUnavailable = false;

    const currentPids = new Set();
    const processes = Array.isArray(snapshot.processes) ? snapshot.processes : [];
    processes.forEach(process => {
        const pid = safePid(process?.pid);
        if (pid === null) return;
        currentPids.add(pid);
        const current = { ...process, pid, departed: false, sampled_at: sampledAt };
        processCache.set(pid, current);
        appendProcessTrend(pid, sampledAt, current);
    });
    if (source === 'snapshot') {
        processCache.forEach((process, pid) => {
            if (!currentPids.has(pid)) {
                processCache.set(pid, {
                    ...process,
                    departed: true,
                    departed_at: process.departed_at || sampledAt,
                });
            }
        });
        pruneDepartedProcesses(sampledAt);
    }
}

function pruneDepartedProcesses(sampledAt) {
    const now = new Date(sampledAt).getTime();
    const cutoff = (Number.isFinite(now) ? now : Date.now()) - DEPARTED_PROCESS_TTL_MS;
    const departed = [...processCache.entries()]
        .filter(([, process]) => process.departed)
        .sort(([, left], [, right]) => String(left.departed_at || '').localeCompare(String(right.departed_at || '')));
    const expired = departed.filter(([, process]) => new Date(process.departed_at).getTime() < cutoff);
    const overflow = departed.slice(0, Math.max(0, departed.length - MAX_DEPARTED_PROCESSES));
    new Set([...expired, ...overflow].map(([pid]) => pid)).forEach(removeDepartedProcess);
}

function removeDepartedProcess(pid) {
    processCache.delete(pid);
    processTrends.delete(pid);
    if (selectedProcessPid === pid) selectedProcessPid = null;
}

function appendProcessTrend(pid, sampledAt, process) {
    const at = new Date(sampledAt).getTime();
    if (!Number.isFinite(at)) return;
    const trend = processTrends.get(pid) || [];
    trend.push({
        at,
        cpu: safeNumber(process.cpu_percent),
        memory: safeNumber(process.memory_bytes),
    });
    processTrends.set(pid, trend.filter(item => item.at >= at - 60000).slice(-31));
}

function renderAll() {
    const latest = points.at(-1);
    renderStatus(publicStatus(latest?.status));
    renderSummary(latest?.summary);
    renderCharts();
    renderHostHistoryStatus();
    renderProcessTable();
    renderDetail();
    renderAttribution();
    renderResourceEvents();
}

function renderAttribution() {
    const container = document.getElementById('resource-monitor-attribution');
    if (!container) return;
    const latest = points.at(-1);
    const processes = Array.isArray(latest?.processes) ? latest.processes : [];
    const fragment = document.createDocumentFragment();
    processes.forEach(process => {
        const tasks = Array.isArray(process.active_tasks) ? process.active_tasks : [];
        if (!tasks.length && process.attribution_kind !== 'worker' && process.attribution_kind !== 'scheduler') return;
        const item = document.createElement('article');
        item.className = 'resource-attribution-item';
        const title = document.createElement('strong');
        const confidence = process.confidence === 'shared_process_estimate'
            ? '共享 API 进程估算' : '独立进程精确值';
        title.textContent = `${safeText(process.role, 'Research Workbench 进程')} · ${confidence}`;
        const detail = document.createElement('span');
        const taskLabels = tasks.map(task => safeText(task.label, safeText(task.task_kind, '运行任务'))).join('、');
        detail.textContent = taskLabels || `PID ${process.pid} · CPU ${process.cpu_percent == null ? '采样中' : `${formatNumber(process.cpu_percent, 1)}%`}`;
        item.append(title, detail);
        fragment.append(item);
    });
    if (!fragment.childNodes.length) {
        const empty = document.createElement('p');
        empty.className = 'resource-monitor-empty';
        empty.textContent = '暂无活跃任务归因；独立 Worker 启动后会显示在这里。';
        fragment.append(empty);
    }
    container.replaceChildren(fragment);
}

function renderResourceEvents() {
    const pending = resourceEvents.filter(event => event.status !== 'resolved');
    renderEventList('resource-monitor-pinned-events', pending, true);
    renderEventList('resource-monitor-event-history', resourceEvents, false);
    const status = document.getElementById('resource-event-status');
    if (status) status.textContent = eventFailure
        ? '异常历史暂不可用，保留上一份记录'
        : `${pending.length} 个待处理异常`;
    renderStatus(publicStatus(points.at(-1)?.status));
}

function renderEventList(elementId, events, isPinned) {
    const container = document.getElementById(elementId);
    if (!container) return;
    const ordered = [...events].sort((left, right) => {
        const severity = (right.severity === 'critical') - (left.severity === 'critical');
        return severity || String(right.triggered_at).localeCompare(String(left.triggered_at));
    });
    const fragment = document.createDocumentFragment();
    ordered.forEach(event => fragment.append(createResourceEvent(event, isPinned)));
    if (!ordered.length) {
        const empty = document.createElement('p');
        empty.className = 'resource-monitor-empty';
        empty.textContent = isPinned ? '当前没有待处理异常。' : '所选条件下没有异常历史。';
        fragment.append(empty);
    }
    container.replaceChildren(fragment);
}

function createResourceEvent(event, isPinned) {
    const item = document.createElement('article');
    const severity = ['critical', 'warning', 'info'].includes(event.severity) ? event.severity : 'warning';
    item.className = 'resource-event resource-event-row';
    item.classList.add(`resource-event-${severity}`);
    const content = document.createElement('div');
    content.className = 'resource-event-content';
    const title = document.createElement('strong');
    title.textContent = safeText(event.title, '资源监控异常');
    const detail = document.createElement('p');
    const metadata = event.metadata && typeof event.metadata === 'object' ? event.metadata : {};
    detail.textContent = `${sourceScopeLabel(metadata.source_scope)} · ${safeText(metadata.task_kind, '系统')} · ${formatTime(event.triggered_at)}`;
    const description = document.createElement('span');
    description.textContent = safeText(event.description, '请查看 Research Workbench 日志。');
    content.append(title, detail, description);
    item.append(content);
    if (isPinned) {
        const actions = document.createElement('div');
        actions.className = 'resource-event-actions';
        if (event.status === 'open') actions.append(createEventAction('确认', event.alert_id, 'acknowledge'));
        if (event.status !== 'resolved') actions.append(createEventAction('解决', event.alert_id, 'resolve'));
        if (actions.childElementCount) item.append(actions);
        else {
            title.tabIndex = 0;
            title.dataset.resourceEventTitleAnchor = 'true';
            title.setAttribute('role', 'heading');
            title.setAttribute('aria-level', '4');
        }
    }
    return item;
}

function sourceScopeLabel(scope) {
    return scope === 'host' || scope === 'host_capacity' ? '整机容量' : 'Research Workbench';
}

function createEventAction(label, alertId, action) {
    const button = document.createElement('button');
    button.type = 'button';
    button.textContent = label;
    button.addEventListener('click', () => updateResourceEvent(alertId, action));
    return button;
}

async function updateResourceEvent(alertId, action) {
    try {
        await apiCall('POST', `/api/system/resource-events/${encodeURIComponent(alertId)}/${action}`,
            action === 'resolve' ? { notes: '已在系统监控页解决。' } : null, { retries: 0 });
        await pollResourceEvents();
    } catch (error) {
        logRequestFailure(`resource-event-${action}`, error);
        eventFailure = true;
        renderResourceEvents();
    }
}

function publicStatus(value) {
    return PUBLIC_STATUSES.has(value) ? value : 'unavailable';
}

function renderStatus(code) {
    const status = document.getElementById('resource-monitor-status');
    if (!status) return;
    const pending = resourceEvents.filter(event => event.status !== 'resolved');
    const unavailable = publicStatus(code) === 'unavailable';
    status.dataset.status = publicStatus(code);
    if (!unavailable && pending.length === 0) {
        status.hidden = true;
        status.textContent = '';
        return;
    }
    status.hidden = false;
    if (unavailable) {
        status.textContent = '采样暂不可用，保留上一帧数据';
        return;
    }
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'resource-monitor-status-action';
    action.setAttribute('aria-controls', 'resource-monitor-pinned-events');
    action.textContent = `${pending.length} 个待处理异常`;
    action.addEventListener('click', focusPinnedResourceEvents);
    status.replaceChildren(action);
}

function focusPinnedResourceEvents() {
    const container = document.getElementById('resource-monitor-pinned-events');
    if (!container) return;
    const target = container.querySelector('.resource-event-actions button')
        || container.querySelector('[data-resource-event-title-anchor="true"]');
    if (!target) return;
    container.scrollIntoView({ behavior: 'smooth', block: 'center' });
    target.focus({ preventScroll: true });
}

function renderSummary(summary) {
    const values = summary && typeof summary === 'object' ? summary : {};
    const latest = points.at(-1);
    const host = latest?.host && typeof latest.host === 'object' ? latest.host : {};
    const alphaCpuPercent = safeNumber(values.cpu_percent);
    const alphaCpuHostPercent = safeNumber(values.cpu_host_percent);
    const alphaMemoryBytes = safeNumber(values.memory_bytes);
    const alphaMemoryHostPercent = safeNumber(values.memory_host_percent);
    const hostCpuPercent = safeNumber(host.cpu_percent);
    const hostCpuIdlePercent = safeNumber(host.cpu_idle_percent);
    const logicalCpuCount = safeNumber(host.logical_cpu_count);
    const hostMemoryUsed = safeNumber(host.memory_used_bytes);
    const hostMemoryTotal = safeNumber(host.memory_total_bytes);
    const hostMemoryAvailable = safeNumber(host.memory_available_bytes);
    setSummary('alpha-cpu', alphaCpuPercent === null || alphaCpuHostPercent === null
        ? '暂不可用'
        : `${formatNumber(alphaCpuPercent / 100, 2)} 核等价 · 整机 ${formatNumber(alphaCpuHostPercent, 1)}%`);
    setSummary('host-cpu', hostCpuPercent === null || hostCpuIdlePercent === null || logicalCpuCount === null
        ? '暂不可用'
        : `用量 ${formatNumber(hostCpuPercent, 1)}% · 空闲约 ${formatNumber(hostCpuIdlePercent, 1)}% · ${formatNumber(logicalCpuCount)} 逻辑核`);
    setSummary('alpha-memory', alphaMemoryBytes === null || alphaMemoryHostPercent === null
        ? '暂不可用'
        : `${formatBytes(alphaMemoryBytes)} RSS · 整机 ${formatNumber(alphaMemoryHostPercent, 1)}%`);
    setSummary('host-memory', hostMemoryUsed === null || hostMemoryTotal === null || hostMemoryAvailable === null
        ? '暂不可用'
        : `已用 ${formatBytes(hostMemoryUsed)} / ${formatBytes(hostMemoryTotal)} · 可用 ${formatBytes(hostMemoryAvailable)}`);
    setSummary(
        'disk',
        isFieldUnavailable(latest, 'io_counters')
            ? '当前平台不支持'
            : `${formatRate(values.disk_read_bytes_per_second)} / ${formatRate(values.disk_write_bytes_per_second)}`,
    );
    setSummary(
        'connections',
        isFieldUnavailable(latest, 'network_connection_count')
            ? '当前平台不支持'
            : formatCount(values.network_connection_count),
    );
    setSummary('sampled-at', points.at(-1) ? formatTime(points.at(-1).sampled_at) : '--');
}

function isFieldUnavailable(snapshot, field) {
    return Array.isArray(snapshot?.warnings)
        && snapshot.warnings.some(warning => warning?.code === 'field_unavailable' && warning.field === field);
}

function setSummary(key, value) {
    const element = document.querySelector(`[data-resource-summary="${key}"]`);
    if (element) element.textContent = value;
}

function renderCharts() {
    const cpuElement = document.getElementById('resource-monitor-cpu-chart');
    const memoryElement = document.getElementById('resource-monitor-memory-chart');
    const hostCpuElement = document.getElementById('resource-monitor-host-cpu-chart');
    const hostMemoryElement = document.getElementById('resource-monitor-host-memory-chart');
    if (!cpuElement || !memoryElement || !hostCpuElement || !hostMemoryElement) return;
    if (!window.echarts) {
        renderChartNotice(cpuElement);
        renderChartNotice(memoryElement);
        renderChartNotice(hostCpuElement);
        renderChartNotice(hostMemoryElement);
        return;
    }
    cpuChart = getOrCreateChart(cpuElement, cpuChart);
    memoryChart = getOrCreateChart(memoryElement, memoryChart);
    hostCpuChart = getOrCreateChart(hostCpuElement, hostCpuChart);
    hostMemoryChart = getOrCreateChart(hostMemoryElement, hostMemoryChart);
    const labels = points.map(point => formatTime(point.sampled_at));
    const colors = getChartColors();
    cpuChart?.setOption(chartOption(labels, points.map(point => safeNumber(point.summary?.cpu_percent)), '%', colors.orange));
    memoryChart?.setOption(chartOption(labels, points.map(point => bytesToMiB(point.summary?.memory_bytes)), ' MiB', colors.blue));
    const hostLabels = hostHistoryPoints.map(point => formatHourMinute(point.sampled_at));
    hostCpuChart?.setOption(chartOption(hostLabels, hostHistoryPoints.map(point => safeNumber(point.host?.cpu_percent)), '%', colors.orange));
    hostMemoryChart?.setOption(chartOption(hostLabels, hostHistoryPoints.map(point => bytesToMiB(point.host?.memory_available_bytes)), ' MiB', colors.green));
    resizeResourceCharts();
}

function renderHostHistoryStatus() {
    const status = document.getElementById('resource-monitor-host-history-status');
    if (!status) return;
    status.textContent = hostHistoryFailure
        ? '整机容量历史暂不可用，保留上一份成功曲线。'
        : hostHistoryPoints.length ? `整机容量历史：最近 24 小时，共 ${hostHistoryPoints.length} 个采样点。` : '整机容量历史暂不可用。';
}

function renderChartNotice(element) {
    if (element.firstElementChild?.classList.contains('resource-chart-notice')) return;
    const notice = document.createElement('p');
    notice.className = 'resource-chart-notice';
    notice.textContent = '图表组件尚未加载，数据仍持续采集。';
    element.replaceChildren(notice);
}

function getOrCreateChart(element, existing) {
    if (existing?.getDom?.() === element) return existing;
    existing?.dispose?.();
    element.replaceChildren();
    return window.echarts.getInstanceByDom?.(element) || window.echarts.init(element);
}

function chartOption(labels, data, suffix, color) {
    return {
        animation: false,
        grid: { left: 44, right: 14, top: 16, bottom: 28 },
        xAxis: { type: 'category', data: labels, axisLabel: { fontSize: 10 } },
        yAxis: { type: 'value', axisLabel: { formatter: `{value}${suffix}`, fontSize: 10 } },
        tooltip: { trigger: 'axis' },
        series: [{ type: 'line', data, showSymbol: false, smooth: true, lineStyle: { color, width: 2 }, areaStyle: { color: `${color}22` } }],
    };
}

function renderProcessTable() {
    const body = document.getElementById('resource-monitor-processes');
    if (!body) return;
    const processes = [...processCache.values()].sort(compareProcesses);
    const fragment = document.createDocumentFragment();
    processes.forEach(process => fragment.append(createProcessRow(process)));
    if (!processes.length) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = 9;
        cell.className = 'resource-monitor-empty';
        cell.textContent = processTreeUnavailable
            ? '未发现 Research Workbench 进程'
            : '等待受限进程树采样…';
        row.append(cell);
        fragment.append(row);
    }
    body.replaceChildren(fragment);
}

function compareProcesses(left, right) {
    const value = processSortValue(left, sortKey) - processSortValue(right, sortKey);
    if (value !== 0) return value * sortDirection;
    return left.pid - right.pid;
}

function processSortValue(process, key) {
    if (key === 'memory') return safeNumber(process.memory_bytes) ?? -1;
    if (key === 'disk') {
        return (safeNumber(process.disk_read_bytes_per_second) ?? 0)
            + (safeNumber(process.disk_write_bytes_per_second) ?? 0);
    }
    return safeNumber(process.cpu_percent) ?? -1;
}

function createProcessRow(process) {
    const row = document.createElement('tr');
    row.tabIndex = 0;
    row.dataset.pid = String(process.pid);
    row.classList.toggle('selected', selectedProcessPid === process.pid);
    row.classList.toggle('departed', Boolean(process.departed));
    row.addEventListener('click', () => selectProcess(process.pid));
    row.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault();
            selectProcess(process.pid);
        }
    });
    appendCell(row, process.departed ? `${displayName(process)}（已退出）` : displayName(process));
    appendCell(row, String(process.pid));
    appendCell(row, safeText(process.role, '未知'));
    appendCell(row, process.cpu_percent == null ? '采样中' : `${formatNumber(process.cpu_percent, 1)}%`);
    appendCell(row, formatBytes(process.memory_bytes));
    appendCell(row, `${formatRate(process.disk_read_bytes_per_second)} / ${formatRate(process.disk_write_bytes_per_second)}`);
    appendCell(row, formatCount(process.thread_count));
    appendCell(row, formatCount(process.network_connection_count));
    appendCell(row, process.departed ? '已退出' : safeText(process.status, '未知'));
    return row;
}

function appendCell(row, value) {
    const cell = document.createElement('td');
    cell.textContent = value;
    row.append(cell);
}

function selectProcess(pid) {
    selectedProcessPid = pid;
    renderProcessTable();
    renderDetail();
}

function closeProcessDetail() {
    const returnPid = selectedProcessPid;
    selectedProcessPid = null;
    renderProcessTable();
    renderDetail();
    document.querySelector(`#resource-monitor-processes tr[data-pid="${returnPid}"]`)?.focus();
}

function renderDetail() {
    const detail = document.getElementById('resource-monitor-detail');
    if (!detail) return;
    if (selectedProcessPid === null) {
        detail.classList.add('hidden');
        detail.setAttribute('aria-hidden', 'true');
        return;
    }
    detail.classList.remove('hidden');
    detail.setAttribute('aria-hidden', 'false');
    const header = createDetailHeader();
    const process = processCache.get(selectedProcessPid);
    if (!process) {
        const empty = document.createElement('p');
        empty.className = 'resource-monitor-empty';
        empty.textContent = selectedProcessPid === null
            ? '选择一个进程以查看详情。'
            : `PID ${selectedProcessPid} 已退出；保留最后一次采样信息`;
        detail.replaceChildren(header, empty);
        return;
    }
    const grid = document.createElement('div');
    grid.className = 'resource-detail-grid';
    [
        ['名称', displayName(process)],
        ['PID', process.pid],
        ['命令', safeText(process.command, '--')],
        ['父进程', process.parent_pid ?? '--'],
        ['启动时间', process.create_time == null ? '—' : formatDateTime(process.create_time)],
        ['状态', process.departed ? '已退出' : safeText(process.status, '未知')],
    ].forEach(([label, value]) => grid.append(createDetailItem(label, value)));
    const departureNotice = process.departed ? document.createElement('p') : null;
    if (departureNotice) {
        departureNotice.className = 'resource-departure-notice';
        departureNotice.textContent = `PID ${process.pid} 已退出；保留最后一次采样信息`;
    }
    detail.replaceChildren(header, grid, ...(departureNotice ? [departureNotice] : []), createTrend(process.pid));
}

function createDetailHeader() {
    const header = document.createElement('div');
    header.className = 'resource-detail-header';
    const title = document.createElement('h3');
    title.textContent = '进程详情';
    const close = document.createElement('button');
    close.id = 'resource-monitor-detail-close';
    close.className = 'resource-detail-close';
    close.type = 'button';
    close.setAttribute('aria-label', '关闭进程详情');
    close.textContent = '关闭';
    close.addEventListener('click', closeProcessDetail);
    header.append(title, close);
    return header;
}

function createDetailItem(label, value) {
    const item = document.createElement('div');
    item.className = 'resource-detail-item';
    const labelElement = document.createElement('span');
    labelElement.textContent = label;
    const valueElement = document.createElement('strong');
    valueElement.textContent = String(value);
    item.append(labelElement, valueElement);
    return item;
}

function createTrend(pid) {
    const container = document.createElement('div');
    container.className = 'resource-detail-trend';
    const label = document.createElement('span');
    label.textContent = '最近一分钟 CPU / 内存趋势';
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 180 46');
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', '最近一分钟资源趋势');
    const trend = processTrends.get(pid) || [];
    appendTrendLine(svg, trend.map(item => item.cpu), '#f59e0b');
    appendTrendLine(svg, trend.map(item => bytesToMiB(item.memory)), '#3182ce');
    container.append(label, svg);
    return container;
}

function appendTrendLine(svg, values, color) {
    const numeric = values.filter(value => Number.isFinite(value));
    if (!numeric.length) return;
    const min = Math.min(...numeric);
    const max = Math.max(...numeric);
    const range = max - min || 1;
    const pointsText = values.map((value, index) => {
        const x = values.length < 2 ? 0 : (index / (values.length - 1)) * 180;
        const y = Number.isFinite(value) ? 43 - ((value - min) / range) * 40 : 43;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');
    const line = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    line.setAttribute('fill', 'none');
    line.setAttribute('stroke', color);
    line.setAttribute('stroke-width', '2');
    line.setAttribute('points', pointsText);
    svg.append(line);
}

function bindControls() {
    const section = document.getElementById('section-resource-monitor');
    if (!section) return;
    if (!filterOutsideListenerAttached) {
        document.addEventListener('click', resourceFilterOutsideListener = event => {
            if (openResourceEventFilter === null) return;
            const trigger = section.querySelector(`[data-resource-filter-trigger="${openResourceEventFilter}"]`);
            const menu = section.querySelector(`[data-resource-filter-menu="${openResourceEventFilter}"]`);
            if (!trigger || !menu) {
                closeResourceEventFilters({ restoreFocus: false });
                return;
            }
            if (!trigger.contains(event.target) && !menu.contains(event.target)) {
                closeResourceEventFilters({
                    restoreFocus: !shouldPreserveOutsideClickFocus(event.target),
                });
            }
        });
        filterOutsideListenerAttached = true;
    }
    if (section.dataset.resourceControlsBound === 'true') return;
    section.dataset.resourceControlsBound = 'true';
    section.querySelectorAll('[data-resource-sort]').forEach(button => {
        button.addEventListener('click', () => {
            const nextKey = button.dataset.resourceSort;
            if (!['cpu', 'memory', 'disk'].includes(nextKey)) return;
            if (sortKey !== nextKey) {
                sortKey = nextKey;
                sortDirection = -1;
            } else {
                sortDirection *= -1;
            }
            renderProcessTable();
        });
    });
    section.querySelectorAll('[data-resource-filter-trigger]').forEach(trigger => {
        trigger.addEventListener('click', () => toggleResourceEventFilter(trigger.dataset.resourceFilterTrigger));
    });
}

function resourceEventFilters() {
    return {
        status: ['all', 'open', 'acknowledged', 'resolved'].includes(resourceEventFilterState.status)
            ? resourceEventFilterState.status : 'all',
        severity: ['critical', 'warning', 'info'].includes(resourceEventFilterState.severity)
            ? resourceEventFilterState.severity : '',
    };
}

function toggleResourceEventFilter(kind) {
    if (!Object.hasOwn(RESOURCE_EVENT_FILTERS, kind)) return;
    if (openResourceEventFilter === kind) {
        closeResourceEventFilters({ restoreFocus: false });
        return;
    }
    openResourceEventFilter = kind;
    renderResourceEventFilters();
}

function closeResourceEventFilters({ restoreFocus = true } = {}) {
    if (openResourceEventFilter === null) return;
    const previousKind = openResourceEventFilter;
    clearResourceEventFilterFocusFrame();
    openResourceEventFilter = null;
    renderResourceEventFilters();
    if (restoreFocus) focusResourceEventFilterTrigger(previousKind);
}

function renderResourceEventFilters() {
    const section = document.getElementById('section-resource-monitor');
    if (!section) return;
    Object.entries(RESOURCE_EVENT_FILTERS).forEach(([kind, options]) => {
        const trigger = section.querySelector(`[data-resource-filter-trigger="${kind}"]`);
        const menu = section.querySelector(`[data-resource-filter-menu="${kind}"]`);
        const label = section.querySelector(`[data-resource-filter-label="${kind}"]`);
        if (!trigger || !menu || !label) return;
        const value = resourceEventFilterState[kind];
        const selected = options.find(([optionValue]) => optionValue === value) || options[0];
        const isOpen = openResourceEventFilter === kind;
        label.textContent = selected[1];
        trigger.setAttribute('aria-expanded', String(isOpen));
        trigger.classList.toggle('is-open', isOpen);
        menu.hidden = !isOpen;
        if (menu.dataset.resourceFilterKeysBound !== 'true') {
            menu.addEventListener('keydown', event => handleResourceEventFilterKeydown(event));
            menu.dataset.resourceFilterKeysBound = 'true';
        }

        const fragment = document.createDocumentFragment();
        options.forEach(([optionValue, optionLabel]) => {
            const option = document.createElement('button');
            const isSelected = optionValue === value;
            option.type = 'button';
            option.className = 'resource-filter-option';
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', String(isSelected));
            option.textContent = optionLabel;
            if (isSelected) {
                const check = document.createElement('i');
                check.className = 'codicon codicon-check';
                check.setAttribute('aria-hidden', 'true');
                option.append(check);
            }
            option.addEventListener('click', () => {
                resourceEventFilterState[kind] = optionValue;
                renderResourceEventFilters();
                pollResourceEvents();
                closeResourceEventFilters();
            });
            fragment.append(option);
        });
        menu.replaceChildren(fragment);
    });
    if (openResourceEventFilter !== null) focusOpenResourceEventFilterOption(openResourceEventFilter);
}

function focusOpenResourceEventFilterOption(kind) {
    clearResourceEventFilterFocusFrame();
    const menu = document.querySelector(`[data-resource-filter-menu="${kind}"]`);
    const option = menu?.querySelector('[aria-selected="true"]') || menu?.querySelector('[role="option"]');
    const trigger = document.querySelector(`[data-resource-filter-trigger="${kind}"]`);
    if (!menu || !option || !trigger) return;
    resourceFilterFocusFrame = requestAnimationFrame(() => {
        resourceFilterFocusFrame = null;
        if (
            openResourceEventFilter !== kind
            || !isVisibleResourceElement(menu)
            || !isVisibleResourceElement(option)
            || !isVisibleResourceElement(trigger)
        ) return;
        option.focus();
    });
}

function focusResourceEventFilterTrigger(kind) {
    clearResourceEventFilterFocusFrame();
    const trigger = document.querySelector(`[data-resource-filter-trigger="${kind}"]`);
    if (!trigger) return;
    resourceFilterFocusFrame = requestAnimationFrame(() => {
        resourceFilterFocusFrame = null;
        if (!isVisibleResourceElement(trigger)) return;
        trigger.focus();
    });
}

function shouldPreserveOutsideClickFocus(target) {
    return target instanceof Element
        && target.closest('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])') !== null;
}

function handleResourceEventFilterKeydown(event) {
    const menu = event.currentTarget;
    const options = [...menu.querySelectorAll('[role="option"]')];
    if (!options.length) return;
    const focusedIndex = Math.max(0, options.indexOf(document.activeElement));
    let nextIndex = null;
    if (event.key === 'ArrowDown') nextIndex = (focusedIndex + 1) % options.length;
    if (event.key === 'ArrowUp') nextIndex = (focusedIndex - 1 + options.length) % options.length;
    if (event.key === 'Home') nextIndex = 0;
    if (event.key === 'End') nextIndex = options.length - 1;
    if (nextIndex !== null) {
        event.preventDefault();
        options[nextIndex].focus();
        return;
    }
    if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        options[focusedIndex].click();
    }
}

function clearResourceEventFilterFocusFrame() {
    if (resourceFilterFocusFrame === null) return;
    cancelAnimationFrame(resourceFilterFocusFrame);
    resourceFilterFocusFrame = null;
}

function isVisibleResourceElement(element) {
    return element.isConnected && !element.hidden && element.getClientRects().length > 0;
}

function normalizeTimestamp(value) {
    const parsed = new Date(value).getTime();
    return Number.isFinite(parsed) ? new Date(parsed).toISOString() : new Date().toISOString();
}

function safePid(value) {
    const numeric = Number(value);
    return Number.isInteger(numeric) && numeric >= 0 ? numeric : null;
}

function safeNumber(value) {
    if (value === null || value === undefined || value === '') return null;
    const numeric = Number(value);
    return Number.isFinite(numeric) ? numeric : null;
}

function safeText(value, fallback) {
    return typeof value === 'string' && value.trim() ? value : fallback;
}

function displayName(process) {
    return safeText(process.name, '未知进程');
}

function formatNumber(value, fractionDigits = 0) {
    const numeric = safeNumber(value);
    return numeric === null ? '--' : numeric.toLocaleString('zh-CN', { maximumFractionDigits: fractionDigits });
}

function formatCount(value) {
    return safeNumber(value) === null ? '--' : formatNumber(value);
}

function formatBytes(value) {
    const numeric = safeNumber(value);
    if (numeric === null) return '--';
    if (numeric < 1024) return `${formatNumber(numeric)} B`;
    if (numeric < 1024 ** 2) return `${formatNumber(numeric / 1024, 1)} KiB`;
    if (numeric < 1024 ** 3) return `${formatNumber(numeric / 1024 ** 2, 1)} MiB`;
    return `${formatNumber(numeric / 1024 ** 3, 2)} GiB`;
}

function formatRate(value) {
    const formatted = formatBytes(value);
    return formatted === '--' ? formatted : `${formatted}/s`;
}

function bytesToMiB(value) {
    const numeric = safeNumber(value);
    return numeric === null ? null : Number((numeric / 1024 ** 2).toFixed(2));
}

function formatTime(value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '--';
}

function formatHourMinute(value) {
    const date = new Date(value);
    return Number.isFinite(date.getTime())
        ? date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
        : '--';
}

function formatDateTime(value) {
    const date = new Date(Number(value) * 1000);
    return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN') : '--';
}
