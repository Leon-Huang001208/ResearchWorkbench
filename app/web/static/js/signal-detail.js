/* ============================================================
   AlphaFoundry — Signal Detail Module
   Signal detail view, audit trail timeline
   ============================================================ */

import { apiCall, esc } from './core.js';

async function showSignalDetail(signalId) {
    document.querySelectorAll('.content-section').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.activity-btn[data-section]').forEach(b => b.classList.remove('active'));

    let detailSection = document.getElementById('section-signal-detail');
    if (!detailSection) {
        detailSection = document.createElement('section');
        detailSection.id = 'section-signal-detail';
        detailSection.className = 'content-section active';
        document.querySelector('.main-content').appendChild(detailSection);
    }
    detailSection.classList.add('active');
    detailSection.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const data = await apiCall('GET', `/api/signals/${encodeURIComponent(signalId)}/detail`);
        renderSignalDetail(data, detailSection);
    } catch (e) {
        detailSection.innerHTML = `<div class="error-state">加载失败: ${esc(e.message)}</div>`;
    }
}

function renderSignalDetail(data, container) {
    const s = data.signal || {};
    const timing = data.timing;
    const outcome = data.outcome;
    const event = data.event;
    const auditTrail = data.audit_trail || [];

    let html = `
        <div class="detail-header">
            <button class="btn-back" onclick="navigateTo('signals')">← 返回信号列表</button>
            <h2 class="section-title">信号详情</h2>
        </div>

        <div class="detail-grid">
            <!-- 信号基本信息 -->
            <div class="card detail-card">
                <h3>基本信息</h3>
                <div class="detail-field"><span class="detail-label">ID</span><span class="detail-value">${esc(s.signal_id)}</span></div>
                <div class="detail-field"><span class="detail-label">主体</span><span class="detail-value">${esc(s.subject_id)}</span></div>
                <div class="detail-field"><span class="detail-label">论点</span><span class="detail-value">${esc(s.thesis)}</span></div>
                <div class="detail-field"><span class="detail-label">预测期</span><span class="detail-value">${esc(s.horizon)}</span></div>
                <div class="detail-field"><span class="detail-label">分数</span><span class="detail-value">${s.score?.toFixed(3) ?? '—'}</span></div>
                <div class="detail-field"><span class="detail-label">置信度</span><span class="detail-value">${s.confidence?.toFixed(3) ?? '—'}</span></div>
                <div class="detail-field"><span class="detail-label">状态</span><span class="detail-value"><span class="status-badge status-${s.status}">${esc(s.status)}</span></span></div>
                ${s.event_type ? `<div class="detail-field"><span class="detail-label">事件类型</span><span class="detail-value">${esc(s.event_type)}</span></div>` : ''}
                ${s.diffusion_stage ? `<div class="detail-field"><span class="detail-label">传播阶段</span><span class="detail-value">${esc(s.diffusion_stage)}</span></div>` : ''}
                ${s.market_regime ? `<div class="detail-field"><span class="detail-label">市场状态</span><span class="detail-value">${esc(s.market_regime)}</span></div>` : ''}
            </div>

            <!-- 择时建议 -->
            <div class="card detail-card">
                <h3>择时建议</h3>
                ${timing ? `
                    <div class="detail-field"><span class="detail-label">决策</span><span class="detail-value"><span class="timing-badge timing-${timing.action}">${esc(timing.action)}</span></span></div>
                    <div class="detail-field"><span class="detail-label">就绪度</span><span class="detail-value">${(timing.readiness_score * 100).toFixed(1)}%</span></div>
                    <div class="detail-field"><span class="detail-label">市场状态</span><span class="detail-value">${esc(timing.market_regime)}</span></div>
                    ${timing.blockers?.length ? `<div class="detail-field"><span class="detail-label">阻止因素</span><span class="detail-value"><ul>${timing.blockers.map(b => `<li>${esc(b)}</li>`).join('')}</ul></span></div>` : ''}
                    ${timing.rationale?.length ? `<div class="detail-field"><span class="detail-label">逻辑</span><span class="detail-value"><ul>${timing.rationale.map(r => `<li>${esc(r)}</li>`).join('')}</ul></span></div>` : ''}
                ` : '<p class="empty-state">暂无择时建议</p>'}
            </div>

            <!-- 关联事件 -->
            <div class="card detail-card">
                <h3>关联事件</h3>
                ${event ? `
                    <div class="detail-field"><span class="detail-label">事件ID</span><span class="detail-value">${esc(event.event_id)}</span></div>
                    <div class="detail-field"><span class="detail-label">类型</span><span class="detail-value">${esc(event.event_type)}</span></div>
                    <div class="detail-field"><span class="detail-label">摘要</span><span class="detail-value">${esc(event.summary)}</span></div>
                    <div class="detail-field"><span class="detail-label">方向</span><span class="detail-value">${esc(event.impact_direction)}</span></div>
                    <div class="detail-field"><span class="detail-label">置信度</span><span class="detail-value">${event.confidence?.toFixed(2) ?? '—'}</span></div>
                ` : '<p class="empty-state">无关联事件</p>'}
            </div>

            <!-- 关联 Outcome -->
            <div class="card detail-card">
                <h3>结果评估</h3>
                ${outcome ? `
                    <div class="detail-field"><span class="detail-label">收益</span><span class="detail-value ${outcome.outcome_return > 0 ? 'positive' : 'negative'}">${outcome.outcome_return > 0 ? '+' : ''}${outcome.outcome_return?.toFixed(2)}%</span></div>
                    <div class="detail-field"><span class="detail-label">超额收益</span><span class="detail-value ${outcome.outcome_excess_return > 0 ? 'positive' : 'negative'}">${outcome.outcome_excess_return > 0 ? '+' : ''}${outcome.outcome_excess_return?.toFixed(2)}%</span></div>
                    <div class="detail-field"><span class="detail-label">最大回撤</span><span class="detail-value">${outcome.max_drawdown?.toFixed(2) ?? '—'}%</span></div>
                    ${outcome.lesson ? `<div class="detail-field"><span class="detail-label">经验教训</span><span class="detail-value">${esc(outcome.lesson)}</span></div>` : ''}
                ` : '<p class="empty-state">暂无结果评估</p>'}
            </div>
        </div>

        <!-- 审计轨迹 -->
        <div class="card detail-card" style="margin-top: 16px;">
            <h3>审计轨迹</h3>
            <div id="audit-trail-container">
                ${auditTrail.length ? renderAuditTrailTimeline(auditTrail) : '<p class="empty-state">暂无审计记录</p>'}
            </div>
        </div>
    `;

    container.innerHTML = html;
}

