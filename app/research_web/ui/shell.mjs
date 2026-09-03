import { escapeHTML as e } from './markdown.mjs';
import { sessionHash, isRunning } from './core.mjs';
import { modelOptions, renderActivities, renderDatasets, renderDelivery, renderFiles } from './views.mjs';

const navItems = [['fingpt', '⌕', 'FinGPT'], ['claw', '◇', 'Claw'], ['skills', '▧', '能力中心'], ['history', '◷', '历史']];

export function filterGlobalSearch(query, sessions = [], skills = []) {
  const normalized = String(query || '').trim().toLocaleLowerCase();
  if (!normalized) return [];
  const work = (Array.isArray(sessions) ? sessions : []).filter((session) => `${session?.title || ''} ${session?.mode || ''}`.toLocaleLowerCase().includes(normalized)).map((session) => ({ kind: 'session', item: session }));
  const capabilities = (Array.isArray(skills) ? skills : []).filter((skill) => `${skill?.name || ''} ${skill?.description || ''}`.toLocaleLowerCase().includes(normalized)).map((skill) => ({ kind: 'skill', item: skill }));
  return [...work, ...capabilities].slice(0, 8);
}

export function renderGlobalSearch(query, sessions, skills) {
  const results = filterGlobalSearch(query, sessions, skills);
  return `<div class="global-search"><label class="sr-only" for="global-search">搜索会话标题和能力名称或简介</label><span aria-hidden="true">⌕</span><input id="global-search" data-global-search type="search" value="${e(query || '')}" placeholder="搜索会话标题、能力名称或简介…" autocomplete="off">${query ? `<div class="global-results" role="listbox">${results.length ? results.map(({ kind, item }) => kind === 'session' ? `<a role="option" href="${sessionHash(item)}" data-global-result="session" data-session-id="${e(item.id)}"><strong>${e(item.title || '未命名会话')}</strong><span>会话 · ${e(item.mode || 'FinGPT')}</span></a>` : `<button type="button" role="option" data-global-result="skill" data-skill-shortcut="${e(item.id)}"><strong>${e(item.name)}</strong><span>${e(item.description || '此 Skill 未提供描述。')}</span></button>`).join('') : '<p class="muted small">没有匹配的真实会话或 Skill。</p>'}</div>` : ''}</div>`;
}

export function renderPrimaryRail({ page, secondaryOpen = false } = {}) {
  return `<nav class="primary-rail" aria-label="产品主导航"><a class="rail-brand" href="#/fingpt" aria-label="AlphaFoundry Research">A</a><div class="primary-nav">${navItems.map(([target, icon, title]) => `<a href="#/${target}" class="rail-link ${page === target ? 'active' : ''}" ${page === target ? 'aria-current="page"' : ''} title="${e(title)}"><span aria-hidden="true">${icon}</span><span class="sr-only">${e(title)}</span></a>`).join('')}</div><button class="rail-link rail-toggle ${secondaryOpen ? 'active' : ''}" data-toggle-sidebar aria-label="${secondaryOpen ? '关闭会话侧栏' : '打开会话侧栏'}" aria-expanded="${secondaryOpen}">☰</button><a class="rail-link rail-settings ${page === 'settings' ? 'active' : ''}" href="#/settings" title="设置"><span aria-hidden="true">⚙</span><span class="sr-only">设置</span></a></nav>`;
}

