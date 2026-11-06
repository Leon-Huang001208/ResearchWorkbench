import { escapeHTML as e } from './markdown.mjs';

export function safeKnowledgeManagementURL(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\u0000-\u0020\u007f]/.test(value)) return '';
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && url.hostname && !url.username && !url.password ? url.href : '';
  } catch { return ''; }
}

export function knowledgePanelHTML(status = {}, {busy = false, loading = false, error = '', bases = [], basesLoaded = false} = {}) {
  const enabled = status.enabled === true;
  const configured = status.configured === true;
  const disabled = busy || loading || !enabled;
  const managementURL = safeKnowledgeManagementURL(status.management_url);
  const label = loading ? '读取状态中' : !enabled ? '入口未启用' : configured ? '已绑定 · 检索待核验' : '未绑定';
  const workspace = typeof status.workspace_id === 'string' && /^[1-9][0-9]{0,18}$/.test(status.workspace_id) ? status.workspace_id : '';
  const libraries = basesLoaded ? `<div data-knowledge-bases><h3>当前可见知识库</h3>${bases.length ? `<ul>${bases.map(item => `<li>${e(String(item.name || item.id || '未命名知识库'))}</li>`).join('')}</ul>` : '<p class="muted">当前认证未返回可见知识库。</p>'}<p class="muted small">列出知识库不代表检索质量、历史时点或完整报告已经验收。</p></div>` : '';
  return `<section class="settings-card" aria-label="研究资料知识库"><div class="section-heading"><div><span class="eyebrow">RESEARCH MATERIALS</span><h2>研究资料知识库 · WeKnora</h2></div><span class="badge">${label}</span></div><p>研究资料由 WeKnora 管理，金融数据、报告底稿与冻结证据仍保留在 RWB。</p><p class="muted small">连接、权限和真实检索尚未核验；绑定配置不等于已启用 RAG 或报告生产。</p>${managementURL ? `<p><a class="button" href="${e(managementURL)}" target="_blank" rel="noopener noreferrer">打开 WeKnora 资料管理 ↗</a></p>` : '<p class="muted small">资料管理地址尚未配置。</p>'}${configured ? `<p class="muted small">绑定用户 <code>${e(String(status.user_id ?? '未知'))}</code> · 空间 <code>${e(String(workspace || '未知'))}</code></p>` : ''}${error ? `<p class="notice warning" role="alert">${e(error)}</p>` : ''}<form data-knowledge-binding class="automation-form-grid"><label><span>WeKnora 空间 ID</span><input name="workspace_id" type="number" min="1" step="1" inputmode="numeric" required value="${workspace}" ${disabled ? 'disabled' : ''}></label><label><span>WeKnora 用户 JWT（仅存受保护凭据后端）</span><input name="token" type="password" autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="16384" required ${disabled ? 'disabled' : ''}></label><div class="button-row"><button class="button" type="submit" ${disabled ? 'disabled' : ''}>${busy ? '正在处理…' : '验证身份并保存绑定'}</button><button class="button" type="button" data-knowledge-action="refresh" ${busy ? 'disabled' : ''}>刷新绑定状态</button><button class="button" type="button" data-knowledge-action="bases" ${busy || !enabled || !configured ? 'disabled' : ''}>读取可见知识库</button></div></form><p class="muted small">请在 WeKnora 独立登录。凭据不进入聊天、浏览器持久存储或日志；提交后输入框立即清空，失败不会自动重发。现有报告流程和只读 MCP 权限保持原边界。</p>${libraries}</section>`;
}

export function createKnowledgeSettings({api, logger = () => {}, document = globalThis.document}) {
  const element = document.createElement('div');
  const lifetime = new AbortController();
  let status = {}, busy = false, loading = true, error = '', bases = [], basesLoaded = false, disposed = false;
  const render = () => { if (!disposed) element.innerHTML = knowledgePanelHTML(status, {busy, loading, error, bases, basesLoaded}); };
  async function run(kind, operation) {
    if (busy || disposed) return;
    busy = true; error = ''; render();
    try {
      const result = await operation(lifetime.signal);
      if (disposed) return;
      if (kind === 'bases') {
        if (!result || !Array.isArray(result.items) || result.items.length > 200) throw Error('knowledge_bases_invalid');
        bases = result.items.filter(item => item && typeof item === 'object').map(item => ({id: String(item.id ?? '').slice(0, 160), name: String(item.name ?? '').slice(0, 240)}));
        basesLoaded = true;
      } else {
        if (!result || typeof result !== 'object' || Array.isArray(result)) throw Error('knowledge_status_invalid');
        status = {enabled: result.enabled === true, configured: result.configured === true, workspace_id: result.workspace_id, user_id: typeof result.user_id === 'string' ? result.user_id.slice(0, 160) : '', management_url: result.management_url};
        bases = []; basesLoaded = false;
      }
      logger('knowledge_settings_operation_completed');
    } catch {
      if (!disposed) {
        error = kind === 'binding' ? '绑定结果尚未确认，请刷新状态核对；不会自动重发。' : '读取未完成，请核对服务与认证状态后重试。';
        logger('knowledge_settings_operation_failed');
      }
    } finally {
      if (!disposed) { busy = false; loading = false; render(); }
    }
  }
  const refresh = () => run('status', signal => api.request('/knowledge', {signal}));
  function submit(event) {
    if (!event.target.matches?.('[data-knowledge-binding]')) return;
    event.preventDefault(); event.stopPropagation();
    const input = event.target.elements.namedItem('token');
    let token = String(input?.value || '');
    if (input) input.value = '';
    if (busy || disposed) { token = ''; return; }
    const rawWorkspace = String(event.target.elements.namedItem('workspace_id')?.value || '');
    const workspace_id = rawWorkspace;
    if (!status.enabled || !/^[1-9][0-9]{0,18}$/.test(rawWorkspace) || !token.trim() || token.length > 16384) {
      token = ''; error = '请填写有效的正整数空间 ID 和用户 JWT。';
      logger('knowledge_binding_input_invalid'); render(); return;
    }
    const body = {token, workspace_id}; token = '';
    void run('binding', signal => {
      try { return api.request('/knowledge/binding', {method: 'POST', body, userAction: true, signal}); }
      finally { delete body.token; }
    });
  }
  function click(event) {
    const target = event.target.closest?.('[data-knowledge-action]');
    if (!target || target.disabled || disposed || busy) return;
    event.preventDefault(); event.stopPropagation();
    if (target.dataset.knowledgeAction === 'refresh') void refresh();
    if (target.dataset.knowledgeAction === 'bases' && status.enabled && status.configured) void run('bases', signal => api.request('/knowledge/bases', {signal}));
  }
  const isolate = event => event.stopPropagation();
  const isolatedEvents = ['input', 'change', 'keydown', 'compositionstart', 'compositionend'];
  element.addEventListener('submit', submit);
  element.addEventListener('click', click);
  isolatedEvents.forEach(name => element.addEventListener(name, isolate));
  render();
  void refresh();
  return {
    element,
    dispose() {
      if (disposed) return;
      disposed = true; lifetime.abort();
      const input = element.querySelector('[name="token"]');
      if (input) input.value = '';
      element.removeEventListener('submit', submit); element.removeEventListener('click', click);
      isolatedEvents.forEach(name => element.removeEventListener(name, isolate));
      element.remove();
    },
  };
}

export function mountKnowledgeSettings(root, panel, options) {
  const mount = root.querySelector('[data-research-knowledge-root]');
  if (!mount) { panel?.dispose(); return null; }
  const current = panel || createKnowledgeSettings(options);
  mount.replaceWith(current.element);
  return current;
}
