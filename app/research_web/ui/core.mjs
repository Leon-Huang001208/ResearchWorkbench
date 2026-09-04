const API_ROOT = '/api/research';
const segment = (value) => encodeURIComponent(value);
const pages = new Set(['fingpt', 'claw', 'history', 'skills', 'settings']);

export function parseRoute(hash = '') {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const page = pages.has(path) ? path : 'fingpt';
  return { page, sessionId: ['fingpt', 'claw'].includes(page) ? new URLSearchParams(query).get('session') : null };
}
export const sessionHash = (session) => `#/${session.mode === 'claw' ? 'claw' : 'fingpt'}?session=${segment(session.id)}`;
export const isRunning = (status) => ['running', 'queued', 'pending', 'waiting', 'waiting_approval', 'awaiting_approval', 'waiting_input', 'busy', 'cancelling'].includes(status);

export function reconcileSessionSummary(sessions, detail) {
  if (!detail?.id) return sessions;
  const { id, title, mode, status, can_cancel } = detail;
  return sessions.map(session => session.id === id ? { ...session, title, mode, status, can_cancel } : session);
}

export function collectQuestionAnswers(values, items) {
  return items.map((item, index) => {
    const selected = values.getAll(`selection-${index}`).map(String);
    if (item.multiSelect !== true && selected.length > 1) throw new Error('单选问题只能选择一个选项');
    return { id: item.id, selected, custom: String(values.get(`custom-${index}`) || '') };
  });
}

// Never log prompts, response bodies, filenames, credentials or session identifiers.
export function safeLog(event, metadata = {}) {
  console.info('[ResearchWeb]', event, { status: metadata.status, method: metadata.method });
}

