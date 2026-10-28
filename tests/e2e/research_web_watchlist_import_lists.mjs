/** Real current-observation Host. Original create buttons and full/partial list updates. */
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, writeFile, appendFile, mkdir, mkdtemp, stat, open } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const epoch = process.env.RWB_WATCHLIST_E2E_EPOCH || '';
assert.match(epoch, /^[a-z0-9-]*$/);
const output = path.join(project, 'logs', 'watchlist-spec-lists-e2e' + (epoch ? '-' + epoch : ''));
await mkdir(output, { recursive: true });
const root = await mkdtemp('/tmp/rwb-watchlist-spec-lists-');
const identity = await stat(root);
const registration = { root, uid: process.getuid(), pid: process.pid, dev: identity.dev, inode: identity.ino, task: 'seek-watchlist-import-20261028-8eb1123d', phase: 'spec-P2' };
await writeFile(path.join(output, 'root-identity.json'), JSON.stringify(registration));
await appendFile(path.join(output, 'root-identities.jsonl'), JSON.stringify(registration) + '\n');
const stream = await open(path.join(output, 'host.log'), 'a');
assert.ok(process.env.RWB_TEST_PYTHON);
const profile = path.join(project, 'tests/e2e/watchlist-loopback.sb');
const boundFiles = ['app/research_web/watchlist_import.py', 'app/research_web/asset_workspace.py', 'app/research_web/asset_routes.py', 'app/research_web/store.py', 'app/research_web/asset_directory.py', 'app/research_web/ui/core.mjs', 'app/research_web/ui/asset-controller.mjs', 'app/research_web/ui/asset-workspace.mjs', 'app/research_web/ui/watchlist-import.mjs', 'app/research_web/ui/asset-workspace.css', 'tests/e2e/watchlist_import_host.py', 'tests/e2e/watchlist-loopback.sb', path.relative(project, fileURLToPath(import.meta.url))];
const sourceBinding = { base_commit: execFileSync('/usr/bin/git', ['rev-parse', 'HEAD'], { cwd: project, encoding: 'utf8' }).trim(), sha256: Object.fromEntries(await Promise.all(boundFiles.map(async file => [file, createHash('sha256').update(await readFile(path.join(project, file))).digest('hex')]))) };

