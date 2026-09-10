/** Browser acceptance for the gated MCP installation and Runtime lifecycle. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.resolve(process.env.RWB_MCP_RUNTIME_OUTPUT || path.join(projectRoot, 'outputs/research-web-mcp-runtime'));
const logPath = path.resolve(process.env.RWB_MCP_RUNTIME_LOG || path.join(projectRoot, 'logs/research-web-mcp-runtime.jsonl'));
const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const viewports = [[1440, 1000], [1280, 960], [768, 1024], [390, 844]];
const themes = ['light', 'dark'];
const installationId = `mcp-installation-${'7'.repeat(32)}`;
const schemaSha = '8'.repeat(64);
const summarySha = '9'.repeat(64);
const writes = [];
let installed = false;
let enabled = false;

const serverRecord = {
  registry_id: 'official', name: 'io.example/research-reader', version: '1.2.3',
  identity: ['official', 'io.example/research-reader', '1.2.3'], title: 'Research Reader',
  description: '只读研究资料连接器。', repository: { url: 'https://example.invalid/research-reader' },
  packages: [],
  remotes: [{ type: 'streamable-http', url: 'https://mcp.example.invalid/runtime' }],
  status: 'active', is_latest: true,
};

const plan = {
  target_kind: 'remote', registry_id: 'official', server_name: serverRecord.name,
  server_version: serverRecord.version, endpoint: serverRecord.remotes[0].url,
  transport: 'streamable-http', argv: [], install_argv: [], environment_names: [],
  artifacts: [], canonical_summary: { endpoint: serverRecord.remotes[0].url },
  summary_sha256: summarySha,
};

function installationRecord(status = enabled ? 'enabled' : 'ready') {
  return { id: installationId, plan, runtime_status: status, active: enabled };
}

const mime = {
  '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.png': 'image/png', '.svg': 'image/svg+xml',
};

async function bodyOf(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  return chunks.length ? JSON.parse(Buffer.concat(chunks).toString('utf8')) : null;
}

function reply(response, status, value) {
  response.writeHead(status, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
  response.end(JSON.stringify(value));
}

async function apiResponse(request, response, url) {
  const method = request.method || 'GET';
  const pathname = url.pathname;
  if (method === 'GET' && pathname === '/api/research/runtime') return reply(response, 200, { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture' });
  if (method === 'GET' && pathname === '/api/research/models') return reply(response, 200, { groups: [], failures: [] });
  if (method === 'GET' && pathname === '/api/research/mcp/registries') return reply(response, 200, { items: [{ id: 'official', name: 'Official Registry', official: true, immutable: true, auth: { type: 'none' } }] });
  if (method === 'GET' && pathname === '/api/research/mcp/servers') return reply(response, 200, { registry_id: 'official', items: [serverRecord], count: 1, next_cursor: null, fetched_at: '2026-09-11T00:00:00Z', stale: false });
  if (method === 'GET' && pathname.includes('/api/research/mcp/servers/') && pathname.includes('/versions/')) return reply(response, 200, serverRecord);
  if (method === 'GET' && pathname === '/api/research/mcp/installations') return reply(response, 200, { items: installed ? [installationRecord()] : [] });
  if (method === 'GET' && pathname === '/api/research/mcp/approvals') return reply(response, 200, { items: [{ id: 'approval-fixture', session_id: 'session-fixture', installation_id: installationId, version: '1.2.3', tool_name: 'write_external', status: 'pending' }] });
  if (method === 'GET' && pathname.endsWith('/capabilities')) return reply(response, 200, { tools: [{ name: 'search', description: '只读检索', schema_sha256: schemaSha, risk_tier: 'external_write_high_risk', allow_unattended: false }] });
  if (method === 'POST' && pathname === '/api/research/mcp/installations/preview') {
    const body = await bodyOf(request); writes.push({ method, pathname, body });
    return reply(response, 200, { plan, confirmation_token: 'confirmation-token-fixture' });
  }
  if (method === 'POST' && pathname === '/api/research/mcp/installations') {
    const body = await bodyOf(request); writes.push({ method, pathname, body }); installed = true;
    return reply(response, 201, { installation: installationRecord('installed') });
  }
  if (method === 'POST' && pathname.endsWith('/probe')) {
    writes.push({ method, pathname, body: await bodyOf(request) });
    return reply(response, 200, { tools: [{ name: 'search', description: '只读检索', schema_sha256: schemaSha, risk_tier: 'external_write_high_risk', allow_unattended: false }] });
  }
  if (method === 'POST' && pathname.endsWith('/enable')) {
    writes.push({ method, pathname, body: await bodyOf(request) }); enabled = true;
    return reply(response, 200, { status: 'enabled', active: true });
  }
  if (method === 'POST' && pathname.endsWith('/disable')) {
    writes.push({ method, pathname, body: await bodyOf(request) }); enabled = false;
    return reply(response, 200, { status: 'disabled', active: false });
  }
  if (method === 'PATCH' && pathname === `/api/research/mcp/installations/${installationId}`) {
    const body = await bodyOf(request); writes.push({ method, pathname, body });
    return reply(response, 200, { ...body, schema_sha256: schemaSha });
  }
  if (method === 'DELETE' && pathname === `/api/research/mcp/installations/${installationId}`) {
    writes.push({ method, pathname, body: null }); installed = false;
    return reply(response, 200, { status: 'deleted', id: installationId });
  }
  if (method === 'POST' && pathname === '/api/research/mcp/approvals/approval-fixture/deny') {
    const body = await bodyOf(request); writes.push({ method, pathname, body });
    return reply(response, 200, { id: 'approval-fixture', session_id: 'session-fixture', status: 'denied' });
  }
  if (method === 'GET' && pathname === '/api/research/data/catalog') return reply(response, 200, { summary: {}, capabilities: [], sources: [], bindings: [] });
  if (method === 'GET' && pathname === '/api/research/data/connections') return reply(response, 200, { groups: [], sources: [], platform: {}, migration: {} });
  return reply(response, 200, { items: [] });
}

async function requestHandler(request, response) {
  try {
    const url = new URL(request.url || '/', 'http://127.0.0.1');
    if (url.pathname.startsWith('/api/research/')) return await apiResponse(request, response, url);
    const requested = url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, '');
    const filePath = path.resolve(uiRoot, requested);
    if (filePath !== path.join(uiRoot, 'index.html') && !filePath.startsWith(`${uiRoot}${path.sep}`)) throw new Error('unsafe static path');
    const body = await readFile(filePath);
    response.writeHead(200, { 'content-type': mime[path.extname(filePath)] || 'application/octet-stream', 'cache-control': 'no-store' });
    response.end(body);
  } catch (error) {
    reply(response, 500, { error: { code: 'fixture_failed', message: error?.name || 'Error' } });
  }
}

async function assertContained(page) {
  const metrics = await page.evaluate(() => ({ innerWidth, scrollWidth: document.documentElement.scrollWidth, mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth }));
  assert.ok(metrics.scrollWidth <= metrics.innerWidth, `page overflow: ${JSON.stringify(metrics)}`);
  assert.equal(metrics.mainOverflow, false, `main overflow: ${JSON.stringify(metrics)}`);
  return metrics;
}

async function runAcceptance() {
  await mkdir(outputRoot, { recursive: true }); await mkdir(path.dirname(logPath), { recursive: true });
  const server = http.createServer((request, response) => { void requestHandler(request, response); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const address = server.address(); if (!address || typeof address === 'string') throw new Error('fixture port unavailable');
  const origin = `http://127.0.0.1:${address.port}`;
  const { chromium } = await import(pathToFileURL(playwrightPath));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const results = [];
  try {
    for (const theme of themes) {
      for (const [width, height] of viewports) {
        const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme, reducedMotion: 'reduce' });
        await context.addInitScript((value) => localStorage.setItem('research-web.appearance.v1', value), theme);
        const page = await context.newPage(); const errors = [];
        page.on('pageerror', (error) => errors.push(`pageerror:${error.name}`));
        page.on('console', (message) => { if (message.type() === 'error') errors.push('console:error'); });
        page.on('response', (item) => { if (item.status() >= 400) errors.push(`http:${item.status()}`); });
        await page.goto(`${origin}/#/skills?kind=tool&view=market`, { waitUntil: 'networkidle' });
        await page.getByRole('heading', { name: 'MCP 市场', exact: true }).waitFor();
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        assert.equal(await page.getByText('Runtime 管理已就绪', { exact: false }).count(), 1);
        const metrics = await assertContained(page);
        if (theme === 'light' && width === 1440) {
          assert.equal(await page.getByText('参数正文不会在此显示。', { exact: false }).count(), 1);
          await page.getByRole('button', { name: '拒绝', exact: true }).click();
          await page.getByText('待处理高风险调用', { exact: true }).waitFor({ state: 'detached' });
          await page.getByRole('button', { name: '查看详情', exact: true }).click();
          await page.getByRole('radio', { name: '远程 Streamable HTTP', exact: false }).check();
          await page.getByRole('button', { name: '生成完整安装预览', exact: true }).click();
          await page.getByRole('heading', { name: '核对完整安装摘要', exact: true }).waitFor();
          assert.equal(await page.getByText(summarySha, { exact: true }).count(), 1);
          assert.equal(await page.getByText('远程目标不执行本地安装命令', { exact: true }).count(), 1);
          await page.getByRole('button', { name: '确认并安装', exact: true }).click();
          await page.getByText('请先勾选二次确认', { exact: false }).waitFor();
          await page.getByRole('checkbox', { name: '我已核对完整命令', exact: false }).check();
          await page.getByRole('button', { name: '确认并安装', exact: true }).click();
          await page.getByText('安装记录已保存。', { exact: false }).waitFor();
          await page.getByRole('button', { name: '运行健康探测', exact: true }).click();
          await page.getByRole('heading', { name: '工具风险与当前会话授权', exact: true }).waitFor();
          await page.getByRole('button', { name: '启用 Runtime', exact: true }).click();
          await page.getByRole('button', { name: '停用 Runtime', exact: true }).waitFor();
          await page.getByRole('combobox', { name: '风险等级', exact: true }).selectOption('read_only');
          await page.getByRole('checkbox', { name: '允许无人值守只读调用', exact: true }).check();
          await page.getByRole('button', { name: '保存分级', exact: true }).click();
          await page.getByRole('button', { name: '停用 Runtime', exact: true }).click();
          page.once('dialog', (dialog) => dialog.accept());
          await page.getByRole('button', { name: '移除安装', exact: true }).click();
          await page.getByRole('radio', { name: '远程 Streamable HTTP', exact: false }).waitFor();
        }
        const transition = await page.locator('.mcp-server-card').first().evaluate((element) => getComputedStyle(element).transitionDuration);
        assert.ok(transition.split(',').every((value) => Number.parseFloat(value) === 0), `reduced motion remains: ${transition}`);
        assert.deepEqual(errors, [], `browser errors at ${theme} ${width}x${height}`);
        const screenshot = path.join(outputRoot, `${theme}-${width}x${height}.png`);
        await page.screenshot({ path: screenshot, fullPage: true });
        results.push({ theme, width, height, status: 'passed', screenshot: path.relative(projectRoot, screenshot), metrics });
        await context.close();
      }
    }
  } finally { await browser.close(); await new Promise((resolve) => server.close(resolve)); }
  const installWrite = writes.find((item) => item.pathname === '/api/research/mcp/installations');
  assert.deepEqual(installWrite?.body, { confirmation_token: 'confirmation-token-fixture', environment_values: {} });
  assert.ok(writes.some((item) => item.pathname.endsWith('/probe')));
  assert.ok(writes.some((item) => item.pathname.endsWith('/enable')));
  assert.ok(writes.some((item) => item.method === 'PATCH' && item.body?.risk_tier === 'read_only' && item.body?.allow_unattended === true));
  assert.ok(writes.some((item) => item.pathname.endsWith('/disable')));
  assert.ok(writes.some((item) => item.method === 'DELETE'));
  assert.ok(writes.some((item) => item.pathname.endsWith('/deny') && item.body?.session_id === 'session-fixture'));
  return { status: 'passed', checks: results.length, results, lifecycle: ['preview', 'confirm', 'install', 'probe', 'enable', 'classify', 'disable', 'remove'], approvalDecision: 'denied', secretValuesRecorded: false };
}

try {
  const receipt = await runAcceptance();
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'mcp_runtime_acceptance', status: 'passed', checks: receipt.checks })}\n`);
  console.log(`MCP runtime: ${receipt.checks} viewport/theme checks and full lifecycle passed`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true }); await mkdir(path.dirname(logPath), { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify({ status: 'failed', error_type: error?.name || 'Error' }, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'mcp_runtime_acceptance', status: 'failed', error_type: error?.name || 'Error' })}\n`);
  console.error(error?.message || 'runtime acceptance failed'); process.exitCode = 1;
}
