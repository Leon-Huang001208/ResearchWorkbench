import { safeLog } from './core.mjs';
import { createMarketController, renderMarketPage } from './market.mjs';
import { GLOBAL_MARKETS, payload, timelineRange } from './market-dashboard-model.mjs';
import { dashboardPage, dashboardTabs, workbenchPage } from './market-dashboard-view.mjs';

export function createMarketWorkspace(options = {}) {
  const legacy = createMarketController(options), dashboard = createMarketDashboard(options);
  let view = 'dashboard';
  return { legacy, dashboard, get state() { return view === 'dashboard' || view === 'workbench' ? dashboard.state : legacy.state; },
    cancel() { legacy.cancel(); dashboard.cancel(); },
    async activate(route = {}) { view = route.marketView || 'dashboard'; if (view === 'dashboard') await dashboard.activate(); else if (view !== 'workbench') await legacy.activate(route); },
    handleInput(event) { return view === 'dashboard' ? false : legacy.handleInput(event); },
    handleChange(event) { return view === 'dashboard' ? dashboard.handleChange(event) : legacy.handleChange(event); },
    handleSubmit(event) { return view === 'dashboard' ? dashboard.handleSubmit(event) : legacy.handleSubmit(event); },
    handleClick(event) { return view === 'dashboard' ? dashboard.handleClick(event) : legacy.handleClick(event); },
  };
}
export function renderMarketWorkspace(controller, route = {}) {
  if ((route.marketView || 'dashboard') === 'dashboard') return dashboardPage(controller.dashboard.state);
  if (route.marketView === 'workbench') return workbenchPage();
  // Keep the complete existing analysis/quotes/funds implementation and actions.
  return renderMarketPage(controller.legacy.state, route).replace(/<nav class="market-tabs"[^>]*>.*?<\/nav>/s, dashboardTabs(route.marketView));
}

