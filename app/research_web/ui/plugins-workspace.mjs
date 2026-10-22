/** Capability-center Plugin controls. Secrets stay in form DOM for one request. */
import { escapeHTML as e } from './markdown.mjs';

const list = value => Array.isArray(value) ? value : [];
const support = { supported: '支持', limited: '有限支持', unsupported: '不支持' };
const reasons = {mcp_managed_local_process_isolation_required:'受管本地 MCP 缺少操作系统进程隔离，保持停用；可使用固定远程端点',review_required:'等待本版本权限审核',native_discovery_pending:'等待 DSH 确认发现原生能力',native_preview_confirmation_required:'等待原生安装预览与确认',native_tool_session_authorization_required:'实际工具仍需当前会话授权',native_validation_failed:'未通过现有能力校验',component_path_missing:'声明的组件路径不存在',component_declaration_unsupported:'组件声明格式尚未适配',host_hook_scripts_require_os_sandbox_and_event_review:'当前宿主 Hook 尚未适配，保持停用',hook_semantics_unsupported:'此 Hook 事件或行为尚未适配',os_sandbox_unavailable:'当前平台缺少操作系统沙箱，保持停用',macos_seatbelt_shell_builtins_only:'macOS 沙箱 Shell 子集，禁网络与外部进程',host_specific_extension:'宿主专用扩展尚未适配',host_execution_or_configuration_unsupported:'宿主执行或配置变更尚未适配',native_registry_selection_required:'需要映射到原生固定版本 Registry 安装',plugin_instruction_semantics_unsupported:'指令含未适配的宿主权限或执行语法'};
const button = (action, label, busy, extra = '') => `<button type="button" class="button${action === 'uninstall' ? ' danger-outline' : ''}" data-plugin-action="${action}" ${busy ? 'disabled' : ''} ${extra}>${label}</button>`;

