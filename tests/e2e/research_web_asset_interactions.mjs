/** Synthetic, loopback-only interaction acceptance. No supplier or model evidence. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, writeFile, appendFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startFixture } from './alphafoundry_fixture.mjs';

assert.match(process.version, /^v24\./, 'Run with the existing bundled Node 24 runtime');
process.env.RWB_DELIVERY_TASK_ID ||= 'wind-date-window-20261022';
assert.ok(!process.env.RWB_ASSET_REAL_PROOF && !process.env.RWB_ASSET_READBACK_JSON, 'This runner accepts synthetic input only');
const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'logs/asset-interactions-e2e');
await mkdir(output, { recursive: true });
const startedAt = new Date().toISOString();
const started = performance.now();
const results = []; const errors = []; const external = []; const screenshots = [];
const fixture = await startFixture(project, output, { interactionMode: true, historyRows: 900 });
const { state, origin } = fixture;
await writeFile(path.join(output, 'source-hashes-before.json'), JSON.stringify(state.migratedSourceHashes, null, 2));
let browser; let page; let sourceEvidence;
const screenshot = async name => { const target = path.join(output, name); await page.screenshot({ path: target, fullPage: false }); screenshots.push(target); };
const check = async (name, fn) => {
  const before = performance.now();
  try { const evidence = await fn(); results.push({ name, status: 'PASS', durationMs: Math.round(performance.now() - before), evidence }); }
  catch (error) { results.push({ name, status: 'FAIL', durationMs: Math.round(performance.now() - before), error: error.message }); if (page) await screenshot(`${name}-failed.png`).catch(failure => { errors.push(`Failure screenshot: ${failure.message}`); }); }
  await appendFile(path.join(output, 'checks.jsonl'), JSON.stringify(results.at(-1)) + '\n');
  console.log(`${results.at(-1).status}: ${name}`);
};
const view = id => page.locator(`[data-asset-tab="${id}"]`);
const stable = () => page.waitForFunction(() => {
  const node = document.querySelector('[data-asset-echarts]');
  const chart = node && window.echarts?.getInstanceByDom(node);
  return Number(node?.dataset.visibleCount) > 0 && chart?.getOption()?.series?.some(series => series.type === 'candlestick');
});
const snapshot = () => page.evaluate(() => {
  const node = document.querySelector('[data-asset-echarts]'); const instance = echarts.getInstanceByDom(node);
  return { chartId: instance.id, selectedDate: node.dataset.selectedDate, start: node.dataset.visibleStart, end: node.dataset.visibleEnd, scrollTop: document.querySelector('#main').scrollTop, tabTop: Math.round(document.querySelector('.asset-topic-tabs').getBoundingClientRect().top) };
});

try {
  assert.equal(state.rows.history.length, 900, 'Interaction fixture must contain more than 600 synthetic bars');
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } });
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (url.startsWith(origin + '/') || url.startsWith('data:')) return route.continue();
    external.push(url); await route.abort();
  });
  page = await context.newPage(); page.setDefaultTimeout(15000);
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto(`${origin}/#/assets?view=overview&asset=600519.SH&asset_type=stock`);
  await stable(); await page.waitForLoadState('networkidle');

  await check('more-than-600-rendered-candle-entities', async () => {
    const source = page.locator('.asset-source-summary');
    assert.equal(await source.count(), 1); assert.equal(await source.getAttribute('open'), null);
    assert.equal(await page.evaluate(() => { const source = document.querySelector('.asset-source-summary'); const chart = document.querySelector('.asset-wind-grid'); const tabs = document.querySelector('.asset-topic-tabs'); return Boolean(chart.compareDocumentPosition(source) & Node.DOCUMENT_POSITION_FOLLOWING) && Boolean(source.compareDocumentPosition(tabs) & Node.DOCUMENT_POSITION_FOLLOWING); }), true);
    await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).dispatchAction({ type: 'dataZoom', start: 0, end: 100 }));
    await page.waitForFunction(() => Number(document.querySelector('[data-asset-echarts]').dataset.visibleCount) === 900);
    const evidence = await page.evaluate(() => {
      const chart = echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]'));
      const model = chart.getModel().getSeries().find(series => series.subType === 'candlestick'); const data = model.getData();
      const items = Array.from({ length: data.count() }, (_, index) => data.getItemGraphicEl(index));
      return { rows: data.count(), renderedEntities: items.filter(item => item && !item.ignore && item.parent).length, large: model.get('large'), progressive: model.get('progressive') };
    });
    assert.equal(evidence.rows, 900); assert.ok(evidence.renderedEntities > 600, JSON.stringify(evidence));
    await screenshot('900-synthetic-candles.png'); return evidence;
  });

  await check('seven-tabs-preserve-dom-instance-selection-viewport-and-scroll', async () => {
    await page.locator('.asset-source-summary > summary').click();
    await page.evaluate(() => { window.fixtureOriginalSource = document.querySelector('.asset-source-summary'); });
    const selectedDate = state.rows.history[450].date;
    await page.locator('[data-asset-selected-date]').fill(selectedDate);
    await page.locator('[data-asset-selected-date]').press('Tab');
    await page.waitForFunction(date => document.querySelector('[data-asset-echarts]').dataset.selectedDate === date, selectedDate);
    await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).dispatchAction({ type: 'dataZoom', startValue: 250, endValue: 799 }));
    await page.waitForFunction(() => { const node = document.querySelector('[data-asset-echarts]'); return node.dataset.visibleStart === '250' && node.dataset.visibleEnd === '800'; });
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    await page.evaluate(() => {
      const node = document.querySelector('[data-asset-echarts]');
      window.fixtureOriginalChart = node; window.fixtureOriginalInstance = echarts.getInstanceByDom(node);
      window.fixtureOriginalChip = document.querySelector('[data-asset-chip-chart]');
      window.fixtureOriginalHeader = document.querySelector('.asset-basic-card');
      const main = document.querySelector('#main'); const tabs = document.querySelector('.asset-topic-tabs');
      main.scrollTop += tabs.getBoundingClientRect().top - main.getBoundingClientRect().top - 24;
    });
    const expected = await snapshot(); const checks = [];
    const historyReads = () => state.reads.filter(read => read.includes('/datasets/history-fixture/')).length;
    const initialReads = historyReads();
    for (const id of ['financials', 'capital', 'holders', 'news', 'announcements', 'materials', 'overview']) {
      await view(id).click(); await page.locator(`[data-asset-topic="${id}"]`).waitFor(); await page.waitForLoadState('networkidle');
      const same = await page.evaluate(() => {
        const node = document.querySelector('[data-asset-echarts]');
        return { chart: node === window.fixtureOriginalChart, instance: echarts.getInstanceByDom(node) === window.fixtureOriginalInstance, chip: document.querySelector('[data-asset-chip-chart]') === window.fixtureOriginalChip, header: document.querySelector('.asset-basic-card') === window.fixtureOriginalHeader };
      });
      assert.deepEqual(same, { chart: true, instance: true, chip: true, header: true });
      assert.deepEqual(await snapshot(), expected, id);
      assert.equal(await page.locator('.asset-observation-page [role="tabpanel"]').count(), 1);
      assert.equal(await page.locator('.asset-source-summary').count(), 1);
      assert.equal(await page.locator('.asset-source-summary').evaluate(node => node === window.fixtureOriginalSource && node.open), true);
      assert.equal(await page.locator('[data-asset-topic-slot] .asset-source-summary').count(), 0);
      assert.doesNotMatch(await page.locator('[data-asset-topic-slot]').innerText(), /离线 fixture · 非真实行情；仅用于浏览器合同验证/);
      assert.equal(await page.locator('[data-asset-news-slot]').count(), ['news', 'announcements'].includes(id) ? 1 : 0);
      for (const topic of ['news', 'announcements']) assert.equal(await view(topic).count(), 1);
      if (id === 'holders') {
        assert.match(await page.locator('#shareholder-panel').innerText(), /合成股东甲/);
        assert.match(await page.locator('#shareholder-panel .asset-card-coverage').innerText(), /offline-fixture · 已取得/);
      }
      if (id === 'overview') {
        assert.equal(await page.locator('[data-asset-block-load="history"]').count(), 0);
        assert.match(await page.locator('[data-asset-source-row="history"]').textContent(), /历史行情使用上方图表控件更新/);
      }
      checks.push({ view: id, ...same, ...await snapshot() });
    }
    assert.equal(historyReads(), initialReads, 'Switching topics must not hydrate history again');
    await screenshot('overview-tabs-preserved.png'); return checks;
  });

  await check('tab-keyboard-and-browser-history-use-the-same-panel', async () => {
    await view('overview').focus(); await page.keyboard.press('ArrowRight');
    await page.locator('[data-asset-topic="financials"]').waitFor();
    assert.equal(await view('financials').getAttribute('aria-selected'), 'true');
    assert.equal(await view('financials').evaluate(node => node === document.activeElement), true);
    await page.goBack(); await page.locator('[data-asset-topic="overview"]').waitFor();
    await page.goForward(); await page.locator('[data-asset-topic="financials"]').waitFor();
    assert.equal(await page.evaluate(() => document.querySelector('[data-asset-echarts]') === window.fixtureOriginalChart), true);
    return { back: 'overview', forward: 'financials', chartDomPreserved: true };
  });

  await check('chinese-and-code-search-use-synthetic-candidates', async () => {
    const input = page.locator('#asset-search-input');
    await input.fill('茅台'); await page.locator('[role="option"]').first().waitFor();
    assert.match(await page.locator('[data-asset-search-results]').innerText(), /合成贵州茅台.*600519\.SH/s);
    await screenshot('synthetic-chinese-search.png');
    await input.fill('000001'); await page.locator('[role="option"]').first().waitFor();
    assert.match(await page.locator('[data-asset-search-results]').innerText(), /000001\.SZ/);
    return { chinese: '合成贵州茅台', fullCode: '000001.SZ', provider: 'synthetic-fixture' };
  });

  await check('initials-keyboard-select-creates-new-asset-and-recent-qfq-history', async () => {
    const creates = state.creates;
    await page.locator('#asset-search-input').fill('zycx'); await page.locator('[role="option"]').first().waitFor();
    assert.match(await page.locator('[data-asset-search-results]').innerText(), /合成兆易创新.*603986\.SH/s);
    let topicWhileHistoryRunning;
    state.historyPending = true;
    try {
      const submitted = page.waitForResponse(response => response.url().endsWith('/history-jobs') && response.request().method() === 'POST');
      await page.locator('#asset-search-input').press('ArrowDown'); await page.locator('#asset-search-input').press('Enter');
      await page.waitForFunction(() => document.querySelector('[data-asset-identity]')?.dataset.assetIdentity === 'stock:603986.SH');
      const job = await (await submitted).json(); assert.equal(job.status, 'running');
      await page.waitForFunction(() => document.querySelector('#fin-revenue')?.textContent === '0 元 CNY');
      assert.equal(state.historyPending, true);
      topicWhileHistoryRunning = { historyStatus: job.status, financialRevenue: await page.locator('#fin-revenue').innerText(), name: await page.locator('#asset-name').innerText() };
      await screenshot('synthetic-financials-before-history-completes.png');
    } finally { state.historyPending = false; }
    await stable(); await page.waitForLoadState('networkidle');
    assert.equal(state.creates, creates + 1);
    assert.ok(state.historyStarts.some(job => job.asset === '603986.SH' && job.scope === 'recent' && job.adjustment === 'qfq'));
    assert.match(await page.locator('#asset-name').innerText(), /合成兆易创新/);
    assert.equal(await view('financials').getAttribute('aria-selected'), 'true');
    await screenshot('synthetic-new-asset-created.png');
    return { asset: '603986.SH', creates: state.creates, history: state.historyStarts, preservedTopic: 'financials', topicWhileHistoryRunning };
  });

  await check('search-narrow-dark-layout-has-no-horizontal-overflow', async () => {
    await page.setViewportSize({ width: 390, height: 844 });
    await page.evaluate(() => { document.documentElement.dataset.theme = 'dark'; });
    await page.locator('#asset-search-input').fill('茅台'); await page.locator('[role="option"]').first().waitFor();
    const evidence = await page.evaluate(() => ({ inputHeight: document.querySelector('#asset-search-input').getBoundingClientRect().height, pageWidth: document.documentElement.scrollWidth, viewportWidth: innerWidth, theme: document.documentElement.dataset.theme }));
    assert.ok(evidence.inputHeight >= 44); assert.ok(evidence.pageWidth <= evidence.viewportWidth + 1);
    await screenshot('synthetic-search-390-dark.png'); return evidence;
  });

  await check('synthetic-only-network-and-source-integrity', async () => {
    assert.deepEqual(external, []); assert.deepEqual(errors, []); assert.deepEqual(state.errors, []);
    sourceEvidence = await fixture.verifySourceUnchanged();
    await writeFile(path.join(output, 'source-hashes-after.json'), JSON.stringify(sourceEvidence.migratedSourceHashesAfter, null, 2));
    return { supplierCalls: 0, modelCalls: 0, synthetic: true, ...sourceEvidence };
  });
} catch (error) {
  results.push({ name: 'runner', status: 'FAIL', error: error.message }); console.error(error.stack);
} finally {
  try { if (browser) await browser.close(); } catch (error) { errors.push(`Browser cleanup: ${error.message}`); }
  try { await fixture.close(); } catch (error) { errors.push(`Fixture cleanup: ${error.message}`); }
  const status = results.length && results.every(result => result.status === 'PASS') && !errors.length && state.resources.fixtureServer === 'closed' ? 'PASS' : 'FAIL';
  await writeFile(path.join(output, 'summary.json'), JSON.stringify({ status, synthetic: true, supplierCalls: 0, modelCalls: 0, deliveryTaskId: process.env.RWB_DELIVERY_TASK_ID, nodeVersion: process.version, startedAt, durationMs: Math.round(performance.now() - started), results, errors, external, screenshots, fixtureErrors: state.errors, fixtureResources: state.resources, reads: state.reads, sourceEvidence }, null, 2));
  console.log(`${status}: synthetic asset interactions (${results.filter(result => result.status === 'PASS').length}/${results.length})`);
  if (status !== 'PASS') process.exitCode = 1;
}
