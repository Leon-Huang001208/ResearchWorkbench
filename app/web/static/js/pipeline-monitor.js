/* ============================================================
   AlphaFoundry — Pipeline Monitor Module
   实时管线状态监控 + 活动日志
   ============================================================ */

import { apiCall, toast } from './core.js';

const POLL_INTERVAL_MS = 15000;

// ─── Pipeline State ──────────────────────────────────────────
let pipelineState = {
    stages: [],
    closed_loop: { last_run_at: null, last_result: {} },
    recent_activity: [],
};
let pollTimer = null;

// ─── Render Pipeline Monitor ─────────────────────────────────
export function renderPipelineMonitor() {
    const container = document.getElementById('pipeline-monitor-content');
    if (!container) return;

    container.innerHTML = `
        <div class="pipeline-toolbar">
            <h3>管线监控</h3>
            <div class="pipeline-toolbar-actions">
                <span id="pipeline-auto-status" class="pipeline-auto-badge">自动: --</span>
                <button id="btn-run-pipeline" class="btn-primary" onclick="window.runPipelineNow()">
                    立即运行
                </button>
            </div>
        </div>

        <!-- Stage Flow -->
        <div class="pipeline-stages" id="pipeline-stages">
            ${renderStageSkeletons()}
        </div>

        <!-- Activity Log -->
        <div class="pipeline-activity">
            <h4>实时活动日志</h4>
            <div class="activity-log" id="pipeline-activity-log">
                <div class="empty-state">等待管线事件...</div>
            </div>
        </div>

        <!-- Cumulative Stats -->
        <div class="pipeline-stats" id="pipeline-stats">
            <h4>累计统计</h4>
            <div class="stats-grid">
                <div class="stat-card"><div class="stat-value">--</div><div class="stat-label">今日信号</div></div>
                <div class="stat-card"><div class="stat-value">--</div><div class="stat-label">胜率</div></div>
                <div class="stat-card"><div class="stat-value">--</div><div class="stat-label">最佳事件类型</div></div>
                <div class="stat-card"><div class="stat-value">--</div><div class="stat-label">上次运行</div></div>
            </div>
        </div>
    `;

    // Start polling
    startPipelinePolling();
}

function renderStageSkeletons() {
    const stages = [
        { key: 'ingestion', label: '数据采集', icon: 'download' },
        { key: 'knowledge', label: '知识提取', icon: 'brain' },
        { key: 'signal_generation', label: '信号生成', icon: 'zap' },
        { key: 'backtest', label: '择时回测', icon: 'bar-chart' },
        { key: 'learning', label: '学习反馈', icon: 'refresh' },
    ];
    return stages.map((s, i) => {
        const arrow = i < stages.length - 1 ? '<span class="stage-arrow">→</span>' : '';
        return `
            <div class="stage-card" id="stage-${s.key}">
                <div class="stage-indicator idle"></div>
                <div class="stage-label">${s.label}</div>
                <div class="stage-count">--</div>
                <div class="stage-status">空闲</div>
            </div>
            ${arrow}
        `;
    }).join('');
}

// ─── Polling ─────────────────────────────────────────────────
function startPipelinePolling() {
    if (pollTimer) clearInterval(pollTimer);
    fetchPipelineStatus();
    pollTimer = setInterval(fetchPipelineStatus, POLL_INTERVAL_MS);
}

export function stopPipelinePolling() {
    if (pollTimer) {
        clearInterval(pollTimer);
        pollTimer = null;
    }
}

async function fetchPipelineStatus() {
    try {
        const status = await apiCall('GET', '/api/pipeline/status');
        pipelineState = status;
        updateStageCards(status.stages || []);
        updateActivityLog(status.recent_activity || []);
        updateStats(status);
        updateAutoBadge(status);
    } catch (e) {
        console.error('Failed to fetch pipeline status:', e);
    }
}

// ─── Stage Cards ─────────────────────────────────────────────
function updateStageCards(stages) {
    for (const stage of stages) {
        const card = document.getElementById(`stage-${stage.key}`);
        if (!card) continue;

        // Update indicator
        const indicator = card.querySelector('.stage-indicator');
        if (indicator) {
            indicator.className = 'stage-indicator ' + stage.status;
        }

        // Update count based on stage
        const countEl = card.querySelector('.stage-count');
        if (countEl) {
            countEl.textContent = formatStageCount(stage);
        }

        // Update status text
        const statusEl = card.querySelector('.stage-status');
        if (statusEl) {
            statusEl.textContent = stage.status === 'running' ? '运行中' : '空闲';
        }

        // Update last activity tooltip
        if (stage.last_activity) {
            card.title = '上次活动: ' + new Date(stage.last_activity).toLocaleTimeString();
        }
    }
}

