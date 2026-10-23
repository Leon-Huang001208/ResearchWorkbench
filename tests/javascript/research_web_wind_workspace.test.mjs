import assert from 'node:assert/strict';
import test from 'node:test';
import { createAPI } from '../../app/research_web/ui/core.mjs';
import { createAssetWorkspaceController, readAssetDatasetRows } from '../../app/research_web/ui/asset-controller.mjs';
import { renderAssetWorkspace } from '../../app/research_web/ui/asset-workspace.mjs';

const observation = (asset = '603986.SH', dataset = 'old') => ({
  id: '11111111-1111-4111-8111-111111111111', session_id: 'session', asset, asset_type: 'stock',
  blocks: { history: { status: 'complete', dataset: { dataset_id: dataset, row_count: 1, provider: 'tinysoft' } } },
});
const apiFor = (extra = {}) => ({
  assetObservations: async () => ({ items: [observation()] }),
  watchlists: async () => ({ items: [] }), assetNotes: async () => ({ items: [] }),
  assetAlerts: async () => ({ items: [] }), assetNotifications: async () => ({ items: [] }),
  datasetRows: async () => ({ items: [{ date: '2026-10-21', close: 10 }], total: 1 }),
  ...extra,
});

test('frozen datasets over5000 rows read completely and use actual progress offsets', async () => {
  const offsets = [];
  const rows = await readAssetDatasetRows({
    datasetRows: async (_sid, _did, offset, limit) => {
      offsets.push(offset);
      const count = Math.min(limit, 97, 6001 - offset);
      return { items: Array.from({ length: count }, (_, i) => ({ id: offset + i })), total: 6001, offset };
    },
  }, 's', { dataset_id: 'd', row_count: 6001 });
  assert.equal(rows.length, 6001);
  assert.equal(rows.at(-1).id, 6000);
  assert.ok(offsets.some(value => value > 5000));
  assert.equal(new Set(rows.map(row => row.id)).size, 6001);
});

test('frozen pagination fails on zero progress or a changed total instead of claiming complete', async () => {
  for (const response of [{ items: [], total: 5 }, { items: [{ id: 1 }], total: 6 }]) {
    await assert.rejects(readAssetDatasetRows({ datasetRows: async () => response }, 's', { dataset_id: 'd', row_count: 5 }));
  }
});

test('cancelled read cannot consume a late first page or issue subsequent pages', async () => {
  const abort = new AbortController(); let calls = 0;
  await assert.rejects(readAssetDatasetRows({ datasetRows: async () => {
    calls++; abort.abort(); return { items: [{ id: 1 }], total: 6000 };
  } }, 's', { dataset_id: 'd', row_count: 6000 }, { signal: abort.signal }));
  assert.equal(calls, 1);
});

