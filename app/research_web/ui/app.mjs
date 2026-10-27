import { closedComposerMenu, openComposerMenu, composerMenuRows, composerMenuKey, composerSlashQuery, consumeComposerSlash, nextComposerFormats } from './composer-menu.mjs';
import { renderSessionMenu, projectMenuPosition, sessionMenuPosition } from './conversation-menus.mjs';
import { createConversationNavigation, renderProjectEditor } from './conversation-navigation.mjs';
import { captureQuestionForm, actionQuestion, collectQuestionGroup, questionStateKey } from './questionnaire.mjs';
import { createAPI, createController, prepareClawExampleDraft, parseRoute, legacyRouteTarget, isDataWorkspaceRoute, isRunning, safeLog, collectQuestionAnswers, reconcileSessionSummary, waitForDataProbe, waitForIntegrationBatch, waitForLocalIntegrationProbe, waitForLocalIntegrationVerification } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { createWarehousePanel } from './research-warehouse.mjs';
import { createDisclosureState } from './disclosures.mjs';
import { createAccountMenu } from './server/account-menu.mjs';
import { createPluginWorkspace } from './plugins-workspace.mjs';
import { createAccountWorkspace, renderAccountProfile } from './server/account-workspace.mjs';
import { canUploadToSession, createUploadHandler } from './uploads.mjs';
import { createSessionSearch } from './session-search.mjs';
import { downloadAnswer } from './answer-actions.mjs';
import { badge, empty, isClawWelcome, renderClawWelcome, renderConversation, copyResearchText, renderDeleteConfirm, renderHistory, renderPurgeConfirm, renderRename, renderDocumentEditor, documentTargets, documentEditValue, documentCreationPayload } from './views.mjs';
import { icon } from './icons.mjs';
import { renderReportWorkspace, reportHref } from './report-workspace.mjs';
import { createReportOperations } from './report-operations.mjs';
import { researchRecipes, renderResearchRecipes } from './research-report.mjs';
import { renderComposer, renderQuickSkills, removeTabbitMentionQuery, slashKey, skillMatches, tabbitKey, tabbitMentionQuery } from './composer.mjs';
import { focusSidebarControl, renderGlobalResults, renderResearchAttention, renderContextPanel, renderPrimaryRail, renderSidebar, renderTopbar } from './shell.mjs';

import { createCapabilityController, refreshProbedSourceDetail } from './capability-controller.mjs';
import { capabilityTabKey, reportWorkflowEligibility, renderCapabilityDetail, renderToolDetail, renderCreationArtifacts, creationArtifacts } from './capabilities.mjs';
import { capabilityWorkspaceKindKey, renderCapabilityPreviewDialog, renderCapabilityWorkspace } from './capability-workspace.mjs';
import { renderClawNavigation, renderClawProject, renderAutomationDrafts, automationDraftBody, renderClawConnections, clawNavigationCurrent, renderClawSchedules, renderClawRunCards, positionClawAutomationCards, clawCases, captureAutomationDraftEdits } from './claw-workspace.mjs';
import { mcpEnvironmentPayload, mcpInstallSelection, mcpMarketplaceTabKey, renderMCPServerDialog } from './mcp-marketplace.mjs';
import { renderDataCapabilityDetail, renderDataSourceDetail } from './data-catalog.mjs';
import { renderCapabilityEditor, renderCreationForm, renderCopyForm, readEditor, moveStepWithFeedback, newWorkflowStep } from './capability-editor.mjs';
import { readWorkbenchQuery, renderWorkbench } from './workbench.mjs';
import { readAssetObservation, updateAssetSummary, updateAssetTopic } from './asset-workspace.mjs';
import { assetHref, assetTopicKey, selectAssetObservation } from './asset-navigation.mjs';
import { createAssetWorkspaceController } from './asset-controller.mjs';
import { createAssetNewsController, renderAssetNews } from './asset-news.mjs';
import {createAssetMinuteK} from './asset-minute-k.mjs';
import { createAssetChartController } from './asset-chart.mjs';
import { createAssetIntraday } from './asset-intraday.mjs';
import { mountAssetSearch } from './asset-search.mjs';
import { mountCapitalFlow } from './asset-workspace.mjs';
import { projectAssetObservation } from './asset-projection.mjs';
import { renderOperations } from './operations.mjs';
import { createIntelController, renderIntel } from './intel.mjs';
import { createDiscoveryController, renderDiscovery } from './discovery.mjs';
import { createScenarioController, renderScenarioPanel, scenarioLaunchContext } from './scenarios.mjs';
import { createAssetResearchController, renderAssetResearch } from './asset-research.mjs';
import { createDossierController, renderDossiers, isDossierRoute } from './dossiers.mjs';

import { createMarketController, renderMarketPage } from './market.mjs';
import { createAihotController, renderAihot } from './aihot.mjs';

import { canUseReportWorkflows } from './weekly-production.mjs';
import { buildConfigurationPayload, confirmAutoProbeConsent, createExecutionEvidenceExpiry, createLocalIntegrationPollingGuard, createOfficeConsentQueue, invalidateLocalIntegrationSnapshot, nextLocalStatusExpiry, mergeIntegrationStatuses } from './connections.mjs';
import { createModelSettings } from './model-settings.mjs';
import { modelConfigurationPayload, syncModelForm, renderSettingsPage, resolveSettingsSection, settingsConnectionId, settingsRefreshCatalogs } from './settings.mjs';
import { renderFrameworks } from './frameworks.mjs';
import { renderEmbeddedBot } from './frameworks/embedded.mjs';
import { createEmbedBridge, createFrameworkLoadGuard, isNativeFramework } from './frameworks/embed-bridge.mjs';
const frameworkLoadGuard = createFrameworkLoadGuard();
const frameworkEmbedBridge = createEmbedBridge({ origin: globalThis.location?.origin || null, logger: safeLog });
let frameworkEmbedFrame = null;
frameworkEmbedBridge.setTheme(document.documentElement?.dataset?.theme || 'light');
if (globalThis.MutationObserver && document.documentElement) {
  new MutationObserver(() => { frameworkEmbedBridge.setTheme(document.documentElement.dataset.theme); mountAssetIndicators(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
}
window.addEventListener('message', event => {
  if (frameworkEmbedBridge.receive(event)) {
    updateFrameworkBotSlot();
  }
});
import { createHotController, renderHotWorkspace } from './hot-workspace.mjs';

const api = createAPI();
let modelSettingsPanel = null;
let warehousePanel = null;
const conversationNavigation = createConversationNavigation({ api, notify: () => render(), changed: () => loadCatalog(['sessions']) });
const clawWorkspace = { projects: [], detail: null, busy: false, error: '', newName: '', targetSession: '', renameEdits: new Map() };
const clawDraftEdits = new Map();
const root = document.querySelector('#app');
root.setAttribute?.('data-account-workspace-native', '1');
const accountWorkspace = createAccountWorkspace({root,user:globalThis.__RWB_ACCOUNT__?{...globalThis.__RWB_ACCOUNT__,id:globalThis.__RWB_USER_ID__}:null,logger:safeLog});
const accountMenu = createAccountMenu({ root, user: globalThis.__RWB_ACCOUNT__, logger: safeLog });
const pluginWorkspace = createPluginWorkspace({ root, user: globalThis.__RWB_ACCOUNT__ ? { ...globalThis.__RWB_ACCOUNT__, id: globalThis.__RWB_USER_ID__ } : null, logger: safeLog });
const disclosureState = createDisclosureState({ logger: safeLog });
const nativeSessionSearch = createSessionSearch({ search: (query, mode) => api.searchSessions(query, mode), notify: updateGlobalSearchResults, logger: safeLog });

function updateGlobalSearchResults() {
  const results = document.getElementById('global-search-results');
  if (!results) return;
  const focused = results.contains?.(document.activeElement) ? document.activeElement?.dataset?.globalResultKey : null;
  results.innerHTML = renderGlobalResults(globalSearch, catalog.sessions, searchableCapabilityList(), { native: state.route.page === 'claw' ? nativeSessionSearch.state : null });
  if (focused) ([...results.querySelectorAll('[data-global-result-key]')].find(item => item.dataset.globalResultKey === focused) || document.getElementById('global-search'))?.focus({ preventScroll: true });
}
const defaultCatalogNames = ['runtime', 'models', 'workspaces', 'sessions', 'capabilities', 'tools', 'reportWorkflows'];
const reportWorkflowsAllowed = canUseReportWorkflows(globalThis.__RWB_USER_ID__, globalThis.__RWB_ACCOUNT__);
if (!reportWorkflowsAllowed) defaultCatalogNames.splice(defaultCatalogNames.indexOf('reportWorkflows'), 1);
const catalog = { runtime: null, tabbit: null, integrations: { summary: {}, items: [], latest_batch: null }, localIntegrations: { categories: [], items: [], summary: {}, service: {} }, connections: { groups: [], sources: [], platform: {}, migration: {} }, models: [], sessions: [], deletedSessions: [], workspaces: [], capabilities: [], tools: [], reportWorkflows: [], automations: [], automationRuns: [], deliveryChannels: [], artifacts: [], dataCatalog: { summary: {}, capabilities: [], sources: [], bindings: [] }, errors: {}, modelFailures: [], pending: new Set(defaultCatalogNames) };
const catalogPendingCounts = new Map();
const catalogRequestGenerations = new Map();

function startCatalogRequest(name) {
  catalogPendingCounts.set(name, (catalogPendingCounts.get(name) || 0) + 1);
  catalog.pending.add(name);
  const generation = (catalogRequestGenerations.get(name) || 0) + 1;
  catalogRequestGenerations.set(name, generation);
  return generation;
}

function isLatestCatalogRequest(name, generation) {
  return catalogRequestGenerations.get(name) === generation;
}

function finishCatalogRequest(name) {
  const remaining = (catalogPendingCounts.get(name) || 1) - 1;
  if (remaining > 0) catalogPendingCounts.set(name, remaining);
  else {
    catalogPendingCounts.delete(name);
    catalog.pending.delete(name);
  }
}
let selectedWorkspace = ''; let selectedPreview = null; let historyFilter = ''; let success = ''; let sidebarOpen = false; let sidebarCollapsed = false; let clawSidebarView = 'sessions'; let contextOpen = false; let contextTab = 'activity'; let researchStage = null; let globalSearch = ''; let slashOpen = false;
let searchOpen = false; let slashIndex = 0; let contextCollapsed = true;
const answerFeedback = new Map(); let copiedTransient = '';
let tabbitOpen = false; let tabbitLoading = false; let tabbitIndex = 0; let tabbitCandidates = []; let tabbitRequest = 0;
let methodPickerOpen = false;
let composerMenu = closedComposerMenu();
const tabbitGrants = new Set();
let quickCategory = '';
let researchDraftRoute = { page: 'fingpt', sessionId: null };
let workbenchQueries = []; let workbenchContext = {}; let workbenchBusy = false;
let workbenchLoadGeneration = 0;
const workbenchDrafts = new Map();
let assetState = { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [] };
let etfState = { readiness: {}, runs: [], result: null };
let operationsRange = '7d';
let operationsData = { usage: null, tools: null, datahub: null, services: null, storage: null };
let reportWorkflowDetail = null; let reportWorkflowBusy = false;
let reportPageLoading = false; let reportPageError = ''; let reportReadGeneration = 0;
let automationFormOpen = false; let automationBusy = false;
let selectedConnectionConfiguration = null; let migrationOpen = false; let connectionDetailOpen = true; let connectionProbeBusy = false; let localIntegrationProbeBusy = false; let localVerificationTarget = ''; let localCategory = 'all'; let officeConsentConfirmation = ''; let localStatusExpiryTimer = null;
const executionEvidenceExpiry = createExecutionEvidenceExpiry({ getSources: () => catalog.connections.sources, isActive: () => Boolean(root.querySelector('[data-connection-workbench]')), onExpire: () => render() });
let frameworkState = { status: 'idle', catalog: null, data: null, slug: '', error: '' };
let frameworkBot = { open: false, mode: 'explain', sessionId: '', detail: null, draft: '', busy: false, error: '', errorCode: '' };
let closeFrameworkStream = () => {};
const workflowVersions = new Map();
let pageGeneration = 0;
const reportOperations = createReportOperations({
  api, scope: () => ({ generation: pageGeneration, page: state.route.page, projectId: state.route.reportProjectId }),
  detail: () => reportWorkflowDetail, setDetail: value => { reportWorkflowDetail = value; },
  allowed: () => reportWorkflowsAllowed, busy: () => reportWorkflowBusy,
  setBusy: value => { reportWorkflowBusy = value; render(); },
  feedback: value => { state.error = value.error || ''; success = value.success || ''; },
  navigate: async href => { history.pushState(null, '', href); await showRoute(); },
  refreshCatalog: () => loadCatalog(['reportWorkflows', 'sessions']),
});

let reportRefreshTimer = null;
function armReportRefresh(ticket) {
  clearTimeout(reportRefreshTimer);
  if (ticket !== pageGeneration || state.route.page !== 'reports' || state.route.reportTab !== 'production' || !reportWorkflowsAllowed || !reportWorkflowDetail?.runs?.some(run => !run.monitoring_disposition && ['queued', 'preparing_data', 'running', 'validating'].includes(run.status))) return;
  reportRefreshTimer = setTimeout(async () => {
    if (ticket !== pageGeneration) return;
    if (document.visibilityState !== 'hidden' && !reportWorkflowBusy && !reportPageLoading && !document.activeElement?.matches('input, select, textarea')) await loadReportPage(ticket);
    armReportRefresh(ticket);
  }, 10000);
}


let renameDraft = null;
let renameSession = null; let deleteSession = null; let purgeSession = null;
const conversationScrollPositions = new Map();
let sessionMenu = null; let sessionActionBusy = false; let sessionActionError = '';
let capabilityDialogReturnSelector = '';
let mcpCatalogGeneration = 0; let mcpDetailGeneration = 0; let mcpPublisherGeneration = 0; let mcpInstallGeneration = 0; let mcpDetailRequestIdentity = ''; let pendingMCPMarketTabFocus = '';
const emptyMCPInstallation = () => ({ target: '', preview: null, confirmationToken: '', installationId: '', installStatus: 'not_installed', probeStatus: 'not_run', enableStatus: 'disabled', authorizationStatus: 'not_authorized', capabilities: null, record: null, busy: '', error: '' });
let mcpMarketplaceState = { registries: [], installations: [], approvals: [], approvalBusy: '', runtimeAvailable: null, runtimeError: '', selectedRegistryId: '', query: '', page: null, detail: null, returnIdentity: null, loading: false, syncing: false, error: '', installation: emptyMCPInstallation(), publisher: { source: '', result: null, resultSource: '', error: '', busy: false } };
const questionDrafts = new Map();
const controller = createController({ api, onNavigate: (hash) => { history.pushState(null, '', hash); } });
const state = controller.state;
let sidebarControlFocused = false;
window.addEventListener('focusin', event => {
  sidebarControlFocused = Boolean(event.target?.matches?.('[data-toggle-sidebar], [data-collapse-sidebar]'));
});
window.addEventListener('focusout', event => {
  if (event.target?.matches?.('[data-toggle-sidebar], [data-collapse-sidebar]') && event.target.getClientRects().length) sidebarControlFocused = false;
});
window.matchMedia('(max-width: 1050px)').addEventListener?.('change', event => {
  const sidebarFocused = document.activeElement?.matches?.('[data-toggle-sidebar], [data-collapse-sidebar]') || (sidebarControlFocused && document.activeElement === document.body);
  sidebarOpen = false; contextOpen = false;
  safeLog('research_navigation_viewport_changed');
  render();
  if (sidebarFocused) focusSidebarControl(document, event.matches, !event.matches && !sidebarCollapsed);
});
const hotController = createHotController({api,onChange:()=>render(),isActive:()=>state.route.page==='intel'&&state.route.intelTab==='hot'||state.route.page==='settings'&&state.route.settingsSection==='hot'});
const intelController = createIntelController({ onChange: () => { if (state.route.page === 'intel') render(); } });
const scenarioController = createScenarioController({ api, changed: () => render(), onOpen: async result => { if (controller.openScenarioHandoff(result)) await showRoute(); } });
const assetResearch = createAssetResearchController({api,changed:()=>paintAssetResearch(),onResearch:context=>scenarioController.open(context)});
function paintAssetResearch() {
  const slot=root.querySelector('[data-asset-research-slot]'); if(!slot || !isAssetPage())return;
  const active=document.activeElement, focus=slot.contains(active)?active.id:null;
  const selection=focus && ['INPUT','TEXTAREA'].includes(active.tagName)?{start:active.selectionStart,end:active.selectionEnd}:null;
  slot.innerHTML=renderAssetResearch(assetResearch.state);
  if(focus){const replacement=document.getElementById(focus);replacement?.focus({preventScroll:true});if(selection?.start!==null && selection?.start!==undefined)replacement?.setSelectionRange?.(selection.start,selection.end);}
}
function syncAssetResearch() {
  if(!isAssetPage()){assetResearch.deactivate();return;}
  void assetResearch.activate(assetState.observation,state.route,assetState.observations);
  paintAssetResearch();
}
const discoveryController = createDiscoveryController({ api, onChange: () => { if (state.route.page === 'intel' && state.route.intelTab === 'discovery') render(); }, onNavigate: (mode, sessionId) => { if (sessionId && ['fingpt', 'claw'].includes(mode)) location.hash = `#/${mode}?session=${encodeURIComponent(sessionId)}`; } });
let dossierDraftOpening = 0;
let dossierDraftOpeningGeneration = 0;
const dossierController = createDossierController({ api, onChange: () => { if (isDossierRoute(state.route)) render(); }, onNavigate: hash => { location.hash = hash; }, onDraft: async result => {
  const openingToken = ++dossierDraftOpeningGeneration;
  dossierDraftOpening = openingToken;
  let prepared = false;
  try {
    history.pushState(null, '', `#/${result.mode}`);
    const ticket = pageGeneration + 1;
    await showRoute();
    if (openingToken !== dossierDraftOpening || ticket !== pageGeneration || state.route.page !== result.mode || state.route.sessionId || state.route.clawView) return;
    const previous = state.draft || '';
    if (!controller.setDossierDraft(previous.trim() && previous !== result.prompt ? `${previous}\n\n${result.prompt}` : result.prompt, result.context)) return;
    success = `已准备档案 v${result.context.revision} 的冻结研究草稿，请核对后发送。`;
    prepared = true;
  } catch (error) {
    if (openingToken === dossierDraftOpening) state.error = '档案研究草稿暂未准备完成，请返回档案核对后重试。';
    safeLog('dossier_draft_open_failed', { status: error.code || 'request_failed' });
  } finally {
    if (openingToken === dossierDraftOpening) {
      dossierDraftOpening = 0; render();
      if (prepared) document.getElementById('prompt')?.focus({ preventScroll: true });
    }
  }
} });
const marketController = createMarketController({ api, onChange: () => { if (state.route.page === 'market') render(); } });
const isAssetPage = () => ['assets', 'workbench'].includes(state.route.page) && state.route.section === 'assets' && state.route.assetView !== 'dossiers';
const assetIntraday = createAssetIntraday({api});
const assetChartOptions = {
  onIndicatorPreferencesChange: preferences => { void assetWorkspace.savePreferences(preferences.panels, assetState.preferences.chip_settings, preferences); },
  onPanelsChange: panels => { void assetWorkspace.savePreferences(panels); },
  onChipSettingsChange: settings => { void assetWorkspace.savePreferences(assetState.preferences.panels, settings); },
  onHistoryRequest: request => {
    if (request.action === 'cancel') return assetWorkspace.stopHistory();
    return assetWorkspace.startHistory(request.scope || 'recent', request.adjustment || 'none', request.action === 'retry' ? assetState.historyJob?.id : undefined, request.source, request.includeChipInputs === true);
  },
};
const assetChart = createAssetChartController(assetChartOptions);
const assetMinuteK = createAssetMinuteK({api,intraday:assetIntraday,chartOptions:assetChartOptions});
let assetCapitalFlow = null;
let assetSearch = null;
let assetTopicNavigation = 0;
const emptyAssetHistory = Object.freeze([]);
let configuredAssetHistory = null;
let configuredAssetSignature = '';
function assetTopicProps() { return { ...assetState, research:assetResearch.state, route: state.route, news: assetNews.state, busy: workbenchBusy }; }
function mountAssetTopicIndicators(page) {
  const observation = selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route);
  assetCapitalFlow?.dispose();
  assetCapitalFlow = mountCapitalFlow(page, projectAssetObservation(observation ? assetState.rows : {}, observation || {}));
}
function paintAssetTopic() {
  const page = root.querySelector('[data-asset-identity]');
  if (!updateAssetTopic(page, assetTopicProps())) return false;
  mountAssetTopicIndicators(page);
  return true;
}
function paintAssetWorkspace() {
  const page = root.querySelector('[data-asset-identity]');
  if (!updateAssetSummary(page, assetTopicProps()) || !paintAssetTopic()) return false;
  configureAssetTerminal();
  syncAssetResearch();
  assetIntraday.mount(page, selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route), String(globalThis.__RWB_USER_ID__ || 'single-user'));
  assetMinuteK.mount(page, selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route), String(globalThis.__RWB_USER_ID__ || 'single-user'), assetState.preferences);
  assetSearch?.update({ asset: state.route.asset || assetState.observation?.asset || '' });
  const notices = page.querySelector('[data-asset-workspace-notices]');
  if (notices) notices.insertAdjacentHTML('afterbegin', `${notice(state.error)}${notice(success, 'success')}`);
  return true;
}
function assetTerminalMetadata(observation = assetState.observation) {
  const dataset = observation?.blocks?.history?.dataset;
  const history = dataset?.asset_history;
  const historySource = history?.source || (history?.canonical_version === 'asset-history-1' ? 'tinysoft' : history?.canonical_version === 'asset-history-raw-2' ? 'unknown' : observation?.request_parameters?.section_sources?.history || observation?.request_parameters?.source || observation?.source || 'tinysoft');
  return { ...dataset, accountIdentity: String(globalThis.__RWB_USER_ID__ || 'single-user'), frequency: observation?.request_parameters?.frequency || 'daily', adjustment: dataset?.asset_history?.adjustment || observation?.request_parameters?.adjustment || 'qfq', assetIdentity: `${observation?.asset_type || state.route.assetType || 'stock'}:${observation?.asset || state.route.asset || ''}`, historyJob: assetState.historyJob, historySource, canLoadHistory: Boolean(observation?.id) && historySource !== 'unknown', asset: observation?.asset, name: assetState.rows.overview?.[0]?.name || assetState.rows.overview?.[0]?.['简称'], currentQuote: projectAssetObservation(assetState.rows, observation || {}).basic };
}
function configureAssetTerminal() {
  const observation = selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route);
  const key = `${observation?.asset_type || state.route.assetType}:${observation?.asset || state.route.asset}:${observation?.blocks?.history?.dataset?.dataset_id || ''}`;
  const rows = observation ? assetState.rows.history || emptyAssetHistory : emptyAssetHistory;
  const metadata = assetTerminalMetadata(observation);
  const signature = JSON.stringify({ key, accountIdentity: metadata.accountIdentity, dataset: observation?.blocks?.history?.dataset, frequency: metadata.frequency, adjustment: metadata.adjustment, historySource: metadata.historySource, historyJob: metadata.historyJob, panels: assetState.preferences?.panels, chipSettings: assetState.preferences?.chip_settings, favorites: assetState.preferences?.favorites, indicatorSettings: assetState.preferences?.indicator_settings });
  if (configuredAssetHistory === rows && configuredAssetSignature === signature) return;
  if (assetChart.configure(rows, key, metadata, assetState.preferences) !== false) { configuredAssetHistory = rows; configuredAssetSignature = signature; }
}
function setAssetMetricsDrawer(open, focus = true) {
  const panel = root.querySelector('.asset-wind-metrics'); const trigger = root.querySelector('[data-asset-metrics-toggle]');
  if (!panel || !trigger) return;
  panel.classList.toggle('is-open', open); trigger.setAttribute('aria-expanded', String(open));
  if (open) { panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-modal', 'true'); if (focus) panel.querySelector('[data-asset-metrics-close]')?.focus({ preventScroll: true }); }
  else { panel.removeAttribute('role'); panel.removeAttribute('aria-modal'); if (focus) trigger.focus({ preventScroll: true }); }
}
function mountAssetIndicators(keepTerminal = false) {
  if (!isAssetPage()) return;
  const page = root.querySelector('[data-asset-identity]');
  if (!page) return;
  try {
    configureAssetTerminal();
    if (!keepTerminal) assetChart.mount(page.querySelector('[data-asset-chart-slot]'));
    assetIntraday.mount(page, selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route), String(globalThis.__RWB_USER_ID__ || 'single-user'));
  assetMinuteK.mount(page, selectAssetObservation(assetState.observation ? [assetState.observation] : [], state.route), String(globalThis.__RWB_USER_ID__ || 'single-user'), assetState.preferences);
    mountAssetTopicIndicators(page);
  } catch (error) { safeLog('asset_indicators_mount_failed', { error: error.name }); }
}
const assetWorkspace = createAssetWorkspaceController({ api, onChange: () => { assetState = assetWorkspace.state; if (isAssetPage() && !paintAssetWorkspace()) render(); } });
assetState = assetWorkspace.state;
const assetNews = createAssetNewsController({ onChange: () => {
  if (!isAssetPage() || assetNews.state.asset !== state.route.asset || assetNews.state.view !== state.route.assetView) return;
  const slot = root.querySelector('[data-asset-news-slot]'); if (!slot) return;
  const active = document.activeElement; const focused = slot.contains(active);
  const selected = active?.dataset?.assetNewsSelect;
  const action = selected !== undefined ? `[data-asset-news-select="${selected}"]` : active?.hasAttribute?.('data-asset-news-more') ? '[data-asset-news-more]' : '[data-asset-news-refresh]';
  const scroll = slot.querySelector('.asset-news-list')?.scrollTop || 0;
  const previousRows = slot.querySelectorAll('[data-asset-news-select]').length;
  slot.innerHTML = renderAssetNews(assetNews.state);
  const list = slot.querySelector('.asset-news-list'); if (list) list.scrollTop = scroll;
  if (focused) (slot.querySelector(action) || slot.querySelector(`[data-asset-news-select="${previousRows}"]`) || slot.querySelector('[data-asset-news-refresh]'))?.focus({ preventScroll: true });
} });
window.addEventListener('blur', () => assetChart.cancel());
window.addEventListener('pointerup', () => assetChart.cancel());
window.addEventListener('pointercancel', () => assetChart.cancel());

const aihotController = createAihotController({ onChange: () => { if (state.route.page === 'aihot') render(); } });
const capabilityController = createCapabilityController({ api, onChange: () => render(), onCatalogChange: () => loadCatalog(['capabilities']) });
const capabilityState = capabilityController.state;
const localIntegrationPollingGuard = createLocalIntegrationPollingGuard(
  () => state.route.page === 'settings' && currentSettingsSection() === 'local',
);

const officeAutoPollingGuard = createLocalIntegrationPollingGuard(
  () => state.route.page === 'settings' && currentSettingsSection() === 'local',
);
const officeConsentQueue = createOfficeConsentQueue((id, consent) => api.setIntegrationConsent(id, consent));

function runtimeLabel() {
  if (catalog.pending.has('runtime')) return 'DSH 连接中';
  if (!catalog.runtime) return 'DSH 未连接';
  if (catalog.runtime.connected && catalog.runtime.credential_configured === false) return 'DSH 待授权';
  return catalog.runtime.connected ? 'DSH 已连接' : 'DSH 不可用';
}

function notice(message, kind = 'error') { return message ? `<div class="notice ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${e(message)}</div>` : ''; }

function forgetConfigurationSecrets(value) {
  if (!value || typeof value !== 'object') return;
  for (const key of Object.keys(value)) {
    if (['password', 'token', 'api_key', 'cj_key'].includes(key)) delete value[key];
    else forgetConfigurationSecrets(value[key]);
  }
}

function applyConnectionWorkspaceFilters(workbench) {
  if (!workbench) return;
  try {
    const query = String(workbench.querySelector('[data-connection-search]')?.value || '').trim().toLocaleLowerCase();
    const status = workbench.querySelector('[data-connection-status]')?.value || 'all';
    const group = workbench.dataset.activeGroup || 'professional';
    let visible = 0;
    workbench.querySelectorAll('[data-connection-card]').forEach((card) => {
      const matchesGroup = query ? true : card.dataset.connectionGroupName === group;
      const matchesStatus = status === 'all' || card.dataset.connectionStatusName === status;
      const matchesQuery = !query || String(card.dataset.connectionSearchText || '').includes(query);
      card.hidden = !(matchesGroup && matchesStatus && matchesQuery);
      if (!card.hidden) visible += 1;
    });
    const count = workbench.querySelector('[data-connection-result-count]');
    if (count) count.textContent = String(visible);
    const emptyState = workbench.querySelector('[data-connection-empty]');
    if (emptyState) emptyState.hidden = visible > 0;
    const searchScope = workbench.querySelector('[data-connection-search-scope]');
    if (searchScope) searchScope.hidden = !query;
    const grid = workbench.querySelector('#connection-source-grid');
    if (grid) grid.setAttribute('aria-labelledby', `connection-group-${group}`);
  } catch (error) {
    safeLog('connection_workspace_filter_failed', { status: error?.name || 'unknown' });
  }
}

function closeConnectionDrawer(workbench, { restoreFocus = true } = {}) {
  const drawer = workbench?.querySelector('[data-connection-drawer]');
  if (!drawer || drawer.hidden) return false;
  connectionDetailOpen = false;
  drawer.hidden = true;
  const selectedCard = workbench.querySelector('[data-connection-select][aria-pressed="true"]');
  selectedCard?.setAttribute('aria-expanded', 'false');
  if (restoreFocus) selectedCard?.focus?.({ preventScroll: true });
  return true;
}

function capabilityPreviewIsOpen() {
  return capabilityState.form !== 'manage' && Boolean(capabilityState.detail || capabilityState.tool || (capabilityState.dataDetail && capabilityState.dataDetailKind === 'capability'));
}

function focusCapabilityPreview() {
  document.querySelector('.capability-preview-dialog [data-cap-close]')?.focus?.({ preventScroll: true });
}

function closeCapabilityPreview({ restoreFocus = true } = {}) {
  if (!capabilityPreviewIsOpen()) return false;
  const selector = capabilityDialogReturnSelector;
  capabilityDialogReturnSelector = '';
  capabilityController.close();
  if (restoreFocus && selector) document.querySelector(selector)?.focus?.({ preventScroll: true });
  return true;
}

function focusMCPServerDialog() {
  document.querySelector('.mcp-server-dialog [data-mcp-detail-close]')?.focus?.({ preventScroll: true });
}

function currentMCPMarketRoute() {
  return state.route.page === 'skills' && capabilityState.kindFilter === 'tool' && capabilityState.view === 'market';
}

function findMCPServerTrigger(identity) {
  if (!identity) return null;
  return [...(document.querySelectorAll?.('[data-mcp-server-detail]') || [])].find(item => item.dataset.registryId === identity.registryId && item.dataset.serverName === identity.serverName && item.dataset.serverVersion === identity.version) || null;
}