function formatStageCount(stage) {
    const key = stage.key;
    if (key === 'ingestion') {
        return (stage.docs_today || 0).toLocaleString();
    }
    if (key === 'knowledge') {
        return (stage.events_today || 0).toLocaleString();
    }
    if (key === 'signal_generation') {
        return (stage.signals_today || 0).toLocaleString();
    }
    if (key === 'backtest') {
        return (stage.outcomes_today || 0).toLocaleString();
    }
    if (key === 'learning') {
        const wr = stage.win_rate;
        return wr != null ? (wr * 100).toFixed(0) + '%' : '--';
    }
    return '--';
}

// ─── Activity Log ────────────────────────────────────────────
function updateActivityLog(activities) {
    const logEl = document.getElementById('pipeline-activity-log');
    if (!logEl) return;

    if (!activities || activities.length === 0) {
        logEl.innerHTML = '<div class="empty-state">等待管线事件...</div>';
        return;
    }

    logEl.innerHTML = activities.slice(0, 50).map(a => {
        const time = new Date(a.datetime).toLocaleTimeString();
        const stageClass = a.stage ? `activity-${a.stage}` : '';
        return `
            <div class="activity-item ${stageClass}">
                <span class="activity-time">${time}</span>
                <span class="activity-stage">[${a.label || a.stage}]</span>
                <span class="activity-msg">${esc_html(a.message)}</span>
            </div>
        `;
    }).join('');
}

// ─── Cumulative Stats ────────────────────────────────────────
function updateStats(status) {
    const statsEl = document.getElementById('pipeline-stats');
    if (!statsEl) return;

    const signalGen = (status.stages || []).find(s => s.key === 'signal_generation') || {};
    const backtest = (status.stages || []).find(s => s.key === 'backtest') || {};
    const learning = (status.stages || []).find(s => s.key === 'learning') || {};
    const cl = status.closed_loop || {};

    const todaySignals = signalGen.signals_today || 0;
    const winRate = learning.win_rate != null ? (learning.win_rate * 100).toFixed(0) + '%' : '--';
    const lastRun = cl.last_run_at
        ? new Date(cl.last_run_at).toLocaleTimeString()
        : '从未运行';

    const lastResult = cl.last_result || {};
    const bestEventType = lastResult.best_event_type || '--';

    statsEl.innerHTML = `
        <h4>累计统计</h4>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value">${todaySignals}</div>
                <div class="stat-label">今日信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${winRate}</div>
                <div class="stat-label">胜率</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${bestEventType}</div>
                <div class="stat-label">最佳事件类型</div>
            </div>
            <div class="stat-card">
                <div class="stat-value">${lastRun}</div>
                <div class="stat-label">上次运行</div>
            </div>
        </div>
    `;
}

function updateAutoBadge(status) {
    const badge = document.getElementById('pipeline-auto-status');
    if (!badge) return;
    const cl = status.closed_loop || {};
    if (cl.last_run_at) {
        badge.textContent = '自动: ON';
        badge.className = 'pipeline-auto-badge auto-on';
    } else {
        badge.textContent = '自动: --';
        badge.className = 'pipeline-auto-badge';
    }
}

// ─── Run Pipeline Now ────────────────────────────────────────
export async function runPipelineNow() {
    const btn = document.getElementById('btn-run-pipeline');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '运行中...';
    }

    try {
        const summary = await apiCall('POST', '/api/pipeline/closed-loop');
        toast('闭循环完成: ' + summary.signals_generated + ' 信号, ' + summary.signals_backtested + ' 回测', 'success');
        // Immediately refresh
        await fetchPipelineStatus();
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '立即运行';
        }
    }
}

