import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { empty } from './views.mjs';
import { capabilityStatus, reportWorkflowEligibility } from './capabilities.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const views = ['library', 'mine', 'plans', 'connections'];
const kinds = ['all', 'skill', 'workflow', 'tool', 'data'];
const kindLabels = { all: '全部类型', skill: 'Skill', workflow: 'Workflow', tool: 'Tool', data: '数据能力' };
const viewLabels = { library: '能力库', mine: '我的能力', plans: '运行计划', connections: '连接与工具' };
const statusLabels = {
  enabled: '已启用', disabled: '已停用', draft: '草稿', invalid: '检查未通过', blocked_dependencies: '依赖不足',
  callable: '可调用', unavailable: '不可调用', internal: '内部控制', scheduled: '已排期', manual: '仅手动',
};

const normalizeText = (value) => String(value || '').trim().toLocaleLowerCase();
const join = (values, fallback = '未声明') => e(list(values).join('、') || fallback);
const attrKey = (kind, id) => `${kind}:${id}`;

export function capabilityWorkspaceViewKey(key, current = 'library') {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return { handled: false };
  const index = Math.max(0, views.indexOf(current));
  const next = key === 'Home' ? 0 : key === 'End' ? views.length - 1 : (index + (key === 'ArrowRight' ? 1 : -1) + views.length) % views.length;
  return { handled: true, view: views[next] };
}

export function capabilityWorkspaceHash(view = 'library', kind = 'all') {
  const safeView = views.includes(view) ? view : 'library';
  const params = new URLSearchParams({ view: safeView });
  if (kinds.includes(kind) && kind !== 'all') params.set('kind', kind);
  return `#/skills?${params.toString()}`;
}

function capabilityEntry(item) {
  const eligibility = reportWorkflowEligibility(item);
  const available = eligibility.report ? eligibility.eligible : Boolean(item.enabled && item.version);
  return {
    raw: item, id: item.id, kind: item.kind, name: item.name, description: item.description || '', category: item.category || '未分类',
    source: item.builtin ? '内置' : '我的', sourceKey: item.builtin ? 'builtin' : 'mine', status: item.status || (available ? 'enabled' : 'disabled'),
    statusLabel: capabilityStatus(item.status), available, version: item.version || null, formats: list(item.metadata?.default_formats),
    scenarios: list(item.metadata?.scenarios), inputs: list(item.metadata?.inputs), tools: list(item.metadata?.required_tools),
    dependencies: list(item.metadata?.dependencies), reason: eligibility.reason || (!item.version ? '尚未发布可调用版本' : item.enabled ? '' : '能力已停用'),
  };
}

function toolEntry(item) {
  const available = item.selectable === true;
  return {
    raw: item, id: item.id, kind: 'tool', name: item.name, description: item.description || '', category: item.category || '研究工具',
    source: item.source || '本机工具目录', sourceKey: 'builtin', status: available ? 'callable' : 'internal',
    statusLabel: available ? '可加入草稿' : 'Agent 内部控制', available, version: item.version || null, formats: [], scenarios: list(item.conditions),
    inputs: [], tools: [], dependencies: [], reason: available ? '' : '该工具由 Agent 内部控制，不能单独加入研究草稿',
  };
}

function dataEntry(item) {
  const available = Number(item.callable_source_count) > 0 && Boolean(item.tool_id);
  return {
    raw: item, id: item.id, kind: 'data', name: item.name, description: item.description || '', category: item.category || '数据',
    source: `${Number(item.source_count) || 0} 个候选来源`, sourceKey: 'builtin', status: available ? 'callable' : 'unavailable',
    statusLabel: available ? '当前可调用' : '暂无可调用来源', available, version: null, formats: [], scenarios: list(item.markets),
    inputs: list(item.parameters), tools: item.tool_id ? [item.tool_id] : [], dependencies: [], reason: available ? '' : '没有完成适配且满足配置的来源',
  };
}

export function collectCapabilityWorkspaceEntries({ capabilities = [], tools = [], dataCatalog = {} } = {}) {
  return [
    ...list(capabilities).filter(item => ['skill', 'workflow'].includes(item.kind)).map(capabilityEntry),
    ...list(tools).map(toolEntry),
    ...list(dataCatalog.capabilities).map(dataEntry),
  ];
}

