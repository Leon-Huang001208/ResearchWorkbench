import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI, parseRoute } from '../../app/research_web/ui/core.mjs';
import { createDiscoveryController, filterDiscoveryThemes, renderDiscovery } from '../../app/research_web/ui/discovery.mjs';
import { renderIntelligenceNavigation } from '../../app/research_web/ui/intel.mjs';

const theme = { id: 'ai', name: 'AI 资本开支', category: '科技', title: '订单能否兑现？', description: '来源归纳', change: '订单变化', next: '核实财报', state: '待核实', counter: ['供给过剩'], invalidation: ['订单未兑现'], chain: [{ title: '投资', status: '待验证', reason: '核对原件' }], materials: [{ id: 'event-1', title: '已有事件', label: '事件资料包', publisher: '现有来源', kind: '事件归纳', url: 'https://example.com/a', event_id: 'event-1', revision: 3, acquired_at: '2026-10-23T02:00:00Z', published_at: null }] };
const feed = { feed_id: 'feed-1', horizon: 'medium', cutoff: '2026-10-23T01:00:00Z', retrieved_at: '2026-10-23T02:00:00Z', source: '现有研究情报', themes: [theme] };
const prepared = { handoff_id: 'handoff-1', session_id: 'session-1', target_mode: 'fingpt', state: 'snapshot_ready', execution_started: false, cutoff: feed.cutoff, context_file: 'inputs/page-context/discovery.json' };
function harness(overrides = {}) {
  const calls = []; const navigations = []; const changes = []; let n = 0; let latestFeed = structuredClone(feed);
  const methods = {
    discoveryFeed: async () => structuredClone(feed), discoveryTracks: async () => ({ items: [], available: true }),
    discoveryHandoffs: async () => ({ items: [] }),
    discoverySelection: async (_feedID, themeID, horizon) => ({ ...latestFeed, feed_id: `selection-${themeID}`, horizon, themes: latestFeed.themes.filter(item => item.id === themeID) }),
    discoveryPrepare: async () => ({ ...prepared }), discoveryHandoff: async () => ({ ...prepared }), discoveryRequest: async () => ({ ...prepared }),
    discoveryExecute: async () => ({ ...prepared, state: 'running', execution_started: true }),
    discoveryTrackSave: async body => ({ ...body, id: 'track-1', theme_id: 'ai', enabled: false, definition_version: 1 }),
    discoveryTrackState: async (id, turnOn) => ({ id, theme_id: 'ai', enabled: turnOn, definition_version: 2 }), ...overrides,
  };
  const api = Object.fromEntries(Object.entries(methods).map(([key, fn]) => [key, async (...args) => { calls.push({ key, args: structuredClone(args) }); const result = await fn(...args); if (key === 'discoveryFeed') latestFeed = structuredClone(result); return result; }]));
  const c = createDiscoveryController({ api, makeID: () => `request-${++n}`, onNavigate: (...args) => navigations.push(args), onChange: () => changes.push(true), logger: () => {} });
  return { c, calls, navigations, changes };
}
function event(type, { matches = '', action = '', id = '', value = '', key = '', isComposing = false } = {}) {
  const target = { value, dataset: { discoveryAction: action, id }, matches: selector => selector.includes(matches) && !!matches, closest: selector => selector === '.discovery-page' ? {} : selector === '[data-discovery-action]' && action ? target : null };
  return { type, target, key, isComposing, preventDefault() { this.prevented = true; } };
}

