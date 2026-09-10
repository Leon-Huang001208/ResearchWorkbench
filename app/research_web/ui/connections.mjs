import { escapeHTML as e } from './markdown.mjs';

const zhiqiuSources = new Set(['zhiqiu_reports', 'zhiqiu_wechat', 'zhiqiu_transcript']);
const tokenLabels = { tinysoft: 'CJ_KEY', tushare: 'API Token', tavily: 'API Key', bing: 'API Key' };
const tokenFields = { tinysoft: 'token', tushare: 'token', tavily: 'api_key', bing: 'api_key' };
const statusText = {
  healthy: '正常', available: '可用', ready: '就绪', checking: '检测中',
  untested: '未检测', unverified: '未验证', unavailable: '不可用',
  not_installed: '未安装', not_logged_in: '未登录', not_applicable: '不适用',
  degraded: '受限', detected: '已检测到组件', failed: '失败', error: '异常', unknown: '待检测',
};
const integrationLabels = { excel_automation: 'Excel 自动化', wind_excel: 'Wind 插件', ifind_excel: 'iFinD 插件', report_workflow: '报告工作流' };
const localIntegrationKeys = Object.keys(integrationLabels);
const localStatusDefinitions = {
  healthy: ['环境已就绪', 'ready', '当前服务设备已通过这项环境检查。'],
  available: ['环境已就绪', 'ready', '当前服务设备已通过这项环境检查。'],
  ready: ['环境已就绪', 'ready', '当前服务设备已通过这项环境检查。'],
  checking: ['待检测', 'pending', '正在检测当前服务设备，请稍候。'],
  untested: ['待检测', 'pending', '尚未执行这项环境检查。'],
  unknown: ['待检测', 'pending', '尚未执行这项环境检查。'],
  unverified: ['待验证', 'pending', '尚未通过真实工作簿或工作流运行验证。'],
  detected: ['待验证', 'pending', '已检测到组件，仍需真实工作簿或工作流验证。'],
  not_installed: ['未安装', 'attention', '当前服务设备未检测到所需组件。'],
  not_logged_in: ['未登录', 'attention', '已检测到组件，但当前本机会话尚未登录。'],
  degraded: ['受限', 'attention', '组件可被识别，但能力受限。'],
  failed: ['异常', 'danger', '环境检查失败，请查看服务日志后重试。'],
  error: ['异常', 'danger', '环境检查失败，请查看服务日志后重试。'],
  unavailable: ['异常', 'danger', '当前服务设备暂不满足使用条件。'],
  not_applicable: ['不适用', 'neutral', '当前操作系统不适用这项能力。'],
};

const localStatusTone = {
  '可用': 'ready', '待配置': 'attention', '待授权': 'attention', '待验证': 'pending',
  '未发现': 'neutral', '未登录': 'attention', '受限': 'attention', '异常': 'danger', '不适用': 'neutral',
};

function safeLocalAction(action) {
  const href = String(action?.href || '');
  return /^#\/settings\/data\?connection=[a-z0-9_]+$/.test(href)
    ? `<a class="button small" href="${e(href)}">${e(action.label || '配置')}</a>`
    : '';
}

function localTruth(label, value) {
  return `<span><small>${e(label)}</small><strong>${e(value)}</strong></span>`;
}

const localVerificationTargets = {
  excel_app: 'excel',
  word_app: 'word',
  powerpoint_app: 'powerpoint',
  wind_excel_addin: 'wind_excel',
};

const localVerificationLabels = {
  excel: 'Excel',
  word: 'Word',
  powerpoint: 'PowerPoint',
  wind_excel: 'Wind Excel',
};

export function createLocalIntegrationPollingGuard(isActive = () => true) {
  let generation = 0;
  return {
    begin() { generation += 1; return generation; },
    invalidate() { generation += 1; },
    isCurrent(ticket) { return ticket === generation && isActive(); },
  };
}

