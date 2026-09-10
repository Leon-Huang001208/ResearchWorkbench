import { createAPI, createController, parseRoute, legacyRouteTarget, isRunning, safeLog, collectQuestionAnswers, reconcileSessionSummary, waitForDataProbe, waitForLocalIntegrationProbe, waitForLocalIntegrationVerification } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { badge, empty, renderConversation, renderDeleteConfirm, renderHistory, renderPurgeConfirm, renderRename } from './views.mjs';
import { icon } from './icons.mjs';
import { renderComposer, renderQuickSkills, slashKey, skillMatches } from './composer.mjs';
import { renderResearchAttention, renderClawWorkspaceCanvas, renderContextPanel, renderPrimaryRail, renderSidebar, renderTopbar } from './shell.mjs';

import { createCapabilityController, refreshProbedSourceDetail } from './capability-controller.mjs';
import { capabilityTabKey, reportWorkflowEligibility, renderCapabilityDetail, renderToolDetail, renderCreationArtifacts, creationArtifacts } from './capabilities.mjs';
import { capabilityWorkspaceKindKey, renderCapabilityPreviewDialog, renderCapabilityWorkspace } from './capability-workspace.mjs';
import { renderDataCapabilityDetail, renderDataSourceDetail } from './data-catalog.mjs';
import { renderCapabilityEditor, renderCreationForm, renderCopyForm, readEditor, moveStepWithFeedback, newWorkflowStep } from './capability-editor.mjs';
import { readWorkbenchQuery, renderWorkbench } from './workbench.mjs';
import { readAssetObservation } from './asset-workspace.mjs';
import { renderOperations } from './operations.mjs';
import { renderReportWorkflowDetail, renderReportWorkflowShelf } from './report-workflows.mjs';
import { buildConfigurationPayload, createLocalIntegrationPollingGuard } from './connections.mjs';
import { renderSettingsPage, resolveSettingsSection, settingsConnectionId, settingsRefreshCatalogs } from './settings.mjs';

const api = createAPI();
const root = document.querySelector('#app');
const catalog = { runtime: null, localIntegrations: { categories: [], items: [], summary: {}, service: {} }, connections: { groups: [], sources: [], platform: {}, migration: {} }, models: [], sessions: [], deletedSessions: [], workspaces: [], capabilities: [], tools: [], reportWorkflows: [], artifacts: [], dataCatalog: { summary: {}, capabilities: [], sources: [], bindings: [] }, errors: {}, modelFailures: [] };
let selectedWorkspace = ''; let selectedPreview = null; let historyFilter = ''; let success = ''; let sidebarOpen = false; let sidebarCollapsed = false; let clawSidebarView = 'sessions'; let contextOpen = false; let contextTab = 'activity'; let globalSearch = ''; let slashOpen = false;
let searchOpen = false; let slashIndex = 0; let contextCollapsed = true;
let quickCategory = '';
let researchDraftRoute = { page: 'fingpt', sessionId: null };
let workbenchQueries = []; let workbenchContext = {}; let workbenchBusy = false;
let assetState = { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [] };
let operationsRange = '7d';
let operationsData = { usage: null, tools: null, datahub: null, services: null, storage: null };
let reportWorkflowDetail = null; let reportWorkflowBusy = false;
let selectedConnectionConfiguration = null; let migrationOpen = false; let connectionDetailOpen = true; let connectionProbeBusy = false; let localIntegrationProbeBusy = false; let localVerificationTarget = '';
const workflowVersions = new Map();
let pageGeneration = 0;
let renameDraft = null;
let renameSession = null; let deleteSession = null; let purgeSession = null;
let sessionMenu = null; let sessionActionBusy = false; let sessionActionError = '';
let capabilityDialogReturnSelector = '';
const questionDrafts = new Map();
const controller = createController({ api, onNavigate: (hash) => { history.pushState(null, '', hash); } });
const state = controller.state;
const capabilityController = createCapabilityController({ api, onChange: () => render(), onCatalogChange: () => loadCatalog(['capabilities']) });
const capabilityState = capabilityController.state;
const localIntegrationPollingGuard = createLocalIntegrationPollingGuard(
  () => state.route.page === 'settings' && currentSettingsSection() === 'local',
);

function runtimeLabel() {
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

function composer() {
  const disabled = state.busy || state.loading || Boolean(state.route.sessionId && !state.detail);
  const taskPending = state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status));
  return renderComposer({ models: catalog.models, model: catalog.runtime?.model, page: state.route.page, draft: state.draft, attachments: state.attachments, expectedFormats: state.expectedFormats, skills: catalog.capabilities, skillId: state.skillId, disabled, busy: state.busy, taskPending, detail: state.detail, slashOpen, slashIndex, capability: state.capability, toolIds: state.toolIds, tools: catalog.tools, runtimeReady: catalog.runtime?.connected === true && catalog.runtime?.credential_configured !== false });
}

function landing() {
  const claw = state.route.page === 'claw';
  return `<div class="landing ${claw ? 'claw-landing' : 'fingpt-landing'}"><div class="greeting">${claw ? `<span class="mode-label">${icon('layers')}Claw</span>` : ''}<h1>${claw ? '把研究目标，变成可用成果。' : '从一个问题，开始研究。'}</h1><p class="landing-subtitle">${claw ? '说明目标、资料与交付要求，在一个空间推进研究。' : '读懂资料，比较公司，探索行业。'}</p></div>${composer()}${claw ? renderReportWorkflowShelf(catalog.reportWorkflows, { busy: reportWorkflowBusy, compact: true }) : ''}${renderQuickSkills(catalog.capabilities, { page: state.route.page, category: quickCategory })}</div>`;
}

