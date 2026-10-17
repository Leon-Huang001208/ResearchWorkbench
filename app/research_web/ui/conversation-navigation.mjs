import { renderProjectActionsMenu } from './conversation-menus.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { safeLog, isRunning } from './core.mjs';

const modes = new Set(['claw', 'fingpt']);
const key = item => `${item.kind}:${item.id}`;
const emptyMetadata = mode => ({ mode, revision: 0, pinned: [], project_order: [] });
export const completionStamp = session => String(session?.updated_at ?? 'completed');
const storageKey = mode => `research-web.navigation.v1.${/^[a-f0-9-]{36}$/.test(globalThis.__RWB_USER_ID__ || '') ? `user.${globalThis.__RWB_USER_ID__}.` : ''}${mode}`;
export function readNavigationView(mode, storage) {
  try {
    storage ??= globalThis.localStorage;
    const value = JSON.parse(storage?.getItem(storageKey(mode)) || '{}');
    return { seenCompletions: value.seenCompletions && typeof value.seenCompletions === 'object' && !Array.isArray(value.seenCompletions) ? Object.fromEntries(Object.entries(value.seenCompletions).filter(([id, stamp]) => id.length <= 255 && typeof stamp === 'string' && stamp.length <= 128)) : {}, collapsed: value.collapsed === true, collapsedSections: Array.isArray(value.collapsedSections) ? value.collapsedSections.filter(id => ['pinned', 'projects', 'recent'].includes(id)) : [], expanded: Array.isArray(value.expanded) ? value.expanded.filter(id => typeof id === 'string') : [], limit: Number.isInteger(value.limit) && value.limit >= 10 ? value.limit : 10 };
  } catch { safeLog('navigation_view_read_failed'); return { seenCompletions: {}, collapsed: false, collapsedSections: [], expanded: [], limit: 10 }; }
}
export function saveNavigationView(mode, view, storage) {
  try { storage ??= globalThis.localStorage; storage?.setItem(storageKey(mode), JSON.stringify(view)); }
  catch { safeLog('navigation_view_write_failed'); }
}
export function orderedProjects(projects, metadata) {
  const rows = projects.filter(item => !item.archived);
  const order = metadata?.project_order || [];
  return [...rows].sort((a, b) => {
    const ai = order.indexOf(a.id), bi = order.indexOf(b.id);
    return (ai < 0 ? order.length : ai) - (bi < 0 ? order.length : bi);
  });
}
export function moveNavigationItem(items, from, to) {
  const result = [...items]; const index = result.findIndex(item => key(item) === key(from));
  if (index < 0 || !Number.isInteger(to) || to < 0 || to >= result.length) return result;
  result.splice(to, 0, result.splice(index, 1)[0]); return result;
}

export function recentNavigationSessions(rows, projects, metadata) {
  const pinned = new Set((metadata?.pinned || []).filter(item => item.kind === 'session').map(item => item.id));
  const grouped = new Set(projects.filter(project => !project.archived && project.id !== 'default').map(project => project.id));
  const timestamp = value => typeof value === 'number' ? value : Date.parse(value) || 0;
  return rows.filter(row => !row.deleted_at && !pinned.has(row.id) && !grouped.has(row.project_id)).sort((a, b) => timestamp(b.updated_at) - timestamp(a.updated_at));
}

