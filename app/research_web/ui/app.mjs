import { createAPI, createController, parseRoute, isRunning, safeLog, collectQuestionAnswers } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { badge, empty, renderConversation, renderHistory, modelOptions, renderRename } from './views.mjs';
import { renderComposer, renderQuickSkills } from './composer.mjs';
import { renderContextPanel, renderPrimaryRail, renderSidebar, renderTopbar } from './shell.mjs';

const api = createAPI();
const root = document.querySelector('#app');
const catalog = { runtime: null, models: [], sessions: [], workspaces: [], skills: [], errors: {}, modelFailures: [] };
let selectedWorkspace = ''; let selectedPreview = null; let historyFilter = ''; let success = ''; let sidebarOpen = false; let sidebarCollapsed = false; let clawSidebarView = 'sessions'; let contextOpen = false; let contextTab = 'activity'; let globalSearch = ''; let slashOpen = false; let selectedSkillDetail = '';
let pageGeneration = 0;
let renameDraft = null;
const questionDrafts = new Map();
const controller = createController({ api, onNavigate: (hash) => { history.pushState(null, '', hash); } });
const state = controller.state;

function runtimeLabel() {
  if (!catalog.runtime) return 'DSH 未连接';
  if (catalog.runtime.connected && catalog.runtime.credential_configured === false) return 'DSH 待授权';
  return catalog.runtime.connected ? 'DSH 已连接' : 'DSH 不可用';
}

function notice(message, kind = 'error') { return message ? `<div class="notice ${kind}" role="${kind === 'error' ? 'alert' : 'status'}">${e(message)}</div>` : ''; }

function composer() {
  const disabled = state.busy || state.loading || Boolean(state.route.sessionId && !state.detail);
  const taskPending = state.detail && (isRunning(state.detail.status) || state.detail.can_cancel || ['pending', 'admission_unknown'].includes(state.detail.delivery?.status));
  return renderComposer({ page: state.route.page, draft: state.draft, attachments: state.attachments, expectedFormats: state.expectedFormats, skills: catalog.skills, skillId: state.skillId, disabled, busy: state.busy, taskPending, detail: state.detail, slashOpen });
}

function landing() {
  const claw = state.route.page === 'claw';
  const detail = catalog.skills.find((skill) => skill.id === selectedSkillDetail);
  return `<div class="landing ${claw ? 'claw-landing' : 'fingpt-landing'}"><div class="landing-brand"><img src="/static/assets/alphafoundry-logo.png" alt="" width="56" height="56"><span class="eyebrow">${claw ? 'CLAW · GOAL WORKSPACE' : 'FINGPT · RESEARCH PARTNER'}</span></div><h1>${claw ? '把研究目标变成可交付结果' : 'FinGPT，您的即时投研伙伴'}</h1><p class="landing-subtitle">${claw ? '描述目标、边界和希望交付的文件。DSH 仅在你开始研究后协调真实 Agent、工具与资料。' : '从一个好问题开始。连接真实信息，理解复杂问题，沉淀研究成果。'}</p>${composer()}${detail ? `<aside class="skill-detail-card" aria-label="${e(detail.name)} 详情"><div><span class="eyebrow">真实 Skill</span><h2>${e(detail.name)}</h2><p>${e(detail.description || '此 Skill 未提供描述。')}</p></div><button type="button" class="icon-button" data-close-skill-detail aria-label="关闭 Skill 详情">×</button></aside>` : ''}${renderQuickSkills(catalog.skills)}<div class="capability-notes"><div><span aria-hidden="true">⌕</span><strong>深入理解</strong><p>围绕问题持续追问，在同一会话中推进研究。</p></div><div><span aria-hidden="true">▤</span><strong>带上你的资料</strong><p>支持 PDF、图片、Markdown、CSV 与 Excel。</p></div><div><span aria-hidden="true">◇</span><strong>${claw ? '明确交付' : '看见研究过程'}</strong><p>${claw ? '设置输出格式，先准备草稿，再由你确认开始。' : '查看真实工具活动、Agent 协作与产出文件。'}</p></div></div></div>`;
}

