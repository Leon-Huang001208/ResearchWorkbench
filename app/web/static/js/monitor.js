/* ============================================================
   AlphaFoundry — Monitor Module
   Crawl feed polling + Workers status
   ============================================================ */

import { apiCall, esc } from './core.js';

// ─── Live Crawl Feed Polling (分源独立轮询) ─────────────────
const CRAWL_FEED_SOURCES = [
    { id: 'cls', label: '财联社电报', shortLabel: '财联社', limit: 250, tone: 'blue' },
    { id: 'cnstock_flash', label: '中国证券网快讯', shortLabel: '快讯', limit: 250, tone: 'cyan' },
    { id: 'cnstock', label: '中国证券网', shortLabel: '中国证券网', limit: 250, tone: 'cyan' },
    { id: 'zhiqiu_reports', label: '知丘研报', shortLabel: '研报', limit: 250, tone: 'orange' },
    { id: 'zhiqiu_wechat', label: '知丘公众号', shortLabel: '公众号', limit: 250, tone: 'orange' },
    { id: 'zhiqiu_transcript', label: '知丘纪要', shortLabel: '纪要', limit: 250, tone: 'orange' },
];

const crawlFeedStates = {};
const crawlFeedControllers = {};
let activeMonitorSource = 'all';
let activeMonitorItemKey = null;
let activeMonitorDetailTab = 'event';
const MAX_UNIFIED_ITEMS = 250;
const monitorContentRefreshes = new Map();

function getFeedState(sourceType) {
    if (!crawlFeedStates[sourceType]) {
        crawlFeedStates[sourceType] = {
            items: [],
            lastTs: null,
            seenIds: new Set(),
            totalToday: 0,
            lastCrawledAt: null,
        };
    }
    return crawlFeedStates[sourceType];
}

async function loadCrawlFeedForSource(sourceType, initial) {
    if (crawlFeedControllers[sourceType]) {
        crawlFeedControllers[sourceType].abort();
    }
    const controller = new AbortController();
    crawlFeedControllers[sourceType] = controller;

    try {
        const state = getFeedState(sourceType);
        let url = `/api/dashboard/crawl-feed?limit=500&source_type=${encodeURIComponent(sourceType)}`;
        if (!initial && state.lastTs) {
            url += '&since=' + encodeURIComponent(state.lastTs);
        }
        const data = await apiCall('GET', url, null, { signal: controller.signal });
        if (!data || !Array.isArray(data.items)) return;

        const sourceConfig = CRAWL_FEED_SOURCES.find(s => s.id === sourceType);
        state.totalToday = Number(data.total_today || 0);
        state.lastCrawledAt = data.last_crawled_at || state.lastCrawledAt;

        let newCount = 0;

        for (const item of [...data.items].reverse()) {
            const itemKey = feedItemKey(sourceType, item);
            if (state.seenIds.has(itemKey)) continue;
            state.seenIds.add(itemKey);
            newCount++;
            state.items.unshift({
                ...item,
                feed_key: itemKey,
                source_type: sourceType,
                source_label: sourceConfig ? sourceConfig.label : sourceType,
            });
        }

        state.items = state.items
            .sort((a, b) => eventTimestamp(b) - eventTimestamp(a))
            .slice(0, MAX_UNIFIED_ITEMS);

        const list = document.getElementById('feed-list-' + sourceType);
        const countEl = document.getElementById('feed-count-' + sourceType);
        const statusEl = document.getElementById('feed-status-' + sourceType);
        const lastFetchEl = document.getElementById('feed-last-fetch-' + sourceType);

        if (countEl) {
            countEl.textContent = state.totalToday + ' 条';
        }

        if (lastFetchEl && state.lastCrawledAt) {
            lastFetchEl.textContent = formatRelativeTime(state.lastCrawledAt);
        }

        if (list) {
            for (const item of state.items.slice(0, sourceConfig ? sourceConfig.limit : 100).reverse()) {
                if (list.querySelector(`[data-doc-id="${cssEscape(item.feed_key)}"]`)) continue;
                const li = document.createElement('li');
                li.dataset.docId = item.feed_key;
                li.innerHTML = `
                    <span class="feed-title" title="${esc(item.title)}">${esc(item.title || '(无标题)')}</span>
                    <span class="feed-time">${formatEventTime(item.published_at || item.crawled_at)}</span>
                `;
                li.classList.add('feed-new');
                setTimeout(() => li.classList.remove('feed-new'), 3000);
                list.prepend(li);
            }

            while (list.children.length > (sourceConfig ? sourceConfig.limit : 100)) {
                list.removeChild(list.lastChild);
            }

            const empty = list.querySelector('.empty-state');
            if (empty && list.children.length > 1) empty.remove();
        }

        const latest = data.items.reduce((best, item) => {
            const t = item.crawled_at || item.published_at;
            return t && (!best || t > best) ? t : best;
        }, null);
        if (latest) state.lastTs = latest;

        if (statusEl && newCount > 0) {
            statusEl.textContent = '+' + newCount + ' 新';
            statusEl.classList.add('badge-real');
            setTimeout(() => {
                statusEl.textContent = '监听中';
                statusEl.classList.remove('badge-real');
            }, 3000);
        }
        renderMonitorSourceList();
        renderUnifiedMonitorFeed();
        renderMonitorSummary();
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.warn('[CrawlFeed:' + sourceType + '] Poll error:', e);
    } finally {
        if (crawlFeedControllers[sourceType] === controller) {
            delete crawlFeedControllers[sourceType];
        }
    }
}