export function createConversationNavigation({ api, notify = () => {}, changed = async () => {} }) {
  const states = Object.fromEntries([...modes].map(mode => [mode, { metadata: emptyMetadata(mode), projects: [], loaded: false, loading: null, busy: false, error: '', editor: null, menu: null, view: readNavigationView(mode) }]));
  const state = mode => states[mode];
  async function load(mode, force = false) {
    if (!modes.has(mode)) return;
    const s = state(mode); if (s.loading) return s.loading; if (s.loaded && !force) return;
    s.loading = (async () => {
      try {
        const [metadata, projects] = await Promise.all([api.navigation(mode), api.projects(mode)]);
        if (metadata?.mode !== mode || !Number.isInteger(metadata.revision) || !Array.isArray(metadata.pinned) || !Array.isArray(metadata.project_order)) throw new Error('会话导航状态不可读取，请重试。');
        s.metadata = metadata; s.projects = projects.items || []; s.loaded = true; s.error = '';
      } catch (error) { s.error = error.message || '会话导航加载失败'; safeLog('navigation_load_failed', { status: error.code || 'request_failed' }); }
      finally { s.loading = null; notify(); }
    })(); return s.loading;
  }
  function view(mode, patch) { if (!state(mode)) return; Object.assign(state(mode).view, patch); saveNavigationView(mode, state(mode).view); }
  function markSeen(session) {
    const s = state(session?.mode);
    if (!s || session.status !== 'completed' || session.questions?.length) return;
    const stamp = completionStamp(session);
    if (s.view.seenCompletions?.[session.id] === stamp) return;
    view(session.mode, { seenCompletions: { ...(s.view.seenCompletions || {}), [session.id]: stamp } });
  }
  async function save(mode, metadata) {
    const s = state(mode); if (s.busy || !s.loaded) return false;
    s.busy = true; s.error = ''; notify();
    try { s.metadata = await api.saveNavigation(mode, { revision: s.metadata.revision, pinned: metadata.pinned, project_order: metadata.project_order }); return true; }
    catch (error) {
      if (error.code === 'navigation_changed' || error.status === 409) await load(mode, true);
      s.error = error.message || '保存失败，已保留原有排序。'; safeLog('navigation_save_failed', { status: error.code || 'request_failed' }); return false;
    } finally { s.busy = false; notify(); }
  }
  async function pin(mode, entity) {
    const s = state(mode); const pinned = s.metadata.pinned; const exists = pinned.some(item => key(item) === key(entity));
    return save(mode, { ...s.metadata, pinned: exists ? pinned.filter(item => key(item) !== key(entity)) : [...pinned, entity] });
  }
  async function reorder(mode, group, entity, directionOrTarget) {
    const s = state(mode); const items = group === 'pinned' ? s.metadata.pinned : orderedProjects(s.projects, s.metadata).map(p => ({ kind: 'project', id: p.id }));
    const index = items.findIndex(item => key(item) === key(entity));
    const target = typeof directionOrTarget === 'number' ? index + directionOrTarget : items.findIndex(item => key(item) === key(directionOrTarget));
    if (index < 0 || target < 0 || target >= items.length || index === target) return;
    const next = moveNavigationItem(items, entity, target);
    await save(mode, { ...s.metadata, ...(group === 'pinned' ? { pinned: next } : { project_order: next.map(item => item.id) }) });
  }
  async function projectSave(mode, name, id = null) {
    const s = state(mode); if (s.busy) return;
    s.busy = true; s.error = ''; notify();
    try { if (id) await api.updateProject(mode, id, { name }); else await api.createProject(mode, { name }); s.editor = null; await load(mode, true); return true; }
    catch (error) { s.error = error.message; safeLog('navigation_project_save_failed', { status: error.code || 'request_failed' }); return false; }
    finally { s.busy = false; notify(); }
  }
  function revealSession(mode, id, rows) {
    const s = state(mode); const session = rows.find(row => row.id === id && row.mode === mode && !row.deleted_at);
    if (!session) return;
    const project = s.projects.find(item => item.id === session.project_id && item.id !== 'default' && !item.archived);
    const pinned = s.metadata.pinned.some(item => item.kind === 'session' && item.id === id);
    const section = pinned || (project && s.metadata.pinned.some(item => item.kind === 'project' && item.id === project.id)) ? 'pinned' : project ? 'projects' : 'recent';
    const recentIndex = section === 'recent' ? recentNavigationSessions(rows.filter(row => row.mode === mode), s.projects, s.metadata).findIndex(row => row.id === id) : -1;
    view(mode, { collapsedSections: (s.view.collapsedSections || []).filter(item => item !== section), ...(project ? { expanded: [...new Set([...s.view.expanded, project.id])] } : {}), ...(recentIndex >= s.view.limit ? { limit: Math.ceil((recentIndex + 1) / 10) * 10 } : {}) });
  }
  async function moveSession(mode, id, projectId) {
    const s = state(mode); if (s.busy) return;
    s.busy = true; s.error = ''; notify();
    try {
      await api.moveClawSession(id, projectId);
      const pinnedSession = s.metadata.pinned.some(item => item.kind === 'session' && item.id === id);
      const targetSection = pinnedSession ? 'pinned' : projectId === 'default' ? 'recent' : s.metadata.pinned.some(item => item.kind === 'project' && item.id === projectId) ? 'pinned' : 'projects';
      view(mode, { expanded: [...new Set([...s.view.expanded, projectId])], collapsedSections: (s.view.collapsedSections || []).filter(section => section !== targetSection) });
      await changed(); await load(mode, true); return true;
    }
    catch (error) { s.error = error.message; safeLog('navigation_session_move_failed', { status: error.code || 'request_failed' }); return false; }
    finally { s.busy = false; notify(); }
  }
  return { state, load, view, markSeen, pin, reorder, projectSave, moveSession, revealSession, async archive(mode, id) {
    const s = state(mode); if (s.busy) return; s.busy = true; notify();
    try { await api.updateProject(mode, id, { archived: true }); s.menu = null; await load(mode, true); }
    catch (error) { s.error = error.message; safeLog('navigation_project_archive_failed', { status: error.code || 'request_failed' }); }
    finally { s.busy = false; notify(); }
  } };
}

