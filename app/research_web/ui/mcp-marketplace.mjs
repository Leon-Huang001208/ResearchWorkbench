import { escapeHTML as e } from './markdown.mjs';
import { empty } from './views.mjs';

const list = (value) => Array.isArray(value) ? value : [];
const text = (value, fallback = '未声明') => e(String(value ?? '').trim() || fallback);
const subviews = ['library', 'market', 'connections'];
const environmentName = /^[A-Za-z_][A-Za-z0-9_]{0,127}$/;

export function mcpMarketplaceTabKey(key, current = 'library') {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return { handled: false };
  const index = Math.max(0, subviews.indexOf(current));
  const next = key === 'Home' ? 0 : key === 'End' ? subviews.length - 1 : (index + (key === 'ArrowRight' ? 1 : -1) + subviews.length) % subviews.length;
  return { handled: true, view: subviews[next] };
}

export function packageSupport(packages = []) {
  const rows = list(packages);
  const types = [...new Set(rows.map(item => String(item?.registryType || item?.registry_type || '').toLowerCase()).filter(Boolean))];
  const unsupported = [...new Set(rows.filter(item => item?.package_type_supported !== true).map(item => String(item?.registryType || item?.registry_type || '未声明').toLowerCase()))];
  const clientSupported = rows.length > 0 && unsupported.length === 0;
  return {
    clientSupported,
    artifactVerified: clientSupported && rows.every(item => item?.immutable_reference === true),
    types,
    unsupported,
  };
}

export function mcpInstallSelection(item, target) {
  const match = /^(package|remote):(\d{1,2})$/.exec(String(target || ''));
  if (!match) throw new Error('installation_target_not_installable');
  const index = Number(match[2]);
  const base = {
    registry_id: String(item?.registry_id || ''),
    server_name: String(item?.name || ''),
    server_version: String(item?.version || ''),
  };
  if (!base.registry_id || !base.server_name || !base.server_version) throw new Error('installation_identity_invalid');
  if (match[1] === 'remote') {
    const remote = list(item?.remotes)[index];
    if (!remote || remote.type !== 'streamable-http') throw new Error('installation_target_not_installable');
    return { ...base, package_index: null, remote_index: index, environment_names: [] };
  }
  const selectedPackage = list(item?.packages)[index];
  if (!selectedPackage || selectedPackage.package_type_supported !== true || selectedPackage.immutable_reference !== true || selectedPackage.transport_type !== 'stdio') {
    throw new Error('installation_target_not_installable');
  }
  const names = list(selectedPackage.environment_variables).map(value => value?.name);
  if (names.some(name => typeof name !== 'string' || !environmentName.test(name)) || new Set(names).size !== names.length) {
    throw new Error('installation_environment_invalid');
  }
  return { ...base, package_index: index, remote_index: null, environment_names: names };
}

export function mcpEnvironmentPayload(fields, expectedNames, confirmed) {
  if (confirmed !== true) throw new Error('installation_confirmation_required');
  const expected = list(expectedNames).map(String);
  const rows = list(fields);
  if (new Set(expected).size !== expected.length || rows.length !== expected.length) throw new Error('installation_environment_values_invalid');
  const values = {};
  for (const field of rows) {
    const name = String(field?.name || '');
    const value = String(field?.value || '');
    if (!expected.includes(name) || Object.hasOwn(values, name) || !value || value.includes('\0')) throw new Error('installation_environment_values_invalid');
    values[name] = value;
  }
  if (Object.keys(values).some((name, index) => name !== expected[index])) {
    return Object.fromEntries(expected.map(name => [name, values[name]]));
  }
  return values;
}

function registryOptions(registries, selectedRegistryId) {
  return list(registries).map(registry => `<option value="${e(registry.id)}" ${registry.id === selectedRegistryId ? 'selected' : ''}>${text(registry.name, registry.id)}${registry.official ? ' · 官方' : ''}</option>`).join('');
}

