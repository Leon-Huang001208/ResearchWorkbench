/* ============================================================
   Research Workbench — Dashboard Module
   Market Overview + Live Monitor tabs
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

const MARKET_SECTOR_VIEWS = [
    { key: 'wind_hot_concept', label: 'Wind热门概念', scope: 'concept' },
    { key: 'wind_l1', label: 'Wind一级', scope: 'sector' },
    { key: 'wind_l2', label: 'Wind二级', scope: 'sector' },
    { key: 'wind_l3', label: 'Wind三级', scope: 'sector' },
    { key: 'wind_l4', label: 'Wind四级', scope: 'sector' },
    { key: 'citic_l1', label: '中信一级', scope: 'sector' },
    { key: 'citic_l2', label: '中信二级', scope: 'sector' },
    { key: 'citic_l3', label: '中信三级', scope: 'sector' },
    { key: 'sw_l1', label: '申万一级', scope: 'sector' },
    { key: 'sw_l2', label: '申万二级', scope: 'sector' },
    { key: 'sw_l3', label: '申万三级', scope: 'sector' },
    { key: 'ths_industry', label: '同花顺行业', scope: 'sector' },
];

const MARKET_HEATMAP_SCOPES = [
    { key: 'concept', label: '概念', viewKey: 'wind_hot_concept' },
    { key: 'sector', label: '板块', viewKey: 'wind_l1' },
];

let activeMarketSectorView = 'wind_hot_concept';
let activeMarketHeatmapScope = 'concept';
let latestMarketOverview = null;
const loadingMarketSectorViews = new Set();
const marketSectorViewRequestCache = new Map();
const MARKET_SECTOR_PREFETCH_VIEWS = [];
const MARKET_REFRESH_INTERVAL_MS = 30000;
const MARKET_SECTOR_REQUEST_TIMEOUT_MS = 90000;
const MARKET_SECTOR_LIST_LIMIT = 10;
const MARKET_HEATMAP_ITEM_LIMIT = 60;
const MARKET_SECTOR_FETCH_LIMIT = 30;
let marketSectorPrefetchTimer = null;
let marketRefreshTimer = null;
let isMarketDashboardRefreshing = false;

if (typeof document !== 'undefined') {
    document.addEventListener('click', event => {
        if (!event.target.closest('.market-sector-view-selector')) {
            closeMarketSectorMenus();
        }
        const marketAction = event.target.closest('[data-market-action]');
        if (marketAction) handleMarketAction(marketAction.dataset.marketAction);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeMarketSectorMenus();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) stopMarketAutoRefresh();
        else scheduleMarketAutoRefresh();
    });
}

// ─── Dashboard Loading ──────────────────────────────────────
export async function loadDashboard(options = {}) {
    const marketPanel = document.getElementById('dash-panel-market');
    const silent = Boolean(options.silent);

    try {
        if (!silent) showSectionLoading(marketPanel);
        setMarketRefreshState(true, silent ? '自动刷新中' : '刷新中');

        primeMarketSectorViewRequest(activeMarketSectorView);
        let data = null;
        try {
            data = normalizeMarketHomeEnvelope(await apiCall('GET', '/api/market-home/live'));
        } catch (e) {
            console.error('dashboard_fetch_failed', e);
            if (!silent) {
                showSectionError(marketPanel, e.message);
                toast('仪表盘加载失败', 'error');
            }
            return;
        }

        try {
            // Update data source badge
            updateDataSourceBadge(data);

            // Render Market Overview
            renderMarketOverview(data);

            // Refresh i18n
            if (typeof I18N !== 'undefined') I18N.applyAll();
            scheduleMarketAutoRefresh();
        } catch (e) {
            console.error('dashboard_render_failed', e);
            if (!silent) {
                showSectionError(marketPanel, e.message);
                toast('仪表盘渲染失败', 'error');
            }
        }
    } catch (e) {
        console.error('Failed to load dashboard:', e);
        if (!silent) {
            showSectionError(marketPanel, e.message);
            toast('仪表盘加载失败', 'error');
        }
    } finally {
        setMarketRefreshState(false);
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
    renderMarketOverviewPayload(data.market_overview || {});
}

function normalizeMarketHomeEnvelope(envelope = {}) {
    const sections = Object.fromEntries(
        (envelope.sections || []).map(section => [section.section_key, section])
    );
    const sectionPayload = key => sections[key]?.payload || {};
    const globalContext = sectionPayload('global_context');
    const aShare = sectionPayload('a_share_status');
    const mainlines = sectionPayload('market_mainlines');
    const importantEvents = sectionPayload('important_events');
    const assetMoves = sectionPayload('asset_moves');
    const normalizeMainline = item => ({
        ...item,
        name: item.name || item.label || item.theme_key,
        change_pct: item.change_pct ?? item.return_value ?? null,
    });
    const leading = (mainlines.leading || []).map(normalizeMainline);
    const weakening = (mainlines.weakening || []).map(normalizeMainline);
    const events = importantEvents.events || importantEvents.items || globalContext.events || [];
    const asOf = (envelope.sections || [])
        .map(section => section.as_of)
        .filter(Boolean)
        .sort()
        .at(-1);
    return {
        market_overview: {
            ...globalContext,
            ...aShare,
            indices: aShare.indices || assetMoves.indices || [],
            breadth: aShare.breadth || {},
            global_news: events,
            top_up_sectors: leading,
            top_down_sectors: weakening,
            heatmap: [...leading, ...weakening],
            sector_views: {
                wind_hot_concept: {
                    up: leading,
                    down: weakening,
                    status: sections.market_mainlines?.status || '',
                    message: sections.market_mainlines?.degradation?.error_code || '',
                },
            },
            trading_status: envelope.trading_status,
            trading_day: envelope.trading_day,
            last_updated: asOf,
            uses_real_news: Boolean(sections.important_events?.source_refs?.length),
            uses_real_sectors: Boolean(sections.market_mainlines?.source_refs?.length),
        },
    };
}

function renderMarketOverviewPayload(mo = {}) {
    const previousViews = latestMarketOverview?.sector_views || {};
    mo.sector_views = {
        ...previousViews,
        ...(mo.sector_views || {}),
    };
    latestMarketOverview = mo;

    renderMarketCommandCenter(mo);

    // Global News
    const newsEl = document.getElementById('market-global-news');
    if (newsEl) {
        const scrollPos = newsEl.scrollTop;
        const globalNews = Array.isArray(mo.global_news) ? mo.global_news : [];
        if (globalNews.length) {
            newsEl.innerHTML = globalNews.map((n, idx) => `
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
    ensureMarketSectorViewLoaded(activeMarketSectorView, { silent: true });
    scheduleMarketSectorPrefetch();

    hideSectionLoading(document.getElementById('dash-panel-market'));
}

export function switchMarketHeatmapScope(scopeKey) {
    const scope = MARKET_HEATMAP_SCOPES.find(item => item.key === scopeKey);
    if (!scope) return;
    activeMarketHeatmapScope = scope.key;
    switchMarketSectorView(scope.viewKey, { fromHeatmapScope: true });
}

export function switchMarketSectorView(view, options = {}) {
    const normalizedView = view === 'theme' ? 'wind_hot_concept' : view === 'industry' ? 'wind_l1' : view;
    if (!MARKET_SECTOR_VIEWS.some(item => item.key === normalizedView)) return;
    activeMarketSectorView = normalizedView;
    if (!options.fromHeatmapScope) {
        activeMarketHeatmapScope = inferMarketHeatmapScope(normalizedView);
    }
    closeMarketSectorMenus();
    renderMarketHeatmapScopes();
    renderMarketSectorTabs();
    if (latestMarketOverview) renderMarketSectorLists(latestMarketOverview);
    ensureMarketSectorViewLoaded(normalizedView);
}

export function refreshMarketDashboard(options = {}) {
    return refreshMarketOverviewOnly({
        forceRefresh: Boolean(options.manual),
        silent: !options.manual,
    });
}

async function refreshMarketOverviewOnly(options = {}) {
    if (isMarketDashboardRefreshing) return Promise.resolve();
    isMarketDashboardRefreshing = true;
    const silent = Boolean(options.silent);
    const forceRefresh = Boolean(options.forceRefresh);

    try {
        setMarketRefreshState(true, silent ? '自动刷新中' : '刷新中');
        const envelope = await apiCall(
            'GET',
            `/api/market-home/live?force_refresh=${forceRefresh ? 'true' : 'false'}&_=${Date.now()}`
        );
        const overview = normalizeMarketHomeEnvelope(envelope).market_overview;
        updateDataSourceBadge({ market_overview: overview });
        renderMarketOverviewPayload(overview);
        await ensureMarketSectorViewLoaded(activeMarketSectorView, { force: true, silent: true });
        if (typeof I18N !== 'undefined') I18N.applyAll();
    } catch (e) {
        console.error('Failed to refresh market overview:', e);
        if (!silent) toast('行情刷新失败', 'error');
    } finally {
        isMarketDashboardRefreshing = false;
        setMarketRefreshState(false);
        scheduleMarketAutoRefresh();
    }
}

function handleMarketAction(action) {
    switch (action) {
        case 'refresh':
            refreshMarketDashboard({ manual: true });
            break;
        case 'etf':
            openAssetAnalysis('ETF');
            break;
        default:
            break;
    }
}

function openAssetAnalysis(query = '') {
    if (typeof window.navigateTo === 'function') {
        window.navigateTo('asset-analysis');
    }
    setTimeout(() => {
        const input = document.getElementById('asset-code');
        if (!input) return;
        if (query) {
            input.value = query;
            input.dispatchEvent(new Event('input', { bubbles: true }));
        }
        input.focus();
    }, 80);
}

function openAssetThemeObservation(item = {}, rank = null) {
    if (typeof window.navigateTo === 'function') {
        window.navigateTo('asset-analysis');
    }
    setTimeout(() => {
        if (typeof window.openThemeObservation === 'function') {
            window.openThemeObservation({
                ...item,
                rank,
                fetched_at: latestMarketOverview?.last_updated || new Date().toISOString(),
            });
        } else {
            openAssetAnalysis(item.name || '');
        }
    }, 80);
}

function scrollMarketTarget(selector) {
    const target = document.querySelector(selector);
    if (!target) return;
    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function scheduleMarketAutoRefresh() {
    stopMarketAutoRefresh();
    if (!shouldAutoRefreshMarket()) return;
    marketRefreshTimer = setTimeout(() => {
        refreshMarketDashboard({ manual: false });
    }, MARKET_REFRESH_INTERVAL_MS);
}

function stopMarketAutoRefresh() {
    if (marketRefreshTimer) clearTimeout(marketRefreshTimer);
    marketRefreshTimer = null;
}

function shouldAutoRefreshMarket() {
    if (typeof document === 'undefined' || document.hidden) return false;
    return Boolean(
        document.getElementById('section-dashboard')?.classList.contains('active')
        && document.getElementById('dash-panel-market')?.classList.contains('active')
        && getMarketSessionInfo().isTrading
    );
}

function setMarketRefreshState(isRefreshing, label = '') {
    // Auto refresh is intentionally silent; the market panel should not expose a manual refresh control.
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
    const visibleViews = getMarketSectorViewsForActiveScope();
    const menu = visibleViews.map(view => {
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
    renderMarketHeatmapScopes();
    updateMarketHeatmapCopy();
}

function renderMarketHeatmapScopes() {
    const markup = MARKET_HEATMAP_SCOPES.map(scope => `
        <button class="${scope.key === activeMarketHeatmapScope ? 'active' : ''}" type="button" onclick="switchMarketHeatmapScope('${scope.key}')">
            ${esc(scope.label)}
        </button>
    `).join('');
    document.querySelectorAll('.market-heatmap-modes').forEach(container => {
        container.innerHTML = markup;
    });
}

function inferMarketHeatmapScope(viewKey) {
    if (viewKey === 'wind_hot_concept') return 'concept';
    return 'sector';
}

function getMarketSectorViewsForActiveScope() {
    return MARKET_SECTOR_VIEWS.filter(view => view.scope === activeMarketHeatmapScope);
}

function updateMarketHeatmapCopy() {
    const activeView = getActiveMarketSectorView();
    const title = activeView.key === 'wind_hot_concept'
        ? 'Wind热门概念矩阵'
        : `${activeView.label}行业矩阵`;
    setText('market-heatmap-title', title);
    setText('market-heatmap-subtitle', '颜色表示涨跌方向，描边表示涨跌强度');
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
    renderSectorList(document.getElementById('market-top-up-sectors'), view.up || [], 'up', isLoading, view);
    renderSectorList(document.getElementById('market-top-down-sectors'), view.down || [], 'down', isLoading, view);
    renderMarketHeatmap(buildMarketHeatmapItems(mo));
}

function renderSectorList(container, sectors, direction, isLoading = false, view = null) {
    if (!container) return;
    const scrollPos = container.scrollTop;
    if (isLoading) {
        container.innerHTML = `<li class="empty-state">${esc(getActiveMarketSectorView().label)}加载中...</li>`;
    } else if (sectors && sectors.length) {
        container.innerHTML = sectors.slice(0, MARKET_SECTOR_LIST_LIMIT).map(s => {
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
        const label = esc(getActiveMarketSectorView().label);
        const status = view && view.status ? String(view.status) : '';
        const message = view && view.message ? String(view.message) : '';
        let text;
        if (message) {
            text = `${label}：${esc(message)}`;
        } else if (status === 'snapshot_empty' || status === 'snapshot_invalid' || status === 'no_snapshot_data') {
            text = `${label}暂无数据（请确认Wind插件已登录）`;
        } else {
            text = `${label}暂无数据`;
        }
        container.innerHTML = `<li class="empty-state">${text}</li>`;
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
    const force = Boolean(options.force);
    const current = latestMarketOverview.sector_views?.[viewKey];
    if (!force && (current?.up?.length || 0) + (current?.down?.length || 0) > 0) return;
    if (loadingMarketSectorViews.has(viewKey)) return;

    loadingMarketSectorViews.add(viewKey);
    if (!silent || activeMarketSectorView === viewKey) {
        renderMarketSectorLists(latestMarketOverview);
    } else {
        renderMarketSectorTabs();
    }
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), MARKET_SECTOR_REQUEST_TIMEOUT_MS);
    try {
        const data = await getMarketSectorViewPayload(viewKey, controller.signal, force);
        const hasFreshSectorData = Boolean(data.has_real_data)
            || (Array.isArray(data.up) && data.up.length > 0)
            || (Array.isArray(data.down) && data.down.length > 0);
        if (force && !hasFreshSectorData && current) return;
        latestMarketOverview.sector_views = latestMarketOverview.sector_views || {};
        latestMarketOverview.sector_views[viewKey] = {
            up: data.up || [],
            down: data.down || [],
            status: data.status || '',
            message: data.message || '',
        };
        // 如果当前激活视图是 Wind 系视图（需要 Wind 终端），但返回数据为空，
        // 自动 fallback 到同花顺行业视图（使用 AKShare，无需 Wind）
        const isWindView = viewKey !== 'ths_industry';
        const isEmpty = !data.up?.length && !data.down?.length;
        if (isWindView && isEmpty && activeMarketSectorView === viewKey) {
            toast('Wind未连接，已切换至同花顺行业数据', 'info');
            switchMarketSectorView('ths_industry');
            return;
        }
    } catch (error) {
        console.error('Failed to load market sector view:', error);
        latestMarketOverview.sector_views = latestMarketOverview.sector_views || {};
        if (force && current) return;
        latestMarketOverview.sector_views[viewKey] = { up: [], down: [], status: '', message: '' };
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

function primeMarketSectorViewRequest(viewKey) {
    if (!MARKET_SECTOR_VIEWS.some(item => item.key === viewKey)) return;
    if (marketSectorViewRequestCache.has(viewKey)) return;
    marketSectorViewRequestCache.set(viewKey, fetchMarketSectorViewPayload(viewKey));
}

async function getMarketSectorViewPayload(viewKey, signal, forceRefresh = false) {
    if (forceRefresh) {
        marketSectorViewRequestCache.delete(viewKey);
        return fetchMarketSectorViewPayload(viewKey, signal, true);
    }
    const cachedRequest = marketSectorViewRequestCache.get(viewKey);
    if (cachedRequest) {
        try {
            return await cachedRequest;
        } finally {
            marketSectorViewRequestCache.delete(viewKey);
        }
    }
    return fetchMarketSectorViewPayload(viewKey, signal);
}

function fetchMarketSectorViewPayload(viewKey, signal, forceRefresh = false) {
    const view = latestMarketOverview?.sector_views?.[viewKey] || {};
    return Promise.resolve({
        up: view.up || [],
        down: view.down || [],
        status: view.status || '',
        message: view.message || '',
        has_real_data: Boolean((view.up || []).length || (view.down || []).length),
        signal,
        forceRefresh,
    });
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
    renderMarketSessionStrip(mo, breadth);

    const heatmapItems = mo.heatmap || buildMarketHeatmapItems(mo);
    renderMarketHeatmap(heatmapItems);

    renderMarketFactSummary(mo);
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
    if (combined.length) return combined.slice(0, MARKET_HEATMAP_ITEM_LIMIT);
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
    if (combined.length) return combined.slice(0, MARKET_HEATMAP_ITEM_LIMIT);
    if (hasActiveSectorView(mo) || hasKnownSectorViews(mo)) return [];
    return buildFallbackHeatmap(mo);
}

function renderMarketIndices(indices = []) {
    const grid = document.getElementById('market-index-grid');
    if (!grid) return;
    if (!indices.length) {
        grid.innerHTML = '<article class="market-index-card"><span>指数行情</span><strong>--</strong><small><em>等待实时刷新</em></small></article>';
        return;
    }
    grid.innerHTML = getPrimaryMarketIndices(indices).map(index => {
        const change = readPercentChange(index);
        const pointChange = readPointChange(index);
        const directionClass = change >= 0 ? 'is-up' : 'is-down';
        const pointText = pointChange === null
            ? ''
            : `<b>${formatSignedNumber(pointChange)}</b>`;
        return `
            <article class="market-index-card ${directionClass}">
                <span>${esc(index.name || '--')}</span>
                <strong>${esc(String(index.value || '--'))}</strong>
                <small>${pointText}<em>${formatSignedPercent(change)}</em></small>
            </article>
        `;
    }).join('');
}

function getPrimaryMarketIndices(indices = []) {
    const preferredNames = [
        '上证指数',
        '深证成指',
        '科创综指',
        '创业板指',
        '中证A500',
        '北证50',
        '上证50',
        '沪深300',
        '科创50',
        '创业板50',
        '中证500',
        '中证1000',
    ];
    const byName = new Map(indices.map(index => [index.name, index]));
    const preferred = preferredNames
        .map(name => byName.get(name))
        .filter(Boolean);
    return preferred;
}

function renderMarketBreadth(breadth = {}) {
    const up = Number(breadth.up || 0);
    const down = Number(breadth.down || 0);
    const ratios = normalizeBreadthRatios(breadth, up, down);
    const meta = breadth.previousTurnover
        ? `上一日成交额 ${breadth.previousTurnover}`
        : '上一日成交额 --';

    setText('market-breadth-ratio', `${down || '--'} : ${up || '--'}`);
    setText('market-breadth-down-label', `跌 ${down || '--'}`);
    setText('market-breadth-up-label', `涨 ${up || '--'}`);
    setText('market-turnover', `今日实时成交额 ${breadth.turnover || '--'}`);
    setText('market-turnover-delta', meta);
    setWidth('market-breadth-up', `${ratios.up}%`);
    setWidth('market-breadth-down', `${ratios.down}%`);
}

function normalizeBreadthRatios(breadth = {}, up = 0, down = 0) {
    const explicitUp = Number(breadth.upRatio);
    const explicitDown = Number(breadth.downRatio);
    if (Number.isFinite(explicitUp) && Number.isFinite(explicitDown) && explicitUp + explicitDown > 0) {
        const total = explicitUp + explicitDown;
        return {
            up: clampRatio(explicitUp / total * 100),
            down: clampRatio(explicitDown / total * 100),
        };
    }

    const total = up + down;
    if (total <= 0) return { up: 50, down: 50 };
    return {
        up: clampRatio(up / total * 100),
        down: clampRatio(down / total * 100),
    };
}

function clampRatio(value) {
    return Math.round(Math.min(95, Math.max(5, value)) * 10) / 10;
}

function renderMarketHeatmap(items = []) {
    const grid = document.getElementById('market-heatmap-grid');
    if (!grid) return;
    if (!items.length) {
        grid.innerHTML = '<div class="empty-state">暂无板块数据</div>';
        return;
    }
    grid.innerHTML = items.map((item, index) => {
        const change = Number(item.change_pct || 0);
        const directionClass = change >= 0 ? 'is-up' : 'is-down';
        const intensityClass = getMarketHeatmapIntensityClass(change);
        const sign = change > 0 ? '+' : '';
        const rank = index + 1;
        return `
            <button class="market-heatmap-tile ${directionClass} ${intensityClass}" type="button" data-heatmap-rank="${rank}">
                <span>${esc(item.name || '--')}</span>
                <strong>${sign}${change.toFixed(2)}%</strong>
            </button>
        `;
    }).join('');
    grid.querySelectorAll('.market-heatmap-tile').forEach((button, index) => {
        button.addEventListener('click', () => openAssetThemeObservation(items[index], index + 1));
    });
}

function getMarketHeatmapIntensityClass(change) {
    const absoluteChange = Math.abs(Number(change) || 0);
    if (absoluteChange >= 5) return 'is-strong';
    if (absoluteChange >= 2) return 'is-medium';
    return 'is-muted';
}

function renderMarketFactSummary(mo = {}) {
    const leadingCount = (mo.top_up_sectors || []).length;
    const weakeningCount = (mo.top_down_sectors || []).length;
    const eventCount = (mo.global_news || []).length;
    const brief = `事实快照：领先主线 ${leadingCount} 条，走弱主线 ${weakeningCount} 条，重要事件 ${eventCount} 条。`;
    const updated = formatMarketDateTime(mo.last_updated);
    setText('market-ai-brief-text', brief);
    setText('market-ai-brief-date', updated);
}

function renderMarketSessionStrip(mo = {}, breadth = {}) {
    const session = getMarketSessionInfo(mo);
    setText('market-session-state', session.state);
    setText('market-session-date', session.date);
    const sessionEl = document.querySelector('.market-session-state');
    if (sessionEl) {
        sessionEl.classList.toggle('is-trading', session.isTrading);
        sessionEl.classList.toggle('is-closed', !session.isTrading);
    }
}

function getMarketSessionInfo(mo = {}) {
    const date = new Date();
    const minutes = date.getHours() * 60 + date.getMinutes();
    const day = date.getDay();
    const isWeekday = day >= 1 && day <= 5;
    const isTradingMinute = isWeekday
        && ((minutes >= 9 * 60 + 30 && minutes <= 11 * 60 + 30)
            || (minutes >= 13 * 60 && minutes <= 15 * 60));
    const isLunchBreak = isWeekday && minutes > 11 * 60 + 30 && minutes < 13 * 60;
    const isBeforeOpen = isWeekday && minutes < 9 * 60 + 30;

    return {
        state: isTradingMinute
            ? '开盘中'
            : isLunchBreak
                ? '午间休市'
                : isBeforeOpen
                    ? '未开盘'
                    : '已收盘',
        date: formatMarketDate(date),
        isTrading: isTradingMinute,
    };
}

function readPercentChange(index = {}) {
    const value = Number(index.change ?? index.change_pct ?? index.changePercent ?? index.pct ?? 0);
    return Number.isFinite(value) ? value : 0;
}

function readPointChange(index = {}) {
    const value = Number(index.point_change ?? index.change_value ?? index.changeValue ?? index.price_change);
    return Number.isFinite(value) ? value : null;
}

function formatSignedPercent(value) {
    const numeric = Number.isFinite(value) ? value : 0;
    return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`;
}

function formatSignedNumber(value) {
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) return '--';
    return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}`;
}

function pickFirstText(...values) {
    const value = values.find(item => item !== undefined && item !== null && String(item).trim() !== '');
    return value === undefined ? '--' : String(value);
}

function hasText(value) {
    return value !== undefined && value !== null && String(value).trim() !== '' && String(value) !== '--';
}

function readDate(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return null;
    return date;
}

function formatMarketDate(value) {
    const date = value instanceof Date ? value : readDate(value);
    if (!date) return '--';
    const weekday = ['星期日', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六'][date.getDay()];
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day} ${weekday}`;
}

function formatMarketDateTime(value) {
    const date = readDate(value) || new Date();
    return date.toLocaleString('zh-CN', {
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value;
}

function setMarkup(id, value) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = value;
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
    if (tabName === 'market') scheduleMarketAutoRefresh();
    else stopMarketAutoRefresh();
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
