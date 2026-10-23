import assert from 'node:assert/strict';
import test from 'node:test';
import { createAssetWorkspaceController } from '../../app/research_web/ui/asset-controller.mjs';
import { createAPI } from '../../app/research_web/ui/core.mjs';

const observed = asset => ({ id: asset, asset, asset_type: 'stock', session_id: 'session', blocks: { history: { status: 'complete', dataset: { dataset_id: 'history', row_count: 1 } } } });
const apiFor = (extra = {}) => ({ assetObservations: async () => ({ items: [observed('603986.SH')] }), watchlists: async () => ({ items: [] }), assetNotes: async () => ({ items: [] }), assetAlerts: async () => ({ items: [] }), assetNotifications: async () => ({ items: [] }), datasetRows: async () => ({ items: [{ close: 10 }], total: 1 }), ...extra });

for (const quote of [{ date: '2026-10-22' }, { '时间': '2026-10-22T15:00:00' }, { date: '2026-10-22T15:00:00+08:00' }, { as_of: '2026-10-22' }]) test(`a newer quote ${JSON.stringify(quote)} advances a separate full-range history once on entry`, async () => {
  const record = observed('603986.SH'); const jobs = [];
  record.blocks.history.dataset.asset_history = { requested_as_of: '2026-10-21', adjustment: 'qfq', coverage: { full_history: true } };
  record.blocks.overview = { status: 'complete', dataset: { dataset_id: 'quote', row_count: 1 } };
  const c = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [record] }),
    datasetRows: async (_sid, did) => ({ items: [did === 'quote' ? { ...quote, close: 10 } : { date: '2026-10-21', close: 11 }], total: 1 }),
    loadAssetBlock: async () => record,
    startAssetHistory: async (_id, body) => { jobs.push(body); return { id: 'advance', status: 'completed' }; },
  }) });
  await c.activateView({ asset: record.asset, assetType: 'stock', assetView: 'financials' });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(jobs, [{ scope: 'all', adjustment: 'qfq', as_of: '2026-10-22' }]);
  await c.activateView({ asset: record.asset, assetType: 'stock', assetView: 'news' });
  assert.equal(jobs.length, 1); c.cancel();
});

test('view activation loads exactly its blocks while preserving historical rows and no news DataHub request', async () => {
  const calls = [];
  const c = createAssetWorkspaceController({ api: apiFor({ loadAssetBlock: async (id, block, body) => { calls.push([block, body]); return { ...observed(id), blocks: { ...observed(id).blocks, [block]: { status: 'complete', dataset: { dataset_id: block, row_count: 1 } } } }; } }) });
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'financials' });
  assert.deepEqual(calls.map(([block]) => block).sort(), ['financials', 'overview', 'valuation']);
  assert.equal(c.state.rows.history[0].close, 10);
  assert.equal(c.state.rows.financials.length, 1); assert.equal(c.state.rows.valuation.length, 1);
  const history = c.state.rows.history;
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.equal(calls.length, 3);
  assert.equal(c.state.rows.history, history);
  c.cancel();
});

test('a new selected stock creates overview and starts recent unadjusted auto history without manual parameters', async () => {
  const created = []; const jobs = [];
  const c = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [] }),
    createAssetObservation: async body => { created.push(body); return { ...observed(body.asset), blocks: { overview: { status: 'complete' } } }; },
    loadAssetBlock: async (id, block) => ({ ...observed(id), blocks: { [block]: { status: 'complete' } } }),
    startAssetHistory: async (id, body) => { jobs.push([id, body]); return { id: 'job', status: 'completed' }; },
  }) });
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'overview' });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(created[0].sections, ['overview']); assert.equal(created[0].source, 'auto');
  assert.deepEqual(jobs[0][1], { scope: 'recent', adjustment: 'none', source: 'auto' });
  assert.equal(c.state.observation.asset, '603986.SH'); c.cancel();
});

