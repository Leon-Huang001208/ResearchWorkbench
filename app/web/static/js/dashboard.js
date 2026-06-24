/* ============================================================
   AlphaFoundry — Dashboard Module
   Market Overview + Live Monitor tabs
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

const MARKET_SECTOR_VIEWS = [
    { key: 'wind_hot_concept', label: 'Wind热门概念' },
    { key: 'wind_l1', label: 'Wind一级' },
    { key: 'wind_l2', label: 'Wind二级' },
    { key: 'wind_l3', label: 'Wind三级' },
    { key: 'wind_l4', label: 'Wind四级' },
    { key: 'citic_l1', label: '中信一级' },
    { key: 'citic_l2', label: '中信二级' },
    { key: 'citic_l3', label: '中信三级' },
    { key: 'sw_l1', label: '申万一级' },
    { key: 'sw_l2', label: '申万二级' },
    { key: 'sw_l3', label: '申万三级' },
    { key: 'ths_industry', label: '同花顺行业' },
];

let activeMarketSectorView = 'ths_industry';
let latestMarketOverview = null;
const loadingMarketSectorViews = new Set();
const MARKET_SECTOR_PREFETCH_VIEWS = [];
let marketSectorPrefetchTimer = null;

if (typeof document !== 'undefined') {
    document.addEventListener('click', event => {
        if (!event.target.closest('.market-sector-view-selector')) {
            closeMarketSectorMenus();
        }
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeMarketSectorMenus();
    });
}

// ─── Dashboard Loading ──────────────────────────────────────
export async function loadDashboard() {
    const marketPanel = document.getElementById('dash-panel-market');

    try {
        showSectionLoading(marketPanel);

        const data = await apiCall('GET', '/api/dashboard');

        // Update data source badge
        updateDataSourceBadge(data);

        // Render Market Overview
        renderMarketOverview(data);

        // Refresh i18n
        if (typeof I18N !== 'undefined') I18N.applyAll();
    } catch (e) {
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
    latestMarketOverview = mo;

    renderMarketCommandCenter(mo);

    // Global News
    const newsEl = document.getElementById('market-global-news');
    if (newsEl) {
        const scrollPos = newsEl.scrollTop;
        if (mo.global_news.length) {
            newsEl.innerHTML = mo.global_news.map((n, idx) => `
                <li class="news-item ${n.is_mock ? 'mock-data-item' : ''}">
                    <div class="news-header">
                        <span class="news-rank">${idx + 1}</span>
                        <span class="news-title-inline">${esc(n.title)}</span>
                        ${n.is_mock ? '<span class="badge badge-mock">模拟</span>' : ''}
                    </div>
                    <div class="news-summary">${esc(n.summary)}</div>
                    <div class="news-meta">
                        <span class="news-time">${formatNewsTimestamp(n.published_at)}</span>
                    </div>
                </li>
            `).join('');
        } else {
            newsEl.innerHTML = '<li class="empty-state">暂无新闻</li>';
        }
        newsEl.scrollTop = scrollPos;
    }

    renderMarketSectorLists(mo);
    scheduleMarketSectorPrefetch();

    hideSectionLoading(document.getElementById('dash-panel-market'));
}

export function switchMarketSectorView(view) {
    const normalizedView = view === 'theme' ? 'wind_hot_concept' : view === 'industry' ? 'wind_l1' : view;
    if (!MARKET_SECTOR_VIEWS.some(item => item.key === normalizedView)) return;
    activeMarketSectorView = normalizedView;
    closeMarketSectorMenus();
    renderMarketSectorTabs();
    if (latestMarketOverview) renderMarketSectorLists(latestMarketOverview);
    ensureMarketSectorViewLoaded(normalizedView);
}

export function toggleMarketSectorMenu(trigger) {
    const selector = trigger?.closest('.market-sector-view-selector');
    if (!selector) return;
    const willOpen = !selector.classList.contains('is-open');
    closeMarketSectorMenus();
    selector.classList.toggle('is-open', willOpen);
    trigger.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
}

function closeMarketSectorMenus() {
    document.querySelectorAll('.market-sector-view-selector.is-open').forEach(selector => {
        selector.classList.remove('is-open');
        selector.querySelector('.market-sector-select-button')?.setAttribute('aria-expanded', 'false');
    });
}

function renderMarketSectorTabs() {
    const activeView = getActiveMarketSectorView();
    const menu = MARKET_SECTOR_VIEWS.map(view => {
        const counts = getMarketSectorViewCounts(view.key);
        const countText = counts.total ? `${counts.up}/${counts.down}` : '暂无';
        return `
        <button type="button" class="${view.key === activeView.key ? 'active' : ''}" data-sector-view="${view.key}" onclick="switchMarketSectorView('${view.key}')">
            <span>${esc(view.label)}</span>
            <small>${countText}</small>
        </button>
    `;
    }).join('');
    const selectorMarkup = `
        <div class="market-sector-view-selector">
            <button class="market-sector-select-button" type="button" aria-haspopup="listbox" aria-expanded="false" onclick="toggleMarketSectorMenu(this)">
                <span>数据口径</span>
                <strong>${esc(activeView.label)}</strong>
                <i class="codicon codicon-chevron-down" aria-hidden="true"></i>
            </button>
            <div class="market-sector-select-menu" role="listbox" aria-label="选择板块口径">
                ${menu}
            </div>
        </div>
    `;
    document.querySelectorAll('.market-sector-view-control').forEach(container => {
        container.innerHTML = selectorMarkup;
    });
}

function getActiveMarketSectorView() {
    return MARKET_SECTOR_VIEWS.find(view => view.key === activeMarketSectorView)
        || MARKET_SECTOR_VIEWS[0];
}

function getMarketSectorViewCounts(viewKey) {
    const view = latestMarketOverview?.sector_views?.[viewKey] || {};
    const up = Array.isArray(view.up) ? view.up.length : 0;
    const down = Array.isArray(view.down) ? view.down.length : 0;
    return {
        up,
        down,
        total: up + down,
    };
}

function hasKnownSectorViews(mo = {}) {
    const views = mo.sector_views || {};
    return MARKET_SECTOR_VIEWS.some(view => Object.prototype.hasOwnProperty.call(views, view.key));
}

function hasActiveSectorView(mo = {}) {
    const views = mo.sector_views || {};
    return Object.prototype.hasOwnProperty.call(views, activeMarketSectorView);
}

function getMarketSectorView(mo = {}) {
    const views = mo.sector_views || {};
    if (hasActiveSectorView(mo)) {
        return views[activeMarketSectorView] || { up: [], down: [] };
    }
    if (hasKnownSectorViews(mo)) return { up: [], down: [] };
    if (MARKET_SECTOR_VIEWS.some(view => view.key === activeMarketSectorView)) {
        return { up: [], down: [] };
    }
    const selected = views[activeMarketSectorView] || {};
    if ((selected.up && selected.up.length) || (selected.down && selected.down.length)) {
        return selected;
    }
    return {
        up: mo.top_up_sectors || [],
        down: mo.top_down_sectors || [],
    };
}

function renderMarketSectorLists(mo) {
    renderMarketSectorTabs();
    const view = getMarketSectorView(mo);
    const isLoading = loadingMarketSectorViews.has(activeMarketSectorView);
    renderSectorList(document.getElementById('market-top-up-sectors'), view.up || [], 'up', isLoading);
    renderSectorList(document.getElementById('market-top-down-sectors'), view.down || [], 'down', isLoading);
    renderMarketHeatmap(buildMarketHeatmapItems(mo));
}

function renderSectorList(container, sectors, direction, isLoading = false) {
    if (!container) return;
    const scrollPos = container.scrollTop;
    if (isLoading) {
        container.innerHTML = `<li class="empty-state">${esc(getActiveMarketSectorView().label)}加载中...</li>`;
    } else if (sectors && sectors.length) {
        container.innerHTML = sectors.map(s => {
            const change = Number(s.change_pct || 0);
            const changeText = `${change > 0 ? '+' : ''}${change.toFixed(2)}%`;
            return `
                <li class="sector-item ${s.is_mock ? 'mock-data-item' : ''}">
                    <div class="sector-header">
                        <span class="sector-name">${esc(s.name)}</span>
                        <span class="sector-right">
                            <span class="badge ${s.is_concept ? 'badge-concept' : 'badge-sector'}">${esc(s.view_label || (s.is_concept ? '概念' : '行业'))}</span>
                            <span class="sector-change sector-${direction}">${changeText}</span>
                        </span>
                    </div>
                </li>
            `;
        }).join('');
    } else {
        container.innerHTML = `<li class="empty-state">${esc(getActiveMarketSectorView().label)}暂无数据</li>`;
    }
    container.scrollTop = scrollPos;
}

function scheduleMarketSectorPrefetch() {
    if (!latestMarketOverview) return;
    if (marketSectorPrefetchTimer) clearTimeout(marketSectorPrefetchTimer);
    marketSectorPrefetchTimer = setTimeout(() => {
        preloadMarketSectorViews(MARKET_SECTOR_PREFETCH_VIEWS);
    }, 1200);
}

async function preloadMarketSectorViews(viewKeys = []) {
    for (const viewKey of viewKeys) {
        if (!latestMarketOverview) return;
        const current = latestMarketOverview.sector_views?.[viewKey];
        if ((current?.up?.length || 0) + (current?.down?.length || 0) > 0) continue;
        if (loadingMarketSectorViews.has(viewKey)) continue;
        await ensureMarketSectorViewLoaded(viewKey, { silent: true });
    }
}

async function ensureMarketSectorViewLoaded(viewKey, options = {}) {
    if (!latestMarketOverview) return;
    const silent = Boolean(options.silent);
    const current = latestMarketOverview.sector_views?.[viewKey];
    if ((current?.up?.length || 0) + (current?.down?.length || 0) > 0) return;
    if (loadingMarketSectorViews.has(viewKey)) return;

    loadingMarketSectorViews.add(viewKey);
    if (!silent || activeMarketSectorView === viewKey) {
        renderMarketSectorLists(latestMarketOverview);
    } else {
        renderMarketSectorTabs();
    }
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 24000);
    try {
        const data = await apiCall(
            'GET',
            `/api/dashboard/sector-movers?view_key=${encodeURIComponent(viewKey)}&limit=10`,
            null,
            { signal: controller.signal }
        );
        latestMarketOverview.sector_views = latestMarketOverview.sector_views || {};
        latestMarketOverview.sector_views[viewKey] = {
            up: data.up || [],
            down: data.down || [],
        };
    } catch (error) {
        console.error('Failed to load market sector view:', error);
        latestMarketOverview.sector_views = latestMarketOverview.sector_views || {};
        latestMarketOverview.sector_views[viewKey] = { up: [], down: [] };
        if (!silent) toast(`加载${getActiveMarketSectorView().label}失败或超时`, 'error');
    } finally {
        clearTimeout(timeoutId);
        loadingMarketSectorViews.delete(viewKey);
        if (activeMarketSectorView === viewKey) {
            renderMarketSectorLists(latestMarketOverview);
        } else {
            renderMarketSectorTabs();
        }
    }
}

function formatNewsTimestamp(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '';

    const time = date.toLocaleTimeString([], {
        hour: 'numeric',
        minute: '2-digit',
    });
    if (isSameLocalDate(date, new Date())) return time;

    return `${date.toLocaleDateString()} ${time}`;
}

function isSameLocalDate(left, right) {
    return left.getFullYear() === right.getFullYear()
        && left.getMonth() === right.getMonth()
        && left.getDate() === right.getDate();
}

function renderMarketCommandCenter(mo = {}) {
    const indices = Array.isArray(mo.indices) ? mo.indices : buildFallbackIndices(mo);
    renderMarketIndices(indices);

    const breadth = mo.breadth || buildFallbackBreadth(mo);
    renderMarketBreadth(breadth);

    const heatmapItems = mo.heatmap || buildMarketHeatmapItems(mo);
    renderMarketHeatmap(heatmapItems);

    renderMarketAiBrief(mo, indices, breadth);
}

function buildFallbackIndices(mo = {}) {
    return [];
}

function buildFallbackBreadth(mo = {}) {
    return {
        up: 0,
        down: 0,
        upRatio: 50,
        downRatio: 50,
        turnover: '--',
        turnoverDelta: null,
        sourceLabel: '等待实时刷新',
    };
}

function buildFallbackHeatmap(mo = {}) {
    const combined = [
        ...(mo.top_up_sectors || []).map(item => ({ ...item, direction: 'up' })),
        ...(mo.top_down_sectors || []).map(item => ({ ...item, direction: 'down' })),
    ];
    if (combined.length) return combined.slice(0, 18);
    return [
        { name: '半导体', change_pct: 2.08, direction: 'up', related_news_count: 9 },
        { name: '机器人链', change_pct: 1.69, direction: 'up', related_news_count: 7 },
        { name: '消费电子', change_pct: 1.32, direction: 'up', related_news_count: 4 },
        { name: '保险', change_pct: -2.36, direction: 'down', related_news_count: 5 },
        { name: '电力', change_pct: -1.98, direction: 'down', related_news_count: 3 },
    ];
}

function buildMarketHeatmapItems(mo = {}) {
    const view = getMarketSectorView(mo);
    const combined = [
        ...(view.up || []).map(item => ({ ...item, direction: 'up' })),
        ...(view.down || []).map(item => ({ ...item, direction: 'down' })),
    ];
    if (combined.length) return combined.slice(0, 18);
    if (hasActiveSectorView(mo) || hasKnownSectorViews(mo)) return [];
    return buildFallbackHeatmap(mo);
}

function renderMarketIndices(indices = []) {
    const grid = document.getElementById('market-index-grid');
    if (!grid) return;
    if (!indices.length) {
        grid.innerHTML = '<article class="market-index-card"><span>指数行情</span><strong>--</strong><small>等待实时刷新</small></article>';
        return;
    }
    grid.innerHTML = indices.map(index => {
        const change = Number(index.change || index.change_pct || 0);
        const directionClass = change >= 0 ? 'is-up' : 'is-down';
        const sign = change > 0 ? '+' : '';
        return `
            <article class="market-index-card ${directionClass}">
                <span>${esc(index.name || '--')}</span>
                <strong>${esc(String(index.value || '--'))}</strong>
                <small>${sign}${change.toFixed(2)}%</small>
            </article>
        `;
    }).join('');
}

function renderMarketBreadth(breadth = {}) {
    const up = Number(breadth.up || 0);
    const down = Number(breadth.down || 0);
    const upRatio = Math.min(95, Math.max(5, Number(breadth.upRatio || 50)));
    const downRatio = Math.max(5, 100 - upRatio);
    const meta = breadth.turnoverDelta
        ? `较昨日 ${breadth.turnoverDelta}`
        : (breadth.sourceLabel || '等待实时刷新');

    setText('market-breadth-ratio', `${up || '--'} : ${down || '--'}`);
    setText('market-turnover', `成交额 ${breadth.turnover || '--'}`);
    setText('market-turnover-delta', meta);
    setWidth('market-breadth-up', `${upRatio}%`);
    setWidth('market-breadth-down', `${downRatio}%`);
}

function renderMarketHeatmap(items = []) {
    const grid = document.getElementById('market-heatmap-grid');
    if (!grid) return;
    if (!items.length) {
        grid.innerHTML = '<div class="empty-state">暂无板块数据</div>';
        return;
    }
    grid.innerHTML = items.map((item, idx) => {
        const change = Number(item.change_pct || 0);
        const directionClass = change >= 0 ? 'is-up' : 'is-down';
        const sizeClass = idx < 2 ? 'is-large' : idx < 6 ? 'is-medium' : 'is-small';
        const sign = change > 0 ? '+' : '';
        return `
            <button class="market-heatmap-tile ${directionClass} ${sizeClass}" type="button">
                <span>${esc(item.name || '--')}</span>
                <strong>${sign}${change.toFixed(2)}%</strong>
            </button>
        `;
    }).join('');
}

function renderMarketAiBrief(mo = {}, indices = [], breadth = {}) {
    const bestSector = (mo.top_up_sectors || [])[0];
    const weakSector = (mo.top_down_sectors || [])[0];
    const leadIndex = indices.find(index => Number(index.change || 0) > 0) || indices[0] || {};
    const brief = [
        `${leadIndex.name || 'A股'}盘面以结构性机会为主。`,
        bestSector ? `${bestSector.name}领涨，涨幅约 ${Number(bestSector.change_pct || 0).toFixed(2)}%。` : '热点板块等待实时数据确认。',
        weakSector ? `${weakSector.name}承压，注意资金轮动。` : '下跌板块暂未形成清晰主线。',
    ].join('');

    const updated = mo.last_updated ? new Date(mo.last_updated).toLocaleString() : new Date().toLocaleDateString();
    setText('market-ai-brief-text', brief);
    setText('market-ai-brief-date', updated);
    setText('market-close-state', mo.uses_real_sectors ? '实时行情' : '本地推演');
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setWidth(id, value) {
    const el = document.getElementById(id);
    if (el) el.style.width = value;
}

// ─── Tab Switching ──────────────────────────────────────────
export function switchDashTab(tabName) {
    document.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.dash-tab-panel').forEach(p => p.classList.remove('active'));
    const tabBtn = document.querySelector(`.dash-tab[data-dash-tab="${tabName}"]`);
    const panel = document.getElementById(`dash-panel-${tabName}`);
    if (tabBtn) tabBtn.classList.add('active');
    if (panel) panel.classList.add('active');
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