function renderClawWorkspace(detail, workspaces, selectedWorkspace) {
  const datasets = Array.isArray(detail?.datasets) ? detail.datasets : [];
  const files = Array.isArray(detail?.files) ? detail.files : [];
  return `<section class="claw-workspace-view" aria-label="当前 Claw 会话工作区"><p class="muted small">仅显示当前会话的资料与产物；不会读取或混入其他会话。</p><label for="workspace-select">新 Claw 会话的工作空间</label><select id="workspace-select"><option value="">默认工作空间</option>${workspaces.map((workspace) => `<option value="${e(workspace.id)}" ${selectedWorkspace === workspace.id ? 'selected' : ''}>${e(workspace.name)}</option>`).join('')}</select>${detail ? `<div class="workspace-current"><strong>${e(detail.title || '当前 Claw 会话')}</strong><p class="small muted">资料 ${datasets.length} 项 · 文件 ${files.length} 个</p><ul>${datasets.map((dataset) => `<li>资料：${e(dataset?.name || dataset?.id || '未命名资料')}</li>`).join('')}${files.map((file) => `<li>文件：${e(file?.name || file?.id || '未命名文件')}</li>`).join('')}${!datasets.length && !files.length ? '<li class="muted">当前会话尚无资料或产物。</li>' : ''}</ul></div>` : '<p class="muted small">打开 Claw 会话后，当前会话的资料和产物会显示在这里。</p>'}</section>`;
}

export function renderClawWorkspaceCanvas({ detail, selectedPreview = null, busy = false } = {}) {
  const datasets = renderDatasets(detail?.id, detail?.datasets) || '<section class="context-section"><h3>研究资料</h3><p class="muted small">当前会话尚无研究资料。</p></section>';
  const files = `<section class="context-section"><div class="section-heading"><h3>文件</h3>${detail ? `<button class="text-button" data-refresh-files ${busy ? 'disabled' : ''}>刷新</button>` : ''}</div>${renderFiles(detail?.files || [], selectedPreview)}</section>`;
  return `<section class="claw-workspace-canvas" aria-label="当前 Claw 会话工作区"><header class="claw-workspace-header"><div><span class="eyebrow">CURRENT CLAW WORKSPACE</span><h2>${e(detail?.title || '当前 Claw 会话')}</h2><p class="muted">只显示当前会话的资料与文件；不会读取或混入其他会话。</p></div></header><div class="claw-workspace-content">${datasets}${files}</div></section>`;
}

export function renderSidebar({ page, sessionId, sessions = [], workspaces = [], selectedWorkspace = '', collapsed = false, mobileOpen = false, detail = null, clawSidebarView = 'sessions' } = {}) {
  const allSessions = Array.isArray(sessions) ? sessions : [];
  const recent = allSessions.slice(0, 10);
  const running = allSessions.filter((session) => isRunning(session.status));
  const clawTabs = page === 'claw' ? `<div class="claw-sidebar-tabs" role="tablist"><button type="button" role="tab" class="${clawSidebarView === 'sessions' ? 'active' : ''}" aria-selected="${clawSidebarView === 'sessions'}" data-claw-sidebar-view="sessions">会话</button><button type="button" role="tab" class="${clawSidebarView === 'workspace' ? 'active' : ''}" aria-selected="${clawSidebarView === 'workspace'}" data-claw-sidebar-view="workspace">当前工作区</button></div>` : '';
  const sessionsView = `<div class="secondary-session-view"><label class="sr-only" for="workspace-select">工作空间</label><select id="workspace-select"><option value="">默认工作空间</option>${workspaces.map((workspace) => `<option value="${e(workspace.id)}" ${selectedWorkspace === workspace.id ? 'selected' : ''}>${e(workspace.name)}</option>`).join('')}</select><button class="button new-session" data-new>＋ 新建研究</button><div class="recent-section"><div class="recent-heading"><span class="eyebrow">运行任务</span><span class="count">${running.length}</span></div>${running.length ? running.map((session) => `<a href="${sessionHash(session)}" class="recent-item"><span class="tiny-dot active"></span><span>${e(session.title || '未命名会话')}</span></a>`).join('') : '<p class="muted small sidebar-empty">当前没有运行任务。</p>'}<div class="recent-heading"><span class="eyebrow">最近会话</span><a href="#/history" aria-label="查看全部历史">↗</a></div><div class="recent-sessions">${recent.length ? recent.map((session) => `<a href="${sessionHash(session)}" class="recent-item ${sessionId === session.id ? 'active' : ''}" title="${e(session.title)}"><span class="tiny-dot ${isRunning(session.status) ? 'active' : ''}"></span><span>${e(session.title || '未命名会话')}</span></a>`).join('') : '<p class="muted small sidebar-empty">开始第一项研究后，会话将显示在这里。</p>'}</div></div></div>`;
  const body = page === 'claw' && clawSidebarView === 'workspace' ? renderClawWorkspace(detail, workspaces, selectedWorkspace) : sessionsView;
  const hidden = collapsed && !mobileOpen;
  return `<aside class="sidebar secondary-sidebar ${mobileOpen ? 'mobile-open' : ''} ${collapsed ? 'collapsed' : ''}" aria-label="会话与工作区侧栏" ${hidden ? 'aria-hidden="true"' : ''}><div class="sidebar-top"><span class="eyebrow">${page === 'claw' ? 'CLAW WORKSPACE' : 'RESEARCH SESSIONS'}</span><button class="icon-button sidebar-close" data-toggle-sidebar aria-label="关闭会话侧栏">×</button><button class="icon-button sidebar-collapse" data-collapse-sidebar aria-label="折叠会话侧栏">‹</button></div>${clawTabs}${body}</aside>`;
}

