import test from 'node:test';
import assert from 'node:assert/strict';
import { createEventLab, renderEventLab } from '../../app/research_web/ui/event-lab.mjs';

test('untrusted event text is escaped and incomplete scores remain unavailable', () => {
  const html = renderEventLab({ view: 'timeline', data: { items: [{ id: 'a', revision: 1, payload: { title: '<img onerror=alert(1)>', admission: 'candidate' } }] }, filters: {}, selected: [], profiles: [], sources: [], loading: false });
  assert.ok(html.includes('&lt;img'));
  assert.ok(!html.includes('<img onerror'));
  const scores = renderEventLab({ view: 'scores', data: { items: [] }, filters: {}, profiles: [], selected: [], sources: [], loading: false });
  assert.ok(scores.includes('待验证'));
  assert.ok(!scores.includes('减仓'));
});

test('stale reads cannot replace the active tab and reads do not carry write authority', async () => {
  const pending = [];
  const lab = createEventLab({ request: (path, options) => new Promise(resolve => pending.push({ path, options, resolve })) });
  const first = lab.activate('timeline');
  const second = lab.activate('studies');
  pending[1].resolve({ items: [{ id: 'new' }] });
  await second;
  pending[0].resolve({ items: [{ id: 'old' }] });
  await first;
  assert.equal(lab.state.view, 'studies');
  assert.equal(lab.state.data.items[0].id, 'new');
  assert.equal(pending[0].options?.method || 'GET', 'GET');
});

test('failed writes reuse idempotency only on explicit retry and concurrent clicks do not duplicate', async () => {
  const calls = [];
  let reject;
  const lab = createEventLab({ request: async (path, options) => {
    if (options?.method === 'POST') { calls.push(options); return new Promise((_, fail) => { reject = fail; }); }
    return { items: [] };
  }, makeKey: () => 'opaque-request-key' });
  const first = lab.write('/events/confirm', { events: [] });
  await lab.write('/events/confirm', { events: [] });
  assert.equal(calls.length, 1);
  reject(new Error('network unknown'));
  await first;
  assert.ok(lab.state.error.includes('network unknown'));
  const second = lab.write('/events/confirm', { events: [] });
  assert.equal(calls[0].key, calls[1].key);
  assert.equal(calls[1].userAction, true);
  reject(new Error('unknown again'));
  await second;
});

test('late write acknowledgements cannot replace the next view or reload it', async () => {
  let finish;
  const reads = [];
  const lab = createEventLab({ request: (path, options) => {
    if (options.method === 'POST') return new Promise(resolve => { finish = resolve; });
    reads.push(path); return Promise.resolve({ items: [] });
  }, makeKey: () => 'write-view-boundary' });
  await lab.activate('timeline');
  const writing = lab.write('/events/freeze', { events: [] });
  await lab.activate('studies');
  finish({ id: 'old-freeze' }); await writing;
  assert.equal(lab.state.view, 'studies');
  assert.equal(lab.state.detail, null);
  assert.equal(reads.filter(path => path === '/event-studies').length, 1);
});

test('score history unwraps the actual service result and decisions are not study history', () => {
  const html = renderEventLab({ view: 'scores', filters: {}, selected: [], sources: [], data: { items: [{ id: 'a', payload: { request: {}, result: { index_id: 'SSE', status: 'VALIDATED', research_score: 61, total_score: null } } }] } });
  assert.match(html, /SSE/); assert.match(html, /历史研究分 61/);
  const detail = renderEventLab({ view: 'timeline', filters: {}, selected: [], sources: [], data: { items: [] }, detailKind: 'event_decisions', detail: { items: [{ id: 'event-only', payload: { title: '确认事件' } }] } });
  assert.doesNotMatch(detail, /data-study-run="event-only"/);
});

test('account changes clear private search and source schedules', async () => {
  let account = 'one'; const paths = [];
  const lab = createEventLab({ getIdentity: () => account, request: async path => { paths.push(path); return { items: [] }; } });
  lab.state.filters.q = 'private-owner-one'; lab.state.sources = [{ id: 'private', enabled: true }];
  account = 'two'; await lab.activate('timeline');
  assert.ok(paths.every(path => !path.includes('private-owner-one')));
  assert.deepEqual(lab.state.sources, []);
});

