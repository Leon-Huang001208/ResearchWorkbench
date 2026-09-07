/** Read-only appearance checks. Never submits research or operates an existing browser. */
import assert from 'node:assert/strict';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, dirname, sep } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const started = performance.now();
const ui = resolve(project, 'app/research_web/ui');
const base = process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088';
const live = process.argv.includes('--live');
const output = resolve(project, 'outputs/research-web-appearance', live ? 'live' : 'isolated');
const logDir = resolve(project, 'logs');
await mkdir(output, { recursive: true }); await mkdir(logDir, { recursive: true });
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, colorScheme: 'light' });
const page = await context.newPage();
page.setDefaultTimeout(15000);
const report = { live, checks: [], screenshots: [], errors: [], blockedWrites: 0 };
page.on('pageerror', error => report.errors.push(error.name));
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url());
  if (url.origin !== base || !['GET', 'HEAD'].includes(request.method())) {
    report.blockedWrites += 1; return route.abort();
  }
  if (!live && (url.pathname === '/' || url.pathname.startsWith('/static/'))) {
    const file = resolve(ui, url.pathname === '/' ? 'index.html' : url.pathname.slice('/static/'.length));
    if (!file.startsWith(ui + sep)) return route.abort();
    try {
      const types = { css: 'text/css', js: 'text/javascript', mjs: 'text/javascript', html: 'text/html', png: 'image/png' };
      return route.fulfill({ body: await readFile(file), contentType: types[file.split('.').at(-1)] || 'application/octet-stream' });
    } catch { return route.fulfill({ status: 404 }); }
  }
  return route.continue();
});
const check = name => report.checks.push(name);
const shot = async name => { await page.screenshot({ path: resolve(output, name + '.png'), fullPage: true }); report.screenshots.push(name + '.png'); };
const setTheme = async value => {
  await page.goto(base + '/#/settings');
  const option = page.locator(`[data-theme-option][value="${value}"]`);
  await option.waitFor();
  const label = { system: '跟随系统', light: '浅色', dark: '深色' }[value];
  await page.locator('.appearance-option').filter({ hasText: label }).click();
  assert.equal(await option.isChecked(), true);
};
try {
  await page.goto(base + '/#/fingpt');
  await page.locator('#prompt').waitFor();
  await page.waitForFunction(() => document.querySelector('#skill-select')?.options.length > 1);
  await page.locator('#prompt').fill('外观切换应保留这条尚未发送的草稿');
  await setTheme('dark');
  await page.goto(base + '/#/fingpt'); await page.locator('#prompt').waitFor();
  assert.equal(await page.locator('#prompt').inputValue(), '外观切换应保留这条尚未发送的草稿');
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark');
  await page.reload(); await page.locator('#prompt').waitFor();
  assert.equal(await page.locator('html').getAttribute('data-theme'), 'dark'); check('manual theme persists across reload; switching does not clear draft');
  await setTheme('system');
  await page.emulateMedia({ colorScheme: 'light' });
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  await page.emulateMedia({ colorScheme: 'dark' });
  await page.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  check('system appearance changes applied');
  for (const theme of ['light', 'dark']) {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await setTheme(theme);
    const buttonStates = await page.evaluate(() => {
      const fixture = document.createElement('section');
      fixture.setAttribute('aria-label', '仅测试：按钮状态');
      fixture.innerHTML = '<button class="button primary">默认</button><button class="button primary" disabled>正在提交…</button><button class="button danger-outline">拒绝</button><button class="button danger-outline" disabled>停止中</button>';
      document.body.append(fixture);
      const result = [...fixture.querySelectorAll('button')].map(button => ({ disabled: button.disabled, color: getComputedStyle(button).color, background: getComputedStyle(button).backgroundColor, cursor: getComputedStyle(button).cursor }));
      fixture.remove(); return result;
    });
    assert.notEqual(buttonStates[0].color, buttonStates[1].color);
    assert.equal(buttonStates[1].cursor, 'not-allowed');
    assert.equal(buttonStates[3].color, buttonStates[1].color);
    assert.notEqual(buttonStates[2].color, buttonStates[3].color);
    check(`${theme}: default, loading-disabled, danger, danger-disabled computed styles`);
    for (const width of [1440, 1600, 1920, 820, 390]) {
      await page.setViewportSize({ width, height: width < 600 ? 844 : 1000 });
      await page.goto(base + '/#/fingpt'); await page.locator('#prompt').waitFor();
      await page.waitForFunction(() => document.querySelectorAll('.quick-skill-card').length > 0);
      const geometry = await page.evaluate(() => ({
        overflow: document.documentElement.scrollWidth > innerWidth,
        mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth,
        input: document.querySelector('#prompt').getBoundingClientRect().width,
        filter: getComputedStyle(document.querySelector('.rail-brand .brand-mark img')).filter,
      }));
      assert.equal(geometry.overflow, false); assert.equal(geometry.mainOverflow, false); assert.ok(geometry.input > 240);
      assert.equal(geometry.filter.includes('invert(1)'), theme === 'dark');
      if (width === 1440) {
        // The approved 68px rail + 248px secondary sidebar shifts the canvas,
        // while the landing content remains one aligned 800px column.
        const boxes = await page.evaluate(() => Object.fromEntries(['.greeting', '.composer', '.quick-skill-grid'].map(selector => [selector, document.querySelector(selector).getBoundingClientRect().toJSON()])));
        assert.equal(boxes['.composer'].width, 800);
        assert.ok(Math.abs(boxes['.greeting'].x - boxes['.composer'].x) <= 2);
        assert.ok(Math.abs(boxes['.quick-skill-grid'].x - boxes['.composer'].x) <= 2);
        assert.ok(boxes['.greeting'].y + boxes['.greeting'].height < boxes['.composer'].y);
        assert.ok(boxes['.composer'].y + boxes['.composer'].height < boxes['.quick-skill-grid'].y);
        assert.equal(boxes['.quick-skill-grid'].height, 94);
        check(`${theme}: approved secondary-navigation canvas keeps one aligned 800px content column`);
      }
      await shot(`${theme}-fingpt-${width}`);
      if (width <= 1050) {
        await page.locator('.menu-toggle').click();
        assert.equal(await page.locator('.primary-rail').isVisible(), true);
        assert.equal(await page.locator('.secondary-sidebar').isVisible(), true);
        await page.locator('.rail-mobile-close').click();
        assert.equal(await page.locator('.primary-rail').isVisible(), false);
      }
      check(`${theme} ${width}: layout, symbol, navigation`);
    }
    await page.setViewportSize({ width: 1440, height: 1000 });
    for (const route of ['claw', 'skills', 'settings', 'history']) {
      await page.goto(base + '/#/' + route); await page.locator('#main h1').waitFor();
      assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
      await shot(`${theme}-${route}`); check(`${theme} ${route}: rendered`);
    }
    await page.goto(base + '/#/skills');
    for (const kind of ['skill', 'tool', 'workflow']) {
      await page.locator(`[data-cap-kind="${kind}"]`).click();
      await page.getByRole('button', { name: '查看详情', exact: true }).first().click();
      await page.locator('.capability-detail').waitFor();
      const colors = await page.locator('.capability-detail').evaluate(el => ({ bg: getComputedStyle(el).backgroundColor, expected: getComputedStyle(document.body).backgroundColor }));
      assert.equal(colors.bg, colors.expected);
      await shot(`${theme}-${kind}-detail`);
      await page.locator('[data-cap-close]').click();
    }
    await page.locator('[data-cap-kind="workflow"]').click();
    await page.locator('[data-cap-create="manual"]').click();
    await page.locator('#cap-editor-form').waitFor();
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth || document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth), false);
    await shot(`${theme}-workflow-editor-mobile`);
    await page.locator('[data-cap-cancel-edit]').click();
    await page.setViewportSize({ width: 1440, height: 1000 });
    check(`${theme}: Skill/Tool/Workflow details and unsaved mobile editor preserve original behaviors`);
  }
  await page.goto(base + '/#/fingpt'); await page.locator('#prompt').waitFor();
  await page.locator('[data-collapse-sidebar]').click();
  assert.equal(await page.locator('.primary-nav').isVisible(), true);
  await page.locator('[data-toggle-sidebar].rail-toggle').click();
  assert.equal(await page.locator('.secondary-sidebar').isVisible(), true);
  await page.goto(base + '/#/claw'); await page.locator('#prompt').waitFor();
  await page.locator('[data-claw-sidebar-view="workspace"]').click();
  assert.equal(await page.locator('#workspace-select').isVisible(), true); check('primary navigation and Claw workspace remain available after secondary-sidebar collapse');
  await page.locator('.search-trigger').click();
  await page.locator('#global-search').fill('company');
  await page.locator('.global-results').waitFor(); check('existing global search opens');
  await page.keyboard.press('Escape');
  assert.equal(await page.locator('.search-popover').isVisible(), false);
  await page.locator('.format-picker summary').click();
  await page.locator('[data-format="md"]').check();
  assert.equal(await page.locator('[data-format="md"]').isChecked(), true);
  if (!await page.locator('[data-no-formats]').isVisible()) await page.locator('.format-picker summary').click();
  await page.locator('[data-no-formats]').click();
  await page.locator('.capability-picker summary').click();
  assert.equal(await page.locator('#skill-select').isVisible(), true);
  assert.equal(await page.locator('#model-select').isVisible(), true);
  await page.locator('.capability-picker summary').click();
  check('search Escape, output format selection and full capability picker remain usable without writes');
  const sessions = await page.evaluate(async () => (await (await fetch('/api/research/sessions')).json()).items || []);
  const session = sessions.find(item => item.mode === 'claw') || sessions[0];
  if (session) {
    await page.goto(`${base}/#/${session.mode === 'claw' ? 'claw' : 'fingpt'}?session=${encodeURIComponent(session.id)}`);
    await page.locator('[data-toggle-context]').waitFor();
    assert.equal(await page.locator('.context-panel').count(), 0);
    await page.locator('[data-toggle-context]').click();
    for (const tab of ['activity', 'datasets', 'files']) {
      await page.locator(`[data-context-tab="${tab}"]`).click();
      assert.equal(await page.locator(`[data-context-tab="${tab}"]`).getAttribute('aria-selected'), 'true');
    }
    await shot('dark-session-files');
    await page.locator('.context-close').click();
    assert.equal(await page.locator('.context-panel').count(), 0); check('real session readback; activity/data/files panel opens and closes');
  }
  assert.deepEqual(report.errors, []);
  assert.equal(report.blockedWrites, 0); check('zero model/mutation requests; zero browser runtime errors');
  report.status = 'passed';
} catch (error) {
  report.status = 'failed'; report.failure = error.message;
  await shot('failure').catch(() => {});
  process.exitCode = 1;
} finally {
  await browser.close();
  report.durationMs = Math.round(performance.now() - started);
  await writeFile(resolve(output, 'verification.json'), JSON.stringify(report, null, 2));
  await writeFile(resolve(logDir, `research-web-appearance-${live ? 'live' : 'isolated'}.json`), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
}
