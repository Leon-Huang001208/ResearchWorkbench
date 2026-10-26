import { escapeHTML as e, safeURL } from './markdown.mjs';
import { safeLog } from './core.mjs';
import { icon } from './icons.mjs';
import { intelTime, renderIntelligenceNavigation } from './intel.mjs';

const list = value => Array.isArray(value) ? value : [];
const text = value => typeof value === 'string' || typeof value === 'number' ? String(value) : '';
export const discoveryHorizons = [['short', '短期', '近期变化'], ['medium', '中期', '逻辑验证'], ['long', '长期', '结构变化']];
const detailTabs = [['evidence', '证据现场'], ['counter', '反方与边界'], ['conditions', '跟踪条件'], ['history', '判断履历']];
const accepted = value => value?.execution_started === true || value?.accepted === true;
const uncertain = value => /unknown|starting|creating/.test(value?.state || '');
const trackID = value => value?.id || value?.track_id || value?.automation_id;
const trackVersion = value => value?.version ?? value?.definition_version;
const enabled = value => value?.enabled === true || value?.status === 'enabled';
const trackLabel = value => value?.client_state_unknown ? '操作结果尚未确认' : !value ? '尚未开启' : enabled(value) ? '已开启' : value.enable_error ? '未开启 · 请处理启用失败' : value.status === 'paused' ? '已暂停' : '已保存 · 未开启';
const latestRun = value => list(value?.runs)[0] || value?.latest_run;
const scheduleTime = value => value?.time || (value?.schedule ? `${String(value.schedule.hour).padStart(2, '0')}:${String(value.schedule.minute).padStart(2, '0')}` : '08:30');
const scheduleLabel = value => value?.schedule?.kind === 'weekly' ? `每周${['一', '二', '三', '四', '五', '六', '日'][value.schedule.weekday] || '待核实'}` : '每天';
const chip = value => `<span class="d-chip">${e(text(value))}</span>`;
const empty = value => `<p class="d-inline-note">${e(value)}</p>`;

export function filterDiscoveryThemes(themes, query = '') {
  const wanted = query.trim().toLocaleLowerCase();
  return list(themes).filter(item => !wanted || [item.name, item.title, item.category, item.description, item.publisher, ...list(item.materials).map(x => x.publisher)].map(text).join(' ').toLocaleLowerCase().includes(wanted));
}

export function discoveryItems(s) {
  const source = Array.isArray(s.feed?.news) && Array.isArray(s.feed?.events) ? (s.view === 'events' ? s.feed.events : s.feed.news) : list(s.feed?.themes);
  const f = s.filters || {};
  const watch = list(s.watchlists).find(x => x.id === f.watchlist);
  const assets = new Set(list(watch?.items).map(x => x.asset));
  return filterDiscoveryThemes(source, s.query).filter(x => {
    const published = x.published_at || list(x.materials)[0]?.published_at;
    const knownDate = typeof published === 'string' && /^\d{4}-\d{2}-\d{2}/.test(published) && Number.isFinite(Date.parse(published));
    const date = knownDate ? published.length === 10 ? published : new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date(published)) : '';
    return (!s.publisher || (x.publisher || list(x.materials)[0]?.publisher) === s.publisher)
      && (!f.category || x.category === f.category)
      && (!f.importance || String(x.priority ?? x.importance ?? '') === f.importance)
      && (!(f.from || f.to) || knownDate && (!f.from || date >= f.from) && (!f.to || date <= f.to))
      && (!f.watchlist || list(x.assets).some(asset => assets.has(typeof asset === 'string' ? asset : asset?.asset || asset?.code)));
  });
}
function selectedItem(s) {
  const items = discoveryItems(s); const item = items.find(x => x.id === s.selected) || items[0];
  return s.associatedFeeds?.[item?.id]?.themes?.[0] || item;
}

function handoffRecords(state) {
  const rows = new Map(list(state.handoffs).map(row => [row.handoff_id, row]));
  for (const draft of Object.values(state.researchDrafts)) {
    if (draft.prepared?.handoff_id) rows.set(draft.prepared.handoff_id, { ...draft.prepared, theme_id: draft.theme_id, question: draft.question, target_mode: draft.target_mode });
  }
  return [...rows.values()];
}

function displayedTrack(state, themeID) {
  const row = state.tracks.find(item => item.theme_id === themeID);
  const unresolved = Object.values(state.trackDrafts).some(draft => draft.theme_id === themeID && draft.unknown);
  return unresolved || row && state.tracksError ? { ...row, client_state_unknown: true } : row;
}

function prepareBody(draft) {
  return { request_id: draft.request_id, feed_id: draft.feed_id, horizon: draft.horizon, theme_id: draft.theme_id, material_ids: [...draft.material_ids], target_mode: draft.target_mode, question: draft.question, ...(draft.scenario_id ? {scenario_id:draft.scenario_id, scenario_inputs:draft.scenario_inputs || {subject:{kind:draft.subject_kind || 'topic',identity:draft.subject_identity || draft.question.slice(0,160)},question:draft.question,as_of:draft.as_of,material_ids:[...draft.material_ids]}} : {}) };
}

function originalPrepareRequest(value) {
  const keys = ['request_id', 'feed_id', 'horizon', 'theme_id', 'material_ids', 'target_mode', 'question'];
  if (value?.scenario_id) keys.push('scenario_id', 'scenario_inputs');
  if (!value || typeof value !== 'object' || Object.keys(value).length !== keys.length || keys.some(key => !(key in value))) return null;
  if (keys.filter(key => !['material_ids', 'scenario_inputs'].includes(key)).some(key => typeof value[key] !== 'string' || !value[key])) return null;
  if (!['short', 'medium', 'long'].includes(value.horizon) || !['fingpt', 'claw'].includes(value.target_mode) || value.question.length > 6000) return null;
  if (!Array.isArray(value.material_ids) || !value.material_ids.length || value.material_ids.length > 20 || value.material_ids.some(id => typeof id !== 'string' || !id)) return null;
  return prepareBody(value);
}

function restorePrepareBody(draft, record) {
  if (draft.prepare_body) return;
  const body = originalPrepareRequest(record.prepare_request);
  if (body) { draft.prepare_body = body; for (const key of Object.keys(body)) draft[key] = body[key]; }
}

