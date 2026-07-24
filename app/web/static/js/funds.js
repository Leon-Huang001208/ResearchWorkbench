/* ============================================================
   AlphaFoundry — Fund Intelligence Panel
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

let initialized = false;

function setText(id, value) {
    const el = document.getElementById(id);
    if (el) el.textContent = value ?? '--';
}

function setStatus(text, kind = 'warning') {
    const badge = document.getElementById('fund-status-badge');
    if (!badge) return;
    badge.textContent = text;
    badge.className = `badge badge-${kind}`;
}

function fmtNumber(value, digits = 4) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return '--';
    return Number(value).toLocaleString('zh-CN', {
        minimumFractionDigits: 0,
        maximumFractionDigits: digits,
    });
}

function fmtPercent(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return '--';
    return `${(Number(value) * 100).toFixed(2)}%`;
}

function normalizeExposureRows(rows) {
    return Array.isArray(rows) ? rows.filter(row => row && row.label) : [];
}

function renderExposureList(containerId, rows) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const normalized = normalizeExposureRows(rows).slice(0, 12);
    if (!normalized.length) {
        container.innerHTML = '<p class="empty-state compact">暂无数据</p>';
        return;
    }

    container.innerHTML = normalized.map(row => {
        const weight = Number(row.weight || 0);
        const width = Math.max(2, Math.min(100, Math.abs(weight) * 100));
        return `
            <div class="fund-exposure-row">
                <span class="fund-exposure-label">${esc(row.label)}</span>
                <span class="fund-exposure-bar"><i style="width:${width}%"></i></span>
                <strong>${fmtPercent(weight)}</strong>
            </div>`;
    }).join('');
}

function renderManagers(managers) {
    const container = document.getElementById('fund-managers');
    if (!container) return;

    if (!Array.isArray(managers) || !managers.length) {
        container.innerHTML = '<p class="empty-state compact">暂无数据</p>';
        return;
    }

    container.innerHTML = managers.map(manager => `
        <div class="fund-list-item">
            <strong>${esc(manager.manager_name || manager.manager_id)}</strong>
            <span>${esc(manager.institution_name || '--')}</span>
            <small>${esc(manager.tenure_start || '--')} 至 ${esc(manager.tenure_end || '今')}</small>
        </div>
    `).join('');
}

function renderHoldings(holdings) {
    const container = document.getElementById('fund-holdings-table');
    if (!container) return;

    if (!Array.isArray(holdings) || !holdings.length) {
        container.innerHTML = '<p class="empty-state compact">暂无数据</p>';
        return;
    }

    container.innerHTML = `
        <table class="compact">
            <thead>
                <tr>
                    <th>股票代码</th>
                    <th>名称</th>
                    <th>行业</th>
                    <th>主题</th>
                    <th>权重</th>
                    <th>市值</th>
                    <th>报告期</th>
                </tr>
            </thead>
            <tbody>
                ${holdings.map(row => `
                    <tr>
                        <td>${esc(row.stock_symbol)}</td>
                        <td>${esc(row.stock_name || '--')}</td>
                        <td>${esc(row.industry || '--')}</td>
                        <td>${esc(row.theme || '--')}</td>
                        <td>${fmtPercent(row.weight)}</td>
                        <td>${fmtNumber(row.market_value, 2)}</td>
                        <td>${esc(row.report_date || '--')}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>`;
}

function renderFundDetail(detail) {
    const master = detail.master || {};
    const latestNav = detail.latest_nav || {};
    const performance = detail.performance || {};

    setText('fund-name', master.name || '--');
    setText('fund-symbol-display', master.symbol || '--');
    setText('fund-type', master.fund_type || '类型 --');
    setText('fund-company', master.management_company || '管理人 --');
    setText('fund-benchmark', master.benchmark || '基准 --');
    setText('fund-unit-nav', fmtNumber(latestNav.unit_nav));
    setText('fund-acc-nav', fmtNumber(latestNav.accumulated_nav));
    setText('fund-total-return', fmtPercent(performance.total_return));
    setText('fund-max-drawdown', fmtPercent(performance.max_drawdown));
    setText('fund-volatility', fmtPercent(performance.volatility));
    setText('fund-win-rate', fmtPercent(performance.win_rate));
    renderManagers(detail.managers);
    renderHoldings(detail.latest_holdings);
}

async function loadFund() {
    const input = document.getElementById('fund-symbol');
    const loading = document.getElementById('fund-loading');
    const result = document.getElementById('fund-result');
    const symbol = input?.value?.trim();

    if (!symbol) {
        toast('请输入基金代码', 'error');
        return;
    }

    loading?.classList.remove('hidden');
    result?.classList.add('hidden');
    setStatus('查询中...', 'warning');

    try {
        const detail = await apiCall('GET', `/api/funds/${encodeURIComponent(symbol)}`);
        const exposure = await apiCall('GET', `/api/funds/${encodeURIComponent(symbol)}/exposure`);
        renderFundDetail(detail);
        renderExposureList('fund-industry-exposure', exposure.industry_exposure);
        result?.classList.remove('hidden');
        setStatus('已加载', 'success');
        toast('基金情报已更新', 'success');
    } catch (error) {
        console.error('[funds] load fund failed', error);
        setStatus('查询失败', 'error');
        toast(`基金查询失败: ${error.message || error}`, 'error');
    } finally {
        loading?.classList.add('hidden');
    }
}

function parsePortfolioPositions(raw) {
    const parsed = JSON.parse(raw || '{}');
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
        throw new Error('组合输入必须是对象');
    }

    return Object.fromEntries(
        Object.entries(parsed)
            .filter(([symbol]) => symbol && symbol.trim())
            .map(([symbol, weight]) => [symbol.trim(), Number(weight)])
            .filter(([, weight]) => Number.isFinite(weight))
    );
}

async function calculatePortfolioExposure() {
    const input = document.getElementById('fund-portfolio-input');
    const container = document.getElementById('fund-portfolio-result');

    try {
        const positions = parsePortfolioPositions(input?.value);
        if (!Object.keys(positions).length) {
            toast('请输入有效组合权重', 'error');
            return;
        }

        const exposure = await apiCall('POST', '/api/funds/portfolio/exposure', { positions });
        if (container) {
            container.innerHTML = `
                <div class="fund-exposure-group">
                    <h4>行业</h4>
                    <div id="fund-portfolio-industry"></div>
                </div>
                <div class="fund-exposure-group">
                    <h4>股票</h4>
                    <div id="fund-portfolio-stock"></div>
                </div>
                <div class="fund-exposure-group">
                    <h4>主题</h4>
                    <div id="fund-portfolio-theme"></div>
                </div>`;
        }
        renderExposureList('fund-portfolio-industry', exposure.industry_exposure);
        renderExposureList('fund-portfolio-stock', exposure.stock_exposure);
        renderExposureList('fund-portfolio-theme', exposure.theme_exposure);
        toast('组合穿透已更新', 'success');
    } catch (error) {
        console.error('[funds] calculate portfolio exposure failed', error);
        toast(`组合穿透失败: ${error.message || error}`, 'error');
    }
}

function parseRows(raw) {
    const rows = JSON.parse(raw || '[]');
    if (!Array.isArray(rows)) {
        throw new Error('Rows JSON 必须是数组');
    }
    return rows;
}

async function ingestFundRows() {
    const dataset = document.getElementById('fund-ingest-dataset')?.value || 'master';
    const source = document.getElementById('fund-ingest-source')?.value?.trim() || 'web';
    const rowsRaw = document.getElementById('fund-ingest-rows')?.value;
    const result = document.getElementById('fund-ingest-result');

    try {
        const rows = parseRows(rowsRaw);
        if (!rows.length) {
            toast('Rows JSON 为空', 'error');
            return;
        }
        const response = await apiCall('POST', '/api/funds/ingest', { dataset, source, rows });
        if (result) {
            result.innerHTML = `
                <span>dataset: <strong>${esc(response.dataset || dataset)}</strong></span>
                <span>fetched: <strong>${esc(String(response.fetched ?? 0))}</strong></span>
                <span>saved: <strong>${esc(String(response.saved ?? 0))}</strong></span>
            `;
        }
        toast('基金数据已导入', 'success');
    } catch (error) {
        console.error('[funds] ingest rows failed', error);
        toast(`基金数据导入失败: ${error.message || error}`, 'error');
    }
}

export function initFundsPanel() {
    if (initialized) return;
    initialized = true;

    document.getElementById('btn-load-fund')?.addEventListener('click', loadFund);
    document.getElementById('fund-symbol')?.addEventListener('keydown', event => {
        if (event.key === 'Enter') loadFund();
    });
    document.getElementById('btn-calc-fund-portfolio')?.addEventListener('click', calculatePortfolioExposure);
    document.getElementById('btn-ingest-fund-rows')?.addEventListener('click', ingestFundRows);
}

window.initFundsPanel = initFundsPanel;