function researchPage() {
  if (state.loading) return `<div class="loading-state" role="status">正在读取会话…</div>`;
  if (state.route.sessionId && !state.detail) return `${empty('暂时无法读取这个会话', '检查连接后重试，输入内容仍会保留。')}<button class="button" data-reload-session>重新读取</button>`;
  if (!state.detail) return landing();
  const detail = state.detail;
  const workspaceView = detail.mode === 'claw' && clawSidebarView === 'workspace';
  const canvas = workspaceView ? renderClawWorkspaceCanvas({ detail, selectedPreview, busy: state.busy }) : `<div id="messages" class="messages" aria-label="会话消息">${renderConversation(detail, questionDrafts)}</div>`;
  return `<header class="page-header"><div class="session-title"><div class="eyebrow">${detail.mode === 'claw' ? 'CLAW · AGENT RESEARCH' : 'FINGPT · RESEARCH SESSION'}</div><h1>${e(detail.title || '未命名会话')}</h1><div class="session-meta">${badge(detail.status)}${detail.model ? `<span>${e(detail.model)}</span>` : ''}</div></div><div class="button-row">${detail.mode !== 'claw' ? `<button class="button small" data-upgrade ${state.busy || isRunning(detail.status) ? 'disabled' : ''}>升级为 Claw ↗</button>` : ''}<button class="button small context-toggle" data-toggle-context aria-expanded="${window.matchMedia('(max-width: 1050px)').matches ? contextOpen : !contextCollapsed}">活动与文件</button></div></header>${notice(state.streamError, 'warning')}${renderCreationArtifacts(detail, state.busy || isRunning(detail.status))}${detail.capability ? `<p class="small muted">所选能力版本：${e(detail.capability.id)} · v${e(detail.capability.version)}（选择记录，不代表每个工具已执行）</p>` : ''}${renderResearchAttention(detail)}${canvas}<div class="composer-dock">${composer()}</div>`;
}

function settingsPage() {
  return renderSettingsPage({
    route: state.route,
    runtime: catalog.runtime,
    models: catalog.models,
    runtimeLabel: runtimeLabel(),
    busy: state.busy || connectionProbeBusy || localIntegrationProbeBusy || Boolean(localVerificationTarget),
    modelFailures: catalog.modelFailures,
    connections: catalog.connections,
    localIntegrations: catalog.localIntegrations,
    localVerificationTarget,
    selectedConfiguration: selectedConnectionConfiguration,
    migrationOpen,
    connectionDetailOpen,
    hash: location.hash,
  });
}

function currentSettingsSection() {
  return resolveSettingsSection(state.route, catalog.connections.sources);
}

function currentSettingsConnectionId() {
  return settingsConnectionId(location.hash, catalog.connections.sources, currentSettingsSection());
}