function renderLocalIntegrationRow(item, verificationTarget = '') {
  const actions = Array.isArray(item?.actions) ? item.actions.map(safeLocalAction).join('') : '';
  const target = localVerificationTargets[item?.id];
  const verifying = target && verificationTarget === target;
  const verifyAction = target && item?.discovery === '已发现'
    ? `<button class="button small local-integration-verify" type="button" data-local-integration-verify="${e(target)}" ${verificationTarget ? 'disabled' : ''} ${verifying ? 'aria-busy="true"' : ''}>${verifying ? '验证中…' : '真实验证'}</button>`
    : '';
  const checked = target && item?.last_verified_at
    ? `<time datetime="${e(item.last_verified_at)}">最近验证：${e(item.last_verified_at)}</time>`
    : '';
  const callable = item?.status === '不适用' ? '不适用' : item?.callable === true ? '是' : '否';
  const tone = localStatusTone[item?.status] || 'danger';
  return `<article class="local-integration-row" data-local-integration="${e(item?.id || '')}"><div class="local-integration-identity"><div><strong>${e(item?.label || '未命名集成')}</strong><span class="local-status ${e(tone)}"><span aria-hidden="true"></span>${e(item?.status || '异常')}</span></div><p>${e(item?.message || '服务未提供状态说明。')}</p>${item?.detail ? `<small>${e(item.detail)}</small>` : ''}${checked}${actions || verifyAction ? `<div class="button-row">${actions}${verifyAction}</div>` : ''}</div><div class="local-integration-truths" aria-label="${e(item?.label || '')} 状态">${localTruth('发现', item?.discovery || '异常')}${localTruth('授权', item?.authorization || '异常')}${localTruth('验证', item?.verification || '异常')}${localTruth('可调用', callable)}</div></article>`;
}

export function renderLocalIntegrationConsole(model = {}, { busy = false, verificationTarget = '' } = {}) {
  const categories = Array.isArray(model?.categories) ? model.categories : [];
  const items = Array.isArray(model?.items) ? model.items : [];
  const byId = new Map(items.map((item) => [item.id, item]));
  const summary = model?.summary || {};
  const serviceLabel = model?.service?.online ? (model.service.label || '本机服务在线') : '本机服务异常';
  const nav = `<nav class="local-category-nav" aria-label="本机集成分类">${categories.map((category) => `<button type="button" data-local-category-target="local-category-${e(category.id)}" aria-controls="local-category-${e(category.id)}">${e(category.label || category.id)}</button>`).join('')}</nav>`;
  const groups = categories.map((category) => {
    const categoryItems = Array.isArray(category.item_ids)
      ? category.item_ids.map((id) => byId.get(id)).filter(Boolean)
      : items.filter((item) => item.category === category.id);
    const rows = categoryItems.length ? categoryItems.map((item) => renderLocalIntegrationRow(item, verificationTarget)).join('') : '<p class="local-category-empty">当前没有已登记项目。</p>';
    return `<section class="local-integration-category" id="local-category-${e(category.id)}" tabindex="-1" aria-labelledby="local-category-title-${e(category.id)}"><header><h2 id="local-category-title-${e(category.id)}">${e(category.label || category.id)}</h2><span>${categoryItems.length} 项</span></header><div class="local-integration-column-head" aria-hidden="true"><span>集成</span><span>发现</span><span>授权</span><span>验证</span><span>可调用</span></div>${rows}</section>`;
  }).join('');
  const verificationLabel = localVerificationLabels[verificationTarget];
  const announcement = verificationLabel
    ? `正在验证 ${verificationLabel}，完成后将自动更新状态。`
    : busy
      ? '正在检测本机集成状态，请稍候。'
      : `${serviceLabel}，${summary.available ?? 0} 项可用，${summary.needs_attention ?? 0} 项需处理。`;
  return `<section class="local-integration-console" data-local-integrations-console><p class="sr-only" role="status" aria-live="polite" aria-atomic="true">${e(announcement)}</p><section class="local-integration-summary" aria-label="本机集成概览"><div><span class="local-service-indicator ${model?.service?.online ? 'ready' : 'danger'}"><span aria-hidden="true"></span>${e(serviceLabel)}</span><p>诊断分别保留发现、授权、验证和可调用事实。</p></div><dl><div><dt><strong>${e(summary.available ?? 0)}</strong> 项可用</dt></div><div><dt><strong>${e(summary.needs_attention ?? 0)}</strong> 项需处理</dt></div></dl><button class="button primary local-integrations-probe" type="button" data-local-integrations-probe ${busy ? 'disabled aria-busy="true"' : ''}>${busy ? '检测中…' : '重新检测'}</button></section>${nav}${groups}<section class="local-report-automation"><div><p class="eyebrow">WORKFLOW</p><h2>报告自动化</h2><p>报告工作流消费 Excel、Word、PowerPoint、Wind/iFinD 数据能力生成报告，并根据自身资源与依赖单独判断能否运行。</p></div><a class="button" href="#/skills?kind=workflow">查看报告 Workflow</a></section></section>`;
}

function get(values, key) {
  return typeof values?.get === 'function' ? values.get(key) : values?.[key];
}

function trim(values, key) { return String(get(values, key) || '').trim(); }

function sourceName(source) { return source?.name || source?.label || source?.id || '未知来源'; }

