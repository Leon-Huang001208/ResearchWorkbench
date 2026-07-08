/* ============================================================
   AlphaFoundry — Application Entry Point
   Theme/i18n, Navigation, SSE, DOM init
   ============================================================ */

import { apiCall, toast, esc, getChartColors, applyChartDefaults } from './core.js';
import { loadDashboard, switchDashTab, switchMarketHeatmapScope, switchMarketSectorView, toggleMarketSectorMenu } from './dashboard.js?v=20260703theme1';
import { startCrawlFeedPolling, stopCrawlFeedPolling, startWorkersPolling, stopWorkersPolling, loadWorkersStatus } from './monitor.js?v=20260624b';
import { searchAssets, selectAsset, analyzeAssetByCode, analyzeAsset, handleAssetSearchKeydown, initAssetSearch, setKLineTimeRange, toggleMA, initKLineToolbar, switchAssetObserveMode, openThemeObservation } from './asset.js?v=20260703theme1';
import { switchSignalLabTab, loadSignalLab, initSignalLab } from './signal-lab.js';
import { loadMemoryPage, loadEpisodes, loadStrategies, loadFailures, loadEventSummary, initMemory } from './memory.js';
import { loadSignals, createSignal, validateSignal, promoteSignal, loadOutcomes, initSignals } from './signals.js';
import { loadReviewStats, loadReviewPending, approveItem, rejectItem, initReview } from './review.js';
import { loadTemplatesPage, loadTemplates, loadTemplatesList, selectTemplate, deleteTemplate, uploadTemplate, downloadTemplateFile, renderReportFromTemplate, downloadRenderedReport, savePlaceholderConfig, exportYamlConfig, generateAiContent, generateAllAiFields, discoverPlaceholders, createYamlConfig, openUploadModal, closeUploadModal, closeEditTemplateModal, openEditTemplateModal, saveTemplateEdit, toggleEditMode, saveTemplatesOrder, handleTemplatePointerDown, handleDragStart, handleDragOver, handleDrop, switchTemplatesTab, goBackToTemplates, clearPlaceholderData, updatePlaceholderConfig, updatePlaceholderValue, initTemplateDropZone, handleTemplateFileSelect, clearFileSelection, handleTemplateNameKeydown, saveTemplateInlineName } from './templates.js?v=20260629paragraphmodes1';
import { showSignalDetail, renderSignalDetail, renderAuditTrailTimeline, loadAuditTrail } from './signal-detail.js';
import { generateScenarios, renderScenarioResult } from './scenario.js';
import { generateEventSignal, loadEventSignals, renderEventSignalResult, renderTimingDecision } from './event-signal.js';
import { loadIndustryChain, loadPropagationPath, renderIndustryGraph, renderPropagationGraph } from './industry.js';
import { renderPipelineMonitor, stopPipelinePolling, handlePipelineSSEEvent } from './pipeline-monitor.js';
import { ingestText, renderIngestResult } from './ingest.js';
import { globalSearch, renderSearchResults, navigateToSignalDetail } from './search.js';
import { initNavigationCuration } from './navigation-curation.js';
import { initWindPanel } from './wind.js';
import { initFundsPanel } from './funds.js?v=20260625a';
import { initCommentaryCenter, selectCommentaryTemplate, loadCommentaryContext, generateCommentaryDraft, copyCommentaryDraft, switchCommentaryWorkspace } from './commentary.js?v=20260707logic1';

// ─── Window Exports (for HTML onclick handlers) ────────────────
window.apiCall = apiCall;
window.toast = toast;
window.esc = esc;
window.getChartColors = getChartColors;
window.applyChartDefaults = applyChartDefaults;

window.loadDashboard = loadDashboard;
window.switchDashTab = switchDashTab;
window.switchMarketHeatmapScope = switchMarketHeatmapScope;
window.switchMarketSectorView = switchMarketSectorView;
window.toggleMarketSectorMenu = toggleMarketSectorMenu;

