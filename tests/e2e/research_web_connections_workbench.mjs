/** Read-only browser acceptance for the settings data-source workbench. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.join(projectRoot, 'outputs/research-web-connections-acceptance');
const logPath = path.join(projectRoot, 'logs/research-web-connections-acceptance.jsonl');
const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const viewports = [[1440, 1000], [768, 1024], [390, 844]];

const groups = [
  { id: 'professional', label: '专业数据源', source_ids: ['wind', 'tinysoft', 'ifind', 'mysql'] },
  { id: 'api', label: 'API 数据源', source_ids: ['tushare', 'tavily', 'bing', 'zhiqiu_reports', 'zhiqiu_wechat', 'zhiqiu_transcript'] },
  { id: 'public', label: '公开来源', source_ids: ['akshare', 'baostock', 'yahoo', 'chinastock', 'csindex', 'szse', 'cninfo', 'cls', 'cnstock_flash', 'cnstock_news', 'eastmoney_fund'] },
  { id: 'local', label: '本机集成', source_ids: ['local_cache'] },
];
const names = {
  wind: 'Wind', tinysoft: '天软', ifind: 'iFinD', mysql: '用户 MySQL 数据库', tushare: 'Tushare',
  tavily: 'Tavily', bing: 'Bing Search', zhiqiu_reports: '知丘研报', zhiqiu_wechat: '知丘公众号',
  zhiqiu_transcript: '知丘纪要', akshare: 'AKShare', baostock: 'BaoStock', yahoo: 'Yahoo Finance',
  chinastock: 'ChinaStock', csindex: '中证指数', szse: '深交所', cninfo: '巨潮资讯', cls: '财联社电报',
  cnstock_flash: '中国证券网快讯', cnstock_news: '中国证券网新闻', eastmoney_fund: '东方财富基金净值',
  local_cache: '本地数据 / 缓存',
};
const sources = groups.flatMap((group) => group.source_ids.map((id) => ({
  id,
  name: names[id],
  group: group.id,
  auth_type: id === 'wind' || id === 'ifind' || id === 'tinysoft' ? 'terminal' : id === 'mysql' ? 'account' : ['tushare', 'tavily', 'bing'].includes(id) ? 'api_key' : id.startsWith('zhiqiu_') ? 'account' : group.id === 'local' ? 'local' : 'none',
  configured: id === 'mysql',
  probed: id === 'mysql',
  probe_status: id === 'mysql' ? 'healthy' : 'untested',
  integration_completed: ['mysql', 'tushare', 'tinysoft', 'akshare', 'cls', 'eastmoney_fund'].includes(id),
  callable: id === 'mysql',
  configuration_supported: ['wind', 'tinysoft', 'ifind', 'mysql', 'tushare', 'tavily', 'bing', 'zhiqiu_reports', 'zhiqiu_wechat', 'zhiqiu_transcript'].includes(id),
  description: `${names[id]} 的安全连接与可调用状态。`,
  actions: ['probe'],
})));

const jsonResponses = new Map([
  ['/api/research/runtime', { connected: true, credential_configured: true, provider: 'test', model: 'acceptance', version: 'test' }],
  ['/api/research/models', { groups: [], failures: [] }],
  ['/api/research/workspaces', { items: [] }],
  ['/api/research/sessions?view=active', { items: [] }],
  ['/api/research/capabilities', { items: [] }],
  ['/api/research/tools', { items: [] }],
  ['/api/research/report-workflows', { items: [] }],
  ['/api/research/data/connections', { groups, sources, platform: {}, migration: {} }],
  ['/api/research/data/sources/wind/configuration', { preferred_adapter: 'auto' }],
]);

const mime = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.png': 'image/png' };

async function requestHandler(request, response) {
  try {
    const url = new URL(request.url || '/', 'http://127.0.0.1');
    const apiBody = jsonResponses.get(`${url.pathname}${url.search}`) || jsonResponses.get(url.pathname);
    if (apiBody) {
      response.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      response.end(JSON.stringify(apiBody));
      return;
    }
    const requested = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const filePath = path.resolve(uiRoot, requested);
    if (!filePath.startsWith(`${uiRoot}${path.sep}`) && filePath !== path.join(uiRoot, 'index.html')) throw new Error('unsafe static path');
    const body = await readFile(filePath);
    response.writeHead(200, { 'content-type': mime[path.extname(filePath)] || 'application/octet-stream', 'cache-control': 'no-store' });
    response.end(body);
  } catch (error) {
    response.writeHead(error?.code === 'ENOENT' ? 404 : 500, { 'content-type': 'text/plain; charset=utf-8' });
    response.end(error?.code === 'ENOENT' ? 'not found' : 'test server error');
  }
}

async function assertContained(page) {
  const metrics = await page.evaluate(() => ({
    innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    overflow: [...document.querySelectorAll('button,input,select,a')]
      .filter((element) => element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden')
      .filter((element) => { const rect = element.getBoundingClientRect(); return rect.left < -1 || rect.right > innerWidth + 1; })
      .filter((element) => {
        let parent = element.parentElement;
        while (parent) {
          const style = getComputedStyle(parent);
          if (parent.scrollWidth > parent.clientWidth && ['auto', 'scroll'].includes(style.overflowX)) return false;
          parent = parent.parentElement;
        }
        return true;
      })
      .map((element) => element.getAttribute('aria-label') || element.textContent.trim().slice(0, 40)),
  }));
  assert.ok(metrics.scrollWidth <= metrics.innerWidth, `horizontal overflow: ${JSON.stringify(metrics)}`);
  assert.deepEqual(metrics.overflow, [], 'interactive controls must remain inside the viewport');
}

async function runAcceptance() {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  const server = http.createServer((request, response) => { void requestHandler(request, response); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('mock server did not expose a TCP port');
  const origin = `http://127.0.0.1:${address.port}`;
  const { chromium } = await import(pathToFileURL(playwrightPath));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const results = [];
  try {
    for (const [width, height] of viewports) {
      const context = await browser.newContext({ viewport: { width, height }, colorScheme: 'light' });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', (error) => errors.push(`pageerror:${error.name}`));
      page.on('console', (message) => { if (message.type() === 'error') errors.push(`console:${message.text()}`); });
      page.on('response', (response) => { if (response.status() >= 400) errors.push(`http:${response.status()}:${response.url()}`); });
      await page.goto(`${origin}/#/settings/data?connection=wind`, { waitUntil: 'networkidle' });
      const workbench = page.locator('[data-connection-workbench]');
      await workbench.waitFor();
      assert.equal(await page.locator('[data-connection-card]:visible').count(), 4, 'professional tab must show only four sources');
      assert.equal(await page.locator('[data-connection-drawer]').isVisible(), true, 'Wind drawer must open from the deep link');
      await page.getByRole('tab', { name: 'API 数据源', exact: true }).click();
      assert.equal(await page.locator('[data-connection-card]:visible').count(), 6, 'API tab must show only six sources');
      assert.equal(await page.locator('[data-connection-drawer]').isVisible(), false, 'changing category must close the stale drawer');
      await page.getByRole('searchbox', { name: '搜索数据源', exact: true }).fill('Wind');
      assert.equal(await page.locator('[data-connection-card]:visible').count(), 1, 'search must span every category');
      await page.getByRole('searchbox', { name: '搜索数据源', exact: true }).fill('');
      await page.getByRole('combobox', { name: '筛选连接状态', exact: true }).selectOption('attention');
      assert.equal(await page.locator('[data-connection-card]:visible').count(), 5, 'status filter must refine the active API category');
      await page.getByRole('combobox', { name: '筛选连接状态', exact: true }).selectOption('all');
      const professional = page.getByRole('tab', { name: '专业数据源', exact: true });
      await professional.click();
      await professional.focus();
      await professional.press('ArrowRight');
      assert.equal(await page.getByRole('tab', { name: 'API 数据源', exact: true }).getAttribute('aria-selected'), 'true', 'arrow keys must move between category tabs');
      await professional.click();
      await page.locator('[data-connection-select="wind"]').click();
      await page.locator('[data-connection-drawer]').waitFor();
      await page.locator('#connection-title').press('Escape');
      assert.equal(await page.locator('[data-connection-drawer]').isVisible(), false, 'Escape must close the drawer');
      await page.locator('[data-connection-select="wind"]').click();
      await page.getByRole('button', { name: '关闭数据源详情', exact: true }).click();
      assert.equal(await page.locator('[data-connection-drawer]').isVisible(), false, 'close button must close the drawer');
      const configurationLoaded = page.waitForResponse((response) => response.url().endsWith('/api/research/data/sources/wind/configuration') && response.ok());
      await page.locator('[data-connection-select="wind"]').click();
      await configurationLoaded;
      await page.locator('[data-connection-drawer]').waitFor();
      await assertContained(page);
      assert.deepEqual(errors, [], `browser errors at ${width}x${height}`);
      await page.locator('#main').evaluate((element) => { element.scrollTop = 0; });
      const screenshot = path.join(outputRoot, `settings-data-${width}x${height}.png`);
      await page.screenshot({ path: screenshot, fullPage: true });
      results.push({ width, height, status: 'passed', screenshot: path.relative(projectRoot, screenshot) });
      await context.close();
    }
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
  return { status: 'passed', origin, results };
}

try {
  const receipt = await runAcceptance();
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'connection_workbench_acceptance', status: 'passed', checks: receipt.results.length })}\n`);
  console.log(`connection workbench: ${receipt.results.length} viewport checks passed`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify({ status: 'failed', error: error.message }, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'connection_workbench_acceptance', status: 'failed', error_type: error.name })}\n`);
  console.error(error.message);
  process.exitCode = 1;
}
