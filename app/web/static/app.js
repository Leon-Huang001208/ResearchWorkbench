/* ============================================================
   AlphaFoundry — Frontend Application Logic
   ============================================================ */

// ─── API Helper ───────────────────────────────────────────
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

// ─── Toast ────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast toast-${type}`;
    setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── Chart Instances (for cleanup) ───────────────────────
let chartPriceVolume = null;
let chartScenarioProb = null;

// ─── Tab Navigation ──────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(`tab-${btn.dataset.tab}`).classList.add('active');

        // Auto-load on tab switch
        if (btn.dataset.tab === 'signals') loadSignals();
        if (btn.dataset.tab === 'review') { loadReviewStats(); loadReviewPending(); }
    });
});

// ─── Theme Toggle ────────────────────────────────────────
const themeToggle = document.getElementById('theme-toggle');
const saved = localStorage.getItem('af-theme');
if (saved) document.documentElement.setAttribute('data-theme', saved);
updateThemeIcon();

themeToggle.addEventListener('click', () => {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('af-theme', next);
    updateThemeIcon();
});

function updateThemeIcon() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    themeToggle.textContent = isDark ? '☀️' : '🌙';
}

// ─── Chart.js Default Theming ────────────────────────────
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

// ═══════════════════════════════════════════════════════════
// Tab 1: 📊 资产分析
// ═══════════════════════════════════════════════════════════

document.getElementById('btn-analyze').addEventListener('click', analyzeAsset);

async function analyzeAsset() {
    const code = document.getElementById('asset-code').value.trim();
    const source = document.getElementById('asset-source').value;
    if (!code) return toast('请输入资产代码', 'error');

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
        toast('资产分析完成', 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderAssetResult(data) {
    // ── Valuation Cards
    const valCards = document.getElementById('valuation-cards');
    const v = data.valuation || {};
    const valMetrics = [
        { label: 'PE (TTM)', value: v.pe_ttm ?? v.PE ?? '—' },
        { label: 'PB', value: v.pb ?? v.PB ?? '—' },
        { label: 'PS', value: v.ps ?? v.PS ?? '—' },
        { label: 'EV/EBITDA', value: v.ev_ebitda ?? v.EV_EBITDA ?? '—' },
    ];
    valCards.innerHTML = valMetrics.map(m =>
        `<div class="metric-card"><div class="metric-label">${m.label}</div><div class="metric-value">${fmtNum(m.value)}</div></div>`
    ).join('');

    // ── Price-Volume Chart
    renderPriceVolumeChart(data.price_volume || {});

    // ── Financial Table
    const finWrap = document.getElementById('financial-table');
    const f = data.financial || {};
    const finRows = [
        ['营业收入 (Revenue)', f.revenue ?? f.Revenue],
        ['净利润 (Net Profit)', f.net_profit ?? f.NetProfit],
        ['每股收益 (EPS)', f.eps ?? f.EPS],
        ['净资产收益率 (ROE)', f.roe ?? f.ROE],
    ].filter(r => r[1] !== undefined);

    if (finRows.length) {
        finWrap.innerHTML = `<table><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>${finRows.map(r =>
            `<tr><td>${r[0]}</td><td>${fmtFinancial(r[1])}</td></tr>`
        ).join('')}</tbody></table>`;
    } else {
        finWrap.innerHTML = '<p style="color:var(--text-secondary)">暂无财务数据</p>';
    }

    // ── Fund Flow
    const ffWrap = document.getElementById('fund-flow-info');
    const ff = data.fund_flow || {};
    const ffItems = [
        { label: '主力净流入', key: 'main_net_inflow' },
        { label: '机构持仓', key: 'institutional_holding' },
        { label: '北向持仓', key: 'northbound_holding' },
    ].filter(i => ff[i.key] !== undefined);

    if (ffItems.length) {
        ffWrap.innerHTML = ffItems.map(i =>
            `<div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(ff[i.key])}</div></div>`
        ).join('');
    } else {
        ffWrap.innerHTML = '<p style="color:var(--text-secondary)">暂无资金流向数据</p>';
    }

    // ── Event Impact
    const evList = document.getElementById('event-impact-list');
    const events = data.event_impact || [];
    evList.innerHTML = events.length
        ? events.map(e => `<li>${e}</li>`).join('')
        : '<li style="color:var(--text-secondary)">暂无事件影响</li>';
}

function renderPriceVolumeChart(pv) {
    const colors = getChartColors();
    if (chartPriceVolume) chartPriceVolume.destroy();

    const labels = pv.dates || [];
    const close = pv.close_price || [];
    const ma5 = pv.ma5 || [];
    const ma20 = pv.ma20 || [];
    const ma60 = pv.ma60 || [];

    // If no data, show a placeholder
    if (!labels.length && !close.length) {
        const ctx = document.getElementById('chart-price-volume').getContext('2d');
        chartPriceVolume = new Chart(ctx, {
            type: 'bar',
            data: { labels: ['暂无数据'], datasets: [{ label: '收盘价', data: [0], backgroundColor: colors.blue }] },
            options: { responsive: true, plugins: { legend: { display: false } } }
        });
        return;
    }

    const ctx = document.getElementById('chart-price-volume').getContext('2d');
    chartPriceVolume = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: '收盘价', data: close, borderColor: colors.blue, backgroundColor: 'rgba(49,130,206,.1)', fill: true, tension: 0.3, pointRadius: 2 },
                { label: 'MA5', data: ma5, borderColor: colors.orange, borderDash: [4,4], pointRadius: 0 },
                { label: 'MA20', data: ma20, borderColor: colors.green, borderDash: [6,3], pointRadius: 0 },
                { label: 'MA60', data: ma60, borderColor: colors.red, borderDash: [8,4], pointRadius: 0 },
            ].filter(d => d.data.length > 0)
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: {
                x: { grid: { color: colors.grid } },
                y: { grid: { color: colors.grid } }
            }
        }
    });
}