function initLiveMonitorBoard() {
    bindMonitorDetailTabs();
    renderMonitorSourceList();
    renderUnifiedMonitorFeed();
    renderMonitorSummary();
}

function bindMonitorDetailTabs() {
    document.querySelectorAll('[data-monitor-detail-tab]').forEach(button => {
        if (button.dataset.monitorTabBound === 'true') return;
        button.dataset.monitorTabBound = 'true';
        button.addEventListener('click', handleMonitorDetailTabClick);
    });
    applyMonitorDetailTab();
}

function renderMonitorSourceList() {
    const list = document.getElementById('monitor-source-list');
    if (!list) return;

    const total = totalToday();
    const rows = [
        monitorSourceButton({
            id: 'all',
            label: '全部来源',
            subtitle: '统一事件流',
            count: total,
            active: activeMonitorSource === 'all',
        }),
        ...CRAWL_FEED_SOURCES.map(source => {
            const state = getFeedState(source.id);
            return monitorSourceButton({
                id: source.id,
                label: source.label,
                subtitle: state.lastCrawledAt ? formatRelativeTime(state.lastCrawledAt) : '等待抓取',
                count: sourceTodayCount(state, source),
                active: activeMonitorSource === source.id,
            });
        }),
    ];

    list.innerHTML = rows.join('');
    list.querySelectorAll('[data-monitor-source]').forEach(button => {
        button.addEventListener('click', handleMonitorSourceClick);
    });
}

function monitorSourceButton({ id, label, subtitle, count, active }) {
    return `
        <button class="monitor-source-row ${active ? 'active' : ''}" type="button" data-monitor-source="${esc(id)}">
            <span class="monitor-status-dot"></span>
            <span class="monitor-source-main"><strong>${esc(label)}</strong><small>${esc(subtitle)}</small></span>
            <span class="monitor-source-count">${esc(String(count || 0))}</span>
        </button>
    `;
}

function handleMonitorSourceClick(event) {
    const source = event.currentTarget.dataset.monitorSource || 'all';
    activeMonitorSource = source;
    activeMonitorItemKey = null;
    renderMonitorSourceList();
    renderUnifiedMonitorFeed();
    renderMonitorSummary();
}

function handleMonitorDetailTabClick(event) {
    activeMonitorDetailTab = event.currentTarget.dataset.monitorDetailTab || 'event';
    applyMonitorDetailTab();
}

function applyMonitorDetailTab() {
    document.querySelectorAll('[data-monitor-detail-tab]').forEach(button => {
        button.classList.toggle('active', button.dataset.monitorDetailTab === activeMonitorDetailTab);
    });
    document.querySelectorAll('.monitor-detail-view').forEach(view => {
        const viewName = view.id === 'monitor-system-detail' ? 'system' : 'event';
        view.classList.toggle('hidden', viewName !== activeMonitorDetailTab);
    });
}

