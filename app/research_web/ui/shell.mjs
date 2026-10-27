import { renderConversationNavigation } from './conversation-navigation.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { sessionHash, isRunning } from './core.mjs';
import { renderActivities, renderDatasets, renderDelivery, renderFiles, statusText } from './views.mjs';
import { icon } from './icons.mjs';
import { renderResearchPanel } from './research-report.mjs';
import { renderWorkflowPlan } from './capabilities.mjs';
import { renderAccountTrigger } from './server/account-menu.mjs';
import { canUseReportWorkflows } from './weekly-production.mjs';

const navItems = [
  { page: 'fingpt', glyph: 'chat', title: 'FinGPT', href: '#/fingpt' },
  { page: 'claw', glyph: 'layers', title: 'Claw', href: '#/claw' },
  { page: 'reports', glyph: 'document', title: '报告生产', href: '#/reports' },
  { page: 'market', glyph: 'chart', title: '全市场概览', href: '#/market' },
  { page: 'assets', glyph: 'chart', title: '资产观察', href: '#/assets' },
  { page: 'intel', glyph: 'activity', title: '研究情报', href: '#/intel/overview' },
  { page: 'aihot', glyph: 'activity', title: 'AI 资讯', href: '#/aihot/daily' },
  { page: 'frameworks', glyph: 'grid', title: '研究框架', href: '#/frameworks' },
  { page: 'simulation', glyph: 'chart', title: '策略模拟', href: '#/simulation/etf' },
  { page: 'skills', glyph: 'grid', title: '能力中心', href: '#/skills' },
  { page: 'operations', glyph: 'activity', title: '运行与用量', href: '#/operations' },
];

export function renderBrandMark() {
  return '<span class="brand-mark" aria-hidden="true"><img src="/static/assets/brand/brand-mark.png" alt="" width="108" height="120"></span>';
}

export function renderAppearancePicker() {
  const options = [['system', '跟随系统'], ['light', '浅色'], ['dark', '深色']];
  return `<fieldset class="appearance-picker"><legend>主题</legend><div class="appearance-options">${options.map(([value, label]) => `<label class="appearance-option"><input type="radio" name="appearance-theme" value="${value}" data-theme-option><span class="theme-preview ${value}" aria-hidden="true"><i></i><b></b><em></em></span><span>${label}</span></label>`).join('')}</div></fieldset>`;
}

export function focusSidebarControl(document, narrow = false, open = false) {
  const selector = narrow ? open ? '.rail-mobile-close' : '.topbar .menu-toggle' : open ? '.secondary-sidebar .sidebar-collapse' : '.topbar .sidebar-reopen';
  document.querySelector(selector)?.focus?.({ preventScroll: true });
}

export function renderResearchAttention(detail) {
  const restriction = detail?.history_warning ? `<p class="notice warning" role="status">历史受限：${e(detail.history_warning)}</p>` : '';
  const abnormal = (items) => (Array.isArray(items) ? items : []).filter(item => item?.error || ['failed', 'error'].includes(item?.status)).length;
  const failedActivities = abnormal(detail?.activities);
  const abnormalSubagents = abnormal(detail?.subagents);
  const errors = failedActivities + abnormalSubagents;
  const incomplete = ['incomplete', 'verification_failed'].includes(detail?.delivery?.status);
  const quality = detail?.research_quality;
  const qualityLabels = { passed: '已通过', incomplete: '未通过', invalid: '完整性未通过' };
  const qualitySummary = quality ? `<section class="research-state-summary" aria-label="研究执行与验收状态"><span>执行：${e(statusText(detail.status))}</span><span>质量：${e(qualityLabels[quality.status] || '未确认')}</span><span>文件：${e(({ completed: '已检查', complete: '已检查', not_required: '无需文件', pending: '待检查', validating: '检查中', incomplete: '不完整', verification_failed: '检查失败', admission_unknown: '受理未知' })[detail.delivery?.status] || '未确认')}</span></section>` : '';
  if (!errors && !incomplete && !['incomplete', 'invalid'].includes(quality?.status)) return restriction + qualitySummary;
  const summary = [failedActivities ? `${failedActivities} 项活动失败` : '', abnormalSubagents ? `${abnormalSubagents} 个子 Agent 异常` : ''].filter(Boolean).join('，');
  const canContinue = quality?.status === 'incomplete' && detail.mode === 'fingpt' && !isRunning(detail.status) && !detail.can_cancel && !detail.can_recheck_stop && !detail.execution_restricted;
  return `${restriction}${qualitySummary}<div class="notice warning research-attention" role="status"><span>${summary ? `${summary}。` : ''}${incomplete ? '文件交付尚未完成。' : ''}${quality?.status === 'incomplete' ? '研究存在缺口，可查看现有成果并补充资料。' : quality?.status === 'invalid' ? '报告完整性未通过，导出已暂停。' : ''}</span><button type="button" class="text-button" ${quality ? 'data-context-tab="report"' : 'data-show-attention'}>查看详情</button>${canContinue ? '<button type="button" class="text-button" data-continue-research>补充资料继续研究</button>' : ''}</div>`;
}

