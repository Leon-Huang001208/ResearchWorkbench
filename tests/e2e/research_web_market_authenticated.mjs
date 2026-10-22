/** Real production auth/runtime/market acceptance on an owned loopback instance. */
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import os from 'node:os';
import path from 'node:path';
import { spawn, execFileSync } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdir, writeFile, appendFile, readFile, readdir, stat } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'logs/market-authenticated', new Date().toISOString().replaceAll(':', '-'));
await mkdir(output, { recursive: true, mode: 0o700 });
const python = process.env.RWB_MARKET_E2E_PYTHON || path.join(project, '.venv', 'bin', 'python');
const node = process.env.RWB_AUTH_NODE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node');
const pin = JSON.parse(await readFile(path.join(project, 'runtimes/research_web.json'), 'utf8')).dsh.commit;
const source = process.env.RWB_AUTH_DSH_SOURCE || path.join(os.homedir(), '.research-workbench/runtime/dsh', pin);
const core = process.env.PLAYWRIGHT_CORE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const protectedPids = (process.env.RWB_AUTH_PROTECTED_PIDS || '').split(',').filter(Boolean).map(value => { const pid = Number(value); assert.ok(Number.isSafeInteger(pid) && pid > 0); return pid; });
const accounts = [{ username: 'market_accept_admin', role: 'admin' }, { username: 'market_accept_user', role: 'user' }].map(item => ({ ...item, password: crypto.randomBytes(24).toString('base64url') }));
const results = [], pageErrors = [], externalBrowser = [], screens = [], refreshRequests = [];
const startedAt = new Date().toISOString(), started = performance.now();
const isolatedDataRoot = path.join('/private/tmp', `rwb-market-auth-${crypto.randomUUID()}`);
const candidateCommit = execFileSync('/usr/bin/git', ['rev-parse', 'HEAD'], { cwd: project, encoding: 'utf8' }).trim();
const sourceHashes = Object.fromEntries(await Promise.all(['app/research_web/datahub/providers_market.py', 'app/research_web/market_service.py', 'app/research_web/market_routes.py', 'app/research_web/multiuser/gateway.py', 'app/research_web/multiuser/runtime.py'].map(async file => [file, crypto.createHash('sha256').update(await readFile(path.join(project, file))).digest('hex')])));
let helper, browser, origin, users, shutdownRecord, gatewayExit, metadataResolve, metadataReject, ownedResolve;
const bounded = (promise, ms, text) => { let timer; return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(text)), ms); })]).finally(() => clearTimeout(timer)); };
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const safeError = error => accounts.reduce((message, item) => item.password ? message.replaceAll(item.password, '[redacted]') : message, String(error.message || error));
async function check(name, fn) {
  const at = performance.now();
  try { const evidence = await fn(); results.push({ name, status: 'PASS', durationMs: Math.round(performance.now() - at), evidence }); console.log(`PASS ${name}`); return evidence; }
  catch (error) { const message = safeError(error); results.push({ name, status: 'FAIL', durationMs: Math.round(performance.now() - at), error: message }); console.error(`FAIL ${name}: ${message}`); return null; }
}
async function fromPage(page, endpoint, options = {}) {
  return page.evaluate(async ({ endpoint, options }) => {
    const response = await fetch(endpoint, { ...options, credentials: 'same-origin', ...(options.body ? { headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(options.body) } : {}) });
    const text = await response.text(); let body;
    try { body = JSON.parse(text); } catch { body = { text }; }
    return { status: response.status, body };
  }, { endpoint, options });
}
async function login(context, account) {
  const page = await context.newPage();
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('request', request => {
    const url = new URL(request.url());
    if (!['data:', 'blob:'].includes(url.protocol) && url.origin !== origin) externalBrowser.push(url.origin);
    if (url.origin === origin && url.pathname === '/api/research/market/refresh' && request.method() === 'POST') {
      const body = request.postDataJSON();
      refreshRequests.push({ at: Date.now(), sections: body.sections, kind: body.kind, period: body.period, board_id: body.board_id });
    }
  });
  await page.goto(`${origin}/auth`);
  await page.locator('#login-form:not([hidden])').waitFor();
  await page.locator('[name=username]').fill(account.username);
  await page.locator('[name=password]').fill(account.password);
  await Promise.all([page.waitForURL(url => url.pathname === '/', { timeout: 90000 }), page.getByRole('button', { name: '登录', exact: true }).click()]);
  await page.waitForFunction(() => Boolean(window.__RWB_USER_ID__), null, { timeout: 90000 });
  return page;
}
async function waitMarket(page, predicate = value => value.sections.quotes.snapshot_id) {
  const limit = Date.now() + 150000;
  while (Date.now() < limit) {
    const value = await fromPage(page, '/api/research/market');
    if (value.status === 200 && !value.body.inflight.length && predicate(value.body)) return value.body;
    await delay(1000);
  }
  throw new Error('real_market_refresh_timeout');
}
async function screen(page, name) {
  const file = path.join(output, `${name}.png`); await page.screenshot({ path: file }); screens.push(file); return file;
}
async function tableAction(page, action, expected = {}) {
  await page.waitForFunction(() => !document.querySelector('.market-pagination')?.textContent.includes('读取中'));
  const exported = await page.getByRole('link', { name: '导出 CSV', exact: true }).getAttribute('href');
  expected = { snapshot_id: new URL(exported, origin).searchParams.get('snapshot_id'), ...expected };
  const response = page.waitForResponse(value => { const url = new URL(value.url()); return url.pathname === '/api/research/market/quotes' && value.request().method() === 'GET' && Object.entries(expected).every(([key, value]) => url.searchParams.get(key) === String(value)); });
  await action(); const value = await response; assert.equal(value.status(), 200); const body = await value.json();
  await page.waitForFunction(({ first, count }) => {
    if (document.querySelector('.market-pagination')?.textContent.includes('读取中')) return false;
    const rows = document.querySelectorAll('.market-table tbody tr');
    return rows.length === count && (!first || rows[0]?.querySelector('a')?.getAttribute('href')?.includes(`asset=${first}`));
  }, { first: body.items[0]?.asset, count: body.items.length });
  return body;
}

