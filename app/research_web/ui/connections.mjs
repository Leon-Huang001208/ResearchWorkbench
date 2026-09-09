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

function renderSourceButton(source, selected) {
  const [label, kind] = compactStatus(source);
  return `<button type="button" class="connection-source ${selected ? 'selected' : ''}" data-connection-select="${e(source.id)}" aria-pressed="${selected}"><span class="connection-source-copy"><strong>${e(sourceName(source))}</strong><small>${e(authLabel(source))}</small></span><span class="badge ${kind}">${e(label)}</span></button>`;
}

function groupSourceIds(group) { return group?.source_ids || group?.items || group?.sources || []; }

function normalizedGroups(connections) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  if (Array.isArray(connections?.groups) && connections.groups.length) return connections.groups;
  const groupOrder = [['professional', '专业数据源'], ['api', 'API 数据源'], ['public', '公开来源'], ['local', '本机集成']];
  return groupOrder.map(([id, label]) => ({ id, label, source_ids: sources.filter((source) => source.group === id).map((source) => source.id) }));
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

function renderUnavailable(source) {
  const probe = Array.isArray(source.actions) && source.actions.includes('probe') ? `<button class="button" type="button" data-connection-probe="${e(source.id)}">检测状态</button>` : '';
  return `<p class="muted">${e(source.description || '当前只提供来源状态与诊断。')}</p>${source.integration_completed ? '' : '<p class="notice warning small">尚未适配 DataHub 查询边界。保存配置或检测成功都不会把它误标为可调用。</p>'}<div class="button-row">${probe}<a class="button" href="#/skills?kind=data">查看 DataHub 目录</a></div>`;
}

function renderDetail(source, configuration, connections) {
  if (!source) return '<section class="connection-detail"><p class="muted">请选择一个数据源。</p></section>';
  let body;
  if (source.id === 'mysql') body = renderMysql(source, configuration);
  else if (source.id === 'wind') body = renderWind(source, configuration);
  else if (source.id === 'ifind') body = renderAccountPool(source, configuration, 'ifind');
  else if (zhiqiuSources.has(source.id)) body = renderAccountPool(source, configuration, source.id);
  else if (tokenLabels[source.id]) body = renderToken(source, configuration);
  else if (source.id === 'local_cache' || source.group === 'local') body = renderIntegration(connections?.platform);
  else body = renderUnavailable(source);
  return `<section class="connection-detail" aria-labelledby="connection-title"><header class="connection-detail-header"><div><p class="eyebrow">${e(authLabel(source))}</p><h2 id="connection-title">${e(sourceName(source))}</h2><p class="muted">${e(source.description || '')}</p></div></header>${renderStateMatrix(source)}${body}</section>`;
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

export function selectedConnectionId(hash, sources = []) {
  const query = String(hash || '').split('?')[1] || '';
  const requested = new URLSearchParams(query).get('connection');
  return sources.some((source) => source.id === requested) ? requested : (sources[0]?.id || '');
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

export function renderConnectionCenter({ connections, selectedId, configuration, migrationOpen = false }) {
  const sources = Array.isArray(connections?.sources) ? connections.sources : [];
  const resolved = sources.some((source) => source.id === selectedId) ? selectedId : (sources[0]?.id || '');
  const source = sources.find((item) => item.id === resolved);
  return `<section class="connection-center" data-selected-connection="${e(resolved)}"><div class="connection-center-heading"><div><p class="eyebrow">DATA CONNECTIONS</p><h2>数据源连接中心</h2><p class="muted">${sources.length} 个来源统一展示；配置、检测、适配与可调用分别核验。</p></div><a class="button" href="#/skills?kind=data">DataHub 目录</a></div>${renderMigration(connections?.migration, migrationOpen)}<div class="connection-center-layout">${renderNavigation(connections, resolved)}${renderDetail(source, configuration, connections)}</div></section>`;
}
