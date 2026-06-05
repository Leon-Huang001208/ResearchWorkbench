/* ============================================================
   AlphaFoundry — Monitor Module
   Crawl feed polling + Workers status
   ============================================================ */

import { apiCall, esc } from './core.js';

// ─── Live Crawl Feed Polling (分源独立轮询) ─────────────────
const CRAWL_FEED_SOURCES = [
    { id: 'cls', label: 'CLS', limit: 200 },
    { id: 'cninfo', label: '巨潮公告', limit: 200 },
    { id: 'cnstock', label: 'CNSTOCK', limit: 200 },
    { id: 'cnstock_flash', label: '快讯', limit: 200 },
    { id: 'zhiqiu_reports', label: 'ZQ研报', limit: 200 },
    { id: 'zhiqiu_wechat', label: 'ZQ公众号', limit: 200 },
    { id: 'zhiqiu_transcript', label: 'ZQ纪要', limit: 200 },
];

const crawlFeedStates = {};

function getFeedState(sourceType) {
    if (!crawlFeedStates[sourceType]) {
        crawlFeedStates[sourceType] = { lastTs: null, seenIds: new Set() };
    }
    return crawlFeedStates[sourceType];
}

async function loadCrawlFeedForSource(sourceType, initial) {
    try {
        const state = getFeedState(sourceType);
        let url = `/api/dashboard/crawl-feed?limit=500&source_type=${encodeURIComponent(sourceType)}`;
        if (!initial && state.lastTs) {
            url += '&since=' + encodeURIComponent(state.lastTs);
        }
        const data = await apiCall('GET', url);
        if (!data || !Array.isArray(data.items)) return;

        const list = document.getElementById('feed-list-' + sourceType);
        const countEl = document.getElementById('feed-count-' + sourceType);
        const statusEl = document.getElementById('feed-status-' + sourceType);
        if (!list) return;

        if (countEl && data.total_today !== undefined) {
            countEl.textContent = data.total_today + ' 条';
        }

        // 更新最后获取时间
        const lastFetchEl = document.getElementById('feed-last-fetch-' + sourceType);
        if (lastFetchEl && data.last_crawled_at) {
            const d = new Date(data.last_crawled_at);
            const now = new Date();
            const diffMs = now - d;
            const diffMin = Math.floor(diffMs / 60000);
            const diffHour = Math.floor(diffMs / 3600000);
            const diffDay = Math.floor(diffMs / 86400000);
            if (diffMin < 1) {
                lastFetchEl.textContent = '刚刚抓取';
            } else if (diffMin < 60) {
                lastFetchEl.textContent = diffMin + ' 分钟前';
            } else if (diffHour < 24 && d.toDateString() === now.toDateString()) {
                lastFetchEl.textContent = '今天 ' + d.toLocaleTimeString();
            } else if (diffDay < 2) {
                lastFetchEl.textContent = diffHour + ' 小时前';
            } else {
                lastFetchEl.textContent = diffDay + ' 天前';
            }
        }

        let newCount = 0;

        for (const item of [...data.items].reverse()) {
            if (state.seenIds.has(item.doc_id)) continue;
            state.seenIds.add(item.doc_id);
            newCount++;

            const li = document.createElement('li');
            const timeStr = item.published_at || item.crawled_at;
            let time = '';
            if (timeStr) {
                const d = new Date(timeStr);
                const now = new Date();
                const isToday = d.toDateString() === now.toDateString();
                time = isToday ? d.toLocaleTimeString() : d.toLocaleString();
            }
            li.innerHTML = `
                <span class="feed-title" title="${esc(item.title)}">${esc(item.title || '(无标题)')}</span>
                <span class="feed-time">${time}</span>
            `;
            li.classList.add('feed-new');
            setTimeout(() => li.classList.remove('feed-new'), 3000);
            list.prepend(li);
        }

        const srcConfig = CRAWL_FEED_SOURCES.find(s => s.id === sourceType);
        const maxItems = srcConfig ? srcConfig.limit : 100;
        while (list.children.length > maxItems) {
            list.removeChild(list.lastChild);
        }

        const empty = list.querySelector('.empty-state');
        if (empty && list.children.length > 1) empty.remove();

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
    } catch (e) {
        console.warn('[CrawlFeed:' + sourceType + '] Poll error:', e);
    }
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
}

// ─── Workers Status ─────────────────────────────────────────
let _workersPollTimer = null;

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
}

async function loadWorkersStatus() {
    try {
        const data = await apiCall('GET', '/api/system/workers/status');
        renderWorkersPanel(data);
    } catch (e) {
        console.error('Failed to load workers status:', e);
    }
}

function renderWorkersPanel(data) {
    const panel = document.getElementById('workers-panel');
    const queueEl = document.getElementById('workers-queue-stats');
    const lastUpdated = document.getElementById('workers-last-updated');

    if (lastUpdated) {
        lastUpdated.textContent = new Date().toLocaleTimeString();
    }

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
            '<span class="queue-stat"><span class="queue-stat-label">待处理</span><span class="queue-stat-value">' + (qs.pending || 0) + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">处理中</span><span class="queue-stat-value queue-processing">' + (qs.processing || 0) + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">已完成</span><span class="queue-stat-value queue-completed">' + (qs.completed || 0) + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">失败</span><span class="queue-stat-value queue-failed">' + (qs.failed || 0) + '</span></span>';
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
            '<span class="queue-stat">' +
                '<span class="queue-stat-label">今日' + trendHtml + '</span>' +
                '<span class="queue-stat-value">' + (ps.today || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat">' +
                '<span class="queue-stat-label">近7天 <span class="proc-avg">日均' + (ps.daily_avg_7d || 0).toFixed(0) + '</span></span>' +
                '<span class="queue-stat-value">' + (ps.last_7_days || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat">' +
                '<span class="queue-stat-label">近30天</span>' +
                '<span class="queue-stat-value">' + (ps.last_30_days || 0) + '</span>' +
            '</span>' +
            '<span class="queue-stat">' +
                '<span class="queue-stat-label">总计</span>' +
                '<span class="queue-stat-value queue-completed">' + (ps.total || 0) + '</span>' +
            '</span>';
    }
}

export { startCrawlFeedPolling, stopCrawlFeedPolling, startWorkersPolling, stopWorkersPolling, loadWorkersStatus, renderWorkersPanel, triggerCrawlAllSources };
