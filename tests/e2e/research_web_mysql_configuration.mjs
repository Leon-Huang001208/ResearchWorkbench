/** Local, mocked MySQL configuration acceptance. Never contacts a database or model. */
import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath, pathToFileURL} from 'node:url';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ui = path.join(project, 'app/research_web/ui');
const origin = new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if (origin.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(origin.hostname)) {
  throw new Error('MySQL UI acceptance is limited to a local Research Web service');
}
const output = path.join(project, 'outputs/research-web-mysql-acceptance');
const logFile = path.join(project, 'logs/research-web-mysql-acceptance.jsonl');
const viewports = [[390, 844], [768, 1024], [1280, 720], [1440, 900]];
const themes = ['light', 'dark'];
const results = [];
let browser;

const json = body => ({status: 200, contentType: 'application/json', body: JSON.stringify(body)});
const readiness = state => ({
  code_exists: true,
  integration_completed: true,
  configured: state.configured && state.secret_configured,
  dependency_ready: true,
  allowed: true,
  integration_state: state.configured && state.secret_configured ? 'ready' : 'blocked_config',
  health: state.health,
  callable: state.configured && state.secret_configured && state.health !== 'unavailable',
});
const source = state => ({
  id: 'mysql', name: '用户 MySQL 数据库', family: 'datahub', source_type: 'database',
  description: '用户在本机配置；仅支持受控单表只读查询。', auth_type: 'account', config_keys: [],
  dependencies: ['PyMySQL', 'keyring'], markets: ['用户数据库'], fee: 'account',
  limitations: ['required_no_verify 不验证 TLS 证书。', 'tls_certificate_unverified'], readiness: readiness(state),
  bindings: [
    {capability: {id: 'database_schema', name: '数据库目录'}, datasets: ['databases', 'tables', 'columns'], priority: 1, implemented: true},
    {capability: {id: 'table_query', name: '数据库单表查询'}, datasets: ['single_table_select'], priority: 1, implemented: true},
  ],
});
const catalog = state => ({
  summary: {capabilities: 15, sources: 22, callable_sources: readiness(state).callable ? 1 : 0, needs_configuration: readiness(state).callable ? 0 : 1, unavailable: 0},
  capabilities: [
    {id: 'database_schema', name: '数据库目录', category: '数据源', description: '逐级读取数据库结构。', tool_id: 'datahub_get_database_schema', source_count: 1, callable_source_count: readiness(state).callable ? 1 : 0, fields: ['database', 'table_name'], markets: ['用户数据库'], assets: ['数据库']},
    {id: 'table_query', name: '数据库单表查询', category: '数据源', description: '受控参数化单表查询。', tool_id: 'datahub_query_table', source_count: 1, callable_source_count: readiness(state).callable ? 1 : 0, fields: ['用户选择列'], markets: ['用户数据库'], assets: ['表']},
  ],
  sources: [source(state)], bindings: [],
});

async function routeLocalUI(route) {
  const request = route.request();
  const url = new URL(request.url());
  if (url.origin !== origin.origin) {
    await route.abort('blockedbyclient');
    return true;
  }
  if (url.pathname === '/' || url.pathname.startsWith('/static/')) {
    const relative = url.pathname === '/' ? 'index.html' : url.pathname.slice('/static/'.length);
    const target = path.resolve(ui, relative);
    if (!target.startsWith(ui + path.sep) && target !== path.join(ui, 'index.html')) {
      await route.abort('blockedbyclient');
      return true;
    }
    const types = {css: 'text/css', js: 'text/javascript', mjs: 'text/javascript', html: 'text/html', png: 'image/png'};
    try {
      await route.fulfill({body: await readFile(target), contentType: types[path.extname(target).slice(1)] || 'application/octet-stream'});
      return true;
    } catch {
      await route.fulfill({status: 404});
      return true;
    }
  }
  return false;
}