function isProbed(source) {
  return source?.probed === true || !['', 'untested', 'unknown'].includes(String(source?.probe_status || source?.health || 'untested'));
}

function sourceState(source) {
  const configured = source?.configured === true;
  const probed = isProbed(source);
  const integrated = source?.integration_completed === true;
  const callable = source?.callable === true;
  return { configured, probed, integrated, callable };
}

function stateBadge(label, active, kind = '') {
  return `<span class="connection-state ${active ? `active ${kind}` : ''}"><span aria-hidden="true">${active ? '●' : '○'}</span>${label}</span>`;
}

function renderStateMatrix(source) {
  const state = sourceState(source);
  return `<div class="connection-state-matrix" aria-label="连接状态">${stateBadge('已配置', state.configured)}${stateBadge('已检测', state.probed)}${stateBadge('已适配', state.integrated)}${stateBadge('可调用', state.callable, 'callable')}</div>`;
}

function authLabel(source) {
  return ({ none: '无需鉴权', api_key: 'API Key', account: '账号凭据', terminal: '本机会话', local: '本机能力' })[source?.auth_type || source?.auth_kind] || '按来源要求';
}

function compactStatus(source) {
  const state = sourceState(source);
  if (state.callable) return ['可调用', 'live'];
  if (!state.integrated) return ['尚未适配', ''];
  if (!state.configured && !['none', 'local', 'terminal'].includes(source?.auth_type || source?.auth_kind)) return ['待配置', 'warning'];
  if (!state.probed) return ['待检测', 'warning'];
  return ['不可调用', 'danger'];
}

function connectionStatusKey(source) {
  const [label] = compactStatus(source);
  if (label === '可调用') return 'connected';
  if (label === '待配置') return 'pending';
  return 'attention';
}

function searchableSourceText(source) {
  return [sourceName(source), source?.id, authLabel(source), compactStatus(source)[0], source?.description]
    .filter(Boolean)
    .join(' ')
    .toLocaleLowerCase();
}

export function filterConnectionSources(sources = [], { group = 'professional', query = '', status = 'all' } = {}) {
  const normalizedQuery = String(query || '').trim().toLocaleLowerCase();
  return sources.filter((source) => {
    const groupMatches = normalizedQuery ? true : source?.group === group;
    const statusMatches = status === 'all' || connectionStatusKey(source) === status;
    return groupMatches && statusMatches && (!normalizedQuery || searchableSourceText(source).includes(normalizedQuery));
  });
}

function renderSourceButton(source, selected, { card = false, visible = true } = {}) {
  const [label, kind] = compactStatus(source);
  const cardAttributes = card ? ` data-connection-card data-connection-group-name="${e(source.group || '')}" data-connection-status-name="${e(connectionStatusKey(source))}" data-connection-search-text="${e(searchableSourceText(source))}" ${visible ? '' : 'hidden'}` : '';
  return `<button type="button" class="connection-source ${card ? 'connection-card' : ''} ${selected ? 'selected' : ''}" data-connection-select="${e(source.id)}"${cardAttributes} aria-pressed="${selected}" aria-expanded="${selected}"><span class="connection-source-copy"><strong>${e(sourceName(source))}</strong><small>${e(authLabel(source))}</small></span><span class="badge ${kind}">${e(label)}</span></button>`;
}

function groupSourceIds(group) { return group?.source_ids || group?.items || group?.sources || []; }

function normalizedGroups(connections) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  if (Array.isArray(connections?.groups) && connections.groups.length) return connections.groups;
  const groupOrder = [['professional', '专业数据源'], ['api', 'API 数据源'], ['public', '公开来源'], ['local', '本机集成']];
  return groupOrder.map(([id, label]) => ({ id, label, source_ids: sources.filter((source) => source.group === id).map((source) => source.id) }));
}

function scopedSources(sources, scope) {
  if (scope === 'local') return sources.filter((source) => source?.group === 'local');
  if (scope === 'data') return sources.filter((source) => source?.group !== 'local');
  return sources;
}

function renderNavigation(connections, selectedId) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  const byId = new Map(sources.map((source) => [source.id, source]));
  return `<nav class="connection-source-list" aria-label="数据源连接">${normalizedGroups(connections).map((group) => {
    const items = groupSourceIds(group).map((item) => typeof item === 'string' ? byId.get(item) : item).filter(Boolean);
    if (!items.length) return '';
    return `<section class="connection-source-group"><h3>${e(group.label || group.name || group.id)}</h3>${items.map((source) => renderSourceButton(source, source.id === selectedId)).join('')}</section>`;
  }).join('')}</nav>`;
}