function packageFacts(packages) {
  const rows = list(packages);
  if (!rows.length) return '<span>未声明包</span>';
  return rows.map(item => {
    const kind = item?.registryType || item?.registry_type || 'unknown';
    const identifier = item?.identifier || '未声明制品';
    const version = item?.version || item?.fileSha256 || item?.file_sha256 || '未声明版本';
    return `<span>${text(kind)} · ${text(identifier)} · ${text(version)}</span>`;
  }).join('');
}

function serverCard(item, stale, busy) {
  const support = packageSupport(item?.packages);
  const remoteSupported = list(item?.remotes).some(remote => remote?.type === 'streamable-http');
  const installable = support.artifactVerified || remoteSupported;
  const source = `${item?.registry_id || 'unknown'} · ${item?.name || 'unknown'} · ${item?.version || 'unknown'}`;
  const artifactStatus = support.artifactVerified ? '固定制品引用已登记 · 可生成安装预览'
    : remoteSupported ? 'Streamable HTTP 端点已登记 · 可生成连接预览'
      : '制品尚未验证 · 安装被禁用';
  const supportLabel = support.clientSupported ? '客户端支持包类型' : remoteSupported ? '支持远程连接' : '客户端暂不支持此包类型';
  return `<article class="mcp-server-card ${stale ? 'stale' : ''}"><header><div><span class="eyebrow">${text(source)}</span><h3>${text(item?.title, item?.name)}</h3></div><span class="badge ${installable ? 'live' : 'danger'}">${supportLabel}</span></header><p>${text(item?.description, '未提供说明')}</p><div class="mcp-package-facts">${packageFacts(item?.packages)}</div><p class="small muted">${artifactStatus}</p><footer><span class="small muted">${item?.is_latest === true ? '当前版本' : `版本 ${text(item?.version)}`}${stale ? ' · 离线缓存' : ''}</span><button type="button" class="button small" data-mcp-server-detail data-registry-id="${e(item?.registry_id)}" data-server-name="${e(item?.name)}" data-server-version="${e(item?.version)}" ${busy ? 'disabled' : ''}>查看详情</button></footer></article>`;
}

function publisherResult(result, error) {
  if (error) return `<div class="notice error" role="alert">${e(error)}</div>`;
  if (!result) return '<p class="muted small">粘贴经过审查的 server.json。预览与校验只生成外部命令，不会执行安装或发布。</p>';
  if (result.valid === false) {
    const issues = list(result.issues);
    return `<div class="notice error" role="alert"><strong>校验未通过</strong>${issues.length ? `<ul>${issues.map(issue => `<li>${text(issue.path)}：${text(issue.message)}</li>`).join('')}</ul>` : ''}</div>`;
  }
  const commands = result.argv || {};
  return `<div class="mcp-publisher-result" role="status"><p><strong>校验通过</strong>${result.sha256 ? ` · SHA-256 ${text(result.sha256)}` : ''}</p>${result.canonical_json ? `<pre>${text(result.canonical_json)}</pre>` : ''}<dl><div><dt>校验命令</dt><dd><code>${text(list(commands.validate).join(' '))}</code></dd></div><div><dt>发布命令</dt><dd><code>${text(list(commands.publish).join(' '))}</code></dd></div></dl><p class="muted small">executed = ${result.executed === true ? 'true' : 'false'}；请在外部官方 CLI 完成登录与发布。</p></div>`;
}

function approvalQueue(approvals, busy) {
  const pending = list(approvals).filter(item => item?.status === 'pending');
  if (!pending.length) return '';
  return `<section class="mcp-approval-queue" aria-labelledby="mcp-approval-title"><div><span class="eyebrow">HUMAN APPROVAL REQUIRED</span><h3 id="mcp-approval-title">待处理高风险调用</h3><p class="muted small">参数正文不会在此显示。批准仅适用于这一次、这一个会话和锁定的 schema。</p></div>${pending.map(item => `<article><div><strong>${text(item.tool_name)}</strong><small>${text(item.installation_id)} · ${text(item.version)}</small></div><div class="button-row"><button type="button" class="button small" data-mcp-approval-deny="${e(item.id)}" ${busy ? 'disabled' : ''}>拒绝</button><button type="button" class="button primary small" data-mcp-approval-approve="${e(item.id)}" ${busy ? 'disabled' : ''}>${busy === item.id ? '提交中…' : '批准本次调用'}</button></div></article>`).join('')}</section>`;
}