window.searchAssets = searchAssets;
window.selectAsset = selectAsset;
window.analyzeAssetByCode = analyzeAssetByCode;
window.analyzeAsset = analyzeAsset;
window.handleAssetSearchKeydown = handleAssetSearchKeydown;
window.setKLineTimeRange = setKLineTimeRange;
window.toggleMA = toggleMA;
window.switchAssetObserveMode = switchAssetObserveMode;
window.openThemeObservation = openThemeObservation;

window.switchSignalLabTab = switchSignalLabTab;
window.loadSignalLab = loadSignalLab;

window.loadMemoryPage = loadMemoryPage;
window.loadEpisodes = loadEpisodes;
window.loadStrategies = loadStrategies;
window.loadFailures = loadFailures;
window.loadEventSummary = loadEventSummary;

window.loadSignals = loadSignals;
window.createSignal = createSignal;
window.validateSignal = validateSignal;
window.promoteSignal = promoteSignal;
window.loadOutcomes = loadOutcomes;

window.loadReviewStats = loadReviewStats;
window.loadReviewPending = loadReviewPending;
window.approveItem = approveItem;
window.rejectItem = rejectItem;

window.loadTemplatesPage = loadTemplatesPage;
window.loadTemplates = loadTemplates;
window.loadTemplatesList = loadTemplatesList;
window.selectTemplate = selectTemplate;
window.deleteTemplate = deleteTemplate;
window.uploadTemplate = uploadTemplate;
window.downloadTemplateFile = downloadTemplateFile;
window.renderReportFromTemplate = renderReportFromTemplate;
window.downloadRenderedReport = downloadRenderedReport;
window.savePlaceholderConfig = savePlaceholderConfig;
window.exportYamlConfig = exportYamlConfig;
window.generateAiContent = generateAiContent;
window.generateAllAiFields = generateAllAiFields;
window.discoverPlaceholders = discoverPlaceholders;
window.createYamlConfig = createYamlConfig;
window.openUploadModal = openUploadModal;
window.closeUploadModal = closeUploadModal;
window.openEditTemplateModal = openEditTemplateModal;
window.closeEditTemplateModal = closeEditTemplateModal;
window.saveTemplateEdit = saveTemplateEdit;
window.toggleEditMode = toggleEditMode;
window.saveTemplatesOrder = saveTemplatesOrder;
window.handleTemplatePointerDown = handleTemplatePointerDown;
window.handleDragStart = handleDragStart;
window.handleDragOver = handleDragOver;
window.handleDrop = handleDrop;
window.switchTemplatesTab = switchTemplatesTab;
window.goBackToTemplates = goBackToTemplates;
window.clearPlaceholderData = clearPlaceholderData;
window.updatePlaceholderConfig = updatePlaceholderConfig;
window.updatePlaceholderValue = updatePlaceholderValue;
window.initTemplateDropZone = initTemplateDropZone;
window.handleTemplateFileSelect = handleTemplateFileSelect;
window.clearFileSelection = clearFileSelection;
window.handleTemplateNameKeydown = handleTemplateNameKeydown;
window.saveTemplateInlineName = saveTemplateInlineName;

window.showSignalDetail = showSignalDetail;
window.renderSignalDetail = renderSignalDetail;
window.renderAuditTrailTimeline = renderAuditTrailTimeline;
window.loadAuditTrail = loadAuditTrail;

window.generateScenarios = generateScenarios;
window.generateEventSignal = generateEventSignal;
window.loadEventSignals = loadEventSignals;
window.renderTimingDecision = renderTimingDecision;
window.loadIndustryChain = loadIndustryChain;
window.loadPropagationPath = loadPropagationPath;
window.ingestText = ingestText;
window.globalSearch = globalSearch;
window.navigateToSignalDetail = navigateToSignalDetail;
window.initWindPanel = initWindPanel;
window.initFundsPanel = initFundsPanel;
window.initCommentaryCenter = initCommentaryCenter;
window.selectCommentaryTemplate = selectCommentaryTemplate;
window.loadCommentaryContext = loadCommentaryContext;
window.generateCommentaryDraft = generateCommentaryDraft;
window.copyCommentaryDraft = copyCommentaryDraft;
window.switchCommentaryWorkspace = switchCommentaryWorkspace;