test('cold creation hydrates an already complete overview dataset once instead of mistaking its id for loaded rows', async () => {
  const reads = [];
  const record = { ...observed('603986.SH'), blocks: { overview: { status: 'complete', dataset: { dataset_id: 'overview-frozen', row_count: 1 } }, valuation: { status: 'empty', dataset: { dataset_id: 'empty-frozen', row_count: 0 } } } };
  const c = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [] }),
    createAssetObservation: async () => structuredClone(record),
    loadAssetBlock: async () => structuredClone(record),
    datasetRows: async (_sid, id) => { reads.push(id); return { items: [{ name: '合成新增资产', close: 10 }], total: 1 }; },
    startAssetHistory: async () => ({ id: 'job', status: 'completed' }),
  }) });
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'overview' });
  assert.equal(c.state.rows.overview?.[0]?.name, '合成新增资产');
  assert.deepEqual(c.state.rows.valuation, []);
  await c.loadBlock('overview'); await c.loadBlock('valuation');
  assert.deepEqual(reads, ['overview-frozen']); c.cancel();
});

test('cold topic blocks load before background history instead of waiting for its terminal state', async () => {
  const calls = []; let finished = false;
  const record = { ...observed('603986.SH'), blocks: { overview: { status: 'complete' } } };
  const c = createAssetWorkspaceController({ pollIntervalMs: 1, api: apiFor({
    assetObservations: async () => ({ items: [] }), createAssetObservation: async () => structuredClone(record),
    loadAssetBlock: async (_id, block) => { calls.push(block); return { ...record, blocks: { ...record.blocks, [block]: { status: 'complete' } } }; },
    startAssetHistory: async () => { calls.push('history'); return { id: 'job', status: 'running' }; },
    assetHistoryJob: async () => ({ id: 'job', status: finished ? 'completed' : 'running' }),
    cancelAssetHistory: async () => ({ id: 'job', status: 'cancelled' }),
  }) });
  const pending = c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'financials' });
  try {
    await new Promise(resolve => setTimeout(resolve, 20));
    assert.ok(calls.includes('financials') && calls.includes('valuation'), 'selected topic must not wait for historical completion');
    assert.ok(calls.indexOf('financials') < calls.indexOf('history'));
  } finally { finished = true; await pending; c.cancel(); }
});

test('late block responses after asset switch cannot replace new identity or its rows', async () => {
  let finish; let oldSignal;
  const c = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [observed('603986.SH'), observed('600519.SH')] }),
    loadAssetBlock: async (id, block, body, key, options) => {
      if (id === '603986.SH') { oldSignal = options.signal; return new Promise(resolve => { finish = () => resolve({ ...observed(id), blocks: { [block]: { status: 'complete', dataset: { dataset_id: 'late', row_count: 1 } } } }); }); }
      return { ...observed(id), blocks: {} };
    },
  }) });
  await c.load({ asset: '603986.SH', assetType: 'stock' });
  const pending = c.loadBlock('financials');
  await c.activateView({ asset: '600519.SH', assetType: 'stock', assetView: 'news' });
  finish(); await pending;
  assert.equal(oldSignal.aborted, true); assert.equal(c.state.observation.asset, '600519.SH');
  assert.equal(c.state.rows.financials, undefined); c.cancel();
});

test('directory and block loading API contracts preserve encoded queries and idempotency', async () => {
  const calls = []; const api = createAPI({ fetcher: async (url, options) => { calls.push([url, options]); return new Response('{}', { headers: { 'content-type': 'application/json' } }); } });
  await api.searchAssets('贵州茅台', { limit: 20 }); await api.loadAssetBlock('o', 'industry', { refresh: true }, 'load-industry');
  assert.match(calls[0][0], /assets\/search\?q=%/); assert.match(calls[1][0], /blocks\/industry\/load$/);
  assert.equal(calls[1][1].method, 'POST');
});

test('switching accounts on the same security drops prior rows and ignores late block completion', async () => {
  const previous = globalThis.__RWB_USER_ID__; let finish; let account = 'a';
  globalThis.__RWB_USER_ID__ = account;
  const c = createAssetWorkspaceController({ api: apiFor({
    assetObservations: async () => ({ items: [{ ...observed('603986.SH'), id: `observation-${account}` }] }),
    loadAssetBlock: async (_id, block) => _id === 'observation-a' && block === 'financials' ? new Promise(resolve => { finish = () => resolve({ ...observed('603986.SH'), id: 'observation-a', blocks: { [block]: { status: 'complete', dataset: { dataset_id: 'late', row_count: 1 } } } }); }) : { ...observed('603986.SH'), id: _id },
  }) });
  try {
    await c.load({ asset: '603986.SH', assetType: 'stock' });
    const old = c.loadBlock('financials');
    account = 'b'; globalThis.__RWB_USER_ID__ = account;
    await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
    finish(); await old;
    assert.equal(c.state.observation.id, 'observation-b'); assert.equal(c.state.rows.financials, undefined);
  } finally { c.cancel(); globalThis.__RWB_USER_ID__ = previous; }
});