export function renderMCPPublisherHandoff({ source = '', result = null, resultSource, error = '', busy = false } = {}) {
  const visibleResult = resultSource === undefined || resultSource === source ? result : null;
  return `<details class="mcp-publisher-handoff"><summary>登记到 Registry（外部 CLI）</summary><div class="mcp-publisher-body"><label for="mcp-publisher-json">server.json</label><textarea id="mcp-publisher-json" data-mcp-publisher-source rows="8" spellcheck="false" placeholder="粘贴完整 server.json">${e(source)}</textarea><div class="button-row"><button type="button" class="button" data-mcp-publisher-action="validate" ${busy ? 'disabled' : ''}>校验 JSON</button><button type="button" class="button primary" data-mcp-publisher-action="preview" ${busy ? 'disabled' : ''}>生成外部命令</button></div>${publisherResult(visibleResult, error)}</div></details>`;
}

export function renderMCPMarketplace({ registries = [], selectedRegistryId = '', query = '', page = null, loading = false, syncing = false, error = '', runtimeAvailable = null, runtimeError = '', approvals = [], approvalBusy = '', publisher = {} } = {}) {
  const registryRows = list(registries);
  const selected = registryRows.some(item => item.id === selectedRegistryId) ? selectedRegistryId : registryRows[0]?.id || '';
  const items = list(page?.items);
  const stale = page?.stale === true;
  const status = stale
    ? `<div class="notice warning mcp-market-status" role="status">正在显示离线缓存${page?.failure_code ? ` · ${text(page.failure_code)}` : ''}。同步失败不会清空上次成功目录。</div>`
    : page?.fetched_at ? `<p class="mcp-market-status small muted" role="status">目录已同步 · ${text(page.fetched_at)}</p>` : '';
  const operationalError = error ? `<div class="notice error mcp-market-status" role="alert">${e(error)}<button type="button" class="button small" data-mcp-market-retry ${loading ? 'disabled' : ''}>重新读取</button></div>` : '';
  const runtimeNotice = runtimeAvailable === false
    ? `<div class="notice warning mcp-market-status" role="status">${text(runtimeError, 'MCP Runtime 当前不可用；仍可浏览 Registry。')}</div>`
    : runtimeAvailable === true ? '<p class="mcp-market-status small muted" role="status">Runtime 管理已就绪；安装、探测、启用与授权保持分离。</p>' : '';
  const results = loading && !page
    ? '<div class="loading-state" role="status">正在读取 MCP 目录…</div>'
    : items.length
      ? `<p class="capability-result-count" role="status">${Number.isFinite(Number(page?.count)) ? Number(page.count) : items.length} 项 Registry 记录</p><div class="mcp-market-grid">${items.map(item => serverCard(item, stale, loading || syncing)).join('')}</div>`
      : empty('没有匹配的 MCP Server', registryRows.length ? '调整 Registry 或搜索条件；目录不会补充演示内容。' : '当前没有可用 Registry；请检查功能开关或连接状态。');
  return `<section class="mcp-marketplace" aria-labelledby="mcp-market-title"><div class="capability-view-heading"><div><span class="eyebrow">MCP REGISTRY + RUNTIME</span><h2 id="mcp-market-title">MCP 市场</h2><p class="muted">浏览只读 Registry 的真实版本记录。安装、健康探测、Runtime 启用和研究授权相互独立。</p></div><button type="button" class="button" data-mcp-sync ${loading || syncing || !selected ? 'disabled' : ''}>${syncing ? '同步中…' : '同步当前目录'}</button></div><form class="mcp-market-toolbar" data-mcp-search><label for="mcp-market-registry"><span>Registry</span><select id="mcp-market-registry" data-mcp-registry ${loading || syncing || !registryRows.length ? 'disabled' : ''}>${registryOptions(registryRows, selected)}</select></label><label class="search-box"><span aria-hidden="true">⌕</span><input id="mcp-market-search" data-mcp-query type="search" value="${e(query)}" aria-label="搜索 MCP Server" placeholder="搜索 Server 名称或简介"></label><button type="submit" class="button" ${loading || syncing || !selected ? 'disabled' : ''}>搜索</button></form>${operationalError}${runtimeNotice}${approvalQueue(approvals, approvalBusy)}${status}${results}${renderMCPPublisherHandoff({ ...publisher, busy: publisher.busy || loading })}</section>`;
}