export function createDiscoveryController({ api, onChange = () => {}, onNavigate = () => {}, makeID = () => globalThis.crypto.randomUUID(), logger = safeLog } = {}) {
  const state = { filters: {}, watchlists: [], scenarios: [], scenarioError: '', active: false, horizon: 'medium', feed: null, loading: false, error: '', query: '', view: 'news', publisher: '', associatedFeeds: {}, associationEvent: '', associationBusy: false, associationError: '', selected: '', chain: 0, tab: 'evidence', handoffs: [], historyError: '', tracks: [], tracksAvailable: null, tracksError: '', schedulerState: '', drawer: null, researchDrafts: {}, trackDrafts: {} };
  let generation = 0;
  let feedAbort;
  let tracksAbort;
  let tracksEpoch = 0;
  let historyAbort;
  let selectionAbort;
  let selectionEpoch = 0;
  const changed = () => { if (state.active) onChange(); };
  const theme = () => selectedItem(state);
  const selectedFeedID = () => state.associatedFeeds[state.selected]?.feed_id || state.feed?.feed_id;
  const draftKey = () => `${selectedFeedID() || ''}:${state.horizon}:${state.selected}`;
  const ownedTrack = id => state.tracks.find(item => item.theme_id === id);
  function cancelSelection() {
    selectionEpoch += 1; selectionAbort?.abort();
    const drawer = state.drawer;
    if (['research', 'tracking'].includes(drawer?.kind)) {
      const draft = (drawer.kind === 'tracking' ? state.trackDrafts : state.researchDrafts)[drawer.key];
      if (draft) draft.selection_loading = false;
    }
  }
  function deactivate() { state.active = false; generation += 1; feedAbort?.abort(); tracksAbort?.abort(); historyAbort?.abort(); cancelSelection(); state.loading = false; state.drawer = null; }
  async function loadHistory() {
    historyAbort?.abort(); historyAbort = new AbortController(); const ticket = generation;
    try {
      const result = await api.discoveryHandoffs({ signal: historyAbort.signal });
      if (ticket !== generation || !state.active) return;
      state.handoffs = list(result.items); state.historyError = '';
    } catch (error) {
      if (ticket !== generation || error.name === 'AbortError') return;
      state.historyError = error.message || '研究交接履历暂未读取成功。'; logger('discovery_history_read_failed', { code: error.code || 'request_failed' });
    } finally { if (ticket === generation) changed(); }
  }
  async function loadTracks() {
    tracksAbort?.abort(); tracksAbort = new AbortController();
    const ticket = generation; const epoch = ++tracksEpoch;
    try {
      const result = await api.discoveryTracks({ signal: tracksAbort.signal });
      if (ticket !== generation || epoch !== tracksEpoch || !state.active) return null;
      if (!Array.isArray(result?.items)) throw new Error('跟踪状态格式暂不可核验。');
      state.tracks = result.items; state.tracksAvailable = result.available !== false;
      state.schedulerState = text(result.scheduler_state); state.tracksError = '';
      return { items: result.items, ticket, epoch };
    } catch (error) {
      if (ticket !== generation || epoch !== tracksEpoch || error.name === 'AbortError') return null;
      state.tracksAvailable = false; state.tracksError = error.message || '跟踪状态暂未读取成功。'; logger('discovery_tracks_read_failed', { code: error.code || 'request_failed' });
      return null;
    } finally { if (ticket === generation && epoch === tracksEpoch) changed(); }
  }
  async function load(refresh = false) {
    feedAbort?.abort(); feedAbort = new AbortController();
    const ticket = ++generation; const horizon = state.horizon;
    state.loading = true; state.error = ''; changed();
    try {
      const result = await api.discoveryFeed(horizon, refresh, { signal: feedAbort.signal });
      if (ticket !== generation || !state.active || horizon !== state.horizon) return;
      if (!result || typeof result.feed_id !== 'string' || !Array.isArray(result.themes)) throw new Error('发现资料格式暂不可用。');
      state.feed = result; state.associatedFeeds = {}; state.associationError = '';
      if (!result.themes.some(item => item.id === state.selected)) { state.selected = result.themes[0]?.id || ''; state.chain = 0; }
    } catch (error) {
      if (ticket !== generation || error.name === 'AbortError') return;
      state.error = error.message || '来源暂不可用，已有资料仍保留。'; logger('discovery_feed_read_failed', { code: error.code || 'request_failed' });
    } finally { if (ticket === generation) { state.loading = false; changed(); } }
  }
  async function activate() {
    state.active = true;
    await load();
    if (state.active && api.watchlists) { try { const result = await api.watchlists(); if (state.active) state.watchlists = list(result.items); } catch (error) { logger('discovery_watchlists_failed', {code:error.code || 'request_failed'}); } }
    if (state.active) await Promise.all([loadTracks(), loadHistory()]);
  }
  async function loadSelection(drawer = state.drawer) {
    const draft = (drawer?.kind === 'tracking' ? state.trackDrafts : state.researchDrafts)[drawer?.key];
    if (!draft || !['research', 'tracking'].includes(drawer?.kind) || draft.busy || draft.prepared || draft.saved || draft.unknown) return;
    selectionAbort?.abort(); selectionAbort = new AbortController();
    const epoch = ++selectionEpoch; const ticket = generation;
    const selectedID = drawer.theme.id; const horizon = state.horizon;
    draft.selection_loading = true; draft.selection_error = ''; draft.selection_ready = false;
    drawer.loading = true; drawer.error = ''; changed();
    try {
      const result = await api.discoverySelection(drawer.parentFeedID, selectedID, horizon, { signal: selectionAbort.signal });
      if (epoch !== selectionEpoch || ticket !== generation || !state.active || state.drawer !== drawer || state.selected !== selectedID) return;
      const selected = list(result?.themes)[0];
      if (typeof result?.feed_id !== 'string' || !result.feed_id || result.horizon !== horizon || !Array.isArray(result.themes) || result.themes.length !== 1 || selected?.id !== selectedID || !Array.isArray(selected?.materials) || !selected.materials.length || selected.materials.length > 20 || selected.materials.some(item => typeof item.id !== 'string' || !item.id)) throw new Error('当前资料范围暂不能核验，请重新读取。');
      draft.source_feed = result; draft.selected_theme = selected; draft.feed_id = result.feed_id;
      draft.material_ids = selected.materials.map(material => material.id); draft.request_id = makeID();
      draft.selection_ready = true; drawer.sourceFeed = result; drawer.theme = selected;
    } catch (error) {
      if (epoch !== selectionEpoch || ticket !== generation || error.name === 'AbortError' || !state.active || state.drawer !== drawer) return;
      draft.selection_error = error.message || '当前资料读取失败，尚未准备研究。'; drawer.error = draft.selection_error;
      logger('discovery_selection_read_failed', { code: error.code || 'request_failed' });
    } finally {
      if (epoch === selectionEpoch) draft.selection_loading = false;
      if (epoch === selectionEpoch && ticket === generation && state.drawer === drawer) { drawer.loading = false; changed(); }
    }
  }
  async function openResearch(fresh = false) {
    if (api.scenarioCatalog) { try { const result = await api.scenarioCatalog(); if (!state.active) return; state.scenarios = result.items; state.scenarioError = ''; } catch (error) { state.scenarioError = error.message || '场景目录不可读取'; logger('discovery_scenarios_failed', {code:error.code || 'request_failed'}); } }
    const item = theme(); if (!item || item.actionable === false) return;
    state.selected = item.id;
    cancelSelection();
    const unresolved = !fresh && Object.entries(state.researchDrafts).find(([, draft]) => draft.theme_id === item.id && (draft.unknown || draft.prepared?.state === 'session_configuration_required'));
    if (unresolved) {
      const draft = unresolved[1]; state.drawer = { kind: 'research', key: unresolved[0], theme: draft.selected_theme || item, sourceFeed: draft.source_feed }; changed(); return;
    }
    const key = draftKey();
    const previous = state.researchDrafts[key];
    if (fresh && previous && !previous.busy && !previous.unknown) {
      if (previous.prepared) state.researchDrafts[`${key}:${previous.request_id}`] = previous;
      delete state.researchDrafts[key];
    }
    state.researchDrafts[key] ||= { key, feed_id: '', horizon: state.horizon, theme_id: item.id, question: item.title || item.name, target_mode: 'fingpt', material_ids: [], request_id: makeID(), execute_request_id: makeID(), prepared: null, unknown: false, busy: false, error: '', selection_ready: false, selection_loading: false, selection_error: '', source_feed: null, selected_theme: null };
    if (fresh && previous && !previous.busy && !previous.unknown) for (const field of ['question', 'target_mode']) state.researchDrafts[key][field] = previous[field];
    const draft = state.researchDrafts[key];
    state.drawer = { kind: 'research', key, theme: draft.selected_theme || item, sourceFeed: draft.source_feed, parentFeedID: selectedFeedID() }; changed();
    if (!draft.prepared && !draft.unknown && !draft.selection_ready) await loadSelection(state.drawer);
  }
  async function openTracking(fresh = false) {
    const item = theme(); if (!item || item.actionable === false) return;
    cancelSelection();
    state.selected = item.id;
    const unresolved = Object.entries(state.trackDrafts).find(([, draft]) => draft.theme_id === item.id && draft.unknown);
    if (unresolved) { state.drawer = { kind: 'tracking', key: unresolved[0], theme: item }; changed(); return; }
    const key = draftKey(); const saved = fresh ? null : ownedTrack(item.id);
    if (fresh || !state.trackDrafts[key]) state.trackDrafts[key] = { key, feed_id: '', horizon: state.horizon, theme_id: item.id, condition: saved?.condition || item.next || item.title, frequency: saved?.frequency || saved?.schedule?.kind || 'daily', time: scheduleTime(saved), request_id: makeID(), saved, busy: false, unknown: false, error: '', selection_ready: false, selection_loading: false, selection_error: '', source_feed: null, selected_theme: null };
    const draft = state.trackDrafts[key];
    state.drawer = { kind: 'tracking', key, theme: draft.selected_theme || item, sourceFeed: draft.source_feed, parentFeedID: selectedFeedID() }; changed();
    if (!draft.saved && !draft.unknown && !draft.selection_ready) await loadSelection(state.drawer);
  }
  async function associate() {
    const item = theme(); if (!item || item.source_kind !== 'news' || !state.associationEvent || state.associationBusy) return;
    cancelSelection(); const id = item.id; const ticket = generation; const epoch = selectionEpoch; const candidate = state.associationEvent; state.associationBusy = true; state.associationError = ''; changed();
    try {
      const result = await api.discoveryAssociation(state.feed.feed_id, id, candidate, state.horizon);
      if (ticket !== generation || epoch !== selectionEpoch || candidate !== state.associationEvent || !state.active || theme()?.id !== id) return;
      if (typeof result?.feed_id !== 'string' || result.horizon !== state.horizon || result.themes?.length !== 1 || result.themes[0].id !== id || result.themes[0].source_kind !== 'news') throw new Error('关联资料范围不可核验。');
      state.associatedFeeds[id] = result;
    } catch (error) { if (ticket === generation && epoch === selectionEpoch) state.associationError = error.message || '关联核对未完成。'; logger('discovery_association_read_failed', {code:error.code || 'request_failed'}); }
    finally { state.associationBusy = false; changed(); }
  }
  function editDraft(name, value) {
    const drawer = state.drawer; if (!drawer || !['research', 'tracking'].includes(drawer.kind)) return;
    const draft = (drawer.kind === 'research' ? state.researchDrafts : state.trackDrafts)[drawer.key];
    if (draft.busy || draft.unknown || draft.prepared || draft.saved) return;
    const same = JSON.stringify(draft[name]) === JSON.stringify(value);
    if (!same) { draft[name] = value; draft.request_id = makeID(); draft.error = ''; }
  }
  async function prepare({ resume = false } = {}) {
    const drawer = state.drawer; const draft = state.researchDrafts[drawer?.key];
    if (!draft || draft.busy || draft.unknown) return;
    if (resume ? draft.prepared?.state !== 'session_configuration_required' || !draft.prepare_body : !!draft.prepared) return;
    if (!resume && (!draft.selection_ready || draft.selection_loading)) return;
    if (!draft.question.trim() || draft.question.length > 6000 || !draft.material_ids.length || draft.material_ids.length > 20) { draft.error = '请填写研究问题，并选择 1–20 份事件资料包。'; changed(); return; }
    if (!resume) draft.prepare_body = prepareBody(draft);
    draft.busy = true; draft.error = ''; changed();
    try {
      const result = await api.discoveryPrepare(draft.prepare_body);
      draft.prepared = result; draft.unknown = uncertain(result);
      if (!result.handoff_id) throw new Error('研究准备回执缺少标识，结果尚未确认。');
      if (result.state !== 'snapshot_ready' && !draft.unknown) draft.error = result.message || '研究资料尚未准备完成，请检查状态。';
    } catch (error) { draft.unknown = !(draft.scenario_id && ['scenario_inputs_invalid','scenario_material_selection_mismatch','scenario_cutoff_mismatch','scenario_capability_unavailable'].includes(error.code)); draft.error = error.message || '准备结果尚未确认，请保留原请求核对。'; logger('discovery_prepare_unconfirmed', { code: error.code || 'request_failed' }); }
    finally { draft.busy = false; changed(); }
  }
  async function readHandoff({ navigate = true } = {}) {
    const draft = state.researchDrafts[state.drawer?.key];
    if (!draft || draft.busy) return;
    const ticket = generation; draft.busy = true; draft.error = ''; changed();
    try {
      const result = draft.prepared?.handoff_id ? await api.discoveryHandoff(draft.prepared.handoff_id) : await api.discoveryRequest(draft.request_id);
      draft.prepared = result; draft.unknown = uncertain(result);
      restorePrepareBody(draft, result);
      if (navigate && accepted(result) && state.active && ticket === generation) onNavigate(result.target_mode || draft.target_mode, result.session_id);
    } catch (error) { draft.error = error.message || '研究状态读取失败。'; logger('discovery_handoff_read_failed', { code: error.code || 'request_failed' }); }
    finally { draft.busy = false; changed(); }
  }
  async function execute() {
    const draft = state.researchDrafts[state.drawer?.key];
    if (!draft || draft.busy || draft.unknown || draft.prepared?.state !== 'snapshot_ready') return;
    const ticket = generation; draft.busy = true; draft.error = ''; changed();
    try {
      const result = await api.discoveryExecute(draft.prepared.handoff_id, { request_id: draft.execute_request_id });
      draft.prepared = { ...draft.prepared, ...result }; draft.unknown = !accepted(result);
      if (accepted(result) && state.active && ticket === generation) onNavigate(draft.target_mode, draft.prepared.session_id);
    } catch (error) { draft.unknown = true; draft.error = error.message || '研究受理结果尚未确认，请查询原请求。'; logger('discovery_execute_unconfirmed', { code: error.code || 'request_failed' }); }
    finally { draft.busy = false; changed(); }
  }
  async function saveTrack() {
    const draft = state.trackDrafts[state.drawer?.key];
    if (!draft || draft.busy || draft.unknown || draft.saved || state.tracksAvailable === false) return;
    if (!draft.selection_ready || draft.selection_loading) return;
    if (!draft.condition.trim() || draft.condition.length > 4000 || !/^([01]\d|2[0-3]):[0-5]\d$/.test(draft.time)) { draft.error = '请填写核查条件和有效时间。'; changed(); return; }
    draft.busy = true; draft.error = ''; changed();
    try {
      const result = await api.discoveryTrackSave(Object.fromEntries(['request_id', 'feed_id', 'horizon', 'theme_id', 'condition', 'frequency', 'time'].map(key => [key, draft[key]])));
      if (!trackID(result)) throw new Error('跟踪保存回执缺少标识，结果尚未确认。');
      draft.saved = result; draft.unknown = uncertain(result);
      state.tracks = [result, ...state.tracks.filter(item => trackID(item) !== trackID(result))];
    } catch (error) { draft.unknown = true; draft.error = error.message || '保存结果尚未确认，请核对跟踪记录。'; logger('discovery_track_save_unconfirmed', { code: error.code || 'request_failed' }); }
    finally { draft.busy = false; changed(); }
  }
  async function changeTrack(enable) {
    const draft = state.trackDrafts[state.drawer?.key]; const saved = draft?.saved;
    if (!saved || draft.busy || draft.unknown || enable && state.tracksAvailable === false || trackVersion(saved) === undefined) return;
    draft.busy = true; draft.error = ''; changed();
    try {
      const result = await api.discoveryTrackState(trackID(saved), enable, { expected_version: trackVersion(saved) });
      draft.saved = { ...saved, ...result }; state.tracks = state.tracks.map(item => trackID(item) === trackID(saved) ? draft.saved : item);
      draft.unknown = uncertain(result);
    } catch (error) { draft.unknown = true; draft.error = error.message || '跟踪变更结果尚未确认，请查询状态。'; logger('discovery_track_change_unconfirmed', { code: error.code || 'request_failed' }); }
    finally { draft.busy = false; changed(); }
  }
  async function reconcileTracks() {
    const draft = state.trackDrafts[state.drawer?.key];
    if (!draft || draft.busy) return;
    const ticket = generation; draft.busy = true; changed();
    try {
      const result = await loadTracks();
      if (!state.active || ticket !== generation || state.trackDrafts[state.drawer?.key] !== draft) return;
      if (!result || result.epoch !== tracksEpoch) { draft.error = state.tracksError || draft.error; return; }
      const expectedID = trackID(draft.saved);
      const found = result.items.find(item => expectedID ? trackID(item) === expectedID : item.request_id === draft.request_id);
      if (found && typeof found.enabled === 'boolean' && typeof trackID(found) === 'string' && Number.isInteger(trackVersion(found))) {
        draft.saved = found; draft.unknown = false; draft.error = '';
      } else draft.error = '本次尚未核验到对应跟踪任务，原操作结果仍未确认。';
    } finally { draft.busy = false; changed(); }
  }
  function selectTab(id) { if (detailTabs.some(([value]) => value === id)) { state.tab = id; changed(); } }
  async function handle(event) {
    const target = event.target;
    if (!target?.closest?.('.discovery-page')) return false;
    if (target.matches?.('[data-discovery-query]') && ['input', 'compositionend'].includes(event.type)) { state.query = target.value; if (!event.isComposing) changed(); return true; }
    if (event.type === 'change' && target.dataset?.discoveryFilter) { state.filters[target.dataset.discoveryFilter] = target.value; state.selected = ''; cancelSelection(); state.drawer = null; changed(); return true; }
    if (event.type === 'change' && target.matches?.('[data-discovery-publisher]')) { state.publisher = target.value; state.selected = ''; cancelSelection(); state.drawer = null; changed(); return true; }
    if (event.type === 'change' && target.matches?.('[data-discovery-association]')) { state.associationEvent = target.value; changed(); return true; }
    if (['input', 'change'].includes(event.type) && target.matches?.('[data-discovery-field]')) {
      const name = target.dataset.discoveryField;
      const value = name === 'material_ids' ? [...target.closest('form').querySelectorAll('[name="material_ids"]:checked')].map(input => input.value) : target.value;
      editDraft(name, value); if (['scenario_id','as_of','subject_kind','subject_identity'].includes(name)) changed(); return true;
    }
    if (event.type === 'keydown' && target.matches?.('[data-discovery-action="tab"]') && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) {
      event.preventDefault(); const index = detailTabs.findIndex(([id]) => id === state.tab);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? detailTabs.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + detailTabs.length) % detailTabs.length;
      selectTab(detailTabs[next][0]); return true;
    }
    if (event.type === 'keydown' && event.key === 'Escape' && state.drawer) { event.preventDefault(); cancelSelection(); state.drawer = null; changed(); return true; }
    if (event.type === 'submit' && target.matches?.('[data-discovery-form]')) { event.preventDefault(); if (event.isComposing) return true; if (target.dataset.discoveryForm === 'research') await prepare(); else await saveTrack(); return true; }
    if (event.type !== 'click') return false;
    const action = target.closest('[data-discovery-action]'); if (!action) return false;
    event.preventDefault(); const name = action.dataset.discoveryAction;
    if (name === 'theme') { cancelSelection(); state.drawer = null; state.selected = action.dataset.id; state.chain = 0; state.tab = 'evidence'; changed(); }
    else if (name === 'view') { cancelSelection(); state.drawer = null; state.view = action.dataset.id === 'events' ? 'events' : 'news'; state.selected = ''; state.publisher = ''; state.tab = 'evidence'; state.associationEvent = ''; changed(); }
    else if (name === 'associate') await associate();
    else if (name === 'horizon' && state.horizon !== action.dataset.id) { cancelSelection(); state.horizon = action.dataset.id; state.feed = null; state.drawer = null; await load(); await Promise.all([loadTracks(), loadHistory()]); }
    else if (name === 'refresh' && !state.loading) { await load(true); await Promise.all([loadTracks(), loadHistory()]); }
    else if (name === 'chain') { state.chain = Number(action.dataset.index); changed(); }
    else if (name === 'tab') selectTab(action.dataset.id);
    else if (name === 'research' || name === 'research-new') await openResearch(name === 'research-new');
    else if (name === 'selection-refresh') await loadSelection();
    else if (name === 'tracking' || name === 'tracking-new') await openTracking(name === 'tracking-new');
    else if (name === 'close') { cancelSelection(); state.drawer = null; changed(); }
    else if (name === 'execute') await execute();
    else if (name === 'prepare-resume') await prepare({ resume: true });
    else if (name === 'handoff-status') await readHandoff();
    else if (name === 'history-status') {
      cancelSelection();
      const row = handoffRecords(state).find(item => item.handoff_id === action.dataset.id);
      if (row) {
        const local = Object.entries(state.researchDrafts).find(([, draft]) => draft.prepared?.handoff_id === row.handoff_id);
        const key = local?.[0] || `handoff:${row.handoff_id}`;
        state.researchDrafts[key] ||= { key, theme_id: row.theme_id, question: row.question || row.title, target_mode: row.target_mode, material_ids: list(row.materials).filter(item => item.kind?.includes('资料包')).map(item => item.id), request_id: row.request_id || '', execute_request_id: makeID(), prepared: row, unknown: uncertain(row), busy: false, error: '' };
        restorePrepareBody(state.researchDrafts[key], row);
        state.drawer = { kind: 'research', key, theme: theme() }; changed();
        await readHandoff({ navigate: false });
      }
    }
    else if (name === 'track-enable' || name === 'track-disable') await changeTrack(name === 'track-enable');
    else if (name === 'track-status') await reconcileTracks();
    else if (name === 'source') { cancelSelection(); state.drawer = { kind: 'source', material: list(theme()?.materials).find(item => item.id === action.dataset.id) }; changed(); }
    return true;
  }
  return { state, activate, deactivate, load, handle, associate, openResearch, openTracking, prepare, execute, readHandoff, saveTrack, changeTrack, editDraft, theme };
}

