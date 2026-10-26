/** Browser acceptance: actual product UI + isolated real frozen snapshots. */
import assert from 'node:assert/strict';
import path from 'node:path';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { startWindFixture } from './wind_workspace_fixture.mjs';

const project = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const output = path.resolve(process.env.RWB_WIND_OUTPUT || path.join(project, 'logs/wind-browser'));
await mkdir(output, { recursive: true });
const fixture = await startWindFixture(project, output);
const { state, origin } = fixture;
const { chromium } = await import(pathToFileURL(process.env.RWB_PLAYWRIGHT_MODULE || '/Users/leon/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright-core/index.mjs').href);
const browser = await chromium.launch({ executablePath: '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', headless: true, args: ['--disable-background-networking'] });
const results = []; const errors = []; const external = []; const screenshots = [];
let page;
const chart = () => page.locator('[data-asset-echarts]');
const action = name => page.locator(`[data-asset-chart-action="${name}"]`).click();
const addPanel = async id => {
  const details = page.locator('[data-asset-panel-choices]').locator('..');
  if (await details.getAttribute('open') === null) await details.locator('summary').click();
  await action(`panel-add-${id}`); await stable();
};
const stateOfChart = () => chart().evaluate(node => ({ ...node.dataset }));
const stable = async () => {
  await page.waitForFunction(() => {
    const node = document.querySelector('[data-asset-echarts]');
    const main = node && window.echarts?.getInstanceByDom(node);
    return node?.dataset.visibleCount && main?.getModel()?.getSeries()?.length && main.getOption().grid?.length === 1 + node.dataset.panels.split(',').filter(Boolean).length;
  });
  await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
};
const stats = () => page.locator('[data-asset-chip-stats]').innerText();
const check = async (name, fn) => {
  const started = performance.now();
  try { const evidence = await fn(); results.push({ name, status: 'PASS', milliseconds: Math.round(performance.now() - started), evidence }); }
  catch (error) { results.push({ name, status: 'FAIL', milliseconds: Math.round(performance.now() - started), error: error.message }); console.error(name, error.message); }
};
async function open(width = 1864, theme = 'dark', asset = '603986.SH') {
  const context = await browser.newContext({ viewport: { width, height: 1080 }, colorScheme: theme });
  const next = await context.newPage(); next.setDefaultTimeout(15000);
  next.on('pageerror', error => errors.push({ url: next.url(), type: 'pageerror', message: error.message }));
  next.on('console', message => { if (message.type() === 'error') errors.push({ url: next.url(), type: 'console', message: message.text() }); });
  await next.route('**/*', route => { if (new URL(route.request().url()).origin !== origin) { external.push(route.request().url()); return route.abort(); } return route.continue(); });
  await next.goto(`${origin}/#/assets?asset=${asset}&asset_type=stock&view=overview`);
  page = next;
  // This suite owns K-line acceptance; the new default intraday has its own suite.
  await page.locator('[data-asset-chart-action="period-day"]').click();
  try { await stable(); }
  catch (error) {
    await writeFile(path.join(output, 'startup-diagnostics.json'), JSON.stringify(await page.evaluate(() => ({ text: document.body.innerText, chart: { ...document.querySelector('[data-asset-echarts]')?.dataset }, echarts: Boolean(window.echarts), chartOptions: window.echarts?.getInstanceByDom(document.querySelector('[data-asset-echarts]'))?.getOption()?.grid?.length })), null, 2));
    await screenshot('startup-failure.png'); throw error;
  }
  return next;
}
async function screenshot(name) {
  const target = path.join(output, name); await page.screenshot({ path: target, fullPage: false }); screenshots.push(target); return target;
}
async function alignment() {
  const values = await page.evaluate(() => {
    const node = document.querySelector('[data-asset-echarts]'); const chipNode = document.querySelector('[data-asset-chip-chart]');
    const main = echarts.getInstanceByDom(node); const chip = echarts.getInstanceByDom(chipNode);
    const axis = main.getOption().yAxis[0]; const lo = axis.min; const hi = axis.max;
    const mr = node.getBoundingClientRect(); const cr = chipNode.getBoundingClientRect();
    return [lo, (lo + hi) / 2, hi].map(price => ({ price, mainY: mr.top + main.convertToPixel({ yAxisIndex: 0 }, price), chipY: cr.top + chip.convertToPixel({ yAxisIndex: 0 }, price) }));
  });
  assert.ok(values.every(value => Number.isFinite(value.mainY) && Math.abs(value.mainY - value.chipY) <= 1), JSON.stringify(values));
  return values;
}
async function themeEvidence(theme) {
  await page.evaluate(value => window.ResearchWebTheme.controller.setPreference(value), theme);
  await stable();
  const evidence = await page.evaluate(() => {
    const mainNode = document.querySelector('[data-asset-echarts]'); const chipNode = document.querySelector('[data-asset-chip-chart]');
    const main = echarts.getInstanceByDom(mainNode); const chip = echarts.getInstanceByDom(chipNode); const o = main.getOption(); const c = chip.getOption();
    const selectors = ['.kline-terminal-layout', '.asset-kline-stage', '[data-asset-echarts]', '.asset-chip-panel', '[data-asset-chip-chart]', '.asset-history-readout'];
    return { theme: document.documentElement.dataset.theme, main: o.backgroundColor, chips: c.backgroundColor, backgrounds: selectors.map(selector => ({ selector, background: getComputedStyle(document.querySelector(selector)).backgroundColor })), series: main.getModel().getSeries().length, views: main.getModel().getSeries().filter(model => main.getViewOfSeriesModel(model)).length, axis: o.yAxis[0].axisLabel.color, chipAxis: c.yAxis[0].axisLabel.color };
  });
  assert.equal(evidence.theme, theme); assert.equal(evidence.main, 'transparent'); assert.equal(evidence.chips, 'transparent');
  assert.ok(evidence.backgrounds.every(item => ['transparent', 'rgba(0, 0, 0, 0)'].includes(item.background)), JSON.stringify(evidence.backgrounds));
  assert.ok(evidence.series > 0 && evidence.series === evidence.views); assert.equal(evidence.axis, evidence.chipAxis);
  return evidence;
}

