/** Offline UI fixtures only. No supplier, model, deployment or real account access. */
import assert from 'node:assert/strict';
import http from 'node:http';
import path from 'node:path';
import { mkdir, readFile, writeFile, appendFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'outputs/research-web-dossiers');
const log = path.join(project, 'logs/research-web-dossiers-ui.jsonl');
const id = '11111111-1111-4111-8111-111111111111';
const evidenceID = 'evidence-fixture';
const targetSessionID = '22222222-2222-4222-8222-222222222222';
let fixtureSession = null;
const base = () => ({ id, title: '离线夹具 · 公司长期研究档案', revision: 3, archived: false, updated_at: '2026-10-23T08:00:00+08:00', subject: { kind: 'company', key: '600519.SH', label: '离线公司 · 非真实研究' }, tracking: { enabled: false, eligible: false, reason: '尚未完成手动闭环' }, records: [{ id: 'view', record_id: 'view', kind: 'opinion', title: '离线初始判断', body: '核心假设待验证。' + '长文本内容用于换行检查'.repeat(24), reason: '离线测试原始记录', state: 'open', evidence_ids: [evidenceID] }], evidence: [{ id: evidenceID, title: '离线证据快照', source: 'offline-fixture', sha256: 'a'.repeat(64), retrieved_at: '2026-10-23T08:00:00+08:00', published_at: null, locator: '表格第一行' }], links: [{ id: 'result', title: '离线报告', quality_status: 'incomplete', source_session_id: id, type: 'report' }] });
let dossier = base(), conflict = false, revoked = false;
const requests = [], unexpected = [], expectedHTTPFailures = [], results = [];
const types = { '.mjs': 'text/javascript', '.js': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.html': 'text/html', '.png': 'image/png', '.svg': 'image/svg+xml' };
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://127.0.0.1');
    if (url.pathname.startsWith('/api/')) {
      const chunks = []; for await (const chunk of request) chunks.push(chunk);
      const body = chunks.length ? JSON.parse(Buffer.concat(chunks)) : {};
      requests.push({ path: url.pathname, method: request.method, body });
      let data = { items: [] }, status = 200;
      const prefix = `/api/research/dossiers/${id}`;
      if (url.pathname === '/api/research/runtime') data = { connected: true, credential_configured: true, provider: 'offline-fixture', model: 'offline-fixture', version: 'fixture', mode: 'native' };
      else if (url.pathname === '/api/research/sessions' && request.method === 'POST') { assert.equal(body.dossier_handoff_id, 'c'.repeat(32)); fixtureSession = { id: targetSessionID, mode: body.mode, title: '离线研究会话', status: 'ready', messages: [] }; data = fixtureSession; }
      else if (url.pathname === `/api/research/sessions/${targetSessionID}`) data = fixtureSession;
      else if (url.pathname === `/api/research/sessions/${targetSessionID}/messages`) { assert.equal(body.dossier_handoff_id, 'c'.repeat(32)); data = { accepted: true }; }
      else if (url.pathname.endsWith('/models')) data = { groups: [], failures: [] };
      else if (url.pathname.endsWith('/navigation')) data = { mode: 'claw', revision: 1, pinned: [], project_order: [] };
      else if (url.pathname === '/api/research/dossiers') data = { items: [dossier], next_cursor: null };
      else if (url.pathname === '/api/research/dossiers/signals') data = { items: [{ id: 'signal', dossier_id: id, title: '离线风险信号', body: '<img src=x onerror=window.fixtureXss=true> 标签作为文本显示', kind: 'risk', state: 'open', evidence_ids: [evidenceID], source: 'offline-fixture', as_of: '2026-10-23', coverage: '仅离线样本', missing: ['盈利预测缺失'], stale: true }], coverage: '仅离线样本', missing: ['无真实供应商数据'] };
      else if (url.pathname === prefix && request.method === 'GET') data = dossier;
      else if (url.pathname === `${prefix}/timeline`) data = { items: dossier.records, next_cursor: null };
      else if (url.pathname === `${prefix}/records`) {
        if (conflict) { status = 409; data = { error: { code: 'revision_conflict', message: '版本已变化' } }; }
        else { assert.equal(body.expected_revision, dossier.revision); assert.ok(body.idempotency_key); dossier.revision++; dossier.records.push({ ...body, id: `record-${dossier.revision}`, revision: dossier.revision }); data = dossier; }
      } else if (url.pathname === `${prefix}/evidence/${evidenceID}`) {
        if (revoked) { status = 403; data = { error: { code: 'evidence_permission_revoked', message: '证据来源已撤权' } }; }
        else data = { content: '离线原始证据\n<script>window.fixtureXss=true</script>', sha256: 'a'.repeat(64) };
      } else if (url.pathname === `${prefix}/scan`) { dossier.revision++; data = { dossier, signals: [], coverage: '仅离线样本', missing: ['盈利预测缺失'] }; }
      else if (url.pathname === `${prefix}/handoff`) {
        assert.equal(body.expected_revision, dossier.revision); const revision = dossier.revision++;
        data = { mode: body.mode, prompt: `离线冻结档案 v${revision}，证据句柄 dossier:${evidenceID}；请核验后研究。`, auto_send: false, dossier_revision: dossier.revision, context: { handoff_id: 'c'.repeat(32), dossier_id: id, revision, evidence_handles: [`dossier:${evidenceID}`], sha256: 'b'.repeat(64) } };
      }
      response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(data)); return;
    }
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.startsWith('/static/') ? url.pathname.slice(8) : null;
    const root = path.join(project, 'app/research_web/ui'), target = relative && path.resolve(root, relative);
    if (!target || !target.startsWith(`${root}${path.sep}`)) { response.writeHead(404); response.end('Not found'); return; }
    const content = await readFile(target); response.writeHead(200, { 'Content-Type': `${types[path.extname(target)] || 'application/octet-stream'}; charset=utf-8` }); response.end(content);
  } catch (error) { unexpected.push(String(error)); response.writeHead(500); response.end('Offline fixture error'); }
});
await mkdir(output, { recursive: true }); await mkdir(path.dirname(log), { recursive: true });
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
let browser, activePage;
try {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  for (const [width, height, theme] of [[1440, 900, 'light'], [768, 1024, 'dark'], [390, 844, 'light']]) {
    dossier = base(); conflict = false; revoked = false; fixtureSession = null;
    const context = await browser.newContext({ viewport: { width, height } });
    const page = await context.newPage(); activePage = page; const errors = [];
    await page.addInitScript(() => { globalThis.EventSource = class { addEventListener() {} close() {} }; });
    page.on('pageerror', error => { errors.push(error.message); unexpected.push(error.message); });
    page.on('console', message => {
      if (message.type() !== 'error') return;
      if (/^Failed to load resource: the server responded with a status of (409 \(Conflict\)|403 \(Forbidden\))$/.test(message.text())) expectedHTTPFailures.push(message.text());
      else unexpected.push(message.text());
    });
    page.on('requestfailed', request => unexpected.push(`request_failed:${request.url()}:${request.failure()?.errorText}`));
    await page.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort('blockedbyclient'));
    await page.goto(`${origin}/#/assets?view=dossiers&dossier=${id}`, { waitUntil: 'networkidle' });
    await page.getByRole('heading', { name: dossier.title, exact: true }).waitFor();
    await assert.doesNotReject(() => page.getByRole('heading', { name: '研究成果', exact: true }).waitFor());
    await page.evaluate(value => { document.documentElement.dataset.theme = value; }, theme);
    assert.equal(await page.locator('[data-dossier-action="tracking"]').isDisabled(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    assert.equal(await page.locator('#main').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
    await page.getByRole('button', { name: '新增研究记录', exact: true }).click();
    await page.locator('#dossier-field-title').fill('离线修订 <script>');
    await page.locator('#dossier-field-body').fill('−2.0% 是下降，不得写成微增。');
    await page.locator('#dossier-field-reason').fill('离线数字符号反例');
    conflict = true;
    await page.getByRole('button', { name: '保存新版本', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '输入已保留' }).waitFor();
    assert.equal(await page.locator('#dossier-field-body').inputValue(), '−2.0% 是下降，不得写成微增。');
    conflict = false;
    await page.getByRole('button', { name: '刷新档案与状态', exact: true }).click();
    await page.getByRole('button', { name: '保存新版本', exact: true }).click();
    await page.getByRole('heading', { name: '离线修订 <script>', exact: true }).waitFor();
    assert.equal(await page.locator('script:not([src])').count(), 0);
    await page.getByRole('button', { name: '重新鉴权并读取', exact: true }).click();
    await page.getByRole('complementary', { name: '证据读取结果', exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.fixtureXss), undefined);
    await page.getByRole('button', { name: '关闭证据', exact: true }).click();
    revoked = true; await page.getByRole('button', { name: '重新鉴权并读取', exact: true }).click();
    await page.getByRole('alert').filter({ hasText: '证据来源已撤权' }).waitFor();
    await page.getByRole('button', { name: '关闭证据', exact: true }).click(); revoked = false;
    await page.getByRole('button', { name: '手动扫描', exact: true }).click();
    await page.getByText('本次扫描缺失：盈利预测缺失', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(output, `dossier-${width}-${theme}.png`), fullPage: true });
    const priorSubmissions = requests.filter(item => item.method === 'POST' && /\/sessions(?:$|\/[^/]+\/messages)/.test(item.path)).length;
    await page.getByRole('button', { name: '准备 Claw 草稿', exact: true }).click();
    await page.waitForFunction(() => document.querySelector('#prompt')?.value.includes('离线冻结档案'));
    assert.match(await page.locator('#prompt').inputValue(), /离线冻结档案/);
    assert.equal(requests.filter(item => item.method === 'POST' && /\/sessions(?:$|\/[^/]+\/messages)/.test(item.path)).length, priorSubmissions);
    const submitted = page.waitForResponse(response => response.url().endsWith(`/sessions/${targetSessionID}/messages`) && response.request().method() === 'POST');
    await page.locator('#prompt').press('Enter'); await submitted;
    await page.waitForFunction(() => document.querySelector('#prompt')?.value === '');
    assert.equal(requests.filter(item => item.method === 'POST' && /\/sessions(?:$|\/[^/]+\/messages)/.test(item.path)).length, priorSubmissions + 2);
    await page.evaluate(() => { location.hash = '#/intel/signals'; });
    await page.getByRole('heading', { name: '离线风险信号', exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.fixtureXss), undefined);
    assert.match(await page.locator('[data-dossier-workspace]').innerText(), /数据已过期/);
    await page.screenshot({ path: path.join(output, `signals-${width}-${theme}.png`), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    await page.getByRole('link', { name: '查看证据与原观点', exact: true }).focus(); await page.keyboard.press('Enter');
    await page.getByRole('heading', { name: dossier.title, exact: true }).waitFor();
    assert.deepEqual(errors, []); results.push({ width, height, theme, status: 'passed' }); await context.close();
  }
  assert.deepEqual(unexpected, []);
  assert.equal(expectedHTTPFailures.filter(message => message.includes('409')).length, 3);
  assert.equal(expectedHTTPFailures.filter(message => message.includes('403')).length, 3);
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify({ status: 'passed', origin, fixture: true, results, requestCount: requests.length, realModelSubmissions: 0, fixturePromptSubmissions: 3, expectedHTTPFailures }, null, 2));
  await appendFile(log, `${JSON.stringify({ event: 'dossier_ui_browser_acceptance', status: 'passed', results, requestCount: requests.length })}\n`);
  console.log(JSON.stringify({ status: 'passed', results, output }));
} catch (error) {
  if (activePage && !activePage.isClosed()) { await activePage.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); await writeFile(path.join(output, 'failure.html'), await activePage.content()); }
  await writeFile(path.join(output, 'failure.json'), JSON.stringify({ error: error.message, unexpected, requests }, null, 2));
  await appendFile(log, `${JSON.stringify({ event: 'dossier_ui_browser_acceptance', status: 'failed', error: error.message })}\n`); throw error;
} finally { await browser?.close(); await new Promise(resolve => server.close(resolve)); }