function mainPage() {
  if (['fingpt', 'claw'].includes(state.route.page)) return researchPage();
  if (state.route.page === 'settings') return settingsPage();
  if (state.route.page === 'workbench') return workbenchPage();
  if (state.route.page === 'operations') return operationsPage();
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

function workbenchPage() {
  return renderWorkbench({ section: state.route.section || 'market', catalog: catalog.dataCatalog, queries: workbenchQueries, artifacts: catalog.artifacts, busy: workbenchBusy, assetState });
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
  if (reportWorkflowDetail) return messages + renderReportWorkflowDetail(reportWorkflowDetail, { busy: reportWorkflowBusy });
  const workspace = renderCapabilityWorkspace({
    capabilities: catalog.capabilities, tools: catalog.tools, reportWorkflows: catalog.reportWorkflows,
    dataCatalog: catalog.dataCatalog, connections: catalog.connections, view: cap.view, kind: cap.kindFilter,
    source: cap.source, category: cap.category, status: cap.status, query: cap.query,
    dataMarket: cap.dataMarket, dataStatus: cap.dataStatus, dataAuth: cap.dataAuth, probe: cap.probe,
    busy: cap.busy || reportWorkflowBusy,
    error: catalog.errors.capabilities || catalog.errors.tools || catalog.errors.dataCatalog || catalog.errors.connections || '',
  });
  return messages + workspace + renderCapabilityPreviewDialog({ detail: cap.detail, tool: cap.tool, dataDetail: cap.dataDetail, dataDetailKind: cap.dataDetailKind, busy: cap.busy });
}

function sidebar() {
  return renderSidebar({ page: state.route.page, sessionId: state.route.sessionId, sessions: catalog.sessions, workspaces: catalog.workspaces, selectedWorkspace, collapsed: sidebarCollapsed, mobileOpen: sidebarOpen, detail: state.detail, clawSidebarView, openMenuId: sessionMenu?.id });
}

function sessionActionsLayer() {
  const menuSession = sessionMenu ? catalog.sessions.find(item => item.id === sessionMenu.id) : null;
  const menu = menuSession ? `<div class="session-action-menu" role="menu" aria-label="会话操作" style="--menu-top:${sessionMenu.top}px;--menu-left:${sessionMenu.left}px"><button type="button" role="menuitem" data-menu-rename="${e(menuSession.id)}">${icon('rename')}<span>重命名</span></button><button type="button" role="menuitem" class="danger-item" data-menu-delete="${e(menuSession.id)}" ${isRunning(menuSession.status) ? 'disabled aria-describedby="session-delete-reason"' : ''}>${icon('trash')}<span>删除</span></button>${isRunning(menuSession.status) ? '<p id="session-delete-reason" class="menu-reason">任务运行或等待处理时不能删除</p>' : ''}</div>` : '';
  const dialog = renameSession
    ? renderRename(renameDraft || '', sessionActionError, sessionActionBusy)
    : deleteSession
      ? renderDeleteConfirm(deleteSession, sessionActionError, sessionActionBusy)
      : purgeSession
        ? renderPurgeConfirm(purgeSession, sessionActionError, sessionActionBusy)
        : '';
  return menu + dialog;
}

function primaryRail() {
  const narrow = window.matchMedia('(max-width: 1050px)').matches;
  return renderPrimaryRail({
    page: state.route.page,
    section: state.route.section,
    secondaryOpen: narrow ? sidebarOpen : !sidebarCollapsed,
  });
}

function contextPanel() {
  return renderContextPanel({ detail: state.detail, selectedTab: contextTab, mobileOpen: contextOpen, selectedPreview, busy: state.busy, workflow: state.detail?.capability ? workflowVersions.get(`${state.detail.capability.id}:${state.detail.capability.version}`) : null });
}

function render() {
  const active = document.activeElement; const focusId = active?.id;
  const selection = active && ['TEXTAREA', 'INPUT'].includes(active.tagName) && active.type !== 'password' ? { start: active.selectionStart, end: active.selectionEnd } : null;
  const mainScroll = document.querySelector('#main')?.scrollTop || 0;
  const research = ['fingpt', 'claw'].includes(state.route.page);
  const hasSecondary = research && !sidebarCollapsed;
  const hasContext = research && Boolean(state.detail) && !contextCollapsed;
  const searchableCapabilities = [...catalog.capabilities, ...catalog.tools, ...catalog.reportWorkflows.map(item => ({ ...item, kind: 'report-workflow' })), ...(catalog.dataCatalog.capabilities || [])];
  root.innerHTML = `<div class="app-shell ${hasContext ? '' : 'wide-page'} ${hasSecondary ? 'has-secondary' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${sidebarOpen ? 'navigation-open' : ''} ${hasContext ? 'context-open' : ''}">${renderTopbar({ page: state.route.page, section: state.route.section, settingsSection: state.route.page === 'settings' ? currentSettingsSection() : '', detail: state.detail, runtimeLabel: runtimeLabel(), runtime: catalog.runtime, models: catalog.models, busy: state.busy, search: globalSearch, sessions: catalog.sessions, skills: searchableCapabilities, searchOpen })}${primaryRail()}${sidebar()}<main id="main" tabindex="-1"><div class="page-content">${notice(state.error)}${Object.entries(catalog.errors).map(([name, error]) => notice(`${({ runtime: '运行时', models: '模型目录', workspaces: '工作空间', sessions: '会话历史', deletedSessions: '已删除会话', capabilities: '能力目录', tools: '工具目录', reportWorkflows: '报告 Workflow', dataCatalog: '数据目录', connections: '连接中心', localIntegrations: '本机集成诊断', connectionConfiguration: '来源配置', migration: '旧配置迁移' })[name] || name}：${error}`)).join('')}${notice(success, 'success')}${mainPage()}</div></main>${hasContext || contextOpen ? contextPanel() : ''}</div>${sidebarOpen || contextOpen ? '<button class="mobile-backdrop" data-close-drawers aria-label="关闭面板"></button>' : ''}${sessionActionsLayer()}`;
  window.ResearchWebTheme?.syncControls();
  document.querySelector('#main').scrollTop = mainScroll;
  if (focusId) {
    const replacement = document.getElementById(focusId);
    if (replacement && !replacement.disabled) { replacement.focus({ preventScroll: true }); if (selection && selection.start !== null) replacement.setSelectionRange?.(selection.start, selection.end); }
  }
  if (state.busy) root.querySelectorAll('[data-approval], [data-upload], .question-form button, #rename-form button').forEach((button) => { button.disabled = true; });
  document.title = `${state.detail?.title || (state.route.page === 'workbench' && state.route.section === 'assets' ? '资产观察' : ({ fingpt: 'FinGPT', claw: 'Claw', workbench: '研究台', history: '研究历史', skills: '能力中心', operations: '运行与用量', settings: '设置' })[state.route.page])} · Research Workbench`;
}

async function loadCatalog(names = ['runtime', 'models', 'workspaces', 'sessions', 'capabilities', 'tools', 'reportWorkflows']) {
  await Promise.all(names.map(async (name) => {
    try {
      const data = name === 'deletedSessions' ? await api.sessions('deleted') : await api[name]();
      if (name === 'runtime') catalog.runtime = data;
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
      };
      else if (name === 'artifacts') catalog.artifacts = data.items || [];
      else catalog[name] = data.items || [];
      delete catalog.errors[name];
    } catch (error) { catalog.errors[name] = error.message; if (name === 'runtime') catalog.runtime = null; }
  }));
  render();
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

async function loadWorkbench() {
  const section = state.route.section || 'market';
  if (section === 'assets') {
    await Promise.all([loadCatalog(['dataCatalog']), loadAssetWorkspace()]);
    render();
    return;
  }
  await Promise.all([
    loadCatalog(['dataCatalog', 'artifacts']),
    (async () => {
      try {
        const data = await api.dataQueries(section);
        workbenchQueries = Array.isArray(data.items) ? data.items : [];
        delete catalog.errors.workbenchQueries;
      } catch (error) {
        workbenchQueries = [];
        catalog.errors.workbenchQueries = error.message;
      }
    })(),
  ]);
  render();
}

async function loadAssetWorkspace() {
  try {
    const [observations, watchlists, notes, alerts, notifications] = await Promise.all([
      api.assetObservations(), api.watchlists(), api.assetNotes(), api.assetAlerts(), api.assetNotifications(),
    ]);
    const items = Array.isArray(observations.items) ? observations.items : [];
    const observation = items[0] || null;
    const rows = {};
    if (observation?.session_id) {
      await Promise.all(Object.entries(observation.blocks || {}).map(async ([name, block]) => {
        const datasetId = block?.dataset?.dataset_id;
        if (!datasetId) return;
        try {
          const result = await api.datasetRows(observation.session_id, datasetId, 0, 200);
          rows[name] = Array.isArray(result.items) ? result.items : [];
        } catch (error) {
          safeLog('asset_dataset_rows_failed', { block: name, code: error.code || 'request_failed' });
          rows[name] = [];
        }
      }));
    }
    assetState = {
      observations: items,
      observation,
      rows,
      watchlists: watchlists.items || [],
      notes: notes.items || [],
      alerts: alerts.items || [],
      notifications: notifications.items || [],
    };
    workbenchContext = observation ? {
      section: 'assets',
      asset: observation.asset,
      asset_type: observation.asset_type,
      source: observation.source,
      requested_at: observation.created_at,
      completed_at: observation.completed_at,
      dataset_ids: observation.dataset_ids || [],
      blocks: Object.fromEntries(Object.entries(observation.blocks || {}).map(([name, block]) => [name, {
        status: block.status,
        as_of: block.dataset?.as_of || null,
        provider: block.dataset?.provider || null,
      }])),
    } : {};
    delete catalog.errors.assetWorkspace;
  } catch (error) {
    assetState = { ...assetState, observation: null, rows: {} };
    catalog.errors.assetWorkspace = error.message;
  }
}

async function showRoute() {
  localIntegrationPollingGuard.invalidate();
  localVerificationTarget = '';
  const legacyTarget = legacyRouteTarget(location.hash);
  if (legacyTarget) {
    history.replaceState(null, '', legacyTarget);
    location.hash = legacyTarget;
  }
  quickCategory = '';
  const ticket = ++pageGeneration; success = ''; selectedPreview = null; sidebarOpen = false; clawSidebarView = 'sessions'; contextOpen = false; contextTab = 'activity'; slashOpen = false; slashIndex = 0; globalSearch = ''; searchOpen = false; renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionMenu = null; sessionActionBusy = false; sessionActionError = ''; questionDrafts.clear();
  await controller.open(parseRoute(location.hash));
  if (ticket !== pageGeneration) return;
  if (state.route.settingsSectionFallback) safeLog('settings_section_fallback');
  if (['fingpt', 'claw'].includes(state.route.page)) researchDraftRoute = { ...state.route };
  document.querySelector('#main')?.scrollTo({ top: 0 });
  await loadWorkflowVersion();
  if (state.route.page === 'history') await loadCatalog([state.route.historyView === 'deleted' ? 'deletedSessions' : 'sessions']);
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
  }
  if (state.route.page === 'skills') {
    const previousKind = capabilityState.kindFilter;
    const nextKind = state.route.capabilityKind || 'skill';
    if (previousKind !== nextKind) {
      capabilityState.source = 'all'; capabilityState.category = ''; capabilityState.status = 'all'; capabilityState.query = '';
      capabilityState.dataMarket = ''; capabilityState.dataStatus = ''; capabilityState.dataAuth = ''; capabilityState.probe = null;
      capabilityState.detail = null; capabilityState.tool = null; capabilityState.dataDetail = null; capabilityState.dataDetailKind = '';
      capabilityState.form = ''; reportWorkflowDetail = null;
    }
    capabilityState.view = state.route.capabilityView || 'library';
    capabilityState.kindFilter = nextKind;
    capabilityState.dataView = nextKind === 'data' && capabilityState.view === 'connections' ? 'sources' : 'capabilities';
    if (['skill', 'workflow'].includes(nextKind)) capabilityState.kind = nextKind;
    await loadCatalog(['capabilities', 'tools', 'reportWorkflows', 'dataCatalog', 'connections', 'sessions']);
  }
  if (state.route.page === 'claw' && !state.route.sessionId) await loadCatalog(['reportWorkflows']);
  if (state.route.page === 'workbench') await loadWorkbench();
  if (state.route.page === 'operations') await loadOperations();
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
  if (state.detail) return true;
  if (state.route.sessionId) return false;
  const result = await controller.create(state.route.page, selectedWorkspace);
  if (!result?.id) return false;
  await showRoute(); await loadCatalog(['sessions']);
  return Boolean(state.detail);
}

