import { createAPI, createController, parseRoute, sessionHash, isRunning, safeLog } from './core.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { badge, empty, renderConversation, renderActivities, renderFiles, renderHistory, modelOptions, renderRename, renderDelivery, renderFormatPicker } from './views.mjs';

const api = createAPI();
const root = document.querySelector('#app');
const catalog = { runtime: null, models: [], sessions: [], workspaces: [], skills: [], errors: {}, modelFailures: [] };
let selectedWorkspace = ''; let selectedPreview = null; let historyFilter = ''; let success = ''; let sidebarOpen = false; let contextOpen = false;
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
  return `<form id="composer" class="composer"><label class="sr-only" for="prompt">${state.route.page === 'claw' ? '任务目标或补充信息' : '研究问题'}</label><textarea id="prompt" name="prompt" rows="3" placeholder="${state.route.page === 'claw' ? '描述研究目标、约束与希望交付的结果…' : '今天想研究什么？输入问题，或添加文件…'}" ${disabled ? 'disabled' : ''}>${e(state.draft)}</textarea>${state.attachments.length ? `<div class="attachment-chips">${state.attachments.map((file) => `<span>${e(file.name)}<button type="button" data-remove-attachment="${e(file.id)}" aria-label="移除附件 ${e(file.name)}">×</button></span>`).join('')}</div>` : ''}${renderFormatPicker(state.expectedFormats, state.skillId)}<div class="composer-tools"><button type="button" class="button attachment-button" data-upload ${disabled ? 'disabled' : ''} title="PDF、图片、Markdown、CSV、Excel">＋ <span>附件</span></button><label class="sr-only" for="skill-select">使用 Skill</label><select id="skill-select" ${disabled ? 'disabled' : ''}><option value="">按需使用 Skill</option>${catalog.skills.map((skill) => `<option value="${e(skill.id)}" ${state.skillId === skill.id ? 'selected' : ''}>${e(skill.name)}</option>`).join('')}</select><span class="spacer"></span>${state.detail && (isRunning(state.detail.status) || state.detail.can_cancel) ? `<button type="button" class="button danger-outline" data-cancel ${state.busy ? 'disabled' : ''}>停止</button>` : ''}<button type="submit" class="button primary" ${disabled || taskPending ? 'disabled' : ''}>${state.busy ? '正在提交…' : state.detail ? '发送' : '开始研究'} <span aria-hidden="true">↑</span></button></div><input id="file-input" type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.webp,.gif,.md,.csv,.xlsx" hidden></form><p class="composer-caption">${taskPending ? '上一任务及其交付尚未确认结束；可准备草稿，完成后再发送。' : 'Enter 发送 · Shift + Enter 换行 · 内容交由 DSH 运行时处理'}</p>`;
}

function landing() {
  const claw = state.route.page === 'claw';
  return `<div class="landing"><div class="landing-brand"><img src="/static/assets/alphafoundry-logo.png" alt="" width="56" height="56"><span class="eyebrow">${claw ? 'AGENT WORKSPACE' : 'YOUR RESEARCH PARTNER'}</span></div><h1>${claw ? '复杂研究，交给 Claw' : 'FinGPT，您的即时投研伙伴'}</h1><p class="landing-subtitle">${claw ? '把目标变成行动。由 DSH 协调 Agent、工具与文件，持续推进研究。' : '从一个好问题开始。连接真实信息，理解复杂问题，沉淀研究成果。'}</p>${composer()}<div class="capability-notes"><div><span aria-hidden="true">⌕</span><strong>深入理解</strong><p>围绕问题持续追问，在同一会话中推进研究。</p></div><div><span aria-hidden="true">▤</span><strong>带上你的资料</strong><p>支持 PDF、图片、Markdown、CSV 与 Excel。</p></div><div><span aria-hidden="true">◇</span><strong>看见研究过程</strong><p>查看真实工具活动、Agent 协作与产出文件。</p></div></div></div>`;
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
  return `<header class="page-header"><div><div class="eyebrow">RESEARCH CAPABILITIES</div><h1>Skills</h1><p class="muted">来自 DSH 的已安装能力。选择后可在研究中使用。</p></div><button class="button" data-refresh>刷新</button></header>${catalog.skills.length ? `<div class="skills-grid">${catalog.skills.map((skill) => `<article class="skill-card"><div class="skill-icon">◇</div><h2>${e(skill.name)}</h2><p>${e(skill.description || '此 Skill 未提供描述。')}</p><button class="button" data-use-skill="${e(skill.id)}">在 FinGPT 使用 ↗</button></article>`).join('')}</div>` : empty('尚无可用 Skill', '请在 DSH 中配置能力后刷新。')}`;
}

