/* ============================================================
   Research Workbench — Wind Excel Data Panel Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

// ─── Wind Data Fetching ─────────────────────────────────

async function fetchWindData(dataType) {
    const codeEl = document.getElementById('wind-stock-code');
    const startEl = document.getElementById('wind-start-date');
    const endEl = document.getElementById('wind-end-date');
    const loadingEl = document.getElementById('wind-loading');
    const resultEl = document.getElementById('wind-result');

    const code = codeEl?.value?.trim();
    if (!code) {
        toast('请输入股票代码', 'error');
        return;
    }

    loadingEl?.classList.remove('hidden');
    resultEl?.classList.add('hidden');

    try {
        const codes = code.split(/[,;\s]+/).filter(Boolean);
        const payload = { codes };
        let endpoint;

        switch (dataType) {
            case 'consensus':
                endpoint = '/api/wind/consensus';
                if (endEl?.value) payload.trade_date = endEl.value;
                break;
            case 'margin_trading':
            case 'block_trades':
            case 'prices':
            case 'fund_flow':
                endpoint = `/api/wind/${dataType === 'margin_trading' ? 'margin-trading' : dataType === 'block_trades' ? 'block-trades' : dataType}`;
                if (!startEl?.value || !endEl?.value) {
                    toast('请选择开始和结束日期', 'error');
                    loadingEl?.classList.add('hidden');
                    return;
                }
                payload.start_date = startEl.value;
                payload.end_date = endEl.value;
                break;
            case 'financials':
                endpoint = '/api/wind/financials';
                if (!endEl?.value) {
                    toast('请选择报告期日期', 'error');
                    loadingEl?.classList.add('hidden');
                    return;
                }
                payload.report_date = endEl.value;
                break;
            case 'industry':
                endpoint = '/api/wind/industry';
                break;
            case 'holders':
                endpoint = '/api/wind/holders';
                if (!endEl?.value) {
                    toast('请选择报告期日期', 'error');
                    loadingEl?.classList.add('hidden');
                    return;
                }
                payload.report_date = endEl.value;
                break;
            default:
                endpoint = '/api/wind/consensus';
        }

        const data = await apiCall('POST', endpoint, payload);
        if (data && data.success) {
            renderWindResults(data.data, dataType);
            resultEl?.classList.remove('hidden');
            toast(`Wind 数据获取成功: ${data.count || 0} 条记录`, 'success');
        } else {
            toast('Wind 数据为空或查询失败', 'warning');
        }
    } catch (e) {
        toast('Wind 数据获取失败: ' + (e.message || e), 'error');
    } finally {
        loadingEl?.classList.add('hidden');
    }
}

function renderWindResults(rows, dataType) {
    const container = document.getElementById('wind-table');
    if (!container) return;

    if (!rows || !rows.length) {
        container.innerHTML = '<p class="empty-state">暂无数据</p>';
        return;
    }

    // Format numbers for display
    const headers = Object.keys(rows[0]);
    const formattedRows = rows.map(row => {
        const formatted = {};
        for (const [key, val] of Object.entries(row)) {
            if (typeof val === 'number') {
                // Large numbers: use 2 decimal places
                if (Math.abs(val) >= 1e6) {
                    formatted[key] = val.toLocaleString('zh-CN', {
                        minimumFractionDigits: 2,
                        maximumFractionDigits: 2,
                    });
                } else if (Math.abs(val) < 1) {
                    formatted[key] = val.toFixed(6);
                } else {
                    formatted[key] = val.toFixed(2);
                }
            } else {
                formatted[key] = val ?? '—';
            }
        }
        return formatted;
    });

    container.innerHTML =
        `<table class="compact">
            <thead><tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr></thead>
            <tbody>
                ${formattedRows.map(row =>
                    `<tr>${headers.map(h => `<td>${esc(String(row[h]))}</td>`).join('')}</tr>`
                ).join('')}
            </tbody>
        </table>`;
}

async function checkWindHealth() {
    const badge = document.getElementById('wind-health-badge');
    if (!badge) return;

    badge.textContent = '检查中...';
    badge.className = 'badge badge-warning';

    try {
        const data = await apiCall('GET', '/api/wind/health');
        if (data && data.available) {
            badge.textContent = 'Wind ✓';
            badge.className = 'badge badge-success';
        } else {
            badge.textContent = 'Wind ✗';
            badge.className = 'badge badge-error';
        }
    } catch (e) {
        badge.textContent = '检查失败';
        badge.className = 'badge badge-error';
    }
}

function initWindPanel() {
    const fetchBtn = document.getElementById('btn-wind-fetch');
    if (fetchBtn) {
        fetchBtn.addEventListener('click', () => {
            const typeEl = document.getElementById('wind-data-type');
            const dataType = typeEl?.value || 'consensus';
            fetchWindData(dataType);
        });
    }
    checkWindHealth();
}

export { fetchWindData, renderWindResults, checkWindHealth, initWindPanel };

// ─── Window Exports (for HTML onclick handlers) ────────────────
window.fetchWindData = fetchWindData;
window.checkWindHealth = checkWindHealth;
window.initWindPanel = initWindPanel;
