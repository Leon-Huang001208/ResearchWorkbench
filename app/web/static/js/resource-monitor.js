/* ============================================================
   AlphaFoundry — Resource Monitor
   Restricted to the local API process and its child processes.
   ============================================================ */

import { apiCall, getChartColors } from './core.js';

const MAX_POINTS = 150;
const POLL_INTERVAL_MS = 2000;
const BACKOFF_DELAYS = [4000, 6000, 8000, 10000];
const DEPARTED_PROCESS_TTL_MS = 5 * 60 * 1000;
const MAX_DEPARTED_PROCESSES = 50;
const PUBLIC_STATUSES = new Set(['warming_up', 'ok', 'degraded', 'unavailable']);

let isMonitoring = false;
let pollTimer = null;
let snapshotController = null;
let historyController = null;
let failureCount = 0;
let historyVersion = 0;
let snapshotVersion = 0;
let lastFailureAt = null;
let retryDelay = null;
let visibilityListenerAttached = false;
let resizeListenerAttached = false;
let keyboardListenerAttached = false;
let cpuChart = null;
let memoryChart = null;
let points = [];
let selectedProcessPid = null;
let processTreeUnavailable = false;
let sortKey = 'cpu';
let sortDirection = -1;
const processCache = new Map();
const processTrends = new Map();

export function startResourceMonitoring() {
    stopResourceMonitoring();
    isMonitoring = true;
    bindControls();
    attachVisibilityListener();
    attachResizeListener();
    attachKeyboardListener();
    resizeResourceCharts();
    if (!canPoll()) {
        renderStatus('warming_up');
        return;
    }
    loadInitialHistory();
    pollSnapshot();
}

export function stopResourceMonitoring() {
    isMonitoring = false;
    clearPollTimer();
    abortRequests();
    if (visibilityListenerAttached) {
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        visibilityListenerAttached = false;
    }
    if (keyboardListenerAttached) {
        document.removeEventListener('keydown', handleDrawerKeydown);
        keyboardListenerAttached = false;
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

function abortRequests() {
    snapshotController?.abort();
    historyController?.abort();
    snapshotController = null;
    historyController = null;
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
    if (event.key === 'Escape' && selectedProcessPid !== null) closeProcessDetail();
}

function resizeResourceCharts() {
    cpuChart?.resize();
    memoryChart?.resize();
}

function handleVisibilityChange() {
    if (document.hidden) {
        clearPollTimer();
        abortRequests();
        return;
    }
    if (canPoll()) {
        resizeResourceCharts();
        loadInitialHistory();
        pollSnapshot();
    }
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
    renderProcessTable();
    renderDetail();
}

function publicStatus(value) {
    return PUBLIC_STATUSES.has(value) ? value : 'unavailable';
}

function renderStatus(code) {
    const status = document.getElementById('resource-monitor-status');
    if (!status) return;
    status.dataset.status = publicStatus(code);
    if (publicStatus(code) === 'unavailable' && lastFailureAt && retryDelay) {
        status.textContent = `unavailable · 采样暂时不可用，保留上一帧数据 · 失败时间 ${formatTime(lastFailureAt)} · ${Math.ceil(retryDelay / 1000)} 秒后重试`;
        return;
    }
    status.textContent = publicStatus(code);
}

function renderSummary(summary) {
    const values = summary && typeof summary === 'object' ? summary : {};
    setSummary('cpu', values.cpu_percent == null ? '采样中' : `${formatNumber(values.cpu_percent, 1)}%`);
    setSummary('memory', formatBytes(values.memory_bytes));
    setSummary('processes', formatCount(values.process_count));
    setSummary(
        'disk',
        `${formatRate(values.disk_read_bytes_per_second)} / ${formatRate(values.disk_write_bytes_per_second)}`,
    );
    setSummary('connections', formatCount(values.network_connection_count));
    setSummary('sampled-at', points.at(-1) ? formatTime(points.at(-1).sampled_at) : '--');
}

function setSummary(key, value) {
    const element = document.querySelector(`[data-resource-summary="${key}"]`);
    if (element) element.textContent = value;
}

function renderCharts() {
    const cpuElement = document.getElementById('resource-monitor-cpu-chart');
    const memoryElement = document.getElementById('resource-monitor-memory-chart');
    if (!cpuElement || !memoryElement) return;
    if (!window.echarts) {
        renderChartNotice(cpuElement);
        renderChartNotice(memoryElement);
        return;
    }
    cpuChart = getOrCreateChart(cpuElement, cpuChart);
    memoryChart = getOrCreateChart(memoryElement, memoryChart);
    const labels = points.map(point => formatTime(point.sampled_at));
    const colors = getChartColors();
    cpuChart?.setOption(chartOption(labels, points.map(point => safeNumber(point.summary?.cpu_percent)), '%', colors.orange));
    memoryChart?.setOption(chartOption(labels, points.map(point => bytesToMiB(point.summary?.memory_bytes)), ' MiB', colors.blue));
    resizeResourceCharts();
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
            ? '未发现 AlphaFoundry 进程'
            : '等待受限进程树采样…';
        row.append(cell);
        fragment.append(row);
    }
    body.replaceChildren(fragment);
}

function compareProcesses(left, right) {
    const value = processSortValue(right, sortKey) - processSortValue(left, sortKey);
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
    if (!section || section.dataset.resourceControlsBound === 'true') return;
    section.dataset.resourceControlsBound = 'true';
    section.querySelectorAll('[data-resource-sort]').forEach(button => {
        button.addEventListener('click', () => {
            const nextKey = button.dataset.resourceSort;
            if (!['cpu', 'memory', 'disk'].includes(nextKey)) return;
            sortDirection = sortKey === nextKey ? sortDirection * -1 : -1;
            sortKey = nextKey;
            renderProcessTable();
        });
    });
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

function formatDateTime(value) {
    const date = new Date(Number(value) * 1000);
    return Number.isFinite(date.getTime()) ? date.toLocaleString('zh-CN') : '--';
}
