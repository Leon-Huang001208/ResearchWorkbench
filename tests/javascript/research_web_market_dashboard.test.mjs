import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import { renderPrimaryRail } from '../../app/research_web/ui/shell.mjs';
import { createMarketDashboard, createMarketWorkspace, renderMarketWorkspace } from '../../app/research_web/ui/market-dashboard.mjs';
import { dashboardPage } from '../../app/research_web/ui/market-dashboard-view.mjs';
import { closedBars, indexQuote, scoreProjection, timelineRange, eventLane, timelineTicks, eventSourceDetails, eventPointDate } from '../../app/research_web/ui/market-dashboard-model.mjs';

const now = () => new Date('2026-11-06T12:00:00Z');
const bar = (date, close) => ({ date, timestamp: `${date}T16:00:00Z`, open: close - 1, high: close + 2, low: close - 2, close, volume: 100 });
const row = { index_id: 'SSE', market: 'CN', name: '上证综指', price: 4000, quote_trade_date: '2026-11-06', daily_bars: [bar('2026-11-03', 3000), bar('2026-11-04', 3030), bar('2026-11-05', 3050)], partial_daily_bar: bar('2026-11-06', 4000), source: 'quote-source', daily_source: 'daily-source' };
const result = { version: 'market-six-axis-v1', index_id: 'SSE', as_of: '2026-11-04', research_score: 72, effective_score: null, total_score: null, formal_score_enabled: false, production_enabled: false, activation_status: 'NOT_ACTIVATED', axes: { trend: { score: 85, status: 'available' } } };
function mockAPI(overrides = {}) {
  const calls = [];
  return { calls, async request(path, options = {}) { calls.push({ path, options }); if (overrides[path]) return overrides[path](options); if (path === '/market') return { sections: { 'indices:global-v1': { rows: [row], stale: true } } }; if (path === '/market-scores/profiles') return { items: [] }; if (path.startsWith('/market-scores/runs?')) return { historical_only: true, items: [{ id: 'saved', payload: { request: { index_id: 'SSE' }, result: { research_score: 99 } } }] }; if (path === '/market-scores/runs/saved') return { id: 'saved', current_eligibility: result, payload: { result: { research_score: 99 } } }; if (path.startsWith('/events/timeline?')) return { items: [], next_cursor: null }; throw new Error(`unexpected ${path}`); } };
}
const click = dataset => ({ preventDefault() {}, target: { closest: () => ({ dataset }) } });