function invalidateMCPDetailRequest() {
  mcpDetailGeneration += 1;
  mcpInstallGeneration += 1;
  mcpDetailRequestIdentity = '';
  mcpMarketplaceState.loading = false;
  mcpMarketplaceState.detail = null;
  mcpMarketplaceState.returnIdentity = null;
  mcpMarketplaceState.installation = emptyMCPInstallation();
}

function invalidateMCPRequests() {
  mcpCatalogGeneration += 1; mcpPublisherGeneration += 1;
  invalidateMCPDetailRequest();
  mcpMarketplaceState.loading = false; mcpMarketplaceState.syncing = false;
  mcpMarketplaceState.publisher.busy = false;
}

function closeMCPServerDialog({ restoreFocus = true } = {}) {
  if (!mcpMarketplaceState.detail) return false;
  const identity = mcpMarketplaceState.returnIdentity;
  mcpInstallGeneration += 1;
  mcpMarketplaceState.detail = null; mcpMarketplaceState.returnIdentity = null; mcpMarketplaceState.installation = emptyMCPInstallation(); render();
  if (restoreFocus && identity) {
    findMCPServerTrigger(identity)?.focus?.({ preventScroll: true });
  }
  return true;
}

function sendBlockReason() {
  if (dossierDraftOpening) return '正在准备档案研究草稿，请等待冻结上下文就绪后发送。';
  if (state.detail?.execution_restricted) return '此历史会话执行受限；保留可读记录，请新建研究。';
  if (state.busy || state.stopping || state.loading || (state.route.sessionId && !state.detail)) return '操作尚未结束；草稿已保留，未发送。';
  if (state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || state.detail.can_recheck_stop || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status))) return '上一任务与交付尚未确认结束；草稿已保留，未发送。';
  if (catalog.pending.has('runtime') || catalog.runtime?.connected !== true || catalog.runtime.credential_configured === false) return '运行时未就绪，请检查连接与授权；草稿已保留。';
  return '';
}

function retryBlockReason() {
  const blocked = sendBlockReason();
  if (blocked) return blocked;
  if (state.draft.trim() || state.attachments.length || state.tabbitTabs.length || state.skillId || state.capability || state.toolIds.length || state.methodIds.length || state.expectedFormats !== null) return '输入区已有未发送的草稿或选择；请先发送或清除后再重试历史问题，当前输入已保留。';
  return '';
}

function composer() {
  const disabled = dossierDraftOpening || state.busy || state.loading || Boolean(state.route.sessionId && !state.detail);
  const taskPending = state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || state.detail.can_recheck_stop || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status));
  const runtimePending = catalog.pending.has('runtime');
  const runtimeReady = !runtimePending && catalog.runtime?.connected === true && catalog.runtime?.credential_configured !== false;
  return `<button type="button" class="button" data-scenario-open>选择研究场景</button>` + renderComposer({ models: catalog.models, model: catalog.runtime?.model, modelEndpoint: catalog.runtime?.connection?.base_url, modelProvider: catalog.runtime?.provider, page: state.route.page, draft: state.draft, attachments: state.attachments, tabbitTabs: state.tabbitTabs, tabbitCandidates, tabbitOpen, tabbitLoading, tabbitIndex, sourceScope: state.sourceScope, researchDepth: state.researchDepth, researchMode: state.researchMode, researchAsOf: state.researchAsOf, expectedFormats: state.expectedFormats, skills: catalog.capabilities, skillId: state.skillId, disabled, busy: state.busy, stopping: state.stopping, taskPending, detail: state.detail, slashOpen, slashIndex, composerMenu, capability: state.capability, toolIds: state.toolIds, tools: catalog.tools, methods: catalog.capabilities.filter(item => item.kind === 'method'), methodIds: state.methodIds, methodPickerOpen, runtimeReady, runtimePending });
}

function landing() {
  const claw = state.route.page === 'claw';
  if (claw) return `<div class="landing claw-landing">${state.busy ? '<div class="claw-welcome-pending" role="status">正在连接会话…</div>' : state.error || state.streamError ? '<div class="claw-welcome-pending" aria-hidden="true"></div>' : renderClawWelcome()}<div class="claw-landing-editor">${composer()}</div></div>`;
  return `<div class="landing fingpt-landing"><div class="greeting"><h1>从一个问题，开始研究。</h1><p class="landing-subtitle">读懂资料，比较公司，探索行业。</p></div>${renderResearchRecipes({ busy: state.busy })}${composer()}${renderQuickSkills(catalog.capabilities, { page: state.route.page, category: quickCategory })}</div>`;
}

function researchPage() {
  if (state.loading) return `<div class="loading-state" role="status">正在读取会话…</div>`;
  if (state.route.sessionId && !state.detail) return `${empty('暂时无法读取这个会话', '检查连接后重试，输入内容仍会保留。')}<button class="button" data-reload-session>重新读取</button>`;
  if (!state.detail) return landing();
  const detail = state.detail;
  const cards = detail.mode === 'claw' ? positionClawAutomationCards(detail,clawDraftEdits,clawWorkspace.busy) : {entries:[],unpositionedDrafts:[],unpositionedRuns:[]};
  const welcomeBlocked = state.busy || state.stopping || Boolean(state.error || state.streamError);
  if (isClawWelcome(detail, { busy: welcomeBlocked, extraEntries: cards.entries }) && !cards.unpositionedDrafts.length && !cards.unpositionedRuns.length) return landing();
  const toolNames = Object.fromEntries((catalog.tools || []).map((tool) => [tool.id, tool.name]).filter(([id, name]) => typeof id === 'string' && typeof name === 'string'));
  const canvas = `<div id="messages" class="messages" aria-label="会话消息">${renderConversation(detail, questionDrafts, { busy: welcomeBlocked || Boolean(cards.unpositionedDrafts.length || cards.unpositionedRuns.length), toolNames, feedback: Object.fromEntries(answerFeedback), copied: copiedTransient, retryAllowed: !retryBlockReason(), extraEntries: cards.entries })}</div>`;
  const sourceLabels = { required: '能力必需', 'user-selected': '用户选择', recommended: '能力推荐', 'model-supplemented': '模型补选' };
  const methodSummary = (detail.methods || []).length ? `<p class="small muted" data-method-adoption>采用方法：${detail.methods.map(item => `${e(item.title || item.method_id)} · ${e(sourceLabels[item.source] || item.source)}`).join('；')}</p>` : '';
  const methodWarning = detail.method_trace_incomplete ? notice('部分推荐或模型补选方法缺少调用证据；本次结果已降级标记 method_trace_incomplete。', 'warning') : '';
  return `<div class="conversation-scroll" data-conversation-scroll="${e(detail.id)}"><header class="session-toolbar" aria-label="会话状态与资料"><div class="session-meta">${detail.model ? `<span>${e(detail.model)}</span>` : ''}</div><div class="button-row">${detail.mode !== 'claw' ? `<button class="button small" data-upgrade ${state.busy || isRunning(detail.status) ? 'disabled' : ''}>升级为 Claw ↗</button>` : ''}<button class="button small context-toggle" data-toggle-context aria-expanded="${window.matchMedia('(max-width: 1050px)').matches ? contextOpen : !contextCollapsed}">活动与文件</button></div></header>${notice(state.streamError, 'warning')}${renderCreationArtifacts(detail, state.busy || isRunning(detail.status))}${detail.capability ? `<p class="small muted">所选能力版本：${e(detail.capability.id)} · v${e(detail.capability.version)}（选择记录，不代表每个工具已执行）</p>` : ''}${methodSummary}${methodWarning}${renderResearchAttention(detail)}${canvas}${detail.mode === 'claw' ? (cards.unpositionedDrafts.length || cards.unpositionedRuns.length ? '<p class="muted small">以下日程记录缺少唯一原生调用位置，未推断其回答顺序。</p>' : '') + renderAutomationDrafts(cards.unpositionedDrafts,clawDraftEdits,clawWorkspace.busy) + (cards.unpositionedRuns.length ? renderClawRunCards(cards.unpositionedRuns) : '') : ''}</div><div class="composer-dock">${composer()}</div>`;
}

function settingsPage() {
  return renderSettingsPage({
    account: globalThis.__RWB_ACCOUNT__,
    route: state.route,
    runtime: catalog.runtime,
    tabbit: catalog.tabbit,
    models: catalog.models,
    runtimeLabel: runtimeLabel(),
    busy: state.busy || connectionProbeBusy || localIntegrationProbeBusy || Boolean(localVerificationTarget),
    modelFailures: catalog.modelFailures,
    connections: catalog.connections,
    localIntegrations: catalog.localIntegrations,
    integrations: catalog.integrations,
    localVerificationTarget,
    localCategory,
    officeConsentConfirmation,
    selectedConfiguration: selectedConnectionConfiguration,
    migrationOpen,
    connectionDetailOpen,
    hash: location.hash,
    hotHTML: renderHotWorkspace(hotController.state,{settings:true}),
  });
}

function currentSettingsSection() {
  return resolveSettingsSection(state.route, catalog.connections.sources, globalThis.__RWB_ACCOUNT__);
}

function currentSettingsConnectionId() {
  return settingsConnectionId(location.hash, catalog.connections.sources, currentSettingsSection());
}

function mainPage() {
  if (state.route.page === 'reports') return renderReportWorkspace({ items: catalog.reportWorkflows, detail: reportWorkflowDetail, route: state.route, allowed: reportWorkflowsAllowed, loading: reportPageLoading, error: reportPageError, busy: reportWorkflowBusy });
  if (isDossierRoute(state.route)) return renderDossiers(dossierController.state);
  if (state.route.page === 'market') return renderMarketPage(marketController.state, state.route);
  if (state.route.page === 'account') return renderAccountProfile(globalThis.__RWB_ACCOUNT__);
  if (state.route.page === 'claw') {
    return clawMainPage();
  }
  if (state.route.page === 'fingpt') return state.route.clawView === 'projects' ? renderClawProject(clawWorkspace, 'fingpt') : researchPage();
  if (state.route.page === 'settings') return settingsPage();
  if (isDataWorkspaceRoute(state.route)) return workbenchPage();
  if (state.route.page === 'frameworks') return renderFrameworks({ slug: state.route.frameworkSlug, anchor: state.route.frameworkTab, catalog: frameworkState.catalog, data: frameworkState.data, status: frameworkState.status, error: frameworkState.error, bot: { ...frameworkBot, bridgeReady: frameworkEmbedBridge.ready(state.route.frameworkSlug, frameworkState.data?.snapshot?.revision) } });
  if (state.route.page === 'operations') return operationsPage();
  if (state.route.page === 'intel') return state.route.intelTab === 'discovery' ? renderDiscovery(discoveryController.state) : state.route.intelTab === 'hot' ? renderHotWorkspace(hotController.state) : renderIntel(intelController.state);
  if (state.route.page === 'aihot') return renderAihot(aihotController.state);
  if (state.route.page === 'history') {
    const mode = state.route.historyMode;
    const view = state.route.historyView || 'active';
    const modeLabel = mode === 'claw' ? 'Claw' : mode === 'fingpt' ? 'FinGPT' : '';
    const modeQuery = mode ? `mode=${mode}` : '';
    const activeHref = `#/history${modeQuery ? `?${modeQuery}` : ''}`;
    const deletedHref = `#/history?${modeQuery ? `${modeQuery}&` : ''}view=deleted`;
    const sessions = view === 'deleted' ? catalog.deletedSessions : catalog.sessions;
    return `<header class="page-header"><div><div class="eyebrow">YOUR RESEARCH</div><h1>${modeLabel ? `${modeLabel} 研究历史` : '研究历史'}</h1><p class="muted">${view === 'deleted' ? '删除的会话保留 30 天，可恢复或立即永久删除。' : modeLabel ? `所有 ${modeLabel} 会话，随时回来继续。` : '所有 FinGPT 与 Claw 会话，随时回来继续。'}</p></div><button class="button" data-refresh>刷新</button></header><nav class="history-tabs" aria-label="研究历史视图"><a href="${activeHref}" class="${view === 'active' ? 'active' : ''}" ${view === 'active' ? 'aria-current="page"' : ''}>研究</a><a href="${deletedHref}" class="${view === 'deleted' ? 'active' : ''}" ${view === 'deleted' ? 'aria-current="page"' : ''}>已删除</a></nav><label class="search-box"><span aria-hidden="true">⌕</span><input id="history-search" type="search" placeholder="搜索会话标题…" value="${e(historyFilter)}" aria-label="搜索${modeLabel ? ` ${modeLabel}` : ''}研究历史"></label><div id="history-results">${renderHistory(sessions, historyFilter, mode, view)}</div>`;
  }
  return capabilityPage();
}

function clawMainPage() {
  const view = state.route.clawView || 'sessions';
  if (view === 'projects') return renderClawProject(clawWorkspace);
  if (view === 'skills') return renderClawConnections(catalog.capabilities, catalog.tools);
  if (view === 'plans') return renderClawSchedules(catalog.automations, catalog.automationRuns, automationBusy || catalog.pending.has('automations') || catalog.pending.has('automationRuns'), catalog.errors.automations || '') + (reportWorkflowsAllowed ? '<p><a class="text-button" href="#/reports">打开报告生产</a></p>' : '');
  return researchPage();
}

async function loadReportPage(ticket = pageGeneration) {
  const generation = ++reportReadGeneration;
  const projectId = state.route.reportProjectId;
  if (state.route.page !== 'reports' || !reportWorkflowsAllowed || state.route.reportInvalid) {
    reportWorkflowDetail = null; reportPageLoading = false; reportPageError = ''; return;
  }
  reportPageLoading = true; reportPageError = '';
  if (reportWorkflowDetail?.id !== projectId) reportWorkflowDetail = null;
  render();
  try {
    await loadCatalog(['reportWorkflows']);
    const detail = projectId ? await api.reportWorkflow(projectId) : null;
    if (ticket !== pageGeneration || generation !== reportReadGeneration || state.route.page !== 'reports' || state.route.reportProjectId !== projectId) return;
    reportWorkflowDetail = detail;
    reportPageError = catalog.errors.reportWorkflows || '';
  } catch (error) {
    if (ticket === pageGeneration && generation === reportReadGeneration) reportPageError = error.message || '报告项目读取失败。';
    safeLog('report_workspace_read_failed', { code: error.code || 'request_failed' });
  } finally {
    if (ticket === pageGeneration && generation === reportReadGeneration) { reportPageLoading = false; render(); }
  }
}

async function loadClawProjects() {
  const ticket = pageGeneration; const projectId = state.route.projectId || 'default';
  if (clawWorkspace.detail?.id !== projectId) clawWorkspace.targetSession = '';
  clawWorkspace.error = ''; clawWorkspace.detail = null; render();
  try {
    const mode = state.route.page;
    const projects = await api.projects(mode);
    const detail = await api.project(mode, projectId);
    if (ticket !== pageGeneration || !['claw', 'fingpt'].includes(state.route.page) || state.route.clawView !== 'projects') return;
    clawWorkspace.projects = projects.items; clawWorkspace.detail = detail;
    if (!detail.sessions.some(s => s.id === clawWorkspace.targetSession)) clawWorkspace.targetSession = '';
  } catch (error) {
    if (ticket !== pageGeneration) return;
    clawWorkspace.error = error.message;
    safeLog('claw_project_load_failed', { status: error.code || 'request_failed' });
  }
  render();
}

async function clawAction(action) {
  if (clawWorkspace.busy) return;
  clawWorkspace.busy = true; clawWorkspace.error = ''; state.error = ''; render();
  const ticket = pageGeneration;
  try { await action(); }
  catch (error) { if (ticket === pageGeneration) { clawWorkspace.error = error.message; state.error = error.message; } safeLog('claw_action_failed', { status: error.code || 'request_failed' }); }
  finally { clawWorkspace.busy = false; render(); }
}

function workbenchPage() {
  if(state.route.section==='hot')return renderHotWorkspace(hotController.state);
  return renderWorkbench({ section: state.route.section || 'assets', catalog: catalog.dataCatalog, queries: workbenchQueries, queryDraft: workbenchDrafts.get(state.route.section), busy: workbenchBusy, assetState: { ...assetState, research:assetResearch.state, route: state.route, news: assetNews.state, chart: assetChart.getState() }, etfState });
}

function operationsPage() {
  return renderOperations(operationsData, operationsRange);
}

function capabilityPage() {
  const cap = capabilityState;
  const messages = notice(cap.error) + notice(cap.success, 'success');
  if (cap.form === 'editor') return messages + renderCapabilityEditor({ draft: cap.editor, id: cap.editorId, items: catalog.capabilities, tools: catalog.tools, busy: cap.busy, announcement: cap.stepAnnouncement || '' });
  if (cap.form === 'conversation') return messages + renderCreationForm(cap.kind, cap.goal, state.busy);
  if (cap.form === 'copy') return messages + renderCopyForm(cap.detail, cap.copy, cap.busy);
  if (cap.form === 'manage' && cap.dataDetail) return messages + (cap.dataDetailKind === 'source' ? renderDataSourceDetail(cap.dataDetail, cap.busy) : renderDataCapabilityDetail(cap.dataDetail));
  if (cap.form === 'manage' && cap.tool) return messages + renderToolDetail(cap.tool);
  if (cap.form === 'manage' && cap.detail) return messages + renderCapabilityDetail(cap.detail, { busy: cap.busy, versions: cap.versions, versionDetail: cap.versionDetail, running: catalog.sessions.some(session => isRunning(session.status)) });
  const workspace = renderCapabilityWorkspace({
    capabilities: catalog.capabilities.filter(item => !item.metadata?.report_workflow), tools: catalog.tools, reportWorkflows: catalog.reportWorkflows,
    automations: catalog.automations, automationRuns: catalog.automationRuns, deliveryChannels: catalog.deliveryChannels, automationFormOpen,
    dataCatalog: catalog.dataCatalog, connections: catalog.connections, mcpMarketplace: mcpMarketplaceState, view: cap.view, kind: cap.kindFilter,
    source: cap.source, category: cap.category, status: cap.status, query: cap.query,
    dataMarket: cap.dataMarket, dataStatus: cap.dataStatus, dataAuth: cap.dataAuth, probe: cap.probe,
    busy: cap.busy || reportWorkflowBusy || automationBusy,
    error: catalog.errors.capabilities || catalog.errors.tools || catalog.errors.automations || catalog.errors.automationRuns || catalog.errors.dataCatalog || catalog.errors.connections || '',
  });
  return messages + workspace + renderCapabilityPreviewDialog({ detail: cap.detail, tool: cap.tool, dataDetail: cap.dataDetail, dataDetailKind: cap.dataDetailKind, capabilities: catalog.capabilities, busy: cap.busy }) + renderMCPServerDialog(mcpMarketplaceState.detail, { ...mcpMarketplaceState.installation, runtimeAvailable: mcpMarketplaceState.runtimeAvailable, currentSessionId: researchDraftRoute.sessionId });
}

function sidebar() {
  return renderSidebar({ page: state.route.page, clawView: state.route.clawView, sessionId: state.route.sessionId, sessions: catalog.sessions, workspaces: catalog.workspaces, selectedWorkspace, collapsed: sidebarCollapsed, mobileOpen: sidebarOpen, detail: state.detail, clawSidebarView, projects: clawWorkspace.projects, navigation: conversationNavigation.state(state.route.page), openMenuId: sessionMenu?.id });
}

function closeGlobalSearch() {
  searchOpen = false; globalSearch = ''; nativeSessionSearch.close(); render();
  document.querySelector(window.matchMedia('(max-width: 1050px)').matches ? '.topbar .menu-toggle' : '.primary-rail .search-trigger')?.focus({ preventScroll: true });
}

function closeProjectEditor() {
  const nav = conversationNavigation.state(state.route.page);
  if (!nav?.editor || nav.busy) return;
  const id = nav.editor.id; nav.editor = null; render();
  const trigger = id ? [...root.querySelectorAll('[data-nav-project-menu]')].find(node => node.dataset.navProjectMenu === id) : root.querySelector('[data-nav-project-create]');
  trigger?.focus({ preventScroll: true });
}

function sessionActionsLayer() {
  const menuSession = sessionMenu ? catalog.sessions.find(item => item.id === sessionMenu.id) : null;
  const menu = menuSession ? renderSessionMenu({ session: menuSession, position: sessionMenu, navigation: conversationNavigation.state(menuSession.mode), move: sessionMenu.move || null }) : '';
  const dialog = renameSession
    ? renderRename(renameDraft || '', sessionActionError, sessionActionBusy)
    : deleteSession
      ? renderDeleteConfirm(deleteSession, sessionActionError, sessionActionBusy)
      : purgeSession
        ? renderPurgeConfirm(purgeSession, sessionActionError, sessionActionBusy)
        : '';
  return menu + dialog + renderProjectEditor(conversationNavigation.state(state.route.page));
}

function primaryRail() {
  const narrow = window.matchMedia('(max-width: 1050px)').matches;
  return renderPrimaryRail({
    page: state.route.page,
    section: state.route.section,
    secondaryOpen: narrow ? sidebarOpen : !sidebarCollapsed,
    account: globalThis.__RWB_ACCOUNT__,
  });
}

function contextPanel() {
  return renderContextPanel({ detail: state.detail, selectedTab: contextTab, researchStage, mobileOpen: contextOpen, selectedPreview, busy: state.busy, workflow: state.detail?.capability ? workflowVersions.get(`${state.detail.capability.id}:${state.detail.capability.version}`) : null });
}

let projectMenuOpenTimer = null;
let projectMenuCloseTimer = null;
function cancelProjectMenuTimers() { clearTimeout(projectMenuOpenTimer); clearTimeout(projectMenuCloseTimer); }
function paintSessionMenu({ focusProjects = false, focusParent = false } = {}) {
  const old = root.querySelector('.session-action-menu');
  const session = catalog.sessions.find(row => row.id === sessionMenu?.id);
  if (!old || !session || !sessionMenu) return;
  const active = document.activeElement; const hadFocus = old.contains(active);
  const identity = Object.entries(active?.dataset || {});
  const holder = document.createElement('div');
  holder.innerHTML = renderSessionMenu({ session, position: sessionMenu, navigation: conversationNavigation.state(session.mode), move: sessionMenu.move || null });
  old.replaceWith(holder.firstElementChild);
  const menu = root.querySelector('.session-action-menu');
  if (focusProjects) menu.querySelector('.session-project-menu [role="menuitemradio"]')?.focus({ preventScroll: true });
  else if (focusParent) menu.querySelector('[data-nav-move-menu]')?.focus({ preventScroll: true });
  else if (hadFocus) ([...menu.querySelectorAll('button,a')].find(node => identity.length && identity.every(([key, value]) => node.dataset[key] === value)) || menu.querySelector('[data-nav-move-menu]'))?.focus?.({ preventScroll: true });
}
function openProjectMenu(button, focusProjects = false) {
  if (!sessionMenu || sessionMenu.id !== button.dataset.navMoveMenu || button.disabled) return;
  cancelProjectMenuTimers();
  const rect = button.getBoundingClientRect(); const owner = button.closest('.session-action-menu')?.getBoundingClientRect() || rect;
  sessionMenu.move = projectMenuPosition({ left: owner.left, right: owner.right, top: rect.top }, { width: window.innerWidth, height: window.innerHeight });
  paintSessionMenu({ focusProjects });
}
function deferProjectMenuClose() {
  clearTimeout(projectMenuCloseTimer); const id = sessionMenu?.id;
  projectMenuCloseTimer = setTimeout(() => { if (sessionMenu?.id === id && sessionMenu.move) { sessionMenu.move = null; paintSessionMenu(); } }, 220);
}
root.addEventListener('pointerover', event => {
  if (event.pointerType !== 'mouse') return;
  const child = event.target.closest?.('.session-project-menu');
  if (child) { cancelProjectMenuTimers(); return; }
  const button = event.target.closest?.('[data-nav-move-menu]');
  if (button && sessionMenu?.id === button.dataset.navMoveMenu && !button.disabled) {
    clearTimeout(projectMenuCloseTimer);
    if (!sessionMenu.move) { clearTimeout(projectMenuOpenTimer); const id = sessionMenu.id; projectMenuOpenTimer = setTimeout(() => { if (sessionMenu?.id === id && button.isConnected) openProjectMenu(button); }, 120); }
  } else if (event.target.closest?.('.session-action-menu')) { clearTimeout(projectMenuOpenTimer); if (sessionMenu?.move) deferProjectMenuClose(); }
});
root.addEventListener('pointerout', event => {
  if (event.pointerType !== 'mouse') return;
  const menu = event.target.closest?.('.session-action-menu');
  if (menu && !menu.contains(event.relatedTarget)) { clearTimeout(projectMenuOpenTimer); if (sessionMenu?.move) deferProjectMenuClose(); }
});

let documentEditor = null;
let composingInput = null;
let renderAfterComposition = false;

function searchableCapabilityList() {
  return [...catalog.capabilities, ...catalog.tools.map(item => ({ ...item, kind: 'tool' })), ...catalog.reportWorkflows.map(item => ({ ...item, kind: 'report-workflow' })), ...(catalog.dataCatalog.capabilities || []).map(item => ({ ...item, kind: 'data' }))];
}