// ─── Theme & i18n Init ───────────────────────────────────────
(function initTheme() {
    const desktopVisualVersion = '20260618-desktop-phase1';
    const savedTheme = localStorage.getItem('af-theme');
    if (localStorage.getItem('af-desktop-visual-version') !== desktopVisualVersion) {
        localStorage.setItem('af-theme', savedTheme || 'dark');
        localStorage.setItem('af-color-scheme', 'claude');
        localStorage.setItem('af-desktop-visual-version', desktopVisualVersion);
    }
    document.documentElement.setAttribute('data-theme', localStorage.getItem('af-theme') || 'dark');
})();

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('af-theme', theme);
    document.querySelectorAll('#settings-panel-theme .settings-opt').forEach(b => {
        b.classList.toggle('active', b.dataset.themeVal === theme);
    });
    try { applyChartDefaults(); } catch(e) {}
}
window.applyTheme = applyTheme;

function switchTheme(theme) { applyTheme(theme); }
window.switchTheme = switchTheme;

function switchLang(lang) {
    if (typeof I18N !== 'undefined') {
        I18N.setLang(lang);
        document.querySelectorAll('#settings-panel-language .settings-opt').forEach(b => {
            b.classList.toggle('active', b.dataset.lang === lang);
        });
        const sl = document.getElementById('status-lang-label');
        if (sl) sl.textContent = lang === 'zh' ? '中文' : 'EN';
    }
}
window.switchLang = switchLang;

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
window.applyColorScheme = applyColorScheme;

function switchColorScheme(scheme) { applyColorScheme(scheme); }
window.switchColorScheme = switchColorScheme;

applyTheme(document.documentElement.getAttribute('data-theme') || 'dark');
applyColorScheme(document.documentElement.getAttribute('data-color-scheme') || 'claude');
applyChartDefaults();

// ─── Chart Instances (for cleanup) ───────────────────────────
window.chartScenarioProb = null;

// ─── Navigation ──────────────────────────────────────────────
function navigateTo(section) {
    document.querySelectorAll('.activity-btn[data-section]').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.content-section').forEach(p => p.classList.remove('active'));
    document.querySelectorAll(`.activity-btn[data-section="${section}"]`).forEach(b => b.classList.add('active'));
    const sectionEl = document.getElementById(`section-${section}`);
    if (sectionEl) sectionEl.classList.add('active');
    localStorage.setItem('af-active-section', section);

    if (section === 'dashboard') {
        loadDashboard();
        startCrawlFeedPolling();
        startWorkersPolling();
    } else {
        stopCrawlFeedPolling();
        stopWorkersPolling();
    }
    if (section === 'signals') loadSignals();
    if (section === 'review') { loadReviewStats(); loadReviewPending(); }
    if (section === 'memory') loadMemoryPage();
    if (section === 'outcomes') loadOutcomes();
    if (section === 'signal-lab') loadSignalLab();
    if (section === 'templates') loadTemplatesPage();
    if (section === 'commentary') initCommentaryCenter();
    if (section === 'wind') initWindPanel();
    if (section === 'funds') initFundsPanel();
    if (section === 'pipeline-monitor') renderPipelineMonitor();
    else stopPipelinePolling();
}
window.navigateTo = navigateTo;

function getInitialSection() {
    const savedSection = localStorage.getItem('af-active-section');
    if (savedSection && document.getElementById(`section-${savedSection}`)) {
        return savedSection;
    }
    const activeButtonSection = document.querySelector('.activity-btn.active[data-section]')?.dataset.section;
    if (activeButtonSection && document.getElementById(`section-${activeButtonSection}`)) {
        return activeButtonSection;
    }
    return 'dashboard';
}

