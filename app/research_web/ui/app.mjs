import { createAPI, createController, parseRoute, legacyRouteTarget, isRunning, safeLog, collectQuestionAnswers, reconcileSessionSummary } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { badge, empty, renderConversation, renderHistory, modelOptions, renderRename } from './views.mjs';
import { icon } from './icons.mjs';
import { renderComposer, renderQuickSkills, slashKey, skillMatches } from './composer.mjs';
import { renderAppearancePicker, renderResearchAttention, renderClawWorkspaceCanvas, renderContextPanel, renderPrimaryRail, renderSidebar, renderTopbar } from './shell.mjs';

import { createCapabilityController, refreshProbedSourceDetail } from './capability-controller.mjs';
import { capabilityTabKey, reportWorkflowEligibility, renderCapabilityCatalog, renderCapabilityDetail, renderToolDetail, renderCreationArtifacts, creationArtifacts } from './capabilities.mjs';
import { renderDataCapabilityDetail, renderDataSourceDetail } from './data-catalog.mjs';
import { renderCapabilityEditor, renderCreationForm, renderCopyForm, readEditor, moveStepWithFeedback, newWorkflowStep } from './capability-editor.mjs';
import { readWorkbenchQuery, renderWorkbench } from './workbench.mjs';
import { readAssetObservation } from './asset-workspace.mjs';
import { renderOperations } from './operations.mjs';

const api = createAPI();
const root = document.querySelector('#app');
const catalog = { runtime: null, models: [], sessions: [], workspaces: [], capabilities: [], tools: [], artifacts: [], dataCatalog: { summary: {}, capabilities: [], sources: [], bindings: [] }, errors: {}, modelFailures: [] };
let selectedWorkspace = ''; let selectedPreview = null; let historyFilter = ''; let success = ''; let sidebarOpen = false; let sidebarCollapsed = false; let clawSidebarView = 'sessions'; let contextOpen = false; let contextTab = 'activity'; let globalSearch = ''; let slashOpen = false;
let searchOpen = false; let slashIndex = 0; let contextCollapsed = true;
let quickCategory = '';
let researchDraftRoute = { page: 'fingpt', sessionId: null };
let workbenchQueries = []; let workbenchContext = {}; let workbenchBusy = false;
let assetState = { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [] };
let operationsRange = '7d';
let operationsData = { usage: null, tools: null, datahub: null, services: null, storage: null };
const workflowVersions = new Map();
let pageGeneration = 0;
let renameDraft = null;
const questionDrafts = new Map();
const controller = createController({ api, onNavigate: (hash) => { history.pushState(null, '', hash); } });
const state = controller.state;
const capabilityController = createCapabilityController({ api, onChange: () => render(), onCatalogChange: () => loadCatalog(['capabilities']) });
const capabilityState = capabilityController.state;

function runtimeLabel() {
  if (!catalog.runtime) return 'DSH 未连接';
  if (catalog.runtime.connected && catalog.runtime.credential_configured === false) return 'DSH 待授权';
  return catalog.runtime.connected ? 'DSH 已连接' : 'DSH 不可用';
}

function notice(message, kind = 'error') { return message ? `<div class="notice ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${e(message)}</div>` : ''; }

function composer() {
  const disabled = state.busy || state.loading || Boolean(state.route.sessionId && !state.detail);
  const taskPending = state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status));
  return renderComposer({ models: catalog.models, model: catalog.runtime?.model, page: state.route.page, draft: state.draft, attachments: state.attachments, expectedFormats: state.expectedFormats, skills: catalog.capabilities, skillId: state.skillId, disabled, busy: state.busy, taskPending, detail: state.detail, slashOpen, slashIndex, capability: state.capability, toolIds: state.toolIds, tools: catalog.tools, runtimeReady: catalog.runtime?.connected === true && catalog.runtime?.credential_configured !== false });
}

function landing() {
  const claw = state.route.page === 'claw';
  return `<div class="landing ${claw ? 'claw-landing' : 'fingpt-landing'}"><div class="greeting">${claw ? `<span class="mode-label">${icon('layers')}Claw</span>` : ''}<h1>${claw ? '把研究目标，变成可用成果。' : '从一个问题，开始研究。'}</h1><p class="landing-subtitle">${claw ? '说明目标、资料与交付要求，在一个空间推进研究。' : '读懂资料，比较公司，探索行业。'}</p></div>${composer()}${renderQuickSkills(catalog.capabilities, { page: state.route.page, category: quickCategory })}</div>`;
}

