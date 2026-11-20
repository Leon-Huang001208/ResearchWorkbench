import { escapeHTML as e } from './markdown.mjs';

const SESSION_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const HIT_ID = /^[a-f0-9]{64}$/;
const INBOX = '/Volumes/WorkDisk/Data/RWB/knowledge-inbox';
const syncStateLabels = {observing:'等待文件稳定',pending:'等待解析',current:'可检索',error:'处理失败',withdrawn:'已撤下'};
const sourceStateLabels = {current:'当前版本',changed:'原文件已变更',superseded:'已有新版本',deleted:'原文件已删除'};
function normalizeSync(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) value = {};
  const count = key => Number.isSafeInteger(value[key]) && value[key] >= 0 ? value[key] : 0;
  const reconfiguration_required=value.reconfiguration_required === true;
  return {reconfiguration_required,configured:!reconfiguration_required && value.configured === true,enabled:!reconfiguration_required && value.enabled === true,running:value.running === true,
    knowledge_base_id:!reconfiguration_required && typeof value.knowledge_base_id === 'string' ? value.knowledge_base_id.slice(0,160) : '',
    last_scan_at:typeof value.last_scan_at === 'string' ? value.last_scan_at.slice(0,64) : '',
    last_scan_result:['not_run','completed','failed','disabled'].includes(value.last_scan_result) ? value.last_scan_result : 'not_run',
    last_error:value.last_error === true || (typeof value.last_error === 'string' && Boolean(value.last_error)),
    current_count:count('current_count'),pending_count:count('pending_count'),error_count:count('error_count'),
    items:Array.isArray(value.items) ? value.items.slice(0,200).filter(item=>item && typeof item.path === 'string').map(item=>({path:item.path.slice(0,512),state:syncStateLabels[item.state] ? item.state : 'error',version:Number.isSafeInteger(item.version) ? item.version : null})) : []};
}

function authenticationPanelHTML({disabled,busy,enabled,configured,workspace}) {
  return `<h3>登录并绑定已有 WeKnora 账号</h3><p class="muted small">请先用自己的真实邮箱在 WeKnora 注册，再在这里登录。RWB 不代注册账号。</p><form data-knowledge-login class="automation-form-grid" autocomplete="off"><label><span>WeKnora 邮箱</span><input name="email" type="email" maxlength="254" autocomplete="off" autocapitalize="none" spellcheck="false" required ${disabled?'disabled':''}></label><label><span>密码</span><input name="password" type="password" minlength="6" maxlength="1024" autocomplete="off" required ${disabled?'disabled':''}></label><button class="button" type="submit" ${disabled?'disabled':''}>${busy?'正在处理…':'登录并绑定'}</button></form><div class="button-row"><button class="button" type="button" data-knowledge-action="refresh" ${busy?'disabled':''}>刷新绑定状态</button><button class="button" type="button" data-knowledge-action="bases" ${busy || !enabled || !configured?'disabled':''}>读取可见知识库</button></div><details><summary>高级绑定 · 用户 JWT 与空间 ID</summary><form data-knowledge-binding class="automation-form-grid"><label><span>WeKnora 空间 ID</span><input name="workspace_id" type="number" min="1" step="1" inputmode="numeric" required value="${workspace}" ${disabled?'disabled':''}></label><label><span>WeKnora 用户 JWT（仅存受保护凭据后端）</span><input name="token" type="password" autocomplete="off" autocapitalize="none" spellcheck="false" maxlength="16384" required ${disabled?'disabled':''}></label><button class="button" type="submit" ${disabled?'disabled':''}>验证身份并保存绑定</button></form></details><p class="muted small">密码提交后立即清空，不保存到聊天、浏览器存储或日志；绑定使用受保护的用户凭据。失败不会自动重发。</p>`;
}

