/* ============================================================
   AlphaFoundry — Dashboard Module
   Market Overview + Live Monitor tabs
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

const MARKET_SECTOR_SILENT_REFRESH_MS = 60000;
const DEFAULT_MARKET_SECTOR_VIEW = 'wind_hot_concept';
const MARKET_SECTOR_STATUS_PASSTHROUGH = new Set([
    'workbook_missing',
    'workbook_not_open',
    'snapshot_invalid',
    'snapshot_empty',
    'snapshot_stale',
    'formula_error',
    'workbook_read_error',
    'xlwings_unavailable',
]);

let activeMarketSectorView = DEFAULT_MARKET_SECTOR_VIEW;
let marketSectorRefreshTimer = null;
let marketSectorRequestSeq = 0;
let dashboardRequestSeq = 0;

// ─── Dashboard Loading ──────────────────────────────────────
export async function loadDashboard() {
    const marketPanel = document.getElementById('dash-panel-market');
    const requestSeq = dashboardRequestSeq + 1;
    dashboardRequestSeq = requestSeq;

    try {
        showSectionLoading(marketPanel);

        const data = await apiCall('GET', '/api/dashboard');
        if (requestSeq !== dashboardRequestSeq) return;

        // Update data source badge
        updateDataSourceBadge(data);

        // Render Market Overview
        renderMarketOverview(data);

        // Refresh i18n
        if (typeof I18N !== 'undefined') I18N.applyAll();
    } catch (e) {
        if (requestSeq !== dashboardRequestSeq) return;
        console.error('Failed to load dashboard:', e);
        showSectionError(marketPanel, e.message);
        toast('仪表盘加载失败', 'error');
    }
}

// ─── Data Source Badge ──────────────────────────────────────
function updateDataSourceBadge(data) {
    const overview = data.market_overview || {};
    setSourceBadge(
        document.getElementById('data-source-news-badge'),
        '新闻',
        Boolean(overview.uses_real_news)
    );
    setSourceBadge(
        document.getElementById('data-source-sectors-badge'),
        '板块',
        Boolean(overview.uses_real_sectors)
    );
}

function setSourceBadge(badge, label, isReal) {
    if (!badge) return;
    badge.textContent = `${label}${isReal ? '真实' : '模拟'}`;
    badge.classList.toggle('badge-real', isReal);
    badge.classList.toggle('badge-mock', !isReal);
}

// ─── Market Overview Tab ────────────────────────────────────
function renderMarketOverview(data) {
    const mo = data.market_overview;

    // Global News
    const newsEl = document.getElementById('market-global-news');
    if (newsEl) {
        const scrollPos = newsEl.scrollTop;
        if (mo.global_news.length) {
            newsEl.innerHTML = mo.global_news.map((n, idx) => `
                <li class="news-item ${n.is_mock ? 'mock-data-item' : ''}">
                    <div class="news-header">
                        <span class="news-rank">#${idx + 1}</span>
                        <span class="news-title-inline">${esc(n.title)}</span>
                        ${n.is_mock ? '<span class="badge badge-mock">模拟</span>' : ''}
                    </div>
                    <div class="news-summary">${esc(n.summary)}</div>
                    <div class="news-meta">
                        <span class="news-source-tag">${esc(n.source)}</span>
                        <span class="news-time">${new Date(n.published_at).toLocaleString()}</span>
                        ${n.related_symbols && n.related_symbols.length ? `<span class="news-symbols">${n.related_symbols.map(s => esc(s)).join(', ')}</span>` : ''}
                    </div>
                </li>
            `).join('');
        } else {
            newsEl.innerHTML = '<li class="empty-state">暂无新闻</li>';
        }
        newsEl.scrollTop = scrollPos;
    }

    renderSectorList('market-top-up-sectors', mo.top_up_sectors, 'up');
    renderSectorList('market-top-down-sectors', mo.top_down_sectors, 'down');

    hideSectionLoading(document.getElementById('dash-panel-market'));
    if (!isMarketDashboardTabActive()) {
        stopMarketSectorRefresh();
        return;
    }

    scheduleActiveMarketSectorRefresh();
    ensureMarketSectorViewLoaded(activeMarketSectorView, { silent: true });
}

function renderSectorList(elementId, sectors, direction) {
    const el = document.getElementById(elementId);
    if (!el) return;

    const scrollPos = el.scrollTop;
    if (sectors && sectors.length) {
        el.innerHTML = sectors.map((sector) => renderSectorItem(sector, direction)).join('');
    } else {
        el.innerHTML = '<li class="empty-state">暂无数据</li>';
    }
    el.scrollTop = scrollPos;
}

function renderSectorItem(sector, direction) {
    const isConcept = Boolean(sector.is_concept);
    const changeClass = direction === 'up' ? 'sector-up' : 'sector-down';

    return `
        <li class="sector-item ${sector.is_mock ? 'mock-data-item' : ''}">
            <div class="sector-header">
                <span class="sector-name">${esc(sector.name)}</span>
                <span class="sector-right">
                    <span class="badge ${isConcept ? 'badge-concept' : 'badge-sector'}">${isConcept ? '概念' : '板块'}</span>
                    <span class="sector-change ${changeClass}">${formatSectorChange(sector.change_pct, direction)}</span>
                </span>
            </div>
        </li>
    `;
}

function formatSectorChange(value, direction) {
    const numericValue = Number(value);
    if (!Number.isFinite(numericValue)) return '--';

    const sign = direction === 'up' && numericValue >= 0 ? '+' : '';
    return `${sign}${numericValue.toFixed(2)}%`;
}

function clearMarketSectorRefreshTimer() {
    if (!marketSectorRefreshTimer) return;
    clearInterval(marketSectorRefreshTimer);
    marketSectorRefreshTimer = null;
}

export function stopMarketSectorRefresh() {
    clearMarketSectorRefreshTimer();
    marketSectorRequestSeq += 1;
}

function scheduleActiveMarketSectorRefresh() {
    clearMarketSectorRefreshTimer();
    marketSectorRefreshTimer = setInterval(() => {
        ensureMarketSectorViewLoaded(activeMarketSectorView, { silent: true });
    }, MARKET_SECTOR_SILENT_REFRESH_MS);
}

async function ensureMarketSectorViewLoaded(viewKey, options = {}) {
    const { silent = false } = options;
    const safeViewKey = viewKey || DEFAULT_MARKET_SECTOR_VIEW;
    const requestSeq = marketSectorRequestSeq + 1;
    marketSectorRequestSeq = requestSeq;
    activeMarketSectorView = safeViewKey;

    try {
        const payload = await apiCall(
            'GET',
            `/api/dashboard/sector-movers?view_key=${encodeURIComponent(safeViewKey)}&limit=10`
        );

        if (requestSeq !== marketSectorRequestSeq || !isMarketDashboardTabActive()) {
            return null;
        }

        renderSectorList('market-top-up-sectors', payload.up, 'up');
        renderSectorList('market-top-down-sectors', payload.down, 'down');
        renderMarketSectorStatus(payload);
        return payload;
    } catch (e) {
        if (requestSeq !== marketSectorRequestSeq) {
            return null;
        }

        renderMarketSectorStatus({
            status: 'workbook_read_error',
            message: '板块数据静默刷新失败，保留上次结果',
        });

        if (silent) {
            console.warn('Silent market sector refresh failed:', e);
            return null;
        }

        console.error('Failed to load market sector view:', e);
        toast('板块数据刷新失败', 'error');
        throw e;
    }
}

function renderMarketSectorStatus(data = {}) {
    const statusEl = document.getElementById('market-sector-status');
    const message = String(data.message || '');
    const status = data.status || '';
    let displayMessage = '';

    if (message.includes('未刷新')) {
        displayMessage = 'Wind 数据可能未刷新';
    } else if (MARKET_SECTOR_STATUS_PASSTHROUGH.has(status) && message) {
        displayMessage = message;
    }

    if (statusEl) {
        statusEl.textContent = displayMessage;
        statusEl.classList.toggle('hidden', !displayMessage);
    }

    return displayMessage;
}

function isMarketDashboardTabActive() {
    return Boolean(document.getElementById('dash-panel-market')?.classList.contains('active'));
}

// ─── Tab Switching ──────────────────────────────────────────
export function switchDashTab(tabName) {
    document.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.dash-tab-panel').forEach(p => p.classList.remove('active'));
    const tabBtn = document.querySelector(`.dash-tab[data-dash-tab="${tabName}"]`);
    const panel = document.getElementById(`dash-panel-${tabName}`);
    if (tabBtn) tabBtn.classList.add('active');
    if (panel) panel.classList.add('active');

    if (tabName === 'market') {
        scheduleActiveMarketSectorRefresh();
        ensureMarketSectorViewLoaded(activeMarketSectorView, { silent: true });
    } else {
        stopMarketSectorRefresh();
    }
}

// ─── Loading / Error helpers ────────────────────────────────
function showSectionLoading(panel) {
    if (!panel) return;
    panel.classList.add('loading');
    const errorEl = panel.querySelector('.section-error');
    if (errorEl) errorEl.classList.add('hidden');
}

function hideSectionLoading(panel) {
    if (!panel) return;
    panel.classList.remove('loading');
}

function showSectionError(panel, message) {
    if (!panel) return;
    panel.classList.remove('loading');
    const errorEl = panel.querySelector('.section-error');
    if (!errorEl) return;
    const msgEl = errorEl.querySelector('.error-msg');
    if (msgEl) msgEl.textContent = message || '加载失败';
    errorEl.classList.remove('hidden');
}