function researchPage() {
  if (state.loading) return `<div class="loading-state" role="status">正在读取会话…</div>`;
  if (state.route.sessionId && !state.detail) return `${empty('暂时无法读取这个会话', '检查连接后重试，输入内容仍会保留。')}<button class="button" data-reload-session>重新读取</button>`;
  if (!state.detail) return landing();
  const detail = state.detail;
  return `<header class="page-header"><div class="session-title"><div class="eyebrow">${detail.mode === 'claw' ? 'CLAW · AGENT RESEARCH' : 'FINGPT · RESEARCH SESSION'}</div><h1>${e(detail.title || '未命名会话')}</h1><div class="session-meta">${badge(detail.status)}${detail.model ? `<span>${e(detail.model)}</span>` : ''}</div></div><div class="button-row"><button class="button small" data-rename ${state.busy ? 'disabled' : ''}>重命名</button>${detail.mode !== 'claw' ? `<button class="button small" data-upgrade ${state.busy || isRunning(detail.status) ? 'disabled' : ''}>升级为 Claw ↗</button>` : ''}<button class="button small context-toggle" data-toggle-context>活动与文件</button></div></header>${renameDraft !== null ? renderRename(renameDraft) : ''}${notice(state.streamError, 'warning')}<div id="messages" class="messages" aria-label="会话消息">${renderConversation(detail, questionDrafts)}</div><div class="composer-dock">${composer()}</div>`;
}

function settingsPage() {
  const runtime = catalog.runtime;
  return `<header class="page-header"><div><div class="eyebrow">WORKSPACE SETTINGS</div><h1>运行时与模型</h1><p class="muted">Research Web 只连接 DSH，不启动其他研究管线。</p></div><button class="button" data-refresh>刷新状态</button></header><section class="settings-card"><div class="section-heading"><h2>DSH 连接</h2><span class="badge ${runtime?.connected ? 'live' : 'danger'}">${runtimeLabel()}</span></div><dl class="runtime-details"><div><dt>Provider</dt><dd>${e(runtime?.provider || '未提供')}</dd></div><div><dt>模型</dt><dd>${e(runtime?.model || '未配置')}</dd></div><div><dt>版本</dt><dd>${e(runtime?.version || '未提供')}</dd></div><div><dt>管理方式</dt><dd>${runtime ? runtime.owned_runtime ? '由 AlphaFoundry 管理' : '外部运行时' : '未知'}</dd></div></dl>${runtime?.message ? `<p class="muted">${e(runtime.message)}</p>` : ''}</section><section class="settings-card"><h2>模型配置</h2><p class="muted">选择模型并按需更新 API Key。秘密值不回填，也不会存入浏览器存储。</p><form id="settings-form" autocomplete="off"><label for="settings-model">可用模型</label><select id="settings-model">${modelOptions(catalog.models, runtime?.model)}</select><div class="form-grid"><label>Provider<input id="provider" name="provider" required autocomplete="off" value="${e(runtime?.provider || '')}" placeholder="例如 openai"></label><label>模型 ID<input id="model-id" name="model" required autocomplete="off" value="${e(runtime?.model || '')}" placeholder="输入运行时支持的模型 ID"></label></div><label for="api-key">API Key <span class="muted">（可选，仅更新时填写）</span></label><input id="api-key" name="api_key" type="password" autocomplete="new-password" spellcheck="false" placeholder="留空则不更改现有凭据"><p class="muted small">只发送给当前同源后端；保存成功后清空输入。模型变更作用于 DSH 运行时。</p><button class="button primary" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在保存…' : '保存配置'}</button></form></section>${catalog.modelFailures.length ? notice('部分模型目录未能加载；可填写已知的 Provider 与模型 ID。', 'warning') : ''}`;
}