test('bare/root route and brand open market; explicit FinGPT, unknown and legacy routes retain semantics', () => {
  for (const route of ['', '#', '#/', '#/market']) assert.equal(parseRoute(route).page, 'market');
  assert.equal(parseRoute('#/market').marketView, 'dashboard');
  assert.equal(parseRoute('#/fingpt?session=x').sessionId, 'x');
  assert.equal(parseRoute('#/unknown').page, 'fingpt');
  for (const view of ['overview', 'quotes', 'sectors']) assert.equal(parseRoute(`#/market?view=${view}`).marketView, view);
  assert.equal(parseRoute('#/market?view=invalid').marketView, 'overview');
  assert.match(renderPrimaryRail({ page: 'market' }), /rail-brand" href="#\/market"/);
});

test('mount reads cached global snapshot, profiles, current run eligibility and paginated timeline without POST or timer', async () => {
  const api = mockAPI(); let timers = 0;
  const dashboard = createMarketDashboard({ api, now, setTimer() { timers++; } });
  await dashboard.activate();
  assert.equal(api.calls.filter(call => call.options.method && call.options.method !== 'GET').length, 0);
  assert.equal(timers, 0);
  assert.ok(api.calls.some(call => call.path === '/market-scores/runs/saved'));
  assert.ok(!api.calls.some(call => /^\/market-scores(?:\?|$)/.test(call.path)));
  assert.ok(api.calls.some(call => call.path === '/market-scores/profiles'));
  assert.ok(api.calls.filter(call => call.path.startsWith('/market-scores/runs?')).every(call => Number(new URL(call.path, 'http://localhost').searchParams.get('limit')) <= 100));
  const timeline = new URL(api.calls.find(call => call.path.startsWith('/events/timeline?')).path, 'http://localhost');
  assert.equal(timeline.searchParams.get('start'), '2026-10-07');
  assert.equal(timeline.searchParams.get('end'), '2026-12-06');
  assert.equal(timeline.searchParams.get('limit'), '200');
  const html = dashboardPage(dashboard.state);
  assert.match(html, /历史研究分/); assert.doesNotMatch(html, />99</);
  assert.match(html, /正式评分未启用/); assert.match(html, /缺失/);
  dashboard.cancel();
});

test('refresh is explicit, keeps global index identity and follows existing reader polling/release contract', async () => {
  const api = mockAPI({ '/market/refresh': () => ({ request_id: 'global-reader', status: 'completed' }) });
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate(); await dashboard.refresh();
  const write = api.calls.find(call => call.path === '/market/refresh');
  assert.deepEqual(write.options.body, { sections: ['indices'], index_set: 'global-v1' });
  assert.equal(write.options.userAction, true);
  assert.equal(typeof write.options.key, 'string'); assert.ok(write.options.key.length >= 8);
  assert.equal(api.calls.filter(call => call.path === '/market').length, 2);
  dashboard.state.replay = '2026-11-04'; await dashboard.refresh();
  assert.equal(api.calls.filter(call => call.path === '/market/refresh').length, 1);
  dashboard.cancel();
});

test('scores never promote list/original results, alternate engines, missing axes or unactivated formal candidates', () => {
  assert.equal(scoreProjection({ payload: { result } }, row).value, null);
  assert.equal(scoreProjection({ current_eligibility: { ...result, version: 'market-observed-v1' } }, row).value, null);
  const research = scoreProjection({ current_eligibility: result }, row);
  assert.equal(research.value, 72); assert.equal(research.historical, true); assert.deepEqual(research.axes.breadth, {});
  assert.equal(scoreProjection({ current_eligibility: result }, row, 'formal').value, null);
  assert.equal(scoreProjection({ current_eligibility: result }, row, 'research', '2026-11-03').value, null);
});

test('replay truncates genuine closed bars and replaces all future quote fields; partial bar is excluded', () => {
  assert.equal(closedBars(row).length, 3);
  const replay = indexQuote(row, '2026-11-04');
  assert.equal(replay.price, 3030); assert.equal(replay.quote_trade_date, '2026-11-04');
  assert.equal(replay.change, 30); assert.equal(replay.source, 'daily-source');
  assert.equal(indexQuote(row, '2020-01-01').price, null);
  assert.deepEqual(closedBars({ daily_bars: [{ date: '2026-11-01', close: 1 }] }), []);
});

test('late responses cannot repopulate a left route or another account', async () => {
  let resolve; let identity = 'first';
  const api = mockAPI({ '/market': () => new Promise(done => { resolve = done; }) });
  const dashboard = createMarketDashboard({ api, now, getIdentity: () => identity });
  const opening = dashboard.activate(); dashboard.cancel(); resolve({ sections: { secret: {} } }); await opening;
  assert.equal(dashboard.state.snapshot, null);
  identity = 'second'; api.request = async path => path === '/market' ? { sections: {} } : { items: [] };
  await dashboard.activate(); assert.deepEqual(dashboard.state.scores, {}); dashboard.cancel();
});

test('changed account cannot start refresh, detail or filtered reads before route reactivation', async () => {
  let identity = 'first'; const api = mockAPI();
  const dashboard = createMarketDashboard({ api, now, getIdentity: () => identity }); await dashboard.activate();
  const before = api.calls.length; identity = 'second';
  await dashboard.refresh();
  await dashboard.handleChange({ target: { dataset: { mdFilter: 'market' }, value: 'US' } });
  await dashboard.handleClick(click({ mdAction: 'refresh' }));
  assert.equal(api.calls.length, before); dashboard.cancel();
});

test('index selection, mode, detail/back preserve choices; event cursor and filtering follow real endpoint', async () => {
  const api = mockAPI(); const dashboard = createMarketDashboard({ api, now }); await dashboard.activate();
  await dashboard.handleChange({ target: { dataset: { mdIndex: 'CN' }, value: 'CSI300' } });
  await dashboard.handleClick(click({ mdAction: 'detail', index: 'CSI300' }));
  await dashboard.handleClick(click({ mdAction: 'back' }));
  assert.equal(dashboard.state.selected.CN, 'CSI300'); assert.equal(dashboard.state.detail, '');
  dashboard.state.nextCursor = 'cursor+/=';
  await dashboard.handleClick(click({ mdAction: 'more' }));
  const request = new URL(api.calls.at(-1).path, 'http://localhost'); assert.equal(request.searchParams.get('cursor'), 'cursor+/=');
  dashboard.cancel();
});

test('timeline distinguishes continuous events, scenarios and calendar effects; custom ranges remain explicit', () => {
  assert.equal(eventLane({ payload: { category: 'war', lifecycle: 'ongoing' } }), 'continuous');
  assert.equal(eventLane({ payload: { category: 'macro', lifecycle: 'scenario' } }), 'forecast');
  assert.equal(eventLane({ payload: { category: 'month_end', lifecycle: 'scheduled' } }), 'calendar');
  assert.equal(eventLane({ payload: { category: 'calendar', lifecycle: 'announced' } }), 'calendar');
  assert.equal(eventLane({ payload: { category: 'calendar', lifecycle: 'scenario' } }), 'forecast');
  for (const category of ['macro', 'policy', 'sports']) assert.equal(eventLane({ payload: { category, lifecycle: 'occurred' } }), category);
  for (const category of ['war', 'geopolitics']) assert.equal(eventLane({ payload: { category, lifecycle: 'occurred' } }), 'conflict');
  for (const category of ['unexpected', 'disaster']) assert.equal(eventLane({ payload: { category, lifecycle: 'occurred' } }), 'unexpected');
  assert.deepEqual(timelineRange('custom', now(), { start: '2026-01-01', end: '2026-12-31' }), { start: '2026-01-01', end: '2026-12-31' });
});

test('auto selects formal only on current server activation and preserves explicit research choice', () => {
  const current = { ...result, as_of: row.quote_trade_date, formal_score_enabled: true, production_enabled: true, activation_status: 'ACTIVATED', effective_score: 70 };
  assert.equal(scoreProjection({ current_eligibility: current }, row).mode, 'formal');
  assert.equal(scoreProjection({ current_eligibility: current }, row).value, 70);
  assert.equal(scoreProjection({ current_eligibility: current }, row, 'research').value, 72);
  assert.equal(scoreProjection({ current_eligibility: { ...current, production_enabled: false } }, row).mode, 'research');
  assert.equal(scoreProjection({ current_eligibility: { ...current, as_of: '2026-10-01' } }, row).mode, 'research');
  assert.equal(scoreProjection({ current_eligibility: { ...current, as_of: '' } }, row).mode, 'research');
});

test('real timeline source catalog resolves directory separately from publication, observation and revision evidence', async () => {
  const event = { id: 'real-calendar', revision: 2, payload: { title: '真实DTO日历记录', category: 'calendar', date_precision: 'day', lifecycle: 'announced', occurrence_start: '2026-11-10', markets: ['US'], admission: 'candidate', source: 'fed_fomc', source_published_at: '2026-11-01T09:00:00Z', first_observed: '2026-11-02T10:00:00Z', evidence_refs: [{ id: 'evidence-original', sha256: 'sha-original' }] } };
  const sources = [{ id: 'fed_fomc', label: 'FOMC官方日程', url: 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm' }];
  const api = mockAPI(); const original = api.request.bind(api);
  api.request = async (path, options) => path.startsWith('/events/timeline?') ? { items: [event], sources } : path === '/events/real-calendar' ? { ...event, evidence_gaps: ['revision_original_unresolved'] } : original(path, options);
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate();
  assert.deepEqual(dashboard.state.sources, sources);
  await dashboard.handleClick(click({ mdAction: 'event', id: event.id }));
  const html = dashboardPage(dashboard.state);
  for (const text of ['FOMC官方日程', '来源目录页面', '2026-11-01T09:00:00Z', '2026-11-02T10:00:00Z', 'evidence-original', 'revision_original_unresolved', '该版本原件链接未提供／未解析', '交易状态待确认', '缓存时效', '待研究 · 未计分', '日期与星期刻度']) assert.ok(html.includes(text), text);
  assert.match(html, /option value="calendar"/); assert.match(html, /md-lane-calendar/);
  assert.doesNotMatch(html, />原始来源 ↗</);
  assert.equal(eventSourceDetails({ source: 'missing' }, sources).directoryURL, '');
  assert.equal(eventSourceDetails(event.payload, [{ ...sources[0], url: 'javascript:alert(1)' }]).directoryURL, '');
  dashboard.cancel();
});

test('month, interval and unknown precision stay visible without fabricated date points or OHLC event marks', async () => {
  const events = ['month', 'interval', 'unknown'].map((precision, i) => ({ id: precision, revision: 1, payload: { title: `精度记录${i}`, category: 'policy', date_precision: precision, occurrence_start: precision === 'month' ? '2026-11' : '2026-11-03', lifecycle: 'occurred', markets: ['CN'] } }));
  for (const event of events) assert.equal(eventPointDate(event), null);
  assert.equal(eventPointDate({ payload: { date_precision: 'day', occurrence_start: '2026-11-03' } }), '2026-11-03');
  const dashboard = createMarketDashboard({ api: mockAPI(), now }); await dashboard.activate();
  dashboard.state.events = events; dashboard.state.detail = 'SSE';
  const html = dashboardPage(dashboard.state);
  assert.match(html, /月份区间／时间待精确/); assert.match(html, /3 条已加载记录/);
  for (const event of events) { assert.ok(html.includes(event.payload.title)); assert.ok(!new RegExp(`class="md-time-event[^>]+data-id="${event.id}"`).test(html)); }
  assert.doesNotMatch(html, /<circle/);
  const ticks = timelineTicks({ start: '2026-11-01', end: '2026-11-08' }); assert.equal(ticks[0].weekday, '周日'); assert.equal(ticks.at(-1).position, 100);
  dashboard.cancel();
});

test('workspace shows one heading and one tab row while retaining all legacy analysis content', async () => {
  const api = mockAPI(); const workspace = createMarketWorkspace({ api, now, storage: null });
  await workspace.activate({ marketView: 'dashboard' });
  for (const view of ['dashboard', 'overview', 'quotes', 'sectors', 'workbench']) {
    const html = renderMarketWorkspace(workspace, { marketView: view });
    assert.equal((html.match(/<h1>/g) || []).length, 1);
    assert.equal((html.match(/aria-label="全市场概览页面"/g) || []).length, 1);
    assert.match(html, /行情分析/); assert.match(html, /研究工作台/);
  }
  workspace.cancel();
});

test('ASC score history follows all cursors and requalifies latest same-index record on a later page', async () => {
  const api = mockAPI(), original = api.request.bind(api), requested = [];
  api.request = async (path, options = {}) => {
    requested.push(path);
    if (path.startsWith('/market-scores/runs?')) {
      const params = new URL(path, 'http://localhost').searchParams; assert.equal(params.get('limit'), '100');
      return params.has('cursor') ? { items: [{ id: 'newest', created_at: '2026-11-06', payload: { request: { index_id: 'SSE' } } }], next_cursor: null, historical_only: true } : { items: [{ id: 'oldest', created_at: '2026-10-01', payload: { request: { index_id: 'SSE' } } }], next_cursor: '100', historical_only: true };
    }
    if (path === '/market-scores/runs/newest') return { id: 'newest', current_eligibility: result };
    if (path === '/market-scores/runs/oldest') throw new Error('must not select oldest');
    return original(path, options);
  };
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate();
  assert.equal(dashboard.state.scores.SSE.id, 'newest'); assert.equal(dashboard.state.scoreCoverage.complete, true);
  assert.ok(requested.includes('/market-scores/runs?limit=100&cursor=100'));
  dashboard.cancel();
});

test('capped history reports incomplete coverage instead of calling a prefix latest or inferring no runs', async () => {
  const api = mockAPI(), original = api.request.bind(api); let pages = 0;
  api.request = async (path, options = {}) => path.startsWith('/market-scores/runs?') ? { items: [{ id: 'prefix', payload: { request: { index_id: 'SSE' } } }], next_cursor: String(++pages * 100) } : original(path, options);
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate();
  assert.equal(pages, 20); assert.equal(dashboard.state.scoreCoverage.complete, false); assert.deepEqual(dashboard.state.scores, {});
  assert.match(dashboardPage(dashboard.state), /评分历史覆盖未完整/); dashboard.cancel();
});

test('refresh transport sends stable idempotency header; unknown response is never auto-retried', async () => {
  const requests = []; let unknown = true;
  const api = createAPI({ logger() {}, fetcher: async (url, options) => {
    requests.push({ url, options });
    if (url.endsWith('/market/refresh')) { if (unknown) throw new Error('network outcome unknown'); return new Response(JSON.stringify({ request_id: 'idempotent-reader', status: 'completed' }), { status: 200 }); }
    return new Response(JSON.stringify(url.endsWith('/market') ? { sections: {} } : { items: [] }), { status: 200 });
  } });
  let keys = 0; const dashboard = createMarketDashboard({ api, now, makeKey: () => `stable-refresh-key-${++keys}` });
  await dashboard.activate(); await dashboard.refresh();
  assert.equal(requests.filter(call => call.url.endsWith('/market/refresh')).length, 1);
  unknown = false; await dashboard.refresh();
  const writes = requests.filter(call => call.url.endsWith('/market/refresh'));
  assert.equal(writes[0].options.headers['Idempotency-Key'], 'stable-refresh-key-1');
  assert.equal(writes[1].options.headers['Idempotency-Key'], 'stable-refresh-key-1');
  assert.equal(writes[1].options.headers['X-Research-User-Action'], '?1');
  await dashboard.refresh(); assert.equal(keys, 2); dashboard.cancel();
});

test('close and reopen the same event fences a late older revision within one activation', async () => {
  const api = mockAPI(), original = api.request.bind(api), pending = [];
  const event = { id: 'same-id', revision: 1, payload: { title: '候选', category: 'policy', occurrence_start: '2026-11-01', markets: ['CN'] } };
  api.request = async (path, options) => path === '/events/same-id' ? new Promise(resolve => pending.push(resolve)) : original(path, options);
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate(); dashboard.state.events = [event];
  const first = dashboard.handleClick(click({ mdAction: 'event', id: event.id }));
  await dashboard.handleClick(click({ mdAction: 'close' }));
  const second = dashboard.handleClick(click({ mdAction: 'event', id: event.id }));
  pending[1]({ ...event, revision: 3 }); await second;
  pending[0]({ ...event, revision: 2 }); await first;
  assert.equal(dashboard.state.drawer.revision, 3); dashboard.cancel();
});

test('detail evidence distinguishes incomplete history, pending/failed detail and confirmed absence', async () => {
  const dashboard = createMarketDashboard({ api: mockAPI(), now }); await dashboard.activate();
  const state = dashboard.state; state.detail = 'SSE'; state.scores = {};
  state.scoreCoverage = { complete: false };
  assert.match(dashboardPage(state), /尚未完整读取/); assert.doesNotMatch(dashboardPage(state), /EMPTY/);
  state.scoreCoverage = { complete: true, indices: ['SSE'] };
  assert.match(dashboardPage(state), /DETAIL_PENDING/); assert.doesNotMatch(dashboardPage(state), /EMPTY/);
  state.errors['score:SSE'] = 'read failed';
  assert.match(dashboardPage(state), /详情读取失败/); assert.doesNotMatch(dashboardPage(state), /EMPTY/);
  delete state.errors['score:SSE']; state.scoreCoverage.indices = [];
  assert.match(dashboardPage(state), /EMPTY/); assert.match(dashboardPage(state), /完整历史读取后未发现/);
  dashboard.cancel();
});

test('filter first-page pending invalidates old cursor and rejects more until the new query commits', async () => {
  const api = mockAPI(), original = api.request.bind(api), pending = [], reads = [];
  api.request = async (path, options) => {
    if (!path.startsWith('/events/timeline?')) return original(path, options);
    reads.push(path); const params = new URL(path, 'http://localhost').searchParams;
    if (params.get('market')) return new Promise(resolve => pending.push(resolve));
    return { items: [{ id: 'old', payload: { markets: ['CN'] } }], next_cursor: '100' };
  };
  const dashboard = createMarketDashboard({ api, now }); await dashboard.activate();
  const us = dashboard.handleChange({ target: { dataset: { mdFilter: 'market' }, value: 'US' } });
  assert.equal(dashboard.state.nextCursor, ''); assert.deepEqual(dashboard.state.events, []);
  await dashboard.handleClick(click({ mdAction: 'more' })); assert.equal(reads.length, 2);
  const hk = dashboard.handleChange({ target: { dataset: { mdFilter: 'market' }, value: 'HK' } });
  pending[1]({ items: [{ id: 'hk', payload: { markets: ['HK'] } }], next_cursor: 'hk-next' }); await hk;
  pending[0]({ items: [{ id: 'us', payload: { markets: ['US'] } }], next_cursor: 'us-next' }); await us;
  assert.deepEqual(dashboard.state.events.map(row => row.id), ['hk']); assert.equal(dashboard.state.nextCursor, 'hk-next');
  assert.ok(reads.filter(path => path.includes('market=')).every(path => !path.includes('cursor=')));
  dashboard.cancel();
});

test('confirmed reader cancellation retires its idempotency intent before returning to refresh', async () => {
  const api = mockAPI(), original = api.request.bind(api), keys = []; let polling = false;
  api.request = async (path, options = {}) => {
    if (path === '/market/refresh') { keys.push(options.key); return { request_id: `reader-${keys.length}`, status: keys.length === 1 ? 'running' : 'completed' }; }
    if (path === '/market/refresh/reader-1' && options.method === 'DELETE') return { status: 'cancelled', request_id: 'reader-1' };
    return original(path, options);
  };
  let generated = 0;
  const dashboard = createMarketDashboard({ api, now, makeKey: () => `cancellation-key-${++generated}`, setTimer() { polling = true; return 1; }, clearTimer() {} });
  await dashboard.activate(); const first = dashboard.refresh();
  for (let i = 0; i < 10 && !polling; i++) await Promise.resolve();
  assert.equal(polling, true); dashboard.cancel(); await first;
  await dashboard.activate(); await dashboard.refresh();
  assert.deepEqual(keys, ['cancellation-key-1', 'cancellation-key-2']); dashboard.cancel();
});
