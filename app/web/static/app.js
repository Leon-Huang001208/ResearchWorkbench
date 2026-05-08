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
}

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

// ─── Global Search ────────────────────────────────────────────
document.getElementById('global-search').addEventListener('input', async (e) => {
    const q = e.target.value.trim();
    if (q.length < 2) return;
    try {
        const results = await apiCall('GET', `/api/workbench/search?q=${encodeURIComponent(q)}`);
        // TODO: display search results
        console.log('Search results:', results);
    } catch (e) {
        console.error('Search failed:', e);
    }
});

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
        const data = await apiCall('GET', '/api/workbench/dashboard');
        document.getElementById('stat-total').textContent = data.signal_stats?.total ?? 0;
        document.getElementById('stat-research').textContent = data.signal_stats?.research_only ?? 0;
        document.getElementById('stat-candidate').textContent = data.signal_stats?.candidate ?? 0;
        document.getElementById('stat-paper').textContent = data.signal_stats?.paper_trade ?? 0;
        document.getElementById('stat-review').textContent = data.review_queue?.length ?? 0;

        const recentEventsEl = document.getElementById('recent-events');
        if (data.recent_events?.length) {
            recentEventsEl.innerHTML = data.recent_events.map(e => `<li>${esc(e.title || e.event_id)}</li>`).join('');
        } else {
            recentEventsEl.innerHTML = '<li class="empty-state">暂无数据</li>';
        }
    } catch (e) {
        console.error('Failed to load dashboard:', e);
    }
}

// ═══════════════════════════════════════════════════════════════
// Asset Analysis
// ═══════════════════════════════════════════════════════════════

document.getElementById('btn-analyze').addEventListener('click', analyzeAsset);

async function analyzeAsset() {
    const code = document.getElementById('asset-code').value.trim();
    const source = document.getElementById('asset-source').value;
    if (!code) return toast(I18N.t('toast.enter_asset_code'), 'error');

    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/assets/analyze', {
            canonical_id: code,
            source: source,
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

document.getElementById('btn-generate-scenarios').addEventListener('click', generateScenarios);

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

document.getElementById('btn-generate-event-signal').addEventListener('click', generateEventSignal);

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
        
        // 获取并展示 Timing 决策
        if (signalId) {
            try {
                const timingDecision = await apiCall('GET', `/api/timing/evaluate-signal/${signalId}`);
                renderTimingDecision(timingDecision);
                document.getElementById('timing-decision-container').classList.remove('hidden');
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

document.getElementById('btn-load-industry').addEventListener('click', loadIndustryChain);
document.getElementById('btn-load-propagation').addEventListener('click', loadPropagationPath);

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

document.getElementById('btn-refresh-review').addEventListener('click', () => {
    loadReviewStats();
    loadReviewPending();
});

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
        document.getElementById('stat-review').textContent = stats.pending_assertions ?? 0;
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

document.getElementById('btn-create-signal').addEventListener('click', createSignal);
document.getElementById('btn-refresh-signals').addEventListener('click', loadSignals);

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
                <td title="${esc(s.signal_id)}">${esc(s.signal_id.substring(0, 8))}</td>
                <td>${esc(s.subject_id)}</td>
                <td>${esc(s.thesis)}</td>
                <td>${esc(s.horizon)}</td>
                <td>${s.score.toFixed(2)}</td>
                <td>${s.confidence.toFixed(2)}</td>
                <td>${s.latest_timing_action ? `<span class="timing-badge timing-${s.latest_timing_action}">${esc(s.latest_timing_action)}</span>` : '—'}</td>
                <td><span class="status-badge status-${s.status || 'pending_backtest'}">${esc(s.status || 'pending_backtest')}</span></td>
                <td class="actions">
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

document.getElementById('btn-ingest').addEventListener('click', ingestText);

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

document.getElementById('btn-load-episodes').addEventListener('click', loadEpisodes);
document.getElementById('btn-load-strategies').addEventListener('click', loadStrategies);
document.getElementById('btn-load-failures').addEventListener('click', loadFailures);
document.getElementById('btn-load-event-summary').addEventListener('click', loadEventSummary);

function loadMemoryPage() {
    loadEpisodes();
    loadStrategies();
    loadFailures();
}

async function loadEpisodes() {
    const eventType = document.getElementById('episode-event-type-filter').value.trim();
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
    const signalFamily = document.getElementById('strategy-signal-filter').value.trim();
    const marketRegime = document.getElementById('strategy-regime-filter').value.trim();
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
    initTheme();
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
