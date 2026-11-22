/** Offline browser acceptance: actual app + Python MarketService/routes, no live data. */
import assert from 'node:assert/strict';
import path from 'node:path';
import os from 'node:os';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { mkdir, writeFile, readFile, appendFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'logs/market-e2e');
await mkdir(output, { recursive: true });
const started = performance.now();
const results = [], pageErrors = [], consoleErrors = [], apiErrors = [], external = [], screenshots = [];
let browser, server, page, origin, shutdown;
const serverLog = path.join(output, 'server.log');
await writeFile(serverLog, 'Offline market fixture; not real market or production authentication evidence.\n');
const python = process.env.RWB_MARKET_E2E_PYTHON || path.join(project, '.venv', process.platform === 'win32' ? 'Scripts' : 'bin', process.platform === 'win32' ? 'python.exe' : 'python');
const core = process.env.PLAYWRIGHT_CORE || path.join(os.homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const bounded = (promise, ms, message) => { let timer; return Promise.race([promise, new Promise((_, reject) => { timer = setTimeout(() => reject(new Error(message)), ms); })]).finally(() => clearTimeout(timer)); };
const check = async (name, run) => {
  const at = performance.now();
  try { const evidence = await run(); results.push({ name, status: 'PASS', durationMs: Math.round(performance.now() - at), evidence }); console.log(`PASS ${name}`); return true; }
  catch (error) { results.push({ name, status: 'FAIL', durationMs: Math.round(performance.now() - at), error: error.message }); console.error(`FAIL ${name}: ${error.message}`); try { await page?.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); } catch (captureError) { results.push({name:'failure screenshot',status:'FAIL',error:captureError.message}); } return false; }
};
async function screenshot(name) { const file = path.join(output, `${name}.png`); await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))); await page.screenshot({ path: file }); screenshots.push(file); return file; }
async function state() { const response = await page.request.get(`${origin}/fixture/state`); assert.equal(response.status(), 200); return response.json(); }
async function control(body) { const response = await page.request.post(`${origin}/fixture/control`, { data: body }); assert.equal(response.status(), 200); return response.json(); }
async function ready() { await page.waitForFunction(() => document.querySelector('[data-market-action="refresh"]') && !document.querySelector('[data-market-action="refresh"]').disabled, null, { timeout: 15000 }); }
async function quotesReady() { await page.waitForFunction(() => document.querySelector('.market-pagination') && !document.querySelector('.market-pagination').textContent.includes('读取中')); }
async function tab(name) { await page.locator('.market-tabs').getByRole('link', { name, exact: true }).click(); await ready(); }