function renderUnifiedMonitorFeed() {
    const list = document.getElementById('monitor-feed-list');
    if (!list) return;

    const items = monitorItemsForActiveSource();
    const title = document.getElementById('monitor-feed-title');
    if (title) title.textContent = activeSourceLabel();

    if (!items.length) {
        list.innerHTML = '<div class="empty-state">等待抓取数据...</div>';
        renderMonitorEventDetail(null);
        return;
    }

    if (!activeMonitorItemKey || !items.some(item => item.feed_key === activeMonitorItemKey)) {
        activeMonitorItemKey = items[0].feed_key;
    }

    list.innerHTML = items.slice(0, MAX_UNIFIED_ITEMS).map(item => {
        const sourceConfig = CRAWL_FEED_SOURCES.find(sourceItem => sourceItem.id === item.source_type);
        const tone = sourceConfig ? sourceConfig.tone : 'blue';
        const sourceLabel = sourceConfig ? sourceConfig.label : item.source_type;
        const sourceLabelMarkup = activeMonitorSource === 'all'
            ? `<span>${esc(sourceLabel)}</span>`
            : '';
        const displayTitle = cleanMonitorDisplayTitle(item.title || '');
        const isSelected = item.feed_key === activeMonitorItemKey;
        return `
            <article class="monitor-event-item ${isSelected ? 'selected' : ''}" data-monitor-item-key="${esc(item.feed_key)}">
                <span class="monitor-event-accent ${esc(tone)}"></span>
                <div class="monitor-event-main">
                    <strong title="${esc(item.title || '')}">${esc(displayTitle || item.title || '(无标题)')}</strong>
                    ${sourceLabelMarkup}
                </div>
                <time class="monitor-event-time">${esc(formatEventTime(item.published_at || item.crawled_at))}</time>
            </article>
        `;
    }).join('');
    list.querySelectorAll('[data-monitor-item-key]').forEach(item => {
        item.addEventListener('click', handleMonitorEventClick);
    });
    renderMonitorEventDetail(items.find(item => item.feed_key === activeMonitorItemKey) || items[0]);
}

function handleMonitorEventClick(event) {
    activeMonitorItemKey = event.currentTarget.dataset.monitorItemKey || null;
    activeMonitorDetailTab = 'event';
    renderUnifiedMonitorFeed();
    applyMonitorDetailTab();
}

function renderMonitorEventDetail(item) {
    const title = document.getElementById('monitor-detail-title');
    const content = document.getElementById('monitor-detail-content');

    if (!item) {
        setText('monitor-detail-title', '选择一条事件查看详情');
        setText('monitor-detail-content', '中间列表只保留标题，完整内容会在这里展开。');
        return;
    }

    if (title) title.textContent = item.title || '(无标题)';
    if (content) {
        const refreshState = monitorContentRefreshes.get(item.doc_id || item.feed_key);
        if (refreshState === 'loading') {
            content.textContent = '正在获取正文...';
        } else {
            content.textContent = eventDetailText(item);
        }
    }
    refreshMonitorEventContent(item);
}

function shouldRefreshMonitorContent(item) {
    if (!item || !item.doc_id) return false;
    if (!['cnstock', 'cnstock_flash'].includes(item.source_type)) return false;
    if (eventHasReadableContent(item)) return false;
    const state = monitorContentRefreshes.get(item.doc_id);
    return state !== 'loading' && state !== 'done';
}

async function refreshMonitorEventContent(item) {
    if (!shouldRefreshMonitorContent(item)) return;

    const docId = item.doc_id;
    monitorContentRefreshes.set(docId, 'loading');
    setText('monitor-detail-content', '正在获取正文...');

    try {
        const data = await apiCall(
            'POST',
            `/api/dashboard/crawl-feed/${encodeURIComponent(item.doc_id)}/content`,
            null,
            { method: 'POST' }
        );

        if (data && data.success) {
            applyMonitorContentRefresh(item, data);
            monitorContentRefreshes.set(docId, 'done');
        } else {
            monitorContentRefreshes.set(docId, 'failed');
            if (activeMonitorItemKey === item.feed_key) {
                setText('monitor-detail-content', data && data.message ? data.message : eventDetailText(item));
            }
        }
    } catch (error) {
        console.warn('[CrawlFeed] Failed to refresh event content:', error);
        monitorContentRefreshes.set(docId, 'failed');
        if (activeMonitorItemKey === item.feed_key) {
            setText('monitor-detail-content', '正文获取失败，稍后可再次点击重试。');
        }
    }
}

function applyMonitorContentRefresh(item, data) {
    const patch = {
        content: data.content || item.content || '',
        summary: data.summary || item.summary || '',
        has_content: Boolean(data.has_content),
        source_name: data.source_name || item.source_name || '',
    };
    CRAWL_FEED_SOURCES.forEach(source => {
        const state = getFeedState(source.id);
        state.items = state.items.map(existing => (
            existing.doc_id === item.doc_id ? { ...existing, ...patch } : existing
        ));
    });
    Object.assign(item, patch);
    if (activeMonitorItemKey === item.feed_key) {
        setText('monitor-detail-content', eventDetailText(item));
    }
}

