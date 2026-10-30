/** Real localhost Host + original asset UI. No provider/model/network evidence. */
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { readFile, writeFile, appendFile, mkdir, mkdtemp, stat, open } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const epoch = process.env.RWB_WATCHLIST_E2E_EPOCH || '';
assert.match(epoch, /^[a-z0-9-]*$/);
const output = path.join(project, 'logs', 'watchlist-import-e2e' + (epoch ? '-' + epoch : ''));
await mkdir(output, { recursive: true });
const root = await mkdtemp('/tmp/rwb-watchlist-browser-');
const info = await stat(root);
await writeFile(path.join(output, 'root-identity.json'), JSON.stringify({ root, uid: process.getuid(), pid: process.pid, dev: info.dev, inode: info.ino, task: 'seek-watchlist-import-20261028-8eb1123d' }));
await appendFile(path.join(output, 'root-identities.jsonl'), JSON.stringify({ root, uid: process.getuid(), pid: process.pid, dev: info.dev, inode: info.ino, task: 'seek-watchlist-import-20261028-8eb1123d', argv: process.argv }) + '\n');
const stream = await open(path.join(output, 'host.log'), 'a');
const python = process.env.RWB_TEST_PYTHON;
assert.ok(python, 'RWB_TEST_PYTHON must select the existing environment');
const profile = path.join(project, 'tests/e2e/watchlist-loopback.sb');
const boundFiles = ['app/research_web/watchlist_import.py', 'app/research_web/asset_workspace.py', 'app/research_web/asset_routes.py', 'app/research_web/store.py', 'app/research_web/asset_directory.py', 'app/research_web/ui/core.mjs', 'app/research_web/ui/asset-controller.mjs', 'app/research_web/ui/asset-workspace.mjs', 'app/research_web/ui/watchlist-import.mjs', 'app/research_web/ui/asset-workspace.css', 'tests/e2e/watchlist_import_host.py', 'tests/e2e/watchlist-loopback.sb', path.relative(project, fileURLToPath(import.meta.url))];
const sourceBinding = { base_commit: execFileSync('/usr/bin/git', ['rev-parse', 'HEAD'], { cwd: project, encoding: 'utf8' }).trim(), sha256: Object.fromEntries(await Promise.all(boundFiles.map(async file => [file, createHash('sha256').update(await readFile(path.join(project, file))).digest('hex')]))) };