root.addEventListener('input', (event) => {
  if (event.target.id === 'prompt') {
    controller.setDraft(event.target.value);
    const wasOpen = slashOpen; slashOpen = event.target.value.trimStart().startsWith('/'); slashIndex = 0;
    if (slashOpen || wasOpen) render();
  }
  if (event.target.closest('#cap-editor-form')) captureEditor();
  if (event.target.closest('#cap-creation-form')) capabilityState.goal = event.target.value;
  if (event.target.closest('#cap-copy-form')) capabilityState.copy = { name: document.querySelector('#cap-copy-name')?.value || '', slug: document.querySelector('#cap-copy-slug')?.value || '' };
  if ('capQuery' in event.target.dataset) { capabilityState.query = event.target.value; render(); }
  if ('globalSearch' in event.target.dataset) { globalSearch = event.target.value; render(); }
  if (event.target.id === 'rename-title') renameDraft = event.target.value;
  if ('connectionSearch' in (event.target.dataset || {})) applyConnectionWorkspaceFilters(event.target.closest('[data-connection-workbench]'));
  const form = event.target.closest('[data-question-form]');
  if (form) {
    const question = state.detail?.questions?.find((item) => item.id === form.dataset.questionForm);
    if (question) { const answers = collectAnswers(form, question); if (answers) questionDrafts.set(question.id, answers); }
  }
  if (event.target.id === 'history-search') {
    historyFilter = event.target.value;
    const view = state.route.historyView || 'active';
    const sessions = view === 'deleted' ? catalog.deletedSessions : catalog.sessions;
    document.querySelector('#history-results').innerHTML = renderHistory(sessions, historyFilter, state.route.historyMode, view);
  }
});

