import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { renderCapabilityEditor, renderCreationForm, renderCopyForm } from './capability-editor.mjs';
import { empty } from './views.mjs';
import { capabilityStatus, reportWorkflowEligibility, renderCapabilityDetail, renderToolDetail } from './capabilities.mjs';
import { renderDataCatalog, renderDataCapabilityDetail, renderDataSourceDetail } from './data-catalog.mjs';
import { renderMCPMarketplace, renderMCPServerDialog } from './mcp-marketplace.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const views = ['library', 'mine', 'plans', 'connections', 'market'];
const kinds = ['skill', 'connector', 'plugin'];
const kindLabels = { skill: '技能', connector: '连接器', plugin: '插件', method: '研究方法', workflow: '步骤模板', tool: '工具', data: '数据能力' };
const primaryKind = kind => ['method', 'workflow'].includes(kind) ? 'skill' : ['tool', 'data'].includes(kind) ? 'connector' : kinds.includes(kind) ? kind : 'skill';
const subviews = {
  skill: [['library', '全部技能'], ['mine', '我的技能']],
  connector: [['library', '全部连接器'], ['market', '添加 MCP'], ['connections', '连接状态']],
  plugin: [],
};
const statusLabels = {
  enabled: '已启用', disabled: '已停用', draft: '草稿', invalid: '检查未通过', blocked_dependencies: '依赖不足',
  callable: '可调用', unavailable: '不可调用', internal: '内部控制', scheduled: '已排期', manual: '仅手动',
};

const normalizeText = (value) => String(value || '').trim().toLocaleLowerCase();
const join = (values, fallback = '未声明') => e(list(values).join('、') || fallback);
const attrKey = (kind, id) => `${kind}:${id}`;

export function capabilityWorkspaceKindKey(key, current = 'skill') {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return { handled: false };
  const index = Math.max(0, kinds.indexOf(primaryKind(current)));
  const next = key === 'Home' ? 0 : key === 'End' ? kinds.length - 1 : (index + (key === 'ArrowRight' ? 1 : -1) + kinds.length) % kinds.length;
  return { handled: true, kind: kinds[next] };
}

export function capabilityWorkspaceHash(kind = 'skill', view = 'library') {
  const safeKind = primaryKind(kind);
  const allowedViews = [...subviews[safeKind].map(([value]) => value), ...(safeKind === 'skill' ? ['plans'] : [])];
  const safeView = views.includes(view) && allowedViews.includes(view) ? view : 'library';
  const params = new URLSearchParams({ kind: safeKind });
  if (kind !== safeKind && ['method', 'workflow', 'tool', 'data'].includes(kind)) params.set('kind', kind);
  if (safeView !== 'library') params.set('view', safeView);
  return `#/skills?${params.toString()}`;
}

function capabilityEntry(item) {
  const eligibility = reportWorkflowEligibility(item);
  const available = eligibility.report ? eligibility.eligible : Boolean(item.enabled && item.version);
  return {
    raw: item, id: item.id, kind: item.kind, name: item.name, description: item.description || '', category: item.category || '未分类',
    source: item.builtin ? '内置' : '我的', sourceKey: item.builtin ? 'builtin' : 'mine', status: item.status || (available ? 'enabled' : 'disabled'),
    statusLabel: capabilityStatus(item.status || (available ? 'enabled' : 'disabled')), available, version: item.version || null, formats: list(item.metadata?.default_formats),
    scenarios: list(item.metadata?.scenarios), inputs: list(item.metadata?.inputs), tools: list(item.metadata?.required_tools),
    dependencies: list(item.metadata?.dependencies), linkedCapabilities: list(item.linked_capabilities), reason: eligibility.reason || (!item.version ? '尚未发布可调用版本' : item.enabled ? '' : '能力已停用'),
  };
}

