/* ============================================================
   AlphaFoundry — Dashboard Module
   Market Overview + Workbench tabs
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

// ─── Dashboard Loading ──────────────────────────────────────
export async function loadDashboard() {
    const marketPanel = document.getElementById('dash-panel-market');
    const workbenchPanel = document.getElementById('dash-panel-workbench');

    try {
        showSectionLoading(marketPanel);
        showSectionLoading(workbenchPanel);

        const data = await apiCall('GET', '/api/dashboard');

        // Update data source badge
        updateDataSourceBadge(data);

        // Render both tab panels from the same data
        renderMarketOverview(data);
        renderWorkbench(data);

        // Refresh i18n
        if (typeof I18N !== 'undefined') I18N.applyAll();
    } catch (e) {
        console.error('Failed to load dashboard:', e);
        showSectionError(marketPanel, e.message);
        showSectionError(workbenchPanel, e.message);
        toast('仪表盘加载失败', 'error');
    }
}

// ─── Data Source Badge ──────────────────────────────────────
function updateDataSourceBadge(data) {
    const badge = document.getElementById('data-source-badge');
    if (!badge) return;

    if (data.market_overview.uses_real_news || data.market_overview.uses_real_sectors) {
        badge.textContent = '真实数据';
        badge.classList.remove('badge-mock');
        badge.classList.add('badge-real');
    } else {
        badge.textContent = '模拟数据';
        badge.classList.remove('badge-real');
        badge.classList.add('badge-mock');
    }
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

// ─── Workbench Tab ──────────────────────────────────────────
function renderWorkbench(data) {
    renderToday(data.today);
    renderResearchQueue(data.research_queue);
    renderCandidateBoard(data.candidate_board);
    renderLearning(data.learning);
    hideSectionLoading(document.getElementById('dash-panel-workbench'));
}

function renderToday(today) {
    if (!today) return;

    // New Events
    const eventsEl = document.getElementById('today-new-events');
    if (eventsEl) {
        eventsEl.innerHTML = today.new_events && today.new_events.length
            ? today.new_events.map(e => `
                <li>
                    <div class="item-title">${esc(e.summary)}</div>
                    <div class="item-meta">${esc(e.event_type)} &bull; ${new Date(e.created_at).toLocaleString()}</div>
                </li>
            `).join('')
            : '<li class="empty-state">暂无新事件</li>';
    }

    // High Priority Theses
    const hpEl = document.getElementById('today-high-priority');
    if (hpEl) {
        hpEl.innerHTML = today.high_priority_theses && today.high_priority_theses.length
            ? today.high_priority_theses.map(t => `
                <li>
                    <div class="item-title">${esc(t.thesis)}</div>
                    <div class="item-meta">${esc(t.subject_id)} &bull; ${esc(t.event_type)} &bull; 评分: ${t.score ? t.score.toFixed(2) : '--'}</div>
                </li>
            `).join('')
            : '<li class="empty-state">暂无高优先级论题</li>';
    }

    // Abnormal Flows
    const flowsEl = document.getElementById('today-abnormal-flows');
    if (flowsEl) {
        flowsEl.innerHTML = today.abnormal_flows && today.abnormal_flows.length
            ? today.abnormal_flows.map(f => `
                <li class="abnormal-flow-item">
                    <span class="diffusion ${f.diffusion_strength > 0.7 ? 'diffusion-high' : f.diffusion_strength > 0.4 ? 'diffusion-medium' : 'diffusion-low'}"></span>
                    <div class="item-title">${esc(f.symbol)} &bull; ${esc(f.industry)}</div>
                    <div class="item-meta">扩散强度: ${f.diffusion_strength.toFixed(2)} &bull; 涨跌幅: ${f.change_pct.toFixed(2)}%</div>
                </li>
            `).join('')
            : '<li class="empty-state">暂无异常</li>';
    }
}

function renderResearchQueue(queue) {
    if (!queue) return;

    const paEl = document.getElementById('queue-pending-assertions');
    if (paEl) {
        paEl.innerHTML = queue.pending_assertions && queue.pending_assertions.length
            ? queue.pending_assertions.map(a => `
                <li>
                    <div class="item-title">${esc(a.subject)}: ${esc(a.claim)}</div>
                    <div class="item-meta">${esc(a.status)} &bull; ${a.created_at ? new Date(a.created_at).toLocaleString() : '--'}</div>
                </li>
            `).join('')
            : '<li class="empty-state">无待处理断言</li>';
    }

    const meEl = document.getElementById('queue-missing-evidence');
    if (meEl) {
        meEl.innerHTML = queue.missing_evidence && queue.missing_evidence.length
            ? queue.missing_evidence.map(m => `
                <li>
                    <div class="item-title">${esc(m.subject)}</div>
                    <div class="item-meta">需要: ${esc(m.required_evidence_type)}</div>
                </li>
            `).join('')
            : '<li class="empty-state">无缺失证据</li>';
    }

    const mrEl = document.getElementById('queue-mapping-reviews');
    if (mrEl) {
        mrEl.innerHTML = queue.mapping_reviews && queue.mapping_reviews.length
            ? queue.mapping_reviews.map(r => `
                <li>
                    <div class="item-title">${esc(r.subject)}</div>
                    <div class="item-meta">${esc(r.status)} &bull; ${esc(r.reviewer || 'unassigned')}</div>
                </li>
            `).join('')
            : '<li class="empty-state">无待审查</li>';
    }
}

function renderCandidateBoard(board) {
    if (!board) return;
    const el = document.getElementById('candidate-top-candidates');
    if (!el) return;
    el.innerHTML = board.top_candidates && board.top_candidates.length
        ? board.top_candidates.map(c => `
            <div class="candidate-item">
                <div class="candidate-header">
                    <span class="candidate-title">${esc(c.subject)}</span>
                    <span class="readiness-score">准备度: ${c.readiness_score.toFixed(2)}</span>
                </div>
                <div class="candidate-thesis">${esc(c.thesis)}</div>
                ${c.timing_blocker ? `<div class="candidate-blocker">⚠ 时间阻挡: ${esc(c.timing_blocker)}</div>` : ''}
                ${c.trigger_condition ? `<div class="item-meta">触发条件: ${esc(c.trigger_condition)}</div>` : ''}
            </div>
        `).join('')
        : '<div class="empty-state">暂无候选机会</div>';
}

function renderLearning(learning) {
    if (!learning) return;

    const rfEl = document.getElementById('learning-recent-failures');
    if (rfEl) {
        rfEl.innerHTML = learning.recent_failures && learning.recent_failures.length
            ? learning.recent_failures.map(f => `
                <li>
                    <div class="item-title">${esc(f.subject_id)}: ${esc(f.failure_reason)}</div>
                    <div class="item-meta">教训: ${esc(f.lesson)} &bull; ${f.outcome_return != null ? f.outcome_return.toFixed(2) + '%' : ''}</div>
                </li>
            `).join('')
            : '<li class="empty-state">无失败记录</li>';
    }

    const betEl = document.getElementById('learning-best-event-types');
    if (betEl) {
        betEl.innerHTML = learning.best_event_types && learning.best_event_types.length
            ? learning.best_event_types.map(et => `
                <div class="event-type-item">
                    <div class="event-type-name">${esc(et.event_type)}</div>
                    <div class="event-type-stats">超额收益: ${et.avg_excess_return.toFixed(2)}%</div>
                    <div class="event-type-stats">胜率: ${(et.win_rate * 100).toFixed(0)}%</div>
                </div>
            `).join('')
            : '<div class="empty-state">暂无数据</div>';
    }

    const wlEl = document.getElementById('learning-weekly-lessons');
    if (wlEl) {
        wlEl.innerHTML = learning.weekly_lessons && learning.weekly_lessons.length
            ? learning.weekly_lessons.map(l => `
                <li>
                    <div class="item-title">${esc(l.week)}: ${esc(l.key_takeaway)}</div>
                </li>
            `).join('')
            : '<li class="empty-state">无总结</li>';
    }
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