function mainPage() {
  if (['fingpt', 'claw'].includes(state.route.page)) return researchPage();
  if (state.route.page === 'settings') return settingsPage();
  if (state.route.page === 'history') return `<header class="page-header"><div><div class="eyebrow">YOUR RESEARCH</div><h1>研究历史</h1><p class="muted">所有 FinGPT 与 Claw 会话，随时回来继续。</p></div><button class="button" data-refresh>刷新</button></header><label class="search-box"><span aria-hidden="true">⌕</span><input id="history-search" type="search" placeholder="搜索会话标题…" value="${e(historyFilter)}" aria-label="搜索研究历史"></label><div id="history-results">${renderHistory(catalog.sessions, historyFilter)}</div>`;
  return `<header class="page-header"><div><div class="eyebrow">RESEARCH CAPABILITIES</div><h1>能力中心</h1><p class="muted">来自 DSH 的已安装能力。选择后可在研究中使用。</p></div><button class="button" data-refresh>刷新</button></header>${catalog.skills.length ? `<div class="skills-grid">${catalog.skills.map((skill) => `<article class="skill-card"><div class="skill-icon">◇</div><h2>${e(skill.name)}</h2><p>${e(skill.description || '此 Skill 未提供描述。')}</p><button class="button" data-use-skill="${e(skill.id)}">放入 FinGPT 草稿 ↗</button></article>`).join('')}</div>` : empty('尚无可用 Skill', '请在 DSH 中配置能力后刷新。')}`;
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
  return renderContextPanel({ detail: state.detail, selectedTab: contextTab, mobileOpen: contextOpen, selectedPreview, busy: state.busy });
}

function render() {
  const active = document.activeElement; const focusId = active?.id;
  const selection = active && ['TEXTAREA', 'INPUT'].includes(active.tagName) && active.type !== 'password' ? { start: active.selectionStart, end: active.selectionEnd } : null;
  const mainScroll = document.querySelector('#main')?.scrollTop || 0;
  const research = ['fingpt', 'claw'].includes(state.route.page);
  root.innerHTML = `<div class="app-shell ${research ? '' : 'wide-page'} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}">${renderTopbar({ runtimeLabel: runtimeLabel(), runtime: catalog.runtime, models: catalog.models, busy: state.busy, search: globalSearch, sessions: catalog.sessions, skills: catalog.skills })}${primaryRail()}${sidebar()}<main id="main" tabindex="-1"><div class="page-content">${notice(state.error)}${Object.entries(catalog.errors).map(([name, error]) => notice(`${({ runtime: '运行时', models: '模型目录', workspaces: '工作空间', sessions: '会话历史', skills: 'Skills' })[name]}：${error}`)).join('')}${notice(success, 'success')}${mainPage()}</div></main>${research ? contextPanel() : ''}</div>${sidebarOpen || contextOpen ? '<button class="mobile-backdrop" data-close-drawers aria-label="关闭面板"></button>' : ''}`;
  document.querySelector('#main').scrollTop = mainScroll;
  if (focusId) {
    const replacement = document.getElementById(focusId);
    if (replacement && !replacement.disabled) { replacement.focus({ preventScroll: true }); if (selection && selection.start !== null) replacement.setSelectionRange?.(selection.start, selection.end); }
  }
  if (state.busy) root.querySelectorAll('[data-approval], [data-upload], .question-form button, #rename-form button').forEach((button) => { button.disabled = true; });
  document.title = `${state.detail?.title || ({ fingpt: 'FinGPT', claw: 'Claw', history: '研究历史', skills: 'Skills', settings: '设置' })[state.route.page]} · AlphaFoundry`;
}

async function loadCatalog(names = ['runtime', 'models', 'workspaces', 'sessions', 'skills']) {
  await Promise.all(names.map(async (name) => {
    try {
      const data = await api[name]();
      if (name === 'runtime') catalog.runtime = data;
      else if (name === 'models') { catalog.models = data.groups || []; catalog.modelFailures = data.failures || []; }
      else catalog[name] = data.items || [];
      delete catalog.errors[name];
    } catch (error) { catalog.errors[name] = error.message; if (name === 'runtime') catalog.runtime = null; }
  }));
  render();
}

