/** Isolated browser fixture acceptance. Never contacts a supplier or real research service. */
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { readFile, mkdir, writeFile, appendFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ui = path.join(project, 'app/research_web/ui');
const output = path.join(project, 'logs/asset-observation-20261021');
const log = path.join(project, 'logs/asset-browser.jsonl');
const sid = '11111111-1111-4111-8111-111111111111';
const did = name => `${name}-fixture`;
const history = Array.from({ length: 240 }, (_, i) => ({ date: new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10), open: 100 + i / 4, high: 102 + i / 4, low: 99 + i / 4, close: 101 + i / 4, volume: i === 0 ? 0 : 1000 + i * 10, turnover: 100000 + i * 1000, turnover_rate_pct: i === 1 ? null : 1.2 }));
let rows = { history, overview: [{ asset: '600519.SH', name: '隔离测试资产 A', price: 160.75, change_pct: 1.2, pe_ttm: 12, pb: 2, total_shares: 1000000 }], financials: [{ report_period: '2026-06-30', revenue: 0, net_profit: null }, { report_period: '2025-12-31', revenue: 200000, net_profit: 1200 }], activity: [{ date: '2026-08-28', main_force_inflow: 0 }], margin: [{ date: '2026-08-28', margin_balance: 10000, short_balance: 0 }], holders: [{ report_period: '2026-06-30', holder_count: 1000, top10_pct: 35 }], research: [] };
let observation = { id: '22222222-2222-4222-8222-222222222222', session_id: sid, asset: '600519.SH', asset_type: 'stock', source: 'auto', status: 'complete', dataset_ids: Object.keys(rows).map(did), request_parameters: { start_date: '2026-07-01', end_date: '2026-08-28', frequency: 'daily', adjustment: 'qfq' }, blocks: Object.fromEntries(Object.entries(rows).map(([name, data]) => [name, { status: data.length ? 'complete' : 'empty', dataset: { dataset_id: did(name), provider: 'fixture', as_of: '2026-08-28', row_count: data.length, fields: [{ name: 'revenue', unit: 'currency', currency: 'CNY' }] } }])) };
const liveProof = process.env.RWB_ASSET_READBACK_JSON ? JSON.parse(await readFile(process.env.RWB_ASSET_READBACK_JSON, 'utf8')) : null;
if (liveProof) { observation = liveProof.observation; rows = Object.fromEntries(Object.entries(liveProof.datasets).map(([name, data]) => [name, data.items])); }
const reads = []; let refreshes = 0; let browser;
const mime = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://127.0.0.1'); reads.push(`${request.method} ${url.pathname}${url.search}`);
    if (url.pathname.startsWith('/api/research/')) {
      response.setHeader('Content-Type', 'application/json'); let data;
      if (request.method === 'POST') {
        assert.match(url.pathname, /\/assets\/observations\/[^/]+\/blocks\/[^/]+\/refresh$/); assert.ok(request.headers['idempotency-key']); refreshes++; data = observation;
      } else if (url.pathname.endsWith('/assets/observations')) data = { items: [observation] };
      else if (url.pathname.includes('/datasets/')) { const id = url.pathname.split('/datasets/')[1].split('/')[0]; const name = liveProof ? Object.entries(liveProof.datasets).find(([, data]) => data.metadata.dataset_id === id)?.[0] : id.replace('-fixture', ''); data = { items: (rows[name] || []).slice(Number(url.searchParams.get('offset')), Number(url.searchParams.get('offset')) + Number(url.searchParams.get('limit'))) }; }
      else if (url.pathname.includes('/intel/news') || url.pathname.includes('/intel/announcements')) { await new Promise(resolve => setTimeout(resolve, 200)); data = Array.from({ length: 25 }, (_, i) => ({ title: `隔离资讯 ${url.searchParams.get('code')} ${i + 1}`, content: '这是隔离 fixture 返回的正文。<script>不可执行</script>', source: 'fixture', date: '2026-08-28', url: 'https://example.com/fixture' })); }
      else if (url.pathname.endsWith('/runtime')) data = { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture', version: 'fixture', mode: 'native' };
      else if (url.pathname.endsWith('/models')) data = { groups: [], failures: [] };
      else if (url.pathname.endsWith('/data/catalog')) data = { capabilities: [], sources: [] };
      else if (url.pathname.endsWith('/watchlists') && liveProof) data = { items: [] };
      else if (url.pathname.endsWith('/watchlists')) data = { items: [{ id: 'watch-fixture', name: '隔离自选', items: [{ asset: '600519.SH', asset_type: 'stock', name: '测试资产 A' }, { asset: '603986.SH', asset_type: 'stock', name: '测试资产 B' }] }] };
      else if (url.pathname.endsWith('/events')) { response.setHeader('Content-Type', 'text/event-stream'); response.end('event: connected\ndata: {}\n\n'); return; }
      else data = { items: [] };
      response.end(JSON.stringify(data)); return;
    }
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const filename = path.resolve(ui, relative); if (!filename.startsWith(ui + path.sep)) throw new Error('invalid path');
    response.setHeader('Content-Type', (mime[path.extname(filename)] || 'application/octet-stream') + (['.html', '.mjs', '.js', '.css'].includes(path.extname(filename)) ? '; charset=utf-8' : '')); response.end(await readFile(filename));
  } catch (error) { await appendFile(log, JSON.stringify({ event: 'fixture_request_failed', code: error.code || error.name }) + '\n'); response.statusCode = 500; response.end('fixture error'); }
});
try {
  await mkdir(output, { recursive: true }); await mkdir(path.dirname(log), { recursive: true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const modulePath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
  const { chromium } = await import(pathToFileURL(modulePath).href);
  browser = await chromium.launch({ headless: true, executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  if (liveProof) {
    for (const [width, theme] of [[1920, 'light'], [390, 'dark']]) {
      const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
      const page = await context.newPage(); const errors = [];
      page.on('pageerror', error => errors.push(error.message));
      await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
      await page.goto(`${origin}/#/workbench/assets?view=overview&asset=${encodeURIComponent(liveProof.asset)}&asset_type=stock`);
      await page.locator('.asset-candle').first().waitFor();
      assert.equal(await page.locator('.asset-candle').count(), Math.min(120, rows.history.length));
      assert.ok((await page.locator('.asset-identity').innerText()).includes(rows.overview[0]['简称']));
      assert.equal(await page.locator('.asset-history-readout').getAttribute('data-active-date'), rows.history.at(-1)['时间']);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
      assert.deepEqual(errors, []);
      await page.screenshot({ path: path.join(output, `cjpy-real-${width}-${theme}.png`), fullPage: true });
      await context.close();
    }
  }
  if (!liveProof) for (const theme of ['light', 'dark']) for (const width of [1920, 1200, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 1000 }, colorScheme: theme });
    const page = await context.newPage(); const errors = [];
    page.on('pageerror', error => { errors.push(error.message); console.error(error.stack); });
    page.setDefaultTimeout(10000);
    await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    await page.goto(`${origin}/#/workbench/assets?view=overview&asset=600519.SH&asset_type=stock`);
    try { await page.locator('.asset-history-readout').waitFor(); }
    catch (error) { await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); await writeFile(path.join(output, 'failure.txt'), (await page.locator('body').innerText()) + '\n' + JSON.stringify({ errors, reads }, null, 2)); throw error; }
    assert.match(await page.locator('.asset-identity').innerText(), /隔离测试资产 A/);
    assert.equal(await page.locator('a[href*="intel/news"], a[href*="intel/filings"]').count(), 0);
    const svg = page.locator('[data-asset-chart]'); await svg.focus(); const date = await page.locator('.asset-history-readout').getAttribute('data-active-date');
    await page.keyboard.press('ArrowLeft'); await page.waitForFunction(value => document.querySelector('.asset-history-readout')?.dataset.activeDate !== value, date);
    assert.equal(await page.locator('.asset-price strong').innerText(), '160.75');
    await page.locator('[data-asset-chart-action="overlay-boll"]').click();
    await page.locator('.asset-series.boll.ma20').waitFor();
    assert.equal(await page.locator('.asset-series.ma5').count(), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true, `overflow ${width}/${theme}`);
    await page.locator('#main').evaluate(element => { element.scrollTop = 0; });
    await page.screenshot({ path: path.join(output, `${width}-${theme}-overview.png`), fullPage: true });
    await page.locator('.asset-topic-tabs a').filter({ hasText: /^财务$/ }).click();
    await page.locator('.asset-financial-table').waitFor(); assert.match(await page.locator('.asset-financial-table').innerText(), /营业收入[\s\S]*0/);
    if (width === 1920 && theme === 'light') {
      await page.locator('[data-asset-block-refresh="financials"]').click();
      await page.waitForFunction(() => !document.querySelector('[data-asset-block-refresh="financials"]')?.disabled);
      assert.equal(refreshes, 1);
    }
    assert.equal(await page.locator('.asset-chart-details').getAttribute('open'), null);
    await page.locator('.asset-topic-tabs a').filter({ hasText: /^新闻$/ }).click();
    await page.locator('[data-asset-personal] > summary').click();
    await page.locator('[data-asset-note] textarea').fill('保留本资产笔记草稿');
    await page.locator('.asset-news-row').first().waitFor();
    assert.equal(await page.locator('[data-asset-note] textarea').inputValue(), '保留本资产笔记草稿');
    await page.locator('[data-asset-news-select="1"]').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('[data-asset-news-select="1"]').evaluate(element => document.activeElement === element), true);
    await page.locator('[data-asset-news-more]').focus(); await page.keyboard.press('Enter');
    assert.equal(await page.locator('.asset-news-row').count(), 25);
    assert.equal(await page.locator('[data-asset-news-select="20"]').evaluate(element => document.activeElement === element), true);
    assert.match(await page.locator('.asset-reading-text').innerText(), /<script>/); assert.equal(await page.locator('.asset-news-reader script').count(), 0);
    await page.locator('[data-asset-select] input').fill('603986.SH'); await page.locator('[data-asset-select] button').first().click();
    await page.waitForFunction(() => document.querySelector('[data-asset-identity]')?.dataset.assetIdentity === 'stock:603986.SH');
    assert.doesNotMatch(await page.locator('.asset-identity').innerText(), /隔离测试资产 A/);
    await page.waitForFunction(() => document.querySelector('.asset-news-workspace h2')?.textContent.includes('603986'));
    await page.locator('.asset-news-row').first().waitFor();
    assert.doesNotMatch(await page.locator('.asset-news-workspace').innerText(), /600519/);
    await page.screenshot({ path: path.join(output, `${width}-${theme}-news.png`), fullPage: true });
    assert.deepEqual(errors, []);
    await appendFile(log, JSON.stringify({ event: 'asset_browser_fixture', width, theme, status: 'PASS' }) + '\n');
    await context.close();
  }
  if (!liveProof) assert.ok(reads.some(value => /offset=200/.test(value)));
  assert.ok(!reads.some(value => /POST.*(?:sessions|research-runs)|\/artifacts/.test(value)));
  await writeFile(path.join(output, liveProof ? 'cjpy-real-summary.json' : 'summary.json'), JSON.stringify({ status: 'PASS', scenarios: liveProof ? 2 : 6, fixture: !liveProof, savedRealData: Boolean(liveProof), rows: liveProof ? rows.history.length : null, supplierCallsDuringReadback: 0, modelCalls: 0, refreshes, reads: reads.length }, null, 2));
  console.log(JSON.stringify({ status: 'PASS', scenarios: liveProof ? 2 : 6, savedRealData: Boolean(liveProof), output }));
} catch (error) { await appendFile(log, JSON.stringify({ event: 'asset_browser_fixture_failed', code: error.name, message: error.message.slice(0, 500) }) + '\n'); throw error; }
finally { await browser?.close(); await new Promise(resolve => server.close(resolve)); }