test('calendar datasets are not offered as price imports and geopolitical filter matches API', () => {
  const state = { view: 'studies', filters: {}, selected: [], sources: [], data: { items: [] }, indices: [], sourceChoices: [
    { kind: 'prices', session_id: 's', dataset_id: 'p', title: '价格资料' },
    { kind: 'calendar', session_id: 's', dataset_id: 'c', title: '日历资料' },
  ] };
  const html = renderEventLab(state), form = html.match(/<form data-event-import>([\s\S]*?)<\/form>/)[1];
  assert.match(form, /价格资料/); assert.doesNotMatch(form, /日历资料/);
  assert.match(renderEventLab({ ...state, view: 'timeline' }), /value="geopolitics"/);
  assert.doesNotMatch(renderEventLab({ ...state, view: 'timeline' }), /value="geopolitical"/);
});

test('reference forms submit actual closed API shapes with explicit idempotent actions', async () => {
  const NativeFormData = globalThis.FormData;
  globalThis.FormData = class {
    constructor(form) { this.pairs = form.pairs; }
    *entries() { yield* this.pairs; }
    [Symbol.iterator]() { return this.entries(); }
    get(key) { return this.pairs.find(([name]) => name === key)?.[1] ?? null; }
    getAll(key) { return this.pairs.filter(([name]) => name === key).map(([, value]) => value); }
    has(key) { return this.pairs.some(([name]) => name === key); }
  };
  try {
    const calls = [], lab = createEventLab({ request: async (path, options) => { if (options.method === 'POST') calls.push({ path, ...options }); return { items: [] }; }, makeKey: () => 'api-shape-key' });
    lab.state.view = 'studies';
    lab.state.bundles = [{ id: 'bundle', revision: 3 }];
    lab.state.sourceChoices = [{ kind: 'calendar', session_id: 's', dataset_id: 'cal' }];
    const submit = async (kind, pairs) => {
      const form = { pairs, matches: selector => selector === `[data-${kind}]` };
      const target = { closest: selector => selector === '.event-lab' ? {} : selector === 'form' ? form : null };
      await lab.handle({ type: 'submit', target, preventDefault() {} });
    };
    await submit('event-calendar', [['calendar_choice', 's/cal'], ['bundle_id', 'bundle']]);
    assert.equal(calls[0].path, '/event-studies/sources/calendar');
    assert.deepEqual(calls[0].body, { session_id: 's', dataset_id: 'cal', bundle_ref: { id: 'bundle', revision: 3 } });
    assert.equal(calls[0].userAction, true); assert.equal(calls[0].key, 'api-shape-key');
    lab.state.data = { items: [{ id: 'study' }] };
    await submit('event-seal', [['study_id', 'study']]);
    assert.equal(calls[1].path, '/event-studies/validation-batches');
    assert.deepEqual(calls[1].body, { study_ids: ['study'] });
  } finally { globalThis.FormData = NativeFormData; }
});

const eventId = 'a'.repeat(32), secondEventId = 'b'.repeat(32);
const knownEvent = { title: '已公布会议', category: 'macro', occurrence_start: '2026-11-04', occurrence_end: null, date_precision: 'day', markets: ['US', 'HK'], lifecycle: 'announced', description: '待核验会议资料' };
const formEvent = (kind, pairs, dataset = {}, type = 'submit') => {
  const form = { pairs, dataset, hasAttribute: attr => attr === `data-${kind}`, matches: selector => selector === `[data-${kind}]` };
  return { type, target: { closest: selector => selector === '.event-lab' ? {} : selector === 'form' ? form : null, matches: () => false }, preventDefault() {} };
};
const clickEvent = dataset => ({ type: 'click', target: { closest: selector => selector === '.event-lab' ? {} : selector === 'button' ? { dataset } : null } });
async function withFormData(run) {
  const NativeFormData = globalThis.FormData;
  globalThis.FormData = class {
    constructor(form) { this.pairs = form.pairs; }
    *entries() { yield* this.pairs; }
    [Symbol.iterator]() { return this.entries(); }
    get(key) { return this.pairs.find(([name]) => name === key)?.[1] ?? null; }
    getAll(key) { return this.pairs.filter(([name]) => name === key).map(([, value]) => value); }
    has(key) { return this.pairs.some(([name]) => name === key); }
  };
  try { await run(); } finally { globalThis.FormData = NativeFormData; }
}