function installableTargets(item, installation) {
  const disabled = installation.runtimeAvailable === false || installation.busy || Boolean(installation.preview);
  const packages = list(item?.packages).flatMap((value, index) => {
    if (value?.package_type_supported !== true || value?.immutable_reference !== true || value?.transport_type !== 'stdio') return [];
    const selected = installation.target === `package:${index}`;
    return [`<label class="mcp-install-target ${selected ? 'selected' : ''}"><input type="radio" name="mcp-install-target" value="package:${index}" data-mcp-install-target ${selected ? 'checked' : ''} ${disabled ? 'disabled' : ''}><span><strong>本地 ${text(value.registry_type)}</strong><small>${text(value.identifier)} @ ${text(value.version)}</small></span></label>`];
  });
  const remotes = list(item?.remotes).flatMap((value, index) => {
    if (value?.type !== 'streamable-http') return [];
    const selected = installation.target === `remote:${index}`;
    return [`<label class="mcp-install-target ${selected ? 'selected' : ''}"><input type="radio" name="mcp-install-target" value="remote:${index}" data-mcp-install-target ${selected ? 'checked' : ''} ${disabled ? 'disabled' : ''}><span><strong>远程 Streamable HTTP</strong><small>${text(value.url)}</small></span></label>`];
  });
  return [...packages, ...remotes];
}

function formatBytes(value) {
  const size = Number(value);
  return Number.isSafeInteger(size) && size >= 0 ? `${size.toLocaleString('en-US')} B` : '未声明';
}

function exactList(values, emptyLabel = '无') {
  const rows = list(values);
  return rows.length ? `<ol class="mcp-exact-list">${rows.map(value => `<li><code>${text(value)}</code></li>`).join('')}</ol>` : `<span class="muted">${emptyLabel}</span>`;
}

function artifactTable(artifacts) {
  const rows = list(artifacts);
  if (!rows.length) return '<p class="muted small">远程连接不包含本地制品。</p>';
  return `<div class="mcp-artifact-table-wrap"><table class="mcp-artifact-table"><thead><tr><th>制品</th><th>固定版本</th><th>SHA-256</th><th>大小</th></tr></thead><tbody>${rows.map(artifact => `<tr><td><strong>${text(artifact?.name)}</strong><small>${text(artifact?.filename)}</small></td><td><code>${text(artifact?.version)}</code></td><td><code>${text(artifact?.sha256)}</code>${artifact?.integrity ? `<small>${text(artifact.integrity)}</small>` : ''}</td><td>${text(formatBytes(artifact?.size_bytes))}</td></tr>`).join('')}</tbody></table></div>`;
}

function environmentInputs(item, installation, plan) {
  const names = list(plan?.environment_names);
  if (!names.length) return '<p class="muted small">此目标不要求环境变量。</p>';
  const packageIndex = /^package:(\d+)$/.exec(installation.target || '')?.[1];
  const declarations = list(item?.packages)[Number(packageIndex)]?.environment_variables || [];
  return `<div class="mcp-environment-grid">${names.map(name => {
    const declaration = list(declarations).find(value => value?.name === name) || {};
    const secret = declaration.is_secret === true;
    return `<label><span><strong>${text(name)}</strong>${secret ? '<em>秘密</em>' : ''}</span>${declaration.description ? `<small>${text(declaration.description)}</small>` : ''}<input data-mcp-env-value data-mcp-env-name="${e(name)}" name="${e(name)}" type="${secret ? 'password' : 'text'}" autocomplete="off" spellcheck="false" required></label>`;
  }).join('')}</div>`;
}

