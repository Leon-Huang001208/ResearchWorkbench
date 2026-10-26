/** Isolated synthetic browser acceptance. No resident services or model requests. */
import assert from 'node:assert/strict';
import { appendFile, mkdir, readFile, writeFile } from 'node:fs/promises';
import http from 'node:http';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const ui = path.join(root, 'app/research_web/ui');
const output = path.join(root, 'logs/codex-navigation-browser');
const preview = process.argv.includes('--preview');
const forwardOnly = process.argv.includes('--focus-forward');
const submitOnly = process.argv.includes('--focus-submit');
const menusOnly = process.argv.includes('--focus-menus');
const dialogsOnly = process.argv.includes('--focus-project-dialog');
const membershipOnly = process.argv.includes('--focus-project-membership');
const statusOnly = process.argv.includes('--focus-session-status');
const composerOnly = process.argv.includes('--focus-bottom-composer');
const searchOnly = process.argv.includes('--focus-search-close');
const welcomeOnly = process.argv.includes('--focus-claw-welcome');
const receiptName = preview ? 'preview-receipt.json' : welcomeOnly ? 'claw-welcome-receipt.json' : searchOnly ? 'search-close-receipt.json' : composerOnly ? 'bottom-composer-receipt.json' : statusOnly ? 'session-status-receipt.json' : membershipOnly ? 'project-membership-receipt.json' : dialogsOnly ? 'project-dialog-receipt.json' : menusOnly ? 'menus-receipt.json' : submitOnly ? 'submit-receipt.json' : forwardOnly ? 'forward-receipt.json' : 'receipt.json';
const report = { status: 'running', environment: 'isolated Chrome synthetic API; no resident HTTP or model calls', checks: [], failures: [], writes: [], screenshots: [] };
const modes = ['fingpt', 'claw'];
const metadata = Object.fromEntries(modes.map(mode => [mode, { mode, revision: 0, pinned: [], project_order: ['default', 'p1', 'p2'] }]));
const projects = Object.fromEntries(modes.map(mode => [mode, ['default', 'p1', 'p2'].map((id, i) => ({ id, name: i ? `${mode} 项目 ${i} ${'长项目标题'.repeat(12)}` : '默认项目', archived: false }))]));
const sessions = modes.flatMap(mode => Array.from({ length: 27 }, (_, i) => ({ id: `${mode}-${i}`, mode, title: `${mode} 会话 ${i} ${'长标题测试'.repeat(15)}`, status: i ? 'completed' : 'running', project_id: 'default', updated_at: 2000 - i })));
const group = { id: 'q-native', seq: 2, items: [{ id: 'one', question: '请选择研究方向', options: [{ label: '基本面（推荐）', description: '比较企业经营' }, { label: '技术面' }] }, { id: 'two', question: '请选择需要的资料', multiSelect: true, options: [{ label: '公告' }, { label: '财务' }, { label: '新闻' }] }] };
const details = Object.fromEntries(sessions.map(s => [s.id, { ...s, messages: [{ id: 'user', role: 'user', text: '请先确认研究参数', seq: 1 }], questions: s.id.endsWith('-0') ? [structuredClone(group)] : [], question_history: [], activities: [], approvals: [], files: [{ id: 'current-file', name: '当前会话资料.md', kind: 'outputs', url: '/fixture-file', preview_url: '/fixture-file' }], datasets: [], subagents: [], can_cancel: false }]));
const streams = new Map();
const sessionState = id => {
  const detail = details[id]; const waitingForAnswer = Boolean(detail?.questions?.length);
  return { status: waitingForAnswer ? 'waiting_input' : detail?.status === 'waiting_input' ? 'running' : detail?.status || sessions.find(s => s.id === id)?.status || 'idle', waitingForAnswer };
};
const fixtureDetail = id => ({ ...details[id], ...sessionState(id) });
let failNavigation = 0;
let failAnswer = false;
let failProjectCreate = false;
let failMove = false;
let holdProjectCreate = false;
let releaseProjectCreate;
let projectCreateStarted;
let holdSearch = false;
let releaseSearch;
let searchStarted;
const send = (response, status, payload) => response.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' }).end(JSON.stringify(payload));
const broadcast = id => { for (const response of streams.get(id) || []) response.write(`event: snapshot\ndata: ${JSON.stringify(fixtureDetail(id))}\n\n`); };
const server = http.createServer(async (request, response) => {
  try {
    const url = new URL(request.url, 'http://127.0.0.1');
    const endpoint = url.pathname.replace('/api/research', '');
    if (url.pathname.startsWith('/api/research/')) {
      let body = {};
      if (!['GET', 'HEAD'].includes(request.method)) {
        let input = ''; for await (const chunk of request) input += chunk;
        body = input ? JSON.parse(input) : {};
        report.writes.push({ method: request.method, endpoint, query: url.search, body });
      }
      const nav = endpoint.match(/^\/navigation\/(claw|fingpt)$/);
      if (endpoint === '/sessions/search' && request.method === 'POST') {
        if (holdSearch && body.query === '迟到验收') { holdSearch = false; await new Promise(resolve => { releaseSearch = resolve; searchStarted?.(); }); }
        return send(response, 200, { source: 'native_dsh', items: sessions.filter(s => s.mode === body.mode).slice(0, 3).map(s => ({ id: s.id, mode: s.mode, title: s.title, snippet: body.query === '迟到验收' ? '迟到响应片段' : '合成原生正文片段' })), has_more: false, unavailable_count: 0 });
      }
      if (nav) {
        const mode = nav[1];
        if (request.method === 'PATCH') {
          if (failNavigation) { const status = failNavigation; failNavigation = 0; return send(response, status, { error: { code: status === 409 ? 'navigation_changed' : 'fixture_failed', message: `夹具导航保存失败 ${status}` } }); }
          if (body.revision !== metadata[mode].revision) return send(response, 409, { error: { code: 'navigation_changed', message: '导航版本已变化' } });
          metadata[mode] = { mode, revision: body.revision + 1, pinned: body.pinned, project_order: body.project_order };
        }
        return send(response, 200, metadata[mode]);
      }
      if (endpoint === '/projects' || endpoint === '/claw/projects') {
        const mode = url.searchParams.get('mode') || 'claw';
        if (request.method === 'POST') { if (holdProjectCreate) { holdProjectCreate = false; await new Promise(resolve => { releaseProjectCreate = resolve; projectCreateStarted?.(); }); } if (failProjectCreate) { failProjectCreate = false; return send(response, 500, { error: { code: 'fixture_project_failed', message: '夹具创建失败，请保留草稿重试' } }); } const item = { id: `${mode}-created`, name: body.name, archived: false }; projects[mode].push(item); return send(response, 201, item); }
        return send(response, 200, { items: projects[mode] });
      }
      const projectMatch = endpoint.match(/^\/projects\/([^/]+)$/);
      if (projectMatch) {
        const mode = url.searchParams.get('mode') || 'claw'; const item = projects[mode].find(p => p.id === projectMatch[1]);
        if (!item) return send(response, 404, { error: { message: '夹具项目不存在' } });
        if (request.method === 'PATCH') Object.assign(item, body);
        return send(response, 200, { ...item, sessions: sessions.filter(s => s.mode === mode && s.project_id === item.id), files: [], datasets: [] });
      }
      const session = endpoint.match(/^\/sessions\/([^/]+)(.*)$/);
      if (session && details[session[1]]) {
        const [ , id, suffix ] = session;
        if (suffix === '/events') {
          response.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' }); response.write(': isolated fixture\n\n');
          if (!streams.has(id)) streams.set(id, new Set()); streams.get(id).add(response); request.on('close', () => streams.get(id)?.delete(response)); return;
        }
        if (suffix.startsWith('/questions/') && request.method === 'POST') {
          if (failAnswer) { failAnswer = false; return send(response, 500, { error: { code: 'fixture_failed', message: '夹具原生回答失败，可重试' } }); }
          details[id].question_history = [{ ...group, answers: body.answers }]; details[id].questions = []; return send(response, 200, { ok: true });
        }
        if (suffix === '/project' && request.method === 'PUT') { if (failMove) { failMove = false; return send(response, 500, { error: { code: 'fixture_move_failed', message: '夹具移动失败，原项目位置保留' } }); } details[id].project_id = body.project_id; sessions.find(s => s.id === id).project_id = body.project_id; return send(response, 200, details[id]); }
        return send(response, 200, suffix === '/files' ? { items: details[id].files } : fixtureDetail(id));
      }
      if (endpoint === '/sessions') return send(response, 200, { items: sessions.map(item => ({ ...item, updated_at: details[item.id]?.updated_at ?? item.updated_at, ...sessionState(item.id) })) });
      if (endpoint === '/runtime') return send(response, 200, { connected: true, credential_configured: true, provider: 'fixture' });
      if (endpoint === '/models') return send(response, 200, { groups: [], failures: [] });
      return send(response, 200, { items: [] });
    }
    const file = path.resolve(ui, url.pathname === '/' ? 'index.html' : url.pathname.replace(/^\/static\//, ''));
    if (!file.startsWith(ui + path.sep)) throw new Error('unsafe static path');
    let bytes = await readFile(file);
    if (preview && path.extname(file) === '.html') bytes = Buffer.from(bytes.toString().replace('<title>', '<title>隔离夹具预览 · ').replace('</body>', '<div role="status" style="position:fixed;right:12px;top:8px;z-index:10000;background:#fff4d2;color:#543d00;border:1px solid #c8a85d;border-radius:5px;padding:4px 8px;font:11px system-ui;pointer-events:none">隔离夹具预览 · 测试会话 · 不调用模型</div></body>'));
    response.writeHead(200, { 'content-type': ({ '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.json': 'application/json', '.css': 'text/css', '.png': 'image/png', '.svg': 'image/svg+xml' })[path.extname(file)] || 'application/octet-stream' }).end(bytes);
  } catch (error) { report.failures.push(`fixture:${error.code || error.name}`); response.writeHead(500).end('fixture error'); }
});

let browser;
const check = async (name, fn) => { try { await fn(); report.checks.push(name); console.log(`PASS ${name}`); } catch (error) { report.failures.push({ name, error: error.stack }); console.log(`FAIL ${name}: ${error.message}`); } };
const shot = async (page, name) => { const target = path.join(output, `${name}.png`); await page.screenshot({ path: target }); report.screenshots.push(target); };
async function assertSquareIcons(page, selector, { centeredButtons = false } = {}) {
  const metrics = await page.evaluate(value => [...document.querySelectorAll(value)].map(element => {
    const rect = element.getBoundingClientRect(); const button = element.closest('button'); const parent = button?.getBoundingClientRect();
    return { width: rect.width, height: rect.height, visible: !!element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden', button: !!button, centerX: parent ? Math.abs(rect.x + rect.width / 2 - parent.x - parent.width / 2) : 0, centerY: parent ? Math.abs(rect.y + rect.height / 2 - parent.y - parent.height / 2) : 0, inside: !parent || (rect.left >= parent.left - .5 && rect.right <= parent.right + .5 && rect.top >= parent.top - .5 && rect.bottom <= parent.bottom + .5) };
  }), selector);
  const visible = metrics.filter(item => item.visible);
  if (!visible.length) {
    const state = await page.evaluate(() => ({ hash: location.hash, sidebar: document.querySelector('.codex-sidebar')?.className, sidebarDisplay: document.querySelector('.codex-sidebar') && getComputedStyle(document.querySelector('.codex-sidebar')).display, mode: document.querySelector('.codex-sidebar')?.dataset.navMode, shell: document.querySelector('.app-shell')?.className, width: innerWidth }));
    await writeFile(path.join(output, 'icon-visibility-failure.json'), JSON.stringify({ selector, metrics, state }, null, 2)); await shot(page, 'icon-visibility-failure');
  }
  assert.ok(visible.length > 0, `no visible icons: ${selector}`);
  for (const item of visible) {
    assert.ok(item.width > 0 && item.height > 0 && Math.abs(item.width - item.height) <= .5, JSON.stringify(item));
    if (centeredButtons && item.button) assert.ok(item.inside && item.centerX <= .5 && item.centerY <= .5, JSON.stringify(item));
  }
}
try {
  await mkdir(output, { recursive: true });
  if (preview && process.env.RWB_PREVIEW_STATE_PATH) {
    let restored;
    try { restored = JSON.parse(await readFile(process.env.RWB_PREVIEW_STATE_PATH, 'utf8')); }
    catch (error) { if (error.code !== 'ENOENT') throw error; report.previewRestore = { restored: false, reason: 'state_file_missing' }; }
    if (restored) {
      if (!Array.isArray(restored.sessions) || !restored.details || typeof restored.details !== 'object' || Array.isArray(restored.details) || modes.some(mode => !Array.isArray(restored.projects?.[mode]) || restored.metadata?.[mode]?.mode !== mode || !Number.isInteger(restored.metadata[mode].revision) || !Array.isArray(restored.metadata[mode].pinned) || !Array.isArray(restored.metadata[mode].project_order)) || restored.sessions.some(item => !item || typeof item.id !== 'string' || !modes.includes(item.mode) || !Object.hasOwn(restored.details, item.id))) throw new Error('invalid synthetic preview state');
      for (const mode of modes) { metadata[mode] = restored.metadata[mode]; projects[mode] = restored.projects[mode]; }
      sessions.splice(0, sessions.length, ...restored.sessions); for (const id of Object.keys(details)) delete details[id];
      for (const [id, detail] of Object.entries(restored.details)) Object.defineProperty(details, id, { value: detail, configurable: true, enumerable: true, writable: true });
      report.previewRestore = { restored: true, sessions: sessions.length, projects: modes.reduce((sum, mode) => sum + projects[mode].length, 0) };
    }
  }
  const previewPort = preview && process.env.RWB_PREVIEW_PORT ? Number(process.env.RWB_PREVIEW_PORT) : 0;
  if (!Number.isInteger(previewPort) || previewPort < 0 || previewPort > 65535) throw new Error('invalid isolated preview port');
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(previewPort, '127.0.0.1', resolve); });
  const origin = `http://127.0.0.1:${server.address().port}`;
  if (preview) {
    report.status = 'preview';
    console.log(JSON.stringify({ status: 'preview', origin, routes: [`${origin}/#/fingpt`, `${origin}/#/claw`, `${origin}/#/claw?session=claw-0`, `${origin}/#/fingpt?session=fingpt-0`], environment: report.environment, ...(report.previewRestore ? { previewRestore: report.previewRestore } : {}) }));
    await new Promise(resolve => { process.once('SIGTERM', resolve); process.once('SIGINT', resolve); });
  } else {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.on('pageerror', error => { report.failures.push(`pageerror:${error.message}`); console.log(`PAGEERROR ${error.message}`); });
  if (welcomeOnly) {
    for (const theme of ['light', 'dark']) for (const width of [390, 1440]) await check(`${theme}/${width}: Claw welcome without examples, composer and active empty projections`, async () => {
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/claw`);
      await page.evaluate(value => localStorage.setItem('research-web.appearance.v1', value), theme); await page.reload();
      await page.locator('.claw-welcome h1').waitFor();
      assert.equal(await page.locator('.claw-examples, .claw-cases, .claw-case-card, [data-claw-case-category]').count(), 0);
      assert.equal(await page.getByText('查看示例', { exact: true }).count(), 0);
      await page.locator('#prompt').fill('');
      const bounds = await page.evaluate(() => { const welcome = document.querySelector('.claw-welcome').getBoundingClientRect(); const editor = document.querySelector('#composer').getBoundingClientRect(); return { welcomeBottom: welcome.bottom, editorTop: editor.top, editorBottom: editor.bottom, height: innerHeight, overflow: document.documentElement.scrollWidth > innerWidth }; });
      assert.equal(bounds.overflow, false); assert.ok(bounds.welcomeBottom <= bounds.editorTop + 1); assert.ok(bounds.editorBottom <= bounds.height, JSON.stringify(bounds));
      await shot(page, `claw-welcome-${theme}-${width}`);
      await page.goto(`${origin}/#/claw?view=plans`);
      await page.locator('[data-claw-case="schedule"]').click();
      await page.locator('.claw-welcome').waitFor();
      await page.waitForFunction(() => document.querySelector('#prompt')?.value.includes('每日收盘点评'));
      assert.ok((await page.locator('#prompt').inputValue()).includes('每日收盘点评'));
      assert.equal(await page.locator('.claw-examples, .claw-cases').count(), 0);
      await page.locator('#prompt').fill('保留编辑器草稿');
      assert.equal(await page.locator('#prompt').inputValue(), '保留编辑器草稿');
      assert.equal(report.writes.filter(w => w.endpoint === '/sessions').length, 0);
      const id = 'claw-8'; details[id] = { ...details[id], status: 'idle', messages: [], questions: [], activities: [], question_history: [], files: [] };
      await page.goto(`${origin}/#/claw?session=${id}`); await page.locator('.claw-welcome').waitFor();
      for (const status of ['running', 'failed', 'completed']) {
        details[id].status = status; broadcast(id); await page.locator('[data-conversation-scroll]').waitFor(); assert.equal(await page.locator('.claw-welcome, .empty-symbol').count(), 0);
      }
      details[id].questions = [{ ...group, seq: undefined }]; broadcast(id); await page.locator('.question-form').waitFor();
      assert.equal(await page.locator('.claw-welcome, .empty-symbol').count(), 0); await shot(page, `claw-pending-${theme}-${width}`);
    });
    for (const mode of modes) await check(`${mode}: full-row single choices, double-click guard, keyboard, multiple choices and explicit final submit`, async () => {
      const id = `${mode}-9`; const q = { id: `row-${mode}`, items: [
        { id: 'one', question: '第一题', options: [{ label: '选项甲', description: '甲的说明' }, { label: '选项乙' }] },
        { id: 'two', question: '第二题', options: [{ label: '选项丙', description: '丙的说明' }, { label: '选项丁' }] },
        { id: 'multi', question: '第三题', multiSelect: true, options: [{ label: '多选甲' }, { label: '多选乙' }] },
        { id: 'last', question: '最后一题', options: [{ label: '确认甲' }, { label: '确认乙' }] },
      ] };
      details[id] = { ...details[id], status: 'waiting_input', messages: [], questions: [q] };
      await page.setViewportSize({ width: 1440, height: 900 }); await page.goto(`${origin}/#/${mode}?session=${id}`); await page.locator('[data-q-index="0"]').waitFor();
      await page.locator('[name="custom-0"]').fill('保留补充');
      await page.locator('.question-option-copy strong').first().dblclick(); await page.locator('[data-q-index="1"]').waitFor();
      assert.equal(await page.evaluate(() => document.activeElement.matches('legend')), true);
      assert.equal(await page.locator('[data-q-index="2"]').count(), 0, 'double click must not answer a second question');
      await page.locator('[data-q-page="prev"]').click(); assert.equal(await page.locator('[name="custom-0"]').inputValue(), '保留补充');
      await page.waitForTimeout(320); await page.locator('.codex-question-option .muted').first().click(); await page.locator('[data-q-index="1"]').waitFor();
      await page.waitForTimeout(320); const row = page.locator('.codex-question-option').first(); const box = await row.boundingBox();
      await row.click({ position: { x: box.width - 50, y: box.height / 2 } }); await page.locator('[data-q-index="2"]').waitFor();
      await page.waitForTimeout(320); await page.locator('.question-option-copy strong').nth(0).click(); await page.locator('.question-option-copy strong').nth(1).click();
      assert.equal(await page.locator('[data-q-index="2"]').count(), 1); assert.equal(await page.locator('.question-form input[type="checkbox"]:checked').count(), 2);
      await page.locator('.codex-question-submit [data-q-page="next"]').click(); await page.locator('[data-q-index="3"]').waitFor();
      await page.locator('input[type="radio"]').first().focus(); await page.keyboard.press('Enter');
      assert.equal(await page.locator('[data-q-index="3"]').count(), 1);
      assert.equal(report.writes.filter(w => w.endpoint.includes(`/sessions/${id}/questions/`)).length, 0);
      assert.equal(await page.locator('input[type="radio"]:checked').count(), 1);
      await page.locator('[data-q-page="prev"]').click(); await page.locator('[data-q-page="prev"]').click();
      await page.locator('input[type="radio"]').first().focus(); await page.keyboard.press('Space'); await page.locator('[data-q-index="2"]').waitFor();
      assert.equal(await page.locator('.question-form input[type="checkbox"]:checked').count(), 2);
      await page.locator('.codex-question-submit [data-q-page="next"]').click();
      await shot(page, `${mode}-row-choice-final`); await page.locator('.question-form [type="submit"]').click(); await page.locator('.question-history').waitFor();
      const writes = report.writes.filter(w => w.endpoint.includes(`/sessions/${id}/questions/`));
      assert.equal(writes.length, 1); assert.deepEqual(writes[0].body.answers.map(a => a.selected), [['选项甲'], ['选项丙'], ['多选甲', '多选乙'], ['确认甲']]);
    });
  } else if (searchOnly) {
    report.searchCoverage = [];
    for (const theme of ['light', 'dark']) for (const width of [390, 1440]) for (const mode of modes) await check(`${theme}/${width}/${mode}: search close, focus, no click-through, draft and result navigation`, async () => {
      const id = `${mode}-6`; const route = `${origin}/#/${mode}?session=${id}`; const draft = `搜索关闭后保留 ${theme} ${width} ${mode} 草稿`;
      await page.setViewportSize({ width, height: 900 }); await page.goto(route);
      await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator(`[data-conversation-scroll="${id}"]`).waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      await page.locator('#prompt').fill(draft);
      const popover = page.getByRole('dialog', { name: '搜索会话与能力', exact: true });
      const open = async () => { if (width <= 1050 && !await page.locator('.primary-rail').isVisible()) await page.locator('.topbar .menu-toggle').click(); await page.locator('.primary-rail [data-toggle-search]').click(); await popover.waitFor(); };
      const closed = async () => {
        assert.equal(await popover.isVisible(), false); assert.equal(await page.locator('#global-search').inputValue(), '');
        assert.equal(await page.evaluate(value => document.activeElement.matches(value), width <= 1050 ? '.topbar .menu-toggle' : '.primary-rail .search-trigger'), true);
        assert.equal(await page.locator('#prompt').inputValue(), draft);
      };
      await open(); await page.locator('#global-search').fill(`${mode} 会话 1 `); await page.locator('#global-search').click(); assert.equal(await popover.isVisible(), true);
      await shot(page, `search-close-${theme}-${width}-${mode}`);
      await page.locator(width <= 1050 ? '.topbar .menu-toggle' : '.new-research').click(); await closed(); assert.equal(page.url(), route);
      if (width <= 1050) assert.equal(await page.locator('.app-shell.navigation-open').count(), 0, 'outside click closes search without opening underlying drawer');
      await open(); await page.locator('#global-search').fill('会话'); await page.locator('[data-close-search]').click(); await closed();
      await open(); await page.locator('#global-search').fill('会话'); await page.keyboard.press('Escape'); await closed();
      if (width > 1050) { await open(); await page.locator('#global-search').fill('会话'); await page.locator('.primary-rail [data-toggle-search]').click(); await closed(); }
      await open(); await page.locator('#global-search').fill(`${mode} 会话 1 `); await page.locator(`[data-global-result="session"][data-session-id="${mode}-1"]`).click();
      await page.locator(`[data-conversation-scroll="${mode}-1"]`).waitFor(); assert.equal(await popover.isVisible(), false);
      await page.goto(route); await page.locator(`[data-conversation-scroll="${id}"]`).waitFor(); assert.equal(await page.locator('#prompt').inputValue(), draft);
      if (mode === 'claw') {
        holdSearch = true; const started = new Promise(resolve => { searchStarted = resolve; });
        const response = page.waitForResponse(r => r.url().endsWith('/sessions/search') && r.request().postDataJSON()?.query === '迟到验收');
        await open(); await page.locator('#global-search').fill('迟到验收'); await started; await page.locator('[data-close-search]').click(); await closed();
        releaseSearch(); searchStarted = null; await (await response).finished(); await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        await closed(); assert.equal(await page.getByText('迟到响应片段', { exact: true }).count(), 0);
      }
      assert.equal(report.writes.filter(w => w.endpoint === '/sessions' || w.endpoint.endsWith('/messages')).length, 0, 'search closure never creates sessions or sends messages');
      report.searchCoverage.push({ theme, width, mode, close: width > 1050 ? ['outside-new-chat', 'explicit-close', 'Escape', 'same-search-toggle'] : ['outside-visible-menu-no-click-through', 'explicit-close', 'Escape'], lateNativeResponse: mode === 'claw' ? 'ignored-after-close' : 'not-applicable-local-search' });
    });
  } else if (composerOnly) {
    report.composerGeometry = [];
    const longMessages = Array.from({ length: 50 }, (_, index) => ({ id: `message-${index}`, seq: index + 1, role: index % 2 ? 'assistant' : 'user', text: `第 ${index + 1} 条合成消息。\n\n${'这是供滚动和布局验收使用的正文内容。'.repeat(12)}` }));
    for (const mode of modes) {
      details[`${mode}-6`].messages = [{ id: 'short-user', role: 'user', seq: 1, text: '短会话' }, { id: 'short-answer', role: 'assistant', seq: 2, text: '简短回答。' }];
      details[`${mode}-7`].messages = structuredClone(longMessages);
      details[`${mode}-0`].messages = structuredClone(longMessages); details[`${mode}-0`].questions = [{ ...structuredClone(group), seq: 1001 }];
    }
    for (const theme of ['light', 'dark']) for (const width of [390, 820, 1440, 1920]) for (const mode of modes) await check(`${theme}/${width}/${mode}: bottom composer, message scroll, width expansion, snapshot and session draft retention`, async () => {
      const shortId = `${mode}-6`; const longId = `${mode}-7`; const draft = `保留 ${theme} ${width} ${mode} 草稿`;
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/${mode}?session=${shortId}`);
      await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator(`[data-conversation-scroll="${shortId}"]`).waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      const shortBox = await page.locator('.composer-dock').boundingBox(); assert.ok(Math.abs(shortBox.y + shortBox.height - 900) <= 1, JSON.stringify({ shortBox }));
      const connected = page.waitForResponse(r => r.url().includes(`/sessions/${longId}/events`));
      await page.goto(`${origin}/#/${mode}?session=${longId}`); await page.locator(`[data-conversation-scroll="${longId}"]`).waitFor(); await connected;
      const scroller = page.locator(`[data-conversation-scroll="${longId}"]`); assert.equal(await scroller.evaluate(el => el.scrollHeight > el.clientHeight + 100), true, 'long conversation has independent scroll extent');
      const fixedBefore = await page.locator('.composer-dock').boundingBox(); await scroller.evaluate(el => { el.scrollTop = 220; });
      const fixedAfter = await page.locator('.composer-dock').boundingBox(); assert.ok(Math.abs(fixedBefore.y - fixedAfter.y) <= 1 && Math.abs(fixedAfter.y + fixedAfter.height - 900) <= 1, JSON.stringify({ fixedBefore, fixedAfter }));
      await page.locator('#prompt').fill(draft);
      if (width > 1050) {
        const expanded = await page.locator('#composer').boundingBox(); await page.locator('[data-collapse-sidebar]').click();
        const collapsed = await page.locator('#composer').boundingBox(); assert.ok(Math.abs(collapsed.width - expanded.width - 280) <= 1, JSON.stringify({ expanded, collapsed }));
        assert.ok(Math.abs(collapsed.y + collapsed.height - expanded.y - expanded.height) <= 1, 'composer bottom stays fixed when sidebar collapses');
        assert.equal(await page.locator('#prompt').inputValue(), draft); assert.equal(await page.evaluate(() => document.activeElement.matches('.primary-rail .rail-toggle')), true, 'collapse focuses reopen control');
        await page.locator('.primary-rail .rail-toggle').click(); assert.equal(await page.evaluate(() => document.activeElement.matches('[data-collapse-sidebar]')), true, 'reopen focuses collapse control');
      } else { await page.locator('.topbar .menu-toggle').click(); await page.locator('.rail-mobile-close').click(); }
      assert.equal(await scroller.evaluate(el => el.scrollTop), 220); assert.equal(await page.locator('#prompt').inputValue(), draft);
      await page.locator('#prompt').focus(); await page.locator('#prompt').evaluate(el => el.setSelectionRange(3, 7));
      const marker = `后台 snapshot ${theme} ${width} ${mode}`; details[longId].messages.push({ id: `snapshot-${theme}-${width}`, role: 'assistant', seq: 500 + width, text: marker });
      broadcast(longId); await page.getByText(marker, { exact: true }).waitFor({ state: 'attached' });
      assert.equal(await scroller.evaluate(el => el.scrollTop), 220); assert.equal(await page.locator('#prompt').inputValue(), draft);
      assert.deepEqual(await page.locator('#prompt').evaluate(el => ({ focused: el === document.activeElement, start: el.selectionStart, end: el.selectionEnd })), { focused: true, start: 3, end: 7 });
      await page.goto(`${origin}/#/${mode}?session=${shortId}`); await page.locator(`[data-conversation-scroll="${shortId}"]`).waitFor();
      await page.goto(`${origin}/#/${mode}?session=${longId}`); await page.locator(`[data-conversation-scroll="${longId}"]`).waitFor();
      await check(`${theme}/${width}/${mode}: returning session restores scroll and draft`, async () => {
        assert.equal(await scroller.evaluate(el => el.scrollTop), 220); assert.equal(await page.locator('#prompt').inputValue(), draft);
      });
      await page.goto(`${origin}/#/${mode}?session=${mode}-0`); await page.locator('.question-form').waitFor();
      await page.locator('.codex-question-arrow[data-q-page="next"]').click(); const submit = page.locator('.question-form [type="submit"]'); await submit.click({ trial: true });
      const question = await page.evaluate(() => { const button = document.querySelector('.question-form [type="submit"]').getBoundingClientRect(); const scroll = document.querySelector('.conversation-scroll').getBoundingClientRect(); const dock = document.querySelector('.composer-dock').getBoundingClientRect(); return { top: button.top, bottom: button.bottom, scrollTop: scroll.top, scrollBottom: scroll.bottom, dockTop: dock.top, dockBottom: dock.bottom }; });
      assert.ok(question.top >= question.scrollTop - 1 && question.bottom <= question.scrollBottom + 1 && question.bottom <= question.dockTop + 1 && Math.abs(question.dockBottom - 900) <= 1, JSON.stringify(question));
      report.composerGeometry.push({ theme, width, mode, shortBox, fixedBefore, fixedAfter, question }); await shot(page, `bottom-composer-${theme}-${width}-${mode}`);
    });
  } else if (statusOnly) {
    report.statusGeometry = [];
    for (const mode of modes) {
      for (const [index, status] of [[1, 'running'], [2, 'completed'], [3, 'running'], [4, 'failed'], [5, 'cancelled']]) { sessions.find(s => s.id === `${mode}-${index}`).status = status; details[`${mode}-${index}`].status = status; }
      details[`${mode}-1`].questions = [structuredClone(group)];
      details[`${mode}-0`].model = 'fixture-model';
    }
    for (const theme of ['light', 'dark']) for (const width of [390, 1440]) for (const mode of modes) await check(`${theme}/${width}/${mode}: actual waiting, unread circle, seen persistence, new revision and mode isolation`, async () => {
      const completedId = `${mode}-2`; details[completedId].updated_at = 1998; sessions.find(s => s.id === completedId).updated_at = 1998;
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/${mode}`);
      await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ seenCompletions: {}, collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('#prompt').waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      const ensureSidebar = async () => { if (width <= 1050 && !await page.locator('.codex-sidebar').isVisible()) await page.locator('.topbar .menu-toggle').click(); };
      await ensureSidebar();
      const labels = ['等待回复', '等待回复', '执行已结束', '运行中', '失败', '已取消'];
      for (const [index, label] of labels.entries()) {
        const row = page.locator(`[data-session-menu="${mode}-${index}"]`).locator('..'); const marker = row.locator('.session-row-status');
        assert.equal(await marker.getAttribute('role'), 'status'); assert.equal(await marker.getAttribute('aria-label'), label); assert.equal(await marker.getAttribute('title'), label);
        const metrics = await row.evaluate(el => { const title = el.querySelector('.session-row-title').getBoundingClientRect(); const marker = el.querySelector('.session-row-status').getBoundingClientRect(); const icon = el.querySelector('.session-row-status svg').getBoundingClientRect(); const link = el.querySelector('.recent-item').getBoundingClientRect(); return { titleWidth: title.width, titleRight: title.right, markerLeft: marker.left, markerRight: marker.right, linkRight: link.right, iconWidth: icon.width, iconHeight: icon.height }; });
        assert.ok(metrics.titleWidth > 0 && metrics.markerLeft >= metrics.titleRight - .5 && metrics.markerRight <= metrics.linkRight + .5, JSON.stringify(metrics));
        assert.ok(Math.abs(metrics.iconWidth - 14) <= .5 && Math.abs(metrics.iconHeight - 14) <= .5, JSON.stringify(metrics));
        if (index < 2) { assert.equal(await marker.locator('circle[r="9"]').count(), 1); assert.equal(await marker.evaluate(el => el.classList.contains('is-executing')), false); }
        if (index === 2) { assert.equal(await marker.locator('circle[r="8"]').count(), 1); assert.equal(await marker.locator('path').count(), 0); assert.equal(await marker.evaluate(el => el.classList.contains('is-executing')), false); }
        if (index === 3) { assert.equal(await marker.locator('circle[r="8"]').count(), 1); assert.equal(await marker.evaluate(el => el.classList.contains('is-executing')), true); }
        if (index > 3) assert.equal(await marker.locator('path').getAttribute('d'), 'm6 6 12 12M6 18 18 6');
        report.statusGeometry.push({ theme, width, mode, index, label, ...metrics });
      }
      const waiting = page.locator(`[data-session-menu="${mode}-0"]`).locator('..').locator('.session-row-status svg');
      const animationName = index => page.evaluate(id => getComputedStyle(document.querySelector(`[data-session-menu="${id}"]`).parentElement.querySelector('.session-row-status svg')).animationName, `${mode}-${index}`);
      await page.emulateMedia({ reducedMotion: 'no-preference' }); assert.notEqual(await animationName(3), 'none'); assert.equal(await animationName(0), 'none');
      await page.emulateMedia({ reducedMotion: 'reduce' }); assert.equal(await animationName(3), 'none'); assert.equal(await animationName(0), 'none');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true); await shot(page, `session-status-${theme}-${width}-${mode}`);
      await page.locator(`.recent-item[href="#/${mode}?session=${mode}-0"]`).click(); await page.locator('.question-form').waitFor(); await ensureSidebar();
      assert.equal(await waiting.locator('circle[r="9"]').count(), 1); assert.equal(await animationName(0), 'none');
      assert.equal(await page.locator('.session-toolbar .badge').count(), 0); assert.equal(await page.locator('.session-toolbar').getByText('fixture-model', { exact: true }).count(), 1);
      assert.equal(await page.locator('.question-form').getByText('正在询问问题', { exact: true }).count(), 1);
      await page.locator(`.recent-item[href="#/${mode}?session=${completedId}"]`).click(); await page.locator(`[data-conversation-scroll="${completedId}"]`).waitFor();
      await page.waitForFunction(([m, id]) => JSON.parse(localStorage.getItem(`research-web.navigation.v1.${m}`)).seenCompletions[id] === '1998', [mode, completedId]); await ensureSidebar();
      const completionMarker = page.locator(`[data-session-menu="${completedId}"]`).locator('..').locator('.session-row-status'); assert.equal(await completionMarker.count(), 0);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator(`[data-conversation-scroll="${completedId}"]`).waitFor(); await ensureSidebar(); assert.equal(await completionMarker.count(), 0);
      await shot(page, `session-status-seen-${theme}-${width}-${mode}`);
      const other = mode === 'claw' ? 'fingpt' : 'claw'; await page.goto(`${origin}/#/${other}`); await page.locator('.landing').waitFor(); await ensureSidebar();
      assert.equal(await page.locator(`[data-session-menu="${other}-2"]`).locator('..').locator('.session-row-status circle[r="8"]').count(), 1);
      assert.deepEqual(await page.evaluate(m => JSON.parse(localStorage.getItem(`research-web.navigation.v1.${m}`)).seenCompletions, other), {});
      assert.equal(await page.evaluate(([m, id]) => JSON.parse(localStorage.getItem(`research-web.navigation.v1.${m}`)).seenCompletions[id], [mode, completedId]), '1998');
      await page.goto(`${origin}/#/${mode}`); await page.locator('.landing').waitFor();
      details[completedId].updated_at = 2998; sessions.find(s => s.id === completedId).updated_at = 2998;
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('.landing').waitFor(); await ensureSidebar();
      await completionMarker.waitFor(); assert.equal(await completionMarker.locator('circle[r="8"]').count(), 1); assert.equal(await animationName(2), 'none');
      assert.equal(await page.evaluate(([m, id]) => JSON.parse(localStorage.getItem(`research-web.navigation.v1.${m}`)).seenCompletions[id], [mode, completedId]), '1998');
      await shot(page, `session-status-unread-again-${theme}-${width}-${mode}`);
    });
  } else if (membershipOnly) {
    for (const mode of modes) await check(`${mode}: unique pinned/project/recent priority, persistence, default return and failure retention`, async () => {
      const id = `${mode}-1`; const row = `[data-session-menu="${id}"]`; const recent = page.locator('.nav-section[aria-label="最近"]'); const pinned = page.locator('.nav-section[aria-label="置顶"]'); const member = page.locator(`.nav-project[data-nav-id="p1"] .nav-project-members ${row}`);
      metadata[mode].pinned.push({ kind: 'session', id: `${mode}-26` });
      projects[mode].push({ id: 'archived-project', name: '已归档项目', archived: true });
      for (const [index, projectId] of [[2, 'archived-project'], [3, 'missing-project'], [4, null]]) { sessions.find(s => s.id === `${mode}-${index}`).project_id = projectId; details[`${mode}-${index}`].project_id = projectId; }
      await page.setViewportSize({ width: 1440, height: 900 }); await page.goto(`${origin}/#/${mode}`);
      await page.evaluate(() => { for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); });
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator(row).waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      const moveTo = async projectId => {
        await page.locator(row).last().click(); await page.locator(`[data-nav-move-menu="${id}"]`).click();
        await Promise.all([page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes(`/sessions/${id}/project`)), page.locator(`[data-nav-move-target="${projectId}"]`).click()]);
        await page.waitForFunction(value => !document.querySelector('.session-action-menu') && document.activeElement?.dataset.sessionMenu === value, id);
      };
      const pin = async () => {
        await page.locator(row).last().click(); await Promise.all([page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().includes(`/navigation/${mode}`)), page.locator('[data-nav-pin="session"]').click()]);
        await page.waitForFunction(value => !document.querySelector('.session-action-menu') && document.activeElement?.dataset.sessionMenu === value, id);
      };
      await page.locator('[data-nav-section="projects"]').click(); await moveTo('p1');
      assert.equal(await page.locator('[data-nav-section="projects"]').getAttribute('aria-expanded'), 'true'); assert.equal(await page.locator('[data-nav-project-toggle="p1"]').getAttribute('aria-expanded'), 'true');
      assert.equal(await recent.locator(row).count(), 0); assert.equal(await member.count(), 1); assert.equal(await page.locator(row).count(), 1);
      for (const index of [2, 3, 4]) assert.equal(await recent.locator(`[data-session-menu="${mode}-${index}"]`).count(), 1, 'archived, missing and ungrouped stay recent');
      await page.reload({ waitUntil: 'domcontentloaded' }); await member.waitFor(); assert.equal(await recent.locator(row).count(), 0); assert.equal(await member.count(), 1);
      await pin(); assert.equal(await pinned.locator(row).count(), 1); assert.equal(await member.count(), 0); assert.equal(await recent.locator(row).count(), 0); assert.equal(await page.locator(row).count(), 1);
      await shot(page, `membership-${mode}-pinned-project`);
      await pin(); await page.locator('[data-nav-section="recent"]').click(); await moveTo('default');
      assert.equal(await page.locator('[data-nav-section="recent"]').getAttribute('aria-expanded'), 'true'); assert.equal(await recent.locator(row).count(), 1); assert.equal(await member.count(), 0);
      await page.locator('[data-nav-project-toggle="default"]').click(); assert.equal(await page.locator('.nav-project[data-nav-id="default"] .nav-project-members [data-session-menu]').count(), 0); assert.equal(await page.locator(row).count(), 1);
      await page.reload({ waitUntil: 'domcontentloaded' }); await recent.locator(row).waitFor();
      await page.locator('[data-nav-project-toggle="p1"]').click(); await page.locator('[data-nav-section="projects"]').click();
      failMove = true; await moveTo('p1'); await page.locator('.nav-scroll [role="alert"]').waitFor();
      assert.equal(await recent.locator(row).count(), 1); assert.equal(await member.count(), 0); assert.equal(sessions.find(s => s.id === id).project_id, 'default');
      assert.equal(await page.locator('[data-nav-section="projects"]').getAttribute('aria-expanded'), 'false'); assert.equal(await page.locator('[data-nav-project-toggle="p1"]').getAttribute('aria-expanded'), 'false');
      await shot(page, `membership-${mode}-failed-preserved`);
      await page.locator('[data-nav-section="projects"]').click();
      if (await page.locator('[data-nav-section="pinned"]').getAttribute('aria-expanded') === 'true') await page.locator('[data-nav-section="pinned"]').click();
      await page.locator('[data-nav-project-menu="p1"]').click();
      await Promise.all([page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().includes(`/navigation/${mode}`)), page.locator('.nav-project-menu [data-nav-pin="project"]').click()]);
      await page.waitForFunction(() => document.querySelector('[data-nav-section="pinned"]')?.getAttribute('aria-expanded') === 'true');
      assert.equal(await pinned.locator('.nav-project[data-nav-id="p1"]').count(), 1);
      await page.locator('[data-nav-section="recent"]').click();
      await page.locator(`[data-session-menu="${mode}-26"]`).click();
      await Promise.all([page.waitForResponse(r => r.request().method() === 'PATCH' && r.url().includes(`/navigation/${mode}`)), page.locator('[data-nav-pin="session"]').click()]);
      await recent.locator(`[data-session-menu="${mode}-26"]`).waitFor();
      assert.equal(await page.locator('[data-nav-section="recent"]').getAttribute('aria-expanded'), 'true');
      assert.ok(await page.evaluate(value => JSON.parse(localStorage.getItem(`research-web.navigation.v1.${value}`)).limit, mode) >= 30, 'unpin old session expands recent limit to include it');
      assert.equal(await page.locator(`[data-session-menu="${mode}-26"]`).count(), 1);
      await page.reload({ waitUntil: 'domcontentloaded' }); await recent.locator(`[data-session-menu="${mode}-26"]`).waitFor();
    });
  } else if (dialogsOnly) {
    for (const theme of ['light', 'dark']) for (const width of [390, 1440]) for (const mode of modes) await check(`${theme}/${width}/${mode}: centered project modal, cancel/Escape, focus trap, failed draft and retry`, async () => {
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/${mode}`);
      await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('[data-nav-project-create]').waitFor({ state: 'attached' });
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
      const open = page.locator('[data-nav-project-create]'); const dialog = page.getByRole('dialog', { name: '创建项目', exact: true }); const start = report.writes.length;
      await open.click(); await dialog.waitFor(); assert.equal(await page.locator('#nav-project-name').evaluate(el => document.activeElement === el), true);
      assert.equal(await dialog.getAttribute('aria-modal'), 'true'); const bounds = await dialog.boundingBox();
      assert.ok(Math.abs(bounds.x + bounds.width / 2 - width / 2) <= 1 && Math.abs(bounds.y + bounds.height / 2 - 450) <= 1, JSON.stringify(bounds));
      assert.ok(bounds.x >= 0 && bounds.x + bounds.width <= width && bounds.y >= 0 && bounds.y + bounds.height <= 900, JSON.stringify(bounds));
      const controls = dialog.locator('input,button'); await controls.last().focus(); await page.keyboard.press('Tab'); assert.equal(await controls.first().evaluate(el => document.activeElement === el), true);
      await page.keyboard.press('Shift+Tab'); assert.equal(await controls.last().evaluate(el => document.activeElement === el), true);
      await page.locator('#nav-project-name').fill('取消草稿'); await dialog.getByRole('button', { name: '取消', exact: true }).click(); assert.equal(await dialog.count(), 0); assert.equal(await open.evaluate(el => document.activeElement === el), true);
      await open.click(); await page.locator('#nav-project-name').fill('Esc草稿'); await page.keyboard.press('Escape'); assert.equal(await dialog.count(), 0); assert.equal(await open.evaluate(el => document.activeElement === el), true);
      await open.click(); await dialog.getByRole('button', { name: '关闭创建项目', exact: true }).click(); assert.equal(await dialog.count(), 0); assert.equal(await open.evaluate(el => document.activeElement === el), true); assert.equal(report.writes.length, start);
      await open.click(); const name = `${mode} ${theme} ${'长标题项目'.repeat(20)}`.slice(0, 120); await page.locator('#nav-project-name').fill(name);
      assert.equal(await dialog.evaluate(el => el.scrollWidth <= el.clientWidth), true); assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await shot(page, `project-dialog-${theme}-${width}-${mode}`);
      failProjectCreate = true; await dialog.getByRole('button', { name: '创建项目', exact: true }).click(); await dialog.getByRole('alert').waitFor();
      assert.equal(await page.locator('#nav-project-name').inputValue(), name); assert.equal(await dialog.getByRole('button', { name: '创建项目', exact: true }).isEnabled(), true);
      await shot(page, `project-dialog-${theme}-${width}-${mode}-failed`);
      holdProjectCreate = true; const started = new Promise(resolve => { projectCreateStarted = resolve; });
      await dialog.getByRole('button', { name: '创建项目', exact: true }).click(); await started;
      await check(`${theme}/${width}/${mode}: saving modal keeps inert background and trapped focus`, async () => {
        await page.waitForFunction(() => document.querySelector('.nav-project-dialog')?.getAttribute('aria-busy') === 'true');
        assert.equal(await page.evaluate(() => { const d = document.querySelector('.nav-project-dialog'); return [...document.querySelector('#app').children].filter(el => !el.contains(d)).every(el => el.inert); }), true);
        assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true);
        await page.keyboard.press('Tab'); assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true, 'Tab cannot leave saving dialog');
        await page.keyboard.press('Shift+Tab'); assert.equal(await dialog.evaluate(el => el.contains(document.activeElement)), true, 'Shift+Tab cannot leave saving dialog');
      });
      releaseProjectCreate(); projectCreateStarted = null; await dialog.waitFor({ state: 'detached' });
      assert.deepEqual(report.writes.slice(start).map(w => ({ method: w.method, endpoint: w.endpoint, query: w.query, body: w.body })), [0, 1].map(() => ({ method: 'POST', endpoint: '/projects', query: `?mode=${mode}`, body: { name } })));
    });
  } else if (menusOnly) {
    for (const mode of modes) projects[mode].push(...Array.from({ length: 15 }, (_, i) => ({ id: `project-${String(i).padStart(32, '0')}`, name: `${mode} 长项目 ${i} ${'不能把菜单撑出浏览器'.repeat(12)}`, archived: false })));
    report.menuGeometry = [];
    for (const theme of ['light', 'dark']) for (const width of [390, 820, 1440]) for (const mode of modes) await check(`${theme}/${width}/${mode}: compact project submenu, keyboard move and scoped state`, async () => {
      const id = `${mode}-0`; details[id].project_id = 'default'; sessions.find(s => s.id === id).project_id = 'default';
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/${mode}`);
      await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['claw', 'fingpt']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
      await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator(`[data-session-menu="${id}"]`).waitFor({ state: 'attached' });
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
      const sourceRect = await page.locator(`[data-session-menu="${id}"]`).locator('..').boundingBox();
      await page.locator(`[data-session-menu="${id}"]`).click(); await page.locator('.session-action-menu').waitFor();
      const parentRect = await page.locator('.session-action-menu').boundingBox();
      assert.ok(parentRect.x >= sourceRect.x + sourceRect.width || parentRect.x + parentRect.width <= sourceRect.x || parentRect.y >= sourceRect.y + sourceRect.height || parentRect.y + parentRect.height <= sourceRect.y, JSON.stringify({ sourceRect, parentRect }));
      if (width >= 820) assert.ok(parentRect.x >= sourceRect.x + sourceRect.width, 'roomy viewport puts menu right of source row');
      assert.equal(await page.locator(`[data-menu-delete="${id}"]`).isDisabled(), true, 'running session remains protected');
      const move = page.locator(`[data-nav-move-menu="${id}"]`); await move.hover();
      const submenu = page.getByRole('menu', { name: '选择项目', exact: true }); await submenu.waitFor();
      await submenu.locator('[data-nav-move-target="default"]').hover(); await page.waitForTimeout(260); assert.equal(await submenu.isVisible(), true, 'crossing parent-child gap retains menu');
      await page.mouse.move(width - 2, 2); await submenu.waitFor({ state: 'detached' }); assert.equal(await page.locator('.session-action-menu').isVisible(), true);
      await move.focus(); await move.press('ArrowRight'); await submenu.waitFor();
      assert.equal(await submenu.locator('.session-project-menu-header').count(), 0);
      assert.equal(await submenu.locator('select, option').count(), 0);
      assert.equal(await submenu.locator('[role="menuitemradio"][aria-checked="true"]').count(), 1);
      assert.equal(await submenu.locator('[data-nav-move-target="default"]').getAttribute('aria-checked'), 'true');
      assert.equal(await submenu.locator('[data-nav-move-target="default"] svg').count(), 2);
      const boxes = await page.evaluate(() => [...document.querySelectorAll('.session-action-menu, .session-project-menu')].map(el => { const r = el.getBoundingClientRect(); return { width: r.width, height: r.height, left: r.left, right: r.right, top: r.top, bottom: r.bottom, viewport: innerWidth }; }));
      for (const box of boxes) { assert.ok(box.left >= 0 && box.right <= width && box.top >= 0 && box.bottom <= 900, JSON.stringify(box)); assert.ok(box.width <= 232, JSON.stringify(box)); }
      assert.equal(Math.round(boxes[0].width), 208); assert.equal(Math.round(boxes[1].width), 232);
      const long = submenu.locator('[data-nav-move-target="p1"]');
      assert.equal(await long.getAttribute('title'), projects[mode].find(p => p.id === 'p1').name);
      const clipped = await long.locator('.conversation-menu-label').evaluate(el => ({ ellipsis: getComputedStyle(el).textOverflow, whiteSpace: getComputedStyle(el).whiteSpace, truncated: el.scrollWidth > el.clientWidth }));
      assert.deepEqual(clipped, { ellipsis: 'ellipsis', whiteSpace: 'nowrap', truncated: true });
      await submenu.locator('.session-project-menu-list').evaluate(el => { el.scrollTop = 90; });
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(resolve)));
      assert.equal(await submenu.isVisible(), true, 'menu scrolling must retain nested menu');
      await page.keyboard.press('End'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navMoveTarget), 'project-00000000000000000000000000000014');
      const keyboardBounds = await page.evaluate(() => { const selected = document.activeElement.getBoundingClientRect(); const list = document.querySelector('.session-project-menu-list').getBoundingClientRect(); return { selectedTop: selected.top, selectedBottom: selected.bottom, listTop: list.top, listBottom: list.bottom }; });
      await check(`${theme}/${width}/${mode}: End keeps focused project visible`, async () => { assert.ok(keyboardBounds.selectedTop >= keyboardBounds.listTop - .5 && keyboardBounds.selectedBottom <= keyboardBounds.listBottom + .5, JSON.stringify(keyboardBounds)); });
      await page.keyboard.press('ArrowUp'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navMoveTarget), 'project-00000000000000000000000000000013');
      await page.keyboard.press('Home'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navMoveTarget), 'default');
      await page.keyboard.press('ArrowDown'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navMoveTarget), 'p1');
      await page.keyboard.press('ArrowLeft'); assert.equal(await submenu.count(), 0); assert.equal(await page.locator('.session-action-menu').isVisible(), true);
      assert.equal(await move.evaluate(el => document.activeElement === el), true);
      await move.press('ArrowRight'); await page.keyboard.press('Escape'); assert.equal(await submenu.count(), 0); assert.equal(await page.locator('.session-action-menu').isVisible(), true);
      if (width <= 1050) assert.equal(await page.locator('.app-shell.navigation-open').count(), 1);
      await move.press('ArrowRight'); await submenu.locator('.session-project-menu-list').evaluate(el => { el.scrollTop = 0; });
      await shot(page, `menus-${theme}-${width}-${mode}`); report.menuGeometry.push({ theme, width, mode, boxes, clipped });
      await page.keyboard.press('Home'); await page.keyboard.press('ArrowDown');
      assert.equal(await page.evaluate(() => document.activeElement.dataset.navMoveTarget), 'p1');
      const other = mode === 'fingpt' ? 'claw' : 'fingpt'; const untouched = sessions.find(s => s.id === `${other}-0`).project_id; const start = report.writes.length;
      await Promise.all([page.waitForResponse(r => r.request().method() === 'PUT' && r.url().includes(`/sessions/${id}/project`)), page.keyboard.press('Enter')]);
      await page.waitForFunction(value => !document.querySelector('.session-action-menu') && document.activeElement?.dataset.sessionMenu === value, id);
      assert.deepEqual(report.writes.slice(start).map(w => ({ method: w.method, endpoint: w.endpoint, body: w.body })), [{ method: 'PUT', endpoint: `/sessions/${id}/project`, body: { project_id: 'p1' } }]);
      assert.equal(sessions.find(s => s.id === `${other}-0`).project_id, untouched);
      await page.locator(`[data-session-menu="${id}"]`).click(); await page.keyboard.press('Escape'); assert.equal(await page.locator('.session-action-menu').count(), 0);
      assert.equal(await page.locator(`[data-session-menu="${id}"]`).evaluate(el => document.activeElement === el), true);
      if (width <= 1050) assert.equal(await page.locator('.app-shell.navigation-open').count(), 1);
      await page.locator('[data-nav-project-menu="p1"]').click(); const projectMenu = page.getByRole('menu', { name: '项目操作', exact: true }); await projectMenu.waitFor();
      const rect = await projectMenu.boundingBox(); assert.equal(Math.round(rect.width), 208); assert.ok(rect.x >= 0 && rect.x + rect.width <= width && rect.y + rect.height <= 900);
      await page.keyboard.press('End'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navProjectArchive), 'p1');
      await page.keyboard.press('Home'); assert.equal(await page.evaluate(() => document.activeElement.dataset.navPin), 'project');
      await shot(page, `project-menu-${theme}-${width}-${mode}`);
      await page.keyboard.press('Escape'); assert.equal(await projectMenu.count(), 0); assert.equal(await page.locator('[data-nav-project-menu="p1"]').evaluate(el => document.activeElement === el), true);
      const assertAnchored = async (menuSelector, triggerSelector) => {
        const geometry = await page.evaluate(([menu, trigger]) => { const m = document.querySelector(menu).getBoundingClientRect(); const r = document.querySelector(trigger).closest('.session-row,.nav-project-row').getBoundingClientRect(); return { left: m.left, right: m.right, top: m.top, bottom: m.bottom, rowLeft: r.left, rowRight: r.right, rowTop: r.top, rowBottom: r.bottom }; }, [menuSelector, triggerSelector]);
        assert.ok(geometry.top >= 8 && geometry.left >= 8, JSON.stringify(geometry));
        assert.ok(geometry.left >= geometry.rowRight || geometry.right <= geometry.rowLeft || geometry.top >= geometry.rowBottom || geometry.bottom <= geometry.rowTop, JSON.stringify(geometry));
        if (width >= 820) assert.ok(geometry.left >= geometry.rowRight, JSON.stringify(geometry));
      };
      await page.locator(`[data-session-menu="${id}"]`).click(); await page.locator('.session-action-menu').waitFor();
      await page.locator('[data-nav-project-menu="p1"]').click(); await projectMenu.waitFor(); assert.equal(await page.locator('.session-action-menu').count(), 0);
      await assertAnchored('.nav-project-menu', '[data-nav-project-menu="p1"]');
      await page.locator(`[data-session-menu="${id}"]`).click(); await page.locator('.session-action-menu').waitFor(); assert.equal(await projectMenu.count(), 0);
      await assertAnchored('.session-action-menu', `[data-session-menu="${id}"]`); await page.keyboard.press('Escape');
    });
  } else if (submitOnly) {
    report.contrast = [];
    for (const theme of ['light', 'dark']) for (const mode of modes) for (const width of [1440, 390]) await check(`${theme}/${mode}/${width}: last question submit contrast, visibility and send guard`, async () => {
      await page.setViewportSize({ width, height: 900 }); await page.goto(`${origin}/#/${mode}?session=${mode}-0`);
      await page.evaluate(value => localStorage.setItem('research-web.appearance.v1', value), theme); await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('[name="selection-0"]').first().waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
      await page.locator('.codex-question-arrow[data-q-page="next"]').click();
      const submit = page.locator('.question-form').getByRole('button', { name: '提交回答', exact: true });
      await submit.waitFor(); assert.equal(await submit.isEnabled(), true); await submit.click({ trial: true });
      const metrics = await submit.evaluate(element => {
        const style = getComputedStyle(element); const rect = element.getBoundingClientRect(); const composer = document.querySelector('#composer').getBoundingClientRect();
        const rgb = value => value.match(/[\d.]+/g).map(Number); const fg = rgb(style.color); const bg = rgb(style.backgroundColor);
        const luminance = channels => channels.slice(0, 3).map(value => value / 255).map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4).reduce((sum, value, i) => sum + value * [.2126, .7152, .0722][i], 0);
        const values = [luminance(fg), luminance(bg)].sort((a, b) => b - a);
        return { foreground: style.color, background: style.backgroundColor, contrast: (values[0] + .05) / (values[1] + .05), opaque: (fg[3] ?? 1) === 1 && (bg[3] ?? 1) === 1, buttonBottom: rect.bottom, composerTop: composer.top, visible: rect.width > 0 && rect.height > 0 && rect.top >= 0 && rect.bottom <= innerHeight };
      });
      assert.equal(metrics.opaque, true); assert.ok(metrics.contrast >= 4.5, JSON.stringify(metrics)); assert.equal(metrics.visible, true); assert.ok(metrics.buttonBottom <= metrics.composerTop + .5, JSON.stringify(metrics));
      report.contrast.push({ theme, mode, width, ...metrics });
      const screenshot = path.join(output, `submit-${theme}-${mode}-${width}-footer.png`); await page.locator('.codex-question-footer').screenshot({ path: screenshot }); report.screenshots.push(screenshot);
      assert.equal(await page.getByText('上一任务及其交付尚未确认结束。可准备草稿，完成后再发送。', { exact: true }).count(), 0);
      assert.equal(await page.locator('.composer-caption').count(), 0);
      const send = page.locator('#composer [type="submit"]'); if (await send.count()) assert.equal(await send.isDisabled(), true);
      const writesBefore = report.writes.length; await page.locator('#prompt').fill('待答时仍保留普通草稿'); await page.locator('#prompt').press('Enter');
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      assert.equal(report.writes.length, writesBefore, 'pending question must continue blocking ordinary sends');
      assert.equal(await page.locator('#prompt').inputValue(), '待答时仍保留普通草稿');
    });
  } else if (forwardOnly) {
    for (const mode of modes) for (const width of [1440, 390]) await check(`${mode}/${width}: full row continues and keyboard reselection preserves drafts`, async () => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${origin}/#/${mode}?session=${mode}-0`); await page.reload();
      await page.locator('[name="selection-0"]').first().waitFor();
      const rows = page.locator('.codex-question-option');
      await rows.nth(0).locator('input').focus(); await page.keyboard.press('ArrowDown');
      assert.equal(await rows.nth(1).locator('input').isChecked(), true);
      assert.equal(await page.locator('.question-form').getAttribute('data-q-index'), '0');
      await shot(page, `forward-${mode}-${width}-reselected`);
      await rows.nth(1).locator('.question-option-copy').click(); await page.locator('[data-q-index="1"]').waitFor();
      assert.equal(await page.evaluate(() => document.activeElement.matches('legend.codex-question-title')), true);
      await page.locator('[data-q-page="prev"]').click();
      assert.equal(await page.locator('[name="selection-0"]').nth(1).isChecked(), true);
    });
    assert.deepEqual(report.writes, [], 'forward navigation must never submit answers');
  } else {
  for (const theme of ['light', 'dark']) {
    for (const width of [1440, 1920, 1051, 820, 390]) {
      await page.setViewportSize({ width, height: 900 });
      for (const mode of modes) await check(`${theme}/${width}/${mode}: geometry, draft, section persistence/keyboard/isolation, collapse, overflow`, async () => {
        await page.goto(`${origin}/#/${mode}`, { waitUntil: 'domcontentloaded' });
        await page.evaluate(value => { localStorage.setItem('research-web.appearance.v1', value); for (const m of ['fingpt', 'claw']) localStorage.setItem(`research-web.navigation.v1.${m}`, JSON.stringify({ collapsed: false, collapsedSections: [], expanded: [], limit: 10 })); }, theme);
        await page.reload({ waitUntil: 'domcontentloaded' });
        try { await page.locator('#prompt').waitFor(); } catch (error) { await shot(page, `failure-${theme}-${width}-${mode}`); await writeFile(path.join(output, 'failure-dom.html'), await page.content()); throw error; }
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        await page.locator('.nav-scroll .session-row').first().waitFor({ state: 'attached' });
        if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
        else if (!await page.locator('.codex-sidebar').isVisible()) await page.locator('.primary-rail .rail-toggle').click();
        const sidebar = page.locator('.codex-sidebar');
        assert.equal(Math.round((await sidebar.boundingBox()).width), 280);
        assert.equal(await page.locator('.new-research').evaluate(el => el.nextElementSibling.matches('.nav-shortcuts')), true);
        const shortcuts = page.locator('.nav-shortcuts a');
        assert.deepEqual(await shortcuts.allTextContents().then(items => items.map(item => item.trim())), mode === 'claw' ? ['Agent 日程', '管理项目'] : ['管理项目']);
        assert.equal(await page.locator('.nav-mode-menu a[href="#/skills"]').count(), 0);
        for (const href of mode === 'claw' ? ['#/claw?view=plans', '#/claw?view=projects&project=default'] : ['#/fingpt?view=projects&project=default']) {
          const shortcut = page.locator(`.nav-shortcuts a[href="${href}"]`); if (width <= 1050) assert.ok((await shortcut.boundingBox()).height >= 44);
          await shortcut.click(); await page.waitForFunction(value => [...document.querySelectorAll('.nav-shortcuts a')].find(el => el.getAttribute('href') === value)?.getAttribute('aria-current') === 'page', href);
          if (width <= 1050 && !await sidebar.isVisible()) await page.locator('.topbar .menu-toggle').click();
        }
        await page.goto(`${origin}/#/${mode}`); await page.locator('#prompt').waitFor();
        if (width <= 1050 && !await sidebar.isVisible()) await page.locator('.topbar .menu-toggle').click();
        await sidebar.waitFor({ state: 'visible' }); await page.locator('[data-nav-section] svg').first().waitFor();
        await assertSquareIcons(page, '[data-nav-section] svg, .nav-project-toggle svg');
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        if (width === 1440 || width === 390) await shot(page, `${theme}-${width}-${mode}`);
        for (const section of ['pinned', 'projects', 'recent']) {
          await page.locator(`[data-nav-section="${section}"]`).click();
          assert.equal(await page.locator(`[data-nav-section="${section}"]`).getAttribute('aria-expanded'), 'false');
          assert.equal(await page.locator(`#nav-section-${mode}-${section}`).isVisible(), false);
        }
        await page.reload({ waitUntil: 'domcontentloaded' }); await page.locator('[data-nav-section="pinned"]').waitFor({ state: 'attached' });
        if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
        for (const section of ['pinned', 'projects', 'recent']) {
          const toggle = page.locator(`[data-nav-section="${section}"]`);
          assert.equal(await toggle.getAttribute('aria-expanded'), 'false');
          assert.equal(await toggle.getAttribute('aria-controls'), `nav-section-${mode}-${section}`);
          await toggle.focus(); await toggle.press('Enter');
          assert.equal(await toggle.getAttribute('aria-expanded'), 'true');
          assert.equal(await page.locator(`#nav-section-${mode}-${section}`).isVisible(), true);
        }
        await page.locator('[data-nav-section="pinned"]').click();
        const otherMode = mode === 'claw' ? 'fingpt' : 'claw';
        await page.goto(`${origin}/#/${otherMode}`); await page.locator(`[data-nav-mode="${otherMode}"]`).waitFor({ state: 'attached' });
        assert.equal(await page.locator('[data-nav-section="pinned"]').getAttribute('aria-expanded'), 'true');
        await page.goto(`${origin}/#/${mode}`); await page.locator(`[data-nav-mode="${mode}"]`).waitFor({ state: 'attached' });
        if (width <= 1050) await page.locator('.topbar .menu-toggle').click();
        assert.equal(await page.locator('[data-nav-section="pinned"]').getAttribute('aria-expanded'), 'false');
        await page.locator('[data-nav-section="pinned"]').click();
        await page.locator('#prompt').fill(`保留草稿 ${mode}`);
        await page.locator('[data-nav-more]').click();
        const headerY = (await page.locator('.sidebar-top').boundingBox()).y;
        await page.locator('.nav-scroll').evaluate(el => { el.scrollTop = 130; });
        assert.equal((await page.locator('.sidebar-top').boundingBox()).y, headerY);
        const before = await page.locator('#main').boundingBox();
        await page.locator(width > 1050 ? '[data-collapse-sidebar]' : '.rail-mobile-close').click();
        const after = await page.locator('#main').boundingBox();
        if (width > 1050) {
          assert.equal(before.y, 0); assert.equal(after.y, 0); assert.equal(Math.round(after.width - before.width), 280);
          assert.ok((await page.locator('.primary-rail .rail-toggle').boundingBox()).y < 160);
          await page.locator('.primary-rail .rail-toggle').click();
        } else await page.locator('.topbar .menu-toggle').click();
        assert.equal(await page.locator('#prompt').inputValue(), `保留草稿 ${mode}`);
        assert.equal(await page.locator('.nav-scroll').evaluate(el => el.scrollTop), 130);
        if (width <= 1050) await page.keyboard.press('Escape');
      });
    }
  }
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`${origin}/#/fingpt`);
  await page.locator('.nav-scroll .session-row').first().waitFor();
  if (await page.locator('.app-shell.sidebar-collapsed').count()) await page.locator('.rail-toggle').click();
  await page.evaluate(() => { window.fixtureScrolls = []; window.addEventListener('scroll', event => window.fixtureScrolls.push({ node: event.target.className || event.target.nodeName, top: event.target.scrollTop }), true); });
  const sessionMenu = async id => {
    if (await page.locator(`.session-action-menu [data-nav-id="${id}"]`).count()) return;
    await page.evaluate(value => [...document.querySelectorAll('[data-session-menu]')].filter(el => el.dataset.sessionMenu === value).at(-1)?.scrollIntoView({ block: 'nearest' }), id);
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.locator(`[data-session-menu="${id}"]`).last().click();
    try { await page.locator('.session-action-menu').waitFor(); }
    catch (error) { await writeFile(path.join(output, 'menu-debug.json'), JSON.stringify(await page.evaluate(() => ({ scrolls: window.fixtureScrolls, active: document.activeElement.outerHTML, list: document.querySelector('.nav-scroll').scrollTop })), null, 2)); await shot(page, 'menu-failure'); throw error; }
  };
  const navAction = async action => { const [response] = await Promise.all([page.waitForResponse(r => r.url().includes('/navigation/') && r.request().method() === 'PATCH'), action()]); await response.finished(); await page.waitForFunction(() => !document.querySelector('[data-nav-project-create]:disabled')); };
  await check('session pin/unpin, project pin, keyboard order and HTML drag/drop', async () => {
    await sessionMenu('fingpt-1'); await navAction(() => page.locator('[data-nav-pin="session"]').click());
    assert.deepEqual(metadata.fingpt.pinned, [{ kind: 'session', id: 'fingpt-1' }]);
    await page.waitForFunction(() => document.activeElement?.dataset.sessionMenu === 'fingpt-1');
    assert.equal(await page.locator('.session-action-menu').count(), 0);
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('.session-action-menu').count(), 0);
    assert.equal(await page.locator('.codex-sidebar').isVisible(), true);
    assert.equal(await page.locator('#prompt').inputValue(), '保留草稿 fingpt');
    await sessionMenu('fingpt-1'); await navAction(() => page.locator('[data-nav-pin="session"]').click());
    assert.deepEqual(metadata.fingpt.pinned, []);
    await page.waitForFunction(() => document.activeElement?.dataset.sessionMenu === 'fingpt-1');
    assert.equal(await page.locator('.session-action-menu').count(), 0);
    await page.locator('[data-nav-project-menu="p1"]').click(); await navAction(() => page.locator('.nav-project-menu [data-nav-pin]').click());
    await page.waitForFunction(() => document.activeElement?.dataset.navProjectMenu === 'p1');
    assert.equal(await page.locator('.nav-project-menu').count(), 0);
    await page.locator('[data-nav-project-menu="p2"]').click(); await navAction(() => page.locator('.nav-project-menu [data-nav-pin]').click());
    await page.waitForFunction(() => document.activeElement?.dataset.navProjectMenu === 'p2');
    await page.locator('[data-nav-project-menu="p2"]').click();
    await navAction(() => page.locator('.nav-project-menu [data-nav-order="-1"]').click());
    assert.equal(metadata.fingpt.pinned[0].id, 'p2');
    await page.waitForFunction(() => document.activeElement?.dataset.navProjectMenu === 'p2');
    await page.locator('[data-nav-project-menu="p2"]').click();
    await navAction(() => page.locator('.nav-project-menu [data-nav-order="1"]').click());
    assert.equal(metadata.fingpt.pinned[0].id, 'p1');
    await navAction(() => page.locator('[data-nav-sortable="pinned"][data-nav-id="p2"]').dragTo(page.locator('[data-nav-sortable="pinned"][data-nav-id="p1"]')));
    await page.waitForFunction(() => document.querySelector('[data-nav-sortable="pinned"]')?.dataset.navId === 'p2');
    assert.equal(metadata.fingpt.pinned[0].id, 'p2');
    assert.deepEqual(metadata.claw.pinned, []);
  });
  await check('project create and session move', async () => {
    await page.locator('[data-nav-project-create]').click(); await page.locator('#nav-project-name').fill('浏览器新项目'); await page.locator('[data-nav-project-form] [type=submit]').click();
    await page.locator('[data-nav-project-toggle="fingpt-created"]').waitFor();
    await sessionMenu('fingpt-2'); await page.locator('[data-nav-move-menu="fingpt-2"]').click(); await page.locator('[data-nav-move-target="fingpt-created"]').click();
    await page.waitForResponse(r => r.url().includes('/navigation/fingpt') && r.request().method() === 'GET');
    assert.equal(sessions.find(s => s.id === 'fingpt-2').project_id, 'fingpt-created');
  });
  await check('500/409 preserve authoritative navigation, show more and search Escape focus', async () => {
    for (const status of [500, 409]) {
      const confirmed = structuredClone(metadata.fingpt.pinned); failNavigation = status;
      await sessionMenu('fingpt-3'); await navAction(() => page.locator('[data-nav-pin="session"]').click());
      await page.locator('.nav-scroll [role=alert]').waitFor(); assert.deepEqual(metadata.fingpt.pinned, confirmed);
      assert.equal(await page.locator('[data-nav-sortable="pinned"][data-nav-id="fingpt-3"]').count(), 0);
    }
    const count = await page.locator('.nav-section[aria-label="最近"] .session-row').count();
    await page.locator('[data-nav-more]').click(); assert.ok(await page.locator('.nav-section[aria-label="最近"] .session-row').count() > count);
    await page.locator('.sidebar-top [data-toggle-search]').click(); await page.locator('#global-search').fill('会话'); await page.keyboard.press('Escape');
    assert.equal(await page.locator('.search-popover').isVisible(), false);
    assert.equal(await page.evaluate(() => document.activeElement.matches('.primary-rail .search-trigger, .sidebar-top [data-toggle-search]')), true);
  });
  for (const mode of modes) await check(`${mode}: question paging, IME, fold, skip, failure retry, native history`, async () => {
    await page.goto(`${origin}/#/${mode}?session=${mode}-0`); await page.locator('[data-question-form]').waitFor();
    assert.equal(await page.locator('#main h1, #main .session-title, #main .page-header .eyebrow').count(), 0, 'session omits large title and mode eyebrow');
    assert.equal(await page.locator('#main .session-toolbar').count(), 1);
    for (const width of [1440, 820, 390]) await check(`${mode}: question card unobstructed at ${width}`, async () => {
      await page.setViewportSize({ width, height: 900 }); await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      await page.locator('.question-form').waitFor(); await page.evaluate(() => document.querySelector('.question-form').scrollIntoView({ block: 'nearest' }));
      const bounds = await page.evaluate(() => { const card = document.querySelector('.codex-question').getBoundingClientRect(); const composer = document.querySelector('#composer').getBoundingClientRect(); return { cardBottom: card.bottom, composerTop: composer.top, overflow: document.documentElement.scrollWidth > innerWidth }; });
      await shot(page, `${mode}-question-${width}`);
      await assertSquareIcons(page, '.question-form svg', { centeredButtons: true });
      assert.equal(bounds.overflow, false); assert.ok(bounds.cardBottom <= bounds.composerTop + 1, JSON.stringify({ width, ...bounds }));
      await page.locator('[data-q-skip]').click({ trial: true });
      const ordinaryDraft = await page.locator('#prompt').inputValue();
      await page.locator('[data-q-close]').click(); assert.equal(await page.locator('#prompt').inputValue(), ordinaryDraft);
      await page.locator('[data-q-open]').click(); assert.equal(await page.locator('#prompt').inputValue(), ordinaryDraft);
    });
    await page.setViewportSize({ width: 1440, height: 900 });
    const custom = page.locator('[name="custom-0"]');
    await custom.fill(`中文补充 ${mode}`);
    if (mode === 'fingpt') {
      await page.goto(`${origin}/#/claw?session=claw-0`); await page.locator('[name="custom-0"]').waitFor(); assert.equal(await page.locator('[name="custom-0"]').inputValue(), '');
      await page.goto(`${origin}/#/fingpt?session=fingpt-0`); await custom.waitFor(); assert.equal(await custom.inputValue(), '中文补充 fingpt');
    }
    await custom.dispatchEvent('compositionstart');
    broadcast(`${mode}-0`);
    await page.locator('.sidebar-top [data-toggle-search]').click(); await page.keyboard.press('Escape');
    assert.equal(await page.locator('[name="custom-0"]').inputValue(), `中文补充 ${mode}`);
    await page.locator('[name="custom-0"]').dispatchEvent('compositionend');
    await page.locator('.codex-question-option').first().click();
    await page.locator('[name="selection-1"]').first().waitFor();
    await assertSquareIcons(page, '.question-form svg', { centeredButtons: true });
    await page.waitForTimeout(320);
    assert.equal(await page.evaluate(() => document.activeElement.matches('legend.codex-question-title[tabindex="-1"]')), true);
    await page.locator('[name="selection-1"]').nth(0).check(); await page.locator('[name="selection-1"]').nth(1).check();
    await page.locator('[data-q-page="prev"]').click(); assert.equal(await page.locator('[name="custom-0"]').inputValue(), `中文补充 ${mode}`);
    assert.equal(await page.evaluate(() => document.activeElement.matches('legend.codex-question-title[tabindex="-1"]')), true);
    await page.locator('[data-q-close]').click(); await page.locator('[data-q-open]').click(); assert.equal(await page.locator('[name="custom-0"]').inputValue(), `中文补充 ${mode}`);
    await shot(page, `${mode}-question-card`);
    await page.locator('[data-q-skip]').click(); assert.equal(await page.locator('[name="selection-1"]:checked').count(), 2);
    failAnswer = true;
    await page.locator('.question-form [type=submit]').click(); await page.getByText('夹具原生回答失败，可重试', { exact: true }).waitFor();
    assert.equal(await page.locator('[name="selection-1"]:checked').count(), 2); assert.equal(await page.locator('.question-history').count(), 0);
    const attempts = report.writes.filter(w => w.endpoint === `/sessions/${mode}-0/questions/q-native`);
    assert.equal(attempts.length, 1); assert.deepEqual(attempts[0].body.answers[0], { id: 'one', selected: [], custom: '用户跳过，未提供答案' });
    await page.locator('.question-form [type=submit]').click(); await page.locator('.question-history summary').waitFor();
    assert.equal(await page.locator('.question-history summary').innerText().then(s => s.includes('已询问 2 个问题')), true);
    await page.locator('.question-history summary').click(); assert.equal(await page.locator('.question-history').getAttribute('open'), '');
    await assertSquareIcons(page, '.question-history svg', { centeredButtons: true });
    await shot(page, `${mode}-confirmed-history`);
    assert.equal(report.writes.filter(w => w.endpoint === `/sessions/${mode}-0/questions/q-native`).length, 2);
    if (!await page.locator('.context-panel').isVisible()) { await page.locator('.nav-mode-menu summary').click(); await page.getByRole('button', { name: '会话资料与文件', exact: true }).click(); }
    await page.getByRole('tab', { name: '文件', exact: true }).click(); await page.getByText('当前会话资料.md', { exact: true }).first().waitFor();
  });
  await check('native failed and expired sessions never create confirmed question history', async () => {
    for (const [mode, status] of [['fingpt', 'failed'], ['claw', 'expired']]) {
      const id = `${mode}-4`; details[id].status = status; details[id].questions = []; details[id].question_history = [];
      await page.goto(`${origin}/#/${mode}?session=${id}`); await page.locator('#prompt').waitFor();
      await page.waitForFunction(value => document.querySelector('.session-row.active [data-session-menu]')?.dataset.sessionMenu === value, id);
      assert.equal(await page.locator('.question-history').count(), 0); assert.equal(await page.getByText('已询问 2 个问题', { exact: true }).count(), 0);
    }
  });
  await check('820px settings/history/workbench mobile navigation has no runtime error', async () => {
    await page.setViewportSize({ width: 820, height: 900 });
    for (const route of ['settings/general', 'history', 'workbench']) {
      await page.goto(`${origin}/#/${route}`); await page.locator('.topbar .menu-toggle').waitFor();
      await page.locator('.topbar .menu-toggle').click(); assert.equal(await page.locator('.primary-rail').isVisible(), true);
      await page.locator('.rail-mobile-close').click(); assert.equal(await page.locator('.primary-rail').isVisible(), false);
    }
  });
  await check('FinGPT project archive/restore uses generic mode-scoped API', async () => {
    const projectId = `project-${'a'.repeat(32)}`; projects.fingpt.push({ id: projectId, name: '归档恢复验收项目', archived: false });
    await page.setViewportSize({ width: 1440, height: 900 }); await page.goto(`${origin}/#/fingpt?view=projects&project=${projectId}`);
    const archive = page.locator(`[data-claw-project-archive="${projectId}"]`); try { await archive.waitFor(); } catch (error) { await writeFile(path.join(output, 'project-failure-dom.html'), await page.content()); throw error; }
    const start = report.writes.length;
    await archive.click(); await page.locator(`[data-claw-project-archive="${projectId}"][data-archived="false"]`).waitFor();
    await archive.click(); await page.locator(`[data-claw-project-archive="${projectId}"][data-archived="true"]`).waitFor();
    assert.deepEqual(report.writes.slice(start).map(w => ({ method: w.method, endpoint: w.endpoint, query: w.query, archived: w.body.archived })), [
      { method: 'PATCH', endpoint: `/projects/${projectId}`, query: '?mode=fingpt', archived: true }, { method: 'PATCH', endpoint: `/projects/${projectId}`, query: '?mode=fingpt', archived: false },
    ]);
  });
  }
  report.status = report.failures.length ? 'failed' : 'passed';
  }
} catch (error) { report.status = 'failed'; report.failures.push({ name: 'acceptance', error: error.stack }); }
finally {
  await browser?.close(); server.closeAllConnections(); await new Promise(resolve => server.close(resolve));
  await mkdir(output, { recursive: true }); await writeFile(path.join(output, receiptName), JSON.stringify(report, null, 2) + '\n');
  await appendFile(path.join(output, 'acceptance.jsonl'), JSON.stringify(report) + '\n');
  console.log(JSON.stringify({ status: report.status, checks: report.checks, failures: report.failures, receipt: path.join(output, receiptName) }, null, 2));
  if (!['passed', 'preview'].includes(report.status)) process.exitCode = 1;
}
