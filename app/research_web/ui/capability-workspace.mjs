import { escapeHTML as e } from './markdown.mjs';
import { icon } from './icons.mjs';
import { empty } from './views.mjs';
import { capabilityStatus, reportWorkflowEligibility } from './capabilities.mjs';
import { renderDataCatalog } from './data-catalog.mjs';
import { renderMCPMarketplace } from './mcp-marketplace.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const views = ['library', 'mine', 'plans', 'connections', 'market'];
const kinds = ['skill', 'tool', 'workflow', 'data'];
const kindLabels = { skill: 'Skill', tool: 'Tool', workflow: 'Workflow', data: '数据' };
const subviews = {
  skill: [['library', '能力库'], ['mine', '我的 Skill']],
  tool: [['library', '工具目录'], ['market', 'MCP 市场'], ['connections', '连接状态']],
  workflow: [['library', '能力库'], ['mine', '我的 Workflow'], ['plans', '运行计划']],
  data: [['library', '数据能力'], ['connections', '数据源与连接']],
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
  const index = Math.max(0, kinds.indexOf(current));
  const next = key === 'Home' ? 0 : key === 'End' ? kinds.length - 1 : (index + (key === 'ArrowRight' ? 1 : -1) + kinds.length) % kinds.length;
  return { handled: true, kind: kinds[next] };
}

export function capabilityWorkspaceHash(kind = 'skill', view = 'library') {
  const safeKind = kinds.includes(kind) ? kind : 'skill';
  const allowedViews = subviews[safeKind].map(([value]) => value);
  const safeView = views.includes(view) && allowedViews.includes(view) ? view : 'library';
  const params = new URLSearchParams({ kind: safeKind });
  if (safeView !== 'library') params.set('view', safeView);
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
  return [
    ...list(capabilities).filter(item => ['skill', 'workflow'].includes(item.kind)).map(capabilityEntry),
    ...list(tools).map(toolEntry),
    ...list(dataCatalog.capabilities).map(dataEntry),
  ];
}

export function filterCapabilityWorkspaceEntries(entries = [], { view = 'library', kind = 'skill', source = 'all', category = '', status = 'all', query = '' } = {}) {
  const q = normalizeText(query);
  return list(entries).filter((item) => {
    if (view === 'mine' && (item.sourceKey !== 'mine' || !['skill', 'workflow'].includes(item.kind))) return false;
    return item.kind === kind
      && (source === 'all' || item.sourceKey === source)
      && (!category || item.category === category)
      && (status === 'all' || (status === 'available' ? item.available : !item.available))
      && (!q || normalizeText(`${item.name} ${item.description} ${item.category} ${item.source} ${item.id}`).includes(q));
  });
}

function workspaceKindNav(kind) {
  return `<nav class="capability-workspace-nav" role="tablist" aria-label="能力类型">${kinds.map(value => `<a id="capability-kind-${value}" role="tab" tabindex="${kind === value ? '0' : '-1'}" aria-selected="${kind === value}" aria-controls="capability-workspace-panel" href="${capabilityWorkspaceHash(value)}" data-cap-kind-nav="${value}">${kindLabels[value]}</a>`).join('')}</nav>`;
}

function workspaceSubviewNav(kind, view) {
  const roving = kind === 'tool';
  return `<nav class="capability-workspace-subnav" ${roving ? 'role="tablist"' : ''} aria-label="${kindLabels[kind]} 视图">${subviews[kind].map(([value, label]) => `<a ${roving ? `id="capability-tool-tab-${value}"` : ''} href="${capabilityWorkspaceHash(kind, value)}" aria-current="${view === value ? 'page' : 'false'}" ${roving ? `role="tab" tabindex="${view === value ? '0' : '-1'}" aria-selected="${view === value}" data-mcp-market-tab="${value}"` : ''}>${label}</a>`).join('')}</nav>`;
}

