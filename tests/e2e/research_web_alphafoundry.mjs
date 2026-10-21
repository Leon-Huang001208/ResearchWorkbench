/** Real local-vendor browser acceptance against the original AF renderer. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startFixture } from './alphafoundry_fixture.mjs';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.join(project, 'logs/alphafoundry-indicators-20261021', process.env.RWB_ASSET_REAL_PROOF || process.env.RWB_ASSET_READBACK_JSON ? 'real-readback' : '');
await mkdir(output, { recursive: true });
const fixture = await startFixture(project, output);
const { state, origin } = fixture;
await writeFile(path.join(output, 'fixture-input-bars.json'), JSON.stringify(state.rows.history, null, 2));
let browser;
const results = []; const errors = []; const external = []; const screenshots = []; let page;
const diagnosticsEnabled = process.env.RWB_ASSET_DIAGNOSTICS === '1';
const check = async (name, fn) => {
  try { const evidence = await fn(); results.push({ name, status: 'PASS', evidence }); }
  catch (error) {
    const diagnostics = await page?.evaluate(() => {
      const node = document.querySelector('[data-asset-echarts]'); const main = node && window.echarts?.getInstanceByDom(node);
      return { chartErrors: window.fixtureChartErrors || [], calls: window.fixtureChartCalls || [], controls: window.fixtureControlTrace || [], dataset: { ...node?.dataset }, chartId: main?.id, seriesViews: main?.getModel()?.getSeries()?.map(series => ({ name: series.name, type: series.type, view: Boolean(main.getViewOfSeriesModel(series)) })) };
    }).catch(() => null);
    results.push({ name, status: 'FAIL', error: error.message, diagnostics }); console.error(`${name}: ${error.stack}\n${JSON.stringify(diagnostics)}`);
  }
};
const assetURL = (asset = state.observation.asset, view = 'overview') => `${origin}/#/workbench/assets?view=${view}&asset=${encodeURIComponent(asset)}&asset_type=stock`;
const chart = () => page.locator('[data-asset-echarts]');
const value = name => chart().getAttribute(`data-${name}`);
const action = async name => {
  if (!diagnosticsEnabled) return page.locator(`[data-asset-chart-action="${name}"]`).click();
  await page.evaluate(label => { const node = document.querySelector('[data-asset-echarts]'); const main = node && echarts.getInstanceByDom(node); window.fixtureControlTrace ||= []; window.fixtureControlTrace.push({ phase: 'before', label, id: main?.id, models: main?.getModel()?.getSeries().length, views: main?.getModel()?.getSeries().filter(series => main.getViewOfSeriesModel(series)).length }); }, name);
  await page.locator(`[data-asset-chart-action="${name}"]`).click();
  await page.evaluate(label => { const node = document.querySelector('[data-asset-echarts]'); const main = node && echarts.getInstanceByDom(node); window.fixtureControlTrace.push({ phase: 'after', label, id: main?.id, models: main?.getModel()?.getSeries().length, views: main?.getModel()?.getSeries().filter(series => main.getViewOfSeriesModel(series)).length }); }, name);
};
const stable = () => page.waitForFunction(() => { const node = document.querySelector('[data-asset-echarts]'); return node && window.echarts?.getInstanceByDom(node)?.getOption()?.grid?.length === 5 && node.dataset.visibleCount; });
const renderedEvidence = () => page.evaluate(() => {
  const node = document.querySelector('[data-asset-echarts]'); const main = echarts.getInstanceByDom(node); const models = main.getModel().getSeries();
  const views = models.filter(model => main.getViewOfSeriesModel(model)).length;
  if (views !== models.length || !views) throw Error(`Actual chart views missing: ${views}/${models.length}`);
  const index = Number(node.dataset.visibleEnd) - 2;
  const samples = ['K线', '成交量'].map(name => {
    const model = models.find(item => item.name === name); const element = model.getData().getItemGraphicEl(index); const rect = element?.getBoundingRect();
    if (!element || element.ignore || element.invisible || element.__zr !== main.getZr() || !rect || !(rect.width > 0 && rect.height > 0)) throw Error(`Missing actual visible ${name} graphic at ${index}`);
    return { name, type: element.type, width: rect.width, height: rect.height };
  });
  return { models: models.length, views, samples };
});
async function open(width = 1920, theme = 'light', url = assetURL()) {
  const context = await browser.newContext({ viewport: { width, height: 1100 }, colorScheme: theme });
  const next = await context.newPage(); next.setDefaultTimeout(12000);
  next.on('pageerror', error => errors.push({ url: next.url(), message: error.message, stack: error.stack }));
  next.on('console', message => { if (message.type() === 'error') errors.push({ url: next.url(), message: message.text() }); });
  await next.route('**/*', route => { if (new URL(route.request().url()).origin !== origin) { external.push(route.request().url()); return route.abort(); } return route.continue(); });
  await next.addInitScript(() => {
    const Native = window.ResizeObserver; window.fixtureObservers = [];
    window.ResizeObserver = class extends Native { constructor(fn) { super(fn); this.targets = new Set(); window.fixtureObservers.push(this); } observe(target, options) { this.targets.add(target); return super.observe(target, options); } unobserve(target) { this.targets.delete(target); return super.unobserve(target); } disconnect() { this.targets.clear(); return super.disconnect(); } };
  });
  await next.goto(url); return next;
}
async function screenshot(target, name) {
  await target.evaluate((node, saved) => { const title = node.matches('.asset-market-terminal') ? node.querySelector('h2') : null; if (title) title.textContent = `K 线与技术指标 · ${saved ? '真实已存快照离线回读' : '离线 fixture · 非真实行情'}`; }, state.saved);
  const filename = path.join(output, name); await target.screenshot({ path: filename }); screenshots.push(filename); return filename;
}
async function fullCanvasScreenshot(name) {
  const before = await chart().evaluate(node => node.clientWidth);
  await page.evaluate(() => { for (const selector of ['#main', '.asset-observation-main']) { const node = document.querySelector(selector); node.style.width = `${node.getBoundingClientRect().width}px`; node.style.boxSizing = 'border-box'; } });
  await page.addStyleTag({ content: 'html,body{height:auto!important;overflow:visible!important}.app-shell{height:auto!important;grid-template-rows:60px auto!important}#main{height:auto!important;max-height:none!important;overflow:visible!important}' });
  await page.evaluate(() => new Promise(requestAnimationFrame));
  assert.equal(await chart().evaluate(node => node.clientWidth), before, 'Test-only full canvas screenshot CSS must preserve indicator width');
  await screenshot(page.locator('.asset-observation-main'), name);
}
async function equalReferenceCanvas(reference) {
  const migrated = await page.evaluate(() => Object.fromEntries([['observationMain', '.asset-observation-main'], ['terminal', '.asset-market-terminal'], ['layout', '.asset-market-terminal .kline-terminal-layout'], ['indicatorCanvas', '[data-asset-echarts]']].map(([key, selector]) => [key, document.querySelector(selector).getBoundingClientRect().width])));
  await reference.locator('#asset-result').evaluate((node, width) => { node.style.width = `${width}px`; }, migrated.layout);
  const before = await reference.locator('#chart-kline').evaluate(node => node.clientWidth);
  await reference.locator('#asset-result').evaluate((node, delta) => { node.style.width = `${parseFloat(node.style.width) + delta}px`; }, migrated.indicatorCanvas - before);
  await reference.evaluate(() => { for (const id of ['chart-kline', 'chart-chip-dist']) { const node = document.getElementById(id); if (node) echarts.getInstanceByDom(node)?.resize(); } });
  const original = await reference.evaluate(() => ({ result: document.querySelector('#asset-result').getBoundingClientRect().width, layout: document.querySelector('.kline-terminal-layout').getBoundingClientRect().width, indicatorCanvas: document.querySelector('#chart-kline').getBoundingClientRect().width, pageOverflow: document.documentElement.scrollWidth > innerWidth + 1, chipsVisible: getComputedStyle(document.querySelector('.chip-distribution-sidebar')).display !== 'none' }));
  assert.equal(original.indicatorCanvas, migrated.indicatorCanvas, JSON.stringify({ original, migrated }));
  return { original, migrated };
}
try {
  const { chromium } = await import(pathToFileURL(process.env.PLAYWRIGHT_CORE_PATH || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
  browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome' });
  if (state.saved) {
    for (const width of [1920, 390]) await check(`real-snapshot-readback-${width}`, async () => {
      page = await open(width, width === 1920 ? 'light' : 'dark'); await stable();
      const rendered = await renderedEvidence();
      assert.equal(await value('visible-count'), String(Math.min(120, state.rows.history.length)));
      assert.equal(await page.locator('[data-asset-identity]').getAttribute('data-asset-identity'), `stock:${state.observation.asset}`);
      assert.equal(await page.locator('#main').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
      assert.equal(await page.locator('.capital-flow-card').count(), 1); assert.equal(await page.locator('.asset-five-panels .panel-card').count(), 5);
      const before = await value('active-index'); await chart().focus(); await page.keyboard.press('ArrowLeft'); await page.waitForFunction(i => document.querySelector('[data-asset-echarts]').dataset.activeIndex !== i, before);
      await screenshot(page.locator('.asset-market-terminal'), `migrated-real-${width}-terminal.png`); await screenshot(page.locator('.asset-five-panels'), `migrated-real-${width}-cards.png`);
      await fullCanvasScreenshot(`migrated-real-${width}-full.png`);
      const evidence = { rows: state.rows.history.length, identity: state.observation.asset, rendered, quote: await page.locator('#asset-price').innerText(), date: await page.locator('[data-asset-history]').innerText() };
      await page.context().close(); return evidence;
    });
    await check('real-snapshot-offline-health', async () => { assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.equal(state.creates, 0); assert.equal(state.refreshes, 0); });
  } else {
  page = await open(); await stable();
  if (diagnosticsEnabled) await page.evaluate(() => { window.fixtureChartErrors = []; window.fixtureChartCalls = []; const main = echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')); const original = main.setOption.bind(main); main.setOption = (...args) => { const call = { id: main.id, notMerge: args[1], series: Boolean(args[0]?.series), stack: new Error().stack }; window.fixtureChartCalls.push(call); try { const result = original(...args); call.models = main.getModel().getSeries().length; call.views = main.getModel().getSeries().filter(series => main.getViewOfSeriesModel(series)).length; return result; } catch (error) { window.fixtureChartErrors.push({ message: error.message, stack: error.stack, at: { ...main.getDom().dataset } }); throw error; } }; });
  await check('initial-real-charts-and-defaults', async () => {
    await renderedEvidence();
    assert.equal(await value('visible-count'), '120'); assert.equal(await value('visible-start'), String(state.rows.history.length - 120));
    assert.equal(await value('enabled-ma'), '5,10,20,60,120,250');
    assert.equal(await page.locator('[data-asset-chart-action^="ma-"]').count(), 6);
    assert.equal(await page.locator('[data-asset-chart-action="intraday"]').isDisabled(), true); assert.equal(await page.locator('[data-asset-chart-action="multiday"]').isDisabled(), true);
    return page.evaluate(() => { const main = echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')); const chip = echarts.getInstanceByDom(document.querySelector('[data-asset-chip-chart]')); if (!main || !chip) throw Error('Both real chart instances required'); const option = main.getOption(); if (option.grid.length !== 5 || option.xAxis.length !== 5 || option.yAxis.length !== 5) throw Error('Five linked grids required'); for (const n of [5, 10, 20, 60, 120, 250]) { if (option.legend[0].selected[`MA${n}`] !== true || !Number.isFinite(option.series.find(s => s.name === `MA${n}`).data.at(-1)[1])) throw Error(`MA${n} must be enabled and warmed at final bar`); } return { echarts: echarts.version, chartJS: Chart.version, grids: option.grid.length, series: option.series.map(s => s.name) }; });
  });
  await check('chart-height-fills-stage', async () => {
    const sizes = await chart().evaluate(node => ({ chart: node.clientHeight, stage: node.parentElement.clientHeight, layout: node.closest('.kline-terminal-layout').clientHeight, maxHeight: getComputedStyle(node).maxHeight }));
    assert.equal(sizes.chart, sizes.stage, JSON.stringify(sizes)); return sizes;
  });
  await check('human-price-ticks-and-source-units', async () => {
    const labels = await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).getModel().getComponent('yAxis', 0).axis.getViewLabels().map(label => label.formattedLabel));
    assert.ok(labels.length > 1 && labels.every(label => /^-?[\d,]+\.\d{2}$/.test(label)), JSON.stringify(labels));
    const readout = await page.locator('[data-asset-history]').innerText(); assert.doesNotMatch(readout, /\b(?:shares|currency|currency_per_share)\b/); assert.match(readout, /股/); assert.match(readout, /元/);
    return { priceAxisLabels: labels, readout };
  });
  await check('early-preview-1920-original-vs-migrated', async () => {
    await screenshot(page.locator('.asset-market-terminal'), 'migrated-1920-light-terminal.png');
    const reference = await open(1920, 'light', `${origin}/reference/`);
    await reference.waitForFunction(() => window.referenceReady && echarts.getInstanceByDom(document.querySelector('#chart-kline')));
    const widths = await equalReferenceCanvas(reference);
    if (state.referenceIndicatorProvenance) { const nonEmpty = await reference.evaluate(() => { const series = echarts.getInstanceByDom(document.querySelector('#chart-kline')).getOption().series; return ['MACD柱', 'DIF', 'DEA', 'K', 'D', 'J', 'RSI'].every(name => series.find(s => s.name === name)?.data.some(d => Number.isFinite(Array.isArray(d) ? d[1] : d?.value?.[1]))); }); assert.ok(nonEmpty, 'Original backend technical fields must render all original indicator series'); }
    await screenshot(reference.locator('.kline-terminal-layout'), 'reference-1920-light-terminal.png');
    await screenshot(reference.locator('#asset-result'), 'reference-1920-light-cards.png');
    const originalChipStats = await reference.locator('#chip-peak-price,#chip-peak-upper,#chip-peak-lower,#chip-avg-cost,#chip-profit-ratio,#chip-loss-ratio').allTextContents();
    const migratedChipStats = await page.locator('[data-asset-chip-stats] strong').allTextContents();
    assert.deepEqual(migratedChipStats, originalChipStats, 'Default-window chip peak/FWHM/mean/profit/locked must equal actual original renderer');
    await reference.context().close(); return { ...widths, originalChipStats, migratedChipStats };
  });
  await check('complete-original-card-field-contract', async () => {
    for (const selector of ['.asset-basic-card', '.capital-flow-card', '#financial-panel', '#shareholder-panel', '#industry-panel', '#events-panel', '#macro-panel', '[data-asset-personal]', '[data-asset-news-slot]']) assert.equal(await page.locator(selector).count(), 1, selector);
    for (const id of ['asset-name', 'asset-code-display', 'asset-price', 'asset-change', 'asset-change-pct', 'asset-volume', 'asset-amount', 'asset-turnover', 'asset-market-cap', 'asset-high-52w', 'asset-low-52w', 'fin-pe', 'fin-pb', 'fin-roe', 'fin-revenue', 'fin-net-profit', 'fin-gross-margin']) assert.ok((await page.locator(`#${id}`).innerText()).trim(), id);
    assert.match(await page.locator('#asset-market-cap').innerText(), /160,750,000|160750000/);
    assert.match(await page.locator('#fin-revenue').innerText(), /^0/); assert.equal(await page.locator('#fin-net-profit').innerText(), '—');
    assert.match(await page.locator('#shareholder-panel').innerText(), /股东名单未取得/); assert.match(await page.locator('#industry-panel').innerText(), /暂无数据/);
    assert.equal(await page.locator('[data-capital-flow-canvas]').isHidden(), true); assert.match(await page.locator('.capital-flow-card').innerText(), /净额不能/);
    const labels = await page.locator('.asset-observation-main').innerText(); for (const label of ['利率', '通胀', '汇率', '大宗商品', '流动性', '主力流入', '主力流出', '北向资金']) assert.ok(labels.includes(label), label);
  });
  await check('MA-BOLL-bare-period-and-all-controls', async () => {
    await action('ma-250'); await page.waitForFunction(() => !document.querySelector('[data-asset-echarts]').dataset.enabledMa.includes('250'));
    await action('ma-250'); await action('overlay-boll'); await page.waitForFunction(() => document.querySelector('[data-asset-echarts]').dataset.overlay === 'boll');
    assert.ok(await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).getOption().series.some(s => /BOLL/.test(s.name))));
    await action('overlay-none'); await page.waitForFunction(() => document.querySelector('[data-asset-echarts]').dataset.overlay === 'none');
    assert.ok(await page.evaluate(() => Object.entries(echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).getOption().legend[0].selected).every(([, selected]) => selected === false)));
    await action('overlay-ma');
    const counts = {};
    for (const period of ['week', 'month', 'day']) { await action(`period-${period}`); await page.waitForFunction(p => document.querySelector('[data-asset-echarts]').dataset.period === p, period); counts[period] = Number(await value('visible-count')); }
    assert.ok(counts.week < 120 && counts.month < counts.week); assert.equal(counts.day, 120);
    await action('all'); await page.waitForFunction(n => Number(document.querySelector('[data-asset-echarts]').dataset.visibleCount) === n, state.rows.history.length); await action('reset');
    await page.waitForFunction(() => { const node = document.querySelector('[data-asset-echarts]'); const main = echarts.getInstanceByDom(node); return node.dataset.visibleCount === '120' && main.getModel().getSeries().every(series => Boolean(main.getViewOfSeriesModel(series))); }); return counts;
  });
  await check('keyboard-axis-pointer-chips-basic-quote-stability', async () => {
    const quote = await page.locator('#asset-price').innerText(); const before = await value('active-index'); const chipBefore = await page.locator('[data-asset-chip-window]').innerText();
    await chart().focus(); await page.keyboard.press('ArrowLeft'); await page.waitForFunction(i => document.querySelector('[data-asset-echarts]').dataset.activeIndex !== i, before);
    assert.notEqual(await page.locator('[data-asset-chip-window]').innerText(), chipBefore); assert.equal(await page.locator('#asset-price').innerText(), quote);
    await page.evaluate(() => { const main = echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')); const x = main.convertToPixel({ xAxisIndex: 0 }, 250); main.dispatchAction({ type: 'updateAxisPointer', x, y: 120 }); });
    await page.waitForFunction(() => document.querySelector('[data-asset-echarts]').dataset.activeIndex === '250');
    assert.equal(await page.locator('#asset-price').innerText(), quote); await chart().dispatchEvent('pointerleave');
    await page.waitForFunction(() => { const s = document.querySelector('[data-asset-echarts]').dataset; return Number(s.activeIndex) === Number(s.visibleEnd) - 1; });
  });
  await check('native-dataZoom-wheel-drag-and-slider', async () => {
    await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).dispatchAction({ type: 'dataZoom', startValue: 200, endValue: 279 }));
    await page.waitForFunction(() => document.querySelector('[data-asset-echarts]').dataset.visibleCount === '80');
    const box = await chart().boundingBox(); await page.mouse.move(box.x + box.width * .6, box.y + 150); const beforeWheel = await value('visible-count'); await page.mouse.wheel(0, -260);
    await page.waitForFunction(c => document.querySelector('[data-asset-echarts]').dataset.visibleCount !== c, beforeWheel);
    const beforeDrag = await value('visible-start'); await page.mouse.down(); await page.mouse.move(box.x + box.width * .75, box.y + 150, { steps: 12 }); await page.mouse.up();
    await page.waitForFunction(s => document.querySelector('[data-asset-echarts]').dataset.visibleStart !== s, beforeDrag);
    const sliderBefore = await value('visible-count'); const slider = await page.evaluate(() => { const c = echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')); const model = c.getModel().getComponent('dataZoom', 1); const v = c.getViewOfComponentModel(model); const handle = v._displayables.handles[0]; const rect = handle.getBoundingRect().clone(); rect.applyTransform(handle.getComputedTransform()); return { x: rect.x + rect.width / 2, y: rect.y + rect.height / 2, chartHeight: c.getHeight(), domHeight: c.getDom().clientHeight }; });
    // The slider track is the actual native ECharts canvas; drag its left handle.
    const option = await page.evaluate(() => echarts.getInstanceByDom(document.querySelector('[data-asset-echarts]')).getOption().dataZoom[1]);
    const handleX = box.x + slider.x; const handleY = box.y + slider.y;
    await page.mouse.move(handleX, handleY); await page.mouse.down(); await page.mouse.move(handleX + 40, handleY, { steps: 12 }); await page.mouse.up();
    await page.waitForFunction(c => document.querySelector('[data-asset-echarts]').dataset.visibleCount !== c, sliderBefore);
    await action('reset'); return { slider, option };
  });
  await check('anchors-preserve-chart-refresh-personal-and-news', async () => {
    for (const view of ['financials', 'capital', 'holders', 'news']) { const handle = await chart().elementHandle(); await page.locator(`.asset-topic-tabs a[href*="view=${view}"]`).click(); await stable(); assert.ok(await handle.evaluate(node => node.isConnected ? Boolean(echarts.getInstanceByDom(node)) : !echarts.getInstanceByDom(node))); assert.equal(await chart().count(), 1); }
    await page.locator('[data-asset-block-refresh="financials"]').click(); await page.waitForFunction(() => { const button = document.querySelector('[data-asset-block-refresh="financials"]'); return button && !button.disabled; }); assert.equal(state.refreshes, 1);
    await page.locator('[data-asset-personal] > summary').click(); await page.locator('[data-asset-note] textarea').fill('隔离测试保留笔记');
    await page.locator('.asset-news-row').first().waitFor(); assert.equal(await page.locator('[data-asset-note] textarea').inputValue(), '隔离测试保留笔记');
    await page.locator('[data-asset-news-select="1"]').focus(); await page.keyboard.press('Enter'); assert.ok(await page.locator('[data-asset-news-select="1"]').evaluate(node => document.activeElement === node));
    await page.locator('[data-asset-news-more]').click(); assert.equal(await page.locator('.asset-news-row').count(), 25); assert.ok(await page.locator('[data-asset-news-select="20"]').evaluate(node => document.activeElement === node));
    assert.match(await page.locator('.asset-reading-text').innerText(), /<script>/); assert.equal(await page.locator('.asset-news-reader script').count(), 0);
  });
  await check('rapid-A-to-B-late-A-and-create-idempotency', async () => {
    state.late = true; await page.goto(assetURL('600519.SH', 'news')); await page.locator('[data-asset-news-refresh]').click();
    await page.locator('[data-asset-select] input').fill('603986.SH'); await page.locator('[data-asset-select] button').first().click(); await page.waitForFunction(() => document.querySelector('[data-asset-identity]')?.dataset.assetIdentity === 'stock:603986.SH');
    await page.waitForFunction(() => document.querySelector('.asset-news-row')?.textContent.includes('603986')); await page.waitForTimeout(850); assert.doesNotMatch(await page.locator('.asset-news-workspace').innerText(), /600519/); assert.doesNotMatch(await page.locator('.asset-basic-card').innerText(), /离线测试资产 A/);
    await page.locator('.asset-query-controls > summary').click(); await page.locator('[data-asset-observation] [name="asset"]').fill('000001.SZ'); await page.locator('[data-asset-observation] button').click(); await page.waitForFunction(() => document.querySelector('[data-asset-identity]')?.dataset.assetIdentity === 'stock:000001.SZ'); assert.equal(state.creates, 1);
    await page.waitForFunction(() => document.querySelector('.asset-news-row')?.textContent.includes('000001')); assert.doesNotMatch(await page.locator('.asset-news-workspace').innerText(), /603986/); state.late = false;
  });
  await check('route-leave-disposes-instances-and-DOM-observers', async () => {
    await page.goto(assetURL()); await stable(); await page.evaluate(() => { window.retiredCharts = [...document.querySelectorAll('[data-asset-echarts],[data-asset-chip-chart]')]; window.retiredObservers = window.fixtureObservers.filter(o => [...o.targets].some(n => window.retiredCharts.includes(n))); });
    await page.evaluate(() => { location.hash = '#/settings'; }); await page.waitForFunction(() => !document.querySelector('[data-asset-echarts]'));
    assert.ok(await page.evaluate(() => retiredCharts.every(node => !echarts.getInstanceByDom(node)))); assert.ok(await page.evaluate(() => retiredObservers.length > 0 && retiredObservers.every(o => o.targets.size === 0)));
    await page.goto(assetURL()); await stable();
  });
  await page.context().close();
  for (const theme of ['light', 'dark']) for (const width of [1920, 1440, 1180, 900, 390]) await check(`responsive-${width}-${theme}`, async () => {
    page = await open(width, theme); await stable();
    await renderedEvidence();
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), true);
    assert.equal(await page.locator('#main').evaluate(node => node.scrollWidth <= node.clientWidth + 1), true);
    const chip = await page.locator('.asset-chip-panel').boundingBox(); const main = await chart().boundingBox(); if (width <= 900) assert.ok(chip.y >= main.y + main.height - 1, JSON.stringify({ chip, main }));
    await screenshot(page.locator('.asset-market-terminal'), `migrated-${width}-${theme}-terminal.png`);
    await screenshot(page.locator('.asset-basic-card'), `migrated-${width}-${theme}-basic.png`);
    await screenshot(page.locator('.capital-flow-card'), `migrated-${width}-${theme}-capital.png`);
    await screenshot(page.locator('.asset-five-panels'), `migrated-${width}-${theme}-cards.png`);
    const ref = await open(width, theme, `${origin}/reference/`); await ref.waitForFunction(() => window.referenceReady); const widths = await equalReferenceCanvas(ref); await screenshot(ref.locator('.kline-terminal-layout'), `reference-${width}-${theme}-terminal.png`); await screenshot(ref.locator('#asset-result'), `reference-${width}-${theme}-cards.png`); await ref.context().close();
    if ((width === 1920 && theme === 'light') || (width === 390 && theme === 'dark')) await fullCanvasScreenshot(`migrated-${width}-${theme}-full.png`);
    await page.context().close();
    return widths;
  });
  for (const mode of ['partial', 'empty']) await check(`${mode}-snapshot-honesty`, async () => {
    state.mode = mode; page = await open();
    if (mode === 'partial') { await stable(); assert.match(await page.locator('#financial-panel').innerText(), /fixture_partial_snapshot/); assert.match(await page.locator('#fin-revenue').innerText(), /^0/); }
    else { await page.locator('[data-asset-echarts]').waitFor(); assert.equal(await page.locator('[data-asset-echarts]').evaluate(node => Boolean(echarts.getInstanceByDom(node))), false); assert.equal(await page.locator('[data-asset-echarts]').getAttribute('data-visible-count'), '0'); }
    await screenshot(page.locator('.asset-market-terminal'), `migrated-${mode}.png`); await page.context().close(); state.mode = 'normal';
  });
  await check('offline-CSP-and-console-health', async () => { assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(state.errors, []); assert.ok(!state.reads.some(r => /POST.*(?:sessions|research-runs)|\/artifacts/.test(r))); });
  }
} catch (error) { results.push({ name: 'runner', status: 'FAIL', error: error.stack }); console.error(error.stack); }
finally {
  await check('product-source-unchanged-during-browser-run', () => fixture.verifySourceUnchanged());
  const status = results.every(item => item.status === 'PASS') ? 'PASS' : 'FAIL';
  await writeFile(path.join(output, 'summary.json'), JSON.stringify({ status, fixture: !state.saved, savedReadback: state.saved, modelCalls: 0, supplierCalls: 0, originalSourceHashes: state.hashes, migratedSourceHashes: state.migratedSourceHashes, referenceIndicatorProvenance: state.referenceIndicatorProvenance || { status: 'MISSING', note: 'Original backend indicator golden not provided; original JS main MA fallback remains authentic.' }, results, errors, external, screenshots, reads: state.reads }, null, 2));
  console.log(JSON.stringify({ status, passed: results.filter(r => r.status === 'PASS').length, failed: results.filter(r => r.status === 'FAIL').map(r => ({ name: r.name, error: r.error })), output }));
  try { await browser?.close(); } finally { await fixture.close(); } if (status === 'FAIL') process.exitCode = 1;
}