const childEnvironment = { ...process.env, PYTHONDONTWRITEBYTECODE: '1', RWB_WATCHLIST_SEATBELT: '1', RESEARCH_FRAMEWORK_COLLECTORS_ENABLED: '0' };
const sanitizedEnvironmentKeys = Object.keys(childEnvironment).filter(key => ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'FTP_PROXY', 'NO_PROXY', 'RESEARCH_CREDENTIAL_HOME'].includes(key.toUpperCase()));
for (const key of sanitizedEnvironmentKeys) { delete childEnvironment[key]; delete process.env[key]; }
const host = spawn('/usr/bin/sandbox-exec', ['-f', profile, python, 'tests/e2e/watchlist_import_host.py', '--root', path.join(root, 'account'), '--ready', path.join(root, 'ready.json')], { cwd: project, stdio: ['ignore', stream.fd, stream.fd], env: childEnvironment });
const started = performance.now(); let browser; let origin; let page; const failures = []; const errors = []; const external = []; const results = []; let hostBoundary;
const wait = ms => new Promise(resolve => setTimeout(resolve, ms));
async function fixture() { return (await fetch(`${origin}/_fixture/state`)).json(); }
async function check(name, run) { await run(); results.push({ name, status: 'PASS' }); console.log(`PASS: ${name}`); }
try {
  for (let n = 0; n < 100; n++) { try { ({ origin } = JSON.parse(await readFile(path.join(root, 'ready.json')))); const response = await fetch(`${origin}/api/research/watchlists`); if (response.ok) break; } catch { /* Fixture startup is bounded; full errors remain in host.log. */ } if (host.exitCode !== null) throw new Error(`Host exited ${host.exitCode}`); await wait(100); }
  assert.ok(origin, 'Host must publish a loopback origin');
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, env: childEnvironment, args: ['--no-proxy-server'], executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  await context.route('**/*', route => { const url = route.request().url(); if (url.startsWith(origin + '/') || url.startsWith('data:')) return route.continue(); external.push(url); return route.abort(); });
  page = await context.newPage(); page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push(error.message));
  await page.goto(`${origin}/#/assets`);
  await page.waitForLoadState('networkidle');
  await page.locator('.asset-more-menu > summary').click();
  await page.locator('.asset-list-drawer > summary').click();
  const importer = page.locator('rwb-watchlist-import');
  await importer.locator('[data-wi-file]').waitFor();
  const initial = await fixture();
  await check('original-self-selection-file-preview-and-all-row-decisions', async () => {
    await importer.locator('[data-wi-file]').setInputFiles({ name: '自选😀.csv', mimeType: 'text/csv', buffer: Buffer.from('\ufeffasset,asset_type,name\r\n600519.SH,stock,贵州茅台\r\n000001,stock,同名\r\n430001.BJ,stock,北交😀\r\n510300.SH,etf,ETF\r\n600519.SH,stock,贵州茅台\r\n') });
    await importer.locator('[data-wi-preview]').click();
    await importer.locator('tbody tr').nth(4).waitFor();
    assert.equal(await importer.locator('tbody tr').count(), 5);
    assert.match(await importer.innerText(), /该类型尚无规范目录/);
    assert.equal(await importer.locator('[data-wi-confirm]').isDisabled(), true);
    assert.deepEqual((await fixture()).watchlists, initial.watchlists);
  });
  await check('keyboard-disambiguation-skip-refreeze-confirm-original-list-update', async () => {
    const choice = importer.locator('[data-wi-choice="2"]');
    await choice.focus(); await choice.press('ArrowDown'); await choice.press('Enter');
    // Select an exact candidate using the native selection event, retaining keyboard focus.
    await importer.locator('[data-wi-choice="2"]').selectOption('000001.SZ');
    await importer.locator('[data-wi-skip="4"]').check();
    assert.equal(await importer.locator('[data-wi-confirm]').isDisabled(), true);
    await importer.locator('[data-wi-preview]').click();
    await importer.locator('[data-wi-confirm]:enabled').waitFor();
    await importer.locator('[data-wi-confirm]').click();
    await importer.getByText('已追加 3 项，跳过 2 行。原自选已保留。').waitFor();
    await page.waitForFunction(() => document.querySelectorAll('.asset-list-row').length === 4);
    const state = await fixture(); const items = state.watchlists[state.target].items;
    assert.deepEqual(items[0], initial.old); assert.equal(items.length, 4);
    assert.equal(state.sessions, initial.sessions); assert.equal(state.observations, initial.observations); assert.equal(state.external_calls, 0);
    await page.screenshot({ path: path.join(output, 'confirmed-original-list.png') });
  });
  await check('conflict-retains-file-and-selection-no-partial-additions', async () => {
    await importer.locator('[data-wi-file]').setInputFiles({ name: '保留输入.csv', mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n000001.SH,stock,同名\n') });
    await importer.locator('[data-wi-preview]').click(); await importer.locator('[data-wi-confirm]:enabled').waitFor();
    const state = await fixture();
    await page.evaluate(async ({ id }) => { const response = await fetch(`/api/research/watchlists/${id}/items`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ asset: '888888.SH', asset_type: 'stock', name: '并发旧单项' }) }); if (!response.ok) throw new Error('fixture single-item writer failed'); }, { id: state.target });
    await importer.locator('[data-wi-confirm]').click();
    await importer.getByText('自选列表已变化。保留了文件与选择，请重新冻结预览。').waitFor();
    assert.match(await importer.locator('[data-wi-filename]').innerText(), /保留输入.csv/);
    assert.equal(await importer.locator('[data-wi-confirm]').isDisabled(), true);
    assert.equal((await fixture()).watchlists[state.target].items.length, 5);
  });
  await check('invalid-csv-error-and-narrow-screen-state', async () => {
    await importer.locator('[data-wi-file]').setInputFiles({ name: '非法.csv', mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n600519.SH,stock,=formula\n') });
    await importer.locator('[data-wi-preview]').click();
    await importer.getByRole('alert').waitFor(); assert.match(await importer.innerText(), /文件包含公式型字段/);
    assert.doesNotMatch(await importer.innerText(), /watchlist_import_/);
    await page.setViewportSize({ width: 390, height: 844 });
    if (await page.locator('.asset-more-menu').getAttribute('open') === null) await page.locator('.asset-more-menu > summary').click();
    if (await page.locator('.asset-list-drawer').getAttribute('open') === null) await page.locator('.asset-list-drawer > summary').click();
    await writeFile(path.join(output, 'narrow-dom-diagnosis.json'), JSON.stringify(await page.evaluate(() => {
      const el = document.querySelector('rwb-watchlist-import');
      const chain = []; for (let n = el; n; n = n.parentElement) { const cs = getComputedStyle(n), r = n.getBoundingClientRect(); chain.push({ tag: n.tagName, class: n.className, open: n.open, display: cs.display, visibility: cs.visibility, position: cs.position, overflow: cs.overflow, rect: {x:r.x,y:r.y,width:r.width,height:r.height}, scrollTop:n.scrollTop }); }
      return { chain, html: el?.outerHTML, active: document.activeElement?.outerHTML, draft: el?.controller?.state, pageScroll: [scrollX, scrollY], viewport:[innerWidth,innerHeight] };
    }), null, 2));
    await importer.getByRole('alert').waitFor({ state: 'visible' });
    await importer.getByRole('alert').evaluate(element => element.scrollIntoView({ block: 'center' }));
    const bounds = await importer.boundingBox(); assert.ok(bounds.width > 100 && bounds.width <= 390 && bounds.x >= 0);
    assert.equal(await importer.locator('[data-wi-file]').evaluate(el => el.files[0]?.name), '非法.csv');
    const rejected = page.waitForResponse(response => response.url().endsWith('/imports/preview') && response.request().method() === 'POST');
    await importer.locator('[data-wi-preview]').focus(); await importer.locator('[data-wi-preview]').press('Enter');
    assert.equal((await rejected).status(), 422);
    await importer.getByRole('alert').waitFor({ state: 'visible' });
    assert.match(await importer.getByRole('alert').innerText(), /文件包含公式型字段/);
    await page.screenshot({ path: path.join(output, 'narrow-error-input-retained.png') });
    assert.equal(await importer.locator('[data-wi-confirm]').isDisabled(), true);
  });
  await check('narrow-dark-long-text-and-keyboard-refreeze', async () => {
    await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
    const longName = '长文件名'.repeat(40) + '.csv';
    await importer.locator('[data-wi-file]').setInputFiles({ name: longName, mimeType: 'text/csv', buffer: Buffer.from('asset,asset_type,name\n同名,stock,' + '长'.repeat(120) + '\n') });
    await importer.locator('[data-wi-preview]').focus(); await importer.locator('[data-wi-preview]').press('Enter');
    await importer.locator('[data-wi-choice="1"]').waitFor({ state: 'visible' });
    await importer.locator('[data-wi-choice="1"]').focus(); await importer.locator('[data-wi-choice="1"]').selectOption('000001.SH');
    await importer.locator('[data-wi-skip="1"]').focus(); await importer.locator('[data-wi-skip="1"]').press('Space');
    assert.equal(await importer.locator('[data-wi-skip="1"]').isChecked(), true);
    await importer.locator('[data-wi-preview]').focus(); await importer.locator('[data-wi-preview]').press('Enter');
    await importer.locator('[data-wi-confirm]:enabled').waitFor();
    assert.equal(await importer.locator('[data-wi-file]').evaluate(el => el.files[0]?.name), longName);
    const box = await importer.boundingBox(); assert.ok(box.width > 100 && box.x >= 0 && box.x + box.width <= 390);
    await importer.locator('[data-wi-confirm]').evaluate(el => el.scrollIntoView({block:'center'}));
    await page.screenshot({ path: path.join(output, 'narrow-dark-long-text-keyboard.png') });
    assert.equal(await page.evaluate(() => getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()), '#222220');
  });
  const boundary = await fixture(); hostBoundary = { kernel: 'macos-seatbelt-inbound-only', sanitized_environment_keys: sanitizedEnvironmentKeys, host_proxy_keys: boundary.proxy_environment_keys, credential_home_present: boundary.credential_home_present, profile_sha256: sourceBinding.sha256['tests/e2e/watchlist-loopback.sb'], child_pid: host.pid, external_calls: boundary.external_calls, network_attempts: boundary.network_attempts, real_credential_attempts: boundary.real_credential_attempts, http_client_counters: boundary.http_client_counters, framework_collectors_enabled: boundary.framework_collectors_enabled };
  assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.equal((await fixture()).external_calls, 0); assert.equal((await fixture()).network_attempts, 0); assert.equal((await fixture()).real_credential_attempts, 0); for (const counts of Object.values((await fixture()).http_client_counters)) assert.equal(counts.nonloopback_attempts || 0, 0); assert.equal((await fixture()).framework_collectors_enabled, false); assert.deepEqual((await fixture()).proxy_environment_keys, []); assert.equal((await fixture()).credential_home_present, false);
} catch (error) { failures.push(error.stack); if (page) await page.screenshot({ path: path.join(output, 'failed.png') }).catch(failure => errors.push(failure.message)); }
finally {
  await browser?.close();
  if (host.exitCode === null) { host.kill('SIGTERM'); await new Promise(resolve => host.once('exit', resolve)); }
  await stream.close();
  await writeFile(path.join(output, 'result.json'), JSON.stringify({ status: failures.length ? 'FAIL' : 'PASS', results, failures, errors, external, hostBoundary, sourceBinding, durationMs: Math.round(performance.now() - started), root }, null, 2));
}
if (failures.length) { console.error(failures.join('\n')); process.exitCode = 1; }
