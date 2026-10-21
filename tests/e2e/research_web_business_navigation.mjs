/** Isolated browser acceptance: real Research Web UI, deterministic local API fixtures. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.resolve(process.env.RWB_BUSINESS_NAVIGATION_OUTPUT || process.env.RWB_BUSINESS_NAV_OUTPUT || path.join(projectRoot, 'outputs/research-web-business-navigation-20261021'));
const logPath = path.resolve(process.env.RWB_BUSINESS_NAVIGATION_LOG || process.env.RWB_BUSINESS_NAV_LOG || path.join(projectRoot, 'logs/research-web-business-navigation-20261021.jsonl'));
const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const expectedNavigation = ['FinGPT', 'Claw', '资产观察', '研究情报', 'AI 资讯', '研究框架', '策略模拟', '能力中心', '运行与用量'];
const sectionCapabilities = { funds: 'fund_data', market: 'search_news', industry: 'search_research', documents: 'search_announcements' };
const sources = [{ id: 'fixture_public', name: '验收公开来源', readiness: { callable: true } }, { id: 'fixture_secondary', name: '验收备用来源', readiness: { callable: true } }];
const dataCatalog = {
  summary: {}, sources,
  capabilities: Object.values(sectionCapabilities).map(id => ({ id, name: id, description: '本地验收夹具', source_count: 2, callable_source_count: 2 })),
  bindings: Object.values(sectionCapabilities).flatMap(capability_id => sources.map(source => ({ capability_id, source_id: source.id }))),
};
const mime = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml' };

function dataset(id, label = id) {
  return { dataset_id: id, name: label, provider: label, source: 'fixture_public', status: 'snapshot', row_count: 2, as_of: '2026-10-20', retrieved_at: '2026-10-21T01:00:00Z', missing: ['验收缺失提示'], limitations: ['仅本地夹具'], pagination_complete: true };
}

function queryRecord(section, id, label = id) {
  return { id, section, session_id: `source_${section}`, status: 'completed', created_at: Date.now(), dataset: dataset(`dataset_${id}`, label) };
}

function etfResult(id = 'run_current') {
  return {
    id, strategy: { strategy_id: 'fixture_etf', version: id, asset_pool: ['510300.SH'], risk_budget: 0.8, security_cap: 0.5, min_cash_weight: 0.2 },
    data_source: '本地工程输入', data_cutoff: '2026-10-20', state: { cash: 10000, fees: 0, lots: [] }, curve: [{ nav: 10000 }],
    review: { net_return: 0, gross_return: 0, max_drawdown: 0, turnover: 0, benchmark: 'fixture', benchmark_return: 0, cash_weight: 1, limitations: ['未验证真实策略收益'] },
    events: [], orders: [], fills: [], real_chain: { status: 'BLOCKED', gaps: ['真实链路未准入'] },
  };
}

function sessionDetail(id = 'handoff_session', mode = 'fingpt') {
  return {
    id, mode, title: '验收交接会话', status: 'idle', messages: [], activities: [], approvals: [], questions: [], subagents: [],
    model: 'local-fixture', datasets: [dataset('session_dataset', '会话资料夹具')],
    files: [{ id: 'fixture_file', name: '会话材料.md', kind: 'inputs', size: 20, url: `/api/research/sessions/${id}/files/fixture_file/download`, preview_url: `/api/research/sessions/${id}/files/fixture_file/preview` }],
  };
}

async function log(event, details = {}) {
  await appendFile(logPath, `${JSON.stringify({ at: new Date().toISOString(), event, ...details })}\n`);
}

function createFixture() {
  const calls = [];
  const queryLists = new Map(Object.keys(sectionCapabilities).map(section => [section, []]));
  const gates = [];
  const unknown = [];
  const pendingQueries = new Map();
  const manifests = new Map();
  let sequence = 0;
  function hold(method, pathname, search = '') {
    let release;
    const ready = new Promise(resolve => { release = resolve; });
    const gate = { method, pathname, search, ready, release, seen: false };
    gates.push(gate);
    return gate;
  }
  const json = (response, body, status = 200) => {
    if (response.destroyed) return;
    response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
    response.end(JSON.stringify(body));
  };
  async function api(request, response, url) {
    const parts = [];
    for await (const part of request) parts.push(part);
    const raw = Buffer.concat(parts).toString();
    const body = raw ? JSON.parse(raw) : null;
    const method = request.method || 'GET';
    const pathname = url.pathname.replace(/^\/api\/research/, '');
    calls.push({ method, pathname, search: url.search, body });
    const gate = gates.find(item => !item.seen && item.method === method && item.pathname === pathname && (!item.search || item.search === url.search));
    if (gate) {
      gate.seen = true;
      const override = await gate.ready;
      if (override) { json(response, override.body, override.status || 200); return; }
    }
    if (method === 'GET') {
      if (pathname === '/runtime') return json(response, { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture', version: 'fixture' });
      if (pathname === '/models') return json(response, { groups: [], failures: [] });
      if (pathname === '/data/catalog') return json(response, dataCatalog);
      if (pathname === '/data/queries') return json(response, { items: queryLists.get(url.searchParams.get('section')) || [] });
      if (pathname.startsWith('/data/queries/')) {
        const record = pendingQueries.get(pathname.split('/').at(-1));
        assert.ok(record, `unknown query fixture: ${pathname}`);
        queryLists.set(record.section, [record]);
        return json(response, record);
      }
      if (/^\/sessions\/[^/]+\/datasets\/[^/]+$/.test(pathname)) {
        const id = pathname.split('/').at(-1);
        assert.ok(manifests.has(id), `unknown dataset manifest fixture: ${id}`);
        return json(response, manifests.get(id));
      }
      if (pathname === '/portfolio-decisions/readiness') return json(response, { status: 'BLOCKED', gaps: ['真实链路未准入'] });
      if (pathname === '/portfolio-decisions/runs') return json(response, { items: [etfResult()] });
      if (pathname.startsWith('/portfolio-decisions/runs/')) return json(response, etfResult(pathname.split('/').at(-1)));
      if (pathname.startsWith('/navigation/')) return json(response, { mode: pathname.split('/').at(-1), pinned_session_ids: [], session_order: [], collapsed: false });
      if (pathname === '/intel/overview') return json(response, { as_of: '2026-10-20', events: [], potential: [], challenges: [], trading: [] });
      if (pathname.startsWith('/intel/')) return json(response, { items: [], stories: [], accounts: [], posts: [], industries: [] });
      if (pathname === '/hot/events') return json(response, { items: [], total: 0 });
      if (pathname.startsWith('/hot/')) return json(response, { items: [], status: 'idle', enabled: false });
      if (pathname === '/artifacts') return json(response, { items: [] }); // Recorded and rejected by acceptance below.
      if (/^\/sessions\/[^/]+\/events$/.test(pathname)) {
        response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
        response.write(': fixture stream\n\n');
        return;
      }
      if (/^\/sessions\/[^/]+\/files$/.test(pathname)) return json(response, { items: sessionDetail(pathname.split('/')[2]).files });
      if (/^\/sessions\/[^/]+\/files\/fixture_file\/(download|preview)$/.test(pathname)) {
        response.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' }); response.end('会话材料夹具'); return;
      }
      if (/^\/sessions\/[^/]+$/.test(pathname)) return json(response, sessionDetail(pathname.split('/')[2]));
      if (['/workspaces', '/sessions', '/capabilities', '/tools', '/report-workflows', '/assets/observations', '/watchlists', '/asset-notes', '/asset-alerts', '/asset-notifications', '/projects', '/claw/projects', '/automations', '/automation-runs', '/delivery-channels'].includes(pathname)) return json(response, { items: [] });
    }
    if (method === 'POST' && pathname === '/data/queries') {
      const id = `query_${++sequence}`;
      const record = queryRecord(body.section, id, `结果_${body.section}_${body.query.parameters.dataset || body.query.parameters.query || sequence}`);
      manifests.set(record.dataset.dataset_id, { ...record.dataset, query: structuredClone(body.query) });
      pendingQueries.set(id, record);
      return json(response, { ...record, status: 'running', dataset: null });
    }
    if (method === 'POST' && pathname === '/handoffs') return json(response, { mode: body.target_mode, session_id: 'handoff_session', draft: '验收交接草稿：确认后才发送' });
    if (method === 'POST' && pathname === '/portfolio-decisions/runs') return json(response, etfResult('run_replay'));
    unknown.push({ method, pathname });
    json(response, { detail: { message: `fixture endpoint missing: ${method} ${pathname}` } }, 404);
  }
  async function handler(request, response) {
    try {
      const url = new URL(request.url || '/', 'http://127.0.0.1');
      if (url.pathname.startsWith('/api/research/')) { await api(request, response, url); return; }
      const requested = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
      const filePath = path.resolve(uiRoot, requested);
      if (!filePath.startsWith(`${uiRoot}${path.sep}`)) throw new Error('unsafe static path');
      const content = await readFile(filePath);
      response.writeHead(200, { 'content-type': mime[path.extname(filePath)] || 'application/octet-stream', 'cache-control': 'no-store' });
      response.end(content);
    } catch (error) {
      await log('fixture_request_failed', { error: error.name, code: error.code || 'fixture_error' });
      json(response, { detail: { message: error.message } }, error.code === 'ENOENT' ? 404 : 500);
    }
  }
  return { calls, unknown, queryLists, hold, handler, releaseAll: () => gates.forEach(gate => gate.release()) };
}

async function waitUntil(predicate, label) {
  const started = Date.now();
  while (!predicate()) {
    if (Date.now() - started > 10000) throw new Error(`timed out: ${label}`);
    await new Promise(resolve => setTimeout(resolve, 25));
  }
}

async function navigate(page, hash) {
  await page.evaluate(value => { location.hash = value; }, hash);
  await page.waitForFunction(value => location.hash === value, hash);
  await page.locator('#main').waitFor();
}

async function assertNavigation(page, active) {
  const links = page.locator('.primary-nav .rail-link');
  assert.deepEqual(await links.locator('.rail-label').allTextContents(), expectedNavigation);
  assert.equal(await links.filter({ hasText: '研究台' }).count(), 0);
  assert.equal(await page.locator('.primary-nav [aria-current="page"]').count(), 1);
  assert.equal((await page.locator('.primary-nav [aria-current="page"] .rail-label').textContent()).trim(), active);
  assert.equal(await page.locator('.artifact-grid').count(), 0, 'cross-session artifact grid must not render');
}

async function assertContained(page) {
  const metrics = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    controls: [...document.querySelectorAll('#main button,#main input,#main select,#main a')].filter(element => element.getClientRects().length).filter(element => {
      const rect = element.getBoundingClientRect();
      if (rect.left >= -1 && rect.right <= innerWidth + 1) return false;
      for (let parent = element.parentElement; parent; parent = parent.parentElement) {
        const style = getComputedStyle(parent);
        if (parent.scrollWidth > parent.clientWidth && ['auto', 'scroll'].includes(style.overflowX)) return false;
      }
      return true;
    }).map(element => element.getAttribute('aria-label') || element.textContent.trim().slice(0, 30)),
  }));
  assert.ok(metrics.scrollWidth <= metrics.width, `horizontal overflow: ${JSON.stringify(metrics)}`);
  assert.deepEqual(metrics.controls, [], `controls outside viewport: ${JSON.stringify(metrics)}`);
}

async function submitQuery(page, fixture, { section = 'funds', dataset: datasetName = 'nav', keyword = '行业检索夹具' } = {}) {
  const form = page.locator('[data-workbench-query]');
  await form.waitFor();
  await form.locator('[name="source"]').selectOption('fixture_secondary');
  if (section === 'funds') {
    await form.locator('[name="code"]').fill('000002');
    await form.locator('[name="dataset"]').selectOption(datasetName);
    await form.locator('[name="start_date"]').fill('2026-01-01');
    await form.locator('[name="end_date"]').fill('2026-10-20');
  } else await form.locator('[name="query"]').fill(keyword);
  const count = fixture.calls.filter(call => call.method === 'POST' && call.pathname === '/data/queries').length;
  await form.getByRole('button', { name: '查询并生成快照', exact: true }).click();
  await waitUntil(() => fixture.calls.filter(call => call.method === 'POST' && call.pathname === '/data/queries').length > count, 'query POST');
  return fixture.calls.filter(call => call.method === 'POST' && call.pathname === '/data/queries').at(-1).body;
}

async function runAcceptance() {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  const fixture = createFixture();
  const server = http.createServer((request, response) => { void fixture.handler(request, response); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  let browser;
  let page;
  const checks = [];
  const errors = [];
  const browserDiagnostics = [];
  const check = async (name, operation) => { await log('acceptance_step', { step: name, status: 'started' }); await operation(); checks.push(name); await log('acceptance_step', { step: name, status: 'passed' }); };
  try {
    const address = server.address();
    assert.ok(address && typeof address !== 'string');
    const { chromium } = await import(pathToFileURL(playwrightPath));
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
    page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') browserDiagnostics.push(message.text()); });
    page.on('requestfailed', request => browserDiagnostics.push(`${request.method()} ${request.url()} ${request.failure()?.errorText}`));
    page.on('response', response => { if (response.status() >= 400) browserDiagnostics.push(`HTTP ${response.status()} ${response.url()}`); });
    await page.goto(`http://127.0.0.1:${address.port}/#/assets`, { waitUntil: 'networkidle' });

    await check('canonical pages and primary navigation', async () => {
      for (const [hash, active, selector] of [
        ['#/assets', '资产观察', '[data-asset-observation]'], ['#/assets/funds', '资产观察', '[data-workbench-query]'],
        ['#/intel/search?kind=news', '研究情报', '[data-workbench-query]'], ['#/intel/search?kind=research', '研究情报', '[data-workbench-query]'],
        ['#/intel/search?kind=announcements', '研究情报', '[data-workbench-query]'], ['#/simulation/etf', '策略模拟', '[data-etf-replay]'],
      ]) {
        await navigate(page, hash); await page.locator(selector).waitFor(); await assertNavigation(page, active);
      }
      assert.equal(fixture.calls.filter(call => call.method === 'POST').length, 0, 'opening a page cannot submit queries or simulation');
      assert.match(await page.locator('#main').textContent(), /真实链路：BLOCKED/);
    });

    await check('legacy path and query links canonicalize', async () => {
      const destinations = { '': '#/assets', assets: '#/assets', funds: '#/assets/funds', market: '#/intel/search?kind=news', industry: '#/intel/search?kind=research', documents: '#/intel/search?kind=announcements', 'etf-paper': '#/simulation/etf' };
      for (const [section, target] of Object.entries(destinations)) {
        for (const legacy of section ? [`#/workbench/${section}`, `#/workbench?section=${section}`] : ['#/workbench']) {
          await page.evaluate(value => { location.hash = value; }, legacy);
          await page.waitForFunction(value => location.hash === value, target);
        }
      }
      await page.evaluate(() => { location.hash = '#/workbench/hot?event=event_fixture&view=timeline'; });
      await page.waitForFunction(() => location.hash.startsWith('#/intel/hot'));
      const hash = await page.evaluate(() => location.hash);
      assert.ok(hash.includes('event=event_fixture') && hash.includes('view=timeline'), `hot parameters dropped: ${hash}`);
      await navigate(page, '#/assets/funds');
      await page.reload({ waitUntil: 'networkidle' }); await page.locator('[data-workbench-query]').waitFor();
      await navigate(page, '#/intel/search?kind=research'); await page.locator('[data-workbench-query]').waitFor();
      await page.goBack(); await page.waitForFunction(() => location.hash === '#/assets/funds');
      await page.goForward(); await page.waitForFunction(() => location.hash === '#/intel/search?kind=research');
    });

    await check('all fund datasets preserve source and historical query contract', async () => {
      await navigate(page, '#/assets/funds');
      for (const name of ['nav', 'profile', 'distributions', 'holdings']) {
        const body = await submitQuery(page, fixture, { dataset: name });
        assert.equal(body.section, 'funds'); assert.equal(body.query.capability, 'fund_data'); assert.equal(body.query.source, 'fixture_secondary');
        assert.deepEqual(body.query.parameters, { code: '000002', dataset: name, start_date: '2026-01-01', end_date: '2026-10-20' });
        await page.locator('.desk-result').filter({ hasText: `结果_funds_${name}` }).waitFor();
        assert.match(await page.locator('.desk-result').textContent(), /2026-10-20/);
        assert.match(await page.locator('.desk-result').textContent(), /验收缺失提示/);
        await page.waitForFunction(() => !document.querySelector('[data-workbench-query] button[type="submit"]')?.disabled);
      }
      assert.ok(fixture.calls.some(call => call.pathname.startsWith('/data/queries/query_')), 'running queries must be polled');
    });

    await check('theme searches preserve historical sections and capabilities', async () => {
      for (const [kind, section] of [['news', 'market'], ['research', 'industry'], ['announcements', 'documents']]) {
        await navigate(page, `#/intel/search?kind=${kind}`);
        const body = await submitQuery(page, fixture, { section, keyword: `检索_${kind}` });
        assert.equal(body.section, section); assert.equal(body.query.capability, sectionCapabilities[section]);
        assert.equal(body.query.source, 'fixture_secondary'); assert.equal(body.query.parameters.query, `检索_${kind}`);
        await page.locator('.desk-result').filter({ hasText: `结果_${section}_检索_${kind}` }).waitFor();
        await page.waitForFunction(() => !document.querySelector('[data-workbench-query] button[type="submit"]')?.disabled);
      }
    });

    await check('late page reads cannot replace another route result or handoff context', async () => {
      const delayed = fixture.hold('GET', '/data/queries', '?section=funds');
      await navigate(page, '#/assets/funds'); await waitUntil(() => delayed.seen, 'delayed fund read');
      await navigate(page, '#/intel/search?kind=research');
      await page.locator('.desk-result').filter({ hasText: '结果_industry_检索_research' }).waitFor();
      delayed.release({ body: { items: [queryRecord('funds', 'stale_read', 'STALE_PAGE_DATA')] } });
      await page.waitForTimeout(100);
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_PAGE_DATA/);
      const before = fixture.calls.filter(call => call.pathname === '/handoffs').length;
      await page.locator('[data-workbench-handoff="fingpt"]').click();
      await waitUntil(() => fixture.calls.filter(call => call.pathname === '/handoffs').length > before, 'research handoff');
      const body = fixture.calls.filter(call => call.pathname === '/handoffs').at(-1).body;
      assert.equal(body.section, 'industry'); assert.equal(body.source_session_id, 'source_industry');
      assert.ok(body.dataset_ids.length === 1 && !body.dataset_ids.includes('dataset_stale_read'));
      assert.equal(body.context.section, 'industry');
      await page.waitForFunction(() => location.hash.includes('session=handoff_session'));
      assert.equal(body.context.source, 'fixture_secondary');
      assert.equal(body.context.parameters.query, '检索_research');
      await page.locator('#prompt').waitFor();
      assert.match(await page.locator('#prompt').inputValue(), /验收交接草稿/);
      assert.equal(fixture.calls.filter(call => call.pathname.endsWith('/messages')).length, 0, 'handoff must not send the draft');
      await page.locator('.session-toolbar [data-toggle-context]').click();
      await page.locator('[data-context-tab="datasets"]').click();
      await page.getByText('会话资料夹具', { exact: true }).waitFor();
      await page.locator('[data-context-tab="files"]').click();
      await page.getByText('会话材料.md', { exact: true }).waitFor();
      assert.ok(await page.locator('.context-panel a[download="会话材料.md"]').count(), 'session file download remains available');
    });

    await check('query completion and failure after switch/back cannot overwrite current state', async () => {
      await navigate(page, '#/assets/funds');
      const delayed = fixture.hold('POST', '/data/queries');
      await submitQuery(page, fixture, { dataset: 'nav' });
      await waitUntil(() => delayed.seen, 'delayed query action');
      await navigate(page, '#/intel/search?kind=news'); await page.locator('[data-workbench-query]').waitFor();
      await page.locator('[name="query"]').fill('当前新闻草稿');
      delayed.release({ body: queryRecord('funds', 'late_action', 'STALE_ACTION_DATA') });
      await page.waitForTimeout(100);
      assert.equal(await page.locator('[name="query"]').inputValue(), '当前新闻草稿');
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ACTION_DATA/);
      await navigate(page, '#/assets/funds'); await page.locator('[data-workbench-query]').waitFor();
      const failed = fixture.hold('POST', '/data/queries');
      await submitQuery(page, fixture, { dataset: 'profile' }); await waitUntil(() => failed.seen, 'delayed query failure');
      await navigate(page, '#/intel/search?kind=news'); await page.locator('[data-workbench-query]').waitFor();
      await navigate(page, '#/assets/funds'); await page.locator('[data-workbench-query]').waitFor();
      await page.locator('[name="code"]').fill('000009');
      failed.release({ status: 503, body: { detail: { message: 'STALE_QUERY_ERROR' } } });
      await page.waitForTimeout(100);
      assert.equal(await page.locator('[name="code"]').inputValue(), '000009');
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_QUERY_ERROR/);
    });

    await check('late asset observation read cannot replace a later visit', async () => {
      const delayed = fixture.hold('GET', '/assets/observations');
      await navigate(page, '#/assets'); await waitUntil(() => delayed.seen, 'delayed asset observations');
      await navigate(page, '#/assets/funds'); await page.locator('[data-workbench-query]').waitFor();
      await navigate(page, '#/assets'); await page.locator('[data-asset-observation]').waitFor();
      await page.locator('[data-asset-observation] [name="asset"]').fill('600519.SH');
      delayed.release({ body: { items: [{ id: 'stale_asset', asset: 'STALE_ASSET', asset_type: 'stock', session_id: 'stale_asset_session', blocks: {}, dataset_ids: [] }] } });
      await page.waitForTimeout(100);
      assert.equal(await page.locator('[data-asset-observation] [name="asset"]').inputValue(), '600519.SH');
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ASSET/);
    });

    await check('stale handoff cannot navigate or replace another conversation draft', async () => {
      await navigate(page, '#/intel/search?kind=news');
      await page.locator('.desk-result').waitFor();
      const delayed = fixture.hold('POST', '/handoffs');
      await page.locator('[data-workbench-handoff="fingpt"]').click(); await waitUntil(() => delayed.seen, 'delayed handoff');
      await navigate(page, '#/claw'); await page.locator('#prompt').waitFor();
      await page.locator('#prompt').fill('当前 Claw 草稿');
      delayed.release({ body: { mode: 'fingpt', session_id: 'stale_handoff', draft: 'STALE_HANDOFF_DRAFT' } });
      await page.waitForTimeout(100);
      assert.equal(await page.evaluate(() => location.hash), '#/claw');
      assert.equal(await page.locator('#prompt').inputValue(), '当前 Claw 草稿');
      assert.equal(fixture.calls.filter(call => call.pathname.endsWith('/messages')).length, 0);
    });

    await check('ETF late detail and replay do not overwrite current route or later visit', async () => {
      await navigate(page, '#/simulation/etf'); await page.locator('[data-etf-run]').waitFor();
      const detail = fixture.hold('GET', '/portfolio-decisions/runs/run_current');
      await page.locator('[data-etf-run]').selectOption('run_current'); await waitUntil(() => detail.seen, 'ETF detail');
      await navigate(page, '#/assets/funds'); await page.locator('[data-workbench-query]').waitFor();
      detail.release({ body: etfResult('STALE_ETF_DETAIL') }); await page.waitForTimeout(100);
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ETF_DETAIL/);
      await navigate(page, '#/simulation/etf'); await page.locator('[data-etf-replay]').waitFor();
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ETF_DETAIL/);
      const replay = fixture.hold('POST', '/portfolio-decisions/runs');
      await page.locator('[data-etf-replay] input[type="file"]').setInputFiles({ name: 'fixture.json', mimeType: 'application/json', buffer: Buffer.from('{}') });
      await page.locator('[data-etf-replay] button').click(); await waitUntil(() => replay.seen, 'ETF replay');
      await navigate(page, '#/intel/search?kind=announcements'); await page.locator('[data-workbench-query]').waitFor();
      replay.release({ body: etfResult('STALE_ETF_REPLAY') }); await page.waitForTimeout(100);
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ETF_REPLAY/);
      await navigate(page, '#/simulation/etf'); await page.locator('[data-etf-replay]').waitFor();
      assert.doesNotMatch(await page.locator('#main').textContent(), /STALE_ETF_REPLAY/);
      assert.match(await page.locator('#main').textContent(), /真实链路：BLOCKED/);
    });

    await check('light dark desktop narrow layouts and keyboard focus', async () => {
      for (const theme of ['light', 'dark']) {
        await page.evaluate(value => window.ResearchWebTheme.controller.setPreference(value), theme);
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        for (const [width, height] of [[1440, 1000], [390, 844]]) {
          await page.setViewportSize({ width, height });
          for (const [hash, active, selector, label] of [
            ['#/assets', '资产观察', '[data-asset-observation]', 'assets'], ['#/assets/funds', '资产观察', '[data-workbench-query]', 'funds'],
            ['#/intel/search?kind=research', '研究情报', '[data-workbench-query]', 'search'], ['#/simulation/etf', '策略模拟', '[data-etf-replay]', 'etf'],
          ]) {
            await navigate(page, hash); await page.locator(selector).waitFor(); await assertNavigation(page, active);
            const focusable = page.locator(`${selector} input:not([type="hidden"]),${selector} select`).first();
            await focusable.focus(); await page.keyboard.press('Tab');
            assert.equal(await page.evaluate(() => document.activeElement !== document.body && !document.activeElement.disabled), true);
            await assertContained(page);
            await page.screenshot({ path: path.join(outputRoot, `${label}-${theme}-${width}.png`), fullPage: true });
          }
        }
      }
    });
    assert.deepEqual(errors, [], 'application must not raise browser page errors');
    assert.deepEqual(fixture.unknown, [], 'every fixture API request must be explicit');
    assert.equal(fixture.calls.filter(call => call.pathname === '/artifacts' && !call.search).length, 0, 'business pages must not fetch cross-session artifact index');
    return { status: 'passed', checks, api_calls: fixture.calls.length, screenshots: 16, scope: 'deterministic fake-API UI acceptance; no real data, models, live service or platform CI' };
  } catch (error) {
    if (page && !page.isClosed()) await page.screenshot({ path: path.join(outputRoot, 'failure.png'), fullPage: true }).catch(async screenshotError => { await log('failure_screenshot_failed', { error: screenshotError.name }); });
    await writeFile(path.join(outputRoot, 'failure-api.json'), `${JSON.stringify({ calls: fixture.calls, unknown: fixture.unknown, page_errors: errors, browser_diagnostics: browserDiagnostics }, null, 2)}\n`);
    throw error;
  } finally {
    fixture.releaseAll();
    if (browser) await browser.close();
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
  }
}

try {
  const receipt = await runAcceptance();
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`);
  await log('business_navigation_acceptance', { status: 'passed', checks: receipt.checks.length });
  console.log(`business navigation: ${receipt.checks.length} checks passed; receipt ${path.relative(projectRoot, path.join(outputRoot, 'receipt.json'))}`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true }); await mkdir(path.dirname(logPath), { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify({ status: 'failed', error: error.message }, null, 2)}\n`);
  await log('business_navigation_acceptance', { status: 'failed', error_type: error.name, error: error.message });
  console.error(error.stack || error.message);
  process.exitCode = 1;
}
