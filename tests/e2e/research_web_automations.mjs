/** Browser acceptance for version-locked Automation plans and delivery isolation. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const projectRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.resolve(process.env.RWB_AUTOMATION_OUTPUT || path.join(projectRoot, '.ai/reports/evidence/research-web-automations'));
const logPath = path.resolve(process.env.RWB_AUTOMATION_LOG || path.join(projectRoot, 'logs/research-web-automations.jsonl'));
const playwrightPath = process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs';
const viewports = [[1440, 1000], [1280, 960], [768, 1024], [390, 844]];
const themes = ['light', 'dark'];
const writes = [];

const capability = {
  id: 'company-research', kind: 'workflow', name: '公司研究', description: '锁定资料口径的公司研究流程。',
  category: '公司', status: 'enabled', enabled: true, version: 2, builtin: true,
  metadata: { default_formats: ['md', 'docx'], inputs: [], scenarios: [], required_tools: [], dependencies: [] },
};
const reportWorkflow = {
  id: 'weekly-report', name: '投研周报', description: '旧报告日程兼容入口。', status: 'enabled',
  current_version: 3, next_run_at: '2026-09-18T10:00:00+00:00', delivery_formats: ['docx'],
};
const automation = {
  id: 'automation-1', name: '每日公司研究', enabled: true, next_run_at: '2026-09-12T01:00:00+00:00',
  target: { kind: 'workflow', id: 'company-research', version: 2, sha256: 'a'.repeat(64) },
  schedule: { kind: 'daily', timezone: 'Asia/Shanghai', hour: 9, minute: 0 },
  delivery: { channel_ids: ['delivery-1'], include_attachments: false }, last_run_id: 'run-failed',
};
const failedRun = {
  id: 'run-failed', automation_id: 'automation-1', research_status: 'failed', delivery_status: 'not_requested',
  scheduled_for: '2026-09-11T01:00:00+00:00', created_at: 1789078800,
};
const channel = { id: 'delivery-1', name: '研究通知', kind: 'webhook', enabled: true, configured: true };
const mime = { '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8', '.svg': 'image/svg+xml' };

function payload(url) {
  if (url.pathname === '/api/research/runtime') return { connected: true, credential_configured: true, provider: 'fixture', model: 'fixture' };
  if (url.pathname === '/api/research/models') return { groups: [], failures: [] };
  if (url.pathname === '/api/research/capabilities') return { items: [capability] };
  if (url.pathname === '/api/research/report-workflows') return { items: [reportWorkflow] };
  if (url.pathname === '/api/research/automations') return { items: [automation] };
  if (url.pathname === '/api/research/automation-runs') return { items: [failedRun] };
  if (url.pathname === '/api/research/delivery-channels') return { items: [channel] };
  if (url.pathname === '/api/research/data/catalog') return { summary: {}, capabilities: [], sources: [], bindings: [] };
  if (url.pathname === '/api/research/data/connections') return { groups: [], sources: [], platform: {}, migration: {} };
  return { items: [] };
}

async function handler(request, response) {
  try {
    const url = new URL(request.url || '/', 'http://127.0.0.1');
    if (url.pathname.startsWith('/api/research/')) {
      if (!['GET', 'HEAD'].includes(request.method || 'GET')) {
        writes.push({ method: request.method, path: url.pathname });
        if (url.pathname.endsWith('/retry')) {
          response.writeHead(202, { 'content-type': 'application/json; charset=utf-8' });
          response.end(JSON.stringify({ ...failedRun, id: 'run-retry', retry_of: 'run-failed', research_status: 'queued' }));
          return;
        }
      }
      response.writeHead(200, { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' });
      response.end(JSON.stringify(payload(url)));
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

async function acceptance() {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  const server = http.createServer((request, response) => { void handler(request, response); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('fixture port unavailable');
  const { chromium } = await import(pathToFileURL(playwrightPath));
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const results = [];
  try {
    for (const theme of themes) {
      for (const [width, height] of viewports) {
        const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme, reducedMotion: 'reduce' });
        await context.addInitScript(value => localStorage.setItem('research-web.appearance.v1', value), theme);
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(`pageerror:${error.name}`));
        page.on('console', message => { if (message.type() === 'error') errors.push('console:error'); });
        page.on('response', item => { if (item.status() >= 400) errors.push(`http:${item.status()}`); });
        await page.goto(`http://127.0.0.1:${address.port}/#/skills?kind=workflow&view=plans`, { waitUntil: 'networkidle' });
        await page.getByRole('heading', { name: '运行计划', exact: true }).waitFor();
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        assert.equal(await page.getByRole('tab', { name: 'Workflow', exact: true }).getAttribute('aria-selected'), 'true');
        assert.equal(await page.getByRole('heading', { name: '每日公司研究', exact: true }).count(), 1);
        assert.equal(await page.getByText('失败', { exact: true }).count() > 0, true);
        assert.equal(await page.getByText('旧报告日程', { exact: true }).count(), 1);
        const metrics = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth, mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth }));
        assert.ok(metrics.scrollWidth <= metrics.width, `horizontal overflow: ${JSON.stringify(metrics)}`);
        assert.equal(metrics.mainOverflow, false, `main overflow: ${JSON.stringify(metrics)}`);
        const transition = await page.locator('.capability-plan-list article').first().evaluate(element => getComputedStyle(element).transitionDuration);
        assert.ok(transition.split(',').every(value => Number.parseFloat(value) === 0), `reduced motion transition remains: ${transition}`);
        if (theme === 'light' && width === 1440) {
          await page.getByRole('button', { name: '新建计划', exact: true }).click();
          await page.getByRole('heading', { name: '新建 Automation', exact: true }).waitFor();
          assert.equal(await page.getByLabel('锁定能力').inputValue(), 'workflow|company-research|2');
          await page.getByRole('button', { name: '取消', exact: true }).click();
          await page.getByRole('button', { name: '手动重试', exact: true }).click();
          await page.getByText('已创建关联原运行记录的手动重试。', { exact: true }).waitFor();
          await page.getByText('配置外发渠道', { exact: true }).click();
          assert.equal(await page.getByLabel('密码 / 签名秘密').getAttribute('autocomplete'), 'new-password');
        }
        assert.deepEqual(errors, [], `browser errors at ${theme} ${width}x${height}`);
        const screenshot = path.join(outputRoot, `${theme}-${width}x${height}.png`);
        await page.screenshot({ path: screenshot, fullPage: true });
        results.push({ theme, width, height, screenshot: path.relative(projectRoot, screenshot), metrics });
        await context.close();
      }
    }
  } finally {
    await browser.close();
    await new Promise(resolve => server.close(resolve));
  }
  assert.deepEqual(writes, [{ method: 'POST', path: '/api/research/automation-runs/run-failed/retry' }]);
  return { status: 'passed', checks: results.length, writes, interactions: { versionLock: true, retry: true, deliverySecretMasked: true, legacySchedule: true, reducedMotion: true }, results };
}

try {
  const receipt = await acceptance();
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify(receipt, null, 2)}\n`);
  await appendFile(logPath, `${JSON.stringify({ event: 'research_web_automation_acceptance', status: 'passed', checks: receipt.checks })}\n`);
  console.log(`Research Web Automation: ${receipt.checks} viewport/theme checks passed`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), `${JSON.stringify({ status: 'failed', error_type: error.name, writes }, null, 2)}\n`);
  console.error(error.message);
  process.exitCode = 1;
}