function materialRows(materials, selected = null, disabled = false, versionAction = true) {
  return list(materials).map(item => {
    const url = safeURL(item.url); const link = url && /^https?:\/\//i.test(url);
    return `<article class="d-evidence"><div class="d-source-label">${selected ? `<input type="checkbox" name="material_ids" data-discovery-field="material_ids" value="${e(item.id)}" aria-label="选择 ${e(item.title)}" ${selected.includes(item.id) ? 'checked' : ''} ${disabled ? 'disabled' : ''}>` : `<span>${e(item.label || '事件资料包')}</span>`}<span>${e(item.kind || '事件汇总')}</span></div><div><strong>${e(item.title || '未命名资料')}</strong><p>${e(item.note || '选材时将核对归档原件；此处是现有事件摘要。')}</p><small>${e(item.publisher || '来源待核实')} · 发布 ${e(intelTime(item.published_at))} · 采集 ${e(intelTime(item.acquired_at))} · 版本 ${e(item.revision ?? '待核实')}</small><details><summary>完整资料身份与内容版本</summary><p>${e(item.id || '未提供')}</p><p>${e(item.content_sha256 || '内容哈希待核对')}</p></details>${link ? `<a class="d-text-button" href="${e(url)}" target="_blank" rel="noopener noreferrer">打开来源入口 ↗</a>` : ''}</div>${selected || !versionAction ? '' : `<button class="d-text-button" type="button" data-discovery-action="source" data-id="${e(item.id)}">${item.revision === null || item.revision === undefined ? '版本待核实' : `版本 ${e(item.revision)}`}</button>`}</article>`;
  }).join('');
}
function selectionStatus(draft, drawer) {
  if (draft.selection_loading) return '<p class="d-inline-note" role="status">正在核对当前资料…此步骤只读取资料。</p>';
  if (draft.selection_error) return `<p class="notice danger" role="alert">${e(draft.selection_error)}</p><button class="button" type="button" data-discovery-action="selection-refresh">重新读取当前资料</button>`;
  if (!draft.selection_ready) return '';
  return `<p class="d-inline-note">资料预览截至 ${e(intelTime(drawer.sourceFeed?.cutoff))} · 核对当前版本后再保存。</p>${drawer.sourceFeed?.stale ? '<p class="notice warning">来源标记此归档为旧资料，请核对截止时间与覆盖缺口。</p>' : ''}${renderAssociations(drawer.theme)}`;
}