test('merge uses only two to thirty selected current references and explicit intent', async () => withFormData(async () => {
  const calls = [], result = { event: { id: 'c'.repeat(32), revision: 1, payload: { ...knownEvent, title: '合并会议', admission: 'candidate' } } };
  const lab = createEventLab({ makeKey: () => 'timeline-merge-key', request: async (path, options) => { calls.push({ path, ...options }); return options.method === 'GET' ? { items: [] } : result; } });
  const records = [{ id: eventId, revision: 2, payload: knownEvent }, { id: secondEventId, revision: 7, payload: knownEvent }];
  lab.state.data = { items: records }; lab.state.selected = [eventId];
  await lab.handle(formEvent('event-merge', [['title', '合并会议'], ['reason', '重复报道同一会议']]));
  assert.equal(calls.length, 0); assert.match(lab.state.error, /2至30/);
  lab.state.selected = [eventId, secondEventId];
  await lab.handle(formEvent('event-merge', [['title', '合并会议'], ['reason', '重复报道同一会议'], ['trusted', 'true']]));
  assert.deepEqual(calls[0], { path: '/events/merge', method: 'POST', body: { events: [{ id: eventId, revision: 2 }, { id: secondEventId, revision: 7 }], title: '合并会议', reason: '重复报道同一会议', idempotency_key: 'timeline-merge-key' }, key: 'timeline-merge-key', userAction: true });
  assert.equal(lab.state.detailKind, 'event_detail'); assert.equal(lab.state.detail.payload.admission, 'candidate');
  lab.state.data = { items: Array.from({ length: 31 }, (_, id) => ({ id: String(id), revision: 1 })) }; lab.state.selected = lab.state.data.items.map(row => row.id);
  await lab.handle(formEvent('event-merge', [['title', '过多事件'], ['reason', '不提交']]));
  assert.equal(calls.filter(call => call.method === 'POST').length, 1);
}));

test('revision PATCH sends complete closed EventFields and the displayed CAS version', async () => withFormData(async () => {
  const calls = [], lab = createEventLab({ makeKey: () => 'timeline-revise-key', request: async (path, options) => { calls.push({ path, ...options }); return options.method === 'GET' ? { items: [] } : { id: eventId, revision: 5, payload: { ...knownEvent, title: '会议延期', admission: 'candidate' } }; } });
  lab.state.detail = { id: eventId, revision: 4, payload: { ...knownEvent, evidence_refs: ['server-only'], formal_backtest_eligible: true } }; lab.state.detailKind = 'event_detail';
  const values = [['title', '会议延期'], ['category', 'macro'], ['occurrence_start', '2026-11-10'], ['occurrence_end', ''], ['date_precision', 'day'], ['market', 'US'], ['market', 'HK'], ['lifecycle', 'postponed'], ['description', '官方日程待核验'], ['reason', '人工核对新公告'], ['expected_revision', '999'], ['formal_backtest_eligible', 'true']];
  await lab.handle(formEvent('event-revise', values, { eventId, eventRevision: '4', draftKey: `${eventId}:4` }));
  assert.deepEqual(calls[0], { path: `/events/${eventId}`, method: 'PATCH', key: 'timeline-revise-key', userAction: true, body: { title: '会议延期', category: 'macro', occurrence_start: '2026-11-10', occurrence_end: null, date_precision: 'day', markets: ['US', 'HK'], lifecycle: 'postponed', description: '官方日程待核验', expected_revision: 4, reason: '人工核对新公告', idempotency_key: 'timeline-revise-key' } });
  assert.equal(lab.state.detail.revision, 5); assert.equal(lab.state.detailKind, 'event_detail');
}));

test('split derives two closed children from known parent fields without source authority', async () => withFormData(async () => {
  const calls = [], lab = createEventLab({ makeKey: () => 'timeline-split-key', request: async (path, options) => { calls.push({ path, ...options }); return options.method === 'GET' ? { items: [] } : { children: [{ id: secondEventId, revision: 1, payload: { ...knownEvent, title: '子会议一' } }] }; } });
  lab.state.detail = { id: eventId, revision: 6, payload: { ...knownEvent, admission: 'confirmed', source_published_at: '1990-01-01', evidence_refs: [{ id: 'source' }], formal_backtest_eligible: true } }; lab.state.detailKind = 'event_detail';
  await lab.handle(formEvent('event-split', [['child_0_title', '子会议一'], ['child_0_occurrence_start', '2026-11-05'], ['child_0_occurrence_end', ''], ['child_1_title', '子会议二'], ['child_1_occurrence_start', '2026-11-06'], ['child_1_occurrence_end', '2026-11-07'], ['reason', '分别讨论不同事项']], { eventId, eventRevision: '6' }));
  assert.deepEqual(calls[0].body, { expected_revision: 6, reason: '分别讨论不同事项', children: [{ ...knownEvent, title: '子会议一', occurrence_start: '2026-11-05' }, { ...knownEvent, title: '子会议二', occurrence_start: '2026-11-06', occurrence_end: '2026-11-07' }], idempotency_key: 'timeline-split-key' });
  assert.equal(calls[0].path, `/events/${eventId}/split`); assert.equal(calls[0].method, 'POST'); assert.equal(calls[0].userAction, true);
  assert.equal(lab.state.detailKind, 'event_split'); assert.match(renderEventLab(lab.state), new RegExp(`data-event-detail="${secondEventId}"`));
}));