function filters(entries, state) {
  const categories = [...new Set(entries.map(item => item.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'zh-CN'));
  if (state.kind === 'tool') {
    return `<div class="capability-workspace-filters tool-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索 Tool" value="${e(state.query)}" placeholder="搜索名称、简介或技术 ID"></label></div>`;
  }
  const source = ['skill', 'workflow'].includes(state.kind) && state.view === 'library' ? `<label><span>来源</span><select data-cap-source><option value="all" ${state.source === 'all' ? 'selected' : ''}>全部来源</option><option value="builtin" ${state.source === 'builtin' ? 'selected' : ''}>内置</option><option value="mine" ${state.source === 'mine' ? 'selected' : ''}>我的</option></select></label>` : '';
  return `<div class="capability-workspace-filters"><label class="search-box"><span aria-hidden="true">⌕</span><input id="cap-search" data-cap-query type="search" aria-label="搜索 ${kindLabels[state.kind]}" value="${e(state.query)}" placeholder="搜索名称、简介或技术 ID"></label>${source}<label><span>分类</span><select data-cap-category><option value="">全部分类</option>${categories.map(value => `<option value="${e(value)}" ${state.category === value ? 'selected' : ''}>${e(value)}</option>`).join('')}</select></label><label><span>状态</span><select data-cap-status><option value="all" ${state.status === 'all' ? 'selected' : ''}>全部状态</option><option value="available" ${state.status === 'available' ? 'selected' : ''}>可调用</option><option value="unavailable" ${state.status === 'unavailable' ? 'selected' : ''}>不可调用</option></select></label></div>`;
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
  const owned = state.view === 'mine';
  const typeName = kindLabels[state.kind];
  const heading = owned
    ? [`我的 ${typeName}`, `集中管理你创建、复制和导入的 ${typeName}。`]
    : [state.kind === 'tool' ? '工具目录' : `${typeName} 能力库`, state.kind === 'tool' ? '只展示本机真实 Tool 声明、调用状态和授权原因，不与其他能力类型混排。' : `只展示本机已审查的 ${typeName}，不会与其他能力类型混排。`];
  const actions = ['skill', 'workflow'].includes(state.kind) ? `<div class="button-row capability-create-actions"><button type="button" class="button primary" data-cap-create="conversation" ${busy ? 'disabled' : ''}>对话创建</button><button type="button" class="button" data-cap-create="manual" ${busy ? 'disabled' : ''}>手动新建</button><button type="button" class="button" data-cap-import ${busy ? 'disabled' : ''}>导入 ${typeName}</button><input id="cap-import-file" type="file" accept=".md,.zip" hidden></div>` : '';
  const scopedEntries = entries.filter(item => item.kind === state.kind);
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
  return `<div class="capability-view-heading"><div><span class="eyebrow">AUTOMATIONS</span><h2>运行计划</h2><p class="muted">通用 Automation 聚合锁定版本、最近运行、下一次执行和独立交付状态。</p></div><button type="button" class="button primary" data-create-automation ${busy ? 'disabled' : ''}>新建计划</button></div>${formOpen ? automationForm(capabilities, legacyItems, deliveryChannels, busy) : ''}${deliveryChannelPanel(deliveryChannels, busy)}<section><div class="section-heading"><div><h3>通用 Automation</h3><p class="muted small">研究失败只允许手动重试；外发失败不会改变研究结果。</p></div></div>${cards}</section>${runHistory}${legacySection}`;
}

function connectionState(source) {
  if (source.callable === true) return ['可调用', 'live'];
  if (source.integration_completed !== true) return ['尚未适配', ''];
  if (source.configured !== true && !['none', 'local', 'terminal'].includes(source.auth_type || source.auth_kind)) return ['待配置', ''];
  return ['待检测', ''];
}

function toolConnectionsView(connections, tools) {
  const sources = list(connections?.sources).filter(source => source.group === 'local');
  return `<div class="capability-view-heading"><div><span class="eyebrow">LOCAL CONNECTIONS</span><h2>Tool 连接状态</h2><p class="muted">查看本机集成与 Tool 的真实调用状态；凭据配置继续在设置中完成。</p></div><div class="button-row"><a class="button" href="#/skills?kind=data&view=connections">查看数据源</a><a class="button" href="#/settings/local">打开本机连接设置</a></div></div><section class="connection-tool-summary" aria-label="Tool 连接状态汇总"><div><strong>${sources.length}</strong><span>本机集成</span></div><div><strong>${sources.filter(item => item.callable === true).length}</strong><span>当前可调用</span></div><div><strong>${list(tools).length}</strong><span>Tool 声明</span></div><div><strong>${list(tools).filter(item => item.selectable === true).length}</strong><span>可加入草稿</span></div></section><div class="connection-tool-sections"><section><div class="section-heading"><div><h3>本机集成</h3><p class="muted small">这里只展示本机连接；数据源在“数据”分区单独管理。</p></div></div>${sources.length ? `<div class="connection-tool-list">${sources.map(source => { const [label, tone] = connectionState(source); return `<article><div><strong>${e(source.name || source.label || source.id)}</strong><small>${e(source.description || source.id)}</small></div><span class="badge ${tone}">${e(label)}</span><a class="button small" href="#/settings/local?connection=${encodeURIComponent(source.id)}">配置</a></article>`; }).join('')}</div>` : empty('没有本机连接记录', '刷新目录后仍为空时，请检查连接服务。')}</section><section><div class="section-heading"><div><h3>研究 Tool</h3><p class="muted small">安装、启用与会话授权仍是独立状态。</p></div></div>${list(tools).length ? `<div class="connection-tool-list">${list(tools).map(tool => `<article><div><strong>${e(tool.name)}</strong><small>${e(tool.description || tool.id)}</small></div><span class="badge ${tool.selectable ? 'live' : ''}">${tool.selectable ? '可加入草稿' : '内部控制'}</span><button type="button" class="button small" data-tool-detail="${e(tool.id)}" data-cap-preview-trigger="${e(attrKey('tool', tool.id))}">快览</button></article>`).join('')}</div>` : empty('没有 Tool 声明', '刷新目录后仍为空时，请检查工具目录。')}</section></div>`;
}

export function renderCapabilityWorkspace({ capabilities = [], tools = [], reportWorkflows = [], automations = [], automationRuns = [], deliveryChannels = [], automationFormOpen = false, dataCatalog = {}, connections = {}, mcpMarketplace = {}, view = 'library', kind = 'skill', source = 'all', category = '', status = 'all', query = '', dataMarket = '', dataStatus = '', dataAuth = '', probe = null, busy = false, error = '' } = {}) {
  const safeKind = kinds.includes(kind) ? kind : 'skill';
  const allowedViews = subviews[safeKind].map(([value]) => value);
  const safeView = views.includes(view) && allowedViews.includes(view) ? view : 'library';
  const entries = collectCapabilityWorkspaceEntries({ capabilities, tools, dataCatalog });
  let body;
  if (safeKind === 'workflow' && safeView === 'plans') body = plansView(automations, automationRuns, reportWorkflows, capabilities, deliveryChannels, busy, automationFormOpen);
  else if (safeKind === 'tool' && safeView === 'market') body = renderMCPMarketplace(mcpMarketplace);
  else if (safeKind === 'tool' && safeView === 'connections') body = toolConnectionsView(connections, tools);
  else if (safeKind === 'data') {
    const dataView = safeView === 'connections' ? 'sources' : 'capabilities';
    const heading = dataView === 'sources'
      ? ['数据源与连接', '查看真实接入、配置和健康状态；连接设置继续在设置页完成。']
      : ['数据能力', '按可解决的研究问题浏览数据能力，不与 Tool 声明混排。'];
    body = `<div class="capability-view-heading"><div><span class="eyebrow">DATA CATALOG</span><h2>${heading[0]}</h2><p class="muted">${heading[1]}</p></div>${dataView === 'sources' ? '<a class="button" href="#/settings/data">打开数据连接设置</a>' : ''}</div>${renderDataCatalog({ catalog: dataCatalog, view: dataView, query, category, market: dataMarket, status: dataStatus, auth: dataAuth, busy, error, probe, showViewSwitch: false })}`;
  } else body = catalogView(entries, { view: safeView, kind: safeKind, source, category, status, query }, busy, error);
  return `<section class="capability-workspace"><header class="capability-workspace-header"><div><span class="eyebrow">CAPABILITY WORKSPACE · V0</span><h1>能力工作区</h1><p class="muted">Skill、Tool、Workflow 与数据分区浏览；任何执行都需要你的明确确认。</p></div><button type="button" class="button" data-cap-refresh ${busy ? 'disabled' : ''}>刷新状态</button></header>${workspaceKindNav(safeKind)}${workspaceSubviewNav(safeKind, safeView)}<div id="capability-workspace-panel" role="tabpanel" aria-labelledby="capability-kind-${safeKind}" tabindex="0">${body}</div></section>`;
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
