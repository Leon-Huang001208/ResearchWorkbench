/* ============================================================
   Research Workbench — Review Queue Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

async function loadReviewStats() {
    try {
        const stats = await apiCall('GET', '/api/review/stats');
        const wrap = document.getElementById('review-stats');
        if (wrap) {
            wrap.innerHTML = `
                <div class="stat-card pending"><div class="stat-value">${stats.pending_assertions ?? 0}</div><div class="stat-label">待审核</div></div>
                <div class="stat-card"><div class="stat-value" style="border-top-color:var(--success)">${stats.approved_assertions ?? 0}</div><div class="stat-label">已批准</div></div>
                <div class="stat-card"><div class="stat-value" style="border-top-color:var(--danger)">${stats.rejected_assertions ?? 0}</div><div class="stat-label">已拒绝</div></div>
            `;
        }
        const statReview = document.getElementById('stat-review');
        if (statReview) statReview.textContent = stats.pending_assertions ?? 0;
    } catch (e) {
        console.error('Failed to load review stats:', e);
    }
}

async function loadReviewPending() {
    try {
        const items = await apiCall('GET', '/api/review/pending');
        renderReviewTable(items);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderReviewTable(items) {
    const wrap = document.getElementById('review-table');
    if (!wrap) return;
    if (!items || !items.length) {
        wrap.innerHTML = '<p class="empty-state">暂无待审核项</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>谓词</th><th>对象</th><th>置信度</th><th>来源</th><th>操作</th></tr></thead>
        <tbody>${items.map(i => `
            <tr>
                <td title="${esc(i.assertion_id)}">${esc((i.assertion_id || '').substring(0, 8))}</td>
                <td>${esc(i.subject_entity_id || '—')}</td>
                <td>${esc(i.predicate)}</td>
                <td>${esc(i.object_value || '—')}</td>
                <td>${i.confidence ? i.confidence.toFixed(2) : '—'}</td>
                <td>${esc((i.source_doc_id || '').substring(0, 8) || '—')}</td>
                <td class="actions">
                    <button class="btn-sm btn-approve" onclick="approveItem('${esc(i.assertion_id)}')">批准</button>
                    <button class="btn-sm btn-reject" onclick="rejectItem('${esc(i.assertion_id)}')">拒绝</button>
                </td>
            </tr>`).join('')}</tbody>
    </table>`;
}

async function approveItem(id) {
    try {
        await apiCall('POST', `/api/review/approve/${id}`);
        toast('已批准', 'success');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function rejectItem(id) {
    try {
        await apiCall('POST', `/api/review/reject/${id}`);
        toast('已拒绝', 'info');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

function initReview() {
    document.getElementById('btn-refresh-review')?.addEventListener('click', loadReviewPending);
}

export { loadReviewStats, loadReviewPending, approveItem, rejectItem, initReview };