function renderConnectionSummary(sources) {
  const counts = sources.reduce((summary, source) => {
    summary[connectionStatusKey(source)] += 1;
    return summary;
  }, { connected: 0, pending: 0, attention: 0 });
  const items = [
    ['已连接', counts.connected, 'connected'],
    ['待配置', counts.pending, 'pending'],
    ['需处理', counts.attention, 'attention'],
    ['来源总数', sources.length, 'total'],
  ];
  return `<dl class="connection-summary" aria-label="数据源状态概览">${items.map(([label, value, kind]) => `<div class="connection-summary-item ${kind}"><dt><span aria-hidden="true"></span>${label}</dt><dd>${value}</dd></div>`).join('')}</dl>`;
}

function renderGroupTabs(connections, activeGroup) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  const available = new Set(sources.map((source) => source.group));
  const groups = normalizedGroups(connections).filter((group) => group.id !== 'local' && available.has(group.id));
  return `<div class="connection-group-tabs" role="tablist" aria-label="数据源分类">${groups.map((group) => `<button type="button" role="tab" id="connection-group-${e(group.id)}" data-connection-group="${e(group.id)}" aria-controls="connection-source-grid" aria-selected="${group.id === activeGroup}" tabindex="${group.id === activeGroup ? '0' : '-1'}">${e(group.label || group.name || group.id)}</button>`).join('')}</div>`;
}

function renderDataWorkbench(connections, selectedId, source, configuration, detailOpen) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  const selectedGroup = source?.group && source.group !== 'local' ? source.group : '';
  const activeGroup = selectedGroup || normalizedGroups(connections).find((group) => group.id !== 'local' && sources.some((item) => item.group === group.id))?.id || 'professional';
  const visibleCount = filterConnectionSources(sources, { group: activeGroup }).length;
  const detail = renderDetail(source, configuration, connections, { drawer: true });
  const renderedDetail = detailOpen ? detail : detail.replace(' data-connection-drawer', ' data-connection-drawer hidden');
  return `<div class="connection-workbench" data-connection-workbench data-active-group="${e(activeGroup)}">${renderConnectionSummary(sources)}<div class="connection-toolbar"><label class="connection-search"><span class="sr-only">搜索数据源</span><input type="search" data-connection-search placeholder="搜索数据源" autocomplete="off"></label><label class="connection-status-filter"><span class="sr-only">筛选连接状态</span><select data-connection-status><option value="all">全部状态</option><option value="connected">已连接</option><option value="pending">待配置</option><option value="attention">需处理</option></select></label><a class="button primary connection-add-source" href="#/skills?kind=data">添加数据源</a></div>${renderGroupTabs(connections, activeGroup)}<div class="connection-workbench-stage"><section class="connection-source-panel" aria-labelledby="connection-results-label"><div class="connection-results-heading"><p id="connection-results-label"><strong data-connection-result-count>${visibleCount}</strong> 个来源</p><p class="muted small" data-connection-search-scope hidden>正在跨全部分类搜索</p></div><div class="connection-card-grid" id="connection-source-grid" role="tabpanel" aria-labelledby="connection-group-${e(activeGroup)}">${sources.map((item) => renderSourceButton(item, item.id === selectedId, { card: true, visible: item.group === activeGroup })).join('')}</div><div class="connection-empty" data-connection-empty hidden><strong>没有匹配的数据源</strong><p class="muted small">尝试清除搜索词或调整状态筛选。</p></div></section>${renderedDetail}</div></div>`;
}

function field(label, name, value = '', options = {}) {
  const type = options.type || 'text';
  const hint = options.hint ? ` <span class="muted">${e(options.hint)}</span>` : '';
  return `<label>${e(label)}${hint}<input name="${e(name)}" type="${e(type)}" value="${type === 'password' ? '' : e(value)}" ${options.required ? 'required' : ''} ${options.min ? `min="${e(options.min)}"` : ''} ${options.max ? `max="${e(options.max)}"` : ''} autocomplete="${type === 'password' ? 'new-password' : 'off'}" ${options.placeholder ? `placeholder="${e(options.placeholder)}"` : ''}></label>`;
}

function selectField(label, name, options, current) {
  return `<label>${e(label)}<select name="${e(name)}">${options.map(([value, text]) => `<option value="${e(value)}" ${value === current ? 'selected' : ''}>${e(text)}</option>`).join('')}</select></label>`;
}

function formActions(source, configuration, { metered = false } = {}) {
  const removable = configuration?.configured || source?.actions?.includes?.('delete');
  return `<div class="button-row"><button class="button primary" type="submit">保存配置</button><button class="button" type="button" data-connection-cancel="${e(source.id)}">取消</button><button class="button danger" type="button" data-connection-remove="${e(source.id)}" ${removable ? '' : 'disabled'}>移除</button><button class="button" type="button" data-connection-probe="${e(source.id)}">${metered ? '检测（可能消耗额度）' : '检测连接'}</button></div>`;
}