// ─── SSE Event Handler ───────────────────────────────────────
export function handlePipelineSSEEvent(event) {
    // Update pipeline state from SSE events
    const type = event.type || '';
    if (type.startsWith('pipeline.') || type.startsWith('knowledge.') ||
        type.startsWith('reasoning.') || type.startsWith('agent.') ||
        type.startsWith('timing.') || type === 'document_parsed' ||
        type === 'event_created' || type === 'queue_update') {

        // Prepend to activity log optimistically
        prependActivityItem(event);

        // Update stage indicators based on event type
        updateStageFromSSE(type, event.payload || {});
    }
}

function prependActivityItem(event) {
    const logEl = document.getElementById('pipeline-activity-log');
    if (!logEl) return;

    const time = new Date().toLocaleTimeString();
    const stage = eventTypeToStage(event.type);
    const stageLabel = stageLabels[stage] || stage;
    const msg = formatSSEMessage(event.type, event.payload || {});

    const item = document.createElement('div');
    item.className = `activity-item activity-${stage}`;
    item.innerHTML = `
        <span class="activity-time">${time}</span>
        <span class="activity-stage">[${stageLabel}]</span>
        <span class="activity-msg">${esc_html(msg)}</span>
    `;

    // Remove empty state if present
    const emptyState = logEl.querySelector('.empty-state');
    if (emptyState) emptyState.remove();

    logEl.insertBefore(item, logEl.firstChild);

    // Trim to 100 items
    while (logEl.children.length > 100) {
        logEl.lastChild.remove();
    }
}

function updateStageFromSSE(eventType, payload) {
    const stage = eventTypeToStage(eventType);
    const card = document.getElementById(`stage-${stage}`);
    if (!card) return;

    // Flash indicator
    const indicator = card.querySelector('.stage-indicator');
    if (indicator) {
        indicator.className = 'stage-indicator running';
        setTimeout(() => {
            if (indicator) indicator.className = 'stage-indicator idle';
        }, 3000);
    }

    // Update status text briefly
    const statusEl = card.querySelector('.stage-status');
    if (statusEl) {
        statusEl.textContent = '运行中';
        setTimeout(() => {
            if (statusEl) statusEl.textContent = '空闲';
        }, 3000);
    }
}

// ─── Helpers ─────────────────────────────────────────────────
function eventTypeToStage(type) {
    const map = {
        'document_parsed': 'knowledge',
        'event_created': 'knowledge',
        'queue_update': 'knowledge',
        'knowledge.entity_resolved': 'knowledge',
        'knowledge.propagation_analyzed': 'knowledge',
        'pipeline.signal.generated': 'signal_generation',
        'pipeline.closed_loop.started': 'signal_generation',
        'pipeline.backtest.completed': 'backtest',
        'pipeline.closed_loop.completed': 'backtest',
        'pipeline.episode.recorded': 'learning',
        'pipeline.pattern.learned': 'learning',
        'reasoning.completed': 'signal_generation',
        'agent.swarm.completed': 'signal_generation',
        'timing.evaluated': 'backtest',
    };
    return map[type] || 'knowledge';
}

const stageLabels = {
    ingestion: '数据采集',
    knowledge: '知识提取',
    signal_generation: '信号生成',
    backtest: '择时回测',
    learning: '学习反馈',
};

function formatSSEMessage(type, payload) {
    const templates = {
        'document_parsed': `文档解析: ${payload.title || payload.doc_id || '?'} (${payload.event_count || 0} 事件)`,
        'event_created': `事件创建: ${payload.summary || payload.event_id || '?'}`,
        'queue_update': `队列更新: ${payload.processed || 0} 项已处理`,
        'pipeline.signal.generated': `生成 ${payload.count || 0} 个信号`,
        'pipeline.backtest.completed': `回测完成: ${payload.count || 0} 个信号`,
        'pipeline.closed_loop.completed': `闭环完成 (${payload.duration_ms || 0}ms)`,
        'knowledge.entity_resolved': `实体解析: ${payload.canonical_name || '?'}`,
        'knowledge.propagation_analyzed': `传播分析: ${payload.steps || 0} 步`,
        'reasoning.completed': `推理完成: ${payload.scenario_count || 0} 场景`,
        'agent.swarm.completed': `Agent 辩论: ${payload.views || 0} 观点, ${payload.conflicts || 0} 冲突`,
        'timing.evaluated': `择时: ${payload.action || '?'} (${payload.readiness_score || '?'})`,
    };
    return templates[type] || type;
}

function esc_html(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

// ─── Window Export ───────────────────────────────────────────
window.runPipelineNow = runPipelineNow;
