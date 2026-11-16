/** Real calculation through the loopback RWB Host and Chrome, using the owner's frozen ZIP. */

import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createHash } from 'node:crypto';
import { chmod, readFile, readdir, mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { homedir, tmpdir } from 'node:os';
import { resolve, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = fileURLToPath(new URL('../../', import.meta.url));
const zip = process.env.RWB_FROZEN_EXIT_ZIP;
const python = process.env.RWB_TEST_PYTHON;
const outputArgument = process.env.RWB_STRATEGY_EVIDENCE;
assert.ok(zip && python && outputArgument, 'Set RWB_FROZEN_EXIT_ZIP, RWB_TEST_PYTHON and RWB_STRATEGY_EVIDENCE');
const output = resolve(outputArgument);
const archive = resolve(zip);
const archiveDigest = createHash('sha256').update(await readFile(archive)).digest('hex');
assert.equal(archiveDigest, '10877827ea5dc42f24eebea2e9d4eae6cce61a75809de1baffb6abfe22c98113');
await mkdir(output, { mode: 0o700 });
const root = await mkdtemp(join(tmpdir(), 'rwb-strategy-browser-'));

const runner = String.raw`
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd() / "tests/e2e"))
from research_web_dossiers_backend import isolate, server_config
isolate(Path(sys.argv[1]) / "host", Path(sys.argv[2]))

import uvicorn
from research_web_fixture_server import BrowserFixtureRuntime

from app.research_web.main import create_app
from app.research_web.service import ResearchService
from app.research_web.store import Store

research = ResearchService(
    BrowserFixtureRuntime(), Store(Path(sys.argv[1]) / "strategy-host"), auto_probe_on_start=False
)
app = create_app(research)
app.state.research = research

with socket.socket() as listener:
    listener.bind(("127.0.0.1", 0))
    print(f"RWB_STRATEGY_PORT={listener.getsockname()[1]}", flush=True)
    uvicorn.Server(server_config(app)).run(sockets=[listener])
`;
const child = spawn(python, ['-u', '-B', '-c', runner, root, output], {
  cwd: project, stdio: ['ignore', 'pipe', 'pipe'],
});
let stderr = '';
let browser;
let page;
const traffic = [];
const closed = new Promise(resolve => child.once('close', resolve));
child.stderr.on('data', chunk => { stderr = (stderr + chunk).slice(-8000); });

function listenerPort() {
  return new Promise((resolve, reject) => {
    let stdout = '';
    const timer = setTimeout(() => reject(new Error('Timed out starting isolated RWB Host')), 25000);
    child.stdout.on('data', chunk => {
      stdout = (stdout + chunk).slice(-4000);
      const match = stdout.match(/RWB_STRATEGY_PORT=(\d+)/);
      if (match) {
        clearTimeout(timer);
        resolve(Number(match[1]));
      }
    });
    child.once('error', error => { clearTimeout(timer); reject(error); });
    child.once('close', code => {
      clearTimeout(timer);
      reject(new Error(`Host exited ${code}: ${stderr}`));
    });
  });
}

async function makeDirectoriesWritable(directory) {
  await chmod(directory, 0o700);
  for (const item of await readdir(directory, { withFileTypes: true })) {
    if (item.isDirectory()) await makeDirectoriesWritable(join(directory, item.name));
  }
}

const endpoint = '/api/research/strategy-validation';
const expected = {
  volume_stall: [1063, 1062, 552, 899, 1059, 551, -0.00602039269],
  sma5_close: [23207, 23073, 12074, 19242, 23014, 12023, -0.00059564934],
  sma10_close: [15392, 15269, 7880, 12356, 15235, 7851, -0.00098349605],
  sma20_close: [10201, 10119, 5312, 8052, 10096, 5292, -0.00046878607],
};

try {
  const port = await listenerPort();
  const origin = `http://127.0.0.1:${port}`;
  const playwright = process.env.PLAYWRIGHT_CORE_PATH || join(homedir(), '.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs');
  const { chromium } = await import(pathToFileURL(playwright).href);
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  const context = await browser.newContext({ viewport: { width: 1750, height: 1050 } });
  const external = [];
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin === origin) return route.continue();
    external.push(url.hostname);
    return route.abort();
  });
  page = await context.newPage();
  page.on('response', response => {
    const url = new URL(response.url());
    if (url.pathname.startsWith(endpoint)) {
      traffic.push({ path: url.pathname, method: response.request().method(), status: response.status() });
    }
  });
  const ready = page.waitForResponse(response =>
    response.url().endsWith(endpoint) && response.request().method() === 'GET');
  await page.goto(`${origin}/#/simulation/strategies`, { waitUntil: 'domcontentloaded', timeout: 25000 });
  await page.getByRole('heading', { name: '策略验证', exact: true }).waitFor();
  assert.equal((await ready).status(), 200);
  await page.locator('#strategy-archive:enabled').waitFor();
  const uploadedResponse = page.waitForResponse(response =>
    response.url().endsWith(`${endpoint}/datasets`) && response.request().method() === 'POST');
  await page.locator('#strategy-archive').setInputFiles(archive);
  await page.getByText('选定 exit-backtest.zip', { exact: true }).waitFor();
  await page.getByRole('button', { name: '导入冻结行情', exact: true }).click();
  const uploaded = await uploadedResponse;
  assert.equal(uploaded.status(), 201, await uploaded.text());
  const dataset = await uploaded.json();
  assert.equal(dataset.sha256, archiveDigest);

  const runResponse = page.waitForResponse(response =>
    response.url().endsWith(`${endpoint}/runs`) && response.request().method() === 'POST',
  { timeout: 120000 });
  await page.getByRole('button', { name: '运行策略验证', exact: true }).click();
  const execution = await runResponse;
  assert.equal(execution.status(), 201, await execution.text());
  const created = await execution.json();
  assert.equal(created.dataset_id, dataset.id);
  const opened = await context.request.get(`${origin}${endpoint}/runs/${created.id}`);
  assert.equal(opened.status(), 200, await opened.text());
  const run = await opened.json();
  assert.equal(run.dataset_id, dataset.id);
  assert.equal(run.horizon, 5);
  assert.deepEqual(new Set(run.rules.map(row => row.id)), new Set(Object.keys(expected)));
  for (const row of run.rules) {
    const [signals, holdN, down, paired, sellN, wins, sellMean] = expected[row.id];
    assert.deepEqual([
      row.signal_count, row.downside.n, row.downside.events, row.matched.n,
      row.sale.n, row.sale.events,
    ], [signals, holdN, down, paired, sellN, wins], row.id);
    assert.ok(Math.abs(row.sale.mean - sellMean) < 1e-8, row.id);
  }
  await page.locator('[data-strategy-result]').getByRole('columnheader', { name: '次日卖出胜率' }).waitFor();
  await page.locator('[data-strategy-events]').getByRole('columnheader', { name: '相似对照股票' }).waitFor();
  const eventApi = `${endpoint}/runs/${run.id}/events`;
  const sample = [];
  for (const [rule, [count]] of Object.entries(expected)) {
    const response = await context.request.get(`${origin}${eventApi}?rule=${rule}&offset=0&limit=50`);
    assert.equal(response.status(), 200, await response.text());
    const payload = await response.json();
    assert.equal(payload.total, count, rule);
    assert.equal(payload.items.length, 50);
    assert.ok(payload.items.every(item => item.rule === rule && item.date && item.ticker));
    assert.ok(payload.items.some(item => item.control_ticker && Number.isFinite(item.control_return)));
    sample.push({ rule, firstRow: payload.items[0] });
  }
  const nextResponse = page.waitForResponse(response => {
    const url = new URL(response.url());
    return url.pathname === eventApi && Number(url.searchParams.get('offset')) > 0;
  });
  await page.getByRole('button', { name: '下一页', exact: true }).click();
  const nextPage = await nextResponse;
  assert.equal(nextPage.status(), 200, await nextPage.text());
  const nextItems = await nextPage.json();
  assert.ok(nextItems.offset > 0 && nextItems.items.length > 0);
  await page.locator('[data-strategy-result]').screenshot({ path: join(output, 'strategy-results.png') });
  await page.locator('[data-strategy-events] table').scrollIntoViewIfNeeded();
  await page.screenshot({ path: join(output, 'strategy-events.png') });

  const configuredResult = page.waitForResponse(response =>
    response.url().endsWith(`${endpoint}/runs`) && response.request().method() === 'POST',
  { timeout: 120000 });
  await page.locator('#strategy-horizon').selectOption('10');
  for (const rule of ['sma5_close', 'sma10_close', 'sma20_close']) {
    await page.locator(`#strategy-rule-${rule}`).uncheck();
  }
  await page.getByRole('button', { name: '运行策略验证', exact: true }).click();
  const configuredResponse = await configuredResult;
  assert.equal(configuredResponse.status(), 201, await configuredResponse.text());
  const configured = await configuredResponse.json();
  assert.notEqual(configured.id, run.id);
  const configuredRead = await context.request.get(`${origin}${endpoint}/runs/${configured.id}`);
  assert.equal(configuredRead.status(), 200, await configuredRead.text());
  const alternate = await configuredRead.json();
  assert.equal(alternate.horizon, 10);
  assert.deepEqual(alternate.rules.map(item => item.id), ['volume_stall']);
  assert.equal(alternate.rules[0].matched.n, 892);
  assert.equal(alternate.rules[0].sale.n, 1053);
  const reread = await context.request.get(`${origin}${endpoint}/runs/${run.id}`);
  assert.equal(reread.status(), 200, await reread.text());
  const originalRun = await reread.json();
  assert.deepEqual(originalRun.rules, run.rules);
  assert.deepEqual(originalRun.configuration, run.configuration);
  assert.deepEqual(external, []);
  await writeFile(join(output, 'strategy-validation.json'), JSON.stringify({
    archiveDigest, run, alternate, sample, nextPageOffset: nextItems.offset,
    verified: ['real_browser_upload', 'real_host_calculation', 'four_prior_reference_results',
      'matched_event_fields', 'ui_pagination', 'changed_rules_and_horizon', 'persisted_run_reread'],
  }, null, 2) + '\n');
  console.log('Frozen exit-strategy ZIP, all four rules, browser pagination and persisted run passed.');
} catch (error) {
  const status = await page?.locator('.strategy-validation [role="alert"]').allTextContents();
  await writeFile(join(output, 'failure.txt'), String(error.stack || error) + '\n' + JSON.stringify({ traffic, status, stderr }) + '\n');
  throw error;
} finally {
  try {
    await browser?.close();
  } finally {
    child.kill('SIGTERM');
    await closed;
    await makeDirectoriesWritable(root);
    await rm(root, { recursive: true, force: true });
  }
}
