import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const { chromium } = await import(process.env.RESEARCH_PLAYWRIGHT_MODULE || 'playwright-core');
const origin = process.env.RESEARCH_WEB_ORIGIN || 'http://127.0.0.1:8088';
const output = 'outputs/research-web-ui-acceptance/interaction-regression';
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, executablePath: process.env.RESEARCH_CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
const receipt = { checks: [], errors: [] };
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  page.on('pageerror', error => receipt.errors.push(error.message));
  await page.goto(`${origin}/#/fingpt`);
  await page.waitForFunction(() => document.querySelector('#model-select')?.options.length > 1);
  await page.locator('.mobile-search-toggle').click();
  const input = page.locator('#global-search');
  await input.fill('研究');
  await page.locator('[data-global-result]').first().waitFor();
  await page.evaluate(() => { window.searchInputBefore = document.querySelector('#global-search'); });
  await input.fill('公司');
  assert.equal(await page.evaluate(() => window.searchInputBefore === document.querySelector('#global-search')), true);
  await input.evaluate(el => {
    el.dispatchEvent(new CompositionEvent('compositionstart', { bubbles: true }));
    el.value = '研报';
    el.dispatchEvent(new InputEvent('input', { bubbles: true, isComposing: true }));
    el.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, key: 'Escape', isComposing: true }));
    el.dispatchEvent(new CompositionEvent('compositionend', { bubbles: true }));
  });
  assert.equal(await input.inputValue(), '研报');
  await page.locator('[data-global-result]').first().waitFor();
  await input.press('ArrowDown');
  assert.equal(await page.evaluate(() => document.activeElement === document.querySelector('[data-global-result]')), true);
  await page.keyboard.press('ArrowDown');
  assert.equal(await page.evaluate(() => document.activeElement === document.querySelectorAll('[data-global-result]')[1]), true);
  await page.keyboard.press('Escape');
  assert.equal(await page.evaluate(() => document.activeElement.matches('.mobile-search-toggle')), true);
  receipt.checks.push('Chinese composition, stable input DOM, keyboard navigation, Escape focus');
  await page.goto(`${origin}/#/history`);
  await page.locator('#history-search').fill('不存在的研究标题');
  assert.match(await page.locator('#history-results').innerText(), /没有|暂无/);
  await page.locator('#history-search').fill('');
  receipt.checks.push('history filtering and clear');
  const historicalSession = process.env.RESEARCH_HISTORICAL_SESSION;
  if (historicalSession) {
  assert.match(historicalSession, /^[A-Za-z0-9_-]{1,255}$/);
  await page.goto(`${origin}/#/fingpt?session=${encodeURIComponent(historicalSession)}`);
  await page.locator('[data-toggle-context]').first().waitFor();
  assert.doesNotMatch(await page.locator('body').innerText(), /原生子会话活动状态未知/);
  assert.equal(await page.locator('[data-cancel]').count(), 0);
  receipt.checks.push('selected historical session has no unresolved child-running state');
  } else { receipt.historical_session = 'NOT_RUN: RESEARCH_HISTORICAL_SESSION not supplied'; }
  await page.screenshot({ path: `${output}/desktop.png`, fullPage: false });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto(`${origin}/#/fingpt`);
  await page.locator('#prompt').waitFor();
  await page.screenshot({ path: `${output}/mobile.png`, fullPage: true });
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth), true);
  receipt.checks.push('mobile no horizontal overflow');
  assert.deepEqual(receipt.errors, []);
  receipt.status = 'passed';
} catch (error) { receipt.status = 'failed'; receipt.failure = String(error); process.exitCode = 1; }
finally { await browser.close(); await writeFile(`${output}/receipt.json`, JSON.stringify(receipt, null, 2)); console.log(JSON.stringify(receipt, null, 2)); }