try {
  assert.ok(protectedPids.length, 'RWB_AUTH_PROTECTED_PIDS must name the verified resident process baseline');
  helper = spawn(python, ['tests/e2e/market_authenticated.py', '--root', isolatedDataRoot, '--source', source, '--node', node, ...protectedPids.flatMap(pid => ['--protect-pid', String(pid)])], { cwd: project, env: { ...process.env, PYTHONPATH: project, PYTHONUNBUFFERED: '1', PYTHONDONTWRITEBYTECODE: '1' }, stdio: ['pipe', 'pipe', 'pipe'] });
  gatewayExit = new Promise(resolve => helper.once('exit', (code, signal) => resolve({ code, signal })));
  const ready = new Promise((resolve, reject) => {
    helper.once('error', reject);
    createInterface({ input: helper.stdout }).on('line', line => {
      try { const value = JSON.parse(line); if (value.ready) resolve(value); if (value.shutdown) shutdownRecord = value; if (value.independent_metadata) metadataResolve?.(value.independent_metadata); if (value.metadata_error) metadataReject?.(new Error(`metadata_${value.metadata_error}`)); if (value.owned) ownedResolve?.(value.owned); if (value.startup_error) reject(new Error(`real_gateway_startup_${value.startup_error}`)); }
      catch (error) { if (error.message.startsWith('real_gateway_')) reject(error); }
      void appendFile(path.join(output, 'gateway.log'), `${line}\n`);
    });
    helper.once('exit', code => reject(new Error(`real_gateway_exited_before_ready_${code}`)));
  });
  helper.stderr.on('data', chunk => { void appendFile(path.join(output, 'gateway-stderr.log'), chunk); });
  helper.stdin.write(`${JSON.stringify({ accounts })}\n`);
  ({ origin, users } = await bounded(ready, 30000, 'real_gateway_startup_timeout'));
  for (let attempt = 0; attempt < 100; attempt++) { try { const r = await fetch(`${origin}/api/server/health`); if (r.ok) break; } catch { /* Startup is bounded by the loop. */ } await delay(100); }
  const { chromium } = await import(pathToFileURL(core).href);
  browser = await chromium.launch({ headless: true, executablePath: chrome });
  const adminContext = await browser.newContext({ viewport: { width: 1440, height: 1000 }, acceptDownloads: true });
  await check('production gateway rejects unauthenticated market requests', async () => {
    const response = await adminContext.request.get(`${origin}/api/research/market`); assert.equal(response.status(), 401); return { status: response.status() };
  });
  const page = await login(adminContext, accounts[0]);
  await check('actual login form creates matching authenticated page identity', async () => {
    const me = await fromPage(page, '/api/server/me'); assert.equal(me.status, 200); assert.equal(me.body.user.id, users[0].id);
    assert.equal(await page.evaluate(() => window.__RWB_USER_ID__), users[0].id);
    const cookies = await adminContext.cookies(origin); assert.ok(cookies.some(cookie => cookie.httpOnly && cookie.sameSite === 'Strict'));
    const wrong = await adminContext.request.get(`${origin}/api/research/market`, { headers: { 'X-RWB-Page-User': users[1].id } }); assert.equal(wrong.status(), 401);
    return { user_id: users[0].id, role: me.body.user.role, wrong_page_identity: wrong.status(), httpOnly_sameSiteStrict: true };
  });
  const runtimeReady = await check('production RuntimePool starts the candidate Web and pinned DSH', async () => {
    const response = await fromPage(page, '/api/research/runtime');
    assert.equal(response.status, 200);
    assert.equal(response.body.health_check_passed, true);
    const sessions = await fromPage(page, '/api/research/sessions');
    assert.equal(sessions.status, 200); assert.equal(sessions.body.items.length, 0);
    return { health_check_passed: true, version: response.body.version, sessions: 0, model_configured: Boolean(response.body.credential_configured) };
  });
  if (!runtimeReady) throw new Error('owned candidate runtime did not become healthy');
  if (!process.argv.includes('--auth-only')) {
    const metadataPromise = new Promise((resolve, reject) => { metadataResolve = resolve; metadataReject = reject; });
    helper.stdin.write(`${JSON.stringify({ operation: 'metadata' })}\n`);
    const independentMetadata = await bounded(metadataPromise, 25000, 'independent_metadata_timeout');
    await page.goto(`${origin}/#/market`);
    const snapshot = await waitMarket(page);
    await check('genuine tenant market refresh completes the SH SZ BJ universe', async () => {
      const quotes = snapshot.sections.quotes;
      assert.equal(quotes.complete, true); assert.equal(quotes.pagination_complete, true); assert.ok(quotes.row_count > 5000);
      assert.equal(quotes.row_count, independentMetadata.total);
      const scopes = quotes.summary.scopes; for (const exchange of ['SH', 'SZ', 'BJ']) { assert.equal(scopes[exchange].complete, true); assert.equal(scopes[exchange].received, scopes[exchange].provider_total); assert.ok(scopes[exchange].received > 0); }
      const breadth = quotes.summary.breadth; assert.equal(breadth.total, quotes.row_count); assert.equal(breadth.up + breadth.down + breadth.flat + breadth.unknown, breadth.total);
      assert.equal(quotes.provider, 'eastmoney'); assert.ok(quotes.as_of);
      return { snapshot_id: quotes.snapshot_id, provider: quotes.provider, row_count: quotes.row_count, provider_total: quotes.provider_total, independentMetadata, scopes, as_of: quotes.as_of, retrieved_at: quotes.retrieved_at, breadth, upcoming_count: quotes.summary.upcoming_count, amount: quotes.summary.amount, missing: quotes.missing, indices: { count: snapshot.sections.indices.rows.length, complete: snapshot.sections.indices.complete, missing: snapshot.sections.indices.missing }, boards: Object.fromEntries(['industry', 'concept'].map(key => [key, { count: snapshot.sections[key].row_count, complete: snapshot.sections[key].complete, missing: snapshot.sections[key].missing }])) };
    });
    await page.locator('.market-page h1').waitFor();
    const pause = page.locator('[data-market-action=pause]'); if (await pause.textContent() === '暂停自动') await pause.click();
    await screen(page, 'real-authenticated-overview');
    await check('real quote table CSV and page statistics bind one snapshot', async () => {
      const id = snapshot.sections.quotes.snapshot_id;
      const all = await fromPage(page, `/api/research/market/quotes?snapshot_id=${id}&limit=200`); assert.equal(all.status, 200); assert.equal(all.body.total, snapshot.sections.quotes.row_count); assert.equal(all.body.snapshot_id, id);
      const exchanges = {};
      for (const exchange of ['SH', 'SZ', 'BJ']) { const r = await fromPage(page, `/api/research/market/quotes?snapshot_id=${id}&exchange=${exchange}&limit=1`); assert.equal(r.status, 200); assert.ok(r.body.items[0].asset.endsWith(`.${exchange}`)); exchanges[exchange] = r.body.total; }
      const csv = await fromPage(page, `/api/research/market/quotes/export?snapshot_id=${id}`); assert.equal(csv.status, 200); const text = csv.body.text; assert.ok(text); const lines = text.trim().split(/\r?\n/); assert.equal(lines.length - 1, all.body.total);
      const identifiers = lines.slice(1).map(line => line.split(',')[0]); assert.equal(new Set(identifiers).size, all.body.total);
      for (const exchange of ['SH', 'SZ', 'BJ']) assert.equal(identifiers.filter(id => id.endsWith(`.${exchange}`)).length, exchanges[exchange]);
      await page.locator('.market-tabs').getByRole('link', { name: '沪深北行情', exact: true }).click(); await page.waitForFunction(() => document.querySelector('.market-table tbody tr'));
      await screen(page, 'real-authenticated-quotes');
      return { snapshot_id: id, total: all.body.total, exchanges, csv_rows: lines.length - 1, unique_ids: new Set(identifiers).size, csv_sha256: crypto.createHash('sha256').update(text).digest('hex') };
    });
    await check('twelve real indices and source gaps are visible', async () => {
      const indices = snapshot.sections.indices;
      assert.equal(indices.rows.length, 12);
      assert.ok(indices.rows.every(row => row.asset && row.as_of));
      assert.equal(indices.complete, true);
      for (const key of ['indices', 'intraday', 'quote_date']) assert.equal(indices.missing[key], 0);
      const tradeDate = snapshot.sections.quotes.summary.quote_trade_date;
      assert.ok(tradeDate);
      assert.ok(indices.rows.every(row => row.as_of.startsWith(tradeDate) && row.series?.length && row.series.every(point => point.time?.startsWith(tradeDate) && Number.isFinite(point.price) && Number.isFinite(point.change_pct))));
      await page.locator('.market-tabs').getByRole('link', { name: '总览', exact: true }).click();
      await page.locator('.market-index-card').first().waitFor();
      assert.equal(await page.locator('.market-index-card').count(), 12);
      assert.ok(await page.locator('.market-metadata').count() > 0);
      return { count: indices.rows.length, series_count: indices.rows.filter(row => row.series?.length).length, as_of: indices.as_of, missing: indices.missing, limitations: indices.limitations };
    });
    await check('authenticated table filtering sorting pagination columns and export operate', async () => {
      await page.locator('.market-tabs').getByRole('link', { name: '沪深北行情', exact: true }).click();
      await page.locator('.market-table tbody tr').first().waitFor();
      const bj = await tableAction(page, () => page.locator('[data-market-filter=exchange]').selectOption('BJ'), { exchange: 'BJ' });
      assert.equal(bj.total, snapshot.sections.quotes.summary.scopes.BJ.received); assert.ok(bj.items.every(row => row.exchange === 'BJ'));
      const all = await tableAction(page, () => page.locator('[data-market-filter=exchange]').selectOption('all'), { exchange: 'all' });
      assert.equal(all.total, snapshot.sections.quotes.row_count);
      const star = await tableAction(page, () => page.locator('[data-market-filter=board]').selectOption('star'), { board: 'star' }); assert.ok(star.total > 0); assert.ok(star.items.every(row => row.board === 'star'));
      await tableAction(page, () => page.locator('[data-market-filter=board]').selectOption('all'), { board: 'all' });
      const sorted = await tableAction(page, () => page.locator('[data-market-action=sort][data-sort=price]').click(), { sort: 'price', direction: 'desc' });
      const prices = sorted.items.map(row => row.price).filter(value => value !== null); assert.deepEqual(prices, [...prices].sort((a, b) => b - a));
      const next = await tableAction(page, () => page.locator('[data-market-action=next]').click(), { offset: 50 }); assert.notEqual(next.items[0].asset, sorted.items[0].asset);
      const code = sorted.items[0].code;
      await page.locator('#market-search').fill(code);
      const searched = await tableAction(page, () => page.locator('[data-market-search]').getByRole('button', { name: '搜索', exact: true }).click(), { search: code });
      assert.ok(searched.total > 0); assert.ok(searched.items.every(row => `${row.asset} ${row.code} ${row.name}`.includes(code)));
      const downloadEvent = page.waitForEvent('download'); await page.getByRole('link', { name: '导出 CSV', exact: true }).click(); const download = await downloadEvent;
      assert.equal(await download.failure(), null); const downloadPath = path.join(output, 'filtered-market.csv'); await download.saveAs(downloadPath);
      const exported = await readFile(downloadPath, 'utf8'); assert.equal(exported.trim().split(/\r?\n/).length - 1, searched.total);
      await page.locator('[data-market-action=columns]').click(); await page.locator('[data-market-column-toggle=pb]').uncheck(); assert.equal(await page.locator('th.market-col-pb').count(), 0);
      await page.locator('[data-market-column-toggle=pb]').check(); assert.equal(await page.locator('th.market-col-pb').count(), 1);
      await page.locator('#market-search').fill(''); await tableAction(page, () => page.locator('[data-market-search]').getByRole('button', { name: '搜索', exact: true }).click(), { search: '' });
      return { exchange_BJ: bj.total, star: star.total, pagination_changed_first_asset: true, sort: 'price desc', searched: searched.total, downloaded_rows: searched.total, columns_hidden_restored: true };
    });
    await check('real sector funds and member quotes use the same market snapshot', async () => {
      await page.locator('.market-tabs').getByRole('link', { name: '板块与资金', exact: true }).click();
      const sectors = await waitMarket(page, value => value.sections['flows:industry:today']?.snapshot_id);
      const flows = sectors.sections['flows:industry:today'];
      assert.ok(sectors.sections.industry.rows.length > 0);
      assert.ok(flows.rows.length > 0); assert.equal(flows.provider, 'eastmoney');
      await screen(page, 'real-authenticated-sectors');
      const board = page.locator('[data-market-action=members]').first(); const boardID = await board.getAttribute('data-board-id');
      await board.click();
      await page.waitForURL(url => url.hash.includes(`board_id=${boardID}`), { timeout: 90000 });
      const r = await fromPage(page, `/api/research/market/quotes?board_id=${boardID}&snapshot_id=${snapshot.sections.quotes.snapshot_id}&limit=200`);
      assert.equal(r.status, 200); assert.ok(r.body.total > 0); assert.equal(r.body.snapshot_id, snapshot.sections.quotes.snapshot_id);
      const membership = r.body.meta.membership;
      assert.equal(membership.summary.quotes_snapshot_id, snapshot.sections.quotes.snapshot_id);
      await screen(page, 'real-authenticated-board-members');
      return { board_id: boardID, rows: r.body.total, snapshot_id: r.body.snapshot_id, membership: membership.summary, funds: { rows: flows.rows.length, complete: flows.complete, as_of: flows.as_of, missing: flows.missing, limitations: flows.limitations, market_flow_rows: flows.summary?.market_flow?.rows?.length } };
    });
    await check('industry concept funds support today five day and ten day source periods', async () => {
      await page.locator('.market-tabs').getByRole('link', { name: '板块与资金', exact: true }).click();
      const observed = [];
      for (const kind of ['industry', 'concept']) {
        if (kind === 'concept') {
          const prior = (await fromPage(page, '/api/research/market')).body.sections['flows:concept:today']?.snapshot_id;
          await page.locator('[data-market-action=kind][data-kind=concept]').click();
          await waitMarket(page, value => value.sections['flows:concept:today']?.snapshot_id !== prior && value.sections['flows:concept:today']?.snapshot_id);
        }
        for (const period of ['today', '5d', '10d']) {
          const key = `flows:${kind}:${period}`;
          if (period !== 'today') {
            const prior = (await fromPage(page, '/api/research/market')).body.sections[key]?.snapshot_id;
            await page.locator('[data-market-period]').selectOption(period);
            await waitMarket(page, value => value.sections[key]?.snapshot_id !== prior && value.sections[key]?.snapshot_id);
          }
          const current = (await fromPage(page, '/api/research/market')).body.sections[key];
          assert.ok(current.rows.length > 0); observed.push({ kind, period, rows: current.rows.length, as_of: current.as_of, complete: current.complete, missing: current.missing, limitations: current.limitations });
        }
        if (kind === 'industry') { await page.locator('[data-market-period]').selectOption('today'); await waitMarket(page); }
      }
      return observed;
    });
    await check('genuine thirty second refresh updates the authenticated snapshot', async () => {
      await page.locator('.market-tabs').getByRole('link', { name: '总览', exact: true }).click();
      const previous = (await fromPage(page, '/api/research/market')).body;
      if (!previous.market_state.auto_refresh) return { status: 'NOT_APPLICABLE', state: previous.market_state, reason: 'real trading calendar does not permit automatic refresh' };
      const resumed = Date.now();
      const pause = page.locator('[data-market-action=pause]'); if (await pause.textContent() === '恢复自动') await pause.click();
      const updated = await waitMarket(page, value => value.sections.quotes.snapshot_id && value.sections.quotes.snapshot_id !== previous.sections.quotes.snapshot_id);
      const automatic = refreshRequests.filter(item => item.at >= resumed && item.sections?.join(',') === 'quotes,indices');
      assert.ok(automatic.length > 0); assert.ok(automatic[0].at - resumed >= 29000);
      await page.locator('[data-market-action=pause]').click();
      return { from: previous.sections.quotes.snapshot_id, to: updated.sections.quotes.snapshot_id, first_request_after_ms: automatic[0].at - resumed, rows: updated.sections.quotes.row_count, as_of: updated.sections.quotes.as_of, state: updated.market_state };
    });
    await check('real authenticated market renders light dark and narrow table scrolling', async () => {
      await page.emulateMedia({ colorScheme: 'dark' }); await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark'); await screen(page, 'real-authenticated-dark');
      await page.emulateMedia({ colorScheme: 'light' }); await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
      await page.setViewportSize({ width: 390, height: 844 }); await screen(page, 'real-authenticated-narrow-overview');
      await page.locator('.market-tabs').getByRole('link', { name: '沪深北行情', exact: true }).click(); await page.locator('.market-table').waitFor();
      const dimensions = await page.locator('.market-table-wrap').evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth, overflow: getComputedStyle(element).overflowX }));
      assert.ok(dimensions.scroll > dimensions.client); assert.ok(['auto', 'scroll'].includes(dimensions.overflow)); await screen(page, 'real-authenticated-narrow-quotes');
      await page.setViewportSize({ width: 1440, height: 1000 });
      return { themes: ['light', 'dark'], viewport: { width: 390, height: 844 }, table: dimensions };
    });
    await check('stock and index links enter existing asset observation without sessions', async () => {
      const stock = page.locator('.market-table tbody a').first(); const stockHref = await stock.getAttribute('href'); assert.ok(stockHref.startsWith('#/assets?'));
      await stock.click(); await page.waitForURL(url => url.hash.startsWith('#/assets?')); await page.locator('.market-page').waitFor({ state: 'detached' });
      await page.goto(`${origin}/#/market`); await page.locator('.market-index-card').first().waitFor();
      const index = page.locator('.market-index-card').first(); const indexHref = await index.getAttribute('href'); assert.ok(indexHref.includes('asset_type=index'));
      await index.click(); await page.waitForURL(url => url.hash.includes('asset_type=index')); await page.locator('.market-page').waitFor({ state: 'detached' });
      const before = refreshRequests.length; await delay(1500); assert.equal(refreshRequests.length, before);
      return { stock: stockHref, index: indexHref, route_leaving_stops_market_requests: true, late_response_regression: 'covered separately by deterministic controller regression; no network timing injected here' };
    });
    await check('market browsing creates no research sessions', async () => { const r = await fromPage(page, '/api/research/sessions'); assert.equal(r.status, 200); assert.equal(r.body.items.length, 0); return { sessions: 0 }; });
    const ownedPromise = new Promise(resolve => { ownedResolve = resolve; }); helper.stdin.write(`${JSON.stringify({ operation: 'owned' })}\n`); await bounded(ownedPromise, 5000, 'owned_pool_evidence_timeout');
    await page.close();
    const stopped = await adminContext.request.post(`${origin}/api/server/users/${users[0].id}/stop`, { headers: { Origin: origin } }); assert.equal(stopped.status(), 200);
    const userContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    const userPage = await login(userContext, accounts[1]);
    await check('a second real account has a separate initially empty market cache', async () => {
      const me = await fromPage(userPage, '/api/server/me'); assert.equal(me.body.user.id, users[1].id); assert.notEqual(me.body.user.id, users[0].id);
      const r = await fromPage(userPage, '/api/research/market'); assert.equal(r.status, 200); assert.equal(r.body.sections.quotes.snapshot_id, null); assert.equal(r.body.sections.quotes.row_count, 0);
      const sessions = await fromPage(userPage, '/api/research/sessions'); assert.equal(sessions.body.items.length, 0);
      const rootA = path.join(isolatedDataRoot, 'users', users[0].id, 'research-web', 'market-cache');
      const rootB = path.join(isolatedDataRoot, 'users', users[1].id, 'research-web', 'market-cache');
      const filesA = await readdir(rootA);
      const filesB = await readdir(rootB).catch(error => { if (error.code === 'ENOENT') return []; throw error; });
      assert.ok(filesA.length > 0); assert.equal(filesB.length, 0); assert.notEqual(rootA, rootB);
      assert.equal((await stat(isolatedDataRoot)).mode & 0o777, 0o700);
      return { user_id: users[1].id, first_cache_rows: 0, first_snapshot: null, sessions: 0, isolated_data_mode: '0700', userA_cache_files: filesA.length, userB_cache_files: 0, distinct_cache_roots: true };
    });
    await userContext.close();
  } else await page.close();
  await adminContext.close();
} catch (error) { const message = safeError(error); results.push({ name: 'authenticated acceptance execution', status: 'FAIL', error: message }); console.error(`FAIL authenticated acceptance: ${message}`); }
finally {
  await browser?.close();
  if (helper?.exitCode === null) { helper.stdin.write(`${JSON.stringify({ operation: 'shutdown' })}\n`); const exited = await bounded(gatewayExit, 45000, 'owned_gateway_shutdown_timeout'); if (exited.code !== 0) results.push({ name: 'owned gateway shutdown', status: 'FAIL', error: `code=${exited.code} signal=${exited.signal}` }); }
  if (shutdownRecord) results.push({ name: 'owned shutdown preserves resident services', status: shutdownRecord.owned_instances === 0 && shutdownRecord.resident_unchanged ? 'PASS' : 'FAIL', evidence: shutdownRecord });
  else results.push({ name: 'owned shutdown evidence', status: 'FAIL', error: 'missing shutdown record' });
  for (const account of accounts) delete account.password;
  const report = { kind: 'real-production-authenticated-market', candidateCommit, sourceHashes, isolatedDataRoot, mockedAuth: false, mockedRuntime: false, mockedProvider: false, residentDeployed: false, residentSnapshotScope: 'explicit verified resident process PIDs, birth times and command identity hashes', protectedPids, startedAt, durationMs: Math.round(performance.now() - started), results, pageErrors, externalBrowser, screenshots: screens };
  await writeFile(path.join(output, 'result.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({ output, passed: results.filter(x => x.status === 'PASS').length, failed: results.filter(x => x.status === 'FAIL').length }));
  if (results.some(x => x.status === 'FAIL') || pageErrors.length) process.exitCode = 1;
}
