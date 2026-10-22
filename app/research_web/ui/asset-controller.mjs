import { safeLog } from './core.mjs';
import { selectAssetObservation } from './asset-navigation.mjs';

const ACTIVE = new Set(['queued', 'running', 'cancelling', 'draining']);
const jobStatus = job => job?.state || job?.status;
const identity = observation => `${observation?.asset_type || 'stock'}:${observation?.asset || ''}`;
const cloneObservation = observation => ({ ...observation, blocks: Object.fromEntries(Object.entries(observation.blocks || {}).map(([key, block]) => [key, { ...block }])) });
const validPanels = panels => Array.isArray(panels) && panels.length <= 4 && new Set(panels).size === panels.length && panels.every(panel => ['volume', 'macd', 'kdj', 'rsi'].includes(panel));
const VIEW_BLOCKS = { overview: ['overview', 'valuation'], financials: ['financials', 'valuation'], capital: ['activity', 'margin'], holders: ['holders', 'holder_details'], materials: ['research', 'industry', 'events'], news: [], announcements: [] };
const currentAccount = () => String(globalThis.__RWB_USER_ID__ || 'single-user');

/** Read an immutable snapshot using actual returned progress, including short pages. */
export async function readAssetDatasetRows(api, sessionId, dataset, { signal, isCurrent = () => true } = {}) {
  const rows = []; const expected = dataset?.row_count;
  const check = () => { if (signal?.aborted || !isCurrent()) { const error = new Error('快照读取已取消'); error.name = 'AbortError'; throw error; } };
  try {
    check();
    if (!dataset?.dataset_id || !Number.isSafeInteger(expected) || expected < 0) throw new Error('快照记录数异常');
    while (rows.length < expected) {
      check(); const offset = rows.length;
      const result = await api.datasetRows(sessionId, dataset.dataset_id, offset, 200, { signal });
      check();
      if (!result || !Array.isArray(result.items) || result.items.some(row => !row || typeof row !== 'object' || Array.isArray(row))) throw new Error('快照行格式异常');
      if (result.total !== undefined && (!Number.isSafeInteger(result.total) || result.total !== expected)) throw new Error('快照记录总数已变化');
      if (result.offset !== undefined && result.offset !== offset) throw new Error('快照分页偏移异常');
      if (result.items.length > 200 || rows.length + result.items.length > expected) throw new Error('快照分页超出声明范围');
      if (!result.items.length) throw new Error('快照记录未完整读取，请重试。');
      rows.push(...result.items);
    }
    check(); return rows;
  } catch (error) { error.partialRows = rows; throw error; }
}

