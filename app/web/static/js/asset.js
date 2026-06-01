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
let assetSearchRequestSeq = 0;

const ASSET_SEARCH_SEEDS = [
    {
        canonical_id: '600519.SH',
        symbol: '600519.SH',
        raw_code: '600519',
        name: '贵州茅台',
        display_name: '贵州茅台',
        asset_type: 'equity',
        exchange: 'SH',
        market: 'A-share',
        industry: '食品饮料',
        pinyin_abbr: 'gzmt',
        source: 'client_seed',
    },
    {
        canonical_id: '399436.SZ',
        symbol: '399436.SZ',
        raw_code: '399436',
        name: '绿色煤炭',
        display_name: '绿色煤炭',
        asset_type: 'index',
        exchange: 'SZ',
        market: 'A-share',
        industry: '煤炭',
        pinyin_abbr: 'lsmt',
        source: 'client_seed',
    },
];

const isFiniteNumber = (value) => typeof value === 'number' && Number.isFinite(value);
const fmtFixed = (value, digits = 2, suffix = '') =>
    isFiniteNumber(value) ? `${value.toFixed(digits)}${suffix}` : '--';
const normalizeSearchText = (value) => String(value || '').trim().toLowerCase().replace(/\s+/g, '');

async function searchAssets(query) {
    if (!query || query.length < 1) {
        assetSearchRequestSeq++;
        assetSearchResults = [];
        selectedAssetIndex = -1;
        hideAssetSearchDropdown();
        return;
    }
    const requestSeq = ++assetSearchRequestSeq;
    renderAssetSearchLoading(query);
    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}&types=symbol&_=${Date.now()}`);
        if (requestSeq !== assetSearchRequestSeq) return;
        assetSearchResults = mergeAssetSearchResults(results.symbols || [], getClientSeedAssetMatches(query));
        renderAssetSearchDropdown(assetSearchResults, query, results.symbol_search_status || {});
    } catch (e) {
        if (requestSeq !== assetSearchRequestSeq) return;
        console.error('Asset search failed:', e);
        const fallbackResults = getClientSeedAssetMatches(query);
        if (fallbackResults.length) {
            assetSearchResults = fallbackResults;
            renderAssetSearchDropdown(assetSearchResults, query, {
                stock_master_empty: true,
                search_error: e?.message || '搜索服务暂不可用',
            });
            return;
        }
        renderAssetSearchError(e);
    }
}

function mergeAssetSearchResults(apiResults, fallbackResults) {
    const merged = [];
    const seen = new Set();
    [...apiResults, ...fallbackResults].forEach(item => {
        const key = item.canonical_id || item.symbol;
        if (!key || seen.has(key)) return;
        seen.add(key);
        merged.push(item);
    });
    return merged;
}

function getClientSeedAssetMatches(query) {
    const normalizedQuery = normalizeSearchText(query);
    if (!normalizedQuery) return [];
    return ASSET_SEARCH_SEEDS
        .map(item => {
            const match = scoreClientSeedAsset(item, normalizedQuery);
            return match.score > 0 ? { ...item, match_type: match.match_type, score: match.score } : null;
        })
        .filter(Boolean)
        .sort((a, b) => b.score - a.score || String(a.symbol).localeCompare(String(b.symbol)))
        .slice(0, 10);
}

function scoreClientSeedAsset(item, query) {
    const symbol = normalizeSearchText(item.symbol);
    const rawCode = normalizeSearchText(item.raw_code);
    const name = normalizeSearchText(item.name || item.display_name);
    const abbr = normalizeSearchText(item.pinyin_abbr);
    if (query === symbol || query === rawCode) return { match_type: 'exact_code', score: 1000 };
    if (symbol.startsWith(query) || rawCode.startsWith(query)) return { match_type: 'code_prefix', score: 900 };
    if (query === abbr) return { match_type: 'pinyin_exact', score: 850 };
    if (abbr.startsWith(query)) return { match_type: 'pinyin_prefix', score: 800 };
    if (name.includes(query)) return { match_type: 'name_contains', score: 700 };
    if (symbol.includes(query) || rawCode.includes(query)) return { match_type: 'code_contains', score: 600 };
    if (abbr.includes(query)) return { match_type: 'pinyin_contains', score: 500 };
    return { match_type: 'none', score: 0 };
}

function renderAssetSearchLoading(query) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    selectedAssetIndex = -1;
    dropdown.innerHTML = `
        <div class="search-result-group">
            <div class="group-title">标的</div>
            <div class="asset-search-status">正在搜索：${esc(query)}</div>
        </div>
    `;
    dropdown.classList.remove('hidden');
}

function renderAssetSearchError(error) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    selectedAssetIndex = -1;
    dropdown.innerHTML = `
        <div class="search-result-group">
            <div class="group-title">标的</div>
            <div class="asset-search-status is-error">搜索失败：${esc(error?.message || '请稍后重试')}</div>
        </div>
    `;
    dropdown.classList.remove('hidden');
}

function renderAssetSearchDropdown(results, query, status = {}) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    const statusHtml = status.stock_master_empty
        ? '<div class="asset-search-status is-warning">标的词典未同步，仅显示内置/已有实体候选；同步 stock_master 后可覆盖全量 A 股。</div>'
        : '';
    const errorHtml = status.search_error
        ? `<div class="asset-search-status is-error">搜索服务异常，已启用本地候选：${esc(status.search_error)}</div>`
        : '';
    if (!results || !results.length) {
        selectedAssetIndex = -1;
        dropdown.innerHTML = `
            <div class="search-result-group">
                <div class="group-title">标的</div>
                ${statusHtml}
                ${errorHtml}
                <div class="asset-search-status">没有匹配：${esc(query)}</div>
            </div>
        `;
        dropdown.classList.remove('hidden');
        return;
    }
    selectedAssetIndex = 0;
    let html = `<div class="search-result-group"><div class="group-title">标的</div>${statusHtml}${errorHtml}`;
    results.forEach((item, index) => {
        const name = item.name || item.display_name || '';
        const industry = item.industry || item.asset_type || '';
        const canonicalId = item.canonical_id || item.symbol || '';
        const symbol = item.symbol || canonicalId;
        html += `
            <div class="search-result-item asset-result-item ${index === selectedAssetIndex ? 'selected' : ''}"
                 data-index="${index}"
                 data-canonical-id="${esc(canonicalId)}"
                 data-symbol="${esc(symbol)}"
                 data-name="${esc(name)}">
                <span class="asset-result-rank">${index + 1}</span>
                <div class="result-title">
                    <span class="asset-symbol">${esc(symbol)}</span>
                    <span class="asset-name">${esc(name)}</span>
                </div>
                ${industry ? `<div class="result-subtitle">${esc(industry)}</div>` : ''}
            </div>
        `;
    });
    html += '</div>';
    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
    dropdown.querySelectorAll('.asset-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const index = Number.parseInt(item.dataset.index, 10);
            selectAssetCandidate(assetSearchResults[index], item);
        });
        item.addEventListener('mouseenter', () => {
            dropdown.querySelectorAll('.asset-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            selectedAssetIndex = parseInt(item.dataset.index);
        });
    });
}

function selectAsset(symbol, element) {
    const candidate = assetSearchResults.find(item => (item.canonical_id || item.symbol) === symbol);
    if (candidate) return selectAssetCandidate(candidate, element);
    selectAssetCandidate({
        canonical_id: symbol,
        symbol: element?.dataset?.symbol || symbol,
        name: element?.dataset?.name || '',
    }, element);
}

function selectAssetCandidate(candidate, element) {
    if (!candidate) return;
    const input = document.getElementById('asset-code');
    const canonicalId = candidate.canonical_id || candidate.symbol || element?.dataset?.canonicalId;
    const name = candidate.name || candidate.display_name || element?.dataset?.name || '';
    const displaySymbol = candidate.symbol || element?.dataset?.symbol || canonicalId;
    if (input) {
        input.value = name ? `${displaySymbol} ${name}` : displaySymbol;
        input.dataset.selectedSymbol = canonicalId;
    }
    hideAssetSearchDropdown();
    analyzeAssetByCode(canonicalId);
}

function hideAssetSearchDropdown() {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (dropdown) dropdown.classList.add('hidden');
}

function handleAssetSearchKeydown(e) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!dropdown) return;
    const items = dropdown.querySelectorAll('.asset-result-item');
    if (dropdown.classList.contains('hidden')) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const code = e.target.dataset.selectedSymbol || normalizeAssetInput(e.target.value);
            if (code) analyzeAssetByCode(code);
        }
        return;
    }
    if (e.key === 'ArrowDown') { e.preventDefault(); selectedAssetIndex = Math.min(selectedAssetIndex + 1, items.length - 1); updateSelectedItem(items); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); selectedAssetIndex = Math.max(selectedAssetIndex - 1, 0); updateSelectedItem(items); }
    else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedAssetIndex >= 0 && items[selectedAssetIndex]) { items[selectedAssetIndex].click(); }
        else if (items.length > 0) { items[0].click(); }
        else {
            const fallbackCandidate = getClientSeedAssetMatches(e.target.value.trim())[0];
            if (fallbackCandidate) {
                selectAssetCandidate(fallbackCandidate);
                return;
            }
            const code = e.target.dataset.selectedSymbol || normalizeAssetInput(e.target.value);
            if (code) { hideAssetSearchDropdown(); analyzeAssetByCode(code); }
        }
    } else if (e.key === 'Escape') { hideAssetSearchDropdown(); }
}

function normalizeAssetInput(value) {
    return (value || '').trim().split(/\s+/)[0];
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
    const input = document.getElementById('asset-code');
    const code = input?.dataset?.selectedSymbol || normalizeAssetInput(input?.value);
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
    setText('asset-price', fmtFixed(data.current_price));
    const priceEl = document.getElementById('asset-price'); if (priceEl) priceEl.className = `asset-price ${priceClass}`;
    setText('asset-change', isFiniteNumber(data.price_change) ? `${changePrefix}${data.price_change.toFixed(2)}` : '--');
    const changeEl = document.getElementById('asset-change'); if (changeEl) changeEl.className = `asset-change ${priceClass}`;
    setText('asset-change-pct', isFiniteNumber(data.price_change_pct) ? `(${changePrefix}${data.price_change_pct.toFixed(2)}%)` : '--');
    const pctEl = document.getElementById('asset-change-pct'); if (pctEl) pctEl.className = `asset-change-pct ${priceClass}`;

    setText('asset-volume', fmtVolume(data.volume));
    setText('asset-amount', fmtAmount(data.amount));
    setText('asset-turnover', fmtFixed(data.turnover, 2, '%'));
    setText('asset-market-cap', fmtMarketCap(basic.market_cap));
    setText('asset-high-52w', fmtFixed(data.high_52w));
    setText('asset-low-52w', fmtFixed(data.low_52w));

    const fin = data.financial || {};
    setText('fin-pe', fmtFixed(fin.pe_ttm));
    setText('fin-pb', fmtFixed(fin.pb_mrq));
    setText('fin-roe', fmtFixed(fin.roe, 2, '%'));
    setText('fin-revenue', fmtRevenue(fin.revenue));
    setText('fin-net-profit', fmtNetProfit(fin.net_profit));
    setText('fin-gross-margin', fmtFixed(fin.gross_margin, 2, '%'));

    renderPriceVolumeChartAdvanced(data.price_bars || []);
    renderCapitalFlowChart(data.capital_flow);
    renderShareholderList(data.top_10_shareholders || []);
    renderIndustryInfo(data.industry);
    renderEventListPanel(data.recent_events || []);
    renderMacroSensitivity(data.macro_sensitivity);
}

function renderPriceVolumeChartAdvanced(priceBars) {
    if (typeof Chart === 'undefined') return;
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
    if (typeof Chart === 'undefined') return;
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
                <span class="shareholder-ratio">${fmtFixed(sh.share_ratio, 2, '%')}</span>
                ${isFiniteNumber(sh.change_ratio) ? `<span class="shareholder-change ${sh.change_ratio >= 0 ? 'change-up' : 'change-down'}">${sh.change_ratio >= 0 ? '+' : ''}${sh.change_ratio.toFixed(2)}%</span>` : ''}
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
            <div class="metric-row"><span class="metric-label">行业PE</span><span class="metric-value">${fmtFixed(industry.industry_pe)}</span></div>
            <div class="metric-row"><span class="metric-label">行业PB</span><span class="metric-value">${fmtFixed(industry.industry_pb)}</span></div>
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
    const container =
        document.getElementById('macro-sensitivity-detail') ||
        document.getElementById('macro-sensitivity');
    if (!container) return;
    if (!macro || !macro.sensitivities || !macro.sensitivities.length) { container.innerHTML = '<p class="empty-state">暂无宏观敏感性数据</p>'; return; }
    container.innerHTML = macro.sensitivities.map(s => `
        <div class="macro-item">
            <span class="macro-factor">${esc(s.factor)}</span>
            <span class="macro-direction ${s.direction === 'positive' ? 'positive' : s.direction === 'negative' ? 'negative' : ''}">${s.direction === 'positive' ? '↑' : s.direction === 'negative' ? '↓' : '—'}</span>
            <span class="macro-strength">${fmtFixed(s.strength)}</span>
        </div>
    `).join('');
}

function initAssetSearch() {
    const assetInput = document.getElementById('asset-code');
    if (assetInput) {
        assetInput.addEventListener('input', (e) => {
            delete e.target.dataset.selectedSymbol;
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