async function showRoute() {
  const ticket = ++pageGeneration; success = ''; selectedPreview = null; sidebarOpen = false; clawSidebarView = 'sessions'; contextOpen = false; contextTab = 'activity'; slashOpen = false; selectedSkillDetail = ''; renameDraft = null; questionDrafts.clear();
  await controller.open(parseRoute(location.hash));
  if (ticket !== pageGeneration) return;
  document.querySelector('#main')?.scrollTo({ top: 0 });
  if (state.route.page === 'history') await loadCatalog(['sessions']);
  if (state.route.page === 'skills') await loadCatalog(['skills']);
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
    slashOpen = event.target.value.trimStart().startsWith('/');
    if (slashOpen) render();
  }
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
  if (event.target.id === 'prompt' && event.key === 'Enter' && !event.shiftKey && !event.isComposing) { event.preventDefault(); document.querySelector('#composer')?.requestSubmit(); }
  if (event.key === 'Escape') { sidebarOpen = false; contextOpen = false; renameDraft = null; render(); }
});

root.addEventListener('change', async (event) => {
  const target = event.target;
  if (target.id === 'workspace-select') selectedWorkspace = target.value;
  if (target.id === 'skill-select') { controller.setSkill(target.value); render(); }
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
    if (!state.draft.trim() || state.busy) return;
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
  const button = event.target.closest('button'); if (!button || button.disabled) return;
  const data = button.dataset;
  if ('new' in data) { history.pushState(null, '', state.route.page === 'claw' ? '#/claw' : '#/fingpt'); await showRoute(); controller.setDraft(''); render(); document.querySelector('#prompt')?.focus(); }
  if ('refresh' in data) { success = ''; await loadCatalog(); await controller.refresh(); }
  if ('reloadSession' in data) await showRoute();
  if ('toggleSidebar' in data) {
    const narrow = window.matchMedia('(max-width: 1050px)').matches;
    if (narrow) sidebarOpen = !sidebarOpen;
    else sidebarCollapsed = !sidebarCollapsed;
    contextOpen = false; render();
  }
  if ('toggleContext' in data) { contextOpen = !contextOpen; sidebarOpen = false; render(); }
  if ('collapseSidebar' in data) {
    if (window.matchMedia('(max-width: 1050px)').matches) sidebarOpen = false;
    else sidebarCollapsed = true;
    render();
  }
  if ('clawSidebarView' in data) { clawSidebarView = data.clawSidebarView; render(); }
  if ('contextTab' in data) { contextTab = data.contextTab; render(); }
  if ('closeDrawers' in data) { sidebarOpen = false; contextOpen = false; render(); }
  if ('upload' in data) document.querySelector('#file-input')?.click();
  if ('slashSearch' in data) { slashOpen = !slashOpen; render(); document.querySelector('#prompt')?.focus(); }
  if ('removeAttachment' in data) controller.removeAttachment(data.removeAttachment);
  if ('cancelRename' in data) { renameDraft = null; render(); }
  if ('noFormats' in data) { controller.setFormats([]); render(); }
  if ('preview' in data) { selectedPreview = data.preview; render(); }
  if ('closePreview' in data) { selectedPreview = null; render(); }
  if ('closeSkillDetail' in data) { selectedSkillDetail = ''; render(); }
  if ('skillDetail' in data) { selectedSkillDetail = data.skillDetail; render(); }
  if ('skillShortcut' in data) {
    if (!catalog.skills.some((skill) => skill.id === data.skillShortcut)) { state.error = '所选 Skill 已不可用，请刷新能力目录。'; render(); return; }
    if (data.globalResult === 'skill' && !['fingpt', 'claw'].includes(state.route.page)) { history.pushState(null, '', '#/fingpt'); await showRoute(); }
    controller.setSkill(data.skillShortcut);
    if (state.draft.trimStart().startsWith('/')) controller.setDraft('');
    slashOpen = false;
    render();
    document.querySelector('#prompt')?.focus();
  }
  if ('useSkill' in data) { history.pushState(null, '', '#/fingpt'); await showRoute(); controller.setSkill(data.useSkill); render(); document.querySelector('#prompt')?.focus(); }
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

controller.subscribe(render);
window.addEventListener('hashchange', () => { void showRoute(); });
document.querySelector('.skip-link').addEventListener('click', (event) => { event.preventDefault(); document.querySelector('#main')?.focus(); });
window.addEventListener('unhandledrejection', (event) => { event.preventDefault(); safeLog('unhandled_async_error'); state.error = '操作出现异常，请刷新状态后重试。'; render(); });
await showRoute();
await loadCatalog();