try {
  await check('preview HTTP method whitelist rejects every non-simulated write', async () => {
    const before = JSON.stringify([...state.current]); const preferences = [...state.preferences];
    const rejected = [];
    for (const [method, route] of [['POST', '/assets/observations'], ['POST', '/watchlists'], ['DELETE', '/assets/chart-preferences'], ['POST', '/sessions'], ['PUT', '/assets/observations']]) {
      const response = await fetch(`${origin}/api/research${route}`, { method, headers: { 'Content-Type': 'application/json' }, ...(['POST', 'PUT'].includes(method) ? { body: '{}' } : {}) });
      assert.equal(response.status, 403); assert.equal((await response.json()).code, 'isolated_preview_read_only'); rejected.push({ method, route, status:response.status });
    }
    assert.equal(JSON.stringify([...state.current]), before); assert.deepEqual(state.preferences, preferences);
    const oid = state.current.get('603986.SH').id; const route = `${origin}/api/research/assets/observations/${oid}/history-jobs`;
    const created = await fetch(route, { method: 'POST', headers: { 'Content-Type':'application/json', 'Idempotency-Key':'preview-http-guard-check' }, body: JSON.stringify({ scope:'recent', adjustment:'qfq' }) });
    assert.equal(created.status, 202); const job = await created.json();
    const getCancel = await fetch(`${route}/${job.id}/cancel`); assert.equal(getCancel.status, 405); assert.equal(state.jobs.get(job.id).state, 'running');
    const cancelled = await fetch(`${route}/${job.id}/cancel`, { method:'POST', headers:{ 'Content-Type':'application/json' }, body:'{}' }); assert.equal(cancelled.status, 200); assert.equal((await cancelled.json()).state, 'cancelled');
    const saved = await fetch(`${origin}/api/research/assets/chart-preferences`, { method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({panels:preferences}) }); assert.equal(saved.status,200);
    state.jobs.delete(job.id); return { rejected, getCancelStatus:getCancel.status, allowedInMemoryOnly:['PUT chart-preferences','POST history-jobs','POST history-jobs/id/cancel'], noObservationChange:JSON.stringify([...state.current])===before };
  });
  await open();
  await check('desktop formal Wind workspace preserves compact structure and all fields', async () => {
    const evidence = await page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height }; };
      return { identity: rect('.asset-identity'), grid: rect('.asset-wind-grid'), market: rect('.asset-market-full'), chip: rect('.asset-chip-panel'), metrics: rect('.asset-wind-metrics'), headings: [...document.querySelectorAll('.asset-wind-metrics dt')].map(node => node.textContent), overflow: document.documentElement.scrollWidth > innerWidth + 1, nameFont: getComputedStyle(document.querySelector('#asset-name')).fontSize, priceFont: getComputedStyle(document.querySelector('#asset-price')).fontSize, blankWatchlistColumn: getComputedStyle(document.querySelector('.asset-observation-page')).gridTemplateColumns };
    });
    assert.ok(!evidence.overflow); assert.ok(Math.abs(evidence.chip.width - 200) < 2); assert.ok(Math.abs(evidence.metrics.width - 260) < 2);
    assert.equal(evidence.nameFont, '18px'); assert.equal(evidence.priceFont, '24px');
    assert.ok(evidence.identity.height < 90, JSON.stringify(evidence.identity));
    for (const label of ['开盘', '最高', '最低', '换手率', '成交量', '成交额', '区间最高', '区间最低', 'PE-TTM', 'PB', 'PS-TTM', '总股本', '市值']) assert.ok(evidence.headings.includes(label), label);
    assert.equal(await page.getByText('MARKET TERMINAL', { exact: true }).count(), 0);
    assert.equal(await page.locator('.asset-watch-rail').isVisible(), false);
    await screenshot('desktop-dark.png'); return evidence;
  });
  await check('default VOL+MACD and real 2261-row canonical data actually draw', async () => {
    const s = await stateOfChart(); assert.equal(s.panels, 'volume,macd'); assert.equal(s.adjustment, 'qfq'); assert.equal(Number(s.visibleCount), 120);
    const evidence = await chart().evaluate(node => {
      const main = echarts.getInstanceByDom(node); const series = main.getModel().getSeries();
      const k = series.find(model => model.subType === 'candlestick');
      const index = k.getData().indexOfRawIndex(+node.dataset.visibleEnd - 2); const element = k.getData().getItemGraphicEl(index); const rect = element?.getBoundingRect();
      const largePaths = []; main.getViewOfSeriesModel(k).group.traverse(item => { const r = item.getBoundingRect?.(); if (item.type === 'largeCandlestickBox' && item.__zr === main.getZr() && !item.ignore && !item.invisible && r.width > 0 && r.height > 0) largePaths.push({ type:item.type, points:item.shape.points.length, width:r.width, height:r.height }); });
      return { rows: main.getOption().series.find(series => series.type === 'candlestick').data.length, filteredCount:k.getData().count(), filteredIndex:index, grids: main.getOption().grid.length, large:k.get('large'), largePaths, graphic: { inRenderer: element?.__zr === main.getZr(), width: rect?.width, height: rect?.height }, date: node.dataset.selectedDate };
    });
    assert.equal(evidence.rows, 2261); assert.equal(evidence.grids, 3); assert.ok(evidence.large ? evidence.largePaths.length > 0 && evidence.largePaths.every(item => item.points >= 2261 * 4) : evidence.graphic.inRenderer && evidence.graphic.width > 0 && evidence.graphic.height > 0, JSON.stringify(evidence)); return evidence;
  });
  await check('add all four panels then remove all and persist account choice', async () => {
    await addPanel('kdj'); await addPanel('rsi');
    assert.equal((await stateOfChart()).panels, 'volume,macd,kdj,rsi');
    for (const id of ['volume', 'macd', 'kdj', 'rsi']) { await action(`panel-remove-${id}`); await stable(); }
    assert.equal((await stateOfChart()).panels, '');
    await page.waitForFunction(() => document.querySelector('[data-asset-echarts]')?.dataset.panels === '');
    for (const id of ['volume', 'macd']) await addPanel(id);
    await page.waitForTimeout(100); assert.deepEqual(state.preferences, ['volume', 'macd']); return { writes: state.preferenceWrites };
  });
  await check('actual pointer and keyboard select a shared historical date', async () => {
    const point = await chart().evaluate(node => {
      const main = echarts.getInstanceByDom(node); const index = +node.dataset.visibleEnd - 30;
      const rect = node.getBoundingClientRect(); const grid = main.getModel().getComponent('grid', 0).coordinateSystem.getRect();
      return { x:rect.left + main.convertToPixel({ xAxisIndex:0 }, index), y:rect.top + grid.y + grid.height / 2, date:main.getOption().xAxis[0].data[index] };
    });
    await page.mouse.move(point.x, point.y); await page.mouse.click(point.x, point.y); await stable();
    assert.equal((await stateOfChart()).selectedDate, point.date);
    assert.equal(await page.locator('[data-asset-selected-date]').inputValue(), point.date);
    const snapshot = state.current.get('603986.SH'); const row = state.rows[snapshot.blocks.history.dataset.dataset_id].find(item => item.date === point.date);
    assert.ok((await page.locator('[data-asset-history]').innerText()).includes(row.close.toFixed(2)));
    const before = await stateOfChart(); await chart().focus(); await page.keyboard.press('ArrowLeft'); await stable();
    assert.notEqual((await stateOfChart()).selectedDate, before.selectedDate);
    const keyboardDate = (await stateOfChart()).selectedDate;
    const links = await chart().evaluate(node => echarts.getInstanceByDom(node).getOption().axisPointer[0].link);
    assert.equal(links[0].xAxisIndex, 'all'); await action('latest'); await stable();
    return { pointerDate:point.date, keyboardDate, axisLinks:links };
  });
  await check('selected day remains while entering chips, zooming, panning and changing periods', async () => {
    const input = page.locator('[data-asset-selected-date]'); await input.fill('2026-06-30'); await input.press('Tab'); await stable();
    const selected = await stateOfChart(); const before = await stats(); assert.equal(selected.selectedDate, '2026-06-30');
    await page.locator('[data-asset-chip-chart]').hover(); assert.equal((await stateOfChart()).selectedDate, selected.selectedDate);
    await action('zoom-in'); await stable(); assert.equal(await stats(), before);
    await action('pan-back'); await stable(); assert.equal(await stats(), before);
    for (const period of ['week', 'month', 'day']) { await action(`period-${period}`); await stable(); assert.equal((await stateOfChart()).selectedDate, selected.selectedDate); assert.equal(await stats(), before); }
    await action('latest'); await stable(); assert.equal((await stateOfChart()).selectedDate, '2026-10-21'); assert.equal(+(await stateOfChart()).visibleCount, 120);
    assert.notEqual(await stats(), before); return { selected: selected.selectedDate, restored: (await stateOfChart()).selectedDate, stableChipStats: before };
  });
  await check('six MA toggles BOLL naked candles wheel drag and linked slider', async () => {
    await page.locator('.asset-overlay-controls details > summary').click();
    assert.equal((await stateOfChart()).enabledMa, '5,10,20,60,120,250');
    for (const n of [5,10,20,60,120,250]) await action(`ma-${n}`);
    assert.equal((await stateOfChart()).enabledMa, '');
    for (const n of [5,10,20,60,120,250]) await action(`ma-${n}`);
    await page.locator('.asset-overlay-controls details > summary').click();
    for (const overlay of ['boll','none','ma']) { await action(`overlay-${overlay}`); await stable(); assert.equal((await stateOfChart()).overlay, overlay); }
    const before = await stateOfChart(); const bounds = await chart().boundingBox();
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + 100); await page.mouse.wheel(0, -240); await page.waitForTimeout(150); await stable();
    const wheel = await stateOfChart(); assert.notEqual(wheel.visibleCount, before.visibleCount);
    await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + 150); await page.mouse.down(); await page.mouse.move(bounds.x + bounds.width / 2 + 90, bounds.y + 150, { steps: 6 }); await page.mouse.up(); await stable();
    const dragged = await stateOfChart(); assert.notEqual(dragged.visibleStart, wheel.visibleStart);
    const range = await chart().evaluate(node => { const main = echarts.getInstanceByDom(node); const start = +node.dataset.visibleStart + 2; const end = +node.dataset.visibleEnd - 3; main.dispatchAction({ type: 'dataZoom', dataZoomIndex: 1, startValue: start, endValue: end }); return { start, end }; });
    await stable(); const slider = await stateOfChart(); assert.equal(+slider.visibleStart, range.start); assert.equal(+slider.visibleEnd, range.end + 1);
    await action('latest'); return { before, wheel, dragged, slider };
  });
  await check('desktop chips align actual price coordinate within 1px', alignment);
  await check('dark and light charts use transparent surfaces and live theme axes', async () => ({ dark: await themeEvidence('dark'), light: await themeEvidence('light') }));
  await check('source disclosure is lazy and all research regions remain', async () => {
    const source = page.locator('details.asset-source-summary'); assert.equal(await source.getAttribute('open'), null);
    const before = state.reads.length; await source.locator(':scope > summary').click(); await page.waitForTimeout(80); assert.equal(state.reads.length, before);
    assert.equal(await source.locator('[data-asset-source-row]').count(), 8);
    const text = await page.locator('.asset-observation-page').innerText();
    for (const label of ['财务', '股东', '行业', '事件', '宏观', '新闻与公告', '个人研究', '两融']) assert.ok(text.includes(label), label);
    await source.locator(':scope > summary').click(); return { rows: 8, noExtraQuery: true };
  });
  await check('real frozen three-adjustment versions switch atomically', async () => {
    const evidence = [];
    for (const adjustment of ['none', 'hfq', 'qfq']) {
      await page.locator('[data-asset-chart-adjustment]').selectOption(adjustment);
      await page.waitForFunction(expected => document.querySelector('[data-asset-echarts]')?.dataset.adjustment === expected && !document.querySelector('[data-asset-chart-adjustment]').disabled, adjustment, { timeout: 25000 }); await stable();
      const expected = state.versions.find(v => v.asset === '603986.SH' && v.adjustment === adjustment); const data = state.rows[expected.observation.blocks.history.dataset.dataset_id];
      const rendered = await chart().evaluate(node => { const main = echarts.getInstanceByDom(node); const k = main.getOption().series.find(series => series.type === 'candlestick'); return { adjustment: node.dataset.adjustment, rows: k.data.length, first: k.data[0], last: k.data.at(-1) }; });
      assert.equal(rendered.rows, data.length); assert.equal(rendered.first[0], data[0].open); assert.equal(rendered.last[1], data.at(-1).close); evidence.push(rendered);
    }
    return { note: 'Polling is an isolated API fixture; all OHLC inputs and immutable metadata are real saved snapshots.', versions: evidence };
  });
  await check('6025 real rows fully paginate and all-history chart exceeds5000', async () => {
    await page.goto(`${origin}/#/assets?asset=600519.SH&asset_type=stock&view=overview`); await stable(); await action('all'); await stable();
    const evidence = await chart().evaluate(node => ({ ...node.dataset, rows: echarts.getInstanceByDom(node).getOption().series.find(series => series.type === 'candlestick').data.length }));
    assert.equal(evidence.rows, 6025); assert.equal(+evidence.visibleCount, 6025);
    assert.ok(state.reads.some(read => read.path.includes('/datasets/') && /offset=6000/.test(read.search))); await screenshot('all-history-6025-light.png'); return evidence;
  });
  await check('medium hides metrics into a working drawer and retains price alignment', async () => {
    await page.setViewportSize({ width: 1200, height: 1000 }); await stable();
    assert.equal(await page.locator('.asset-wind-metrics').isVisible(), false); await page.locator('[data-asset-metrics-toggle]').click();
    assert.equal(await page.locator('.asset-wind-metrics').isVisible(), true); await page.locator('[data-asset-metrics-close]').click();
    await action('latest'); await stable(); const values = await alignment(); await screenshot('medium-light.png'); return values;
  });
  await check('mobile stacks chips preserves all panels and has44px touch controls', async () => {
    await page.setViewportSize({ width: 430, height: 1000 }); await stable();
    await addPanel('kdj'); await addPanel('rsi');
    assert.equal((await stateOfChart()).panels, 'volume,macd,kdj,rsi');
    const evidence = await page.evaluate(() => {
      const chart = document.querySelector('[data-asset-echarts]').getBoundingClientRect(); const chips = document.querySelector('.asset-chip-panel').getBoundingClientRect();
      return { chart: { top: chart.top, bottom: chart.bottom }, chips: { top: chips.top, bottom: chips.bottom }, overflow: document.documentElement.scrollWidth > innerWidth + 1, controls: [...document.querySelectorAll('.asset-market-terminal button,.asset-market-terminal select,.asset-market-terminal input,.asset-market-terminal summary')].filter(node => node.getClientRects().length && !node.hidden).map(node => { const r=node.getBoundingClientRect(); return { text: node.textContent.trim() || node.getAttribute('aria-label'), width:r.width,height:r.height }; }) };
    });
    assert.ok(evidence.chips.top >= evidence.chart.bottom); assert.equal(evidence.overflow, false);
    assert.ok(evidence.controls.every(control => control.width >= 44 && control.height >= 44), JSON.stringify(evidence.controls.filter(control=>control.width<44||control.height<44)));
    await screenshot('mobile-light.png'); return evidence;
  });
  await check('legacy ten-row snapshot stays readable without claimed full history', async () => {
    const original = structuredClone(state.current.get('603986.SH')); const legacy = structuredClone(original); const dataset = legacy.blocks.history.dataset;
    const id = 'legacy-ten-frozen'; state.rows[id] = state.rows[dataset.dataset_id].slice(-10); dataset.dataset_id = id; dataset.row_count = 10; delete dataset.asset_history; delete legacy.history_job; legacy.dataset_ids = [id];
    state.current.set('603986.SH', legacy); await page.goto(`${origin}/#/assets?asset=603986.SH&asset_type=stock&view=overview`); await stable();
    const evidence = await stateOfChart(); assert.equal(+evidence.visibleCount, 10); assert.equal(await page.locator('[data-asset-chart-action="all"]').innerText(), '全历史');
    state.current.set('603986.SH', original); return evidence;
  });
  await check('legacy first left-load builds recent canonical before any older extension', async () => {
    assert.ok(state.partialVersions.length, 'RWB_WIND_PARTIAL_PROOF must provide a verified real intermediate canonical snapshot');
    const original = structuredClone(state.current.get('603986.SH')); const legacy = structuredClone(original); const dataset = legacy.blocks.history.dataset;
    const id = 'legacy-ten-first-left'; state.rows[id] = state.rows[dataset.dataset_id].slice(-10); dataset.dataset_id = id; dataset.row_count = 10; delete dataset.asset_history; delete legacy.history_job; legacy.dataset_ids = [id];
    state.current.set('603986.SH', legacy); state.usePartialForRecent = true;
    await page.goto(`${origin}/#/assets?asset=603986.SH&asset_type=stock&view=overview`); await stable();
    const firstPost = page.waitForRequest(request => request.method() === 'POST' && /\/history-jobs$/.test(new URL(request.url()).pathname));
    await action('pan-back'); const first = JSON.parse((await firstPost).postData()); assert.equal(first.scope, 'recent');
    const partial = state.partialVersions.find(version => version.asset === '603986.SH' && version.adjustment === first.adjustment); assert.ok(partial);
    const partialDataset = partial.observation.blocks.history.dataset;
    await page.waitForFunction(expected => { const node=document.querySelector('[data-asset-echarts]'); const main=node && echarts.getInstanceByDom(node); return main?.getOption()?.series?.find(series=>series.type==='candlestick')?.data.length===expected && document.querySelector('[data-asset-chart-adjustment]')?.disabled===false; }, partialDataset.row_count, {timeout:25000}); await stable();
    assert.ok(state.current.get('603986.SH').blocks.history.dataset.asset_history.canonical_version);
    assert.equal(partialDataset.asset_history.coverage.full_history, false);
    await chart().evaluate(node => echarts.getInstanceByDom(node).dispatchAction({ type:'dataZoom', dataZoomIndex:1, startValue:1, endValue:120 })); await stable();
    const secondPost = page.waitForRequest(request => request.method() === 'POST' && /\/history-jobs$/.test(new URL(request.url()).pathname));
    await action('pan-back'); const second = JSON.parse((await secondPost).postData()); assert.equal(second.scope, 'older'); assert.equal(second.adjustment, first.adjustment);
    await page.waitForFunction(expected => { const node=document.querySelector('[data-asset-echarts]'); const main=node && echarts.getInstanceByDom(node); return main?.getOption()?.series?.find(series=>series.type==='candlestick')?.data.length===expected && document.querySelector('[data-asset-chart-adjustment]')?.disabled===false; }, original.blocks.history.dataset.row_count, {timeout:25000}); await stable();
    state.usePartialForRecent=false; state.current.set('603986.SH', original);
    return { firstPost:first, secondPost:second, intermediateRows:partialDataset.row_count, finalRows:original.blocks.history.dataset.row_count, intermediateProvenance:state.partialProvenance, note:'HTTP job transitions are in-memory only; intermediate and complete canonical inputs are verified actual saved snapshots.' };
  });
  await check('no browser/server errors no outside requests and exact source hashes', async () => {
    const handoffs = page.locator('[data-workbench-handoff]');
    assert.equal(await handoffs.count(), 2);
    for (const button of await handoffs.all()) { assert.ok(await button.isDisabled()); assert.match(await button.getAttribute('title'), /隔离预览/); }
    assert.deepEqual(errors, []); assert.deepEqual(external, []); assert.deepEqual(state.errors, []); return { errors, external, supplierCalls: 0, modelCalls: 0, sourceHashes: await fixture.verifySourceUnchanged() };
  });
} finally {
  await writeFile(path.join(output, 'report.json'), JSON.stringify({ startedAt: new Date().toISOString(), origin, proofPath: state.proofPath, partialProofPath:state.partialProofPath, results, errors, external, serverErrors: state.errors, screenshots, requests: state.reads, historyRequests:state.historyRequests, sourceHashes: state.hashes, actualSupplierModelRequestsInBrowser: 0, isolation: 'real frozen OHLC snapshots; API job transitions and preference writes are in-memory fixture only' }, null, 2));
  await browser.close(); await fixture.close();
}
const failed = results.filter(result => result.status === 'FAIL');
console.log(JSON.stringify({ passed: results.length - failed.length, failed: failed.length, failures: failed.map(result => ({ name: result.name, error: result.error })), report: path.join(output, 'report.json') }));
process.exitCode = failed.length ? 1 : 0;
