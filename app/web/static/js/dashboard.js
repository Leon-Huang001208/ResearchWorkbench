/* ============================================================
   AlphaFoundry — Dashboard Module
   Market Overview + Live Monitor tabs
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

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

    // Top Up Sectors
    const upEl = document.getElementById('market-top-up-sectors');
    if (upEl) {
        const scrollPos = upEl.scrollTop;
        if (mo.top_up_sectors && mo.top_up_sectors.length) {
            upEl.innerHTML = mo.top_up_sectors.map(s => `
                <li class="sector-item ${s.is_mock ? 'mock-data-item' : ''}">
                    <div class="sector-header">
                        <span class="sector-name">${esc(s.name)}</span>
                        <span class="sector-right">
                            <span class="badge ${s.is_concept ? 'badge-concept' : 'badge-sector'}">${s.is_concept ? '概念' : '板块'}</span>
                            <span class="sector-change sector-up">+${s.change_pct.toFixed(2)}%</span>
                        </span>
                    </div>
                </li>
            `).join('');
        } else {
            upEl.innerHTML = '<li class="empty-state">暂无数据</li>';
        }
        upEl.scrollTop = scrollPos;
    }

    // Top Down Sectors
    const downEl = document.getElementById('market-top-down-sectors');
    if (downEl) {
        const scrollPos = downEl.scrollTop;
        if (mo.top_down_sectors && mo.top_down_sectors.length) {
            downEl.innerHTML = mo.top_down_sectors.map(s => `
                <li class="sector-item ${s.is_mock ? 'mock-data-item' : ''}">
                    <div class="sector-header">
                        <span class="sector-name">${esc(s.name)}</span>
                        <span class="sector-right">
                            <span class="badge ${s.is_concept ? 'badge-concept' : 'badge-sector'}">${s.is_concept ? '概念' : '板块'}</span>
                            <span class="sector-change sector-down">${s.change_pct.toFixed(2)}%</span>
                        </span>
                    </div>
                </li>
            `).join('');
        } else {
            downEl.innerHTML = '<li class="empty-state">暂无数据</li>';
        }
        downEl.scrollTop = scrollPos;
    }

    hideSectionLoading(document.getElementById('dash-panel-market'));
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
