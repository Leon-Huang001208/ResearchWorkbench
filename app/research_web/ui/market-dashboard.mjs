import { safeLog } from './core.mjs';
import { createMarketController, renderMarketPage } from './market.mjs';
import { GLOBAL_MARKETS, calendarToday, offsetDay, offsetMonth, payload, timelineRange, validDate, validTimelineRange } from './market-dashboard-model.mjs';
import { dashboardPage, dashboardTabs, workbenchPage } from './market-dashboard-view.mjs';
import { createMarketDailyBootstrap } from './market-daily-bootstrap.mjs';

export function createMarketWorkspace(options = {}) {
  const legacy = createMarketController(options), dashboard = createMarketDashboard(options);
  const bootstrap = createMarketDailyBootstrap(options);
  let view = 'dashboard';
  return { legacy, dashboard, bootstrap, get state() { return view === 'dashboard' || view === 'workbench' ? dashboard.state : legacy.state; },
    paint(page, render) {
      if (page !== 'market') return render();
      dashboard.capturePresentation();
      try { render(); } finally { dashboard.restorePresentation(); }
    },
    cancel() { legacy.cancel(); dashboard.cancel(); bootstrap.dispose(); },
    async activate(route = {}) { view = route.marketView || 'dashboard'; if (view === 'dashboard') await dashboard.activate(); else if (view !== 'workbench') await legacy.activate(route); },
    handleInput(event) { return view === 'dashboard' ? dashboard.handleInput(event) : legacy.handleInput(event); },
    handleChange(event) { return view === 'dashboard' ? dashboard.handleChange(event) : legacy.handleChange(event); },
    handleSubmit(event) { return view === 'dashboard' ? dashboard.handleSubmit(event) : legacy.handleSubmit(event); },
    handleClick(event) {
      if (event.target?.closest?.('[data-market-daily-action]')) return view === 'workbench' ? bootstrap.handleClick(event) : false;
      return view === 'dashboard' ? dashboard.handleClick(event) : legacy.handleClick(event);
    },
  };
}
export function renderMarketWorkspace(controller, route = {}) {
  if ((route.marketView || 'dashboard') === 'dashboard') return dashboardPage(controller.dashboard.state);
  if (route.marketView === 'workbench') return workbenchPage(controller.bootstrap.render());
  // Keep the complete existing analysis/quotes/funds implementation and actions.
  return renderMarketPage(controller.legacy.state, route).replace(/<nav class="market-tabs"[^>]*>.*?<\/nav>/s, dashboardTabs(route.marketView));
}

