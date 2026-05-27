/* ============================================================
   AlphaFoundry — Document Ingest Module
   ============================================================ */

import { apiCall, toast, esc } from './core.js';

async function ingestText() {
    const text = document.getElementById('ingest-text').value.trim();
    if (!text) return toast('请输入文本内容', 'error');

    const loading = document.getElementById('ingest-loading');
    const result = document.getElementById('ingest-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/ingest/text', {
            text,
            source_type: document.getElementById('ingest-source-type').value,
            source_name: document.getElementById('ingest-source-name').value.trim() || 'unknown',
            title: document.getElementById('ingest-title').value.trim() || undefined,
        });
        renderIngestResult(data);
        result.classList.remove('hidden');
        toast('摄入完成', 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderIngestResult(data) {
    const wrap = document.getElementById('ingest-result');
    wrap.innerHTML = `
        <div class="ingest-summary">
            <h3>摄入成功 — ${esc(data.title || data.doc_id)}</h3>
            <div class="ingest-stats">
                <div class="ingest-stat"><div class="num">${data.assertions_extracted ?? 0}</div><div class="lbl">提取断言</div></div>
                <div class="ingest-stat"><div class="num">${data.assertions_approved ?? 0}</div><div class="lbl">已批准</div></div>
                <div class="ingest-stat"><div class="num">${data.assertions_pending ?? 0}</div><div class="lbl">待审核</div></div>
                <div class="ingest-stat"><div class="num">${data.events_extracted ?? 0}</div><div class="lbl">提取事件</div></div>
                <div class="ingest-stat"><div class="num">${data.events_approved ?? 0}</div><div class="lbl">事件已批准</div></div>
            </div>
        </div>`;
}

export { ingestText, renderIngestResult };