function installStatusChain(installation) {
  const labels = {
    install: installation.installStatus === 'installed' ? '已安装' : installation.preview ? '待确认' : '未安装',
    probe: installation.probeStatus === 'ready' ? '已通过' : installation.probeStatus === 'failed' ? '失败' : '未执行',
    enable: installation.enableStatus === 'enabled' ? '已启用' : '未启用',
    authorization: installation.authorizationStatus === 'authorized' ? '已授权' : '未授权',
  };
  return `<ol class="mcp-install-status" aria-label="MCP 生命周期状态"><li class="${labels.install === '已安装' ? 'complete' : ''}"><span>1</span><div><strong>安装记录</strong><small>${labels.install}</small></div></li><li class="${labels.probe === '已通过' ? 'complete' : ''}"><span>2</span><div><strong>健康探测</strong><small>${labels.probe}</small></div></li><li class="${labels.enable === '已启用' ? 'complete' : ''}"><span>3</span><div><strong>运行时启用</strong><small>${labels.enable}</small></div></li><li class="${labels.authorization === '已授权' ? 'complete' : ''}"><span>4</span><div><strong>研究授权</strong><small>${labels.authorization}</small></div></li></ol>`;
}

function installPreview(item, installation) {
  const plan = installation.preview;
  if (!plan) return '';
  const local = plan.target_kind === 'local';
  const source = local ? plan.package_source : plan.endpoint;
  return `<form class="mcp-install-confirmation" data-mcp-install-form><div class="mcp-install-preview-heading"><div><span class="eyebrow">IMMUTABLE INSTALL PREVIEW</span><h3>核对完整安装摘要</h3></div><span class="badge">${local ? `本地 ${text(plan.package_type)}` : '远程 HTTPS'}</span></div>${installation.error ? `<div class="notice error" role="alert">${e(installation.error)}</div>` : ''}<dl class="mcp-install-facts"><div><dt>包 / 端点来源</dt><dd><code>${text(source)}</code></dd></div><div><dt>固定版本</dt><dd><code>${text(plan.package_version || plan.server_version)}</code></dd></div><div><dt>摘要 SHA-256</dt><dd><code>${text(plan.summary_sha256)}</code></dd></div></dl><section><h4>运行 argv（逐项原样展示）</h4>${exactList(plan.argv, '远程目标无本地 argv')}</section><section><h4>安装 argv（逐项原样展示）</h4>${exactList(plan.install_argv, '远程目标不执行本地安装命令')}</section><section><h4>全部已验证制品</h4>${artifactTable(plan.artifacts)}</section><section><h4>环境变量名称与本次值</h4><p class="muted small">值仅用于本次提交，不会回填、写入页面状态或日志。</p>${environmentInputs(item, installation, plan)}</section><label class="mcp-install-confirm-check"><input type="checkbox" data-mcp-install-confirm><span>我已核对完整命令、固定版本、来源、全部哈希和环境变量名称，并确认安装。安装完成后仍需单独探测、启用和授权。</span></label><div class="button-row"><button type="button" class="button" data-mcp-install-reset ${installation.busy ? 'disabled' : ''}>返回重选</button><button type="button" class="button primary" data-mcp-install-confirm-action ${installation.busy ? 'disabled' : ''}>${installation.busy === 'install' ? '安装中…' : '确认并安装'}</button></div></form>`;
}