export function filterGlobalSearch(query, sessions = [], skills = []) {
  const normalized = String(query || '').trim().toLocaleLowerCase();
  if (!normalized) return [];
  const work = (Array.isArray(sessions) ? sessions : []).filter((session) => `${session?.title || ''} ${session?.mode || ''}`.toLocaleLowerCase().includes(normalized)).map((session) => ({ kind: 'session', item: session }));
  const capabilities = (Array.isArray(skills) ? skills : []).filter((skill) => `${skill?.name || ''} ${skill?.description || ''}`.toLocaleLowerCase().includes(normalized)).map((skill) => ({
    kind: ['tool', 'report-workflow', 'data'].includes(skill.kind) ? skill.kind : 'skill',
    item: skill,
  }));
  return [...work, ...capabilities].slice(0, 8);
}

export function renderGlobalSearch(query, sessions, skills, options = {}) {
  const native = options.native;
  const label = native ? "搜索Claw会话标题、正文和能力" : "搜索会话标题和能力名称或简介";
  return `<div class="global-search"><label class="sr-only" for="global-search">${label}</label>${icon('search')}<input id="global-search" data-global-search type="search" value="${e(query || '')}" placeholder="${native ? "搜索Claw标题、正文或能力…" : "搜索会话标题、能力名称或简介…"}" ${native ? 'maxlength="500"' : ""} autocomplete="off" role="combobox" aria-expanded="${query || native?.mode === 'claw' ? 'true' : 'false'}" aria-controls="global-search-results">` +
    `<div class="global-results" id="global-search-results" role="listbox" aria-label="搜索结果">${renderGlobalResults(query, sessions, skills, options)}</div></div>`;
}

export function renderGlobalResults(query, sessions, skills, { native = null } = {}) {
  const queryText = String(query || '').trim();
  if (!queryText && native?.mode !== 'claw') return '';
  const current = native?.query === queryText && native.mode === 'claw';
  const nativeItems = current ? native.items || [] : [];
  const snippets = new Map(nativeItems.map(item => [item.id, item.snippet]));
  const results = queryText ? filterGlobalSearch(query, native ? (sessions || []).filter(item => item.mode === 'claw') : sessions, skills) : (sessions || []).filter(item => item.mode === 'claw').slice(0, 8).map(item => ({ kind: 'session', item }));
  const known = new Set(results.filter(row => row.kind === 'session').map(row => row.item.id));
  for (const item of nativeItems) if (!known.has(item.id)) { results.push({ kind: 'session', item }); known.add(item.id); }
  const status = current ? `${native.pending ? '<p class="small muted" role="status">正在搜索 Claw 正文…</p>' : ''}${native.error ? `<p class="small muted" role="status">${e(native.error)} <button type="button" class="text-button" data-retry-native-search>重试正文搜索</button></p>` : ''}${!native.pending && native.unavailable_count > 0 ? `<p class="small muted" role="status">部分历史未搜索：${e(native.unavailable_count)} 个会话格式暂不支持或原生不可见；当前结果不代表全部历史。</p>` : ''}${native.has_more ? '<p class="small muted">结果可能不完整，请缩小关键词。</p>' : ''}` : '';
  const heading = !queryText && results.length ? '<p class="small muted">最近 Claw 会话</p>' : '';

  const attribute = (kind, item) => ({ tool: 'data-tool-detail', data: 'data-data-capability-detail', 'report-workflow': 'data-report-workflow-detail' })[kind] || (item.enabled === false ? 'data-skill-detail' : 'data-skill-shortcut');
  if (!results.length) return status || '<p class="muted small">没有匹配的真实会话或能力。</p>';
  return heading + status + results.map(({ kind, item }) => kind === 'session' ? `<a role="option" href="${sessionHash(item)}" data-global-result="session" data-global-result-key="session:${e(item.id)}" data-session-id="${e(item.id)}"><strong>${e(item.title || '未命名会话')}</strong><span>会话 · ${e({ fingpt: 'FinGPT', claw: 'Claw' }[item.mode] || '研究')}</span>${snippets.has(item.id) ? `<span class="native-search-snippet">${e(snippets.get(item.id))}</span>` : ''}</a>` : `<button type="button" role="option" data-global-result="${kind}" data-global-result-key="${kind}:${e(item.id)}" ${attribute(kind, item)}="${e(item.id)}"><strong>${e(item.name)}</strong><span>${e(item.description || '此能力未提供描述。')}</span></button>`).join('');
}

