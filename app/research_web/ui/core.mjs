const API_ROOT = '/api/research';
import { ASSET_VIEWS, ASSET_TYPES, cleanAsset } from './asset-navigation.mjs';
const segment = (value) => encodeURIComponent(value);
const pages = new Set(['fingpt', 'claw', 'market', 'assets', 'simulation', 'workbench', 'frameworks', 'skills', 'history', 'operations', 'settings', 'account', 'intel', 'aihot']);
const workbenchSections = new Set(['market', 'assets', 'funds', 'industry', 'documents', 'hot', 'etf-paper']);
const searchSections = { news: 'market', research: 'industry', announcements: 'documents' };
const settingsSections = new Set(['general', 'model', 'data', 'local', 'docs', 'hot', 'users']);
const capabilityViews = new Set(['library', 'mine', 'plans', 'connections', 'market']);
const capabilityKinds = new Set(['skill', 'method', 'tool', 'workflow', 'data', 'plugin']);
const frameworkTabs = new Set(['overview', 'drivers', 'supply', 'cycle', 'positioning', 'allocation', 'quantity', 'price', 'fiscal', 'plumbing', 'cross-border', 'evidence']);

export function parseRoute(hash = '') {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const [pageSegment, sectionSegment, ...extraSegments] = path.split('/');
  const page = pages.has(pageSegment) ? pageSegment : 'fingpt';
  const params = new URLSearchParams(query);
  const route = {
    page,
    sessionId: ['fingpt', 'claw'].includes(page) ? params.get('session') : null,
  };
  if (page === 'market') {
    route.marketView = ['overview', 'quotes', 'sectors'].includes(params.get('view')) ? params.get('view') : 'overview';
    route.marketBoardId = /^BK[0-9]{4,6}$/.test(params.get('board_id') || '') ? params.get('board_id') : null;
  }
  if (page === 'aihot') {
    route.aihotTab = !extraSegments.length && ['hot', 'archive', 'weekly', 'monthly', 'manage'].includes(sectionSegment) ? sectionSegment : 'daily';
    route.aiNewsSection = params.get('section') || 'sources';
    const identity = extraSegments.length === 1 ? extraSegments[0] : '';
    const validDetail = sectionSegment === 'item' ? /^[A-Za-z0-9_-]{1,80}$/.test(identity) : sectionSegment === 'story' ? /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(identity) : sectionSegment === 'topic' && /^[a-z0-9][a-z0-9_-]{0,79}$/.test(identity);
    if (validDetail) {
      route.aihotTab = sectionSegment; route.aihotId = identity;
      route.aihotLanguage = params.get('lang') === 'original' ? 'original' : 'zh';
      const requestedPage = params.get('page') || '1';
      route.aihotPage = /^\d{1,5}$/.test(requestedPage) && Number(requestedPage) >= 1 && Number(requestedPage) <= 10000 ? Number(requestedPage) : 1;
    }
    const datePattern = route.aihotTab === 'weekly' ? /^\d{4}-W\d{2}$/ : route.aihotTab === 'monthly' ? /^\d{4}-\d{2}$/ : /^\d{4}-\d{2}-\d{2}$/;
    route.aihotDate = datePattern.test(params.get('date') || '') ? params.get('date') : null;
  }
  if (page === 'intel') {
    const tabs = new Set(['discovery', 'hot', 'overview', 'search', 'research-reports', 'investment-news', 'wsc', 'social', 'events', 'signals']);

    route.intelTab = !extraSegments.length && tabs.has(sectionSegment) ? sectionSegment : 'overview';
    if (route.intelTab === 'search') {
      route.searchKind = Object.hasOwn(searchSections, params.get('kind')) ? params.get('kind') : 'news';
      route.section = searchSections[route.searchKind];
    }
    if (route.intelTab === 'hot') {
      route.hotView = ['events', 'sources', 'channels', 'briefs', 'research', 'follows', 'plans'].includes(params.get('view')) ? params.get('view') : 'events';
      route.hotEventId = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(params.get('event') || '') ? params.get('event') : null;
    }
  }
  if (['claw', 'fingpt'].includes(page) && (params.has('view') || params.has('project'))) {
    route.clawView = (page === 'claw' ? ['projects','plans','skills'] : ['projects']).includes(params.get('view')) ? params.get('view') : 'sessions';
    route.projectId = /^(default|project-[a-f0-9]{32})$/.test(params.get('project') || '') ? params.get('project') : 'default';
  }
  if (page === 'history') {
    route.historyMode = ['fingpt', 'claw'].includes(params.get('mode')) ? params.get('mode') : null;
    route.historyView = params.get('view') === 'deleted' ? 'deleted' : 'active';
  }
  if (page === 'skills') {
    const requestedView = capabilityViews.has(params.get('view')) ? params.get('view') : 'library';
    const requestedKind = capabilityKinds.has(params.get('kind')) ? params.get('kind') : null;
    route.capabilityKind = requestedKind || (requestedView === 'plans' ? 'workflow' : ['connections', 'market'].includes(requestedView) ? 'tool' : 'skill');
    route.capabilityView = requestedView;
    if (requestedView === 'mine' && !['skill', 'workflow'].includes(route.capabilityKind)) route.capabilityView = 'library';
    if (requestedView === 'plans' && route.capabilityKind !== 'workflow') route.capabilityView = 'library';
    if (requestedView === 'connections' && !['tool', 'data'].includes(route.capabilityKind)) route.capabilityView = 'library';
    if (requestedView === 'market' && route.capabilityKind !== 'tool') route.capabilityView = 'library';
  }
  if (page === 'settings') {
    const connection = params.get('connection');
    const hasSafeConnection = /^[a-z0-9_]+$/.test(connection || '');
    const requestedSection = extraSegments.length ? '' : (sectionSegment || (hasSafeConnection ? 'data' : 'general'));
    route.settingsSection = settingsSections.has(requestedSection) ? requestedSection : 'general';
    if (extraSegments.length || (sectionSegment && !settingsSections.has(sectionSegment))) route.settingsSectionFallback = true;
    if (hasSafeConnection) {
      route.connectionId = connection;
      if (!sectionSegment) route.legacySettingsConnection = true;
    }
  }
  if (page === 'workbench') {
    const requestedSection = extraSegments.length ? '' : (sectionSegment || params.get('section'));
    route.section = workbenchSections.has(requestedSection) ? requestedSection : 'assets';
    if (route.section === 'hot') {
      route.hotView = ['events', 'sources', 'channels', 'briefs', 'research', 'follows', 'plans'].includes(params.get('view')) ? params.get('view') : 'events';
      route.hotEventId = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(params.get('event') || '') ? params.get('event') : null;
    }
  }
  if (page === 'assets') route.section = !extraSegments.length && sectionSegment === 'funds' ? 'funds' : 'assets';
  if (['assets', 'workbench'].includes(page) && route.section === 'assets') {
    route.asset = cleanAsset(params.get('asset'));
    route.assetType = ASSET_TYPES.includes(params.get('asset_type')) ? params.get('asset_type') : 'stock';
    route.assetView = params.get('view') === 'dossiers' && page === 'assets' ? 'dossiers' : ASSET_VIEWS.includes(params.get('view')) ? params.get('view') : 'overview';
    if (route.assetView === 'dossiers') route.dossierId = /^[a-f0-9]{32}$/.test(params.get('dossier') || '') ? params.get('dossier') : null;
  }
  if (page === 'simulation') route.section = 'etf-paper';
  if (page === 'frameworks') {
    route.frameworkSlug = !extraSegments.length && /^[a-z0-9-]+$/.test(sectionSegment || '') ? sectionSegment : null;
    route.frameworkTab = frameworkTabs.has(params.get('tab')) ? params.get('tab') : 'overview';
  }
  return route;
}

