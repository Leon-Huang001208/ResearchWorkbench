/* ============================================================
   Research Workbench — Memory & Learning Module
   ============================================================ */

import { apiCall, esc } from './core.js';

function loadMemoryPage() { loadEpisodes(); }

async function loadEpisodes() {
    const el = document.getElementById('memory-episodes');
    if (el) el.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>加载中...</span></div>';
    try {
        const data = await apiCall('GET', '/api/memory/episodes');
        if (el) el.innerHTML = (data.episodes || data || []).slice(0, 20).map(e => `
            <div class="memory-item">
                <span class="badge">${esc(e.event_type || '')}</span>
                <span>${esc(e.summary || e.title || '')}</span>
            </div>
        `).join('') || '<div class="empty-state">暂无记忆</div>';
    } catch (e) {
        console.error(e);
        if (el) el.innerHTML = `<div class="error-state"><span class="error-icon">!</span><span class="error-msg">加载失败</span></div>`;
    }
}

async function loadStrategies() {
    try {
        const data = await apiCall('GET', '/api/memory/strategies');
        const el = document.getElementById('memory-strategies');
        if (el) el.innerHTML = (data.strategies || data || []).map(s => `<div>${esc(s.name || s)}</div>`).join('') || '<div class="empty-state">暂无策略</div>';
    } catch (e) { console.error(e); }
}

async function loadFailures() {
    const el = document.getElementById('memory-failures');
    if (el) el.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><span>加载中...</span></div>';
    try {
        const data = await apiCall('GET', '/api/memory/failures');
        if (el) el.innerHTML = (data.failures || data || []).slice(0, 20).map(f => `
            <div class="failure-item">
                <span>${esc(f.failure_reason || f.reason || '')}</span>
                <span>${esc(f.lesson || '')}</span>
            </div>
        `).join('') || '<div class="empty-state">无失败记录</div>';
    } catch (e) {
        console.error(e);
        if (el) el.innerHTML = `<div class="error-state"><span class="error-icon">!</span><span class="error-msg">加载失败</span></div>`;
    }
}

async function loadEventSummary() {
    try {
        const type = document.getElementById('memory-event-type')?.value || '';
        const data = await apiCall('GET', `/api/memory/summarize/${encodeURIComponent(type || 'all')}`);
        const el = document.getElementById('memory-summary');
        if (el) el.innerHTML = `<pre>${esc(JSON.stringify(data, null, 2))}</pre>`;
    } catch (e) { console.error(e); }
}

function initMemory() {
    document.getElementById('btn-load-failures')?.addEventListener('click', loadFailures);
    document.getElementById('btn-event-summary')?.addEventListener('click', loadEventSummary);
}

export { loadMemoryPage, loadEpisodes, loadStrategies, loadFailures, loadEventSummary, initMemory };
