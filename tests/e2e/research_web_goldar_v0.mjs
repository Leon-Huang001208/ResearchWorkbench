/** Read-only visual acceptance for the Goldar fixed-fixture checkpoint. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const projectRoot = path.resolve(import.meta.dirname, '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.join(projectRoot, 'outputs/goldar-v0');
const origin = 'http://127.0.0.1:8088';
const contentTypes = new Map([['.css', 'text/css'], ['.html', 'text/html'], ['.js', 'text/javascript'], ['.mjs', 'text/javascript'], ['.png', 'image/png']]);
const viewports = [[1440, 900], [1280, 720], [1024, 768], [768, 1024], [390, 844]];
const report = { status: 'running', checks: [], screenshots: [], consoleErrors: [], pageErrors: [] };

async function fulfill(route) {
  const request = route.request();
  if (!['GET', 'HEAD'].includes(request.method())) return route.abort('blockedbyclient');
  const url = new URL(request.url());
  if (url.pathname.startsWith('/api/research/')) {
    const payload = url.pathname.endsWith('/runtime')
      ? { connected: true, credential_configured: true }
      : url.pathname.endsWith('/models')
        ? { groups: [], failures: [] }
        : { items: [] };
    return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) });
  }
  const relative = url.pathname === '/' ? 'index.html' : url.pathname.startsWith('/static/') ? url.pathname.slice(8) : null;
  if (relative === null) return route.abort('blockedbyclient');
  const file = path.resolve(uiRoot, relative);
  if (file !== uiRoot && !file.startsWith(`${uiRoot}${path.sep}`)) return route.abort('blockedbyclient');
  try {
    return route.fulfill({ status: 200, body: await readFile(file), contentType: contentTypes.get(path.extname(file)) || 'application/octet-stream' });
  } catch (error) {
    console.error(JSON.stringify({ event: 'goldar_v0_asset_failed', error_type: error?.name || 'Error' }));
    return route.fulfill({ status: 404, body: 'Not found' });
  }
}

await mkdir(outputRoot, { recursive: true });
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });

try {
  for (const theme of ['light', 'dark']) {
    for (const [width, height] of viewports) {
      const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme });
      await context.addInitScript((selectedTheme) => localStorage.setItem('research-web.appearance.v1', selectedTheme), theme);
      const page = await context.newPage();
      page.on('pageerror', error => report.pageErrors.push(error.name));
      page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(message.text()); });
      await page.route('**/*', fulfill);
      await page.goto(`${origin}/#/frameworks/gold`, { waitUntil: 'networkidle' });
      await page.locator('.framework-detail').waitFor();
      assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
      assert.equal(await page.locator('.framework-tabs a').count(), 7);
      assert.equal(await page.locator('iframe').count(), 0);
      assert.equal(await page.locator('link[href^="http"], script[src^="http"], img[src^="http"]').count(), 0);
      const geometry = await page.evaluate(() => ({
        documentOverflow: document.documentElement.scrollWidth > innerWidth,
        mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth,
        tabHeight: Math.min(...[...document.querySelectorAll('.framework-tabs a')].map(item => item.getBoundingClientRect().height)),
        chartOverflowReady: [...document.querySelectorAll('.lieflat-chart')].every(item => getComputedStyle(item).overflowX === 'auto' || item.scrollWidth <= item.clientWidth),
      }));
      assert.equal(geometry.documentOverflow, false);
      assert.equal(geometry.mainOverflow, false);
      assert.ok(geometry.tabHeight >= 44);
      assert.equal(geometry.chartOverflowReady, true);
      if ([1440, 390].includes(width)) {
        const filename = `${theme}-${width}x${height}-overview.png`;
        await page.screenshot({ path: path.join(outputRoot, filename), fullPage: true });
        report.screenshots.push(filename);
      }
      report.checks.push({ theme, width, height, route: '#/frameworks/gold', geometry });
      await context.close();
    }
  }

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce' });
  await context.addInitScript(() => localStorage.setItem('research-web.appearance.v1', 'light'));
  const page = await context.newPage();
  page.on('pageerror', error => report.pageErrors.push(error.name));
  page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(message.text()); });
  await page.route('**/*', fulfill);
  await page.goto(`${origin}/#/frameworks/gold`, { waitUntil: 'networkidle' });
  const tabs = ['drivers', 'supply', 'cycle', 'positioning', 'allocation', 'evidence'];
  for (const tab of tabs) {
    await page.locator(`.framework-tabs a[href*="tab=${tab}"]`).focus();
    await page.keyboard.press('Enter');
    await page.locator(`#framework-${tab}`).waitFor();
    assert.equal(await page.locator('.framework-tabs a[aria-current="page"]').textContent(), ({ drivers: '定价驱动', supply: '供需与资金', cycle: '周期与宏观', positioning: '持仓与期权', allocation: '情景与配置', evidence: '事件与证据' })[tab]);
    const filename = `light-1440x900-${tab}.png`;
    await page.screenshot({ path: path.join(outputRoot, filename), fullPage: true });
    report.screenshots.push(filename);
  }
  assert.equal(await page.locator('#framework-evidence').evaluate(element => getComputedStyle(element).animationName), 'none');
  await page.goto(`${origin}/#/frameworks`, { waitUntil: 'networkidle' });
  await page.locator('.framework-hub').waitFor();
  const hubFilename = 'light-1440x900-hub.png';
  await page.screenshot({ path: path.join(outputRoot, hubFilename), fullPage: true });
  report.screenshots.push(hubFilename);
  await context.close();
  assert.deepEqual(report.pageErrors, []);
  assert.deepEqual(report.consoleErrors, []);
  report.checks.push({ reducedMotion: true, keyboardTabs: tabs.length });
  report.status = 'passed';
} catch (error) {
  report.status = 'failed';
  report.failure = error.stack || error.message;
  process.exitCode = 1;
} finally {
  await browser.close();
  await writeFile(path.join(outputRoot, 'verification.json'), JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report));
}