root.addEventListener('keydown', (event) => {
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
  if (event.target.id === 'prompt' && (slashOpen || state.draft.trimStart().startsWith('/')) && !event.isComposing) {
    const result = slashKey(event.key, slashIndex, currentSlashMatches());
    if (result.handled) {
      event.preventDefault();
      if (result.select) void selectCapability(result.select);
      else { if (result.close) slashOpen = false; if (result.index !== undefined) slashIndex = result.index; render(); }
      return;
    }
  }
  if (event.target.id === 'prompt' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); document.querySelector('#composer')?.requestSubmit(); }
  if (event.key === 'Escape') {
    const workbench = event.target.closest?.('[data-connection-workbench]') || document.querySelector('[data-connection-workbench]');
    if (closeConnectionDrawer(workbench)) { event.preventDefault(); return; }
    event.preventDefault();
    const focusSession = sessionMenu?.id || renameSession?.id || deleteSession?.id || purgeSession?.id;
    sidebarOpen = false; contextOpen = false; slashOpen = false; globalSearch = ''; searchOpen = false;
    renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionMenu = null; sessionActionError = '';
    render();
    if (focusSession) document.querySelector(`[data-session-menu="${focusSession}"]`)?.focus({ preventScroll: true });
  }
});

root.addEventListener('change', async (event) => {
  const target = event.target;
  if ('connectionStatus' in (target.dataset || {})) applyConnectionWorkspaceFilters(target.closest('[data-connection-workbench]'));
  if (target.id === 'workspace-select') selectedWorkspace = target.value;
  if ('quickCategory' in target.dataset) { quickCategory = target.value; render(); }
  if (target.id === 'skill-select') { if (target.value) await selectCapability(target.value); else { controller.setCapability(null); render(); } }
  if ('capSource' in target.dataset) { capabilityState.source = target.value; render(); }
  if ('capCategory' in target.dataset) { capabilityState.category = target.value; render(); }
  if ('capStatus' in target.dataset) { capabilityState.status = target.value; render(); }
  if ('dataCategory' in target.dataset) { capabilityState.category = target.value; render(); }
  if ('dataMarket' in target.dataset) { capabilityState.dataMarket = target.value; render(); }
  if ('dataStatus' in target.dataset) { capabilityState.dataStatus = target.value; render(); }
  if ('dataAuth' in target.dataset) { capabilityState.dataAuth = target.value; render(); }
  if (target.closest('#cap-editor-form')) captureEditor();
  if (target.id === 'cap-import-file' && target.files?.length) await capabilityController.import(target.files[0]);
  if ('autoFormats' in target.dataset) { controller.setFormats(target.checked ? null : []); render(); }
  if ('format' in target.dataset) {
    const selected = [...root.querySelectorAll('[data-format]:checked')].map((input) => input.dataset.format);
    controller.setFormats(selected); render();
    root.querySelector('.format-picker')?.setAttribute('open', '');
  }
  if (target.id === 'settings-model' && target.value) {
    try { const selected = JSON.parse(target.value); document.querySelector('#provider').value = selected.provider; document.querySelector('#model-id').value = selected.model; }
    catch { safeLog('invalid_model_selection'); }
  }
  if (target.id === 'model-select' && target.value) {
    const result = await controller.action(() => api.configure(JSON.parse(target.value)), { refreshAfter: false });
    if (result?.configured) { success = '运行模型已更新。'; await loadCatalog(['runtime']); }
  }
  if (target.id === 'file-input' && target.files?.length) await uploadFiles([...target.files]);
});