test('explicit retry freezes source adjustment and cutoff despite current controls', async () => {
  const jobs = []; const c = createAssetWorkspaceController({ api: apiFor({ startAssetHistory: async (_id, body) => { jobs.push(body); return { id: 'retried', status: 'completed' }; } }) });
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'overview' });
  c.state.historyJob = { id: 'failed', status: 'failed', scope: 'recent', source: 'baostock', adjustment: 'none', requested_as_of: '2026-10-20' };
  c.state.rows.overview = [{ date: '2026-10-23' }];
  await c.startHistory('all', 'hfq', 'failed', 'wind');
  assert.deepEqual(jobs, [{ scope: 'recent', adjustment: 'none', source: 'baostock', as_of: '2026-10-20', retry_of: 'failed' }]);
  c.cancel();
});

test('unbound raw2 snapshot never auto-advances with an invented fixed source', async () => {
  const record = observed('603986.SH'); const jobs = [];
  record.source = 'auto';
  record.blocks.history.dataset.asset_history = { canonical_version: 'asset-history-raw-2', requested_as_of: '2026-10-20', adjustment: 'none' };
  record.blocks.overview = { status: 'complete', dataset: { dataset_id: 'quote', row_count: 1 } };
  const c = createAssetWorkspaceController({ api: apiFor({ assetObservations: async () => ({ items: [record] }), loadAssetBlock: async () => record, datasetRows: async (_sid, did) => ({ items: [did === 'quote' ? { date: '2026-10-22', close: 10 } : { date: '2026-10-20', close: 11 }], total: 1 }), startAssetHistory: async (_id, body) => { jobs.push(body); return { id: 'new', status: 'completed' }; } }) });
  await c.activateView({ asset: record.asset, assetType: 'stock', assetView: 'overview' });
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(jobs, []); assert.match(c.state.errors.historyJobs, /来源未知/); c.cancel();
});

test('chip retry preserves the frozen true flag after publishing queued UI state', async () => {
  const jobs = []; const c = createAssetWorkspaceController({ api: apiFor({ startAssetHistory: async (_id, body) => { jobs.push(body); return { id: 'retried', status: 'completed', include_chip_inputs: true }; } }) });
  await c.activateView({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  c.state.historyJob = { id: 'failed-chip', status: 'failed', scope: 'all', source: 'tinysoft', adjustment: 'qfq', requested_as_of: '2026-10-20', include_chip_inputs: true };
  await c.startHistory('recent', 'none', 'failed-chip', 'wind', false);
  assert.deepEqual(jobs, [{ scope: 'all', adjustment: 'qfq', source: 'tinysoft', as_of: '2026-10-20', retry_of: 'failed-chip', include_chip_inputs: true }]);
  c.cancel();
});

test('a readable legacy Tinysoft snapshot automatically upgrades to a separate full chip version once', async () => {
  const record=observed('603986.SH'); const jobs=[];
  Object.assign(record.blocks.history.dataset,{provider:'tinysoft',row_count:10,adjustment:'qfq'});
  const rows=Array.from({length:10},(_,i)=>({date:`2026-10-${String(i+1).padStart(2,'0')}`,open:10,high:12,low:9,close:11,volume:100}));
  const c=createAssetWorkspaceController({api:apiFor({assetObservations:async()=>({items:[record]}),datasetRows:async()=>({items:rows,total:10}),startAssetHistory:async(_id,body)=>{jobs.push(body);return {id:'legacy-upgrade',status:'completed',include_chip_inputs:true}}})});
  await c.activateView({asset:record.asset,assetType:'stock',assetView:'news'}); await new Promise(resolve=>setTimeout(resolve,0));
  assert.deepEqual(jobs,[{scope:'all',adjustment:'qfq',source:'tinysoft',include_chip_inputs:true}]);
  assert.equal(c.state.rows.history.length,10);
  await c.activateView({asset:record.asset,assetType:'stock',assetView:'announcements'});
  assert.equal(jobs.length,1); c.cancel();
});
