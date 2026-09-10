import { escapeHTML as e } from './markdown.mjs';
import { empty } from './views.mjs';

const knownPackageTypes = new Set(['npm', 'pypi', 'mcpb']);
const list = (value) => Array.isArray(value) ? value : [];
const text = (value, fallback = '未声明') => e(String(value ?? '').trim() || fallback);
const subviews = ['library', 'market', 'connections'];

export function mcpMarketplaceTabKey(key, current = 'library') {
  if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(key)) return { handled: false };
  const index = Math.max(0, subviews.indexOf(current));
  const next = key === 'Home' ? 0 : key === 'End' ? subviews.length - 1 : (index + (key === 'ArrowRight' ? 1 : -1) + subviews.length) % subviews.length;
  return { handled: true, view: subviews[next] };
}

export function packageSupport(packages = []) {
  const rows = list(packages);
  const types = [...new Set(rows.map(item => String(item?.registryType || item?.registry_type || '').toLowerCase()).filter(Boolean))];
  const unsupported = types.filter(type => !knownPackageTypes.has(type));
  return {
    installable: rows.length > 0 && unsupported.length === 0,
    types,
    unsupported,
  };
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
  const source = `${item?.registry_id || 'unknown'} · ${item?.name || 'unknown'} · ${item?.version || 'unknown'}`;
  return `<article class="mcp-server-card ${stale ? 'stale' : ''}"><header><div><span class="eyebrow">${text(source)}</span><h3>${text(item?.title, item?.name)}</h3></div><span class="badge ${support.installable ? 'live' : ''}">${support.installable ? '支持安装' : '当前不可安装'}</span></header><p>${text(item?.description, '未提供说明')}</p><div class="mcp-package-facts">${packageFacts(item?.packages)}</div><footer><span class="small muted">${item?.is_latest === true ? '当前版本' : `版本 ${text(item?.version)}`}${stale ? ' · 离线缓存' : ''}</span><button type="button" class="button small" data-mcp-server-detail data-registry-id="${e(item?.registry_id)}" data-server-name="${e(item?.name)}" data-server-version="${e(item?.version)}" ${busy ? 'disabled' : ''}>查看详情</button></footer></article>`;
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

export function renderMCPPublisherHandoff({ source = '', result = null, error = '', busy = false } = {}) {
  return `<details class="mcp-publisher-handoff"><summary>登记到 Registry（外部 CLI）</summary><div class="mcp-publisher-body"><label for="mcp-publisher-json">server.json</label><textarea id="mcp-publisher-json" data-mcp-publisher-source rows="8" spellcheck="false" placeholder="粘贴完整 server.json">${e(source)}</textarea><div class="button-row"><button type="button" class="button" data-mcp-publisher-action="validate" ${busy ? 'disabled' : ''}>校验 JSON</button><button type="button" class="button primary" data-mcp-publisher-action="preview" ${busy ? 'disabled' : ''}>生成外部命令</button></div>${publisherResult(result, error)}</div></details>`;
}

export function renderMCPMarketplace({ registries = [], selectedRegistryId = '', query = '', page = null, loading = false, syncing = false, error = '', publisher = {} } = {}) {
  const registryRows = list(registries);
  const selected = registryRows.some(item => item.id === selectedRegistryId) ? selectedRegistryId : registryRows[0]?.id || '';
  const items = list(page?.items);
  const stale = page?.stale === true;
  const status = stale
    ? `<div class="notice warning mcp-market-status" role="status">正在显示离线缓存${page?.failure_code ? ` · ${text(page.failure_code)}` : ''}。同步失败不会清空上次成功目录。</div>`
    : page?.fetched_at ? `<p class="mcp-market-status small muted" role="status">目录已同步 · ${text(page.fetched_at)}</p>` : '';
  const operationalError = error ? `<div class="notice error mcp-market-status" role="alert">${e(error)}<button type="button" class="button small" data-mcp-market-retry ${loading ? 'disabled' : ''}>重新读取</button></div>` : '';
  const results = loading && !page
    ? '<div class="loading-state" role="status">正在读取 MCP 目录…</div>'
    : items.length
      ? `<p class="capability-result-count" role="status">${Number.isFinite(Number(page?.count)) ? Number(page.count) : items.length} 项 Registry 记录</p><div class="mcp-market-grid">${items.map(item => serverCard(item, stale, loading || syncing)).join('')}</div>`
      : empty('没有匹配的 MCP Server', registryRows.length ? '调整 Registry 或搜索条件；目录不会补充演示内容。' : '当前没有可用 Registry；请检查功能开关或连接状态。');
  return `<section class="mcp-marketplace" aria-labelledby="mcp-market-title"><div class="capability-view-heading"><div><span class="eyebrow">READ-ONLY MCP REGISTRY</span><h2 id="mcp-market-title">MCP 市场</h2><p class="muted">浏览官方与私有 Registry 的真实版本记录。安装、启用和研究授权将在后续阶段独立完成。</p></div><button type="button" class="button" data-mcp-sync ${loading || syncing || !selected ? 'disabled' : ''}>${syncing ? '同步中…' : '同步当前目录'}</button></div><form class="mcp-market-toolbar" data-mcp-search><label><span>Registry</span><select data-mcp-registry ${loading || syncing || !registryRows.length ? 'disabled' : ''}>${registryOptions(registryRows, selected)}</select></label><label class="search-box"><span aria-hidden="true">⌕</span><input id="mcp-market-search" data-mcp-query type="search" value="${e(query)}" aria-label="搜索 MCP Server" placeholder="搜索 Server 名称或简介"></label><button type="submit" class="button" ${loading || syncing || !selected ? 'disabled' : ''}>搜索</button></form>${operationalError}${status}${results}${renderMCPPublisherHandoff({ ...publisher, busy: publisher.busy || loading })}</section>`;
}

export function renderMCPServerDialog(item) {
  if (!item) return '';
  const support = packageSupport(item.packages);
  const identity = list(item.identity).length === 3 ? item.identity : [item.registry_id, item.name, item.version];
  const remoteFacts = list(item.remotes).map(remote => `${remote?.type || 'remote'} · ${remote?.url || '未声明地址'}`);
  const repository = typeof item.repository === 'object' ? item.repository?.url || item.repository?.source : item.repository;
  return `<div class="capability-dialog-backdrop" data-mcp-dialog-backdrop><section class="capability-preview-dialog mcp-server-dialog" role="dialog" aria-modal="true" aria-labelledby="mcp-server-dialog-title" aria-describedby="mcp-server-dialog-description"><header><span class="skill-icon" aria-hidden="true">M</span><div><span class="eyebrow">${text(identity.join(' · '))}</span><h2 id="mcp-server-dialog-title">${text(item.title, item.name)}</h2><span class="badge ${support.installable ? 'live' : 'danger'}">${support.installable ? '支持安装' : '当前不可安装'}</span></div><button type="button" class="icon-button" data-mcp-detail-close aria-label="关闭 MCP Server 详情">×</button></header><p id="mcp-server-dialog-description" class="capability-preview-description">${text(item.description, '未提供说明')}</p><dl class="capability-preview-grid"><div><dt>来源身份</dt><dd>${text(identity.join(' · '))}</dd></div><div><dt>版本状态</dt><dd>${text(item.status)}${item.is_latest === true ? ' · 当前版本' : ''}</dd></div><div><dt>包与制品</dt><dd>${packageFacts(item.packages)}</dd></div><div><dt>远程传输</dt><dd>${remoteFacts.length ? remoteFacts.map(value => text(value)).join('<br>') : '未声明'}</dd></div><div><dt>源码仓库</dt><dd>${text(repository)}</dd></div><div><dt>可安装性</dt><dd>${support.installable ? 'Registry 声明的包类型受支持；此阶段仅浏览，不执行安装。' : `当前不可安装${support.unsupported.length ? `：不支持 ${support.unsupported.map(value => text(value)).join('、')}` : '：没有可验证的包声明'}`}</dd></div></dl><footer><button type="button" class="button" data-mcp-detail-close>关闭</button><button type="button" class="button primary" disabled aria-describedby="mcp-install-unavailable">安装</button><span id="mcp-install-unavailable" class="visually-hidden">只读 Registry 阶段不执行安装</span></footer></section></div>`;
}