function syncPanelHTML(status, {busy,loading,bases,basesLoaded}) {
  const sync=normalizeSync(status.sync),disabled=busy || loading || !status.enabled || !status.configured;
  const last={not_run:'尚未扫描',completed:'扫描完成',failed:'扫描失败',disabled:'已暂停'}[sync.last_scan_result];
  return `<div data-knowledge-sync-panel><h3>本地资料目录</h3><p><code>${INBOX}</code></p><p class="muted small">支持 PDF、Word（.docx）、Markdown 和纯文本，单个文件最多 8 MiB。扫描件、图片和表格文件暂不支持；文件连续两次扫描保持稳定后才会入库。目录外文件、隐藏文件和链接不会导入。</p><form data-knowledge-sync class="automation-form-grid"><label><span>导入到知识库</span><select name="knowledge_base_id" required ${disabled || !basesLoaded || !bases.length ? 'disabled' : ''}><option value="">请先读取可见知识库</option>${bases.map(item=>`<option value="${e(item.id)}" ${item.id===sync.knowledge_base_id?'selected':''}>${e(item.name || item.id)}</option>`).join('')}</select></label><div class="button-row"><button class="button" type="submit" ${disabled || !basesLoaded || !bases.length ? 'disabled' : ''}>启用目录同步</button><button class="button" type="button" data-knowledge-action="pause" ${disabled || !sync.configured || !sync.enabled ? 'disabled' : ''}>暂停同步</button><button class="button" type="button" data-knowledge-action="scan" ${disabled || !sync.configured || sync.running ? 'disabled' : ''}>扫描一次</button><button class="button" type="button" data-knowledge-action="sync" ${busy || loading ? 'disabled' : ''}>刷新同步状态</button></div></form><p role="status">${sync.running?'正在扫描':sync.enabled?'同步已启用':'同步已暂停'} · ${last}${sync.last_scan_at?` · ${e(sync.last_scan_at)}`:''}</p><p class="muted small">可检索 ${sync.current_count} · 等待处理 ${sync.pending_count} · 失败 ${sync.error_count}。修改与删除会更新检索范围；已经保存的引用保留原版本。</p>${sync.last_error?'<p class="notice warning">最近扫描未完成，请检查资料服务、权限与文件格式后重试。</p>':''}${sync.items.length?`<details><summary>查看文件状态（${sync.items.length}）</summary><ul>${sync.items.map(item=>`<li>${e(item.path)} · ${syncStateLabels[item.state]}${item.version?` · 版本 ${item.version}`:''}</li>`).join('')}</ul></details>`:''}</div>`;
}

function citationsPanelHTML(status,{busy,loading,sessions=[],sessionsLoaded=false,sessionId='',query='',hits=[],selected=new Set(),preview='',message=''}) {
  const disabled=busy || loading || !status.enabled || !status.configured;
  return `<div data-knowledge-citations><h3>检索并保存研究引用</h3><p class="muted small">选择研究会话，核对实际原文后保存所选引用。资料中的时间未知，不能据此认定历史时点可用或报告已经通过质量检查。</p><button class="button" type="button" data-knowledge-action="sessions" ${disabled?'disabled':''}>读取研究会话</button>${sessionsLoaded?`<form data-knowledge-search class="automation-form-grid"><label><span>研究会话</span><select name="session_id" data-knowledge-session required ${disabled?'disabled':''}><option value="">请选择会话</option>${sessions.map(item=>`<option value="${e(item.id)}" ${item.id===sessionId?'selected':''}>${e(item.title || '未命名研究')}</option>`).join('')}</select></label><label><span>检索资料</span><input name="query" maxlength="2000" required value="${e(query)}" ${disabled?'disabled':''}></label><button class="button" type="submit" ${disabled || !sessions.length?'disabled':''}>检索原文</button></form>${!sessions.length?'<p class="muted">尚无可用研究会话，请先创建研究。</p>':''}`:''}${hits.length?`<div><p class="muted small">以下为原文引用。勾选内容后，点击“确认保存所选引用”会保存当时的原件、位置与版本。</p><ul>${hits.map(item=>`<li><label><input type="checkbox" data-knowledge-hit="${item.hit_id}" ${selected.has(item.hit_id)?'checked':''} ${busy?'disabled':''}>${e(item.title)}</label><p>${e(item.snippet)}</p><p class="muted small">${sourceStateLabels[item.source_status] || '状态待核对'} · 版本 ${item.document_version || '未知'} · 来源时间未知</p><button class="button" type="button" data-knowledge-action="read" data-hit-id="${item.hit_id}" ${busy?'disabled':''}>核对原文</button></li>`).join('')}</ul><button class="button" type="button" data-knowledge-action="freeze" ${busy || !selected.size?'disabled':''}>确认保存所选引用（${selected.size}）</button></div>`:''}${preview?`<details open><summary>命中原文</summary><p class="knowledge-source-excerpt">${e(preview)}</p></details>`:''}${message?`<p class="notice" role="status">${e(message)}</p>`:''}</div>`;
}

