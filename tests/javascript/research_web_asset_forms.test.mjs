import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createAssetForms, windRangeError } from '../../app/research_web/ui/asset-forms.mjs';

function fakeForm(fields = {}) {
  return {
    fields,
    resetCount: 0,
    reset() { this.resetCount += 1; },
  };
}

// The module reads FormData; stub it per test.
function withFormData(fields, body) {
  const original = globalThis.FormData;
  globalThis.FormData = class { get(k) { return fields[k] ?? null; } };
  try { return body(); } finally { globalThis.FormData = original; }
}

test('wind rejects non-daily frequencies', () => {
  assert.match(
    windRangeError({ source: 'wind', frequency: 'minute', start_date: '2026-01-01', end_date: '2026-01-02' }),
    /仅支持不超过 60 个日历日的股票日线/,
  );
});

test('wind accepts exactly 60 calendar days inclusive', () => {
  // 2026-01-01 .. 2026-03-01 is 60 days inclusive.
  assert.equal(
    windRangeError({ source: 'wind', frequency: 'daily', start_date: '2026-01-01', end_date: '2026-03-01' }),
    null,
  );
});

test('wind rejects 61 days', () => {
  assert.match(
    windRangeError({ source: 'wind', frequency: 'daily', start_date: '2026-01-01', end_date: '2026-03-02' }),
    /仅支持不超过 60 个日历日/,
  );
});

test('non-wind sources are never range limited', () => {
  assert.equal(
    windRangeError({ source: 'tinysoft', frequency: 'minute', start_date: '2020-01-01', end_date: '2026-01-01' }),
    null,
  );
});

test('an unparseable date fails closed instead of allowing the request', () => {
  assert.match(
    windRangeError({ source: 'wind', frequency: 'daily', start_date: 'not-a-date', end_date: '2026-03-01' }),
    /仅支持不超过 60 个日历日/,
  );
});

function harness({ createResult = { status: 'complete', id: 'r1' }, throwOn = null } = {}) {
  const s = {
    success: '', error: '', busy: [], renders: 0, refreshes: 0, polls: 0,
    url: '', cancelled: 0, historyStarted: null, newsActivated: 0, logged: [],
  };
  const assetState = { observation: null, rows: { overview: [{ name: '平安银行' }] }, observations: [], watchlists: [], notes: [], alerts: [], notifications: [] };
  const api = {
    createAssetObservation: async () => { if (throwOn === 'create') throw new Error('创建失败'); return createResult; },
    addWatchlistItem: async () => { if (throwOn === 'watch') throw Object.assign(new Error('自选失败'), { code: 'x' }); return {}; },
    createAssetNote: async () => { if (throwOn === 'note') throw new Error('笔记失败'); return {}; },
    createAssetAlert: async () => { if (throwOn === 'alert') throw new Error('提醒失败'); return {}; },
  };
  const forms = createAssetForms({
    api, assetState,
    assetWorkspace: { cancel: () => { s.cancelled += 1; }, startHistory: (...args) => { s.historyStarted = args; } },
    assetNews: { activate: async () => { s.newsActivated += 1; } },
    getState: () => ({ route: { page: 'assets' } }),
    isBusy: () => false,
    setBusy: v => { s.busy.push(v); },
    owner: () => () => true,
    generation: () => 1,
    pollObservation: async record => { s.polls += 1; return record; },
    loadWorkspace: async () => { s.refreshes += 1; },
    render: () => { s.renders += 1; },
    setSuccess: v => { s.success = v; },
    setError: v => { s.error = v; },
    replaceUrl: url => { s.url = url; },
    assetHref: (a, t, v) => `#/${t}/${a}/${v}`,
    readObservation: () => ({ asset: '000001.SZ', asset_type: 'stock', source: 'tinysoft', frequency: 'daily', adjustment: 'none', start_date: '2026-01-01', end_date: '2026-02-01' }),
    newId: () => 'fixed',
    log: (...args) => s.logged.push(args),
  });
  return { forms, s, assetState };
}

test('observation cancels prior work, sets busy and settles it in finally', async () => {
  const h = harness();
  await withFormData({}, () => h.forms.createObservation(fakeForm()));
  assert.equal(h.s.cancelled, 1, 'a new run cancels the previous one');
  assert.deepEqual(h.s.busy, [true, false]);
  assert.equal(h.s.success, '资产数据查询已结束，请查看各区块的来源与覆盖。');
  assert.equal(h.s.refreshes, 1);
});

