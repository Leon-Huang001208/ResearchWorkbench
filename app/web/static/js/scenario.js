/* ============================================================
   Research Workbench — Scenario Analysis Module
   ============================================================ */

import { apiCall, toast, esc, getChartColors } from './core.js';

async function generateScenarios() {
    const topic = document.getElementById('scenario-topic').value.trim();
    const subjectsStr = document.getElementById('scenario-subjects').value.trim();
    const subject_ids = subjectsStr ? subjectsStr.split(',').map(s => s.trim()).filter(s => s) : [];
    if (!topic) return toast('请输入分析主题', 'error');

    const loading = document.getElementById('scenario-loading');
    const result = document.getElementById('scenario-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/scenarios/generate', { topic, subject_ids });
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
    const hypotheses = data.hypotheses || [];

    // Probability Chart
    if (window.chartScenarioProb) window.chartScenarioProb.destroy();
    const colors = getChartColors();
    if (hypotheses.length) {
        const ctx = document.getElementById('chart-scenario-prob').getContext('2d');
        window.chartScenarioProb = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: hypotheses.map(h => h.title),
                datasets: [{ data: hypotheses.map(h => (h.probability * 100).toFixed(1)), backgroundColor: colors.colors.slice(0, hypotheses.length) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } } } }
        });
    }

    // Normalization Check
    const checkEl = document.getElementById('normalization-check');
    const sum = hypotheses.reduce((acc, h) => acc + (h.probability || 0), 0);
    if (data.normalization_check?.ok || Math.abs(sum - 1) < 0.01) {
        checkEl.className = 'check-indicator ok';
        checkEl.textContent = '概率归一化检查通过';
    } else {
        checkEl.className = 'check-indicator warn';
        checkEl.textContent = '概率归一化检查未通过';
    }

    // Scenario Cards
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

    // Residual Uncertainty
    const resList = document.getElementById('residual-list');
    const residual = data.residual_uncertainty || [];
    resList.innerHTML = residual.length ? residual.map(r => `<li>${esc(r)}</li>`).join('') : '<li class="empty-state">无</li>';
}

export { generateScenarios, renderScenarioResult };