export function renderConversationNavigation({ page, sessionId, clawView = 'sessions', sessions = [], collapsed, mobileOpen, detail, workspaces = [], selectedWorkspace = '', openMenuId, navigation, renderSessionRow }) {
  if (!modes.has(page)) return '';
  const s = navigation || { metadata: emptyMetadata(page), projects: [], view: { expanded: [], limit: 10 }, loaded: false };
  const hidden = collapsed && !mobileOpen; const label = page === 'claw' ? 'Claw' : 'FinGPT';
  const rows = sessions.filter(row => row.mode === page && !row.deleted_at).map(row => {
    const current = row.id === detail?.id ? { ...row, status: detail.status || row.status, updated_at: detail.updated_at ?? row.updated_at, waitingForAnswer: Boolean(detail.questions?.length) } : row;
    return { ...current, completionSeen: s.view.seenCompletions?.[row.id] === completionStamp(current) };
  });
  const projects = orderedProjects(s.projects || [], s.metadata);
  const pinned = (s.metadata?.pinned || []).filter(item => item.kind === 'session' ? rows.some(row => row.id === item.id) : projects.some(row => row.id === item.id));
  const pinnedSessions = new Set(pinned.filter(p => p.kind === 'session').map(p => p.id));
  const recent = recentNavigationSessions(rows, projects, s.metadata);
  const drag = (group, entity) => `draggable="${!s.busy}" data-nav-sortable="${group}" data-nav-entity="${entity.kind}" data-nav-id="${e(entity.id)}"`;
  function projectRow(project, group) {
    const expanded = s.view.expanded.includes(project.id); const members = rows.filter(row => project.id !== 'default' && (row.project_id || 'default') === project.id && !pinnedSessions.has(row.id));
    return `<div class="nav-project" ${drag(group, { kind: 'project', id: project.id })}><div class="nav-project-row"><button type="button" class="nav-project-toggle" data-nav-project-toggle="${e(project.id)}" aria-expanded="${expanded}" title="${e(project.name)}">${icon('folder')}<span>${e(project.name)}</span><span class="nav-chevron ${expanded ? 'expanded' : ''}" aria-hidden="true">${icon('chevron')}</span></button><button type="button" class="session-actions-trigger" data-nav-project-menu="${e(project.id)}" aria-haspopup="menu" aria-label="${e(project.name)}的项目操作" aria-expanded="${s.menu === project.id}">${icon('more')}</button></div>${s.menu === project.id ? renderProjectActionsMenu({ project, position: s.menuPosition || { left: 76, top: 80 }, pinned: pinned.some(item => item.kind === 'project' && item.id === project.id), group, busy: s.busy, mode: page }) : ''}${expanded ? `<div class="nav-project-members">${members.length ? members.map(row => renderSessionRow(row, sessionId, openMenuId)).join('') : `<p class="sidebar-empty muted">${project.id === 'default' ? '未分组会话显示在最近' : '暂无会话'}</p>`}</div>` : ''}</div>`;
  }
  const folded = section => (s.view.collapsedSections || []).includes(section);
  const sectionToggle = (section, text) => `<button type="button" id="nav-section-toggle-${page}-${section}" class="nav-section-toggle" data-nav-section="${section}" aria-expanded="${!folded(section)}" aria-controls="nav-section-${page}-${section}"><span>${text}</span><span class="nav-section-chevron ${folded(section) ? '' : 'expanded'}" aria-hidden="true">${icon('chevron')}</span></button>`;
  const sectionBody = section => `id="nav-section-${page}-${section}" class="nav-section-body" ${folded(section) ? 'hidden' : ''}`;

  return `<aside class="sidebar secondary-sidebar ${mobileOpen ? 'mobile-open' : ''} ${collapsed ? 'collapsed' : ''} codex-sidebar" data-nav-mode="${page}" aria-label="${page === 'claw' ? 'Claw 会话与项目侧栏' : 'FinGPT 会话侧栏'}" ${hidden ? 'aria-hidden="true"' : ''}><header class="sidebar-top"><details class="nav-mode-menu" data-disclosure-key="${page}:nav-mode"><summary><h2>${label}</h2>${icon('chevron')}</summary><nav aria-label="研究模式与操作"><a href="#/fingpt">FinGPT</a><a href="#/claw">Claw</a>${detail ? '<button type="button" data-toggle-context>会话资料与文件</button>' : ''}${workspaces.length ? `<label for="workspace-select">新会话工作空间</label><select id="workspace-select"><option value="">默认工作空间</option>${workspaces.map(w => `<option value="${e(w.id)}" ${w.id === selectedWorkspace ? 'selected' : ''}>${e(w.name)}</option>`).join('')}</select>` : ''}</nav></details><div class="nav-header-actions"><button type="button" class="icon-button" data-toggle-search aria-label="搜索会话">${icon('search')}</button><button type="button" class="icon-button sidebar-collapse" data-collapse-sidebar aria-label="折叠 ${label} 二级侧栏">${icon('sidebar')}</button></div></header><button type="button" class="new-research" data-new aria-label="新建 ${label} 研究">${icon('compose')}<span>新聊天</span></button><nav class="nav-shortcuts" aria-label="${label} 常用功能">${page === 'claw' ? `<a href="#/claw?view=plans" ${clawView === 'plans' ? 'aria-current="page"' : ''}>${icon('activity')}<span>Agent 日程</span></a>` : ''}<a href="#/${page}?view=projects&project=default" ${clawView === 'projects' ? 'aria-current="page"' : ''}>${icon('folder')}<span>管理项目</span></a></nav><div class="nav-scroll">${s.error ? `<p class="notice error" role="alert">${e(s.error)} <button type="button" data-nav-retry>重试</button></p>` : ''}${!s.loaded && !s.error ? '<p class="muted small" role="status">正在加载会话导航…</p>' : ''}<section class="nav-section" aria-label="置顶"><div class="nav-section-heading">${sectionToggle('pinned', '置顶')}</div><div ${sectionBody('pinned')}>${pinned.length ? pinned.map(item => item.kind === 'project' ? projectRow(projects.find(p => p.id === item.id), 'pinned') : `<div ${drag('pinned', item)}>${renderSessionRow(rows.find(row => row.id === item.id), sessionId, openMenuId)}</div>`).join('') : '<p class="muted sidebar-empty">将常用会话或项目置顶</p>'}</div></section><section class="nav-section" aria-label="项目"><div class="nav-section-heading">${sectionToggle('projects', '项目')}<button type="button" class="icon-button" data-nav-project-create aria-label="新建项目" ${s.busy ? 'disabled' : ''}>+</button></div><div ${sectionBody('projects')}>${projects.filter(p => !pinned.some(item => item.kind === 'project' && item.id === p.id)).map(p => projectRow(p, 'project')).join('')}</div></section><section class="nav-section" aria-label="最近"><div class="nav-section-heading">${sectionToggle('recent', '最近')}<a href="#/history?mode=${page}">查看全部</a></div><div ${sectionBody('recent')}>${recent.filter((row, index) => index < s.view.limit || isRunning(row.status)).map(row => renderSessionRow(row, sessionId, openMenuId)).join('')}${!recent.length ? '<p class="muted sidebar-empty">开始新聊天后会显示在这里</p>' : ''}${recent.length > s.view.limit ? '<button type="button" class="text-button nav-show-more" data-nav-more>展开显示</button>' : ''}</div></section></div></aside>`;
}


export function renderProjectEditor(state) {
  if (!state?.editor) return '';
  const creating = !state.editor.id;
  const title = creating ? '创建项目' : '重命名项目';
  return `<div class="nav-project-backdrop" data-nav-project-backdrop><form class="nav-project-dialog" data-nav-project-form tabindex="-1" role="dialog" aria-modal="true" aria-labelledby="nav-project-heading" aria-busy="${!!state.busy}"><header><h2 id="nav-project-heading">${title}</h2><button type="button" class="icon-button" data-nav-editor-close aria-label="关闭${title}" ${state.busy ? 'disabled' : ''}>${icon('close')}</button></header><label class="nav-project-name-field" for="nav-project-name">${icon('folder')}<span class="sr-only">项目名称</span><input id="nav-project-name" name="name" value="${e(state.editor.name || '')}" placeholder="项目名称" maxlength="120" required ${state.busy ? 'disabled' : ''}></label>${state.error ? `<p class="notice error" role="alert">${e(state.error)}</p>` : ''}<footer><button type="button" class="text-button" data-nav-editor-close ${state.busy ? 'disabled' : ''}>取消</button><button type="submit" class="button primary" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在保存…' : creating ? '创建项目' : '保存'}</button></footer></form></div>`;
}