export function createAPI({ fetcher = globalThis.fetch.bind(globalThis), EventSourceClass = globalThis.EventSource, logger = safeLog } = {}) {
  async function request(path, { method = 'GET', body, key } = {}) {
    const headers = { Accept: 'application/json' };
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
    let response;
    try {
      response = await fetcher(`${API_ROOT}${path}`, { method, credentials: 'same-origin', cache: 'no-store', headers, body: body === undefined ? undefined : isForm ? body : JSON.stringify(body) });
    } catch {
      logger('request_failed', { method });
      throw new Error('网络连接失败，请检查服务后重试。未自动重新提交请求。');
    }
    logger('request_finished', { method, status: response.status });
    let data;
    try { data = response.status === 204 ? {} : await response.json(); } catch {
      throw new Error(`服务响应格式异常（HTTP ${response.status}），请检查后端日志。`);
    }
    if (!response.ok) {
      const error = new Error(data?.error?.message || `请求失败（HTTP ${response.status}）`);
      error.code = data?.error?.code || 'request_failed'; throw error;
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('服务响应格式异常，请检查后端日志。');
    return data;
  }
  const sessionPath = (id) => `/sessions/${segment(id)}`;
  const capabilityPath = (id) => `/capabilities/${segment(id)}`;
  return {
    runtime: () => request('/runtime'), models: () => request('/models'), workspaces: () => request('/workspaces'),
    sessions: () => request('/sessions'), skills: () => request('/skills'),
    capabilities: () => request('/capabilities'), tools: () => request('/tools'),
    dataCatalog: () => request('/data/catalog'),
    dataCapability: (id) => request(`/data/capabilities/${segment(id)}`),
    dataSource: (id) => request(`/data/sources/${segment(id)}`),
    probeDataSource: (id, key) => request(`/data/sources/${segment(id)}/probes`, { method: 'POST', body: {}, key }),
    dataProbe: (id) => request(`/data/probes/${segment(id)}`),
    capability: (id) => request(capabilityPath(id)),
    createCapability: (body) => request('/capabilities', { method: 'POST', body }),
    saveCapability: (id, body) => request(`${capabilityPath(id)}/draft`, { method: 'PATCH', body }),
    capabilityAction: (id, action, body = {}) => {
      if (!['copy', 'check', 'publish', 'disable', 'enable', 'rollback'].includes(action)) throw new Error('未知能力操作');
      return request(`${capabilityPath(id)}/${action}`, { method: 'POST', body });
    },
    capabilityVersions: (id) => request(`${capabilityPath(id)}/versions`),
    capabilityVersion: (id, version) => request(`${capabilityPath(id)}/versions/${segment(version)}`),
    importCapability: (file) => { const body = new FormData(); body.append('file', file); return request('/capabilities/import', { method: 'POST', body }); },
    createCapabilitySession: (kind, goal) => request('/capabilities/creation-sessions', { method: 'POST', body: { kind, goal } }),
    capabilityFromArtifact: (sessionId, fileId) => request('/capabilities/from-artifact', { method: 'POST', body: { session_id: sessionId, file_id: fileId } }),
    create: (body) => request('/sessions', { method: 'POST', body }),
    detail: (id) => request(sessionPath(id)),
    message: (id, body, key) => request(`${sessionPath(id)}/messages`, { method: 'POST', body, key }),
    rename: (id, title) => request(sessionPath(id), { method: 'PATCH', body: { title } }),
    cancel: (id) => request(`${sessionPath(id)}/cancel`, { method: 'POST', body: {} }),
    upgrade: (id) => request(`${sessionPath(id)}/upgrade`, { method: 'POST', body: {} }),
    files: (id) => request(`${sessionPath(id)}/files`),
    upload: (id, files) => { const body = new FormData(); for (const file of files) body.append('files', file); return request(`${sessionPath(id)}/uploads`, { method: 'POST', body }); },
    approve: (id, approval, decision) => request(`${sessionPath(id)}/approvals/${segment(approval)}`, { method: 'POST', body: { decision } }),
    answer: (id, question, answers) => request(`${sessionPath(id)}/questions/${segment(question)}`, { method: 'POST', body: { answers } }),
    configure: (body) => request('/runtime/model', { method: 'PUT', body }),
    events: (id, handlers) => {
      if (!EventSourceClass) { handlers.error('当前浏览器不支持实时连接，可手动刷新会话。'); return () => {}; }
      const source = new EventSourceClass(`${API_ROOT}${sessionPath(id)}/events`);
      source.addEventListener('snapshot', (event) => {
        try { handlers.snapshot(JSON.parse(event.data)); } catch { handlers.error('运行时事件格式异常，请刷新会话。'); }
      });
      source.addEventListener('runtime_error', (event) => {
        try { handlers.error(JSON.parse(event.data).message || 'DSH 运行时异常'); } catch { handlers.error('DSH 运行时异常'); }
      });
      source.onopen = () => { void handlers.open(); };
      source.onerror = () => { logger('stream_disconnected'); handlers.error('实时连接已断开，正在重新连接；不会自动重发消息。'); };
      return () => source.close();
    },
  };
}

export function createController({ api, makeID = () => globalThis.crypto.randomUUID(), onNavigate = () => {} }) {
  const state = { route: { page: 'fingpt', sessionId: null }, detail: null, draft: '', attachments: [], skillId: '', capability: null, toolIds: [], expectedFormats: null, error: '', streamError: '', loading: false, busy: false };
  const listeners = new Set(); const drafts = new Map(); const pending = new Map();
  let generation = 0; let snapshotRevision = 0; let closeStream = () => {};
  const emit = () => listeners.forEach((listener) => listener(state));
  const draftKey = () => state.route.sessionId || `new:${state.route.page}`;
  const draftState = () => ({ draft: state.draft, attachments: state.attachments, skillId: state.skillId, capability: state.capability, toolIds: state.toolIds, expectedFormats: state.expectedFormats });
  const saveDraft = () => drafts.set(draftKey(), draftState());
  const fail = (error) => { state.error = error?.message || '操作失败，请重试。'; };
  function snapshot(data) {
    if (!data || data.id !== state.route.sessionId || !Array.isArray(data.messages)) throw new Error('会话响应格式异常，请刷新重试。');
    state.detail = data; snapshotRevision++;
  }
  async function refresh() {
    const ticket = generation; const revision = snapshotRevision; const id = state.route.sessionId;
    if (!id) return;
    try { const data = await api.detail(id); if (ticket === generation && revision === snapshotRevision) { snapshot(data); state.streamError = ''; emit(); } }
    catch (error) { if (ticket === generation) { fail(error); emit(); } }
  }
  async function open(route) {
    saveDraft(); const ticket = ++generation; closeStream(); closeStream = () => {};
    state.route = route; state.detail = null; state.error = ''; state.streamError = ''; state.loading = Boolean(route.sessionId); state.busy = false;
    Object.assign(state, { expectedFormats: null, capability: null, toolIds: [] }, drafts.get(draftKey()) || { draft: '', attachments: [], skillId: '' }); emit();
    if (!route.sessionId) return;
    try {
      const data = await api.detail(route.sessionId);
      if (ticket !== generation) return;
      snapshot(data);
      if (api.events) closeStream = api.events(route.sessionId, {
        snapshot: (next) => { if (ticket === generation) { try { snapshot(next); state.streamError = ''; emit(); } catch (error) { fail(error); emit(); } } },
        error: (message) => { if (ticket === generation) { state.streamError = message; emit(); } },
        open: async () => { if (ticket === generation) await refresh(); },
      });
    } catch (error) { if (ticket === generation) fail(error); }
    finally { if (ticket === generation) { state.loading = false; emit(); } }
  }
  async function send() {
    if (state.busy || !state.detail || !state.draft.trim()) return;
    const id = state.detail.id; const ticket = generation; const text = state.draft;
    const body = { text: text.trim(), ...(state.capability ? { capability_id: state.capability.id, capability_version: state.capability.version } : state.skillId ? { skill_id: state.skillId } : {}), ...(state.toolIds.length ? { tool_ids: state.toolIds } : {}), ...(state.expectedFormats !== null ? { expected_formats: state.expectedFormats } : {}), ...(state.attachments.length ? { attachment_ids: state.attachments.map((file) => file.id) } : {}) };
    const signature = JSON.stringify(body); const previous = pending.get(id);
    const attempt = previous?.signature === signature ? previous : { signature, key: makeID() };
    pending.set(id, attempt); state.busy = true; state.error = ''; emit();
    try {
      const response = await api.message(id, body, attempt.key);
      if (response.accepted !== true) throw new Error('运行时未确认接收，请检查会话后重试。');
      pending.delete(id);
      if (ticket === generation) {
        if (state.draft === text) state.draft = '';
        state.attachments = []; saveDraft(); await refresh();
      } else {
        const saved = drafts.get(id); if (saved?.draft === text) drafts.set(id, { ...saved, draft: '', attachments: [] });
      }
    } catch (error) { if (ticket === generation) fail(error); }
    finally { if (ticket === generation) { state.busy = false; emit(); } }
  }
  async function action(operation, { refreshAfter = true } = {}) {
    if (state.busy) return null;
    const ticket = generation; state.busy = true; state.error = ''; emit();
    try { const result = await operation(); if (ticket === generation && refreshAfter) await refresh(); return result; }
    catch (error) { if (ticket === generation) fail(error); return null; }
    finally { if (ticket === generation) { state.busy = false; emit(); } }
  }
  return {
    state, subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); }, open, refresh, send, action,
    setDraft: (value) => { state.draft = value; saveDraft(); },
    setSkill: (value) => { state.skillId = value; state.capability = null; saveDraft(); },
    setCapability: (value) => {
      if (value && (value.enabled !== true || !Number.isInteger(value.version) || value.version < 1)) throw new Error('只能选择已启用的已发布能力版本。');
      state.capability = value ? structuredClone(value) : null; state.skillId = value?.id || ''; saveDraft();
    },
    setTools: (values) => { state.toolIds = [...new Set(values)]; saveDraft(); },
    setFormats: (value) => { state.expectedFormats = value === null ? null : [...new Set(value)]; saveDraft(); },
    addAttachments: (items) => { state.attachments = [...new Map([...state.attachments, ...items].map((file) => [file.id, file])).values()]; saveDraft(); emit(); },
    removeAttachment: (id) => { state.attachments = state.attachments.filter((file) => file.id !== id); saveDraft(); emit(); },
    create: async (mode, workspaceId) => {
      const ticket = generation;
      const previousDraft = { ...draftState(), attachments: [] };
      const result = await action(() => api.create({ mode, ...(workspaceId ? { workspace_id: workspaceId } : {}) }), { refreshAfter: false });
      if (ticket !== generation) return null;
      if (result?.id) { drafts.set(result.id, previousDraft); onNavigate(sessionHash(result)); }
      return result;
    },
    createCapabilitySession: async (kind, goal) => {
      const ticket = generation;
      const result = await action(() => api.createCapabilitySession(kind, goal), { refreshAfter: false });
      if (ticket !== generation) return null;
      if (result?.id && typeof result.draft === 'string') {
        drafts.set(result.id, { draft: result.draft, attachments: [], skillId: '', capability: null, toolIds: [], expectedFormats: null });
        onNavigate(sessionHash(result));
      }
      return result;
    },
    upgrade: async () => {
      if (!state.detail) return null;
      const ticket = generation; const id = state.detail.id;
      const result = await action(() => api.upgrade(id), { refreshAfter: false });
      if (ticket !== generation) return null;
      if (result?.id) {
        drafts.set(result.id, { draft: typeof result.draft === 'string' ? result.draft : '', attachments: result.attachments || [], skillId: '' });
        onNavigate(sessionHash(result));
      }
      return result;
    },
  };
}