test('a running observation tells the user not to resubmit', async () => {
  const h = harness({ createResult: { status: 'running', id: 'r1' } });
  await withFormData({}, () => h.forms.createObservation(fakeForm()));
  assert.match(h.s.success, /未重新提交/);
});

test('a partial observation asks the user to read the block statuses', async () => {
  const h = harness({ createResult: { status: 'partial', id: 'r1' } });
  await withFormData({}, () => h.forms.createObservation(fakeForm()));
  assert.match(h.s.success, /部分区块有缺失或失败/);
});

test('a wind range violation is rejected before any API call', async () => {
  const h = harness();
  h.forms.readObservation = null; // ensure the real reader is what runs
  const custom = createAssetForms({
    api: { createAssetObservation: () => { throw new Error('must not run'); } },
    assetState: h.assetState,
    assetWorkspace: { cancel() {}, startHistory() {} },
    assetNews: { activate() {} },
    getState: () => ({ route: {} }),
    isBusy: () => false, setBusy() {}, owner: () => () => true, generation: () => 1,
    pollObservation: async r => r, loadWorkspace: async () => {}, render() {},
    setSuccess() {}, setError: v => { h.s.error = v; },
    replaceUrl() {}, assetHref: () => '#', newId: () => 'x',
    readObservation: () => ({ asset: '000001.SZ', asset_type: 'stock', source: 'wind', frequency: 'daily', start_date: '2026-01-01', end_date: '2026-06-01' }),
  });
  const outcome = await withFormData({}, () => custom.createObservation(fakeForm()));
  assert.equal(outcome, 'rejected');
  assert.match(h.s.error, /仅支持不超过 60 个日历日/);
});

test('a stale page after create does not touch shared state', async () => {
  const h = harness();
  const stale = createAssetForms({
    api: { createAssetObservation: async () => ({ status: 'complete', id: 'r' }) },
    assetState: h.assetState,
    assetWorkspace: { cancel() {}, startHistory() {} },
    assetNews: { activate() {} },
    getState: () => ({ route: {} }),
    isBusy: () => false, setBusy() {}, owner: () => () => false, generation: () => 1,
    pollObservation: async r => r, loadWorkspace: async () => {}, render() {},
    setSuccess: v => { h.s.success = v; }, setError: v => { h.s.error = v; },
    replaceUrl() {}, assetHref: () => '#', newId: () => 'x',
    readObservation: () => ({ source: 'tinysoft' }),
  });
  const outcome = await withFormData({}, () => stale.createObservation(fakeForm()));
  assert.equal(outcome, 'stale');
  assert.equal(h.s.success, '', 'no success message for an abandoned page');
});

test('watchlist, note and alert share the post-then-refresh shape', async () => {
  const h = harness();
  const form = fakeForm({ watchlist_id: 'w1', asset: '000001.SZ', text: ' hello ', field: 'price', operator: '>', threshold: '10' });

  await withFormData(form.fields, async () => {
    assert.equal(await h.forms.addWatchlistItem(form), 'saved');
    assert.equal(h.s.success, '已加入本地自选列表。');
    assert.equal(h.s.renders >= 1, true);
  });
  await withFormData(form.fields, async () => {
    assert.equal(await h.forms.saveNote(form), 'saved');
    assert.equal(h.s.success, '观察笔记已保存。');
  });
  await withFormData(form.fields, async () => {
    assert.equal(await h.forms.saveAlert(form), 'saved');
    assert.match(h.s.success, /新快照到达时评估/);
  });
  assert.equal(form.resetCount, 3, 'each successful form resets');
});

test('a failed save logs a stable code and does not reset the form', async () => {
  const h = harness({ throwOn: 'watch' });
  const form = fakeForm({ watchlist_id: 'w1', asset: '000001.SZ' });
  await withFormData(form.fields, () => h.forms.addWatchlistItem(form));
  assert.equal(h.s.error, '自选失败');
  assert.equal(form.resetCount, 0, 'failed submissions keep their input');
  assert.deepEqual(h.s.logged.at(-1), ['asset_watchlist_update_failed', { code: 'x' }]);
});