function toolEntry(item) {
  const available = item.selectable === true;
  const authorization = list(item.conditions).join('；') || item.approval || '未声明授权条件';
  return {
    raw: item, id: item.id, kind: 'tool', name: item.name, description: item.description || '', category: item.category || '研究工具',
    source: item.source || '本机工具目录', sourceKey: 'builtin', status: available ? 'callable' : 'internal',
    statusLabel: available ? '可加入草稿' : 'Agent 内部控制', available, version: item.version || null, formats: [], scenarios: list(item.conditions),
    inputs: [], tools: [], dependencies: [], reason: available ? `授权条件：${authorization}` : `授权条件：${authorization}；该工具由 Agent 内部控制，不能单独加入研究草稿`,
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
  const linked = new Map();
  for (const capability of list(capabilities).filter(item => ['skill', 'workflow'].includes(item.kind))) {
    const policy = capability.metadata?.method_policy || {};
    for (const [source, ids] of [['required', policy.required], ['recommended', policy.recommended]]) {
      for (const methodId of list(ids)) linked.set(methodId, [...(linked.get(methodId) || []), { id: capability.id, name: capability.name, source }]);
    }
  }
  return [
    ...list(capabilities).filter(item => ['skill', 'method', 'workflow'].includes(item.kind)).map(item => capabilityEntry(item.kind === 'method' ? { ...item, linked_capabilities: linked.get(item.id) || [] } : item)),
    ...list(tools).map(toolEntry),
    ...list(dataCatalog.capabilities).map(dataEntry),
  ];
}

export function filterCapabilityWorkspaceEntries(entries = [], { view = 'library', kind = 'skill', source = 'all', category = '', status = 'all', query = '' } = {}) {
  const q = normalizeText(query);
  return list(entries).filter((item) => {
    if (view === 'mine' && (item.sourceKey !== 'mine' || !['skill', 'workflow'].includes(item.kind))) return false;
    return (primaryKind(kind) === 'skill' ? ['skill', 'workflow', 'method'].includes(item.kind) : item.kind === kind)
      && (source === 'all' || item.sourceKey === source)
      && (!category || item.category === category)
      && (status === 'all' || (status === 'published' ? Boolean(item.version) : status === 'available' ? item.available : !item.available))
      && (!q || normalizeText(`${item.name} ${item.description} ${item.category} ${item.source} ${item.id}`).includes(q));
  });
}

function workspaceKindNav(kind) {
  return `<nav class="capability-workspace-nav" role="tablist" aria-label="能力类型">${kinds.map(value => `<a id="capability-kind-${value}" role="tab" tabindex="${kind === value ? '0' : '-1'}" aria-selected="${kind === value}" aria-controls="capability-workspace-panel" href="${capabilityWorkspaceHash(value)}" data-cap-kind-nav="${value}">${kindLabels[value]}</a>`).join('')}</nav>`;
}

function workspaceSubviewNav(kind, view) {
  const roving = kind === 'connector';
  return `<nav class="capability-workspace-subnav" ${roving ? 'role="tablist"' : ''} aria-label="${kindLabels[kind]} 视图">${subviews[kind].map(([value, label]) => `<a ${roving ? `id="capability-tool-tab-${value}"` : ''} href="${capabilityWorkspaceHash(kind, value)}" aria-current="${view === value ? 'page' : 'false'}" ${roving ? `role="tab" tabindex="${view === value ? '0' : '-1'}" aria-selected="${view === value}" data-mcp-market-tab="${value}"` : ''}>${label}</a>`).join('')}</nav>`;
}

function filters(entries, state) {
  const categories = [...new Set(entries.map(item => item.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  if (state.kind === 'tool') {
    return `<div class="capability-workspace-filters tool-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索 Tool" value="${e(state.query)}" placeholder="搜索名称、简介或技术 ID"></label></div>`;
  }
  const source = ['skill', 'workflow'].includes(state.kind) && state.view === 'library' ? `<label><span>来源</span><select data-cap-source><option value="all" ${state.source === 'all' ? 'selected' : ''}>全部来源</option><option value="builtin" ${state.source === 'builtin' ? 'selected' : ''}>内置</option><option value="mine" ${state.source === 'mine' ? 'selected' : ''}>我的</option></select></label>` : '';
  return `<div class="capability-workspace-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索 ${kindLabels[state.kind]}" value="${e(state.query)}" placeholder="搜索名称、简介或技术 ID"></label>${source}<label><span>分类</span><select data-cap-category><option value="">全部分类</option>${categories.map(value => `<option value="${e(value)}" ${state.category === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label><label><span>状态</span><select data-cap-status><option value="all" ${state.status === 'all' ? 'selected' : ''}>全部状态</option><option value="published" ${state.status === 'published' ? 'selected' : ''}>已有发布版本</option><option value="available" ${state.status === 'available' ? 'selected' : ''}>可加入草稿</option><option value="unavailable" ${state.status === 'unavailable' ? 'selected' : ''}>暂不可选</option></select></label></div>`;
}

function detailAttribute(item) {
  if (item.kind === 'tool') return `data-tool-detail="${e(item.id)}"`;
  if (item.kind === 'data') return `data-data-capability-detail="${e(item.id)}"`;
  return `data-skill-detail="${e(item.id)}"`;
}

function useAttribute(item) {
  if (item.kind === 'tool') return `data-use-tool="${e(item.id)}"`;
  if (item.kind === 'data') return `data-use-data-tool="${e(item.raw.tool_id || '')}"`;
  if (item.kind === 'method') return `data-use-method="${e(item.id)}"`;
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
  const owned = state.view === 'mine';
  const typeName = kindLabels[state.kind];
  const heading = owned
    ? [`我的 ${typeName}`, `集中管理你创建、复制和导入的 ${typeName}。`]
    : [state.kind === 'tool' ? '工具目录' : state.kind === 'method' ? '方法能力库' : `${typeName} 能力库`, state.kind === 'tool' ? '只展示本机真实 Tool 声明、调用状态和授权原因，不与其他能力类型混排。' : '统一浏览技能、步骤模板与研究方法；选择后放入研究草稿。'];
  const actions = ['skill', 'workflow'].includes(state.kind) ? `<div class="button-row capability-create-actions"><button type="button" class="button primary" data-cap-create="conversation" ${busy ? 'disabled' : ''}>对话创建</button><button type="button" class="button" data-cap-create="manual" ${busy ? 'disabled' : ''}>手动新建</button><button type="button" class="button" data-cap-import ${busy ? 'disabled' : ''}>导入 ${typeName}</button><input id="cap-import-file" type="file" accept=".md,.zip" hidden></div>` : '';
  const scopedEntries = entries.filter(item => primaryKind(item.kind) === state.kind);
  return `<div class="capability-view-heading"><div><span class="eyebrow">${owned ? 'OWNED CAPABILITIES' : 'LOCAL CATALOG'}</span><h2>${heading[0]}</h2><p class="muted">${heading[1]}</p></div>${actions}</div>${filters(scopedEntries, state)}${error ? `<p class="notice error" role="alert">${e(error)}</p>` : ''}<p class="capability-result-count" role="status">${results.length} 项真实目录记录</p>${results.length ? `<div class="capability-workspace-grid">${results.map(item => capabilityCard(item, busy)).join('')}</div>` : empty(`没有匹配的 ${typeName}`, '调整搜索或筛选；目录不会补充演示内容。')}`;
}

function runLabel(status) {
  return ({ queued: '排队中', preparing_data: '准备资料', blocked_data: '数据阻塞', blocked_approval: '等待审批', running: 'Claw 执行中', validating: '校验交付', completed: '已完成', delivery_incomplete: '交付不完整', failed: '失败', cancelled: '已取消', skipped_overlap: '重叠跳过' })[status] || status || '尚未运行';
}

function formatTime(value) {
  if (!value) return '未安排';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date);
}

function automationForm(capabilities, reportWorkflows, deliveryChannels, busy) {
  const targets = [
    ...list(capabilities).filter(item => ['skill', 'workflow'].includes(item.kind) && item.enabled && item.version).map(item => ({ kind: item.kind, id: item.id, version: item.version, name: item.name })),
    ...list(reportWorkflows).filter(item => item.status === 'enabled' && item.current_version).map(item => ({ kind: 'report_workflow', id: item.id, version: item.current_version, name: item.name })),
  ];
  const channelOptions = list(deliveryChannels)
    .filter(item => item.enabled)
    .map(item => `<option value="${e(item.id)}">${e(item.name)} · ${e(item.kind)}</option>`)
    .join('');
  return `<form class="automation-form" data-automation-form><div class="section-heading"><div><span class="eyebrow">VERSION-LOCKED</span><h3>新建 Automation</h3><p class="muted small">创建时锁定当前版本与内容哈希；保存后默认停用。</p></div><button type="button" class="icon-button" data-close-automation-form aria-label="关闭新建计划">×</button></div><div class="automation-form-grid"><label><span>任务名称</span><input name="name" required maxlength="160"></label><label><span>锁定能力</span><select name="target" required>${targets.map(item => `<option value="${e(`${item.kind}|${item.id}|${item.version}`)}">${e(item.name)} · v${e(item.version)}</option>`).join('')}</select></label><label><span>日程</span><select name="schedule_kind"><option value="daily">每日</option><option value="weekly">每周</option><option value="monthly">每月</option><option value="once">仅一次</option></select></label><label><span>IANA 时区</span><input name="timezone" value="Asia/Shanghai" required></label><label><span>时间</span><input name="time" type="time" value="09:00" required></label><label><span>周几（0=周一）</span><input name="weekday" type="number" min="0" max="6" value="0"></label><label><span>每月日期</span><input name="day" type="number" min="1" max="31" value="1"></label><label><span>一次执行时间</span><input name="once_at" type="text" placeholder="2026-09-12T09:00:00+08:00"></label><label><span>交付渠道（可多选）</span><select name="channel_id" multiple>${channelOptions}</select></label><label class="automation-channel-choice"><input type="checkbox" name="include_attachments"><span>显式附带研究文件引用</span></label><label class="span-all"><span>输入模板</span><textarea name="input_template" required maxlength="100000" rows="4" placeholder="描述每次执行时固定使用的研究目标与边界"></textarea></label></div><div class="button-row"><button type="button" class="button" data-close-automation-form>取消</button><button type="submit" class="button primary" ${busy || !targets.length ? 'disabled' : ''}>${busy ? '保存中…' : '保存计划'}</button></div></form>`;
}

function deliveryChannelPanel(channels, busy) {
  const rows = list(channels);
  return `<details class="delivery-channel-panel"><summary>配置外发渠道</summary><div class="delivery-channel-body"><p class="muted small">地址、密码、签名秘密和收件人只写入系统凭据库，不写入任务索引或日志。签名 Webhook 必须提供秘密；其他机器人可将令牌保留在地址中。</p><form class="automation-form-grid" data-delivery-channel-form><label><span>名称</span><input name="name" required maxlength="160"></label><label><span>类型</span><select name="kind"><option value="webhook">签名 Webhook</option><option value="smtp">SMTP</option><option value="feishu">飞书</option><option value="wecom">企业微信</option><option value="dingtalk">钉钉</option></select></label><label class="span-all"><span>Webhook 地址</span><input name="endpoint" type="url" placeholder="https://..."></label><label><span>SMTP Host</span><input name="smtp_host"></label><label><span>SMTP Port</span><input name="smtp_port" type="number" min="1" max="65535" value="587"></label><label><span>SMTP 用户名</span><input name="smtp_username"></label><label><span>发件人</span><input name="sender" type="email"></label><label class="span-all"><span>收件人（逗号分隔）</span><input name="recipients"></label><label class="span-all"><span>密码 / 签名秘密</span><input name="secret" type="password" autocomplete="new-password"></label><div class="span-all button-row"><button type="submit" class="button" ${busy ? 'disabled' : ''}>保存渠道</button></div></form>${rows.length ? `<div class="connection-tool-list">${rows.map(item => `<article><div><strong>${e(item.name)}</strong><small>${e(item.kind)} · 系统凭据库</small></div><span class="badge ${item.enabled ? 'live' : ''}">${item.enabled ? '已启用' : '已停用'}</span></article>`).join('')}</div>` : ''}</div></details>`;
}

function plansView(automations, runs, legacyItems, capabilities, deliveryChannels, busy, formOpen) {
  const rows = list(automations);
  const runById = new Map(list(runs).map(item => [item.id, item]));
  const legacy = list(legacyItems).filter(item => item.next_run_at);
  const cards = rows.length ? `<div class="capability-plan-list">${rows.map(item => { const run = runById.get(item.last_run_id); return `<article><header><div><span class="eyebrow">${e(item.target?.kind || 'AUTOMATION')} · ${e(item.target?.id || '')}</span><h3>${e(item.name)}</h3></div><span class="badge ${item.enabled ? 'live' : ''}">${item.enabled ? '已启用' : '已停用'}</span></header><dl><div><dt>锁定版本</dt><dd>v${e(item.target?.version || '—')}</dd></div><div><dt>下次执行</dt><dd>${e(formatTime(item.next_run_at))}</dd></div><div><dt>最近运行</dt><dd>${e(runLabel(run?.research_status))}</dd></div><div><dt>交付状态</dt><dd>${e(run?.delivery_status || '尚未交付')}</dd></div></dl><div class="button-row"><button type="button" class="button small" data-run-automation="${e(item.id)}" ${busy ? 'disabled' : ''}>立即运行</button><button type="button" class="button small" data-${item.enabled ? 'disable' : 'enable'}-automation="${e(item.id)}" ${busy ? 'disabled' : ''}>${item.enabled ? '停用' : '启用'}</button><button type="button" class="button small danger" data-delete-automation="${e(item.id)}" ${busy ? 'disabled' : ''}>移除</button></div></article>`; }).join('')}</div>` : empty('暂无通用 Automation', '从已发布的 Skill、Workflow 或报告 Workflow 创建版本锁定的运行计划。');
  const recentRuns = list(runs).slice(0, 12);
  const runHistory = `<section><div class="section-heading"><div><h3>最近运行记录</h3><p class="muted small">研究状态与交付状态分别记录；失败研究仅支持显式手动重试。</p></div></div>${recentRuns.length ? `<div class="connection-tool-list">${recentRuns.map(run => `<article><div><strong>${e(run.id)}</strong><small>${e(runLabel(run.research_status))} · 交付 ${e(run.delivery_status || '未请求')} · ${e(formatTime(run.scheduled_for || run.created_at * 1000))}</small></div>${['failed', 'interrupted', 'blocked_version'].includes(run.research_status) ? `<button type="button" class="button small" data-retry-automation-run="${e(run.id)}" ${busy ? 'disabled' : ''}>手动重试</button>` : ''}</article>`).join('')}</div>` : '<p class="muted">暂无运行记录。</p>'}</section>`;
  const legacySection = `<section class="legacy-schedule-section"><div class="section-heading"><div><h3>旧报告日程</h3><p class="muted small">迁移前旧接口持续可用；仅在对应 Automation 保存成功后停用旧日程。</p></div></div>${legacy.length ? `<div class="connection-tool-list">${legacy.map(item => `<article><div><strong>${e(item.name)}</strong><small>v${e(item.current_version || '—')} · 下次 ${e(formatTime(item.next_run_at))}</small></div><button type="button" class="button small" data-report-workflow-detail="${e(item.id)}" ${busy ? 'disabled' : ''}>查看</button><button type="button" class="button small primary" data-migrate-report-schedule="${e(item.id)}" ${busy ? 'disabled' : ''}>迁移</button></article>`).join('')}</div>` : '<p class="muted">没有待迁移的旧报告日程。</p>'}</section>`;
  return `<div class="capability-view-heading"><div><span class="eyebrow">AUTOMATIONS</span><h2>定时任务</h2><p class="muted">通用 Automation 聚合锁定版本、最近运行、下一次执行和独立交付状态。</p></div><button type="button" class="button primary" data-create-automation ${busy ? 'disabled' : ''}>新建计划</button></div><section class="notice"><h3>Hot 周期简报</h3><p>由 Hot 的 PostgreSQL 队列管理计划与运行，保存后另行启用。</p><a class="button" href="#/intel/hot?view=plans">管理频道周期简报</a></section>${formOpen ? automationForm(capabilities, legacyItems, deliveryChannels, busy) : ''}${deliveryChannelPanel(deliveryChannels, busy)}<section><div class="section-heading"><div><h3>通用 Automation</h3><p class="muted small">研究失败只允许手动重试；外发失败不会改变研究结果。</p></div></div>${cards}</section>${runHistory}${legacySection}`;
}

function connectionState(source) {
  if (source.callable === true) return ['可调用', 'live'];
  if (source.integration_completed !== true) return ['尚未适配', ''];
  if (source.configured !== true && !['none', 'local', 'terminal'].includes(source.auth_type || source.auth_kind)) return ['待配置', ''];
  return ['待检测', ''];
}

function toolConnectionsView(connections, tools, { legacyTools = false, query = '' } = {}) {
  const q = normalizeText(query);
  const sources = list(connections?.sources).filter(source => source.group === 'local' && (!q || normalizeText(`${source.name || source.label || ''} ${source.id} ${source.description}`).includes(q)));
  const toolRows = list(tools).filter(tool => !q || normalizeText(`${tool.name} ${tool.id} ${tool.description}`).includes(q));
  const legacy = legacyTools ? `<details open><summary>旧工具链接 · 工具声明</summary><p class="muted small">选择仅加入草稿；实际调用仍需运行时与原生审批。</p>${toolRows.map(tool => `<p><button type="button" class="button small" data-tool-detail="${e(tool.id)}" data-cap-preview-trigger="tool:${e(tool.id)}">${e(tool.name)}</button> <span class="badge">${tool.selectable ? '可加入草稿' : '内部控制'}</span></p>`).join('')}</details>` : '';
  return `<section aria-label="本机连接器"><div class="capability-view-heading"><div><h2>本机集成</h2><p class="muted">配置、启用与实际可调用分别核验。</p></div><a class="button" href="#/settings/local">配置本机集成</a></div>${sources.length ? `<div class="connection-tool-list">${sources.map(source => { const [label, tone] = connectionState(source); const provided = list(source.tools || source.tool_ids); return `<article><div><strong>${e(source.name || source.label || source.id)}</strong><small>${e(source.description || source.id)}</small>${provided.length ? `<details><summary>提供的工具</summary>${provided.map(tool => `<button type="button" class="button small" data-tool-detail="${e(typeof tool === 'string' ? tool : tool.id)}">${e(typeof tool === 'string' ? tool : tool.name || tool.id)}</button>`).join('')}</details>` : ''}</div><span class="badge ${tone}">${e(label)}</span><a class="button small" href="#/settings/local?connection=${encodeURIComponent(source.id)}">配置</a></article>`; }).join('')}</div>` : empty('没有匹配的本机集成', '请在本机连接设置中查看配置。')}${legacy}</section>`;
}

function installedMCPView(state, query) {
  const q = normalizeText(query);
  const rows = list(state.installations).filter(item => !q || normalizeText(`${item.plan?.server_name} ${item.id}`).includes(q));
  return `<section aria-label="MCP 连接器"><div class="capability-view-heading"><h2>MCP 连接器</h2><a class="button" href="#/skills?kind=connector&view=market">添加 MCP</a></div>${state.runtimeError ? `<p class="muted" role="status">${e(state.runtimeError)}</p>` : ''}${state.error ? `<p class="notice error" role="alert">${e(state.error)}</p>` : ''}${rows.length ? `<div class="connection-tool-list">${rows.map(item => `<article><div><strong>${e(item.plan?.server_name || item.id)}</strong><small>MCP · ${e(item.plan?.server_version || '版本未知')}</small></div><span class="badge">${e(item.runtime_status || '状态未知')}${item.active === true ? ' · 已启用' : ''}</span><button type="button" class="button small" data-mcp-server-detail data-registry-id="${e(item.plan?.registry_id)}" data-server-name="${e(item.plan?.server_name)}" data-server-version="${e(item.plan?.server_version)}">查看连接与工具</button></article>`).join('')}</div>` : empty('没有匹配的 MCP 连接器', '安装、启用与实际调用权限分别确认。')}</section>`;
}

export function renderCapabilityWorkspace({ capabilities = [], tools = [], reportWorkflows = [], automations = [], automationRuns = [], deliveryChannels = [], automationFormOpen = false, dataCatalog = {}, connections = {}, mcpMarketplace = {}, view = 'library', kind = 'skill', context = '', source = 'all', category = '', status = 'all', query = '', dataMarket = '', dataStatus = '', dataAuth = '', probe = null, busy = false, error = '' } = {}) {
  const safeKind = primaryKind(kind);
  const legacyContext = context || (kind !== safeKind ? kind : '');
  const allowedViews = [...subviews[safeKind].map(([value]) => value), ...(safeKind === 'skill' ? ['plans'] : [])];
  const safeView = views.includes(view) && allowedViews.includes(view) ? view : 'library';
  const entries = collectCapabilityWorkspaceEntries({ capabilities, tools, dataCatalog });
  let body;
  if (safeKind === 'plugin') body = '<div data-plugin-workspace></div>';
  else if (safeKind === 'skill' && safeView === 'plans') body = plansView(automations, automationRuns, reportWorkflows, capabilities, deliveryChannels, busy, automationFormOpen);
  else if (safeKind === 'connector' && safeView === 'market') body = renderMCPMarketplace(mcpMarketplace);
  else if (safeKind === 'connector') {
    const sources = renderDataCatalog({ catalog: dataCatalog, view: legacyContext === 'data' && safeView === 'library' ? 'capabilities' : 'sources', query, category, market: dataMarket, status: dataStatus, auth: dataAuth, busy, error, probe, showViewSwitch: false, embedded: true });
    body = `<label class="search-box"><input id="cap-search" data-cap-query type="search" aria-label="搜索连接器" value="${e(query)}" placeholder="搜索连接器"></label>${installedMCPView(mcpMarketplace, query)}${toolConnectionsView(connections, tools, { legacyTools: legacyContext === 'tool', query })}<section aria-label="DataHub 来源与能力"><h2>${legacyContext === 'data' && safeView === 'library' ? 'DataHub 数据能力' : 'DataHub 数据源'}</h2>${sources}</section>`;
  } else body = catalogView(entries, { view: safeView, kind: safeKind, source, category, status, query }, busy, error);
  if (safeView === 'plans') return `<section class="capability-workspace"><header class="capability-workspace-header"><h1>定时任务</h1><a class="button" href="#/skills">能力中心</a></header>${body}</section>`;
  return `<section class="capability-workspace"><header class="capability-workspace-header"><div><h1>能力中心</h1><p class="muted">选择技能，接入连接器，管理插件。</p></div><div class="button-row"><a class="button" href="#/automations">${icon('activity')}定时任务</a><button type="button" class="button" data-cap-refresh ${busy ? 'disabled' : ''}>刷新状态</button></div></header>${workspaceKindNav(safeKind)}${workspaceSubviewNav(safeKind, safeView)}<div id="capability-workspace-panel" role="tabpanel" aria-labelledby="capability-kind-${safeKind}" tabindex="0">${body}</div></section>`;
}

function previewFromState({ detail, tool, dataDetail, dataDetailKind, capabilities }) {
  if (detail) {
    const item = capabilityEntry(detail);
    if (item.kind === 'method') {
      item.linkedCapabilities = list(capabilities).filter(capability => ['skill', 'workflow'].includes(capability.kind)).flatMap(capability => {
        const policy = capability.metadata?.method_policy || {};
        if (list(policy.required).includes(item.id)) return [{ id: capability.id, name: capability.name, source: 'required' }];
        if (list(policy.recommended).includes(item.id)) return [{ id: capability.id, name: capability.name, source: 'recommended' }];
        return [];
      });
    }
    return item;
  }
  if (tool) return toolEntry(tool);
  if (dataDetail && dataDetailKind === 'capability') return dataEntry(dataDetail);
  return null;
}

export function renderCapabilityPreviewDialog(state = {}) {
  const item = previewFromState(state);
  if (!item) return '';
  const inputText = item.inputs.map(input => `${input.label || input.name || '参数'}（${input.type || '参数'}${input.required ? ' · 必填' : ''}）`);
  const linked = item.kind === 'method' ? `<div><dt>关联业务能力</dt><dd>${item.linkedCapabilities.length ? e(item.linkedCapabilities.map(value => `${value.name}（${value.source === 'required' ? '必需' : '推荐'}）`).join('、')) : '尚未进入默认策略，可手动选择'}</dd></div>` : '';
  return `<div class="capability-dialog-backdrop" data-capability-dialog-backdrop><section class="capability-preview-dialog" role="dialog" aria-modal="true" aria-labelledby="capability-preview-title" aria-describedby="capability-preview-description"><header><span class="skill-icon">${icon(entryIcon(item))}</span><div><span class="eyebrow">${e(kindLabels[item.kind])} · ${e(item.source)}</span><h2 id="capability-preview-title">${e(item.name)}</h2><span class="badge ${item.available ? 'live' : 'danger'}">${e(item.statusLabel)}</span></div><button type="button" class="icon-button" data-cap-close aria-label="关闭能力快览">×</button></header><p id="capability-preview-description" class="capability-preview-description">${e(item.description || '尚未提供简介')}</p><dl class="capability-preview-grid"><div><dt>适用场景</dt><dd>${join(item.scenarios)}</dd></div><div><dt>输入</dt><dd>${join(inputText)}</dd></div><div><dt>输出</dt><dd>${join(item.formats, item.kind === 'data' ? '结构化数据' : '无需文件')}</dd></div><div><dt>所需工具</dt><dd>${item.tools.length ? item.tools.map(id => `<button type="button" class="button small" data-tool-detail="${e(id)}">${e(list(state.tools).find(tool => tool.id === id)?.name || id)}</button>`).join('') : '无显式工具要求'}</dd></div><div><dt>依赖</dt><dd>${join(item.dependencies, '无额外依赖')}</dd></div>${linked}<div><dt>状态说明</dt><dd>${e(item.reason || '可加入草稿；实际调用仍按会话权限与运行时状态核验')}</dd></div></dl><footer><button type="button" class="button" data-cap-close>取消</button>${['skill', 'workflow', 'method', 'tool', 'data'].includes(item.kind) ? `<button type="button" class="button" data-cap-manage="${e(item.id)}">进入管理</button>` : ''}<button type="button" class="button primary" ${useAttribute(item)} ${state.busy || !item.available ? 'disabled' : ''}>立即使用</button></footer></section></div>`;
}

export function renderCapabilityPage({ cap, catalog, messages = '', conversationBusy = false, workspaceBusy = false, running = false, automationFormOpen = false, mcpMarketplace, currentSessionId = null }) {
  if (cap.form === 'editor') return messages + renderCapabilityEditor({ draft: cap.editor, id: cap.editorId, items: catalog.capabilities, tools: catalog.tools, busy: cap.busy, announcement: cap.stepAnnouncement || '' });
  if (cap.form === 'conversation') return messages + renderCreationForm(cap.kind, cap.goal, conversationBusy);
  if (cap.form === 'copy') return messages + renderCopyForm(cap.detail, cap.copy, cap.busy);
  if (cap.form === 'manage' && cap.dataDetail) {
    const tools = (cap.dataDetail.bindings || []).map(binding => binding.capability?.tool_id || catalog.dataCatalog.capabilities?.find(item => item.id === binding.capability?.id)?.tool_id).filter(Boolean);
    const provided = cap.dataDetailKind === 'source' && tools.length ? `<details><summary>提供的工具</summary>${[...new Set(tools)].map(id => `<button type="button" class="button small" data-tool-detail="${e(id)}">${e(id)}</button>`).join('')}</details>` : '';
    return messages + (cap.dataDetailKind === 'source' ? renderDataSourceDetail(cap.dataDetail, cap.busy) + provided : renderDataCapabilityDetail(cap.dataDetail));
  }
  if (cap.form === 'manage' && cap.tool) return messages + renderToolDetail(cap.tool);
  if (cap.form === 'manage' && cap.detail) return messages + renderCapabilityDetail(cap.detail, { busy: cap.busy, versions: cap.versions, versionDetail: cap.versionDetail, running: running });
  const workspace = renderCapabilityWorkspace({
    capabilities: catalog.capabilities.filter(item => !item.metadata?.report_workflow), tools: catalog.tools, reportWorkflows: catalog.reportWorkflows,
    automations: catalog.automations, automationRuns: catalog.automationRuns, deliveryChannels: catalog.deliveryChannels, automationFormOpen,
    dataCatalog: catalog.dataCatalog, connections: catalog.connections, mcpMarketplace: mcpMarketplace, view: cap.view, kind: cap.kindFilter, context: cap.context,
    source: cap.source, category: cap.category, status: cap.status, query: cap.query,
    dataMarket: cap.dataMarket, dataStatus: cap.dataStatus, dataAuth: cap.dataAuth, probe: cap.probe,
    busy: cap.busy || workspaceBusy,
    error: catalog.errors.capabilities || catalog.errors.tools || catalog.errors.automations || catalog.errors.automationRuns || catalog.errors.dataCatalog || catalog.errors.connections || '',
  });
  return messages + workspace + renderCapabilityPreviewDialog({ detail: cap.detail, tool: cap.tool, dataDetail: cap.dataDetail, dataDetailKind: cap.dataDetailKind, capabilities: catalog.capabilities, tools: catalog.tools, busy: cap.busy }) + renderMCPServerDialog(mcpMarketplace.detail, { ...mcpMarketplace.installation, runtimeAvailable: mcpMarketplace.runtimeAvailable, currentSessionId: currentSessionId });
}