export function safeKnowledgeManagementURL(value) {
  if (typeof value !== 'string' || value.length > 2048 || /[\u0000-\u0020\u007f]/.test(value)) return '';
  try {
    const url = new URL(value);
    return ['https:', 'http:'].includes(url.protocol) && url.hostname && !url.username && !url.password ? url.href : '';
  } catch { return ''; }
}

export function knowledgePanelHTML(status = {}, options = {}) {
  const {busy = false, loading = false, error = '', bases = [], basesLoaded = false} = options;
  const enabled = status.enabled === true;
  const configured = status.configured === true;
  const disabled = busy || loading || !enabled;
  const managementURL = safeKnowledgeManagementURL(status.management_url);
  const label = loading ? '读取状态中' : !enabled ? '入口未启用' : configured ? '已绑定 · 检索待核验' : '未绑定';
  const workspace = typeof status.workspace_id === 'string' && /^[1-9][0-9]{0,18}$/.test(status.workspace_id) ? status.workspace_id : '';
  const savedEvidence = HIT_ID.test(options.evidenceId || '') ? `<p><a class="button" href="/api/research/knowledge/evidence/${options.evidenceId}" target="_blank" rel="noopener noreferrer">查看已保存的引用记录 ↗</a></p>` : '';
  const libraries = (basesLoaded ? `<div data-knowledge-bases><h3>当前可见知识库</h3>${bases.length ? `<ul>${bases.map(item => `<li>${e(String(item.name || item.id || '未命名知识库'))}</li>`).join('')}</ul>` : '<p class="muted">当前认证未返回可见知识库。</p>'}<p class="muted small">列出知识库不代表检索质量、历史时点或完整报告已经验收。</p></div>` : '') + syncPanelHTML(status,{busy,loading,bases,basesLoaded}) + citationsPanelHTML(status,{...options,busy,loading}) + savedEvidence;
  const reconfigure=status.sync?.reconfiguration_required === true ? '<p class="notice" role="status">账号已变更，旧账号的资料配置已停用。请先完成本机资料目录的账号切换，再配置本人知识库；历史资料继续保留。</p>' : '';
  return `<section class="settings-card" aria-label="研究资料知识库"><div class="section-heading"><div><span class="eyebrow">RESEARCH MATERIALS</span><h2>研究资料知识库 · WeKnora</h2></div><span class="badge">${label}</span></div><p>研究资料由 WeKnora 管理，金融数据、报告底稿与冻结证据仍保留在 RWB。</p><p class="muted small">连接、权限和真实检索尚未核验；绑定配置不等于已启用 RAG 或报告生产。</p>${managementURL ? `<p><a class="button" href="${e(managementURL)}" target="_blank" rel="noopener noreferrer">打开 WeKnora 注册与资料管理 ↗</a></p>` : '<p class="muted small">资料管理地址尚未配置。</p>'}${configured ? `<p class="muted small">绑定用户 <code>${e(String(status.user_id ?? '未知'))}</code> · 空间 <code>${e(String(workspace || '未知'))}</code></p>` : ''}${error ? `<p class="notice warning" role="alert">${e(error)}</p>` : ''}${authenticationPanelHTML({disabled,busy,enabled,configured,workspace})}${reconfigure}${libraries}</section>`;
}

