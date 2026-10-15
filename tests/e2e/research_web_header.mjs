/** Isolated browser acceptance for shared header chrome. Never contacts resident services. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ui = path.join(project, 'app/research_web/ui');
const output = path.join(project, 'logs/research-web-header');
const log = path.join(project, 'logs/research-web-header.jsonl');
const report = { status: 'running', checks: [], errors: [], writes: [] };
let runtime = { connected: true, credential_configured: true };
const mime = { '.json': 'application/json', '.js': 'text/javascript', '.html': 'text/html', '.mjs': 'text/javascript', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml' };
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://127.0.0.1');
    if (request.method !== 'GET') {
      report.writes.push(request.method);
      response.writeHead(405).end(); return;
    }
    if (url.pathname.startsWith('/api/')) {
      const payload = url.pathname.endsWith('/runtime') ? runtime
        : url.pathname.endsWith('/models') ? { groups: [], failures: [] }
          : url.pathname.endsWith('/sessions') ? { items: [{ id: 'header-test', title: '顶部栏搜索测试', mode: 'fingpt', status: 'completed' }] }
            : { items: [] };
      response.writeHead(200, { 'content-type': 'application/json' }).end(JSON.stringify(payload)); return;
    }
    const file = path.resolve(ui, url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, ''));
    if (!file.startsWith(ui + path.sep)) throw new Error('unsafe static path');
    const body = await readFile(file);
    response.writeHead(200, { 'content-type': mime[path.extname(file)] || 'application/octet-stream' }).end(body);
  } catch (error) {
    report.errors.push(`server:${error.code || error.name}`);
    response.writeHead(500).end('header test server error');
  }
});
let browser;
try {
  await mkdir(output, { recursive: true });
  await mkdir(path.dirname(log), { recursive: true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  for (const theme of ['light', 'dark']) {
    const context = await browser.newContext({ colorScheme: theme });
    await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
    const page = await context.newPage();
    page.on('pageerror', error => report.errors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') report.errors.push(message.text()); });
    for (const width of [1440, 1051, 820, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const route of ['fingpt', 'claw', 'workbench/assets', 'workbench', 'intel', 'frameworks', 'skills', 'operations', 'settings/general']) {
        await page.goto(`${origin}/#/${route}`);
        await page.locator('.topbar').waitFor({ state: 'attached' });
        assert.equal(await page.locator('.topbar-title, .title-separator, .page-subtitle, .mobile-search-toggle, .topbar [data-toggle-search]').count(), 0);
        const geometry = await page.evaluate(() => ({
          height: document.querySelector('.topbar').getBoundingClientRect().height,
          top: document.querySelector('#main').getBoundingClientRect().top,
          overflow: document.documentElement.scrollWidth > innerWidth,
        }));
        assert.equal(geometry.height, width > 1050 ? 0 : width <= 600 ? 56 : 64);
        assert.equal(geometry.top, geometry.height);
        assert.equal(geometry.overflow, false);
      }
      await page.goto(`${origin}/#/fingpt`);
      await page.locator('#prompt').waitFor();
      if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
      await page.locator('.primary-rail .search-trigger').click();
      await page.locator('#global-search').fill('顶部栏搜索测试');
      await page.locator('[data-global-result]').first().waitFor();
      await page.locator('#global-search').press('ArrowDown');
      await page.keyboard.press('Escape');
      assert.equal(await page.locator('.search-popover').isVisible(), false);
      assert.equal(await page.evaluate(() => document.activeElement.matches(innerWidth <= 1050 ? '.topbar .menu-toggle' : '.primary-rail .search-trigger')), true);
      if (width === 1440 || width === 390) await page.screenshot({ path: path.join(output, `${theme}-${width}.png`) });
      report.checks.push(`${theme}/${width}: nine routes, collapsed header, rail search, keyboard focus, navigation, overflow`);
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    for (const [state, label] of [
      [{ connected: true, credential_configured: false }, '需要配置模型'],
      [{ connected: false, health_check_passed: true }, '研究服务连接中'],
      [{ connected: false, health_check_passed: false }, '研究服务不可用'],
    ]) {
      runtime = state;
      await page.reload();
      await page.getByRole('link', { name: label, exact: true }).waitFor();
      assert.equal(await page.locator('.topbar').evaluate(el => el.getBoundingClientRect().height), 64);
      assert.equal(await page.locator('.runtime-status').getAttribute('href'), '#/settings/model');
    }
    runtime = { connected: true, credential_configured: true };
    report.checks.push(`${theme}: three actionable runtime warnings preserve settings destination`);
    await context.close();
  }
  assert.deepEqual(report.errors, []);
  assert.deepEqual(report.writes, []);
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.failure = String(error); process.exitCode = 1;
} finally {
  await browser?.close();
  await new Promise(resolve => server.close(resolve));
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify(report, null, 2));
  await appendFile(log, JSON.stringify(report) + '\n');
  console.log(JSON.stringify(report));
}
