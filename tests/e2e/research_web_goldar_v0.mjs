/** Read-only visual acceptance for the Gold and Dollar continuous research canvases. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const projectRoot = path.resolve(import.meta.dirname, '../..');
const uiRoot = path.join(projectRoot, 'app/research_web/ui');
const outputRoot = path.join(projectRoot, 'outputs/frameworks-v1');
const origin = 'http://127.0.0.1:8088';
const contentTypes = new Map([['.css', 'text/css'], ['.html', 'text/html'], ['.js', 'text/javascript'], ['.mjs', 'text/javascript'], ['.png', 'image/png']]);
const viewports = [[1440, 900], [1280, 720], [1024, 768], [768, 1024], [390, 844]];
const report = { status: 'running', checks: [], screenshots: [], consoleErrors: [], pageErrors: [] };
const { goldTestData } = await import(pathToFileURL(path.join(uiRoot, 'frameworks/fixtures/gold-v0.mjs')));
const { dollarTestData } = await import(pathToFileURL(path.join(uiRoot, 'frameworks/fixtures/dollar-v1.mjs')));
const frameworkCases = [
  {
    slug: 'gold',
    data: goldTestData(),
    chartCount: 5,
    anchors: { drivers: '定价驱动', supply: '供需与资金', cycle: '周期与宏观', positioning: '持仓与期权', allocation: '情景与配置', evidence: '事件与证据' },
  },
  {
    slug: 'dollar',
    data: dollarTestData(),
    chartCount: 6,
    anchors: { quantity: 'Q 总量水库', price: 'P 资金价格', fiscal: 'g 财政水流', plumbing: 'M 融资管道', 'cross-border': 'X 跨境美元', evidence: '传导与证据' },
  },
];

async function fulfill(route) {
  const request = route.request();
  if (!['GET', 'HEAD'].includes(request.method())) return route.abort('blockedbyclient');
  const url = new URL(request.url());
  if (url.pathname.startsWith('/api/research/')) {
    const matchingFramework = frameworkCases.find((item) => url.pathname === `/api/research/frameworks/${item.slug}/data`);
    const payload = matchingFramework
      ? matchingFramework.data
      : url.pathname === '/api/research/frameworks'
        ? { items: frameworkCases.map(({ data }) => ({ ...data.framework, status: data.snapshot.status, coverage: data.snapshot.coverage, updated_at: data.snapshot.as_of })) }
        : url.pathname.endsWith('/runtime')
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
    console.error(JSON.stringify({ event: 'frameworks_v1_asset_failed', error_type: error?.name || 'Error' }));
    return route.fulfill({ status: 404, body: 'Not found' });
  }
}

await mkdir(outputRoot, { recursive: true });
const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs'));
const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });

try {
  for (const theme of ['light', 'dark']) {
    for (const [width, height] of viewports) {
      for (const frameworkCase of frameworkCases) {
        const context = await browser.newContext({ viewport: { width, height }, colorScheme: theme });
        await context.addInitScript((selectedTheme) => localStorage.setItem('research-web.appearance.v1', selectedTheme), theme);
        const page = await context.newPage();
        page.on('pageerror', error => report.pageErrors.push(`${frameworkCase.slug}:${error.name}`));
        page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`${frameworkCase.slug}:${message.text()}`); });
        await page.route('**/*', fulfill);
        await page.goto(`${origin}/#/frameworks/${frameworkCase.slug}`, { waitUntil: 'networkidle' });
        await page.locator('.framework-detail').waitFor();
        assert.equal(await page.locator('html').getAttribute('data-theme'), theme);
        assert.equal(await page.locator('.framework-anchor-rail a').count(), 7);
        assert.equal(await page.locator('[data-lieflat-basics]').count(), frameworkCase.chartCount);
        assert.equal(await page.locator('iframe').count(), 0);
        assert.equal(await page.locator('link[href^="http"], script[src^="http"], img[src^="http"]').count(), 0);
        const geometry = await page.evaluate(() => ({
          documentOverflow: document.documentElement.scrollWidth > innerWidth,
          mainOverflow: document.querySelector('#main').scrollWidth > document.querySelector('#main').clientWidth,
          mainLandmarks: document.querySelectorAll('main').length,
          canvasTag: document.querySelector('.framework-canvas')?.tagName,
          canvasLabel: document.querySelector('.framework-canvas')?.getAttribute('aria-label'),
          heroStacked: document.querySelector('.framework-hero-meta').getBoundingClientRect().top >= document.querySelector('.framework-hero-main').getBoundingClientRect().bottom - 1,
          metadataFits: [...document.querySelectorAll('.framework-hero-meta dd')].every(item => item.scrollWidth <= item.clientWidth),
          launcher: (() => {
            const item = document.querySelector('[data-framework-bot-open]');
            const rect = item.getBoundingClientRect();
            const canvas = document.querySelector('.framework-canvas').getBoundingClientRect();
            const overlapsCanvas = rect.left < canvas.right && rect.right > canvas.left && rect.top < canvas.bottom && rect.bottom > canvas.top;
            return { width: rect.width, height: rect.height, label: item.getAttribute('aria-label'), overlapsCanvas };
          })(),
          tabHeight: Math.min(...[...document.querySelectorAll('.framework-anchor-rail a')].map(item => item.getBoundingClientRect().height)),
          chartOverflowReady: [...document.querySelectorAll('.lieflat-chart')].every(item => getComputedStyle(item).overflowX === 'auto' || item.scrollWidth <= item.clientWidth),
        }));
        assert.equal(geometry.documentOverflow, false);
        assert.equal(geometry.mainOverflow, false);
        assert.equal(geometry.mainLandmarks, 1);
        assert.equal(geometry.canvasTag, 'SECTION');
        assert.equal(geometry.canvasLabel, frameworkCase.slug === 'gold' ? '黄金研究画布' : '美元流动性研究画布');
        assert.ok(geometry.tabHeight >= 44);
        assert.equal(geometry.chartOverflowReady, true);
        if (width <= 900) {
          assert.equal(geometry.heroStacked, true);
          assert.equal(geometry.metadataFits, true);
          assert.equal(geometry.launcher.label, '问当前框架');
          assert.ok(geometry.launcher.width <= 44.1);
          assert.ok(geometry.launcher.height <= 44.1);
          assert.equal(geometry.launcher.overlapsCanvas, false);
        }
        if ([1440, 768, 390].includes(width)) {
          const filename = `${frameworkCase.slug}-${theme}-${width}x${height}-overview.png`;
          await page.screenshot({ path: path.join(outputRoot, filename), fullPage: true });
          report.screenshots.push(filename);
        }
        if (theme === 'light' && [1440, 390].includes(width)) {
          await page.locator('[data-framework-bot-open]').click();
          await page.locator('.framework-bot').waitFor();
          assert.match(await page.locator('.framework-bot-context').textContent(), /无工具解释/);
          const filename = `${frameworkCase.slug}-light-${width}x${height}-bot.png`;
          await page.screenshot({ path: path.join(outputRoot, filename) });
          report.screenshots.push(filename);
        }
        report.checks.push({ theme, width, height, route: `#/frameworks/${frameworkCase.slug}`, geometry });
        await context.close();
      }
    }
  }

  for (const frameworkCase of frameworkCases) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light', reducedMotion: 'reduce' });
    await context.addInitScript(() => localStorage.setItem('research-web.appearance.v1', 'light'));
    const page = await context.newPage();
    page.on('pageerror', error => report.pageErrors.push(`${frameworkCase.slug}:${error.name}`));
    page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`${frameworkCase.slug}:${message.text()}`); });
    await page.route('**/*', fulfill);
    await page.goto(`${origin}/#/frameworks/${frameworkCase.slug}`, { waitUntil: 'networkidle' });
    for (const [tab, label] of Object.entries(frameworkCase.anchors)) {
      await page.locator(`.framework-anchor-rail a[href*="tab=${tab}"]`).focus();
      await page.keyboard.press('Enter');
      await page.locator(`#framework-${tab}`).waitFor();
      assert.match(await page.locator('.framework-anchor-rail a[aria-current="location"]').textContent(), new RegExp(label));
      const filename = `${frameworkCase.slug}-light-1440x900-${tab}.png`;
      await page.screenshot({ path: path.join(outputRoot, filename), fullPage: true });
      report.screenshots.push(filename);
    }
    assert.equal(await page.locator('.lf-reveal').first().evaluate(element => getComputedStyle(element).animationName), 'none');
    report.checks.push({ framework: frameworkCase.slug, reducedMotion: true, keyboardAnchors: Object.keys(frameworkCase.anchors).length });
    await context.close();
  }

  const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, colorScheme: 'light' });
  const page = await context.newPage();
  page.on('pageerror', error => report.pageErrors.push(`hub:${error.name}`));
  page.on('console', message => { if (message.type() === 'error') report.consoleErrors.push(`hub:${message.text()}`); });
  await page.route('**/*', fulfill);
  await page.goto(`${origin}/#/frameworks`, { waitUntil: 'networkidle' });
  await page.locator('.framework-hub').waitFor();
  assert.equal(await page.locator('[data-framework-card]').count(), 2);
  const hubFilename = 'light-1440x900-hub.png';
  await page.screenshot({ path: path.join(outputRoot, hubFilename), fullPage: true });
  report.screenshots.push(hubFilename);
  await context.close();
  assert.deepEqual(report.pageErrors, []);
  assert.deepEqual(report.consoleErrors, []);
  report.checks.push({ hubCards: 2 });
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