test('CAS conflict retains the scoped draft, never auto-retries and rejects a stale displayed form', async () => withFormData(async () => {
  const calls = [], lab = createEventLab({ makeKey: () => 'timeline-conflict-key', request: async (path, options) => { calls.push({ path, ...options }); throw new Error('event_revision_conflict'); } });
  lab.state.detail = { id: eventId, revision: 4, payload: knownEvent }; lab.state.detailKind = 'event_detail';
  const pairs = [['title', '未保存名称'], ['category', 'macro'], ['occurrence_start', '2026-11-04'], ['date_precision', 'day'], ['market', 'US'], ['lifecycle', 'announced'], ['reason', '等待重新核对']];
  const dataset = { eventId, eventRevision: '4', draftKey: `${eventId}:4` };
  await lab.handle(formEvent('event-revise', pairs, dataset, 'input'));
  await lab.handle(formEvent('event-revise', pairs, dataset));
  assert.equal(calls.length, 1); assert.match(lab.state.error, /event_revision_conflict/); assert.equal(lab.state.detail.revision, 4);
  assert.deepEqual(lab.state.formDrafts[`event-revise:${eventId}:4`], pairs);
  const input = { name: 'title', type: 'text', value: '' }, wrongVersion = { name: 'title', type: 'text', value: '其他版本原值' };
  const restoring = [
    { dataset, elements: [input], hasAttribute: attr => attr === 'data-event-revise' },
    { dataset: { draftKey: `${eventId}:5` }, elements: [wrongVersion], hasAttribute: attr => attr === 'data-event-revise' },
  ];
  lab.restore({ querySelectorAll: () => restoring }); assert.equal(input.value, '未保存名称'); assert.equal(wrongVersion.value, '其他版本原值');
  await lab.handle(formEvent('event-revise', pairs, dataset));
  assert.equal(calls.length, 2); assert.equal(calls[0].key, calls[1].key);
  lab.state.detail.revision = 5;
  await lab.handle(formEvent('event-revise', pairs, dataset));
  assert.equal(calls.length, 2); assert.match(lab.state.error, /不是当前可编辑版本/);
}));

test('event versions read exact revisions, escape text and remain read-only', async () => withFormData(async () => {
  const calls = [], historical = { id: eventId, revision: 2, payload: { ...knownEvent, title: '"><img src=x onerror=alert(1)>', description: '</textarea><script>bad()</script>', revision_reason: '<svg onload=bad()>' } };
  const lab = createEventLab({ request: async (path, options) => { calls.push({ path, ...options }); return path.endsWith('/versions') ? { items: [historical] } : historical; } });
  await lab.handle(clickEvent({ eventVersions: eventId }));
  let html = renderEventLab(lab.state);
  assert.equal(lab.state.detailKind, 'event_versions'); assert.match(html, /事件版本历史/); assert.match(html, /&lt;svg/); assert.doesNotMatch(html, /data-study-run=/);
  await lab.handle(clickEvent({ eventId, eventVersion: '2' }));
  assert.equal(calls[1].path, `/events/${eventId}?revision=2`); assert.equal(calls[1].method, 'GET'); assert.equal(calls[1].userAction, undefined);
  html = renderEventLab(lab.state);
  assert.equal(lab.state.detailKind, 'event_historical'); assert.match(html, /历史只读版本/); assert.match(html, /&lt;img/); assert.match(html, /&lt;script/); assert.doesNotMatch(html, /<img|<script|<svg|<form data-event-revise|<form data-event-split/);
  await lab.handle(formEvent('event-revise', [['title', '恶意历史编辑']], { eventId, eventRevision: '2' }));
  assert.equal(calls.length, 2);
  await lab.handle(clickEvent({ eventLatest: eventId }));
  assert.equal(calls[2].path, `/events/${eventId}`); assert.equal(lab.state.detailKind, 'event_detail');
  html = renderEventLab(lab.state); assert.match(html, /<form data-event-revise/); assert.doesNotMatch(html, /<img|<script|<svg/);
}));