export function renderPrimaryRail({ page, section = '', secondaryOpen = false, account = null } = {}) {
  const primaryPage = page === 'workbench' ? ['market', 'industry', 'documents', 'hot'].includes(section) ? 'intel' : section === 'etf-paper' ? 'simulation' : 'assets' : page;
  const links = navItems.filter(item => item.page !== 'reports' || canUseReportWorkflows(globalThis.__RWB_USER_ID__ || account?.id, account)).map((item) => {
    const active = primaryPage === item.page;
    return `<a href="${item.href}" class="rail-link ${active ? 'active' : ''}" ${active ? 'aria-current="page"' : ''} title="${e(item.title)}"><span class="rail-icon" aria-hidden="true">${icon(item.glyph)}</span><span class="rail-label">${e(item.title)}</span></a>`;
  }).join('');
  const footer = account ? renderAccountTrigger(account) : `<a class="rail-link rail-settings ${page === 'settings' ? 'active' : ''}" href="#/settings/general" title="设置" ${page === 'settings' ? 'aria-current="page"' : ''}><span class="rail-icon" aria-hidden="true">${icon('settings')}</span><span class="rail-label">设置</span></a>`;
  return `<nav class="primary-rail" aria-label="产品主导航"><a class="rail-brand" href="#/fingpt" aria-label="Research Workbench Research">${renderBrandMark()}<span class="brand-name">Research Workbench</span></a><button class="icon-button rail-mobile-close" data-toggle-sidebar aria-label="关闭导航">×</button><button class="search-trigger" data-toggle-search aria-label="搜索会话与能力">${icon('search')}<span>搜索</span></button><div class="primary-nav">${links}</div><div class="navigation-footer">${footer}</div></nav>`;
}

function renderClawWorkspace(detail, workspaces, selectedWorkspace) {
  const datasets = Array.isArray(detail?.datasets) ? detail.datasets : [];
  const files = Array.isArray(detail?.files) ? detail.files : [];
  return `<section class="claw-workspace-view" aria-label="当前 Claw 会话工作区"><p class="muted small">仅显示当前会话的资料与产物；不会读取或混入其他会话。</p><label for="workspace-select">新 Claw 会话的工作空间</label><select id="workspace-select"><option value="">默认工作空间</option>${workspaces.map((workspace) => `<option value="${e(workspace.id)}" ${selectedWorkspace === workspace.id ? 'selected' : ''}>${e(workspace.name)}</option>`).join('')}</select>${detail ? `<div class="workspace-current"><strong>${e(detail.title || '当前 Claw 会话')}</strong><p class="small muted">资料 ${datasets.length} 项 · 文件 ${files.length} 个</p><ul>${datasets.map((dataset) => `<li>资料：${e(dataset?.name || dataset?.id || '未命名资料')}</li>`).join('')}${files.map((file) => `<li>文件：${file?.id ? `<button type="button" class="text-button" data-workspace-preview="${e(file.id)}">${e(file?.name || file.id)}</button>` : e(file?.name || '未命名文件')}</li>`).join('')}${!datasets.length && !files.length ? '<li class="muted">当前会话尚无资料或产物。</li>' : ''}</ul></div>` : '<p class="muted small">打开 Claw 会话后，当前会话的资料和产物会显示在这里。</p>'}</section>`;
}