function researchPage() {
  if (state.loading) return `<div class="loading-state" role="status">正在读取会话…</div>`;
  if (state.route.sessionId && !state.detail) return `${empty('暂时无法读取这个会话', '检查连接后重试，输入内容仍会保留。')}<button class="button" data-reload-session>重新读取</button>`;
  if (!state.detail) return landing();
  const detail = state.detail;
  const workspaceView = detail.mode === 'claw' && clawSidebarView === 'workspace';
  const canvas = workspaceView ? renderClawWorkspaceCanvas({ detail, selectedPreview, busy: state.busy }) : `<div id="messages" class="messages" aria-label="会话消息">${renderConversation(detail, questionDrafts)}</div>`;
  return `<header class="page-header"><div class="session-title"><div class="eyebrow">${detail.mode === 'claw' ? 'CLAW · AGENT RESEARCH' : 'FINGPT · RESEARCH SESSION'}</div><h1>${e(detail.title || '未命名会话')}</h1><div class="session-meta">${badge(detail.status)}${detail.model ? `<span>${e(detail.model)}</span>` : ''}</div></div><div class="button-row"><button class="button small" data-rename ${state.busy ? 'disabled' : ''}>重命名</button>${detail.mode !== 'claw' ? `<button class="button small" data-upgrade ${state.busy || isRunning(detail.status) ? 'disabled' : ''}>升级为 Claw ↗</button>` : ''}<button class="button small context-toggle" data-toggle-context aria-expanded="${window.matchMedia('(max-width: 1050px)').matches ? contextOpen : !contextCollapsed}">活动与文件</button></div></header>${renameDraft !== null ? renderRename(renameDraft) : ''}${notice(state.streamError, 'warning')}${renderCreationArtifacts(detail, state.busy || isRunning(detail.status))}${detail.capability ? `<p class="small muted">所选能力版本：${e(detail.capability.id)} · v${e(detail.capability.version)}（选择记录，不代表每个工具已执行）</p>` : ''}${renderResearchAttention(detail)}${canvas}<div class="composer-dock">${composer()}</div>`;
}

function settingsPage() {
  const runtime = catalog.runtime;
  return `<section class="settings-card"><h2>架构与实现文档</h2><p class="muted">只读查看当前架构图；检查回执不替代实现与人工验收。</p><a class="button" href="/api/research/documentation/index.html" target="_blank" rel="noopener noreferrer">打开架构文档 ↗</a></section><header class="page-header"><div><div class="eyebrow">WORKSPACE SETTINGS</div><h1>设置</h1><p class="muted">Research Web 只连接 DSH，不启动其他研究管线。</p></div><button class="button" data-refresh>刷新状态</button></header><section class="settings-card appearance-settings"><h2>外观</h2><p class="muted">选择浅色、深色，或跟随系统。仅保存在此浏览器，不影响研究任务。</p>${renderAppearancePicker()}</section><section class="settings-card"><div class="section-heading"><h2>DSH 连接</h2><span class="badge ${runtime?.connected ? 'live' : 'danger'}">${runtimeLabel()}</span></div><dl class="runtime-details"><div><dt>Provider</dt><dd>${e(runtime?.provider || '未提供')}</dd></div><div><dt>模型</dt><dd>${e(runtime?.model || '未配置')}</dd></div><div><dt>版本</dt><dd>${e(runtime?.version || '未提供')}</dd></div><div><dt>管理方式</dt><dd>${runtime ? runtime.owned_runtime ? '由 Research Workbench 管理' : '外部运行时' : '未知'}</dd></div></dl>${runtime?.message ? `<p class="muted">${e(runtime.message)}</p>` : ''}</section><section class="settings-card"><h2>模型配置</h2><p class="muted">选择模型并按需更新 API Key。秘密值不回填，也不会存入浏览器存储。</p><form id="settings-form" autocomplete="off"><label for="settings-model">可用模型</label><select id="settings-model">${modelOptions(catalog.models, runtime?.model)}</select><div class="form-grid"><label>Provider<input id="provider" name="provider" required autocomplete="off" value="${e(runtime?.provider || '')}" placeholder="例如 openai"></label><label>模型 ID<input id="model-id" name="model" required autocomplete="off" value="${e(runtime?.model || '')}" placeholder="输入运行时支持的模型 ID"></label></div><label for="api-key">API Key <span class="muted">（可选，仅更新时填写）</span></label><input id="api-key" name="api_key" type="password" autocomplete="new-password" spellcheck="false" placeholder="留空则不更改现有凭据"><p class="muted small">只发送给当前同源后端；保存成功后清空输入。模型变更作用于 DSH 运行时。</p><button class="button primary" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在保存…' : '保存配置'}</button></form></section>${catalog.modelFailures.length ? notice('部分模型目录未能加载；可填写已知的 Provider 与模型 ID。', 'warning') : ''}`;
}

