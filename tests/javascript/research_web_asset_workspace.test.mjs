import assert from 'node:assert/strict';
import test from 'node:test';
import { parseRoute, legacyRouteTarget } from '../../app/research_web/ui/core.mjs';
import { assetHref, selectAssetObservation } from '../../app/research_web/ui/asset-navigation.mjs';
import { createAssetNewsController, renderAssetNews } from '../../app/research_web/ui/asset-news.mjs';
import { createAssetWorkspaceController } from '../../app/research_web/ui/asset-controller.mjs';
import { renderAssetWorkspace, readAssetObservation } from '../../app/research_web/ui/asset-workspace.mjs';
import { enrichMarketBars } from '../../app/research_web/ui/asset-chart.mjs';

const response = data => ({ ok: true, status: 200, json: async () => data });
test('CJPY original date, name and volume fields remain readable without guessing units', () => {
  const row = { 代码: 'SH603986', 简称: '兆易创新', 时间: '2026-10-20', open: 10, high: 12, low: 9, close: 11, amount: 2000, vol: 30 };
  const bars = enrichMarketBars([row]); assert.equal(bars.length, 1); assert.equal(bars[0].date, '2026-10-20'); assert.equal(bars[0].volume, 30);
  const html = renderAssetWorkspace({ observation: { asset: '603986.SH', asset_type: 'stock', blocks: { overview: { status: 'complete', dataset: { provider: 'tinysoft', retrieved_at: '2026-10-21T08:00:00Z' } } } }, rows: { overview: [row], history: [row] } });
  assert.match(html, /兆易创新/); assert.match(html, /数据日[^<]*2026-10-20/); assert.match(html, /成交量<\/dt><dd>30<\/dd>/);
});
test('current quote changes use the same snapshot and never borrow historical trading fields', () => {
  const html = renderAssetWorkspace({ observation: { asset: '603986.SH', asset_type: 'stock', blocks: {} }, rows: { overview: [{ close: 11, yclose: 10, amount: 3000, 时间: '2026-10-21' }], history: [{ date: '2026-10-20', open: 9, high: 12, low: 8, close: 10 }] } });
  assert.match(html, /较昨收计算[^<]*10%/);
  const quote = html.slice(html.indexOf('<aside class="asset-quote-panel"'));
  assert.match(quote, /开盘<\/dt><dd>—<\/dd>/);
  assert.match(quote, /交易数据日[^<]*2026-10-21/);
});
test('asset page uses research topics, source-aware metrics and complete financial records', () => {
  const html = renderAssetWorkspace({ route: { asset: '600519.SH', assetType: 'stock', assetView: 'financials' }, observation: { asset: '600519.SH', asset_type: 'stock', blocks: { financials: { status: 'complete', dataset: { provider: 'wind', as_of: '2026-06-30', fields: [{ name: 'revenue', unit: 'currency', currency: 'CNY' }] } } } }, rows: { financials: [{ report_period: '2026-06-30', revenue: 0, net_profit: null }] } });
  for (const label of ['资金与两融', '股东', '新闻', '公告', '资料', '营业收入', '2026-06-30', 'CNY']) assert.match(html, new RegExp(label));
  assert.doesNotMatch(html, /52周高|十大股东明细|THEME EXPOSURE/);
  assert.match(html, /data-asset-block-refresh="financials"/);
  assert.match(html, /data-asset-personal/);
});
test('renderer refuses a previous asset snapshot and news during a route transition', () => {
  const html = renderAssetWorkspace({ route: { asset: '603986.SH', assetType: 'stock', assetView: 'news' }, observation: { asset: '600519.SH', asset_type: 'stock', session_id: 'wrong-session', dataset_ids: ['wrong-data'], blocks: {} }, rows: { overview: [{ name: '旧资产名称', price: 999999 }] }, news: { asset: '600519.SH', assetType: 'stock', view: 'news', status: 'complete', items: [{ title: '旧资产新闻' }] } });
  assert.doesNotMatch(html, /旧资产名称|旧资产新闻|wrong-session|wrong-data|999,999/);
  assert.match(html, /603986.SH/);
});
test('asset topic routes preserve identity and migrate only the two legacy columns', () => {
  const hash = assetHref('600519.SH', 'stock', 'financials');
  assert.equal(parseRoute(hash).asset, '600519.SH');
  assert.equal(parseRoute(hash).assetView, 'financials');
  assert.equal(parseRoute(hash).assetType, 'stock');
  assert.equal(legacyRouteTarget('#/intel/news?code=600519'), '#/workbench/assets?view=news&asset=600519&asset_type=stock');
  assert.equal(legacyRouteTarget('#/intel/filings'), '#/workbench/assets?view=announcements');
  assert.equal(legacyRouteTarget('#/intel/news/extra'), null);
  assert.equal(parseRoute('#/workbench/assets?asset=%3Cscript%3E&view=unknown').asset, '');
  assert.equal(parseRoute('#/workbench/assets?view=unknown').assetView, 'overview');
});
test('observation selection never borrows another security or asset type', () => {
  const items = [{ id: 'index', asset: '000001.SH', asset_type: 'index' }, { id: 'stock', asset: '000001.SZ', asset_type: 'stock' }];
  assert.equal(selectAssetObservation(items, { asset: '000001.SZ', assetType: 'stock' }).id, 'stock');
  assert.equal(selectAssetObservation(items, { asset: '000001.SH', assetType: 'stock' }), null);
  assert.equal(selectAssetObservation(items, { asset: '600519.SH', assetType: 'stock' }), null);
});
test('asset news is a lazy read-only query, isolated by code and column', async () => {
  const calls = [];
  const c = createAssetNewsController({ fetcher: async path => { calls.push(path); return response([{ title: '公告', content: '<script>x</script>', url: 'javascript:x' }]); } });
  await c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'overview' });
  assert.equal(calls.length, 0);
  await c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'news' });
  assert.deepEqual(calls, ['/api/research/intel/news?code=600519']);
  assert.match(renderAssetNews(c.state), /&lt;script&gt;/);
  assert.doesNotMatch(renderAssetNews(c.state), /href="javascript:/);
  await c.activate({ asset: '000001.SH', assetType: 'index', assetView: 'announcements' });
  assert.equal(calls.length, 1);
  assert.match(renderAssetNews(c.state), /A 股股票/);
});
test('late news cannot overwrite a different asset and malformed data is not empty success', async () => {
  let resolveOld; let signal;
  const c = createAssetNewsController({ fetcher: async (path, options) => {
    if (path.includes('600519')) { signal = options.signal; return new Promise(resolve => { resolveOld = resolve; }); }
    return response([{ title: '新资产' }]);
  } });
  const old = c.activate({ asset: '600519.SH', assetType: 'stock', assetView: 'news' });
  await c.activate({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.ok(signal.aborted);
  resolveOld(response([{ title: '旧资产' }])); await old;
  assert.match(renderAssetNews(c.state), /新资产/);
  assert.doesNotMatch(renderAssetNews(c.state), /旧资产/);
  const bad = createAssetNewsController({ fetcher: async () => response({ unexpected: [] }) });
  await bad.activate({ asset: '603986.SH', assetType: 'stock', assetView: 'news' });
  assert.equal(bad.state.status, 'error');
});
test('workspace reads all snapshot pages and marks row failures without losing personal data', async () => {
  const calls = [];
  const observation = { id: 'o', session_id: 's', asset: '600519.SH', asset_type: 'stock', blocks: { history: { status: 'complete', dataset: { dataset_id: 'd', row_count: 201 } }, financials: { status: 'complete', dataset: { dataset_id: 'bad', row_count: 1 } } } };
  const api = {
    assetObservations: async () => ({ items: [observation] }), watchlists: async () => ({ items: [{ id: 'w' }] }), assetNotes: async () => ({ items: [] }), assetAlerts: async () => ({ items: [] }), assetNotifications: async () => ({ items: [] }),
    datasetRows: async (sid, did, offset) => { calls.push([did, offset]); if (did === 'bad') throw new Error('读取失败'); return { items: Array.from({ length: offset ? 1 : 200 }, (_, i) => ({ date: String(offset + i) })) }; },
  };
  const c = createAssetWorkspaceController({ api });
  await c.load({ asset: '600519.SH', assetType: 'stock', assetView: 'overview' });
  assert.equal(c.state.rows.history.length, 201);
  assert.ok(calls.some(([id, offset]) => id === 'd' && offset === 200));
  assert.equal(c.state.observation.blocks.financials.status, 'error');
  assert.equal(c.state.watchlists.length, 1);
});