// ─── SSE Real-time Stream ────────────────────────────────────
let sseConnection = null;
function connectSSE() {
    if (sseConnection) { sseConnection.close(); }
    sseConnection = new EventSource('/api/realtime/stream');
    sseConnection.onopen = () => console.log('[SSE] Connected to real-time stream');
    sseConnection.addEventListener('document_parsed', (e) => {
        try {
            const data = JSON.parse(e.data);
            toast('New document parsed', 'info');
            loadDashboard();
        } catch (_) {}
    });
    sseConnection.addEventListener('event_created', (e) => {
        try {
            const data = JSON.parse(e.data);
            toast('New event created', 'info');
            loadDashboard();
        } catch (_) {}
    });
    sseConnection.addEventListener('queue_update', (e) => {
        try {
            const data = JSON.parse(e.data);
            if (data.processed > 0) loadDashboard();
        } catch (_) {}
    });
    // Pipeline events — forward to pipeline-monitor module
    const pipelineEventTypes = [
        'pipeline.closed_loop.started', 'pipeline.signal.generated',
        'pipeline.backtest.completed', 'pipeline.episode.recorded',
        'pipeline.pattern.learned', 'pipeline.closed_loop.completed',
        'pipeline.closed_loop.error',
        'knowledge.entity_resolved', 'knowledge.propagation_analyzed',
        'reasoning.completed', 'agent.swarm.completed', 'timing.evaluated',
    ];
    pipelineEventTypes.forEach(type => {
        sseConnection.addEventListener(type, (e) => {
            try {
                const payload = JSON.parse(e.data);
                handlePipelineSSEEvent({ type, payload });
            } catch (_) {}
        });
    });
}

// ─── Global Search Wrapper ───────────────────────────────────
let searchDebounceTimer = null;
window.globalSearchWrapped = async function(query) {
    if (!query || query.length < 2) {
        const dropdown = document.getElementById('search-results-dropdown');
        if (dropdown) dropdown.classList.add('hidden');
        return;
    }
    await globalSearch(query);
};

// ─── Status Bar ──────────────────────────────────────────────
async function updateStatusBar() {
    try {
        const data = await apiCall('GET', '/api/system/status-bar');
        const setText = (id, text) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        };
        setText('status-branch', data.git_branch || 'unknown');
        setText('status-errors', String(data.error_count ?? 0));
        setText('status-warnings', String(data.warning_count ?? 0));
        setText('status-db', data.db_type || 'PostgreSQL');
        setText('status-llm', data.llm_provider || 'Volcengine');
        setText('status-doc-count', String(data.doc_count ?? 0));
    } catch (e) { /* silent */ }
}

// ─── DOM Content Loaded ──────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.activity-btn[data-section]').forEach(btn => {
        btn.addEventListener('click', () => navigateTo(btn.dataset.section));
    });
    initNavigationCuration();

    document.querySelectorAll('.dash-tab').forEach(tab => {
        tab.addEventListener('click', () => switchDashTab(tab.dataset.dashTab));
    });

    document.getElementById('btn-settings')?.addEventListener('click', (e) => {
        e.stopPropagation();
        document.getElementById('settings-popover')?.classList.toggle('hidden');
        if (typeof I18N !== 'undefined') I18N.applyAll();
    });
    document.addEventListener('click', (e) => {
        const popover = document.getElementById('settings-popover');
        const btn = document.getElementById('btn-settings');
        if (popover && !popover.contains(e.target) && !btn?.contains(e.target)) {
            popover.classList.add('hidden');
        }
    });
    document.addEventListener('click', (e) => {
        const dropdown = document.getElementById('search-results-dropdown');
        const input = document.getElementById('global-search');
        if (dropdown && !dropdown.contains(e.target) && e.target !== input) {
            dropdown.classList.add('hidden');
        }
    });

    initAssetSearch();
    initKLineToolbar();

    const searchInput = document.getElementById('global-search');
    if (searchInput) {
        searchInput.addEventListener('input', (e) => {
            clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => window.globalSearch(e.target.value.trim()), 300);
        });
    }

    document.getElementById('btn-generate-scenarios')?.addEventListener('click', generateScenarios);
    document.getElementById('btn-generate-event-signal')?.addEventListener('click', generateEventSignal);
    document.getElementById('btn-load-industry')?.addEventListener('click', loadIndustryChain);

    initReview();
    initSignals();
    initMemory();
    document.getElementById('btn-ingest')?.addEventListener('click', ingestText);
    initSignalLab();

    connectSSE();
    navigateTo(getInitialSection());
    updateStatusBar();
    setInterval(updateStatusBar, 30000);
});
