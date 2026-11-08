/** macOS browser acceptance for real calendar UI against an isolated fixture. */
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = fileURLToPath(new URL('../../', import.meta.url));
const ui = path.join(project, 'app/research_web/ui');
const output = path.join(project, 'logs/financial-calendar/browser');
const origin = 'http://127.0.0.1:41871'; // Intercepted before any network IO.
const calendar = '/api/research/market/financial-calendar';
const core = process.env.PLAYWRIGHT_CORE || path.join(os.homedir(),
  '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
const chrome = process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const report = { kind: 'offline-browser-fixture', results: [], errors: [] };
const mime = { '.html': 'text/html', '.mjs': 'text/javascript', '.js': 'text/javascript',
  '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json' };
const observed = '2026-11-07T16:00:00Z';
const source = { id: 'bls_cpi', label: 'BLS CPI', url: 'https://www.bls.gov/schedule/news_release/cpi.htm',
  observed_at: observed, status: 'partial' };

function response(query) {
  const { view, start, end, category = 'economic', page = '0' } = Object.fromEntries(query);
  const summary = view === 'summary', connected = category === 'economic';
  const days = [];
  for (let day = Date.parse(start); day <= Date.parse(end); day += 86400000) {
    const date = new Date(day).toISOString().slice(0, 10);
    const event = { id: `fixture-${date}-${page}`, date, title: page === '0' ? '离线排期样本' : '离线分页样本',
      date_precision: 'day', source_id: source.id, source_url: source.url, observed_at: observed };
    days.push(summary ? { date, status: 'partial', counts: { economic: 2, ipo: null, notify: null, report: null } }
      : { date, items: connected ? [event] : [], total: connected ? 2 : null,
        has_more: connected && page === '0', status: connected ? 'partial' : 'not_connected' });
  }
  return { days, snapshot_id: connected ? 'a'.repeat(32) : null, sources: connected ? [source] : [] };
}

await mkdir(output, { recursive: true });
let browser;
try {
  const { chromium } = await import(pathToFileURL(core).href);
  browser = await chromium.launch({ headless: true, executablePath: chrome });
  for (const [width, height] of [[1440, 900], [390, 844]]) {
    const context = await browser.newContext({ viewport: { width, height },
      locale: 'zh-CN', timezoneId: 'Asia/Shanghai', colorScheme: 'light', reducedMotion: 'reduce' });
    const requests = [];
    const unexpected = [];
    try {
      await context.route('**/*', async route => {
        const request = route.request(), url = new URL(request.url());
        if (url.origin !== origin || request.method() !== 'GET') {
          unexpected.push([request.method(), url.origin, url.pathname]);
          await route.abort();
          return;
        }
        if (url.pathname.startsWith('/api/')) {
          requests.push({ path: url.pathname, query: Object.fromEntries(url.searchParams) });
          const json = url.pathname === calendar ? response(url.searchParams) : { items: [], groups: [] };
          await route.fulfill({ json });
          return;
        }
        const name = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
        const file = path.resolve(ui, name);
        if (!file.startsWith(ui + path.sep)) throw new Error('unsafe fixture path');
        await route.fulfill({ path: file, contentType: mime[path.extname(file)] });
      });
      const page = await context.newPage();
      page.on('pageerror', error => report.errors.push(String(error)));
      await page.clock.setFixedTime(new Date('2026-11-08T00:30:00+08:00'));
      page.setDefaultTimeout(6000);
      await page.goto(origin + '/#/market?view=calendar');
      assert.ok(await page.locator('a[href="#/market?view=calendar"][aria-current="page"]').count());
      await page.getByText('离线排期样本', { exact: true }).first().waitFor();
      assert.equal(await page.getByText('离线排期样本', { exact: true }).count(), 7);
      assert.ok(requests.some(({ path, query }) => path === calendar && query.view === 'summary'
        && query.start === '2026-11-02' && query.end === '2026-11-08'));
      const dimensions = await page.evaluate(() => {
        const main = document.querySelector('#main');
        const mode = document.getElementById('financial-calendar-mode-month').getBoundingClientRect();
        return { pageWidth: document.documentElement.scrollWidth, viewport: innerWidth,
          mainScroll: main.scrollWidth, mainWidth: main.clientWidth, modeRight: mode.right };
      });
      assert.ok(dimensions.pageWidth <= dimensions.viewport && dimensions.mainScroll <= dimensions.mainWidth + 1
        && dimensions.modeRight <= dimensions.viewport, `calendar viewport clipping: ${JSON.stringify(dimensions)}`);
      await page.screenshot({ path: path.join(output, `week-${width}.png`) });
      await page.getByRole('button', { name: '加载更多', exact: true }).first().click();
      await page.getByText('离线分页样本', { exact: true }).waitFor();
      assert.ok(requests.some(({ path, query }) => path === calendar && query.page === '1'
        && query.snapshot_id === 'a'.repeat(32) && query.start === query.end));

      const month = page.getByRole('button', { name: '月历', exact: true });
      await month.click();
      assert.equal(await month.getAttribute('aria-pressed'), 'true');
      await page.getByText('离线排期样本', { exact: true }).waitFor();
      assert.equal(await page.getByText('离线排期样本', { exact: true }).count(), 1);
      assert.ok(requests.some(({ path, query }) => path === calendar && query.view === 'summary'
        && query.start === '2026-11-01' && query.end === '2026-11-30'));
      await page.screenshot({ path: path.join(output, `month-${width}.png`) });
      if (width === 390) {
        const strip = page.locator('.financial-calendar-month-scroll');
        const initial = await strip.evaluate(node => {
          node.scrollLeft = node.scrollWidth;
          return node.scrollLeft;
        });
        assert.ok(initial > 0);
        await Promise.all([
          page.waitForResponse(resp => {
            const params = new URL(resp.url()).searchParams;
            return params.get('view') === 'events' && params.get('start') === '2026-11-14';
          }),
          page.locator('#financial-calendar-pick-2026-11-14').click(),
        ]);
        await page.getByText('离线排期样本', { exact: true }).waitFor();
        assert.ok(await strip.evaluate(node => node.scrollLeft > 0), 'month grid lost its horizontal position');
      }

      for (const [label, category] of [['新股发行','ipo'], ['交易提醒','notify'],
        ['财报发行','report'], ['机构交易','inst']]) {
        const button = page.getByRole('button', { name: label, exact: true });
        await Promise.all([
          page.waitForResponse(resp => new URL(resp.url()).searchParams.get('category') === category),
          button.click(),
        ]);
        assert.equal(await button.getAttribute('aria-pressed'), 'true');
        if (category === 'ipo') {
          await page.getByRole('columnheader', { name: '发行价', exact: true }).waitFor();
        }
      }
      await Promise.all([
        page.waitForResponse(resp => new URL(resp.url()).searchParams.get('filter_set') === 'topAum'),
        page.getByRole('button', { name: 'Top AUM', exact: true }).click(),
      ]);
      assert.ok(requests.every(({ path }) => !/^\/api\/research\/market(?:\/quotes|\/refresh|$)/.test(path)));
      assert.deepEqual(unexpected, []);
      assert.deepEqual(report.errors, []);
      report.results.push({ width, height, status: 'PASS', calendarRequests: requests.filter(r => r.path === calendar).length });
    } finally {
      await context.close();
    }
  }
} catch (error) {
  report.errors.push(error.stack || String(error));
  console.error(error);
  process.exitCode = 1;
} finally {
  await browser?.close();
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify(report, null, 2) + '\n');
}
console.log(JSON.stringify(report));