function renderMysql(source, configuration) {
  const c = configuration || {};
  const warning = c.credential_store_available === false ? '<p class="notice error small">系统凭据库不可用或已锁定，不会降级保存明文密码。</p>' : '';
  return `${warning}<form class="connection-config-form" id="connection-config-mysql" data-connection-config="mysql" autocomplete="off"><div class="form-grid">${field('连接名称', 'label', c.label, { required: true, placeholder: '例如 阿里云因子库' })}${field('主机', 'host', c.host, { required: true, placeholder: '数据库主机名或 IP' })}${field('端口', 'port', c.port || 3306, { type: 'number', required: true, min: 1, max: 65535 })}${field('用户名', 'user', c.user, { required: true, placeholder: '只读账号' })}${field('密码', 'password', '', { type: 'password', hint: '（留空保留）', placeholder: '不会回填或复制' })}${selectField('字符集', 'charset', [['utf8mb4', 'utf8mb4'], ['utf8', 'utf8'], ['gbk', 'gbk']], c.charset || 'utf8mb4')}${selectField('TLS 模式', 'tls_mode', [['required_no_verify', '必须加密 · 不验证证书']], c.tls_mode || 'required_no_verify')}</div><p class="notice warning small">required_no_verify 会强制 TLS，但无法验证服务端证书身份。</p>${formActions(source, c)}</form>`;
}

function renderWind(source, configuration) {
  const c = configuration || {};
  return `<p class="muted">Wind 使用当前设备上的本机已登录会话，平台不保存 Wind 账号或密码。检测到组件不等于可调用，只有完成 DataHub 适配并通过探测后才会进入 Runtime。</p><form class="connection-config-form" data-connection-config="wind" autocomplete="off">${selectField('接入偏好', 'preferred_adapter', [['auto', '自动选择（auto）'], ['client_api', 'Wind Client API（client_api）'], ['excel', 'Wind Excel 插件（excel）']], c.preferred_adapter || 'auto')}<p class="small muted">Client API 会读取当前会话连接状态但不会代为登录；Excel 只有在提供真实工作簿心跳后才能验证，当前仅报告组件兼容性。</p>${formActions(source, c)}</form>`;
}

function renderAccountPool(source, configuration, kind) {
  const c = configuration || {};
  const accounts = Array.isArray(c.accounts) && c.accounts.length ? c.accounts : [{ id: 'primary', username: '' }];
  const backend = c.backend || c.preferred_adapter || 'auto';
  const isIFind = kind === 'ifind';
  const options = isIFind ? [['auto', '自动选择（auto）'], ['python_sdk', 'Python SDK（python_sdk）'], ['http_api', 'HTTP API（http_api）']] : [['auto', '自动选择（auto）']];
  return `<form class="connection-config-form" data-connection-config="${e(kind)}" autocomplete="off"><div class="section-heading compact"><div><h3>账号池</h3><p class="muted small">每个账号的密码独立保存在系统凭据库，读取接口只返回是否已配置。</p></div><button class="button small" type="button" data-account-add="${e(kind)}">添加账号</button></div><div class="connection-account-list">${accounts.map((account, index) => `<fieldset class="connection-account"><legend>账号 ${index + 1}</legend>${field('账号 ID', `accounts.${index}.id`, account.id || `account-${index + 1}`, { required: true })}${field('用户名', `accounts.${index}.username`, account.username, { required: true })}${field('密码', `accounts.${index}.password`, '', { type: 'password', hint: account.secret_configured ? '（已保存，留空保留）' : '（尚未保存）' })}</fieldset>`).join('')}</div>${isIFind ? selectField('接入方式', 'backend', options, backend) : ''}${isIFind ? field('HTTP 地址', 'http_base_url', c.http_base_url || '', { placeholder: '仅 http_api 使用' }) : ''}${formActions(source, c, { metered: true })}</form>`;
}

function renderToken(source, configuration) {
  const c = configuration || {};
  const label = tokenLabels[source.id] || 'API Key';
  return `<form class="connection-config-form" data-connection-config="${e(source.id)}" autocomplete="off">${field(label, tokenFields[source.id], '', { type: 'password', hint: c.secret_configured ? '（已保存，留空保留）' : '（留空保留）', placeholder: '仅本次提交使用' })}${formActions(source, c, { metered: ['tushare', 'tavily', 'bing'].includes(source.id) })}</form>`;
}