try {
  server = spawn(python, ['tests/e2e/market_fixture.py', '--data-root', path.join(output, 'data')], { cwd: project, env: { ...process.env, PYTHONPATH: project, PYTHONUNBUFFERED: '1' }, stdio: ['ignore', 'pipe', 'pipe'] });
  const exited = new Promise(resolve => { server.once('exit', (code, signal) => resolve({code,signal})); });
  shutdown = exited;
  const readyPort = new Promise((resolve, reject) => {
    server.once('error', reject);
    const lines = createInterface({ input: server.stdout });
    lines.on('line', line => { void appendFile(serverLog, `${line}\n`); try { const value = JSON.parse(line); if (value.fixture_port) resolve(value.fixture_port); } catch { /* Uvicorn/project logs remain in local evidence. */ } });
    server.once('exit', code => reject(new Error(`Fixture exited before ready (${code})`)));
  });
  server.stderr.on('data', chunk => { void appendFile(serverLog, chunk); });
  origin = `http://127.0.0.1:${await bounded(readyPort, 15000, 'Fixture startup timeout')}`;
  await (async () => { let lastFailure='not ready'; for (let attempt=0;attempt<150;attempt++) { try { const response = await fetch(`${origin}/health`,{signal:AbortSignal.timeout(1000)}); if (response.ok) return; lastFailure=`HTTP ${response.status}`; } catch(error) { lastFailure=error.message; } await delay(100); } throw new Error(`Fixture health timeout: ${lastFailure}`); })();
  const { chromium } = await import(pathToFileURL(core).href);
  browser = await chromium.launch({ headless: true, executablePath: chrome });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true, colorScheme: 'light' });
  await context.route('**/*', route => { const url = new URL(route.request().url()); if (url.origin === origin || ['data:', 'blob:'].includes(url.protocol)) return route.continue(); external.push(url.origin); return route.abort('blockedbyclient'); });
  page = await context.newPage();
  page.on('pageerror', error => pageErrors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') consoleErrors.push(message.text()); });
  page.on('response', response => { if (response.status() >= 400 && response.url().includes('/api/')) apiErrors.push({ url: response.url(), status: response.status() }); });

  const loaded = await check('actual app boot, fixture cookie and 6001-stock service snapshot', async () => {
    assert.equal((await fetch(`${origin}/api/research/market`)).status, 401, 'Fixture API must reject missing fixture cookie');
    await page.goto(`${origin}/#/market`, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => document.querySelectorAll('.market-index-card').length === 12, null, { timeout: 20000 });
    await ready();
    const result = await (await page.request.get(`${origin}/api/research/market`)).json();
    assert.equal(result.sections.quotes.row_count, 6001); assert.equal(result.sections.quotes.provider_total, 6001); assert.equal(result.sections.quotes.complete, true);
    assert.equal(await page.locator('.market-tabs a').count(), 3);
    assert.equal(await page.locator('.market-intraday').count(), 1);
    assert.equal((await state()).session_creates, 0);
    return { rowCount: result.sections.quotes.row_count, indices: 12, snapshotId: result.sections.quotes.snapshot_id, auth: 'offline fixture cookie, not production auth' };
  });
  if (!loaded) throw new Error('Initial market app load failed; further interactions skipped');
  await screenshot('overview-light-1440');
  if (process.argv.includes('--smoke')) { console.log('Smoke complete'); }
  else {
    await check('full market pagination, exchange/board/search and ordering use real routes', async () => {
      await tab('沪深北行情');
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('6,001'));
      assert.equal(await page.locator('.market-table tbody tr').count(), 50);
      const initial = await page.locator('.market-table tbody tr:first-child').innerText();
      await page.getByRole('button', { name: '下一页', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('2 / 121'));
      await quotesReady();
      assert.notEqual(await page.locator('.market-table tbody tr:first-child').innerText(), initial);
      await page.locator('[data-market-filter="exchange"]').selectOption('BJ');
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('2,000'));
      await quotesReady();
      assert.ok((await page.locator('.market-table tbody td.market-col-code').allTextContents()).every(value => value.includes('BJ')));
      await page.locator('[data-market-filter="exchange"]').selectOption('all');
      await quotesReady();
      await page.locator('[data-market-filter="board"]').selectOption('star');
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('201'));
      await quotesReady();
      await page.locator('[data-market-filter="board"]').selectOption('all');
      await quotesReady();
      await page.locator('#market-search').fill('离线夹具股票0002');
      await page.locator('[data-market-search]').getByRole('button', { name: '搜索', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('共 1 只'));
      await quotesReady();
      assert.match(await page.locator('.market-table tbody').innerText(), /离线夹具股票0002/);
      await page.locator('#market-search').fill(''); await page.locator('[data-market-search]').getByRole('button', { name: '搜索', exact: true }).click();
      await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('6,001'));
      await quotesReady();
      await page.locator('[data-market-action="sort"][data-sort="price"]').click();
      await page.waitForFunction(() => document.querySelector('th.market-col-price')?.getAttribute('aria-sort') === 'descending');
      await quotesReady();
      const values = await page.locator('[data-market-column="price"]').allTextContents();
      assert.ok(Number(values[0]) >= Number(values.at(-1)));
      return { pages: 121, beijing: 2000, star: 201, searchMatches: 1 };
    });
    await check('column visibility and CSV bind the accepted snapshot and complete filtered universe', async () => {
      await page.locator('[data-market-action="columns"]').click();
      await page.locator('[data-market-column-toggle="volume"]').uncheck();
      assert.equal(await page.locator('[data-market-column="volume"]').count(), 0);
      await page.locator('[data-market-action="columns"]').click();
      const link = page.getByRole('link', { name: '导出 CSV', exact: true });
      const href = await link.getAttribute('href'); const id = new URL(href, origin).searchParams.get('snapshot_id');
      const response = await page.request.get(new URL(href, origin).href); assert.equal(response.status(), 200);
      assert.ok(response.headers()['content-disposition'].includes(id));
      const csv = await response.text(); assert.equal(csv.trim().split(/\r?\n/).length, 6002);
      const downloaded = page.waitForEvent('download'); await link.click(); const download = await downloaded;
      await download.saveAs(path.join(output, 'market-fixture.csv'));
      assert.equal((await readFile(path.join(output, 'market-fixture.csv'), 'utf8')).replace(/^\uFEFF/, ''), csv.replace(/^\uFEFF/, ''));
      return { snapshotId: id, csvRows: 6001, noOffsetLimit: !new URL(href, origin).searchParams.has('limit') };
    });
    await check('draft search and focus survive a real 30-second automatic refresh', async () => {
      const input = page.locator('#market-search'); await input.fill('尚未提交的搜索草稿'); await input.focus();
      await page.evaluate(() => { const node = document.getElementById('market-search'); node.setSelectionRange(3, 8); });
      const waitingAt=performance.now();
      const automatic = await page.waitForRequest(request => request.method()==='POST' && request.url()===`${origin}/api/research/market/refresh` && request.postDataJSON()?.sections?.includes('quotes') && request.postDataJSON()?.sections?.includes('indices'), {timeout:37000});
      await ready();
      assert.equal(await input.inputValue(), '尚未提交的搜索草稿');
      const focus = await input.evaluate(node => ({ active: node === document.activeElement, start: node.selectionStart, end: node.selectionEnd }));
      assert.deepEqual(focus, { active: true, start: 3, end: 8 });
      assert.match(await page.locator('.market-pagination').innerText(), /6,001/);
      return {...focus,automaticSections:automatic.postDataJSON().sections,elapsedMs:Math.round(performance.now()-waitingAt)};
    });
    await check('pause/resume and sector period/constituent navigation', async () => {
      await page.locator('[data-market-action="pause"]').click(); assert.match(await page.locator('.market-refresh-label').innerText(), /暂停/);
      await page.locator('[data-market-action="pause"]').click(); assert.match(await page.locator('.market-refresh-label').innerText(), /30秒/);
      await tab('板块与资金'); await page.waitForFunction(() => document.querySelectorAll('.market-flow-table tbody tr').length === 8);
      await page.locator('[data-market-period]').selectOption('5d'); await ready();
      await page.waitForFunction(() => document.querySelector('.market-page-body')?.textContent.includes('5日板块资金流向'));
      await page.locator('[data-market-action="kind"][data-kind="concept"]').click(); await ready();
      await page.waitForFunction(() => document.querySelector('.market-page-body')?.textContent.includes('概念涨跌全景'));
      await page.locator('[data-market-action="members"][data-board-id="BK1001"]').first().click();
      await page.waitForFunction(() => location.hash.includes('board_id=BK1001'));
      await ready(); await page.waitForFunction(() => document.querySelector('.market-pagination')?.textContent.includes('共 3 只'));
      assert.equal(await page.locator('.market-table tbody tr').count(), 3);
      const codeCells = await page.locator('.market-table tbody td.market-col-code').allTextContents();
      assert.ok(codeCells.some(code => code.includes('SH')) && codeCells.some(code => code.includes('SZ')) && codeCells.some(code => code.includes('BJ')));
      return { membershipRows: 3, exchanges: ['SH','SZ','BJ'], selectedKind: 'concept', period: '5d' };
    });
    await check('light/dark desktop and narrow layouts contain horizontal scrolling in the table', async () => {
      const layouts = [];
      for (const theme of ['light','dark']) {
        await page.evaluate(theme => window.ResearchWebTheme.controller.setPreference(theme), theme);
        for (const width of [1440, 390]) {
          await page.setViewportSize({width,height:900});
          const bounds = await page.evaluate(() => ({ viewport:innerWidth, document:document.documentElement.scrollWidth, main:document.getElementById('main').scrollWidth, mainClient:document.getElementById('main').clientWidth, table:document.querySelector('.market-table-wrap').scrollWidth, tableClient:document.querySelector('.market-table-wrap').clientWidth, theme:document.documentElement.dataset.theme, marketPages:document.querySelectorAll('[data-market-page]').length, appShells:document.querySelectorAll('.app-shell').length }));
          assert.equal(bounds.marketPages,1);assert.equal(bounds.appShells,1);
          assert.ok(bounds.document <= width + 1, `Page overflow at ${width}: ${JSON.stringify(bounds)}`);
          assert.ok(bounds.main <= bounds.mainClient + 1, `Main overflow at ${width}: ${JSON.stringify(bounds)}`);
          if(width===390)assert.ok(bounds.table > bounds.tableClient, 'Wide market table must scroll inside its wrapper');
          layouts.push(bounds); await screenshot(`quotes-${theme}-${width}`);
        }
      }
      return layouts;
    });
    await check('partial source is visible without false market totals or CSV acceptance', async () => {
      await control({mode:'partial',reset:true}); await page.setViewportSize({width:1440,height:900});
      await page.goto(`${origin}/#/market`, {waitUntil:'networkidle'}); await ready();
      await page.waitForFunction(() => document.querySelector('.market-page')?.textContent.includes('5,928 / 6,001'));
      assert.match(await page.locator('.market-page').innerText(), /部分覆盖|未完整/);
      assert.ok(await page.locator('.market-error[role="alert"]').isVisible(), 'Partial task error must remain visible');
      const response=await page.request.get(`${origin}/api/research/market`);const market=await response.json();
      assert.equal(market.sections.quotes.complete,false);assert.equal(market.sections.quotes.row_count,5928);
      assert.equal(Object.hasOwn(market.sections.quotes.summary,'up'),false);
      await tab('沪深北行情');
      assert.equal(await page.getByRole('link',{name:'导出 CSV',exact:true}).getAttribute('aria-disabled'),'true');
      await screenshot('partial-1440');
      return {rowCount:5928,providerTotal:6001,complete:false,exportDisabled:true};
    });
    await check('offline network, console/API errors and no research session creation', async () => {
      const latest=await state(); assert.equal(latest.session_creates,0);assert.deepEqual(external,[]);assert.deepEqual(pageErrors,[]);assert.deepEqual(consoleErrors,[]);assert.deepEqual(apiErrors,[]);
      return { sessionCreates:latest.session_creates,providerCalls:latest.provider_calls.length,externalRequests:external.length,pageErrors,consoleErrors,apiErrors };
    });
  }
} catch(error) { results.push({name:'runner',status:'FAIL',error:error.stack || error.message}); console.error(error.stack); }
finally {
  if(browser) await browser.close().catch(error=>results.push({name:'browser-close',status:'FAIL',error:error.message}));
  if(server && server.exitCode===null) {
    try {
      const response=await fetch(`${origin}/fixture/shutdown`,{method:'POST',headers:{Cookie:'rwb_market_fixture=local-only'},signal:AbortSignal.timeout(3000)});
      assert.equal(response.status,200);
    } catch(error) { results.push({name:'fixture graceful shutdown request',status:'FAIL',error:error.message});server.kill('SIGTERM'); }
  }
  if(shutdown) { try { const result=await bounded(shutdown,15000,'Fixture shutdown timeout');results.push({name:'fixture shutdown',status:result.code===0?'PASS':'FAIL',evidence:result}); } catch(error){results.push({name:'fixture shutdown',status:'FAIL',error:error.message});} }
  const report={kind:'offline-market-browser-fixture',notRealMarketAcceptance:true,notProductionAuthentication:true,startedAt:new Date(Date.now()-(performance.now()-started)).toISOString(),durationMs:Math.round(performance.now()-started),origin,results,pageErrors,consoleErrors,apiErrors,external,screenshots};
  await writeFile(path.join(output,'result.json'),JSON.stringify(report,null,2));
  console.log(JSON.stringify({output,passed:results.filter(row=>row.status==='PASS').length,failed:results.filter(row=>row.status==='FAIL').length,durationMs:report.durationMs}));
  process.exitCode=results.some(row=>row.status==='FAIL')?1:0;
}