async function assertContained(page) {
  const metrics = await page.evaluate(() => ({
    innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    mainWidth: document.querySelector('#main')?.clientWidth,
    mainScrollWidth: document.querySelector('#main')?.scrollWidth,
  }));
  assert.ok(metrics.scrollWidth <= metrics.innerWidth, JSON.stringify(metrics));
  assert.ok(metrics.mainScrollWidth <= metrics.mainWidth, JSON.stringify(metrics));
  return metrics;
}

async function runCase(width, height, theme) {
  const context = await browser.newContext({viewport: {width, height}, colorScheme: theme});
  await context.addInitScript(value => localStorage.setItem('research-web.appearance.v1', value), theme);
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  const errors = [];
  const savedPayloads = [];
  const state = {configured: false, secret_configured: false, health: 'untested', failNext: false};
  page.on('pageerror', error => errors.push(error.name));
  await page.route('**/*', async route => {
    if (await routeLocalUI(route)) return;
    const request = route.request();
    const url = new URL(request.url());
    if (url.pathname === '/api/research/data/sources/mysql/configuration') {
      if (request.method() === 'GET') return route.fulfill(json({...state, credential_store_available: true, restart_required: state.configured, failure_code: null}));
      if (request.method() === 'PUT') {
        const payload = request.postDataJSON();
        savedPayloads.push(payload);
        if (state.failNext) {
          state.failNext = false;
          return route.fulfill({status: 503, contentType: 'application/json', body: JSON.stringify({error: {code: 'credential_store_unavailable', message: '本机凭据库或连接配置不可用'}})});
        }
        state.configured = true;
        state.secret_configured ||= Boolean(payload.password);
        Object.assign(state, {label: payload.label, host: payload.host, port: payload.port, user: payload.user, charset: payload.charset, tls_mode: payload.tls_mode});
        return route.fulfill(json({...state, credential_store_available: true, restart_required: true, failure_code: null}));
      }
      if (request.method() === 'DELETE') {
        Object.assign(state, {configured: false, secret_configured: false, health: 'untested'});
        return route.fulfill(json({deleted: true}));
      }
    }
    if (url.pathname === '/api/research/data/catalog') return route.fulfill(json(catalog(state)));
    if (url.pathname === '/api/research/data/sources/mysql' && request.method() === 'GET') return route.fulfill(json(source(state)));
    if (url.pathname === '/api/research/data/sources/mysql/probes' && request.method() === 'POST') {
      state.health = 'healthy';
      return route.fulfill({status: 202, contentType: 'application/json', body: JSON.stringify({id: 'mysql-probe', source_id: 'mysql', status: 'checking', health: 'checking', duration_ms: null})});
    }
    if (url.pathname === '/api/research/data/probes/mysql-probe' && request.method() === 'GET') {
      return route.fulfill(json({id: 'mysql-probe', source_id: 'mysql', status: 'completed', health: 'healthy', duration_ms: 8, failure_code: null}));
    }
    if (!['GET', 'HEAD'].includes(request.method())) {
      errors.push(`unexpected_${request.method()}_${url.pathname}`);
      return route.abort('blockedbyclient');
    }
    return route.continue();
  });

  try {
    await page.goto(`${origin.origin}/#/settings`, {waitUntil: 'domcontentloaded'});
    await page.locator('#mysql-settings-form').waitFor();
    assert.equal(await page.locator('#mysql-password').inputValue(), '');
    await page.locator('input[name="label"]').fill('阿里云因子库');
    await page.locator('input[name="host"]').fill('db.example.test');
    await page.locator('input[name="user"]').fill('research_reader');
    await page.locator('select[name="charset"]').selectOption('gbk');
    await page.locator('#mysql-password').fill('acceptance-secret');
    await page.getByRole('button', {name: '保存连接', exact: true}).click();
    await page.getByText('MySQL 连接已保存；密码不会回填。', {exact: true}).waitFor();
    assert.equal(await page.locator('#mysql-password').inputValue(), '');
    assert.equal(savedPayloads[0].password, 'acceptance-secret');
    await page.locator('input[name="label"]').fill('本机因子库');
    await page.getByRole('button', {name: '保存连接', exact: true}).click();
    assert.equal('password' in savedPayloads[1], false, 'blank password must retain the credential');
    const settingsMetrics = await assertContained(page);
    if (width <= 768) {
      const undersized = await page.locator('#mysql-settings-form :is(input,select,button,a.button)').evaluateAll(elements => elements.filter(element => {
        const box = element.getBoundingClientRect();
        return box.width > 0 && box.height > 0 && box.height < 43.5;
      }).map(element => `${element.tagName}:${element.textContent || element.name}`));
      assert.deepEqual(undersized, [], 'mobile MySQL controls must keep 44px touch height');
    }
    await page.screenshot({path: path.join(output, `${theme}-settings-${width}x${height}.png`), fullPage: true});

    await page.goto(`${origin.origin}/#/skills?kind=data`, {waitUntil: 'domcontentloaded'});
    await page.getByRole('tab', {name: '数据', exact: true}).click();
    await page.getByRole('tab', {name: '按数据来源', exact: true}).click();
    const card = page.locator('.source-data-card').filter({hasText: '用户 MySQL 数据库'});
    await card.getByRole('button', {name: '查看详情', exact: true}).click();
    const stateChain = page.locator('.connection-state-chain[aria-label="MySQL 连接状态"]');
    await stateChain.waitFor();
    await page.getByRole('button', {name: '检测这个来源', exact: true}).click();
    await stateChain.locator('span.done', {hasText: '可调用'}).waitFor();
    await page.getByText('已接入 / 健康', {exact: true}).waitFor();
    const dataMetrics = await assertContained(page);
    await page.screenshot({path: path.join(output, `${theme}-datahub-${width}x${height}.png`), fullPage: true});

    if (width === 1440 && theme === 'light') {
      await page.goto(`${origin.origin}/#/settings`);
      await page.locator('#mysql-settings-form').waitFor();
      state.failNext = true;
      await page.locator('#mysql-password').fill('one-time-failure-secret');
      await page.getByRole('button', {name: '保存连接', exact: true}).click();
      await page.getByRole('alert').filter({hasText: '本机凭据库或连接配置不可用'}).waitFor();
      assert.equal(await page.locator('#mysql-password').inputValue(), '', 'failed saves must also clear the browser password input');
      await page.getByRole('button', {name: '移除', exact: true}).click();
      await page.getByText('本机 MySQL 配置和系统凭据已移除；历史快照保持可读。', {exact: true}).waitFor();
      assert.equal(state.configured, false);
    }
    assert.deepEqual(errors, []);
    results.push({width, height, theme, status: 'passed', settingsMetrics, dataMetrics});
  } finally {
    await context.close();
  }
}

try {
  await mkdir(output, {recursive: true});
  await mkdir(path.dirname(logFile), {recursive: true});
  const {chromium} = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
  browser = await chromium.launch({headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  for (const theme of themes) for (const [width, height] of viewports) await runCase(width, height, theme);
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify({status: 'passed', realDatabaseContacted: false, results}, null, 2));
  await writeFile(logFile, JSON.stringify({event: 'research_web_mysql_acceptance', status: 'passed', checks: results.length}) + '\n');
  console.log(`MySQL configuration UI: ${results.length} theme/viewport cases passed; no database or model calls`);
} catch (error) {
  await mkdir(output, {recursive: true});
  await mkdir(path.dirname(logFile), {recursive: true});
  await writeFile(path.join(output, 'receipt.json'), JSON.stringify({status: 'failed', error: error.message, realDatabaseContacted: false, results}, null, 2));
  await writeFile(logFile, JSON.stringify({event: 'research_web_mysql_acceptance', status: 'failed', error_type: error.name}) + '\n');
  console.error(error.stack || error.message);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
