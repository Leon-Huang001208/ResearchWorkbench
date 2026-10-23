/** Real loopback HTTP + Chrome; temporary Host storage and NativeFixture only. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createWriteStream } from 'node:fs';
import { mkdir, writeFile, readFile } from 'node:fs/promises';
import { createHash, randomUUID } from 'node:crypto';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'outputs/research-web-dossiers-real');
const python = process.env.RWB_DOSSIER_TEST_PYTHON || path.join(project, '.venv/bin/python');
const producerFiles = ['app/research_web/ui/app.mjs', 'app/research_web/ui/core.mjs', 'app/research_web/ui/dossiers.mjs', 'app/research_web/dossiers/__init__.py', 'app/research_web/dossiers/scans.py', 'app/research_web/dossiers/signals.py', 'app/research_web/dossiers/models.py', 'app/research_web/dossiers/storage.py', 'app/research_web/dossiers/routes.py', 'app/research_web/service.py', 'tests/e2e/research_web_dossiers_backend.py', 'tests/e2e/research_web_dossiers_real_backend.mjs'];
const digestSources = async () => Object.fromEntries(await Promise.all(producerFiles.map(async file => [file, createHash('sha256').update(await readFile(path.join(project, file))).digest('hex')])));
await mkdir(output, { recursive: true }); await mkdir(path.join(project, 'logs'), { recursive: true });
const sourceHashes = await digestSources();
const stdout = createWriteStream(path.join(project, 'logs/research-web-dossiers-real-backend.log'));
const stderr = createWriteStream(path.join(project, 'logs/research-web-dossiers-real-backend-errors.log'));
const child = spawn(python, ['-u', path.join(project, 'tests/e2e/research_web_dossiers_backend.py'), '--output', output], { cwd: project, env: { PATH: process.env.PATH || '/usr/bin:/bin', PYTHONIOENCODING: 'utf-8' }, stdio: ['ignore', 'pipe', 'pipe'] });
let readyBuffer = '', resolveReady, rejectReady, browser, page;
const exited = new Promise(resolve => child.once('exit', (code, signal) => resolve({ code, signal })));
const ready = new Promise((resolve, reject) => { resolveReady = resolve; rejectReady = reject; });
child.once('error', rejectReady);
child.once('exit', code => { if (!readyBuffer.includes('RWB_DOSSIER_HTTP_READY')) rejectReady(new Error(`Fixture backend exited before readiness (${code})`)); });
child.stdout.on('data', bytes => {
  stdout.write(bytes); readyBuffer = (readyBuffer + bytes.toString()).slice(-12000);
  const line = /RWB_DOSSIER_HTTP_READY (\{[^\n]+\})/.exec(readyBuffer);
  if (line) resolveReady(JSON.parse(line[1]));
});
child.stderr.pipe(stderr);
const results = [], blocked = [], pageErrors = [], expectedHTTP = [];
let origin;
async function api(context, route, body) {
  const response = body === undefined ? await context.request.get(`${origin}${route}`) : await context.request.post(`${origin}${route}`, { data: body });
  const value = await response.json();
  assert.ok(response.ok(), `${route}: HTTP ${response.status()} ${JSON.stringify(value).slice(0, 1000)}`);
  return value;
}
async function chooseDossier(id, title) {
  await page.evaluate(hash => { location.hash = hash; }, `#/assets?view=dossiers&dossier=${id}`);
  await page.getByRole('heading', { name: title, exact: true }).waitFor();
}
async function createDossier(title) {
  await page.getByRole('button', { name: '新建档案', exact: true }).click();
  await page.locator('#dossier-field-title').fill(title);
  await page.locator('#dossier-field-key').fill('600519.SH');
  await page.locator('#dossier-field-label').fill('离线 HTTP 公司');
  const response = page.waitForResponse(response => response.request().method() === 'POST' && new URL(response.url()).pathname === '/api/research/dossiers');
  await page.getByRole('button', { name: '保存新版本', exact: true }).click();
  const detail = await (await response).json(); assert.match(detail.id, /^[a-f0-9]{32}$/);
  await page.getByRole('heading', { name: title, exact: true }).waitFor();
  return detail;
}
async function evidenceForm(source, type, reference) {
  await page.getByRole('button', { name: '归入证据', exact: true }).click();
  await page.locator('#dossier-field-source_session_id').fill(source);
  await page.locator('#dossier-field-type').selectOption(type);
  await page.locator('#dossier-field-reference_id').fill(reference);
  await page.getByRole('button', { name: '预览归档', exact: true }).click();
  await page.getByRole('region', { name: '归档预览', exact: true }).waitFor();
  const response = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/evidence'));
  await page.getByRole('button', { name: '确认写入新版本', exact: true }).click();
  return (await response).json();
}
async function scan() {
  const response = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/scan'));
  await page.getByRole('button', { name: '手动扫描', exact: true }).click();
  const value = await (await response).json();
  await page.getByText('手动扫描已完成，请核对信号的证据和数据覆盖。', { exact: true }).waitFor();
  return value;
}
async function prepare() {
  const response = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/handoff'));
  await page.getByRole('button', { name: '准备 Claw 草稿', exact: true }).click();
  const handoff = await (await response).json();
  await page.locator('#prompt').waitFor();
  assert.equal(await page.locator('#prompt').isDisabled(), true, 'composer cannot send a stale homepage draft during handoff navigation');
  await page.waitForFunction(value => !document.querySelector('#prompt')?.disabled && document.querySelector('#prompt')?.value.includes(value.prompt) && Object.keys(sessionStorage).some(key => key.includes('explicit-draft:') && JSON.parse(sessionStorage.getItem(key)).dossierHandoff?.id === value.receipt), { prompt: handoff.prompt, receipt: handoff.context.handoff_id });
  return handoff;
}
async function enter() {
  await page.waitForFunction(() => {
    const prompt = document.querySelector('#prompt'), caption = document.querySelector('#composer .composer-caption');
    return prompt && !prompt.disabled && (!caption || !/运行时|正在连接/.test(caption.textContent));
  });
  const response = page.waitForResponse(response => response.request().method() === 'POST' && /\/sessions\/[^/]+\/messages$/.test(new URL(response.url()).pathname));
  await page.locator('#prompt').press('Enter');
  const result = await response;
  assert.equal(result.status(), 202, await result.text());
  await page.waitForFunction(() => document.querySelector('#prompt')?.value === '');
  return /\/sessions\/([^/]+)\/messages$/.exec(new URL(result.url()).pathname)[1];
}
try {
  const timer = setTimeout(() => rejectReady(new Error('Fixture backend readiness timed out')), 20000);
  const target = await ready; clearTimeout(timer);
  origin = `http://127.0.0.1:${target.port}`;
  let health;
  for (let attempt = 0; attempt < 40; attempt++) {
    try { const response = await fetch(`${origin}/__fixture/ready`); if (response.ok) { health = await response.json(); break; } }
    catch { /* Listener exists before uvicorn starts; only this local readiness read retries. */ }
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  assert.equal(health?.lifespan, 'off');
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  for (const [width, height, theme] of [[1440, 1000, 'light'], [390, 844, 'dark']]) {
    const context = await browser.newContext({ viewport: { width, height } });
    const unauthenticated = await context.request.get(`${origin}/api/research/dossiers`); assert.equal(unauthenticated.status(), 401);
    await context.addInitScript(account => { globalThis.__RWB_USER_ID__ = account; }, health.account);
    page = await context.newPage(); page.setDefaultTimeout(15000); page.on('dialog', dialog => dialog.accept());
    page.on('pageerror', error => pageErrors.push(error.message));
    page.on('console', message => { if (message.type() === 'error') { if (/status of 403 \(Forbidden\)/.test(message.text())) expectedHTTP.push(message.text()); else pageErrors.push(message.text()); } });
    await page.route('**/*', route => { if (new URL(route.request().url()).origin === origin) return route.continue(); blocked.push(route.request().url()); return route.abort('blockedbyclient'); });
    await page.goto(`${origin}/__fixture/login`);
    await page.getByRole('button', { name: '进入离线验收', exact: true }).click();
    await page.getByRole('heading', { name: '研究档案', exact: true }).waitFor();
    await page.evaluate(theme => { document.documentElement.dataset.theme = theme; }, theme);
    const seed = await api(context, '/__fixture/bootstrap'), before = await api(context, '/__fixture/state');
    const original = await createDossier(`真实HTTP档案 ${width}`);
    for (const title of ['当前判断', '观点时间线', '证据', '催化剂与风险', '研究成果']) await page.getByRole('heading', { name: title, exact: true }).waitFor();
    const missing = await scan(); assert.equal(missing.coverage.eligible, false); assert.ok(missing.missing.some(item => item.code === 'no_frozen_evidence'));
    const withFile = await evidenceForm(seed.source_session_id, 'file', seed.source_path); assert.equal(withFile.evidence.length, 1);
    await page.getByRole('button', { name: '新增研究记录', exact: true }).click();
    await page.locator('#dossier-field-title').fill('跨会话持续观点'); await page.locator('#dossier-field-body').fill('基于已有证据保留判断与下一项验证。');
    await page.locator('#dossier-field-reason').fill('真实 HTTP 离线初判'); await page.locator('#dossier-field-evidence_ids').fill(withFile.evidence[0].id);
    const recorded = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/records'));
    await page.getByRole('button', { name: '保存新版本', exact: true }).click(); assert.equal((await recorded).status(), 200);
    await page.getByRole('heading', { name: '跨会话持续观点', exact: true }).waitFor();
    await page.getByRole('button', { name: '重新鉴权并读取', exact: true }).click();
    await page.getByText('此处仅为部分正文预览；服务端或页面已截断，不代表完整材料。', { exact: true }).waitFor();
    assert.match(await page.locator('.dossier-preview pre').innerText(), /FROZEN_BACKEND_HTTP_SOURCE/);
    await page.getByRole('button', { name: '关闭证据', exact: true }).click();
    await page.getByRole('button', { name: '关联成果', exact: true }).click();
    await page.locator('#dossier-field-source_session_id').fill(seed.source_session_id);
    await page.locator('#dossier-field-type').selectOption('file'); await page.locator('#dossier-field-reference_id').fill(seed.source_path);
    await page.getByRole('button', { name: '预览归档', exact: true }).click();
    const linked = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith('/links'));
    await page.getByRole('button', { name: '确认写入新版本', exact: true }).click(); assert.equal((await linked).status(), 200);
    await page.getByRole('button', { name: '受控原件预览', exact: true }).click();
    await page.getByRole('heading', { name: '冻结研究成果', exact: true }).waitFor();
    assert.match(await page.locator('.dossier-preview pre').innerText(), /FROZEN_BACKEND_HTTP_SOURCE/); await page.getByRole('button', { name: '关闭证据', exact: true }).click();
    const noSignal = await api(context, '/api/research/dossiers', { title: `完整空快照 ${width}`, subject: original.subject, idempotency_key: randomUUID() });
    const emptyEvidence = await api(context, `/api/research/dossiers/${noSignal.id}/evidence`, { expected_revision: noSignal.revision, idempotency_key: randomUUID(), source_session_id: seed.source_session_id, reference: { type: 'dataset', id: seed.datasets.empty } });
    await chooseDossier(noSignal.id, noSignal.title); const none = await scan(); assert.equal(none.coverage.eligible, true); assert.equal(none.signals.length, 0); assert.equal(none.coverage.accepted, 1);
    assert.equal(emptyEvidence.evidence[0].state, undefined, 'write response is raw metadata; GET performs actual source validation');
    const signalDoc = await api(context, '/api/research/dossiers', { title: `披露线索 ${width}`, subject: original.subject, idempotency_key: randomUUID() });
    await api(context, `/api/research/dossiers/${signalDoc.id}/evidence`, { expected_revision: signalDoc.revision, idempotency_key: randomUUID(), source_session_id: seed.source_session_id, reference: { type: 'dataset', id: seed.datasets.signal } });
    await chooseDossier(signalDoc.id, signalDoc.title); const signal = await scan(); assert.equal(signal.signals.length, 1); assert.equal(signal.signals[0].signal_type, 'review');
    await page.evaluate(() => { location.hash = '#/intel/signals'; }); await page.getByRole('heading', { name: '财务披露待研究', exact: true }).first().waitFor();
    await page.locator('#dossier-signal-kind').selectOption('review'); await page.getByRole('heading', { name: '财务披露待研究', exact: true }).first().waitFor();
    await page.screenshot({ path: path.join(output, `signals-${width}-${theme}.png`), fullPage: true });
    await chooseDossier(original.id, original.title); await page.screenshot({ path: path.join(output, `dossier-${width}-${theme}.png`), fullPage: true });
    const handoff = await prepare(); let audit = await api(context, '/__fixture/state'); assert.equal(audit.bound_receipts, before.bound_receipts);
    const draft = await page.locator('#prompt').inputValue(); await page.locator('#prompt').fill(`${draft} @`); await page.locator('#tabbit-options').waitFor();
    audit = await api(context, '/__fixture/state'); assert.equal(audit.bound_receipts, before.bound_receipts); assert.equal(audit.native_prompt_calls, before.native_prompt_calls);
    await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('#prompt').waitFor(); await page.locator('#prompt').fill(draft);
    const firstTarget = await enter(); audit = await api(context, '/__fixture/state'); assert.equal(audit.bound_receipts, before.bound_receipts + 1); assert.equal(audit.native_prompt_calls, before.native_prompt_calls + 1);
    await page.waitForFunction(() => Object.keys(sessionStorage).filter(key => key.startsWith('research-web:') && key.includes('explicit-draft:')).every(key => !JSON.parse(sessionStorage.getItem(key)).dossierHandoff));
    const read = await api(context, '/__fixture/read-bound', { session_id: firstTarget, handle: handoff.context.evidence_handles[0] }); assert.equal(read.contains_fixture_source, true);
    await chooseDossier(original.id, original.title); await prepare(); const secondTarget = await enter(); assert.notEqual(secondTarget, firstTarget);
    audit = await api(context, '/__fixture/state'); assert.equal(audit.bound_receipts, before.bound_receipts + 2); assert.equal(audit.automations, 0); assert.deepEqual(audit.blocked_outbound, []);
    await chooseDossier(original.id, original.title); await page.getByRole('button', { name: '重新鉴权并读取', exact: true }).click(); await page.locator('.dossier-preview pre').waitFor();
    await api(context, '/__fixture/revoke', {}); await page.getByRole('button', { name: '重新鉴权并读取', exact: true }).click(); await page.getByRole('alert').filter({ hasText: '撤销' }).waitFor();
    assert.equal(await page.locator('.dossier-preview').count(), 0); assert.doesNotMatch(await page.locator('body').innerText(), /FROZEN_BACKEND_HTTP_SOURCE/);
    await page.screenshot({ path: path.join(output, `revoked-${width}-${theme}.png`), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    results.push({ width, height, theme, state: 'passed', missingEvidence: true, emptySnapshotNoSignal: true, realSignals: signal.signals.length, preparedBindings: 0, targetReload: true, promptBindings: 2 });
    await api(context, '/__fixture/restore', {}); await context.close();
  }
  assert.deepEqual(blocked, []); assert.deepEqual(pageErrors, []); assert.deepEqual(await digestSources(), sourceHashes);
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify({ state: 'passed', backend: 'actual ResearchService/routers/Store/SQLite', native: 'NativeFixture', authentication: 'fixture-only temporary cookie gate', lifespan: 'off', sourceHashes, results, realModelCalls: 0, externalRequests: 0, expectedHTTP }, null, 2));
  console.log(JSON.stringify({ state: 'passed', results, output }));
} catch (error) {
  if (page && !page.isClosed()) { await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }); await writeFile(path.join(output, 'failure.html'), await page.content()); }
  await writeFile(path.join(output, 'failure.json'), JSON.stringify({ state: 'failed', error: error.message, blocked, pageErrors, results }, null, 2)); throw error;
} finally {
  await browser?.close(); child.kill('SIGTERM');
  const stopped = await Promise.race([exited, new Promise(resolve => setTimeout(() => resolve(null), 10000))]);
  if (!stopped) { child.kill('SIGKILL'); await exited; }
  stdout.end(); stderr.end();
}
