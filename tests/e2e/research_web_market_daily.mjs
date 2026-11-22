/** Authenticated shell fixture only; no resident, vendor requests, or business writes. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { calendarToday, offsetDay } from '../../app/research_web/ui/market-dashboard-model.mjs';

const output = path.resolve(process.env.RWB_DAILY_OUTPUT || 'logs/market-daily-browser');
const root = path.resolve('app/research_web/ui');
const today = calendarToday(new Date()), day = offsetDay(today, -1), old = offsetDay(today, -2), future = offsetDay(today, 1);
const broken = offsetDay(today, 4);
const sourceUrl = 'https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm';
const account = { id: '11111111-1111-4111-8111-111111111111', username: 'daily_fixture', role: 'admin', primary: true };
const events = [
  { id: 'continuing', revision: 1, payload: { title: '夹具持续事件', category: 'policy', date_precision: 'interval', occurrence_start: old, occurrence_end: future, lifecycle: 'ongoing', markets: ['CN'], source: 'fed_fomc', source_url: sourceUrl } },
  { id: 'closed', revision: 1, payload: { title: '夹具公告休市', category: 'calendar', date_precision: 'day', occurrence_start: day, lifecycle: 'scheduled', calendar_status: 'closed', markets: ['CN'], source: 'sse_trading_calendar' } },
  { id: 'conflicting-closure', revision: 1, payload: { title: '夹具与真实点位冲突的休市', category: 'calendar', date_precision: 'day', occurrence_start: old, lifecycle: 'announced', calendar_status: 'closed', markets: ['CN'], source: 'sse_trading_calendar' } },
  { id: 'future', revision: 1, payload: { title: '夹具未来日程', category: 'macro', date_precision: 'day', occurrence_start: future, lifecycle: 'scheduled', markets: ['US'], source: 'fed_fomc' } },
];
const sources = [{ id: 'fed_fomc', label: 'FOMC 官方日程', url: sourceUrl }, { id: 'sse_trading_calendar', label: '上交所交易日历', url: 'https://www.sse.com.cn/disclosure/dealinstruc/closed/' }];
const bars = [offsetDay(today, -6), offsetDay(today, -5), old].map((date, index) => ({ date, open: 4000 + index, close: 4001 + index, low: 3999 + index, high: 4002 + index, volume: 12 }));
const row = { index_id: 'SSE', market: 'CN', price: 4100, change: -20, change_pct: -0.48, quote_trade_date: today, as_of: today + 'T15:00:00+08:00', timezone: 'Asia/Shanghai', daily_bars: bars, partial_daily_bar: { date: today }, gaps: [{ date: offsetDay(today, -4), code: 'ohlcv_incomplete' }], source: 'tencent', daily_source: 'tencent' };
const errors = [], external = [], writes = [], checks = [];
const mime = { '.html': 'text/html', '.css': 'text/css', '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
await mkdir(output, { recursive: true });
let allowDetail;
const detailGate = new Promise(resolve => { allowDetail = resolve; });
const server = http.createServer(async (req, res) => {
  try {
    const url = new URL(req.url, 'http://127.0.0.1');
    if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/server/api/')) {
      if (!['GET', 'HEAD'].includes(req.method)) {
        writes.push(url.pathname); res.writeHead(405).end(); return;
      }
      const p = url.pathname.replace(/^\/api\/research/, '');
      const params = url.searchParams;
      let status = 200, data = { items: [], sources: [], summary: {}, enabled: false, status: 'idle', capabilities: [], groups: [], projects: [] };
      if (p === '/market') data = { sections: { 'indices:global-v1': { rows: [row] } } };
      else if (p === '/events/timeline') {
        const start = params.get('start'), end = params.get('end');
        if (start === broken && end === broken) { status = 503; data = { detail: 'fixture_unavailable' }; }
        else data = { items: events.filter(e => (e.payload.occurrence_end || e.payload.occurrence_start) >= start && e.payload.occurrence_start <= end && (!params.get('market') || e.payload.markets.includes(params.get('market'))) && (!params.get('category') || e.payload.category === params.get('category'))), sources };
      } else if (p === '/events/continuing') { await detailGate; data = { ...events[0], revision: 2, payload: { ...events[0].payload, description: '详情异步回填完成' } }; }
      else if (p === '/events/coverage') data = { complete: false, items: [{ payload: { source: 'fed_fomc', start: old, end: future, state: 'partial_page' } }] };
      else if (p === '/market-scores/initial-evidence') data = { items: [{ index_id: 'SSE', as_of: old, axes: { trend: { value: 2.5, unit: 'percent', status: 'NOT_ADMITTED', reasons: ['host_factor_evidence_not_admitted'], source: { provider: 'eastmoney' } } } }] };
      else if (p === '/runtime') data = { connected: true, credential_configured: true, model: 'offline-fixture' };
      else if (p === '/server/api/me') data = account;
      else if (p.startsWith('/navigation/')) data = { revision: 0, pinned: [], project_order: [] };
      res.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' }).end(JSON.stringify(data));
      return;
    }
    const rel = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const file = path.resolve(root, rel);
    if (!file.startsWith(root + path.sep)) throw new Error('unsafe fixture static path');
    const content = await readFile(file);
    res.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream', 'cache-control': 'no-store' }).end(content);
  } catch (error) { errors.push(error.code || error.message); res.writeHead(500).end(); }
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = 'http://127.0.0.1:' + server.address().port;
let browser;
async function setup(viewport, hasTouch = false) {
  const context = await browser.newContext({ viewport, hasTouch, colorScheme: 'dark' });
  await context.addInitScript(user => { window.__RWB_USER_ID__ = user.id; window.__RWB_ACCOUNT__ = user; window.__RWB_USER_ROLE__ = user.role; }, account);
  await context.route('**/*', async route => {
    const url = new URL(route.request().url());
    if (url.origin !== origin) { external.push(url.origin); await route.abort(); } else await route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/');
  await page.locator('.md-page[aria-busy="false"]').waitFor();
  return { context, page };
}
try {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH).href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const desktop = await setup({ width: 1440, height: 900 });
  const { page } = desktop;
  const scroll = page.locator('.md-time-scroll'), date = day => page.locator('[data-md-action="day"][data-date="' + day + '"]'), panel = page.getByRole('region', { name: '所选日期详情' });
  assert.equal(await scroll.locator('[data-md-action="day"]').count(), 61);
  assert(await scroll.evaluate(e => e.scrollWidth > e.clientWidth && e.scrollLeft > 0));
  const centered = await scroll.evaluate(e => e.scrollLeft);
  await scroll.hover({ position: { x: 20, y: 30 } });
  await page.mouse.wheel(280, 0);
  await page.waitForFunction(left => document.querySelector('.md-time-scroll')?.scrollLeft > left + 20, centered);
  await date(day).click();
  await panel.getByRole('button', { name: '夹具持续事件', exact: true }).waitFor();
  assert.equal(await page.locator('.md-replay-banner').count(), 0);
  await panel.getByRole('button', { name: '夹具公告休市', exact: true }).first().waitFor();
  const left = await scroll.evaluate(e => e.scrollLeft);
  await page.getByLabel('事件市场').selectOption('CN');
  await page.waitForFunction(() => document.querySelector('.md-timeline footer')?.textContent.includes('3 条已加载'));
  assert.equal(await scroll.evaluate(e => e.scrollLeft), left);
  const opener = panel.getByRole('button', { name: '夹具持续事件', exact: true });
  await opener.click();
  const dialog = page.getByRole('dialog');
  await dialog.getByRole('link', { name: '该记录的公开来源 ↗' }).waitFor();
  const link = dialog.getByRole('link', { name: '该记录的公开来源 ↗' });
  assert.equal(await link.getAttribute('href'), sourceUrl);
  await link.focus();
  allowDetail();
  await dialog.getByText('详情异步回填完成', { exact: true }).waitFor();
  assert(await link.evaluate(e => e === document.activeElement));
  await page.keyboard.press('Escape');
  await dialog.waitFor({ state: 'hidden' });
  assert(await opener.evaluate(e => e === document.activeElement));
  assert.equal(await scroll.evaluate(e => e.scrollLeft), left);
  await panel.getByRole('button', { name: '查看该日行情' }).click();
  await page.locator('.md-replay-banner').waitFor();
  assert((await page.locator('.md-quote').first().innerText()).includes('官方日历：所选日期休市'));
  assert.equal(await page.locator('.md-quote strong').first().innerText(), '—');
  await page.getByRole('button', { name: '退出回放' }).click();
  await date(old).click();
  await panel.getByRole('button', { name: '夹具与真实点位冲突的休市', exact: true }).first().waitFor();
  await panel.getByRole('button', { name: '查看该日行情' }).click();
  assert.equal(await page.locator('.md-quote strong').first().innerText(), '4,003.00');
  assert((await page.locator('.md-quote').first().innerText()).includes('与日线记录存在差异'));
  await page.getByRole('button', { name: '退出回放' }).click();
  await date(future).click();
  assert.equal(await panel.getByRole('button', { name: '查看该日行情' }).count(), 0);
  await page.getByLabel('事件市场').selectOption('');
  await panel.getByRole('button', { name: '夹具未来日程' }).waitFor();
  await date(broken).click();
  await panel.getByText('该日记录读取失败，不能判定无事件。').first().waitFor();
  await page.getByLabel('选择日期', { exact: true }).fill('2020-02-29');
  await page.getByRole('button', { name: '定位日期' }).click();
  await date('2020-02-29').waitFor();
  await page.getByLabel('开始', { exact: true }).fill('2020-02-28');
  await page.getByLabel('结束', { exact: true }).fill('2020-03-01');
  await page.getByRole('button', { name: '应用范围' }).click();
  assert.equal(await scroll.locator('[data-md-action="day"]').count(), 3);
  await date('2020-02-29').press('ArrowRight');
  assert.equal(await date('2020-03-01').getAttribute('aria-pressed'), 'true');
  const chart = page.locator('.md-spark').first(), points = chart.locator('.md-chart-point');
  await points.last().focus();
  await points.last().press('ArrowLeft');
  assert((await chart.locator('output').innerText()).includes(bars[1].date));
  assert((await page.locator('.md-axis-evidence').first().innerText()).includes('原值 2.50%'));
  checks.push('desktop daily scroll, filter retention, keyboard, sources, selected-day replay, future, failed day, leap-day custom range and chart');
  await page.getByRole('button', { name: '今天', exact: true }).click();
  await page.waitForFunction(() => document.querySelector('.md-timeline footer')?.textContent.includes('4 条已加载'));
  await page.screenshot({ path: path.join(output, 'desktop-timeline.png') });
  await desktop.context.close();

  const mobile = await setup({ width: 390, height: 844 }, true);
  const m = mobile.page;
  assert(await m.locator('.md-time-scroll').evaluate(e => e.scrollWidth > e.clientWidth));
  assert(await m.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  const mChart = m.locator('.md-spark').first();
  await mChart.locator('.md-chart-point').first().tap();
  assert((await mChart.locator('output').innerText()).includes(bars[0].date));
  await m.locator('[data-md-action="day"][data-date="' + day + '"]').tap();
  await m.getByRole('region', { name: '所选日期详情' }).getByRole('button', { name: '夹具持续事件' }).waitFor();
  await m.screenshot({ path: path.join(output, 'mobile-timeline.png') });
  checks.push('mobile no body overflow, scrollable day columns, chart tap and day tap');
  await mobile.context.close();
  assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(writes, []);
  const result = { status: 'PASS', checks, errors, external, writes, fixture: 'loopback full-shell, real UI and CSS, synthetic fixture data only' };
  await writeFile(path.join(output, 'result.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result));
} catch (error) {
  await writeFile(path.join(output, 'failure.json'), JSON.stringify({ message: error.message, stack: error.stack, errors, external, writes, checks }, null, 2));
  throw error;
} finally {
  await browser?.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
}