export function createKnowledgeSettings({api, logger = () => {}, document = globalThis.document}) {
  const element = document.createElement('div');
  const lifetime = new AbortController();
  let status = {}, busy = false, loading = true, error = '', bases = [], basesLoaded = false, disposed = false;
  const emptyResearch = () => ({sessions:[],sessionsLoaded:false,sessionId:'',query:'',hits:[],selected:new Set(),preview:'',message:'',evidenceId:''});
  const research = emptyResearch();
  const render = () => { if (!disposed) element.innerHTML = knowledgePanelHTML(status, {busy, loading, error, bases, basesLoaded,...research}); };
  function receiveBases(result) {
    if (!result || !Array.isArray(result.items) || result.items.length > 200) throw Error('knowledge_bases_invalid');
    bases=result.items.filter(item=>item && typeof item==='object').map(item=>({id:String(item.id ?? '').slice(0,160),name:String(item.name ?? '').slice(0,240)}));
    basesLoaded=true;
  }
  async function run(kind, operation) {
    if (busy || disposed) return;
    busy = true; error = ''; render();
    let loginAccepted=false;
    try {
      const result = await operation(lifetime.signal);
      if (disposed) return;
      if (kind === 'bases') {
        receiveBases(result);
      } else if (kind === 'sync' || kind === 'scan') {
        if (!result || typeof result !== 'object' || Array.isArray(result)) throw Error('knowledge_sync_invalid');
        status.sync = normalizeSync(result.sync || result);
        if (status.sync.reconfiguration_required) {bases=[];basesLoaded=false;Object.assign(research,emptyResearch());}
      } else if (kind === 'sessions') {
        const items=result?.items;
        if (!Array.isArray(items)) throw Error('knowledge_sessions_invalid');
        research.sessions=items.filter(item=>item && SESSION_ID.test(item.id || '')).slice(0,200).map(item=>({id:item.id,title:String(item.title || '').slice(0,240)}));
        research.sessionsLoaded=true;
      } else if (kind === 'search') {
        if (result?.session_id !== research.sessionId || !Array.isArray(result.items) || result.items.length > 8 || result.generated_answer !== false || result.items.some(item=>!HIT_ID.test(item?.hit_id || '') || typeof item.snippet !== 'string' || item.snippet.length > 16000)) throw Error('knowledge_hits_invalid');
        research.hits=result.items.map(item=>({hit_id:item.hit_id,title:String(item.title || '').slice(0,1000),snippet:item.snippet,source_status:item.source_status,document_version:Number.isSafeInteger(item.document_version)?item.document_version:null}));
        research.selected.clear(); research.preview=''; research.message=research.hits.length?'':'没有匹配的原文。';
      } else if (kind === 'read') {
        if (result?.session_id !== research.sessionId || !research.hits.some(item=>item.hit_id === result.hit_id) || typeof result.content !== 'string' || result.content.length > 16000) throw Error('knowledge_read_invalid');
        research.preview=result.content;
        const hit=research.hits.find(item=>item.hit_id === result.hit_id); hit.source_status=result.source_status;
      } else if (kind === 'freeze') {
        if (typeof result?.id !== 'string' || !HIT_ID.test(result.id) || result.session_id !== research.sessionId) throw Error('knowledge_freeze_invalid');
        research.message='所选引用已保存，原件、引用位置与版本已保留。来源时间未知，仍需遵守研究质量要求。';
        research.evidenceId=result.id;
        research.selected.clear();
      } else {
        if (!result || typeof result !== 'object' || Array.isArray(result)) throw Error('knowledge_status_invalid');
        const identityChanged = status.user_id !== result.user_id || status.workspace_id !== result.workspace_id;
        status = {enabled: result.enabled === true, configured: result.configured === true, workspace_id: result.workspace_id, user_id: typeof result.user_id === 'string' ? result.user_id.slice(0, 160) : '', management_url: result.management_url,sync:normalizeSync(result.sync)};
        bases = []; basesLoaded = false;
        if (kind === 'binding' || kind === 'login' || identityChanged || status.sync.reconfiguration_required) Object.assign(research,emptyResearch());
        if (kind === 'login') {
          if (!status.configured) throw Error('knowledge_login_status_invalid');
          loginAccepted=true;
          render();
          const visible=await api.request('/knowledge/bases',{signal:lifetime.signal});
          if (disposed) return;
          receiveBases(visible);
        }
      }
      logger('knowledge_settings_operation_completed');
    } catch (failure) {
      if (!disposed) {
        error = kind === 'login' ? loginAccepted ? '账号已绑定，但知识库读取未完成，请重试读取可见知识库。' : failure?.code === 'knowledge_login_failed' ? '登录失败，请检查邮箱和密码后重试。' : '登录绑定结果尚未确认，请刷新状态核对；不会自动重发。' : kind === 'binding' ? '绑定结果尚未确认，请刷新状态核对；不会自动重发。' : kind === 'scan' ? '扫描结果尚未确认，请刷新同步状态核对；不会自动重发。' : kind === 'freeze' ? '引用保存结果尚未确认，请核对研究会话；不会自动重发。' : kind === 'sync' ? '同步配置或状态尚未确认，请刷新状态核对；不会自动重发。' : '读取未完成，请核对服务与认证状态后重试。';
        logger('knowledge_settings_operation_failed');
      }
    } finally {
      if (!disposed) { busy = false; loading = false; render(); }
    }
  }
  const refresh = () => run('status', signal => api.request('/knowledge', {signal}));
  function submit(event) {
    if (event.target.matches?.('[data-knowledge-login]')) {
      event.preventDefault();event.stopPropagation();
      const input=event.target.elements.namedItem('password');
      let password=String(input?.value || '');
      if (input) input.value='';
      if (busy || disposed) {password='';return;}
      let email=String(event.target.elements.namedItem('email')?.value || '').trim();
      if (!status.enabled || email.length>254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) || password.length<6 || password.length>1024) {
        email='';password='';error='请填写有效的邮箱和密码。';logger('knowledge_login_input_invalid');render();return;
      }
      const body={email,password};email='';password='';
      void run('login',signal=>{
        try {return api.request('/knowledge/login',{method:'POST',body,userAction:true,signal});}
        finally {delete body.email;delete body.password;}
      });
      return;
    }
    if (event.target.matches?.('[data-knowledge-sync]')) {
      event.preventDefault(); event.stopPropagation();
      if (busy || disposed || !status.enabled || !status.configured) return;
      const knowledge_base_id=String(event.target.elements.namedItem('knowledge_base_id')?.value || '');
      if (!basesLoaded || !bases.some(item=>item.id === knowledge_base_id)) {error='请先读取并选择当前可见的知识库。';render();return;}
      void run('sync',signal=>api.request('/knowledge/sync/config',{method:'POST',body:{knowledge_base_id,enabled:true},userAction:true,signal}));
      return;
    }
    if (event.target.matches?.('[data-knowledge-search]')) {
      event.preventDefault(); event.stopPropagation();
      if (busy || disposed || !status.enabled || !status.configured) return;
      const session_id=String(event.target.elements.namedItem('session_id')?.value || '');
      const query=String(event.target.elements.namedItem('query')?.value || '').trim();
      if (!research.sessions.some(item=>item.id === session_id) || !query || query.length > 2000) {error='请选择研究会话并输入有效查询。';render();return;}
      research.sessionId=session_id; research.query=query;research.hits=[];research.selected.clear();research.preview='';research.message='';
      void run('search',signal=>api.request('/knowledge/search',{method:'POST',body:{session_id,query},readOnly:true,signal}));
      return;
    }
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
    if (target.dataset.knowledgeAction === 'sync') void run('sync',signal=>api.request('/knowledge/sync',{signal}));
    if (status.enabled && status.configured) {
      if (target.dataset.knowledgeAction === 'pause' && status.sync?.configured && status.sync?.enabled) void run('sync',signal=>api.request('/knowledge/sync/config',{method:'POST',body:{knowledge_base_id:status.sync.knowledge_base_id,enabled:false},userAction:true,signal}));
      if (target.dataset.knowledgeAction === 'scan' && status.sync?.configured && !status.sync?.running) void run('scan',signal=>api.request('/knowledge/sync/scan',{method:'POST',body:{},userAction:true,signal}));
      if (target.dataset.knowledgeAction === 'sessions') void run('sessions',signal=>api.request('/sessions',{signal}));
      const hit_id=target.dataset.hitId;
      if (target.dataset.knowledgeAction === 'read' && research.hits.some(item=>item.hit_id === hit_id)) void run('read',signal=>api.request('/knowledge/read',{method:'POST',body:{session_id:research.sessionId,hit_id},readOnly:true,signal}));
      if (target.dataset.knowledgeAction === 'freeze' && research.selected.size) {
        const hit_ids=research.hits.filter(item=>research.selected.has(item.hit_id)).map(item=>item.hit_id);
        void run('freeze',signal=>api.request('/knowledge/freeze',{method:'POST',body:{session_id:research.sessionId,hit_ids},userAction:true,signal}));
      }
    }
  }
  const isolate = event => event.stopPropagation();
  function change(event) {
    event.stopPropagation();
    if (disposed || busy) return;
    const hit=event.target?.dataset?.knowledgeHit;
    if (hit && research.hits.some(item=>item.hit_id === hit)) {
      if (event.target.checked) research.selected.add(hit); else research.selected.delete(hit);
      render();
    }
    if (event.target?.dataset?.knowledgeSession !== undefined && research.sessionId !== event.target.value) {
      research.sessionId=research.sessions.some(item=>item.id === event.target.value)?event.target.value:'';
      research.hits=[];research.selected.clear();research.preview='';research.message='';render();
    }
  }
  const isolatedEvents = ['input', 'keydown', 'compositionstart', 'compositionend'];
  element.addEventListener('submit', submit);
  element.addEventListener('click', click);
  element.addEventListener('change',change);
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
      for (const name of ['password','email']) {
        const input=element.querySelector(`[name="${name}"]`);
        if (input) input.value='';
      }
      element.removeEventListener('submit', submit); element.removeEventListener('click', click);
      element.removeEventListener('change',change);
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