export function renderClawWorkspaceCanvas({ detail, selectedPreview = null, busy = false } = {}) {
  const datasets = renderDatasets(detail?.id, detail?.datasets) || '<section class="context-section"><h3>研究资料</h3><p class="muted small">当前会话尚无研究资料。</p></section>';
  const files = `<section class="context-section"><div class="section-heading"><h3>文件</h3>${detail ? `<button class="text-button" data-refresh-files ${busy ? 'disabled' : ''}>刷新</button>` : ''}</div>${renderFiles(detail?.files || [], selectedPreview)}</section>`;
  return `<section class="claw-workspace-canvas" aria-label="当前 Claw 会话工作区"><header class="claw-workspace-header"><div><span class="eyebrow">CURRENT CLAW WORKSPACE</span><h2>${e(detail?.title || '当前 Claw 会话')}</h2><p class="muted">只显示当前会话的资料与文件；不会读取或混入其他会话。</p></div></header><div class="claw-workspace-content">${datasets}${files}</div></section>`;
}

const deliveryLabel = (status) => ({ pending: '等待交付', validating: '交付校验中', complete: '交付完整', incomplete: '交付不完整' })[status] || (status ? `交付：${status}` : '交付状态未知');

export function renderLockedWorkflowSummary(detail) {
  if (detail?.mode !== 'claw') return '';
  const locked = detail.report_workflow || (detail.capability?.kind === 'workflow' ? detail.capability : null);
  if (!locked?.workflow_id && !locked?.id) return '';
  const id = locked.workflow_id || locked.id;
  const name = locked.name || detail.capability?.name || id;
  const version = locked.version || detail.capability?.version;
  const delivery = locked.delivery_status || detail.delivery?.status;
  return `<section class="locked-workflow-summary" aria-label="锁定 Workflow 只读摘要"><div><span class="eyebrow">锁定 Workflow · 只读摘要</span><strong>${e(name)}</strong><span class="mono">${e(id)}${version ? ` · v${e(version)}` : ''}</span></div><span class="badge ${delivery === 'complete' ? 'live' : delivery === 'incomplete' ? 'danger' : ''}">${e(deliveryLabel(delivery))}</span><p class="muted small">步骤执行证据以活动记录为准；文件是否完成以独立交付校验为准。</p></section>`;
}

export function renderSessionRow(session, currentSessionId = null, openMenuId = null) {
  const active = currentSessionId === session.id;
  const busy = ['running', 'busy'].includes(session.status);
  const title = session.title || '未命名会话';
  const status = session.waitingForAnswer ? 'waiting_input' : session.status;
  const statusLabel = statusText(status);
  const glyph = status === 'waiting_input' || ['waiting_approval', 'awaiting_approval'].includes(status) ? 'question' : busy ? 'spinner' : status === 'completed' ? 'completedCircle' : ['failed', 'cancelled', 'interrupted'].includes(status) ? 'close' : 'history';
  const statusMarker = status === 'completed' && session.completionSeen ? '' : `<span class="session-row-status ${busy && status !== 'waiting_input' ? 'is-executing' : ''}" role="status" aria-label="${e(statusLabel)}" title="${e(statusLabel)}">${icon(glyph)}</span>`;
  return `<div class="session-row ${active ? 'active' : ''} ${openMenuId === session.id ? 'menu-open' : ''}"><a href="${sessionHash(session)}" class="recent-item ${active ? 'active' : ''}" title="${e(title)}${statusLabel ? ` · ${statusLabel}` : ''}" ${active ? 'aria-current="page"' : ''}><span class="session-row-title">${e(title)}</span>${statusMarker}</a><button type="button" class="session-actions-trigger" data-session-menu="${e(session.id)}" aria-label="${e(title)}的更多操作" aria-haspopup="menu" aria-expanded="${openMenuId === session.id}">${icon('more')}</button>${session.history_warning ? `<span class="session-history-warning small" role="status">历史受限：${e(session.history_warning)}</span>` : ''}</div>`;
}

