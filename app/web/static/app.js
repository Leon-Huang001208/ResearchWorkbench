
/* ============================================================
   AlphaFoundry — Frontend Application Logic
   ============================================================ */

// ─── Theme & i18n Init ───────────────────────────────────────
(function initTheme() {
    const saved = localStorage.getItem('af-theme') || 'light';
    document.documentElement.setAttribute('data-theme', saved);
})();

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('af-theme', theme);
    document.querySelectorAll('#settings-panel-theme .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.themeVal === theme);
    });
    try { applyChartDefaults(); } catch(e) {}
}

// Global switchers (called from onclick in HTML)
function switchTheme(theme) {
    applyTheme(theme);
}

function switchLang(lang) {
    I18N.setLang(lang);
    document.querySelectorAll('#settings-panel-language .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.lang === lang);
    });
    const sl = document.getElementById('status-lang-label');
    if (sl) sl.textContent = lang === 'zh' ? '中文' : 'EN';
}

// Color scheme
(function initColorScheme() {
    const saved = localStorage.getItem('af-color-scheme') || 'claude';
    document.documentElement.setAttribute('data-color-scheme', saved);
})();

function applyColorScheme(scheme) {
    document.documentElement.setAttribute('data-color-scheme', scheme);
    localStorage.setItem('af-color-scheme', scheme);
    document.querySelectorAll('#settings-panel-color .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.colorScheme === scheme);
    });
}

function switchColorScheme(scheme) {
    applyColorScheme(scheme);
}

// ─── API Helper ───────────────────────────────────────────────
const API_BASE = '';

async function apiCall(method, url, body = null) {
    const opts = {
        method,
        headers: { 'Content-Type': 'application/json' },
    };
    if (body) opts.body = JSON.stringify(body);
    const resp = await fetch(`${API_BASE}${url}`, opts);
    if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: resp.statusText }));
        throw new Error(err.error || err.detail || `HTTP ${resp.status}`);
    }
    return resp.json();
}

// ─── Toast ────────────────────────────────────────────────────
function toast(msg, type = 'info') {
    const el = document.getElementById('toast');
    el.textContent = msg;
    el.className = `toast toast-${type}`;
    setTimeout(() => el.classList.add('hidden'), 3500);
}

// ─── Chart Instances (for cleanup) ───────────────────────────
let chartPriceVolume = null;
let chartScenarioProb = null;

// ─── Navigation ───────────────────────────────────────────────
function navigateTo(section) {
    document.querySelectorAll('.activity-btn[data-section]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(p => p.classList.remove('active'));
    document.querySelectorAll(`.activity-btn[data-section="${section}"]`).forEach(b => b.classList.add('active'));
    document.getElementById(`section-${section}`).classList.add('active');
    // Load data
    if (section === 'dashboard') { loadDashboard(); startCrawlFeedPolling(); startWorkersPolling(); }
    else { stopCrawlFeedPolling(); stopWorkersPolling(); }
    if (section === 'signals') loadSignals();
    if (section === 'review') { loadReviewStats(); loadReviewPending(); }
    if (section === 'memory') loadMemoryPage();
    if (section === 'outcomes') loadOutcomes();
    if (section === 'signal-lab') loadSignalLab();
    if (section === 'templates') loadTemplatesPage();
}

// ─── Dashboard Tab Switching ──────────────────────────────────
function switchDashTab(tabName) {
    document.querySelectorAll('.dash-tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.dash-tab-panel').forEach(p => p.classList.remove('active'));
    const tabBtn = document.querySelector(`.dash-tab[data-dash-tab="${tabName}"]`);
    const panel = document.getElementById(`dash-panel-${tabName}`);
    if (tabBtn) tabBtn.classList.add('active');
    if (panel) panel.classList.add('active');
}

// Wait for DOM ready before binding all interactive events
document.addEventListener('DOMContentLoaded', () => {
    // Navigation buttons
    document.querySelectorAll('.activity-btn[data-section]').forEach(btn => {
        btn.addEventListener('click', () => navigateTo(btn.dataset.section));
    });

    // Dashboard tab switching
    document.querySelectorAll('.dash-tab').forEach(tab => {
        tab.addEventListener('click', () => switchDashTab(tab.dataset.dashTab));
    });

    // Settings popover toggle
    document.getElementById('btn-settings')?.addEventListener('click', (e) => {
        e.stopPropagation();
        const popover = document.getElementById('settings-popover');
        if (popover) {
            popover.classList.toggle('hidden');
            I18N.applyAll();
        }
    });

    // Close settings popover on outside click
    document.addEventListener('click', (e) => {
        const popover = document.getElementById('settings-popover');
        const btn = document.getElementById('btn-settings');
        if (popover && !popover.contains(e.target) && !btn?.contains(e.target)) {
            popover.classList.add('hidden');
        }
    });

    // Asset search input
    const assetInput = document.getElementById('asset-code');
    if (assetInput) {
        assetInput.addEventListener('input', (e) => {
            clearTimeout(assetSearchDebounceTimer);
            const query = e.target.value.trim();
            assetSearchDebounceTimer = setTimeout(() => searchAssets(query), 200);
        });

        assetInput.addEventListener('keydown', handleAssetSearchKeydown);

        assetInput.addEventListener('focus', (e) => {
            if (e.target.value.trim()) {
                searchAssets(e.target.value.trim());
            }
        });
    }

    // Close asset search dropdown on outside click
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('asset-search-dropdown');
        const input = document.getElementById('asset-code');
        if (dropdown && !dropdown.contains(e.target) && e.target !== input) {
            dropdown.classList.add('hidden');
        }
    });

    // Scenario analysis button
    document.getElementById('btn-generate-scenarios')?.addEventListener('click', generateScenarios);
    
    // Event signal button
    document.getElementById('btn-generate-event-signal')?.addEventListener('click', generateEventSignal);
    
    // Industry chain button
    document.getElementById('btn-load-industry')?.addEventListener('click', loadIndustryChain);
    
    // Review refresh button
    document.getElementById('btn-refresh-review')?.addEventListener('click', () => {
        loadReviewPending();
    });
    
    // Create signal button
    document.getElementById('btn-create-signal')?.addEventListener('click', createSignal);
    
    // Ingest text button
    document.getElementById('btn-ingest')?.addEventListener('click', ingestText);
    
    // Load failures button
    document.getElementById('btn-load-failures')?.addEventListener('click', loadFailures);
    
    // Load event summary button
    document.getElementById('btn-event-summary')?.addEventListener('click', loadEventSummary);

    // Outcomes page: refresh button
    document.getElementById('btn-refresh-outcomes')?.addEventListener('click', loadOutcomes);

    // Outcomes page: event type filter change
    document.getElementById('outcome-event-type-filter')?.addEventListener('change', loadOutcomes);

    // Closed loop page: run button
    document.getElementById('btn-run-closed-loop')?.addEventListener('click', runClosedLoop);

    // Signal Lab events
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchSignalLabTab(btn.dataset.tab));
    });
    document.getElementById('btn-compute-features')?.addEventListener('click', computeFeatures);
    document.getElementById('btn-compute-labels')?.addEventListener('click', computeLabels);
    document.getElementById('btn-run-backtests')?.addEventListener('click', runBacktests);

    // Templates events - both list view and detail view
    document.querySelectorAll('#section-templates .tab-btn, #template-detail-view .tab-btn').forEach(btn => {
        btn.addEventListener('click', () => switchTemplatesTab(btn.dataset.tab));
    });
    document.getElementById('btn-back-to-templates')?.addEventListener('click', goBackToTemplates);
    document.getElementById('btn-upload-template')?.addEventListener('click', uploadTemplate);
    document.getElementById('btn-create-yaml-template')?.addEventListener('click', createYamlConfig);
    document.getElementById('btn-render-report')?.addEventListener('click', renderReportFromTemplate);
    document.getElementById('btn-discover-placeholders')?.addEventListener('click', discoverPlaceholders);
    document.getElementById('btn-refresh-templates')?.addEventListener('click', loadTemplatesList);
    document.getElementById('btn-save-placeholder-config')?.addEventListener('click', savePlaceholderConfig);
    document.getElementById('btn-export-yaml')?.addEventListener('click', exportYamlConfig);
    document.getElementById('btn-generate-all-ai')?.addEventListener('click', generateAllAiFields);
    document.getElementById('btn-edit-templates')?.addEventListener('click', toggleEditMode);
    document.getElementById('btn-save-templates-order')?.addEventListener('click', saveTemplatesOrder);
    document.getElementById('btn-new-template')?.addEventListener('click', openUploadModal);
    document.getElementById('btn-close-upload-modal')?.addEventListener('click', closeUploadModal);
    document.getElementById('btn-cancel-upload')?.addEventListener('click', closeUploadModal);
    document.getElementById('btn-close-edit-modal')?.addEventListener('click', closeEditTemplateModal);
    document.getElementById('btn-cancel-edit')?.addEventListener('click', closeEditTemplateModal);
    document.getElementById('btn-save-edit')?.addEventListener('click', saveTemplateEdit);

    // 渲染标签页模板选择变化
    document.getElementById('render-template-select')?.addEventListener('change', (e) => {
        const templateName = e.target.value;
        const fileType = document.getElementById('render-type-select').value || 'docx';
        if (templateName) {
            loadTemplatePlaceholdersForRender(templateName, fileType);
        } else {
            document.getElementById('render-placeholders-container').innerHTML = '';
        }
    });

    // 渲染标签页类型选择变化
    document.getElementById('render-type-select')?.addEventListener('change', (e) => {
        const templateName = document.getElementById('render-template-select').value;
        const fileType = e.target.value || 'docx';
        if (templateName) {
            loadTemplatePlaceholdersForRender(templateName, fileType);
        }
    });

    // Drop zone and file select handled in initTemplateDropZone()

    // Global search input
    document.getElementById('global-search')?.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        const q = e.target.value.trim();
        if (q.length < 2) {
            document.getElementById('search-results-dropdown')?.classList.add('hidden');
            return;
        }
        searchDebounceTimer = setTimeout(() => globalSearch(q), 300);
    });
    document.getElementById('global-search')?.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.getElementById('search-results-dropdown')?.classList.add('hidden');
            e.target.blur();
        }
    });
});

// ─── Global Search ────────────────────────────────────────────
let searchDebounceTimer = null;