export function createAssetWorkspaceController({ api, onChange = () => {}, pollIntervalMs = 500 } = {}) {
  const state = { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [], errors: {}, loading: false, loadingBlocks: {}, historyJob: null, preferences: { panels: ['volume', 'macd'] } };
  const blockReads = new Map();
  const creationKeys = new Map();
  let account = currentAccount();
  let generation = 0; let readAbort; let historyContext = null; let preferencesLoaded = false; let preferenceVersion = 0; let preferenceQueue = Promise.resolve(); let persistedPreferences = state.preferences;
  const currentHistory = context => account === currentAccount() && historyContext === context && !context.cancelled && state.observation?.id === context.observationId && identity(state.observation) === context.identity;
  const notify = () => onChange();
  async function cancelCaptured(context) {
    if (!context?.job?.id || !ACTIVE.has(jobStatus(context.job))) return;
    try { await api.cancelAssetHistory(context.observationId, context.job.id); }
    catch (error) { safeLog('asset_history_cancel_failed', { status: error.code || 'request_failed' }); }
  }
  function cancel({ stopHistory = true } = {}) {
    generation++; readAbort?.abort(); readAbort = null; state.loading = false;
    for (const context of blockReads.values()) context.abort.abort();
    blockReads.clear(); state.loadingBlocks = {};
    if (stopHistory && historyContext) {
      const previous = historyContext; previous.cancelled = true; previous.abort.abort(); historyContext = null;
      void cancelCaptured(previous);
    }
  }
  function checkAccount() {
    if (account === currentAccount()) return;
    cancel(); account = currentAccount(); creationKeys.clear(); preferencesLoaded = false; preferenceVersion++;
    persistedPreferences = { panels: ['volume', 'macd'] };
    Object.assign(state, { observations: [], observation: null, rows: {}, watchlists: [], notes: [], alerts: [], notifications: [], errors: {}, historyJob: null, preferences: persistedPreferences });
  }
  async function installHistory(context, job) {
    if (job.current_dataset?.dataset_id && job.current_dataset.dataset_id === state.observation?.blocks?.history?.dataset?.dataset_id) return;
    if (!api.assetObservation || !currentHistory(context)) return;
    const observation = await api.assetObservation(context.observationId, { signal: context.abort.signal });
    if (!currentHistory(context)) return;
    if (observation?.id !== context.observationId || identity(observation) !== context.identity || observation.session_id !== state.observation.session_id) throw new Error('历史快照资产身份异常');
    const dataset = observation?.blocks?.history?.dataset;
    if (!dataset?.dataset_id || dataset.dataset_id === state.observation?.blocks?.history?.dataset?.dataset_id) return;
    const rows = await readAssetDatasetRows(api, observation.session_id, dataset, { signal: context.abort.signal, isCurrent: () => currentHistory(context) });
    if (!currentHistory(context)) return;
    // Metadata and complete rows are published together; the prior price basis remains during reads.
    const blocks = { ...state.observation.blocks, history: { ...observation.blocks.history } };
    state.observation = { ...state.observation, blocks, history_job: job, updated_at: observation.updated_at, dataset_ids: Object.values(blocks).map(block => block?.dataset?.dataset_id).filter(Boolean) };
    state.rows = { ...state.rows, history: rows };
    state.observations = state.observations.map(item => item.id === observation.id ? state.observation : item);
    delete state.errors.historyJobs; notify();
  }
  async function followHistory(context, first) {
    let job = first; context.following = true;
    try {
    while (currentHistory(context)) {
      context.job = job; state.historyJob = job; notify();
      if (job.current_dataset || jobStatus(job) === 'completed') {
        try { await installHistory(context, job); }
        catch (error) { if (!currentHistory(context)) return; state.errors.historyJobs = `新行情快照读取失败，保留当前数据与复权口径：${error.message}`; safeLog('asset_history_snapshot_failed', { status: error.code || 'snapshot_read_failed' }); notify(); }
      }
      if (!currentHistory(context)) return;
      if (!ACTIVE.has(jobStatus(job))) { historyContext = null; return; }
      await new Promise(resolve => setTimeout(resolve, pollIntervalMs));
      if (!currentHistory(context)) return;
      job = await api.assetHistoryJob(context.observationId, job.id, { signal: context.abort.signal });
      if (!currentHistory(context)) return;
    }
    } finally { context.following = false; }
  }
  async function startHistory(scope = 'recent', adjustment = 'none', retryOf) {
    const observation = state.observation;
    if (!observation?.id || !api.startAssetHistory || historyContext) return;
    if (!['recent', 'older', 'all'].includes(scope) || !['none', 'qfq', 'hfq'].includes(adjustment)) { state.errors.historyJobs = '历史加载参数无效'; notify(); return; }
    const context = { observationId: observation.id, identity: identity(observation), key: globalThis.crypto.randomUUID(), cancelled: false, abort: new AbortController(), job: null };
    historyContext = context; delete state.errors.historyJobs;
    state.historyJob = { status: 'queued', scope, adjustment, request_key: context.key }; notify();
    try {
      let job;
      try {
        // Creation is intentionally not tied to read cancellation: a late 202 identifies the exact job.
        job = await api.startAssetHistory(context.observationId, { scope, adjustment, ...(retryOf ? { retry_of: retryOf } : {}) }, context.key);
      } catch (error) {
        if (error.status >= 400 && error.status < 500) { context.rejected = true; throw error; }
        safeLog('asset_history_submit_reconcile', { status: error.code || 'request_failed' });
        const list = api.assetHistoryJobs ? await api.assetHistoryJobs(context.observationId) : { items: [] };
        job = list.items?.find(item => item.request_key === context.key);
        if (!job) throw new Error('提交结果未知；未重复提交。请刷新任务状态后核对。');
      }
      if (!job?.id) throw new Error('历史任务响应缺少身份');
      context.job = job;
      if (!currentHistory(context)) { await cancelCaptured(context); return; }
      if (context.stopRequested) {
        job = await api.cancelAssetHistory(context.observationId, job.id);
        if (!currentHistory(context)) return;
      }
      await followHistory(context, job);
    } catch (error) {
      if (!currentHistory(context)) return;
      state.errors.historyJobs = error.message; safeLog('asset_history_job_failed', { status: error.code || 'request_failed' });
      if (context.rejected) { historyContext = null; state.historyJob = { ...state.historyJob, status: 'failed', failure_code: error.code || 'request_rejected' }; }
      else if (!context.job?.id) state.historyJob = { ...state.historyJob, status: 'unknown', submission_unknown: true };
      notify();
    }
  }
  async function stopHistory() {
    const context = historyContext; const job = context?.job || state.historyJob;
    if (context && !context.job?.id) { context.stopRequested = true; state.historyJob = { ...state.historyJob, status: 'cancelling' }; notify(); return; }
    if (!job?.id || !state.observation?.id || !ACTIVE.has(jobStatus(job))) return;
    const observationId = context?.observationId || state.observation.id;
    try { const result = await api.cancelAssetHistory(observationId, job.id); if (context && currentHistory(context)) { context.job = result; state.historyJob = result; notify(); } }
    catch (error) { if (!context || currentHistory(context)) { state.errors.historyJobs = error.message; notify(); } safeLog('asset_history_stop_failed', { status: error.code || 'request_failed' }); }
  }
  async function resumeHistory(observation, ticket) {
    if (!api.assetHistoryJobs || historyContext?.following) return;
    const follow = (job, existing = null) => {
      const context = existing || { observationId: observation.id, identity: identity(observation), job, cancelled: false, abort: new AbortController() }; context.job = job; historyContext = context;
      void followHistory(context, job).catch(error => { if (currentHistory(context)) { state.errors.historyJobs = error.message; notify(); } safeLog('asset_history_resume_failed', { status: error.code || 'request_failed' }); });
    };
    try {
      const result = await api.assetHistoryJobs(observation.id, { signal: readAbort?.signal });
      if (ticket !== generation || state.observation?.id !== observation.id || historyContext?.following) return;
      const existing = historyContext;
      let job = existing?.key ? result.items?.find(item => item.request_key === existing.key) : result.items?.find(item => ACTIVE.has(jobStatus(item))) || observation.history_job || result.items?.[0];
      if (existing && !job) return;
      if (existing?.stopRequested && job?.id && ACTIVE.has(jobStatus(job))) { job = await api.cancelAssetHistory(observation.id, job.id); if (ticket !== generation || !currentHistory(existing)) return; }
      state.historyJob = job || null;
      if (job?.id && (ACTIVE.has(jobStatus(job)) || existing)) {
        follow(job, existing);
      } else if (existing) { historyContext = null; }
    } catch (error) { if (ticket === generation) { state.errors.historyJobs = error.message; safeLog('asset_history_index_failed', { status: error.code || 'request_failed' }); if (!historyContext && observation.history_job?.id && ACTIVE.has(jobStatus(observation.history_job))) { state.historyJob = observation.history_job; follow(observation.history_job); } } }
  }
  async function load(route = {}) {
    checkAccount();
    const sameAsset = Boolean(state.observation && selectAssetObservation([state.observation], route));
    cancel({ stopHistory: !sameAsset }); const ticket = generation; readAbort = new AbortController(); const options = { signal: readAbort.signal };
    if (!sameAsset) Object.assign(state, { observation: null, rows: {}, historyJob: null });
    state.errors = {}; state.loading = true; notify();
    const requests = [['observations', 'assetObservations'], ['watchlists', 'watchlists'], ['notes', 'assetNotes'], ['alerts', 'assetAlerts'], ['notifications', 'assetNotifications']];
    const preferenceReadVersion = preferenceVersion;
    if (!preferencesLoaded && api.assetChartPreferences) requests.push(['preferences', 'assetChartPreferences']);
    await Promise.all(requests.map(async ([name, method]) => {
      try { const data = await api[method](options); if (ticket === generation) { if (name === 'preferences') { if (preferenceReadVersion === preferenceVersion && validPanels(data.panels)) { state.preferences = { panels: [...data.panels] }; persistedPreferences = state.preferences; preferencesLoaded = true; } } else state[name] = Array.isArray(data.items) ? data.items : []; } }
      catch (error) { if (ticket === generation && (name !== 'preferences' || preferenceReadVersion === preferenceVersion)) { if (name !== 'preferences') state[name] = []; state.errors[name] = error.message; safeLog('asset_workspace_read_failed', { status: name }); } }
    }));
    if (ticket !== generation) return;
    const chosen = selectAssetObservation(state.observations, route);
    if (chosen) {
      if (historyContext && historyContext.observationId !== chosen.id) { const previous = historyContext; previous.cancelled = true; previous.abort.abort(); historyContext = null; void cancelCaptured(previous); }
      const observation = cloneObservation(chosen); const nextRows = {};
      await Promise.all(Object.entries(observation.blocks).filter(([name]) => !['news', 'announcements'].includes(name)).map(async ([name, block]) => {
        if (name === 'history' && historyContext && sameAsset) return;
        const dataset = block.dataset; if (!dataset?.dataset_id || !observation.session_id) return;
        try { nextRows[name] = await readAssetDatasetRows(api, observation.session_id, dataset, { signal: options.signal, isCurrent: () => ticket === generation }); }
        catch (error) { if (ticket !== generation) return; nextRows[name] = error.partialRows || []; block.status = nextRows[name].length ? 'partial' : 'error'; block.failure_code = 'snapshot_read_failed'; state.errors[name] = error.message; safeLog('asset_dataset_rows_failed', { status: name }); }
      }));
      if (ticket !== generation) return;
      if (sameAsset && historyContext) { observation.blocks.history = state.observation.blocks.history; nextRows.history = state.rows.history || []; }
      state.observation = observation; state.rows = nextRows;
      await resumeHistory(observation, ticket);
    }
    if (ticket === generation) { state.loading = false; notify(); }
  }
  function loadBlock(block, { refresh = false } = {}) {
    checkAccount();
    const observation = state.observation;
    if (!observation?.id || !api.loadAssetBlock || !Object.values(VIEW_BLOCKS).flat().includes(block)) return Promise.resolve();
    const key = `${observation.id}:${block}`;
    if (blockReads.has(key)) return blockReads.get(key).promise;
    const context = { ticket: generation, observationId: observation.id, identity: identity(observation), abort: new AbortController() };
    const current = () => account === currentAccount() && context.ticket === generation && !context.abort.signal.aborted && state.observation?.id === context.observationId && identity(state.observation) === context.identity;
    const install = async result => {
      if (!current()) return;
      if (result?.id !== observation.id || identity(result) !== context.identity || result.session_id !== observation.session_id) throw new Error('区块响应资产身份异常');
      const next = result.blocks?.[block]; if (!next) throw new Error('区块响应缺失');
      let rows = state.rows[block];
      if (next.dataset?.dataset_id && (next.dataset.dataset_id !== state.observation.blocks?.[block]?.dataset?.dataset_id || !Array.isArray(rows) || rows.length !== next.dataset.row_count)) rows = await readAssetDatasetRows(api, observation.session_id, next.dataset, { signal: context.abort.signal, isCurrent: current });
      if (!current()) return;
      const blocks = { ...state.observation.blocks, [block]: { ...next } };
      state.observation = { ...state.observation, blocks, updated_at: result.updated_at, dataset_ids: Object.values(blocks).map(value => value?.dataset?.dataset_id).filter(Boolean) };
      if (rows) state.rows = { ...state.rows, [block]: rows };
      state.observations = state.observations.map(item => item.id === observation.id ? state.observation : item);
      if (['error', 'unavailable'].includes(next.status)) state.errors[block] = next.failure_code || '区块读取失败，可重试'; else delete state.errors[block];
      notify();
    };
    state.loadingBlocks = { ...state.loadingBlocks, [block]: true }; notify();
    const run = async () => {
      try {
        let result = await api.loadAssetBlock(observation.id, block, { refresh }, globalThis.crypto.randomUUID(), { signal: context.abort.signal });
        while (current()) {
          await install(result); if (!current() || result.blocks?.[block]?.status !== 'loading') return;
          await new Promise(resolve => setTimeout(resolve, pollIntervalMs)); if (!current()) return;
          result = await api.assetObservation(observation.id, { signal: context.abort.signal });
        }
      } catch (error) { if (current()) { state.errors[block] = error.message; const prior = state.observation.blocks?.[block]; if (prior?.status === 'loading') state.observation = { ...state.observation, blocks: { ...state.observation.blocks, [block]: { ...prior, status: 'error', failure_code: 'snapshot_read_failed' } } }; safeLog('asset_block_load_failed', { status: error.code || 'request_failed' }); notify(); } }
      finally { if (blockReads.get(key) === context) { blockReads.delete(key); if (current()) { delete state.loadingBlocks[block]; notify(); } } }
    };
    blockReads.set(key, context); context.promise = run(); return context.promise;
  }
  async function activateView(route = {}, { refresh = false } = {}) {
    checkAccount();
    const sameAsset = Boolean(state.observation && selectAssetObservation([state.observation], route));
    if (!sameAsset) {
      const expected = generation + 1;
      await load(route);
      if (generation !== expected) return;
    }
    const ticket = generation;
    let needsInitialHistory = false;
    if (!state.observation && route.asset && (route.assetType || 'stock') === 'stock' && api.createAssetObservation) {
      state.loading = true; notify();
      try {
        const creationIdentity = `${route.assetType || 'stock'}:${route.asset.toUpperCase()}`;
        if (!creationKeys.has(creationIdentity)) { creationKeys.set(creationIdentity, globalThis.crypto.randomUUID()); if (creationKeys.size > 64) creationKeys.delete(creationKeys.keys().next().value); }
        const created = await api.createAssetObservation({ asset: route.asset, asset_type: 'stock', source: 'tinysoft', sections: ['overview'], frequency: 'daily', adjustment: 'qfq' }, creationKeys.get(creationIdentity));
        if (ticket !== generation) return;
        if (!selectAssetObservation([created], route)) throw new Error('新增观察资产身份异常');
        state.observation = cloneObservation(created); state.rows = {}; state.observations = [state.observation, ...state.observations];
        await loadBlock('overview');
        if (ticket !== generation) return;
        needsInitialHistory = true;
      } catch (error) { if (ticket === generation) { state.errors.observation = error.message; safeLog('asset_observation_create_failed', { status: error.code || 'request_failed' }); } }
      finally { if (ticket === generation) { state.loading = false; notify(); } }
    }
    if (ticket !== generation || !state.observation) return;
    const blocks = [...new Set([...(sameAsset ? [] : ['overview', 'valuation']), ...(VIEW_BLOCKS[route.assetView] || VIEW_BLOCKS.overview)])];
    await Promise.all(blocks.map(block => loadBlock(block, { refresh })));
    if (needsInitialHistory && ticket === generation) void startHistory('recent', 'qfq').catch(() => { safeLog('asset_initial_history_failed', { status: 'history_failed' }); });
  }
  function savePreferences(panels) {
    if (!validPanels(panels)) { state.errors.preferences = '副图选择无效'; notify(); return Promise.resolve(); }
    const version = ++preferenceVersion; const owner = account; state.preferences = { panels: [...panels] }; notify();
    preferenceQueue = preferenceQueue.then(async () => {
      if (owner !== account || owner !== currentAccount()) return;
      try { const data = await api.saveAssetChartPreferences({ panels }); if (owner !== account || owner !== currentAccount()) return; persistedPreferences = { panels: validPanels(data?.panels) ? [...data.panels] : [...panels] }; if (version === preferenceVersion) { state.preferences = persistedPreferences; preferencesLoaded = true; delete state.errors.preferences; notify(); } }
      catch (error) { if (owner === account && owner === currentAccount() && version === preferenceVersion) { state.preferences = persistedPreferences; state.errors.preferences = error.message; notify(); } safeLog('asset_chart_preferences_failed', { status: error.code || 'request_failed' }); }
    }); return preferenceQueue;
  }
  return { state, load, activateView, loadBlock, cancel, startHistory, stopHistory, savePreferences };
}