function sidebar() {
  return `<aside class="sidebar ${sidebarOpen ? 'mobile-open' : ''}" aria-label="研究导航"><div class="sidebar-top"><span class="eyebrow">RESEARCH WORKSPACE</span><button class="icon-button sidebar-close" data-toggle-sidebar aria-label="关闭导航">×</button></div><label class="sr-only" for="workspace-select">工作空间</label><select id="workspace-select"><option value="">默认工作空间</option>${catalog.workspaces.map((workspace) => `<option value="${e(workspace.id)}" ${selectedWorkspace === workspace.id ? 'selected' : ''}>${e(workspace.name)}</option>`).join('')}</select><button class="button new-session" data-new>＋ 新建研究</button><nav class="main-nav" aria-label="产品导航">${[['fingpt', '⌕', 'FinGPT', '即时研究'], ['claw', '◇', 'Claw', 'Agent 协作'], ['history', '◷', '研究历史', ''], ['skills', '▧', 'Skills', '']].map(([page, icon, title, description]) => `<a href="#/${page}" class="nav-link ${state.route.page === page ? 'active' : ''}" ${state.route.page === page ? 'aria-current="page"' : ''}><span class="nav-icon" aria-hidden="true">${icon}</span><span><strong>${title}</strong>${description ? `<small>${description}</small>` : ''}</span></a>`).join('')}</nav><div class="recent-heading"><span class="eyebrow">最近会话</span><a href="#/history" aria-label="查看全部历史">↗</a></div><div class="recent-sessions">${catalog.sessions.slice(0, 10).map((session) => `<a href="${sessionHash(session)}" class="recent-item ${state.route.sessionId === session.id ? 'active' : ''}" title="${e(session.title)}"><span class="tiny-dot ${isRunning(session.status) ? 'active' : ''}"></span><span>${e(session.title || '未命名会话')}</span></a>`).join('') || '<p class="muted small sidebar-empty">开始第一项研究后，会话将显示在这里。</p>'}</div><div class="sidebar-footer"><a class="nav-link ${state.route.page === 'settings' ? 'active' : ''}" href="#/settings"><span class="nav-icon" aria-hidden="true">⚙</span><strong>设置</strong></a><span class="local-caption">AlphaFoundry Research · DSH</span></div></aside>`;
}

function contextPanel() {
  const usage = state.detail?.usage;
  return `<aside class="context-panel ${contextOpen ? 'mobile-open' : ''}" aria-label="研究活动与文件"><header class="context-header"><h2>研究空间</h2><button class="icon-button context-close" data-toggle-context aria-label="关闭研究空间">×</button><span class="badge">${state.detail?.mode === 'claw' ? 'CLAW' : 'FINGPT'}</span></header>${renderDelivery(state.detail?.delivery)}${renderActivities(state.detail)}<section class="context-section"><div class="section-heading"><h3>文件</h3>${state.detail ? `<button class="text-button" data-refresh-files ${state.busy ? 'disabled' : ''}>刷新</button>` : ''}</div>${renderFiles(state.detail?.files || [], selectedPreview)}</section>${usage && (usage.tokens != null || usage.cost != null) ? `<footer class="usage-footer">${usage.tokens != null ? `<span>Tokens <strong>${e(usage.tokens)}</strong></span>` : ''}${usage.cost != null ? `<span>运行时费用 <strong>${e(usage.cost)}</strong></span>` : ''}</footer>` : ''}</aside>`;
}