async function uploadFiles(files) {
  if (!files.length || state.busy || state.loading || !(await ensureSession())) return;
  const id = state.detail?.id;
  if (!id) return;
  const result = await controller.action(() => api.upload(id, files));
  if (result?.items && state.detail?.id === id) controller.addAttachments(result.items);
}

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
  event.preventDefault();
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
    reportWorkflowBusy = true; state.error = ''; success = ''; render();
    try {
      await api.saveReportSchedule(workflowId, body);
      reportWorkflowDetail = await api.reportWorkflow(workflowId);
      success = enabled ? '报告 Workflow 日程已启用。' : '报告 Workflow 日程已保存但未启用。';
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return;
  }
  if (event.target.matches('[data-asset-observation]')) {
    if (workbenchBusy) return;
    workbenchBusy = true; state.error = ''; render();
    try {
      const payload = readAssetObservation(event.target);
      let record = await api.createAssetObservation(payload, crypto.randomUUID());
      assetState = { ...assetState, observation: record, observations: [record, ...assetState.observations.filter(item => item.id !== record.id)] };
      render();
      for (let attempt = 0; attempt < 120 && record.status === 'running'; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        record = await api.assetObservation(record.id);
        assetState = { ...assetState, observation: record, observations: [record, ...assetState.observations.filter(item => item.id !== record.id)] };
        render();
      }
      await loadAssetWorkspace();
      success = record.status === 'completed'
        ? '资产各区块已按真实数据源更新，可冻结快照并交给研究。'
        : '资产区块查询已结束；请查看各区块的失败或缺失状态。';
    } catch (error) { state.error = error.message; }
    finally { workbenchBusy = false; render(); }
    return;
  }
  if (event.target.matches('[data-watchlist-item]')) {
    const values = new FormData(event.target);
    try {
      await api.addWatchlistItem(String(values.get('watchlist_id')), {
        asset: String(values.get('asset')),
        asset_type: assetState.observation?.asset_type || 'stock',
        name: String(assetState.rows?.overview?.[0]?.name || values.get('asset')),
      });
      success = '已加入本地自选列表。'; await loadAssetWorkspace(); render();
    } catch (error) { state.error = error.message; render(); }
    return;
  }
  if (event.target.matches('[data-asset-note]')) {
    const values = new FormData(event.target);
    try {
      await api.createAssetNote({ asset: String(values.get('asset')), text: String(values.get('text')).trim() });
      success = '观察笔记已保存。'; await loadAssetWorkspace(); render();
    } catch (error) { state.error = error.message; render(); }
    return;
  }
  if (event.target.matches('[data-asset-alert]')) {
    const values = new FormData(event.target);
    try {
      await api.createAssetAlert({
        asset: String(values.get('asset')),
        field: String(values.get('field')),
        operator: String(values.get('operator')),
        threshold: Number(values.get('threshold')),
        cooldown_minutes: 60,
      });
      success = '提醒规则已保存，将在新快照到达时评估。'; await loadAssetWorkspace(); render();
    } catch (error) { state.error = error.message; render(); }
    return;
  }
  if (event.target.matches('[data-workbench-query]')) {
    if (workbenchBusy) return;
    workbenchBusy = true; state.error = ''; render();
    try {
      const query = readWorkbenchQuery(event.target);
      const section = state.route.section || 'market';
      const previous = [...workbenchQueries].reverse().find(item => item.section === section);
      workbenchContext = { section, source: query.source, parameters: query.parameters, requested_at: new Date().toISOString() };
      let record = await api.startDataQuery({ session_id: previous?.session_id || null, section, query }, crypto.randomUUID());
      workbenchQueries = [...workbenchQueries.filter(item => item.id !== record.id), record]; render();
      for (let attempt = 0; attempt < 80 && record.status === 'running'; attempt++) {
        await new Promise(resolve => setTimeout(resolve, 500));
        record = await api.dataQuery(record.id);
        workbenchQueries = [...workbenchQueries.filter(item => item.id !== record.id), record]; render();
      }
      if (record.status === 'completed') success = '真实数据快照已生成，可交给 FinGPT 或 Claw。';
      else if (record.status === 'failed') state.error = `查询失败：${record.failure_code || '未知错误'}`;
    } catch (error) { state.error = error.message; }
    finally { workbenchBusy = false; render(); }
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
    const answers = collectAnswers(event.target, question);
    if (!answers) return;
    questionDrafts.set(question.id, answers);
    if (answers.some((answer) => !answer.custom.trim() && !answer.selected.length)) { state.error = '请完整回答这组问题。'; render(); return; }
    const result = await controller.action(() => api.answer(id, question.id, answers));
    if (result) { questionDrafts.delete(question.id); render(); }
  }
  if (event.target.id === 'composer') {
    if (state.draft.trimStart().startsWith('/')) { slashOpen = true; slashIndex = 0; render(); return; }
    if (!state.draft.trim() || state.busy || slashOpen) return;
    if (state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status))) { state.error = '上一任务与交付尚未确认结束；草稿已保留，未发送。'; render(); return; }
    if (!catalog.runtime?.connected || catalog.runtime.credential_configured === false) { state.error = '运行时未就绪，请检查连接与授权；草稿已保留。'; render(); return; }
    if (await ensureSession()) { await controller.send(); await loadCatalog(['sessions']); }
  }
  if (event.target.id === 'settings-form') {
    const values = new FormData(event.target); const key = String(values.get('api_key') || '').trim();
    const payload = { provider: String(values.get('provider')).trim(), model: String(values.get('model')).trim(), ...(key ? { api_key: key } : {}) };
    // Capture once, clear immediately; never copy secrets into application state or logs.
    document.querySelector('#api-key').value = '';
    const result = await controller.action(() => api.configure(payload), { refreshAfter: false });
    delete payload.api_key;
    if (result?.configured) { success = '配置已保存。API Key 不会回填。'; await loadCatalog(['runtime', 'models']); }
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

root.addEventListener('click', async (event) => {
  const clickTarget = event.target;
  if (clickTarget?.matches?.('[data-capability-dialog-backdrop]')) {
    closeCapabilityPreview(); return;
  }
  if (clickTarget?.matches?.('[data-dialog-backdrop]')) {
    renameDraft = null; renameSession = null; deleteSession = null; purgeSession = null; sessionActionError = ''; render();
    return;
  }
  if (sessionMenu && !clickTarget?.closest?.('.session-action-menu') && !clickTarget?.closest?.('[data-session-menu]')) {
    sessionMenu = null; render();
  }
  const button = clickTarget?.closest?.('button'); if (!button || button.disabled || button.getAttribute?.('aria-disabled') === 'true') return;
  const data = button.dataset;
  if ('localCategoryTarget' in data) {
    const target = document.getElementById(data.localCategoryTarget);
    const main = document.querySelector('#main');
    const scroller = main?.scrollHeight > main?.clientHeight ? main : document.scrollingElement;
    if (target && scroller) {
      target.focus({ preventScroll: true });
      const scrollerTop = scroller === document.scrollingElement ? 0 : scroller.getBoundingClientRect().top;
      const currentTop = scroller === document.scrollingElement ? window.scrollY : scroller.scrollTop;
      const top = currentTop + target.getBoundingClientRect().top - scrollerTop - 60;
      const behavior = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
      scroller.scrollTo({ top: Math.max(0, top), behavior });
    }
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
  if ('localIntegrationsProbe' in data) {
    state.error = ''; success = ''; localIntegrationProbeBusy = true; render();
    try {
      const accepted = await api.probeLocalIntegrations(`local-integrations-${crypto.randomUUID()}`);
      if (typeof accepted?.id !== 'string' || !accepted.id) throw new Error('服务未返回有效的探测任务，请刷新后重试。');
      const current = await waitForLocalIntegrationProbe((probeId) => api.localIntegrationProbe(probeId), accepted.id);
      if (current.status !== 'completed' || !current.snapshot) throw new Error(current?.error?.message || '本机能力检测未完成。');
      catalog.localIntegrations = current.snapshot;
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
    const rect = button.getBoundingClientRect(); const width = 156;
    const mobile = window.matchMedia('(max-width: 1050px)').matches;
    const drawerRight = Math.min(window.innerWidth, 68 + 248);
    const minLeft = mobile ? 76 : 8;
    const maxLeft = (mobile ? drawerRight : window.innerWidth) - width - 8;
    const preferredLeft = rect.right + 8;
    const left = Math.max(minLeft, Math.min(maxLeft, preferredLeft));
    const top = Math.max(8, Math.min(window.innerHeight - 112, rect.top));
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
  if ('toggleSearch' in data) { searchOpen = !searchOpen; sidebarOpen = false; contextOpen = false; if (!searchOpen) globalSearch = ''; render(); if (searchOpen) document.querySelector('#global-search')?.focus(); }
  if ('clearCapability' in data) { controller.setCapability(null); render(); }
  if ('removeTool' in data) { controller.setTools(state.toolIds.filter(id => id !== data.removeTool)); render(); }
  if ('new' in data) { history.pushState(null, '', state.route.page === 'claw' ? '#/claw' : '#/fingpt'); await showRoute(); controller.setDraft(''); render(); document.querySelector('#prompt')?.focus(); }
  if ('refresh' in data) {
    success = '';
    if (state.route.page === 'workbench') await loadWorkbench();
    else if (state.route.page === 'operations') await loadOperations();
    else if (state.route.page === 'history' && state.route.historyView === 'deleted') await loadCatalog(['deletedSessions']);
    else if (state.route.page === 'settings') {
      const section = currentSettingsSection();
      if (section === 'local') {
        localIntegrationPollingGuard.invalidate();
        localVerificationTarget = '';
      }
      if (section === 'data') selectedConnectionConfiguration = null;
      const catalogs = settingsRefreshCatalogs(section);
      if (catalogs.length) await loadCatalog(catalogs);
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
    workbenchBusy = true; state.error = ''; render();
    try {
      const result = await api.handoff({
        source_session_id: data.sourceSession,
        target_mode: data.workbenchHandoff,
        section: state.route.section || 'market',
        dataset_ids: JSON.parse(data.datasetIds || '[]'),
        context: workbenchContext,
      }, crypto.randomUUID());
      history.pushState(null, '', `#/${result.mode}?session=${encodeURIComponent(result.session_id)}`);
      await showRoute();
      controller.setDraft(result.draft || '请基于研究台交接资料继续研究。');
      await loadCatalog(['sessions']);
      success = '页面参数和数据集已冻结到新会话，确认草稿后再发送。';
    } catch (error) { state.error = error.message; }
    finally { workbenchBusy = false; render(); }
  }
  if ('reloadSession' in data) await showRoute();
  if ('toggleSidebar' in data) {
    const narrow = window.matchMedia('(max-width: 1050px)').matches;
    if (narrow) sidebarOpen = !sidebarOpen;
    else sidebarCollapsed = !sidebarCollapsed;
    contextOpen = false; render();
  }
  if ('toggleContext' in data) { if (window.matchMedia('(max-width: 1050px)').matches) contextOpen = !contextOpen; else contextCollapsed = !contextCollapsed; sidebarOpen = false; render(); }
  if ('collapseSidebar' in data) {
    if (window.matchMedia('(max-width: 1050px)').matches) sidebarOpen = false;
    else sidebarCollapsed = true;
    render();
  }
  if ('clawSidebarView' in data) { clawSidebarView = data.clawSidebarView; render(); }
  if ('showAttention' in data) { contextOpen = window.matchMedia('(max-width: 1050px)').matches; contextCollapsed = false; contextTab = 'activity'; render(); }
  if ('contextTab' in data) { contextTab = data.contextTab; render(); }
  if ('closeDrawers' in data) { sidebarOpen = false; contextOpen = false; render(); }
  if ('upload' in data) document.querySelector('#file-input')?.click();
  if ('slashSearch' in data) { slashOpen = !slashOpen; slashIndex = 0; render(); document.querySelector('#prompt')?.focus(); }
  if ('removeAttachment' in data) controller.removeAttachment(data.removeAttachment);
  if ('noFormats' in data) { controller.setFormats([]); render(); }
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
  const id = state.detail?.id;
  if (!id) return;
  if ('cancel' in data) { await controller.action(() => api.cancel(id)); await loadCatalog(['sessions']); }
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
  if (state.draft.trimStart().startsWith('/')) controller.setDraft('');
  slashOpen = false; globalSearch = ''; searchOpen = false; render();
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
  if ('capRefresh' in data) { await loadCatalog(['capabilities', 'tools', 'reportWorkflows', 'dataCatalog', 'connections']); return true; }
  if ('capKind' in data) { cap.kind = data.capKind; cap.kindFilter = data.capKind; cap.category = ''; cap.query = ''; cap.dataDetail = null; cap.dataDetailKind = ''; reportWorkflowDetail = null; render(); return true; }
  if ('closeReportWorkflow' in data) { reportWorkflowDetail = null; render(); return true; }
  if ('reportWorkflowDetail' in data) {
    const ticket = pageGeneration;
    cap.detail = null; cap.tool = null; cap.dataDetail = null; cap.form = '';
    reportWorkflowBusy = true; state.error = ''; render();
    try {
      const detail = await api.reportWorkflow(data.reportWorkflowDetail);
      if (ticket !== pageGeneration) return true;
      reportWorkflowDetail = detail;
      if (state.route.page !== 'skills') {
        history.pushState(null, '', '#/skills?kind=workflow');
        await showRoute();
        reportWorkflowDetail = detail;
      }
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return true;
  }
  if ('runReportWorkflow' in data) {
    reportWorkflowBusy = true; state.error = ''; success = ''; render();
    try {
      let run = await api.runReportWorkflow(data.runReportWorkflow);
      for (let attempt = 0; attempt < 12 && !run.session_id && ['queued', 'preparing_data', 'running'].includes(run.status); attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 500));
        run = await api.reportRun(run.id);
      }
      await loadCatalog(['reportWorkflows', 'sessions']);
      if (run.session_id) {
        history.pushState(null, '', `#/claw?session=${encodeURIComponent(run.session_id)}`);
        await showRoute();
        success = '已创建锁定报告 Workflow 版本的 Claw 会话。';
      } else if (['blocked_data', 'blocked_approval', 'delivery_incomplete', 'failed', 'cancelled', 'skipped_overlap'].includes(run.status)) {
        state.error = `报告 Workflow 未进入 Claw：${run.failure_code || run.status}。`;
      } else {
        success = '报告 Workflow 已受理，正在准备 Excel 底稿。';
      }
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return true;
  }
  if ('probeReportProvider' in data) {
    reportWorkflowBusy = true; state.error = ''; success = ''; render();
    try {
      const result = await api.probeReportProvider(data.probeReportProvider, crypto.randomUUID());
      success = result.ready
        ? `${data.probeReportProvider} 探测通过。`
        : `${data.probeReportProvider} 探测未通过：${result.code || '状态未知'}。`;
      if (reportWorkflowDetail) reportWorkflowDetail = await api.reportWorkflow(reportWorkflowDetail.id);
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return true;
  }
  if ('cancelReportRun' in data) {
    reportWorkflowBusy = true; state.error = ''; render();
    try {
      await api.cancelReportRun(data.cancelReportRun);
      if (reportWorkflowDetail) reportWorkflowDetail = await api.reportWorkflow(reportWorkflowDetail.id);
      success = '报告运行已取消。';
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return true;
  }
  if ('retryReportRun' in data) {
    reportWorkflowBusy = true; state.error = ''; render();
    try {
      const run = await api.retryReportRun(data.retryReportRun);
      if (reportWorkflowDetail) reportWorkflowDetail = await api.reportWorkflow(reportWorkflowDetail.id);
      success = `已创建重试运行 ${run.id}。`;
    } catch (error) { state.error = error.message; }
    finally { reportWorkflowBusy = false; render(); }
    return true;
  }
  if ('dataView' in data) { cap.dataView = data.dataView; cap.category = ''; cap.query = ''; cap.dataMarket = ''; cap.dataStatus = ''; cap.dataAuth = ''; render(); return true; }
  if ('dataCapabilityDetail' in data) {
    capabilityDialogReturnSelector = `[data-cap-preview-trigger="data:${data.dataCapabilityDetail}"]`;
    const result = await capabilityController.run(() => api.dataCapability(data.dataCapabilityDetail));
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
window.addEventListener('hashchange', () => { void showRoute(); });
window.addEventListener('resize', () => { if (sessionMenu) { sessionMenu = null; render(); } });
window.addEventListener('scroll', () => { if (sessionMenu) { sessionMenu = null; render(); } }, true);
document.querySelector('.skip-link').addEventListener('click', (event) => { event.preventDefault(); document.querySelector('#main')?.focus(); });
window.addEventListener('unhandledrejection', (event) => { event.preventDefault(); safeLog('unhandled_async_error'); state.error = '操作出现异常，请刷新状态后重试。'; render(); });
await showRoute();
await loadCatalog();