function renderAuditTrailTimeline(trail) {
    if (!trail.length) return '<p class="empty-state">暂无审计记录</p>';
    return `<div class="audit-timeline">${trail.map(entry => `
        <div class="audit-entry">
            <div class="audit-entry-dot"></div>
            <div class="audit-entry-content">
                <div class="audit-entry-header">
                    <span class="audit-action badge">${esc(entry.action)}</span>
                    <span class="audit-actor">${esc(entry.actor)}</span>
                    <span class="audit-time">${esc(entry.timestamp || '')}</span>
                </div>
                ${entry.details && Object.keys(entry.details).length ?
                    `<div class="audit-details">${Object.entries(entry.details).map(([k,v]) => `<span class="audit-detail-item"><strong>${esc(k)}:</strong> ${esc(String(v))}</span>`).join(', ')}</div>` : ''}
            </div>
        </div>
    `).join('')}</div>`;
}

async function loadAuditTrail(entityType, entityId) {
    const container = document.getElementById('audit-trail-container');
    if (!container) return;
    container.innerHTML = '<div class="loading">加载中...</div>';
    try {
        const data = await apiCall('GET', `/api/audit/trail/${entityType}/${encodeURIComponent(entityId)}`);
        const trail = data.trail || [];
        container.innerHTML = trail.length ? renderAuditTrailTimeline(trail) : '<p class="empty-state">暂无审计记录</p>';
    } catch (e) {
        container.innerHTML = `<div class="error-state">加载失败: ${esc(e.message)}</div>`;
    }
}

export { showSignalDetail, renderSignalDetail, renderAuditTrailTimeline, loadAuditTrail };
