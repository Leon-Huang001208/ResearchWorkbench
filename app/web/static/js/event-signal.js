/* ============================================================
   AlphaFoundry — Event Signal Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

async function generateEventSignal() {
    const event = {
        event_id: crypto.randomUUID(),
        title: document.getElementById('event-title').value.trim(),
        type: document.getElementById('event-type').value,
        timestamp: document.getElementById('event-date').value || new Date().toISOString(),
    };
    if (!event.title) return toast('请输入事件标题', 'error');

    try {
        const result = await apiCall('POST', '/api/pipeline/event-signal', { event });
        const signalId = result.signal_id;
        toast('事件信号生成成功', 'success');
        loadEventSignals();

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

function renderEventSignalResult(data) {
    const container = document.getElementById('event-signal-content');
    if (!container) return;
    container.innerHTML = `
        <div class="signal-card"><h4>信号</h4><p>${esc(data.signal_summary || data.thesis || '--')}</p></div>
        ${data.timing ? renderTimingDecision(data.timing) : ''}
    `;
}

function renderTimingDecision(decision) {
    const container = document.getElementById('timing-decision-card');
    if (!container) return '';
    container.innerHTML = decision ? `
        <h4>择时判断</h4>
        <div class="timing-decision">
            <div class="timing-action">决策: ${esc(decision.action || decision.decision || '--')}</div>
            ${decision.confidence !== undefined ? `<div class="timing-confidence">置信度: ${(decision.confidence * 100).toFixed(1)}%</div>` : ''}
            ${decision.summary ? `<div class="timing-summary">${esc(decision.summary)}</div>` : ''}
        </div>
    ` : '<p class="empty-state">暂无择时判断</p>';
    return '';
}

export { generateEventSignal, loadEventSignals, renderEventSignalResult, renderTimingDecision };