function renderIntegration(platform) {
  const items = ['excel_automation', 'wind_excel', 'ifind_excel', 'report_workflow'];
  return `<div class="local-integration-grid">${items.map((key) => {
    const item = platform?.[key] || { status: 'unverified' };
    return `<article><div class="section-heading compact"><h3>${e(item.label || integrationLabels[key])}</h3><span class="badge ${['available', 'healthy', 'ready'].includes(item.status) ? 'live' : ''}">${e(statusText[item.status] || item.status || '未知')}</span></div><p class="muted small">${e(item.message || item.detail || '状态由当前 8088 服务所在设备实际检测。')}</p></article>`;
  }).join('')}</div><p class="notice warning small">插件只有完成实际心跳或带真实工作簿探测后才会标记可用；操作系统能力按当前运行环境判断。</p>`;
}

function localOverallDiagnosis(source) {
  if (!source) return {
    title: '未发现本机能力定义',
    label: '需刷新',
    tone: 'neutral',
    description: '连接目录中没有返回本机能力。请刷新状态；若问题持续，请查看服务日志。',
  };
  if (source.callable === true) return {
    title: '本机工作流可用',
    label: '可调用',
    tone: 'ready',
    description: '当前服务设备已完成检测和接入，可供研究任务调用。',
  };
  if (source.integration_completed !== true) return {
    title: '尚未接入可调用链路',
    label: '尚未接入',
    tone: 'attention',
    description: '本机组件状态只说明设备环境；系统完成接入适配后，研究任务才能调用。',
  };
  if (['checking', 'queued'].includes(String(source.probe_status || source.health || ''))) return {
    title: '正在检测本机环境',
    label: '检测中',
    tone: 'pending',
    description: '正在读取当前服务设备的组件与工作流状态，完成后会自动刷新结果。',
  };
  if (!isProbed(source)) return {
    title: '等待检测',
    label: '待检测',
    tone: 'pending',
    description: '尚未运行本机环境探测。完成检测后会更新组件与工作流状态。',
  };
  return {
    title: '检测未通过',
    label: '需处理',
    tone: 'danger',
    description: '已完成环境探测，但至少一项条件仍未满足。请根据下方结果处理后重试。',
  };
}

function localComponentState(item = {}) {
  const status = String(item.status || 'unknown');
  const [label, tone, fallback] = localStatusDefinitions[status] || ['异常', 'danger', '服务返回了尚未识别的状态，请刷新或查看日志。'];
  const apiExplanation = [item.message, item.detail].find((value) => typeof value === 'string' && value.trim());
  return { label, tone, explanation: apiExplanation?.trim() || fallback };
}

function platformLabel(platform = {}) {
  const os = String(platform.os || '').toLocaleLowerCase();
  if (['darwin', 'macos', 'mac'].includes(os)) return 'macOS';
  if (['win32', 'windows', 'win'].includes(os)) return 'Windows';
  if (os === 'linux') return 'Linux';
  return '系统待识别';
}

function renderLocalSourceSwitcher(sources, selectedId) {
  if (sources.length < 2) return '';
  return `<nav class="local-source-switcher" aria-label="本机能力组">${sources.map((source) => `<button type="button" data-connection-select="${e(source.id)}" aria-pressed="${source.id === selectedId}" class="${source.id === selectedId ? 'selected' : ''}">${e(sourceName(source))}</button>`).join('')}</nav>`;
}

function renderLocalChecks(platform = {}) {
  return `<section class="local-checks" aria-labelledby="local-checks-title"><div class="local-section-heading"><div><p class="eyebrow">ENVIRONMENT CHECKS</p><h2 id="local-checks-title">本机环境检查</h2></div><p class="muted small">检测结果描述当前服务设备，不等同于研究任务已经可调用。</p></div><div class="local-check-table" role="table" aria-label="本机环境检测结果"><div class="local-check-header" role="row"><span role="columnheader">检测项</span><span role="columnheader">状态</span><span role="columnheader">具体说明</span></div>${localIntegrationKeys.map((key) => {
    const item = platform[key] || { status: 'unknown' };
    const state = localComponentState(item);
    return `<div class="local-check-row" role="row"><strong role="cell" data-label="检测项">${e(item.label || integrationLabels[key])}</strong><span role="cell" data-label="状态"><span class="local-status ${e(state.tone)}"><span aria-hidden="true"></span>${e(state.label)}</span></span><p role="cell" data-label="具体说明">${e(state.explanation)}</p></div>`;
  }).join('')}</div></section>`;
}