function scenarioFields(s, draft) {
  return `<section><h3>研究方法</h3>${s.scenarioError ? `<p role="alert">${e(s.scenarioError)}</p>` : ''}<label>场景<select id="discovery-scenario" data-discovery-field="scenario_id"><option value="">现有通用发现研究</option>${s.scenarios.filter(x=>['news-query','news-transmission','research-prep'].includes(x.id)).map(x=>`<option value="${e(x.id)}" ${draft.scenario_id===x.id?'selected':''}>${e(x.name)}${x.capabilities.some(c=>!c.available)?' · 能力不可用':''}</option>`).join('')}</select></label>${draft.scenario_id ? `<label>研究截止<input id="discovery-scenario-date" type="date" data-discovery-field="as_of" value="${e(draft.as_of || '')}" required></label><label>标的类型<select id="discovery-subject-kind" data-discovery-field="subject_kind">${['topic','stock','industry'].map(kind=>`<option value="${kind}" ${(draft.subject_kind || 'topic')===kind?'selected':''}>${kind}</option>`).join('')}</select></label><label>规范标的或独立主题<input id="discovery-subject-identity" data-discovery-field="subject_identity" value="${e(draft.subject_identity || '')}" required></label><p>采用完整已选资料包身份和内容Hash，不从浏览器提交正文或自报证据资格。</p>` : ''}</section>`;
}
function filterFields(s, lane) {
  const f=s.filters || {};
  const choices=(key,values,label)=>`<label>${label}<select id="discovery-filter-${key}" data-discovery-filter="${key}"><option value="">全部</option>${[...new Set(values.filter(x=>x!==undefined && x!==null && x!==''))].map(x=>`<option value="${e(String(x))}" ${f[key]===String(x)?'selected':''}>${e(String(x))}</option>`).join('')}</select></label>`;
  return `${choices('category',lane.map(x=>x.category),'分类')}${choices('importance',lane.map(x=>x.priority ?? x.importance),'来源重要性')}<label>起始<input id="discovery-filter-from" type="date" data-discovery-filter="from" value="${e(f.from || '')}"></label><label>截止<input id="discovery-filter-to" type="date" data-discovery-filter="to" value="${e(f.to || '')}"></label><label>自选关联<select id="discovery-filter-watchlist" data-discovery-filter="watchlist"><option value="">全部</option>${list(s.watchlists).map(x=>`<option value="${e(x.id)}" ${f.watchlist===x.id?'selected':''}>${e(x.name)}</option>`).join('')}</select></label>`;
}