// Close search dropdown on outside click
document.addEventListener('click', (e) => {
    const dropdown = document.getElementById('search-results-dropdown');
    const searchInput = document.getElementById('global-search');
    if (dropdown && !dropdown.contains(e.target) && e.target !== searchInput) {
        dropdown.classList.add('hidden');
    }
});

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

    // Calculate total across all result groups
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
        dropdown.innerHTML = `<div class="search-result-group"><div class="search-empty">未找到 "${esc(query)}" 相关结果</div></div>`;
        dropdown.classList.remove('hidden');
        return;
    }

    let html = '';

    // Symbols
    if (results.symbols?.length) {
        html += `<div class="search-result-group"><div class="group-title">标的 (${results.symbols.length})</div>`;
        html += results.symbols.map(s => `
            <div class="search-result-item">
                <div class="result-title">${esc(s.symbol)} — ${esc(s.name || s.display_name)}</div>
                <div class="result-subtitle">${esc(s.industry)} • ${esc(s.asset_type)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Event Types
    if (results.event_types?.length) {
        html += `<div class="search-result-group"><div class="group-title">事件类型 (${results.event_types.length})</div>`;
        html += results.event_types.map(et => `
            <div class="search-result-item">
                <div class="result-title">${esc(et.event_type)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Theses
    if (results.theses?.length) {
        html += `<div class="search-result-group"><div class="group-title">论题 (${results.theses.length})</div>`;
        html += results.theses.map(t => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(t.signal_id)}')">
                <div class="result-title">${esc(t.thesis)}</div>
                <div class="result-subtitle">${esc(t.subject_id)} • score: ${t.score.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Source Docs
    if (results.source_docs?.length) {
        html += `<div class="search-result-group"><div class="group-title">源文档 (${results.source_docs.length})</div>`;
        html += results.source_docs.map(doc => `
            <div class="search-result-item">
                <div class="result-title">${esc(doc.title)}</div>
                <div class="result-subtitle">${esc(doc.source_type)} • ${doc.ingested_at ? new Date(doc.ingested_at).toLocaleDateString() : ''}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Failure Memory
    if (results.failure_memories?.length) {
        html += `<div class="search-result-group"><div class="group-title">失败记忆 (${results.failure_memories.length})</div>`;
        html += results.failure_memories.map(f => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(f.signal_id)}')">
                <div class="result-title">${esc(f.failure_reason || f.subject_id)}</div>
                <div class="result-subtitle">${esc(f.lesson)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Market Episodes
    if (results.market_episodes?.length) {
        html += `<div class="search-result-group"><div class="group-title">市场片段 (${results.market_episodes.length})</div>`;
        html += results.market_episodes.map(me => `
            <div class="search-result-item">
                <div class="result-title">${esc(me.title)}</div>
                <div class="result-subtitle">${esc(me.tags)} • ${me.start_date ? new Date(me.start_date).toLocaleDateString() : ''}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Signals
    if (results.signals?.length) {
        html += `<div class="search-result-group"><div class="group-title">信号 (${results.signals.length})</div>`;
        html += results.signals.map(s => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(s.signal_id)}')">
                <div class="result-title">${esc(s.thesis)}</div>
                <div class="result-subtitle">${esc(s.subject_id)} • ${esc(s.event_type)} • ${I18N.t('dashboard.score')}: ${s.score.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Events
    if (results.events?.length) {
        html += `<div class="search-result-group"><div class="group-title">事件 (${results.events.length})</div>`;
        html += results.events.map(e => `
            <div class="search-result-item">
                <div class="result-title">${esc(e.summary)}</div>
                <div class="result-subtitle">${esc(e.event_type)} • confidence: ${e.confidence.toFixed(2)}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Outcomes
    if (results.outcomes?.length) {
        html += `<div class="search-result-group"><div class="group-title">结果 (${results.outcomes.length})</div>`;
        html += results.outcomes.map(o => `
            <div class="search-result-item" onclick="navigateToSignalDetail('${esc(o.signal_id)}')">
                <div class="result-title">${esc(o.lesson || o.subject_id)}</div>
                <div class="result-subtitle">${o.outcome_excess_return > 0 ? '+' : ''}${o.outcome_excess_return.toFixed(2)}% 超额收益</div>
            </div>
        `).join('');
        html += '</div>';
    }

    // Reviews
    if (results.reviews?.length) {
        html += `<div class="search-result-group"><div class="group-title">审核 (${results.reviews.length})</div>`;
        html += results.reviews.map(r => `
            <div class="search-result-item">
                <div class="result-title">${esc(r.action)} — ${esc(r.entity_type)}/${esc(r.entity_id.substring(0,8))}</div>
            </div>
        `).join('');
        html += '</div>';
    }

    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');
}

function navigateToSignalDetail(signalId) {
    document.getElementById('search-results-dropdown').classList.add('hidden');
    document.getElementById('global-search').value = '';
    showSignalDetail(signalId);
}

// ─── Chart.js Default Theming ─────────────────────────────────
function getChartColors() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    return {
        grid: isDark ? 'rgba(148,163,184,.15)' : 'rgba(0,0,0,.06)',
        text: isDark ? '#94a3b8' : '#64748b',
        blue: '#3182ce',
        orange: '#ed8936',
        green: '#38a169',
        red: '#e53e3e',
        purple: '#805ad5',
        colors: ['#3182ce','#ed8936','#38a169','#e53e3e','#805ad5','#d69e2e','#319795','#b83280'],
    };
}

function applyChartDefaults() {
    const c = getChartColors();
    Chart.defaults.color = c.text;
    Chart.defaults.borderColor = c.grid;
}

applyChartDefaults();

// ═══════════════════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════════════════

// SSE real-time event stream
let sseConnection = null;

function connectSSE() {
    if (sseConnection) { sseConnection.close(); }
    sseConnection = new EventSource('/api/realtime/stream');

    sseConnection.onopen = () => console.log('[SSE] Connected to real-time stream');

    sseConnection.addEventListener('document_parsed', (e) => {
        const data = JSON.parse(e.data);
        toast(`📄 ${data.source_type}: ${(data.title || '').substring(0, 40)}... — ${data.event_count || 0} events`, 'info');
        loadDashboard();  // always refresh to show new crawl data
    });

    sseConnection.addEventListener('event_created', (e) => {
        const data = JSON.parse(e.data);
        toast(`📰 新事件: ${(data.summary || '').substring(0, 50)}...`, 'info');
        loadDashboard();  // always refresh to show new crawl data
    });

    sseConnection.addEventListener('queue_update', (e) => {
        const data = JSON.parse(e.data);
        if (data.processed > 0) loadDashboard();
    });

    sseConnection.addEventListener('error_alert', (e) => {
        const data = JSON.parse(e.data);
        toast(`⚠️ 处理错误: ${(data.error || '').substring(0, 80)}`, 'error');
    });

    sseConnection.onerror = () => {
        console.warn('[SSE] Connection error, retrying in 5s...');
        sseConnection.close();
        setTimeout(connectSSE, 5000);
    };
}

// Connect SSE on page load, disconnect on unload
connectSSE();
window.addEventListener('beforeunload', () => { if (sseConnection) sseConnection.close(); });

async function loadDashboard() {
    try {
        const data = await apiCall('GET', '/api/dashboard');

        // Update data source badge
        const dataSourceBadge = document.getElementById('data-source-badge');

        if (data.market_overview.uses_real_news || data.market_overview.uses_real_sectors) {
            dataSourceBadge.textContent = '真实数据';
            dataSourceBadge.style.backgroundColor = '';
            dataSourceBadge.classList.remove('badge-new');
            dataSourceBadge.classList.add('badge-real');
            dataSourceBadge.classList.remove('badge-mock');
        } else {
            dataSourceBadge.textContent = '模拟数据';
            dataSourceBadge.style.backgroundColor = '';
            dataSourceBadge.classList.remove('badge-new');
            dataSourceBadge.classList.add('badge-mock');
            dataSourceBadge.classList.remove('badge-real');
        }

        // Render Market Overview Section
        // Save scroll positions before updating content
        const globalNewsEl = document.getElementById('market-global-news');
        const topUpSectorsEl = document.getElementById('market-top-up-sectors');
        const topDownSectorsEl = document.getElementById('market-top-down-sectors');
        const newsScroll = globalNewsEl.scrollTop || 0;
        const upScroll = topUpSectorsEl.scrollTop || 0;
        const downScroll = topDownSectorsEl.scrollTop || 0;

        // Global News
        if (data.market_overview.global_news.length) {
            globalNewsEl.innerHTML = data.market_overview.global_news.map((n, idx) => `
                <li class="news-item ${n.is_mock ? 'mock-data-item' : ''}">
                    <div class="news-header">
                        <span class="news-rank">#${idx + 1}</span>
                        <span class="news-title-inline">${esc(n.title)}</span>
                        ${n.is_mock ? '<span class="badge badge-mock">模拟</span>' : ''}
                    </div>
                    <div class="news-summary">${esc(n.summary)}</div>
                    <div class="news-meta">
                        <span class="news-source-tag">${esc(n.source)}</span>
                        <span class="news-time">${new Date(n.published_at).toLocaleString()}</span>
                        ${n.related_symbols.length ? `<span class="news-symbols">${n.related_symbols.map(s => esc(s)).join(', ')}</span>` : ''}
                    </div>
                </li>
            `).join('');
        } else {
            globalNewsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无新闻</li>';
        }

        // Top Up Sectors
        if (data.market_overview.top_up_sectors.length) {
            topUpSectorsEl.innerHTML = data.market_overview.top_up_sectors.map(s => `
                <li class="sector-item ${s.is_mock ? 'mock-data-item' : ''}">
                    <div class="sector-header">
                        <span class="sector-name">${esc(s.name)}</span>
                        <span class="sector-right">
                            <span class="badge ${s.is_concept ? 'badge-concept' : 'badge-sector'}">${s.is_concept ? '概念' : '板块'}</span>
                            <span class="sector-change sector-up">+${s.change_pct.toFixed(2)}%</span>
                        </span>
                    </div>
                </li>
            `).join('');
        } else {
            topUpSectorsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无数据</li>';
        }

        // Top Down Sectors
        if (data.market_overview.top_down_sectors.length) {
            topDownSectorsEl.innerHTML = data.market_overview.top_down_sectors.map(s => `
                <li class="sector-item ${s.is_mock ? 'mock-data-item' : ''}">
                    <div class="sector-header">
                        <span class="sector-name">${esc(s.name)}</span>
                        <span class="sector-right">
                            <span class="badge ${s.is_concept ? 'badge-concept' : 'badge-sector'}">${s.is_concept ? '概念' : '板块'}</span>
                            <span class="sector-change sector-down">${s.change_pct.toFixed(2)}%</span>
                        </span>
                    </div>
                </li>
            `).join('');
        } else {
            topDownSectorsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无数据</li>';
        }

        // Restore scroll positions after content update
        globalNewsEl.scrollTop = newsScroll;
        topUpSectorsEl.scrollTop = upScroll;
        topDownSectorsEl.scrollTop = downScroll;

        // Render Today Section
        // New Events
        const newEventsEl = document.getElementById('today-new-events');
        if (data.today.new_events.length) {
            newEventsEl.innerHTML = data.today.new_events.map(e => `
                <li>
                    <div class="item-title">${esc(e.summary)}</div>
                    <div class="item-meta">${esc(e.event_type)} • ${new Date(e.created_at).toLocaleString()}</div>
                </li>
            `).join('');
        } else {
            newEventsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无新事件</li>';
        }

        // High Priority Theses
        const highPriorityEl = document.getElementById('today-high-priority');
        if (data.today.high_priority_theses.length) {
            highPriorityEl.innerHTML = data.today.high_priority_theses.map(t => `
                <li>
                    <div class="item-title">${esc(t.thesis)}</div>
                    <div class="item-meta">${esc(t.subject_id)} • ${esc(t.event_type)} • ${I18N.t('dashboard.score')}: ${t.score.toFixed(2)}</div>
                </li>
            `).join('');
        } else {
            highPriorityEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无高优先级论题</li>';
        }

        // Abnormal Flows
        const abnormalFlowsEl = document.getElementById('today-abnormal-flows');
        if (data.today.abnormal_flows.length) {
            abnormalFlowsEl.innerHTML = data.today.abnormal_flows.map(f => `
                <li class="abnormal-flow-item">
                    <span class="diffusion ${f.diffusion_strength > 0.7 ? 'diffusion-high' : f.diffusion_strength > 0.4 ? 'diffusion-medium' : 'diffusion-low'}"></span>
                    <div class="item-title">${esc(f.symbol)} • ${esc(f.industry)}</div>
                    <div class="item-meta">${I18N.t('dashboard.diffusion')}: ${f.diffusion_strength.toFixed(2)} • ${I18N.t('dashboard.change')}: ${f.change_pct.toFixed(2)}%</div>
                </li>
            `).join('');
        } else {
            abnormalFlowsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">暂无异常</li>';
        }

        // Render Research Queue Section
        // Pending Assertions
        const pendingAssertionsEl = document.getElementById('queue-pending-assertions');
        if (data.research_queue.pending_assertions.length) {
            pendingAssertionsEl.innerHTML = data.research_queue.pending_assertions.map(a => `
                <li>
                    <div class="item-title">${esc(a.subject)}: ${esc(a.claim)}</div>
                    <div class="item-meta">${esc(a.status)} • ${new Date(a.created_at).toLocaleString()}</div>
                </li>
            `).join('');
        } else {
            pendingAssertionsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无待处理断言</li>';
        }

        // Missing Evidence
        const missingEvidenceEl = document.getElementById('queue-missing-evidence');
        if (data.research_queue.missing_evidence.length) {
            missingEvidenceEl.innerHTML = data.research_queue.missing_evidence.map(m => `
                <li>
                    <div class="item-title">${esc(m.subject)}</div>
                    <div class="item-meta">${I18N.t('dashboard.required_evidence')}: ${esc(m.required_evidence_type)}</div>
                </li>
            `).join('');
        } else {
            missingEvidenceEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无缺失证据</li>';
        }

        // Mapping Reviews
        const mappingReviewsEl = document.getElementById('queue-mapping-reviews');
        if (data.research_queue.mapping_reviews.length) {
            mappingReviewsEl.innerHTML = data.research_queue.mapping_reviews.map(r => `
                <li>
                    <div class="item-title">${esc(r.subject)}</div>
                    <div class="item-meta">${esc(r.status)} • ${esc(r.reviewer || 'unassigned')}</div>
                </li>
            `).join('');
        } else {
            mappingReviewsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无待审查</li>';
        }

        // Render Candidate Board Section
        const candidatesEl = document.getElementById('candidate-top-candidates');
        if (data.candidate_board.top_candidates.length) {
            candidatesEl.innerHTML = data.candidate_board.top_candidates.map(c => `
                <div class="candidate-item">
                    <div class="candidate-header">
                        <span class="candidate-title">${esc(c.subject)}</span>
                        <span class="readiness-score">${I18N.t('dashboard.readiness')}: ${c.readiness_score.toFixed(2)}</span>
                    </div>
                    <div class="candidate-thesis">${esc(c.thesis)}</div>
                    ${c.timing_blocker ? `<div class="candidate-blocker">⚠️ ${I18N.t('dashboard.timing_blocker')}: ${esc(c.timing_blocker)}</div>` : ''}
                    ${c.trigger_condition ? `<div class="item-meta">${I18N.t('dashboard.trigger')}: ${esc(c.trigger_condition)}</div>` : ''}
                </div>
            `).join('');
        } else {
            candidatesEl.innerHTML = '<div class="empty-state" data-i18n="dashboard.no_data">暂无候选机会</div>';
        }

        // Render Learning Section
        // Recent Failures
        const recentFailuresEl = document.getElementById('learning-recent-failures');
        if (data.learning.recent_failures.length) {
            recentFailuresEl.innerHTML = data.learning.recent_failures.map(f => `
                <li>
                    <div class="item-title">${esc(f.subject_id)}: ${esc(f.failure_reason)}</div>
                    <div class="item-meta">${I18N.t('dashboard.lesson')}: ${esc(f.lesson)} • ${f.outcome_return ? f.outcome_return.toFixed(2) + '%' : ''}</div>
                </li>
            `).join('');
        } else {
            recentFailuresEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无失败记录</li>';
        }

        // Best Event Types
        const bestEventTypesEl = document.getElementById('learning-best-event-types');
        if (data.learning.best_event_types.length) {
            bestEventTypesEl.innerHTML = data.learning.best_event_types.map(et => `
                <div class="event-type-item">
                    <div class="event-type-name">${esc(et.event_type)}</div>
                    <div class="event-type-stats">${I18N.t('dashboard.avg_excess')}: ${et.avg_excess_return.toFixed(2)}%</div>
                    <div class="event-type-stats">${I18N.t('dashboard.win_rate')}: ${(et.win_rate * 100).toFixed(0)}%</div>
                </div>
            `).join('');
        } else {
            bestEventTypesEl.innerHTML = '<div class="empty-state" data-i18n="dashboard.no_data">暂无数据</div>';
        }

        // Weekly Lessons
        const weeklyLessonsEl = document.getElementById('learning-weekly-lessons');
        if (data.learning.weekly_lessons.length) {
            weeklyLessonsEl.innerHTML = data.learning.weekly_lessons.map(l => `
                <li>
                    <div class="item-title">${esc(l.week)}: ${esc(l.key_takeaway)}</div>
                </li>
            `).join('');
        } else {
            weeklyLessonsEl.innerHTML = '<li class="empty-state" data-i18n="dashboard.no_data">无总结</li>';
        }

        // Refresh i18n
        I18N.applyAll();
    } catch (e) {
        console.error('Failed to load dashboard:', e);
        toast(I18N.t('toast.load_dashboard_failed'), 'error');
    }

    // Also refresh workers status
    loadWorkersStatus();
}

// ── Workers Panel ──────────────────────────────────────────────

let _workersPollTimer = null;

function startWorkersPolling() {
    stopWorkersPolling();
    _workersPollTimer = setInterval(loadWorkersStatus, 15000);
}

function stopWorkersPolling() {
    if (_workersPollTimer) {
        clearInterval(_workersPollTimer);
        _workersPollTimer = null;
    }
}

async function loadWorkersStatus() {
    try {
        const data = await apiCall('GET', '/api/system/workers/status');
        renderWorkersPanel(data);
    } catch (e) {
        console.error('Failed to load workers status:', e);
    }
}

function renderWorkersPanel(data) {
    const panel = document.getElementById('workers-panel');
    const queueEl = document.getElementById('workers-queue-stats');
    const lastUpdated = document.getElementById('workers-last-updated');

    if (lastUpdated) {
        lastUpdated.textContent = new Date().toLocaleTimeString();
    }

    // ── Worker rows ──────────────────────────────────────────
    let html = '';

    // Knowledge workers
    if (data.workers && data.workers.length) {
        data.workers.forEach(function(w) {
            const statusClass = w.alive ? 'worker-alive' : 'worker-dead';
            const statusText = w.alive ? '运行中' : '已停止';
            const pidText = w.pid ? 'PID ' + w.pid : '—';
            const activityText = w.activity || (w.alive ? '—' : '—');

            html += '<div class="worker-row">';
            html += '<span class="worker-dot ' + statusClass + '" title="' + statusText + '"></span>';
            html += '<span class="worker-name">' + esc(w.name) + '</span>';
            html += '<span class="worker-type badge badge-outline">知识加工</span>';
            html += '<span class="worker-pid text-muted">' + pidText + '</span>';
            html += '<span class="worker-activity text-muted">' + esc(activityText) + '</span>';
            html += '</div>';
        });
    } else {
        html += '<div class="empty-state">无知识加工 Worker</div>';
    }

    // Scheduler
    if (data.scheduler) {
        var s = data.scheduler;
        var sStatusClass = s.alive ? 'worker-alive' : 'worker-dead';
        var sStatusText = s.alive ? '运行中' : '已停止';
        var sPidText = s.pid ? 'PID ' + s.pid : '—';
        var sActivityText = s.activity || '—';

        html += '<div class="worker-row">';
        html += '<span class="worker-dot ' + sStatusClass + '" title="' + sStatusText + '"></span>';
        html += '<span class="worker-name">' + esc(s.name) + '</span>';
        html += '<span class="worker-type badge badge-outline">调度</span>';
        html += '<span class="worker-pid text-muted">' + sPidText + '</span>';
        html += '<span class="worker-activity text-muted">' + esc(sActivityText) + '</span>';
        html += '</div>';
    }

    panel.innerHTML = html;

    // ── Queue stats ──────────────────────────────────────────
    if (queueEl && data.queue_stats) {
        var qs = data.queue_stats;
        queueEl.innerHTML =
            '<span class="queue-stat"><span class="queue-stat-label">待处理</span><span class="queue-stat-value">' + qs.pending + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">处理中</span><span class="queue-stat-value queue-processing">' + qs.processing + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">已完成</span><span class="queue-stat-value queue-completed">' + qs.completed + '</span></span>' +
            '<span class="queue-stat"><span class="queue-stat-label">失败</span><span class="queue-stat-value queue-failed">' + qs.failed + '</span></span>';
    }
}

// ═══════════════════════════════════════════════════════════════
// Asset Analysis
// ═══════════════════════════════════════════════════════════════

// 资产搜索相关变量
let assetSearchDebounceTimer = null;
let selectedAssetIndex = -1;
let assetSearchResults = [];

// 资产搜索功能
async function searchAssets(query) {
    if (!query || query.length < 1) {
        hideAssetSearchDropdown();
        return;
    }

    try {
        const results = await apiCall('GET', `/api/search?q=${encodeURIComponent(query)}&types=symbol`);
        assetSearchResults = results.symbols || [];
        renderAssetSearchDropdown(assetSearchResults, query);
    } catch (e) {
        console.error('Asset search failed:', e);
    }
}

function renderAssetSearchDropdown(results, query) {
    const dropdown = document.getElementById('asset-search-dropdown');
    if (!results || results.length === 0) {
        dropdown.classList.add('hidden');
        return;
    }

    selectedAssetIndex = -1;
    let html = '<div class="search-result-group"><div class="group-title">标的</div>';
    results.forEach((item, index) => {
        const name = item.name || item.display_name || '';
        const symbol = item.symbol || '';
        const industry = item.industry || '';
        html += `
            <div class="search-result-item asset-result-item" data-index="${index}" data-symbol="${esc(symbol)}">
                <div class="result-title">
                    <span class="asset-symbol">${esc(symbol)}</span>
                    <span class="asset-name">${esc(name)}</span>
                </div>
                ${industry ? `<div class="result-subtitle">${esc(industry)}</div>` : ''}
            </div>
        `;
    });
    html += '</div>';

    dropdown.innerHTML = html;
    dropdown.classList.remove('hidden');

    // 添加点击事件
    dropdown.querySelectorAll('.asset-result-item').forEach(item => {
        item.addEventListener('click', () => {
            const symbol = item.dataset.symbol;
            selectAsset(symbol, item);
        });
        item.addEventListener('mouseenter', () => {
            dropdown.querySelectorAll('.asset-result-item').forEach(el => el.classList.remove('selected'));
            item.classList.add('selected');
            selectedAssetIndex = parseInt(item.dataset.index);
        });
    });
}

function selectAsset(symbol, element) {
    const input = document.getElementById('asset-code');
    input.value = symbol;
    hideAssetSearchDropdown();
    analyzeAssetByCode(symbol);
}

function hideAssetSearchDropdown() {
    const dropdown = document.getElementById('asset-search-dropdown');
    dropdown.classList.add('hidden');
}

// 键盘导航
function handleAssetSearchKeydown(e) {
    const dropdown = document.getElementById('asset-search-dropdown');
    const items = dropdown.querySelectorAll('.asset-result-item');

    if (dropdown.classList.contains('hidden')) return;

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedAssetIndex = Math.min(selectedAssetIndex + 1, items.length - 1);
        updateSelectedItem(items);
    } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedAssetIndex = Math.max(selectedAssetIndex - 1, 0);
        updateSelectedItem(items);
    } else if (e.key === 'Enter') {
        e.preventDefault();
        if (selectedAssetIndex >= 0 && items[selectedAssetIndex]) {
            items[selectedAssetIndex].click();
        } else {
            // 直接使用输入框的值进行分析
            const code = e.target.value.trim();
            if (code) {
                hideAssetSearchDropdown();
                analyzeAssetByCode(code);
            }
        }
    } else if (e.key === 'Escape') {
        hideAssetSearchDropdown();
    }
}

function updateSelectedItem(items) {
    items.forEach((item, index) => {
        if (index === selectedAssetIndex) {
            item.classList.add('selected');
            item.scrollIntoView({ block: 'nearest' });
        } else {
            item.classList.remove('selected');
        }
    });
}

// 直接通过代码分析资产
async function analyzeAssetByCode(code) {
    if (!code) return toast(I18N.t('toast.enter_asset_code'), 'error');

    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/assets/analysis-card', {
            canonical_id: code,
        });
        renderAssetAnalysisCard(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.analyze_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

// 资产分析方法 - 保留向后兼容
async function analyzeAsset() {
    const code = document.getElementById('asset-code').value.trim();
    if (!code) return toast(I18N.t('toast.enter_asset_code'), 'error');

    const loading = document.getElementById('asset-loading');
    const result = document.getElementById('asset-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/assets/analysis-card', {
            canonical_id: code,
        });
        renderAssetAnalysisCard(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.analyze_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

// 渲染新的资产分析卡片
function renderAssetAnalysisCard(data) {
    // 基本信息
    const basic = data.basic_info || {};
    document.getElementById('asset-name').textContent = basic.name || data.canonical_id || '--';
    document.getElementById('asset-code-display').textContent = basic.symbol || data.canonical_id || '--';

    // 价格信息
    const priceClass = (data.price_change_pct || 0) >= 0 ? 'price-up' : 'price-down';
    const changePrefix = (data.price_change_pct || 0) >= 0 ? '+' : '';
    document.getElementById('asset-price').textContent = data.current_price ? data.current_price.toFixed(2) : '--';
    document.getElementById('asset-price').className = `asset-price ${priceClass}`;
    document.getElementById('asset-change').textContent = data.price_change !== undefined ? `${changePrefix}${data.price_change.toFixed(2)}` : '--';
    document.getElementById('asset-change').className = `asset-change ${priceClass}`;
    document.getElementById('asset-change-pct').textContent = data.price_change_pct !== undefined ? `(${changePrefix}${data.price_change_pct.toFixed(2)}%)` : '--';
    document.getElementById('asset-change-pct').className = `asset-change-pct ${priceClass}`;

    // 市场数据
    document.getElementById('asset-volume').textContent = fmtVolume(data.volume);
    document.getElementById('asset-amount').textContent = fmtAmount(data.amount);
    document.getElementById('asset-turnover').textContent = data.turnover !== undefined ? `${data.turnover.toFixed(2)}%` : '--';
    document.getElementById('asset-market-cap').textContent = fmtMarketCap(basic.market_cap);
    document.getElementById('asset-high-52w').textContent = data.high_52w !== undefined ? data.high_52w.toFixed(2) : '--';
    document.getElementById('asset-low-52w').textContent = data.low_52w !== undefined ? data.low_52w.toFixed(2) : '--';

    // 财务数据
    const fin = data.financial || {};
    document.getElementById('fin-pe').textContent = fin.pe_ttm !== undefined ? fin.pe_ttm.toFixed(2) : '--';
    document.getElementById('fin-pb').textContent = fin.pb_mrq !== undefined ? fin.pb_mrq.toFixed(2) : '--';
    document.getElementById('fin-roe').textContent = fin.roe !== undefined ? `${fin.roe.toFixed(2)}%` : '--';
    document.getElementById('fin-revenue').textContent = fmtRevenue(fin.revenue);
    document.getElementById('fin-net-profit').textContent = fmtNetProfit(fin.net_profit);
    document.getElementById('fin-gross-margin').textContent = fin.gross_margin !== undefined ? `${fin.gross_margin.toFixed(2)}%` : '--';

    // K线图
    renderPriceVolumeChartAdvanced(data.price_bars || []);

    // 资金流向
    renderCapitalFlowChart(data.capital_flow);

    // 股东列表
    renderShareholderList(data.top_10_shareholders || []);

    // 行业信息
    renderIndustryInfo(data.industry);

    // 事件列表
    renderEventListPanel(data.recent_events || []);

    // 宏观敏感性
    renderMacroSensitivity(data.macro_sensitivity);
}

// 渲染K线图
function renderPriceVolumeChartAdvanced(priceBars) {
    const colors = getChartColors();
    if (chartPriceVolume) chartPriceVolume.destroy();

    const labels = priceBars.map(b => {
        if (typeof b.date === 'string') return b.date.substring(5);
        if (b.date instanceof Date) return `${b.date.getMonth() + 1}-${b.date.getDate()}`;
        return '';
    });
    const closePrices = priceBars.map(b => b.close);
    const volumes = priceBars.map(b => b.volume || 0);

    const ctx = document.getElementById('chart-price-volume').getContext('2d');
    chartPriceVolume = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [
                {
                    label: '收盘价',
                    data: closePrices,
                    borderColor: colors.blue,
                    backgroundColor: colors.blue + '20',
                    fill: true,
                    tension: 0.2,
                    pointRadius: 0,
                }
            ]
        },
        options: {
            responsive: true,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                }
            },
            scales: {
                x: {
                    grid: {
                        color: colors.grid,
                    }
                },
                y: {
                    grid: {
                        color: colors.grid,
                    }
                }
            }
        }
    });
}

// 渲染资金流向
let chartCapitalFlow = null;
function renderCapitalFlowChart(capitalFlow) {
    if (!capitalFlow) {
        document.getElementById('capital-flow-details').innerHTML = '<p class="empty-state">暂无资金流向数据</p>';
        return;
    }

    // 渲染饼图
    const colors = getChartColors();
    if (chartCapitalFlow) chartCapitalFlow.destroy();

    const labels = ['主力净流入', '超大单', '大单', '中单', '小单'];
    const values = [
        capitalFlow.main_net || 0,
        capitalFlow.super_net || 0,
        capitalFlow.large_net || 0,
        capitalFlow.medium_net || 0,
        capitalFlow.small_net || 0,
    ];

    // 过滤掉0值
    const validData = labels.map((l, i) => ({ label: l, value: values[i] })).filter(d => d.value !== 0);
    const validLabels = validData.map(d => d.label);
    const validValues = validData.map(d => Math.abs(d.value));
    const bgColors = validData.map(d => d.value >= 0 ? colors.green : colors.red);

    const ctx = document.getElementById('chart-capital-flow').getContext('2d');
    chartCapitalFlow = new Chart(ctx, {
        type: 'pie',
        data: {
            labels: validLabels,
            datasets: [
                {
                    data: validValues,
                    backgroundColor: bgColors.length ? bgColors : [colors.blue, colors.orange, colors.green, colors.red, colors.purple],
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'bottom',
                }
            }
        }
    });

    // 渲染详情
    const detailsHtml = `
        <div class="flow-detail-item">
            <span class="flow-label">主力流入</span>
            <span class="flow-value inflow">${fmtAmount(capitalFlow.main_inflow)}</span>
        </div>
        <div class="flow-detail-item">
            <span class="flow-label">主力流出</span>
            <span class="flow-value outflow">${fmtAmount(capitalFlow.main_outflow)}</span>
        </div>
        <div class="flow-detail-item">
            <span class="flow-label">主力净流入</span>
            <span class="flow-value ${(capitalFlow.main_net || 0) >= 0 ? 'inflow' : 'outflow'}">
                ${(capitalFlow.main_net || 0) >= 0 ? '+' : ''}${fmtAmount(capitalFlow.main_net)}
            </span>
        </div>
        ${capitalFlow.northbound_flow !== undefined ? `
            <div class="flow-detail-item">
                <span class="flow-label">北向资金</span>
                <span class="flow-value ${capitalFlow.northbound_flow >= 0 ? 'inflow' : 'outflow'}">
                    ${capitalFlow.northbound_flow >= 0 ? '+' : ''}${fmtAmount(capitalFlow.northbound_flow)}
                </span>
            </div>
        ` : ''}
    `;
    document.getElementById('capital-flow-details').innerHTML = detailsHtml;
}

// 渲染股东列表
function renderShareholderList(shareholders) {
    const container = document.getElementById('shareholder-list');
    if (!shareholders || !shareholders.length) {
        container.innerHTML = '<p class="empty-state">暂无股东数据</p>';
        return;
    }

    container.innerHTML = shareholders.map(sh => `
        <div class="shareholder-item">
            <div class="shareholder-name">${esc(sh.name)}</div>
            <div class="shareholder-meta">
                <span class="shareholder-ratio">${sh.share_ratio.toFixed(2)}%</span>
                ${sh.change_ratio !== undefined ? `
                    <span class="shareholder-change ${sh.change_ratio >= 0 ? 'change-up' : 'change-down'}">
                        ${sh.change_ratio >= 0 ? '+' : ''}${sh.change_ratio.toFixed(2)}%
                    </span>
                ` : ''}
                ${sh.is_state_owned ? '<span class="soe-badge">国资</span>' : ''}
            </div>
        </div>
    `).join('');
}

// 渲染行业信息
function renderIndustryInfo(industry) {
    const container = document.getElementById('industry-info-detail');
    if (!industry) {
        container.innerHTML = '<p class="empty-state">暂无行业数据</p>';
        return;
    }

    container.innerHTML = `
        <div class="industry-class">
            <div class="industry-label">申万一级</div>
            <div class="industry-value">${esc(industry.sw_level_1 || '--')}</div>
        </div>
        <div class="industry-class">
            <div class="industry-label">申万二级</div>
            <div class="industry-value">${esc(industry.sw_level_2 || '--')}</div>
        </div>
        <div class="industry-metrics">
            <div class="metric-row">
                <span class="metric-label">行业PE</span>
                <span class="metric-value">${industry.industry_pe !== undefined ? industry.industry_pe.toFixed(2) : '--'}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">行业PB</span>
                <span class="metric-value">${industry.industry_pb !== undefined ? industry.industry_pb.toFixed(2) : '--'}</span>
            </div>
            <div class="metric-row">
                <span class="metric-label">板块排名</span>
                <span class="metric-value">${industry.sector_rank !== undefined ? `${industry.sector_rank}/${industry.total_stocks || '--'}` : '--'}</span>
            </div>
        </div>
        ${industry.related_concepts && industry.related_concepts.length ? `
            <div class="concepts-section">
                <div class="concepts-label">相关概念</div>
                <div class="concepts-tags">
                    ${industry.related_concepts.map(c => `<span class="concept-tag">${esc(c)}</span>`).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

// 渲染事件列表
function renderEventListPanel(events) {
    const container = document.getElementById('event-list-panel');
    if (!events || !events.length) {
        container.innerHTML = '<p class="empty-state">暂无事件数据</p>';
        return;
    }

    container.innerHTML = events.map(evt => {
        const dirClass = evt.impact_direction === 'positive' ? 'event-positive' :
                        evt.impact_direction === 'negative' ? 'event-negative' : 'event-neutral';
        const dateStr = evt.publish_date ?
            (typeof evt.publish_date === 'string' ? evt.publish_date.substring(0, 10) :
             evt.publish_date instanceof Date ? evt.publish_date.toLocaleDateString() : '') : '';
        return `
            <div class="event-item-panel ${dirClass}">
                <div class="event-item-header">
                    <div class="event-title">${esc(evt.title)}</div>
                    ${dateStr ? `<div class="event-date">${dateStr}</div>` : ''}
                </div>
                ${evt.content ? `<div class="event-content">${esc(evt.content)}</div>` : ''}
                <div class="event-item-meta">
                    ${evt.source ? `<span class="event-source">${esc(evt.source)}</span>` : ''}
                    ${evt.impact_score !== undefined ? `
                        <span class="event-impact-score">影响度: ${(evt.impact_score * 100).toFixed(0)}%</span>
                    ` : ''}
                    ${evt.price_reaction !== undefined ? `
                        <span class="event-price-reaction">
                            股价反应: ${evt.price_reaction >= 0 ? '+' : ''}${evt.price_reaction.toFixed(2)}%
                        </span>
                    ` : ''}
                </div>
            </div>
        `;
    }).join('');
}

// 渲染宏观敏感性
function renderMacroSensitivity(macro) {
    const container = document.getElementById('macro-sensitivity-detail');
    if (!macro) {
        container.innerHTML = '<p class="empty-state">暂无宏观数据</p>';
        return;
    }

    const sensitivityItems = [
        { label: '利率敏感度', value: macro.interest_rate_sensitivity },
        { label: '通胀敏感度', value: macro.inflation_sensitivity },
        { label: '汇率敏感度', value: macro.exchange_rate_sensitivity },
        { label: '商品敏感度', value: macro.commodity_sensitivity },
        { label: '流动性敏感度', value: macro.liquidity_sensitivity },
    ].filter(i => i.value !== undefined);

    container.innerHTML = `
        <div class="sensitivity-list">
            ${sensitivityItems.map(item => `
                <div class="sensitivity-item">
                    <div class="sensitivity-label">${item.label}</div>
                    <div class="sensitivity-bar">
                        <div class="sensitivity-fill ${item.value >= 0 ? 'sensitivity-pos' : 'sensitivity-neg'}"
                             style="width: ${Math.min(Math.abs(item.value) * 100, 100)}%"></div>
                    </div>
                    <div class="sensitivity-value">${item.value.toFixed(2)}</div>
                </div>
            `).join('')}
        </div>
        ${macro.key_macro_factors && macro.key_macro_factors.length ? `
            <div class="key-factors-section">
                <div class="factors-label">关键宏观因子</div>
                <div class="factors-tags">
                    ${macro.key_macro_factors.map(f => `<span class="factor-tag">${esc(f)}</span>`).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

// 格式化辅助函数
function fmtVolume(vol) {
    if (vol === undefined || vol === null) return '--';
    if (vol >= 100000000) return `${(vol / 100000000).toFixed(2)}亿股`;
    if (vol >= 10000) return `${(vol / 10000).toFixed(2)}万股`;
    return `${vol.toFixed(0)}股`;
}

function fmtAmount(amt) {
    if (amt === undefined || amt === null) return '--';
    if (amt >= 100000000) return `${(amt / 100000000).toFixed(2)}亿`;
    if (amt >= 10000) return `${(amt / 10000).toFixed(2)}万`;
    return `${amt.toFixed(0)}`;
}

function fmtMarketCap(cap) {
    if (cap === undefined || cap === null) return '--';
    if (cap >= 1000000000000) return `${(cap / 1000000000000).toFixed(2)}万亿`;
    if (cap >= 100000000) return `${(cap / 100000000).toFixed(2)}亿`;
    return `${cap.toFixed(0)}`;
}

function fmtRevenue(rev) {
    if (rev === undefined || rev === null) return '--';
    if (rev >= 100000000) return `${(rev / 100000000).toFixed(2)}亿`;
    if (rev >= 10000) return `${(rev / 10000).toFixed(2)}万`;
    return `${rev.toFixed(0)}`;
}

function fmtNetProfit(profit) {
    if (profit === undefined || profit === null) return '--';
    if (profit >= 100000000) return `${(profit / 100000000).toFixed(2)}亿`;
    if (profit >= 10000) return `${(profit / 10000).toFixed(2)}万`;
    return `${profit.toFixed(0)}`;
}

// 保留旧的渲染函数用于兼容
function renderAssetResult(data) {
    // ─── Valuation
    const valCards = document.getElementById('valuation-cards');
    const v = data.valuation || {};
    const valMetrics = [
        { label: I18N.t('metric.pe_ttm'), value: v.pe_ttm ?? v.PE ?? '—' },
        { label: I18N.t('metric.pb'), value: v.pb ?? v.PB ?? '—' },
        { label: I18N.t('metric.ps'), value: v.ps ?? v.PS ?? '—' },
        { label: I18N.t('metric.ev_ebitda'), value: v.ev_ebitda ?? v.EV_EBITDA ?? '—' },
    ];
    valCards.innerHTML = valMetrics.map(m => `
        <div class="info-item"><div class="info-label">${m.label}</div><div class="info-value">${fmtNum(m.value)}</div></div>
    `).join('');

    // ─── Price/Volume Chart
    renderPriceVolumeChart(data.price_volume || {});

    // ─── Financial
    const finWrap = document.getElementById('financial-table');
    const f = data.financial || {};
    const finRows = [
        [I18N.t('metric.revenue'), f.revenue ?? f.Revenue],
        [I18N.t('metric.net_profit'), f.net_profit ?? f.NetProfit],
        [I18N.t('metric.eps'), f.eps ?? f.EPS],
        [I18N.t('metric.roe'), f.roe ?? f.ROE],
    ].filter(r => r[1] !== undefined);

    if (finRows.length) {
        finWrap.innerHTML = `<table><thead><tr><th>指标</th><th>值</th></tr></thead><tbody>${finRows.map(r =>
            `<tr><td>${r[0]}</td><td>${fmtFinancial(r[1])}</td></tr>`
        ).join('')}</tbody></table>`;
    } else {
        finWrap.innerHTML = '<p class="empty-state">' + I18N.t('asset.no_financial') + '</p>';
    }

    // ─── Fund Flow
    const ffWrap = document.getElementById('fund-flow-info');
    const ff = data.fund_flow || {};
    const ffItems = [
        { label: I18N.t('metric.main_net_inflow'), key: 'main_net_inflow' },
        { label: I18N.t('metric.institutional_holding'), key: 'institutional_holding' },
        { label: I18N.t('metric.northbound_holding'), key: 'northbound_holding' },
    ].filter(i => ff[i.key] !== undefined);
    ffWrap.innerHTML = ffItems.length ? ffItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(ff[i.key])}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_fund_flow') + '</p>';

    // ─── Shareholder
    const shWrap = document.getElementById('shareholder-info');
    const sh = data.shareholder || {};
    const shItems = Object.entries(sh).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    shWrap.innerHTML = shItems.length ? shItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_shareholder') + '</p>';

    // ─── Industry
    const indWrap = document.getElementById('industry-info');
    const ind = data.industry || {};
    const indItems = Object.entries(ind).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    indWrap.innerHTML = indItems.length ? indItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_industry') + '</p>';

    // ─── Event Impact
    const evList = document.getElementById('event-impact-list');
    const events = data.event_impact || [];
    evList.innerHTML = events.length ? events.map(e => `<li>${esc(e)}</li>`).join('') : '<li class="empty-state">' + I18N.t('asset.no_event_impact') + '</li>';

    // ─── Macro
    const macroWrap = document.getElementById('macro-info');
    const macro = data.macro_exposure || {};
    const macroItems = Object.entries(macro).slice(0, 6).map(([k, v]) => ({ label: k, value: v }));
    macroWrap.innerHTML = macroItems.length ? macroItems.map(i => `
        <div class="info-item"><div class="info-label">${i.label}</div><div class="info-value">${fmtNum(i.value)}</div></div>
    `).join('') : '<p class="empty-state">' + I18N.t('asset.no_macro') + '</p>';
}

function renderPriceVolumeChart(pv) {
    const colors = getChartColors();
    if (chartPriceVolume) chartPriceVolume.destroy();

    const labels = pv.dates || [];
    const close = pv.close_price || [];
    const ma5 = pv.ma5 || [];
    const ma20 = pv.ma20 || [];
    const ma60 = pv.ma60 || [];

    const ctx = document.getElementById('chart-price-volume').getContext('2d');
    chartPriceVolume = new Chart(ctx, {
        type: 'line',
        data: {
            labels,
            datasets: [
                { label: I18N.t('metric.close_price'), data: close, borderColor: colors.blue, backgroundColor: 'rgba(49,130,206,.1)', fill: true, tension: 0.3, pointRadius: 2 },
                { label: 'MA5', data: ma5, borderColor: colors.orange, borderDash: [4,4], pointRadius: 0 },
                { label: 'MA20', data: ma20, borderColor: colors.green, borderDash: [6,3], pointRadius: 0 },
                { label: 'MA60', data: ma60, borderColor: colors.red, borderDash: [8,4], pointRadius: 0 },
            ].filter(d => d.data.length > 0)
        },
        options: {
            responsive: true,
            interaction: { mode: 'index', intersect: false },
            plugins: { legend: { position: 'top' } },
            scales: { x: { grid: { color: colors.grid } }, y: { grid: { color: colors.grid } } }
        }
    });
}

// ═══════════════════════════════════════════════════════════════
// Scenario Analysis
// ═══════════════════════════════════════════════════════════════

async function generateScenarios() {
    const topic = document.getElementById('scenario-topic').value.trim();
    const subjectsStr = document.getElementById('scenario-subjects').value.trim();
    const subject_ids = subjectsStr ? subjectsStr.split(',').map(s => s.trim()).filter(s => s) : [];
    if (!topic) return toast(I18N.t('toast.enter_topic'), 'error');

    const loading = document.getElementById('scenario-loading');
    const result = document.getElementById('scenario-result');
    result.classList.add('hidden');
    loading.classList.remove('hidden');

    try {
        const data = await apiCall('POST', '/api/scenarios/generate', { topic, subject_ids });
        renderScenarioResult(data);
        result.classList.remove('hidden');
        toast(I18N.t('toast.scenario_complete'), 'success');
    } catch (e) {
        toast(e.message, 'error');
    } finally {
        loading.classList.add('hidden');
    }
}

function renderScenarioResult(data) {
    const hypotheses = data.hypotheses || [];

    // ─── Probability Chart
    if (chartScenarioProb) chartScenarioProb.destroy();
    const colors = getChartColors();
    if (hypotheses.length) {
        const ctx = document.getElementById('chart-scenario-prob').getContext('2d');
        chartScenarioProb = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: hypotheses.map(h => h.title),
                datasets: [{ data: hypotheses.map(h => (h.probability * 100).toFixed(1)), backgroundColor: colors.colors.slice(0, hypotheses.length) }]
            },
            options: { responsive: true, plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.raw}%` } } } }
        });
    }

    // ─── Normalization Check
    const checkEl = document.getElementById('normalization-check');
    const sum = hypotheses.reduce((acc, h) => acc + (h.probability || 0), 0);
    if (data.normalization_check?.ok || Math.abs(sum - 1) < 0.01) {
        checkEl.className = 'check-indicator ok';
        checkEl.textContent = '概率归一化检查通过';
    } else {
        checkEl.className = 'check-indicator warn';
        checkEl.textContent = '概率归一化检查未通过';
    }

    // ─── Scenario Cards
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

    // ─── Residual Uncertainty
    const resList = document.getElementById('residual-list');
    const residual = data.residual_uncertainty || [];
    resList.innerHTML = residual.length ? residual.map(r => `<li>${esc(r)}</li>`).join('') : '<li class="empty-state">无</li>';
}

// ═══════════════════════════════════════════════════════════════
// Event Signal
// ═══════════════════════════════════════════════════════════════

async function generateEventSignal() {
    const event = {
        event_id: crypto.randomUUID(),
        title: document.getElementById('event-title').value.trim(),
        type: document.getElementById('event-type').value,
        timestamp: document.getElementById('event-date').value || new Date().toISOString(),
    };
    if (!event.title) return toast(I18N.t('toast.enter_event_type'), 'error');

    try {
        const result = await apiCall('POST', '/api/pipeline/event-signal', { event });
        const signalId = result.signal_id;
        toast('事件信号生成成功', 'success');
        loadEventSignals();
        
        // Get and show Timing decision
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
    // TODO: load real event signals from API
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

function renderTimingDecision(decision) {
    const container = document.getElementById('timing-decision-card');
    const blockersHtml = decision.blockers.length ? `
        <div class="timing-section">
            <h4>阻止因素</h4>
            <ul class="timing-blockers">
                ${decision.blockers.map(b => `<li>${esc(b)}</li>`).join('')}
            </ul>
        </div>
    ` : '';
    
    container.innerHTML = `
        <div class="timing-header">
            <span class="timing-badge timing-${decision.action}">${esc(decision.action)}</span>
            <span class="timing-regime">市场状态: ${esc(decision.market_regime)}</span>
        </div>
        <div class="timing-readiness">
            <div class="timing-readiness-label">就绪度: ${(decision.readiness_score * 100).toFixed(1)}%</div>
            <div class="timing-readiness-bar">
                <div class="timing-readiness-fill" style="width: ${decision.readiness_score * 100}%"></div>
            </div>
        </div>
        ${blockersHtml}
        ${decision.rationale.length ? `
        <div class="timing-section">
            <h4>逻辑</h4>
            <ul>
                ${decision.rationale.map(r => `<li>${esc(r)}</li>`).join('')}
            </ul>
        </div>
        ` : ''}
    `;
}

// ═══════════════════════════════════════════════════════════════
// Industry Chain
// ═══════════════════════════════════════════════════════════════

async function loadIndustryChain() {
    const industry = document.getElementById('industry-select').value;
    try {
        const data = await apiCall('GET', `/api/graph/industry-chain/${encodeURIComponent(industry)}`);
        renderIndustryGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadPropagationPath() {
    const eventId = document.getElementById('event-id').value.trim();
    if (!eventId) return toast('请输入事件 ID', 'error');
    try {
        const data = await apiCall('GET', `/api/graph/propagation/${encodeURIComponent(eventId)}`);
        renderPropagationGraph(data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

function renderIndustryGraph(data) {
    const container = document.getElementById('industry-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;

    const nodes = data.nodes || [];
    const links = data.edges || [];

    // 如果没有数据，显示空状态提示
    if (!nodes.length) {
        container.innerHTML = '<div class="empty-state">暂无产业链数据</div>';
        return;
    }

    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);

    const color = d3.scaleOrdinal()
        .domain(['upstream', 'midstream', 'downstream'])
        .range(['#e53e3e', '#3182ce', '#38a169']);

    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2));

    const link = svg.append('g').selectAll('line').data(links).enter().append('line')
        .attr('stroke', '#94a3b8').attr('stroke-width', 2);

    const linkLabel = svg.append('g').selectAll('text').data(links).enter().append('text')
        .attr('font-size', '10px').attr('fill', '#64748b').text(d => d.label);

    const node = svg.append('g').selectAll('circle').data(nodes).enter().append('circle')
        .attr('r', 12).attr('fill', d => color(d.group)).call(drag(simulation));

    const nodeLabel = svg.append('g').selectAll('text').data(nodes).enter().append('text')
        .attr('font-size', '12px').attr('fill', '#1a202c').text(d => d.label);

    simulation.on('tick', () => {
        link.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
        linkLabel.attr('x', d => (d.source.x + d.target.x) / 2).attr('y', d => (d.source.y + d.target.y) / 2);
        node.attr('cx', d => d.x).attr('cy', d => d.y);
        nodeLabel.attr('x', d => d.x + 16).attr('y', d => d.y + 4);
    });

    function drag(simulation) {
        function dragstarted(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            if (!event.active) simulation.alphaTarget(0.3).restart();
            event.subject.fx = event.subject.x;
            event.subject.fy = event.subject.y;
        }
        function dragged(event) {
            event.sourceEvent.preventDefault();
            event.sourceEvent.stopPropagation();
            event.subject.fx = event.x;
            event.subject.fy = event.y;
        }
        function dragended(event) {
            if (!event.active) simulation.alphaTarget(0);
            event.subject.fx = null;
            event.subject.fy = null;
        }
        return d3.drag().on('start', dragstarted).on('drag', dragged).on('end', dragended);
    }
}

function renderPropagationGraph(data) {
    const container = document.getElementById('propagation-graph');
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = container.clientHeight;
    const svg = d3.select(container).append('svg').attr('width', width).attr('height', height);
    svg.append('text').attr('x', width / 2).attr('y', height / 2).attr('text-anchor', 'middle').attr('fill', '#64748b').text('传播路径可视化');
}

// ═══════════════════════════════════════════════════════════════
// Review Queue
// ═══════════════════════════════════════════════════════════════

async function loadReviewStats() {
    try {
        const stats = await apiCall('GET', '/api/review/stats');
        const wrap = document.getElementById('review-stats');
        wrap.innerHTML = `
            <div class="stat-card pending"><div class="stat-value">${stats.pending_assertions ?? 0}</div><div class="stat-label">待审核</div></div>
            <div class="stat-card"><div class="stat-value" style="border-top-color:var(--success)">${stats.approved_assertions ?? 0}</div><div class="stat-label">已批准</div></div>
            <div class="stat-card"><div class="stat-value" style="border-top-color:var(--danger)">${stats.rejected_assertions ?? 0}</div><div class="stat-label">已拒绝</div></div>
        `;
        // Also update dashboard stat
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
    if (!items.length) {
        wrap.innerHTML = '<p class="empty-state">暂无待审核项</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>谓词</th><th>对象</th><th>置信度</th><th>来源</th><th>操作</th></tr></thead>
        <tbody>${items.map(i => `
            <tr>
                <td title="${esc(i.assertion_id)}">${esc(i.assertion_id.substring(0, 8))}</td>
                <td>${esc(i.subject_entity_id || '—')}</td>
                <td>${esc(i.predicate)}</td>
                <td>${esc(i.object_value || '—')}</td>
                <td>${i.confidence.toFixed(2)}</td>
                <td>${esc(i.source_doc_id?.substring(0, 8) || '—')}</td>
                <td class="actions">
                    <button class="btn-sm btn-approve" onclick="approveItem('${esc(i.assertion_id)}')">批准</button>
                    <button class="btn-sm btn-reject" onclick="rejectItem('${esc(i.assertion_id)}')">拒绝</button>
                </td>
            </tr>
        `).join('')}</tbody>
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
        toast('已拒绝', 'success');
        loadReviewPending();
        loadReviewStats();
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Signals Management
// ═══════════════════════════════════════════════════════════════

async function createSignal() {
    const body = {
        subject_id: document.getElementById('sig-subject-id').value.trim(),
        thesis: document.getElementById('sig-thesis').value.trim(),
        score: parseFloat(document.getElementById('sig-score').value),
        confidence: parseFloat(document.getElementById('sig-confidence').value),
        horizon: document.getElementById('sig-horizon').value,
    };
    if (!body.subject_id || !body.thesis) return toast(I18N.t('toast.enter_asset_code'), 'error');

    try {
        await apiCall('POST', '/api/signals/create', body);
        toast(I18N.t('toast.signal_created'), 'success');
        document.getElementById('sig-thesis').value = '';
        loadSignals();
    } catch (e) {
        toast(e.message, 'error');
    }
}

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
    if (!signals.length) {
        wrap.innerHTML = '<p class="empty-state">暂无信号</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>论点</th><th>预测期</th><th>分数</th><th>置信度</th><th>择时决策</th><th>状态</th><th>操作</th></tr></thead>
        <tbody>${signals.map(s => `
            <tr>
                <td title="${esc(s.signal_id)}"><a href="javascript:void(0)" onclick="showSignalDetail('${esc(s.signal_id)}')">${esc(s.signal_id.substring(0, 8))}</a></td>
                <td>${esc(s.subject_id)}</td>
                <td>${esc(s.thesis)}</td>
                <td>${esc(s.horizon)}</td>
                <td>${s.score.toFixed(2)}</td>
                <td>${s.confidence.toFixed(2)}</td>
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

// ═══════════════════════════════════════════════════════════════
// Ingest
// ═══════════════════════════════════════════════════════════════

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
        toast(I18N.t('toast.ingest_complete'), 'success');
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
        </div>
    `;
}

// ═══════════════════════════════════════════════════════════════
// Memory & Learning
// ═══════════════════════════════════════════════════════════════

function loadMemoryPage() {
    loadEpisodes();
    loadStrategies();
    loadFailures();
}

async function loadEpisodes() {
    const filterEl = document.getElementById('episode-event-type-filter');
    const eventType = filterEl ? filterEl.value.trim() : '';
    const params = new URLSearchParams();
    if (eventType) params.append('event_type', eventType);
    
    try {
        const episodes = await apiCall('GET', `/api/memory/episodes?${params.toString()}`);
        const container = document.getElementById('market-episode-list');
        if (!episodes.length) {
            container.innerHTML = '<p class="empty-state">暂无事件记忆</p>';
            return;
        }
        container.innerHTML = episodes.map(ep => {
            const returnClass = ep.outcome_return > 0 ? 'positive' : 'negative';
            const returnSign = ep.outcome_return > 0 ? '+' : '';
            return `
                <div class="memory-card episode-card">
                    <div class="card-header-row">
                        <span class="badge event-type-badge">${esc(ep.event_type)}</span>
                        <span class="badge regime-badge">${esc(ep.market_regime)}</span>
                        <span class="return ${returnClass}">${returnSign}${ep.outcome_return.toFixed(2)}%</span>
                    </div>
                    ${ep.lesson ? `<div class="episode-lesson"><strong>经验教训：</strong>${esc(ep.lesson)}</div>` : ''}
                </div>
            `;
        }).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadStrategies() {
    const sfEl = document.getElementById('strategy-signal-filter');
    const signalFamily = sfEl ? sfEl.value.trim() : '';
    const mrEl = document.getElementById('strategy-regime-filter');
    const marketRegime = mrEl ? mrEl.value.trim() : '';
    const params = new URLSearchParams();
    if (signalFamily) params.append('signal_family', signalFamily);
    if (marketRegime) params.append('market_regime', marketRegime);
    
    try {
        const strategies = await apiCall('GET', `/api/memory/strategies?${params.toString()}`);
        const container = document.getElementById('strategy-memory-list');
        if (!strategies.length) {
            container.innerHTML = '<p class="empty-state">暂无策略记忆</p>';
            return;
        }
        container.innerHTML = strategies.map(str => `
            <div class="strategy-card">
                <div class="strategy-header">
                    <span class="badge">${esc(str.signal_family)}</span>
                    <span class="badge">${esc(str.market_regime)}</span>
                    <span class="sample-size">样本量: ${str.sample_size}</span>
                </div>
                <div class="metric-row">
                    <div class="metric">
                        <div class="metric-label">胜率</div>
                        <div class="win-rate-bar">
                            <div class="win-rate-fill" style="width: ${(str.win_rate * 100)}%"></div>
                            <span class="win-rate-text">${(str.win_rate * 100).toFixed(1)}%</span>
                        </div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">夏普比率</div>
                        <div class="metric-value">${str.sharpe_ratio.toFixed(2)}</div>
                    </div>
                    <div class="metric">
                        <div class="metric-label">平均超额收益</div>
                        <div class="metric-value ${str.average_excess_return > 0 ? 'positive' : 'negative'}">${str.average_excess_return.toFixed(2)}%</div>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadFailures() {
    const failureType = document.getElementById('failure-type-filter').value.trim();
    const sourceId = document.getElementById('failure-source-filter').value.trim();
    const params = new URLSearchParams();
    if (failureType) params.append('failure_type', failureType);
    if (sourceId) params.append('source_id', sourceId);
    
    try {
        const failures = await apiCall('GET', `/api/memory/failures?${params.toString()}`);
        const container = document.getElementById('failure-memory-list');
        if (!failures.length) {
            container.innerHTML = '<p class="empty-state">暂无失败记忆</p>';
            return;
        }
        container.innerHTML = failures.map(fail => `
            <div class="failure-card">
                <div class="failure-header">
                    <span class="failure-badge failure-type-${fail.failure_type}">${esc(fail.failure_type)}</span>
                    <span class="failure-source">来源: ${esc(fail.source_id.substring(0, 8))}...</span>
                </div>
                <div class="failure-root"><strong>根本原因：</strong>${esc(fail.root_cause)}</div>
                <div class="failure-corrective"><strong>修正措施：</strong>${esc(fail.corrective_action)}</div>
            </div>
        `).join('');
    } catch (e) {
        toast(e.message, 'error');
    }
}

async function loadEventSummary() {
    const eventType = document.getElementById('event-type-summary').value.trim();
    if (!eventType) return toast(I18N.t('toast.enter_event_type'), 'error');
    
    try {
        const summary = await apiCall('GET', `/api/memory/summarize/${encodeURIComponent(eventType)}`);
        const container = document.getElementById('event-summary-cards');
        container.innerHTML = `
            <div class="stat-card"><div class="stat-value">${summary.total_episodes}</div><div class="stat-label">总样本数</div></div>
            <div class="stat-card"><div class="stat-value ${summary.average_return > 0 ? 'positive' : 'negative'}">${summary.average_return.toFixed(2)}%</div><div class="stat-label">平均收益</div></div>
            <div class="stat-card"><div class="stat-value ${summary.average_excess_return > 0 ? 'positive' : 'negative'}">${summary.average_excess_return.toFixed(2)}%</div><div class="stat-label">平均超额收益</div></div>
            <div class="stat-card"><div class="stat-value">${(summary.positive_rate * 100).toFixed(1)}%</div><div class="stat-label">胜率</div></div>
        `;
    } catch (e) {
        toast(e.message, 'error');
    }
}

// ═══════════════════════════════════════════════════════════════
// Signal Detail View
// ═══════════════════════════════════════════════════════════════

async function showSignalDetail(signalId) {
    // Hide all sections, show detail
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

// ═══════════════════════════════════════════════════════════════
// Utilities
// ═══════════════════════════════════════════════════════════════

function fmtNum(v) {
    if (v === null || v === undefined || v === '') return '—';
    const n = typeof v === 'object' ? (v.ttm ?? v.value ?? JSON.stringify(v)) : v;
    if (typeof n === 'number') return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
    return String(n);
}

function fmtFinancial(v) {
    if (v === null || v === undefined) return '—';
    if (typeof v === 'object') {
        return Object.entries(v).map(([k, val]) =>
            `<strong>${k}</strong>: ${typeof val === 'number' ? val.toLocaleString() : val}`
        ).join('<br>');
    }
    return typeof v === 'number' ? v.toLocaleString() : String(v);
}

function esc(s) {
    if (!s) return '';
    const d = document.createElement('div');
    d.textContent = String(s);
    return d.innerHTML;
}

// ─── Initial Load ─────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', () => {
    applyChartDefaults();
    // Restore correct active states for switchers
    const savedTheme = localStorage.getItem('af-theme') || 'light';
    document.querySelectorAll('#settings-panel-theme .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.themeVal === savedTheme);
    });
    const savedLang = I18N.getLang();
    document.querySelectorAll('#settings-panel-language .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.lang === savedLang);
    });
    const savedColorScheme = localStorage.getItem('af-color-scheme') || 'vscode';
    applyColorScheme(savedColorScheme);
    I18N.applyAll();
    navigateTo('dashboard');
    loadEventSignals();

    // Update status bar doc count on dashboard load
    const updateStatusBar = async () => {
        try {
            const data = await apiCall('GET', '/api/workbench/dashboard');
            const dc = document.getElementById('status-doc-count');
            if (dc) dc.textContent = data.review_queue?.length ?? 0;
        } catch (e) { /* ignore */ }
    };
    updateStatusBar();

    // ─── SSE Realtime Stream ──────────────────────────────────
    initRealtimeStream();
});

let _realtimeEventSource = null;

function initRealtimeStream() {
    if (_realtimeEventSource) {
        _realtimeEventSource.close();
    }
    try {
        const es = new EventSource('/api/realtime/stream');
        _realtimeEventSource = es;

        es.addEventListener('document_parsed', (msg) => {
            try {
                const ev = JSON.parse(msg.data);
                updateQueuePanel({ type: 'document', ...ev.payload });
            } catch (_) {}
        });

        es.addEventListener('event_created', (msg) => {
            try {
                const ev = JSON.parse(msg.data);
                prependEventCard(ev.payload);
            } catch (_) {}
        });

        es.addEventListener('signal_generated', (msg) => {
            try {
                const ev = JSON.parse(msg.data);
                prependSignalCard(ev.payload);
            } catch (_) {}
        });

        es.addEventListener('queue_update', (msg) => {
            try {
                const ev = JSON.parse(msg.data);
                updateQueuePanel(ev.payload);
            } catch (_) {}
        });

        es.addEventListener('error_alert', (msg) => {
            try {
                const ev = JSON.parse(msg.data);
                console.warn('[SSE] Error:', ev.payload);
                toast(ev.payload.error || '系统错误', 'error');
            } catch (_) {}
        });

        es.addEventListener('worker_heartbeat', () => {
            loadWorkersStatus();  // Phase 2: real-time refresh on heartbeat
        });

        es.onerror = () => {
            // EventSource auto-reconnects; no action needed
        };

        console.log('[SSE] Realtime stream connected');
    } catch (e) {
        console.warn('[SSE] Failed to connect:', e);
    }
}

function updateQueuePanel(payload) {
    const badge = document.getElementById('queue-pending-count');
    if (badge && payload.processed !== undefined) {
        const current = parseInt(badge.textContent || '0', 10);
        badge.textContent = Math.max(0, current - (payload.processed || 0));
    }
}

function prependEventCard(payload) {
    const container = document.getElementById('today-new-events');
    if (!container || !payload.summary) return;
    const li = document.createElement('li');
    li.innerHTML = `<div class="item-title">${esc(payload.summary)}</div><div class="item-meta">${esc(payload.event_type || '')} • ${I18N.t('dashboard.just_now')}</div>`;
    li.classList.add('fresh-event');
    container.prepend(li);
    setTimeout(() => li.classList.remove('fresh-event'), 3000);
}

function prependSignalCard(payload) {
    const container = document.getElementById('today-high-priority');
    if (!container || !payload.thesis) return;
    const li = document.createElement('li');
    li.innerHTML = `<div class="item-title">${esc(payload.thesis)}</div><div class="item-meta">${esc(payload.subject_id || '')} • ${I18N.t('dashboard.score')}: ${(payload.score || 0).toFixed(2)}</div>`;
    li.classList.add('fresh-event');
    container.prepend(li);
    setTimeout(() => li.classList.remove('fresh-event'), 3000);
}

// ─── Live Crawl Feed Polling (分源独立轮询) ─────────────────
const CRAWL_FEED_SOURCES = [
    { id: 'cls', label: 'CLS', limit: 200 },
    { id: 'cnstock', label: 'CNSTOCK', limit: 200 },
    { id: 'cnstock_flash', label: '快讯', limit: 200 },
    { id: 'zhiqiu_reports', label: 'ZQ研报', limit: 200 },
    { id: 'zhiqiu_wechat', label: 'ZQ公众号', limit: 200 },
    { id: 'zhiqiu_transcript', label: 'ZQ纪要', limit: 200 },
];

const crawlFeedStates = {};

function getFeedState(sourceType) {
    if (!crawlFeedStates[sourceType]) {
        crawlFeedStates[sourceType] = { lastTs: null, seenIds: new Set() };
    }
    return crawlFeedStates[sourceType];
}

async function loadCrawlFeedForSource(sourceType, initial) {
    try {
        const state = getFeedState(sourceType);
        let url = `/api/dashboard/crawl-feed?limit=500&source_type=${encodeURIComponent(sourceType)}`;
        if (!initial && state.lastTs) {
            url += '&since=' + encodeURIComponent(state.lastTs);
        }
        const data = await apiCall('GET', url);
        if (!data || !Array.isArray(data.items)) return;

        const list = document.getElementById('feed-list-' + sourceType);
        const countEl = document.getElementById('feed-count-' + sourceType);
        const statusEl = document.getElementById('feed-status-' + sourceType);
        if (!list) return;

        // Update today's total count from API
        if (countEl && data.total_today !== undefined) {
            countEl.textContent = data.total_today + ' 条';
        }

        let newCount = 0;

        for (const item of [...data.items].reverse()) {
            if (state.seenIds.has(item.doc_id)) continue;
            state.seenIds.add(item.doc_id);
            newCount++;

            const li = document.createElement('li');
            const timeStr = item.published_at || item.crawled_at;
            let time = '';
            if (timeStr) {
                const d = new Date(timeStr);
                const now = new Date();
                const isToday = d.toDateString() === now.toDateString();
                time = isToday ? d.toLocaleTimeString() : d.toLocaleString();
            }
            li.innerHTML = `
                <span class="feed-title" title="${esc(item.title)}">${esc(item.title || '(无标题)')}</span>
                <span class="feed-time">${time}</span>
            `;
            li.classList.add('feed-new');
            setTimeout(() => li.classList.remove('feed-new'), 3000);
            list.prepend(li);
        }

        // Trim to source-configured max items
        const srcConfig = CRAWL_FEED_SOURCES.find(s => s.id === sourceType);
        const maxItems = srcConfig ? srcConfig.limit : 100;
        while (list.children.length > maxItems) {
            list.removeChild(list.lastChild);
        }

        // Remove empty-state if present
        const empty = list.querySelector('.empty-state');
        if (empty && list.children.length > 1) empty.remove();

        // Update trailing timestamp for next incremental poll
        const latest = data.items.reduce((best, item) => {
            const t = item.crawled_at || item.published_at;
            return t && (!best || t > best) ? t : best;
        }, null);
        if (latest) state.lastTs = latest;

        if (statusEl && newCount > 0) {
            statusEl.textContent = '+' + newCount + ' 新';
            statusEl.classList.add('badge-real');
            setTimeout(() => {
                statusEl.textContent = '监听中';
                statusEl.classList.remove('badge-real');
            }, 3000);
        }
    } catch (e) {
        console.warn('[CrawlFeed:' + sourceType + '] Poll error:', e);
    }
}

const crawlFeedIntervals = {};

async function triggerCrawlAllSources() {
    for (const { id } of CRAWL_FEED_SOURCES) {
        try {
            const resp = await fetch('/api/scheduler/trigger/' + encodeURIComponent(id), { method: 'POST' });
            const result = await resp.json();
            if (result.success) {
                console.log('[CrawlFeed] Triggered crawl for', id, ':', result.result.success_count, 'new');
            }
        } catch (e) {
            console.warn('[CrawlFeed] Failed to trigger crawl for', id, ':', e);
        }
    }
}

function startCrawlFeedPolling() {
    CRAWL_FEED_SOURCES.forEach(({ id }) => {
        if (crawlFeedIntervals[id]) return;
        loadCrawlFeedForSource(id, true);
        crawlFeedIntervals[id] = setInterval(() => loadCrawlFeedForSource(id, false), 5000);
    });
    console.log('[CrawlFeed] Per-source polling started (5s interval)');
}

function stopCrawlFeedPolling() {
    Object.keys(crawlFeedIntervals).forEach(id => {
        clearInterval(crawlFeedIntervals[id]);
        delete crawlFeedIntervals[id];
    });
}

// ═══════════════════════════════════════════════════════════════
// Outcomes Management
// ═══════════════════════════════════════════════════════════════

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
    if (!outcomes.length) {
        wrap.innerHTML = '<p class="empty-state">暂无回测结果</p>';
        return;
    }
    wrap.innerHTML = `<table>
        <thead><tr><th>ID</th><th>主体</th><th>事件类型</th><th>收益</th><th>超额收益</th><th>最大回撤</th><th>教训</th><th>操作</th></tr></thead>
        <tbody>${outcomes.map(o => {
            const returnClass = o.outcome_return > 0 ? 'positive' : 'negative';
            const excessReturnClass = o.outcome_excess_return > 0 ? 'positive' : 'negative';
            const eventType = o.metadata?.event_type || '—';
            return `
            <tr>
                <td title="${esc(o.outcome_id)}">${esc(o.outcome_id.substring(0, 8))}</td>
                <td>${esc(o.subject_id)}</td>
                <td>${esc(eventType)}</td>
                <td class="${returnClass}">${o.outcome_return > 0 ? '+' : ''}${o.outcome_return?.toFixed(2) ?? '—'}%</td>
                <td class="${excessReturnClass}">${o.outcome_excess_return > 0 ? '+' : ''}${o.outcome_excess_return?.toFixed(2) ?? '—'}%</td>
                <td>${o.max_drawdown?.toFixed(2) ?? '—'}%</td>
                <td class="lesson-cell">${o.lesson ? esc(o.lesson) : '<span class="empty-state">—</span>'}</td>
                <td class="actions">
                    <button class="btn-sm btn-detail" onclick="showOutcomeDetail('${esc(o.outcome_id)}', '${esc(o.signal_id)}')">详情</button>
                    <button class="btn-sm btn-edit" onclick="editLesson('${esc(o.outcome_id)}', '${esc(o.lesson || '')}')">编辑</button>
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
        toast(`Outcome 详情加载成功`, 'success');
        console.log('Outcome detail:', data);
    } catch (e) {
        toast(e.message, 'error');
    }
}

// 闭循环运行
async function runClosedLoop() {
    const statusEl = document.getElementById('closed-loop-status');
    const resultsEl = document.getElementById('closed-loop-results');
    const btnEl = document.getElementById('btn-run-closed-loop');

    // 禁用按钮并显示加载状态
    btnEl.disabled = true;
    btnEl.textContent = '运行中...';
    statusEl.textContent = '正在运行闭循环，请稍候...';
    resultsEl.style.display = 'none';

    try {
        const summary = await apiCall('POST', '/api/pipeline/closed-loop');
        renderClosedLoopResults(summary);
        statusEl.textContent = '闭循环运行完成！';
        toast('闭循环运行完成', 'success');
    } catch (e) {
        statusEl.textContent = '运行失败: ' + e.message;
        toast(e.message, 'error');
    } finally {
        btnEl.disabled = false;
        btnEl.textContent = '运行闭循环';
    }
}

function renderClosedLoopResults(summary) {
    const resultsEl = document.getElementById('closed-loop-results');
    resultsEl.style.display = 'block';

    resultsEl.innerHTML = `
        <div class="card-row" style="margin-top:16px;">
            <div class="stat-card pending">
                <div class="stat-value">${summary.signals_generated}</div>
                <div class="stat-label">生成信号</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#38a169;">${summary.signals_backtested}</div>
                <div class="stat-label">回测信号</div>
            </div>
        </div>
        <div class="card-row" style="margin-top:16px;">
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#3182ce;">${(summary.avg_return * 100).toFixed(2)}%</div>
                <div class="stat-label">平均收益</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#805ad5;">${(summary.avg_excess_return * 100).toFixed(2)}%</div>
                <div class="stat-label">平均超额收益</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#d69e2e;">${(summary.win_rate * 100).toFixed(1)}%</div>
                <div class="stat-label">胜率</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" style="border-top-color:#e53e3e;">${(summary.correct_direction_rate * 100).toFixed(1)}%</div>
                <div class="stat-label">方向正确率</div>
            </div>
        </div>
        <div class="card" style="margin-top:16px;">
            <div class="card-header">
                <h3>回测结果详情</h3>
            </div>
            <table>
                <thead>
                    <tr>
                        <th>信号ID</th>
                        <th>标的</th>
                        <th>收益</th>
                        <th>超额收益</th>
                        <th>方向正确</th>
                    </tr>
                </thead>
                <tbody>
                    ${(summary.results || []).map(r => `
                        <tr>
                            <td title="${r.signal_id}">${r.signal_id.substring(0, 8)}...</td>
                            <td>${r.subject_id}</td>
                            <td class="${r.return > 0 ? 'positive' : 'negative'}">${r.return > 0 ? '+' : ''}${(r.return * 100).toFixed(2)}%</td>
                            <td class="${r.excess_return > 0 ? 'positive' : 'negative'}">${r.excess_return > 0 ? '+' : ''}${(r.excess_return * 100).toFixed(2)}%</td>
                            <td>${r.direction_correct ? '✓' : '✗'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;
}

// ============ Signal Lab ============
let signalLabData = {
    featureGroups: {},
    labelTypes: {},
    scorerTypes: {}
};

async function loadSignalLab() {
    try {
        // Load summary
        const summary = await apiCall('GET', '/api/signal-lab/summary');
        if (summary.success && summary.summary) {
            document.getElementById('sl-signals-count').textContent = summary.summary.signals_count ?? '-';
            document.getElementById('sl-backtests-count').textContent = summary.summary.backtests_count ?? '-';
            document.getElementById('sl-features-count').textContent = summary.summary.features_count ?? '-';
            document.getElementById('sl-groups-count').textContent = summary.summary.feature_groups_count ?? '-';
        }
        // Load feature groups
        await loadFeatureGroups();
        // Load label types
        await loadLabelTypes();
        // Load scorers
        await loadScorers();
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
    select.innerHTML = '<option value="">全部特征组</option>' +
        Object.keys(groups).map(key => `<option value="${key}">${esc(groups[key].name)}</option>`).join('');
}

async function computeFeatures() {
    const subjectId = document.getElementById('sl-subject-id').value.trim();
    const group = document.getElementById('sl-feature-group').value;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-features-loading');
    const resultEl = document.getElementById('sl-features-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const payload = { subject_id: subjectId };
        if (group) {
            payload.groups = [group];
        }
        const data = await apiCall('POST', '/api/signal-lab/features/compute', payload);
        if (data.success) {
            renderFeaturesResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算特征失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderFeaturesResult(data) {
    const container = document.getElementById('sl-features-table');
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
    container.innerHTML = Object.entries(types).map(([key, type]) => `
        <div class="label-type-card">
            <div class="lt-name">${esc(type.name)}</div>
            <div class="lt-desc">${esc(type.description)}</div>
        </div>
    `).join('');
}

async function computeLabels() {
    const subjectId = document.getElementById('sl-label-subject').value.trim();
    const labelType = document.getElementById('sl-label-type').value;
    const horizon = parseInt(document.getElementById('sl-label-horizon').value) || 20;

    if (!subjectId) {
        toast('请输入标的代码', 'error');
        return;
    }

    const loadingEl = document.getElementById('sl-labels-loading');
    const resultEl = document.getElementById('sl-labels-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const data = await apiCall('POST', '/api/signal-lab/labels/compute', {
            subject_id: subjectId,
            label_type: labelType,
            horizon: horizon
        });
        if (data.success) {
            renderLabelsResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('计算标签失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderLabelsResult(data) {
    const container = document.getElementById('sl-labels-table');
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
    container.innerHTML = Object.entries(scorers).map(([key, scorer]) => `
        <div class="scorer-card">
            <div class="sc-name">${esc(scorer.name)}</div>
            <div class="sc-desc">${esc(scorer.description)}</div>
        </div>
    `).join('');
}

async function runBacktests() {
    const signalIdsInput = document.getElementById('sl-backtest-signals').value.trim();
    const initialCapital = parseFloat(document.getElementById('sl-initial-capital').value) || 1000000;

    const loadingEl = document.getElementById('sl-backtests-loading');
    const resultEl = document.getElementById('sl-backtests-result');

    loadingEl.classList.remove('hidden');
    resultEl.classList.add('hidden');

    try {
        const payload = { initial_capital: initialCapital };
        if (signalIdsInput) {
            payload.signal_ids = signalIdsInput.split(',').map(s => s.trim()).filter(s => s);
        }
        const data = await apiCall('POST', '/api/signal-lab/backtests/run', payload);
        if (data.success) {
            renderBacktestsResult(data);
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('运行回测失败: ' + e.message, 'error');
    } finally {
        loadingEl.classList.add('hidden');
    }
}

function renderBacktestsResult(data) {
    const container = document.getElementById('sl-backtests-table');
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
                        <td title="${esc(r.signal_id)}">${esc(r.signal_id.substring(0, 8))}...</td>
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

// Signal Lab Tab Switching
function switchSignalLabTab(tabName) {
    document.querySelectorAll('#section-signal-lab .tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('#section-signal-lab .tab-panel').forEach(p => p.classList.add('hidden'));
    document.querySelector(`#section-signal-lab .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
    document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
}

// ═══════════════════════════════════════════════════════════════
// Template Management
// ═══════════════════════════════════════════════════════════════

let currentTemplateState = {
    selectedTemplate: null,
    selectedFileType: 'docx',
    discoveredPlaceholders: [],
    placeholderValues: {},
    renderedReportId: null,
    templates: []
};

async function loadTemplatesPage() {
    try {
        await loadTemplatesList();
        // Initialize upload drop zone
        initTemplateDropZone();
        // Initialize template select dropdowns
        await initTemplateSelects();
    } catch (e) {
        toast('加载模板页面失败: ' + e.message, 'error');
    }
}

async function loadTemplatesList() {
    try {
        const data = await apiCall('GET', '/api/templates/');
        currentTemplateState.templates = data.templates || [];
        renderTemplatesList(currentTemplateState.templates);
    } catch (e) {
        console.error('Failed to load templates:', e);
        const container = document.getElementById('template-list');
        if (container) container.innerHTML = '<p class="empty-state">加载失败</p>';
    }
}

// Alias for consistency
async function loadTemplates() {
    return loadTemplatesList();
}

// Global variable to track current selected template
let currentSelectedTemplate = null;
let currentSelectedFileType = null;

let isEditMode = false;

function renderTemplatesList(templates) {
    const container = document.getElementById('templates-grid');
    if (!container) return;

    if (!templates.length) {
        container.innerHTML = '<div style="grid-column: 1/-1; text-align: center; padding: 60px 20px; color: var(--text-secondary);">暂无模板，点击下方"上传"按钮添加</div>';
        return;
    }

    container.innerHTML = templates.map((t, index) => {
        // Determine file type from template data
        let fileType = 'docx';
        if (t.has_docx) fileType = 'docx';
        else if (t.has_pptx) fileType = 'pptx';
        else if (t.has_excel) fileType = 'excel';
        else if (t.type) fileType = t.type;

        const templateName = t.template_name || t.name;
        const version = t.version || '1.0';
        const description = t.description || '';

        // Get icon based on file type
        let iconHtml = '';
        if (fileType === 'pptx') {
            iconHtml = '<i class="codicon codicon-file-media" style="font-size: 60px;"></i>';
        } else if (fileType === 'excel') {
            iconHtml = '<i class="codicon codicon-table" style="font-size: 60px;"></i>';
        } else {
            iconHtml = '<i class="codicon codicon-file-code" style="font-size: 60px;"></i>';
        }

        const wrapperClasses = ['iphone-template-wrapper'];
        if (isEditMode) wrapperClasses.push('edit-mode');

        return `
        <div class="${wrapperClasses.join(' ')}" data-template-name="${esc(templateName)}" data-index="${index}" ${isEditMode ? 'draggable="true" ondragstart="handleDragStart(event)" ondragover="handleDragOver(event)" ondrop="handleDrop(event)"' : ''}>
            <button class="iphone-delete-btn" onclick="event.stopPropagation(); deleteTemplate('${esc(templateName)}')"></button>
            <div class="iphone-app-icon ${fileType}" onclick="!isEditMode && selectTemplate('${esc(templateName)}', '${fileType}')">
                ${iconHtml}
            </div>
            <div class="iphone-app-name">${esc(templateName)}</div>
        </div>
    `}).join('');
}

// Select template and show detail view
async function selectTemplate(templateName, fileType) {
    // Update both state variables
    currentSelectedTemplate = templateName;
    currentSelectedFileType = fileType;
    currentTemplateState.selectedTemplate = templateName;
    currentTemplateState.selectedFileType = fileType;
    currentTemplateState.discoveredPlaceholders = [];
    currentTemplateState.placeholderValues = {};
    currentTemplateState.renderedReportId = null;

    // Update UI selection
    const cards = document.querySelectorAll('.iphone-template-wrapper');
    cards.forEach(c => c.classList.remove('selected'));
    const selected = document.querySelector(`.iphone-template-wrapper[data-template-name="${esc(templateName)}"]`);
    if (selected) selected.classList.add('selected');

    // Load template details
    await loadTemplateDetails(templateName);

    // Switch to detail view
    document.getElementById('templates-list-view').classList.add('hidden');
    document.getElementById('template-detail-view').classList.remove('hidden');

    // Clear any previous placeholder data
    clearPlaceholderData();

    // Auto-load placeholders for render tab
    await loadTemplatePlaceholdersForRender(templateName, fileType);
}

// Load template details and populate the detail view
async function loadTemplateDetails(templateName) {
    try {
        const data = await apiCall('GET', '/api/templates/');
        const templates = data.templates || [];
        const template = templates.find(t => (t.template_name || t.name) === templateName);

        if (template) {
            // Update detail view UI
            document.getElementById('detail-template-name').textContent = template.template_name || template.name;
            document.getElementById('detail-template-title').textContent = template.template_name || template.name;
            document.getElementById('detail-template-description').textContent = template.description || '';
            document.getElementById('detail-template-version').textContent = `v${template.version || '1.0'}`;

            // Update type badges
            document.getElementById('detail-has-docx').classList.toggle('hidden', !template.has_docx);
            document.getElementById('detail-has-pptx').classList.toggle('hidden', !template.has_pptx);
            document.getElementById('detail-has-excel').classList.toggle('hidden', !template.has_excel);

            // Update large icon
            const iconEl = document.getElementById('detail-template-icon');
            iconEl.className = 'template-icon-large';
            if (template.has_docx) iconEl.classList.add('docx');
            else if (template.has_pptx) iconEl.classList.add('pptx');
            else if (template.has_excel) iconEl.classList.add('excel');
            else iconEl.classList.add('default');

            // Set download button handler
            document.getElementById('btn-download-template').onclick = () => {
                downloadTemplateFile(templateName, currentSelectedFileType);
            };

            // Set delete button handler
            document.getElementById('btn-delete-template').onclick = () => {
                deleteTemplate(templateName);
            };
        }
    } catch (e) {
        console.error('Failed to load template details:', e);
        toast('加载模板详情失败: ' + e.message, 'error');
    }
}

// Go back to templates list view
function goBackToTemplates() {
    document.getElementById('template-detail-view').classList.add('hidden');
    document.getElementById('templates-list-view').classList.remove('hidden');
    currentSelectedTemplate = null;
    currentSelectedFileType = null;
    clearPlaceholderData();
}

// Upload template modal functions
function openUploadModal() {
    document.getElementById('upload-template-modal').classList.remove('hidden');
    // Reset form
    document.getElementById('template-name-input').value = '';
    document.getElementById('template-desc-input').value = '';
    document.getElementById('template-version-input').value = '1.0';
    document.getElementById('template-file-input').value = '';
    document.getElementById('selected-file-info').classList.add('hidden');
    document.getElementById('template-upload-status').innerHTML = '';
}

function closeUploadModal() {
    document.getElementById('upload-template-modal').classList.add('hidden');
}

// Drag & drop for template reordering - iPhone style
let draggedTemplateName = null;
let draggedElement = null;

function handleDragStart(event) {
    const card = event.target.closest('.iphone-template-wrapper');
    if (!card) return;
    draggedTemplateName = card.dataset.templateName;
    draggedElement = card;
    card.classList.add('dragging');

    // Hide the default drag image
    const dragImage = new Image();
    dragImage.src = 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7';
    event.dataTransfer.setDragImage(dragImage, 0, 0);

    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/plain', draggedTemplateName);
}

function handleDragOver(event) {
    event.preventDefault();
    if (event.dataTransfer) {
        event.dataTransfer.dropEffect = 'move';
    }

    const container = document.getElementById('templates-grid');

    if (!draggedTemplateName || !draggedElement) return;

    // Find where to insert
    const afterElement = getDragAfterElement(container, event.clientX, event.clientY);

    // Directly move DOM element
    if (afterElement) {
        container.insertBefore(draggedElement, afterElement);
    } else {
        container.appendChild(draggedElement);
    }
}

function getDragAfterElement(container, x, y) {
    const draggableElements = [...container.querySelectorAll('.iphone-template-wrapper:not(.dragging)')];

    return draggableElements.reduce((closest, child) => {
        const box = child.getBoundingClientRect();
        const centerX = box.left + box.width / 2;
        const centerY = box.top + box.height / 2;

        // Calculate distance from mouse to center of element
        const dx = x - centerX;
        const dy = y - centerY;
        const distance = Math.sqrt(dx * dx + dy * dy);

        // Find element that is closest and after the mouse position
        const isAfter = y < centerY || (Math.abs(y - centerY) < box.height / 2 && x < centerX);

        if (isAfter && (closest.element === null || distance < closest.distance)) {
            return { distance: distance, element: child };
        } else {
            return closest;
        }
    }, { distance: Number.POSITIVE_INFINITY, element: null }).element;
}

async function handleDrop(event) {
    event.preventDefault();

    const container = document.getElementById('templates-grid');
    const cards = Array.from(container.querySelectorAll('.iphone-template-wrapper'));

    // Clear dragging style
    cards.forEach(card => {
        card.classList.remove('dragging');
    });

    if (!draggedTemplateName) return;

    // Get final order from DOM
    const newOrder = cards.map(c => c.dataset.templateName);

    // Update state
    const templateMap = {};
    currentTemplateState.templates.forEach(t => {
        const name = t.template_name || t.name;
        templateMap[name] = t;
    });
    currentTemplateState.templates = newOrder.map(name => templateMap[name]);

    // Send to backend
    try {
        await apiCall('POST', '/api/templates/reorder', { template_names: newOrder });
        toast('模板顺序已更新', 'success');
    } catch (e) {
        toast('更新顺序失败: ' + e.message, 'error');
        await loadTemplates();
    }

    draggedTemplateName = null;
    draggedElement = null;
}

// Edit template modal functions
let editingTemplateName = null;

function openEditTemplateModal(templateName, description, version) {
    editingTemplateName = templateName;
    document.getElementById('edit-template-name').value = templateName;
    document.getElementById('edit-template-description').value = description || '';
    document.getElementById('edit-template-version').value = version || '1.0';
    document.getElementById('edit-template-modal').classList.remove('hidden');
}

function closeEditTemplateModal() {
    document.getElementById('edit-template-modal').classList.add('hidden');
    editingTemplateName = null;
}

async function saveTemplateEdit() {
    const newName = document.getElementById('edit-template-name').value.trim();
    const newDescription = document.getElementById('edit-template-description').value.trim();
    const newVersion = document.getElementById('edit-template-version').value.trim();

    if (!newName) {
        toast('模板名称不能为空', 'error');
        return;
    }

    try {
        await apiCall('PATCH', `/api/templates/${encodeURIComponent(editingTemplateName)}`, {
            template_name: newName,
            description: newDescription,
            version: newVersion
        });

        toast('模板已更新', 'success');
        closeEditTemplateModal();
        await loadTemplates();

        // If we renamed the currently selected template, update selection
        if (currentSelectedTemplate === editingTemplateName && newName !== editingTemplateName) {
            currentSelectedTemplate = newName;
            currentTemplateState.selectedTemplate = newName;
            await loadTemplateDetails(newName);
        }
    } catch (e) {
        toast('更新模板失败: ' + e.message, 'error');
    }
}

// Toggle edit mode for templates
let originalTemplates = [];

function toggleEditMode() {
    isEditMode = !isEditMode;

    // Store original state when entering edit mode
    if (isEditMode) {
        originalTemplates = [...(currentTemplateState.templates || [])];
    }

    // Update button visibility
    document.getElementById('btn-edit-templates').classList.toggle('hidden', isEditMode);
    document.getElementById('btn-save-templates-order').classList.toggle('hidden', !isEditMode);

    // Re-render templates
    renderTemplatesList(currentTemplateState.templates || []);
}

async function saveTemplatesOrder() {
    // Get current template order from DOM
    const cards = document.querySelectorAll('.iphone-template-wrapper');
    const newOrder = Array.from(cards).map(card => card.dataset.templateName);

    try {
        // Update order
        await apiCall('POST', '/api/templates/reorder', { template_names: newOrder });

        toast('模板已保存', 'success');
        isEditMode = false;

        // Update buttons
        document.getElementById('btn-edit-templates').classList.remove('hidden');
        document.getElementById('btn-save-templates-order').classList.add('hidden');

        // Reload templates
        await loadTemplates();
    } catch (e) {
        toast('保存失败: ' + e.message, 'error');
    }
}

// Clear placeholder data from form
function clearPlaceholderData() {
    const container = document.getElementById('render-placeholders-container');
    if (container) container.innerHTML = '';
    const result = document.getElementById('render-result');
    if (result) result.classList.add('hidden');
}

async function initTemplateSelects() {
    try {
        const data = await apiCall('GET', '/api/templates/');
        const templates = data.templates || [];

        const configureSelect = document.getElementById('configure-template-select');
        const renderSelect = document.getElementById('render-template-select');

        const optionsHtml = '<option value="">选择模板...</option>' +
            templates.map(t => {
                const templateName = t.template_name || t.name;
                return `<option value="${esc(templateName)}">${esc(templateName)}</option>`;
            }).join('');

        if (configureSelect) configureSelect.innerHTML = optionsHtml;
        if (renderSelect) renderSelect.innerHTML = optionsHtml;
    } catch (e) {
        console.error('Failed to init template selects:', e);
    }
}

async function discoverPlaceholders() {
    // Use current selected template if available, otherwise check dropdown
    let templateName = currentSelectedTemplate;
    let fileType = currentSelectedFileType || 'docx';

    if (!templateName) {
        const templateSelect = document.getElementById('configure-template-select');
        const typeSelect = document.getElementById('configure-type-select');
        templateName = templateSelect?.value;
        fileType = typeSelect?.value || 'docx';
    }

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const loadingEl = document.getElementById('discover-loading');
    const placeholderList = document.getElementById('placeholder-list');
    const noPlaceholders = document.getElementById('no-placeholders');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (placeholderList) placeholderList.innerHTML = '';
    if (noPlaceholders) noPlaceholders.classList.add('hidden');

    try {
        const data = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/placeholders/${fileType}`);
        currentTemplateState.discoveredPlaceholders = data.placeholders || [];
        currentTemplateState.selectedTemplate = templateName;
        currentTemplateState.selectedFileType = fileType;
        renderPlaceholders(data.placeholders || []);
    } catch (e) {
        toast('发现占位符失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

function renderPlaceholders(placeholders) {
    const container = document.getElementById('placeholder-list');
    const noPlaceholders = document.getElementById('no-placeholders');

    if (!container) return;

    if (!placeholders.length) {
        if (noPlaceholders) noPlaceholders.classList.remove('hidden');
        container.innerHTML = '';
        return;
    }

    if (noPlaceholders) noPlaceholders.classList.add('hidden');

    // 确保currentTemplateState有placeholderConfigs
    if (!currentTemplateState.placeholderConfigs) {
        currentTemplateState.placeholderConfigs = {};
    }

    container.innerHTML = placeholders.map(ph => {
        const name = typeof ph === 'string' ? ph : (ph.name || ph);
        const config = currentTemplateState.placeholderConfigs[name] || {};
        const type = config.type || 'string';
        const description = config.description || '';
        const prompt = config.prompt || '';

        return `
        <div class="placeholder-item" data-placeholder-name="${esc(name)}">
            <div class="placeholder-item-header">
                <div class="placeholder-name">${esc(name)}</div>
                <select class="placeholder-type-select" onchange="updatePlaceholderConfig('${esc(name)}', 'type', this.value)">
                    <option value="string" ${type === 'string' ? 'selected' : ''}>字符串</option>
                    <option value="number" ${type === 'number' ? 'selected' : ''}>数字</option>
                    <option value="date" ${type === 'date' ? 'selected' : ''}>日期</option>
                    <option value="rich_text" ${type === 'rich_text' ? 'selected' : ''}>长文本/AI生成</option>
                </select>
            </div>
            <input type="text" class="placeholder-description-input" placeholder="占位符描述"
                   value="${esc(description)}"
                   onchange="updatePlaceholderConfig('${esc(name)}', 'description', this.value)" />
            <textarea class="placeholder-prompt-textarea" placeholder="AI生成提示词（仅rich_text类型时使用，描述需要生成的内容"
                      onchange="updatePlaceholderConfig('${esc(name)}', 'prompt', this.value)">${esc(prompt)}</textarea>
        </div>
    `}).join('');
}

function updatePlaceholderConfig(name, key, value) {
    if (!currentTemplateState.placeholderConfigs) {
        currentTemplateState.placeholderConfigs = {};
    }
    if (!currentTemplateState.placeholderConfigs[name]) {
        currentTemplateState.placeholderConfigs[name] = {};
    }
    currentTemplateState.placeholderConfigs[name][key] = value;
}

function updatePlaceholderValue(name, value) {
    currentTemplateState.placeholderValues[name] = value;
}

async function loadTemplatePlaceholdersForRender(templateName, fileType = 'docx') {
    const container = document.getElementById('render-placeholders-container');
    if (!container) return;

    container.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在加载占位符配置...</span></div>';

    try {
        // 先尝试获取模板的配置
        let placeholders = [];
        try {
            const data = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/placeholders/${fileType}`);
            placeholders = data.placeholders || [];
        } catch (e) {
            // 如果没有配置，就用空的
            placeholders = [];
        }

        // 加载配置
        let config = {};
        try {
            const configData = await apiCall('GET', `/api/templates/${encodeURIComponent(templateName)}/config`);
            config = configData.config || {};
            currentTemplateState.placeholderConfigs = config.placeholders || {};
        } catch (e) {
            // 没有配置也没关系
        }

        renderRenderPlaceholders(placeholders, currentTemplateState.placeholderConfigs || {});
    } catch (e) {
        container.innerHTML = `<div class="error-state">加载占位符失败: ${esc(e.message)}</div>`;
        toast('加载占位符失败: ' + e.message, 'error');
    }
}

function renderRenderPlaceholders(placeholders, configs = {}) {
    const container = document.getElementById('render-placeholders-container');
    if (!container) return;

    if (!placeholders.length) {
        container.innerHTML = '<div class="empty-state"><i class="codicon codicon-search"></i><p>该模板没有配置占位符</p></div>';
        return;
    }

    container.innerHTML = placeholders.map(ph => {
        const name = typeof ph === 'string' ? ph : (ph.name || ph);
        const config = configs[name] || {};
        const type = config.type || 'string';
        const existingValue = currentTemplateState.placeholderValues[name] || '';

        let inputHtml = '';
        if (type === 'rich_text') {
            inputHtml = `
                <textarea class="render-placeholder-textarea" placeholder="输入内容或点击右侧AI按钮生成"
                          data-placeholder-name="${esc(name)}"
                          onchange="updatePlaceholderValue('${esc(name)}', this.value)">${esc(existingValue)}</textarea>
                <button class="btn-ai-generate" onclick="generateAiContent('${esc(name)}')">
                    <i class="codicon codicon-hubot"></i>
                    AI生成
                </button>
            `;
        } else {
            inputHtml = `
                <input type="text" class="render-placeholder-input" placeholder="输入值"
                       value="${esc(existingValue)}"
                       data-placeholder-name="${esc(name)}"
                       onchange="updatePlaceholderValue('${esc(name)}', this.value)" />
            `;
        }

        return `
        <div class="render-placeholder-item">
            <div class="render-placeholder-header">
                <div class="render-placeholder-name">${esc(name)}</div>
                <div class="render-placeholder-type">${type === 'rich_text' ? 'AI生成文本' : type}</div>
            </div>
            ${inputHtml}
        </div>
        `}).join('');
}

function switchTemplatesTab(tabName) {
    // Handle both list view tabs and detail view tabs
    const detailViewActive = !document.getElementById('template-detail-view').classList.contains('hidden');

    if (detailViewActive && (tabName === 'detail-configure' || tabName === 'detail-render')) {
        // Detail view tabs
        document.querySelectorAll('#template-detail-view .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#template-detail-view .tab-panel').forEach(p => p.classList.add('hidden'));
        document.querySelector(`#template-detail-view .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
    } else {
        // List view tabs (if any)
        document.querySelectorAll('#section-templates .tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('#section-templates .tab-panel').forEach(p => p.classList.add('hidden'));
        document.querySelector(`#section-templates .tab-btn[data-tab="${tabName}"]`)?.classList.add('active');
        document.getElementById(`tab-${tabName}`)?.classList.remove('hidden');
    }
}

function initTemplateDropZone() {
    const dropZone = document.getElementById('template-drop-zone');
    const fileInput = document.getElementById('template-file-input');

    if (!dropZone || !fileInput) return;

    // Handle drop
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('dragover');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('dragover');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('dragover');
        const files = e.dataTransfer.files;
        if (files.length) {
            handleTemplateFileSelect(files[0]);
        }
    });

    // Handle click on drop zone to open file selector
    dropZone.addEventListener('click', () => {
        fileInput.click();
    });

    // Handle file input change
    fileInput.addEventListener('change', (e) => {
        if (e.target.files?.[0]) {
            handleTemplateFileSelect(e.target.files[0]);
        }
    });

    // Handle choose file button
    const chooseBtn = document.getElementById('btn-choose-file');
    if (chooseBtn) {
        chooseBtn.addEventListener('click', () => {
            fileInput.click();
        });
    }

    // Handle clear file button
    const clearBtn = document.getElementById('btn-clear-file');
    if (clearBtn) {
        clearBtn.addEventListener('click', () => {
            clearFileSelection();
        });
    }
}

async function handleTemplateFileSelect(file) {
    if (!file.name.match(/\.(pptx|docx)$/i)) {
        toast('请上传 .pptx 或 .docx 文件', 'error');
        return;
    }

    const fileNameEl = document.getElementById('selected-file-name');
    const fileInfoEl = document.getElementById('selected-file-info');

    if (fileNameEl) fileNameEl.textContent = file.name;
    if (fileInfoEl) fileInfoEl.classList.remove('hidden');
}

function clearFileSelection() {
    const fileNameEl = document.getElementById('selected-file-name');
    const fileInfoEl = document.getElementById('selected-file-info');
    const fileInput = document.getElementById('template-file-input');

    if (fileNameEl) fileNameEl.textContent = '';
    if (fileInfoEl) fileInfoEl.classList.add('hidden');
    if (fileInput) fileInput.value = '';
}

async function uploadTemplate() {
    const fileInput = document.getElementById('template-file-input');
    const nameInput = document.getElementById('template-name-input');
    const descInput = document.getElementById('template-desc-input');
    const versionInput = document.getElementById('template-version-input');
    const typeSelect = document.getElementById('template-type-select');
    const statusEl = document.getElementById('template-upload-status');

    const file = fileInput?.files?.[0];
    if (!file) {
        toast('请选择文件', 'error');
        return;
    }

    const name = nameInput?.value.trim() || file.name.replace(/\.(pptx|docx|xlsx)$/i, '');
    const description = descInput?.value.trim() || '';
    const version = versionInput?.value.trim() || '1.0';
    const fileType = typeSelect?.value || 'docx';

    // Determine file type from extension if needed
    let actualFileType = fileType;
    if (file.name.toLowerCase().endsWith('.pptx')) actualFileType = 'pptx';
    if (file.name.toLowerCase().endsWith('.xlsx')) actualFileType = 'excel';

    if (statusEl) {
        statusEl.innerHTML = '<div class="loading"><div class="spinner"></div><span>正在上传...</span></div>';
        statusEl.classList.remove('hidden');
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('template_name', name);
    formData.append('file_type', actualFileType);
    formData.append('description', description);
    formData.append('version', version);

    try {
        const response = await fetch('/api/templates/upload', {
            method: 'POST',
            headers: { 'Authorization': 'Bearer dummy' },
            body: formData
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Upload failed' }));
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await response.json();
        toast('模板上传成功', 'success');
        await loadTemplatesList();
        await initTemplateSelects();
        switchTemplatesTab('configure');

        // Reset form
        if (nameInput) nameInput.value = '';
        if (descInput) descInput.value = '';
        clearFileSelection();
    } catch (e) {
        toast('上传失败: ' + e.message, 'error');
    } finally {
        if (statusEl) statusEl.classList.add('hidden');
    }
}

async function downloadTemplateFile(name, type) {
    try {
        window.open(`/api/templates/files/${encodeURIComponent(name)}/${type}`, '_blank');
    } catch (e) {
        toast('下载失败: ' + e.message, 'error');
    }
}

async function deleteTemplate(name) {
    if (!confirm(`确定要删除模板 "${name}" 吗？`)) return;

    try {
        await apiCall('DELETE', `/api/templates/${encodeURIComponent(name)}`);
        toast('模板已删除', 'success');
        await loadTemplatesList();
        await initTemplateSelects();

        if (currentTemplateState.selectedTemplate === name) {
            currentTemplateState.selectedTemplate = null;
        }
    } catch (e) {
        toast('删除失败: ' + e.message, 'error');
    }
}

async function createYamlConfig() {
    const name = document.getElementById('template-name-input')?.value.trim();
    const description = document.getElementById('template-desc-input')?.value.trim();
    const yamlContent = prompt('请输入YAML配置:');

    if (!name) {
        toast('请输入模板名称', 'error');
        return;
    }

    if (!yamlContent) {
        toast('请输入YAML配置', 'error');
        return;
    }

    try {
        await apiCall('POST', '/api/templates/create-yaml', {
            name,
            description,
            yaml_content: yamlContent
        });
        toast('YAML配置创建成功', 'success');
        await loadTemplatesList();
        await initTemplateSelects();
    } catch (e) {
        toast('创建失败: ' + e.message, 'error');
    }
}

async function renderReportFromTemplate() {
    const templateSelect = document.getElementById('render-template-select');
    const typeSelect = document.getElementById('render-type-select');
    const canonicalIdInput = document.getElementById('render-canonical-id');
    const reportTypeSelect = document.getElementById('render-report-type');

    const templateName = templateSelect?.value || currentTemplateState.selectedTemplate;
    const fileType = typeSelect?.value || currentTemplateState.selectedFileType || 'docx';
    const canonicalId = canonicalIdInput?.value.trim() || null;
    const reportType = reportTypeSelect?.value || 'full';

    if (!templateName) {
        toast('请先选择一个模板', 'error');
        return;
    }

    const loadingEl = document.getElementById('render-loading');
    const resultEl = document.getElementById('render-result');

    if (loadingEl) loadingEl.classList.remove('hidden');
    if (resultEl) resultEl.classList.add('hidden');

    try {
        let result;

        if (canonicalId) {
            // Use asset data
            result = await apiCall('POST', '/api/templates/render-from-asset', {
                template_name: templateName,
                file_type: fileType,
                canonical_id: canonicalId,
                report_type: reportType,
                additional_placeholders: currentTemplateState.placeholderValues
            });
        } else {
            // Use manual placeholders only
            result = await apiCall('POST', '/api/templates/render', {
                template_name: templateName,
                file_type: fileType,
                placeholders: currentTemplateState.placeholderValues
            });
        }

        currentTemplateState.renderedReportId = result.report_id;

        if (resultEl) {
            const downloadLink = document.getElementById('render-download-link');
            if (downloadLink && result.report_id) {
                downloadLink.href = `/api/templates/download/${encodeURIComponent(result.report_id)}`;
            }
            resultEl.innerHTML = `
                <div class="success-message">
                    <i class="codicon codicon-pass"></i>
                    <span>报告渲染成功！</span>
                </div>
                <a id="render-download-link" href="/api/templates/download/${encodeURIComponent(result.report_id)}"
                   class="btn-primary" target="_blank">下载报告</a>
            `;
            resultEl.classList.remove('hidden');
        }
    } catch (e) {
        toast('渲染失败: ' + e.message, 'error');
    } finally {
        if (loadingEl) loadingEl.classList.add('hidden');
    }
}

async function downloadRenderedReport(reportId) {
    try {
        window.open(`/api/templates/download/${encodeURIComponent(reportId)}`, '_blank');
    } catch (e) {
        toast('下载失败: ' + e.message, 'error');
    }
}

async function savePlaceholderConfig() {
    const templateName = document.getElementById('configure-template-select')?.value;
    const fileType = document.getElementById('configure-type-select')?.value || 'docx';

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const config = {
        template_name: templateName,
        file_type: fileType,
        placeholders: currentTemplateState.placeholderConfigs || {}
    };

    try {
        await apiCall('POST', '/api/templates/config', config);
        toast('配置保存成功', 'success');
    } catch (e) {
        toast('保存配置失败: ' + e.message, 'error');
    }
}

async function exportYamlConfig() {
    const templateName = document.getElementById('configure-template-select')?.value;
    const fileType = document.getElementById('configure-type-select')?.value || 'docx';

    if (!templateName) {
        toast('请先选择模板', 'error');
        return;
    }

    const config = {
        name: templateName,
        description: `${templateName} 模板配置`,
        file_type: fileType,
        placeholders: currentTemplateState.placeholderConfigs || {}
    };

    // 转换为YAML格式
    const yaml = jsYaml.dump(config, { indent: 2 });

    // 下载文件
    const blob = new Blob([yaml], { type: 'application/x-yaml' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${templateName}_config.yaml`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    toast('YAML配置导出成功', 'success');
}

async function generateAiContent(placeholderName) {
    const config = currentTemplateState.placeholderConfigs?.[placeholderName] || {};
    const prompt = config.prompt;

    if (!prompt) {
        toast('该占位符没有配置生成提示词，请先在配置页面设置', 'error');
        return;
    }

    const btn = document.querySelector(`.render-placeholder-item:has([data-placeholder-name="${esc(placeholderName)}"]) .btn-ai-generate`);
    const input = document.querySelector(`.render-placeholder-item [data-placeholder-name="${esc(placeholderName)}"]`);

    if (btn) {
        btn.classList.add('loading');
        btn.disabled = true;
        btn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
    }

    try {
        // 构建完整的prompt
        const fullPrompt = `
请根据以下要求生成内容：
${prompt}

要求：
1. 内容符合券商研报的专业风格
2. 语言流畅，逻辑清晰
3. 不需要多余的解释和说明
4. 直接返回生成的内容即可
        `.trim();

        const result = await callLlmApi(fullPrompt);

        if (input && result) {
            input.value = result;
            updatePlaceholderValue(placeholderName, result);
            toast('生成成功', 'success');
        }
    } catch (e) {
        toast('生成失败: ' + e.message, 'error');
    } finally {
        if (btn) {
            btn.classList.remove('loading');
            btn.disabled = false;
            btn.innerHTML = '<i class="codicon codicon-hubot"></i> AI生成';
        }
    }
}

async function generateAllAiFields() {
    const configs = currentTemplateState.placeholderConfigs || {};
    const aiPlaceholders = Object.entries(configs)
        .filter(([name, config]) => config.type === 'rich_text' && config.prompt)
        .map(([name]) => name);

    if (aiPlaceholders.length === 0) {
        toast('没有需要生成的AI字段，请先配置占位符类型为"长文本/AI生成"并设置提示词', 'info');
        return;
    }

    const confirmBtn = confirm(`确定要生成所有 ${aiPlaceholders.length} 个AI字段吗？这可能需要一点时间。`);
    if (!confirmBtn) return;

    const btn = document.getElementById('btn-generate-all-ai');
    if (btn) {
        btn.classList.add('loading');
        btn.disabled = true;
        btn.innerHTML = '<i class="codicon codicon-loading spin"></i> 生成中...';
    }

    let successCount = 0;
    let failCount = 0;

    try {
        for (const name of aiPlaceholders) {
            try {
                await generateAiContent(name);
                successCount++;
                // 间隔一点时间避免API限流
                await new Promise(resolve => setTimeout(resolve, 1000));
            } catch (e) {
                console.error(`生成 ${name} 失败:`, e);
                failCount++;
            }
        }

        toast(`批量生成完成：成功 ${successCount} 个，失败 ${failCount} 个`, successCount > 0 ? 'success' : 'error');
    } finally {
        if (btn) {
            btn.classList.remove('loading');
            btn.disabled = false;
            btn.innerHTML = '<i class="codicon codicon-hubot"></i> 生成所有AI字段';
        }
    }
}

async function callLlmApi(prompt) {
    try {
        const response = await apiCall('POST', '/api/llm/generate', {
            prompt: prompt,
            temperature: 0.7,
            max_tokens: 2000
        });

        return response.content || response.result || response.text || '';
    } catch (e) {
        throw new Error(`LLM调用失败: ${e.message}`);
    }
}