export function legacyRouteTarget(hash = '') {
  const oldAssetTopic = /^#\/intel\/(news|filings)(?:\?([^#]*))?$/.exec(String(hash));
  if (oldAssetTopic) {
    const params = new URLSearchParams({ view: oldAssetTopic[1] === 'news' ? 'news' : 'announcements' });
    const code = new URLSearchParams(oldAssetTopic[2] || '').get('code');
    if (/^\d{6}$/.test(code || '')) { params.set('asset', code); params.set('asset_type', 'stock'); }
    return `#/assets?${params}`;
  }
  if (/^#\/settings\/account(?:\?|$)/.test(String(hash))) return '#/account';
  if (/^#\/workbench(?:\/|\?|$)/.test(String(hash))) {
    const route = parseRoute(hash);
    const params = new URLSearchParams(String(hash).split('?')[1] || '');
    params.delete('section');
    const targets = { assets: '#/assets', funds: '#/assets/funds', market: '#/intel/search', industry: '#/intel/search', documents: '#/intel/search', 'etf-paper': '#/simulation/etf', hot: '#/intel/hot' };
    const kind = Object.keys(searchSections).find(key => searchSections[key] === route.section);
    if (kind) {
      params.delete('kind');
      const searchParams = new URLSearchParams({ kind });
      for (const [key, value] of params) searchParams.append(key, value);
      return `${targets[route.section]}?${searchParams}`;
    }
    return `${targets[route.section]}${params.size ? `?${params}` : ''}`;
  }
  return /^#\/reports\/?$/.test(String(hash)) ? '#/skills?kind=workflow' : null;
}

export function isDataWorkspaceRoute(route) {
  return ['assets', 'simulation', 'workbench'].includes(route?.page) || (route?.page === 'intel' && route?.intelTab === 'search');
}
export async function prepareClawExampleDraft(controller, prompt, { navigate, currentGeneration }) {
  const pending = navigate();
  const ticket = currentGeneration();
  await pending;
  const route = controller.state.route;
  if (ticket !== currentGeneration() || route.page !== 'claw' || route.sessionId || route.clawView) return false;
  const previous = controller.state.draft || '';
  controller.setDraft(previous.trim() && previous !== prompt ? `${previous}\n\n${prompt}` : prompt);
  return true;
}

export const sessionHash = (session) => `#/${session.mode === 'claw' ? 'claw' : 'fingpt'}?session=${segment(session.id)}`;
export const isRunning = (status) => ['running', 'queued', 'pending', 'waiting', 'waiting_approval', 'awaiting_approval', 'waiting_input', 'busy', 'cancelling'].includes(status);

export function reconcileSessionSummary(sessions, detail) {
  if (!detail?.id) return sessions;
  const { id, title, mode, status, can_cancel } = detail;
  return sessions.map(session => session.id === id ? { ...session, title, mode, status, can_cancel, ...(detail.updated_at !== undefined ? { updated_at: detail.updated_at } : {}), ...(Array.isArray(detail.questions) ? { waitingForAnswer: detail.questions.length > 0 } : {}) } : session);
}

export function collectQuestionAnswers(values, items) {
  return items.map((item, index) => {
    const selected = values.getAll(`selection-${index}`).map(String);
    if (item.multiSelect !== true && selected.length > 1) throw new Error('单选问题只能选择一个选项');
    return { id: item.id, selected, custom: String(values.get(`custom-${index}`) || '') };
  });
}

export async function waitForDataProbe(getProbe, probeId, { maxAttempts = 40, delay = 250, sleep = (milliseconds) => new Promise((resolve) => setTimeout(resolve, milliseconds)) } = {}) {
  const attempts = Number.isInteger(maxAttempts) && maxAttempts > 0 ? maxAttempts : 40;
  for (let attempt = 0; attempt < attempts; attempt += 1) {
    const current = await getProbe(probeId);
    if (!current || typeof current !== 'object' || Array.isArray(current) || typeof current.status !== 'string' || !current.status) {
      throw new Error('探测状态响应格式异常，请检查后端日志。');
    }
    if (!['checking', 'queued'].includes(current.status)) return current;
    if (attempt + 1 < attempts && delay > 0) await sleep(delay);
  }
  throw new Error('检测仍在进行，请稍后刷新状态。');
}

export const waitForLocalIntegrationProbe = waitForDataProbe;
export const waitForLocalIntegrationVerification = waitForDataProbe;
export const INTEGRATION_BATCH_POLL_INTERVAL_MS = 1000;
export const INTEGRATION_BATCH_MAX_ATTEMPTS = 451;
export function waitForIntegrationBatch(getBatch, batchId, options = {}) {
  return waitForDataProbe(getBatch, batchId, {
    maxAttempts: INTEGRATION_BATCH_MAX_ATTEMPTS,
    delay: INTEGRATION_BATCH_POLL_INTERVAL_MS,
    ...options,
  });
}

// Never log prompts, response bodies, filenames, credentials or session identifiers.
export function safeLog(event, metadata = {}) {
  console.info('[ResearchWeb]', event, { status: metadata.status, method: metadata.method });
}

export function createAPI({ fetcher = globalThis.fetch.bind(globalThis), EventSourceClass = globalThis.EventSource, logger = safeLog, requestTimeoutMs = 120000 } = {}) {
  async function request(path, { method = 'GET', body, key, userAction = false, readOnly = false, signal } = {}) {
    const reading = method === 'GET' || readOnly;
    const abort = new AbortController();
    let timer;
    const timeout = new Promise((_, reject) => {
      timer = setTimeout(() => {
        abort.abort();
        logger('request_timeout', { method });
        const error = new Error(reading ? '读取超时，请刷新重试。' : '请求超时，操作结果尚未确认；请核对会话状态。草稿已保留，不会自动重发。');
        error.code = 'request_timeout'; reject(error);
      }, reading ? Math.min(requestTimeoutMs, 30000) : requestTimeoutMs);
    });
    const combined = signal ? AbortSignal.any([signal, abort.signal]) : abort.signal;
    try { return await Promise.race([performRequest(path, { method, body, key, userAction, signal: combined }), timeout]); }
    finally { clearTimeout(timer); }
  }
  async function performRequest(path, { method, body, key, userAction, signal }) {
    const headers = { Accept: 'application/json' };
    const isForm = typeof FormData !== 'undefined' && body instanceof FormData;
    if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
    if (key) headers['Idempotency-Key'] = key;
    if (userAction) headers['X-Research-User-Action'] = '?1';
    let response;
    try {
      response = await fetcher(`${API_ROOT}${path}`, { method, signal, credentials: 'same-origin', cache: 'no-store', headers, body: body === undefined ? undefined : isForm ? body : JSON.stringify(body) });
    } catch (error) {
      if (signal.aborted) throw new DOMException('读取已取消', 'AbortError');
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
      error.code = data?.error?.code || 'request_failed'; error.status = response.status; throw error;
    }
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('服务响应格式异常，请检查后端日志。');
    return data;
  }
  const sessionPath = (id) => `/sessions/${segment(id)}`;
  const capabilityPath = (id) => `/capabilities/${segment(id)}`;
  const mcpRegistryPath = (id) => `/mcp/registries/${segment(id)}`;
  const hotQuery = (params = {}) => {
    const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value !== undefined && value !== null && value !== '').map(([key, value]) => [key, String(value)]));
    return query.size ? `?${query}` : '';
  };
  return {
    request,
    hotStatus: () => request('/hot/status'), hotConfiguration: () => request('/hot/configuration'),
    hotConfigure: (body) => request('/hot/configuration', { method: 'PUT', body, userAction: true }),
    hotLifecycle: (action) => request('/hot/lifecycle', { method: 'POST', body: { action }, userAction: true }),
    hotChannels: (params) => request(`/hot/channels${hotQuery(params)}`), hotEvents: (params) => request(`/hot/events${hotQuery(params)}`),
    hotEvent: (id, params) => request(`/hot/events/${segment(id)}${hotQuery(params)}`), hotSources: () => request('/hot/sources'),
    hotChannelConfigure: (body) => request('/hot/channels/configure', { method: 'POST', body, userAction: true }),
    hotCorrect: (body) => request('/hot/events/correct', { method: 'POST', body, userAction: true }),
    hotSourceConfigure: (body) => request('/hot/sources/configure', { method: 'POST', body, userAction: true }),
    hotResearchResults: (params) => request(`/hot/research/runs${hotQuery(params)}`),
    hotResearchRefresh: (id) => request(`/hot/research/runs/${segment(id)}/refresh`, {method:'POST',body:{},userAction:true}),
    hotResearchPrepare: (body) => request('/hot/research/handoffs', {method:'POST',body,userAction:true}),
    hotFollows: () => request('/hot/follows'),
    hotBriefPlans: () => request('/automations/hot-brief-plans'),
    hotPlanRuns: (id) => request(`/automations/hot-brief-plans/${segment(id)}/runs`),
    hotPlanConfigure: (body) => request('/automations/hot-brief-plans/configure', {method:'POST',body,userAction:true}),
    hotFollowConfigure: (body) => request('/hot/follows/configure', {method:'POST',body,userAction:true}),
    hotResearchExecute: (body) => request(`/hot/research-runs/${segment(body.runId)}/execute`, {method:'POST',body:{question:body.question,formats:body.formats},userAction:true}),
    hotBriefs: (params) => request(`/hot/briefs${hotQuery(params)}`),
    hotBrief: (id, params) => request(`/hot/briefs/${segment(id)}${hotQuery(params)}`),
    hotBriefCreate: (body) => request('/hot/briefs', { method: 'POST', body, userAction: true }),

    etfReadiness: () => request('/portfolio-decisions/readiness'),
    etfRuns: () => request('/portfolio-decisions/runs'),
    etfRun: (id) => request(`/portfolio-decisions/runs/${segment(id)}`),
    etfReplay: (body, key) => request('/portfolio-decisions/runs', { method: 'POST', body, key, userAction: true }),
    runtime: () => request('/runtime'), models: () => request('/models'), workspaces: () => request('/workspaces'),
    sessions: (view = 'active') => request(`/sessions?view=${segment(view)}`), skills: () => request('/skills'),
    searchSessions: (query, mode = 'claw') => request('/sessions/search', { method: 'POST', body: { query, mode }, readOnly: true }),
    documentOperation: (id, body) => request(`${sessionPath(id)}/document-operations`, { method: 'POST', body }),
    capabilities: () => request('/capabilities'), tools: () => request('/tools'),
    mcpRegistries: () => request('/mcp/registries'),
    mcpRegistry: (id) => request(mcpRegistryPath(id)),
    createMcpRegistry: (body) => request('/mcp/registries', { method: 'POST', body }),
    updateMcpRegistry: (id, body) => request(mcpRegistryPath(id), { method: 'PATCH', body }),
    deleteMcpRegistry: (id) => request(mcpRegistryPath(id), { method: 'DELETE' }),
    mcpSyncRegistry: (id, body = {}) => request(`${mcpRegistryPath(id)}/sync`, { method: 'POST', body }),
    mcpServers: ({ registryId, search = '', cursor = '', limit = 100 } = {}) => {
      const params = new URLSearchParams({ registry_id: String(registryId || '') });
      if (search) params.set('search', String(search));
      if (cursor) params.set('cursor', String(cursor));
      params.set('limit', String(limit));
      return request(`/mcp/servers?${params.toString()}`);
    },
    mcpServerVersion: (registryId, serverName, version) => request(`/mcp/servers/${segment(registryId)}/${segment(serverName)}/versions/${segment(version)}`),
    mcpPublisherPreview: (body) => request('/mcp/publisher/preview', { method: 'POST', body }),
    mcpPublisherValidate: (body) => request('/mcp/publisher/validate', { method: 'POST', body }),
    mcpInstallationPreview: (body) => request('/mcp/installations/preview', { method: 'POST', body }),
    mcpInstall: (body) => request('/mcp/installations', { method: 'POST', body }),
    mcpInstallations: () => request('/mcp/installations'),
    mcpInstallation: (id) => request(`/mcp/installations/${segment(id)}`),
    mcpClassifyTool: (id, body) => request(`/mcp/installations/${segment(id)}`, { method: 'PATCH', body }),
    mcpDeleteInstallation: (id) => request(`/mcp/installations/${segment(id)}`, { method: 'DELETE' }),
    mcpInstallationStatus: (id) => request(`/mcp/installations/${segment(id)}/status`),
    mcpInstallationCapabilities: (id) => request(`/mcp/installations/${segment(id)}/capabilities`),
    mcpProbeInstallation: (id) => request(`/mcp/installations/${segment(id)}/probe`, { method: 'POST', body: {} }),
    mcpEnableInstallation: (id) => request(`/mcp/installations/${segment(id)}/enable`, { method: 'POST', body: {} }),
    mcpDisableInstallation: (id) => request(`/mcp/installations/${segment(id)}/disable`, { method: 'POST', body: {} }),
    mcpUpdateInstallation: (id) => request(`/mcp/installations/${segment(id)}/update`, { method: 'POST', body: {} }),
    mcpStartOAuth: (id, body) => request(`/mcp/installations/${segment(id)}/oauth/start`, { method: 'POST', body }),
    mcpApprovals: (sessionId = '') => request(`/mcp/approvals${sessionId ? `?session_id=${segment(sessionId)}` : ''}`),
    mcpApprove: (id, body) => request(`/mcp/approvals/${segment(id)}/approve`, { method: 'POST', body }),
    mcpDeny: (id, body) => request(`/mcp/approvals/${segment(id)}/deny`, { method: 'POST', body }),
    mcpAuthorizeSession: (sessionId, body) => request(`${sessionPath(sessionId)}/mcp-authorizations`, { method: 'POST', body }),
    mcpReadResource: (sessionId, body) => request(`${sessionPath(sessionId)}/mcp/resources/read`, { method: 'POST', body }),
    mcpGetPrompt: (sessionId, body) => request(`${sessionPath(sessionId)}/mcp/prompts/get`, { method: 'POST', body }),
    reportWorkflows: () => request('/report-workflows'),
    automations: () => request('/automations'),
    automationRuns: () => request('/automation-runs'),
    deliveryChannels: () => request('/delivery-channels'),
    saveDeliveryChannel: (body) => request('/delivery-channels', { method: 'PUT', body }),
    createAutomation: (body) => request('/automations', { method: 'POST', body }),
    updateAutomation: (id, body) => request(`/automations/${segment(id)}`, { method: 'PATCH', body }),
    deleteAutomation: (id) => request(`/automations/${segment(id)}`, { method: 'DELETE' }),
    enableAutomation: (id) => request(`/automations/${segment(id)}/enable`, { method: 'POST', body: {} }),
    disableAutomation: (id) => request(`/automations/${segment(id)}/disable`, { method: 'POST', body: {} }),
    runAutomation: (id) => request(`/automations/${segment(id)}/run`, { method: 'POST', body: {} }),
    retryAutomationRun: (id) => request(`/automation-runs/${segment(id)}/retry`, { method: 'POST', body: {} }),
    previewReportScheduleMigrations: () => request('/automations/migrations/report-schedules/preview', { method: 'POST', body: {} }),
    applyReportScheduleMigrations: (workflowIds) => request('/automations/migrations/report-schedules/apply', { method: 'POST', body: { workflow_ids: workflowIds } }),
    reportWorkflow: (id) => request(`/report-workflows/${segment(id)}`),
    prepareWeeklyProduction: (id) => request(`/report-workflows/${segment(id)}/weekly-production/prepare`, { method: 'POST', body: {} }),
    publishReportWorkflowVersion: (id, version) => request(`/report-workflows/${segment(id)}/versions/${segment(version)}/publish`, { method: 'POST', body: {} }),
    runReportWorkflow: (id) => request(`/report-workflows/${segment(id)}/runs`, { method: 'POST', body: {} }),
    runHistoricalReportWorkflow: (id) => request(`/report-workflows/${segment(id)}/historical-acceptance-runs`, { method: 'POST', body: {} }),
    reportWorkflowRuns: (id) => request(`/report-workflows/${segment(id)}/runs`),
    reportProviders: () => request('/report-workflows/providers'),
    probeReportProvider: (id, key) => request(`/report-workflows/providers/${segment(id)}/probe`, { method: 'POST', body: {}, key }),
    reportRun: (id) => request(`/report-runs/${segment(id)}`),
    cancelReportRun: (id) => request(`/report-runs/${segment(id)}/cancel`, { method: 'POST', body: {} }),
    retryReportRun: (id) => request(`/report-runs/${segment(id)}/retry`, { method: 'POST', body: {} }),
    reportRunDelivery: (id) => request(`/report-runs/${segment(id)}/delivery`),
    reportRunRefreshManifests: (id) => request(`/report-runs/${segment(id)}/refresh-manifests`),
    reportSchedule: (id) => request(`/report-workflows/${segment(id)}/schedule`),
    saveReportSchedule: (id, body) => request(`/report-workflows/${segment(id)}/schedule`, { method: 'PUT', body }),
    dataCatalog: () => request('/data/catalog'),
    warehouseStatus: (options = {}) => request('/data/warehouse', options),
    warehouseControl: (body, options = {}) => request('/data/warehouse', {...options, method:'POST', body}),
    dataCapability: (id) => request(`/data/capabilities/${segment(id)}`),
    dataSource: (id) => request(`/data/sources/${segment(id)}`),
    connections: () => request('/data/connections'),
    integrations: (scope = 'all') => request(`/integrations/status?scope=${segment(scope)}`),
    startIntegrationProbeBatch: (scope, key) => request('/integrations/probe-batches', { method: 'POST', body: { scope }, key, userAction: true }),
    integrationProbeBatch: (id) => request(`/integrations/probe-batches/${segment(id)}`),
    setIntegrationConsent: (id, consent) => request(`/integrations/${segment(id)}/auto-probe-consent`, { method: 'PUT', body: { consent }, userAction: true }),
    localIntegrations: () => request('/local-integrations'),
    probeLocalIntegrations: (key) => request('/local-integrations/probes', { method: 'POST', body: {}, key }),
    localIntegrationProbe: (id) => request(`/local-integrations/probes/${segment(id)}`),
    verifyLocalIntegration: (target, key) => request('/local-integrations/verifications', { method: 'POST', body: { target }, key }),
    localIntegrationVerification: (id) => request(`/local-integrations/verifications/${segment(id)}`),
    sourceConfiguration: (id) => request(`/data/sources/${segment(id)}/configuration`),
    verifySourceAuthorization: (id) => request(`/data/sources/${segment(id)}/configuration/verify`, {method:'POST',body:{},userAction:true}),
    saveSourceConfiguration: (id, body) => request(`/data/sources/${segment(id)}/configuration`, { method: 'PUT', body }),
    deleteSourceConfiguration: (id) => request(`/data/sources/${segment(id)}/configuration`, { method: 'DELETE' }),
    connectionMigrationPreview: () => request('/data/connections/migration-preview'),
    migrateConnections: (body) => request('/data/connections/migrations', { method: 'POST', body }),
    mysqlConfiguration: () => request('/data/sources/mysql/configuration'),
    saveMysqlConfiguration: (body) => request('/data/sources/mysql/configuration', { method: 'PUT', body }),
    deleteMysqlConfiguration: () => request('/data/sources/mysql/configuration', { method: 'DELETE' }),
    probeDataSource: (id, key) => request(`/data/sources/${segment(id)}/probes`, { method: 'POST', body: {}, key }),
    dataProbe: (id) => request(`/data/probes/${segment(id)}`),
    startDataQuery: (body, key) => request('/data/queries', { method: 'POST', body, key }),
    dataQueries: (section = '') => request(`/data/queries${section ? `?section=${segment(section)}` : ''}`),
    dataQuery: (id) => request(`/data/queries/${segment(id)}`),
    datasetManifest: (sid, did) => request(`/sessions/${segment(sid)}/datasets/${segment(did)}`),
    datasetRows: (sid, did, offset = 0, limit = 200, options = {}) => request(`/sessions/${segment(sid)}/datasets/${segment(did)}/rows?offset=${segment(offset)}&limit=${segment(limit)}`, options),
    dossiers: ({ includeArchived = false, cursor, ...options } = {}) => request(`/dossiers?include_archived=${includeArchived ? 'true' : 'false'}${cursor ? `&cursor=${segment(cursor)}` : ''}`, options),
    dossier: (id, options = {}) => request(`/dossiers/${segment(id)}`, options),
    createDossier: (body, options = {}) => request('/dossiers', { ...options, method: 'POST', body }),
    updateDossier: (id, body, options = {}) => request(`/dossiers/${segment(id)}`, { ...options, method: 'PATCH', body }),
    dossierTimeline: (id, { cursor, ...options } = {}) => request(`/dossiers/${segment(id)}/timeline${cursor ? `?cursor=${segment(cursor)}` : ''}`, options),
    addDossierRecord: (id, body, options = {}) => request(`/dossiers/${segment(id)}/records`, { ...options, method: 'POST', body }),
    addDossierEvidence: (id, body, options = {}) => request(`/dossiers/${segment(id)}/evidence`, { ...options, method: 'POST', body }),
    dossierEvidence: (id, evidenceId, options = {}) => request(`/dossiers/${segment(id)}/evidence/${segment(evidenceId)}`, options),
    addDossierLink: (id, body, options = {}) => request(`/dossiers/${segment(id)}/links`, { ...options, method: 'POST', body }),
    dossierLink: (id, linkId, options = {}) => request(`/dossiers/${segment(id)}/links/${segment(linkId)}`, options),
    dossierHandoff: (id, body, options = {}) => request(`/dossiers/${segment(id)}/handoff`, { ...options, method: 'POST', body }),
    dossierSignals: (options = {}) => request('/dossiers/signals', options),
    scanDossier: (id, body, options = {}) => request(`/dossiers/${segment(id)}/scan`, { ...options, method: 'POST', body }),
    setDossierTracking: (id, body, options = {}) => request(`/dossiers/${segment(id)}/tracking`, { ...options, method: 'PATCH', body }),
    assetObservations: (options = {}) => request('/assets/observations', options),
    searchAssets: (query = '', { limit = 20, ...options } = {}) => request(`/assets/search?q=${segment(query)}&limit=${segment(limit)}`, options),
    assetObservation: (id, options = {}) => request(`/assets/observations/${segment(id)}`, options),
    assetIntraday: (id, body = {}, options = {}) => request(`/assets/observations/${segment(id)}/intraday`, { ...options, method: 'POST', body }),
    assetMinuteBars: (id, body, options = {}) => request(`/assets/observations/${segment(id)}/minute-bars`, { ...options, method: 'POST', body }),
    createAssetObservation: (body, key, options = {}) => request('/assets/observations', { ...options, method: 'POST', body, key }),
    refreshAssetBlock: (id, block, key) => request(`/assets/observations/${segment(id)}/blocks/${segment(block)}/refresh`, { method: 'POST', body: {}, key }),
    loadAssetBlock: (id, block, body, key, options = {}) => request(`/assets/observations/${segment(id)}/blocks/${segment(block)}/load`, { ...options, method: 'POST', body, key }),
    startAssetHistory: (id, body, key, options = {}) => request(`/assets/observations/${segment(id)}/history-jobs`, { ...options, method: 'POST', body, key }),
    assetHistoryJobs: (id, options = {}) => request(`/assets/observations/${segment(id)}/history-jobs`, options),
    assetHistoryJob: (id, jobId, options = {}) => request(`/assets/observations/${segment(id)}/history-jobs/${segment(jobId)}`, options),
    cancelAssetHistory: (id, jobId) => request(`/assets/observations/${segment(id)}/history-jobs/${segment(jobId)}/cancel`, { method: 'POST', body: {} }),
    assetChartPreferences: (options = {}) => request('/assets/chart-preferences', options),
    saveAssetChartPreferences: body => request('/assets/chart-preferences', { method: 'PUT', body }),
    watchlists: (options = {}) => request('/watchlists', options),
    createWatchlist: (body) => request('/watchlists', { method: 'POST', body }),
    addWatchlistItem: (id, body) => request(`/watchlists/${segment(id)}/items`, { method: 'POST', body }),
    assetNotes: (options = {}) => request('/asset-notes', options),
    createAssetNote: (body) => request('/asset-notes', { method: 'POST', body }),
    assetAlerts: (options = {}) => request('/asset-alerts', options),
    createAssetAlert: (body) => request('/asset-alerts', { method: 'POST', body }),
    assetNotifications: (options = {}) => request('/asset-notifications', options),
    handoff: (body, key) => request('/handoffs', { method: 'POST', body, key }),
    discoveryFeed: (horizon = 'medium', refresh = false, options = {}) => request(`/discovery/feed?horizon=${segment(horizon)}&refresh=${refresh ? 'true' : 'false'}`, options),
    discoveryAssociation: (feedId, newsId, eventId, horizon, options = {}) => request(`/discovery/association?feed_id=${segment(feedId)}&news_id=${segment(newsId)}&event_id=${segment(eventId)}&horizon=${segment(horizon)}`, options),
    discoverySelection: (feedId, themeId, horizon, options = {}) => request(`/discovery/selection?feed_id=${segment(feedId)}&theme_id=${segment(themeId)}&horizon=${segment(horizon)}`, options),
    discoveryPrepare: body => request('/discovery/prepare', { method: 'POST', body, userAction: true }),
    discoveryHandoff: id => request(`/discovery/handoffs/${segment(id)}`),
    discoveryHandoffs: (options = {}) => request('/discovery/handoffs', options),
    discoveryRequest: id => request(`/discovery/requests/${segment(id)}`),
    discoveryExecute: (id, body) => request(`/discovery/handoffs/${segment(id)}/execute`, { method: 'POST', body, userAction: true }),
    discoveryTracks: (options = {}) => request('/discovery/tracks', options),
    discoveryTrackSave: body => request('/discovery/tracks', { method: 'POST', body, userAction: true }),
    discoveryTrackState: (id, enabled, body) => request(`/discovery/tracks/${segment(id)}/${enabled ? 'enable' : 'disable'}`, { method: 'POST', body, userAction: true }),
    artifacts: (sessionId = '') => request(`/artifacts${sessionId ? `?session_id=${segment(sessionId)}` : ''}`),
    operationsUsage: (range = '7d') => request(`/operations/usage?range=${segment(range)}`),
    operationsTools: (range = '7d') => request(`/operations/tools?range=${segment(range)}`),
    operationsDatahub: (range = '7d') => request(`/operations/datahub?range=${segment(range)}`),
    operationsSummary: (range = '7d') => request(`/operations/summary?range=${segment(range)}`),
    operationsServices: () => request('/operations/services'),
    operationsStorage: () => request('/operations/storage'),
    frameworks: () => request('/frameworks'),
    frameworkData: (slug) => request(`/frameworks/${segment(slug)}/data`),
    createFrameworkSession: (slug, body) => request(`/frameworks/${segment(slug)}/sessions`, { method: 'POST', body }),
    frameworkMessage: (slug, id, body, key) => request(`/frameworks/${segment(slug)}/sessions/${segment(id)}/messages`, { method: 'POST', body, key }),
    verifyFrameworkSession: (slug, id, body, key) => request(`/frameworks/${segment(slug)}/sessions/${segment(id)}/verify`, { method: 'POST', body, key }),
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
    clawProjects: () => request('/claw/projects'),
    clawProject: (id) => request(`/claw/projects/${segment(id)}`),
    createClawProject: (body) => request('/claw/projects', { method: 'POST', body }),
    updateClawProject: (id, body) => request(`/claw/projects/${segment(id)}`, { method: 'PATCH', body }),
    navigation: mode => request(`/navigation/${segment(mode)}`),
    saveNavigation: (mode, body) => request(`/navigation/${segment(mode)}`, { method: 'PATCH', body }),
    projects: mode => request(`/projects?mode=${segment(mode)}`),
    project: (mode, id) => request(`/projects/${segment(id)}?mode=${segment(mode)}`),
    createProject: (mode, body) => request(`/projects?mode=${segment(mode)}`, { method: 'POST', body }),
    updateProject: (mode, id, body) => request(`/projects/${segment(id)}?mode=${segment(mode)}`, { method: 'PATCH', body }),
    moveClawSession: (id, projectId) => request(`${sessionPath(id)}/project`, { method: 'PUT', body: { project_id: projectId } }),
    referenceClawFile: (id, body) => request(`${sessionPath(id)}/file-references`, { method: 'POST', body }),
    confirmAutomationDraft: (id, draftId, body, enable = false) => request(`${sessionPath(id)}/automation-drafts/${segment(draftId)}/confirm${enable ? "?enable=true" : ""}`, { method: 'POST', body }),
    dismissAutomationDraft: (id, draftId) => request(`${sessionPath(id)}/automation-drafts/${segment(draftId)}/dismiss`, { method: 'POST', body: {} }),
    detail: (id) => request(sessionPath(id)),
    message: (id, body, key) => request(`${sessionPath(id)}/messages`, { method: 'POST', body, key }),
    rename: (id, title) => request(sessionPath(id), { method: 'PATCH', body: { title } }),
    deleteSession: (id) => request(sessionPath(id), { method: 'DELETE' }),
    restoreSession: (id) => request(`${sessionPath(id)}/restore`, { method: 'POST', body: {} }),
    purgeSession: (id) => request(`${sessionPath(id)}/permanent`, { method: 'DELETE' }),
    cancel: (id) => request(`${sessionPath(id)}/cancel`, { method: 'POST', body: {} }),
    upgrade: (id) => request(`${sessionPath(id)}/upgrade`, { method: 'POST', body: {} }),
    files: (id) => request(`${sessionPath(id)}/files`),
    upload: (id, files) => { const body = new FormData(); for (const file of files) body.append('files', file); return request(`${sessionPath(id)}/uploads`, { method: 'POST', body }); },
    approve: (id, approval, decision) => request(`${sessionPath(id)}/approvals/${segment(approval)}`, { method: 'POST', body: { decision } }),
    answer: (id, question, answers) => request(`${sessionPath(id)}/questions/${segment(question)}`, { method: 'POST', body: { answers } }),
    configure: (body) => request('/runtime/model', { method: 'PUT', body }),
    modelProfiles: () => request('/model-profiles'),
    saveModelProfile: (id, body) => request(id ? `/model-profiles/${segment(id)}` : '/model-profiles', { method: id ? 'PUT' : 'POST', body }),
    activateModelProfile: id => request(`/model-profiles/${segment(id)}/activate`, { method: 'POST', body: {} }),
    archiveModelProfile: id => request(`/model-profiles/${segment(id)}`, { method: 'DELETE' }),
    testModel: () => request('/runtime/model/test', { method: 'POST', body: {} }),
    tabbitStatus: () => request('/runtime/tabbit'),
    configureTabbit: (body) => request('/runtime/tabbit', { method: 'PUT', body }),
    tabbitAccess: (id, decision) => request(`${sessionPath(id)}/tabbit-access`, { method: 'POST', body: { decision } }),
    tabbitTabs: (id, query = '', limit = 50) => request(`${sessionPath(id)}/tabbit-tabs?q=${segment(query)}&limit=${segment(limit)}`),
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

export function createController({ api, draftStorage, logger = safeLog, makeID = () => globalThis.crypto.randomUUID(), onNavigate = () => {}, getAccount = () => globalThis.__RWB_USER_ID__ || 'local', confirmTabbit = async () => globalThis.confirm?.('所选标签页将临时移入代理任务，标签分组可能改变。继续发送？') !== false }) {
  const state = { route: { page: 'fingpt', sessionId: null }, detail: null, draft: '', dossierHandoff: null, attachments: [], tabbitTabs: [], skillId: '', capability: null, toolIds: [], methodIds: [], sourceScope: ['datahub', 'web', 'uploads'], researchDepth: 'instant', researchMode: 'quick', researchAsOf: '', expectedFormats: null, error: '', streamError: '', loading: false, busy: false, stopping: false };
  const listeners = new Set(); const drafts = new Map(); const pending = new Map(); const createdDraftOrigins = new Map(); const sendingSessions = new Set();
  let generation = 0; let snapshotRevision = 0; let closeStream = () => {}; let hasOpened = false;
  const emit = () => listeners.forEach((listener) => listener(state));
  const draftKey = () => state.route.sessionId || `new:${state.route.page}`;
  const researchMode = (value, depth) => ['quick', 'deep', 'agent'].includes(value) ? value : depth === 'deep' ? 'deep' : 'quick';
  const validResearchAsOf = value => value === '' || (typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) && !value.startsWith('0000-') && Number.isFinite(Date.parse(value)) && new Date(value).toISOString().slice(0, 10) === value);
  const draftState = () => ({ draft: state.draft, dossierHandoff: state.dossierHandoff, attachments: state.attachments, tabbitTabs: state.tabbitTabs, skillId: state.skillId, capability: state.capability, toolIds: state.toolIds, methodIds: state.methodIds, sourceScope: state.sourceScope, researchDepth: state.researchDepth, researchMode: state.researchMode, researchAsOf: state.researchAsOf, expectedFormats: state.expectedFormats });
  const controllerAccount = String(getAccount());
  let dossierScopeID = null;
  const validDossierHandoff = value => value == null || typeof value === 'object' && /^[a-f0-9]{32}$/.test(value.id || '') && /^[a-f0-9]{32}$/.test(value.dossierID || '') && Object.keys(value).every(key => ['id', 'dossierID'].includes(key));
  const accountCurrent = () => {
    if (controllerAccount === String(getAccount())) return true;
    state.dossierHandoff = null; state.draft = ''; state.attachments = []; drafts.clear(); pending.clear();
    state.error = '账户已变化，请重新加载页面后继续研究。'; logger('dossier_draft_account_changed'); emit(); return false;
  };
  if (draftStorage === undefined) {
    try { draftStorage = globalThis.sessionStorage; } catch { logger('draft_storage_unavailable', {}); }
  }
  const userNamespace = /^[a-f0-9-]{36}$/.test(controllerAccount) ? `user:${controllerAccount}:` : '';
  const storageKey = id => `research-web:${userNamespace}explicit-draft:v1:${id}`;
  const validDraft = value => typeof value?.draft === 'string' && Array.isArray(value.attachments) && value.attachments.length <= 100 && value.attachments.every(file => typeof file?.id === 'string' && /^[A-Za-z0-9_-]{1,255}$/.test(file.id) && typeof file.name === 'string' && file.name.length <= 500);
  const draftAttachment = file => {
    const result = { id: file.id, name: file.name };
    const validators = {
      source_name: value => typeof value === 'string' && value.length > 0 && value.length <= 500 && !/[\u0000-\u001f\u007f]/.test(value),
      source_session_id: value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,255}$/.test(value),
      source_file_id: value => typeof value === 'string' && /^[A-Za-z0-9_-]{1,255}$/.test(value),
    };
    for (const [field, validate] of Object.entries(validators)) {
      if (file[field] === undefined) continue;
      if (validate(file[field])) result[field] = file[field];
      else logger('draft_attachment_source_invalid', {});
    }
    return result;
  };
  const pendingSelection = value => ({
    skillId: value.skillId || '',
    capability: value.capability ? { id: value.capability.id, version: value.capability.version, name: value.capability.name || value.capability.id } : null,
    toolIds: value.toolIds || [], methodIds: value.methodIds || [], expectedFormats: value.expectedFormats ?? null,
    ...(value.researchAsOf !== undefined ? { researchAsOf: value.researchAsOf } : {}),
    ...(value.dossierHandoff ? { dossierHandoff: value.dossierHandoff } : {}),
    tabbitTabs: (value.tabbitTabs || []).map(({ tab_id, instance_id, title }) => ({ tab_id, instance_id, ...(typeof title === 'string' ? { title: title.slice(0, 500) } : {}) })),
  });
  const restorePending = (id, value) => {
    const attempt = value.pending;
    if (!attempt) return {};
    try {
      const identifier = value => typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,255}$/.test(value);
      if (attempt.session_id !== id || !identifier(attempt.key) || typeof attempt.signature !== 'string' || attempt.signature.length > 200000) throw new Error('pending_identity_invalid');
      const request = JSON.parse(attempt.signature);
      if (typeof request?.text !== 'string' || (request.research_as_of !== undefined && !validResearchAsOf(request.research_as_of))) throw new Error('pending_request_invalid');
      const selection = attempt.selection;
      const identifiers = (value, max) => Array.isArray(value) && value.length <= max && value.every(identifier);
      if (!selection || (selection.skillId !== '' && !identifier(selection.skillId)) || !identifiers(selection.toolIds, 3) || !identifiers(selection.methodIds, 3)) throw new Error('pending_selection_invalid');
      if (selection.researchAsOf !== undefined && !validResearchAsOf(selection.researchAsOf)) throw new Error('pending_cutoff_invalid');
      if (!validDossierHandoff(selection.dossierHandoff) || request.dossier_handoff_id !== selection.dossierHandoff?.id) throw new Error('pending_dossier_handoff_invalid');
      if (selection.capability && (!identifier(selection.capability.id) || !Number.isInteger(selection.capability.version) || selection.capability.version < 1)) throw new Error('pending_capability_invalid');
      if (selection.expectedFormats !== null && (!Array.isArray(selection.expectedFormats) || selection.expectedFormats.length > 7 || selection.expectedFormats.some(format => !['md', 'html', 'docx', 'xlsx', 'pptx', 'png', 'pdf'].includes(format)))) throw new Error('pending_formats_invalid');
      if (!Array.isArray(selection.tabbitTabs) || selection.tabbitTabs.length > 8 || selection.tabbitTabs.some(tab => !Number.isInteger(tab?.tab_id) || tab.tab_id < 0 || !identifier(tab.instance_id))) throw new Error('pending_tabs_invalid');
      pending.set(id, { signature: attempt.signature, key: attempt.key, durable: true });
      logger('pending_submission_restored', {});
      return { researchAsOf: request.research_as_of ?? '', ...pendingSelection(selection) };
    } catch {
      logger('pending_submission_restore_failed', {});
      state.error = '未能恢复上次提交的重试凭据；草稿已保留，请先核对会话记录。';
      return {};
    }
  };
  const persistDraft = (id, value) => {
    if (!draftStorage) return true;
    try {
      if (!validDraft(value)) throw new Error('draft_invalid');
      if (!validResearchAsOf(value.researchAsOf ?? '')) throw new Error('draft_cutoff_invalid');
      const record = { draft: value.draft, attachments: value.attachments.map(draftAttachment), researchMode: researchMode(value.researchMode, value.researchDepth), researchAsOf: value.researchAsOf ?? '' };
      if (!validDossierHandoff(value.dossierHandoff)) throw new Error('draft_dossier_handoff_invalid');
      if (value.dossierHandoff) record.dossierHandoff = { ...value.dossierHandoff };
      if (JSON.stringify(record).length > 200000) throw new Error('draft_too_large');
      const attempt = pending.get(id);
      if (attempt?.durable) record.pending = { session_id: id, signature: attempt.signature, key: attempt.key, selection: pendingSelection(value) };
      const serialized = JSON.stringify(record);
      if (serialized.length > 400000) throw new Error('draft_too_large');
      draftStorage.setItem(storageKey(id), serialized);
      return true;
    } catch { logger('draft_storage_write_failed', {}); state.error = '草稿仍保留在页面中，但无法保存刷新恢复副本。'; return false; }
  };
  const putDraft = (id, value) => { drafts.set(id, value); return persistDraft(id, value); };
  const readDraft = id => {
    if (drafts.has(id)) return drafts.get(id);
    if (!draftStorage) return undefined;
    try {
      const raw = draftStorage.getItem(storageKey(id));
      if (!raw) return undefined;
      if (raw.length > 400000) throw new Error('draft_too_large');
      let value = JSON.parse(raw);
      if (!validDraft(value)) throw new Error('draft_invalid');
      if (!validDossierHandoff(value.dossierHandoff)) throw new Error('draft_dossier_handoff_invalid');
      if (dossierScopeID !== null && value.dossierHandoff && value.dossierHandoff.dossierID !== dossierScopeID) {
        value = { ...value, dossierHandoff: null }; delete value.pending; persistDraft(id, value); logger('dossier_draft_scope_cleared');
      }
      const mode = researchMode(value.researchMode, value.researchDepth);
      const savedDate = Object.hasOwn(value, 'researchAsOf') ? { researchAsOf: validResearchAsOf(value.researchAsOf) ? value.researchAsOf : '' } : {};
      if (Object.hasOwn(value, 'researchAsOf') && !validResearchAsOf(value.researchAsOf)) { logger('draft_cutoff_restore_failed', {}); state.error = '草稿截止日期无效，已保留问题和附件，请重新选择日期。'; }
      if (JSON.stringify({ draft: value.draft, attachments: value.attachments }).length > 200000) throw new Error('draft_too_large');
      return { draft: value.draft, dossierHandoff: value.dossierHandoff || null, attachments: value.attachments.map(draftAttachment), tabbitTabs: [], skillId: '', methodIds: [], ...restorePending(id, value), ...savedDate, ...(value.researchMode !== undefined || value.researchDepth !== undefined ? { researchMode: mode, researchDepth: mode === 'quick' ? 'instant' : 'deep' } : {}) };
    } catch { logger('draft_storage_read_failed', {}); state.error = '草稿恢复副本无效；请重新选择附件。'; return undefined; }
  };
  const saveDraft = () => putDraft(draftKey(), draftState());
  function clearDossierHandoff(nextDossierID = '') {
    dossierScopeID = nextDossierID;
    for (const [key, value] of drafts) {
      if (value.dossierHandoff && value.dossierHandoff.dossierID !== nextDossierID) { pending.delete(key); putDraft(key, { ...value, dossierHandoff: null }); }
    }
    if (state.dossierHandoff && state.dossierHandoff.dossierID !== nextDossierID) { state.dossierHandoff = null; pending.delete(draftKey()); saveDraft(); }
  }
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
    if (!accountCurrent()) return;
    if (hasOpened) saveDraft(); hasOpened = true; const ticket = ++generation; closeStream(); closeStream = () => {};
    state.route = route; state.detail = null; state.error = ''; state.streamError = ''; state.loading = Boolean(route.sessionId); state.busy = false; state.stopping = false;
    const savedDraft = readDraft(draftKey());
    Object.assign(state, { sourceScope: ["datahub", "web", "uploads"], researchDepth: "instant", researchMode: 'quick', researchAsOf: '', dossierHandoff: null, expectedFormats: null, capability: null, toolIds: [], methodIds: [], tabbitTabs: [] }, savedDraft || { draft: '', attachments: [], tabbitTabs: [], skillId: '', methodIds: [] }); emit();
    if (!route.sessionId) return;
    try {
      const data = await api.detail(route.sessionId);
      if (ticket !== generation) return;
      snapshot(data);
      if (!savedDraft?.researchMode) {
        state.researchMode = researchMode(data.research_mode, data.research_depth);
        state.researchDepth = state.researchMode === 'quick' ? 'instant' : 'deep';
      }
      if (data.mode === 'fingpt' && !Object.hasOwn(savedDraft || {}, 'researchAsOf') && data.research_quality?.as_of && validResearchAsOf(data.research_quality.as_of)) state.researchAsOf = data.research_quality.as_of;
      if (api.events) closeStream = api.events(route.sessionId, {
        snapshot: (next) => { if (ticket === generation) { try { snapshot(next); state.streamError = ''; emit(); } catch (error) { fail(error); emit(); } } },
        error: (message) => { if (ticket === generation) { state.streamError = message; emit(); } },
        open: async () => { if (ticket === generation) await refresh(); },
      });
    } catch (error) { if (ticket === generation) fail(error); }
    finally { if (ticket === generation) { state.loading = false; emit(); } }
  }
  async function send() {
    if (!accountCurrent()) return;
    if (state.busy || state.stopping || !state.detail || !state.draft.trim()) return;
    const id = state.detail.id; const ticket = generation; const text = state.draft;
    if (sendingSessions.has(id)) return;
    const execution = state.detail.execution_context;
    let body;
    if (execution) {
      const definition = execution.definition_snapshot;
      const task = definition?.research_task;
      if (!Array.isArray(definition?.output_formats) || !Array.isArray(task?.approved_tools) || !Array.isArray(task?.approved_data_sources)) { fail(new Error('日程执行定义缺少批准范围，无法发送追问；请刷新会话。')); emit(); return; }
      body = {text:text.trim(),tool_ids:[...task.approved_tools],expected_formats:[...definition.output_formats],...(task.approved_data_sources.includes('uploads') && state.attachments.length ? {attachment_ids:state.attachments.map(file=>file.id)} : {})};
      logger('execution_followup_scope_locked');
    } else body = { text: text.trim(), ...(state.capability ? { capability_id: state.capability.id, capability_version: state.capability.version } : state.skillId ? { skill_id: state.skillId } : {}), ...(state.toolIds.length ? { tool_ids: [...state.toolIds] } : {}), ...(state.methodIds.length ? { method_ids: [...state.methodIds] } : {}), ...(state.expectedFormats !== null ? { expected_formats: [...state.expectedFormats] } : {}), ...(state.attachments.length ? { attachment_ids: state.attachments.map((file) => file.id) } : {}), ...(state.tabbitTabs.length ? { tabbit_tabs: state.tabbitTabs.map(({ tab_id, instance_id }) => ({ tab_id, instance_id })), tabbit_live_confirmed: true } : {}) };
    if (!execution && state.detail.mode === 'fingpt') {
      body.research_mode = state.researchMode;
      if (state.researchAsOf) body.research_as_of = state.researchAsOf;
    }
    if (!execution && state.dossierHandoff) body.dossier_handoff_id = state.dossierHandoff.id;
    // Bind confirmation and accepted cleanup to the submitted snapshot, never the next draft.
    const attachmentIds = new Set(body.attachment_ids || []);
    const tabIdentity = tab => JSON.stringify([tab.instance_id, tab.tab_id]);
    const tabIds = new Set((body.tabbit_tabs || []).map(tabIdentity));
    const acceptedDraft = value => ({ ...value, draft: value.draft === text ? '' : value.draft, dossierHandoff: value.dossierHandoff?.id === body.dossier_handoff_id ? null : value.dossierHandoff,
      attachments: value.attachments.filter(file => !attachmentIds.has(file.id)),
      tabbitTabs: (value.tabbitTabs || []).filter(tab => !tabIds.has(tabIdentity(tab))) });
    sendingSessions.add(id); state.busy = true; state.error = ''; emit();
    try {
      if (tabIds.size) {
        const confirmed = await confirmTabbit();
        if (ticket !== generation) { logger('send_confirmation_navigation_cancelled'); return; }
        if (!confirmed) return;
      }
      const signature = JSON.stringify(body); const previous = pending.get(id);
      const attempt = previous?.signature === signature ? previous : { signature, key: makeID(), durable: !execution && (state.detail.mode === 'fingpt' || Boolean(body.dossier_handoff_id)) };
      pending.set(id, attempt);
      if (attempt.durable && !putDraft(id, draftState())) throw new Error('无法保存提交重试凭据，本次问题尚未发送；请恢复浏览器存储后重试。');
      const response = await api.message(id, body, attempt.key);
      if (!accountCurrent()) return;
      if (response.accepted !== true) throw new Error('运行时未确认接收，请检查会话后重试。');
      pending.delete(id);
      if (body.dossier_handoff_id) {
        // A page reload may leave only the active session in memory. The two
        // durable homepage drafts still need the same receipt cleanup.
        for (const key of new Set([...drafts.keys(), 'new:claw', 'new:fingpt'])) {
          const value = readDraft(key);
          if (key !== id && value?.dossierHandoff?.id === body.dossier_handoff_id) {
            pending.delete(key); putDraft(key, { ...value, dossierHandoff: null });
            if (draftKey() === key && state.dossierHandoff?.id === body.dossier_handoff_id) state.dossierHandoff = null;
          }
        }
      }
      const origin = createdDraftOrigins.get(id);
      createdDraftOrigins.delete(id);
      if (origin && origin.draft === text) {
        const homepage = readDraft(origin.key);
        if (homepage?.draft === origin.draft) {
          putDraft(origin.key,{...homepage,draft:'',dossierHandoff:homepage.dossierHandoff?.id === body.dossier_handoff_id ? null : homepage.dossierHandoff});
          if (draftKey() === origin.key && state.draft === origin.draft) { state.draft = ''; state.dossierHandoff = null; emit(); }
          logger('accepted_initial_draft_cleared');
        }
      }
      if (state.route.sessionId === id) {
        Object.assign(state, acceptedDraft(draftState())); saveDraft(); await refresh();
      } else {
        const saved = readDraft(id); if (saved) putDraft(id, acceptedDraft(saved));
      }
      logger('submitted_materials_accepted');
    } catch (error) { logger('message_submit_failed'); if (ticket === generation) fail(error); }
    finally { sendingSessions.delete(id); if (ticket === generation) { state.busy = false; emit(); } }
  }
  async function action(operation, { refreshAfter = true } = {}) {
    if (state.busy || state.stopping) return null;
    const ticket = generation; state.busy = true; state.error = ''; emit();
    try { const result = await operation(); if (ticket === generation && refreshAfter) await refresh(); return result; }
    catch (error) { if (ticket === generation) fail(error); return null; }
    finally { if (ticket === generation) { state.busy = false; emit(); } }
  }
  async function cancel() {
    if (state.stopping || !state.detail) return null;
    const ticket = generation; const id = state.detail.id;
    state.stopping = true; state.error = ''; emit();
    try {
      const result = await api.cancel(id);
      if (result?.accepted !== true) throw new Error('停止尚未确认，请重新核对会话状态。');
      if (ticket === generation) await refresh();
      return result;
    } catch (error) { if (ticket === generation) fail(error); return null; }
    finally { if (ticket === generation) { state.stopping = false; emit(); } }
  }
  return {
    state, subscribe: (listener) => { listeners.add(listener); return () => listeners.delete(listener); }, open, refresh, send, action, cancel,
    setSourceScope: (value) => { if (!Array.isArray(value) || !value.length || value.some(s => !["datahub", "web", "uploads"].includes(s))) throw new Error("至少选择一个资料范围"); state.sourceScope = [...new Set(value)]; saveDraft(); emit(); },
    setResearchDepth: (value) => { if (!["instant", "deep"].includes(value)) throw new Error("不支持的研究深度"); state.researchDepth = value; state.researchMode = value === 'deep' ? 'deep' : 'quick'; saveDraft(); emit(); },
    setResearchMode: (value) => { if (!['quick', 'deep', 'agent'].includes(value)) throw new Error('不支持的研究模式'); state.researchMode = value; state.researchDepth = value === 'quick' ? 'instant' : 'deep'; logger('research_mode_selected', { mode: value }); saveDraft(); emit(); },
    setResearchAsOf: (value) => { if (!validResearchAsOf(value)) throw new Error('研究截止日期须为有效的 YYYY-MM-DD 日期；留空时新研究默认今日，续研沿用原截止日期。'); state.researchAsOf = value; logger('research_cutoff_selected', { configured: Boolean(value) }); saveDraft(); emit(); },
    setDraft: (value) => { state.draft = value; if (!value.trim()) { state.dossierHandoff = null; pending.delete(draftKey()); } saveDraft(); },
    setDossierDraft: (prompt, context) => {
      if (!accountCurrent()) return false;
      const receipt = { id: context?.handoff_id, dossierID: context?.dossier_id };
      if (typeof prompt !== 'string' || !prompt.trim() || !validDossierHandoff(receipt)) throw new Error('档案研究交接凭据无效，请重新准备草稿。');
      dossierScopeID = receipt.dossierID; state.dossierHandoff = receipt; state.draft = prompt; saveDraft(); logger('dossier_research_draft_prepared'); return true;
    },
    clearDossierHandoff,
    setSkill: (value) => { state.skillId = value; state.capability = null; saveDraft(); },
    setCapability: (value) => {
      if (value && (value.enabled !== true || !Number.isInteger(value.version) || value.version < 1)) throw new Error('只能选择已启用的已发布能力版本。');
      state.capability = value ? structuredClone(value) : null; state.skillId = value?.id || ''; saveDraft();
    },
    setTools: (values) => { state.toolIds = [...new Set(values)]; saveDraft(); },
    setMethods: (values) => {
      const unique = [...new Set(values)];
      if (unique.length > 3) throw new Error('最多选择三个方法');
      state.methodIds = unique; saveDraft();
    },
    setFormats: (value) => { state.expectedFormats = value === null ? null : [...new Set(value)]; saveDraft(); },
    addAttachments: (items) => { state.attachments = [...new Map([...state.attachments, ...items].map((file) => [file.id, file])).values()]; saveDraft(); emit(); },
    addAttachmentsForSession: (id, items) => {
      if (state.route.sessionId === id) {
        state.attachments = [...new Map([...state.attachments, ...items].map(file => [file.id, file])).values()]; saveDraft(); emit();
      } else {
        const saved = readDraft(id) || { draft: '', attachments: [], tabbitTabs: [], skillId: '', capability: null, toolIds: [], methodIds: [], expectedFormats: null };
        putDraft(id, { ...saved, attachments: [...new Map([...saved.attachments, ...items].map(file => [file.id, file])).values()] });
      }
    },
    removeAttachment: (id) => { state.attachments = state.attachments.filter((file) => file.id !== id); saveDraft(); emit(); },
    addTabbit: (item) => {
      if (state.tabbitTabs.some((tab) => tab.tab_id === item.tab_id && tab.instance_id === item.instance_id)) return;
      if (state.tabbitTabs.length >= 8) throw new Error('每条消息最多选择 8 个实时标签页。');
      if (state.tabbitTabs.length && state.tabbitTabs[0].instance_id !== item.instance_id) throw new Error('一次只能选择同一个 Tabbit 实例的标签页。');
      state.tabbitTabs = [...state.tabbitTabs, structuredClone(item)]; saveDraft(); emit();
    },
    removeTabbit: (tabId) => { state.tabbitTabs = state.tabbitTabs.filter((item) => item.tab_id !== Number(tabId)); saveDraft(); emit(); },
    create: async (mode, workspaceId, projectId) => {
      if (!accountCurrent()) return null;
      const ticket = generation;
      const previousDraft = { ...draftState(), attachments: [] };
      const origin = !state.route.sessionId ? {key:draftKey(),draft:previousDraft.draft} : null;
      const result = await action(() => api.create({ mode, research_depth: state.researchDepth, ...(mode === 'fingpt' ? { research_mode: state.researchMode } : {}), source_scope: state.sourceScope, ...(workspaceId ? { workspace_id: workspaceId } : {}), ...(projectId ? { project_id: projectId } : {}) }), { refreshAfter: false });
      if (!accountCurrent()) return null;
      if (ticket !== generation) return null;
      if (result?.id) { putDraft(result.id, previousDraft); if (origin) { createdDraftOrigins.set(result.id,origin); putDraft(origin.key, previousDraft); } onNavigate(sessionHash(result)); }
      return result;
    },
    createCapabilitySession: async (kind, goal) => {
      const ticket = generation;
      const result = await action(() => api.createCapabilitySession(kind, goal), { refreshAfter: false });
      if (ticket !== generation) return null;
      if (result?.id && typeof result.draft === 'string') {
        drafts.set(result.id, { draft: result.draft, attachments: [], tabbitTabs: [], skillId: '', capability: null, toolIds: [], expectedFormats: null });
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
