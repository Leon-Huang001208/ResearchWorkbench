/* ============================================================
   AlphaFoundry — Signal Management Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

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
    if (!wrap) return;
    if (!signals || !signals.length) {
        wrap.innerHTML = '<p class="empty-state">暂无信号</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>论点</th><th>预测期</th><th>分数</th><th>置信度</th><th>择时决策</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${signals.map(s => `
            <tr>
                <td title="${esc(s.signal_id)}"><a href="javascript:void(0)" onclick="showSignalDetail('${esc(s.signal_id)}')">${esc((s.signal_id || '').substring(0, 8))}</a></td>
                <td>${esc(s.subject_id)}</td>
                <td>${esc(s.thesis)}</td>
                <td>${esc(s.horizon)}</td>
                <td>${s.score ? s.score.toFixed(2) : '—'}</td>
                <td>${s.confidence ? s.confidence.toFixed(2) : '—'}</td>
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

async function createSignal() {
    const body = {
        subject_id: document.getElementById('sig-subject-id')?.value.trim(),
        thesis: document.getElementById('sig-thesis')?.value.trim(),
        score: parseFloat(document.getElementById('sig-score')?.value) || 0,
        confidence: parseFloat(document.getElementById('sig-confidence')?.value) || 0,
        horizon: document.getElementById('sig-horizon')?.value || '',
    };
    if (!body.subject_id || !body.thesis) return toast('请输入资产代码和论点', 'error');

    try {
        await apiCall('POST', '/api/signals/create', body);
        toast('信号已创建', 'success');
        const thesisEl = document.getElementById('sig-thesis');
        if (thesisEl) thesisEl.value = '';
        loadSignals();
    } catch (e) {
        toast(e.message, 'error');
    }
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
    if (!wrap) return;
    if (!outcomes || !outcomes.length) {
        wrap.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>事件类型</th><th>收益</th><th>超额收益</th><th>最大回撤</th><th>教训</th><th>操作</th></tr></thead>
        <tbody>${outcomes.map(o => {
            const returnClass = (o.outcome_return || 0) > 0 ? 'positive' : 'negative';
            const excessReturnClass = (o.outcome_excess_return || 0) > 0 ? 'positive' : 'negative';
            const eventType = o.metadata?.event_type || '—';
            return `
            <tr>
                <td title="${esc(o.outcome_id)}">${esc((o.outcome_id || '').substring(0, 8))}</td>
                <td>${esc(o.subject_id)}</td>
                <td>${esc(eventType)}</td>
                <td class="${returnClass}">${o.outcome_return > 0 ? '+' : ''}${o.outcome_return?.toFixed(2) ?? '—'}%</td>
                <td class="${excessReturnClass}">${o.outcome_excess_return > 0 ? '+' : ''}${o.outcome_excess_return?.toFixed(2) ?? '—'}%</td>
                <td>${o.max_drawdown?.toFixed(2) ?? '—'}%</td>
                <td class="lesson-cell">${o.lesson ? esc(o.lesson) : '<span class="empty-state">—</span>'}</td>
                <td class="actions">
                    <button class="btn-sm btn-detail" onclick="showOutcomeDetail('${esc(o.outcome_id)}', '${esc(o.signal_id)}')">详情</button>
                    <button class="btn-sm btn-edit" onclick="editLesson('${esc(o.outcome_id)}', '${esc((o.lesson || ''))}')">编辑</button>
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
        toast('Outcome 详情加载成功', 'success');
        console.log('Outcome detail:', data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function initSignals() {
    document.getElementById('btn-create-signal')?.addEventListener('click', createSignal);
    document.getElementById('btn-refresh-outcomes')?.addEventListener('click', loadOutcomes);
    document.getElementById('outcome-event-type-filter')?.addEventListener('change', loadOutcomes);
}

export { loadSignals, createSignal, validateSignal, promoteSignal, loadOutcomes, renderSignalsTable, renderOutcomesTable, editLesson, showOutcomeDetail, initSignals };