test('Wind page puts original metrics beside the chart and keeps research and menus', () => {
  const html = renderAssetWorkspace({ route: { asset: '603986.SH', assetType: 'stock' } });
  assert.match(html, /asset-wind-grid/);
  assert.match(html, /asset-wind-metrics/);
  assert.ok(html.indexOf('data-asset-chart-slot') < html.indexOf('asset-wind-metrics'));
  for (const label of ['PS-TTM', 'PB', '总股本', '区间最高', '区间最低', '个人研究', '来源与口径', 'data-asset-search-slot', 'asset-more-menu']) assert.ok(html.includes(label), label);
  assert.match(html, /id="asset-tab-financials"[^>]*aria-selected="true"/);
  assert.match(html, /id="financial-panel"/);
  assert.doesNotMatch(html, /asset-tab-overview|asset-topic-overview/);
  for (const marker of ['shareholder-panel', 'industry-panel', 'events-panel', 'macro-panel']) assert.equal(html.includes(marker), false, marker);
  for (const [assetView, markers] of [['financials', ['financial-panel']], ['holders', ['shareholder-panel']], ['materials', ['industry-panel', 'events-panel']]]) {
    const topic = renderAssetWorkspace({ route: { asset: '603986.SH', assetType: 'stock', assetView } });
    for (const marker of markers) assert.ok(topic.includes(marker), `${assetView}: ${marker}`);
    assert.doesNotMatch(topic, /macro-panel/);
  }
  assert.doesNotMatch(html, /MARKET TERMINAL/);
  assert.doesNotMatch(html, /asset-list-drawer" open/);
});

test('history and account panel preference APIs use dedicated compatible paths', async () => {
  const calls = [];
  const api = createAPI({ fetcher: async (url, options) => {
    calls.push([url, options]); return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json' } });
  } });
  await api.startAssetHistory('o', { scope: 'all', adjustment: 'qfq' }, 'key');
  await api.assetHistoryJob('o', 'j'); await api.cancelAssetHistory('o', 'j');
  await api.assetChartPreferences(); await api.saveAssetChartPreferences({ panels: [] });
  assert.match(calls[0][0], /\/assets\/observations\/o\/history-jobs$/);
  assert.equal(calls[0][1].method, 'POST');
  assert.match(calls[1][0], /\/history-jobs\/j$/);
  assert.match(calls[2][0], /\/history-jobs\/j\/cancel$/);
  assert.match(calls[3][0], /\/assets\/chart-preferences$/);
  assert.equal(calls[4][1].method, 'PUT');
});

test('canonical generation preserves old rows until the complete new version is read', async () => {
  let finishPage; let enteredPage;
  const entered = new Promise(resolve => { enteredPage = resolve; });
  const newObservation = observation('603986.SH', 'canonical');
  const controller = createAssetWorkspaceController({ pollIntervalMs: 0, api: apiFor({
    startAssetHistory: async () => ({ id: 'job', status: 'completed', current_dataset: newObservation.blocks.history.dataset }),
    assetObservation: async () => newObservation,
    datasetRows: async (_s, did) => did === 'old' ? { items: [{ date: '2026-10-21', close: 10 }], total: 1 } : (enteredPage(), new Promise(resolve => { finishPage = resolve; })),
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' });
  const pending = controller.startHistory('all', 'hfq'); await entered;
  assert.equal(controller.state.rows.history[0].close, 10);
  assert.equal(controller.state.observation.blocks.history.dataset.dataset_id, 'old');
  finishPage({ items: [{ date: '2026-10-21', close: 50 }], total: 1 }); await pending;
  assert.equal(controller.state.rows.history[0].close, 50);
  assert.equal(controller.state.observation.blocks.history.dataset.dataset_id, 'canonical');
});

test('failed canonical read retains matching old dataset and price basis', async () => {
  const controller = createAssetWorkspaceController({ pollIntervalMs: 0, api: apiFor({
    startAssetHistory: async () => ({ id: 'job', status: 'completed' }),
    assetObservation: async () => observation('603986.SH', 'canonical'),
    datasetRows: async (_s, did) => did === 'old' ? { items: [{ close: 10 }], total: 1 } : Promise.reject(new Error('read failed')),
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); await controller.startHistory('all', 'hfq');
  assert.equal(controller.state.rows.history[0].close, 10);
  assert.equal(controller.state.observation.blocks.history.dataset.dataset_id, 'old');
  assert.ok(controller.state.errors.historyJobs);
});

test('pagination retains partial rows and rejects wrong offsets, excess and malformed records', async () => {
  for (const invalid of [
    { items: [{ id: 2 }], total: 3, offset: 0 },
    { items: Array.from({ length: 201 }, () => ({})), total: 3, offset: 1 },
    { items: [null], total: 3, offset: 1 },
    { items: [], total: 3, offset: 1 },
  ]) {
    await assert.rejects(readAssetDatasetRows({ datasetRows: async (_s, _d, offset) => offset ? invalid : { items: [{ id: 1 }], total: 3, offset } }, 's', { dataset_id: 'd', row_count: 3 }), error => error.partialRows.length === 1 && error.partialRows[0].id === 1);
  }
  for (const row_count of [undefined, null, -1, 1.2, '5']) await assert.rejects(readAssetDatasetRows({}, 's', { dataset_id: 'd', row_count }));
});

test('late history submission cancels the captured previous asset job', async () => {
  let finish; const calls = []; const first = observation(); const second = { ...observation('600519.SH', 'second'), id: 'second-observation' };
  const controller = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [first, second] }),
    startAssetHistory: async () => new Promise(resolve => { finish = resolve; }),
    cancelAssetHistory: async (oid, jid) => { calls.push([oid, jid]); return { id: jid, status: 'cancelled' }; },
  }) });
  await controller.load({ asset: first.asset, assetType: 'stock' });
  const pending = controller.startHistory('all', 'hfq');
  await controller.load({ asset: second.asset, assetType: 'stock' });
  finish({ id: 'old-job', status: 'running' }); await pending;
  assert.deepEqual(calls, [[first.id, 'old-job']]);
  assert.equal(controller.state.observation.id, second.id);
  assert.equal(controller.state.historyJob, null);
});

test('same asset view navigation preserves a running job and stop drains it', async () => {
  let finishPoll; const cancelled = []; let enteredPoll;
  const entered = new Promise(resolve => { enteredPoll = resolve; });
  const controller = createAssetWorkspaceController({ pollIntervalMs: 0, api: apiFor({
    startAssetHistory: async () => ({ id: 'job', status: 'running' }),
    assetHistoryJob: async () => { enteredPoll(); return new Promise(resolve => { finishPoll = resolve; }); },
    cancelAssetHistory: async (oid, jid) => { cancelled.push([oid, jid]); return { id: jid, status: 'draining' }; },
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' });
  const pending = controller.startHistory('all', 'qfq'); await entered;
  await controller.load({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.equal(cancelled.length, 0); assert.equal(controller.state.historyJob.id, 'job');
  await controller.stopHistory(); assert.equal(controller.state.historyJob.status, 'draining');
  finishPoll({ id: 'job', status: 'cancelled' }); await pending;
  assert.equal(cancelled.length, 1); assert.equal(controller.state.rows.history[0].close, 10);
});

test('cancel before a 202 waits for its identity then cancels that job', async () => {
  let finish; const cancelled = [];
  const controller = createAssetWorkspaceController({ api: apiFor({
    startAssetHistory: async () => new Promise(resolve => { finish = resolve; }),
    cancelAssetHistory: async (oid, jid) => { cancelled.push([oid, jid]); return { id: jid, status: 'cancelled' }; },
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' });
  const pending = controller.startHistory(); await controller.stopHistory();
  assert.equal(controller.state.historyJob.status, 'cancelling'); assert.equal(cancelled.length, 0);
  finish({ id: 'job', status: 'queued' }); await pending;
  assert.deepEqual(cancelled, [[observation().id, 'job']]); assert.equal(controller.state.historyJob.status, 'cancelled');
});

test('unknown submission reconciles by its own request key and never retries POST', async () => {
  let key; let submissions = 0; let lists = 0;
  const controller = createAssetWorkspaceController({ api: apiFor({
    startAssetHistory: async (_oid, _body, requestKey) => { submissions++; key = requestKey; throw new Error('network'); },
    assetHistoryJobs: async () => { lists++; return { items: key ? [{ id: 'other', request_key: 'not-ours', status: 'running' }, { id: 'own', request_key: key, status: 'cancelled' }] : [] }; },
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); await controller.startHistory();
  assert.equal(submissions, 1); assert.ok(lists >= 2); assert.equal(controller.state.historyJob.id, 'own');
});

test('unresolved submissions do not blindly retry and cannot cancel someone else', async () => {
  let submissions = 0; let cancels = 0;
  const controller = createAssetWorkspaceController({ api: apiFor({
    startAssetHistory: async () => { submissions++; throw new Error('unknown'); },
    assetHistoryJobs: async () => ({ items: [] }), cancelAssetHistory: async () => { cancels++; },
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); await controller.startHistory(); await controller.startHistory();
  assert.equal(controller.state.historyJob.status, 'unknown'); assert.equal(submissions, 1);
  controller.cancel(); assert.equal(cancels, 0);
});

test('account panel preferences retain order and an empty set across asset navigation', async () => {
  const saved = []; const second = { ...observation('600519.SH'), id: 'second' }; let reads = 0;
  const controller = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [observation(), second] }),
    assetChartPreferences: async () => { reads++; return { panels: ['rsi', 'volume'] }; },
    saveAssetChartPreferences: async body => { saved.push(body.panels); return body; },
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); assert.deepEqual(controller.state.preferences.panels, ['rsi', 'volume']);
  await controller.savePreferences([]); await controller.load({ asset: second.asset, assetType: 'stock' });
  assert.deepEqual(controller.state.preferences.panels, []); assert.deepEqual(saved, [[]]); assert.equal(reads, 1);
  await controller.savePreferences(['rsi', 'rsi']); assert.equal(saved.length, 1); assert.ok(controller.state.errors.preferences);
});

test('a late initial preference read cannot overwrite a newer successful save', async () => {
  let releaseRead;
  const initialRead = new Promise(resolve => { releaseRead = resolve; });
  const controller = createAssetWorkspaceController({ api: apiFor({
    assetChartPreferences: () => initialRead,
    saveAssetChartPreferences: async body => body,
  }) });
  const loading = controller.load({ asset: '603986.SH', assetType: 'stock' });
  await controller.savePreferences(['rsi']);
  releaseRead({ panels: ['volume', 'macd'] });
  await loading;
  assert.deepEqual(controller.state.preferences.panels, ['rsi']);
});

test('a late initial preference error cannot replace a newer successful save state', async () => {
  let rejectRead;
  const initialRead = new Promise((_resolve, reject) => { rejectRead = reject; });
  const controller = createAssetWorkspaceController({ api: apiFor({
    assetChartPreferences: () => initialRead,
    saveAssetChartPreferences: async body => body,
  }) });
  const loading = controller.load({ asset: '603986.SH', assetType: 'stock' });
  await controller.savePreferences(['rsi']);
  rejectRead(new Error('stale initial read failure'));
  await loading;
  assert.deepEqual(controller.state.preferences.panels, ['rsi']);
  assert.equal(controller.state.errors.preferences, undefined);
});

test('a failed account preference save restores the last persisted selection', async () => {
  const controller = createAssetWorkspaceController({ api: apiFor({ saveAssetChartPreferences: async () => { throw new Error('save failed'); } }) });
  await controller.savePreferences(['kdj']);
  assert.deepEqual(controller.state.preferences.panels, ['volume', 'macd']); assert.match(controller.state.errors.preferences, /save failed/);
});

test('queued preference failures cannot roll back to an unpersisted optimistic selection', async () => {
  const controller = createAssetWorkspaceController({ api: apiFor({ saveAssetChartPreferences: async () => { throw new Error('offline'); } }) });
  await Promise.all([controller.savePreferences(['kdj']), controller.savePreferences(['rsi'])]);
  assert.deepEqual(controller.state.preferences.panels, ['volume', 'macd']);
});

test('unknown submission recovered after refresh installs its completed immutable dataset', async () => {
  let key; let recover = false; let installed;
  const completed = new Promise(resolve => { installed = resolve; });
  const canonical = observation('603986.SH', 'canonical');
  const controller = createAssetWorkspaceController({ onChange: () => { if (controller.state.observation?.blocks.history.dataset.dataset_id === 'canonical') installed(); }, api: apiFor({
    startAssetHistory: async (_oid, _body, requestKey) => { key = requestKey; throw new Error('network'); },
    assetHistoryJobs: async () => ({ items: recover ? [{ id: 'job', request_key: key, status: 'completed', current_dataset: canonical.blocks.history.dataset }] : [] }),
    assetObservation: async () => canonical,
    datasetRows: async (_s, did) => ({ items: [{ close: did === 'old' ? 10 : 50 }], total: 1 }),
  }) });
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); await controller.startHistory(); recover = true;
  await controller.load({ asset: '603986.SH', assetType: 'stock' }); await completed;
  assert.equal(controller.state.rows.history[0].close, 50); assert.equal(controller.state.historyJob.id, 'job');
});