function researchDrawer(s, d) {
  const draft = s.researchDrafts[d.key]; const p = draft.prepared; const ready = p?.state === 'snapshot_ready' && !draft.unknown;
  const canResume = p?.state === 'session_configuration_required' && !draft.unknown && !!draft.prepare_body;
  const frozen = !!p || draft.unknown;
  const body = frozen ? `<div class="d-steps"><span class="active">1 固定资料</span><span class="${ready ? 'active' : ''}">2 确认研究</span></div><div class="d-confirm-notice"><strong>${draft.unknown ? '操作结果尚未确认' : ready ? '资料已冻结 · 研究尚未提交' : '研究准备状态'}</strong><p>${e(p?.state || '结果未知')}。${draft.unknown ? '保留原请求，不会自动重发。' : canResume ? '原会话已存在，继续完成模型配置；这一步不提交研究。' : '确认后才调用现有研究流程。'}</p></div><dl class="d-review"><div><dt>研究方式</dt><dd>${draft.target_mode === 'claw' ? 'Claw' : 'FinGPT'}</dd></div><div><dt>资料截止</dt><dd>${e(intelTime(p?.cutoff || s.feed?.cutoff))}</dd></div><div><dt>选定资料</dt><dd>${draft.material_ids.length} 份 · 以冻结原件为准</dd></div><div><dt>质量状态</dt><dd>尚未检查；受理与执行完成不代表质量通过。</dd></div></dl><section class="d-review-question"><h3>研究问题</h3><p>${e(draft.question)}</p></section>${p?.scenario_context ? `<section><h3>场景 ${e(p.scenario_context.scenario.status === 'incomplete' ? '证据不完整' : '查看冻结要求')}</h3><ul>${p.scenario_context.requirements.map(x=>`<li>${e(x)}</li>`).join('')}</ul></section>` : ''}${list(p?.materials).length ? `<details class="d-frozen-materials"><summary>本次实际冻结的资料 · ${list(p.materials).length} 项</summary>${materialRows(p.materials, null, false, false)}</details>` : ''}<details class="d-technical"><summary>请求与交接标识</summary><p>${e(draft.request_id || '请求标识请以原交接记录为准')}</p><p>${e(p?.handoff_id || '交接标识待确认')}</p>${p?.context_file ? `<p>${e(p.context_file)}</p>` : ''}</details>` : `${selectionStatus(draft, d)}${scenarioFields(s, draft, frozen)}<label class="d-field">研究方式<select id="discovery-research-mode" name="target_mode" data-discovery-field="target_mode" ${draft.busy ? 'disabled' : ''}><option value="fingpt" ${draft.target_mode === 'fingpt' ? 'selected' : ''}>FinGPT</option><option value="claw" ${draft.target_mode === 'claw' ? 'selected' : ''}>Claw</option></select></label><label class="d-field">研究问题<textarea id="discovery-research-question" name="question" data-discovery-field="question" rows="5" ${draft.busy ? 'disabled' : ''} required maxlength="6000">${e(draft.question)}</textarea></label><div class="d-source-heading"><h3>${d.theme.source_kind === 'news' ? '带入研究的原始资料包' : '带入研究的事件资料包'}</h3><span>选择 1–20 份，服务端核对原件</span></div><fieldset class="d-material-selection" ${draft.busy || !draft.selection_ready ? 'disabled' : ''}><legend class="sr-only">选择研究资料</legend>${draft.selection_ready ? materialRows(d.theme.materials, draft.material_ids, draft.busy) : '<p class="d-inline-note">当前资料核对完成后再选择研究依据。</p>'}</fieldset><p class="d-inline-note">原文不可用、版本变化、时间未知或证据不足时保留缺口。页面摘要不是研究结论。</p>`;
  const footer = ready ? `<button class="button" type="button" data-discovery-action="research-new" ${draft.busy ? 'disabled' : ''}>返回修改</button><span class="d-footer-note">提交可能产生模型费用</span><button class="button primary" data-discovery-action="execute" ${draft.busy ? 'disabled' : ''}>${draft.busy ? '正在受理…' : '确认并开始研究'}</button>` : canResume ? `<button class="button" type="button" data-discovery-action="handoff-status" ${draft.busy ? 'disabled' : ''}>查询原交接状态</button><button class="button primary" type="button" data-discovery-action="prepare-resume" ${draft.busy ? 'disabled' : ''}>${draft.busy ? '继续配置中…' : '继续准备原会话'}</button>` : frozen ? `<button class="button" data-discovery-action="handoff-status" ${draft.busy ? 'disabled' : ''}>${draft.busy ? '查询中…' : '查询原交接状态'}</button>` : `<span class="d-footer-note">这一步不调用模型</span><button class="button primary" type="submit" ${draft.busy || !draft.selection_ready || draft.selection_loading ? 'disabled' : ''}>${draft.busy ? '核对并冻结中…' : '冻结资料，准备研究'}</button>`;
  return { title: '手动发起研究', subtitle: '先核对问题与资料，再明确提交。', form: 'research', body, footer, error: draft.error };
}
function trackingDrawer(s, d) {
  const draft = s.trackDrafts[d.key]; const saved = draft.saved; const locked = !!saved || draft.unknown || draft.busy;
  const unavailable = s.tracksAvailable === false;
  const body = `${saved || draft.unknown ? '' : selectionStatus(draft, d)}<div class="d-tracking-status">${chip(draft.unknown || s.tracksError && saved ? '操作结果尚未确认' : trackLabel(saved))}<p>保存草稿与开启跟踪是两个独立动作，创建不会立即执行。</p></div>${!saved && draft.selection_ready ? `<details class="d-frozen-materials"><summary>本次跟踪依据</summary>${materialRows(d.theme.materials, null, false, false)}</details>` : ''}<label class="d-field">核查条件<textarea id="discovery-track-condition" data-discovery-field="condition" name="condition" rows="4" maxlength="4000" required ${locked ? 'disabled' : ''}>${e(draft.condition)}</textarea></label><div class="d-form-row"><label class="d-field">研究日程<select id="discovery-track-frequency" data-discovery-field="frequency" name="frequency" ${locked ? 'disabled' : ''}><option value="daily" ${draft.frequency === 'daily' ? 'selected' : ''}>每天</option><option value="weekly" ${draft.frequency === 'weekly' ? 'selected' : ''}>每周五</option></select></label><label class="d-field">核查时间<input id="discovery-track-time" type="time" data-discovery-field="time" name="time" value="${e(draft.time)}" required ${locked ? 'disabled' : ''}></label></div><p class="d-inline-note">Asia/Shanghai · 沿用当前模型、资料权限和既有受控工具；无变化时保持安静。</p>${saved ? `<dl class="d-review"><div><dt>固定模型</dt><dd>${e(saved.model?.provider || '当前研究模型')} · ${e(saved.model?.model || '以保存的定义为准')}</dd></div><div><dt>调用上限</dt><dd>每天最多 ${e(saved.max_model_runs_per_day ?? 1)} 次模型研究；没有实质变化时跳过。</dd></div><div><dt>日程</dt><dd>${e(scheduleLabel(saved))} ${e(scheduleTime(saved))} · ${e(saved.scheduler_state || s.schedulerState || '以自动化中心状态为准')}</dd></div><div><dt>执行与质量</dt><dd>执行 ${e(latestRun(saved)?.execution_status || latestRun(saved)?.status || '未运行')} · 质量 ${e(latestRun(saved)?.quality_status || '未检查')}</dd></div></dl>` : ''}${unavailable ? `<p class="notice warning" role="status">${e(s.tracksError || '当前账号或运行环境未开放跟踪。研究与资料仍可查看。')}</p>` : ''}${draft.unknown ? '<p class="notice warning">保留原请求；先查询跟踪记录，不自动重复保存或变更。</p>' : ''}`;
  const footer = draft.unknown ? `<button class="button" data-discovery-action="track-status" ${draft.busy ? 'disabled' : ''}>查询跟踪状态</button>` : saved ? `<button class="button" data-discovery-action="tracking-new" ${draft.busy ? 'disabled' : ''}>另建草稿</button><button class="button ${enabled(saved) ? '' : 'primary'}" data-discovery-action="${enabled(saved) ? 'track-disable' : 'track-enable'}" ${draft.busy || unavailable && !enabled(saved) ? 'disabled' : ''}>${draft.busy ? '处理中…' : enabled(saved) ? '暂停跟踪' : '单独开启跟踪'}</button>` : `<span class="d-footer-note">保存后仍为未开启</span><button class="button primary" type="submit" ${draft.busy || unavailable || !draft.selection_ready || draft.selection_loading ? 'disabled' : ''}>${draft.busy ? '保存中…' : '保存跟踪草稿'}</button>`;
  return { title: '设置持续跟踪', subtitle: '让下一次核查有明确的问题与条件。', form: 'tracking', body, footer, error: draft.error };
}
function renderDrawer(s) {
  const d = s.drawer; if (!d) return '';
  let content;
  if (d.kind === 'research') content = researchDrawer(s, d);
  else if (d.kind === 'tracking') content = trackingDrawer(s, d);
  else { const m = d.material; if (!m) return ''; content = { title: '资料与版本', subtitle: '研究绑定选定版本，新增证据另记。', body: `<h3>${e(m.title)}</h3><p>${e(m.note)}</p><dl class="d-review"><div><dt>资料类型</dt><dd>${e(m.kind || '事件资料包')}</dd></div><div><dt>发布者</dt><dd>${e(m.publisher || '待核实')}</dd></div><div><dt>版本</dt><dd>${e(m.revision ?? '待核实')}</dd></div><div><dt>发布时间</dt><dd>${e(intelTime(m.published_at))}</dd></div><div><dt>采集时间</dt><dd>${e(intelTime(m.acquired_at))}</dd></div></dl><p class="d-inline-note">页面展示已有来源的事件归纳。冻结时核对实际原件；来源观点、研究判断和质量检查分别记录。</p>` }; }
  return `<div class="d-drawer-backdrop"><aside class="d-drawer" role="dialog" aria-modal="true" aria-labelledby="discovery-drawer-title"><header><div><span class="d-mini-label">今日发现</span><h2 id="discovery-drawer-title" tabindex="-1">${content.title}</h2><p>${content.subtitle}</p></div><button class="d-close" type="button" data-discovery-action="close" aria-label="关闭面板">${icon('close')}</button></header><form data-discovery-form="${content.form || 'source'}"><div class="d-drawer-body">${content.error ? `<p class="notice danger" role="alert">${e(content.error)}</p>` : ''}${content.body}</div><footer>${content.footer || '<button class="button" type="button" data-discovery-action="close">关闭</button>'}</footer></form></aside></div>`;
}
function renderEventContext(s, item) {
  if (item.source_kind === 'news') return '';
  const chain = list(item.chain);
  return `<section class="d-event-context"><h3>传导、标的与下一验证点</h3>${list(item.assets).length ? `<p>关联资产 ${list(item.assets).map(x=>e(text(x))).join(' · ')}</p>` : '<p class="d-inline-note">关联资产尚未映射，保持缺口。</p>'}<details><summary>来源传导关系 · ${chain.length} 环（待核验）</summary>${chain.length ? `<ol>${chain.map((x,i)=>`<li><button type="button" data-discovery-action="chain" data-index="${i}" aria-pressed="${s.chain===i}">${e(text(x.title))}</button><p>${e(text(x.reason))}</p><small>${e(x.status==='third_party_judgment'?'来源判断 · 待核验':text(x.status))}</small></li>`).join('')}</ol>` : '<p>当前来源尚未提供可核对的传导链。</p>'}</details><p>下一验证点：${e(item.next || '尚未提供具体进展，保持待核验。')}</p></section>`;
}
function renderDetail(s, item) {
  const materials = list(item.materials); const track = displayedTrack(s, item.id);
  if (s.tab === 'counter') return `<div class="d-counter-grid"><section><h3>先读反方证据</h3>${list(item.counter).map((value, i) => `<div class="d-point"><span>${i + 1}</span><p>${e(text(value))}</p></div>`).join('') || empty('当前来源未提供反方证据，不能据此认定不存在反证。')}</section><section><h3>什么会让逻辑失效</h3>${list(item.invalidation).map(value => `<p class="d-condition">${e(text(value))}</p>`).join('') || empty('失效条件尚待研究核实。')}</section><p class="d-inline-note">来源归纳与待验证条件，尚未形成通过质量检查的研究结论。</p></div>`;
  if (s.tab === 'conditions') return `<div class="d-follow-content"><div><span class="d-mini-label">下一次，核查这些变化</span><h3>${e(item.next || '先核对原件、日期与覆盖范围。')}</h3><ul>${list(item.invalidation).map(value => `<li>${e(text(value))}</li>`).join('')}</ul></div><aside><span class="d-mini-label">持续跟踪</span><strong>${trackLabel(track)}</strong><p>按确认的日程复核证据。保存草稿不会启用日程。</p><button class="button" data-discovery-action="tracking">${track ? '查看跟踪设置' : '设置跟踪'}</button>${s.tracksError ? `<p>${e(s.tracksError)}</p>` : ''}</aside></div>`;
  if (s.tab === 'history') {
    const rows = handoffRecords(s).filter(row => row.theme_id === item.id);
    return `<div class="d-history"><h3>每次判断留在当时的证据里</h3><p>交接记录只证明准备或受理状态；实际研究正文、产物与质量结果保留在原研究会话。</p>${s.historyError ? `<p class="notice warning">${e(s.historyError)}</p>` : ''}${rows.map(row => `<div class="d-draft-record"><strong>${e(row.question || row.title)}</strong><span>${e(row.state)} · 质量未核对，请查看原研究会话</span><button class="d-text-button" type="button" data-discovery-action="history-status" data-id="${e(row.handoff_id)}">核对原交接状态</button>${row.session_id ? `<a class="d-text-button" href="#/${row.target_mode === 'claw' ? 'claw' : 'fingpt'}?session=${encodeURIComponent(row.session_id)}">查看研究会话</a>` : ''}</div>`).join('') || empty('此页面尚无已准备的研究交接。')}${latestRun(track) ? `<div class="d-draft-record">最近跟踪执行 ${e(latestRun(track).execution_status || latestRun(track).status || '未知')} · 质量 ${e(latestRun(track).quality_status || '未检查')}</div>` : ''}</div>`;
  }
  return `${renderEventContext(s,item)}<div class="d-evidence-head"><p>${item.source_kind === 'news' ? '原始资讯与关联归档' : '现有事件归纳与报道线索'}</p><span>冻结时核对原件 · 版本分别保留</span></div>${materialRows(materials)}<p class="d-inline-note">摘要由现有来源提供，页面不调用模型。资料包不是单篇原文；未知时间、缺失正文及来源失败保持可见。</p>`;
}
function renderAssociations(item) {
  const rows = list(item?.related_events);
  if (!rows.length) return '';
  return `<section class="d-associated"><h3>已核验地址关联 · ${rows.length}</h3><p class="d-inline-note">仅核对所选事件的归档报道地址；不表示唯一关联，也不提升事实或报告质量。</p>${rows.map(row => `<article><strong>${e(text(row.title))}</strong><small>研判截止 ${e(intelTime(row.judgment_as_of))} · 事件记录更新 ${e(intelTime(row.event_updated_at))}</small><p>${e(text(row.judgment?.description || row.judgment?.change || '来源未给出可展示研判'))}</p>${row.judgment?.next ? `<p class="d-inline-note">下一核查点：${e(text(row.judgment.next))}</p>` : ''}<small>匹配地址 ${e(text(row.matched_url))}</small></article>`).join('')}</section>`;
}
function renderFreshness(s) {
  const f = s.feed?.freshness; const n = f?.news; const j = f?.events;
  const label = s.loading ? '正在读取来源' : s.error ? '本次连接失败，保留已有资料' : n?.status === 'unavailable' ? '原始资讯读取失败，保留上次资料' : n?.status === 'empty' ? '原始资讯来源返回空列表' : n ? '本次原始资讯读取成功' : '现有来源资料';
  const eventHint = j?.status === 'unavailable' ? '事件与研判本次读取失败，原始资讯单独更新。' : j?.cache_status === 'expired' ? '上游事件汇总缓存过期；不据此认定原始资讯没有更新。' : j?.cache_status === 'not_reported' ? '上游未独立报告事件汇总缓存状态。' : '';
  const hint = [n?.cache_status === 'expired' ? '上游原始资讯缓存过期；保留原始发布时间与缓存状态，不当作新观察开启跟踪。' : '', eventHint].filter(Boolean).join(' ');
  const coverage = n?.coverage;
  return `<div class="d-freshness" role="status"><strong>${e(label)}</strong><span>原始资讯读取 ${e(intelTime(n?.retrieved_at || (!f ? s.feed?.retrieved_at : null)))}</span><span>最新资讯发布 ${e(intelTime(n?.latest_published_at))}</span><details><summary>来源与时间说明</summary><p>本次尝试 ${e(intelTime(n?.last_attempt_at))} · 上游事件汇总 ${e(intelTime(j?.source_as_of || s.feed?.source_as_of))}</p><p>${e(hint || '来源时点、读取时间和研究冻结时间分别保留；未知时间不补造。')}</p>${coverage ? `<p>上游报告读取失败 ${e(text(coverage.failed_sources ?? '未知'))} 个，停用 ${e(text(coverage.disabled_sources ?? '未知'))} 个；未将不可用来源算作已覆盖。</p>` : ''}<p>“未形成研判”表示未关联本条RWB研判，不推断外部是否已有分析。原始归档不等于已抓取链接网页全文。</p></details></div>${hint ? `<p class="d-lane-note">${e(hint)}</p>` : ''}${s.feed?.stale && !f ? '<p class="notice warning">来源标记资料陈旧，请核对原始时间与覆盖缺口。</p>' : ''}`;
}
function renderFocus(s, item) {
  const raw = item.source_kind === 'news'; const material = list(item.materials)[0]; const url = safeURL(material?.url);
  const canAct = item.actionable !== false && list(item.materials).length;
  const candidates = list(s.feed?.events).filter(x => x.source_kind !== 'news');
  const associations = raw ? `<section class="d-association-control"><h3>已有研判</h3>${list(item.related_events).length ? renderAssociations(item) : '<p class="d-judgment-empty">未关联本条资讯的RWB研判。原始资讯先展示，不等待模型补齐。</p>'}<div class="d-judgment-clock">研判截止：${raw ? '未关联或由关联事件分别报告' : e(intelTime(item.judgment_as_of))}</div><label>核对已有事件的原始地址<select id="discovery-association" data-discovery-association aria-label="选择关联事件" ${!candidates.length || s.associationBusy || !canAct ? 'disabled' : ''}><option value="">选择当前预览中的事件</option>${candidates.map(x => `<option value="${e(x.id)}" ${x.id === s.associationEvent ? 'selected' : ''}>${e(text(x.title).slice(0,120))}</option>`).join('')}</select></label><button class="button" id="discovery-associate-button" data-discovery-action="associate" aria-disabled="${s.associationBusy}" ${!s.associationEvent || !canAct ? 'disabled' : ''}>${s.associationBusy ? '核对中…' : '核对来源地址关联'}</button>${s.associationError ? `<p class="notice warning">${e(s.associationError)}</p>` : ''}<p class="d-inline-note">一次只核对明确选择的事件；相似标题或相同主题不是关联证据。最多保留5个已核验候选。</p></section>` : `<section class="d-judgment-meta"><h3>已有事件与研判</h3><p>研判截止 ${e(intelTime(item.judgment_as_of))}</p><p class="d-inline-note">事件记录更新 ${e(intelTime(item.event_updated_at))}；事件更新时间不代替研判截止。</p></section>`;
  return `<section class="d-focus" aria-label="当前研究命题"><div class="d-focus-body"><div class="d-hero-kicker">${e(item.category || '来源未分类')} ${chip(raw ? '原始资讯 · 未形成研判' : '来源归纳 · 非质量结论')}</div><h2>${e(item.title)}</h2><div class="d-source-line"><span>${e(item.publisher || material?.publisher || '来源未报告')}</span><span>发布 ${e(intelTime(item.published_at || material?.published_at))}</span>${url && /^https?:\/\//i.test(url) ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">打开来源原文 ↗</a>` : ''}</div><section class="d-summary"><h3>${raw ? '来源摘要' : '来源现有记录'}</h3><p>${e(item.description || item.change || '来源未提供摘要。')}</p><p class="d-inline-note">现有来源返回内容，尚未独立核验原文；不构成RWB研究结论。</p>${list(item.limitations).length ? `<p class="d-inline-note">资料缺口：${list(item.limitations).map(x=>e(text(x))).join('；')}</p>` : ''}</section>${associations}<div class="d-detail-section"><div class="d-detail-tabs" role="tablist" aria-label="命题资料">${detailTabs.map(([id,name])=>`<button type="button" id="discovery-tab-${id}" role="tab" aria-selected="${s.tab===id}" aria-controls="discovery-panel-${id}" tabindex="${s.tab===id?0:-1}" data-discovery-action="tab" data-id="${id}">${name}</button>`).join('')}</div><section id="discovery-panel-${s.tab}" role="tabpanel" aria-labelledby="discovery-tab-${s.tab}">${renderDetail(s,item)}</section></div></div><footer class="d-focus-actions"><small>先核对来源，再手动研究 · 研究期限 ${e(discoveryHorizons.find(([id])=>id===s.horizon)?.slice(1).join(' · ') || '待确认')}</small><button class="button" data-discovery-action="tracking" ${canAct ? '' : 'disabled'}>设置跟踪</button><button class="button primary" data-discovery-action="research" ${canAct ? '' : 'disabled'}>手动研究 ${icon('arrowRight')}</button></footer></section>`;
}
export function renderDiscovery(s) {
  const themes = discoveryItems(s); const current = selectedItem(s);
  const lane = Array.isArray(s.feed?.news) ? (s.view === 'events' ? list(s.feed.events) : list(s.feed.news)) : list(s.feed?.themes);
  const publishers = [...new Set(lane.map(x=>x.publisher || list(x.materials)[0]?.publisher).filter(x=>typeof x==='string'))].sort();
  return `<div class="intel-page discovery-page d-page"><header class="intel-page-header"><div><p class="d-breadcrumb">研究情报 / 今日发现</p><h1>今日发现</h1></div><button id="discovery-refresh-button" class="button" data-discovery-action="refresh" aria-disabled="${s.loading}">${icon('restore')}${s.loading?'读取中…':'刷新资讯'}</button></header>${renderIntelligenceNavigation('discovery')}${renderFreshness(s)}${s.error?`<p class="notice danger" role="alert">${e(s.error)} 旧资料如有保留，请留意截止时点。</p>`:''}<div class="d-toolbar"><div class="d-lane-switch" role="group" aria-label="资料类型"><button type="button" data-discovery-action="view" data-id="news" aria-pressed="${s.view!=='events'}">最新资讯 <small>${list(s.feed?.news).length}</small></button><button type="button" data-discovery-action="view" data-id="events" aria-pressed="${s.view==='events'}">事件与已有研判 <small>${list(s.feed?.events).length}</small></button></div><div class="d-filters"><label class="d-query">${icon('search')}<input id="discovery-query" type="search" data-discovery-query value="${e(s.query)}" aria-label="筛选研究命题" placeholder="搜索标题或来源"></label><select id="discovery-publisher" data-discovery-publisher aria-label="筛选来源"><option value="">全部来源</option>${publishers.map(x=>`<option ${s.publisher===x?'selected':''}>${e(x)}</option>`).join('')}</select>${filterFields(s, lane)}<div class="d-horizons" role="group" aria-label="研究期限"><span>研究期限</span>${discoveryHorizons.map(([id,name,span])=>`<button type="button" title="${span}" data-discovery-action="horizon" data-id="${id}" aria-pressed="${s.horizon===id}">${name}</button>`).join('')}</div></div></div>${!current?`<section class="d-empty" role="status">${icon('search')}<h2>${s.loading?'正在读取线索…':s.error?'来源暂不可用':s.query||s.publisher?'没有匹配的命题':'当前来源暂无资料'}</h2><p>仅显示真实取得的资料；可调整筛选、刷新或切换资料类型，来源失败不会补造内容。</p></section>`:`<div class="d-workspace"><aside class="d-theme-column" aria-label="研究主题"><div class="d-column-title"><strong>按明确发布时间排序</strong><span>${themes.length} / ${lane.length} 条</span></div><div class="d-theme-list">${themes.map(item=>`<button type="button" class="d-theme ${current.id===item.id?'selected':''}" data-discovery-action="theme" data-id="${e(item.id)}" aria-pressed="${current.id===item.id}"><div class="d-row-meta"><span>${e(item.publisher || item.category || '来源未报告')}</span><span class="d-news-label">${item.source_kind==='news'?'未形成研判':'事件记录'}</span><time>${e(intelTime(item.published_at || list(item.materials)[0]?.published_at))}</time></div><strong>${e(item.name || item.title)}</strong>${item.change && item.change!==item.title ? `<span class="d-theme-question">${e(item.change)}</span>`:''}</button>`).join('')}</div><div class="d-list-foot">仅筛选本次有界返回集；未知发布时间不进入日期筛选。来源未提供热度时不生成热门排行。</div></aside>${renderFocus(s,current)}</div>`}<footer class="d-page-footer"><span>${e(s.feed?.source_label || 'Golddata / Vibe-Research')} · Asia/Shanghai</span><span>打开页面不调用模型 · 跟踪需单独开启</span></footer>${renderDrawer(s)}</div>`;
}