function renderLocalTechnicalDetails(source) {
  const state = sourceState(source);
  const stages = [
    ['服务已识别', state.configured, '服务目录已确认这组本机能力。', '服务目录尚未确认这组本机能力。'],
    ['完成环境检测', state.probed, '已从当前服务设备读取组件状态。', '尚未从当前服务设备完成环境探测。'],
    ['接入研究工作流', state.integrated, '检测结果已接入 Research Runtime 的本机工作流。', '环境证据尚未接入 Research Runtime 的可调用链路。'],
    ['可在研究任务中调用', state.callable, '研究任务可通过受控工具调用本机能力。', '研究任务当前不能调用这组本机能力。'],
  ];
  const completed = stages.filter(([, active]) => active).length;
  return `<details class="local-technical-details"><summary><span>接入详情</span><span class="muted small">${completed} / ${stages.length} 已完成</span></summary><ol class="local-stage-list">${stages.map(([label, active, completedCopy, pendingCopy], index) => `<li class="${active ? 'complete' : ''}"><span class="local-stage-marker" aria-hidden="true">${active ? '✓' : index + 1}</span><div><div class="local-stage-title"><strong>${e(label)}</strong><span>${active ? '已完成' : '未完成'}</span></div><p>${e(active ? completedCopy : pendingCopy)}</p></div></li>`).join('')}</ol></details>`;
}

function renderLocalDiagnostics(connections, sources, selectedId, busy) {
  const source = sources.find((item) => item.id === selectedId) || sources[0];
  const diagnosis = localOverallDiagnosis(source);
  const actions = Array.isArray(source?.actions) ? source.actions : [];
  const probe = actions.includes('probe') ? `<button class="button primary" type="button" data-connection-probe="${e(source.id)}" ${busy ? 'disabled aria-busy="true"' : ''}>${busy ? '检测中…' : '检测本机环境'}</button>` : '';
  const selector = renderLocalSourceSwitcher(sources, source?.id || '');
  const footer = '<a class="local-capability-link" href="#/skills?kind=data">查看可用数据能力 <span aria-hidden="true">→</span></a>';
  if (!source) return `${selector}<section class="local-diagnostics"><section class="local-diagnosis-card neutral" aria-live="polite"><div class="local-diagnosis-copy"><div class="local-diagnosis-meta"><span>总体结论</span><span class="local-status neutral"><span aria-hidden="true"></span>${e(diagnosis.label)}</span></div><h2>${e(diagnosis.title)}</h2><p>${e(diagnosis.description)}</p></div></section>${footer}</section>`;
  return `${selector}<section class="local-diagnostics"><section class="local-diagnosis-card ${e(diagnosis.tone)}" aria-labelledby="local-diagnosis-title" aria-live="polite"><div class="local-diagnosis-copy"><div class="local-diagnosis-meta"><span>总体结论</span><span class="local-status ${e(diagnosis.tone)}"><span aria-hidden="true"></span>${e(diagnosis.label)}</span></div><h2 id="local-diagnosis-title">${e(diagnosis.title)}</h2><p>${e(diagnosis.description)}</p><p class="local-device-label">当前服务设备 · ${e(platformLabel(connections?.platform))}</p></div>${probe ? `<div class="local-diagnosis-action">${probe}<span>重新检测会更新下方结果</span></div>` : ''}</section>${renderLocalChecks(connections?.platform)}${renderLocalTechnicalDetails(source)}${footer}</section>`;
}

function renderUnavailable(source) {
  const probe = Array.isArray(source.actions) && source.actions.includes('probe') ? `<button class="button" type="button" data-connection-probe="${e(source.id)}">检测状态</button>` : '';
  return `<p class="muted">${e(source.description || '当前只提供来源状态与诊断。')}</p>${source.integration_completed ? '' : '<p class="notice warning small">尚未适配 DataHub 查询边界。保存配置或检测成功都不会把它误标为可调用。</p>'}<div class="button-row">${probe}<a class="button" href="#/skills?kind=data">查看 DataHub 目录</a></div>`;
}

function renderDetail(source, configuration, connections, { drawer = false } = {}) {
  if (!source) return '<section class="connection-detail"><p class="muted">请选择一个数据源。</p></section>';
  let body;
  if (source.id === 'mysql') body = renderMysql(source, configuration);
  else if (source.id === 'wind') body = renderWind(source, configuration);
  else if (source.id === 'ifind') body = renderAccountPool(source, configuration, 'ifind');
  else if (zhiqiuSources.has(source.id)) body = renderAccountPool(source, configuration, source.id);
  else if (tokenLabels[source.id]) body = renderToken(source, configuration);
  else if (source.id === 'local_cache' || source.group === 'local') body = renderIntegration(connections?.platform);
  else body = renderUnavailable(source);
  const close = drawer ? '<button class="connection-detail-close" type="button" data-connection-detail-close aria-label="关闭数据源详情">×</button>' : '';
  return `<section class="connection-detail ${drawer ? 'connection-drawer' : ''}" ${drawer ? 'id="connection-detail" data-connection-drawer' : ''} aria-labelledby="connection-title"><header class="connection-detail-header"><div><p class="eyebrow">${e(authLabel(source))}</p><h2 id="connection-title" tabindex="-1">${e(sourceName(source))}</h2><p class="muted">${e(source.description || '')}</p></div>${close}</header>${renderStateMatrix(source)}${body}</section>`;
}