function monitorItemsForActiveSource() {
    const items = activeMonitorSource === 'all'
        ? CRAWL_FEED_SOURCES.flatMap(source => getFeedState(source.id).items)
        : getFeedState(activeMonitorSource).items;
    const sorted = items
        .slice()
        .sort((a, b) => eventTimestamp(b) - eventTimestamp(a));
    return activeMonitorSource === 'all' ? sorted.slice(0, MAX_UNIFIED_ITEMS) : sorted;
}

function activeSourceLabel() {
    const source = CRAWL_FEED_SOURCES.find(item => item.id === activeMonitorSource);
    return activeMonitorSource === 'all' ? '全部来源' : (source ? source.label : activeMonitorSource);
}

function cleanMonitorDisplayTitle(title) {
    return String(title || '')
        .replace(/\\.pdf$/i, '')
        .replace(/[_＿]+/g, '：')
        .replace(/[\\s\\-—_：:]*\\d{8}$/g, '')
        .replace(/[\\s\\-—_：:]*\\d{6}$/g, '')
        .replace(/\\s+/g, ' ')
        .replace(/：{2,}/g, '：')
        .replace(/\\s*：\\s*/g, '：')
        .trim();
}

function feedItemKey(sourceType, item) {
    return [
        sourceType,
        item.doc_id || item.id || item.url || item.link || '',
        item.published_at || item.crawled_at || '',
        item.title || '',
    ].join('|');
}

function renderMonitorSummary() {
    setText('monitor-summary-sources', `${onlineSourceCount()} / ${CRAWL_FEED_SOURCES.length}`);
    setText('monitor-summary-total', String(totalToday()));

    const latest = latestCrawledAt('all');
    const latestSource = latestSourceLabel();
    setText('monitor-summary-last', latest ? formatRelativeTime(latest) : '--');
    setText('monitor-summary-last-source', latestSource || '等待数据');
}

function setText(id, text) {
    const element = document.getElementById(id);
    if (element) element.textContent = text;
}

function onlineSourceCount() {
    return CRAWL_FEED_SOURCES.filter(source => {
        const state = getFeedState(source.id);
        return state.lastCrawledAt || state.items.length || state.totalToday;
    }).length;
}

function totalToday() {
    return CRAWL_FEED_SOURCES.reduce((sum, source) => sum + Number(getFeedState(source.id).totalToday || 0), 0);
}

function sourceTodayCount(state, source) {
    if (Number.isFinite(state.totalToday)) return state.totalToday;
    return Math.min(state.items.length, source.limit || state.items.length);
}

function eventDetailText(item) {
    const text = item.content || item.summary || item.description || '';
    const compactText = String(text).replace(/\s+/g, ' ').trim();
    const compactTitle = String(item.title || '').replace(/\s+/g, ' ').trim();
    const compactRawTitle = String(item.raw_title || '').replace(/\s+/g, ' ').trim();
    if (!compactText || compactText === compactTitle || compactText === compactRawTitle) {
        return '当前来源暂未获取到独立正文，只能展示标题。';
    }
    return text;
}

function eventHasReadableContent(item) {
    const text = item.content || item.summary || item.description || '';
    const compactText = String(text).replace(/\s+/g, ' ').trim();
    const compactTitle = String(item.title || '').replace(/\s+/g, ' ').trim();
    const compactRawTitle = String(item.raw_title || '').replace(/\s+/g, ' ').trim();
    return Boolean(compactText && compactText !== compactTitle && compactText !== compactRawTitle);
}

function latestCrawledAt(sourceId) {
    const states = sourceId === 'all'
        ? CRAWL_FEED_SOURCES.map(source => getFeedState(source.id))
        : [getFeedState(sourceId)];
    const sorted = states
        .map(state => state.lastCrawledAt)
        .filter(Boolean)
        .sort();
    return sorted.length ? sorted[sorted.length - 1] : null;
}

function latestSourceLabel() {
    let latest = null;
    let label = '';
    CRAWL_FEED_SOURCES.forEach(source => {
        const state = getFeedState(source.id);
        if (state.lastCrawledAt && (!latest || state.lastCrawledAt > latest)) {
            latest = state.lastCrawledAt;
            label = source.label;
        }
    });
    return label;
}

function eventTimestamp(item) {
    const value = item.crawled_at || item.published_at;
    const date = value ? new Date(value) : new Date(0);
    return Number.isNaN(date.getTime()) ? 0 : date.getTime();
}