function mainPage() {
  if (['fingpt', 'claw'].includes(state.route.page)) return researchPage();
  if (state.route.page === 'settings') return settingsPage();
  if (state.route.page === 'workbench') return workbenchPage();
  if (state.route.page === 'operations') return operationsPage();
  if (state.route.page === 'history') return `<header class="page-header"><div><div class="eyebrow">YOUR RESEARCH</div><h1>研究历史</h1><p class="muted">所有 FinGPT 与 Claw 会话，随时回来继续。</p></div><button class="button" data-refresh>刷新</button></header><label class="search-box"><span aria-hidden="true">⌕</span><input id="history-search" type="search" placeholder="搜索会话标题…" value="${e(historyFilter)}" aria-label="搜索研究历史"></label><div id="history-results">${renderHistory(catalog.sessions, historyFilter)}</div>`;
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
  if (cap.dataDetail) return messages + (cap.dataDetailKind === 'source' ? renderDataSourceDetail(cap.dataDetail, cap.busy) : renderDataCapabilityDetail(cap.dataDetail));
  if (cap.tool) return messages + renderToolDetail(cap.tool);
  if (cap.detail) return messages + renderCapabilityDetail(cap.detail, { busy: cap.busy, versions: cap.versions, versionDetail: cap.versionDetail, running: catalog.sessions.some(session => isRunning(session.status)) });
  return messages + renderCapabilityCatalog({ ...cap, items: catalog.capabilities, tools: catalog.tools, dataCatalog: catalog.dataCatalog, error: catalog.errors.capabilities || catalog.errors.tools || catalog.errors.dataCatalog || '' });
}

function sidebar() {
  return renderSidebar({ page: state.route.page, sessionId: state.route.sessionId, sessions: catalog.sessions, workspaces: catalog.workspaces, selectedWorkspace, collapsed: sidebarCollapsed, mobileOpen: sidebarOpen, detail: state.detail, clawSidebarView });
}