function render() {
  if (composingInput?.isConnected !== false && composingInput) { renderAfterComposition = true; return; }
  if (assetTopicNavigation === pageGeneration && isAssetPage() && paintAssetWorkspace()) return;
  accountWorkspace.captureFocus();
  if (!document.hidden && state.route.sessionId === state.detail?.id) conversationNavigation.markSeen(state.detail);
  // Keep the user's own dirty DOM form through unrelated catalog renders.
  // Secrets never enter application state or a server-provided refill.
  const modelForm = root.querySelector('#settings-form[data-dirty]:not(.mp-form)');
  const dirtyHotForms=[...root.querySelectorAll('[data-hot-form][data-hot-dirty]')];
  const documentForm = root.querySelector('#document-edit-form');
  const assetPage = root.querySelector('[data-asset-identity]');
  const assetIdentity = `${state.route.assetType || assetState.observation?.asset_type || 'stock'}:${state.route.asset || assetState.observation?.asset || ''}`;
  const keepAssetForms = isAssetPage() && assetPage?.dataset.assetIdentity === assetIdentity;
  const persistentAssetTerminal = keepAssetForms ? assetPage.querySelector('[data-asset-chart-slot]') : null;
  const assetFormSelectors = ['[data-asset-select]', '[data-asset-observation]', '[data-asset-note]', '[data-asset-alert]', '[data-watchlist-item]', '[data-asset-watchlist-create]'];
  const assetForms = keepAssetForms ? assetFormSelectors.map(selector => [selector, assetPage.querySelector(selector)]).filter(([, node]) => node) : [];
  const assetFocus = keepAssetForms && assetForms.some(([, form]) => form.contains(document.activeElement)) ? document.activeElement : null;
  const assetMetricsOpen = keepAssetForms && assetPage.querySelector('.asset-wind-metrics')?.classList.contains('is-open');
  const assetDetails = keepAssetForms ? ['.asset-list-drawer', '.asset-personal-details', '.asset-source-summary', '.asset-identity-switch', '.asset-research-menu', ...(assetPage.dataset.assetView === (state.route.assetView || 'overview') ? ['.asset-chart-details', ...(assetPage.dataset.observationId ? ['.asset-query-controls'] : [])] : [])].map(selector => [selector, assetPage.querySelector(selector)?.open]) : [];
  const active = document.activeElement; const focusId = active?.id;
  const modelPanelFocus = modelSettingsPanel?.element.contains(active) ? {node:active,action:active.dataset?.mpAction,profile:active.dataset?.profile} : null;
  const activeQuestion = active?.closest?.('[data-question-form]');
  const questionFocus = activeQuestion ? { session: activeQuestion.dataset.qSession, id: activeQuestion.dataset.questionForm, index: activeQuestion.dataset.qIndex, legend: active.matches('legend'), name: active.name, value: active.value } : null;
  const focusedSearchResult = active?.dataset?.globalResultKey;
  disclosureState.capture(root, active);
  const selection = active && ['TEXTAREA', 'INPUT'].includes(active.tagName) && active.type !== 'password' ? { start: active.selectionStart, end: active.selectionEnd } : null;
  const mainScroll = document.querySelector('#main')?.scrollTop || 0;
  const aihotArchiveScroll = root.querySelector('.aihot-archive-scroll')?.scrollTop || 0;
  const conversationScroller = root.querySelector('[data-conversation-scroll]');
  if (conversationScroller) conversationScrollPositions.set(conversationScroller.dataset.conversationScroll, conversationScroller.scrollTop);
  const navigationList = root.querySelector('.nav-scroll');
  const renderedMode = root.querySelector('[data-nav-mode]')?.dataset.navMode;
  if (navigationList?.clientHeight > 0 && conversationNavigation.state(renderedMode)) conversationNavigation.state(renderedMode).scrollTop = navigationList.scrollTop;
  const research = ['fingpt', 'claw'].includes(state.route.page);
  const hasSecondary = research && !sidebarCollapsed;
  const hasContext = research && Boolean(state.detail) && !contextCollapsed;
  const searchableCapabilities = searchableCapabilityList();
  const visibleErrors = Object.entries(catalog.errors).filter(([name]) => {
    if (name === 'artifacts') return false;
    if (name === 'assetWorkspace') return state.route.page === 'assets' && state.route.section === 'assets';
    if (name === 'etfPaper') return state.route.page === 'simulation';
    if (name === 'workbenchQueries') return isDataWorkspaceRoute(state.route) && !['assets', 'etf-paper'].includes(state.route.section);
    return true;
  });
  assetSearch?.dispose(); assetSearch = null;
  if (!persistentAssetTerminal) { assetMinuteK.dispose(); assetIntraday.dispose(); assetChart.dispose(); }
  assetCapitalFlow?.dispose(); assetCapitalFlow = null;
  root.innerHTML = `<div class="app-shell ${state.route.page === 'claw' ? 'claw-shell' : ''} ${hasContext ? '' : 'wide-page'} ${hasSecondary ? 'has-secondary' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${sidebarOpen ? 'navigation-open' : ''} ${hasContext ? 'context-open' : ''}">${renderTopbar({ page: state.route.page, section: state.route.section, frameworkSlug: state.route.frameworkSlug, settingsSection: state.route.page === 'settings' ? currentSettingsSection() : '', detail: state.detail, runtimeLabel: runtimeLabel(), runtime: catalog.runtime, models: catalog.models, busy: state.busy, search: globalSearch, sessions: catalog.sessions, skills: searchableCapabilities, searchOpen, nativeSearch: state.route.page === 'claw' ? nativeSessionSearch.state : null })}<div class="navigation-column">${primaryRail()}${sidebar()}</div><main id="main" tabindex="-1"><div class="page-content">${notice(state.error)}${visibleErrors.map(([name, error]) => notice(`${({ runtime: '运行时', models: '模型目录', workspaces: '工作空间', sessions: '会话历史', deletedSessions: '已删除会话', capabilities: '能力目录', tools: '工具目录', reportWorkflows: '报告 Workflow', automations: '运行计划', automationRuns: 'Automation 运行', deliveryChannels: '交付渠道', dataCatalog: '数据目录', connections: '连接中心', localIntegrations: '本机集成诊断', connectionConfiguration: '来源配置', migration: '旧配置迁移' })[name] || name}：${error}`)).join('')}${notice(success, 'success')}${mainPage()}</div></main>${hasContext || contextOpen ? contextPanel() : ''}</div>${sidebarOpen || contextOpen ? '<button class="mobile-backdrop" data-close-drawers aria-label="关闭面板"></button>' : ''}${sessionActionsLayer()}${renderScenarioPanel(scenarioController.state)}${documentEditor?.sessionId === state.detail?.id ? renderDocumentEditor(documentEditor) : ""}`;
  syncAssetResearch();
  root.querySelector('.app-shell').inert = scenarioController.state.open;
  if (scenarioController.state.open && !document.activeElement?.closest?.('.scenario-panel')) root.querySelector('#scenario-query')?.focus({ preventScroll: true });
  const newFrameworkFrame = root.querySelector('iframe[data-native-framework]');
  executionEvidenceExpiry.sync();
  frameworkEmbedFrame = newFrameworkFrame;
  frameworkEmbedBridge.clear();
  if (newFrameworkFrame) {
    try { frameworkEmbedBridge.bind(newFrameworkFrame, frameworkState.data, crypto.randomUUID()); }
    catch (error) { safeLog('framework_embed_bind_failed', { error: error.name }); }
  }
  updateFrameworkBotSlot();
  const freshAihotArchive = root.querySelector('.aihot-archive-scroll');
  if (freshAihotArchive) freshAihotArchive.scrollTop = aihotArchiveScroll;
  window.ResearchWebTheme?.syncControls();
  const freshDocumentForm = root.querySelector('#document-edit-form');
  if (persistentAssetTerminal) root.querySelector('[data-asset-chart-slot]')?.replaceWith(persistentAssetTerminal);
  for (const [selector, form] of assetForms) root.querySelector(selector)?.replaceWith(form);
  for (const [selector, open] of assetDetails) { const details = root.querySelector(selector); if (details && open !== undefined) details.open = open; }
  if (assetMetricsOpen) setAssetMetricsDrawer(true, false);
  if (assetFocus?.isConnected) assetFocus.focus({ preventScroll: true });
  if (documentForm && freshDocumentForm && documentForm.dataset.documentBusy !== "true" && !documentEditor?.busy && documentForm.dataset.documentRevision === freshDocumentForm.dataset.documentRevision) freshDocumentForm.replaceWith(documentForm);
  const modelPanelMount = root.querySelector('[data-model-profiles-root]');
  const warehouseMount = root.querySelector('[data-research-warehouse-root]');
  if (warehouseMount) {
    if (!warehousePanel) warehousePanel = createWarehousePanel({api,logger:safeLog,onValidated:()=>loadCatalog(['connections','dataCatalog'])});
    warehouseMount.replaceWith(warehousePanel.element);
  } else if (warehousePanel) { warehousePanel.dispose(); warehousePanel = null; }
  if (modelPanelMount) {
    const props = {runtime:catalog.runtime || {},models:catalog.models,busy:state.busy};
    if (!modelSettingsPanel) modelSettingsPanel = createModelSettings({api,...props,changed:()=>loadCatalog(['runtime','models']),logger:safeLog});
    modelPanelMount.replaceWith(modelSettingsPanel.element);
    modelSettingsPanel.update(props);
  } else if (modelSettingsPanel) { modelSettingsPanel.dispose(); modelSettingsPanel = null; }
  const freshModelForm = root.querySelector('#settings-form');
  if (modelForm && freshModelForm) {
    const disabled = freshModelForm.querySelector('button[type="submit"]').disabled;
    modelForm.querySelector('button[type="submit"]').disabled = disabled;
    const select = modelForm.querySelector('#settings-model');
    const selected = select.value;
    const freshSelect = freshModelForm.querySelector('#settings-model');
    select.innerHTML = freshSelect.innerHTML;
    select.disabled = freshSelect.disabled;
    if ([...select.options].some(option => option.value === selected)) select.value = selected;
    const provider = modelForm.querySelector('#provider');
    const selectedProvider = provider.value;
    provider.innerHTML = freshModelForm.querySelector('#provider').innerHTML;
    if ([...provider.options].some(option => option.value === selectedProvider)) provider.value = selectedProvider;
    freshModelForm.replaceWith(modelForm);
    syncModelForm(modelForm, { busy: state.busy });
  }
  for(const form of dirtyHotForms){
    const fresh=[...root.querySelectorAll('[data-hot-form]')].find(item=>item.dataset.hotFormKey===form.dataset.hotFormKey);
    if(fresh){const blocked=form.dataset.hotForm==='filters'?hotController.state.loading:hotController.state.busy||hotController.state.pending;form.querySelectorAll('button').forEach(button=>{button.disabled=Boolean(blocked);});fresh.replaceWith(form);}
  }
  document.querySelector('#main').scrollTop = mainScroll;
  const freshConversationScroller = root.querySelector('[data-conversation-scroll]');
  if (freshConversationScroller) freshConversationScroller.scrollTop = conversationScrollPositions.get(freshConversationScroller.dataset.conversationScroll) || 0;
  if (root.querySelector('.nav-scroll')) root.querySelector('.nav-scroll').scrollTop = conversationNavigation.state(state.route.page)?.scrollTop || 0;
  disclosureState.restore(root);
  accountMenu.sync();
  accountWorkspace.sync();
  pluginWorkspace.sync();
  if (focusId) {
    const replacement = document.getElementById(focusId);
    if (replacement && !replacement.disabled) { replacement.focus({ preventScroll: true }); if (selection && selection.start !== null) replacement.setSelectionRange?.(selection.start, selection.end); }
  }
  else if (modelPanelFocus && modelSettingsPanel) {
    const replacement = modelPanelFocus.node.isConnected ? modelPanelFocus.node : [...modelSettingsPanel.element.querySelectorAll('[data-mp-action]')].find(node=>node.dataset.mpAction===modelPanelFocus.action&&node.dataset.profile===modelPanelFocus.profile);
    if(replacement && !replacement.disabled) replacement.focus({preventScroll:true});
  }
  else if (focusedSearchResult && searchOpen) {
    ([...root.querySelectorAll('[data-global-result-key]')].find(item => item.dataset.globalResultKey === focusedSearchResult) || document.getElementById('global-search'))?.focus({ preventScroll: true });
  }
  else if (questionFocus) {
    const form = [...root.querySelectorAll('[data-question-form]')].find(item => item.dataset.qSession === questionFocus.session && item.dataset.questionForm === questionFocus.id && item.dataset.qIndex === questionFocus.index);
    const replacement = questionFocus.legend ? form?.querySelector('legend') : [...(form?.querySelectorAll('input') || [])].find(item => item.name === questionFocus.name && item.value === questionFocus.value);
    replacement?.focus({ preventScroll: true });
  }
  if (state.busy) root.querySelectorAll('[data-approval], [data-upload], .question-form button, #rename-form button').forEach((button) => { button.disabled = true; });
  const projectDialog = root.querySelector('.nav-project-dialog');
  if (projectDialog) {
    for (const sibling of root.children) if (!sibling.contains(projectDialog)) sibling.inert = true;
    if (!projectDialog.contains(document.activeElement) || document.activeElement?.disabled) (projectDialog.querySelector('input:not(:disabled)') || projectDialog).focus({ preventScroll: true });
  }
  const discoveryDialog = root.querySelector('.discovery-page .d-drawer');
  if (discoveryDialog) {
    for (const background of root.querySelectorAll('.discovery-page > :not(.d-drawer-backdrop), .navigation-column, .topbar')) background.inert = true;
    if (!discoveryDialog.contains(document.activeElement) || document.activeElement?.disabled) root.querySelector('#discovery-drawer-title')?.focus({ preventScroll: true });
  }
  mountAssetIndicators(Boolean(persistentAssetTerminal));
  const assetSearchSlot = root.querySelector('[data-asset-search-slot]');
  if (assetSearchSlot) assetSearch = mountAssetSearch(assetSearchSlot, { api, account: () => globalThis.__RWB_USER_ID__ || 'local', asset: state.route.asset || assetState.observation?.asset || '', onSelect: item => { location.hash = assetHref(item.asset, 'stock', state.route.assetView || 'overview'); } });
  document.title = `${state.detail?.title || ({ fingpt: 'FinGPT', claw: 'Claw', reports: '报告生产', market: '全市场概览', assets: '资产观察', simulation: '策略模拟', frameworks: '研究框架', history: '研究历史', skills: '能力中心', operations: '运行与用量', intel: '研究情报', aihot: 'AI 资讯', settings: '设置', account: '账号资料' })[state.route.page] || '资产观察'} · Research Workbench`;
}

async function loadCatalog(names = defaultCatalogNames) {
  names = names.filter(name => name !== 'reportWorkflows' || reportWorkflowsAllowed);
  const requests = names.map(name => ({ name, generation: startCatalogRequest(name) }));
  render();
  await Promise.all(requests.map(async ({ name, generation }) => {
    try {
      const data = name === 'deletedSessions' ? await api.sessions('deleted') : name === 'tabbit' ? await api.tabbitStatus() : name === 'integrations' ? await api.integrations(state.route.page === 'settings' && currentSettingsSection() === 'data' ? 'data' : 'all') : await api[name]();
      if (!isLatestCatalogRequest(name, generation)) return;
      if (name === 'runtime') catalog.runtime = data;
      else if (name === 'tabbit') catalog.tabbit = data;
      else if (name === 'models') { catalog.models = data.groups || []; catalog.modelFailures = data.failures || []; }
      else if (name === 'dataCatalog') catalog.dataCatalog = {
        summary: data?.summary || {},
        capabilities: Array.isArray(data?.capabilities) ? data.capabilities : [],
        sources: Array.isArray(data?.sources) ? data.sources : [],
        bindings: Array.isArray(data?.bindings) ? data.bindings : [],
      };
      else if (name === 'connections') catalog.connections = {
        groups: Array.isArray(data?.groups) ? data.groups : [],
        sources: Array.isArray(data?.sources) ? data.sources : Array.isArray(data?.items) ? data.items : [],
        platform: data?.platform || {},
        migration: data?.migration || {},
      };
      else if (name === 'localIntegrations') catalog.localIntegrations = {
        platform: data?.platform || 'unknown',
        service: data?.service || {},
        summary: data?.summary || {},
        categories: Array.isArray(data?.categories) ? data.categories : [],
        items: Array.isArray(data?.items) ? data.items : [],
        last_checked_at: data?.last_checked_at || null,
        integration_status: data?.integration_status ? {
          ...data.integration_status,
          items: (data.integration_status.items || []).map((item) => {
            const desired = officeConsentQueue.desired(item.id);
            return desired === undefined ? item : { ...item, details: { ...item.details, auto_probe_consent: desired } };
          }),
        } : null,
      };
      else if (name === 'integrations') catalog.integrations = {
        summary: data?.summary || {},
        items: Array.isArray(data?.items) ? data.items : [],
        latest_batch: data?.latest_batch || null,
      };
      else if (name === 'artifacts') catalog.artifacts = data.items || [];
      else catalog[name] = data.items || [];
      delete catalog.errors[name];
      if (name === 'localIntegrations') scheduleLocalStatusRefresh();
    } catch (error) {
      if (!isLatestCatalogRequest(name, generation)) return;
      catalog.errors[name] = error.message;
      if (name === 'runtime') catalog.runtime = null;
      if (name === 'localIntegrations') { catalog.localIntegrations = invalidateLocalIntegrationSnapshot(catalog.localIntegrations); scheduleLocalStatusRefresh(); }
    }
    finally {
      finishCatalogRequest(name);
      render();
    }
  }));
  if (names.includes('connections') || names.includes('integrations')) {
    catalog.connections = mergeIntegrationStatuses(catalog.connections, catalog.integrations);
  }
  render();
}

function scheduleLocalStatusRefresh() {
  clearTimeout(localStatusExpiryTimer);
  localStatusExpiryTimer = null;
  if (state.route.page !== 'settings' || currentSettingsSection() !== 'local') return;
  const delay = nextLocalStatusExpiry(catalog.localIntegrations);
  if (delay === null) return;
  localStatusExpiryTimer = setTimeout(() => {
    if (document.hidden || state.route.page !== 'settings' || currentSettingsSection() !== 'local') return;
    void loadCatalog(['localIntegrations']);
  }, Math.min(delay + 1, 2147483647));
}

function updateFrameworkBotSlot() {
  const slot = root.querySelector('[data-framework-bot-slot]');
  if (!slot || !frameworkState.data?.snapshot) return;
  slot.innerHTML = renderEmbeddedBot(frameworkState.data.snapshot, { ...frameworkBot, bridgeReady: frameworkEmbedBridge.ready(state.route.frameworkSlug, frameworkState.data.snapshot.revision) });
  const button = slot.querySelector('[data-framework-bot-open]');
  if (button) button.disabled = !frameworkEmbedBridge.ready(state.route.frameworkSlug, frameworkState.data.snapshot.revision);
}

function attachFrameworkStream(sessionId) {
  closeFrameworkStream();
  closeFrameworkStream = api.events(sessionId, {
    snapshot: (detail) => {
      if (frameworkBot.sessionId !== sessionId) return;
      frameworkBot.detail = detail; frameworkBot.busy = isRunning(detail.status); if (frameworkBot.revision === frameworkState.data?.snapshot?.revision) { frameworkBot.error = ''; frameworkBot.errorCode = ''; } updateFrameworkBotSlot();
    },
    error: (message) => {
      if (frameworkBot.sessionId !== sessionId) return;
      frameworkBot.error = message; updateFrameworkBotSlot();
    },
    open: async () => {
      if (frameworkBot.sessionId !== sessionId) return;
      try { const detail = await api.detail(sessionId); if (frameworkBot.sessionId !== sessionId) return; frameworkBot.detail = detail; frameworkBot.busy = isRunning(detail.status); updateFrameworkBotSlot(); }
      catch (error) { if (frameworkBot.sessionId === sessionId) { frameworkBot.error = error.message; updateFrameworkBotSlot(); } }
    },
  });
}

function scrollFrameworkTarget(anchor, behavior = 'auto') {
  const target = document.getElementById(`framework-${anchor}`);
  const main = document.querySelector('.main');
  const scroller = main?.scrollHeight > main?.clientHeight ? main : document.scrollingElement;
  if (!target || !scroller) return;
  const scrollerTop = scroller === document.scrollingElement ? 0 : scroller.getBoundingClientRect().top;
  const currentTop = scroller === document.scrollingElement ? window.scrollY : scroller.scrollTop;
  const top = currentTop + target.getBoundingClientRect().top - scrollerTop - 64;
  scroller.scrollTo({ top: Math.max(0, top), behavior });
}

async function loadFrameworkPage(ticket = pageGeneration) {
  const slug = state.route.frameworkSlug || '';
  const request = frameworkLoadGuard.begin();
  const current = () => frameworkLoadGuard.current(request) && ticket === pageGeneration && state.route.page === 'frameworks' && (state.route.frameworkSlug || '') === slug;
  const data = frameworkState.slug === slug ? frameworkState.data : null;
  frameworkState = { ...frameworkState, status: 'loading', data, slug, error: '' }; render();
  try {
    const [catalogData, fetchedData] = await Promise.all([api.frameworks(), slug ? api.frameworkData(slug) : Promise.resolve(null)]);
    if (!current()) return;
    frameworkState = { status: 'ready', catalog: catalogData, data: fetchedData, slug, error: '' };
    if (frameworkBot.sessionId && frameworkBot.revision !== fetchedData?.snapshot?.revision) {
      frameworkBot.errorCode = 'framework_snapshot_changed';
      frameworkBot.error = '数据已更新，请基于新快照重新开始。';
    }
    render();
  } catch (error) {
    if (!current()) return;
    frameworkState.status = 'error'; frameworkState.error = error.message; render();
  }
}

async function ensureFrameworkSession() {
  if (frameworkBot.sessionId) {
    if (frameworkBot.revision !== frameworkState.data?.snapshot?.revision) throw Object.assign(new Error('数据已更新，请关闭后重新开始。'), { code: 'framework_snapshot_changed' });
    return frameworkBot.sessionId;
  }
  const revision = frameworkState.data?.snapshot?.revision;
  if (!revision) throw new Error('框架快照尚未就绪。');
  const slug = state.route.frameworkSlug;
  if (!slug) throw new Error('框架路由尚未就绪。');
  if (!isNativeFramework(slug) || !frameworkEmbedBridge.ready(slug, revision)) throw new Error('看板尚未确认当前快照。');
  const botOwner = frameworkBot;
  const generation = pageGeneration;
  const created = await api.createFrameworkSession(slug, { snapshot_revision: revision, focus_section: state.route.frameworkTab || 'overview', gap_ids: [] });
  if (botOwner !== frameworkBot || generation !== pageGeneration || slug !== state.route.frameworkSlug) throw new Error('框架路由已变更。');
  frameworkBot.revision = revision;
  frameworkBot.sessionId = created.session.id; frameworkBot.mode = 'explain';
  const detail = await api.detail(created.session.id);
  if (botOwner !== frameworkBot) throw new Error('框架路由已变更。');
  frameworkBot.detail = detail;
  attachFrameworkStream(created.session.id);
  return created.session.id;
}

async function sendFrameworkQuestion(question) {
  if (frameworkBot.busy || !question.trim()) return;
  const botOwner = frameworkBot;
  const slug = state.route.frameworkSlug;
  frameworkBot.busy = true; frameworkBot.error = ''; frameworkBot.errorCode = ''; updateFrameworkBotSlot();
  try {
    const sid = await ensureFrameworkSession();
    if (botOwner !== frameworkBot || slug !== state.route.frameworkSlug) return;
    const revision = botOwner.revision;
    if (revision !== frameworkState.data?.snapshot?.revision) throw Object.assign(new Error('数据已更新，请关闭后重新开始。'), { code: 'framework_snapshot_changed' });
    await api.frameworkMessage(slug, sid, { text: question.trim(), expected_snapshot_revision: revision, mode: 'explain' }, crypto.randomUUID());
    const detail = await api.detail(sid);
    if (botOwner !== frameworkBot) return;
    frameworkBot.draft = ''; frameworkBot.detail = detail;
  } catch (error) {
    if (botOwner === frameworkBot) { frameworkBot.error = error.message; frameworkBot.errorCode = error.code || ''; }
  } finally { if (botOwner === frameworkBot) { frameworkBot.busy = false; updateFrameworkBotSlot(); } }
}

async function verifyFrameworkQuestion(question) {
  if (frameworkBot.busy || !frameworkBot.sessionId) return;
  const botOwner = frameworkBot;
  const slug = state.route.frameworkSlug;
  frameworkBot.busy = true; frameworkBot.error = ''; frameworkBot.errorCode = ''; updateFrameworkBotSlot();
  try {
    if (botOwner !== frameworkBot || slug !== state.route.frameworkSlug) return;
    const revision = botOwner.revision;
    if (revision !== frameworkState.data?.snapshot?.revision) throw Object.assign(new Error('数据已更新，请关闭后重新开始。'), { code: 'framework_snapshot_changed' });
    const result = await api.verifyFrameworkSession(slug, frameworkBot.sessionId, { expected_snapshot_revision: revision, question: question.trim() || '核验当前最重要的数据缺口与反证条件。' }, crypto.randomUUID());
    if (botOwner !== frameworkBot) return;
    frameworkBot.sessionId = result.session.id; frameworkBot.mode = 'verify'; frameworkBot.draft = '';
    const detail = await api.detail(result.session.id);
    if (botOwner !== frameworkBot) return;
    frameworkBot.detail = detail;
    attachFrameworkStream(result.session.id);
  } catch (error) {
    if (botOwner === frameworkBot) { frameworkBot.error = error.message; frameworkBot.errorCode = error.code || ''; }
  } finally { if (botOwner === frameworkBot) { frameworkBot.busy = false; updateFrameworkBotSlot(); } }
}

function mcpInstallationFor(identity) {
  return mcpMarketplaceState.installations.find((item) => {
    const plan = item?.plan || {};
    return plan.registry_id === identity.registryId
      && plan.server_name === identity.serverName
      && plan.server_version === identity.version;
  }) || null;
}

function mcpInstallationState(record) {
  if (!record?.id) return emptyMCPInstallation();
  const runtimeStatus = String(record.runtime_status || 'installed');
  const probeStatus = ['ready', 'enabled', 'disabled'].includes(runtimeStatus) ? 'ready'
    : runtimeStatus === 'health_failed' ? 'failed' : 'not_run';
  return {
    ...emptyMCPInstallation(),
    installationId: record.id,
    installStatus: 'installed',
    probeStatus,
    enableStatus: record.active === true || runtimeStatus === 'enabled' ? 'enabled' : 'disabled',
    record: structuredClone(record),
  };
}

function replaceMCPInstallation(record) {
  if (!record?.id) return;
  mcpMarketplaceState.installations = [
    record,
    ...mcpMarketplaceState.installations.filter(item => item?.id !== record.id),
  ];
}

async function loadMCPRuntimeInventory() {
  try {
    const [response, approvals] = await Promise.all([api.mcpInstallations(), api.mcpApprovals()]);
    mcpMarketplaceState.installations = Array.isArray(response?.items) ? response.items : [];
    mcpMarketplaceState.approvals = Array.isArray(approvals?.items) ? approvals.items.filter(item => item?.status === 'pending') : [];
    mcpMarketplaceState.runtimeAvailable = true;
    mcpMarketplaceState.runtimeError = '';
  } catch (error) {
    mcpMarketplaceState.installations = [];
    mcpMarketplaceState.approvals = [];
    mcpMarketplaceState.runtimeAvailable = false;
    mcpMarketplaceState.runtimeError = error?.code === 'mcp_runtime_disabled'
      ? 'MCP Runtime 功能开关尚未启用；当前仍可浏览 Registry。'
      : (error?.message || 'MCP Runtime 状态读取失败；Registry 浏览仍可使用。');
    safeLog('mcp_runtime_inventory_failed', { status: error?.code || 'request_failed' });
  }
}

async function decideMCPApproval(approvalId, approve) {
  const approval = mcpMarketplaceState.approvals.find(item => item?.id === approvalId);
  if (!approval?.session_id || mcpMarketplaceState.approvalBusy) return;
  mcpMarketplaceState.approvalBusy = approvalId; mcpMarketplaceState.runtimeError = ''; render();
  try {
    if (approve) await api.mcpApprove(approvalId, { session_id: approval.session_id });
    else await api.mcpDeny(approvalId, { session_id: approval.session_id });
    mcpMarketplaceState.approvals = mcpMarketplaceState.approvals.filter(item => item?.id !== approvalId);
    safeLog('mcp_approval_decided', { status: approve ? 'approved' : 'denied' });
  } catch (error) {
    mcpMarketplaceState.runtimeError = error?.message || 'MCP 人工审批提交失败。';
    safeLog('mcp_approval_decision_failed', { status: error?.code || 'request_failed' });
  } finally {
    mcpMarketplaceState.approvalBusy = ''; render();
  }
}

async function loadMCPMarketplace({ sync = false, reloadRegistries = false } = {}) {
  if (mcpMarketplaceState.loading || mcpMarketplaceState.syncing) return;
  const ticket = pageGeneration; const operation = ++mcpCatalogGeneration;
  const request = { registryId: mcpMarketplaceState.selectedRegistryId, query: mcpMarketplaceState.query, sync };
  const current = () => operation === mcpCatalogGeneration && ticket === pageGeneration && currentMCPMarketRoute()
    && request.query === mcpMarketplaceState.query && (!request.registryId || request.registryId === mcpMarketplaceState.selectedRegistryId);
  mcpMarketplaceState.error = '';
  mcpMarketplaceState[sync ? 'syncing' : 'loading'] = true;
  render();
  try {
    if (reloadRegistries || mcpMarketplaceState.runtimeAvailable === null) {
      await loadMCPRuntimeInventory();
      if (!current()) return;
    }
    if (reloadRegistries || !mcpMarketplaceState.registries.length) {
      const response = await api.mcpRegistries();
      if (!current()) return;
      const registries = Array.isArray(response.items) ? response.items : [];
      mcpMarketplaceState.registries = registries;
      if (!registries.some(item => item.id === mcpMarketplaceState.selectedRegistryId)) mcpMarketplaceState.selectedRegistryId = registries[0]?.id || '';
    }
    if (operation !== mcpCatalogGeneration || ticket !== pageGeneration || !currentMCPMarketRoute() || request.query !== mcpMarketplaceState.query) return;
    const registryId = mcpMarketplaceState.selectedRegistryId; request.registryId = registryId;
    if (!registryId) { mcpMarketplaceState.page = null; return; }
    const page = sync
      ? await api.mcpSyncRegistry(registryId, { search: request.query || null, cursor: null, limit: 100 })
      : await api.mcpServers({ registryId, search: request.query, limit: 100 });
    if (!current()) return;
    mcpMarketplaceState.page = page;
    safeLog(sync ? 'mcp_registry_sync_finished' : 'mcp_registry_catalog_loaded', { status: mcpMarketplaceState.page?.stale ? 'stale' : 'ready' });
  } catch (error) {
    if (!current()) return;
    mcpMarketplaceState.error = error?.message || 'MCP Registry 暂时不可用，请稍后重试。';
    safeLog(sync ? 'mcp_registry_sync_failed' : 'mcp_registry_catalog_failed', { status: error?.code || 'request_failed' });
  } finally {
    if (operation === mcpCatalogGeneration) {
      mcpMarketplaceState.loading = false; mcpMarketplaceState.syncing = false; render();
    }
  }
}

async function openMCPServerDetail(identity) {
  if (mcpMarketplaceState.loading || mcpMarketplaceState.syncing || !identity.registryId || !identity.serverName || !identity.version) return;
  const ticket = pageGeneration; const operation = ++mcpDetailGeneration;
  const requested = { registryId: identity.registryId, serverName: identity.serverName, version: identity.version };
  const identityKey = JSON.stringify([requested.registryId, requested.serverName, requested.version]);
  mcpDetailRequestIdentity = identityKey;
  mcpInstallGeneration += 1; mcpMarketplaceState.installation = emptyMCPInstallation();
  const current = () => operation === mcpDetailGeneration && identityKey === mcpDetailRequestIdentity && ticket === pageGeneration && currentMCPMarketRoute();
  mcpMarketplaceState.loading = true; mcpMarketplaceState.error = ''; render();
  try {
    const detail = await api.mcpServerVersion(requested.registryId, requested.serverName, requested.version);
    if (!current()) return;
    mcpMarketplaceState.detail = detail;
    mcpMarketplaceState.returnIdentity = requested;
    const existing = mcpInstallationFor(requested);
    if (existing) {
      mcpMarketplaceState.installation = mcpInstallationState(existing);
      if (mcpMarketplaceState.installation.probeStatus === 'ready') {
        try {
          const capabilities = await api.mcpInstallationCapabilities(existing.id);
          if (current()) mcpMarketplaceState.installation.capabilities = capabilities;
        } catch (error) {
          if (current() && error?.code !== 'mcp_capabilities_unavailable') {
            mcpMarketplaceState.installation.error = error?.message || 'MCP 能力快照读取失败。';
          }
        }
      }
    }
  } catch (error) {
    if (!current()) return;
    mcpMarketplaceState.error = error?.message || 'MCP Server 详情读取失败。';
    safeLog('mcp_registry_detail_failed', { status: error?.code || 'request_failed' });
  } finally {
    if (operation !== mcpDetailGeneration) return;
    mcpMarketplaceState.loading = false; render();
    if (mcpMarketplaceState.detail) focusMCPServerDialog();
    else findMCPServerTrigger(requested)?.focus?.({ preventScroll: true });
  }
}

async function runMCPInstallPreview() {
  const detail = mcpMarketplaceState.detail;
  const installation = mcpMarketplaceState.installation;
  if (!detail || !installation.target || installation.busy) return;
  let selection;
  try { selection = mcpInstallSelection(detail, installation.target); }
  catch { installation.error = '请选择客户端已验证的固定本地包或 Streamable HTTP 目标。'; render(); return; }
  const ticket = pageGeneration; const operation = ++mcpInstallGeneration;
  installation.busy = 'preview'; installation.error = ''; installation.preview = null; installation.confirmationToken = ''; render();
  try {
    const result = await api.mcpInstallationPreview(selection);
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    if (!result?.plan || typeof result.confirmation_token !== 'string' || !result.confirmation_token) throw new Error('安装预览响应格式异常。');
    installation.preview = result.plan; installation.confirmationToken = result.confirmation_token; installation.installStatus = 'preview_ready';
    safeLog('mcp_installation_preview_ready', { status: result.plan.target_kind === 'remote' ? 'remote' : 'local' });
  } catch (error) {
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    installation.error = error?.message || '安装预览失败，请检查固定版本与制品完整性。';
    safeLog('mcp_installation_preview_failed', { status: error?.code || 'request_failed' });
  } finally {
    if (operation === mcpInstallGeneration) { installation.busy = ''; render(); }
  }
}

async function runMCPInstallConfirmation() {
  const detail = mcpMarketplaceState.detail;
  const installation = mcpMarketplaceState.installation;
  const form = document.querySelector('[data-mcp-install-form]');
  if (!detail || !installation.preview || !installation.confirmationToken || installation.busy || !form) return;
  const inputs = [...(form.querySelectorAll?.('[data-mcp-env-value]') || [])];
  let environmentValues;
  try {
    environmentValues = mcpEnvironmentPayload(
      inputs.map(input => ({ name: input.dataset.mcpEnvName, value: input.value })),
      installation.preview.environment_names,
      form.querySelector?.('[data-mcp-install-confirm]')?.checked === true,
    );
  } catch (error) {
    installation.error = error.message === 'installation_confirmation_required'
      ? '请先勾选二次确认，确认你已核对完整安装摘要。'
      : '请为预览列出的每个环境变量填写本次值。';
    render(); return;
  }
  const ticket = pageGeneration; const operation = ++mcpInstallGeneration;
  installation.busy = 'install'; installation.error = ''; render();
  const request = { confirmation_token: installation.confirmationToken, environment_values: environmentValues };
  const pending = api.mcpInstall(request);
  inputs.forEach(input => { input.value = ''; });
  Object.keys(environmentValues).forEach(name => { delete environmentValues[name]; });
  request.confirmation_token = ''; request.environment_values = {};
  try {
    const result = await pending;
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    const installationId = result?.installation?.id;
    if (typeof installationId !== 'string' || !installationId) throw new Error('安装结果缺少记录 ID。');
    installation.preview = null; installation.confirmationToken = ''; installation.installationId = installationId;
    installation.installStatus = 'installed'; installation.probeStatus = 'not_run'; installation.enableStatus = 'disabled'; installation.authorizationStatus = 'not_authorized';
    installation.record = { ...result.installation, runtime_status: 'installed', active: false };
    replaceMCPInstallation(installation.record);
    safeLog('mcp_installation_finished', { status: 'installed' });
  } catch (error) {
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    installation.error = error?.message || '安装失败；未自动探测、启用或授权。';
    safeLog('mcp_installation_failed', { status: error?.code || 'request_failed' });
  } finally {
    Object.keys(environmentValues).forEach(name => { delete environmentValues[name]; });
    if (operation === mcpInstallGeneration) { installation.busy = ''; render(); }
  }
}