function formatEventTime(value) {
    if (!value) return '';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    const time = date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    if (date.toDateString() === new Date().toDateString()) return time;
    return `${date.toLocaleDateString()} ${time}`;
}

function formatRelativeTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';
    const diffMs = Date.now() - date.getTime();
    const diffMin = Math.max(0, Math.floor(diffMs / 60000));
    const diffHour = Math.floor(diffMs / 3600000);
    const diffDay = Math.floor(diffMs / 86400000);
    if (diffMin < 1) return '刚刚';
    if (diffMin < 60) return `${diffMin} 分钟前`;
    if (diffHour < 24 && date.toDateString() === new Date().toDateString()) {
        return `今天 ${date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}`;
    }
    if (diffDay < 2) return `${diffHour} 小时前`;
    return `${diffDay} 天前`;
}

function cssEscape(value) {
    if (typeof window !== 'undefined' && window.CSS && typeof window.CSS.escape === 'function') {
        return window.CSS.escape(String(value));
    }
    return String(value).replace(/"/g, '\\"');
}

const crawlFeedIntervals = {};

async function triggerCrawlAllSources() {
    for (const { id } of CRAWL_FEED_SOURCES) {
        try {
            const resp = await fetch('/api/scheduler/trigger/' + encodeURIComponent(id), { method: 'POST' });
            const result = await resp.json();
            if (result.success) {
                console.log('[CrawlFeed] Triggered crawl for', id, ':', result.result.success_count, 'new');
            }
        } catch (e) {
            console.warn('[CrawlFeed] Failed to trigger crawl for', id, ':', e);
        }
    }
}

function startCrawlFeedPolling() {
    initLiveMonitorBoard();
    CRAWL_FEED_SOURCES.forEach(({ id }) => {
        if (crawlFeedIntervals[id]) return;
        loadCrawlFeedForSource(id, true);
        crawlFeedIntervals[id] = setInterval(() => loadCrawlFeedForSource(id, false), 5000);
    });
    console.log('[CrawlFeed] Per-source polling started (5s interval)');
}

function stopCrawlFeedPolling() {
    Object.keys(crawlFeedIntervals).forEach(id => {
        clearInterval(crawlFeedIntervals[id]);
        delete crawlFeedIntervals[id];
    });
    Object.keys(crawlFeedControllers).forEach(id => {
        crawlFeedControllers[id].abort();
        delete crawlFeedControllers[id];
    });
}

// ─── Workers Status ─────────────────────────────────────────
let _workersPollTimer = null;
let _workersStatusController = null;

function startWorkersPolling() {
    stopWorkersPolling();
    loadWorkersStatus();
    _workersPollTimer = setInterval(loadWorkersStatus, 15000);
}

function stopWorkersPolling() {
    if (_workersPollTimer) {
        clearInterval(_workersPollTimer);
        _workersPollTimer = null;
    }
    if (_workersStatusController) {
        _workersStatusController.abort();
        _workersStatusController = null;
    }
}

async function loadWorkersStatus() {
    if (_workersStatusController) {
        _workersStatusController.abort();
    }
    const controller = new AbortController();
    _workersStatusController = controller;

    try {
        const data = await apiCall('GET', '/api/system/workers/status', null, {
            signal: controller.signal,
        });
        renderWorkersPanel(data);
    } catch (e) {
        if (e.name === 'AbortError') return;
        console.error('Failed to load workers status:', e);
    } finally {
        if (_workersStatusController === controller) {
            _workersStatusController = null;
        }
    }
}

function renderWorkersPanel(data) {
    const panel = document.getElementById('workers-panel');
    const queueEl = document.getElementById('workers-queue-stats');

    updateMonitorWorkerSummary(data);

    let html = '';

    // Knowledge workers
    if (data.workers && data.workers.length) {
        data.workers.forEach(function(w) {
            const statusClass = w.alive ? 'worker-alive' : 'worker-dead';
            const statusText = w.alive ? '运行中' : '已停止';
            const pidText = w.pid ? 'PID ' + w.pid : '—';
            const activityText = w.activity || (w.alive ? '—' : '—');

            html += '<div class="worker-row">';
            html += '<span class="worker-dot ' + statusClass + '" title="' + statusText + '"></span>';
            html += '<span class="worker-name">' + esc(w.name) + '</span>';
            html += '<span class="worker-type badge badge-outline">知识加工</span>';
            html += '<span class="worker-pid text-muted">' + pidText + '</span>';
            html += '<span class="worker-activity text-muted">' + esc(activityText) + '</span>';
            html += '</div>';
        });
    } else {
        html += '<div class="empty-state">无知识加工 Worker</div>';
    }

    // Scheduler
    if (data.scheduler) {
        var s = data.scheduler;
        var sStatusClass = s.alive ? 'worker-alive' : 'worker-dead';
        var sStatusText = s.alive ? '运行中' : '已停止';
        var sPidText = s.pid ? 'PID ' + s.pid : '—';
        var sActivityText = s.activity || '—';

        html += '<div class="worker-row">';
        html += '<span class="worker-dot ' + sStatusClass + '" title="' + sStatusText + '"></span>';
        html += '<span class="worker-name">' + esc(s.name) + '</span>';
        html += '<span class="worker-type badge badge-outline">调度</span>';
        html += '<span class="worker-pid text-muted">' + sPidText + '</span>';
        html += '<span class="worker-activity text-muted">' + esc(sActivityText) + '</span>';
        html += '</div>';
    }

    panel.innerHTML = html;

    // Queue stats (4-color cards)
    if (queueEl && data.queue_stats) {
        var qs = data.queue_stats;
        queueEl.innerHTML =
            '<span class="queue-stat monitor-health-card"><span class="queue-stat-label">待处理</span><span class="queue-stat-value">' + (qs.pending || 0) + '</span></span>' +
            '<span class="queue-stat monitor-health-card"><span class="queue-stat-label">处理中</span><span class="queue-stat-value queue-processing">' + (qs.processing || 0) + '</span></span>' +
            '<span class="queue-stat monitor-health-card"><span class="queue-stat-label">已完成</span><span class="queue-stat-value queue-completed">' + (qs.completed || 0) + '</span></span>' +
            '<span class="queue-stat monitor-health-card"><span class="queue-stat-label">失败</span><span class="queue-stat-value queue-failed">' + (qs.failed || 0) + '</span></span>';
    }

    // Processing stats (今日/近7天/近30天/总计 + 趋势对比)
    var procEl = document.getElementById('workers-processing-stats');
    if (procEl && data.processing_stats) {
        var ps = data.processing_stats;

        // 今日 vs 昨日同期环比
        var trendHtml = '';
        if (ps.yesterday_same_time > 0) {
            var delta = ps.today - ps.yesterday_same_time;
            var pct = Math.round((delta / ps.yesterday_same_time) * 100);
            if (pct > 0) {
                trendHtml = '<span class="trend-badge trend-up">+' + pct + '%</span>';
            } else if (pct < 0) {
                trendHtml = '<span class="trend-badge trend-down">' + pct + '%</span>';
            } else {
                trendHtml = '<span class="trend-badge trend-flat">→</span>';
            }
        }

        procEl.innerHTML =
            '<span class="queue-stat monitor-health-card">' +
                '<span class="queue-stat-label">今日' + trendHtml + '</span>' +
                '<span class="queue-stat-value">' + (ps.today || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat monitor-health-card">' +
                '<span class="queue-stat-label">近7天 <span class="proc-avg">日均' + (ps.daily_avg_7d || 0).toFixed(0) + '</span></span>' +
                '<span class="queue-stat-value">' + (ps.last_7_days || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat monitor-health-card">' +
                '<span class="queue-stat-label">近30天</span>' +
                '<span class="queue-stat-value">' + (ps.last_30_days || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat monitor-health-card">' +
                '<span class="queue-stat-label">总计</span>' +
                '<span class="queue-stat-value queue-completed">' + (ps.total || 0) + '</span>' +
            '</span>';
    }
}

function updateMonitorWorkerSummary(data) {
    const aliveWorkers = Array.isArray(data.workers)
        ? data.workers.filter(worker => worker.alive).length
        : 0;
    const totalWorkers = Array.isArray(data.workers) ? data.workers.length : 0;
    const schedulerAlive = data.scheduler && data.scheduler.alive ? 1 : 0;
    const schedulerTotal = data.scheduler ? 1 : 0;
    setText('monitor-summary-workers', `${aliveWorkers + schedulerAlive} / ${totalWorkers + schedulerTotal}`);

    if (data.queue_stats) {
        setText('monitor-summary-failed', String(data.queue_stats.failed || 0));
    }
}

export { startCrawlFeedPolling, stopCrawlFeedPolling, startWorkersPolling, stopWorkersPolling, loadWorkersStatus, renderWorkersPanel, triggerCrawlAllSources };
