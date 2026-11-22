import test from 'node:test';
import assert from 'node:assert/strict';
import { createAssetSearchController, renderAssetSearch, normalizeAssetSearch } from '../../app/research_web/ui/asset-search.mjs';

const row = (asset = '603986.SH', name = '兆易创新') => ({ asset, name, exchange: asset.split('.')[1], asset_type: 'stock' });
const tick = () => new Promise(resolve => setTimeout(resolve, 0));
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done; }); return { promise, resolve }; };

test('asset search normalizes full-width text without losing leading zeroes', () => {
  assert.equal(normalizeAssetSearch(' ０００００１ '), '000001');
  assert.equal(normalizeAssetSearch(' ZYCX '), 'zycx');
  assert.equal(normalizeAssetSearch('兆易创新'), '兆易创新');
  assert.equal(normalizeAssetSearch('x'.repeat(100)).length, 80);
});

test('asset search renders one accessible search input and escaped candidates', () => {
  const html = renderAssetSearch({ query: 'zycx', open: true, status: 'ready', items: [row('603986.SH', '<script>')], selected: 0 });
  assert.match(html, /role="combobox"/);
  assert.match(html, /role="listbox"/);
  assert.match(html, /role="option"/);
  assert.match(html, /603986.SH/);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<select|<script>/);
});

test('directory warm-up and actual empty results have different messages', () => {
  assert.match(renderAssetSearch({ query: 'zycx', open: true, status: 'loading', items: [] }), /目录|准备/);
  assert.doesNotMatch(renderAssetSearch({ query: 'zycx', open: true, status: 'loading', items: [] }), /没有匹配/);
  assert.match(renderAssetSearch({ query: 'zycx', open: true, status: 'empty', items: [] }), /没有匹配/);
  assert.match(renderAssetSearch({ query: 'zycx', open: true, status: 'error', error: '目录读取失败', items: [] }), /目录读取失败/);
});

test('late search responses cannot overwrite a newer query', async () => {
  const first = deferred(); const second = deferred(); const calls = [];
  const c = createAssetSearchController({ api: { searchAssets(q, opts) { calls.push([q, opts]); return calls.length === 1 ? first.promise : second.promise; } }, debounceMs: 0 });
  const one = c.search('gzmt'); const two = c.search('zycx');
  second.resolve({ status: 'ready', items: [row()], total_count: 6000 }); await two;
  first.resolve({ status: 'ready', items: [row('600519.SH', '贵州茅台')] }); await one;
  assert.equal(c.state.query, 'zycx'); assert.equal(c.state.items[0].asset, '603986.SH');
  assert.equal(calls[0][1].signal.aborted, true); c.dispose();
});

test('keyboard selection uses matching candidates and Escape closes the list', async () => {
  let chosen; const c = createAssetSearchController({ api: { searchAssets: async () => ({ status: 'ready', items: [row(), row('600519.SH', '贵州茅台')] }) }, onSelect: item => { chosen = item; } });
  await c.search('x'); c.key('ArrowDown'); c.key('Enter');
  assert.equal(chosen.asset, '600519.SH');
  c.key('Escape'); assert.equal(c.state.open, false); c.dispose();
});

test('switching account invalidates pending results and selection', async () => {
  let owner = 'one'; let chosen = false; const pending = deferred();
  const c = createAssetSearchController({ api: { searchAssets: () => pending.promise }, account: () => owner, onSelect: () => { chosen = true; } });
  const load = c.search('zycx'); owner = 'two'; pending.resolve({ status: 'ready', items: [row()] }); await load;
  c.key('Enter'); assert.equal(chosen, false); assert.equal(c.state.items.length, 0); c.dispose();
});

test('warm directory polling retains bounded old results then settles', async () => {
  let calls = 0;
  const c = createAssetSearchController({ api: { searchAssets: async () => ++calls === 1 ? { status: 'stale', items: [row()], total_count: 6000 } : { status: 'ready', items: [row()], total_count: 6001 } }, pollMs: 0 });
  await c.search('zycx'); await tick(); await tick();
  assert.equal(c.state.items[0].asset, '603986.SH'); assert.equal(c.state.status, 'ready'); assert.equal(c.state.totalCount, 6001); c.dispose();
});

test('nonstock and malformed candidates are never selectable', async () => {
  const c = createAssetSearchController({ api: { searchAssets: async () => ({ status: 'ready', items: [{ ...row(), asset_type: 'index' }, row('javascript:alert(1)'), row()] }) } });
  await c.search('z'); assert.deepEqual(c.state.items.map(item => item.asset), ['603986.SH']); c.dispose();
});

test('disposed searches cannot publish state or start further polling', async () => {
  const pending = deferred(); let calls = 0;
  const c = createAssetSearchController({ api: { searchAssets: () => { calls++; return pending.promise; } } });
  const load = c.search('zycx'); c.dispose(); pending.resolve({ status: 'loading', items: [] }); await load; await tick();
  assert.equal(c.state.items.length, 0); assert.equal(calls, 1);
});
