
/* ============================================================
   AlphaFoundry — Frontend Application Logic
   ============================================================ */

// ─── Theme & i18n Init ───────────────────────────────────────
(function initTheme() {
    const saved = localStorage.getItem('af-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('af-theme', theme);
    document.querySelectorAll('#settings-panel-theme .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.themeVal === theme);
    });
    try { applyChartDefaults(); } catch(e) {}
}

// Global switchers (called from onclick in HTML)
function switchTheme(theme) {
    applyTheme(theme);
}

function switchLang(lang) {
    I18N.setLang(lang);
    document.querySelectorAll('#settings-panel-language .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.lang === lang);
    });
    const sl = document.getElementById('status-lang-label');
    if (sl) sl.textContent = lang === 'zh' ? '中文' : 'EN';
}

// Color scheme
(function initColorScheme() {
    const saved = localStorage.getItem('af-color-scheme') || 'vscode';
    document.documentElement.setAttribute('data-color-scheme', saved);
})();

function applyColorScheme(scheme) {
    document.documentElement.setAttribute('data-color-scheme', scheme);
    localStorage.setItem('af-color-scheme', scheme);
    document.querySelectorAll('#settings-panel-color .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.colorScheme === scheme);
    });
}

function switchColorScheme(scheme) {
    applyColorScheme(scheme);
}

// ─── API Helper ───────────────────────────────────────────────
const API_BASE = '';

async function apiCall(method, url, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(`${API_BASE}${url}`, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.error || err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}

// ─── Toast ────────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast toast-${type}`;
    setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── Chart Instances (for cleanup) ───────────────────────────
let chartPriceVolume = null;
let chartScenarioProb = null;

// ─── Navigation ───────────────────────────────────────────────
function navigateTo(section) {
    document.querySelectorAll('.activity-btn[data-section]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(p => p.classList.remove('active'));
    document.querySelectorAll(`.activity-btn[data-section="${section}"]`).forEach(b => b.classList.add('active'));
    document.getElementById(`section-${section}`).classList.add('active');
    // Load data
    if (section === 'dashboard') loadDashboard();
    if (section === 'signals') loadSignals();
    if (section === 'review') { loadReviewStats(); loadReviewPending(); }
    if (section === 'memory') loadMemoryPage();
    if (section === 'outcomes') loadOutcomes();
    if (section === 'signal-lab') loadSignalLab();
}

// Wait for DOM ready before binding all interactive events
document.addEventListener('DOMContentLoaded', () => {
    // Navigation buttons
    document.querySelectorAll('.activity-btn[data-section]').forEach(btn => {
        btn.addEventListener('click', () => navigateTo(btn.dataset.section));
    });

    // Settings popover toggle
    document.getElementById('btn-settings')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const popover = document.getElementById('settings-popover');
        if (popover) {
            popover.classList.toggle('hidden');
            I18N.applyAll();
        }
    });

    // Close settings popover on outside click
    document.addEventListener('click', (e) => {
        const popover = document.getElementById('settings-popover');
        const btn = document.getElementById('btn-settings');
        if (popover && !popover.contains(e.target) && !btn?.contains(e.target)) {
            popover.classList.add('hidden');
        }
    });

    // Asset analysis button
    document.getElementById('btn-analyze')?.addEventListener('click', analyzeAsset);
    
    // Scenario analysis button
    document.getElementById('btn-generate-scenarios')?.addEventListener('click', generateScenarios);
    
    // Event signal button
    document.getElementById('btn-generate-event-signal')?.addEventListener('click', generateEventSignal);
    
    // Industry chain button
    document.getElementById('btn-load-industry')?.addEventListener('click', loadIndustryChain);
    
    // Review refresh button
    document.getElementById('btn-refresh-review')?.addEventListener('click', () => {
        loadReviewPending();
    });
    
    // Create signal button
    document.getElementById('btn-create-signal')?.addEventListener('click', createSignal);
    
    // Ingest text button
    document.getElementById('btn-ingest')?.addEventListener('click', ingestText);
    
    // Load failures button
    document.getElementById('btn-load-failures')?.addEventListener('click', loadFailures);
    
    // Load event summary button
    document.getElementById('btn-event-summary')?.addEventListener('click', loadEventSummary);

    // Outcomes page: refresh button
    document.getElementById('btn-refresh-outcomes')?.addEventListener('click', loadOutcomes);

    // Outcomes page: event type filter change
    document.getElementById('outcome-event-type-filter')?.addEventListener('change', loadOutcomes);

    // Closed loop page: run button
    document.getElementById('btn-run-closed-loop')?.addEventListener('click', runClosedLoop);

    // Signal Lab events
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchSignalLabTab(btn.dataset.tab));
    });
    document.getElementById('btn-compute-features')?.addEventListener('click', computeFeatures);
    document.getElementById('btn-compute-labels')?.addEventListener('click', computeLabels);
    document.getElementById('btn-run-backtests')?.addEventListener('click', runBacktests);

    // Global search input
    document.getElementById('global-search')?.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        const q = e.target.value.trim();
        if (q.length < 2) {
            document.getElementById('search-results-dropdown')?.classList.add('hidden');
            return;
        }
        searchDebounceTimer = setTimeout(() => globalSearch(q), 300);
    });
    document.getElementById('global-search')?.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('search-results-dropdown')?.classList.add('hidden');
            e.target.blur();
        }
    });
});

// ─── Global Search ────────────────────────────────────────────
let searchDebounceTimer = null;

// Close search dropdown on outside click
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('search-results-dropdown');
    const searchInput = document.getElementById('global-search');
    if (dropdown && !dropdown.contains(e.target) && e.target !== searchInput) {
        dropdown.classList.add('hidden');
    }
});

