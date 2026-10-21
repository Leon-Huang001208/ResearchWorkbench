/** Offline, clearly labelled browser fixtures. Never invokes supplier/model APIs. */
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { readFile, appendFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

export async function startFixture(project, output) {
  const original = process.env.RWB_ALPHAFOUNDRY_WEB_ROOT || '/Users/leon/Desktop/AlphaFoundry/app/web';
  const sources = { template: 'templates/index.html', style: 'static/style.css', asset: 'static/js/asset.js', core: 'static/js/core.js' };
  const text = Object.fromEntries(await Promise.all(Object.entries(sources).map(async ([key, file]) => [key, await readFile(path.join(original, file), 'utf8')])));
  const hashes = Object.fromEntries(Object.entries(text).map(([key, value]) => [sources[key], createHash('sha256').update(value).digest('hex')]));
  const migratedFiles = ['asset-chart.mjs', 'asset-indicators.mjs', 'asset-projection.mjs', 'asset-workspace.mjs', 'asset-controller.mjs', 'asset-news.mjs', 'asset-chart.css', 'asset-workspace.css', 'app.mjs', 'styles.css', 'index.html', 'vendor/echarts-5.5.0.min.js', 'vendor/chart-4.4.7.umd.js'];
  const migratedSourceHashes = Object.fromEntries(await Promise.all(migratedFiles.map(async file => [file, createHash('sha256').update(await readFile(path.join(project, 'app/research_web/ui', file))).digest('hex')])));
  const history = Array.from({ length: 320 }, (_, i) => { const close = +(110 + i * .13 + Math.sin(i / 9) * 7).toFixed(2); return { date: new Date(Date.UTC(2025, 8, 1 + Math.round(i * 365 / 319))).toISOString().slice(0, 10), open: close - .7, high: close + 2, low: close - 2, close, volume: i ? 100000 + (i % 31) * 1234 : 0, amount: close * 100000, turnover_rate_pct: 1.2 }; });
  const sid = '11111111-1111-4111-8111-111111111111';
  const rows = { history, overview: [{ date: history.at(-1).date, asset: '600519.SH', name: '离线测试资产 A · 非真实行情', price: 160.75, yclose: 159, volume: 100000, amount: 16075000, turnover_rate_pct: 1.2, open: 160, high: 162, low: 159 }], valuation: [{ date: history.at(-1).date, price: 160.75, total_shares: 1000000, pe_ttm: 12, pb_mrq: 2 }], financials: [{ report_period: '2026-06-30', revenue: 0, net_profit: null, roe: 12.5, gross_margin: 25.5 }, { report_period: '2025-12-31', revenue: 200000, net_profit: 1200 }], activity: [{ date: history.at(-1).date, main_net: 0, north_bound_shares: 1000 }], margin: [{ date: history.at(-1).date, margin_balance: 10000, short_balance: 0 }], holders: [{ report_period: '2026-06-30', holder_count: 1000, top10_pct: 35 }], research: [], shareholders: [], industry: [], events: [], macro: [] };
  const observation = { id: '22222222-2222-4222-8222-222222222222', session_id: sid, asset: '600519.SH', asset_type: 'stock', source: 'auto', status: 'complete', request_parameters: { start_date: history[0].date, end_date: history.at(-1).date, frequency: 'daily', adjustment: 'qfq' }, dataset_ids: Object.keys(rows).map(name => `${name}-fixture`), blocks: Object.fromEntries(Object.entries(rows).map(([name, items]) => [name, { status: items.length ? 'complete' : 'empty', dataset: { dataset_id: `${name}-fixture`, provider: name === 'valuation' ? 'wind' : 'offline-fixture', as_of: history.at(-1).date, row_count: items.length, frequency: 'daily', adjustment: 'qfq', pagination_complete: true, coverage: { complete: true, full_year: true }, fields: [{ name: 'price', unit: 'currency_per_share', currency: 'CNY' }, { name: 'total_shares', unit: 'shares' }, { name: 'revenue', unit: 'currency', currency: 'CNY' }, { name: 'net_profit', unit: 'currency', currency: 'CNY' }, { name: 'volume', unit: 'shares' }, { name: 'amount', unit: 'currency', currency: 'CNY' }] } }])) };
  const proofPath = process.env.RWB_ASSET_REAL_PROOF || process.env.RWB_ASSET_READBACK_JSON;
  const saved = proofPath ? JSON.parse(await readFile(proofPath, 'utf8')) : null;
  if (saved?.datasets && !saved.rows) saved.rows = Object.fromEntries(Object.entries(saved.datasets).map(([name, data]) => [name, data.items]));
  if (saved) { for (const key of Object.keys(rows)) rows[key] = []; Object.assign(rows, saved.rows); Object.assign(observation, saved.observation); }
  const state = { rows, observation, reads: [], errors: [], refreshes: 0, creates: 0, mode: 'normal', late: false, hashes, migratedSourceHashes, saved: Boolean(saved) };
  const snippet = text.template.slice(text.template.indexOf('<div id="asset-result"'), text.template.indexOf('<!-- Scenario Analysis Section -->')).replace(/<\/section>\s*$/, '');
  const mapped = { canonical_id: observation.asset, basic_info: { symbol: observation.asset, name: rows.overview[0]?.name || '离线测试资产', market_cap: 160750000 }, current_price: 160.75, price_change: 1.75, price_change_pct: 1.1, volume: 100000, amount: 16075000, turnover: 1.2, high_52w: Math.max(...history.map(b => b.high)), low_52w: Math.min(...history.map(b => b.low)), price_bars: history.map(b => ({ ...b, turnover: b.turnover_rate_pct })), financial: { pe_ttm: 12, pb_mrq: 2, roe: 12.5, revenue: 0, net_profit: null, gross_margin: 25.5 }, capital_flow: null, top_10_shareholders: [], industry: null, recent_events: [], macro_sensitivity: null };
  if (process.env.RWB_ALPHAFOUNDRY_GOLDEN_BARS) {
    const goldenText = await readFile(process.env.RWB_ALPHAFOUNDRY_GOLDEN_BARS, 'utf8'); const golden = JSON.parse(goldenText); const bars = golden.bars || golden;
    assert.equal(bars.length, history.length, 'Independent original AF golden must use the same 320 bars');
    mapped.price_bars = history.map((bar, i) => { for (const key of ['date', 'open', 'high', 'low', 'close', 'volume']) assert.equal(bars[i][key], bar[key], `Golden input ${i}/${key}`); return { ...bars[i], turnover: bar.turnover_rate_pct }; });
    state.referenceIndicatorProvenance = { source: process.env.RWB_ALPHAFOUNDRY_GOLDEN_BARS, sha256: createHash('sha256').update(goldenText).digest('hex'), rows: bars.length };
  }
  const referenceInit = `import {renderAssetAnalysisCard,initKLineToolbar} from '/reference/asset.js';document.documentElement.dataset.theme=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';document.querySelector('.asset-agent-committee-card')?.remove();document.querySelector('#asset-result').classList.remove('hidden');const data=await(await fetch('/reference/data.json')).json();renderAssetAnalysisCard(data);initKLineToolbar();window.referenceReady=true;`;
  const mime = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
  const server = http.createServer(async (request, response) => {
    try {
      const url = new URL(request.url, 'http://127.0.0.1'); state.reads.push(`${request.method} ${url.pathname}${url.search}`);
      const send = (value, type = 'application/json') => { response.setHeader('Content-Type', `${type}; charset=utf-8`); response.end(typeof value === 'string' ? value : JSON.stringify(value)); };
      response.setHeader('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; object-src 'none'; frame-ancestors 'none'");
      if (url.pathname === '/reference/') return send(`<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>AlphaFoundry original offline reference</title><link rel="stylesheet" href="/reference/style.css"><style>body{display:block!important;overflow:auto!important;padding:16px;box-sizing:border-box}.fixture-banner{color:#ef4444;font:14px sans-serif;margin:8px 0}#asset-result{max-width:100%;min-width:0}</style><script defer src="/static/vendor/echarts-5.5.0.min.js"></script><script defer src="/static/vendor/chart-4.4.7.umd.js"></script><script type="module" src="/reference/init.mjs"></script></head><body><div class="fixture-banner">离线 fixture · 非真实行情 · 原始 AlphaFoundry 源码参考</div>${snippet}</body></html>`, 'text/html');
      if (url.pathname === '/reference/style.css') return send(text.style, 'text/css');
      if (url.pathname === '/reference/asset.js') return send(text.asset + '\nexport { renderAssetAnalysisCard };\n', 'text/javascript');
      if (url.pathname === '/reference/core.js') return send(text.core, 'text/javascript');
      if (url.pathname === '/reference/init.mjs') return send(referenceInit, 'text/javascript');
      if (url.pathname === '/reference/data.json') return send(mapped);
      if (url.pathname.startsWith('/api/research/')) {
        let data;
        if (request.method === 'POST') {
          assert.ok(request.headers['idempotency-key']);
          if (url.pathname.endsWith('/assets/observations')) { let body = ''; for await (const chunk of request) body += chunk; const payload = JSON.parse(body); state.creates++; data = { ...observation, asset: payload.asset, asset_type: payload.asset_type }; }
          else { assert.match(url.pathname, /\/assets\/observations\/[^/]+\/blocks\/[^/]+\/refresh$/); state.refreshes++; data = observation; }
        } else if (url.pathname.endsWith('/assets/observations')) {
          data = { items: [{ ...observation, blocks: Object.fromEntries(Object.entries(observation.blocks).map(([name, block]) => [name, { ...block, status: state.mode === 'empty' && name === 'history' ? 'empty' : state.mode === 'partial' && name === 'financials' ? 'partial' : block.status, failure_code: state.mode === 'partial' && name === 'financials' ? 'fixture_partial_snapshot' : undefined }])) }] };
        } else if (url.pathname.includes('/datasets/')) { const id = url.pathname.split('/datasets/')[1].split('/')[0]; const name = Object.keys(observation.blocks).find(key => observation.blocks[key].dataset?.dataset_id === id); const items = state.mode === 'empty' && name === 'history' ? [] : rows[name] || []; data = { items: items.slice(Number(url.searchParams.get('offset')), Number(url.searchParams.get('offset')) + Number(url.searchParams.get('limit'))) }; }
        else if (url.pathname.includes('/intel/news') || url.pathname.includes('/intel/announcements')) { const code = url.searchParams.get('code'); await new Promise(resolve => setTimeout(resolve, state.late && code === '600519.SH' ? 700 : 40)); data = Array.from({ length: 25 }, (_, i) => ({ title: `隔离资讯 ${code} ${i + 1}`, content: '离线正文 <script>不可执行</script>', source: 'fixture', date: history.at(-1).date, url: 'https://example.com/fixture' })); }
        else if (url.pathname.endsWith('/runtime')) data = { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture', version: 'fixture', mode: 'native' };
        else if (url.pathname.endsWith('/models')) data = { groups: [], failures: [] };
        else if (url.pathname.endsWith('/data/catalog')) data = { capabilities: [], sources: [] };
        else if (url.pathname.endsWith('/watchlists')) data = { items: [{ id: 'watch-fixture', name: '隔离自选', items: [{ asset: observation.asset, asset_type: 'stock', name: '测试资产 A' }, { asset: '603986.SH', asset_type: 'stock', name: '测试资产 B' }] }] };
        else if (url.pathname.endsWith('/events')) { response.setHeader('Content-Type', 'text/event-stream'); response.end('event: connected\ndata: {}\n\n'); return; }
        else data = { items: [] };
        return send(data);
      }
      if (url.pathname === '/favicon.ico') { response.statusCode = 204; return response.end(); }
      const ui = path.join(project, 'app/research_web/ui'); const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, ''); const filename = path.resolve(ui, relative); assert.ok(filename.startsWith(ui + path.sep));
      const type = mime[path.extname(filename)] || 'application/octet-stream';
      response.setHeader('Content-Type', type); response.end(await readFile(filename));
    } catch (error) { state.errors.push(error.message); await appendFile(path.join(output, 'server.jsonl'), JSON.stringify({ event: 'fixture_error', code: error.code || error.name, message: error.message }) + '\n'); response.statusCode = 500; response.end('fixture error'); }
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  return { state, origin: `http://127.0.0.1:${server.address().port}`, verifySourceUnchanged: async () => { for (const file of migratedFiles) assert.equal(createHash('sha256').update(await readFile(path.join(project, 'app/research_web/ui', file))).digest('hex'), migratedSourceHashes[file], `Product source changed during browser run: ${file}`); }, close: () => new Promise(resolve => server.close(resolve)) };
}