export function filterCapabilityWorkspaceEntries(entries = [], { view = 'library', kind = 'all', source = 'all', category = '', status = 'all', query = '' } = {}) {
  const q = normalizeText(query);
  return list(entries).filter((item) => {
    if (view === 'mine' && (item.sourceKey !== 'mine' || !['skill', 'workflow'].includes(item.kind))) return false;
    return (kind === 'all' || item.kind === kind)
      && (source === 'all' || item.sourceKey === source)
      && (!category || item.category === category)
      && (status === 'all' || (status === 'available' ? item.available : !item.available))
      && (!q || normalizeText(`${item.name} ${item.description} ${item.category} ${item.source} ${item.id}`).includes(q));
  });
}

function workspaceNav(view) {
  return `<nav class="capability-workspace-nav" role="tablist" aria-label="能力工作区视图">${views.map(value => `<a id="capability-view-${value}" role="tab" tabindex="${view === value ? '0' : '-1'}" aria-selected="${view === value}" aria-controls="capability-workspace-panel" href="${capabilityWorkspaceHash(value)}" data-cap-view="${value}">${viewLabels[value]}</a>`).join('')}</nav>`;
}

function filters(entries, state) {
  const categories = [...new Set(entries.map(item => item.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  return `<div class="capability-workspace-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索能力" value="${e(state.query)}" placeholder="搜索名称、简介或技术 ID"></label><label><span>类型</span><select data-cap-kind-filter>${kinds.map(value => `<option value="${value}" ${state.kind === value ? 'selected' : ''}>${kindLabels[value]}</option>`).join('')}</select></label>${state.view === 'library' ? `<label><span>来源</span><select data-cap-source><option value="all" ${state.source === 'all' ? 'selected' : ''}>全部来源</option><option value="builtin" ${state.source === 'builtin' ? 'selected' : ''}>内置</option><option value="mine" ${state.source === 'mine' ? 'selected' : ''}>我的</option></select></label>` : ''}<label><span>分类</span><select data-cap-category><option value="">全部分类</option>${categories.map(value => `<option value="${e(value)}" ${state.category === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label><label><span>状态</span><select data-cap-status><option value="all" ${state.status === 'all' ? 'selected' : ''}>全部状态</option><option value="available" ${state.status === 'available' ? 'selected' : ''}>可调用</option><option value="unavailable" ${state.status === 'unavailable' ? 'selected' : ''}>不可调用</option></select></label></div>`;
}

function detailAttribute(item) {
  if (item.kind === 'tool') return `data-tool-detail="${e(item.id)}"`;
  if (item.kind === 'data') return `data-data-capability-detail="${e(item.id)}"`;
  return `data-skill-detail="${e(item.id)}"`;
}

function useAttribute(item) {
  if (item.kind === 'tool') return `data-use-tool="${e(item.id)}"`;
  if (item.kind === 'data') return `data-use-data-tool="${e(item.raw.tool_id || '')}"`;
  return `data-use-skill="${e(item.id)}"`;
}

function entryIcon(item) {
  if (item.kind === 'tool') return 'grid';
  if (item.kind === 'workflow') return 'layers';
  if (item.kind === 'data') return 'database';
  return ({ 'company-research': 'company', 'industry-research': 'industry', 'fund-evaluation': 'chart' })[item.id] || 'document';
}

function capabilityCard(item, busy) {
  return `<article class="capability-workspace-card"><header><span class="skill-icon">${icon(entryIcon(item))}</span><div><span class="eyebrow">${e(kindLabels[item.kind])} · ${e(item.source)}</span><h2>${e(item.name)}</h2></div></header><p>${e(item.description || '尚未提供简介')}</p><div class="capability-card-meta"><span>${e(item.category)}</span>${item.version ? `<span>v${e(item.version)}</span>` : ''}${item.formats.length ? `<span>${join(item.formats)}</span>` : ''}</div><footer><span class="badge ${item.available ? 'live' : ['invalid', 'blocked_dependencies'].includes(item.status) ? 'danger' : ''}">${e(item.statusLabel || statusLabels[item.status] || '状态未知')}</span><div class="button-row"><button type="button" class="button small" ${detailAttribute(item)} data-cap-preview-trigger="${e(attrKey(item.kind, item.id))}" ${busy ? 'disabled' : ''}>快览</button><button type="button" class="button small primary" ${useAttribute(item)} ${busy || !item.available ? 'disabled' : ''}>立即使用</button></div></footer></article>`;
}

function catalogView(entries, state, busy, error) {
  const results = filterCapabilityWorkspaceEntries(entries, state);
  const heading = state.view === 'mine'
    ? ['我的能力', '集中管理你创建、复制和导入的 Skill 与 Workflow。']
    : ['能力库', '统一浏览本机已审查的 Skill、Workflow、Tool 与数据能力。'];
  const actions = state.view === 'mine' ? `<div class="button-row capability-create-actions"><button type="button" class="button primary" data-cap-create="conversation" ${busy ? 'disabled' : ''}>对话创建</button><button type="button" class="button" data-cap-create="manual" ${busy ? 'disabled' : ''}>手动新建</button><button type="button" class="button" data-cap-import ${busy ? 'disabled' : ''}>导入</button><input id="cap-import-file" type="file" accept=".md,.zip" hidden></div>` : '';
  return `<div class="capability-view-heading"><div><span class="eyebrow">${state.view === 'mine' ? 'OWNED CAPABILITIES' : 'LOCAL CATALOG'}</span><h2>${heading[0]}</h2><p class="muted">${heading[1]}</p></div>${actions}</div>${filters(entries, state)}${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}<p class="capability-result-count" role="status">${results.length} 项真实目录记录</p>${results.length ? `<div class="capability-workspace-grid">${results.map(item => capabilityCard(item, busy)).join('')}</div>` : empty('没有匹配的能力', '调整搜索或筛选；目录不会补充演示内容。')}`;
}

function runLabel(status) {
  return ({ queued: '排队中', preparing_data: '准备资料', blocked_data: '数据阻塞', blocked_approval: '等待审批', running: 'Claw 执行中', validating: '校验交付', completed: '已完成', delivery_incomplete: '交付不完整', failed: '失败', cancelled: '已取消', skipped_overlap: '重叠跳过' })[status] || status || '尚未运行';
}

function formatTime(value) {
  if (!value) return '未安排';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function plansView(items, busy) {
  const rows = list(items);
  return `<div class="capability-view-heading"><div><span class="eyebrow">EXISTING REPORT SCHEDULES</span><h2>运行计划</h2><p class="muted">首期聚合现有报告 Workflow 日程、最近运行和下一次执行。</p></div></div>${rows.length ? `<div class="capability-plan-list">${rows.map(item => `<article><header><div><span class="eyebrow">REPORT WORKFLOW</span><h3>${e(item.name)}</h3></div><span class="badge ${item.next_run_at ? 'live' : ''}">${item.next_run_at ? '已排期' : '仅手动'}</span></header><p>${e(item.description || '未提供说明')}</p><dl><div><dt>锁定版本</dt><dd>${item.current_version ? `v${e(item.current_version)}` : '未发布'}</dd></div><div><dt>下次执行</dt><dd>${e(formatTime(item.next_run_at))}</dd></div><div><dt>最近运行</dt><dd>${e(runLabel(item.latest_run?.status))}</dd></div><div><dt>交付格式</dt><dd>${join(item.delivery_formats)}</dd></div></dl><div class="button-row"><button type="button" class="button small" data-report-workflow-detail="${e(item.id)}" ${busy ? 'disabled' : ''}>管理计划</button><button type="button" class="button small primary" data-run-report-workflow="${e(item.id)}" ${busy || item.status !== 'enabled' || !item.current_version ? 'disabled' : ''}>立即运行</button></div></article>`).join('')}</div>` : empty('暂无运行计划', '导入并发布报告 Workflow 后，可在这里查看它的现有日程。')}`;
}

function connectionState(source) {
  if (source.callable === true) return ['可调用', 'live'];
  if (source.integration_completed !== true) return ['尚未适配', ''];
  if (source.configured !== true && !['none', 'local', 'terminal'].includes(source.auth_type || source.auth_kind)) return ['待配置', ''];
  return ['待检测', ''];
}

function connectionsView(connections, tools) {
  const sources = list(connections?.sources);
  return `<div class="capability-view-heading"><div><span class="eyebrow">LOCAL CONNECTIONS</span><h2>连接与工具</h2><p class="muted">查看当前数据源、本机集成与 Tool 状态；凭据配置继续在设置中完成。</p></div><a class="button" href="#/settings/data">打开连接设置</a></div><section class="connection-tool-summary" aria-label="连接与工具汇总"><div><strong>${sources.length}</strong><span>数据源</span></div><div><strong>${sources.filter(item => item.callable === true).length}</strong><span>可调用来源</span></div><div><strong>${list(tools).length}</strong><span>Tool 声明</span></div><div><strong>${list(tools).filter(item => item.selectable === true).length}</strong><span>可加入草稿</span></div></section><div class="connection-tool-sections"><section><div class="section-heading"><div><h3>数据源与本机集成</h3><p class="muted small">状态来自当前服务设备。</p></div></div>${sources.length ? `<div class="connection-tool-list">${sources.map(source => { const [label, tone] = connectionState(source); const section = source.group === 'local' ? 'local' : 'data'; return `<article><div><strong>${e(source.name || source.label || source.id)}</strong><small>${e(source.description || source.id)}</small></div><span class="badge ${tone}">${e(label)}</span><a class="button small" href="#/settings/${section}?connection=${encodeURIComponent(source.id)}">配置</a></article>`; }).join('')}</div>` : empty('没有连接记录', '刷新目录后仍为空时，请检查连接服务。')}</section><section><div class="section-heading"><div><h3>研究 Tool</h3><p class="muted small">安装、启用与会话授权仍是独立状态。</p></div></div>${list(tools).length ? `<div class="connection-tool-list">${list(tools).map(tool => `<article><div><strong>${e(tool.name)}</strong><small>${e(tool.description || tool.id)}</small></div><span class="badge ${tool.selectable ? 'live' : ''}">${tool.selectable ? '可加入草稿' : '内部控制'}</span><button type="button" class="button small" data-tool-detail="${e(tool.id)}" data-cap-preview-trigger="${e(attrKey('tool', tool.id))}">快览</button></article>`).join('')}</div>` : empty('没有 Tool 声明', '刷新目录后仍为空时，请检查工具目录。')}</section></div>`;
}

export function renderCapabilityWorkspace({ capabilities = [], tools = [], reportWorkflows = [], dataCatalog = {}, connections = {}, view = 'library', kind = 'all', source = 'all', category = '', status = 'all', query = '', busy = false, error = '' } = {}) {
  const safeView = views.includes(view) ? view : 'library';
  const entries = collectCapabilityWorkspaceEntries({ capabilities, tools, dataCatalog });
  const body = safeView === 'plans' ? plansView(reportWorkflows, busy) : safeView === 'connections' ? connectionsView(connections, tools) : catalogView(entries, { view: safeView, kind: kinds.includes(kind) ? kind : 'all', source, category, status, query }, busy, error);
  return `<section class="capability-workspace"><header class="capability-workspace-header"><div><span class="eyebrow">CAPABILITY WORKSPACE · V0</span><h1>能力工作区</h1><p class="muted">发现、管理并准备研究能力；任何执行都需要你的明确确认。</p></div><button type="button" class="button" data-cap-refresh ${busy ? 'disabled' : ''}>刷新状态</button></header>${workspaceNav(safeView)}<div id="capability-workspace-panel" role="tabpanel" aria-labelledby="capability-view-${safeView}" tabindex="0">${body}</div></section>`;
}

function previewFromState({ detail, tool, dataDetail, dataDetailKind }) {
  if (detail) return capabilityEntry(detail);
  if (tool) return toolEntry(tool);
  if (dataDetail && dataDetailKind === 'capability') return dataEntry(dataDetail);
  return null;
}

export function renderCapabilityPreviewDialog(state = {}) {
  const item = previewFromState(state);
  if (!item) return '';
  const inputText = item.inputs.map(input => `${input.label || input.name || '参数'}（${input.type || '参数'}${input.required ? ' · 必填' : ''}）`);
  return `<div class="capability-dialog-backdrop" data-capability-dialog-backdrop><section class="capability-preview-dialog" role="dialog" aria-modal="true" aria-labelledby="capability-preview-title" aria-describedby="capability-preview-description"><header><span class="skill-icon">${icon(entryIcon(item))}</span><div><span class="eyebrow">${e(kindLabels[item.kind])} · ${e(item.source)}</span><h2 id="capability-preview-title">${e(item.name)}</h2><span class="badge ${item.available ? 'live' : 'danger'}">${e(item.statusLabel)}</span></div><button type="button" class="icon-button" data-cap-close aria-label="关闭能力快览">×</button></header><p id="capability-preview-description" class="capability-preview-description">${e(item.description || '尚未提供简介')}</p><dl class="capability-preview-grid"><div><dt>适用场景</dt><dd>${join(item.scenarios)}</dd></div><div><dt>输入</dt><dd>${join(inputText)}</dd></div><div><dt>输出</dt><dd>${join(item.formats, item.kind === 'data' ? '结构化数据' : '无需文件')}</dd></div><div><dt>所需工具</dt><dd>${join(item.tools, '无显式工具要求')}</dd></div><div><dt>依赖</dt><dd>${join(item.dependencies, '无额外依赖')}</dd></div><div><dt>状态说明</dt><dd>${e(item.reason || '当前目录状态允许加入研究草稿')}</dd></div></dl><footer><button type="button" class="button" data-cap-close>取消</button>${['skill', 'workflow'].includes(item.kind) ? `<button type="button" class="button" data-cap-manage="${e(item.id)}">进入管理</button>` : ''}<button type="button" class="button primary" ${useAttribute(item)} ${state.busy || !item.available ? 'disabled' : ''}>立即使用</button></footer></section></div>`;
}