function render() {
  const active = document.activeElement; const focusId = active?.id;
  const selection = active && ['TEXTAREA', 'INPUT'].includes(active.tagName) && active.type !== 'password' ? { start: active.selectionStart, end: active.selectionEnd } : null;
  const mainScroll = document.querySelector('#main')?.scrollTop || 0;
  const research = ['fingpt', 'claw'].includes(state.route.page);
  root.innerHTML = `<div class="app-shell ${research ? '' : 'wide-page'}"><header class="topbar"><button class="icon-button menu-toggle" data-toggle-sidebar aria-label="打开导航" aria-expanded="${sidebarOpen}">☰</button><a class="brand" href="#/fingpt"><img src="/static/assets/alphafoundry-logo.png" width="30" height="30" alt=""><span>AlphaFoundry</span><span class="brand-divider"></span><span class="brand-label">Research</span></a><div class="topbar-right"><a href="#/settings" class="runtime-status"><span class="tiny-dot ${catalog.runtime?.connected ? 'active' : ''}"></span>${runtimeLabel()}</a><label class="sr-only" for="model-select">运行模型</label><select id="model-select" ${state.busy ? 'disabled' : ''}>${modelOptions(catalog.models, catalog.runtime?.model)}</select><button class="icon-button" data-refresh aria-label="刷新服务状态" title="刷新服务状态">↻</button></div></header>${sidebar()}<main id="main" tabindex="-1"><div class="page-content">${notice(state.error)}${Object.entries(catalog.errors).map(([name, error]) => notice(`${({ runtime: '运行时', models: '模型目录', workspaces: '工作空间', sessions: '会话历史', skills: 'Skills' })[name]}：${error}`)).join('')}${notice(success, 'success')}${mainPage()}</div></main>${research ? contextPanel() : ''}</div>${sidebarOpen || contextOpen ? '<button class="mobile-backdrop" data-close-drawers aria-label="关闭面板"></button>' : ''}`;
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
  const ticket = ++pageGeneration; success = ''; selectedPreview = null; sidebarOpen = false; contextOpen = false; renameDraft = null; questionDrafts.clear();
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
  if (event.target.id === 'prompt') controller.setDraft(event.target.value);
  if (event.target.id === 'rename-title') renameDraft = event.target.value;
  const form = event.target.closest('[data-question-form]');
  if (form) {
    const question = state.detail?.questions?.find((item) => item.id === form.dataset.questionForm);
    if (question) questionDrafts.set(question.id, collectAnswers(form, question));
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
  if (target.id === 'file-input' && target.files?.length) {
    const files = [...target.files];
    if (!(await ensureSession())) return;
    const id = state.detail.id;
    const result = await controller.action(() => api.upload(id, files));
    if (result?.items && state.detail?.id === id) controller.addAttachments(result.items);
  }
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
  if ('toggleSidebar' in data) { sidebarOpen = !sidebarOpen; contextOpen = false; render(); }
  if ('toggleContext' in data) { contextOpen = !contextOpen; sidebarOpen = false; render(); }
  if ('closeDrawers' in data) { sidebarOpen = false; contextOpen = false; render(); }
  if ('upload' in data) document.querySelector('#file-input')?.click();
  if ('removeAttachment' in data) controller.removeAttachment(data.removeAttachment);
  if ('cancelRename' in data) { renameDraft = null; render(); }
  if ('noFormats' in data) { controller.setFormats([]); render(); }
  if ('preview' in data) { selectedPreview = data.preview; render(); }
  if ('closePreview' in data) { selectedPreview = null; render(); }
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
  const values = new FormData(form);
  return question.items.map((item, index) => ({ id: item.id, selected: values.getAll(`selection-${index}`).map(String), custom: String(values.get(`custom-${index}`) || '') }));
}

controller.subscribe(render);
window.addEventListener('hashchange', () => { void showRoute(); });
document.querySelector('.skip-link').addEventListener('click', (event) => { event.preventDefault(); document.querySelector('#main')?.focus(); });
window.addEventListener('unhandledrejection', (event) => { event.preventDefault(); safeLog('unhandled_async_error'); state.error = '操作出现异常，请刷新状态后重试。'; render(); });
await showRoute();
await loadCatalog();