function renderMigration(migration, open) {
  if (!migration?.available) return '';
  const targets = Array.isArray(migration.targets) ? migration.targets : [];
  const review = open ? `<form class="migration-confirm" data-migration-confirm><fieldset><legend>选择迁移目标</legend>${targets.map((target) => {
    const id = typeof target === 'string' ? target : target.source_id;
    const label = typeof target === 'string' ? target : (target.label || target.source_id);
    return `<label><input type="checkbox" name="source_ids" value="${e(id)}">${e(label)}</label>`;
  }).join('')}</fieldset><label class="migration-confirm-check"><input type="checkbox" name="confirm" required>我确认将选中凭据写入系统凭据库，并在验证后从本地 .env 清除对应秘密。</label><div class="button-row"><button class="button primary" type="submit">确认迁移</button><button class="button" type="button" data-migration-cancel>取消</button></div></form>` : '';
  return `<section class="legacy-migration"><div><p class="eyebrow">旧配置迁移</p><h3>检测到可迁移的环境变量</h3><p class="muted small">预览只显示变量是否存在和目标来源，不读取或展示秘密值。迁移需要再次确认。</p></div><button class="button" type="button" data-migration-review aria-expanded="${Boolean(open)}">查看迁移</button>${review}</section>`;
}

export function selectedConnectionId(hash, sources = [], scope = 'all') {
  const query = String(hash || '').split('?')[1] || '';
  const requested = new URLSearchParams(query).get('connection');
  const available = scopedSources(sources, scope);
  return available.some((source) => source.id === requested) ? requested : (available[0]?.id || '');
}

export function buildConfigurationPayload(sourceId, values) {
  if (sourceId === 'mysql') {
    const payload = { label: trim(values, 'label'), host: trim(values, 'host'), port: Number(get(values, 'port')), user: trim(values, 'user'), charset: trim(values, 'charset'), tls_mode: trim(values, 'tls_mode') };
    const password = String(get(values, 'password') || '');
    if (password) payload.password = password;
    return payload;
  }
  if (sourceId === 'wind') return { preferred_adapter: trim(values, 'preferred_adapter') || 'auto' };
  if (tokenLabels[sourceId]) {
    const secretField = tokenFields[sourceId]; const token = trim(values, secretField);
    return token ? { [secretField]: token } : {};
  }
  if (sourceId === 'ifind' || zhiqiuSources.has(sourceId)) {
    const payload = { accounts: [] };
    if (sourceId === 'ifind') { payload.backend = trim(values, 'backend') || 'auto'; payload.http_base_url = trim(values, 'http_base_url') || null; }
    for (let index = 0; index < 20; index += 1) {
      const id = trim(values, `accounts.${index}.id`); const username = trim(values, `accounts.${index}.username`);
      if (!id && !username) continue;
      const account = { id, username }; const password = String(get(values, `accounts.${index}.password`) || '');
      if (password) account.password = password;
      payload.accounts.push(account);
    }
    return payload;
  }
  throw new Error('该来源不支持配置。');
}

export function renderConnectionCenter({ connections, selectedId, configuration, migrationOpen = false, detailOpen = true, scope = 'all', busy = false }) {
  const allSources = Array.isArray(connections?.sources) ? connections.sources : [];
  const sources = scopedSources(allSources, scope);
  const scopedConnections = { ...connections, sources };
  const resolved = sources.some((source) => source.id === selectedId) ? selectedId : (sources[0]?.id || '');
  const source = sources.find((item) => item.id === resolved);
  const local = scope === 'local';
  if (!local) return `<section class="connection-center" data-connection-scope="${e(scope)}" data-selected-connection="${e(resolved)}">${renderMigration(connections?.migration, migrationOpen)}${renderDataWorkbench(scopedConnections, resolved, source, configuration, detailOpen)}</section>`;
  return `<section class="connection-center local-connection-center" data-connection-scope="${e(scope)}" data-selected-connection="${e(resolved)}">${renderLocalDiagnostics(connections, sources, resolved, busy)}</section>`;
}
