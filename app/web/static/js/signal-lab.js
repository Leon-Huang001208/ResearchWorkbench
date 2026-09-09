/* ============================================================
   Research Workbench — Signal Lab Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

let signalLabData = {
    featureGroups: {},
    labelTypes: {},
    scorerTypes: {}
};

async function loadSignalLab() {
    try {
        ensureDynamicFactorsPanel();
        const summary = await apiCall('GET', '/api/signal-lab/summary');
        if (summary.success && summary.summary) {
            const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val ?? '—'; };
            setVal('sl-signals-count', summary.summary.signals_count);
            setVal('sl-backtests-count', summary.summary.backtests_count);
            setVal('sl-features-count', summary.summary.features_count);
            setVal('sl-groups-count', summary.summary.feature_groups_count);
        }
        await loadFeatureGroups();
        await loadLabelTypes();
        await loadScorers();
        await loadDynamicFactorsOverview();
    } catch (e) {
        toast('加载Signal Lab失败: ' + e.message, 'error');
    }
}

async function loadFeatureGroups() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/features/groups');
        if (data.success && data.groups) {
            signalLabData.featureGroups = data.groups;
            renderFeatureGroups(data.groups);
            populateFeatureGroupSelect(data.groups);
        }
    } catch (e) {
        console.error('Failed to load feature groups:', e);
    }
}

function renderFeatureGroups(groups) {
    const container = document.getElementById('feature-groups-list');
    if (!container) return;
    container.innerHTML = Object.entries(groups).map(([key, group]) => `
        <div class="feature-group-card">
            <div class="fg-name">${esc(group.name)}</div>
            <div class="fg-desc">${esc(group.description)}</div>
            <div class="fg-count">${group.features.length} 个特征</div>
            <div class="fg-features">
                ${group.features.slice(0, 5).map(f => `<span class="feature-tag">${esc(f)}</span>`).join('')}
                ${group.features.length > 5 ? `<span class="feature-tag">+${group.features.length - 5} 更多</span>` : ''}
            </div>
        </div>
    `).join('');
}

function populateFeatureGroupSelect(groups) {
    const select = document.getElementById('sl-feature-group');
    if (!select) return;
    select.innerHTML = '<option value="">全部特征组</option>' +
        Object.keys(groups).map(key => `<option value="${key}">${esc(groups[key].name)}</option>`).join('');
}

async function computeFeatures() {
    const subjectId = document.getElementById('sl-subject-id')?.value.trim();
    const group = document.getElementById('sl-feature-group')?.value;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-features-loading');
    const resultEl = document.getElementById('sl-features-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        const payload = { subject_id: subjectId };
        if (group) payload.groups = [group];
        const data = await apiCall('POST', '/api/signal-lab/features/compute', payload);
        if (data.success) {
            renderFeaturesResult(data);
            if (resultEl) resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算特征失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderFeaturesResult(data) {
    const container = document.getElementById('sl-features-table');
    if (!container) return;
    if (!data.features || !data.features.length) {
        container.innerHTML = '<p class="empty-state">暂无特征数据</p>';
        return;
    }

    const featureNames = data.feature_names || [];
    const headers = ['日期', ...featureNames];

    container.innerHTML = `
        <table>
            <thead>
                <tr>${headers.map(h => `<th>${esc(h)}</th>`).join('')}</tr>
            </thead>
            <tbody>
                ${data.features.slice(-20).map(row => {
                    const date = row.date || row.index || '-';
                    const values = featureNames.map(name => {
                        let val = row[name];
                        if (val === undefined) {
                            for (const groupKey of Object.keys(signalLabData.featureGroups)) {
                                const prefixed = `${groupKey}.${name}`;
                                if (row[prefixed] !== undefined) {
                                    val = row[prefixed];
                                    break;
                                }
                            }
                        }
                        return typeof val === 'number' ? val.toFixed(4) : (val ?? '—');
                    });
                    return `<tr><td>${esc(date)}</td>${values.map(v => `<td>${esc(v)}</td>`).join('')}</tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

async function loadLabelTypes() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/labels/types');
        if (data.success && data.label_types) {
            signalLabData.labelTypes = data.label_types;
            renderLabelTypes(data.label_types);
        }
    } catch (e) {
        console.error('Failed to load label types:', e);
    }
}

function renderLabelTypes(types) {
    const container = document.getElementById('label-types-list');
    if (!container) return;
    container.innerHTML = Object.entries(types).map(([key, type]) => `
        <div class="label-type-card">
            <div class="lt-name">${esc(type.name)}</div>
            <div class="lt-desc">${esc(type.description)}</div>
        </div>
    `).join('');
}

async function computeLabels() {
    const subjectId = document.getElementById('sl-label-subject')?.value.trim();
    const labelType = document.getElementById('sl-label-type')?.value || '';
    const horizon = parseInt(document.getElementById('sl-label-horizon')?.value) || 20;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-labels-loading');
    const resultEl = document.getElementById('sl-labels-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        const data = await apiCall('POST', '/api/signal-lab/labels/compute', {
            subject_id: subjectId,
            label_type: labelType,
            horizon: horizon
        });
        if (data.success) {
            renderLabelsResult(data);
            if (resultEl) resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算标签失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderLabelsResult(data) {
    const container = document.getElementById('sl-labels-table');
    if (!container) return;
    if (!data.labels || !data.labels.length) {
        container.innerHTML = '<p class="empty-state">暂无标签数据</p>';
        return;
    }

    container.innerHTML = `
        <table>
            <thead>
                <tr><th>日期</th><th>标签值</th></tr>
            </thead>
            <tbody>
                ${data.labels.slice(-20).map(row => {
                    const date = row.date || row.index || '-';
                    let val = row.label ?? row[data.label_type] ?? row.value;
                    if (val === undefined) {
                        const keys = Object.keys(row).filter(k => k !== 'date' && k !== 'index');
                        if (keys.length > 0) val = row[keys[0]];
                    }
                    const displayVal = typeof val === 'number' ? (val * 100).toFixed(2) + '%' : (val ?? '—');
                    return `<tr><td>${esc(date)}</td><td>${esc(displayVal)}</td></tr>`;
                }).join('')}
            </tbody>
        </table>
    `;
}

async function loadScorers() {
    try {
        const data = await apiCall('GET', '/api/signal-lab/scorers/types');
        if (data.success && data.scorer_types) {
            signalLabData.scorerTypes = data.scorer_types;
            renderScorers(data.scorer_types);
        }
    } catch (e) {
        console.error('Failed to load scorers:', e);
    }
}

function renderScorers(scorers) {
    const container = document.getElementById('scorers-list');
    if (!container) return;
    container.innerHTML = Object.entries(scorers).map(([key, scorer]) => `
        <div class="scorer-card">
            <div class="sc-name">${esc(scorer.name)}</div>
            <div class="sc-desc">${esc(scorer.description)}</div>
        </div>
    `).join('');
}

async function runBacktests() {
    const signalIdsInput = document.getElementById('sl-backtest-signals')?.value.trim();
    const initialCapital = parseFloat(document.getElementById('sl-initial-capital')?.value) || 1000000;

    const loadingEl = document.getElementById('sl-backtests-loading');
    const resultEl = document.getElementById('sl-backtests-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        const payload = { initial_capital: initialCapital };
        if (signalIdsInput) {
            payload.signal_ids = signalIdsInput.split(',').map(s => s.trim()).filter(s => s);
        }
        const data = await apiCall('POST', '/api/signal-lab/backtests/run', payload);
        if (data.success) {
            renderBacktestsResult(data);
            if (resultEl) resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('运行回测失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderBacktestsResult(data) {
    const container = document.getElementById('sl-backtests-table');
    if (!container) return;
    if (!data.results || !data.results.length) {
        container.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }

    container.innerHTML = `
        <div style="margin-bottom:16px;">
            <strong>回测数量:</strong> ${data.backtested_count}
        </div>
        <table>
            <thead>
                <tr><th>信号ID</th><th>标的</th><th>收益</th><th>超额收益</th><th>方向正确</th></tr>
            </thead>
            <tbody>
                ${data.results.map(r => `
                    <tr>
                        <td title="${esc(r.signal_id)}">${esc((r.signal_id || '').substring(0, 8))}...</td>
                        <td>${esc(r.subject_id)}</td>
                        <td class="${r.return > 0 ? 'positive' : 'negative'}">${r.return > 0 ? '+' : ''}${(r.return * 100).toFixed(2)}%</td>
                        <td class="${r.excess_return > 0 ? 'positive' : 'negative'}">${r.excess_return > 0 ? '+' : ''}${(r.excess_return * 100).toFixed(2)}%</td>
                        <td>${r.direction_correct ? '✓' : '✗'}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function ensureDynamicFactorsPanel() {
    const section = document.getElementById('section-signal-lab');
    if (!section) return;

    const tabs = section.querySelector('.tabs');
    if (tabs && !tabs.querySelector('[data-tab="dynamic-factors"]')) {
        const tab = document.createElement('button');
        tab.className = 'tab-btn';
        tab.dataset.tab = 'dynamic-factors';
        tab.textContent = '动态因子';
        tabs.appendChild(tab);
    }

    if (!document.getElementById('tab-dynamic-factors')) {
        const panel = document.createElement('div');
        panel.id = 'tab-dynamic-factors';
        panel.className = 'tab-panel hidden';
        panel.innerHTML = `
            <div class="dynamic-factor-shell">
                <div class="dynamic-factor-header">
                    <div>
                        <h3>动态多因子 Alpha Control Room</h3>
                        <p id="df-note">事件信号、因子验证、择时门控与最终 alpha 的可解释视图。</p>
                    </div>
                    <button id="btn-refresh-dynamic-factors" class="btn-secondary">
                        <i class="codicon codicon-refresh"></i> 刷新
                    </button>
                </div>
                <div id="df-status" class="df-status">加载中...</div>
                <div id="df-content" class="hidden">
                    <div id="df-loop-steps" class="df-loop-steps"></div>
                    <div class="df-grid">
                        <section class="df-panel df-panel-wide">
                            <div class="df-panel-title">最终 Alpha 排名</div>
                            <div id="df-fusion-table" class="data-table-wrap"></div>
                        </section>
                        <section class="df-panel">
                            <div class="df-panel-title">滚动因子权重</div>
                            <div id="df-weights"></div>
                        </section>
                        <section class="df-panel">
                            <div class="df-panel-title">IC / RankIC</div>
                            <div id="df-evaluation-table" class="data-table-wrap"></div>
                        </section>
                        <section class="df-panel df-panel-wide">
                            <div class="df-panel-title">点时因子矩阵</div>
                            <div id="df-matrix-table" class="data-table-wrap"></div>
                        </section>
                    </div>
                </div>
            </div>
        `;
        const backtestsPanel = document.getElementById('tab-backtests');
        if (backtestsPanel?.parentNode) {
            backtestsPanel.parentNode.insertBefore(panel, backtestsPanel.nextSibling);
        } else {
            section.appendChild(panel);
        }
        document
            .getElementById('btn-refresh-dynamic-factors')
            ?.addEventListener('click', loadDynamicFactorsOverview);
    }
}

async function loadDynamicFactorsOverview() {
    ensureDynamicFactorsPanel();
    const statusEl = document.getElementById('df-status');
    const contentEl = document.getElementById('df-content');
    if (statusEl) {
        statusEl.textContent = '加载动态因子视图...';
        statusEl.classList.remove('hidden');
    }
    if (contentEl) contentEl.classList.add('hidden');

    try {
        const data = await apiCall('GET', '/api/signal-lab/dynamic-factors/overview');
        renderDynamicFactorsOverview(data);
        if (statusEl) statusEl.classList.add('hidden');
        if (contentEl) contentEl.classList.remove('hidden');
    } catch (e) {
        if (statusEl) statusEl.textContent = '加载动态因子失败: ' + e.message;
        toast('加载动态因子失败: ' + e.message, 'error');
    }
}

function renderDynamicFactorsOverview(data) {
    if (!data?.success) return;
    const noteEl = document.getElementById('df-note');
    if (noteEl) {
        const mode = data.data_mode === 'demo' ? '样例数据' : '真实数据';
        noteEl.textContent = `${mode} · ${data.as_of_date || '—'} · ${data.note || ''}`;
    }
    renderDynamicLoopSteps(data.closed_loop_steps || []);
    renderDynamicWeights(data.dynamic_weights || {});
    renderDynamicEvaluations(data.evaluations || []);
    renderDynamicFusion(data.fusion_results || []);
    renderDynamicMatrix(data.factor_matrix || {});
}

function renderDynamicLoopSteps(steps) {
    const container = document.getElementById('df-loop-steps');
    if (!container) return;
    container.innerHTML = steps.map(step => `
        <div class="df-loop-step df-step-${esc(step.status || 'unknown')}">
            <div class="df-step-name">${esc(step.step)}</div>
            <div class="df-step-label">${esc(step.label)}</div>
            <div class="df-step-metric">${esc(step.metric || '')}</div>
        </div>
    `).join('');
}

function renderDynamicWeights(dynamicWeights) {
    const container = document.getElementById('df-weights');
    if (!container) return;
    const weights = dynamicWeights.weights || {};
    const entries = Object.entries(weights).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    if (!entries.length) {
        container.innerHTML = '<p class="empty-state">暂无动态权重</p>';
        return;
    }
    container.innerHTML = entries.map(([factor, weight]) => {
        const pct = Math.min(100, Math.abs(weight) * 100);
        return `
            <div class="df-weight-row">
                <div class="df-weight-meta">
                    <span>${esc(factor)}</span>
                    <strong class="${weight >= 0 ? 'positive' : 'negative'}">${formatSigned(weight)}</strong>
                </div>
                <div class="df-bar-track">
                    <div class="df-bar-fill ${weight >= 0 ? 'df-bar-positive' : 'df-bar-negative'}" style="width:${pct}%"></div>
                </div>
            </div>
        `;
    }).join('');
}

function renderDynamicEvaluations(evaluations) {
    const container = document.getElementById('df-evaluation-table');
    if (!container) return;
    if (!evaluations.length) {
        container.innerHTML = '<p class="empty-state">暂无因子评估</p>';
        return;
    }
    container.innerHTML = `
        <table class="compact">
            <thead>
                <tr><th>因子</th><th>IC</th><th>RankIC</th><th>Decile Spread</th><th>覆盖率</th></tr>
            </thead>
            <tbody>
                ${evaluations.map(item => `
                    <tr>
                        <td>${esc(item.factor_id)}</td>
                        <td class="${item.ic >= 0 ? 'positive' : 'negative'}">${formatSigned(item.ic)}</td>
                        <td class="${item.rank_ic >= 0 ? 'positive' : 'negative'}">${formatSigned(item.rank_ic)}</td>
                        <td class="${item.decile_spread >= 0 ? 'positive' : 'negative'}">${formatSigned(item.decile_spread)}</td>
                        <td>${formatPct(item.coverage)}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderDynamicFusion(rows) {
    const container = document.getElementById('df-fusion-table');
    if (!container) return;
    if (!rows.length) {
        container.innerHTML = '<p class="empty-state">暂无融合结果</p>';
        return;
    }
    container.innerHTML = `
        <table class="compact">
            <thead>
                <tr>
                    <th>标的</th><th>Final Alpha</th><th>事件</th><th>因子</th><th>择时</th><th>风险</th><th>主要贡献</th>
                </tr>
            </thead>
            <tbody>
                ${rows.map(row => `
                    <tr>
                        <td>${esc(row.subject_id)}</td>
                        <td>
                            <div class="df-score-cell">
                                <span>${formatPct(row.final_alpha_score)}</span>
                                <div class="df-mini-track"><div class="df-mini-fill" style="width:${clampPct(row.final_alpha_score)}%"></div></div>
                            </div>
                        </td>
                        <td>${formatPct(row.event_alpha_score)}</td>
                        <td>${formatPct(row.factor_alpha_score)}</td>
                        <td>${formatPct(row.timing_readiness)}</td>
                        <td>${formatPct(row.risk_penalty)}</td>
                        <td>${(row.top_contributors || []).map(name => `<span class="df-chip">${esc(name)}</span>`).join('')}</td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function renderDynamicMatrix(matrix) {
    const container = document.getElementById('df-matrix-table');
    if (!container) return;
    const factors = matrix.factors || [];
    const rows = matrix.rows || [];
    if (!factors.length || !rows.length) {
        container.innerHTML = '<p class="empty-state">暂无因子矩阵</p>';
        return;
    }
    container.innerHTML = `
        <table class="compact">
            <thead>
                <tr><th>标的</th>${factors.map(factor => `<th>${esc(factor)}</th>`).join('')}</tr>
            </thead>
            <tbody>
                ${rows.map(row => `
                    <tr>
                        <td>${esc(row.subject_id)}</td>
                        ${factors.map(factor => `<td>${formatNumber(row[factor])}</td>`).join('')}
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

function formatNumber(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
    return Number(value).toFixed(3);
}

function formatPct(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
    return `${(Number(value) * 100).toFixed(1)}%`;
}

function formatSigned(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return '—';
    const num = Number(value);
    return `${num >= 0 ? '+' : ''}${num.toFixed(3)}`;
}

function clampPct(value) {
    if (value === undefined || value === null || Number.isNaN(Number(value))) return 0;
    return Math.max(0, Math.min(100, Number(value) * 100));
}

function switchSignalLabTab(tabName) {
    ensureDynamicFactorsPanel();
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#section-signal-lab .tab-panel').forEach(p => p.classList.add('hidden'));
    const tabBtn = document.querySelector(`#section-signal-lab .tab-btn[data-tab="${tabName}"]`);
    if (tabBtn) tabBtn.classList.add('active');
    const tabPanel = document.getElementById(`tab-${tabName}`);
    if (tabPanel) tabPanel.classList.remove('hidden');
    if (tabName === 'dynamic-factors') loadDynamicFactorsOverview();
}

function initSignalLab() {
    ensureDynamicFactorsPanel();
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchSignalLabTab(btn.dataset.tab));
    });
    document.getElementById('btn-compute-features')?.addEventListener('click', computeFeatures);
    document.getElementById('btn-compute-labels')?.addEventListener('click', computeLabels);
    document.getElementById('btn-run-backtests')?.addEventListener('click', runBacktests);
}

export { switchSignalLabTab, loadSignalLab, loadFeatureGroups, loadLabelTypes, loadScorers, computeFeatures, computeLabels, runBacktests, initSignalLab, renderFeatureGroups, renderLabelTypes, renderScorers, renderFeaturesResult, renderLabelsResult, renderBacktestsResult, loadDynamicFactorsOverview, renderDynamicFactorsOverview };