test('canonical discovery route is first intelligence tab and existing defaults stay valid', () => {
  assert.equal(parseRoute('#/intel/discovery').intelTab, 'discovery');
  assert.equal(parseRoute('#/intel/overview').intelTab, 'overview');
  assert.equal(parseRoute('#/intel/unknown').intelTab, 'overview');
  const html = renderIntelligenceNavigation('discovery');
  assert.ok(html.indexOf('#/intel/discovery') < html.indexOf('#/intel/hot'));
  assert.match(html, /href="#\/intel\/discovery" class="active" aria-current="page"/);
});
test('opening discovery only reads feed and tracking state; no research or model admission', async () => {
  const { c, calls } = harness(); assert.equal(calls.length, 0);
  await c.activate();
  assert.deepEqual(calls.map(call => call.key), ['discoveryFeed', 'discoveryTracks', 'discoveryHandoffs']);
  assert.equal(c.state.feed.feed_id, 'feed-1'); assert.equal(c.state.selected, 'ai');
  assert.equal(calls[0].args[1], false);
});
test('current selection preview is read-only and does not replace the complete main feed', async () => {
  const second = { ...theme, id: 'other', name: '另一主题' };
  const { c, calls } = harness({ discoveryFeed: async () => ({ ...feed, themes: [theme, second] }) });
  await c.activate(); await c.openResearch();
  assert.equal(calls.filter(call => call.key === 'discoverySelection').length, 1);
  assert.deepEqual(calls.find(call => call.key === 'discoverySelection').args.slice(0, 3), ['feed-1', 'ai', 'medium']);
  assert.equal(c.state.feed.feed_id, 'feed-1'); assert.equal(c.state.feed.themes.length, 2);
  assert.equal(c.state.drawer.sourceFeed.feed_id, 'selection-ai');
  assert.equal(calls.filter(call => call.key === 'discoveryPrepare' || call.key === 'discoveryExecute').length, 0);
});
test('failed current selection preview cannot fall back to preparing compact homepage materials', async () => {
  const { c, calls } = harness({ discoverySelection: async () => { throw new Error('当前资料读取失败'); } });
  await c.activate(); await c.openResearch(); await c.prepare();
  assert.equal(calls.filter(call => call.key === 'discoveryPrepare').length, 0);
  assert.ok(renderDiscovery(c.state).includes('当前资料读取失败'));
});
test('selection preview loading and late departure cannot overwrite a later drawer or page', async () => {
  let finish;
  const { c, calls } = harness({ discoverySelection: () => new Promise(done => { finish = done; }) });
  await c.activate(); const opening = c.openResearch();
  assert.equal(typeof finish, 'function', 'opening the drawer starts one current-details read');
  assert.ok(renderDiscovery(c.state).includes('正在核对当前资料'));
  await c.prepare(); assert.equal(calls.filter(call => call.key === 'discoveryPrepare').length, 0);
  c.deactivate(); finish({ ...feed, feed_id: 'late-selection', themes: [theme] }); await opening;
  assert.equal(c.state.drawer, null); assert.equal(c.state.feed.feed_id, 'feed-1');
  assert.equal(Object.values(c.state.researchDrafts).some(draft => draft.selection_ready), false);
});
test('prepare freezes the selected current preview ID and materials rather than compact-list hashes', async () => {
  const detailed = { ...theme, materials: [{ ...theme.materials[0], id: 'event-current-detail-version', revision: 3 }] };
  const { c, calls } = harness({ discoverySelection: async () => ({ ...feed, feed_id: 'current-detail-feed', themes: [detailed] }) });
  await c.activate(); await c.openResearch(); c.editDraft('question', '核对当前原件'); await c.prepare();
  const body = calls.find(call => call.key === 'discoveryPrepare').args[0];
  assert.equal(body.feed_id, 'current-detail-feed'); assert.deepEqual(body.material_ids, ['event-current-detail-version']);
  assert.equal(body.question, '核对当前原件'); assert.equal(c.state.feed.feed_id, 'feed-1');
});
test('switching themes discards a late selection without replacing the next selected drawer', async () => {
  let finish;
  const second = { ...theme, id: 'other', name: '另一主题' };
  const { c } = harness({
    discoveryFeed: async () => ({ ...feed, themes: [theme, second] }),
    discoverySelection: async (_feedID, themeID) => themeID === 'ai' ? new Promise(done => { finish = done; }) : { ...feed, feed_id: 'other-selection', themes: [second] },
  });
  await c.activate(); const opening = c.openResearch(); await c.handle(event('click', { action: 'theme', id: 'other' })); await c.openResearch();
  const next = c.state.drawer; finish({ ...feed, feed_id: 'late-ai-selection', themes: [theme] }); await opening;
  assert.equal(c.state.drawer, next); assert.equal(c.state.drawer.sourceFeed.feed_id, 'other-selection'); assert.equal(c.state.drawer.theme.id, 'other');
});
test('new tracking drafts use their own current selection and preview failures cannot save', async () => {
  const { c, calls } = harness({ discoverySelection: async () => ({ ...feed, feed_id: 'tracking-detail-feed', themes: [theme] }) });
  await c.activate(); await c.openTracking(); await c.saveTrack();
  assert.equal(calls.find(call => call.key === 'discoveryTrackSave').args[0].feed_id, 'tracking-detail-feed');
  assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 0); assert.equal(c.state.feed.feed_id, 'feed-1');
  const failed = harness({ discoverySelection: async () => { throw new Error('跟踪依据读取失败'); } });
  await failed.c.activate(); await failed.c.openTracking(); await failed.c.saveTrack();
  assert.equal(failed.calls.filter(call => call.key === 'discoveryTrackSave').length, 0);
  assert.ok(renderDiscovery(failed.c.state).includes('跟踪依据读取失败'));
});
test('reopening prepared or unknown research preserves original request without another selection read', async () => {
  for (const state of ['snapshot_ready', 'session_outcome_unknown', 'session_configuration_required']) {
    const { c, calls } = harness({ discoveryPrepare: async () => ({ ...prepared, state }) });
    await c.activate(); await c.openResearch(); const draft = c.state.researchDrafts[c.state.drawer.key]; const id = draft.request_id;
    await c.prepare(); await c.handle(event('click', { action: 'close' })); await c.openResearch();
    assert.equal(c.state.researchDrafts[c.state.drawer.key], draft); assert.equal(draft.request_id, id);
    assert.equal(calls.filter(call => call.key === 'discoverySelection').length, 1);
  }
});
test('research freezes exact selected event package and requires a second explicit execute', async () => {
  const { c, calls, navigations } = harness(); await c.activate(); await c.openResearch();
  c.editDraft('question', '核对原件后研究反方'); c.editDraft('material_ids', ['event-1']);
  const draft = c.state.researchDrafts[c.state.drawer.key]; const key = draft.request_id;
  await c.prepare();
  const request = calls.find(call => call.key === 'discoveryPrepare').args[0];
  assert.deepEqual(request, { request_id: key, feed_id: 'selection-ai', horizon: 'medium', theme_id: 'ai', material_ids: ['event-1'], target_mode: 'fingpt', question: '核对原件后研究反方' });
  assert.equal(calls.filter(call => call.key === 'discoveryExecute').length, 0);
  assert.equal(draft.prepared.execution_started, false); assert.equal(navigations.length, 0);
  await c.execute(); assert.equal(calls.filter(call => call.key === 'discoveryExecute').length, 1);
  assert.deepEqual(navigations, [['fingpt', 'session-1']]);
});
test('lost prepare reply preserves original request and recovers by GET without another POST', async () => {
  const { c, calls } = harness({ discoveryPrepare: async () => { throw new Error('响应丢失'); } });
  await c.activate(); await c.openResearch(); const draft = c.state.researchDrafts[c.state.drawer.key]; const id = draft.request_id;
  await c.prepare(); assert.equal(draft.unknown, true); assert.equal(draft.request_id, id);
  await c.prepare(); assert.equal(calls.filter(call => call.key === 'discoveryPrepare').length, 1);
  await c.readHandoff();
  assert.deepEqual(calls.find(call => call.key === 'discoveryRequest').args, [id]);
  assert.equal(draft.unknown, false); assert.equal(draft.prepared.state, 'snapshot_ready');
});
test('unknown model acceptance does not navigate or resend and checks the same handoff', async () => {
  const { c, calls, navigations } = harness({ discoveryExecute: async () => ({ state: 'execution_outcome_unknown', execution_started: null }) });
  await c.activate(); await c.openResearch(); await c.prepare();
  const draft = c.state.researchDrafts[c.state.drawer.key]; const id = draft.execute_request_id;
  await c.execute(); await c.execute();
  assert.equal(draft.unknown, true); assert.equal(calls.filter(call => call.key === 'discoveryExecute').length, 1);
  assert.equal(calls.find(call => call.key === 'discoveryExecute').args[1].request_id, id);
  assert.equal(navigations.length, 0);
  await c.readHandoff(); assert.deepEqual(calls.find(call => call.key === 'discoveryHandoff').args, ['handoff-1']);
});
test('confirmation reviews the actual frozen article versions and editing makes a separate request', async () => {
  const { c } = harness({ discoveryPrepare: async () => ({ ...prepared, materials: [{ ...theme.materials[0], title: '本次冻结归档报道', revision: 7 }] }) });
  await c.activate(); await c.openResearch(); const draft = c.state.researchDrafts[c.state.drawer.key]; const id = draft.request_id;
  await c.prepare(); const html = renderDiscovery(c.state);
  assert.match(html, /本次冻结归档报道/); assert.match(html, /版本 7/);
  await c.handle(event('click', { action: 'research-new' }));
  const next = c.state.researchDrafts[c.state.drawer.key];
  assert.notEqual(next.request_id, id); assert.equal(next.prepared, null);
  assert.ok(Object.values(c.state.researchDrafts).some(item => item.request_id === id && item.prepared));
});
test('accepted execution arriving after route deactivation never navigates another page', async () => {
  let finish;
  const { c, navigations } = harness({ discoveryExecute: () => new Promise(done => { finish = done; }) });
  await c.activate(); await c.openResearch(); await c.prepare(); const task = c.execute(); c.deactivate();
  finish({ ...prepared, state: 'running', execution_started: true }); await task;
  assert.equal(navigations.length, 0);
});
test('tracking save stays disabled until a distinct version-bound enable and supports pause', async () => {
  const { c, calls } = harness(); await c.activate(); await c.openTracking();
  const draft = c.state.trackDrafts[c.state.drawer.key]; const original = draft.request_id;
  c.editDraft('condition', '核查订单是否撤回'); assert.notEqual(draft.request_id, original);
  const requestID = draft.request_id; await c.saveTrack();
  assert.equal(draft.saved.enabled, false); assert.equal(draft.request_id, requestID);
  assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 0);
  await c.changeTrack(true);
  assert.deepEqual(calls.find(call => call.key === 'discoveryTrackState').args, ['track-1', true, { expected_version: 1 }]);
  assert.equal(draft.saved.enabled, true);
  await c.changeTrack(false); assert.equal(draft.saved.enabled, false);
});
test('tracking unknown saves retain the original request and never auto-enable or repeat', async () => {
  const { c, calls } = harness({ discoveryTrackSave: async () => { throw new Error('连接中断'); } });
  await c.activate(); await c.openTracking(); const draft = c.state.trackDrafts[c.state.drawer.key]; const id = draft.request_id;
  await c.saveTrack(); await c.saveTrack();
  assert.equal(draft.unknown, true); assert.equal(draft.request_id, id);
  assert.equal(calls.filter(call => call.key === 'discoveryTrackSave').length, 1);
  assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 0);
});
test('failed tracking status GET cannot clear an unknown enable using the old disabled row', async () => {
  let reads = 0;
  const old = { id: 'track-1', theme_id: 'ai', enabled: false, definition_version: 1, condition: '核查原件' };
  const { c, calls } = harness({
    discoveryTracks: async () => { if (++reads > 1) throw new Error('GET失败'); return { available: true, items: [old] }; },
    discoveryTrackState: async () => { throw new Error('启用回执丢失'); },
  });
  await c.activate(); await c.openTracking(); const draft = c.state.trackDrafts[c.state.drawer.key];
  await c.changeTrack(true); assert.equal(draft.unknown, true);
  await c.handle(event('click', { action: 'track-status' }));
  assert.equal(draft.unknown, true); assert.match(renderDiscovery(c.state), /操作结果尚未确认/);
  await c.changeTrack(true); assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 1);
  await c.handle(event('click', { action: 'close' })); c.state.tab = 'conditions';
  assert.equal(renderDiscovery(c.state).includes('已保存 · 未开启'), false, 'cached disabled task must not become a confirmed status outside the drawer');
  c.state.feed = { ...c.state.feed, feed_id: 'new-feed-version' }; await c.openTracking();
  assert.equal(c.state.trackDrafts[c.state.drawer.key], draft, 'a new feed cannot bypass the unresolved original task');
});
test('stale tracking status epoch cannot clear unknown after leaving and returning to the page', async () => {
  let reads = 0; let finish;
  const old = { id: 'track-1', theme_id: 'ai', enabled: false, definition_version: 1, condition: '核查原件' };
  const { c } = harness({
    discoveryTracks: async () => { reads += 1; return reads === 2 ? new Promise(done => { finish = done; }) : { available: true, items: [old] }; },
    discoveryTrackState: async () => { throw new Error('启用回执丢失'); },
  });
  await c.activate(); await c.openTracking(); const draft = c.state.trackDrafts[c.state.drawer.key]; await c.changeTrack(true);
  const reading = c.handle(event('click', { action: 'track-status' })); c.deactivate(); await c.activate(); await c.openTracking();
  finish({ available: true, items: [{ ...old, enabled: true, definition_version: 2 }] }); await reading;
  assert.equal(draft.unknown, true); assert.equal(draft.saved.enabled, false);
});
test('configuration-required recovery explicitly resumes the original prepare UUID and exact body', async () => {
  let prepares = 0;
  const { c, calls } = harness({
    discoveryPrepare: async () => ({ ...prepared, state: ++prepares === 1 ? 'session_outcome_unknown' : 'snapshot_ready' }),
    discoveryHandoff: async () => ({ ...prepared, state: 'session_configuration_required' }),
  });
  await c.activate(); await c.openResearch(); const draft = c.state.researchDrafts[c.state.drawer.key]; const originalID = draft.request_id;
  await c.prepare(); await c.readHandoff();
  assert.ok(renderDiscovery(c.state).includes('继续准备原会话'), 'configuration recovery action is visible');
  await c.handle(event('click', { action: 'prepare-resume' }));
  const posts = calls.filter(call => call.key === 'discoveryPrepare');
  assert.equal(posts.length, 2); assert.deepEqual(posts[1].args, posts[0].args);
  assert.equal(draft.request_id, originalID); assert.equal(draft.prepared.state, 'snapshot_ready');
  assert.equal(calls.filter(call => call.key === 'discoveryExecute').length, 0);
});
test('persisted configuration recovery uses the Host original prepare body and missing legacy bodies stay read-only', async () => {
  const original = { request_id: 'original-request-id', feed_id: 'original-feed-id', horizon: 'long', theme_id: 'ai', material_ids: ['original-event-version'], target_mode: 'claw', question: '原研究问题' };
  const row = { ...prepared, theme_id: 'ai', state: 'session_configuration_required', prepare_request: original };
  const { c, calls } = harness({ discoveryHandoffs: async () => ({ items: [row] }), discoveryHandoff: async () => row });
  await c.activate(); await c.handle(event('click', { action: 'history-status', id: 'handoff-1' }));
  assert.ok(renderDiscovery(c.state).includes('继续准备原会话'));
  await c.handle(event('click', { action: 'prepare-resume' }));
  assert.deepEqual(calls.find(call => call.key === 'discoveryPrepare').args, [original]);
  const legacy = harness({ discoveryHandoffs: async () => ({ items: [{ ...row, prepare_request: undefined }] }), discoveryHandoff: async () => ({ ...row, prepare_request: undefined }) });
  await legacy.c.activate(); await legacy.c.handle(event('click', { action: 'history-status', id: 'handoff-1' }));
  assert.equal(renderDiscovery(legacy.c.state).includes('继续准备原会话'), false);
  await legacy.c.handle(event('click', { action: 'prepare-resume' }));
  assert.equal(legacy.calls.filter(call => call.key === 'discoveryPrepare').length, 0);
});
test('successful status GET must identify the same saved task before clearing an unknown change', async () => {
  let reads = 0;
  const old = { id: 'track-1', theme_id: 'ai', enabled: false, definition_version: 1, condition: '核查原件' };
  const { c } = harness({ discoveryTracks: async () => ({ available: true, items: [{ ...old, id: ++reads === 1 ? 'track-1' : 'other-task' }] }), discoveryTrackState: async () => { throw new Error('启用回执丢失'); } });
  await c.activate(); await c.openTracking(); const draft = c.state.trackDrafts[c.state.drawer.key]; await c.changeTrack(true);
  await c.handle(event('click', { action: 'track-status' }));
  assert.equal(draft.unknown, true); assert.equal(draft.saved.id, 'track-1');
});
test('unknown native-session absence only offers reads and never resumes a prepare mutation', async () => {
  const { c, calls } = harness({ discoveryPrepare: async () => ({ ...prepared, state: 'session_outcome_unknown' }), discoveryHandoff: async () => ({ ...prepared, state: 'session_outcome_unknown' }) });
  await c.activate(); await c.openResearch(); await c.prepare(); await c.readHandoff();
  assert.doesNotMatch(renderDiscovery(c.state), /继续准备原会话/);
  await c.handle(event('click', { action: 'prepare-resume' }));
  assert.equal(calls.filter(call => call.key === 'discoveryPrepare').length, 1);
});
test('newly prepared local handoff opens its visible history record and actually reads its state', async () => {
  const { c, calls } = harness(); await c.activate(); await c.openResearch(); await c.prepare();
  await c.handle(event('click', { action: 'close' })); c.state.tab = 'history';
  assert.match(renderDiscovery(c.state), /data-discovery-action="history-status" data-id="handoff-1"/);
  await c.handle(event('click', { action: 'history-status', id: 'handoff-1' }));
  assert.deepEqual(calls.find(call => call.key === 'discoveryHandoff')?.args, ['handoff-1']);
  assert.equal(c.state.drawer?.kind, 'research');
  assert.equal(c.state.researchDrafts[c.state.drawer.key].prepared.handoff_id, 'handoff-1');
});
test('persisted handoff history survives activation and remains separate from quality acceptance', async () => {
  const { c } = harness({ discoveryHandoffs: async () => ({ items: [{ ...prepared, question: '此前研究', theme_id: 'ai', state: 'running' }] }) });
  await c.activate(); c.state.tab = 'history'; const html = renderDiscovery(c.state);
  assert.match(html, /此前研究/); assert.match(html, /质量未核对/); assert.match(html, /#\/fingpt\?session=session-1/);
  assert.doesNotMatch(html, /质量通过|passed/);
});
test('restored history can read and submit its original frozen handoff without preparing another', async () => {
  const { c, calls, navigations } = harness({ discoveryHandoffs: async () => ({ items: [{ ...prepared, question: '此前研究', theme_id: 'ai', materials: [{ id: 'event-1', kind: '已冻结事件归档资料包' }] }] }) });
  await c.activate(); await c.handle(event('click', { action: 'history-status', id: 'handoff-1' }));
  assert.equal(calls.filter(call => call.key === 'discoveryPrepare').length, 0);
  assert.deepEqual(calls.find(call => call.key === 'discoveryHandoff').args, ['handoff-1']);
  assert.equal(navigations.length, 0);
  await c.execute(); assert.deepEqual(navigations, [['fingpt', 'session-1']]);
});
test('saved tracking reads actual schedule and latest run execution independently from quality', async () => {
  const { c } = harness({ discoveryTracks: async () => ({ available: true, items: [{ id: 'track-1', theme_id: 'ai', enabled: true, definition_version: 1, condition: '原核查条件', schedule: { kind: 'weekly', weekday: 4, hour: 9, minute: 15 }, runs: [{ execution_status: 'completed', quality_status: 'incomplete' }] }] }) });
  await c.activate(); await c.openTracking(); const html = renderDiscovery(c.state);
  assert.equal(c.state.trackDrafts[c.state.drawer.key].time, '09:15');
  assert.match(html, /每周五 09:15/); assert.match(html, /执行 completed · 质量 incomplete/); assert.match(html, /暂停跟踪/);
});
test('unavailable tracking cannot enable but an existing enabled task can still be paused', async () => {
  const { c, calls } = harness({ discoveryTracks: async () => ({ available: false, items: [{ id: 'track-1', theme_id: 'ai', enabled: true, definition_version: 1, condition: '核查原件' }] }) });
  await c.activate(); await c.openTracking(); await c.changeTrack(false);
  assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 1);
  await c.changeTrack(true);
  assert.equal(calls.filter(call => call.key === 'discoveryTrackState').length, 1);
});
test('late feed responses cannot replace a newer route generation or navigate off-page', async () => {
  let resolve;
  const { c, navigations } = harness({ discoveryFeed: () => new Promise(done => { resolve = done; }) });
  const task = c.activate(); c.deactivate(); resolve(feed); await task;
  assert.equal(c.state.feed, null); assert.equal(c.state.active, false); assert.equal(navigations.length, 0);
});
test('filter is case insensitive, IME input does not rerender until composition ends', async () => {
  const { c, changes } = harness(); await c.activate(); const before = changes.length;
  assert.equal(filterDiscoveryThemes([theme], 'ai').length, 1);
  assert.equal(filterDiscoveryThemes([theme], 'aI').length, 1);
  await c.handle(event('input', { matches: '[data-discovery-query]', value: '资', isComposing: true }));
  assert.equal(changes.length, before); assert.equal(c.state.query, '资');
  await c.handle(event('compositionend', { matches: '[data-discovery-query]', value: '资本' }));
  assert.equal(changes.length, before + 1);
});
test('filtered fallback research targets the visible theme rather than a hidden selection', async () => {
  const second = { ...theme, id: 'other', name: '债券', title: '利率变化', materials: [{ ...theme.materials[0], id: 'event-2' }] };
  const { c } = harness({ discoveryFeed: async () => ({ ...feed, themes: [theme, second] }) });
  await c.activate(); c.state.query = '债券'; await c.openResearch();
  assert.equal(c.state.researchDrafts[c.state.drawer.key].theme_id, 'other');
});
test('render preserves stale/errors/unknown times and never turns source claims into quality success', async () => {
  const { c } = harness(); await c.activate();
  c.state.feed.stale = true; c.state.error = '上游暂不可用';
  const html = renderDiscovery(c.state);
  assert.match(html, /上次保存的资料/); assert.match(html, /上游暂不可用/); assert.match(html, /时间待核实/);
  assert.match(html, /来源归纳 · 非质量结论/); assert.match(html, /版本 3/);
  assert.doesNotMatch(html, /质量已通过|Tweaks|preview-events|样例资料/);
});
test('identical source name and title render once in sidebar while preserving change context', async () => {
  const repeated = '来源事件同名标题';
  const { c } = harness({ discoveryFeed: async () => ({ ...feed, themes: [{ ...theme, name: repeated, title: repeated, change: '本次新增归档报道', category: '来源原分类' }] }) });
  await c.activate(); const html = renderDiscovery(c.state);
  const sidebar = html.slice(html.indexOf('<aside class="d-theme-column"'), html.indexOf('</aside>'));
  assert.equal(sidebar.split(repeated).length - 1, 1);
  assert.ok(sidebar.includes('本次新增归档报道'));
  const kicker = html.slice(html.indexOf('<div class="d-hero-kicker"'), html.indexOf('</div><h2>'));
  assert.ok(kicker.includes('来源原分类')); assert.equal(kicker.includes(repeated), false);
});
test('unsafe third-party HTML and links remain escaped and drawer tabs have keyboard semantics', async () => {
  const { c } = harness({ discoveryFeed: async () => ({ ...feed, themes: [{ ...theme, title: '<img src=x onerror=alert(1)>', materials: [{ ...theme.materials[0], url: 'javascript:alert(1)', title: '<script>bad</script>' }] }] }) });
  await c.activate(); await c.openResearch(); const html = renderDiscovery(c.state);
  assert.doesNotMatch(html, /<script>bad|<img src=x|href="javascript:/); assert.match(html, /&lt;script&gt;bad/);
  c.state.drawer = null; const key = event('keydown', { matches: '[data-discovery-action="tab"]', key: 'ArrowRight' });
  await c.handle(key); assert.equal(c.state.tab, 'counter'); assert.equal(key.prevented, true);
});
test('discovery mutations use explicit-user-action headers and reads never resend writes', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (path, options) => { calls.push({ path, options }); return { ok: true, status: 200, json: async () => ({}) }; }, logger: () => {} });
  await api.discoveryFeed('short', false); await api.discoveryPrepare({ request_id: 'one' }); await api.discoveryExecute('handoff', { request_id: 'two' });
  await api.discoveryTrackSave({ request_id: 'three' }); await api.discoveryTrackState('track', true, { expected_version: 1 }); await api.discoveryRequest('one');
  assert.equal(calls[0].path, '/api/research/discovery/feed?horizon=short&refresh=false');
  for (const call of calls.slice(1, 5)) assert.equal(call.options.headers['X-Research-User-Action'], '?1');
  assert.equal(calls.at(-1).options.method, 'GET');
  await api.discoverySelection('feed id', 'theme/id', 'long');
  assert.equal(calls.at(-1).path, '/api/research/discovery/selection?feed_id=feed%20id&theme_id=theme%2Fid&horizon=long');
  assert.equal(calls.at(-1).options.method, 'GET');
  assert.equal(calls.at(-1).options.headers['X-Research-User-Action'], undefined);
});