const host = spawn('/usr/bin/sandbox-exec', ['-f', profile, process.env.RWB_TEST_PYTHON, 'tests/e2e/watchlist_import_host.py', '--root', path.join(root, 'account'), '--ready', path.join(root, 'ready.json'), '--empty-watchlists', '--current-observation'], { cwd: project, stdio: ['ignore', stream.fd, stream.fd], env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', RWB_WATCHLIST_SEATBELT: '1' } });
let browser; let page; let origin; const errors = [], external = [], results = []; const started = performance.now();
const delay = ms => new Promise(resolve => setTimeout(resolve, ms));
const check = async (name, run) => { await run(); results.push({ name, status: 'PASS' }); console.log(`PASS: ${name}`); };
const state = async () => (await fetch(origin + '/_fixture/state')).json();
let failure; let hostBoundary;
try {
  for (let n = 0; n < 100; n++) { try { ({ origin } = JSON.parse(await readFile(path.join(root, 'ready.json')))); if ((await fetch(origin + '/api/research/watchlists')).ok) break; } catch { /* Bounded fixture startup; detailed errors remain in host.log. */ } if (host.exitCode !== null) throw new Error(`Fixture exited ${host.exitCode}`); await delay(100); }
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.route('**/*', route => { const url = route.request().url(); if (url.startsWith(origin + '/') || url.startsWith('data:')) return route.continue(); external.push(url); return route.abort(); });
  page = await context.newPage(); page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(error.message));
  await page.goto(origin + '/#/assets?view=overview&asset=600519.SH&asset_type=stock'); await page.waitForLoadState('networkidle');
  const initial = await state(); assert.ok(initial.current_observation); assert.equal(initial.observations, 1); assert.deepEqual(initial.watchlists, {});
  await page.waitForFunction(() => Boolean(document.querySelector('[data-observation-id]')?.dataset.observationId));
  await page.locator('.asset-more-menu > summary').click(); await page.locator('.asset-list-drawer > summary').click();
  const importer = page.locator('rwb-watchlist-import');
  const create = async name => { const form = page.locator('[data-asset-watchlist-create]'); await form.locator('[name=name]').fill(name); await form.getByRole('button', { name: '创建', exact: true }).click(); };
  const option = name => importer.locator('[data-wi-target]').getByRole('option', { name, exact: true });
  let a, b;
  await check('current-observation-zero-list-original-create-then-preview-confirm', async () => {
    await page.evaluate(() => {
      window.fixtureOriginalFileRead = File.prototype.arrayBuffer;
      File.prototype.arrayBuffer = function () { const file = this; return new Promise(resolve => { window.fixtureReleaseFileRead = async () => resolve(await window.fixtureOriginalFileRead.call(file)); }); };
    });
    await importer.locator('[data-wi-file]').setInputFiles({ name: '首建前选择.csv', mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n600519.SH,stock,贵州茅台\n') });
    assert.equal(await importer.locator('[data-wi-preview]').isDisabled(), true);
    await create('列表 A'); await option('列表 A').waitFor({ state: 'attached' });
    a = await option('列表 A').getAttribute('value'); assert.ok(a);
    await page.evaluate(async () => { await window.fixtureReleaseFileRead(); File.prototype.arrayBuffer = window.fixtureOriginalFileRead; });
    assert.equal(await importer.locator('[data-wi-target]').inputValue(), a);
    assert.equal(await importer.locator('[data-wi-file]').evaluate(el => el.files[0]?.name), '首建前选择.csv');
    await importer.locator('[data-wi-preview]:enabled').click(); await importer.locator('[data-wi-confirm]:enabled').waitFor();
    await importer.locator('[data-wi-confirm]').click(); await importer.getByText('已追加 1 项，跳过 0 行。原自选已保留。').waitFor();
    assert.equal((await state()).watchlists[a].items[0].asset, '600519.SH');
    await page.screenshot({ path: path.join(output, 'current-observation-first-list-confirmed.png') });
  });
  await check('existing-A-original-create-B-preserves-draft-and-explicit-new-target-freeze', async () => {
    await importer.locator('[data-wi-file]').setInputFiles({ name: 'A后新建B.csv', mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n000001.SZ,stock,同名\n') });
    await importer.locator('[data-wi-preview]').click(); await importer.locator('[data-wi-confirm]:enabled').waitFor();
    await create('列表 B'); await option('列表 B').waitFor({ state: 'attached' });
    b = await option('列表 B').getAttribute('value'); assert.ok(b && b !== a);
    assert.equal(await importer.locator('[data-wi-target]').inputValue(), a, 'existing target selection must stay A');
    assert.equal(await importer.locator('[data-wi-file]').evaluate(el => el.files[0]?.name), 'A后新建B.csv');
    await importer.locator('[data-wi-target]').selectOption(b);
    assert.equal(await importer.locator('[data-wi-confirm]').isDisabled(), true, 'target change invalidates old freeze');
    await importer.locator('[data-wi-preview]').click(); await importer.locator('[data-wi-confirm]:enabled').waitFor();
    await importer.locator('[data-wi-confirm]').click(); await importer.getByText('已追加 1 项，跳过 0 行。原自选已保留。').waitFor();
    const result = await state(); assert.deepEqual(result.watchlists[a].items.map(row => row.asset), ['600519.SH']); assert.deepEqual(result.watchlists[b].items.map(row => row.asset), ['000001.SZ']);
    await page.screenshot({ path: path.join(output, 'current-observation-second-list-confirmed.png') });
  });
  await check('real-partial-summary-sync-keeps-authorized-file-and-current-target', async () => {
    await importer.locator('[data-wi-file]').setInputFiles({ name: '局部更新保留.csv', mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n430001.BJ,stock,北交😀\n') });
    const outcome = await page.evaluate(async () => {
      const { updateAssetSummary } = await import('/static/asset-workspace.mjs');
      const page = document.querySelector('[data-asset-identity]'), old = page.querySelector('rwb-watchlist-import'), file = old.querySelector('[data-wi-file]').files[0];
      const response = await fetch('/api/research/assets/observations'), observations = (await response.json()).items;
      const observation = observations[0];
      const listResponse = await fetch('/api/research/watchlists'), watchlists = (await listResponse.json()).items;
      const ok = updateAssetSummary(page, { observation, observations, watchlists, route: { asset: '600519.SH', assetType: 'stock', assetView: 'overview' } });
      const current = page.querySelector('rwb-watchlist-import');
      return { ok, sameNode: current === old, file: current.querySelector('[data-wi-file]').files[0]?.name, sameFile: current.querySelector('[data-wi-file]').files[0] === file, options: [...current.querySelector('[data-wi-target]').options].map(option => option.textContent) };
    });
    assert.deepEqual(outcome, { ok: true, sameNode: true, file: '局部更新保留.csv', sameFile: true, options: ['列表 B', '列表 A'] });
    assert.equal(await importer.locator('[data-wi-target]').inputValue(), b);
    const final = await state(); assert.equal(final.external_calls, 0); assert.equal(final.network_attempts, 0); assert.equal(final.real_credential_attempts, 0); for (const counts of Object.values(final.http_client_counters)) assert.equal(counts.nonloopback_attempts || 0, 0); assert.equal(final.framework_collectors_enabled, false); assert.equal(final.sessions, initial.sessions); assert.equal(final.observations, initial.observations);
  });
  const boundary = await state(); hostBoundary = { kernel: 'macos-seatbelt-loopback-only', profile_sha256: sourceBinding.sha256['tests/e2e/watchlist-loopback.sb'], child_pid: host.pid, external_calls: boundary.external_calls, network_attempts: boundary.network_attempts, real_credential_attempts: boundary.real_credential_attempts, http_client_counters: boundary.http_client_counters, framework_collectors_enabled: boundary.framework_collectors_enabled };
  assert.deepEqual(errors, []); assert.deepEqual(external, []);
} catch (error) { failure = error.stack; if (page) await page.screenshot({ path: path.join(output, 'failed.png') }).catch(e => errors.push(e.message)); }
finally {
  await browser?.close(); if (host.exitCode === null) { host.kill('SIGTERM'); await new Promise(resolve => host.once('exit', resolve)); } await stream.close();
  await writeFile(path.join(output, 'result.json'), JSON.stringify({ status: failure ? 'FAIL' : 'PASS', results, failure, errors, external, hostBoundary, sourceBinding, root, durationMs: Math.round(performance.now() - started) }, null, 2));
}
if (failure) { console.error(failure); process.exitCode = 1; }