// ═══════════════════════════════════════════════════════════
// Tab 2: 🎲 情景分析
// ═══════════════════════════════════════════════════════════

document.getElementById('btn-generate-scenarios').addEventListener('click', generateScenarios);

async function generateScenarios() {
    const topic = document.getElementById('scenario-topic').value.trim();
    if (!topic) return toast('请输入研究主题', 'error');

    const loading = document.getElementById('scenario-loading');
    const result = document.getElementById('scenario-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/scenarios/generate', { topic });
        renderScenarioResult(data);
        result.classList.remove('hidden');
        toast('情景分析完成', 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderScenarioResult(data) {
    // ── Probability Pie
    const hypotheses = data.hypotheses || [];
    if (chartScenarioProb) chartScenarioProb.destroy();

    const colors = getChartColors();
    if (hypotheses.length) {
        const ctx = document.getElementById('chart-scenario-prob').getContext('2d');
        chartScenarioProb = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: hypotheses.map(h => h.title),
                datasets: [{
                    data: hypotheses.map(h => (h.probability * 100).toFixed(1)),
                    backgroundColor: colors.colors.slice(0, hypotheses.length),
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: { position: 'bottom' },
                    tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } }
                }
            }
        });
    }

    // ── Scenario Cards
    const cards = document.getElementById('scenario-cards');
    cards.innerHTML = hypotheses.map(h => `
        <div class="scenario-card">
            <div class="sc-header">
                <span class="sc-title">${esc(h.title)}</span>
                <span class="sc-prob">${(h.probability * 100).toFixed(1)}%</span>
            </div>
            ${h.assumptions && h.assumptions.length ? `<div class="sc-section"><h4>假设</h4><ul>${h.assumptions.map(a => `<li>${esc(a)}</li>`).join('')}</ul></div>` : ''}
            ${h.key_triggers && h.key_triggers.length ? `<div class="sc-section"><h4>触发条件</h4><ul>${h.key_triggers.map(t => `<li>${esc(t)}</li>`).join('')}</ul></div>` : ''}
            ${h.invalidation_signals && h.invalidation_signals.length ? `<div class="sc-section"><h4>失效信号</h4><ul>${h.invalidation_signals.map(s => `<li>${esc(s)}</li>`).join('')}</ul></div>` : ''}
            ${h.confidence !== undefined ? `<div class="sc-section"><h4>置信度</h4><span>${(h.confidence * 100).toFixed(0)}%</span></div>` : ''}
        </div>
    `).join('');

    // ── Residual Uncertainty
    const resList = document.getElementById('residual-list');
    const residual = data.residual_uncertainty || [];
    resList.innerHTML = residual.length
        ? residual.map(r => `<li>${esc(r)}</li>`).join('')
        : '<li style="color:var(--text-secondary)">无</li>';
}