export function renderPluginWorkspace(state) {
  const item = state.items.find(row => row.digest === state.selected);
  const admin = !state.user || state.user.role === 'admin';
  const busy = state.busy;
  const runtime = state.runtimeItems.find(row => row.digest === item?.digest);
  const projected = runtime || item;
  const grants = list(item?.permissions);
  const allGranted = grants.every(grant => state.grants.has(grant));
  const mcp = list(projected?.components).filter(component => component.kind === 'mcp' && component.selection);
  const selectedMCP = mcp.find(component => component.key === state.mcpKey) || mcp[0];
  const localMCPBlocked = selectedMCP?.selection?.package_index != null;
  const tools = list(state.mcpSnapshot?.capabilities?.tools);
  return `<section class="plugin-workspace" aria-label="插件管理" aria-busy="${Boolean(busy)}">
    <div class="section-heading"><div><h2>插件</h2><p class="muted">固定版本与内容摘要审核后，复用现有 DSH、Skill、Workflow 和 MCP。账号与密钥属于当前用户。</p></div>${button('reload', busy ? '处理中…' : '刷新插件状态', busy)}</div>
    ${state.user ? `<div class="button-row"><label>审批范围 <select data-plugin-scope ${busy ? 'disabled' : ''}><option value="shared" ${state.scope === 'shared' ? 'selected' : ''}>管理员共享</option><option value="personal" ${state.scope === 'personal' ? 'selected' : ''}>当前用户个人</option></select></label>${button('refresh-runtime', '空闲时应用到当前实例', busy)}</div>` : ''}
    <p role="status" aria-live="polite" class="muted">${e(state.message || '')}</p>${state.error ? `<p role="alert" class="notice error">${e(state.error)}</p>` : ''}
    ${admin ? `<form data-plugin-import class="plugin-import"><label>导入固定版本插件 ZIP <input name="file" type="file" accept=".zip,application/zip" ${busy ? 'disabled' : ''}></label>${state.file ? `<span class="muted">已选择：${e(state.file.name)}</span>` : ''}<button class="button primary" type="submit" ${busy ? 'disabled' : ''}>安全预览，不执行代码</button></form>` : '<p class="muted">仅管理员可导入、审核和分发插件。你可以查看支持状态，并为已批准的 MCP 配置自己的凭据与会话授权。</p>'}
    <div class="plugin-layout"><nav aria-label="插件版本" class="plugin-versions">${state.items.length ? state.items.map(row => `<button type="button" class="plugin-version ${row.digest === state.selected ? 'selected' : ''}" data-plugin-select="${e(row.digest)}" ${busy ? 'disabled' : ''}><strong>${e(row.name)}</strong><span>v${e(row.version)} · ${row.enabled ? (state.user ? '批准分发' : '已启用投影') : row.state === 'superseded' ? '旧会话保留' : row.review ? '已审核' : '待审核'}</span><small>${e(row.digest.slice(0, 16))}</small></button>`).join('') : '<p class="muted">尚无插件。导入后可逐项查看权限与不支持的组件。</p>'}</nav>
    <div class="plugin-detail">${item ? `<h3>${e(item.name)} <span class="muted">v${e(item.version)}</span></h3><p class="plugin-digest">SHA-256 ${e(item.digest)}</p><p class="muted">${runtime ? '以下就绪状态来自当前 Host。' : state.user ? '此版本是审批仓记录，尚未在当前 Host 发现。' : '发布投影与 DSH 发现分开记录；下一次研究会话会核对原生加载。'}</p>
      <table class="plugin-components"><thead><tr><th>组件</th><th>兼容程度</th><th>当前执行状态</th></tr></thead><tbody>${list(projected.components).map(component => `<tr><td>${e(component.kind)} / ${e(component.key)}</td><td>${e(support[component.support] || '未知')}</td><td><span data-plugin-reason="${e(component.reason || '')}">${component.ready ? 'Host 已加载并授权' : e(reasons[component.reason] || component.reason || '尚未就绪')}</span>${component.issues?.length ? `<ul>${component.issues.map(issue => `<li>${e(issue.code)}：${e(issue.message)}</li>`).join('')}</ul>` : ''}</td></tr>`).join('')}</tbody></table>
      <details><summary>检查原始文件与内容摘要（${list(item.file_inventory).length} 个）</summary><ul class="plugin-files">${list(item.file_inventory).map(file => `<li><a href="${e(state.sourcePrefix + '/' + item.digest + '/files/' + file.path.split('/').map(encodeURIComponent).join('/'))}" download>${e(file.path)}</a> · ${file.bytes} B <code>${e(file.sha256)}</code></li>`).join('')}</ul></details>
      ${admin ? `<fieldset ${busy ? 'disabled' : ''}><legend>本版本请求的权限</legend>${grants.map((grant, index) => `<label class="plugin-grant"><input type="checkbox" data-plugin-grant="${index}" ${state.grants.has(grant) ? 'checked' : ''}> <code>${e(grant)}</code></label>`).join('') || '<p>此包没有可执行组件权限。</p>'}<div class="button-row">${button('select-grants', '选择本版本全部权限', busy)}${button('review', '审核并授权所选权限', busy || !allGranted)}</div><p class="muted">授权绑定本包摘要与全部权限。版本、脚本、依赖或新权限变化需要重新审核；安装不会运行包内安装脚本。</p></fieldset>
      <div class="button-row">${button('enable', state.items.some(row => row.name === item.name && row.enabled && row.digest !== item.digest) ? '回滚到此已审版本' : '启用此已审版本', busy || !item.review)}${button('disable', '撤权并停用', busy || !(item.approved_for_sessions || item.enabled))}${button('uninstall', '卸载本版本', busy)}</div>` : ''}
      ${mcp.length ? `<hr><h3>此插件的 MCP</h3><label>组件 <select data-plugin-mcp ${busy ? 'disabled' : ''}>${mcp.map(component => `<option value="${e(component.key)}" ${component.key === selectedMCP?.key ? 'selected' : ''}>${e(component.key)}</option>`).join('')}</select></label><p class="muted">包审批、原生安装确认、实际字节/schema 审批、启用和会话授权各自保留。受管本地 MCP 因缺少操作系统进程隔离保持停用；固定远程端点可继续原生审核流程。服务器 OAuth 回调尚未适配；需要 OAuth 的连接保持未就绪。</p><div class="button-row">${button('mcp-preview', '生成原生安装预览', busy || localMCPBlocked || !item.review)}${button('mcp-probe', '探测已安装组件', busy || localMCPBlocked)}${button('mcp-status', '查看当前工具与审批快照', busy)}${button('mcp-enable', '空闲时启用 MCP', busy || localMCPBlocked)}${button('mcp-disable', '停用 MCP', busy)}</div>
      ${state.mcpPreview && !localMCPBlocked ? `<form data-plugin-mcp-install><h4>确认此固定安装计划</h4><pre>${e(JSON.stringify(state.mcpPreview.plan, null, 2))}</pre>${list(state.mcpPreview.plan?.environment_names).map(name => `<label>${e(name)} <input type="password" name="${e(name)}" autocomplete="off" required ${busy ? 'disabled' : ''}></label>`).join('')}<button class="button primary" type="submit" ${busy ? 'disabled' : ''}>确认原生安装</button></form>` : ''}
      ${state.mcpSnapshot ? `<h4>实际安装与工具快照</h4><pre>${e(JSON.stringify(state.mcpSnapshot.fingerprint, null, 2))}</pre>${!state.user && admin ? button('mcp-review', '审核并锁定这份工具 schema', busy) : ''}${tools.map(tool => `<article class="plugin-tool"><strong>${e(tool.name)}</strong><p>${e(tool.description || '')}</p><code>${e(tool.schema_sha256 || 'schema 尚未登记')}</code>${admin ? `<label>人工风险分类 <select data-plugin-risk="${e(tool.name)}" ${busy ? 'disabled' : ''}>${['read_only', 'private_data', 'external_write_high_risk'].map(risk => `<option value="${risk}" ${tool.risk_tier === risk ? 'selected' : ''}>${risk}</option>`).join('')}</select></label>${button('mcp-classify', '保存此工具风险分类', busy, `data-tool="${e(tool.name)}"`)}` : ''}<form data-plugin-authorize data-tool="${e(tool.name)}"><label>授权到已有会话 <select name="session_id" required ${busy ? 'disabled' : ''}><option value="">选择当前用户的研究会话</option>${state.sessions.map(session => `<option value="${e(session.id)}">${e(session.title || session.id)}</option>`).join('')}</select></label><button class="button" type="submit" ${busy || !tool.schema_sha256 ? 'disabled' : ''}>授予这个会话的固定工具权限</button></form></article>`).join('')}` : ''}` : ''}
    ` : ''}</div></div>
    ${state.user?.role === 'admin' ? `<section><h3>待审的个人 MCP 实际快照</h3>${state.pending.map(review => `<article class="plugin-tool"><p>用户 ${e(review.owner)} · 组件 ${e(review.component)}</p><pre>${e(JSON.stringify(review.snapshot, null, 2))}</pre>${button('approve-native', '批准这份固定快照', busy, `data-review="${e(review.id)}"`)}</article>`).join('') || '<p class="muted">暂无待审快照。用户探测组件后，由服务器生成锁定用户和安装的待审记录。</p>'}</section>` : ''}
  </section>`;
}