async function runMCPInstalledAction(action) {
  const detail = mcpMarketplaceState.detail;
  const installation = mcpMarketplaceState.installation;
  if (!detail || installation.installStatus !== 'installed' || !installation.installationId || installation.busy) return;
  if (action === 'enable' && installation.probeStatus !== 'ready') return;
  if (action === 'disable' && installation.enableStatus !== 'enabled') return;
  const ticket = pageGeneration; const operation = ++mcpInstallGeneration;
  installation.busy = action; installation.error = ''; render();
  try {
    const result = action === 'probe'
      ? await api.mcpProbeInstallation(installation.installationId)
      : action === 'enable'
        ? await api.mcpEnableInstallation(installation.installationId)
        : await api.mcpDisableInstallation(installation.installationId);
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    if (action === 'probe') {
      installation.probeStatus = 'ready';
      installation.capabilities = result;
    } else if (action === 'enable') {
      installation.probeStatus = 'ready';
      installation.enableStatus = result?.active === true || result?.status === 'enabled' ? 'enabled' : 'disabled';
      if (installation.enableStatus !== 'enabled') throw new Error('Runtime 未确认启用状态。');
    } else {
      installation.enableStatus = result?.active === false ? 'disabled' : 'enabled';
      if (installation.enableStatus !== 'disabled') throw new Error('Runtime 未确认停用状态。');
    }
    if (installation.record) {
      installation.record = {
        ...installation.record,
        runtime_status: action === 'probe' ? 'ready' : installation.enableStatus,
        active: installation.enableStatus === 'enabled',
      };
      replaceMCPInstallation(installation.record);
    }
    safeLog(`mcp_installation_${action}_finished`, { status: action === 'probe' ? 'ready' : installation.enableStatus });
  } catch (error) {
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    if (action === 'probe') installation.probeStatus = 'failed';
    installation.error = error?.message || `${action === 'probe' ? '健康探测' : action === 'enable' ? 'Runtime 启用' : 'Runtime 停用'}失败。`;
    safeLog(`mcp_installation_${action}_failed`, { status: error?.code || 'request_failed' });
  } finally {
    if (operation === mcpInstallGeneration) { installation.busy = ''; render(); }
  }
}

async function removeMCPInstallation() {
  const detail = mcpMarketplaceState.detail;
  const installation = mcpMarketplaceState.installation;
  if (!detail || !installation.installationId || installation.busy || installation.enableStatus === 'enabled') return;
  if (!globalThis.confirm?.('移除此 MCP 安装记录及其隔离文件？已启用的安装必须先停用。')) return;
  const ticket = pageGeneration; const operation = ++mcpInstallGeneration;
  installation.busy = 'remove'; installation.error = ''; render();
  try {
    await api.mcpDeleteInstallation(installation.installationId);
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    mcpMarketplaceState.installations = mcpMarketplaceState.installations.filter(item => item?.id !== installation.installationId);
    mcpMarketplaceState.installation = emptyMCPInstallation();
    safeLog('mcp_installation_removed', { status: 'deleted' });
  } catch (error) {
    if (operation !== mcpInstallGeneration || ticket !== pageGeneration || mcpMarketplaceState.detail !== detail) return;
    installation.error = error?.message || 'MCP 安装移除失败。';
    safeLog('mcp_installation_remove_failed', { status: error?.code || 'request_failed' });
  } finally {
    if (operation === mcpInstallGeneration) { mcpMarketplaceState.installation.busy = ''; render(); }
  }
}

async function classifyMCPTool(toolName, riskTier, allowUnattended) {
  const installation = mcpMarketplaceState.installation;
  if (!installation.installationId || installation.busy) return;
  installation.busy = `classify:${toolName}`; installation.error = ''; render();
  try {
    const result = await api.mcpClassifyTool(installation.installationId, {
      tool_name: toolName,
      risk_tier: riskTier,
      allow_unattended: allowUnattended === true && riskTier === 'read_only',
    });
    const tools = installation.capabilities?.tools;
    const tool = Array.isArray(tools) ? tools.find(item => item?.name === toolName) : null;
    if (tool) {
      tool.risk_tier = result.risk_tier;
      tool.allow_unattended = result.allow_unattended === true;
      tool.schema_sha256 = result.schema_sha256;
    }
    installation.authorizationStatus = 'not_authorized';
    safeLog('mcp_tool_policy_updated', { status: result.risk_tier || 'updated' });
  } catch (error) {
    installation.error = error?.message || 'MCP 工具风险分级保存失败。';
    safeLog('mcp_tool_policy_failed', { status: error?.code || 'request_failed' });
  } finally {
    installation.busy = ''; render();
  }
}

async function authorizeMCPTool(toolName) {
  const installation = mcpMarketplaceState.installation;
  const sessionId = researchDraftRoute.sessionId;
  const tool = installation.capabilities?.tools?.find?.(item => item?.name === toolName);
  const version = installation.record?.plan?.server_version;
  if (!sessionId || !installation.installationId || installation.enableStatus !== 'enabled' || !tool?.schema_sha256 || !version || installation.busy) return;
  installation.busy = `authorize:${toolName}`; installation.error = ''; render();
  try {
    await api.mcpAuthorizeSession(sessionId, {
      installation_id: installation.installationId,
      version,
      tool_name: toolName,
      schema_sha256: tool.schema_sha256,
    });
    tool.authorized = true;
    installation.authorizationStatus = 'authorized';
    safeLog('mcp_session_tool_authorized', { status: 'active' });
  } catch (error) {
    installation.error = error?.message || '当前研究会话的 MCP 工具授权失败。';
    safeLog('mcp_session_tool_authorization_failed', { status: error?.code || 'request_failed' });
  } finally {
    installation.busy = ''; render();
  }
}

async function startMCPOAuth() {
  const installation = mcpMarketplaceState.installation;
  const resource = installation.record?.plan?.endpoint;
  if (!installation.installationId || !resource || installation.busy) return;
  installation.busy = 'oauth'; installation.error = ''; render();
  try {
    const result = await api.mcpStartOAuth(installation.installationId, { resource });
    if (typeof result?.authorization_url !== 'string' || !result.authorization_url.startsWith('https://')) throw new Error('OAuth 授权地址无效。');
    globalThis.location.assign?.(result.authorization_url);
  } catch (error) {
    installation.error = error?.message || 'MCP OAuth 授权启动失败。';
    safeLog('mcp_oauth_start_failed', { status: error?.code || 'request_failed' });
  } finally {
    installation.busy = ''; render();
  }
}

async function runMCPPublisherAction(action) {
  const publisher = mcpMarketplaceState.publisher;
  if (publisher.busy) return;
  publisher.error = ''; publisher.result = null;
  let value;
  try { value = JSON.parse(publisher.source); }
  catch { publisher.error = 'server.json 不是有效 JSON；请修正后重试。'; render(); return; }
  if (!value || typeof value !== 'object' || Array.isArray(value)) { publisher.error = 'server.json 顶层必须是对象。'; render(); return; }
  const ticket = pageGeneration; const operation = ++mcpPublisherGeneration; const source = publisher.source;
  const current = () => operation === mcpPublisherGeneration && ticket === pageGeneration && source === publisher.source;
  publisher.busy = true; render();
  try {
    const result = action === 'preview' ? await api.mcpPublisherPreview(value) : await api.mcpPublisherValidate(value);
    if (!current()) return;
    publisher.result = result; publisher.resultSource = source;
    safeLog('mcp_publisher_handoff_finished', { status: publisher.result?.valid === false ? 'invalid' : 'valid' });
  } catch (error) {
    if (!current()) return;
    publisher.error = error?.message || 'server.json 处理失败，请检查后重试。';
    safeLog('mcp_publisher_handoff_failed', { status: error?.code || 'request_failed' });
  } finally { if (operation === mcpPublisherGeneration) { publisher.busy = false; render(); } }
}

async function loadOperations() {
  try {
    const summary = await api.operationsSummary(operationsRange);
    for (const name of ['usage', 'tools', 'datahub', 'services', 'storage']) {
      operationsData[name] = summary[name] || null;
      delete catalog.errors[`operations-${name}`];
    }
  } catch (error) {
    for (const name of ['usage', 'tools', 'datahub', 'services', 'storage']) operationsData[name] = null;
    catalog.errors['operations-summary'] = error.message;
  }
  render();
}

// A response belongs to the navigation that requested it, even after back/forward
// returns to the same section. Server-side queries continue independently.
function workbenchOwner() {
  const ticket = pageGeneration;
  const section = state.route.section;
  return () => ticket === pageGeneration && isDataWorkspaceRoute(state.route) && state.route.section === section;
}

async function loadWorkbench() {
  if (!isDataWorkspaceRoute(state.route)) return;
  if (isDossierRoute(state.route)) { await dossierController.activate(state.route); return; }
  const owner = workbenchOwner();
  const request = ++workbenchLoadGeneration;
  const current = () => owner() && request === workbenchLoadGeneration;
  const section = state.route.section || 'assets';
  if(section==='hot'){await hotController.activate(state.route);return;}

  if (section === 'etf-paper') {
    try {
      const [readiness, runs] = await Promise.all([api.etfReadiness(), api.etfRuns()]);
      if (!current()) return;
      etfState = { ...etfState, readiness, runs: runs.items || [] };
      delete catalog.errors.etfPaper;
    } catch (error) { if (current()) catalog.errors.etfPaper = error.message; safeLog('etf_paper_load_failed'); }
    if (current()) render(); return;
  }
  if (section === 'assets') {
    delete catalog.errors.artifacts;
    await Promise.all([loadCatalog(['dataCatalog']), loadAssetWorkspace(current), assetNews.activate(state.route)]);
    if (current()) render();
    return;
  }
  await Promise.all([
    loadCatalog(['dataCatalog']),
    (async () => {
      try {
        const data = await api.dataQueries(section);
        if (!current()) return;
        workbenchQueries = Array.isArray(data.items) ? data.items : [];
        delete catalog.errors.workbenchQueries;
      } catch (error) {
        safeLog('business_query_index_failed', { section, code: error.code || 'request_failed' });
        if (!current()) return;
        workbenchQueries = [];
        catalog.errors.workbenchQueries = error.message;
      }
    })(),
  ]);
  if (current()) render();
}

async function loadAssetWorkspace(current = workbenchOwner()) {
  const ticket = pageGeneration;
  await assetWorkspace.activateView(state.route, { refresh: false });
  if (ticket !== pageGeneration || !current() || !isAssetPage()) return;
  assetState = assetWorkspace.state;
  const observation = assetState.observation;
  configureAssetTerminal();
  workbenchContext = observation ? { section: 'assets', asset: observation.asset, asset_type: observation.asset_type, source: observation.source, requested_at: observation.created_at, completed_at: observation.updated_at, dataset_ids: observation.dataset_ids || [], blocks: Object.fromEntries(Object.entries(observation.blocks || {}).map(([name, block]) => [name, { status: block.status, as_of: block.dataset?.as_of || null, provider: block.dataset?.provider || null }])) } : {};
  delete catalog.errors.assetWorkspace;
}

async function pollAssetObservation(record, ticket) {
  const deadline = Date.now() + 240000;
  while (record.status === 'running' && Date.now() < deadline && ticket === pageGeneration && isAssetPage()) {
    await new Promise(resolve => setTimeout(resolve, 500));
    if (ticket !== pageGeneration || !isAssetPage()) return record;
    record = await api.assetObservation(record.id);
    if (ticket !== pageGeneration) return record;
    assetState.observation = record; render();
  }
  return record;
}

async function showRoute() {
  if (/^#\/skills\?.*\bview=plans(?:&|$)/.test(location.hash)) {
    history.replaceState(null, '', '#/claw?view=plans');
  }
  const legacyTarget = legacyRouteTarget(location.hash);
  if (legacyTarget) {
    history.replaceState(null, '', legacyTarget);
    location.hash = legacyTarget;
  }
  const requestedRoute = parseRoute(location.hash);
  const assetPage = root.querySelector('[data-asset-identity]');
  const requestedAssetIdentity = `${requestedRoute.assetType || 'stock'}:${requestedRoute.asset || assetState.observation?.asset || ''}`;
  const sameAssetPage = isAssetPage() && requestedRoute.assetView !== 'dossiers' && ['assets', 'workbench'].includes(requestedRoute.page) && requestedRoute.section === 'assets' && assetPage?.dataset.assetIdentity === requestedAssetIdentity;
  if (sameAssetPage && requestedRoute.assetView !== state.route.assetView) {
    const ticket = ++pageGeneration;
    assetTopicNavigation = ticket;
    state.route = requestedRoute;
    state.error = ''; workbenchBusy = false;
    delete assetState.errors.topic;
    updateAssetTopic(assetPage, assetTopicProps());
    mountAssetTopicIndicators(assetPage);
    try {
      await Promise.all([assetWorkspace.activateView?.(requestedRoute, { refresh: false }), assetNews.activate(requestedRoute)]);
    } catch (error) {
      if (ticket === pageGeneration) {
        assetState.errors ||= {};
        assetState.errors.topic = error.message || '页签数据读取失败，请重试。';
      }
      safeLog('asset_topic_navigation_failed', { status: 'error' });
    } finally {
      if (ticket === pageGeneration) { paintAssetWorkspace(); assetTopicNavigation = 0; }
    }
    return;
  }
  assetTopicNavigation = 0;
  if (isDossierRoute(requestedRoute)) controller.clearDossierHandoff(requestedRoute.dossierId || '');
  intelController.cancel();
  discoveryController.deactivate();
  dossierController.cancel();

  marketController.cancel();
  assetNews.cancel(); assetChart.cancel();
  aihotController.cancel();
  localIntegrationPollingGuard.invalidate(); officeAutoPollingGuard.invalidate(); officeConsentConfirmation = '';
  localVerificationTarget = '';
  quickCategory = '';
  assetWorkspace.cancel({ stopHistory: !sameAssetPage });
  if(!(requestedRoute.page==='intel'&&requestedRoute.intelTab==='hot'||requestedRoute.page==='settings'&&requestedRoute.settingsSection==='hot'))hotController.deactivate();
  if (requestedRoute.page !== 'frameworks' || requestedRoute.frameworkSlug !== state.route.frameworkSlug) {
    closeFrameworkStream(); closeFrameworkStream = () => {};
    frameworkBot = { open: false, mode: 'explain', sessionId: '', detail: null, draft: '', busy: false, error: '', errorCode: '' };
  }
  const requestedMarket = requestedRoute.page === 'skills' && requestedRoute.capabilityKind === 'tool' && requestedRoute.capabilityView === 'market';
  if (!requestedMarket) invalidateMCPRequests();
  composerMenu = closedComposerMenu();
  clearTimeout(reportRefreshTimer);
  const ticket = ++pageGeneration; workbenchBusy = false; nativeSessionSearch.close(); success = ''; selectedPreview = null; sidebarOpen = false; clawSidebarView = 'sessions'; contextOpen = false; contextTab = 'activity'; researchStage = null; slashOpen = false; slashIndex = 0; tabbitOpen = false; tabbitLoading = false; tabbitIndex = 0; tabbitCandidates = []; tabbitRequest += 1; globalSearch = ''; searchOpen = false; renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionMenu = null; sessionActionBusy = false; sessionActionError = ''; answerFeedback.clear(); copiedTransient = '';
  if (['claw', 'fingpt'].includes(requestedRoute.page)) sidebarCollapsed = conversationNavigation.state(requestedRoute.page).view.collapsed;
  if (conversationNavigation.state(requestedRoute.page)) conversationNavigation.state(requestedRoute.page).menu = null;
  cancelProjectMenuTimers();
  await controller.open(requestedRoute);
  if (ticket !== pageGeneration) return;
  if (state.route.settingsSectionFallback) safeLog('settings_section_fallback');
  if (['fingpt', 'claw'].includes(state.route.page)) researchDraftRoute = { ...state.route };
  document.querySelector('#main')?.scrollTo({ top: 0 });
  await loadWorkflowVersion();
  if (['claw', 'fingpt'].includes(state.route.page)) { sidebarCollapsed = conversationNavigation.state(state.route.page).view.collapsed; await conversationNavigation.load(state.route.page, true); }
  if (state.route.page === 'history') await loadCatalog([state.route.historyView === 'deleted' ? 'deletedSessions' : 'sessions']);
  if (state.route.page === 'reports') { await loadReportPage(ticket); armReportRefresh(ticket); }
  if (state.route.page === 'frameworks') await loadFrameworkPage(ticket);
  if (state.route.page === 'settings') {
    migrationOpen = false;
    connectionDetailOpen = true;
    selectedConnectionConfiguration = null;
    let section = currentSettingsSection();
    const catalogs = settingsRefreshCatalogs(section);
    if (catalogs.length) await loadCatalog(catalogs);
    const resolvedSection = currentSettingsSection();
    if (resolvedSection !== section) {
      section = resolvedSection;
      const resolvedCatalogs = settingsRefreshCatalogs(section);
      if (resolvedCatalogs.length) await loadCatalog(resolvedCatalogs);
    }
    if (section === 'data') {
      const selectedId = currentSettingsConnectionId();
      if (selectedId) await loadConnectionConfiguration(selectedId);
    }
    if(section==='hot')await hotController.activate(state.route);
  }
  if (state.route.page === 'skills') {
    const previousKind = capabilityState.kindFilter;
    const previousView = capabilityState.view;
    const nextKind = state.route.capabilityKind || 'skill';
    if (previousKind !== nextKind) {
      capabilityState.source = 'all'; capabilityState.category = ''; capabilityState.status = 'all'; capabilityState.query = '';
      capabilityState.dataMarket = ''; capabilityState.dataStatus = ''; capabilityState.dataAuth = ''; capabilityState.probe = null;
      capabilityState.detail = null; capabilityState.tool = null; capabilityState.dataDetail = null; capabilityState.dataDetailKind = '';
      capabilityState.form = ''; reportWorkflowDetail = null;
      mcpMarketplaceState = { ...mcpMarketplaceState, query: '', page: null, detail: null, returnIdentity: null, error: '', loading: false, syncing: false };
      automationFormOpen = false;
    }
    capabilityState.view = state.route.capabilityView || 'library';
    capabilityState.kindFilter = nextKind;
    capabilityState.dataView = nextKind === 'data' && capabilityState.view === 'connections' ? 'sources' : 'capabilities';
    if (['skill', 'workflow'].includes(nextKind)) capabilityState.kind = nextKind;
    if (nextKind !== 'plugin') await loadCatalog(['capabilities', 'tools', 'reportWorkflows', 'dataCatalog', 'connections', 'sessions']);
    if (nextKind === 'workflow' && capabilityState.view === 'plans') await loadCatalog(['automations', 'automationRuns', 'deliveryChannels']);
    if (nextKind === 'tool' && capabilityState.view === 'market') await loadMCPMarketplace({ reloadRegistries: !mcpMarketplaceState.registries.length });
    else if (previousView === 'market') mcpMarketplaceState = { ...mcpMarketplaceState, detail: null, returnIdentity: null, error: '', loading: false, syncing: false };
  }
  if (state.route.page === 'claw') {
    try { const projects = await api.clawProjects(); if (ticket === pageGeneration) clawWorkspace.projects = projects.items || []; }
    catch (error) { if (ticket === pageGeneration) clawWorkspace.error = error.message; safeLog('claw_project_index_failed', { status: error.code || 'request_failed' }); }
  }
  if (state.route.page === 'claw' && !state.route.sessionId && reportWorkflowsAllowed) await loadCatalog(['reportWorkflows']);
  if (['claw', 'fingpt'].includes(state.route.page) && state.route.clawView === 'projects') await loadClawProjects();
  if (state.route.page === 'claw' && state.route.clawView === 'plans') await loadCatalog(['automations', 'automationRuns']);
  if (state.route.page === 'claw' && state.route.clawView === 'skills') await loadCatalog(['capabilities', 'tools']);
  if (isDataWorkspaceRoute(state.route)) await loadWorkbench();
  if (ticket !== pageGeneration) return;
  if (state.route.page === 'operations') await loadOperations();
  if (state.route.page === 'market') await marketController.activate(state.route);
  if (state.route.page === 'aihot') await aihotController.activate(state.route);
  if (state.route.page === 'intel') {
    if (state.route.intelTab === 'discovery') await discoveryController.activate();
    else if (state.route.intelTab === 'hot') await hotController.activate(state.route);
    else if (state.route.intelTab === 'signals') await dossierController.activate(state.route);

    else if (state.route.intelTab !== 'search') await intelController.activate(state.route.intelTab);
  }
  if (ticket === pageGeneration && pendingMCPMarketTabFocus) {
    const expected = pendingMCPMarketTabFocus;
    pendingMCPMarketTabFocus = '';
    if (state.route.page === 'skills' && state.route.capabilityKind === 'tool' && state.route.capabilityView === expected) {
      document.getElementById(`capability-tool-tab-${expected}`)?.focus?.({ preventScroll: true });
    }
  }
}

async function loadConnectionConfiguration(sourceId) {
  const source = catalog.connections.sources.find((item) => item.id === sourceId);
  if (!source || source.configuration_supported === false) { selectedConnectionConfiguration = null; render(); return; }
  try {
    selectedConnectionConfiguration = await api.sourceConfiguration(sourceId);
    delete catalog.errors.connectionConfiguration;
  } catch (error) {
    selectedConnectionConfiguration = null;
    if (error.code !== 'configuration_not_supported' && error.code !== 'not_found') catalog.errors.connectionConfiguration = error.message;
  }
  render();
}

async function ensureSession() {
  if (dossierDraftOpening) return false;
  if (state.detail) return true;
  if (state.route.sessionId) return false;
  const result = await controller.create(state.route.page, selectedWorkspace, state.route.projectId);
  if (!result?.id) return false;
  await showRoute(); await loadCatalog(['sessions']);
  return state.detail?.id === result.id;
}

async function loadTabbitCandidates(query) {
  let request;
  try {
    if (!await ensureSession()) throw new Error('请先创建或打开一个研究会话。');
    request = ++tabbitRequest;
    tabbitOpen = true; tabbitLoading = true; tabbitIndex = 0; tabbitCandidates = []; slashOpen = false; render();
    const id = state.detail?.id;
    if (!id) throw new Error('当前会话不可用。');
    if (!tabbitGrants.has(id)) {
      const approved = globalThis.confirm?.('允许当前研究会话读取所选 Tabbit 实例的标签页标题和 URL 吗？授权仅在本次 Runtime 生命周期内有效。') !== false;
      if (!approved) { await api.tabbitAccess(id, 'deny'); tabbitOpen = false; return; }
      const access = await api.tabbitAccess(id, 'approve');
      if (access.accepted !== true) throw new Error('Tabbit 页面访问授权未生效。');
      tabbitGrants.add(id);
    }
    const result = await api.tabbitTabs(id, query, 50);
    if (request !== tabbitRequest) return;
    tabbitCandidates = Array.isArray(result.items) ? result.items.filter((item) => !state.tabbitTabs.some((selected) => selected.tab_id === item.tab_id && selected.instance_id === item.instance_id)) : [];
  } catch (error) {
    if (request === undefined || request === tabbitRequest) state.error = error?.message || 'Tabbit 标签页列表不可用。';
  } finally {
    if (request === undefined || request === tabbitRequest) { tabbitLoading = false; render(); }
  }
}

function selectTabbit(tabId) {
  const item = tabbitCandidates.find((candidate) => candidate.tab_id === Number(tabId));
  if (!item) return;
  try {
    controller.addTabbit(item);
    controller.setDraft(removeTabbitMentionQuery(state.draft));
    tabbitOpen = false; tabbitCandidates = []; tabbitIndex = 0; render();
    document.querySelector('#prompt')?.focus();
  } catch (error) { state.error = error.message; render(); }
}

function handleInput(event) {
  if (event.target.closest?.('[data-asset-research]')) { void assetResearch.handle(event); return; }
  if (event.target.closest?.('.scenario-panel')) { void scenarioController.handle(event); return; }
  if (event.target.closest?.('.discovery-page')) { void discoveryController.handle(event); return; }
  if (event.target.closest?.('[data-dossier-workspace]')) { void dossierController.handle(event); return; }

  if (state.route.page === 'market' && marketController.handleInput(event)) return;
  if (event.target.matches?.('[data-asset-list-query]')) { const query = event.target.value.trim().toUpperCase(); for (const row of root.querySelectorAll('[data-asset-list-code]')) row.hidden = !row.dataset.assetListCode.includes(query); return; }
  const hotForm=event.target.closest?.('[data-hot-form]');
  if(hotForm)hotForm.dataset.hotDirty='true';
  const draftForm = event.target.closest?.('[data-claw-draft-form]');
  if (draftForm) { clawDraftEdits.set(draftForm.dataset.clawDraftForm, captureAutomationDraftEdits(new FormData(draftForm), clawDraftEdits.get(draftForm.dataset.clawDraftForm))); return; }
  if (event.target.closest?.('[data-claw-project-create]')) { clawWorkspace.newName = event.target.value; return; }
  const renameForm = event.target.closest?.('[data-claw-project-update]');
  if (renameForm) { clawWorkspace.renameEdits.set(renameForm.dataset.clawProjectUpdate, event.target.value); return; }
  if (event.target.matches?.('[data-intel-query], [data-intel-code]')) { void intelController.handle(event); return; }
  const documentForm = event.target.closest?.('#document-edit-form');
  if (documentForm && documentEditor) {
    const fields = new FormData(documentForm);
    documentEditor.draft = { target: Number(fields.get('target')), value: String(fields.get('value') || ''), mode: String(fields.get('mode')), value_type: String(fields.get('value_type') || 'string') };
    return;
  }
  const creationForm = event.target.closest?.('#document-create-form');
  if (creationForm && documentEditor?.creating && !documentEditor.busy) {
    documentEditor.draft = Object.fromEntries(new FormData(creationForm));
    return;
  }
  const modelForm = event.target.closest?.('#settings-form');
  if (modelForm) modelForm.dataset.dirty = 'true';
  if (event.target.id === 'framework-bot-input') frameworkBot.draft = event.target.value;
  if (event.target.id === 'composer-command-search') { composerMenu.query = event.target.value; composerMenu.index = 0; if (!event.isComposing) render(); return; }
  if (event.target.id === 'prompt') {
    controller.setDraft(event.target.value);
    for (const button of root.querySelectorAll('[data-retry-round]')) button.disabled = Boolean(retryBlockReason());
    const wasCommandOpen = Boolean(composerMenu.entry);
    if (state.route.page === 'claw' && !state.detail?.execution_context && !event.isComposing) {
      const query = composerSlashQuery(event.target.value);
      composerMenu = query === null ? closedComposerMenu() : openComposerMenu('slash', 'root', query);
      if (composerMenu.entry) { tabbitOpen = false; tabbitCandidates = []; tabbitRequest += 1; }
    }
    const wasOpen = slashOpen; slashOpen = state.route.page !== 'claw' && event.target.value.trimStart().startsWith('/'); slashIndex = 0;
    const query = tabbitMentionQuery(event.target.value);
    if (query !== null && !slashOpen && !composerMenu.entry) void loadTabbitCandidates(query);
    else {
      const wasTabbitOpen = tabbitOpen;
      tabbitOpen = false; tabbitLoading = false; tabbitCandidates = []; tabbitRequest += 1;
      if (slashOpen || wasOpen || wasTabbitOpen || composerMenu.entry || wasCommandOpen) render();
    }
  }
  if (event.target.closest('#cap-editor-form')) captureEditor();
  if (event.target.closest('#cap-creation-form')) capabilityState.goal = event.target.value;
  if (event.target.closest('#cap-copy-form')) capabilityState.copy = { name: document.querySelector('#cap-copy-name')?.value || '', slug: document.querySelector('#cap-copy-slug')?.value || '' };
  if ('capQuery' in event.target.dataset) { capabilityState.query = event.target.value; render(); }
  if ('mcpQuery' in event.target.dataset) {
    invalidateMCPDetailRequest();
    mcpCatalogGeneration += 1; mcpMarketplaceState.loading = false; mcpMarketplaceState.syncing = false;
    mcpMarketplaceState.query = event.target.value; mcpMarketplaceState.page = null; render();
  }
  if ('mcpPublisherSource' in event.target.dataset) {
    mcpPublisherGeneration += 1; mcpMarketplaceState.publisher.busy = false;
    mcpMarketplaceState.publisher.source = event.target.value; mcpMarketplaceState.publisher.result = null; mcpMarketplaceState.publisher.resultSource = ''; mcpMarketplaceState.publisher.error = '';
    render();
  }
  if ('globalSearch' in event.target.dataset) {
    // IME composition must not rebuild the popover under the composing text;
    // update only the results list so the input keeps focus and composition.
    globalSearch = event.target.value;
    if (event.isComposing) return;
    event.target.setAttribute?.('aria-expanded', globalSearch.trim() ? 'true' : 'false');
    if (state.route.page === 'claw') nativeSessionSearch.update(globalSearch, 'claw');
    else updateGlobalSearchResults();
  }
  if (event.target.id === 'rename-title') renameDraft = event.target.value;
  if ('connectionSearch' in (event.target.dataset || {})) applyConnectionWorkspaceFilters(event.target.closest('[data-connection-workbench]'));
  const projectEditor = event.target.closest?.('[data-nav-project-form]');
  if (projectEditor && conversationNavigation.state(state.route.page)?.editor) { conversationNavigation.state(state.route.page).editor.name = event.target.value; return; }
  const form = event.target.closest('[data-question-form]');
  if (form) {
    const question = state.detail?.questions?.find((item) => item.id === form.dataset.questionForm);
    if (question) captureQuestionForm(form, questionDrafts, state.detail.id, question);
  }
  if (event.target.id === 'history-search') {
    historyFilter = event.target.value;
    const view = state.route.historyView || 'active';
    const sessions = view === 'deleted' ? catalog.deletedSessions : catalog.sessions;
    const historyResults = document.querySelector('#history-results');
    if (historyResults) historyResults.innerHTML = renderHistory(sessions, historyFilter, state.route.historyMode, view);
  }
}
root.addEventListener('input', handleInput);
root.addEventListener('compositionstart', event => { composingInput = event.target; });
root.addEventListener('compositionend', event => {
  composingInput = null;
  handleInput(event);
  if (renderAfterComposition) { renderAfterComposition = false; render(); }
});