async function globalSearch(query) {
    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}`);
        renderSearchResults(results, query);
    } catch (e) {
        console.error('Search failed:', e);
    }
}

function renderSearchResults(results, query) {
    const dropdown = document.getElementById('search-results-dropdown');
    if (!dropdown) return;

    // Calculate total across all result groups
    let total = 0;
    const groups = [
        { key: 'symbols', title: '标的' },
        { key: 'event_types', title: '事件类型' },
        { key: 'theses', title: '论题' },
        { key: 'source_docs', title: '源文档' },
        { key: 'failure_memories', title: '失败记忆' },
        { key: 'market_episodes', title: '市场片段' },
        { key: 'signals', title: '信号' },
        { key: 'events', title: '事件' },
        { key: 'outcomes', title: '结果' },
        { key: 'reviews', title: '审核' },
    ];
    groups.forEach(g => total += (results[g.key]?.length || 0));

    if (total === 0) {
        dropdown.innerHTML = `<div class="search-result-group"><div class="search-empty">未找到 "${esc(query)}" 相关结果</div></div>`;
        dropdown.classList.remove('hidden');
        return;
    }

    let html = '';

    // Symbols
    if (results.symbols?.length) {
        html += `<div class="search-result-group"><div class="group-title">标的 (${results.symbols.length})</div>`;
        html += results.symbols.map(s => `
            <div class="search-result-item">
                <div class="result-title">${esc(s.symbol)} — ${esc(s.name || s.display_name)}</div>
                <div class="result-subtitle">${esc(s.industry)} • ${esc(s.asset_type)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Event Types
    if (results.event_types?.length) {
        html += `<div class="search-result-group"><div class="group-title">事件类型 (${results.event_types.length})</div>`;
        html += results.event_types.map(et => `
            <div class="search-result-item">
                <div class="result-title">${esc(et.event_type)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Theses
    if (results.theses?.length) {
        html += `<div class="search-result-group"><div class="group-title">论题 (${results.theses.length})</div>`;
        html += results.theses.map(t => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(t.signal_id)}')">
                <div class="result-title">${esc(t.thesis)}</div>
                <div class="result-subtitle">${esc(t.subject_id)} • score: ${t.score.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Source Docs
    if (results.source_docs?.length) {
        html += `<div class="search-result-group"><div class="group-title">源文档 (${results.source_docs.length})</div>`;
        html += results.source_docs.map(doc => `
            <div class="search-result-item">
                <div class="result-title">${esc(doc.title)}</div>
                <div class="result-subtitle">${esc(doc.source_type)} • ${doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : ''}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Failure Memory
    if (results.failure_memories?.length) {
        html += `<div class="search-result-group"><div class="group-title">失败记忆 (${results.failure_memories.length})</div>`;
        html += results.failure_memories.map(f => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(f.signal_id)}')">
                <div class="result-title">${esc(f.failure_reason || f.subject_id)}</div>
                <div class="result-subtitle">${esc(f.lesson)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Market Episodes
    if (results.market_episodes?.length) {
        html += `<div class="search-result-group"><div class="group-title">市场片段 (${results.market_episodes.length})</div>`;
        html += results.market_episodes.map(me => `
            <div class="search-result-item">
                <div class="result-title">${esc(me.title)}</div>
                <div class="result-subtitle">${esc(me.tags)} • ${me.start_date ? new Date(me.start_date).toLocaleDateString() : ''}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Signals
    if (results.signals?.length) {
        html += `<div class="search-result-group"><div class="group-title">信号 (${results.signals.length})</div>`;
        html += results.signals.map(s => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(s.signal_id)}')">
                <div class="result-title">${esc(s.thesis)}</div>
                <div class="result-subtitle">${esc(s.subject_id)} • ${esc(s.event_type)} • ${I18N.t('dashboard.score')}: ${s.score.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Events
    if (results.events?.length) {
        html += `<div class="search-result-group"><div class="group-title">事件 (${results.events.length})</div>`;
        html += results.events.map(e => `
            <div class="search-result-item">
                <div class="result-title">${esc(e.summary)}</div>
                <div class="result-subtitle">${esc(e.event_type)} • confidence: ${e.confidence.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Outcomes
    if (results.outcomes?.length) {
        html += `<div class="search-result-group"><div class="group-title">结果 (${results.outcomes.length})</div>`;
        html += results.outcomes.map(o => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(o.signal_id)}')">
                <div class="result-title">${esc(o.lesson || o.subject_id)}</div>
                <div class="result-subtitle">${o.outcome_excess_return > 0 ? '+' : ''}${o.outcome_excess_return.toFixed(2)}% 超额收益</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Reviews
    if (results.reviews?.length) {
        html += `<div class="search-result-group"><div class="group-title">审核 (${results.reviews.length})</div>`;
        html += results.reviews.map(r => `
            <div class="search-result-item">
                <div class="result-title">${esc(r.action)} — ${esc(r.entity_type)}/${esc(r.entity_id.substring(0,8))}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
}

function navigateToSignalDetail(signalId) {
    document.getElementById('search-results-dropdown').classList.add('hidden');
    document.getElementById('global-search').value = '';
    showSignalDetail(signalId);
}

// ─── Chart.js Default Theming ─────────────────────────────────
function getChartColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        grid: isDark ? 'rgba(148,163,184,.15)' : 'rgba(0,0,0,.06)',
        text: isDark ? '#94a3b8' : '#64748b',
        blue: '#3182ce',
        orange: '#ed8936',
        green: '#38a169',
        red: '#e53e3e',
        purple: '#805ad5',
        colors: ['#3182ce','#ed8936','#38a169','#e53e3e','#805ad5','#d69e2e','#319795','#b83280'],
    };
}

function applyChartDefaults() {
    const c = getChartColors();
    Chart.defaults.color = c.text;
    Chart.defaults.borderColor = c.grid;
}

applyChartDefaults();

// ═══════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════

async function loadDashboard() {
    try {
        const data = await apiCall('GET', '/api/dashboard');
        
        // Render Today Section
        // New Events
        const newEventsEl = document.getElementById('today-new-events');
        if (data.today.new_events.length) {
            newEventsEl.innerHTML = data.today.new_events.map(e => `
                <li>
                    <div class="item-title">${esc(e.summary)}</div>
                    <div class="item-meta">${esc(e.event_type)} • ${new Date(e.created_at).toLocaleString()}</div>
                </li>
            `).join('');
        } else {
            newEventsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无新事件</li>';
        }

        // High Priority Theses
        const highPriorityEl = document.getElementById('today-high-priority');
        if (data.today.high_priority_theses.length) {
            highPriorityEl.innerHTML = data.today.high_priority_theses.map(t => `
                <li>
                    <div class="item-title">${esc(t.thesis)}</div>
                    <div class="item-meta">${esc(t.subject_id)} • ${esc(t.event_type)} • ${I18N.t('dashboard.score')}: ${t.score.toFixed(2)}</div>
                </li>
            `).join('');
        } else {
            highPriorityEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无高优先级论题</li>';
        }

        // Abnormal Flows
        const abnormalFlowsEl = document.getElementById('today-abnormal-flows');
        if (data.today.abnormal_flows.length) {
            abnormalFlowsEl.innerHTML = data.today.abnormal_flows.map(f => `
                <li class="abnormal-flow-item">
                    <span class="diffusion ${f.diffusion_strength > 0.7 ? 'diffusion-high' : f.diffusion_strength > 0.4 ? 'diffusion-medium' : 'diffusion-low'}"></span>
                    <div class="item-title">${esc(f.symbol)} • ${esc(f.industry)}</div>
                    <div class="item-meta">${I18N.t('dashboard.diffusion')}: ${f.diffusion_strength.toFixed(2)} • ${I18N.t('dashboard.change')}: ${f.change_pct.toFixed(2)}%</div>
                </li>
            `).join('');
        } else {
            abnormalFlowsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无异常</li>';
        }

        // Render Research Queue Section
        // Pending Assertions
        const pendingAssertionsEl = document.getElementById('queue-pending-assertions');
        if (data.research_queue.pending_assertions.length) {
            pendingAssertionsEl.innerHTML = data.research_queue.pending_assertions.map(a => `
                <li>
                    <div class="item-title">${esc(a.subject)}: ${esc(a.claim)}</div>
                    <div class="item-meta">${esc(a.status)} • ${new Date(a.created_at).toLocaleString()}</div>
                </li>
            `).join('');
        } else {
            pendingAssertionsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无待处理断言</li>';
        }

        // Missing Evidence
        const missingEvidenceEl = document.getElementById('queue-missing-evidence');
        if (data.research_queue.missing_evidence.length) {
            missingEvidenceEl.innerHTML = data.research_queue.missing_evidence.map(m => `
                <li>
                    <div class="item-title">${esc(m.subject)}</div>
                    <div class="item-meta">${I18N.t('dashboard.required_evidence')}: ${esc(m.required_evidence_type)}</div>
                </li>
            `).join('');
        } else {
            missingEvidenceEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无缺失证据</li>';
        }

        // Mapping Reviews
        const mappingReviewsEl = document.getElementById('queue-mapping-reviews');
        if (data.research_queue.mapping_reviews.length) {
            mappingReviewsEl.innerHTML = data.research_queue.mapping_reviews.map(r => `
                <li>
                    <div class="item-title">${esc(r.subject)}</div>
                    <div class="item-meta">${esc(r.status)} • ${esc(r.reviewer || 'unassigned')}</div>
                </li>
            `).join('');
        } else {
            mappingReviewsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无待审查</li>';
        }

        // Render Candidate Board Section
        const candidatesEl = document.getElementById('candidate-top-candidates');
        if (data.candidate_board.top_candidates.length) {
            candidatesEl.innerHTML = data.candidate_board.top_candidates.map(c => `
                <div class="candidate-item">
                    <div class="candidate-header">
                        <span class="candidate-title">${esc(c.subject)}</span>
                        <span class="readiness-score">${I18N.t('dashboard.readiness')}: ${c.readiness_score.toFixed(2)}</span>
                    </div>
                    <div class="candidate-thesis">${esc(c.thesis)}</div>
                    ${c.timing_blocker ? `<div class="candidate-blocker">⚠️ ${I18N.t('dashboard.timing_blocker')}: ${esc(c.timing_blocker)}</div>` : ''}
                    ${c.trigger_condition ? `<div class="item-meta">${I18N.t('dashboard.trigger')}: ${esc(c.trigger_condition)}</div>` : ''}
                </div>
            `).join('');
        } else {
            candidatesEl.innerHTML = '<div class="empty-state" data-i18n="dashboard.no_data">暂无候选机会</div>';
        }

        // Render Learning Section
        // Recent Failures
        const recentFailuresEl = document.getElementById('learning-recent-failures');
        if (data.learning.recent_failures.length) {
            recentFailuresEl.innerHTML = data.learning.recent_failures.map(f => `
                <li>
                    <div class="item-title">${esc(f.subject_id)}: ${esc(f.failure_reason)}</div>
                    <div class="item-meta">${I18N.t('dashboard.lesson')}: ${esc(f.lesson)} • ${f.outcome_return ? f.outcome_return.toFixed(2) + '%' : ''}</div>
                </li>
            `).join('');
        } else {
            recentFailuresEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无失败记录</li>';
        }

        // Best Event Types
        const bestEventTypesEl = document.getElementById('learning-best-event-types');
        if (data.learning.best_event_types.length) {
            bestEventTypesEl.innerHTML = data.learning.best_event_types.map(et => `
                <div class="event-type-item">
                    <div class="event-type-name">${esc(et.event_type)}</div>
                    <div class="event-type-stats">${I18N.t('dashboard.avg_excess')}: ${et.avg_excess_return.toFixed(2)}%</div>
                    <div class="event-type-stats">${I18N.t('dashboard.win_rate')}: ${(et.win_rate * 100).toFixed(0)}%</div>
                </div>
            `).join('');
        } else {
            bestEventTypesEl.innerHTML = '<div class="empty-state" data-i18n="dashboard.no_data">暂无数据</div>';
        }

        // Weekly Lessons
        const weeklyLessonsEl = document.getElementById('learning-weekly-lessons');
        if (data.learning.weekly_lessons.length) {
            weeklyLessonsEl.innerHTML = data.learning.weekly_lessons.map(l => `
                <li>
                    <div class="item-title">${esc(l.week)}: ${esc(l.key_takeaway)}</div>
                </li>
            `).join('');
        } else {
            weeklyLessonsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无总结</li>';
        }

        // Refresh i18n
        I18N.applyAll();
    } catch (e) {
        console.error('Failed to load dashboard:', e);
        toast(I18N.t('toast.load_dashboard_failed'), 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Asset Analysis
// ═══════════════════════════════════════════════════════════════

async function analyzeAsset() {
    const code = document.getElementById('asset-code').value.trim();
    if (!code) return toast(I18N.t('toast.enter_asset_code'), 'error');

    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/assets/analyze', {
            canonical_id: code,
        });
        renderAssetResult(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.analyze_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderAssetResult(data) {
    // ─── Valuation
    const valCards = document.getElementById('valuation-cards');
    const v = data.valuation || {};
    const valMetrics = [
        { label: I18N.t('metric.pe_ttm'), value: v.pe_ttm ?? v.PE ?? '—' },
        { label: I18N.t('metric.pb'), value: v.pb ?? v.PB ?? '—' },
        { label: I18N.t('metric.ps'), value: v.ps ?? v.PS ?? '—' },
        { label: I18N.t('metric.ev_ebitda'), value: v.ev_ebitda ?? v.EV_EBITDA ?? '—' },
    ];
    valCards.innerHTML = valMetrics.map(m => `
        <div class="info-item"><div class="info-label">${m.label}</div><div class="info-value">${fmtNum(m.value)}</div></div>
    `).join('');

    // ─── Price/Volume Chart
    renderPriceVolumeChart(data.price_volume || {});

    // ─── Financial
    const finWrap = document.getElementById('financial-table');
    const f = data.financial || {};
    const finRows = [
        [I18N.t('metric.revenue'), f.revenue ?? f.Revenue],
        [I18N.t('metric.net_profit'), f.net_profit ?? f.NetProfit],
        [I18N.t('metric.eps'), f.eps ?? f.EPS],
        [I18N.t('metric.roe'), f.roe ?? f.ROE],
    ].filter(r => r[1] !== undefined);

    if (finRows.length) {
        finWrap.innerHTML = `<table><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>${finRows.map(r =>
            `<tr><td>${r[0]}</td><td>${fmtFinancial(r[1])}</td></tr>`
        ).join('')}</tbody></table>`;
    } else {
        finWrap.innerHTML = '<p class="empty-state">' + I18N.t('asset.no_financial') + '</p>';
    }

    // ─── Fund Flow
    const ffWrap = document.getElementById('fund-flow-info');
    const ff = data.fund_flow || {};
    const ffItems = [
        { label: I18N.t('metric.main_net_inflow'), key: 'main_net_inflow' },
        { label: I18N.t('metric.institutional_holding'), key: 'institutional_holding' },
        { label: I18N.t('metric.northbound_holding'), key: 'northbound_holding' },
    ].filter(i => ff[i.key] !== undefined);
    ffWrap.innerHTML = ffItems.length ? ffItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(ff[i.key])}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_fund_flow') + '</p>';

    // ─── Shareholder
    const shWrap = document.getElementById('shareholder-info');
    const sh = data.shareholder || {};
    const shItems = Object.entries(sh).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    shWrap.innerHTML = shItems.length ? shItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_shareholder') + '</p>';

    // ─── Industry
    const indWrap = document.getElementById('industry-info');
    const ind = data.industry || {};
    const indItems = Object.entries(ind).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    indWrap.innerHTML = indItems.length ? indItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_industry') + '</p>';

    // ─── Event Impact
    const evList = document.getElementById('event-impact-list');
    const events = data.event_impact || [];
    evList.innerHTML = events.length ? events.map(e => `<li>${esc(e)}</li>`).join('') : '<li class="empty-state">' + I18N.t('asset.no_event_impact') + '</li>';

    // ─── Macro
    const macroWrap = document.getElementById('macro-info');
    const macro = data.macro_exposure || {};
    const macroItems = Object.entries(macro).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    macroWrap.innerHTML = macroItems.length ? macroItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_macro') + '</p>';
}

function renderPriceVolumeChart(pv) {
    const colors = getChartColors();
    if (chartPriceVolume) chartPriceVolume.destroy();

    const labels = pv.dates || [];
    const close = pv.close_price || [];
    const ma5 = pv.ma5 || [];
    const ma20 = pv.ma20 || [];
    const ma60 = pv.ma60 || [];

    const ctx = document.getElementById('chart-price-volume').getContext('2d');
    chartPriceVolume = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: I18N.t('metric.close_price'), data: close, borderColor: colors.blue, backgroundColor: 'rgba(49,130,206,.1)', fill: true, tension: 0.3, pointRadius: 2 },
                { label: 'MA5', data: ma5, borderColor: colors.orange, borderDash: [4,4], pointRadius: 0 },
                { label: 'MA20', data: ma20, borderColor: colors.green, borderDash: [6,3], pointRadius: 0 },
                { label: 'MA60', data: ma60, borderColor: colors.red, borderDash: [8,4], pointRadius: 0 },
            ].filter(d => d.data.length > 0)
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: { x: { grid: { color: colors.grid } }, y: { grid: { color: colors.grid } } }
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// Scenario Analysis
// ═══════════════════════════════════════════════════════════════

async function generateScenarios() {
    const topic = document.getElementById('scenario-topic').value.trim();
    const subjectsStr = document.getElementById('scenario-subjects').value.trim();
    const subject_ids = subjectsStr ? subjectsStr.split(',').map(s => s.trim()).filter(s => s) : [];
    if (!topic) return toast(I18N.t('toast.enter_topic'), 'error');

    const loading = document.getElementById('scenario-loading');
    const result = document.getElementById('scenario-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/scenarios/generate', { topic, subject_ids });
        renderScenarioResult(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.scenario_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderScenarioResult(data) {
    const hypotheses = data.hypotheses || [];

    // ─── Probability Chart
    if (chartScenarioProb) chartScenarioProb.destroy();
    const colors = getChartColors();
    if (hypotheses.length) {
        const ctx = document.getElementById('chart-scenario-prob').getContext('2d');
        chartScenarioProb = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: hypotheses.map(h => h.title),
                datasets: [{ data: hypotheses.map(h => (h.probability * 100).toFixed(1)), backgroundColor: colors.colors.slice(0, hypotheses.length) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } } } }
        });
    }

    // ─── Normalization Check
    const checkEl = document.getElementById('normalization-check');
    const sum = hypotheses.reduce((acc, h) => acc + (h.probability || 0), 0);
    if (data.normalization_check?.ok || Math.abs(sum - 1) < 0.01) {
        checkEl.className = 'check-indicator ok';
        checkEl.textContent = '概率归一化检查通过';
    } else {
        checkEl.className = 'check-indicator warn';
        checkEl.textContent = '概率归一化检查未通过';
    }

    // ─── Scenario Cards
    const cardsEl = document.getElementById('scenario-cards');
    cardsEl.innerHTML = hypotheses.map(h => `
        <div class="scenario-card">
            <div class="sc-header">
                <span class="sc-title">${esc(h.title)}</span>
                <span class="sc-prob">${(h.probability * 100).toFixed(1)}%</span>
            </div>
            ${h.assumptions?.length ? `<div class="sc-section"><h4>假设</h4><ul>${h.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div>` : ''}
            ${h.key_triggers?.length ? `<div class="sc-section"><h4>触发条件</h4><ul>${h.key_triggers.map(t => `<li>${esc(t)}</li>`).join('')}</ul></div>` : ''}
            ${h.invalidation_signals?.length ? `<div class="sc-section"><h4>失效信号</h4><ul>${h.invalidation_signals.map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
        </div>
    `).join('');

    // ─── Residual Uncertainty
    const resList = document.getElementById('residual-list');
    const residual = data.residual_uncertainty || [];
    resList.innerHTML = residual.length ? residual.map(r => `<li>${esc(r)}</li>`).join('') : '<li class="empty-state">无</li>';
}

// ═══════════════════════════════════════════════════════════════
// Event Signal
// ═══════════════════════════════════════════════════════════════

async function generateEventSignal() {
    const event = {
        event_id: crypto.randomUUID(),
        title: document.getElementById('event-title').value.trim(),
        type: document.getElementById('event-type').value,
        timestamp: document.getElementById('event-date').value || new Date().toISOString(),
    };
    if (!event.title) return toast(I18N.t('toast.enter_event_type'), 'error');

    try {
        const result = await apiCall('POST', '/api/pipeline/event-signal', { event });
        const signalId = result.signal_id;
        toast('事件信号生成成功', 'success');
        loadEventSignals();
        
        // Get and show Timing decision
        if (signalId) {
            try {
                const timingDecision = await apiCall('POST', `/api/timing/evaluate-signal/${signalId}`);
                renderTimingDecision(timingDecision);
                document.getElementById('timing-decision-container')?.classList.remove('hidden');
            } catch (e) {
                console.warn('Failed to get timing decision:', e);
            }
        }
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadEventSignals() {
    // TODO: load real event signals from API
    const mockSignals = [
        { signal_id: '1', thesis: '某公司财报超预期，短期看涨', score: 0.75, confidence: 0.8, diffusion_stage: 'early', validation_status: 'pending_backtest' },
        { signal_id: '2', thesis: '政策利好新能源，长期看好', score: 0.8, confidence: 0.7, diffusion_stage: 'mid', validation_status: 'validated' },
    ];
    const listEl = document.getElementById('signal-cards');
    listEl.innerHTML = mockSignals.map(s => `
        <div class="signal-card">
            <div class="signal-header">
                <span class="status-badge status-${s.validation_status}">${s.validation_status}</span>
            </div>
            <div class="signal-thesis">${esc(s.thesis)}</div>
            <div class="signal-meta">
                <span>分数: ${s.score.toFixed(2)}</span>
                <span>置信度: ${s.confidence.toFixed(2)}</span>
                <span>传播阶段: ${s.diffusion_stage}</span>
            </div>
        </div>
    `).join('');
}

function renderTimingDecision(decision) {
    const container = document.getElementById('timing-decision-card');
    const blockersHtml = decision.blockers.length ? `
        <div class="timing-section">
            <h4>阻止因素</h4>
            <ul class="timing-blockers">
                ${decision.blockers.map(b => `<li>${esc(b)}</li>`).join('')}
            </ul>
        </div>
    ` : '';
    
    container.innerHTML = `
        <div class="timing-header">
            <span class="timing-badge timing-${decision.action}">${esc(decision.action)}</span>
            <span class="timing-regime">市场状态: ${esc(decision.market_regime)}</span>
        </div>
        <div class="timing-readiness">
            <div class="timing-readiness-label">就绪度: ${(decision.readiness_score * 100).toFixed(1)}%</div>
            <div class="timing-readiness-bar">
                <div class="timing-readiness-fill" style="width: ${decision.readiness_score * 100}%"></div>
            </div>
        </div>
        ${blockersHtml}
        ${decision.rationale.length ? `
        <div class="timing-section">
            <h4>逻辑</h4>
            <ul>
                ${decision.rationale.map(r => `<li>${esc(r)}</li>`).join('')}
            </ul>
        </div>
        ` : ''}
    `;
}

// ═══════════════════════════════════════════════════════════════
// Industry Chain
// ═══════════════════════════════════════════════════════════════

async function loadIndustryChain() {
    const industry = document.getElementById('industry-select').value;
    try {
        const data = await apiCall('GET', `/api/graph/industry-chain/${encodeURIComponent(industry)}`);
        renderIndustryGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadPropagationPath() {
    const eventId = document.getElementById('event-id').value.trim();
    if (!eventId) return toast('请输入事件 ID', 'error');
    try {
        const data = await apiCall('GET', `/api/graph/propagation/${encodeURIComponent(eventId)}`);
        renderPropagationGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderIndustryGraph(data) {
    const container = document.getElementById('industry-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;

    const mockNodes = [
        { id: 'up1', label: '上游1', group: 'upstream' },
        { id: 'up2', label: '上游2', group: 'upstream' },
        { id: 'mid1', label: '中游1', group: 'midstream' },
        { id: 'mid2', label: '中游2', group: 'midstream' },
        { id: 'down1', label: '下游1', group: 'downstream' },
        { id: 'down2', label: '下游2', group: 'downstream' },
    ];
    const mockLinks = [
        { source: 'up1', target: 'mid1', label: '供应' },
        { source: 'up2', target: 'mid1', label: '供应' },
        { source: 'mid1', target: 'down1', label: '供应' },
        { source: 'mid2', target: 'down1', label: '替代' },
        { source: 'mid2', target: 'down2', label: '依赖' },
    ];

    const nodes = data.nodes?.length ? data.nodes : mockNodes;
    const links = data.edges?.length ? data.edges : mockLinks;

    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

    const color = d3.scaleOrdinal()
        .domain(['upstream', 'midstream', 'downstream'])
        .range(['#e53e3e', '#3182ce', '#38a169']);

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g').selectAll('line').data(links).enter().append('line')
        .attr('stroke', '#94a3b8').attr('stroke-width', 2);

    const linkLabel = svg.append('g').selectAll('text').data(links).enter().append('text')
        .attr('font-size', '10px').attr('fill', '#64748b').text(d => d.label);

    const node = svg.append('g').selectAll('circle').data(nodes).enter().append('circle')
        .attr('r', 12).attr('fill', d => color(d.group)).call(drag(simulation));

    const nodeLabel = svg.append('g').selectAll('text').data(nodes).enter().append('text')
        .attr('font-size', '12px').attr('fill', '#1a202c').text(d => d.label);

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        linkLabel.attr('x', d => (d.source.x + d.target.x) / 2).attr('y', d => (d.source.y + d.target.y) / 2);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        nodeLabel.attr('x', d => d.x + 16).attr('y', d => d.y + 4);
    });

    function drag(simulation) {
        function dragstarted(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        function dragged(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
    }
}

function renderPropagationGraph(data) {
    const container = document.getElementById('propagation-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width / 2).attr('y', height / 2).attr('text-anchor', 'middle').attr('fill', '#64748b').text('传播路径可视化');
}

// ═══════════════════════════════════════════════════════════════
// Review Queue
// ═══════════════════════════════════════════════════════════════

async function loadReviewStats() {
    try {
        const stats = await apiCall('GET', '/api/review/stats');
        const wrap = document.getElementById('review-stats');
        wrap.innerHTML = `
            <div class="stat-card pending"><div class="stat-value">${stats.pending_assertions ?? 0}</div><div class="stat-label">待审核</div></div>
            <div class="stat-card"><div class="stat-value" style="border-top-color:var(--success)">${stats.approved_assertions ?? 0}</div><div class="stat-label">已批准</div></div>
            <div class="stat-card"><div class="stat-value" style="border-top-color:var(--danger)">${stats.rejected_assertions ?? 0}</div><div class="stat-label">已拒绝</div></div>
        `;
        // Also update dashboard stat
        const statReview = document.getElementById('stat-review');
        if (statReview) statReview.textContent = stats.pending_assertions ?? 0;
    } catch (e) {
        console.error('Failed to load review stats:', e);
    }
}

async function loadReviewPending() {
    try {
        const items = await apiCall('GET', '/api/review/pending');
        renderReviewTable(items);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderReviewTable(items) {
    const wrap = document.getElementById('review-table');
    if (!items.length) {
        wrap.innerHTML = '<p class="empty-state">暂无待审核项</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>谓词</th><th>对象</th><th>置信度</th><th>来源</th><th>操作</th></tr></thead>
        <tbody>${items.map(i => `
            <tr>
                <td title="${esc(i.assertion_id)}">${esc(i.assertion_id.substring(0, 8))}</td>
                <td>${esc(i.subject_entity_id || '—')}</td>
                <td>${esc(i.predicate)}</td>
                <td>${esc(i.object_value || '—')}</td>
                <td>${i.confidence.toFixed(2)}</td>
                <td>${esc(i.source_doc_id?.substring(0, 8) || '—')}</td>
                <td class="actions">
                    <button class="btn-sm btn-approve" onclick="approveItem('${esc(i.assertion_id)}')">批准</button>
                    <button class="btn-sm btn-reject" onclick="rejectItem('${esc(i.assertion_id)}')">拒绝</button>
                </td>
            </tr>
        `).join('')}</tbody>
    </table>`;
}

async function approveItem(id) {
    try {
        await apiCall('POST', `/api/review/approve/${id}`);
        toast('已批准', 'success');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function rejectItem(id) {
    try {
        await apiCall('POST', `/api/review/reject/${id}`);
        toast('已拒绝', 'success');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Signals Management
// ═══════════════════════════════════════════════════════════════

async function createSignal() {
    const body = {
        subject_id: document.getElementById('sig-subject-id').value.trim(),
        thesis: document.getElementById('sig-thesis').value.trim(),
        score: parseFloat(document.getElementById('sig-score').value),
        confidence: parseFloat(document.getElementById('sig-confidence').value),
        horizon: document.getElementById('sig-horizon').value,
    };
    if (!body.subject_id || !body.thesis) return toast(I18N.t('toast.enter_asset_code'), 'error');

    try {
        await apiCall('POST', '/api/signals/create', body);
        toast(I18N.t('toast.signal_created'), 'success');
        document.getElementById('sig-thesis').value = '';
        loadSignals();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadSignals() {
    try {
        const signals = await apiCall('GET', '/api/signals/list');
        renderSignalsTable(signals);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderSignalsTable(signals) {
    const wrap = document.getElementById('signals-table');
    if (!signals.length) {
        wrap.innerHTML = '<p class="empty-state">暂无信号</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>论点</th><th>预测期</th><th>分数</th><th>置信度</th><th>择时决策</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${signals.map(s => `
            <tr>
                <td title="${esc(s.signal_id)}"><a href="javascript:void(0)" onclick="showSignalDetail('${esc(s.signal_id)}')">${esc(s.signal_id.substring(0, 8))}</a></td>
                <td>${esc(s.subject_id)}</td>
                <td>${esc(s.thesis)}</td>
                <td>${esc(s.horizon)}</td>
                <td>${s.score.toFixed(2)}</td>
                <td>${s.confidence.toFixed(2)}</td>
                <td>${s.latest_timing_action ? `<span class="timing-badge timing-${s.latest_timing_action}">${esc(s.latest_timing_action)}</span>` : '—'}</td>
                <td><span class="status-badge status-${s.status || 'pending_backtest'}">${esc(s.status || 'pending_backtest')}</span></td>
                <td class="actions">
                    <button class="btn-sm btn-detail" onclick="showSignalDetail('${esc(s.signal_id)}')">详情</button>
                    <button class="btn-sm btn-validate" onclick="validateSignal('${esc(s.signal_id)}')">验证</button>
                    <button class="btn-sm btn-promote" onclick="promoteSignal('${esc(s.signal_id)}')">升级</button>
                </td>
            </tr>
        `).join('')}</tbody>
    </table>`;
}

async function validateSignal(id) {
    try {
        const result = await apiCall('POST', `/api/signals/validate/${id}`);
        toast(`验证完成，综合分数: ${result.composite_score?.toFixed(3) ?? '—'}`, 'success');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function promoteSignal(id) {
    try {
        const result = await apiCall('POST', `/api/signals/promote/${id}?new_status=candidate`);
        toast(result.success ? `已升级至 ${result.new_status}` : (result.message || '升级失败'), result.success ? 'success' : 'error');
        loadSignals();
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Ingest
// ═══════════════════════════════════════════════════════════════

async function ingestText() {
    const text = document.getElementById('ingest-text').value.trim();
    if (!text) return toast('请输入文本内容', 'error');

    const loading = document.getElementById('ingest-loading');
    const result = document.getElementById('ingest-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/ingest/text', {
            text,
            source_type: document.getElementById('ingest-source-type').value,
            source_name: document.getElementById('ingest-source-name').value.trim() || 'unknown',
            title: document.getElementById('ingest-title').value.trim() || undefined,
        });
        renderIngestResult(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.ingest_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderIngestResult(data) {

    const wrap = document.getElementById('ingest-result');
    wrap.innerHTML = `
        <div class="ingest-summary">
            <h3>摄入成功 — ${esc(data.title || data.doc_id)}</h3>
            <div class="ingest-stats">
                <div class="ingest-stat"><div class="num">${data.assertions_extracted ?? 0}</div><div class="lbl">提取断言</div></div>
                <div class="ingest-stat"><div class="num">${data.assertions_approved ?? 0}</div><div class="lbl">已批准</div></div>
                <div class="ingest-stat"><div class="num">${data.assertions_pending ?? 0}</div><div class="lbl">待审核</div></div>
                <div class="ingest-stat"><div class="num">${data.events_extracted ?? 0}</div><div class="lbl">提取事件</div></div>
                <div class="ingest-stat"><div class="num">${data.events_approved ?? 0}</div><div class="lbl">事件已批准</div></div>
            </div>
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════
// Memory & Learning
// ═══════════════════════════════════════════════════════════════

function loadMemoryPage() {
    loadEpisodes();
    loadStrategies();
    loadFailures();
}

async function loadEpisodes() {
    const filterEl = document.getElementById('episode-event-type-filter');
    const eventType = filterEl ? filterEl.value.trim() : '';
    const params = new URLSearchParams();
    if (eventType) params.append('event_type', eventType);
    
    try {
        const episodes = await apiCall('GET', `/api/memory/episodes?${params.toString()}`);
        const container = document.getElementById('market-episode-list');
        if (!episodes.length) {
            container.innerHTML = '<p class="empty-state">暂无事件记忆</p>';
            return;
        }
        container.innerHTML = episodes.map(ep => {
            const returnClass = ep.outcome_return > 0 ? 'positive' : 'negative';
            const returnSign = ep.outcome_return > 0 ? '+' : '';
            return `
                <div class="memory-card episode-card">
                    <div class="card-header-row">
                        <span class="badge event-type-badge">${esc(ep.event_type)}</span>
                        <span class="badge regime-badge">${esc(ep.market_regime)}</span>
                        <span class="return ${returnClass}">${returnSign}${ep.outcome_return.toFixed(2)}%</span>
                    </div>
                    ${ep.lesson ? `<div class="episode-lesson"><strong>经验教训：</strong>${esc(ep.lesson)}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadStrategies() {
    const sfEl = document.getElementById('strategy-signal-filter');
    const signalFamily = sfEl ? sfEl.value.trim() : '';
    const mrEl = document.getElementById('strategy-regime-filter');
    const marketRegime = mrEl ? mrEl.value.trim() : '';
    const params = new URLSearchParams();
    if (signalFamily) params.append('signal_family', signalFamily);
    if (marketRegime) params.append('market_regime', marketRegime);
    
    try {
        const strategies = await apiCall('GET', `/api/memory/strategies?${params.toString()}`);
        const container = document.getElementById('strategy-memory-list');
        if (!strategies.length) {
            container.innerHTML = '<p class="empty-state">暂无策略记忆</p>';
            return;
        }
        container.innerHTML = strategies.map(str => `
            <div class="strategy-card">
                <div class="strategy-header">
                    <span class="badge">${esc(str.signal_family)}</span>
                    <span class="badge">${esc(str.market_regime)}</span>
                    <span class="sample-size">样本量: ${str.sample_size}</span>
                </div>
                <div class="metric-row">
                    <div class="metric">
                        <div class="metric-label">胜率</div>
                        <div class="win-rate-bar">
                            <div class="win-rate-fill" style="width: ${(str.win_rate * 100)}%"></div>
                            <span class="win-rate-text">${(str.win_rate * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">夏普比率</div>
                        <div class="metric-value">${str.sharpe_ratio.toFixed(2)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">平均超额收益</div>
                        <div class="metric-value ${str.average_excess_return > 0 ? 'positive' : 'negative'}">${str.average_excess_return.toFixed(2)}%</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadFailures() {
    const failureType = document.getElementById('failure-type-filter').value.trim();
    const sourceId = document.getElementById('failure-source-filter').value.trim();
    const params = new URLSearchParams();
    if (failureType) params.append('failure_type', failureType);
    if (sourceId) params.append('source_id', sourceId);
    
    try {
        const failures = await apiCall('GET', `/api/memory/failures?${params.toString()}`);
        const container = document.getElementById('failure-memory-list');
        if (!failures.length) {
            container.innerHTML = '<p class="empty-state">暂无失败记忆</p>';
            return;
        }
        container.innerHTML = failures.map(fail => `
            <div class="failure-card">
                <div class="failure-header">
                    <span class="failure-badge failure-type-${fail.failure_type}">${esc(fail.failure_type)}</span>
                    <span class="failure-source">来源: ${esc(fail.source_id.substring(0, 8))}...</span>
                </div>
                <div class="failure-root"><strong>根本原因：</strong>${esc(fail.root_cause)}</div>
                <div class="failure-corrective"><strong>修正措施：</strong>${esc(fail.corrective_action)}</div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadEventSummary() {
    const eventType = document.getElementById('event-type-summary').value.trim();
    if (!eventType) return toast(I18N.t('toast.enter_event_type'), 'error');
    
    try {
        const summary = await apiCall('GET', `/api/memory/summarize/${encodeURIComponent(eventType)}`);
        const container = document.getElementById('event-summary-cards');
        container.innerHTML = `
            <div class="stat-card"><div class="stat-value">${summary.total_episodes}</div><div class="stat-label">总样本数</div></div>
            <div class="stat-card"><div class="stat-value ${summary.average_return > 0 ? 'positive' : 'negative'}">${summary.average_return.toFixed(2)}%</div><div class="stat-label">平均收益</div></div>
            <div class="stat-card"><div class="stat-value ${summary.average_excess_return > 0 ? 'positive' : 'negative'}">${summary.average_excess_return.toFixed(2)}%</div><div class="stat-label">平均超额收益</div></div>
            <div class="stat-card"><div class="stat-value">${(summary.positive_rate * 100).toFixed(1)}%</div><div class="stat-label">胜率</div></div>
        `;
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Signal Detail View
// ═══════════════════════════════════════════════════════════════

async function showSignalDetail(signalId) {
    // Hide all sections, show detail
    document.querySelectorAll('.content-section').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.activity-btn[data-section]').forEach(b => b.classList.remove('active'));

    let detailSection = document.getElementById('section-signal-detail');
    if (!detailSection) {
        detailSection = document.createElement('section');
        detailSection.id = 'section-signal-detail';
        detailSection.className = 'content-section active';
        document.querySelector('.main-content').appendChild(detailSection);
    }
    detailSection.classList.add('active');
    detailSection.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const data = await apiCall('GET', `/api/signals/${encodeURIComponent(signalId)}/detail`);
        renderSignalDetail(data, detailSection);
    } catch (e) {
        detailSection.innerHTML = `<div class="error-state">加载失败: ${esc(e.message)}</div>`;
    }
}

function renderSignalDetail(data, container) {
    const s = data.signal || {};
    const timing = data.timing;
    const outcome = data.outcome;
    const event = data.event;
    const auditTrail = data.audit_trail || [];

    let html = `
        <div class="detail-header">
            <button class="btn-back" onclick="navigateTo('signals')">← 返回信号列表</button>
            <h2 class="section-title">信号详情</h2>
        </div>

        <div class="detail-grid">
            <!-- 信号基本信息 -->
            <div class="card detail-card">
                <h3>基本信息</h3>
                <div class="detail-field"><span class="detail-label">ID</span><span class="detail-value">${esc(s.signal_id)}</span></div>
                <div class="detail-field"><span class="detail-label">主体</span><span class="detail-value">${esc(s.subject_id)}</span></div>
                <div class="detail-field"><span class="detail-label">论点</span><span class="detail-value">${esc(s.thesis)}</span></div>
                <div class="detail-field"><span class="detail-label">预测期</span><span class="detail-value">${esc(s.horizon)}</span></div>
                <div class="detail-field"><span class="detail-label">分数</span><span class="detail-value">${s.score?.toFixed(3) ?? '—'}</span></div>
                <div class="detail-field"><span class="detail-label">置信度</span><span class="detail-value">${s.confidence?.toFixed(3) ?? '—'}</span></div>
                <div class="detail-field"><span class="detail-label">状态</span><span class="detail-value"><span class="status-badge status-${s.status}">${esc(s.status)}</span></span></div>
                ${s.event_type ? `<div class="detail-field"><span class="detail-label">事件类型</span><span class="detail-value">${esc(s.event_type)}</span></div>` : ''}
                ${s.diffusion_stage ? `<div class="detail-field"><span class="detail-label">传播阶段</span><span class="detail-value">${esc(s.diffusion_stage)}</span></div>` : ''}
                ${s.market_regime ? `<div class="detail-field"><span class="detail-label">市场状态</span><span class="detail-value">${esc(s.market_regime)}</span></div>` : ''}
            </div>

            <!-- 择时建议 -->
            <div class="card detail-card">
                <h3>择时建议</h3>
                ${timing ? `
                    <div class="detail-field"><span class="detail-label">决策</span><span class="detail-value"><span class="timing-badge timing-${timing.action}">${esc(timing.action)}</span></span></div>
                    <div class="detail-field"><span class="detail-label">就绪度</span><span class="detail-value">${(timing.readiness_score * 100).toFixed(1)}%</span></div>
                    <div class="detail-field"><span class="detail-label">市场状态</span><span class="detail-value">${esc(timing.market_regime)}</span></div>
                    ${timing.blockers?.length ? `<div class="detail-field"><span class="detail-label">阻止因素</span><span class="detail-value"><ul>${timing.blockers.map(b => `<li>${esc(b)}</li>`).join('')}</ul></span></div>` : ''}
                    ${timing.rationale?.length ? `<div class="detail-field"><span class="detail-label">逻辑</span><span class="detail-value"><ul>${timing.rationale.map(r => `<li>${esc(r)}</li>`).join('')}</ul></span></div>` : ''}
                ` : '<p class="empty-state">暂无择时建议</p>'}
            </div>

            <!-- 关联事件 -->
            <div class="card detail-card">
                <h3>关联事件</h3>
                ${event ? `
                    <div class="detail-field"><span class="detail-label">事件ID</span><span class="detail-value">${esc(event.event_id)}</span></div>
                    <div class="detail-field"><span class="detail-label">类型</span><span class="detail-value">${esc(event.event_type)}</span></div>
                    <div class="detail-field"><span class="detail-label">摘要</span><span class="detail-value">${esc(event.summary)}</span></div>
                    <div class="detail-field"><span class="detail-label">方向</span><span class="detail-value">${esc(event.impact_direction)}</span></div>
                    <div class="detail-field"><span class="detail-label">置信度</span><span class="detail-value">${event.confidence?.toFixed(2) ?? '—'}</span></div>
                ` : '<p class="empty-state">无关联事件</p>'}
            </div>

            <!-- 关联 Outcome -->
            <div class="card detail-card">
                <h3>结果评估</h3>
                ${outcome ? `
                    <div class="detail-field"><span class="detail-label">收益</span><span class="detail-value ${outcome.outcome_return > 0 ? 'positive' : 'negative'}">${outcome.outcome_return > 0 ? '+' : ''}${outcome.outcome_return?.toFixed(2)}%</span></div>
                    <div class="detail-field"><span class="detail-label">超额收益</span><span class="detail-value ${outcome.outcome_excess_return > 0 ? 'positive' : 'negative'}">${outcome.outcome_excess_return > 0 ? '+' : ''}${outcome.outcome_excess_return?.toFixed(2)}%</span></div>
                    <div class="detail-field"><span class="detail-label">最大回撤</span><span class="detail-value">${outcome.max_drawdown?.toFixed(2) ?? '—'}%</span></div>
                    ${outcome.lesson ? `<div class="detail-field"><span class="detail-label">经验教训</span><span class="detail-value">${esc(outcome.lesson)}</span></div>` : ''}
                ` : '<p class="empty-state">暂无结果评估</p>'}
            </div>
        </div>

        <!-- 审计轨迹 -->
        <div class="card detail-card" style="margin-top: 16px;">
            <h3>审计轨迹</h3>
            <div id="audit-trail-container">
                ${auditTrail.length ? renderAuditTrailTimeline(auditTrail) : '<p class="empty-state">暂无审计记录</p>'}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function renderAuditTrailTimeline(trail) {
    if (!trail.length) return '<p class="empty-state">暂无审计记录</p>';
    return `<div class="audit-timeline">${trail.map(entry => `
        <div class="audit-entry">
            <div class="audit-entry-dot"></div>
            <div class="audit-entry-content">
                <div class="audit-entry-header">
                    <span class="audit-action badge">${esc(entry.action)}</span>
                    <span class="audit-actor">${esc(entry.actor)}</span>
                    <span class="audit-time">${esc(entry.timestamp || '')}</span>
                </div>
                ${entry.details && Object.keys(entry.details).length ?
                    `<div class="audit-details">${Object.entries(entry.details).map(([k,v]) => `<span class="audit-detail-item"><strong>${esc(k)}:</strong> ${esc(String(v))}</span>`).join(', ')}</div>` : ''}
            </div>
        </div>
    `).join('')}</div>`;
}

async function loadAuditTrail(entityType, entityId) {
    const container = document.getElementById('audit-trail-container');
    if (!container) return;
    container.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const data = await apiCall('GET', `/api/audit/trail/${entityType}/${encodeURIComponent(entityId)}`);
        const trail = data.trail || [];
        container.innerHTML = trail.length ? renderAuditTrailTimeline(trail) : '<p class="empty-state">暂无审计记录</p>';
    } catch (e) {
        container.innerHTML = `<div class="error-state">加载失败: ${esc(e.message)}</div>`;
    }
}

// ═══════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════

function fmtNum(v) {
    if (v === null || v === undefined || v === '') return '—';
    const n = typeof v === 'object' ? (v.ttm ?? v.value ?? JSON.stringify(v)) : v;
    if (typeof n === 'number') return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(n);
}

function fmtFinancial(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
        return Object.entries(v).map(([k, val]) =>
            `<strong>${k}</strong>: ${typeof val === 'number' ? val.toLocaleString() : val}`
        ).join('<br>');
    }
    return typeof v === 'number' ? v.toLocaleString() : String(v);
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

// ─── Initial Load ─────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    applyChartDefaults();
    // Restore correct active states for switchers
    const savedTheme = localStorage.getItem('af-theme') || 'light';
    document.querySelectorAll('#settings-panel-theme .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.themeVal === savedTheme);
    });
    const savedLang = I18N.getLang();
    document.querySelectorAll('#settings-panel-language .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.lang === savedLang);
    });
    const savedColorScheme = localStorage.getItem('af-color-scheme') || 'vscode';
    applyColorScheme(savedColorScheme);
    I18N.applyAll();
    navigateTo('dashboard');
    loadEventSignals();

    // Update status bar doc count on dashboard load
    const updateStatusBar = async () => {
        try {
            const data = await apiCall('GET', '/api/workbench/dashboard');
            const dc = document.getElementById('status-doc-count');
            if (dc) dc.textContent = data.review_queue?.length ?? 0;
        } catch (e) { /* ignore */ }
    };
    updateStatusBar();
});

// ═══════════════════════════════════════════════════════════════
// Outcomes Management
// ═══════════════════════════════════════════════════════════════

async function loadOutcomes() {
    const eventTypeFilter = document.getElementById('outcome-event-type-filter');
    const eventType = eventTypeFilter ? eventTypeFilter.value.trim() : '';
    const params = new URLSearchParams();
    if (eventType) params.append('event_type', eventType);

    try {
        const outcomes = await apiCall('GET', `/api/outcomes/aggregate/list?${params.toString()}`);
        renderOutcomesTable(outcomes);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderOutcomesTable(outcomes) {
    const wrap = document.getElementById('outcomes-table');
    if (!outcomes.length) {
        wrap.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>事件类型</th><th>收益</th><th>超额收益</th><th>最大回撤</th><th>教训</th><th>操作</th></tr></thead>
        <tbody>${outcomes.map(o => {
            const returnClass = o.outcome_return > 0 ? 'positive' : 'negative';
            const excessReturnClass = o.outcome_excess_return > 0 ? 'positive' : 'negative';
            const eventType = o.metadata?.event_type || '—';
            return `
            <tr>
                <td title="${esc(o.outcome_id)}">${esc(o.outcome_id.substring(0, 8))}</td>
                <td>${esc(o.subject_id)}</td>
                <td>${esc(eventType)}</td>
                <td class="${returnClass}">${o.outcome_return > 0 ? '+' : ''}${o.outcome_return?.toFixed(2) ?? '—'}%</td>
                <td class="${excessReturnClass}">${o.outcome_excess_return > 0 ? '+' : ''}${o.outcome_excess_return?.toFixed(2) ?? '—'}%</td>
                <td>${o.max_drawdown?.toFixed(2) ?? '—'}%</td>
                <td class="lesson-cell">${o.lesson ? esc(o.lesson) : '<span class="empty-state">—</span>'}</td>
                <td class="actions">
                    <button class="btn-sm btn-detail" onclick="showOutcomeDetail('${esc(o.outcome_id)}', '${esc(o.signal_id)}')">详情</button>
                    <button class="btn-sm btn-edit" onclick="editLesson('${esc(o.outcome_id)}', '${esc(o.lesson || '')}')">编辑</button>
                </td>
            </tr>`;
        }).join('')}</tbody>
    </table>`;
}

async function editLesson(outcomeId, currentLesson) {
    const newLesson = prompt('请输入教训总结:', currentLesson);
    if (newLesson === null) return;

    try {
        await apiCall('PATCH', `/api/outcomes/${encodeURIComponent(outcomeId)}/lesson?lesson=${encodeURIComponent(newLesson)}`);
        toast('教训已更新', 'success');
        loadOutcomes();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function showOutcomeDetail(outcomeId, signalId) {
    if (signalId) {
        showSignalDetail(signalId);
        return;
    }

    try {
        const data = await apiCall('GET', `/api/outcomes/${encodeURIComponent(outcomeId)}`);
        toast(`Outcome 详情加载成功`, 'success');
        console.log('Outcome detail:', data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

// 闭循环运行
async function runClosedLoop() {
    const statusEl = document.getElementById('closed-loop-status');
    const resultsEl = document.getElementById('closed-loop-results');
    const btnEl = document.getElementById('btn-run-closed-loop');

    // 禁用按钮并显示加载状态
    btnEl.disabled = true;
    btnEl.textContent = '运行中...';
    statusEl.textContent = '正在运行闭循环，请稍候...';
    resultsEl.style.display = 'none';

    try {
        const summary = await apiCall('POST', '/api/pipeline/closed-loop');
        renderClosedLoopResults(summary);
        statusEl.textContent = '闭循环运行完成！';
        toast('闭循环运行完成', 'success');
    } catch (e) {
        statusEl.textContent = '运行失败: ' + e.message;
        toast(e.message, 'error');
    } finally {
        btnEl.disabled = false;
        btnEl.textContent = '运行闭循环';
    }
}

function renderClosedLoopResults(summary) {
    const resultsEl = document.getElementById('closed-loop-results');
    resultsEl.style.display = 'block';

    resultsEl.innerHTML = `
        <div class="card-row" style="margin-top:16px;">
            <div class="stat-card pending">
                <div class="stat-value">${summary.signals_generated}</div>
                <div class="stat-label">生成信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#38a169;">${summary.signals_backtested}</div>
                <div class="stat-label">回测信号</div>
            </div>
        </div>
        <div class="card-row" style="margin-top:16px;">
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#3182ce;">${(summary.avg_return * 100).toFixed(2)}%</div>
                <div class="stat-label">平均收益</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#805ad5;">${(summary.avg_excess_return * 100).toFixed(2)}%</div>
                <div class="stat-label">平均超额收益</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#d69e2e;">${(summary.win_rate * 100).toFixed(1)}%</div>
                <div class="stat-label">胜率</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#e53e3e;">${(summary.correct_direction_rate * 100).toFixed(1)}%</div>
                <div class="stat-label">方向正确率</div>
            </div>
        </div>
        <div class="card" style="margin-top:16px;">
            <div class="card-header">
                <h3>回测结果详情</h3>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>信号ID</th>
                        <th>标的</th>
                        <th>收益</th>
                        <th>超额收益</th>
                        <th>方向正确</th>
                    </tr>
                </thead>
                <tbody>
                    ${(summary.results || []).map(r => `
                        <tr>
                            <td title="${r.signal_id}">${r.signal_id.substring(0, 8)}...</td>
                            <td>${r.subject_id}</td>
                            <td class="${r.return > 0 ? 'positive' : 'negative'}">${r.return > 0 ? '+' : ''}${(r.return * 100).toFixed(2)}%</td>
                            <td class="${r.excess_return > 0 ? 'positive' : 'negative'}">${r.excess_return > 0 ? '+' : ''}${(r.excess_return * 100).toFixed(2)}%</td>
                            <td>${r.direction_correct ? '✓' : '✗'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// ============ Signal Lab ============
let signalLabData = {
    featureGroups: {},
    labelTypes: {},
    scorerTypes: {}
};

async function loadSignalLab() {
    try {
        // Load summary
        const summary = await apiCall('GET', '/api/signal-lab/summary');
        if (summary.success && summary.summary) {
            document.getElementById('sl-signals-count').textContent = summary.summary.signals_count ?? '-';
            document.getElementById('sl-backtests-count').textContent = summary.summary.backtests_count ?? '-';
            document.getElementById('sl-features-count').textContent = summary.summary.features_count ?? '-';
            document.getElementById('sl-groups-count').textContent = summary.summary.feature_groups_count ?? '-';
        }
        // Load feature groups
        await loadFeatureGroups();
        // Load label types
        await loadLabelTypes();
        // Load scorers
        await loadScorers();
    } catch (e) {
        toast('加载Signal Lab失败: ' + e.message, 'error');
    }
}

async function loadFeatureGroups() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/features/groups');
        if (data.success && data.groups) {
            signalLabData.featureGroups = data.groups;
            renderFeatureGroups(data.groups);
            populateFeatureGroupSelect(data.groups);
        }
    } catch (e) {
        console.error('Failed to load feature groups:', e);
    }
}

function renderFeatureGroups(groups) {
    const container = document.getElementById('feature-groups-list');
    container.innerHTML = Object.entries(groups).map(([key, group]) => `
        <div class="feature-group-card">
            <div class="fg-name">${esc(group.name)}</div>
            <div class="fg-desc">${esc(group.description)}</div>
            <div class="fg-count">${group.features.length} 个特征</div>
            <div class="fg-features">
                ${group.features.slice(0, 5).map(f => `<span class="feature-tag">${esc(f)}</span>`).join('')}
                ${group.features.length > 5 ? `<span class="feature-tag">+${group.features.length - 5} 更多</span>` : ''}
            </div>
        </div>
    `).join('');
}

function populateFeatureGroupSelect(groups) {
    const select = document.getElementById('sl-feature-group');
    select.innerHTML = '<option value="">全部特征组</option>' +
        Object.keys(groups).map(key => `<option value="${key}">${esc(groups[key].name)}</option>`).join('');
}

async function computeFeatures() {
    const subjectId = document.getElementById('sl-subject-id').value.trim();
    const group = document.getElementById('sl-feature-group').value;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-features-loading');
    const resultEl = document.getElementById('sl-features-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const payload = { subject_id: subjectId };
        if (group) {
            payload.groups = [group];
        }
        const data = await apiCall('POST', '/api/signal-lab/features/compute', payload);
        if (data.success) {
            renderFeaturesResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算特征失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderFeaturesResult(data) {
    const container = document.getElementById('sl-features-table');
    if (!data.features || !data.features.length) {
        container.innerHTML = '<p class="empty-state">暂无特征数据</p>';
        return;
    }

    const featureNames = data.feature_names || [];
    const headers = ['日期', ...featureNames];

    container.innerHTML = `
        <table>
            <thead>
                <tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr>
            </thead>
            <tbody>
                ${data.features.slice(-20).map(row => {
                    const date = row.date || row.index || '-';
                    const values = featureNames.map(name => {
                        let val = row[name];
                        if (val === undefined) {
                            for (const groupKey of Object.keys(signalLabData.featureGroups)) {
                                const prefixed = `${groupKey}.${name}`;
                                if (row[prefixed] !== undefined) {
                                    val = row[prefixed];
                                    break;
                                }
                            }
                        }
                        return typeof val === 'number' ? val.toFixed(4) : (val ?? '—');
                    });
                    return `<tr><td>${esc(date)}</td>${values.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

async function loadLabelTypes() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/labels/types');
        if (data.success && data.label_types) {
            signalLabData.labelTypes = data.label_types;
            renderLabelTypes(data.label_types);
        }
    } catch (e) {
        console.error('Failed to load label types:', e);
    }
}

function renderLabelTypes(types) {
    const container = document.getElementById('label-types-list');
    container.innerHTML = Object.entries(types).map(([key, type]) => `
        <div class="label-type-card">
            <div class="lt-name">${esc(type.name)}</div>
            <div class="lt-desc">${esc(type.description)}</div>
        </div>
    `).join('');
}

async function computeLabels() {
    const subjectId = document.getElementById('sl-label-subject').value.trim();
    const labelType = document.getElementById('sl-label-type').value;
    const horizon = parseInt(document.getElementById('sl-label-horizon').value) || 20;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-labels-loading');
    const resultEl = document.getElementById('sl-labels-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const data = await apiCall('POST', '/api/signal-lab/labels/compute', {
            subject_id: subjectId,
            label_type: labelType,
            horizon: horizon
        });
        if (data.success) {
            renderLabelsResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算标签失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderLabelsResult(data) {
    const container = document.getElementById('sl-labels-table');
    if (!data.labels || !data.labels.length) {
        container.innerHTML = '<p class="empty-state">暂无标签数据</p>';
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr><th>日期</th><th>标签值</th></tr>
            </thead>
            <tbody>
                ${data.labels.slice(-20).map(row => {
                    const date = row.date || row.index || '-';
                    let val = row.label ?? row[data.label_type] ?? row.value;
                    if (val === undefined) {
                        const keys = Object.keys(row).filter(k => k !== 'date' && k !== 'index');
                        if (keys.length > 0) val = row[keys[0]];
                    }
                    const displayVal = typeof val === 'number' ? (val * 100).toFixed(2) + '%' : (val ?? '—');
                    return `<tr><td>${esc(date)}</td><td>${esc(displayVal)}</td></tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

async function loadScorers() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/scorers/types');
        if (data.success && data.scorer_types) {
            signalLabData.scorerTypes = data.scorer_types;
            renderScorers(data.scorer_types);
        }
    } catch (e) {
        console.error('Failed to load scorers:', e);
    }
}

function renderScorers(scorers) {
    const container = document.getElementById('scorers-list');
    container.innerHTML = Object.entries(scorers).map(([key, scorer]) => `
        <div class="scorer-card">
            <div class="sc-name">${esc(scorer.name)}</div>
            <div class="sc-desc">${esc(scorer.description)}</div>
        </div>
    `).join('');
}

async function runBacktests() {
    const signalIdsInput = document.getElementById('sl-backtest-signals').value.trim();
    const initialCapital = parseFloat(document.getElementById('sl-initial-capital').value) || 1000000;

    const loadingEl = document.getElementById('sl-backtests-loading');
    const resultEl = document.getElementById('sl-backtests-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const payload = { initial_capital: initialCapital };
        if (signalIdsInput) {
            payload.signal_ids = signalIdsInput.split(',').map(s => s.trim()).filter(s => s);
        }
        const data = await apiCall('POST', '/api/signal-lab/backtests/run', payload);
        if (data.success) {
            renderBacktestsResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('运行回测失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderBacktestsResult(data) {
    const container = document.getElementById('sl-backtests-table');
    if (!data.results || !data.results.length) {
        container.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }

    container.innerHTML = `
        <div style="margin-bottom:16px;">
            <strong>回测数量:</strong> ${data.backtested_count}
        </div>
        <table>
            <thead>
                <tr><th>信号ID</th><th>标的</th><th>收益</th><th>超额收益</th><th>方向正确</th></tr>
            </thead>
            <tbody>
                ${data.results.map(r => `
                    <tr>
                        <td title="${esc(r.signal_id)}">${esc(r.signal_id.substring(0, 8))}...</td>
                        <td>${esc(r.subject_id)}</td>
                        <td class="${r.return > 0 ? 'positive' : 'negative'}">${r.return > 0 ? '+' : ''}${(r.return * 100).toFixed(2)}%</td>
                        <td class="${r.excess_return > 0 ? 'positive' : 'negative'}">${r.excess_return > 0 ? '+' : ''}${(r.excess_return * 100).toFixed(2)}%</td>
                        <td>${r.direction_correct ? '✓' : '✗'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

// Signal Lab Tab Switching
function switchSignalLabTab(tabName) {
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#section-signal-lab .tab-panel').forEach(p => p.classList.add('hidden'));
    document.querySelector(`#section-signal-lab .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
    document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
}