export function createPluginWorkspace({ root, user = null, fetcher = globalThis.fetch.bind(globalThis), logger = () => {} } = {}) {
  const state = { user, scope: 'shared', items: [], runtimeItems: [], sessions: [], pending: [], selected: '', grants: new Set(), busy: false, error: '', message: '', mcpKey: '', mcpPreview: null, mcpSnapshot: null, sourcePrefix: '', file: null };
  let panel = null, loaded = false, epoch = 0;
  const sourcePrefix = () => user ? `/api/server/plugins/${state.scope}` : '/api/research/plugins';
  const selected = () => state.items.find(item => item.digest === state.selected);
  const mcpKey = () => state.mcpKey || list((state.runtimeItems.find(item => item.digest === state.selected) || selected())?.components).find(component => component.kind === 'mcp' && component.selection)?.key;
  function paint() { if (panel?.isConnected) { state.sourcePrefix = sourcePrefix(); panel.innerHTML = renderPluginWorkspace(state); } }
  async function request(path, method = 'GET', body) {
    const abort = new AbortController();
    const timer = setTimeout(() => abort.abort(), 180000);
    const form = body instanceof FormData;
    try {
      const response = await fetcher(path, { method, credentials: 'same-origin', cache: 'no-store', signal: abort.signal, headers: { ...(user ? { 'X-RWB-Page-User': user.id } : {}), ...(!form && body !== undefined ? { 'Content-Type': 'application/json' } : {}) }, ...(body !== undefined ? { body: form ? body : JSON.stringify(body) } : {}) });
      const value = await response.json();
      if (!response.ok) throw Object.assign(new Error(value?.error?.message || value?.reason || value?.error?.code || `请求未完成（${response.status}）`), { code: value?.error?.code || value?.status || 'plugin_request_failed' });
      return value;
    } catch (error) {
      logger('plugin_workspace_request_failed', { method, code: error.code || 'network_unknown' });
      if (error.code) throw error;
      throw new Error('请求结果尚未确认。请刷新状态核实；系统不会自动重试安装或授权。');
    } finally { clearTimeout(timer); }
  }
  async function load() {
    const results = await Promise.allSettled([request(sourcePrefix()), request('/api/research/plugins'), request('/api/research/sessions'), user?.role === 'admin' ? request('/api/server/plugins/reviews/pending') : Promise.resolve({ items: [] })]);
    if (results[0].status === 'rejected') throw results[0].reason;
    state.items = list(results[0].value.items);
    state.runtimeItems = results[1].status === 'fulfilled' ? list(results[1].value.items) : [];
    state.sessions = results[2].status === 'fulfilled' ? list(results[2].value.items) : [];
    state.pending = results[3].status === 'fulfilled' ? list(results[3].value.items) : [];
    const problems = results.slice(1).filter(result => result.status === 'rejected');
    if (problems.length) state.message = '部分 Host/会话/审批状态读取失败，未标为就绪。';
    if (results[1].status === 'fulfilled' && Object.keys(results[1].value.deferred_updates || {}).length) state.message = '插件更新等待当前 MCP 安全停用与空闲激活；已有会话继续使用仍获批准的固定版本。';
    if (!state.items.some(item => item.digest === state.selected)) state.selected = state.items[0]?.digest || '';
    loaded = true;
  }
  async function operation(run) {
    if (state.busy) return;
    const ticket = epoch;
    state.busy = true; state.error = ''; state.message = ''; paint();
    try { await run(); if (ticket === epoch && run !== load) await load(); }
    catch (error) { if (ticket === epoch) state.error = error.message; }
    finally { state.busy = false; if (ticket === epoch) paint(); }
  }
  const mcp = (action, body = {}) => {
    const key = mcpKey();
    if (!key) throw new Error('此版本没有可映射的 MCP 组件。');
    const prefix = user ? `/api/server/plugins/mcp/${state.selected}/${key}` : `/api/research/plugins/${state.selected}/mcp/${key}`;
    return request(`${prefix}/${action}`, 'POST', body);
  };
  root.addEventListener('change', event => {
    if (!panel?.contains(event.target)) return;
    event.stopImmediatePropagation();
    if (event.target.matches('[data-plugin-import] input[type="file"]')) state.file = event.target.files?.[0] || null;
    if (event.target.matches('[data-plugin-grant]')) {
      const grant = selected()?.permissions[Number(event.target.dataset.pluginGrant)];
      if (grant) { if (event.target.checked) state.grants.add(grant); else state.grants.delete(grant); }
      paint();
    }
    if (event.target.matches('[data-plugin-mcp]')) { state.mcpKey = event.target.value; state.mcpPreview = null; state.mcpSnapshot = null; paint(); }
    if (event.target.matches('[data-plugin-scope]')) { state.scope = event.target.value === 'personal' ? 'personal' : 'shared'; state.selected = ''; state.grants.clear(); state.mcpPreview = null; state.mcpSnapshot = null; state.file = null; void operation(load); }
  });
  root.addEventListener('input', event => { if (panel?.contains(event.target)) event.stopImmediatePropagation(); });
  root.addEventListener('click', event => {
    if (panel?.contains(event.target)) event.stopImmediatePropagation();
    const target = event.target.closest('[data-plugin-action], [data-plugin-select]');
    if (!target || !panel?.contains(target) || state.busy) return;
    if (target.dataset.pluginSelect) { state.selected = target.dataset.pluginSelect; state.grants.clear(); state.mcpPreview = null; state.mcpSnapshot = null; state.mcpKey = ''; paint(); return; }
    const action = target.dataset.pluginAction;
    if (action === 'reload') { void operation(load); return; }
    if (action === 'select-grants') { state.grants = new Set(selected()?.permissions || []); paint(); return; }
    const risk = action === 'mcp-classify' ? panel.querySelector(`[data-plugin-risk="${CSS.escape(target.dataset.tool)}"]`)?.value : null;
    void operation(async () => {
      if (action === 'refresh-runtime') { const result = await request('/api/server/plugins/runtime/refresh', 'POST', {}); state.message = `当前实例：${result.status}`; return; }
      if (action === 'approve-native') { await request(`/api/server/plugins/reviews/${target.dataset.review}/approve`, 'POST', {}); state.message = '已批准该用户、安装与工具的固定快照。'; return; }
      if (action === 'review') { await request(`${sourcePrefix()}/${state.selected}/review`, 'POST', { permissions: [...state.grants].sort() }); state.message = '已记录此摘要的明确权限审核。'; return; }
      if (['enable', 'disable', 'uninstall'].includes(action)) { await request(`${sourcePrefix()}/${state.selected}${action === 'uninstall' ? '' : '/' + action}`, action === 'uninstall' ? 'DELETE' : 'POST', action === 'uninstall' ? undefined : {}); state.message = user ? '审批分发状态已保存；请空闲时应用到当前实例，查看 Host 实际就绪状态。' : 'Host 投影状态已更新；原生发现和会话授权单独显示。'; return; }
      if (action === 'mcp-preview') { state.mcpPreview = await mcp('preview'); state.message = '预览不执行安装。确认固定计划后再提交。'; return; }
      if (action === 'mcp-status') { state.mcpSnapshot = await mcp('status'); return; }
      if (action === 'mcp-review') { await mcp('review', { expected: state.mcpSnapshot.fingerprint }); state.message = '已锁定实际字节、配置与 schema。'; return; }
      if (action === 'mcp-classify') { await mcp('classify', {tool_name: target.dataset.tool, risk_tier: risk, allow_unattended: false}); state.mcpSnapshot = await mcp('status'); return; }
      if (action?.startsWith('mcp-')) { const result = await mcp(action.slice(4)); state.message = result.admin_review_id ? `等待管理员审核：${result.admin_review_id}` : `MCP：${result.status || '操作已完成，请检查 Host 状态'}`; }
    });
  });
  root.addEventListener('submit', event => {
    if (!panel?.contains(event.target)) return;
    event.stopImmediatePropagation();
    const form = event.target;
    if (!form.matches('[data-plugin-import], [data-plugin-mcp-install], [data-plugin-authorize]')) return;
    event.preventDefault();
    const data = new FormData(form);
    if (form.matches('[data-plugin-import]') && state.file) data.set('file', state.file);
    const token = state.mcpPreview?.confirmation_token;
    const environmentValues = form.matches('[data-plugin-mcp-install]') ? Object.fromEntries(list(state.mcpPreview?.plan?.environment_names).map(name => [name, String(data.get(name) || '')])) : null;
    const tool = state.mcpSnapshot?.capabilities?.tools?.find(item => item.name === form.dataset.tool);
    const session = data.get('session_id');
    // Remove secret DOM values before any rerender/await; never persist them.
    form.querySelectorAll('input[type="password"]').forEach(input => { input.value = ''; });
    void operation(async () => {
      if (form.matches('[data-plugin-import]')) { const file = data.get('file'); if (!file?.size || file.size > 10 * 1024 * 1024) throw new Error('请选择不超过 10 MiB 的插件 ZIP。'); state.file = null; const value = await request(sourcePrefix() + '/preview', 'POST', data); state.selected = value.digest; state.grants.clear(); state.message = '已安全预览，未执行任何包内脚本。'; }
      else if (form.matches('[data-plugin-mcp-install]')) { state.mcpPreview = null; await mcp('install', {confirmation_token: token, environment_values: environmentValues}); state.message = '原生安装已完成；探测和实际 schema 审核仍待执行。'; }
      else if (tool && session) { const component = list((state.runtimeItems.find(item => item.digest === state.selected) || selected())?.components).find(item => item.key === mcpKey() && item.kind === 'mcp'); await mcp('authorize', {session_id: session, version: component.selection.server_version, tool_name: tool.name, schema_sha256: tool.schema_sha256}); state.message = '已由原生 MCP 授予此会话的固定工具权限。'; }
    });
  });
  return { state, sync() { const next = root.querySelector('[data-plugin-workspace]'); if (!next) { if (panel) { epoch++; state.mcpPreview = null; state.mcpSnapshot = null; } panel = null; return; } if (panel !== next) { panel = next; paint(); } if (!loaded && !state.busy) void operation(load); } };
}
