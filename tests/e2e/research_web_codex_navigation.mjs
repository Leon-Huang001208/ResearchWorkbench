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
const receiptName = preview ? 'preview-receipt.json' : dialogsOnly ? 'project-dialog-receipt.json' : menusOnly ? 'menus-receipt.json' : submitOnly ? 'submit-receipt.json' : forwardOnly ? 'forward-receipt.json' : 'receipt.json';
const report = { status: 'running', environment: 'isolated Chrome synthetic API; no resident HTTP or model calls', checks: [], failures: [], writes: [], screenshots: [] };
const modes = ['fingpt', 'claw'];
const metadata = Object.fromEntries(modes.map(mode => [mode, { mode, revision: 0, pinned: [], project_order: ['default', 'p1', 'p2'] }]));
const projects = Object.fromEntries(modes.map(mode => [mode, ['default', 'p1', 'p2'].map((id, i) => ({ id, name: i ? `${mode} 项目 ${i} ${'长项目标题'.repeat(12)}` : '默认项目', archived: false }))]));
const sessions = modes.flatMap(mode => Array.from({ length: 27 }, (_, i) => ({ id: `${mode}-${i}`, mode, title: `${mode} 会话 ${i} ${'长标题测试'.repeat(15)}`, status: i ? 'completed' : 'running', project_id: 'default', updated_at: 2000 - i })));
const group = { id: 'q-native', seq: 2, items: [{ id: 'one', question: '请选择研究方向', options: [{ label: '基本面（推荐）', description: '比较企业经营' }, { label: '技术面' }] }, { id: 'two', question: '请选择需要的资料', multiSelect: true, options: [{ label: '公告' }, { label: '财务' }, { label: '新闻' }] }] };
const details = Object.fromEntries(sessions.map(s => [s.id, { ...s, messages: [{ id: 'user', role: 'user', text: '请先确认研究参数', seq: 1 }], questions: s.id.endsWith('-0') ? [structuredClone(group)] : [], question_history: [], activities: [], approvals: [], files: [{ id: 'current-file', name: '当前会话资料.md', kind: 'outputs', url: '/fixture-file', preview_url: '/fixture-file' }], datasets: [], subagents: [], can_cancel: false }]));
const streams = new Map();
let failNavigation = 0;
let failAnswer = false;
let failProjectCreate = false;
const send = (response, status, payload) => response.writeHead(status, { 'content-type': 'application/json', 'cache-control': 'no-store' }).end(JSON.stringify(payload));
const broadcast = id => { for (const response of streams.get(id) || []) response.write(`event: snapshot\ndata: ${JSON.stringify(details[id])}\n\n`); };
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
        if (request.method === 'POST') { if (failProjectCreate) { failProjectCreate = false; return send(response, 500, { error: { code: 'fixture_project_failed', message: '夹具创建失败，请保留草稿重试' } }); } const item = { id: `${mode}-created`, name: body.name, archived: false }; projects[mode].push(item); return send(response, 201, item); }
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
        if (suffix === '/project' && request.method === 'PUT') { details[id].project_id = body.project_id; sessions.find(s => s.id === id).project_id = body.project_id; return send(response, 200, details[id]); }
        return send(response, 200, suffix === '/files' ? { items: details[id].files } : details[id]);
      }
      if (endpoint === '/sessions') return send(response, 200, { items: sessions });
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
const check = async (name, fn) => { try { await fn(); report.checks.push(name); console.log(`PASS ${name}`); } catch (error) { report.failures.push({ name, error: error.message }); console.log(`FAIL ${name}: ${error.message}`); } };
const shot = async (page, name) => { const target = path.join(output, `${name}.png`); await page.screenshot({ path: target }); report.screenshots.push(target); };
async function assertSquareIcons(page, selector, { centeredButtons = false } = {}) {
  const metrics = await page.locator(selector).evaluateAll(elements => elements.map(element => {
    const rect = element.getBoundingClientRect(); const button = element.closest('button'); const parent = button?.getBoundingClientRect();
    return { width: rect.width, height: rect.height, visible: !!element.getClientRects().length && getComputedStyle(element).visibility !== 'hidden', button: !!button, centerX: parent ? Math.abs(rect.x + rect.width / 2 - parent.x - parent.width / 2) : 0, centerY: parent ? Math.abs(rect.y + rect.height / 2 - parent.y - parent.height / 2) : 0, inside: !parent || (rect.left >= parent.left - .5 && rect.right <= parent.right + .5 && rect.top >= parent.top - .5 && rect.bottom <= parent.bottom + .5) };
  }));
  const visible = metrics.filter(item => item.visible); assert.ok(visible.length > 0, `no visible icons: ${selector}`);
  for (const item of visible) {
    assert.ok(item.width > 0 && item.height > 0 && Math.abs(item.width - item.height) <= .5, JSON.stringify(item));
    if (centeredButtons && item.button) assert.ok(item.inside && item.centerX <= .5 && item.centerY <= .5, JSON.stringify(item));
  }
}
try {
  await mkdir(output, { recursive: true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  if (preview) {
    report.status = 'preview';
    console.log(JSON.stringify({ status: 'preview', origin, routes: [`${origin}/#/fingpt`, `${origin}/#/claw`, `${origin}/#/claw?session=claw-0`, `${origin}/#/fingpt?session=fingpt-0`], environment: report.environment }));
    await new Promise(resolve => { process.once('SIGTERM', resolve); process.once('SIGINT', resolve); });
  } else {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ reducedMotion: 'reduce' });
  await context.route('**/*', route => new URL(route.request().url()).origin === origin ? route.continue() : route.abort());
  const page = await context.newPage();
  page.setDefaultTimeout(5000);
  page.on('pageerror', error => { report.failures.push(`pageerror:${error.message}`); console.log(`PAGEERROR ${error.message}`); });
  if (dialogsOnly) {
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
      await dialog.getByRole('button', { name: '创建项目', exact: true }).click(); await dialog.waitFor({ state: 'detached' });
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
    for (const mode of modes) for (const width of [1440, 390]) await check(`${mode}/${width}: first selection, reselection, visible forward and click continue`, async () => {
      await page.setViewportSize({ width, height: 900 });
      await page.goto(`${origin}/#/${mode}?session=${mode}-0`); await page.reload({ waitUntil: 'domcontentloaded' });
      await page.locator('[name="selection-0"]').first().waitFor();
      await page.waitForFunction(value => ['models', 'workspaces', 'report-workflows', `navigation/${value}`].every(endpoint => performance.getEntriesByType('resource').some(entry => entry.name.includes(`/api/research/${endpoint}`))), mode);
      await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
      const rows = page.locator('.codex-question-option-row');
      assert.equal(await rows.nth(0).locator('.codex-option-forward').isVisible(), false);
      assert.equal(await rows.nth(1).locator('.codex-option-forward').isVisible(), false);
      await rows.nth(0).locator('input').evaluate(element => { window.fixtureRadio = element; });
      await rows.nth(0).locator('input').check();
      assert.equal(await rows.nth(0).locator('.codex-option-forward').isVisible(), true);
      assert.equal(await rows.nth(1).locator('.codex-option-forward').isVisible(), false);
      await shot(page, `forward-${mode}-${width}-first`);
      assert.equal(await page.evaluate(() => window.fixtureRadio.isConnected), true, 'radio DOM must survive capture');
      await rows.nth(0).locator('input').press('ArrowDown');
      assert.equal(await rows.nth(1).locator('input').isChecked(), true, 'ArrowDown selects B');
      assert.equal(await rows.nth(1).locator('input').evaluate(element => document.activeElement === element), true, 'ArrowDown retains radio focus');
      assert.equal(await rows.nth(0).locator('.codex-option-forward').isVisible(), false);
      assert.equal(await rows.nth(1).locator('.codex-option-forward').isVisible(), true);
      await check(`${mode}/${width}: forward SVG geometry`, () => assertSquareIcons(page, '.codex-option-forward:visible svg', { centeredButtons: true }));
      await shot(page, `forward-${mode}-${width}-reselected`);
      await rows.nth(1).getByRole('button', { name: '选择并继续', exact: true }).click();
      assert.equal(await page.locator('.question-form').getAttribute('data-q-index'), '1');
      assert.equal(await page.evaluate(() => document.activeElement.matches('legend.codex-question-title')), true);
      await page.locator('[data-q-page="prev"]').click();
      assert.equal(await page.locator('[name="selection-0"]').nth(1).isChecked(), true);
      assert.equal(await rows.nth(0).locator('.codex-option-forward').isVisible(), false);
      assert.equal(await rows.nth(1).locator('.codex-option-forward').isVisible(), true);
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
    await page.locator('[name="selection-0"]').first().check();
    await assertSquareIcons(page, '.question-form svg', { centeredButtons: true });
    await page.locator('.codex-question-arrow[data-q-page="next"]').click();
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