// ═══════════════════════════════════════════════════════════
// Tab 3: ⚡ 信号实验室
// ═══════════════════════════════════════════════════════════

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
    if (!body.subject_id || !body.thesis) return toast('请填写主体ID和论点', 'error');

    try {
        await apiCall('POST', '/api/signals/create', body);
        toast('信号创建成功', 'success');
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
        wrap.innerHTML = '<p style="color:var(--text-secondary)">暂无信号</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>论点</th><th>预测期</th><th>分数</th><th>置信度</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${signals.map(s => `
            <tr>
                <td title="${esc(s.signal_id)}">${esc(s.signal_id.substring(0,8))}</td>
                <td>${esc(s.subject_id)}</td>
                <td>${esc(s.thesis)}</td>
                <td>${esc(s.horizon)}</td>
                <td>${s.score.toFixed(2)}</td>
                <td>${s.confidence.toFixed(2)}</td>
                <td><span class="status-badge status-${esc(s.status)}">${esc(s.status)}</span></td>
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

// ═══════════════════════════════════════════════════════════
// Tab 4: 📝 审核
// ═══════════════════════════════════════════════════════════

document.getElementById('btn-refresh-review').addEventListener('click', () => {
    loadReviewStats();
    loadReviewPending();
});

async function loadReviewStats() {
    try {
        const stats = await apiCall('GET', '/api/review/stats');
        renderReviewStats(stats);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderReviewStats(stats) {
    const wrap = document.getElementById('review-stats');
    wrap.innerHTML = `
        <div class="stat-card pending"><div class="stat-value">${stats.pending_assertions ?? 0}</div><div class="stat-label">待审核</div></div>
        <div class="stat-card approved"><div class="stat-value">${stats.approved_assertions ?? 0}</div><div class="stat-label">已批准</div></div>
        <div class="stat-card rejected"><div class="stat-value">${stats.rejected_assertions ?? 0}</div><div class="stat-label">已拒绝</div></div>
        <div class="stat-card pending"><div class="stat-value">${stats.pending_events ?? 0}</div><div class="stat-label">待审核事件</div></div>
    `;
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
        wrap.innerHTML = '<p style="color:var(--text-secondary)">暂无待审核项</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>谓词</th><th>置信度</th><th>来源</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${items.map(i => `
            <tr>
                <td title="${esc(i.assertion_id)}">${esc(i.assertion_id.substring(0,8))}</td>
                <td>${esc(i.subject_entity_id || '—')}</td>
                <td>${esc(i.predicate)}</td>
                <td>${i.confidence.toFixed(2)}</td>
                <td>${esc(i.source_doc_id?.substring(0,8) || '—')}</td>
                <td>${esc(i.reviewer_status)}</td>
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
        const result = await apiCall('POST', `/api/review/approve/${id}`);
        toast(result.success ? '已批准' : (result.message || '操作失败'), result.success ? 'success' : 'error');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function rejectItem(id) {
    try {
        const result = await apiCall('POST', `/api/review/reject/${id}`);
        toast(result.success ? '已拒绝' : (result.message || '操作失败'), result.success ? 'success' : 'error');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════
// Tab 5: 📥 文档摄入
// ═══════════════════════════════════════════════════════════

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
        toast('文档摄入完成', 'success');
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
            <h3>✅ 摄入成功 — ${esc(data.title || data.doc_id)}</h3>
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

// ═══════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════

function fmtNum(v) {
    if (v === null || v === undefined || v === '') return '—';
    const n = typeof v === 'object' ? (v.ttm ?? v.value ?? JSON.stringify(v)) : v;
    if (typeof n === 'number') return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(n);
}

function fmtFinancial(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
        // Handle nested like { ttm: 15000000000 }
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

// ─── Initial Load ────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    applyChartDefaults();
});