test('a late event version response cannot replace a newer detail or escape the account fence', async () => {
  const pending = []; let account = 'one';
  const lab = createEventLab({ getIdentity: () => account, request: (path, options) => new Promise(resolve => pending.push({ path, options, resolve })) });
  const first = lab.handle(clickEvent({ eventVersions: eventId })), next = lab.handle(clickEvent({ eventDetail: secondEventId }));
  pending[1].resolve({ id: secondEventId, revision: 1, payload: knownEvent }); await next;
  pending[0].resolve({ items: [{ id: eventId, revision: 1, payload: knownEvent }] }); await first;
  assert.equal(lab.state.detail.id, secondEventId); assert.equal(lab.state.detailKind, 'event_detail');
  const oldOwner = lab.handle(clickEvent({ eventVersions: eventId })); account = 'two';
  pending[2].resolve({ items: [{ id: eventId, revision: 2, payload: knownEvent }] }); await oldOwner;
  assert.equal(lab.state.detail.id, secondEventId);
});

test('score selectors omit descriptive and unqualified records and explain empty states', () => {
  const html = renderEventLab({ view: 'scores', data: { items: [] }, choices: { validations: [
    { id: 'descriptive-run', role: 'event_overlay', status: 'DATA_INELIGIBLE', label: 'study_run · SSE' },
    { id: 'too-few-events', role: 'calendar_overlay', status: 'INSUFFICIENT_SAMPLE' },
    { id: 'failed-base', role: 'base_score', status: 'VALIDATION_FAILED' },
    { id: 'unknown-state', role: 'base_score' },
    { id: 'unknown-role', role: 'other', status: 'VALIDATED' },
  ] } });
  for (const excluded of ['descriptive-run', 'too-few-events', 'failed-base', 'unknown-state', 'unknown-role', 'study_run']) assert.ok(!html.includes(excluded));
  assert.match(html, /尚无通过验证的基础评分证书/); assert.match(html, /尚无通过验证的事件／日历修正证书/);
  assert.match(html, /href="#\/simulation\/events"/); assert.match(html, /当前时点、冻结版本和来源资格仍由服务端重新核验/); assert.match(html, /历史研究分不代表生产评分/);
});

test('validated score certificates appear only under their matching role with readable index labels', () => {
  const html = renderEventLab({ view: 'scores', data: { items: [] }, choices: { validations: [
    { id: 'passed-base', revision: 3, role: 'base_score', index_id: 'SSE', status: 'VALIDATED', label: 'study_run · SSE' },
    { id: 'passed-event', revision: 2, role: 'event_overlay', index_id: 'SP500', status: 'VALIDATED' },
    { id: 'passed-calendar', revision: 1, role: 'calendar_overlay', index_id: 'HSI', status: 'VALIDATED' },
  ] } });
  const base = html.match(/<select name="validation_id"[^>]*>([\s\S]*?)<\/select>/)[1];
  const overlays = html.match(/<fieldset><legend>事件／日历修正验证<\/legend>([\s\S]*?)<\/fieldset>/)[1];
  assert.match(base, /value="passed-base"/); assert.match(base, /六维基础评分 · 上证综指 · 版本3/); assert.doesNotMatch(base, /passed-event|passed-calendar/);
  assert.match(overlays, /value="passed-event"/); assert.match(overlays, /重大事件修正 · 标普500/); assert.match(overlays, /value="passed-calendar"/); assert.match(overlays, /日历效应修正 · 恒生指数/); assert.doesNotMatch(overlays, /passed-base/);
  assert.doesNotMatch(html, /study_run|尚无通过验证的/);
});

test('validated score certificate ids and index labels are escaped without rendering raw kind labels', () => {
  const html = renderEventLab({ view: 'scores', data: { items: [] }, indices: [{ id: 'custom', name: '<img src=x onerror=bad()>' }], choices: { validations: [
    { id: '"><script>bad()</script>', revision: 1, role: 'base_score', index_id: 'custom', status: 'VALIDATED', label: 'study_run-unreadable' },
    { id: '"><svg onload=bad()>', revision: 2, role: 'event_overlay', index_id: '<iframe src=bad()>', status: 'VALIDATED' },
  ] } });
  assert.match(html, /&lt;img/); assert.match(html, /&lt;script/); assert.match(html, /&lt;iframe/); assert.match(html, /&lt;svg/);
  assert.doesNotMatch(html, /<script|<img|<svg|<iframe|study_run-unreadable/);
});