function installedActions(installation) {
  if (installation.installStatus !== 'installed') return '';
  const id = installation.installationId;
  const enabled = installation.enableStatus === 'enabled';
  const remote = installation.record?.plan?.target_kind === 'remote';
  return `<div class="mcp-installed-actions"><p class="notice success" role="status">安装记录已保存。不会自动探测、启用或授予研究权限。</p><div class="button-row"><button type="button" class="button" data-mcp-install-probe="${e(id)}" ${installation.busy ? 'disabled' : ''}>${installation.busy === 'probe' ? '探测中…' : '运行健康探测'}</button>${enabled ? `<button type="button" class="button" data-mcp-install-disable="${e(id)}" ${installation.busy ? 'disabled' : ''}>${installation.busy === 'disable' ? '停用中…' : '停用 Runtime'}</button>` : `<button type="button" class="button primary" data-mcp-install-enable="${e(id)}" ${installation.busy || installation.probeStatus !== 'ready' ? 'disabled' : ''}>${installation.busy === 'enable' ? '启用中…' : '启用 Runtime'}</button>`}${remote ? `<button type="button" class="button" data-mcp-oauth-start="${e(id)}" ${installation.busy ? 'disabled' : ''}>${installation.busy === 'oauth' ? '准备授权…' : '连接 OAuth'}</button>` : ''}<button type="button" class="button danger" data-mcp-install-remove="${e(id)}" ${installation.busy || enabled ? 'disabled' : ''}>${installation.busy === 'remove' ? '移除中…' : '移除安装'}</button></div><p class="muted small">更新不可原地替换：请在 Registry 中选择新版本，重新核对完整预览并安装。已启用安装须先停用后移除。</p>${toolPolicies(installation)}</div>`;
}

function toolPolicies(installation) {
  const tools = list(installation.capabilities?.tools);
  if (!tools.length) return '<p class="muted small">健康探测后显示工具、schema 哈希和风险授权。</p>';
  const canAuthorize = installation.enableStatus === 'enabled' && Boolean(installation.currentSessionId);
  return `<section class="mcp-tool-policies" aria-labelledby="mcp-tool-policy-title"><div><h3 id="mcp-tool-policy-title">工具风险与当前会话授权</h3><p class="muted small">第三方声明不能降低风险；策略变化会暂停旧授权。外部写入与高风险工具每次调用仍需人工批准。</p></div>${tools.map(tool => {
    const name = String(tool?.name || '');
    const risk = ['read_only', 'private_data', 'external_write_high_risk'].includes(tool?.risk_tier) ? tool.risk_tier : 'external_write_high_risk';
    const busy = installation.busy === `classify:${name}` || installation.busy === `authorize:${name}`;
    const describedBy = `mcp-tool-${e(name)}-reason`;
    return `<article class="mcp-tool-policy"><header><div><strong>${text(name)}</strong><small>${text(tool?.description, '未提供说明')}</small></div><code>${text(tool?.schema_sha256)}</code></header><form data-mcp-tool-policy="${e(name)}"><label><span>风险等级</span><select name="risk_tier" data-mcp-risk-select ${installation.busy ? 'disabled' : ''}><option value="read_only" ${risk === 'read_only' ? 'selected' : ''}>只读</option><option value="private_data" ${risk === 'private_data' ? 'selected' : ''}>私有数据</option><option value="external_write_high_risk" ${risk === 'external_write_high_risk' ? 'selected' : ''}>外部写入 / 高风险</option></select></label><label class="mcp-unattended"><input type="checkbox" name="allow_unattended" ${tool?.allow_unattended === true ? 'checked' : ''} ${risk !== 'read_only' || installation.busy ? 'disabled' : ''}><span>允许无人值守只读调用</span></label><button type="submit" class="button small" ${installation.busy ? 'disabled' : ''}>${busy && installation.busy.startsWith('classify:') ? '保存中…' : '保存分级'}</button></form><div class="button-row"><button type="button" class="button small" data-mcp-authorize-tool="${e(name)}" ${busy || !canAuthorize || tool?.authorized === true ? 'disabled' : ''} aria-describedby="${describedBy}">${tool?.authorized === true ? '当前会话已授权' : busy && installation.busy.startsWith('authorize:') ? '授权中…' : '授权当前研究会话'}</button></div><p id="${describedBy}" class="muted small">${canAuthorize ? '授权锁定当前安装版本、工具名与 schema 哈希。' : '需先启用 Runtime，并打开或创建一个研究会话。'}</p></article>`;
  }).join('')}</section>`;
}

