/* ============================================================
   Research Workbench — Global Search Module
   ============================================================ */

import { apiCall, esc } from './core.js';

async function globalSearch(query) {
    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}`);
        renderSearchResults(results, query);
    } catch (e) {
        console.error('Search failed:', e);
    }
}

function renderSearchResults(results, query) {
    const dropdown = document.getElementById('search-results-dropdown');
    if (!dropdown) return;

    let total = 0;
    const groups = [
        { key: 'symbols', title: '标的' },
        { key: 'event_types', title: '事件类型' },
        { key: 'theses', title: '论题' },
        { key: 'source_docs', title: '源文档' },
        { key: 'failure_memories', title: '失败记忆' },
        { key: 'market_episodes', title: '市场片段' },
        { key: 'signals', title: '信号' },
        { key: 'events', title: '事件' },
        { key: 'outcomes', title: '结果' },
        { key: 'reviews', title: '审核' },
    ];
    groups.forEach(g => total += (results[g.key]?.length || 0));

    if (total === 0) {
        dropdown.innerHTML = '<div class="search-empty">未找到结果</div>';
        dropdown.classList.remove('hidden');
        return;
    }

    let html = '';
    groups.forEach(g => {
        const items = results[g.key];
        if (!items || !items.length) return;
        html += `<div class="search-group"><div class="search-group-title">${g.title} (${items.length})</div>`;
        items.slice(0, 5).forEach(item => {
            let label = '';
            let link = '#';
            if (g.key === 'symbols') {
                label = `${item.symbol} — ${item.name || ''}`;
                link = `javascript:analyzeAssetByCode('${esc(item.symbol || item.code)}')`;
            } else if (g.key === 'signals') {
                label = item.thesis || item.signal_id;
                link = `javascript:navigateToSignalDetail('${esc(item.signal_id)}')`;
            } else if (g.key === 'events') {
                label = item.title || item.event_id;
            } else if (g.key === 'event_types') {
                label = item;
            } else if (g.key === 'theses') {
                label = item;
            } else if (g.key === 'source_docs') {
                label = item.title || item;
            } else if (g.key === 'failure_memories') {
                label = item.title || item.failure_id;
            } else {
                label = item.title || item.id || JSON.stringify(item).substring(0, 40);
            }
            html += `<div class="search-item"><a href="${link}">${esc(String(label))}</a></div>`;
        });
        html += '</div>';
    });

    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
}

function navigateToSignalDetail(signalId) {
    document.getElementById('search-results-dropdown').classList.add('hidden');
    document.getElementById('global-search').value = '';
    window.showSignalDetail(signalId);
}

export { globalSearch, renderSearchResults, navigateToSignalDetail };
