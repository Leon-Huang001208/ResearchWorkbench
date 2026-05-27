/* ============================================================
   AlphaFoundry — Asset Analysis Module
   ============================================================ */

import { apiCall, toast, esc, getChartColors, fmtVolume, fmtAmount, fmtMarketCap, fmtRevenue, fmtNetProfit } from './core.js';

// ─── Chart Instances ───────────────────────────────────────
let chartPriceVolume = null;
let chartCapitalFlow = null;

// ─── Search State ──────────────────────────────────────────
let assetSearchDebounceTimer = null;
let selectedAssetIndex = -1;
let assetSearchResults = [];

async function searchAssets(query) {
    if (!query || query.length < 1) { hideAssetSearchDropdown(); return; }
    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}&types=symbol`);
        assetSearchResults = results.symbols || [];
        renderAssetSearchDropdown(assetSearchResults, query);
    } catch (e) { console.error('Asset search failed:', e); }
}

function renderAssetSearchDropdown(results, query) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!results || !results.length) { dropdown.classList.add('hidden'); return; }
    selectedAssetIndex = -1;
    let html = '<div class="search-result-group"><div class="group-title">标的</div>';
    results.forEach((item, index) => {
        html += `
            <div class="search-result-item asset-result-item" data-index="${index}" data-symbol="${esc(item.symbol || '')}">
                <div class="result-title">
                    <span class="asset-symbol">${esc(item.symbol || '')}</span>
                    <span class="asset-name">${esc(item.name || item.display_name || '')}</span>
                </div>
                ${item.industry ? `<div class="result-subtitle">${esc(item.industry)}</div>` : ''}
            </div>
        `;
    });
    html += '</div>';
    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
    dropdown.querySelectorAll('.asset-result-item').forEach(item => {
        item.addEventListener('click', () => selectAsset(item.dataset.symbol, item));
        item.addEventListener('mouseenter', () => {
            dropdown.querySelectorAll('.asset-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            selectedAssetIndex = parseInt(item.dataset.index);
        });
    });
}

function selectAsset(symbol, element) {
    document.getElementById('asset-code').value = symbol;
    hideAssetSearchDropdown();
    analyzeAssetByCode(symbol);
}

function hideAssetSearchDropdown() { document.getElementById('asset-search-dropdown').classList.add('hidden'); }

function handleAssetSearchKeydown(e) {
    const dropdown = document.getElementById('asset-search-dropdown');
    const items = dropdown.querySelectorAll('.asset-result-item');
    if (dropdown.classList.contains('hidden')) return;
    if (e.key === 'ArrowDown') { e.preventDefault(); selectedAssetIndex = Math.min(selectedAssetIndex + 1, items.length - 1); updateSelectedItem(items); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selectedAssetIndex = Math.max(selectedAssetIndex - 1, 0); updateSelectedItem(items); }
    else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedAssetIndex >= 0 && items[selectedAssetIndex]) { items[selectedAssetIndex].click(); }
        else { const code = e.target.value.trim(); if (code) { hideAssetSearchDropdown(); analyzeAssetByCode(code); } }
    } else if (e.key === 'Escape') { hideAssetSearchDropdown(); }
}

function updateSelectedItem(items) {
    items.forEach((item, index) => {
        item.classList.toggle('selected', index === selectedAssetIndex);
        if (index === selectedAssetIndex) item.scrollIntoView({ block: 'nearest' });
    });
}

async function analyzeAssetByCode(code) {
    if (!code) return toast('请输入资产代码', 'error');
    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    if (result) result.classList.add('hidden');
    if (loading) loading.classList.remove('hidden');
    try {
        const data = await apiCall('POST', '/api/assets/analysis-card', { canonical_id: code });
        renderAssetAnalysisCard(data);
        if (result) result.classList.remove('hidden');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        if (loading) loading.classList.add('hidden');
    }
}

async function analyzeAsset() {
    const code = document.getElementById('asset-code').value.trim();
    if (!code) return toast('请输入资产代码', 'error');
    return analyzeAssetByCode(code);
}

function renderAssetAnalysisCard(data) {
    const basic = data.basic_info || {};
    const setText = (id, text) => { const el = document.getElementById(id); if (el) el.textContent = text; };
    setText('asset-name', basic.name || data.canonical_id || '--');
    setText('asset-code-display', basic.symbol || data.canonical_id || '--');

    const priceClass = (data.price_change_pct || 0) >= 0 ? 'price-up' : 'price-down';
    const changePrefix = (data.price_change_pct || 0) >= 0 ? '+' : '';
    setText('asset-price', data.current_price ? data.current_price.toFixed(2) : '--');
    const priceEl = document.getElementById('asset-price'); if (priceEl) priceEl.className = `asset-price ${priceClass}`;
    setText('asset-change', data.price_change !== undefined ? `${changePrefix}${data.price_change.toFixed(2)}` : '--');
    const changeEl = document.getElementById('asset-change'); if (changeEl) changeEl.className = `asset-change ${priceClass}`;
    setText('asset-change-pct', data.price_change_pct !== undefined ? `(${changePrefix}${data.price_change_pct.toFixed(2)}%)` : '--');
    const pctEl = document.getElementById('asset-change-pct'); if (pctEl) pctEl.className = `asset-change-pct ${priceClass}`;

    setText('asset-volume', fmtVolume(data.volume));
    setText('asset-amount', fmtAmount(data.amount));
    setText('asset-turnover', data.turnover !== undefined ? `${data.turnover.toFixed(2)}%` : '--');
    setText('asset-market-cap', fmtMarketCap(basic.market_cap));
    setText('asset-high-52w', data.high_52w !== undefined ? data.high_52w.toFixed(2) : '--');
    setText('asset-low-52w', data.low_52w !== undefined ? data.low_52w.toFixed(2) : '--');

    const fin = data.financial || {};
    setText('fin-pe', fin.pe_ttm !== undefined ? fin.pe_ttm.toFixed(2) : '--');
    setText('fin-pb', fin.pb_mrq !== undefined ? fin.pb_mrq.toFixed(2) : '--');
    setText('fin-roe', fin.roe !== undefined ? `${fin.roe.toFixed(2)}%` : '--');
    setText('fin-revenue', fmtRevenue(fin.revenue));
    setText('fin-net-profit', fmtNetProfit(fin.net_profit));
    setText('fin-gross-margin', fin.gross_margin !== undefined ? `${fin.gross_margin.toFixed(2)}%` : '--');

    renderPriceVolumeChartAdvanced(data.price_bars || []);
    renderCapitalFlowChart(data.capital_flow);
    renderShareholderList(data.top_10_shareholders || []);
    renderIndustryInfo(data.industry);
    renderEventListPanel(data.recent_events || []);
    renderMacroSensitivity(data.macro_sensitivity);
}

function renderPriceVolumeChartAdvanced(priceBars) {
    const colors = getChartColors();
    if (chartPriceVolume) chartPriceVolume.destroy();
    if (!priceBars.length) return;
    const labels = priceBars.map(b => typeof b.date === 'string' ? b.date.substring(5) : '');
    const closePrices = priceBars.map(b => b.close);
    const ctx = document.getElementById('chart-price-volume')?.getContext('2d');
    if (!ctx) return;
    chartPriceVolume = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets: [{ label: '收盘价', data: closePrices, borderColor: colors.blue, backgroundColor: colors.blue + '20', fill: true, tension: 0.2, pointRadius: 0 }] },
        options: { responsive: true, interaction: { mode: 'index', intersect: false }, plugins: { legend: { position: 'top' } }, scales: { x: { grid: { color: colors.grid } }, y: { grid: { color: colors.grid } } } }
    });
}

function renderCapitalFlowChart(capitalFlow) {
    const detailsEl = document.getElementById('capital-flow-details');
    if (!capitalFlow) { if (detailsEl) detailsEl.innerHTML = '<p class="empty-state">暂无资金流向数据</p>'; return; }
    const colors = getChartColors();
    if (chartCapitalFlow) chartCapitalFlow.destroy();
    const labels = ['主力净流入', '超大单', '大单', '中单', '小单'];
    const values = [capitalFlow.main_net || 0, capitalFlow.super_net || 0, capitalFlow.large_net || 0, capitalFlow.medium_net || 0, capitalFlow.small_net || 0];
    const validData = labels.map((l, i) => ({ label: l, value: values[i] })).filter(d => d.value !== 0);
    const ctx = document.getElementById('chart-capital-flow')?.getContext('2d');
    if (ctx) {
        chartCapitalFlow = new Chart(ctx, {
            type: 'pie',
            data: { labels: validData.map(d => d.label), datasets: [{ data: validData.map(d => Math.abs(d.value)), backgroundColor: validData.map(d => d.value >= 0 ? colors.green : colors.red) }] },
            options: { responsive: true, plugins: { legend: { position: 'bottom' } } }
        });
    }
    if (detailsEl) {
        detailsEl.innerHTML = `
            <div class="flow-detail-item"><span class="flow-label">主力流入</span><span class="flow-value inflow">${fmtAmount(capitalFlow.main_inflow)}</span></div>
            <div class="flow-detail-item"><span class="flow-label">主力流出</span><span class="flow-value outflow">${fmtAmount(capitalFlow.main_outflow)}</span></div>
            <div class="flow-detail-item"><span class="flow-label">主力净流入</span><span class="flow-value ${(capitalFlow.main_net || 0) >= 0 ? 'inflow' : 'outflow'}">${(capitalFlow.main_net || 0) >= 0 ? '+' : ''}${fmtAmount(capitalFlow.main_net)}</span></div>
            ${capitalFlow.northbound_flow !== undefined ? `<div class="flow-detail-item"><span class="flow-label">北向资金</span><span class="flow-value ${capitalFlow.northbound_flow >= 0 ? 'inflow' : 'outflow'}">${capitalFlow.northbound_flow >= 0 ? '+' : ''}${fmtAmount(capitalFlow.northbound_flow)}</span></div>` : ''}
        `;
    }
}

function renderShareholderList(shareholders) {
    const container = document.getElementById('shareholder-list');
    if (!container) return;
    if (!shareholders || !shareholders.length) { container.innerHTML = '<p class="empty-state">暂无股东数据</p>'; return; }
    container.innerHTML = shareholders.map(sh => `
        <div class="shareholder-item">
            <div class="shareholder-name">${esc(sh.name)}</div>
            <div class="shareholder-meta">
                <span class="shareholder-ratio">${sh.share_ratio.toFixed(2)}%</span>
                ${sh.change_ratio !== undefined ? `<span class="shareholder-change ${sh.change_ratio >= 0 ? 'change-up' : 'change-down'}">${sh.change_ratio >= 0 ? '+' : ''}${sh.change_ratio.toFixed(2)}%</span>` : ''}
                ${sh.is_state_owned ? '<span class="soe-badge">国资</span>' : ''}
            </div>
        </div>
    `).join('');
}

function renderIndustryInfo(industry) {
    const container = document.getElementById('industry-info-detail');
    if (!container) return;
    if (!industry) { container.innerHTML = '<p class="empty-state">暂无行业数据</p>'; return; }
    container.innerHTML = `
        <div class="industry-class"><div class="industry-label">申万一级</div><div class="industry-value">${esc(industry.sw_level_1 || '--')}</div></div>
        <div class="industry-class"><div class="industry-label">申万二级</div><div class="industry-value">${esc(industry.sw_level_2 || '--')}</div></div>
        <div class="industry-metrics">
            <div class="metric-row"><span class="metric-label">行业PE</span><span class="metric-value">${industry.industry_pe !== undefined ? industry.industry_pe.toFixed(2) : '--'}</span></div>
            <div class="metric-row"><span class="metric-label">行业PB</span><span class="metric-value">${industry.industry_pb !== undefined ? industry.industry_pb.toFixed(2) : '--'}</span></div>
        </div>
    `;
}

function renderEventListPanel(events) {
    const panel = document.getElementById('event-list-panel');
    if (!panel) return;
    if (!events || !events.length) { panel.innerHTML = '<p class="empty-state">暂无相关事件</p>'; return; }
    panel.innerHTML = events.map(e => `
        <div class="event-list-item">
            <div class="item-title">${esc(e.summary || e.title || '')}</div>
            <div class="item-meta">${esc(e.event_type || '')} &bull; ${new Date(e.created_at).toLocaleString()}</div>
        </div>
    `).join('');
}

function renderMacroSensitivity(macro) {
    const container = document.getElementById('macro-sensitivity');
    if (!container) return;
    if (!macro || !macro.sensitivities || !macro.sensitivities.length) { container.innerHTML = '<p class="empty-state">暂无宏观敏感性数据</p>'; return; }
    container.innerHTML = macro.sensitivities.map(s => `
        <div class="macro-item">
            <span class="macro-factor">${esc(s.factor)}</span>
            <span class="macro-direction ${s.direction === 'positive' ? 'positive' : s.direction === 'negative' ? 'negative' : ''}">${s.direction === 'positive' ? '↑' : s.direction === 'negative' ? '↓' : '—'}</span>
            <span class="macro-strength">${s.strength ? s.strength.toFixed(2) : '--'}</span>
        </div>
    `).join('');
}

function initAssetSearch() {
    const assetInput = document.getElementById('asset-code');
    if (assetInput) {
        assetInput.addEventListener('input', (e) => {
            clearTimeout(assetSearchDebounceTimer);
            assetSearchDebounceTimer = setTimeout(() => searchAssets(e.target.value.trim()), 200);
        });
        assetInput.addEventListener('keydown', handleAssetSearchKeydown);
        assetInput.addEventListener('focus', (e) => { if (e.target.value.trim()) searchAssets(e.target.value.trim()); });
    }
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('asset-search-dropdown');
        const input = document.getElementById('asset-code');
        if (dropdown && !dropdown.contains(e.target) && e.target !== input) dropdown.classList.add('hidden');
    });
}

export { searchAssets, selectAsset, analyzeAssetByCode, analyzeAsset, handleAssetSearchKeydown, initAssetSearch };