export function createMarketDashboard({ api, onChange = () => {}, getIdentity = () => String(globalThis.__RWB_USER_ID__ || 'single-user'), now = () => new Date(), documentRef = globalThis.document, makeKey = () => globalThis.crypto.randomUUID(), setTimer = globalThis.setTimeout.bind(globalThis), clearTimer = globalThis.clearTimeout.bind(globalThis) } = {}) {
  if (!api?.request) throw new TypeError('market dashboard API request is required');
  const initial = () => ({ snapshot: null, profiles: [], scores: {}, scoreCoverage: { complete: false, rows: 0 }, selected: Object.fromEntries(GLOBAL_MARKETS.map(market => [market.id, market.indices[0][0]])), modes: {}, events: [], sources: [], nextCursor: '', range: 'month', custom: {}, market: '', category: '', loading: false, refreshing: false, error: '', errors: {}, detail: '', drawer: null, replay: '', today: now().toISOString().slice(0, 10) });
  const state = initial();
  let generation = 0, eventGeneration = 0, detailGeneration = 0, refreshIntentKey = '', owner = getIdentity(), active = false, abort = new AbortController(), reader = '', poll;
  const emit = () => { if (active && owner === getIdentity()) { const focused = documentRef?.activeElement, dialogFocused = focused?.closest?.('.md-drawer'); onChange(); if (dialogFocused) documentRef?.querySelector('.md-drawer [data-md-action="close"]')?.focus?.({ preventScroll: true }); } };
  const valid = ticket => active && ticket === generation && owner === getIdentity();
  async function releaseReader(id, intentKey) {
    const account = owner;
    try { const result = await api.request(`/market/refresh/${encodeURIComponent(id)}`, { method: 'DELETE' }); if (result.status === 'cancelled' && account === owner && refreshIntentKey === intentKey) refreshIntentKey = ''; }
    catch { safeLog('market_dashboard_reader_release_failed', { status: 'failed' }); }
  }
  function cancel() {
    documentRef?.removeEventListener?.('keydown', drawerKeyboard);
    active = false; generation++; eventGeneration++; detailGeneration++; abort.abort(); abort = new AbortController(); clearTimer(poll);
    if (reader) { const id = reader; reader = ''; void releaseReader(id, refreshIntentKey); }
    state.loading = false; state.refreshing = false; state.eventsLoading = false;
  }
  function drawerKeyboard(event) {
    if (!active || !state.drawer) return;
    const dialog = documentRef?.querySelector('.md-drawer');
    if (event.key === 'Escape') { event.preventDefault(); const id = state.drawer.id; detailGeneration++; state.drawer = null; emit(); [...(documentRef?.querySelectorAll('[data-md-action="event"]') || [])].find(node => node.dataset.id === id)?.focus?.({ preventScroll: true }); }
    if (event.key !== 'Tab' || !dialog) return;
    const nodes = [...dialog.querySelectorAll('a[href],button:not(:disabled),summary,[tabindex="0"]')].filter(node => node.getClientRects().length);
    const first = nodes[0], last = nodes.at(-1), focused = documentRef.activeElement;
    if (first && (!dialog.contains(focused) || event.shiftKey && focused === first || !event.shiftKey && focused === last)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
  }
  async function read(path, key, ticket, accept, isCurrent = () => true) {
    try { const data = await api.request(path, { signal: abort.signal }); if (valid(ticket) && isCurrent()) { accept(data); delete state.errors[key]; emit(); } return data; }
    catch (error) { if (valid(ticket) && isCurrent() && error.name !== 'AbortError') { state.errors[key] = error.message || '读取失败'; safeLog('market_dashboard_read_failed', { section: key, status: error.code || 'failed' }); emit(); } return null; }
  }
  async function loadScores(ticket) {
    state.scores = {}; state.scoreCoverage = { complete: false, rows: 0 };
    // The real store lists ASC by created_at,id. Exhaust pagination before
    // choosing the last encountered record for each index; never call a capped
    // prefix "latest" or infer absence from an incomplete history scan.
    const latest = new Map(), seen = new Set(); let cursor = '', complete = false;
    for (let page = 0; page < 20; page++) {
      const params = new URLSearchParams({ limit: '100' }); if (cursor) params.set('cursor', cursor);
      const runs = await read(`/market-scores/runs?${params}`, 'scores', ticket, () => {});
      if (!valid(ticket)) return;
      if (!runs || !Array.isArray(runs.items)) break;
      state.scoreCoverage.rows += runs.items.length;
      for (const record of runs.items) { const index = payload(record).request?.index_id; if (GLOBAL_MARKETS.some(m => m.indices.some(([id]) => id === index))) latest.set(index, record); }
      if (!runs.next_cursor) { complete = true; break; }
      cursor = String(runs.next_cursor); if (seen.has(cursor)) break; seen.add(cursor);
    }
    if (!valid(ticket)) return;
    state.scoreCoverage.complete = complete; state.scoreCoverage.indices = [...latest.keys()];
    if (!complete) { state.errors.scores = '评分历史覆盖未完整，无法确认最新运行或是否缺失；当前评分保留空缺。'; emit(); return; }
    await Promise.all([...latest].map(([index, record]) => read(`/market-scores/runs/${encodeURIComponent(record.id)}`, `score:${index}`, ticket, data => { state.scores[index] = data; })));
  }
  async function loadEvents(more = false) {
    if (!active || owner !== getIdentity()) return;
    const range = timelineRange(state.range, now(), state.custom);
    const params = new URLSearchParams({ ...range, limit: '200' });
    if (state.market) params.set('market', state.market);
    if (state.category) params.set('category', state.category);
    const query = params.toString();
    if (more && (state.eventsLoading || !state.nextCursor || state.eventQuery !== query)) return;
    const ticket = generation, eventTicket = ++eventGeneration;
    if (more && state.nextCursor) params.set('cursor', state.nextCursor);
    if (!more) { state.nextCursor = ''; state.events = []; state.window = range; state.eventQuery = query; }
    state.eventsLoading = true; emit();
    await read(`/events/timeline?${params}`, 'events', ticket, data => {
      if (eventTicket !== eventGeneration) return;
      const rows = Array.isArray(data.items) ? data.items : [];
      state.events = more ? [...new Map([...state.events, ...rows].map(row => [row.id, row])).values()] : rows;
      if (Array.isArray(data.sources)) state.sources = data.sources;
      state.nextCursor = data.next_cursor || ''; state.window = range;
    }, () => eventTicket === eventGeneration);
    if (valid(ticket) && eventTicket === eventGeneration) { state.eventsLoading = false; emit(); }
  }
  async function activate() {
    cancel(); if (owner !== getIdentity()) { Object.assign(state, initial()); refreshIntentKey = ''; owner = getIdentity(); }
    active = true; documentRef?.addEventListener?.('keydown', drawerKeyboard); const ticket = generation; state.loading = true; state.error = ''; emit();
    await Promise.all([
      read('/market', 'quotes', ticket, data => { state.snapshot = data; }),
      read('/market-scores/profiles', 'profiles', ticket, data => { state.profiles = data.profiles || data.items || []; }),
      loadScores(ticket), loadEvents(),
    ]);
    if (valid(ticket)) { state.loading = false; emit(); safeLog('market_dashboard_loaded', { status: Object.keys(state.errors).length ? 'partial' : 'cached' }); }
  }
  async function refresh() {
    if (!active || owner !== getIdentity() || state.refreshing || state.replay) return;
    const ticket = generation; state.refreshing = true; state.error = ''; emit();
    let terminal = false;
    try {
      if (!refreshIntentKey) refreshIntentKey = makeKey();
      const intentKey = refreshIntentKey;
      let result = await api.request('/market/refresh', { method: 'POST', body: { sections: ['indices'], index_set: 'global-v1' }, key: intentKey, userAction: true, signal: abort.signal });
      const id = result.request_id;
      if (!id) throw new Error('刷新任务缺少编号');
      if (!valid(ticket)) { await releaseReader(id, intentKey); return; }
      reader = id;
      for (let attempt = 0; !['completed', 'failed', 'cancelled'].includes(result.status); attempt++) {
        if (attempt >= 160) throw new Error('刷新尚未完成，已停止等待；原缓存保留');
        await new Promise((resolve, reject) => { const signal = abort.signal; const cancelled = () => { clearTimer(poll); reject(new DOMException('已取消', 'AbortError')); }; signal.addEventListener('abort', cancelled, { once: true }); poll = setTimer(() => { signal.removeEventListener('abort', cancelled); resolve(); }, 750); });
        if (!valid(ticket)) return;
        result = await api.request(`/market/refresh/${encodeURIComponent(id)}`, { signal: abort.signal });
      }
      terminal = true;
      if (!valid(ticket)) return;
      refreshIntentKey = '';
      if (result.status !== 'completed') state.error = '本次刷新未完整完成，请核对来源与缺口。';
      await read('/market', 'quotes', ticket, data => { state.snapshot = data; });
      safeLog('market_dashboard_refresh_finished', { status: result.status });
    } catch (error) { if (valid(ticket) && error.name !== 'AbortError') { state.error = error.message || '刷新失败，保留原快照'; safeLog('market_dashboard_refresh_failed', { status: error.code || 'failed' }); } }
    finally { if (valid(ticket)) { if (!terminal && reader) { const id = reader; void releaseReader(id, refreshIntentKey); } reader = ''; state.refreshing = false; emit(); } }
  }
  async function handleChange(event) {
    if (!active || owner !== getIdentity()) return false;
    const target = event.target, data = target?.dataset || {};
    if (data.mdIndex) { if (GLOBAL_MARKETS.find(m => m.id === data.mdIndex)?.indices.some(([id]) => id === target.value)) state.selected[data.mdIndex] = target.value; }
    else if (data.mdFilter) { if (!['range', 'market', 'category'].includes(data.mdFilter)) return false; state[data.mdFilter] = target.value; await loadEvents(); }
    else return false;
    emit(); return true;
  }
  async function handleSubmit(event) {
    if (!active || owner !== getIdentity()) return false;
    const form = event.target;
    if (!form?.hasAttribute?.('data-md-dates') && !form?.hasAttribute?.('data-md-replay')) return false;
    event.preventDefault(); const values = new FormData(form);
    if (form.hasAttribute('data-md-replay')) { const date = String(values.get('date') || ''); if (/^\d{4}-\d{2}-\d{2}$/.test(date) && date <= state.today) state.replay = date; else state.error = '请选择有效的过去日期，未来行情不能回放'; }
    else { const start = String(values.get('start') || ''), end = String(values.get('end') || ''); if (!start || !end || start > end) state.error = '结束日期不得早于开始日期'; else { state.custom = { start, end }; state.range = 'custom'; await loadEvents(); } }
    emit(); return true;
  }
  async function handleClick(event) {
    if (!active || owner !== getIdentity()) return false;
    const target = event.target?.closest?.('[data-md-action]'); if (!target) return false;
    const data = target.dataset; event.preventDefault();
    if (data.mdAction === 'refresh') await refresh();
    else if (data.mdAction === 'mode' && ['research', 'formal'].includes(data.mode)) state.modes[data.market] = data.mode;
    else if (data.mdAction === 'detail') state.detail = data.index;
    else if (data.mdAction === 'back') state.detail = '';
    else if (data.mdAction === 'exit-replay') state.replay = '';
    else if (data.mdAction === 'event') { const selected = state.events.find(row => row.id === data.id); if (selected) { const detailTicket = ++detailGeneration; state.drawer = selected; emit(); documentRef?.querySelector('.md-drawer [data-md-action="close"]')?.focus?.({ preventScroll: true }); const ticket = generation; await read(`/events/${encodeURIComponent(data.id)}`, 'event-detail', ticket, result => { state.drawer = result; }, () => detailTicket === detailGeneration && state.drawer?.id === data.id); } }
    else if (data.mdAction === 'close') { const id = state.drawer?.id; detailGeneration++; state.drawer = null; emit(); [...(documentRef?.querySelectorAll('[data-md-action="event"]') || [])].find(node => node.dataset.id === id)?.focus?.({ preventScroll: true }); return true; }
    else if (data.mdAction === 'more') await loadEvents(true);
    else return false;
    emit(); return true;
  }
  return { state, activate, cancel, refresh, handleChange, handleSubmit, handleClick };
}