export function renderSidebar(options = {}) {
  return renderConversationNavigation({ ...options, renderSessionRow });
}

export function renderContextPanel({ detail, selectedTab = 'activity', mobileOpen = false, selectedPreview = null, busy = false, workflow = null, researchStage = null } = {}) {
  if (!detail) return '';
  const tabs = [['activity', '活动'], ['plan', '计划'], ['evidence', '证据'], ['notes', '笔记'], ['report', '报告'], ['datasets', '资料'], ['files', '文件']];
  const panel = ['plan', 'evidence', 'notes', 'report'].includes(selectedTab) ? renderResearchPanel(detail, selectedTab, researchStage) : selectedTab === 'datasets' ? renderDatasets(detail?.id, detail?.datasets) || '<p class="muted small context-empty">本会话暂无研究资料。</p>' : selectedTab === 'files' ? `<section class="context-section"><div class="section-heading"><h3>文件</h3>${detail ? `<button class="text-button" data-refresh-files ${busy ? 'disabled' : ''}>刷新</button>` : ''}</div>${renderFiles(detail?.files || [], selectedPreview, { blockReportExports: detail.research_quality?.status === 'invalid' })}</section>` : `${renderLockedWorkflowSummary(detail)}${renderDelivery(detail?.delivery)}${renderWorkflowPlan(workflow || detail.capability)}${renderActivities(detail)}`;
  return `<aside class="context-panel ${mobileOpen ? 'mobile-open' : ''}" aria-label="研究活动、资料与文件"><header class="context-header"><div><h2>研究空间</h2><span class="badge">${detail?.mode === 'claw' ? 'CLAW' : 'FINGPT'}</span></div><button class="icon-button context-close" data-toggle-context aria-label="关闭研究空间">×</button></header><div class="context-tabs" role="tablist">${tabs.map(([id, label]) => `<button type="button" role="tab" class="context-tab ${selectedTab === id ? 'active' : ''}" aria-selected="${selectedTab === id}" data-context-tab="${id}">${label}</button>`).join('')}</div><div class="context-tab-panel">${panel}</div></aside>`;
}

export function renderTopbar({ page = 'fingpt', section = '', frameworkSlug = '', settingsSection = '', detail = null, runtimeLabel, runtime, search = '', sessions = [], skills = [], searchOpen = false, nativeSearch = null } = {}) {
  const sidebarReopen = ['fingpt', 'claw'].includes(page) ? `<button type="button" class="icon-button sidebar-reopen" data-toggle-sidebar aria-label="打开会话侧栏" aria-expanded="false">${icon('sidebar')}</button>` : '';
  let runtimeAttention = '';
  if (runtime && (!runtime.connected || runtime.credential_configured === false)) {
    const [label, tone] = runtime.connected
      ? ['需要配置模型', 'warning']
      : runtime.health_check_passed
        ? ['研究服务连接中', 'warning']
        : ['研究服务不可用', 'danger'];
    runtimeAttention = `<div class="topbar-right"><a href="#/settings/model" class="runtime-status ${tone}" title="${e(runtime.message || runtimeLabel || label)}"><span class="tiny-dot" aria-hidden="true"></span>${label}</a></div>`;
  }
  return `<header class="topbar ${searchOpen ? 'search-open' : ''}">${sidebarReopen}<button class="icon-button menu-toggle" data-toggle-sidebar aria-label="打开导航">${icon('sidebar')}</button><div class="search-popover" role="dialog" aria-label="搜索会话与能力" ${searchOpen ? '' : 'hidden'}><button type="button" class="icon-button search-close" data-close-search aria-label="关闭搜索">${icon('close')}</button>${renderGlobalSearch(search, sessions, skills, { native: nativeSearch })}</div>${runtimeAttention}</header>`;
}
