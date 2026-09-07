/** Read-only navigation-shell acceptance against the current worktree UI. */
import assert from 'node:assert/strict';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import path from 'node:path';

const origin = new URL(process.env.RESEARCH_WEB_URL || 'http://127.0.0.1:8088');
if (origin.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(origin.hostname)) {
  throw new Error('Navigation acceptance is limited to a local Research Workbench deployment');
}

const uiRoot = path.resolve('app/research_web/ui');
const outputRoot = path.resolve('outputs/research-web-nav-v0');
const logPath = path.resolve('logs/research-web-navigation-v0.jsonl');
const contentTypes = new Map([
  ['.css', 'text/css; charset=utf-8'],
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml'],
]);

async function serveWorktreeAsset(route) {
  const request = route.request();
  if (!['GET', 'HEAD'].includes(request.method())) {
    await route.abort('blockedbyclient');
    return;
  }
  const url = new URL(request.url());
  const relative = url.pathname === '/' ? 'index.html' : url.pathname.startsWith('/static/') ? url.pathname.slice(8) : null;
  if (relative === null) {
    await route.continue();
    return;
  }
  const candidate = path.resolve(uiRoot, relative);
  if (candidate !== uiRoot && !candidate.startsWith(`${uiRoot}${path.sep}`)) {
    await route.abort('blockedbyclient');
    return;
  }
  try {
    const body = await readFile(candidate);
    await route.fulfill({ status: 200, body, contentType: contentTypes.get(path.extname(candidate)) || 'application/octet-stream' });
  } catch (error) {
    console.error(JSON.stringify({ event: 'navigation_asset_read_failed', error_type: error?.name || 'Error' }));
    await route.fulfill({ status: 404, body: 'Not found', contentType: 'text/plain; charset=utf-8' });
  }
}

async function geometry(page, mode, width) {
  const nav = page.getByRole('navigation', { name: '产品主导航', exact: true });
  const sidebarName = mode === 'fingpt' ? 'FinGPT 会话侧栏' : 'Claw 会话与工作空间侧栏';
  const sidebar = page.getByRole('complementary', { name: sidebarName, exact: true });
  if (width <= 1050) await page.getByRole('button', { name: '打开导航', exact: true }).click();
  await nav.waitFor({ state: 'visible' });
  await sidebar.waitFor({ state: 'visible' });
  const [railBox, sidebarBox] = await Promise.all([nav.boundingBox(), sidebar.boundingBox()]);
  assert.ok(railBox && sidebarBox, `${mode} navigation must have measurable geometry`);
  assert.ok(Math.abs(railBox.width - 68) <= 1, `${mode} primary rail should be 68px, received ${railBox.width}`);
  assert.ok(Math.abs(sidebarBox.x - 68) <= 1, `${mode} secondary sidebar should begin after the rail, received x=${sidebarBox.x}`);
  assert.ok(Math.abs(sidebarBox.width - 248) <= 1, `${mode} secondary sidebar should be 248px, received ${sidebarBox.width}`);
  const overflow = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
  assert.ok(overflow.scrollWidth <= overflow.width, `${mode} should not overflow horizontally: ${JSON.stringify(overflow)}`);
  return { rail: railBox, sidebar: sidebarBox, overflow };
}

let browser;
const results = [];
try {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  const { chromium } = await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
  browser = await chromium.launch({
    headless: true,
    executablePath: process.env.CHROME_EXECUTABLE_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  });
  for (const mode of ['fingpt', 'claw']) {
    for (const [width, height] of [[1440, 900], [390, 844]]) {
      const context = await browser.newContext({ viewport: { width, height } });
      const page = await context.newPage();
      await page.route('**/*', serveWorktreeAsset);
      await page.goto(`${origin.origin}/#/${mode}`, { waitUntil: 'domcontentloaded' });
      await page.locator('.app-shell').waitFor();
      const measured = await geometry(page, mode, width);
      const imagePath = path.join(outputRoot, `${mode}-${width}x${height}.png`);
      await page.screenshot({ path: imagePath, fullPage: true });
      results.push({ mode, width, height, status: 'passed', imagePath, measured });
      await context.close();
    }
  }
  await writeFile(path.join(outputRoot, 'receipt.json'), JSON.stringify({ status: 'passed', results }, null, 2));
  await writeFile(logPath, `${JSON.stringify({ event: 'research_navigation_v0', status: 'passed', checks: results.length })}\n`);
  console.log(`research navigation v0: ${results.length} viewport checks passed`);
} catch (error) {
  await mkdir(outputRoot, { recursive: true });
  await mkdir(path.dirname(logPath), { recursive: true });
  await writeFile(path.join(outputRoot, 'receipt.json'), JSON.stringify({ status: 'failed', error: error.message, results }, null, 2));
  await writeFile(logPath, `${JSON.stringify({ event: 'research_navigation_v0', status: 'failed', error_type: error.name })}\n`);
  console.error(error.message);
  process.exitCode = 1;
} finally {
  if (browser) await browser.close();
}