export function renderContextPanel({ detail, selectedTab = 'activity', mobileOpen = false, selectedPreview = null, busy = false } = {}) {
  const tabs = [['activity', '活动'], ['datasets', '资料'], ['files', '文件']];
  const panel = selectedTab === 'datasets' ? renderDatasets(detail?.id, detail?.datasets) || '<p class="muted small context-empty">本会话暂无研究资料。</p>' : selectedTab === 'files' ? `<section class="context-section"><div class="section-heading"><h3>文件</h3>${detail ? `<button class="text-button" data-refresh-files ${busy ? 'disabled' : ''}>刷新</button>` : ''}</div>${renderFiles(detail?.files || [], selectedPreview)}</section>` : `${renderDelivery(detail?.delivery)}${renderActivities(detail)}`;
  return `<aside class="context-panel ${mobileOpen ? 'mobile-open' : ''}" aria-label="研究活动、资料与文件"><header class="context-header"><div><h2>研究空间</h2><span class="badge">${detail?.mode === 'claw' ? 'CLAW' : 'FINGPT'}</span></div><button class="icon-button context-close" data-toggle-context aria-label="关闭研究空间">×</button></header><div class="context-tabs" role="tablist">${tabs.map(([id, label]) => `<button type="button" role="tab" class="context-tab ${selectedTab === id ? 'active' : ''}" aria-selected="${selectedTab === id}" data-context-tab="${id}">${label}</button>`).join('')}</div><div class="context-tab-panel">${panel}</div></aside>`;
}

export function renderTopbar({ runtimeLabel, runtime, models = [], busy = false, search = '', sessions = [], skills = [] } = {}) {
  return `<header class="topbar"><button class="icon-button menu-toggle" data-toggle-sidebar aria-label="打开导航">☰</button><a class="brand" href="#/fingpt"><img src="/static/assets/alphafoundry-logo.png" width="30" height="30" alt=""><span>AlphaFoundry</span><span class="brand-divider"></span><span class="brand-label">Research</span></a>${renderGlobalSearch(search, sessions, skills)}<div class="topbar-right"><a href="#/settings" class="runtime-status"><span class="tiny-dot ${runtime?.connected ? 'active' : ''}"></span>${e(runtimeLabel || 'DSH 未连接')}</a><label class="sr-only" for="model-select">运行模型</label><select id="model-select" ${busy ? 'disabled' : ''}>${modelOptions(models, runtime?.model)}</select><button class="icon-button" data-refresh aria-label="刷新服务状态" title="刷新服务状态">↻</button></div></header>`;
}