export function createMarketDashboard({ api, onChange = () => {}, getIdentity = () => String(globalThis.__RWB_USER_ID__ || 'single-user'), now = () => new Date(), documentRef = globalThis.document, makeKey = () => globalThis.crypto.randomUUID(), setTimer = globalThis.setTimeout.bind(globalThis), clearTimer = globalThis.clearTimeout.bind(globalThis) } = {}) {
  if (!api?.request) throw new TypeError('market dashboard API request is required');
  const initial = () => {
    const today = calendarToday(now());
    return { snapshot: null, profiles: [], scores: {}, observations: {}, scoreCoverage: { complete: false, rows: 0 },
      selected: Object.fromEntries(GLOBAL_MARKETS.map(market => [market.id, market.indices[0][0]])), modes: {},
      events: [], dayEvents: [], sources: [], coverage: null, nextCursor: '', dayCursor: '',
      range: 'month', custom: {}, customDraft: {}, dateDraft: null, market: '', category: '', selectedDate: today, anchor: today,
      loading: false, refreshing: false, error: '', dateError: '', errors: {}, detail: '', drawer: null, drawerFocus: '',
      replay: '', replayCalendar: [], today };
  };
  const state = initial();
  let generation = 0, eventGeneration = 0, dayGeneration = 0, detailGeneration = 0, refreshIntentKey = '', owner = getIdentity(), active = false, abort = new AbortController(), reader = '', poll;
  let scrollLeft = 0, centerRequested = true, focusRequested = '', presentation = null;
  const scrollRegion = () => documentRef?.querySelector?.('.md-time-scroll');
  function rememberScroll() {
    const region = scrollRegion();
    if (region) scrollLeft = region.scrollLeft;
  }
  function focusControl(key) {
    if (!key) return false;
    const node = [...(documentRef?.querySelectorAll?.('[data-md-focus]') || [])].find(item => item.dataset.mdFocus === key);
    node?.focus?.({ preventScroll: true });
    return Boolean(node);
  }
  function capturePresentation() {
    if (!active || owner !== getIdentity()) return;
    const focused = documentRef?.activeElement;
    rememberScroll();
    presentation = {
      dialogFocused: Boolean(focused?.closest?.('.md-drawer')),
      coverageWasOpen: documentRef?.querySelector?.('[data-md-retain]')?.open,
      wasScrolling: Boolean(focused && focused === scrollRegion()),
      previousFocus: focused?.dataset?.mdFocus,
      openDrawerDetails: [...(documentRef?.querySelectorAll?.('.md-drawer details[data-md-details]') || [])].filter(item => item.open).map(item => item.dataset.mdDetails),
    };
  }
  function restorePresentation() {
    const saved = presentation;
    presentation = null;
    if (!saved || !active || owner !== getIdentity()) return;
    const { dialogFocused, coverageWasOpen, wasScrolling, previousFocus, openDrawerDetails } = saved;
    const coverage = documentRef?.querySelector?.('[data-md-retain]');
    if (coverage && coverageWasOpen) coverage.open = true;
    for (const details of documentRef?.querySelectorAll?.('.md-drawer details[data-md-details]') || []) {
      if (openDrawerDetails.includes(details.dataset.mdDetails)) details.open = true;
    }
    const region = scrollRegion();
    if (region) {
      const tick = centerRequested && [...region.querySelectorAll('[data-md-action="day"]')].find(node => node.dataset.date === state.selectedDate);
      if (tick) {
        region.scrollLeft = tick.offsetLeft + tick.offsetWidth / 2 - region.clientWidth / 2;
        scrollLeft = region.scrollLeft;
        centerRequested = false;
      } else region.scrollLeft = scrollLeft;
      if (wasScrolling && !focusRequested) region.focus({ preventScroll: true });
    }
    if (!focusControl(focusRequested || previousFocus) && dialogFocused && state.drawer) focusControl('drawer:close');
    focusRequested = '';
  }
  function emit() {
    if (!active || owner !== getIdentity()) return;
    capturePresentation();
    onChange();
    restorePresentation();
  }
  const valid = ticket => active && ticket === generation && owner === getIdentity();
  async function releaseReader(id, intentKey) {
    const account = owner;
    if (account !== getIdentity()) return;
    try { const result = await api.request(`/market/refresh/${encodeURIComponent(id)}`, { method: 'DELETE' }); if (result.status === 'cancelled' && account === owner && refreshIntentKey === intentKey) refreshIntentKey = ''; }
    catch { safeLog('market_dashboard_reader_release_failed', { status: 'failed' }); }
  }
  function cancel() {
    rememberScroll();
    presentation = null;
    documentRef?.removeEventListener?.('keydown', dashboardKeyboard);
    documentRef?.removeEventListener?.('pointerover', chartPreview);
    documentRef?.removeEventListener?.('focusin', chartPreview);
    active = false; generation++; eventGeneration++; dayGeneration++; detailGeneration++; abort.abort(); abort = new AbortController(); clearTimer(poll);
    if (reader) { const id = reader; reader = ''; void releaseReader(id, refreshIntentKey); }
    state.loading = false; state.refreshing = false; state.eventsLoading = false; state.dayLoading = false;
  }
  function dashboardKeyboard(event) {
    if (!active || owner !== getIdentity()) return;
    if (!state.drawer) {
      const point = event.target?.closest?.('[data-md-action="chart-point"]');
      if (point && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const points = [...point.closest('.md-chart-points').querySelectorAll('[data-md-action="chart-point"]')];
        const index = event.key === 'Home' ? 0 : event.key === 'End' ? points.length - 1 : points.indexOf(point) + (event.key === 'ArrowLeft' ? -1 : 1);
        points[Math.max(0, Math.min(points.length - 1, index))]?.focus({ preventScroll: true });
        return;
      }
      const date = event.target?.closest?.('[data-md-action="day"]')?.dataset?.date;
      if (!date || !['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      event.preventDefault();
      const next = event.key === 'Home' ? state.window?.start : event.key === 'End' ? state.window?.end : offsetDay(date, event.key === 'ArrowLeft' ? -1 : 1);
      if (validDate(next)) void selectDate(next, { focusDay: true });
      return;
    }
    const dialog = documentRef?.querySelector('.md-drawer');
    if (event.key === 'Escape') { event.preventDefault(); closeDrawer(); }
    if (event.key !== 'Tab' || !dialog) return;
    const nodes = [...dialog.querySelectorAll('a[href],button:not(:disabled),summary,[tabindex="0"]')].filter(node => node.getClientRects().length);
    const first = nodes[0], last = nodes.at(-1), focused = documentRef.activeElement;
    if (first && (!dialog.contains(focused) || event.shiftKey && focused === first || !event.shiftKey && focused === last)) { event.preventDefault(); (event.shiftKey ? last : first).focus(); }
  }
  function closeDrawer() {
    detailGeneration++;
    state.drawer = null;
    focusRequested = state.drawerFocus;
    state.drawerFocus = '';
    emit();
  }
  function chartPreview(event) {
    if (!active || owner !== getIdentity()) return;
    const point = event.target?.closest?.('[data-md-action="chart-point"]');
    if (!point?.dataset?.pointLabel) return;
    const chart = point.closest('.md-spark');
    const output = chart?.querySelector('[data-md-chart-value]');
    if (output) output.textContent = point.dataset.pointLabel;
    for (const item of chart?.querySelectorAll('[data-md-action="chart-point"]') || []) {
      item.setAttribute('aria-pressed', String(item === point));
      item.tabIndex = item === point ? 0 : -1;
    }
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
    const range = timelineRange(state.range, state.anchor, state.custom);
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
  async function loadDay(more = false) {
    if (!active || owner !== getIdentity() || (more && (state.dayLoading || !state.dayCursor))) return;
    const ticket = generation, dayTicket = ++dayGeneration, date = state.selectedDate;
    const params = new URLSearchParams({ start: date, end: date, limit: '200' });
    if (more) params.set('cursor', state.dayCursor);
    else { state.dayEvents = []; state.dayCursor = ''; state.dayStatus = 'loading'; delete state.errors.day; }
    state.dayLoading = true;
    emit();
    const data = await read(`/events/timeline?${params}`, 'day', ticket, response => {
      const items = Array.isArray(response.items) ? response.items : [];
      state.dayEvents = more ? [...new Map([...state.dayEvents, ...items].map(row => [row.id, row])).values()] : items;
      state.dayCursor = response.next_cursor || '';
      if (Array.isArray(response.sources)) state.sources = response.sources;
      state.dayStatus = 'ready';
    }, () => dayTicket === dayGeneration && date === state.selectedDate);
    if (valid(ticket) && dayTicket === dayGeneration) {
      state.dayLoading = false;
      if (!data && !more) state.dayStatus = 'failed';
      emit();
    }
  }
  async function selectDate(date, { recenterWindow = false, focusDay = false } = {}) {
    if (!validDate(date)) { state.dateError = '请输入有效日期（1990-01-01 至 2199-12-31）'; emit(); return; }
    const range = state.window || timelineRange(state.range, state.anchor, state.custom);
    const resetWindow = recenterWindow || date < range.start || date > range.end;
    state.selectedDate = date; state.dateDraft = null; state.dateError = '';
    if (resetWindow) { if (state.range === 'custom') state.range = 'month'; state.anchor = date; state.customDraft = {}; }
    centerRequested = true;
    if (focusDay) focusRequested = `day:${date}`;
    await Promise.all([resetWindow ? loadEvents() : undefined, loadDay()]);
  }
  async function activate() {
    cancel();
    if (owner !== getIdentity()) {
      for (const key of Object.keys(state)) delete state[key];
      Object.assign(state, initial()); refreshIntentKey = ''; owner = getIdentity(); scrollLeft = 0; centerRequested = true; focusRequested = '';
    }
    state.today = calendarToday(now());
    active = true; documentRef?.addEventListener?.('keydown', dashboardKeyboard);
    documentRef?.addEventListener?.('pointerover', chartPreview);
    documentRef?.addEventListener?.('focusin', chartPreview);
    const ticket = generation; state.loading = true; state.error = ''; emit();
    await Promise.all([
      read('/market', 'quotes', ticket, data => { state.snapshot = data; }),
      read('/market-scores/profiles', 'profiles', ticket, data => { state.profiles = data.profiles || data.items || []; }),
      read('/market-scores/initial-evidence', 'initialEvidence', ticket, data => { state.observations = Object.fromEntries((Array.isArray(data.items) ? data.items : []).filter(item => GLOBAL_MARKETS.some(market => market.indices.some(([id]) => id === item?.index_id))).map(item => [item.index_id, item])); }),
      read('/events/coverage', 'coverage', ticket, data => { state.coverage = data; }),
      loadScores(ticket), loadEvents(), loadDay(),
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
  function handleInput(event) {
    if (!active || owner !== getIdentity()) return false;
    const field = event.target?.dataset?.mdDateDraft;
    if (field === 'date') state.dateDraft = event.target.value;
    else if (field === 'start' || field === 'end') state.customDraft[field] = event.target.value;
    else return false;
    return true;
  }
  async function handleChange(event) {
    if (!active || owner !== getIdentity()) return false;
    const target = event.target, data = target?.dataset || {};
    if (data.mdIndex) { if (GLOBAL_MARKETS.find(m => m.id === data.mdIndex)?.indices.some(([id]) => id === target.value)) state.selected[data.mdIndex] = target.value; }
    else if (data.mdFilter) {
      if (!['range', 'market', 'category'].includes(data.mdFilter)) return false;
      state[data.mdFilter] = target.value;
      if (data.mdFilter === 'range' && target.value !== 'custom') { state.anchor = state.selectedDate; centerRequested = true; }
      await loadEvents();
    }
    else return false;
    emit(); return true;
  }
  async function handleSubmit(event) {
    if (!active || owner !== getIdentity()) return false;
    const form = event.target;
    if (!form?.hasAttribute?.('data-md-dates') && !form?.hasAttribute?.('data-md-select-date')) return false;
    event.preventDefault(); const values = new FormData(form);
    if (form.hasAttribute('data-md-select-date')) await selectDate(String(values.get('date') || ''));
    else {
      const range = { start: String(values.get('start') || ''), end: String(values.get('end') || '') };
      if (!validTimelineRange(range)) { state.dateError = '请选择有效起止日期，结束不早于开始，且最多 731 天'; emit(); return true; }
      state.custom = range; state.customDraft = {}; state.range = 'custom'; state.dateError = '';
      const target = state.selectedDate < range.start || state.selectedDate > range.end ? range.start : state.selectedDate;
      const changed = target !== state.selectedDate;
      state.selectedDate = target; state.dateDraft = null; centerRequested = true;
      await Promise.all([loadEvents(), changed ? loadDay() : undefined]);
    }
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
    else if (data.mdAction === 'day') { await selectDate(data.date, { focusDay: true }); return true; }
    else if (data.mdAction === 'today') { state.today = calendarToday(now()); state.range = 'month'; await selectDate(state.today, { recenterWindow: true }); return true; }
    else if (data.mdAction === 'previous-month' || data.mdAction === 'next-month') { await selectDate(offsetMonth(state.selectedDate, data.mdAction === 'previous-month' ? -1 : 1), { recenterWindow: true }); return true; }
    else if (data.mdAction === 'view-day') {
      if (validDate(state.selectedDate) && state.selectedDate <= state.today) { state.replay = state.selectedDate; state.replayCalendar = [...state.dayEvents]; state.dateError = ''; }
      else state.dateError = '未来日期只查看已公布日程，不能回放行情';
    }
    else if (data.mdAction === 'exit-replay') { state.replay = ''; state.replayCalendar = []; }
    else if (data.mdAction === 'jump-date') { const input = documentRef?.querySelector?.('[data-md-date-draft="date"]'); input?.scrollIntoView?.({ block: 'center', inline: 'nearest' }); input?.focus?.({ preventScroll: true }); return true; }
    else if (data.mdAction === 'chart-point') { chartPreview(event); return true; }
    else if (data.mdAction === 'more-day') await loadDay(true);
    else if (data.mdAction === 'event') { const selected = [...state.events, ...state.dayEvents].find(row => row.id === data.id); if (selected) { const detailTicket = ++detailGeneration; state.drawer = selected; state.drawerFocus = data.mdFocus || `event:${selected.id}`; emit(); documentRef?.querySelector('.md-drawer [data-md-action="close"]')?.focus?.({ preventScroll: true }); const ticket = generation; await read(`/events/${encodeURIComponent(data.id)}`, 'event-detail', ticket, result => { state.drawer = result; }, () => detailTicket === detailGeneration && state.drawer?.id === data.id); } }
    else if (data.mdAction === 'close') { if (state.drawer) closeDrawer(); return true; }
    else if (data.mdAction === 'more') await loadEvents(true);
    else return false;
    emit(); return true;
  }
  return { state, activate, cancel, refresh, capturePresentation, restorePresentation, handleInput, handleChange, handleSubmit, handleClick };
}