function primaryRail() {
  const narrow = window.matchMedia('(max-width: 1050px)').matches;
  return renderPrimaryRail({
    page: state.route.page,
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
  const hasContext = research && Boolean(state.detail) && !contextCollapsed;
  root.innerHTML = `<div class="app-shell ${hasContext ? '' : 'wide-page'} ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${sidebarOpen ? 'navigation-open' : ''} ${hasContext ? 'context-open' : ''}">${renderTopbar({ page: state.route.page, detail: state.detail, runtimeLabel: runtimeLabel(), runtime: catalog.runtime, models: catalog.models, busy: state.busy, search: globalSearch, sessions: catalog.sessions, skills: [...catalog.capabilities, ...catalog.tools, ...(catalog.dataCatalog.capabilities || [])], searchOpen })}<div class="navigation-column">${primaryRail()}${sidebar()}</div><main id="main" tabindex="-1"><div class="page-content">${notice(state.error)}${Object.entries(catalog.errors).map(([name, error]) => notice(`${({ runtime: '运行时', models: '模型目录', workspaces: '工作空间', sessions: '会话历史', capabilities: '能力目录', tools: '工具目录', dataCatalog: '数据目录' })[name] || name}：${error}`)).join('')}${notice(success, 'success')}${mainPage()}</div></main>${hasContext || contextOpen ? contextPanel() : ''}</div>${sidebarOpen || contextOpen ? '<button class="mobile-backdrop" data-close-drawers aria-label="关闭面板"></button>' : ''}`;
  window.ResearchWebTheme?.syncControls();
  document.querySelector('#main').scrollTop = mainScroll;
  if (focusId) {
    const replacement = document.getElementById(focusId);
    if (replacement && !replacement.disabled) { replacement.focus({ preventScroll: true }); if (selection && selection.start !== null) replacement.setSelectionRange?.(selection.start, selection.end); }
  }
  if (state.busy) root.querySelectorAll('[data-approval], [data-upload], .question-form button, #rename-form button').forEach((button) => { button.disabled = true; });
  document.title = `${state.detail?.title || ({ fingpt: 'FinGPT', claw: 'Claw', workbench: '研究台', history: '研究历史', skills: '能力中心', operations: '运行与用量', settings: '设置' })[state.route.page]} · Research Workbench`;
}

async function loadCatalog(names = ['runtime', 'models', 'workspaces', 'sessions', 'capabilities', 'tools']) {
  await Promise.all(names.map(async (name) => {
    try {
      const data = await api[name]();
      if (name === 'runtime') catalog.runtime = data;
      else if (name === 'models') { catalog.models = data.groups || []; catalog.modelFailures = data.failures || []; }
      else if (name === 'dataCatalog') catalog.dataCatalog = {
        summary: data?.summary || {},
        capabilities: Array.isArray(data?.capabilities) ? data.capabilities : [],
        sources: Array.isArray(data?.sources) ? data.sources : [],
        bindings: Array.isArray(data?.bindings) ? data.bindings : [],
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
  const legacyTarget = legacyRouteTarget(location.hash);
  if (legacyTarget) {
    history.replaceState(null, '', legacyTarget);
    location.hash = legacyTarget;
  }
  quickCategory = '';
  const ticket = ++pageGeneration; success = ''; selectedPreview = null; sidebarOpen = false; clawSidebarView = 'sessions'; contextOpen = false; contextTab = 'activity'; slashOpen = false; slashIndex = 0; globalSearch = ''; searchOpen = false; renameDraft = null; questionDrafts.clear();
  await controller.open(parseRoute(location.hash));
  if (ticket !== pageGeneration) return;
  if (['fingpt', 'claw'].includes(state.route.page)) researchDraftRoute = { ...state.route };
  document.querySelector('#main')?.scrollTo({ top: 0 });
  await loadWorkflowVersion();
  if (state.route.page === 'history') await loadCatalog(['sessions']);
  if (state.route.page === 'skills') {
    if (state.route.capabilityKind) capabilityState.kind = state.route.capabilityKind;
    await loadCatalog(['capabilities', 'tools', 'dataCatalog', 'sessions']);
  }
  if (state.route.page === 'workbench') await loadWorkbench();
  if (state.route.page === 'operations') await loadOperations();
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
  const form = event.target.closest('[data-question-form]');
  if (form) {
    const question = state.detail?.questions?.find((item) => item.id === form.dataset.questionForm);
    if (question) { const answers = collectAnswers(form, question); if (answers) questionDrafts.set(question.id, answers); }
  }
  if (event.target.id === 'history-search') { historyFilter = event.target.value; document.querySelector('#history-results').innerHTML = renderHistory(catalog.sessions, historyFilter); }
});

root.addEventListener('keydown', (event) => {
  if ('capKind' in (event.target.dataset || {})) {
    const result = capabilityTabKey(event.key, event.target.dataset.capKind);
    if (result.handled) {
      event.preventDefault();
      const cap = capabilityState;
      cap.kind = result.kind; cap.category = ''; cap.query = ''; cap.dataDetail = null; cap.dataDetailKind = '';
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
  if (event.key === 'Escape') { event.preventDefault(); sidebarOpen = false; contextOpen = false; slashOpen = false; globalSearch = ''; searchOpen = false; renameDraft = null; render(); }
});

root.addEventListener('change', async (event) => {
  const target = event.target;
  if (target.id === 'workspace-select') selectedWorkspace = target.value;
  if ('quickCategory' in target.dataset) { quickCategory = target.value; render(); }
  if (target.id === 'skill-select') { if (target.value) await selectCapability(target.value); else { controller.setCapability(null); render(); } }
  if ('capSource' in target.dataset) { capabilityState.source = target.value; render(); }
  if ('capCategory' in target.dataset) { capabilityState.category = target.value; render(); }
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
    const id = state.detail?.id; const title = String(new FormData(event.target).get('title') || '').trim();
    if (!id || !title) { state.error = '会话名称不能为空。'; render(); return; }
    const result = await controller.action(() => api.rename(id, title));
    if (result && state.detail?.id === id) { renameDraft = null; await loadCatalog(['sessions']); }
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
});

root.addEventListener('click', async (event) => {
  const button = event.target.closest('button'); if (!button || button.disabled || button.getAttribute?.('aria-disabled') === 'true') return;
  const data = button.dataset;
  if (await handleCapabilityClick(data)) return;
  if ('toggleSearch' in data) { searchOpen = !searchOpen; sidebarOpen = false; contextOpen = false; if (!searchOpen) globalSearch = ''; render(); if (searchOpen) document.querySelector('#global-search')?.focus(); }
  if ('clearCapability' in data) { controller.setCapability(null); render(); }
  if ('removeTool' in data) { controller.setTools(state.toolIds.filter(id => id !== data.removeTool)); render(); }
  if ('new' in data) { history.pushState(null, '', state.route.page === 'claw' ? '#/claw' : '#/fingpt'); await showRoute(); controller.setDraft(''); render(); document.querySelector('#prompt')?.focus(); }
  if ('refresh' in data) {
    success = '';
    if (state.route.page === 'workbench') await loadWorkbench();
    else if (state.route.page === 'operations') await loadOperations();
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
  if ('cancelRename' in data) { renameDraft = null; render(); }
  if ('noFormats' in data) { controller.setFormats([]); render(); }
  if ('preview' in data) { selectedPreview = data.preview; render(); }
  if ('closePreview' in data) { selectedPreview = null; render(); }
  if ('closeSkillDetail' in data) { capabilityController.close(); render(); }
  if ('skillDetail' in data) {
    const ticket = pageGeneration;
    await capabilityController.open(data.skillDetail);
    if (ticket !== pageGeneration) return;
    if (state.route.page !== 'skills') { history.pushState(null, '', '#/skills'); await showRoute(); }
    document.querySelector('#main')?.scrollTo({ top: 0 });
  }
  if ('skillShortcut' in data) await selectCapability(data.skillShortcut);
  if ('useSkill' in data) await selectCapability(data.useSkill);
  const id = state.detail?.id;
  if (!id) return;
  if ('cancel' in data) { await controller.action(() => api.cancel(id)); await loadCatalog(['sessions']); }
  if ('approval' in data) await controller.action(() => api.approve(id, data.approval, data.decision));
  if ('rename' in data) {
    renameDraft = state.detail.title || ''; render(); document.querySelector('#rename-title')?.focus();
  }
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
  if ('capRefresh' in data) { await loadCatalog(cap.kind === 'data' ? ['dataCatalog', 'tools'] : ['capabilities', 'tools']); return true; }
  if ('capKind' in data) { cap.kind = data.capKind; cap.category = ''; cap.query = ''; cap.dataDetail = null; cap.dataDetailKind = ''; render(); return true; }
  if ('dataView' in data) { cap.dataView = data.dataView; cap.category = ''; cap.query = ''; cap.dataMarket = ''; cap.dataStatus = ''; cap.dataAuth = ''; render(); return true; }
  if ('dataCapabilityDetail' in data) {
    const result = await capabilityController.run(() => api.dataCapability(data.dataCapabilityDetail));
    if (result) { cap.dataDetail = result; cap.dataDetailKind = 'capability'; render(); }
    return true;
  }
  if ('dataSourceDetail' in data) {
    const result = await capabilityController.run(() => api.dataSource(data.dataSourceDetail));
    if (result) { cap.dataDetail = result; cap.dataDetailKind = 'source'; render(); }
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
    await goToResearchDraft(); controller.setTools([...state.toolIds, tool.id]); render(); document.querySelector('#prompt')?.focus(); return true;
  }
  if ('capClose' in data) { capabilityController.close(); return true; }
  if ('capCancelEdit' in data) { cap.form = ''; cap.editor = null; render(); return true; }
  if ('capCreate' in data) { capabilityController.create(data.capCreate); return true; }
  if ('capImport' in data) { document.querySelector('#cap-import-file')?.click(); return true; }
  if ('capEdit' in data) { capabilityController.edit(); return true; }
  if ('capCopy' in data) { cap.form = 'copy'; cap.copy = {}; render(); return true; }
  if ('capVersions' in data) { await capabilityController.versions(); return true; }
  if ('capVersion' in data) { await capabilityController.version(Number(data.capVersion)); return true; }
  if ('capAction' in data) { await capabilityController.action(data.capAction); return true; }
  if ('capRollback' in data) { await capabilityController.action('rollback', Number(data.capRollback)); return true; }
  if ('toolDetail' in data) { cap.tool = catalog.tools.find(tool => tool.id === data.toolDetail); if (state.route.page !== 'skills') { history.pushState(null, '', '#/skills'); await showRoute(); } else render(); return true; }
  if ('useTool' in data) {
    const tool = catalog.tools.find(item => item.id === data.useTool && item.selectable);
    if (!tool) { state.error = '此工具不可单独选择。'; render(); return true; }
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
document.querySelector('.skip-link').addEventListener('click', (event) => { event.preventDefault(); document.querySelector('#main')?.focus(); });
window.addEventListener('unhandledrejection', (event) => { event.preventDefault(); safeLog('unhandled_async_error'); state.error = '操作出现异常，请刷新状态后重试。'; render(); });
await showRoute();
await loadCatalog();