root.addEventListener('keydown', (event) => {
  if (scenarioController.state.open && scenarioController.key(event)) return;
  if (event.target.closest?.('.discovery-page')) {
    if (event.isComposing || event.keyCode === 229) return;
    const drawerKind = discoveryController.state.drawer?.kind;
    if (event.key === 'Tab' && discoveryController.state.drawer) {
      const dialog = root.querySelector('.d-drawer');
      const items = [...(dialog?.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)') || [])];
      if (items.length && (!items.includes(document.activeElement) || event.shiftKey && document.activeElement === items[0] || !event.shiftKey && document.activeElement === items.at(-1))) { event.preventDefault(); (event.shiftKey ? items.at(-1) : items[0]).focus({ preventScroll: true }); }
      return;
    }
    void discoveryController.handle(event).then(handled => {
      if (handled && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) root.querySelector(`#discovery-tab-${discoveryController.state.tab}`)?.focus({ preventScroll: true });
      if (handled && event.key === 'Escape' && drawerKind) root.querySelector(`[data-discovery-action="${drawerKind === 'tracking' ? 'tracking' : 'research'}"]`)?.focus({ preventScroll: true });
    });
    return;
  }
  if (state.route.page === 'claw' && composerMenu.entry && (event.target.id === 'prompt' || event.target.closest?.('#claw-composer-menu'))) {
    if (event.isComposing || event.keyCode === 229) return;
    if (event.key === 'Enter' && event.target.closest?.('[data-cm-back], [data-cm-done]')) return;
    const rows = currentComposerRows();
    const clickedIndex = event.target.dataset?.cmRow;
    const index = clickedIndex === undefined ? composerMenu.index : Number(clickedIndex);
    const result = composerMenuKey(event.key, index, rows);
    if (result.handled) {
      event.preventDefault();
      if (result.back) backComposerMenu();
      else if (result.select) void activateComposerRow(result.select);
      else if (result.index !== undefined) {
        composerMenu.index = result.index; render();
        if (clickedIndex !== undefined) document.getElementById(`composer-command-${result.index}`)?.focus({ preventScroll: true });
        document.getElementById(`composer-command-${result.index}`)?.scrollIntoView({ block: 'nearest' });
      }
      return;
    }
  }

  if (isAssetPage()) {
    const metrics = root.querySelector('.asset-wind-metrics.is-open');
    if (metrics && event.key === 'Escape') { event.preventDefault(); setAssetMetricsDrawer(false); return; }
    if (metrics && event.key === 'Tab') {
      const focusable = [...metrics.querySelectorAll('button, a[href], input, select, textarea, [tabindex="0"]')].filter(item => !item.disabled);
      const first = focusable[0]; const last = focusable.at(-1);
      if (event.shiftKey && document.activeElement === first || !event.shiftKey && document.activeElement === last) { event.preventDefault(); (event.shiftKey ? last : first)?.focus(); return; }
    }
    if (event.key === 'Escape') {
      const menu = event.target.closest?.('.asset-header-actions details[open]');
      if (menu) { event.preventDefault(); menu.open = false; menu.querySelector('summary')?.focus(); return; }
    }
  }
  if (state.route.page === 'aihot' && event.key === 'Escape') root.querySelectorAll('.aihot-faces[open]').forEach(item => { item.open = false; });
  if (event.isComposing || event.keyCode === 229) return;
  if (event.target.type === 'radio' && event.target.matches?.('.codex-question-option input') && ['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(event.key)) {
    event.preventDefault();
    const form = event.target.closest('[data-question-form]');
    const question = state.detail?.questions?.find(item => item.id === form.dataset.questionForm);
    if (!question || form.dataset.qSession !== state.detail.id || state.busy) return;
    const inputs = [...form.querySelectorAll('input[type="radio"]')];
    const direction = ['ArrowUp', 'ArrowLeft'].includes(event.key) ? -1 : 1;
    const next = inputs[(inputs.indexOf(event.target) + direction + inputs.length) % inputs.length];
    try { next.checked = true; captureQuestionForm(form, questionDrafts, state.detail.id, question); next.focus(); }
    catch (error) { safeLog('question_option_failed'); state.error = error.message || '无法保存选项，请重试。'; render(); }
    return;
  }
  if (['radio', 'checkbox'].includes(event.target.type) && event.target.matches?.('.codex-question-option input') && ['Enter', ' '].includes(event.key)) {
    event.preventDefault();
    if (!event.repeat) event.target.click();
    return;
  }
  if (searchOpen && event.key === 'Escape') { event.preventDefault(); closeGlobalSearch(); return; }
  const assetTab = event.target.closest?.('[data-asset-tab]');
  const nextAssetTopic = assetTab && (['Enter', ' '].includes(event.key) ? assetTab.dataset.assetTab : assetTopicKey(event.key, assetTab.dataset.assetTab));
  if (isAssetPage() && nextAssetTopic) {
    event.preventDefault();
    root.querySelector(`[data-asset-tab="${nextAssetTopic}"]`)?.focus({ preventScroll: true });
    location.hash = assetHref(state.route.asset || assetState.observation?.asset || '', state.route.assetType || 'stock', nextAssetTopic);
    return;
  }
  const projectDialog = event.target.closest?.('.nav-project-dialog');
  const projectEditorState = conversationNavigation.state(state.route.page);
  if (projectDialog && projectEditorState?.editor) {
    if (event.key === 'Escape') { event.preventDefault(); closeProjectEditor(); return; }
    if (event.key === 'Tab') {
      const controls = [...projectDialog.querySelectorAll('input:not(:disabled),button:not(:disabled)')];
      if (!controls.length) { event.preventDefault(); projectDialog.focus({ preventScroll: true }); return; }
      const first = controls[0], last = controls.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      return;
    }
  }
  const activeMenu = event.target.closest?.('.conversation-action-menu[role="menu"]');
  if (activeMenu && ['ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
    const choices = [...activeMenu.querySelectorAll('button[role="menuitem"]:not(:disabled),button[role="menuitemradio"]:not(:disabled),a[role="menuitem"]')].filter(node => node.closest('[role="menu"]') === activeMenu);
    if (choices.length) {
      event.preventDefault(); const current = choices.indexOf(event.target.closest('button,a'));
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? choices.length - 1 : (current + (event.key === 'ArrowDown' ? 1 : -1) + choices.length) % choices.length;
      choices[next].focus({ preventScroll: true }); choices[next].scrollIntoView?.({ block: 'nearest', inline: 'nearest' }); return;
    }
  }
  if (event.key === 'ArrowRight' && event.target.matches?.('[data-nav-move-menu]')) { event.preventDefault(); event.target.click(); return; }
  if (sessionMenu?.move && ['Escape', 'ArrowLeft'].includes(event.key)) {
    event.preventDefault(); cancelProjectMenuTimers(); sessionMenu.move = null; paintSessionMenu({ focusParent: true }); return;
  }
  const projectMenuState = conversationNavigation.state(state.route.page);
  if (projectMenuState?.menu && event.key === 'Escape') {
    event.preventDefault(); const id = projectMenuState.menu; projectMenuState.menu = null; render();
    [...root.querySelectorAll('[data-nav-project-menu]')].find(node => node.dataset.navProjectMenu === id)?.focus?.({ preventScroll: true }); return;
  }
  if (sessionMenu && event.key === 'Escape') {
    event.preventDefault(); const id = sessionMenu.id; sessionMenu = null; render();
    [...root.querySelectorAll('[data-session-menu]')].find(node => node.dataset.sessionMenu === id)?.focus?.({ preventScroll: true }); return;
  }
  const modelMenu = root.querySelector('.composer-model-menu[open]');
  if (event.key === 'Escape' && modelMenu) { event.preventDefault(); modelMenu.open = false; modelMenu.querySelector('summary')?.focus(); return; }
  if (modelMenu && event.target.closest?.('.composer-model-menu') && ['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
    const choices = [...modelMenu.querySelectorAll('[data-composer-model]:not(:disabled)')];
    if (choices.length) {
      event.preventDefault();
      const current = choices.indexOf(document.activeElement);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? choices.length - 1 : current < 0 ? (event.key === 'ArrowUp' ? choices.length - 1 : 0) : (current + (event.key === 'ArrowUp' ? -1 : 1) + choices.length) % choices.length;
      choices[next].focus();
    }
    return;
  }
  const legacyComposerMenu = root.querySelector('.composer-more[open]');
  if (event.key === 'Escape' && legacyComposerMenu) { event.preventDefault(); legacyComposerMenu.open = false; legacyComposerMenu.querySelector('summary')?.focus(); return; }
  if (state.route.page === 'intel' && event.key === 'Escape' && intelController.state.detailId) { event.preventDefault(); intelController.closeDetail(); document.querySelector('.intel-tabs [aria-current="page"]')?.focus({ preventScroll: true }); return; }
  if (mcpMarketplaceState.detail && event.key === 'Tab') {
    const dialog = document.querySelector('.mcp-server-dialog');
    const focusable = [...(dialog?.querySelectorAll?.('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)') || [])];
    if (focusable.length) {
      const first = focusable[0]; const last = focusable.at(-1);
      if (!dialog.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault(); (event.shiftKey ? last : first).focus({ preventScroll: true });
      }
    }
    return;
  }
  if (mcpMarketplaceState.detail && event.key === 'Escape') { event.preventDefault(); closeMCPServerDialog(); return; }
  if (capabilityPreviewIsOpen() && event.key === 'Tab') {
    const dialog = document.querySelector('.capability-preview-dialog');
    const focusable = [...(dialog?.querySelectorAll?.('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled)') || [])];
    if (focusable.length) {
      const first = focusable[0]; const last = focusable.at(-1);
      if (!dialog.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault(); (event.shiftKey ? last : first).focus({ preventScroll: true });
      }
    }
    return;
  }
  if (capabilityPreviewIsOpen() && event.key === 'Escape') {
    event.preventDefault(); closeCapabilityPreview(); return;
  }
  if ('capKindNav' in (event.target.dataset || {})) {
    const result = capabilityWorkspaceKindKey(event.key, event.target.dataset.capKindNav);
    if (result.handled) {
      event.preventDefault();
      const target = document.getElementById(`capability-kind-${result.kind}`);
      if (target) { target.click(); target.focus({ preventScroll: true }); }
      return;
    }
  }
  if ('mcpMarketTab' in (event.target.dataset || {})) {
    const result = mcpMarketplaceTabKey(event.key, event.target.dataset.mcpMarketTab);
    if (result.handled) {
      event.preventDefault();
      const target = document.getElementById(`capability-tool-tab-${result.view}`);
      if (target) { pendingMCPMarketTabFocus = result.view; target.click(); }
      return;
    }
  }
  if ('connectionGroup' in (event.target.dataset || {}) && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
    const tabs = [...event.target.closest('[role="tablist"]')?.querySelectorAll('[data-connection-group]') || []];
    if (tabs.length) {
      event.preventDefault();
      const current = tabs.indexOf(event.target);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 : (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      tabs[next].click();
      tabs[next].focus({ preventScroll: true });
    }
    return;
  }
  if ('capKind' in (event.target.dataset || {})) {
    const result = capabilityTabKey(event.key, event.target.dataset.capKind);
    if (result.handled) {
      event.preventDefault();
      const cap = capabilityState;
      cap.kind = result.kind; cap.kindFilter = result.kind; cap.category = ''; cap.query = ''; cap.dataDetail = null; cap.dataDetailKind = '';
      render(); document.getElementById(`capability-tab-${result.kind}`)?.focus({ preventScroll: true }); return;
    }
  }
  if (event.target.id === 'prompt' && tabbitOpen && !event.isComposing) {
    const result = tabbitKey(event.key, tabbitIndex, tabbitCandidates);
    if (result.handled) {
      event.preventDefault();
      if (result.select !== undefined) selectTabbit(result.select);
      else { if (result.close) tabbitOpen = false; if (result.index !== undefined) tabbitIndex = result.index; render(); }
      return;
    }
  }
  if (state.route.page !== 'claw' && event.target.id === 'prompt' && (slashOpen || state.draft.trimStart().startsWith('/')) && !event.isComposing) {
    const result = slashKey(event.key, slashIndex, currentSlashMatches());
    if (result.handled) {
      event.preventDefault();
      if (result.select) void selectCapability(result.select);
      else { if (result.close) slashOpen = false; if (result.index !== undefined) slashIndex = result.index; render(); }
      return;
    }
  }
  if (event.target.id === 'prompt' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); document.querySelector('#composer')?.requestSubmit(); }
  if (event.target.id === 'global-search' && ['ArrowDown', 'Enter'].includes(event.key)) {
    const first = document.querySelector('#global-search-results [data-global-result]');
    if (first) { event.preventDefault(); if (event.key === 'Enter') first.click(); else first.focus({ preventScroll: true }); }
    return;
  }
  if (['ArrowUp', 'ArrowDown'].includes(event.key) && event.target.matches?.('[data-global-result]')) {
    const items = [...document.querySelectorAll('#global-search-results [data-global-result]')];
    const index = items.indexOf(event.target) + (event.key === 'ArrowDown' ? 1 : -1);
    const next = index < 0 ? document.querySelector('#global-search') : items[Math.min(index, items.length - 1)];
    if (next) { event.preventDefault(); next.focus({ preventScroll: true }); }
    return;
  }
  if (event.key === 'Escape') {
    const workbench = event.target.closest?.('[data-connection-workbench]') || document.querySelector('[data-connection-workbench]');
    if (closeConnectionDrawer(workbench)) { event.preventDefault(); return; }
    event.preventDefault();
    const wasSearchOpen = searchOpen; nativeSessionSearch.close();
    const focusSession = sessionMenu?.id || renameSession?.id || deleteSession?.id || purgeSession?.id;
    const wasSidebarOpen = sidebarOpen;
    sidebarOpen = false; contextOpen = false; slashOpen = false; tabbitOpen = false; tabbitCandidates = []; tabbitRequest += 1; globalSearch = ''; searchOpen = false;
    renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionMenu = null; sessionActionError = '';
    render();
    if (wasSearchOpen) document.querySelector(window.matchMedia('(max-width: 1050px)').matches ? '.topbar .menu-toggle' : '.primary-rail .search-trigger')?.focus({ preventScroll: true });
    if (focusSession) document.querySelector(`[data-session-menu="${focusSession}"]`)?.focus({ preventScroll: true });
    else if (wasSidebarOpen) focusSidebarControl(document, window.matchMedia('(max-width: 1050px)').matches);
  }
});

async function configureComposerModel(value) {
  if (state.busy || state.stopping) return;
  try {
    const selection = JSON.parse(value);
    if (selection.provider === 'openai-compatible') {
      const connection = catalog.runtime?.connection;
      if (!connection) { safeLog('compatible_connection_missing'); return; }
      for (const name of ['base_url', 'protocol', 'credential_mode']) selection[name] = connection[name];
    }
    const result = await controller.action(() => api.configure(selection), { refreshAfter: false });
    if (result?.configured) { success = state.detail ? '默认模型已更新，下次新研究生效；当前会话仍使用原模型。' : '默认模型已更新，新研究将使用此模型。'; await loadCatalog(['runtime']); }
    return Boolean(result?.configured);
  } catch { safeLog('composer_model_selection_failed'); state.error = '模型选择失败，请刷新模型目录后重试。'; render(); }
}

root.addEventListener('change', async (event) => {
  // This local filter form is submitted explicitly; generic redraw would discard its values.
  if (event.target.closest?.('[data-report-directory-filter]')) return;
  if (event.target.matches?.('[data-report-run-select]')) {
    history.pushState(null, '', reportHref(state.route.reportProjectId, 'production', event.target.value));
    await showRoute(); return;
  }

  if(event.target.closest?.('[data-asset-research]') && await assetResearch.handle(event))return;
  if (event.target.closest?.('.scenario-panel') && await scenarioController.handle(event)) return;
  if (event.target.closest?.('.discovery-page') && await discoveryController.handle(event)) return;
  if (event.target.closest?.('[data-dossier-workspace]') && await dossierController.handle(event)) return;

  if (state.route.page === 'market' && await marketController.handleChange(event)) return;
  if (event.target.matches?.('[data-etf-run]')) {
    if (!event.target.value || workbenchBusy) return;
    const current = workbenchOwner();
    workbenchBusy = true;
    try { const result = await api.etfRun(event.target.value); if (current()) etfState.result = result; }
    catch (error) { if (current()) state.error = error.message; safeLog('etf_paper_detail_failed'); }
    finally { if (current()) { workbenchBusy = false; render(); } }
    return;
  }
  if (event.target.closest?.('.intel-page') && await intelController.handle(event)) return;
  const target = event.target;
  const questionForm = target.closest?.('[data-question-form]');
  if (questionForm) { const question = state.detail?.questions?.find(q => q.id === questionForm.dataset.questionForm); if (question) captureQuestionForm(questionForm, questionDrafts, state.detail.id, question); }
  if (target.matches?.('[data-nav-move-session]')) { const mode = state.route.page; sessionMenu = null; await conversationNavigation.moveSession(mode, target.dataset.navMoveSession, target.value); return; }
  if('hotMaterial' in (target.dataset||{})){hotController.selectMaterial(target.value,target.checked);return;}

  if (target.matches?.('[data-claw-project-select]')) {
    history.pushState(null, '', `#/${state.route.page}?view=projects&project=${encodeURIComponent(target.value)}`);
    await showRoute(); return;
  }
  if (target.matches?.('[data-claw-session-project]') && target.value) {
    const sid = target.dataset.clawSessionProject; const projectId = target.value;
    await clawAction(async () => { await api.moveClawSession(sid, projectId); await loadClawProjects(); await loadCatalog(['sessions']); }); return;
  }
  if (target.matches?.('[data-claw-reference-target]')) { clawWorkspace.targetSession = target.value; return; }
  const changedDraft = target.closest?.('[data-claw-draft-form]');
  if (changedDraft) { clawDraftEdits.set(changedDraft.dataset.clawDraftForm, captureAutomationDraftEdits(new FormData(changedDraft), clawDraftEdits.get(changedDraft.dataset.clawDraftForm))); if (target.name === 'kind') render(); return; }
  if (target.matches?.('[data-document-target]') && documentEditor) {
    const selected = documentTargets(documentEditor.result)[Number(target.value)];
    const input = target.closest('form')?.querySelector('textarea[name=value]');
    if (selected && input) {
      input.value = String(selected.value);
      const type = target.closest('form')?.querySelector('select[name=value_type]');
      if (type) type.value = typeof selected.value === 'number' ? 'number' : typeof selected.value === 'boolean' ? 'boolean' : 'string';
      documentEditor.draft = null;
    }
    return;
  }
  if ('connectionStatus' in (target.dataset || {})) applyConnectionWorkspaceFilters(target.closest('[data-connection-workbench]'));
  if ('researchSource' in target.dataset) { const values = target.checked ? [...state.sourceScope, target.dataset.researchSource] : state.sourceScope.filter(s => s !== target.dataset.researchSource); if (values.length) controller.setSourceScope(values); render(); }
  if (target.id === 'research-depth') { controller.setResearchMode(target.value); render(); }
  if (target.id === 'research-as-of') { controller.setResearchAsOf(target.value); render(); }
  if (target.id === 'workspace-select') selectedWorkspace = target.value;
  if ('quickCategory' in target.dataset) { quickCategory = target.value; render(); }
  if (target.id === 'skill-select') { if (target.value) await selectCapability(target.value); else { controller.setCapability(null); render(); } }
  if ('methodId' in target.dataset) {
    const id = target.dataset.methodId;
    methodPickerOpen = true;
    controller.setMethods(target.checked ? [...state.methodIds, id] : state.methodIds.filter(value => value !== id));
    render();
  }
  if ('capSource' in target.dataset) { capabilityState.source = target.value; render(); }
  if ('capCategory' in target.dataset) { capabilityState.category = target.value; render(); }
  if ('capStatus' in target.dataset) { capabilityState.status = target.value; render(); }
  if ('dataCategory' in target.dataset) { capabilityState.category = target.value; render(); }
  if ('dataMarket' in target.dataset) { capabilityState.dataMarket = target.value; render(); }
  if ('dataStatus' in target.dataset) { capabilityState.dataStatus = target.value; render(); }
  if ('dataAuth' in target.dataset) { capabilityState.dataAuth = target.value; render(); }
  if ('mcpRegistry' in target.dataset) {
    const preserveContextFocus = document.activeElement === target;
    invalidateMCPDetailRequest();
    mcpMarketplaceState.selectedRegistryId = target.value;
    mcpMarketplaceState.page = null; mcpMarketplaceState.detail = null; mcpMarketplaceState.error = '';
    await loadMCPMarketplace();
    if (preserveContextFocus && currentMCPMarketRoute() && (!document.activeElement?.id || document.activeElement.id === target.id)) {
      document.getElementById(target.id)?.focus?.({ preventScroll: true });
    }
  }
  if ('mcpInstallTarget' in target.dataset) {
    mcpInstallGeneration += 1;
    mcpMarketplaceState.installation = { ...emptyMCPInstallation(), target: target.value };
    render();
  }
  if ('mcpRiskSelect' in target.dataset) {
    const checkbox = target.closest('[data-mcp-tool-policy]')?.querySelector('[name="allow_unattended"]');
    if (checkbox) {
      checkbox.disabled = target.value !== 'read_only';
      if (checkbox.disabled) checkbox.checked = false;
    }
  }
  if (target.closest('#cap-editor-form')) captureEditor();
  if (target.id === 'cap-import-file' && target.files?.length) await capabilityController.import(target.files[0]);
  if ('autoFormats' in target.dataset) { controller.setFormats(target.checked ? null : []); render(); }
  if ('format' in target.dataset) {
    const selected = [...root.querySelectorAll('[data-format]:checked')].map((input) => input.dataset.format);
    controller.setFormats(selected); render();
    root.querySelector('.format-picker')?.setAttribute('open', '');
  }
  if (target.id === 'provider' || target.name === 'credential_mode') { syncModelForm(target.closest('form'), { clearKey: true }); target.closest('form').dataset.dirty = 'true'; }
  if (target.id === 'settings-model' && target.value) {
    try { const selected = JSON.parse(target.value); document.querySelector('#provider').value = selected.provider; document.querySelector('#model-id').value = selected.model; syncModelForm(target.closest('form'), { clearKey: true }); target.closest('form').dataset.dirty = 'true'; }
    catch { safeLog('invalid_model_selection'); }
  }
  if (target.id === 'model-select' && target.value) {
    await configureComposerModel(target.value);
  }
  if (target.id === 'file-input' && target.files?.length) await uploadFiles([...target.files]);
});

root.addEventListener('toggle', (event) => {
  if (state.route.page === 'aihot' && event.target.isConnected && event.target.dataset?.aihotMonth) aihotController.toggleMonth(event.target.dataset.aihotMonth, event.target.open);
  if (state.route.page === 'aihot' && event.target.isConnected && event.target.matches?.('.aihot-faces[open]')) {
    const popup = event.target.querySelector('.aihot-participants');
    const box = event.target.querySelector('summary').getBoundingClientRect();
    if (popup) {
      const width = Math.min(280, window.innerWidth - 16);
      Object.assign(popup.style, { position: 'fixed', width: `${width}px`, left: `${Math.min(Math.max(8, box.left), window.innerWidth - width - 8)}px`, top: `${window.innerHeight - box.bottom > 260 ? box.bottom + 6 : Math.max(8, box.top - 266)}px` });
    }
  }
  if (event.target.matches?.('.method-picker')) methodPickerOpen = event.target.open;
}, true);

root.addEventListener('error', (event) => {
  if (event.target.matches?.('.aihot-page img')) event.target.hidden = true;
}, true);

const uploadFiles = createUploadHandler({
  state, ensureSession,
  upload: (id, files) => controller.action(() => api.upload(id, files)),
  accept: (id, files) => controller.addAttachmentsForSession(id, files),
  notify: message => { state.error = message; render(); },
  logger: safeLog,
});

root.addEventListener('dragstart', event => {
  const row = event.target.closest?.('[data-nav-sortable]');
  if (!row || event.target.closest?.('button') || conversationNavigation.state(state.route.page)?.busy) return;
  event.dataTransfer?.setData('application/x-rwb-navigation', JSON.stringify({ mode: state.route.page, group: row.dataset.navSortable, entity: { kind: row.dataset.navEntity, id: row.dataset.navId } }));
});
root.addEventListener('dragover', event => {
  const row = event.target.closest?.('[data-nav-sortable]'); if (!row || ![...(event.dataTransfer?.types || [])].includes('application/x-rwb-navigation')) return;
  event.preventDefault(); event.dataTransfer.dropEffect = 'move'; row.classList.add('nav-drop-target');
});
root.addEventListener('dragleave', event => event.target.closest?.('[data-nav-sortable]')?.classList.remove('nav-drop-target'));
root.addEventListener('drop', async event => {
  const row = event.target.closest?.('[data-nav-sortable]'); if (!row || ![...(event.dataTransfer?.types || [])].includes('application/x-rwb-navigation')) return;
  event.preventDefault(); row.classList.remove('nav-drop-target');
  try {
    const source = JSON.parse(event.dataTransfer.getData('application/x-rwb-navigation'));
    if (source.mode !== state.route.page || source.group !== row.dataset.navSortable) return;
    await conversationNavigation.reorder(source.mode, source.group, source.entity, { kind: row.dataset.navEntity, id: row.dataset.navId });
  } catch { safeLog('navigation_drop_rejected'); }
});
root.addEventListener('dragover', (event) => {
  if (!event.target.closest('[data-dropzone]')) return;
  event.preventDefault();
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'copy';
});

root.addEventListener('drop', (event) => {
  if (!event.target.closest('[data-dropzone]')) return;
  event.preventDefault();
  void uploadFiles([...(event.dataTransfer?.files || [])]);
});

root.addEventListener('paste', (event) => {
  if (!event.target.closest('[data-paste-support]')) return;
  const files = [...(event.clipboardData?.files || [])];
  if (!files.length) return;
  event.preventDefault();
  void uploadFiles(files);
});

root.addEventListener('submit', async (event) => {
  if (event.target.matches?.('[data-report-directory-filter]')) {
    event.preventDefault(); const values = new FormData(event.target);
    const params = new URLSearchParams({ q: String(values.get('q') || '').slice(0, 120), status: String(values.get('status') || 'all') });
    history.pushState(null, '', `#/reports?${params}`); await showRoute(); return;
  }

  if (event.target.closest?.('.scenario-panel') && await scenarioController.handle(event)) return;
  if (event.target.closest?.('.discovery-page') && await discoveryController.handle(event)) return;
  if (event.target.closest?.('[data-dossier-workspace]') && await dossierController.handle(event)) return;

  if (state.route.page === 'market' && await marketController.handleSubmit(event)) return;
  if (event.target.matches?.('[data-asset-select]')) {
    event.preventDefault(); const data = new FormData(event.target);
    location.hash = assetHref(String(data.get('asset') || '').trim(), String(data.get('asset_type') || 'stock'), state.route.assetView || 'overview'); return;
  }
  if (event.target.matches?.('[data-asset-list-filter]')) { event.preventDefault(); return; }
  if (event.target.matches?.('[data-asset-watchlist-create]')) {
    event.preventDefault(); const name = String(new FormData(event.target).get('name') || '').trim(); if (!name) return;
    try { await api.createWatchlist({ name }); await loadAssetWorkspace(); }
    catch (error) { state.error = error.message; safeLog('asset_watchlist_create_failed'); } render(); return;
  }

  if(event.target.matches?.('[data-news-form]')) {
    event.preventDefault(); await aihotController.management.submit(event.target,event.submitter);return;
  }
  if (event.target.matches?.('[data-etf-replay]')) {
    event.preventDefault();
    if (workbenchBusy) return;
    const file = new FormData(event.target).get('snapshot');
    if (!file || file.size > 8 * 1024 * 1024) { state.error = '输入文件须小于 8 MiB'; render(); return; }
    const current = workbenchOwner();
    workbenchBusy = true; state.error = ''; render();
    try {
      const body = JSON.parse(await file.text());
      if (!current()) return;
      const result = await api.etfReplay(body, crypto.randomUUID());
      if (!current()) return;
      etfState.result = result;
      await loadWorkbench();
    } catch (error) { if (current()) state.error = error.message; safeLog('etf_paper_replay_failed'); }
    finally { if (current()) { workbenchBusy = false; render(); } }
    return;
  }
  if (event.target.closest?.('.intel-page') && await intelController.handle(event)) return;
  event.preventDefault();
  if(event.target.matches('[data-hot-form]')){await hotController.submit(event.target);return;}
  safeLog('document_form_dispatch', { status: event.target.id === 'document-edit-form' ? 'document' : 'other' });
  if (event.target.matches('[data-nav-project-form]')) {
    const mode = state.route.page; const editor = conversationNavigation.state(mode).editor;
    if (editor) {
      const saved = await conversationNavigation.projectSave(mode, String(new FormData(event.target).get('name') || ''), editor.id);
      if (saved && state.route.page === mode) root.querySelector('[data-nav-project-create]')?.focus({ preventScroll: true });
    }
    return;
  }
  if (event.target.matches('[data-claw-project-create]')) {
    const name = String(new FormData(event.target).get('name') || '');
    const ticket = pageGeneration;
    await clawAction(async () => {
      const project = await api.createProject(state.route.page, { name }); clawWorkspace.newName = '';
      if (!clawNavigationCurrent(ticket, pageGeneration)) return;
      history.pushState(null, '', `#/${state.route.page}?view=projects&project=${encodeURIComponent(project.id)}`); await showRoute();
    }); return;
  }
  if (event.target.matches('[data-claw-project-update]')) {
    const projectId = event.target.dataset.clawProjectUpdate; const name = String(new FormData(event.target).get('name') || '');
    await clawAction(async () => { await api.updateProject(state.route.page, projectId, { name }); clawWorkspace.renameEdits.delete(projectId); await loadClawProjects(); }); return;
  }
  if (event.target.matches('[data-claw-draft-form]')) {
    const sid = state.detail?.id; const draftId = event.target.dataset.clawDraftForm;
    const draft = state.detail?.automation_drafts?.find(d => d.id === draftId);
    if (!sid || !draft || clawWorkspace.busy) return;
    let body;
    try { body = draft.operation === 'update' || draft.status === 'confirmed' ? structuredClone(draft.body) : automationDraftBody(draft.body, new FormData(event.target)); }
    catch (error) { state.error = error.message; render(); return; }
    const ticket = pageGeneration;
    await clawAction(async () => {
      let result;
      try { result = await api.confirmAutomationDraft(sid, draftId, body, draft.operation !== 'update' && (draft.body.target_kind === 'research_task' || Boolean(draft.body.research_task))); }
      catch (error) { if (ticket === pageGeneration && state.detail?.id === sid) await controller.refresh(); throw error; }
      if (ticket !== pageGeneration || state.detail?.id !== sid) return;
      clawDraftEdits.delete(draftId);
      success = result.enabled === false ? '任务已保存但尚未启用，请重试启用。' : '日程定义已确认。';
      await controller.refresh(); await loadCatalog(['automations', 'automationRuns']);
    }); return;
  }
  if (event.target.id === 'document-create-form') {
    const editor = documentEditor; if (!editor || editor.busy || editor.sessionId !== state.detail?.id) return;
    editor.draft = Object.fromEntries(new FormData(event.target));
    let body; try { body = documentCreationPayload({ ...editor.draft, format: editor.creating }); }
    catch (error) { editor.error = error.message; render(); return; }
    editor.busy = true; editor.error = ''; render();
    try {
      const result = await api.documentOperation(editor.sessionId, body);
      if (documentEditor !== editor || editor.sessionId !== state.detail?.id) return;
      editor.lastResult = result;
      if (result.status !== 'completed' || !result.output) { editor.error = '生成未完成：' + (result.code || result.status); return; }
      const read = await api.documentOperation(editor.sessionId, { format: body.format, operation: 'read', mode: 'file', file_id: result.output.id });
      if (documentEditor !== editor || editor.sessionId !== state.detail?.id) return;
      if (read.status !== 'completed') { editor.error = '文件已生成，但读回未完成；可刷新文件列表下载。'; return; }
      editor.creating = null; editor.file = result.output; editor.result = { ...read, output: result.output }; editor.draft = null;
      await showRoute();
    } catch (error) { if (documentEditor === editor) editor.error = error.message; }
    finally { editor.busy = false; render(); }
    return;
  }
  if (event.target.id === 'document-edit-form') {
    const editor = documentEditor;
    if (!editor || editor.busy || editor.sessionId !== state.detail?.id) { safeLog('document_form_rejected', { status: !editor ? 'missing_editor' : editor.busy ? 'busy' : 'session_changed' }); return; }
    const values = new FormData(event.target);
    const target = documentTargets(editor.result)[Number(values.get('target'))];
    if (!target) { safeLog('document_form_rejected', { status: 'target_missing' }); return; }
    const value = String(values.get('value') ?? '');
    const change = { ...target.change };
    if (change.kind === 'cell') {
      try { change.value = documentEditValue(value, String(values.get("value_type") || "string")); }
      catch (error) { editor.error = error.message; render(); return; }
    }
    else change.text = value;
    editor.draft = { target: Number(values.get('target')), value, mode: String(values.get('mode')), value_type: String(values.get('value_type') || 'string') };
    editor.busy = true; editor.error = ''; render();
    try {
      const result = await api.documentOperation(editor.sessionId, {
        format: editor.result.format, operation: 'modify', mode: String(values.get('mode')),
        file_id: editor.file.id, expected_sha256: editor.result.sha256, changes: [change],
      });
      if (documentEditor !== editor || state.detail?.id !== editor.sessionId) return;
      editor.lastResult = result;
      if (result.status === 'completed' && result.output) {
        const read = await api.documentOperation(editor.sessionId, { format: result.format, operation: 'read', mode: 'file', file_id: result.output.id });
        if (documentEditor !== editor || state.detail?.id !== editor.sessionId) return;
        if (read.status !== "completed") { editor.error = "新文件已生成，但读回未完成；原编辑内容仍保留。"; return; }
        editor.file = result.output; editor.result = { ...read, output: result.output }; editor.draft = null;
        await showRoute();
      } else editor.error = `未完成修改：${result.code || result.status}`;
    } catch (error) { if (documentEditor === editor) editor.error = error.message; }
    finally { editor.busy = false; render(); }
    return;
  }
  if (event.target.matches('[data-framework-bot-form]')) { await sendFrameworkQuestion(frameworkBot.draft); return; }
  if (event.target.matches('[data-mcp-search]')) { await loadMCPMarketplace(); return; }
  if (event.target.matches('[data-delivery-channel-form]')) {
    if (automationBusy) return;
    const values = new FormData(event.target);
    const kind = String(values.get('kind') || 'webhook');
    const body = { name: String(values.get('name') || ''), kind, enabled: true };
    const secret = String(values.get('secret') || '');
    if (secret) body.secret = secret;
    if (kind === 'smtp') {
      body.smtp_host = String(values.get('smtp_host') || '');
      body.smtp_port = Number(values.get('smtp_port'));
      body.smtp_username = String(values.get('smtp_username') || '') || null;
      body.sender = String(values.get('sender') || '');
      body.recipients = String(values.get('recipients') || '').split(',').map(value => value.trim()).filter(Boolean);
    } else body.endpoint = String(values.get('endpoint') || '');
    automationBusy = true; state.error = ''; success = ''; render();
    try {
      await api.saveDeliveryChannel(body);
      success = '外发渠道已保存到系统凭据库。';
      await loadCatalog(['deliveryChannels']);
    } catch (error) { state.error = error.message; }
    finally { automationBusy = false; render(); }
    return;
  }
  if (event.target.matches('[data-automation-form]')) {
    if (automationBusy) return;
    const values = new FormData(event.target);
    const [targetKind, targetId, versionText] = String(values.get('target') || '').split('|');
    const scheduleKind = String(values.get('schedule_kind') || 'daily');
    const [hourText, minuteText] = String(values.get('time') || '09:00').split(':');
    const target = targetKind === 'report_workflow'
      ? catalog.reportWorkflows.find(item => item.id === targetId)
      : catalog.capabilities.find(item => item.id === targetId && item.kind === targetKind);
    const schedule = { kind: scheduleKind, timezone: String(values.get('timezone') || 'Asia/Shanghai') };
    if (scheduleKind === 'once') schedule.once_at = String(values.get('once_at') || '');
    else {
      schedule.hour = Number(hourText); schedule.minute = Number(minuteText);
      if (scheduleKind === 'weekly') schedule.weekday = Number(values.get('weekday'));
      if (scheduleKind === 'monthly') schedule.day = Number(values.get('day'));
    }
    const outputFormats = targetKind === 'report_workflow' ? (target?.delivery_formats || []) : (target?.metadata?.default_formats || []);
    automationBusy = true; state.error = ''; success = ''; render();
    try {
      await api.createAutomation({
        name: String(values.get('name') || ''), target_kind: targetKind, target_id: targetId,
        target_version: Number(versionText), input_template: String(values.get('input_template') || ''),
        workspace_id: 'research', output_formats: outputFormats, mcp_tools: [], schedule,
        delivery: {
          channel_ids: values.getAll('channel_id').map(String),
          include_attachments: values.get('include_attachments') === 'on',
        },
      });
      automationFormOpen = false;
      success = 'Automation 已保存并保持停用；确认锁定内容后再启用。';
      await loadCatalog(['automations', 'automationRuns']);
    } catch (error) { state.error = error.message; }
    finally { automationBusy = false; render(); }
    return;
  }
  if (event.target.matches('[data-mcp-tool-policy]')) {
    const values = new FormData(event.target);
    await classifyMCPTool(
      event.target.dataset.mcpToolPolicy,
      String(values.get('risk_tier') || 'external_write_high_risk'),
      values.get('allow_unattended') === 'on',
    );
    return;
  }
  if (event.target.matches('[data-report-schedule-form]')) {
    if (reportWorkflowBusy) return;
    const workflowId = event.target.dataset.reportScheduleForm;
    const values = new FormData(event.target);
    const kind = String(values.get('kind') || 'manual');
    const enabled = values.get('enabled') === 'on' && kind !== 'manual';
    const body = {
      kind, enabled, timezone: 'Asia/Shanghai',
      once_at: kind === 'once' ? String(values.get('once_at') || '') || null : null,
      weekday: kind === 'weekly' ? Number(values.get('weekday')) : null,
      hour: kind === 'weekly' ? Number(values.get('hour')) : null,
      minute: kind === 'weekly' ? Number(values.get('minute')) : null,
    };
    await reportOperations.saveSchedule(workflowId, body);
    return;
  }
  if (event.target.matches('[data-asset-observation]')) {
    if (workbenchBusy) return;
    const current = workbenchOwner();
    const payload = readAssetObservation(event.target); const ticket = pageGeneration;
    if (payload.source === 'wind' && (payload.frequency !== 'daily' || (Date.parse(payload.end_date) - Date.parse(payload.start_date)) / 86400000 + 1 > 60)) { state.error = 'Wind 当前仅支持不超过 60 个日历日的股票日线，请修改区间或来源。'; render(); return; }
    assetWorkspace.cancel();
    workbenchBusy = true; state.error = ''; render();
    try {
      let record = await api.createAssetObservation(payload, crypto.randomUUID());
      if (ticket !== pageGeneration || !current()) return;
      Object.assign(state.route, { asset: payload.asset, assetType: payload.asset_type });
      history.replaceState(null, '', assetHref(payload.asset, payload.asset_type, state.route.assetView || 'overview'));
      assetState.observation = record; assetState.rows = {}; render();
      // replaceState does not dispatch hashchange; keep topic reads bound to this asset.
      void assetNews.activate(state.route);
      record = await pollAssetObservation(record, ticket);
      if (ticket !== pageGeneration || !current()) return;
      await loadAssetWorkspace();
      if (ticket === pageGeneration && current() && record.status !== 'running' && assetState.observation?.id === record.id) void assetWorkspace.startHistory('recent', payload.adjustment, undefined, payload.adjustment === 'none' ? payload.source : 'tinysoft');
      success = record.status === 'complete' ? '资产数据查询已结束，请查看各区块的来源与覆盖。' : record.status === 'running' ? '查询仍在运行，刷新本地状态可继续查看；未重新提交。' : '查询已结束，部分区块有缺失或失败，请查看对应状态。';
    } catch (error) { if (ticket === pageGeneration) state.error = error.message; safeLog('asset_observation_create_failed'); }
    finally { if (current()) { workbenchBusy = false; render(); } }
    return;
  }
  if (event.target.matches('[data-watchlist-item]')) {
    const current = workbenchOwner();
    const values = new FormData(event.target);
    try {
      await api.addWatchlistItem(String(values.get('watchlist_id')), {
        asset: String(values.get('asset')),
        asset_type: assetState.observation?.asset_type || 'stock',
        name: String(assetState.rows?.overview?.[0]?.name || values.get('asset')),
      });
      if (!current()) return;
      success = '已加入本地自选列表。'; await loadAssetWorkspace(); render();
    } catch (error) { if (current()) { state.error = error.message; render(); } safeLog('asset_watchlist_update_failed', { code: error.code || 'request_failed' }); }
    return;
  }
  if (event.target.matches('[data-asset-note]')) {
    const current = workbenchOwner();
    const values = new FormData(event.target);
    try {
      await api.createAssetNote({ asset: String(values.get('asset')), text: String(values.get('text')).trim() });
      if (!current()) return;
      event.target.reset(); success = '观察笔记已保存。'; await loadAssetWorkspace(); render();
    } catch (error) { if (current()) { state.error = error.message; render(); } safeLog('asset_note_update_failed', { code: error.code || 'request_failed' }); }
    return;
  }
  if (event.target.matches('[data-asset-alert]')) {
    const current = workbenchOwner();
    const values = new FormData(event.target);
    try {
      await api.createAssetAlert({
        asset: String(values.get('asset')),
        field: String(values.get('field')),
        operator: String(values.get('operator')),
        threshold: Number(values.get('threshold')),
        cooldown_minutes: 60,
      });
      if (!current()) return;
      event.target.reset(); success = '提醒规则已保存，将在新快照到达时评估。'; await loadAssetWorkspace(); render();
    } catch (error) { if (current()) { state.error = error.message; render(); } safeLog('asset_alert_update_failed', { code: error.code || 'request_failed' }); }
    return;
  }
  if (event.target.matches('[data-workbench-query]')) {
    if (workbenchBusy) return;
    const current = workbenchOwner();
    const section = state.route.section;
    const query = readWorkbenchQuery(event.target);
    workbenchDrafts.set(section, query);
    workbenchBusy = true; state.error = ''; render();
    try {
      const previous = workbenchQueries.filter(item => item.section === section).sort((a, b) => (b.created_at || 0) - (a.created_at || 0))[0];
      let record = await api.startDataQuery({ session_id: previous?.session_id || null, section, query }, crypto.randomUUID());
      if (!current()) return;
      workbenchQueries = [...workbenchQueries.filter(item => item.id !== record.id), record]; render();
      for (let attempt = 0; attempt < 80 && record.status === 'running' && current(); attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        if (!current()) return;
        record = await api.dataQuery(record.id);
        if (!current()) return;
        workbenchQueries = [...workbenchQueries.filter(item => item.id !== record.id), record]; render();
      }
      if (record.status === 'completed') success = '真实数据快照已生成，可交给 FinGPT 或 Claw。';
      else if (record.status === 'failed') state.error = `查询失败：${record.failure_code || '未知错误'}`;
    } catch (error) { if (current()) state.error = error.message; safeLog('business_query_failed', { section, code: error.code || 'request_failed' }); }
    finally { if (current()) { workbenchBusy = false; render(); } }
    return;
  }
  if (event.target.id === 'cap-editor-form') { captureEditor(); await capabilityController.save(); return; }
  if (event.target.id === 'cap-copy-form') { await capabilityController.copy(); return; }
  if (event.target.id === 'cap-creation-form') {
    const result = await controller.createCapabilitySession(capabilityState.kind, capabilityState.goal.trim());
    if (result?.id) { capabilityController.close(); await showRoute(); await loadCatalog(['sessions']); }
    return;
  }
  if (event.target.id === 'rename-form') {
    const id = renameSession?.id; const title = String(new FormData(event.target).get('title') || '').trim();
    if (!id || !title || sessionActionBusy) { sessionActionError = '会话名称不能为空。'; render(); return; }
    sessionActionBusy = true; sessionActionError = ''; render();
    try {
      const result = await api.rename(id, title);
      if (state.detail?.id === id) state.detail.title = result.title || title;
      renameSession = null; renameDraft = null; success = '会话名称已更新。';
      await loadCatalog(['sessions']);
    } catch (error) { sessionActionError = error.message; }
    finally { sessionActionBusy = false; render(); }
    return;
  }
  if (event.target.id === 'delete-session-form') {
    if (!deleteSession?.id || sessionActionBusy) return;
    const removed = deleteSession;
    sessionActionBusy = true; sessionActionError = ''; render();
    try {
      await api.deleteSession(removed.id);
      deleteSession = null; success = '会话已移至“已删除”，将在 30 天后永久删除。';
      if (state.route.sessionId === removed.id) {
        history.pushState(null, '', `#/${removed.mode === 'claw' ? 'claw' : 'fingpt'}`);
        await showRoute();
      }
      await loadCatalog(['sessions']);
    } catch (error) { sessionActionError = error.message; }
    finally { sessionActionBusy = false; render(); }
    return;
  }
  if (event.target.id === 'purge-session-form') {
    if (!purgeSession?.id || sessionActionBusy) return;
    const removed = purgeSession;
    sessionActionBusy = true; sessionActionError = ''; render();
    try {
      await api.purgeSession(removed.id);
      purgeSession = null; success = '会话及其 DSH 日志、附件、数据集和产物已永久删除。';
      await loadCatalog(['deletedSessions', 'sessions']);
    } catch (error) { sessionActionError = error.message; }
    finally { sessionActionBusy = false; render(); }
    return;
  }
  if (event.target.dataset.questionForm) {
    const id = state.detail?.id; const question = state.detail?.questions?.find((item) => item.id === event.target.dataset.questionForm);
    if (!id || !question?.items?.length) return;
    if (state.busy) return;
    captureQuestionForm(event.target, questionDrafts, id, question);
    let answers;
    try { answers = collectQuestionGroup(questionDrafts, id, question); }
    catch (error) { state.error = error.message; render(); return; }
    const result = await controller.action(() => api.answer(id, question.id, answers));
    if (result) { questionDrafts.delete(questionStateKey(id, question.id)); render(); }
  }
  if (event.target.id === 'composer') {
    if (state.route.page === 'claw' && !state.detail?.execution_context && (composerMenu.entry || composerSlashQuery(state.draft) !== null)) { if (!composerMenu.entry) composerMenu = openComposerMenu('slash', 'root', composerSlashQuery(state.draft)); render(); return; }
    if (state.route.page !== 'claw' && state.draft.trimStart().startsWith('/')) { slashOpen = true; slashIndex = 0; render(); return; }
    if (!state.draft.trim() || state.busy || slashOpen) return;
    const blocked = sendBlockReason();
    if (blocked) { state.error = blocked; render(); return; }
    if (await ensureSession()) { await controller.send(); await loadCatalog(['sessions']); }
  }
  if (event.target.id === 'tabbit-settings-form') {
    const values = new FormData(event.target);
    const instance = String(values.get('instance_id') || '').trim();
    const result = await controller.action(() => api.configureTabbit({
      browser_enabled: values.get('browser_enabled') === 'on',
      web_fetch_enabled: values.get('web_fetch_enabled') === 'on',
      instance_id: instance || null,
    }), { refreshAfter: false });
    if (result) { success = 'Tabbit 配置已保存；Runtime 空闲并重启后应用。'; await loadCatalog(['tabbit']); }
    return;
  }
  if (event.target.id === 'settings-form') {
    const values = new FormData(event.target);
    // Every submit clears the password, including payload-validation failures.
    document.querySelector('#api-key').value = '';
    let payload;
    try { payload = modelConfigurationPayload(values); }
    catch (error) { values.delete('api_key'); state.error = error.message; render(); return; }
    values.delete('api_key');
    const result = await controller.action(() => {
      const pending = api.configure(payload); delete payload.api_key; return pending;
    }, { refreshAfter: false });
    if (result?.configured) { delete root.querySelector('#settings-form')?.dataset.dirty; success = '配置已保存，新会话使用此模型；真实推理待测试。API Key 不会回填。'; await loadCatalog(['runtime', 'models']); }
  }
  if (event.target.matches('[data-connection-config]')) {
    const sourceId = event.target.dataset.connectionConfig;
    const values = new FormData(event.target);
    let payload;
    try { payload = buildConfigurationPayload(sourceId, values); }
    catch (error) { state.error = error.message; render(); return; }
    event.target.querySelectorAll('input[type="password"]').forEach((input) => { input.value = ''; });
    const submit = () => {
      const pending = api.saveSourceConfiguration(sourceId, payload);
      forgetConfigurationSecrets(payload);
      for (const key of [...values.keys()]) if (/(?:password|token|api_key|cj_key)$/i.test(key)) values.delete(key);
      return pending;
    };
    const result = await controller.action(submit, { refreshAfter: false });
    if (result) {
      success = `${catalog.connections.sources.find((item) => item.id === sourceId)?.name || sourceId} 配置已保存；秘密不会回填。`;
      await loadCatalog(['connections', 'dataCatalog', 'tools']);
      await loadConnectionConfiguration(sourceId);
    }
  }
  if (event.target.matches('[data-migration-confirm]')) {
    const values = new FormData(event.target); const sourceIds = values.getAll('source_ids').map(String);
    if (!sourceIds.length || values.get('confirm') !== 'on') { state.error = '请选择迁移目标并完成二次确认。'; render(); return; }
    const result = await controller.action(() => api.migrateConnections({ source_ids: sourceIds, confirm: true }), { refreshAfter: false });
    if (result) { migrationOpen = false; success = '旧配置已写入系统凭据库并完成回读验证。'; await loadCatalog(['connections', 'dataCatalog', 'tools']); }
  }
});

let questionAdvanceUntil = 0;
let questionAdvanceKey = '';
root.addEventListener('pointerdown', event => {
  const form = event.target.closest?.('.codex-question-option')?.closest('[data-question-form]');
  if (form && questionAdvanceKey === questionStateKey(form.dataset.qSession, form.dataset.questionForm) && (event.detail > 1 || performance.now() < questionAdvanceUntil)) event.preventDefault();
});
root.addEventListener('click', async (event) => {
  if(event.target.closest?.('[data-asset-research]') && await assetResearch.handle(event))return;
  if (event.target.closest?.('.scenario-panel') && await scenarioController.handle(event)) return;
  const scenarioAction = event.target.closest?.('[data-scenario-open], [data-workbench-handoff]');
  if (scenarioAction) {
    const launch = scenarioLaunchContext({ assetPage:isAssetPage(), route:state.route, observation:assetState.observation, observations:assetState.observations, detail:state.detail, draft:state.draft, researchAsOf:state.researchAsOf }, scenarioAction.dataset);
    if (launch) {
      event.preventDefault();
      if (launch.error) { state.error = launch.error; render(); }
      else await scenarioController.open(launch.context);
      return;
    }
  }
  if (event.target.closest?.('[data-dossier-workspace]') && await dossierController.handle(event)) return;
  if (state.route.page === 'market' && await marketController.handleClick(event)) return;
  if (isAssetPage()) {
    if (event.target.closest?.('[data-asset-metrics-toggle]')) { setAssetMetricsDrawer(!root.querySelector('.asset-wind-metrics')?.classList.contains('is-open')); return; }
    if (event.target.closest?.('[data-asset-metrics-close]')) { setAssetMetricsDrawer(false); return; }
    if (assetChart.handle(event)) return;
    if (event.target.closest?.('[data-asset-news-refresh]')) { await assetNews.activate(state.route, { refresh: true }); return; }
    const newsRow = event.target.closest?.('[data-asset-news-select]');
    if (newsRow) { assetNews.select(Number(newsRow.dataset.assetNewsSelect)); return; }
    if (event.target.closest?.('[data-asset-news-more]')) { assetNews.more(); return; }
    const loadBlock = event.target.closest?.('[data-asset-block-load]');
    if (loadBlock) {
      event.preventDefault();
      delete assetState.errors.topic;
      try { await assetWorkspace.loadBlock(loadBlock.dataset.assetBlockLoad, { refresh: true }); }
      catch (error) { assetState.errors.topic = error.message || '区块读取失败，请重试。'; safeLog('asset_block_load_failed', { status: 'error' }); paintAssetTopic(); }
      return;
    }
    const refreshBlock = event.target.closest?.('[data-asset-block-refresh]');
    if (refreshBlock && assetState.observation && !workbenchBusy) {
      const ticket = pageGeneration; workbenchBusy = true; state.error = ''; render();
      try { const record = await api.refreshAssetBlock(assetState.observation.id, refreshBlock.dataset.assetBlockRefresh, crypto.randomUUID()); await pollAssetObservation(record, ticket); if (ticket === pageGeneration) await loadAssetWorkspace(); }
      catch (error) { if (ticket === pageGeneration) state.error = error.message; safeLog('asset_block_refresh_failed'); }
      finally { if (ticket === pageGeneration && isAssetPage()) { workbenchBusy = false; render(); } }
      return;
    }
  }

  const commandTrigger = event.target.closest?.('[data-cm-open]');
  if (state.route.page === 'claw' && commandTrigger && Object.hasOwn(commandTrigger.dataset, 'cmOpen')) {
    if (commandTrigger.disabled || state.detail?.execution_restricted) return;
    const view = commandTrigger.dataset.cmOpen;
    if (composerMenu.entry && composerMenu.view === view) closeComposerMenu();
    else {
      composerMenu = openComposerMenu('add', view);
      slashOpen = false; tabbitOpen = false; tabbitCandidates = []; tabbitRequest += 1;
      root.querySelectorAll('.composer-model-menu[open], .composer-more[open]').forEach(item => { item.open = false; });
      safeLog('claw_composer_menu_opened'); focusComposerMenu();
    }
    return;
  }
  if (state.route.page === 'claw' && event.target.closest?.('#claw-composer-menu')) {
    if (event.target.closest('[data-cm-back]')) backComposerMenu();
    else if (event.target.closest('[data-cm-done]')) closeComposerMenu(true);
    else {
      const button = event.target.closest('[data-cm-row]');
      if (button && !button.disabled) { composerMenu.index = Number(button.dataset.cmRow); await activateComposerRow(currentComposerRows()[composerMenu.index]); }
    }
    return;
  }
  if (composerMenu.entry && !event.target.closest?.('#claw-composer-menu') && !(composerMenu.entry === 'slash' && event.target.id === 'prompt')) { composerMenu = closedComposerMenu(); render(); }

  if (searchOpen && !event.target.closest?.('.search-popover, [data-toggle-search]')) {
    event.preventDefault(); event.stopPropagation(); closeGlobalSearch(); return;
  }
  const closeSearchButton = event.target.closest?.('[data-close-search]');
  if (closeSearchButton && Object.hasOwn(closeSearchButton.dataset, 'closeSearch')) { closeGlobalSearch(); return; }
  const questionOption = event.target.closest?.('.codex-question-option');
  const questionInput = questionOption?.querySelector?.('input');
  if (questionInput) {
    const input = questionInput;
    const form = questionOption.closest('[data-question-form]');
    const question = state.detail?.questions?.find(item => item.id === form?.dataset.questionForm);
    const key = form && questionStateKey(form.dataset.qSession, form.dataset.questionForm);
    if (!question || form.dataset.qSession !== state.detail.id || state.busy || event.detail > 1 || (event.detail > 0 && key === questionAdvanceKey && performance.now() < questionAdvanceUntil)) { event.preventDefault(); return; }
    // Checkboxes keep native toggle/keyboard semantics; change captures their draft.
    if (input?.type !== 'radio') return;
    if (event.target !== input) { event.preventDefault(); input.checked = true; }
    try {
      captureQuestionForm(form, questionDrafts, state.detail.id, question);
      const next = Number(form.dataset.qIndex) < question.items.length - 1;
      if (next) {
        actionQuestion(questionDrafts, state.detail.id, question, 'next');
        questionAdvanceKey = key;
        questionAdvanceUntil = performance.now() + 300;
        safeLog('question_option_advanced');
      }
      state.error = ''; render();
      const nextForm = [...root.querySelectorAll('[data-question-form]')].find(item => item.dataset.questionForm === question.id);
      if (next) nextForm?.querySelector('legend')?.focus({ preventScroll: true });
      else [...(nextForm?.querySelectorAll('input[type="radio"]') || [])].find(item => item.value === input.value)?.focus({ preventScroll: true });
    } catch (error) { safeLog('question_option_failed'); state.error = error.message || '无法保存选项，请重试。'; render(); }
    return;
  }
  const modelMenu = root.querySelector('.composer-model-menu[open]');
  if (modelMenu && !event.target.closest?.('.composer-model-menu')) modelMenu.open = false;
  const legacyComposerMenu = root.querySelector('.composer-more[open]');
  if (legacyComposerMenu && !event.target.closest?.('.composer-more')) legacyComposerMenu.open = false;
  const modelChoice = event.target.closest?.('[data-composer-model]');
  if (modelChoice && Object.hasOwn(modelChoice.dataset, 'composerModel')) {
    if (modelChoice.disabled) return;
    const picker = modelChoice.closest('.composer-model-menu'); if (picker) picker.open = false;
    await configureComposerModel(modelChoice.dataset.composerModel); return;
  }
  const answerAction = event.target.closest?.('[data-claw-answer-action]');
  if (answerAction && Object.hasOwn(answerAction.dataset, 'clawAnswerAction')) {
    const index = Number(answerAction.dataset.answerIndex);
    const detail = state.detail;
    if (answerAction.disabled || detail?.mode !== 'claw' || answerAction.dataset.answerSession !== detail.id || !Number.isInteger(index) || index < 0 || detail.messages?.[index]?.role !== 'assistant') return;
    const message = detail.messages[index];
    const action = answerAction.dataset.clawAnswerAction;
    const ticket = pageGeneration;
    try {
      if (action === 'download') downloadAnswer(message.text);
      else if (action === 'share') {
        await copyResearchText(globalThis.location.href);
        if (ticket === pageGeneration && answerAction.isConnected) { answerAction.title = '已复制本机链接'; answerAction.setAttribute('aria-label', '已复制本机链接'); }
      } else if (['sources', 'files', 'process'].includes(action)) {
        contextTab = { sources: 'datasets', files: 'files', process: 'activity' }[action];
        contextCollapsed = false; contextOpen = window.matchMedia('(max-width: 1050px)').matches; sidebarOpen = false; render();
        root.querySelector('.context-tabs [aria-selected="true"]')?.focus();
      } else if (action === 'retry') {
        const blocked = retryBlockReason();
        if (detail.execution_restricted || blocked) throw new Error(blocked || '此执行会话不能重新发起研究，请返回原对话操作。');
        const source = detail.messages.slice(0, index).findLast(item => item.role === 'user');
        if (source?.text) { controller.setDraft(source.text); await controller.send(); }
      }
    } catch (error) { safeLog('claw_answer_action_failed'); if (ticket === pageGeneration) { state.error = error.message || '操作失败，请重试。'; render(); } }
    return;
  }
  const copy = event.target.closest?.('[data-copy-message]');
  if (copy && Object.hasOwn(copy.dataset,'copyMessage')) {
    const index = Number(copy.dataset.copyMessage);
    const detail = state.detail;
    if (copy.dataset.copySession !== detail?.id || !Number.isInteger(index) || index < 0 || detail.messages?.[index]?.role !== 'assistant') return;
    const ticket = pageGeneration;
    try { await copyResearchText(detail.messages[index].text); if (ticket === pageGeneration && copy.isConnected) { copy.title = '已复制'; copy.setAttribute('aria-label', '已复制回复'); } }
    catch (error) { if (ticket === pageGeneration) { state.error = error.message; render(); } }
    return;
  }
  if (state.route.page === 'aihot') {
    const sourceEdit=event.target.closest?.('[data-news-source]');
    if(sourceEdit){await aihotController.management.action('source.detail',{id:sourceEdit.dataset.newsSource});return;}
    if(event.target.closest?.('[data-news-new]')){aihotController.management.state.selection=null;aihotController.management.state.draft=null;aihotController.management.state.preview=null;render();return;}
    root.querySelectorAll('.aihot-faces[open]').forEach(item => { if (!item.contains(event.target)) item.open = false; });
    const readingAnchor=event.target.closest?.('.aihot-page a[href^="#/aihot/"]');
    if(readingAnchor && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey && event.button===0) {
      if(readingAnchor.hasAttribute('data-aihot-back')) { event.preventDefault();location.hash=aihotController.back(); }
      else aihotController.prepareLink(readingAnchor.getAttribute('href'));
      return;
    }
    if (event.target.closest?.('[data-aihot-group]')) { await aihotController.loadGroup(); return; }
    const copyKind = event.target.closest?.('[data-aihot-copy]')?.dataset.aihotCopy;
    if (copyKind) { await aihotController.copy(copyKind); return; }
    if (event.target.closest?.('[data-aihot-download]')) { aihotController.download(); return; }
    const storyFilter = event.target.closest?.('[data-aihot-filter]')?.dataset.aihotFilter;
    const storyOrder = event.target.closest?.('[data-aihot-order]')?.dataset.aihotOrder;
    if (storyFilter || storyOrder) { aihotController.setStoryView({filter:storyFilter,order:storyOrder}); return; }
    if (event.target.closest?.('[data-aihot-refresh]')) { await aihotController.refresh(); return; }
    const jump = event.target.closest?.('[data-aihot-jump]');
    if (jump) {
      event.preventDefault();
      const target = document.getElementById(jump.dataset.aihotJump);
      if (target?.tagName === 'DETAILS') target.open = true;
      document.querySelector('.aihot-outline-dialog')?.close();
      target?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
      return;
    }
    if (event.target.closest?.('[data-aihot-outline]')) { document.querySelector('.aihot-outline-dialog')?.showModal(); return; }
    if (event.target.closest?.('[data-aihot-outline-close]')) { document.querySelector('.aihot-outline-dialog')?.close(); return; }
    const month = event.target.closest?.('[data-aihot-month-retry]')?.dataset.aihotMonthRetry;
    if (month) { await aihotController.loadMonth(month); return; }
  }
  if (event.target.closest?.('.discovery-page')) {
    const action = event.target.closest?.('[data-discovery-action]')?.dataset.discoveryAction;
    if (await discoveryController.handle(event)) {
      if (['research', 'tracking', 'source', 'tracking-new', 'research-new', 'history-status'].includes(action)) root.querySelector('#discovery-drawer-title')?.focus({ preventScroll: true });
      if (action === 'close') root.querySelector('[data-discovery-action="research"]')?.focus({ preventScroll: true });
      return;
    }
  }
  if (event.target.closest?.('.intel-page')) {
    const action = event.target.closest?.('[data-intel-action]')?.dataset.intelAction;
    if (await intelController.handle(event)) {
      if (['event', 'report'].includes(action)) document.querySelector('#intel-detail-title')?.focus({ preventScroll: true });
      if (action === 'close') document.querySelector('.intel-tabs [aria-current="page"]')?.focus({ preventScroll: true });
      return;
    }
  }
  const recipe = event.target.closest?.('[data-research-recipe]')?.dataset.researchRecipe;
  if (recipe && researchRecipes[recipe]) { if (state.busy) return; controller.setDraft(researchRecipes[recipe] + '\n' + state.draft); render(); root.querySelector('#prompt')?.focus(); return; }
  const clickTarget = event.target;
  const clickedNavigationRect = clickTarget?.closest?.('.session-row, .nav-project-row')?.getBoundingClientRect?.();
  const hotAction=clickTarget?.closest?.('[data-hot-action]');
  if(hotAction?.dataset?.hotAction){await hotController.action(hotAction);return;}
  const modelAction = clickTarget?.closest?.('[data-model-clear], [data-model-test]')?.dataset;
  if (modelAction && 'modelClear' in modelAction) {
    if (!catalog.runtime?.model) { state.error = '当前模型未知，请先刷新 Runtime 状态。'; render(); return; }
    if (!window.confirm('清除专属模型凭据？后续模型请求将不可用，已有会话仍保留。')) return;
    const form = root.querySelector('#settings-form');
    const values = new FormData(form); form.querySelector('#api-key').value = '';
    values.delete('api_key');
    let payload;
    try { payload = modelConfigurationPayload(values, { clear: true }); }
    catch (error) { state.error = error.message; render(); return; }
    const result = await controller.action(() => api.configure(payload), { refreshAfter: false });
    if (result?.configured) { success = '模型凭据已清除。'; await loadCatalog(['runtime']); }
    return;
  }
  if (modelAction && 'modelTest' in modelAction) {
    const result = await controller.action(() => api.testModel(), { refreshAfter: false });
    if (result) { if (result.status === 'passed') success = '真实生成已收到最终文本；工具调用需单独验证。'; else state.error = `真实生成测试失败：${result.code || 'model_generation_failed'}`; await loadCatalog(['runtime']); }
    return;
  }
  const frameworkAnchor = clickTarget?.closest?.('[data-framework-anchor]');
  const frameworkAnchorId = frameworkAnchor?.dataset?.frameworkAnchor;
  if (frameworkAnchorId) {
    event.preventDefault?.();
    const anchor = frameworkAnchorId;
    history.replaceState(null, '', frameworkAnchor.getAttribute('href'));
    state.route.frameworkTab = anchor; render();
    requestAnimationFrame(() => scrollFrameworkTarget(anchor, matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'));
    return;
  }
  if (clickTarget?.matches?.('[data-nav-project-backdrop]')) { closeProjectEditor(); return; }
  if (clickTarget?.matches?.('[data-mcp-dialog-backdrop]')) {
    closeMCPServerDialog(); return;
  }
  if (clickTarget?.matches?.('[data-capability-dialog-backdrop]')) {
    closeCapabilityPreview(); return;
  }
  if (clickTarget?.matches?.('[data-dialog-backdrop]')) {
    renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionActionError = ''; render();
    return;
  }
  const modeMenuState = conversationNavigation.state(state.route.page);
  if (modeMenuState?.menu && !clickTarget?.closest?.('.nav-project-menu') && !clickTarget?.closest?.('[data-nav-project-menu]')) { modeMenuState.menu = null; render(); }
  if (sessionMenu && !clickTarget?.closest?.('.session-action-menu') && !clickTarget?.closest?.('[data-session-menu]')) {
    sessionMenu = null; render();
  }
  const button = clickTarget?.closest?.('button'); if (!button || button.disabled || button.getAttribute?.('aria-disabled') === 'true') return;
  const data = button.dataset;
  const mode = state.route.page;
  const nav = conversationNavigation.state(mode);
  if (['qPage', 'qClose', 'qOpen', 'qSkip'].some(name => name in data)) {
    const form = button.closest('[data-question-form]');
    const question = state.detail?.questions?.find(q => q.id === form?.dataset.questionForm);
    if (!question || form.dataset.qSession !== state.detail.id || state.busy) return;
    questionAdvanceUntil = 0; questionAdvanceKey = '';
    captureQuestionForm(form, questionDrafts, state.detail.id, question);
    actionQuestion(questionDrafts, state.detail.id, question, data.qPage || ('qClose' in data ? 'close' : 'qOpen' in data ? 'open' : 'skip'));
    state.error = ''; render();
    const nextForm = [...root.querySelectorAll('[data-question-form]')].find(f => f.dataset.questionForm === question.id);
    nextForm?.querySelector('legend, [data-q-open], textarea')?.focus?.({ preventScroll: true }); return;
  }
  if (nav && 'navMoveMenu' in data && sessionMenu?.id === data.navMoveMenu) {
    openProjectMenu(button, true); return;
  }
  if (nav && 'navMoveClose' in data && sessionMenu) { sessionMenu.move = null; render(); document.querySelector('[data-nav-move-menu]')?.focus({ preventScroll: true }); return; }
  if (nav && 'navMoveTarget' in data) {
    const row = catalog.sessions.find(item => item.id === data.navSession && item.mode === mode);
    if (!row || sessionMenu?.id !== row.id || !nav.projects.some(item => item.id === data.navMoveTarget && !item.archived)) return;
    if ((row.project_id || 'default') !== data.navMoveTarget) {
      const moved = await conversationNavigation.moveSession(mode, row.id, data.navMoveTarget);
      if (moved) conversationNavigation.revealSession(mode, row.id, catalog.sessions);
    }
    sessionMenu = null; render(); [...root.querySelectorAll('[data-session-menu]')].find(node => node.dataset.sessionMenu === row.id)?.focus?.({ preventScroll: true }); return;
  }
  if (nav && 'navRetry' in data) { await conversationNavigation.load(mode, true); return; }
  if (nav && 'navSection' in data) {
    const sections = new Set(nav.view.collapsedSections || []);
    if (sections.has(data.navSection)) sections.delete(data.navSection); else sections.add(data.navSection);
    conversationNavigation.view(mode, { collapsedSections: [...sections] }); render(); return;
  }
  if (nav && 'navMore' in data) { conversationNavigation.view(mode, { limit: nav.view.limit + 10 }); render(); return; }
  if (nav && 'navProjectToggle' in data) {
    const expanded = new Set(nav.view.expanded); if (expanded.has(data.navProjectToggle)) expanded.delete(data.navProjectToggle); else expanded.add(data.navProjectToggle);
    conversationNavigation.view(mode, { expanded: [...expanded] }); render(); return;
  }
  if (nav && 'navProjectMenu' in data) {
    nav.menu = nav.menu === data.navProjectMenu ? null : data.navProjectMenu;
    const rect = clickedNavigationRect || button.getBoundingClientRect(); nav.menuPosition = sessionMenuPosition(rect, { width: window.innerWidth, height: window.innerHeight });
    render(); document.querySelector('.nav-project-menu [role="menuitem"]')?.focus({ preventScroll: true }); return;
  }
  if (nav && 'navEditorClose' in data) { closeProjectEditor(); return; }
  if (nav && ('navProjectCreate' in data || 'navProjectRename' in data)) {
    const project = nav.projects.find(p => p.id === data.navProjectRename);
    nav.editor = project ? { id: project.id, name: project.name } : { name: '' }; nav.error = ''; nav.menu = null; sessionMenu = null; render(); document.querySelector('#nav-project-name')?.focus(); return;
  }
  if (nav && 'navPin' in data) {
    const saved = await conversationNavigation.pin(mode, { kind: data.navPin, id: data.navId });
    if (saved) {
      if (data.navPin === 'session') conversationNavigation.revealSession(mode, data.navId, catalog.sessions);
      else {
        const section = nav.metadata.pinned.some(item => item.kind === 'project' && item.id === data.navId) ? 'pinned' : 'projects';
        conversationNavigation.view(mode, { collapsedSections: (nav.view.collapsedSections || []).filter(item => item !== section) });
      }
    }
    sessionMenu = null; nav.menu = null; render();
    const selector = data.navPin === 'session' ? '[data-session-menu]' : '[data-nav-project-menu]';
    [...root.querySelectorAll(selector)].find(node => (node.dataset.sessionMenu || node.dataset.navProjectMenu) === data.navId)?.focus?.({ preventScroll: true });
    return;
  }
  if (nav && 'navOrder' in data) {
    await conversationNavigation.reorder(mode, data.navGroup, { kind: data.navEntity, id: data.navId }, Number(data.navOrder));
    sessionMenu = null; nav.menu = null; render();
    const selector = data.navEntity === 'session' ? '[data-session-menu]' : '[data-nav-project-menu]';
    [...root.querySelectorAll(selector)].find(node => (node.dataset.sessionMenu || node.dataset.navProjectMenu) === data.navId)?.focus?.({ preventScroll: true }); return;
  }
  if (nav && 'navProjectArchive' in data) { await conversationNavigation.archive(mode, data.navProjectArchive); return; }
  if (nav && 'navNewInProject' in data) { history.pushState(null, '', `#/${mode}?project=${encodeURIComponent(data.navNewInProject)}`); await showRoute(); controller.setDraft(''); render(); document.querySelector('#prompt')?.focus(); return; }

  if ('clawProjectRefresh' in data) { await loadClawProjects(); return; }
  if ('clawProjectArchive' in data) {
    await clawAction(async () => { await api.updateProject(state.route.page, data.clawProjectArchive, { archived: data.archived === 'true' }); await loadClawProjects(); }); return;
  }
  if ('clawNewSession' in data) {
    const ticket = pageGeneration;
    await clawAction(async () => {
      const created = await api.create({ mode: state.route.page, project_id: data.clawNewSession });
      if (!clawNavigationCurrent(ticket, pageGeneration)) return;
      history.pushState(null, '', `#/${state.route.page}?session=${encodeURIComponent(created.id)}`); await showRoute(); await loadCatalog(['sessions']);
    }); return;
  }
  if ('clawReference' in data) {
    const target = root.querySelector('[data-claw-reference-target]')?.value;
    if (!target) { state.error = '请先显式选择接收会话。'; render(); return; }
    const ticket = pageGeneration;
    await clawAction(async () => {
      const file = await api.referenceClawFile(target, { source_session_id: data.sourceSession, file_id: data.clawReference, expected_sha256: data.sha256 });
      controller.addAttachmentsForSession(target, [file]);
      if (!clawNavigationCurrent(ticket, pageGeneration)) return;
      history.pushState(null, '', `#/${state.route.page}?session=${encodeURIComponent(target)}`); await showRoute();
      if (state.detail?.id === target) success = '已复制所选文件并加入当前会话草稿；尚未发送研究。';
    }); return;
  }
  if ('clawDraftDismiss' in data) {
    const sid = state.detail?.id; if (!sid) return;
    await clawAction(async () => { await api.dismissAutomationDraft(sid, data.clawDraftDismiss); clawDraftEdits.delete(data.clawDraftDismiss); await controller.refresh(); }); return;
  }
  if ('frameworkBotOpen' in data) { if (!frameworkEmbedBridge.ready(state.route.frameworkSlug, frameworkState.data?.snapshot?.revision)) return; frameworkBot.open = true; updateFrameworkBotSlot(); requestAnimationFrame(() => document.getElementById('framework-bot-input')?.focus()); return; }
  if ('frameworkBotClose' in data) { if (frameworkBot.errorCode === 'framework_snapshot_changed') { closeFrameworkStream(); closeFrameworkStream = () => {}; frameworkBot = { open: false, sessionId: '', draft: '', busy: false, error: '', errorCode: '', mode: 'explain' }; } frameworkBot.open = false; updateFrameworkBotSlot(); return; }
  if ('frameworkRetry' in data) { await loadFrameworkPage(); return; }
  if ('frameworkGap' in data) { frameworkBot.open = true; frameworkBot.draft = '请解释当前最重要的数据缺口，以及需要什么证据才能解除“待核验”。'; updateFrameworkBotSlot(); requestAnimationFrame(() => document.getElementById('framework-bot-input')?.focus()); return; }
  if ('frameworkVerify' in data) { await verifyFrameworkQuestion(frameworkBot.draft); return; }
  if ('mcpDetailClose' in data) { closeMCPServerDialog(); return; }
  if ('mcpMarketRetry' in data) { await loadMCPMarketplace({ reloadRegistries: !mcpMarketplaceState.registries.length }); return; }
  if ('mcpSync' in data) { await loadMCPMarketplace({ sync: true }); return; }
  if ('mcpServerDetail' in data) {
    await openMCPServerDetail({ registryId: data.registryId, serverName: data.serverName, version: data.serverVersion });
    return;
  }
  if ('mcpInstallPreview' in data) { await runMCPInstallPreview(); return; }
  if ('mcpInstallReset' in data) {
    mcpInstallGeneration += 1;
    mcpMarketplaceState.installation = { ...emptyMCPInstallation(), target: mcpMarketplaceState.installation.target };
    render(); return;
  }
  if ('mcpInstallConfirmAction' in data) { await runMCPInstallConfirmation(); return; }
  if ('mcpInstallProbe' in data) { await runMCPInstalledAction('probe'); return; }
  if ('mcpInstallEnable' in data) { await runMCPInstalledAction('enable'); return; }
  if ('mcpInstallDisable' in data) { await runMCPInstalledAction('disable'); return; }
  if ('mcpInstallRemove' in data) { await removeMCPInstallation(); return; }
  if ('mcpAuthorizeTool' in data) { await authorizeMCPTool(data.mcpAuthorizeTool); return; }
  if ('mcpOauthStart' in data) { await startMCPOAuth(); return; }
  if ('mcpApprovalApprove' in data) { await decideMCPApproval(data.mcpApprovalApprove, true); return; }
  if ('mcpApprovalDeny' in data) { await decideMCPApproval(data.mcpApprovalDeny, false); return; }
  if ('mcpPublisherAction' in data) { await runMCPPublisherAction(data.mcpPublisherAction); return; }
  if ('localCategoryTarget' in data) {
    localCategory = data.localCategoryTarget === 'all' ? 'all' : data.localCategoryTarget.replace(/^local-category-/, '');
    render();
    document.querySelector(`[data-local-category-target="${CSS.escape(data.localCategoryTarget)}"]`)?.focus();
    return;
  }
  if ('officeAutoCancel' in data) {
    const target = officeConsentConfirmation;
    officeConsentConfirmation = ''; render();
    document.querySelector(`[data-office-auto-consent="${CSS.escape(target)}"]`)?.focus();
    return;
  }
  if ('officeAutoConsent' in data) {
    const allowed = ['local:excel_app', 'local:word_app', 'local:powerpoint_app'];
    const ids = data.officeAutoConsent === 'all' ? allowed : allowed.filter((id) => id === data.officeAutoConsent);
    if (!ids.length) return;
    const enabled = data.consentEnabled === 'true';
    if (!enabled && (data.officeAutoConfirmed !== 'true' || officeConsentConfirmation !== data.officeAutoConsent)) {
      officeConsentConfirmation = data.officeAutoConsent;
      render();
      document.querySelector('[data-office-auto-confirmed]')?.focus();
      return;
    }
    officeConsentConfirmation = '';
    const ticket = officeAutoPollingGuard.begin();
    for (const item of catalog.localIntegrations.integration_status?.items || []) {
      if (ids.includes(item.id)) item.details = { ...item.details, auto_probe_consent: !enabled };
    }
    render();
    try {
      const settled = await Promise.allSettled(ids.map((id) => officeConsentQueue.set(id, !enabled)));
      if (!officeAutoPollingGuard.isCurrent(ticket)) return;
      const rejected = settled.find((result) => result.status === 'rejected');
      if (rejected) throw rejected.reason;
      const results = settled.map((result) => result.value);
      await loadCatalog(['localIntegrations']);
      if (!officeAutoPollingGuard.isCurrent(ticket)) return;
      if (enabled) { success = '已关闭对应 Office 自动验证。'; render(); }
      const latest = catalog.localIntegrations.integration_status?.latest_batch;
      const batches = [...new Set(results.map((result) => result.batch?.id).filter(Boolean))];
      if (latest?.id && ['queued', 'checking'].includes(latest.status)) batches.push(latest.id);
      if (batches.length) {
        for (const id of batches) {
          let previousProgress = '';
          await waitForIntegrationBatch(async (batchId) => {
            if (!officeAutoPollingGuard.isCurrent(ticket)) return { status: 'cancelled' };
            const batch = await api.integrationProbeBatch(batchId);
            if (!officeAutoPollingGuard.isCurrent(ticket)) return { status: 'cancelled' };
            const progress = JSON.stringify(batch.items || {});
            if (progress !== previousProgress) {
              previousProgress = progress;
              await loadCatalog(['localIntegrations']);
            }
            return batch;
          }, id);
        }
        if (!officeAutoPollingGuard.isCurrent(ticket)) return;
        await loadCatalog(['localIntegrations']);
      }
      if (!officeAutoPollingGuard.isCurrent(ticket)) return;
      success = enabled ? '已关闭对应 Office 自动验证。' : 'Office 自动验证已处理；请查看每项结果。';
    } catch (error) {
      if (!officeAutoPollingGuard.isCurrent(ticket)) return;
      state.error = error?.message || 'Office 自动验证设置失败。';
      safeLog('office_auto_consent_failed', { status: error?.code || error?.name || 'unknown' });
      await loadCatalog(['localIntegrations']);
    }
    if (officeAutoPollingGuard.isCurrent(ticket)) render();
    return;
  }
  if ('connectionGroup' in data) {
    const workbench = button.closest('[data-connection-workbench]');
    if (!workbench) return;
    workbench.dataset.activeGroup = data.connectionGroup;
    workbench.querySelectorAll('[data-connection-group]').forEach((tab) => {
      const selected = tab === button;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    closeConnectionDrawer(workbench, { restoreFocus: false });
    applyConnectionWorkspaceFilters(workbench);
    return;
  }
  if ('connectionDetailClose' in data) {
    closeConnectionDrawer(button.closest('[data-connection-workbench]'));
    return;
  }
  if ('connectionSelect' in data) {
    const sourceId = data.connectionSelect;
    const source = catalog.connections.sources.find((item) => item.id === sourceId);
    const section = source?.group === 'local' ? 'local' : 'data';
    state.route.settingsSection = section;
    state.route.connectionId = sourceId;
    delete state.route.legacySettingsConnection;
    history.pushState(null, '', `#/settings/${section}?connection=${encodeURIComponent(sourceId)}`);
    selectedConnectionConfiguration = null; connectionDetailOpen = true; state.error = ''; render();
    await loadConnectionConfiguration(sourceId);
    document.querySelector('#connection-title')?.focus?.({ preventScroll: true });
    return;
  }
  if ('connectionCancel' in data) { await loadConnectionConfiguration(data.connectionCancel); return; }
  if ('connectionRemove' in data) {
    const sourceId = data.connectionRemove;
    const sourceLabel = catalog.connections.sources.find((item) => item.id === sourceId)?.label || sourceId;
    const sharedImpact = sourceId.startsWith('zhiqiu_') ? '该账号池由知丘研报、公众号与纪要共享，三项授权都会被移除。' : '';
    if (!globalThis.confirm?.(`移除 ${sourceLabel} 的本机配置与凭据？${sharedImpact}历史快照不会删除。`)) return;
    const result = await controller.action(() => api.deleteSourceConfiguration(sourceId), { refreshAfter: false });
    if (result) { success = '本机配置和系统凭据已移除；历史快照保持可读。'; selectedConnectionConfiguration = null; await loadCatalog(['connections', 'dataCatalog', 'tools']); await loadConnectionConfiguration(sourceId); }
    return;
  }
  if ('integrationConsent' in data) {
    const sourceId = data.integrationConsent;
    const enabled = data.consentEnabled === 'true';
    const nextConsent = !enabled;
    const sourceLabel = catalog.connections.sources.find((item) => item.id === sourceId)?.label || sourceId;
    if (!confirmAutoProbeConsent((message) => globalThis.confirm?.(message), sourceLabel, nextConsent)) return;
    const result = await controller.action(
      () => api.setIntegrationConsent(`data:${sourceId}`, nextConsent),
      { refreshAfter: false },
    );
    if (result) {
      success = nextConsent ? `已允许自动检测 ${sourceLabel}。` : `已停用 ${sourceLabel} 的自动检测。`;
      await loadCatalog(['connections', 'integrations']);
    }
    return;
  }
  if ('connectionProbe' in data) {
    const sourceId = data.connectionProbe; state.error = ''; success = '';
    const sourceLabel = catalog.connections.sources.find((item) => item.id === sourceId)?.label || sourceId;
    connectionProbeBusy = true; render();
    try {
      const accepted = await controller.action(() => api.probeDataSource(sourceId, `probe-${sourceId}-${crypto.randomUUID()}`), { refreshAfter: false });
      if (!accepted) return;
      if (typeof accepted.id !== 'string' || !accepted.id) throw new Error('服务未返回有效的探测任务，请刷新后重试。');
      const current = await waitForDataProbe((probeId) => api.dataProbe(probeId), accepted.id);
      success = current.health === 'healthy' ? `${sourceLabel}检测通过。` : `${sourceLabel}检测完成，请根据状态说明处理。`;
      await loadCatalog(['connections', 'dataCatalog']);
      await loadConnectionConfiguration(sourceId);
    } catch (error) {
      state.error = error?.message || '检测失败，请重试。';
      safeLog('connection_probe_failed', { status: error?.code || error?.name || 'unknown' });
    } finally {
      connectionProbeBusy = false; render();
    }
    return;
  }
  if ('verifySourceAuth' in data) {
    connectionProbeBusy = true; state.error = ''; success = ''; render();
    try {
      const result = await api.verifySourceAuthorization(data.verifySourceAuth);
      success = result.status === 'authenticated' ? 'HTTP 授权交换成功；具体数据权限尚未验证。' : '授权尚未验证。';
      await loadConnectionConfiguration(data.verifySourceAuth);
    } catch (error) { state.error = error.message || '授权未验证'; safeLog('source_authorization_unverified'); }
    finally { connectionProbeBusy = false; render(); }
    return;
  }
  if ('localIntegrationsProbe' in data) {
    state.error = ''; success = ''; localIntegrationProbeBusy = true; render();
    try {
      const accepted = await api.probeLocalIntegrations(`local-integrations-${crypto.randomUUID()}`);
      if (typeof accepted?.id !== 'string' || !accepted.id) throw new Error('服务未返回有效的探测任务，请刷新后重试。');
      const current = await waitForLocalIntegrationProbe((probeId) => api.localIntegrationProbe(probeId), accepted.id);
      if (current.status !== 'completed' || !current.snapshot) throw new Error(current?.error?.message || '本机能力检测未完成。');
      await loadCatalog(['localIntegrations']);
      success = '本机能力状态已更新。';
    } catch (error) {
      state.error = error?.message || '本机能力检测失败，请重试。';
      safeLog('local_integration_probe_failed', { status: error?.code || error?.name || 'unknown' });
    } finally {
      localIntegrationProbeBusy = false; render();
    }
    return;
  }
  if ('localIntegrationVerify' in data) {
    const target = data.localIntegrationVerify;
    const labels = { excel: 'Excel', word: 'Word', powerpoint: 'PowerPoint', wind_excel: 'Wind Excel' };
    if (!(target in labels)) return;
    if (target === 'wind_excel' && globalThis.confirm?.('单独确认 Wind Excel 真实厂商验证？会使用已登录厂商会话，在登记的独占测试工作簿中运行最小公式，可能出现厂商安全验证提示。Office 自动验证开关不包含此调用。') !== true) return;
    const verificationTicket = localIntegrationPollingGuard.begin();
    state.error = ''; success = ''; localVerificationTarget = target; render();
    try {
      const accepted = await api.verifyLocalIntegration(target, `local-verification-${target}-${crypto.randomUUID()}`);
      if (!localIntegrationPollingGuard.isCurrent(verificationTicket)) return;
      if (typeof accepted?.id !== 'string' || !accepted.id) throw new Error('服务未返回有效的验证任务，请刷新后重试。');
      const current = await waitForLocalIntegrationVerification(
        async (verificationId) => {
          if (!localIntegrationPollingGuard.isCurrent(verificationTicket)) return { status: 'cancelled' };
          const result = await api.localIntegrationVerification(verificationId);
          return localIntegrationPollingGuard.isCurrent(verificationTicket) ? result : { status: 'cancelled' };
        },
        accepted.id,
        { maxAttempts: 740, delay: 250 },
      );
      if (!localIntegrationPollingGuard.isCurrent(verificationTicket)) return;
      if (current.status !== 'completed') throw new Error(current?.error?.message || '本机真实验证未完成。');
      await loadCatalog(['localIntegrations']);
      if (!localIntegrationPollingGuard.isCurrent(verificationTicket)) return;
      success = current.outcome === 'available'
        ? `${labels[target]} 真实验证通过。`
        : `${labels[target]} 验证完成，请根据状态说明处理。`;
    } catch (error) {
      if (!localIntegrationPollingGuard.isCurrent(verificationTicket)) return;
      state.error = error?.message || '本机真实验证失败，请重试。';
      safeLog('local_integration_verification_failed', { status: error?.code || error?.name || 'unknown' });
    } finally {
      if (localIntegrationPollingGuard.isCurrent(verificationTicket)) {
        localVerificationTarget = ''; render();
      }
    }
    return;
  }
  if ('accountAdd' in data) {
    const accounts = Array.isArray(selectedConnectionConfiguration?.accounts) ? selectedConnectionConfiguration.accounts : [];
    selectedConnectionConfiguration = { ...(selectedConnectionConfiguration || {}), accounts: [...accounts, { id: `account-${accounts.length + 1}`, username: '' }] };
    render(); return;
  }
  if ('migrationReview' in data) {
    try { const preview = await api.connectionMigrationPreview(); catalog.connections.migration = preview; migrationOpen = true; delete catalog.errors.migration; }
    catch (error) { catalog.errors.migration = error.message; }
    render(); return;
  }
  if ('migrationCancel' in data) { migrationOpen = false; render(); return; }
  if ('sessionMenu' in data) {
    const id = data.sessionMenu;
    if (sessionMenu?.id === id) { sessionMenu = null; render(); return; }
    cancelProjectMenuTimers();
    const rect = clickedNavigationRect || button.getBoundingClientRect();
    const { left, top } = sessionMenuPosition(rect, { width: window.innerWidth, height: window.innerHeight });
    sessionMenu = { id, left, top }; sessionActionError = ''; render();
    document.querySelector('.session-action-menu [role="menuitem"]')?.focus({ preventScroll: true });
    return;
  }
  if ('menuRename' in data) {
    renameSession = catalog.sessions.find(item => item.id === data.menuRename) || null;
    if (renameSession) { renameDraft = renameSession.title || ''; sessionMenu = null; sessionActionError = ''; render(); document.querySelector('#rename-title')?.focus(); document.querySelector('#rename-title')?.select(); }
    return;
  }
  if ('menuDelete' in data) {
    deleteSession = catalog.sessions.find(item => item.id === data.menuDelete) || null;
    if (deleteSession) { sessionMenu = null; sessionActionError = ''; render(); document.querySelector('#delete-session-form button[type="submit"]')?.focus(); }
    return;
  }
  if ('renameHistory' in data) {
    event.preventDefault();
    renameSession = catalog.sessions.find(item => item.id === data.renameHistory) || null;
    if (renameSession) { renameDraft = renameSession.title || ''; sessionMenu = null; sessionActionError = ''; render(); document.querySelector('#rename-title')?.focus(); document.querySelector('#rename-title')?.select(); }
    return;
  }
  if ('deleteHistory' in data) {
    event.preventDefault();
    deleteSession = catalog.sessions.find(item => item.id === data.deleteHistory) || null;
    if (deleteSession) { sessionMenu = null; sessionActionError = ''; render(); document.querySelector('#delete-session-form button[type="submit"]')?.focus(); }
    return;
  }
  if ('cancelRename' in data) { const id = renameSession?.id; renameDraft = null; renameSession = null; sessionActionError = ''; render(); if (id) document.querySelector(`[data-session-menu="${id}"]`)?.focus({ preventScroll: true }); return; }
  if ('cancelDelete' in data) { const id = deleteSession?.id; deleteSession = null; sessionActionError = ''; render(); if (id) document.querySelector(`[data-session-menu="${id}"]`)?.focus({ preventScroll: true }); return; }
  if ('cancelPurge' in data) { purgeSession = null; sessionActionError = ''; render(); return; }
  if ('restoreSession' in data) {
    if (sessionActionBusy) return;
    sessionActionBusy = true; state.error = ''; render();
    try { await api.restoreSession(data.restoreSession); success = '会话已恢复。'; await loadCatalog(['deletedSessions', 'sessions']); }
    catch (error) { state.error = error.message; }
    finally { sessionActionBusy = false; render(); }
    return;
  }
  if ('purgeSession' in data) {
    purgeSession = catalog.deletedSessions.find(item => item.id === data.purgeSession) || null;
    sessionActionError = ''; render(); document.querySelector('#purge-session-form button[type="submit"]')?.focus();
    return;
  }
  if (await handleCapabilityClick(data)) return;
  if ('tabbitRefresh' in data) { await loadCatalog(['tabbit']); return; }
  if ('tabbitSelect' in data) { selectTabbit(data.tabbitSelect); return; }
  if ('removeTabbit' in data) { controller.removeTabbit(data.removeTabbit); render(); return; }
  if ('retryNativeSearch' in data && state.route.page === 'claw') { nativeSessionSearch.update(globalSearch, 'claw'); return; }
  if ('toggleSearch' in data) { if (searchOpen) { closeGlobalSearch(); return; } searchOpen = true; sidebarOpen = false; contextOpen = false; if (state.route.page === 'claw') nativeSessionSearch.update(globalSearch, 'claw'); render(); document.querySelector('#global-search')?.focus(); }
  if ('clearCapability' in data) { controller.setCapability(null); render(); }
  if ('removeTool' in data) { controller.setTools(state.toolIds.filter(id => id !== data.removeTool)); render(); }
  if ('removeMethod' in data) { controller.setMethods(state.methodIds.filter(id => id !== data.removeMethod)); render(); }
  if ('new' in data) { history.pushState(null, '', state.route.page === 'claw' ? '#/claw' : '#/fingpt'); await showRoute(); controller.setDraft(''); render(); document.querySelector('#prompt')?.focus(); }
  if ('refresh' in data) {
    success = '';
    state.error = '';
    if (isDataWorkspaceRoute(state.route)) await loadWorkbench();
    else if (state.route.page === 'operations') await loadOperations();
    else if (state.route.page === 'history' && state.route.historyView === 'deleted') await loadCatalog(['deletedSessions']);
    else if (state.route.page === 'settings') {
      const section = currentSettingsSection();
      if (section === 'local') {
        localIntegrationPollingGuard.invalidate(); officeAutoPollingGuard.invalidate(); officeConsentConfirmation = '';
        localVerificationTarget = '';
      }
      if (section === 'data') selectedConnectionConfiguration = null;
      if (['data', 'local'].includes(section)) {
        const scope = section;
        if (scope === 'data') connectionProbeBusy = true;
        else localIntegrationProbeBusy = true;
        render();
        try {
          const accepted = await api.startIntegrationProbeBatch(scope, `integration-${scope}-${crypto.randomUUID()}`);
          if (typeof accepted?.id !== 'string' || !accepted.id) throw new Error('服务未返回有效的全量检测批次。');
          const completed = await waitForIntegrationBatch((batchId) => api.integrationProbeBatch(batchId), accepted.id);
          await loadCatalog(settingsRefreshCatalogs(section));
          if (completed.status === 'completed_with_failures') {
            state.error = '全量检测已完成，但部分项目失败，请根据状态说明处理。';
          } else if (completed.status === 'completed') {
            success = section === 'data' ? '数据源已完成全量重新检测。' : '本机集成已完成全量重新检测。';
          } else {
            throw new Error('全量检测未完成，请查看服务日志。');
          }
        } catch (error) {
          state.error = error?.message || '全量检测失败，请重试。';
          safeLog('integration_probe_batch_failed', { status: error?.code || error?.name || 'unknown' });
        } finally {
          connectionProbeBusy = false;
          localIntegrationProbeBusy = false;
          render();
        }
      } else {
        const catalogs = settingsRefreshCatalogs(section);
        if (catalogs.length) await loadCatalog(catalogs);
      }
      if (section === 'data') {
        const selectedId = currentSettingsConnectionId();
        if (selectedId) await loadConnectionConfiguration(selectedId);
      }
    }
    else { await loadCatalog(); await controller.refresh(); }
  }
  if ('operationsRange' in data) { operationsRange = data.operationsRange; await loadOperations(); }
  if ('workbenchHandoff' in data) {
    if (workbenchBusy || !data.sourceSession) return;
    const current = workbenchOwner();
    const section = state.route.section;
    const assetContext = workbenchContext;
    workbenchBusy = true; state.error = ''; render();
    try {
      const datasetIds = JSON.parse(data.datasetIds || '[]');
      let context = assetContext;
      if (section !== 'assets') {
        if (datasetIds.length !== 1) throw new Error('请选择一个有效的查询快照。');
        const manifest = await api.datasetManifest(data.sourceSession, datasetIds[0]);
        if (!current()) return;
        if (!manifest.query || !manifest.query.parameters) throw new Error('查询快照缺少原始参数，无法交接。');
        context = { section, source: manifest.query.source, parameters: manifest.query.parameters, requested_at: manifest.retrieved_at, as_of: manifest.as_of };
      }
      const result = await api.handoff({
        source_session_id: data.sourceSession,
        target_mode: data.workbenchHandoff,
        section,
        dataset_ids: datasetIds,
        context,
      }, crypto.randomUUID());
      if (!current()) return;
      history.pushState(null, '', `#/${result.mode}?session=${encodeURIComponent(result.session_id)}`);
      const targetTicket = pageGeneration + 1;
      await showRoute();
      if (pageGeneration !== targetTicket || state.route.page !== result.mode || state.route.sessionId !== result.session_id) return;
      controller.setDraft(result.draft || '请基于冻结的页面资料继续研究。');
      success = '页面参数和数据集已冻结到新会话，确认草稿后再发送。';
      await loadCatalog(['sessions']);
      if (targetTicket === pageGeneration) render();
    } catch (error) { if (current()) state.error = error.message; safeLog('business_handoff_failed', { section, code: error.code || 'request_failed' }); }
    finally { if (current()) { workbenchBusy = false; render(); } }
  }
  if ('clawScheduleRefresh' in data) {
    if (state.route.page !== 'claw' || state.route.clawView !== 'plans' || catalog.pending.has('automations') || catalog.pending.has('automationRuns')) return;
    const ticket = pageGeneration;
    await loadCatalog(['automations', 'automationRuns']);
    if (ticket === pageGeneration && state.route.page === 'claw' && state.route.clawView === 'plans') document.querySelector('[data-claw-schedule-refresh]')?.focus({ preventScroll: true });
    return;
  }
  if ('reloadSession' in data) await showRoute();
  if ('toggleSidebar' in data) {
    const narrow = window.matchMedia('(max-width: 1050px)').matches;
    if (narrow) sidebarOpen = !sidebarOpen;
    else sidebarCollapsed = !sidebarCollapsed;
    conversationNavigation.view(state.route.page, { collapsed: sidebarCollapsed });
    contextOpen = false; render(); focusSidebarControl(document, narrow, narrow ? sidebarOpen : !sidebarCollapsed);
  }
  if ('toggleContext' in data) { if (window.matchMedia('(max-width: 1050px)').matches) contextOpen = !contextOpen; else contextCollapsed = !contextCollapsed; sidebarOpen = false; render(); }
  if ('collapseSidebar' in data) {
    if (window.matchMedia('(max-width: 1050px)').matches) sidebarOpen = false;
    else sidebarCollapsed = true;
    conversationNavigation.view(state.route.page, { collapsed: sidebarCollapsed });
    render(); focusSidebarControl(document, window.matchMedia('(max-width: 1050px)').matches);
  }
  if ('clawSidebarView' in data) {
    clawSidebarView = data.clawSidebarView === 'workspace' ? 'workspace' : 'sessions';
    safeLog('claw_sidebar_view_changed', { status: clawSidebarView });
    render();
    document.querySelector(`[data-claw-sidebar-view="${clawSidebarView}"]`)?.focus({ preventScroll: true });
  }
  if ('workspacePreview' in data) {
    const file = state.detail?.files?.find(item => item.id === data.workspacePreview);
    if (file) {
      selectedPreview = file.id; contextTab = 'files'; contextOpen = window.matchMedia('(max-width: 1050px)').matches; contextCollapsed = false; sidebarOpen = false;
      render();
      document.querySelector('[data-close-preview]')?.focus({ preventScroll: true });
    } else {
      safeLog('claw_workspace_preview_missing', {});
    }
  }
  if ('clawCase' in data || 'clawEditTask' in data) {
    const prompt = 'clawEditTask' in data ? `请查询任务 ID ${data.clawEditTask} 的当前定义。我想修改它，请先澄清修改内容，提出同一任务的待确认变更。` : clawCases.find(c => c.id === data.clawCase)?.text;
    if (prompt) {
      const prepared = await prepareClawExampleDraft(controller, prompt, {
        currentGeneration: () => pageGeneration,
        navigate: () => {
          if (state.route.clawView || state.route.sessionId || state.route.page !== 'claw') {
            history.pushState(null, '', '#/claw');
            return showRoute();
          }
        },
      });
      if (prepared) { render(); document.querySelector('#prompt')?.focus(); }
    }
  }
  if ('showAttention' in data) { contextOpen = window.matchMedia('(max-width: 1050px)').matches; contextCollapsed = false; contextTab = 'activity'; render(); }
  if ('continueResearch' in data && state.detail?.mode === 'fingpt' && state.detail.research_quality?.status === 'incomplete') {
    if (state.busy || state.stopping || isRunning(state.detail.status) || state.detail.can_cancel || state.detail.can_recheck_stop || state.detail.execution_restricted) return;
    if (!state.draft.trim()) controller.setDraft('请基于本会话已有研究和新补充资料，继续核验尚未通过的质量检查项；保留原报告并生成新版本。');
    safeLog('research_continuation_draft_prepared', {});
    render(); document.querySelector('#prompt')?.focus(); return;
  }
  if ('reportStage' in data && state.detail?.research_report?.sections?.some(section => section.id === data.reportStage)) { researchStage = data.reportStage; contextTab = 'notes'; render(); }
  if ('contextTab' in data) { researchStage = null; contextTab = data.contextTab; contextOpen = window.matchMedia('(max-width: 1050px)').matches; contextCollapsed = false; render(); }
  if ('closeDrawers' in data) { const wasSidebarOpen = sidebarOpen; sidebarOpen = false; contextOpen = false; render(); if (wasSidebarOpen) focusSidebarControl(document, window.matchMedia('(max-width: 1050px)').matches); }
  if ('upload' in data) document.querySelector('#file-input')?.click();
  if ('slashSearch' in data) { if (legacyComposerMenu) legacyComposerMenu.open = false; slashOpen = !slashOpen; tabbitOpen = false; tabbitCandidates = []; tabbitRequest += 1; slashIndex = 0; render(); document.querySelector('#prompt')?.focus(); }
  if ('removeAttachment' in data) controller.removeAttachment(data.removeAttachment);
  if ('noFormats' in data) { controller.setFormats([]); render(); }
  if ('documentCreate' in data && ['docx', 'xlsx', 'pptx'].includes(data.documentCreate) && state.detail?.id) {
    documentEditor = { creating: data.documentCreate, file: { name: '新文件' }, sessionId: state.detail.id, busy: false, error: '', draft: null }; render(); return;
  }
  if ('documentClose' in data) { documentEditor = null; render(); }
  if ('documentOpen' in data) {
    const file = state.detail?.files?.find(item => item.id === data.documentOpen);
    const format = file?.name?.split('.').pop()?.toLowerCase();
    if (!file || !['docx', 'xlsx', 'pptx'].includes(format)) return;
    const editor = { file, sessionId: state.detail.id, busy: true, result: null, error: '' };
    documentEditor = editor; render();
    try {
      const result = await api.documentOperation(editor.sessionId, { format, operation: 'read', mode: 'file', file_id: file.id });
      if (documentEditor === editor && state.detail?.id === editor.sessionId) editor.result = result;
    } catch (error) { if (documentEditor === editor) editor.error = error.message; }
    finally { editor.busy = false; render(); }
  }
  if ('preview' in data) { selectedPreview = data.preview; render(); }
  if ('closePreview' in data) { selectedPreview = null; render(); }
  if ('closeSkillDetail' in data) { capabilityController.close(); render(); }
  if ('skillDetail' in data) {
    const ticket = pageGeneration;
    capabilityDialogReturnSelector = `[data-cap-preview-trigger="${catalog.capabilities.find(item => item.id === data.skillDetail)?.kind || 'skill'}:${data.skillDetail}"]`;
    await capabilityController.open(data.skillDetail);
    if (ticket !== pageGeneration) return;
    if (state.route.page !== 'skills') { history.pushState(null, '', '#/skills'); await showRoute(); }
    focusCapabilityPreview();
  }
  if ('skillShortcut' in data) await selectCapability(data.skillShortcut);
  if ('useSkill' in data) await selectCapability(data.useSkill);
  if ('useMethod' in data) {
    const item = catalog.capabilities.find(capability => capability.id === data.useMethod && capability.kind === 'method' && capability.enabled && capability.version);
    if (!item) { state.error = '所选方法未启用或版本不可用。'; render(); return; }
    await goToResearchDraft();
    try { controller.setMethods([...state.methodIds, item.id]); }
    catch (error) { state.error = error.message; }
    render(); document.querySelector('#prompt')?.focus();
  }
  const id = state.detail?.id;
  if (!id) return;
  if ('docRef' in data) {
    contextCollapsed = false; contextOpen = window.matchMedia('(max-width: 1050px)').matches; contextTab = 'datasets'; render();
    const index = Number.parseInt(data.docRef, 10) - 1;
    const card = index >= 0 ? document.querySelectorAll('.context-panel .dataset-card')[index] : null;
    if (card) {
      card.classList.add('flash');
      const panel = card.closest('.context-panel');
      if (panel) {
        const top = card.getBoundingClientRect().top - panel.getBoundingClientRect().top + panel.scrollTop - 12;
        panel.scrollTo({ top: Math.max(0, top), behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
      }
      setTimeout(() => card.classList.remove('flash'), 2400);
    }
    return;
  }
  if ('copyAnswer' in data) {
    const message = (state.detail?.messages || []).find((item) => item.id === data.copyAnswer);
    if (message?.text) {
      try {
        await navigator.clipboard.writeText(message.text);
        copiedTransient = `answer:${message.id}`; render();
        setTimeout(() => { if (copiedTransient === `answer:${message.id}`) { copiedTransient = ''; render(); } }, 1600);
      } catch { state.error = '复制失败，请手动选择正文复制。'; render(); }
    }
    return;
  }
  if ('shareSession' in data) {
    try {
      await navigator.clipboard.writeText(globalThis.location.href);
      copiedTransient = 'share'; render();
      setTimeout(() => { if (copiedTransient === 'share') { copiedTransient = ''; render(); } }, 1600);
    } catch { state.error = '复制链接失败，请手动复制地址栏地址。'; render(); }
    return;
  }
  if ('retryRound' in data) {
    const source = (state.detail?.messages || []).find((item) => item.id === data.retryRound && item.role === 'user');
    const blocked = retryBlockReason();
    if (blocked) { state.error = blocked; render(); return; }
    if (source?.text) {
      controller.setDraft(source.text);
      await controller.send();
    }
    return;
  }
  if ('answerFeedback' in data) {
    const messageId = data.message;
    const value = ['good', 'bad'].includes(data.answerFeedback) ? data.answerFeedback : null;
    if (messageId && value) {
      answerFeedback.set(messageId, answerFeedback.get(messageId) === value ? null : value);
      render();
    }
    return;
  }
  if ('cancel' in data) { await controller.cancel(); await loadCatalog(['sessions']); }
  if ('approval' in data) await controller.action(() => api.approve(id, data.approval, data.decision));
  if ('upgrade' in data) {
    const upgraded = await controller.upgrade();
    if (upgraded?.id) { await showRoute(); await loadCatalog(['sessions']); }
  }
  if ('refreshFiles' in data) {
    const result = await controller.action(() => api.files(id), { refreshAfter: false });
    if (result?.items && state.detail?.id === id) { state.detail.files = result.items; render(); }
  }
});

function collectAnswers(form, question) {
  try { return collectQuestionAnswers(new FormData(form), question.items); }
  catch (error) { safeLog('invalid_question_selection'); state.error = error.message; render(); return null; }
}

function composerTaskPending() { return Boolean(state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || state.detail.can_recheck_stop || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status))); }
function currentComposerRows() {
  return composerMenuRows(composerMenu, { skills: catalog.capabilities, methods: catalog.capabilities.filter(item => item.kind === 'method'), methodIds: state.methodIds, expectedFormats: state.expectedFormats, models: catalog.models, model: catalog.runtime?.model, modelProvider: catalog.runtime?.provider, modelEndpoint: catalog.runtime?.connection?.base_url, disabled: Boolean(state.busy || state.loading || state.route.sessionId && !state.detail || state.detail?.execution_restricted || state.detail?.execution_context), busy: state.busy || state.stopping || composerTaskPending(), uploadsAllowed: canUploadToSession(state.detail, state.sourceScope) });
}
function closeComposerMenu(consume = false) {
  const entry = composerMenu.entry;
  const modelView = composerMenu.view === 'models';
  if (consume && entry === 'slash') controller.setDraft(consumeComposerSlash(state.draft));
  composerMenu = closedComposerMenu(); render();
  document.getElementById(entry === 'slash' ? 'prompt' : modelView ? 'composer-model' : 'composer-add')?.focus({ preventScroll: true });
}
function focusComposerMenu() {
  const rows = currentComposerRows();
  if (!rows[composerMenu.index] || rows[composerMenu.index].disabled) composerMenu.index = Math.max(0, rows.findIndex(row => !row.disabled));
  render();
  const row = document.getElementById(`composer-command-${composerMenu.index}`);
  (document.getElementById('composer-command-search') || (row && !row.disabled ? row : null) || document.getElementById('claw-composer-menu'))?.focus({ preventScroll: true });
}
function backComposerMenu() {
  if (composerMenu.view === 'root') { closeComposerMenu(); return; }
  composerMenu = openComposerMenu(composerMenu.entry, 'root', composerMenu.entry === 'slash' ? composerSlashQuery(state.draft) || '' : '');
  render();
  const prompt = document.getElementById('prompt');
  if (composerMenu.entry === 'slash' && prompt && !prompt.disabled) prompt.focus({ preventScroll: true });
  else focusComposerMenu();
}
async function activateComposerRow(row) {
  if (!row || row.disabled || state.detail?.execution_restricted || state.detail?.execution_context) return;
  try {
    if (row.action === 'view') {
      composerMenu = openComposerMenu(composerMenu.entry, row.value); focusComposerMenu(); return;
    }
    if (state.busy || state.stopping || composerTaskPending()) return;
    if (row.action === 'upload') {
      if (!canUploadToSession(state.detail, state.sourceScope)) return;
      closeComposerMenu(true); document.getElementById('file-input')?.click(); return;
    }
    if (row.action === 'capability') {
      await selectCapability(row.value);
      if (state.capability?.id === row.value) closeComposerMenu();
      return;
    }
    if (row.action === 'method') {
      const ids = state.methodIds;
      if (!ids.includes(row.value) && ids.length >= 3) return;
      controller.setMethods(ids.includes(row.value) ? ids.filter(id => id !== row.value) : [...ids, row.value]);
    } else if (row.action === 'format') controller.setFormats(nextComposerFormats(state.expectedFormats, row.value));
    else if (row.action === 'model') {
      const menu = composerMenu, generation = pageGeneration, draft = state.draft;
      const pending = configureComposerModel(row.value);
      document.getElementById('claw-composer-menu')?.focus({ preventScroll: true });
      const configured = await pending;
      if (configured && generation === pageGeneration && menu === composerMenu && draft === state.draft) closeComposerMenu(true);
      return;
    }
    safeLog('claw_composer_selection_changed'); render();
    document.getElementById(`composer-command-${composerMenu.index}`)?.focus({ preventScroll: true });
  } catch { safeLog('claw_composer_selection_failed'); state.error = '无法应用所选选项，请刷新目录后重试。'; render(); }
}

function currentSlashMatches() {
  return skillMatches(state.draft.trimStart().replace(/^\//, ''), catalog.capabilities).slice(0, 6);
}

async function goToResearchDraft() {
  if (['fingpt', 'claw'].includes(state.route.page)) return;
  const route = researchDraftRoute;
  history.pushState(null, '', `#/${route.page}${route.sessionId ? `?session=${encodeURIComponent(route.sessionId)}` : ''}`);
  await showRoute();
}

async function selectCapability(id) {
  const item = catalog.capabilities.find(cap => cap.id === id);
  const eligibility = reportWorkflowEligibility(item);
  if (eligibility.report && !eligibility.eligible) { state.error = `报告 Workflow 暂不可用：${eligibility.reason}`; render(); return; }
  if (!eligibility.report && (!item?.enabled || !item.version)) { state.error = '所选能力未启用或尚未发布，请刷新能力目录。'; render(); return; }
  capabilityDialogReturnSelector = '';
  if (capabilityPreviewIsOpen()) capabilityController.close();
  await goToResearchDraft();
  controller.setCapability(eligibility.report ? { ...item, version: eligibility.version } : item);
  if (state.draft.trimStart().startsWith('/')) controller.setDraft(state.route.page === 'claw' ? consumeComposerSlash(state.draft) : '');
  slashOpen = false; globalSearch = ''; searchOpen = false; nativeSessionSearch.close(); render();
  document.querySelector('#prompt')?.focus();
}

function captureEditor() {
  const form = document.querySelector('#cap-editor-form');
  if (form && capabilityState.editor && !capabilityState.busy) capabilityState.editor = readEditor(new FormData(form), capabilityState.editor);
}

async function loadWorkflowVersion() {
  const ref = state.detail?.capability;
  if (ref?.kind !== 'workflow') return;
  const key = `${ref.id}:${ref.version}`;
  if (workflowVersions.has(key)) return;
  workflowVersions.set(key, { ...ref, steps: [] });
  const versionError = '未能读取本次 Workflow 的不可变版本步骤；实际活动仍以 DSH 为准。';
  try {
    const version = await api.capabilityVersion(ref.id, ref.version);
    workflowVersions.set(key, { ...version, kind: 'workflow' });
    if (state.error === versionError) state.error = '';
  } catch { workflowVersions.delete(key); safeLog('workflow_version_read_failed'); state.error = versionError; }
  render();
}

async function handleCapabilityClick(data) {
  const cap = capabilityState;
  if ('capRefresh' in data) {
    await loadCatalog(['capabilities', 'tools', 'reportWorkflows', 'dataCatalog', 'connections', ...(cap.kindFilter === 'workflow' && cap.view === 'plans' ? ['automations', 'automationRuns', 'deliveryChannels'] : [])]);
    if (cap.kindFilter === 'tool' && cap.view === 'market') await loadMCPMarketplace({ reloadRegistries: true });
    return true;
  }
  if ('createAutomation' in data) { automationFormOpen = true; render(); document.querySelector('[data-automation-form] input')?.focus(); return true; }
  if ('closeAutomationForm' in data) { automationFormOpen = false; render(); return true; }
  if ('runAutomation' in data || 'enableAutomation' in data || 'disableAutomation' in data || 'deleteAutomation' in data) {
    const action = 'runAutomation' in data ? 'run' : 'enableAutomation' in data ? 'enable' : 'disableAutomation' in data ? 'disable' : 'delete';
    const id = data[`${action}Automation`];
    if (action === 'delete' && !window.confirm('移除此 Automation？已有运行记录会保留。')) return true;
    automationBusy = true; state.error = ''; success = ''; render();
    try {
      if (action === 'run') await api.runAutomation(id);
      else if (action === 'enable') await api.enableAutomation(id);
      else if (action === 'disable') await api.disableAutomation(id);
      else await api.deleteAutomation(id);
      success = ({ run: 'Automation 已受理；研究失败时不会自动重试。', enable: 'Automation 已启用。', disable: 'Automation 已停用。', delete: 'Automation 已移除。' })[action];
      await loadCatalog(['automations', 'automationRuns']);
    } catch (error) { state.error = error.message; }
    finally { automationBusy = false; render(); }
    return true;
  }
  if ('retryAutomationRun' in data) {
    automationBusy = true; state.error = ''; success = ''; render();
    try {
      await api.retryAutomationRun(data.retryAutomationRun);
      success = '已创建关联原运行记录的手动重试。';
      await loadCatalog(['automations', 'automationRuns']);
    } catch (error) { state.error = error.message; }
    finally { automationBusy = false; render(); }
    return true;
  }
  if ('migrateReportSchedule' in data) {
    if (!window.confirm('迁移此旧报告日程？只有新 Automation 保存成功后，旧日程才会停用。')) return true;
    automationBusy = true; state.error = ''; success = ''; render();
    try {
      await api.applyReportScheduleMigrations([data.migrateReportSchedule]);
      success = '旧报告日程已迁移为锁定版本的 Automation。';
      await loadCatalog(['automations', 'automationRuns', 'reportWorkflows']);
    } catch (error) { state.error = error.message; }
    finally { automationBusy = false; render(); }
    return true;
  }
  if ('capKind' in data) { cap.kind = data.capKind; cap.kindFilter = data.capKind; cap.category = ''; cap.query = ''; cap.dataDetail = null; cap.dataDetailKind = ''; reportWorkflowDetail = null; render(); return true; }
  if ('closeReportWorkflow' in data) { reportWorkflowDetail = null; history.pushState(null, '', '#/reports'); await showRoute(); return true; }
  if ('refreshReportWorkspace' in data) { if (!reportWorkflowBusy) await loadReportPage(); return true; }
  if (reportOperations.matches(data)) return reportOperations.handle(data);
  if ('reportWorkflowDetail' in data) {
    history.pushState(null, '', reportHref(data.reportWorkflowDetail));
    await showRoute(); return true;
  }
  if ('dataView' in data) { cap.dataView = data.dataView; cap.category = ''; cap.query = ''; cap.dataMarket = ''; cap.dataStatus = ''; cap.dataAuth = ''; render(); return true; }
  if ('dataCapabilityDetail' in data) {
    capabilityDialogReturnSelector = `[data-cap-preview-trigger="data:${data.dataCapabilityDetail}"]`;
    const ticket = pageGeneration;
    const result = await capabilityController.run(() => api.dataCapability(data.dataCapabilityDetail));
    if (ticket !== pageGeneration) return true;
    if (result && state.route.page !== 'skills') { history.pushState(null, '', '#/skills?kind=data'); await showRoute(); }
    if (result) { cap.dataDetail = result; cap.dataDetailKind = 'capability'; cap.form = ''; render(); focusCapabilityPreview(); }
    return true;
  }
  if ('dataSourceDetail' in data) {
    const result = await capabilityController.run(() => api.dataSource(data.dataSourceDetail));
    if (result) { cap.dataDetail = result; cap.dataDetailKind = 'source'; cap.form = 'manage'; render(); }
    return true;
  }
  if ('probeSource' in data) {
    const key = `probe-${data.probeSource}-${crypto.randomUUID()}`;
    const accepted = await capabilityController.run(() => api.probeDataSource(data.probeSource, key));
    if (!accepted?.id) return true;
    cap.probe = accepted; render();
    for (let attempt = 0; attempt < 20 && cap.probe?.status === 'checking'; attempt++) {
      await new Promise(resolve => setTimeout(resolve, 250));
      const current = await capabilityController.run(() => api.dataProbe(accepted.id));
      if (!current) break;
      cap.probe = current;
      if (current.status !== 'checking') {
        await loadCatalog(['dataCatalog']);
        if (cap.dataDetailKind === 'source') {
          const detail = await capabilityController.run(() => refreshProbedSourceDetail(api, cap.dataDetail, data.probeSource));
          if (detail) cap.dataDetail = detail;
        }
        render();
      } else render();
    }
    return true;
  }
  if ('useDataTool' in data) {
    const tool = catalog.tools.find(item => item.id === data.useDataTool && item.selectable);
    if (!tool) { state.error = '这项数据能力目前没有可调用来源。'; render(); return true; }
    capabilityDialogReturnSelector = ''; if (capabilityPreviewIsOpen()) capabilityController.close();
    await goToResearchDraft(); controller.setTools([...state.toolIds, tool.id]); render(); document.querySelector('#prompt')?.focus(); return true;
  }
  if ('capClose' in data) { if (!closeCapabilityPreview()) capabilityController.close(); return true; }
  if ('capManage' in data) { cap.form = 'manage'; render(); document.querySelector('#main')?.scrollTo({ top: 0 }); return true; }
  if ('capCancelEdit' in data) { cap.form = ''; cap.editor = null; render(); return true; }
  if ('capCreate' in data) { capabilityController.create(data.capCreate); return true; }
  if ('capImport' in data) { document.querySelector('#cap-import-file')?.click(); return true; }
  if ('capEdit' in data) { capabilityController.edit(); return true; }
  if ('capCopy' in data) { cap.form = 'copy'; cap.copy = {}; render(); return true; }
  if ('capVersions' in data) { await capabilityController.versions(); return true; }
  if ('capVersion' in data) { await capabilityController.version(Number(data.capVersion)); return true; }
  if ('capAction' in data) { await capabilityController.action(data.capAction); return true; }
  if ('capRollback' in data) { await capabilityController.action('rollback', Number(data.capRollback)); return true; }
  if ('toolDetail' in data) {
    capabilityDialogReturnSelector = `[data-cap-preview-trigger="tool:${data.toolDetail}"]`;
    cap.tool = catalog.tools.find(tool => tool.id === data.toolDetail); cap.form = '';
    if (state.route.page !== 'skills') { history.pushState(null, '', '#/skills'); await showRoute(); }
    else render();
    focusCapabilityPreview(); return true;
  }
  if ('useTool' in data) {
    const tool = catalog.tools.find(item => item.id === data.useTool && item.selectable);
    if (!tool) { state.error = '此工具不可单独选择。'; render(); return true; }
    capabilityDialogReturnSelector = ''; if (capabilityPreviewIsOpen()) capabilityController.close();
    await goToResearchDraft(); controller.setTools([...state.toolIds, tool.id]); render(); document.querySelector('#prompt')?.focus(); return true;
  }
  if ('capArtifact' in data) {
    const ticket = pageGeneration;
    if (!creationArtifacts(state.detail).some(file => file.id === data.capArtifact)) { state.error = '请选择专用创建会话的实际候选产物。'; render(); return true; }
    const result = await capabilityController.fromArtifact(state.detail.id, data.capArtifact);
    if (ticket !== pageGeneration) return true;
    if (result) { history.pushState(null, '', '#/skills'); await showRoute(); }
    else { state.error = cap.error; render(); }
    return true;
  }
  if (!cap.editor) return false;
  const editActions = ['inputAdd', 'inputRemove', 'stepAdd', 'stepRemove', 'stepMove', 'packageFileAdd', 'packageFileRemove', 'reviewScript'];
  if (!editActions.some(key => key in data)) return false;
  captureEditor();
  const editor = cap.editor;
  if ('inputAdd' in data) editor.metadata.inputs.push({ name: '', label: '', type: 'text', required: true });
  if ('inputRemove' in data) editor.metadata.inputs.splice(Number(data.inputRemove), 1);
  if ('stepAdd' in data) editor.steps.push(newWorkflowStep());
  if ('stepRemove' in data) editor.steps.splice(Number(data.stepRemove), 1);
  let stepFocus = '';
  if ('stepMove' in data) {
    const feedback = moveStepWithFeedback(editor.steps, Number(data.stepMove), Number(data.direction));
    editor.steps = feedback.steps; cap.stepAnnouncement = feedback.announcement; stepFocus = feedback.focusId;
  }
  if ('packageFileAdd' in data) editor.files.push({ path: '', content: '' });
  if ('packageFileRemove' in data) { editor.files.splice(Number(data.packageFileRemove), 1); editor.reviewed_scripts = []; }
  if ('reviewScript' in data) await capabilityController.run(async () => {
    const file = editor.files[Number(data.reviewScript)];
    if (!file || typeof file.content !== 'string' || !/^scripts\/.*\.py$/.test(file.path)) throw new Error('只可审查当前候选的研究 Python 脚本。');
    const hash = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(file.content));
    file.sha256 = [...new Uint8Array(hash)].map(byte => byte.toString(16).padStart(2, '0')).join('');
    editor.reviewed_scripts = [...new Set([...editor.reviewed_scripts, file.sha256])];
    cap.success = '已记录你对当前脚本字节的审查确认；仍需保存并检查。';
  });
  render();
  if (stepFocus) document.getElementById(stepFocus)?.focus({ preventScroll: true });
  return true;
}

controller.subscribe(() => { catalog.sessions = reconcileSessionSummary(catalog.sessions, state.detail); render(); void loadWorkflowVersion(); });
window.addEventListener('hashchange', () => { clearTimeout(localStatusExpiryTimer); executionEvidenceExpiry.cancel(); void showRoute(); });
window.addEventListener('pagehide', () => executionEvidenceExpiry.cancel());
window.addEventListener('pageshow', () => { if (root.querySelector('[data-connection-workbench]')) render(); });
window.addEventListener('visibilitychange', () => {
  if (!document.hidden && state.detail?.status === 'completed') render();
  if (!document.hidden && state.route.page === 'settings' && currentSettingsSection() === 'local') void loadCatalog(['localIntegrations']);
}, true);
window.addEventListener('resize', () => { if (state.route.page === 'aihot') root.querySelectorAll('.aihot-faces[open]').forEach(item => { item.open = false; }); const nav = conversationNavigation.state(state.route.page); if (sessionMenu || nav?.menu) { sessionMenu = null; if (nav) nav.menu = null; render(); } });
window.addEventListener('scroll', event => {
  if (state.route.page === 'aihot' && !event.target?.closest?.('.aihot-participants')) root.querySelectorAll('.aihot-faces[open]').forEach(item => { item.open = false; });
  if (!sessionMenu) return;
  // Rebuilding the sidebar restores its scrollTop asynchronously. That is not
  // a user scroll and must not immediately dismiss the menu just opened.
  const list = event.target;
  if (list?.closest?.('[role="menu"]')) return;
  const mode = list?.closest?.('[data-nav-mode]')?.dataset.navMode;
  if (list?.matches?.('.nav-scroll') && list.scrollTop === (conversationNavigation.state(mode)?.scrollTop || 0)) return;
  sessionMenu = null; render();
}, true);
document.querySelector('.skip-link').addEventListener('click', (event) => { event.preventDefault(); document.querySelector('#main')?.focus(); });
window.addEventListener('unhandledrejection', (event) => { event.preventDefault(); safeLog('unhandled_async_error'); state.error = '操作出现异常，请刷新状态后重试。'; render(); });
await showRoute();
await loadCatalog();