export function renderMCPServerDialog(item, installation = {}) {
  if (!item) return '';
  const support = packageSupport(item.packages);
  const identity = list(item.identity).length === 3 ? item.identity : [item.registry_id, item.name, item.version];
  const remoteFacts = list(item.remotes).map(remote => `${remote?.type || 'remote'} · ${remote?.url || '未声明地址'}`);
  const repository = typeof item.repository === 'object' ? item.repository?.url || item.repository?.source : item.repository;
  const targets = installableTargets(item, installation);
  const remoteSupported = list(item.remotes).some(remote => remote?.type === 'streamable-http');
  const freshness = item.stale === true
    ? `<div class="notice warning mcp-market-status" role="status">正在显示详情离线缓存${item.failure_code ? ` · ${text(item.failure_code)}` : ''}。版本详情刷新失败，页面目录的新鲜状态不适用于此记录。</div>`
    : '';
  const supportReason = remoteSupported && !support.artifactVerified
    ? '客户端支持此 Streamable HTTP 远程目标；连接前仍需核对端点与授权。'
    : !support.clientSupported
    ? `客户端暂不支持此包类型${support.unsupported.length ? `：${support.unsupported.map(value => text(value)).join('、')}` : '：没有受支持的包声明'}`
    : support.artifactVerified
      ? '客户端支持此包类型；存在已审查的固定安装目标。'
      : '客户端支持此包类型，但没有可安装的不可变目标。';
  const runtimeUnavailable = installation.runtimeAvailable === false
    ? '<p id="mcp-runtime-unavailable" class="notice warning">MCP Runtime 功能开关尚未启用；当前只能浏览 Registry 详情。</p>' : '';
  const targetSection = installation.installStatus === 'installed' ? '' : `${runtimeUnavailable}<fieldset class="mcp-install-targets"><legend>选择一个已审查目标</legend>${targets.length ? targets.join('') : '<p id="mcp-install-unavailable" class="notice warning">此版本没有客户端可安装的固定本地包或 Streamable HTTP 目标。</p>'}</fieldset>`;
  const previewButton = targets.length && !installation.preview && installation.installStatus !== 'installed'
    ? `<button type="button" class="button primary" data-mcp-install-preview ${installation.runtimeAvailable !== false && installation.target && !installation.busy ? '' : 'disabled'}>${installation.busy === 'preview' ? '解析中…' : '生成完整安装预览'}</button>`
    : !targets.length ? '<button type="button" class="button primary" disabled aria-describedby="mcp-install-unavailable">安装不可用</button>' : '';
  return `<div class="capability-dialog-backdrop" data-mcp-dialog-backdrop><section class="capability-preview-dialog mcp-server-dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-server-dialog-title" aria-describedby="mcp-server-dialog-description"><header><span class="skill-icon" aria-hidden="true">M</span><div><span class="eyebrow">${text(identity.join(' · '))}</span><h2 id="mcp-server-dialog-title">${text(item.title, item.name)}</h2><span class="badge ${targets.length ? 'live' : 'danger'}">${targets.length ? '存在已审查安装目标' : '没有可安装目标'}</span></div><button type="button" class="icon-button" data-mcp-detail-close aria-label="关闭 MCP Server 详情">×</button></header>${freshness}<p id="mcp-server-dialog-description" class="capability-preview-description">${text(item.description, '未提供说明')}</p><dl class="capability-preview-grid"><div><dt>来源身份</dt><dd>${text(identity.join(' · '))}</dd></div><div><dt>版本状态</dt><dd>${text(item.status)}${item.is_latest === true ? ' · 当前版本' : ''}</dd></div><div><dt>包与制品</dt><dd>${packageFacts(item.packages)}</dd></div><div><dt>远程传输</dt><dd>${remoteFacts.length ? remoteFacts.map(value => text(value)).join('<br>') : '未声明'}</dd></div><div><dt>源码仓库</dt><dd>${text(repository)}</dd></div><div><dt>支持与验证</dt><dd>${supportReason}</dd></div></dl>${installStatusChain(installation)}${installation.error && !installation.preview ? `<div class="notice error" role="alert">${e(installation.error)}</div>` : ''}${targetSection}${installPreview(item, installation)}${installedActions(installation)}<footer><button type="button" class="button" data-mcp-detail-close>关闭</button>${previewButton}</footer></section></div>`;
}
