/* ============================================================
   Research Workbench — Closed Loop Module
   ============================================================ */

import { apiCall, toast } from './core.js';

async function runClosedLoop() {
    const statusEl = document.getElementById('closed-loop-status');
    const resultsEl = document.getElementById('closed-loop-results');
    const btnEl = document.getElementById('btn-run-closed-loop');

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
        </div>`;
}

export { runClosedLoop, renderClosedLoopResults };
