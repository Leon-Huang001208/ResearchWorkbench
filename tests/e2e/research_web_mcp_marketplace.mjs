/** Read-only browser acceptance for the Tool MCP Registry marketplace. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.resolve(process.env.RWB_MCP_MARKET_OUTPUT || path.join(projectRoot, 'outputs/research-web-mcp-marketplace'));
const logPath = path.resolve(process.env.RWB_MCP_MARKET_LOG || path.join(projectRoot, 'logs/research-web-mcp-marketplace.jsonl'));
const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const viewports = [[1440, 1000], [1280, 960], [768, 1024], [390, 844]];
const themes = ['light', 'dark'];
const writes = [];

const registries = [
  { id: 'official', name: 'Official Registry', base_url: 'https://registry.modelcontextprotocol.io', official: true, immutable: true, auth: { type: 'none', secret_configured: false } },
  { id: 'local-private', name: 'Private Research Registry', base_url: 'https://registry.example.invalid', official: false, immutable: false, auth: { type: 'bearer', secret_configured: true } },
];
const servers = [
  {
    registry_id: 'official', name: 'io.modelcontextprotocol/equity-reader', version: '1.2.3',
    identity: ['official', 'io.modelcontextprotocol/equity-reader', '1.2.3'], title: 'Equity Filing Reader',
    description: '只读解析已审查的公司披露。', repository: { url: 'https://example.invalid/equity-reader' },
    packages: [{ registryType: 'npm', identifier: '@example/equity-reader', version: '1.2.3' }],
    remotes: [], status: 'active', is_latest: true,
  },
  {
    registry_id: 'official', name: 'io.example/future-transport', version: '2026.9.1',
    identity: ['official', 'io.example/future-transport', '2026.9.1'], title: 'Future Transport Catalog',
    description: '<img src=x onerror=alert(1)> 保持为纯文本。', repository: { url: 'https://example.invalid/future' },
    packages: [{ registryType: 'future-package', identifier: '<future-package>', version: '2026.9.1' }],
    remotes: [{ type: 'streamable-http', url: 'https://example.invalid/mcp' }], status: 'active', is_latest: true,
  },
];

const mime = {
  '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8', '.png': 'image/png', '.svg': 'image/svg+xml',
};

function apiPayload(url) {
  if (url.pathname === '/api/research/runtime') return { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture' };
  if (url.pathname === '/api/research/models') return { groups: [], failures: [] };
  if (url.pathname === '/api/research/mcp/registries') return { items: registries };
  if (url.pathname === '/api/research/mcp/servers') {
    const query = String(url.searchParams.get('search') || '').toLocaleLowerCase();
    const items = query ? servers.filter((item) => `${item.name} ${item.title} ${item.description}`.toLocaleLowerCase().includes(query)) : servers;
    return { registry_id: 'official', items, cursor: null, next_cursor: null, count: items.length, fetched_at: '2026-09-10T08:00:00Z', stale: true, failure_code: 'registry_timeout' };
  }
  if (url.pathname.startsWith('/api/research/mcp/servers/') && url.pathname.includes('/versions/')) {
    const item = url.pathname.includes('future-transport') ? servers[1] : servers[0];
    return { ...item, fetched_at: '2026-09-10T08:00:00Z', stale: true, failure_code: 'registry_timeout' };
  }
  if (url.pathname === '/api/research/data/catalog') return { summary: {}, capabilities: [], sources: [], bindings: [] };
  if (url.pathname === '/api/research/data/connections') return { groups: [], sources: [], platform: {}, migration: {} };
  return { items: [] };
}

async function requestHandler(request, response) {
  try {
    const url = new URL(request.url || '/', 'http://127.0.0.1');
    if (!['GET', 'HEAD'].includes(request.method || 'GET')) {
      writes.push(request.method || 'UNKNOWN');
      response.writeHead(405, { 'content-type': 'application/json; charset=utf-8' });
      response.end(JSON.stringify({ error: { code: 'read_only_fixture', message: '只读验收禁止写操作' } }));
      return;
    }
    if (url.pathname.startsWith('/api/research/')) {
      response.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      response.end(JSON.stringify(apiPayload(url)));
      return;
    }
    const requested = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const filePath = path.resolve(uiRoot, requested);
    if (filePath !== path.join(uiRoot, 'index.html') && !filePath.startsWith(`${uiRoot}${path.sep}`)) throw new Error('unsafe static path');
    const body = await readFile(filePath);
    response.writeHead(200, { 'content-type': mime[path.extname(filePath)] || 'application/octet-stream', 'cache-control': 'no-store' });
    response.end(body);
  } catch (error) {
    response.writeHead(error?.code === 'ENOENT' ? 404 : 500, { 'content-type': 'text/plain; charset=utf-8' });
    response.end(error?.code === 'ENOENT' ? 'not found' : 'test server error');
  }
}

async function assertContained(page, expectedColumns) {
  const metrics = await page.evaluate(() => ({
    innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth,
    columns: getComputedStyle(document.querySelector('.mcp-market-grid')).gridTemplateColumns.split(' ').length,
  }));
  assert.ok(metrics.scrollWidth <= metrics.innerWidth, `page horizontal overflow: ${JSON.stringify(metrics)}`);
  assert.equal(metrics.mainOverflow, false, `main horizontal overflow: ${JSON.stringify(metrics)}`);
  assert.equal(metrics.columns, expectedColumns, `unexpected card columns: ${JSON.stringify(metrics)}`);
  return metrics;
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
    for (const theme of themes) {
      for (const [width, height] of viewports) {
        const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme, reducedMotion: 'reduce' });
        await context.addInitScript((value) => localStorage.setItem('research-web.appearance.v1', value), theme);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', (error) => errors.push(`pageerror:${error.name}`));
        page.on('console', (message) => { if (message.type() === 'error') errors.push('console:error'); });
        page.on('response', (item) => { if (item.status() >= 400) errors.push(`http:${item.status()}`); });
        await page.goto(`${origin}/#/skills?kind=tool&view=market`, { waitUntil: 'networkidle' });
        await page.getByRole('heading', { name: 'MCP 市场', exact: true }).waitFor();
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        assert.equal(await page.getByRole('tab', { name: 'MCP 市场', exact: true }).getAttribute('aria-selected'), 'true', 'MCP market tab must be selected');
        assert.equal(await page.getByRole('combobox', { name: 'Registry', exact: true }).inputValue(), 'official');
        assert.equal(await page.locator('.mcp-server-card').count(), 2);
        assert.equal(await page.getByText('正在显示离线缓存', { exact: false }).count(), 1);
        assert.equal(await page.getByText('当前不可安装', { exact: true }).count(), 1);
        assert.equal(await page.locator('.mcp-server-card img, .mcp-server-card script').count(), 0);
        const expectedColumns = width >= 1400 ? 4 : width <= 600 ? 1 : width <= 1100 ? 2 : 3;
        const metrics = await assertContained(page, expectedColumns);
        if (theme === 'light' && width === 1440) {
          await page.getByRole('searchbox', { name: '搜索 MCP Server', exact: true }).fill('equity');
          await page.getByRole('button', { name: '搜索', exact: true }).click();
          await page.waitForFunction(() => document.querySelectorAll('.mcp-server-card').length === 1);
          assert.equal(await page.getByRole('heading', { name: 'Equity Filing Reader', exact: true }).count(), 1);
          await page.getByRole('searchbox', { name: '搜索 MCP Server', exact: true }).fill('');
          await page.getByRole('button', { name: '搜索', exact: true }).click();
          await page.waitForFunction(() => document.querySelectorAll('.mcp-server-card').length === 2);
          const trigger = page.getByRole('button', { name: '查看详情', exact: true }).first();
          await trigger.focus(); await trigger.click();
          await page.getByRole('dialog', { name: 'Equity Filing Reader', exact: true }).waitFor();
          assert.equal(await page.getByText('正在显示详情离线缓存', { exact: false }).count(), 1);
          await page.keyboard.press('Escape');
          await page.getByRole('dialog').waitFor({ state: 'detached' });
          assert.equal(await trigger.evaluate((element) => element === document.activeElement), true, 'Escape must restore card focus');
          await trigger.click();
          await page.locator('[data-mcp-dialog-backdrop]').click({ position: { x: 5, y: 5 } });
          await page.getByRole('dialog').waitFor({ state: 'detached' });
          assert.equal(await trigger.evaluate((element) => element === document.activeElement), true, 'backdrop must restore card focus');
          const transition = await page.locator('.mcp-server-card').first().evaluate((element) => getComputedStyle(element).transitionDuration);
          assert.ok(transition.split(',').every((value) => Number.parseFloat(value) === 0), `reduced motion transition remains: ${transition}`);
          await page.goto(`${origin}/#/skills?kind=skill&view=market`, { waitUntil: 'networkidle' });
          await page.locator('#capability-kind-skill[aria-selected="true"]').waitFor();
          assert.equal(await page.getByRole('tab', { name: 'Skill', exact: true }).getAttribute('aria-selected'), 'true', 'invalid cross-kind market route must select Skill');
          assert.equal(await page.getByRole('heading', { name: 'MCP 市场', exact: true }).count(), 0);
          await page.goto(`${origin}/#/skills?kind=tool&view=market`, { waitUntil: 'networkidle' });
          await page.getByRole('heading', { name: 'MCP 市场', exact: true }).waitFor();
        }
        assert.deepEqual(errors, [], `browser errors at ${theme} ${width}x${height}`);
        const screenshot = path.join(outputRoot, `${theme}-${width}x${height}.png`);
        await page.screenshot({ path: screenshot, fullPage: true });
        results.push({ theme, width, height, status: 'passed', screenshot: path.relative(projectRoot, screenshot), metrics });
        await context.close();
      }
    }
  } finally {
    await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
  assert.deepEqual(writes, [], 'browser acceptance must not issue writes, installs, syncs, or publisher execution');
  return {
    status: 'passed',
    readOnly: true,
    writeRequestCount: writes.length,
    forbiddenActionsObserved: { install: 0, publisherExecution: 0, registryMutation: 0 },
    interactions: {
      canonicalRoute: true, typeIsolation: true, registrySelector: true, search: true,
      staleOfflineCache: true, supportedAndUnknownPackages: true, thirdPartyTextOnly: true,
      detailDialog: true, escapeClose: true, backdropClose: true, focusRestore: true,
      reducedMotion: true, consoleErrors: 0, pageErrors: 0, failedResponses: 0,
    },
    checks: results.length,
    results,
  };
}

try {
  const receipt = await runAcceptance();
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'mcp_marketplace_acceptance', status: 'passed', checks: receipt.checks, write_request_count: receipt.writeRequestCount })}\n`);
  console.log(`MCP marketplace: ${receipt.checks} viewport/theme checks passed; 0 writes`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify({ status: 'failed', error_type: error.name, writeRequestCount: writes.length }, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'mcp_marketplace_acceptance', status: 'failed', error_type: error.name, write_request_count: writes.length })}\n`);
  console.error(error.message);
  process.exitCode = 1;
}
