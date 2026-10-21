import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { enrichMarketBars, renderMarketTerminal, createAssetChartController, buildMarketChartOption, buildChipChartOption } from '../../app/research_web/ui/asset-chart.mjs';
import { aggregateMarketBars, estimateChipDistribution } from '../../app/research_web/ui/asset-indicators.mjs';

const day = i => new Date(Date.UTC(2025, 0, i + 1)).toISOString().slice(0, 10);
const rows = (n, value = i => 100 + i) => Array.from({ length: n }, (_, i) => ({ date: day(i), open: value(i) - .2, high: value(i) + 1, low: value(i) - 1, close: value(i), volume: 1000 + i, amount: 100000 + i, turnover_rate_pct: 2 }));
const near = (a, b, tolerance = 1e-8) => assert.ok(Math.abs(a - b) < tolerance, `${a} should equal ${b}`);
const click = action => ({ type: 'click', target: { closest: selector => selector === '[data-asset-chart-action]' ? { dataset: { assetChartAction: action } } : null } });

test('normalizes, sorts and deduplicates real dates without null/boolean to zero coercion', () => {
  const bars = enrichMarketBars([{ date: '20250103', open: '12', high: '14', low: '11', close: '13', volume: '' }, { trade_date: day(0), open: 10, high: 12, low: 9, close: 11, volume: 0, amount: 0 }, { date: day(2), open: 12, high: 14, low: 11, close: 13, volume: null, turnover: 99, turnover_rate_pct: 4 }, { date: '2025-02-30', close: 22 }, { date: 'bad', close: 23 }, { date: day(1), close: true, open: null, high: 12, low: 9, volume: false }]);
  assert.deepEqual(bars.map(b => b.date), [day(0), day(1), day(2)]);
  assert.equal(bars[0].volume, 0); assert.equal(bars[1].close, null); assert.equal(bars[1].validOHLC, false);
  assert.equal(bars[2].volume, null); assert.equal(bars[2].amount, 99); assert.equal(bars[2].turnover_rate_pct, 4);
  assert.equal(bars.diagnostics.invalidDates, 2); assert.equal(bars.diagnostics.duplicates, 1);
});

test('strict calendar aliases and supplied VWAP never infer unverified amount/volume units', () => {
  const bars = enrichMarketBars([{ date: '2025-0101', close: 1 }, { date: '202501-02', close: 1 }, { date: '2025-01-01T25:00:00Z', close: 1 }, { date: '', trade_date: day(2), close: 1 }, { datetime: '2025-01-04T10:30:00+08:00', close: 1 }]);
  assert.deepEqual(bars.map(b => b.date), [day(2), day(3)]); assert.equal(bars.diagnostics.invalidDates, 3);
  assert.equal(enrichMarketBars(rows(1))[0].vwap, null);
  assert.equal(enrichMarketBars([{ ...rows(1)[0], vwap: 99.5 }])[0].vwap, 99.5);
});

test('all loaded records remain available and calendar intervals remain factual', () => {
  assert.equal(enrichMarketBars(rows(5002)).length, 5002);
  assert.equal(enrichMarketBars([rows(1)[0], { ...rows(1)[0], date: day(4) }])[1].gapDays, 4);
});

test('AlphaFoundry MA complete windows and BOLL20 sample standard deviation', () => {
  const bars = enrichMarketBars(rows(260));
  for (const n of [5, 10, 20, 60, 120, 250]) { assert.equal(bars[n - 2][`ma${n}`], null); near(bars[n - 1][`ma${n}`], 100 + (n - 1) / 2); }
  assert.equal(bars[18].bollUpper, null); near(bars[19].bollUpper, 109.5 + 2 * Math.sqrt(35)); near(bars[19].bollLower, 109.5 - 2 * Math.sqrt(35));
});

test('AlphaFoundry first-close seeded EMA golden values, DIF26 and DEA34 masks', () => {
  const bars = enrichMarketBars(rows(40));
  assert.equal(bars[24].dif, null); near(bars[25].dif, 5.25922548017322);
  assert.equal(bars[32].dea, null); assert.equal(bars[32].macd, null);
  near(bars[33].dif, 6.03608007259611); near(bars[33].dea, 5.625637699754547); near(bars[33].macd, .8208847456831267);
});

test('KDJ seeds from first valid RSV and RSI14 uses simple rolling actual deltas', () => {
  const bars = enrichMarketBars(rows(20)); assert.equal(bars[7].k, null); near(bars[8].k, 85.62661034540321); near(bars[8].d, 79.33028985612434); near(bars[8].j, 98.21925132396095);
  assert.equal(bars[13].rsi, null); assert.equal(bars[14].rsi, 100);
  assert.equal(enrichMarketBars(rows(20, () => 100))[14].rsi, 50); assert.equal(enrichMarketBars(rows(20, i => 100 - i))[14].rsi, 0);
  const volatile = enrichMarketBars(rows(40, i => 100 + (i < 15 ? i : 30 - i)));
  near(volatile[29].rsi, 0); // rolling window discards all earlier gains; Wilder would remain positive
  const zigzag = enrichMarketBars(rows(20, i => 100 + i + i % 4 * 2));
  near(zigzag[8].k, 74.5595876460074); near(zigzag[9].k, 74.70639176400493); near(zigzag[9].d, 74.17584625403555); near(zigzag[9].j, 75.7674827839437);
  const flat = enrichMarketBars(rows(10, () => 100).map(b => ({ ...b, open: 100, high: 100, low: 100 })));
  assert.equal(flat[8].k, 50); assert.equal(flat[8].d, 50); assert.equal(flat[8].j, 50);
});

test('missing/invalid OHLC and explicit gap reset all price warmup; missing volume stays missing', () => {
  const input = rows(65); input[20].close = null; input[25].volume = null;
  const bars = enrichMarketBars(input);
  for (let i = 20; i < 25; i++) assert.equal(bars[i].ma5, null);
  near(bars[25].ma5, 123); assert.equal(bars[45].dif, null); assert.notEqual(bars[46].dif, null);
  assert.equal(bars[53].macd, null); assert.notEqual(bars[54].macd, null);
  assert.equal(bars[34].rsi, null); assert.equal(bars[35].rsi, 100); assert.equal(bars[25].volumeMA5, null);
  const gap = rows(40); gap[20].gap = true; assert.equal(enrichMarketBars(gap)[24].ma5, null);
  const invalid = rows(40); invalid[20].high = 1; assert.equal(enrichMarketBars(invalid)[28].k, null); assert.notEqual(enrichMarketBars(invalid)[29].k, null);
});

test('week/month aggregate OHLCV before recomputing every indicator and do not sum unknown volume', () => {
  const source = enrichMarketBars(rows(300)); const weeks = aggregateMarketBars(source, 'week'); const months = aggregateMarketBars(source, 'month');
  assert.equal(weeks[0].open, source[0].open); assert.equal(weeks[0].close, source[4].close); assert.equal(weeks[0].volume, 5010);
  assert.equal(weeks[0].ma5, null); near(weeks[4].ma5, weeks.slice(0, 5).reduce((s, b) => s + b.close, 0) / 5);
  assert.equal(weeks[24].dif, null); assert.notEqual(weeks[25].dif, null); assert.equal(weeks[13].rsi, null); assert.notEqual(weeks[14].rsi, null);
  assert.equal(months[0].close, source[30].close); assert.equal(months[0].ma20, null);
  const unknown = rows(8); unknown[1].volume = null; assert.equal(aggregateMarketBars(enrichMarketBars(unknown), 'week')[0].volume, null);
});

test('terminal reproduces ECharts five-grid rail, chips and complete controls without SVG fallback', () => {
  const html = renderMarketTerminal(rows(150), {}, { currency: 'CNY', adjustment: '前复权', frequency: 'daily' });
  assert.match(html, /kline-terminal-layout/); assert.match(html, /data-asset-echarts/); assert.match(html, /data-asset-chip-chart/); assert.doesNotMatch(html, /<svg/);
  for (const n of [5, 10, 20, 60, 120, 250]) assert.match(html, new RegExp(`data-asset-chart-action="ma-${n}"`));
  for (const action of ['period-day', 'period-week', 'period-month', 'all', 'overlay-boll', 'overlay-none']) assert.ok(html.includes(`data-asset-chart-action="${action}"`));
  assert.match(html, /分时<\/button>/); assert.match(html, /OHLCV估算/); assert.match(html, /不是实际持仓/); assert.match(html, /前复权/);
});

test('historical change and amplitude use previous close and metadata is escaped', () => {
  const html = renderMarketTerminal([{ ...rows(1)[0], close: 100 }, { ...rows(1)[0], date: day(1), open: 105, close: 110, low: 100, high: 120 }], {}, { dataset: '<img src=x>', currency: 'CNY' });
  assert.match(html, /10\.00%/); assert.match(html, /20\.00%/); assert.doesNotMatch(html, /<img src=x>/); assert.match(html, /历史读数/);
});

test('historical readout retains change amount and average-price slots without guessing units', () => {
  const input = [{ ...rows(1)[0], close: 100 }, { ...rows(1)[0], date: day(1), open: 105, close: 110, low: 100, high: 120, amount: 999000, volume: 3 }];
  const missing = renderMarketTerminal(input);
  assert.match(missing, /涨跌额 <strong>\+10\.00<\/strong>/);
  assert.match(missing, /均价（源字段） <strong>—<\/strong>/);
  for (const key of ['vwap', 'avg_price', 'average_price']) {
    const source = [{ ...input[1], [key]: 108.25 }];
    assert.equal(enrichMarketBars(source)[0].vwap, 108.25);
    assert.match(renderMarketTerminal(source), /均价（源字段） <strong>108\.25<\/strong>/);
  }
  assert.match(renderMarketTerminal([input[0]]), /涨跌额 <strong>—<\/strong>/);
});

test('price axes format floating-point ticks to readable two-decimal prices', () => {
  const option = buildMarketChartOption(enrichMarketBars(rows(30)));
  assert.equal(option.yAxis[0].axisLabel.formatter(129.99999996), '130.00');
  assert.equal(option.yAxis[0].axisPointer.label.formatter({ value: 129.99999996 }), '130.00');
  const chip = estimateChipDistribution(enrichMarketBars(rows(10)), 0, 9);
  assert.equal(buildChipChartOption(chip, [90, 130]).yAxis.axisLabel.formatter(129.99999996), '130.00');
});

test('confirmed share/currency units are translated and unknown units remain source units', () => {
  for (const unit of ['share', 'shares']) {
    const html = renderMarketTerminal(rows(2), {}, { fields: { volume: { unit }, turnover: { unit: 'currency', currency: 'CNY' } } });
    assert.match(html, /成交量（股）/); assert.match(html, /成交额（元）/); assert.doesNotMatch(html, /成交量（shares?）|成交额（currency）/);
  }
  const foreign = renderMarketTerminal(rows(2), {}, { fields: { volume: { unit: 'shares' }, amount: { unit: 'currency', currency: 'USD' } } });
  assert.match(foreign, /成交额（美元）/); assert.doesNotMatch(foreign, /成交额（元）/);
  assert.match(renderMarketTerminal(rows(2), {}, { fields: { amount: { unit: 'currency' } } }), /成交额（源单位）/);
  assert.match(renderMarketTerminal(rows(2)), /成交量（源单位）/);
});

test('aggregated week/month turnover rate cannot reuse the final day percentage as a whole-period fact', () => {
  const daily = rows(5).map(b => ({ ...b, turnover_rate_pct: 1 }));
  assert.equal(aggregateMarketBars(enrichMarketBars(daily), 'week')[0].turnover_rate_pct, null);
  assert.equal(aggregateMarketBars(enrichMarketBars(daily), 'month')[0].turnover_rate_pct, null);
  const html = renderMarketTerminal(daily, { period: 'week' }, { frequency: 'daily' });
  assert.match(html, /换手率 <strong>—<\/strong>/); assert.doesNotMatch(html, /换手率 <strong>1\.00%<\/strong>/);
});

test('five ECharts grids, cross-panel pointer, two linked zooms, all six MA and no volume MA series', () => {
  const bars = enrichMarketBars(rows(260)); const option = buildMarketChartOption(bars, { start: 140, end: 260, overlay: 'ma', enabledMA: [5, 10, 20, 60, 120, 250] });
  assert.equal(option.grid.length, 5); assert.equal(option.grid[0].height, '44%'); assert.equal(option.grid[4].top, '89%');
  assert.equal(option.axisPointer.link[0].xAxisIndex, 'all'); assert.equal(option.dataZoom.length, 2);
  for (const zoom of option.dataZoom) { assert.deepEqual(zoom.xAxisIndex, [0, 1, 2, 3, 4]); assert.equal(zoom.startValue, 140); assert.equal(zoom.endValue, 259); }
  assert.equal(option.series.filter(s => /^MA\d+$/.test(s.name)).length, 6); assert.equal(option.series.some(s => /^VOLMA/.test(s.name)), false);
  assert.match(option.graphic[0].style.text, /VOL:.*MA5:.*MA10:/); assert.equal(option.series[0].data.length, 260);
});

test('both terminal canvases are transparent and explicit themes keep neutral labels readable', () => {
  const bars = enrichMarketBars(rows(260)); const chip = estimateChipDistribution(bars, 140, 259);
  const state = { start: 140, end: 260, overlay: 'ma' };
  const fallback = buildMarketChartOption(bars, state);
  assert.equal(fallback.xAxis[0].axisLabel.color, '#9ca3af');
  for (const [theme, text, muted, grid] of [['light', '#242424', '#686860', '#e8e8e5'], ['dark', '#d1d5db', '#9ca3af', 'rgba(148,163,184,.18)']]) {
    const option = buildMarketChartOption(bars, state, {}, theme); const chips = buildChipChartOption(chip, [90, 370], null, theme);
    assert.equal(option.backgroundColor, 'transparent'); assert.equal(chips.backgroundColor, 'transparent');
    assert.equal(option.xAxis[0].axisLabel.color, muted); assert.equal(option.yAxis[0].axisLabel.color, muted);
    assert.equal(option.yAxis[0].splitLine.lineStyle.color, grid); assert.equal(option.graphic[0].style.fill, text);
    assert.equal(option.tooltip.textStyle.color, text); assert.equal(chips.tooltip.textStyle.color, text);
    assert.equal(option.axisPointer.label.color, text); assert.equal(option.dataZoom[1].textStyle.color, muted);
    assert.equal(option.dataZoom[1].backgroundColor, 'transparent');
    assert.equal(option.dataZoom[1].dataBackground.lineStyle.color, muted);
    assert.equal(option.dataZoom[1].moveHandleStyle.color, muted);
    assert.equal(option.dataZoom[1].emphasis.handleStyle.color, text);
    assert.equal(chips.xAxis.axisLabel.color, muted); assert.equal(chips.yAxis.axisLabel.color, muted);
    assert.equal(option.series.at(-1).markLine.label.color, muted);
    assert.equal(chips.series[0].markLine.data[0].label.color, text);
    assert.deepEqual(option.grid, fallback.grid); assert.deepEqual(option.legend, fallback.legend);
    assert.deepEqual(option.series.map(s => s.data), fallback.series.map(s => s.data));
    assert.deepEqual(option.series.filter(s => s.lineStyle).map(s => s.lineStyle), fallback.series.filter(s => s.lineStyle).map(s => s.lineStyle));
    assert.deepEqual(option.series[0].itemStyle, fallback.series[0].itemStyle);
    assert.ok(option.yAxis.slice(1).every(axis => !Object.hasOwn(axis, 'axisPointer')), 'non-price axes must omit axisPointer instead of setting undefined');
  }
  assert.equal(buildChipChartOption(estimateChipDistribution([], 0, 0), [0, 1], null, 'light').graphic[0].style.fill, '#686860');
});

test('visible price domain includes enabled overlays only', () => {
  const bars = enrichMarketBars(rows(260, i => i < 250 ? 1000 : 100));
  const enabled = buildMarketChartOption(bars, { start: 250, end: 260, overlay: 'ma', enabledMA: [250] });
  const bare = buildMarketChartOption(bars, { start: 250, end: 260, overlay: 'none' });
  assert.ok(enabled.yAxis[0].max > 900); assert.ok(bare.yAxis[0].max < 105);
});

test('KDJ axis includes visible out-of-range J values while RSI alone stays fixed to 0–100', () => {
  const bars = enrichMarketBars(rows(100, i => i < 25 ? 100 : i < 50 ? 200 : 100));
  const values = bars.flatMap(b => [b.k, b.d, b.j]).filter(v => v !== null);
  assert.ok(Math.min(...values) < 0); assert.ok(Math.max(...values) > 100);
  const option = buildMarketChartOption(bars, { start: 0, end: 100 });
  assert.ok(option.yAxis[3].min <= Math.min(...values)); assert.ok(option.yAxis[3].max >= Math.max(...values));
  assert.equal(option.yAxis[4].min, 0); assert.equal(option.yAxis[4].max, 100);
});

test('AF 180 buckets quantize price, volume and concentration before cost/FWHM/profit', () => {
  const source = rows(5, () => 10).map(b => ({ ...b, open: 10, low: 8, high: 12, close: 10, volume: 100 }));
  const chip = estimateChipDistribution(enrichMarketBars(source), 0, 4, [8, 12]);
  assert.equal(chip.points.length, 180); near(chip.points.reduce((s, p) => s + p.volume, 0), 500.4);
  assert.deepEqual(chip.points[0], { price: 8.01, volume: 2.78, concentration_pct: .56 }); near(chip.averageCost, 10); near(chip.profitFraction, .5); near(chip.lockedFraction, .5);
  assert.ok(chip.lower <= chip.peak && chip.upper >= chip.peak); assert.equal(chip.validBars, 5);
  const option = buildChipChartOption(chip, [8, 12]); assert.equal(option.yAxis.min, 8); assert.equal(option.yAxis.max, 12); assert.equal(option.series[0].type, 'custom');
});

test('chips require five valid dates and OHLCV; zero volume is valid but cannot invent distribution', () => {
  assert.equal(estimateChipDistribution(enrichMarketBars(rows(4)), 0, 3).points.length, 0);
  for (const invalid of [{ volume: null }, { volume: -1 }, { low: 999 }, { date: 'bad' }]) {
    const input = rows(5); input[0] = { ...input[0], ...invalid }; assert.equal(estimateChipDistribution(enrichMarketBars(input), 0, 4).points.length, 0);
  }
  assert.equal(estimateChipDistribution(enrichMarketBars(rows(5).map(b => ({ ...b, volume: 0 }))), 0, 4).points.length, 0);
});

test('chip window from visible left to active bar changes reference close and distribution', () => {
  const bars = enrichMarketBars(rows(20)); const full = estimateChipDistribution(bars, 0, 19); const cursor = estimateChipDistribution(bars, 10, 14);
  assert.equal(cursor.referenceClose, bars[14].close); assert.equal(cursor.validBars, 5); assert.equal(cursor.startDate, bars[10].date); assert.notEqual(cursor.averageCost, full.averageCost);
});

test('chip bins and statistics depend only on the OHLCV window, never MA or main price-axis domain', () => {
  const bars = enrichMarketBars(rows(260, i => i < 250 ? 1000 : 100));
  const withMA = buildMarketChartOption(bars, { start: 250, end: 260, overlay: 'ma', enabledMA: [250] }).yAxis[0];
  const bare = buildMarketChartOption(bars, { start: 250, end: 260, overlay: 'none' }).yAxis[0];
  assert.notEqual(withMA.max, bare.max);
  const first = estimateChipDistribution(bars, 250, 259, [withMA.min, withMA.max]);
  const second = estimateChipDistribution(bars, 250, 259, [bare.min, bare.max]);
  assert.deepEqual(first, second); assert.deepEqual(first.domain, [99, 101]);
});

test('chips require five positive-volume candles, although zero volume remains valid market data', () => {
  const input = rows(5); input[0].volume = 0; const bars = enrichMarketBars(input);
  assert.equal(bars[0].volume, 0); assert.equal(bars[0].validOHLC, true);
  assert.equal(estimateChipDistribution(bars, 0, 4).points.length, 0);
});

test('chip FWHM interpolates half-height crossings rather than rounding whole buckets', () => {
  const flat = rows(5, () => 10).map(b => ({ ...b, open: 10, low: 10, high: 10, volume: 100 }));
  assert.equal(estimateChipDistribution(enrichMarketBars(flat), 0, 4).points.length, 0, 'zero raw price range cannot invent an expanded domain');
  const bars = enrichMarketBars([...flat, { ...rows(6, () => 10)[5], open: 10, low: 8, high: 12, volume: 1 }]);
  const chip = estimateChipDistribution(bars, 0, 5, [8, 12]);
  near(chip.lower, 10); near(chip.upper, 10.02); near(chip.peak, 10.01);
  const total = chip.points.reduce((sum, point) => sum + point.volume, 0);
  const profit = chip.points.filter(point => point.price < 10).reduce((sum, point) => sum + point.volume, 0);
  near(chip.profitFraction, profit / total); near(chip.lockedFraction, 1 - profit / total);
});

test('configure never triggers outer render and controls retain independent MA choices', () => {
  let changes = 0; const c = createAssetChartController({ onChange: () => changes++ }); c.configure(rows(260), 'one');
  assert.equal(changes, 0); assert.equal(c.getState().start, 140); assert.equal(c.getState().activeIndex, 259);
  c.handle(click('ma-60')); assert.equal(c.getState().enabledMA.includes(60), false); assert.equal(c.getState().enabledMA.includes(120), true);
  c.handle(click('overlay-boll')); assert.equal(c.getState().overlay, 'boll'); c.handle(click('overlay-ma')); assert.equal(c.getState().enabledMA.includes(60), false);
  c.handle(click('all')); assert.equal(c.getState().start, 0); assert.equal(c.getState().end, 260); assert.equal(changes, 4);
});

test('weekly/monthly controls recompute, legacy weekly inputs never masquerade as day', () => {
  const c = createAssetChartController(); c.configure(rows(300), 'one'); c.handle(click('period-week')); assert.equal(c.getState().period, 'week'); assert.ok(c.getState().end < 50);
  c.handle(click('period-month')); assert.equal(c.getState().end, 10); c.configure(rows(20), 'legacy', { frequency: 'weekly' });
  assert.equal(c.getState().period, 'week'); assert.equal(c.handle(click('period-day')), false);
  assert.match(renderMarketTerminal(rows(20), c.getState(), { frequency: 'weekly' }), /源数据频率：周/);
});

test('refresh follows latest only at latest and preserves historical date; empty/cancel/dispose safe', () => {
  const c = createAssetChartController(); c.configure(rows(200), 'one'); c.configure(rows(202), 'one'); assert.equal(c.getState().end, 202);
  c.pan(-30); c.select(130); const before = c.getState(); c.configure(rows(204), 'one'); assert.equal(c.getState().start, before.start); assert.equal(c.getState().activeIndex, 130);
  c.configure([], 'one'); assert.equal(c.getState().activeIndex, -1); assert.equal(c.select(0), false); assert.equal(c.zoom(.5), false); c.cancel(); c.dispose(); c.dispose();
});

test('errors log only stable codes and never private exception text', () => {
  const logs = []; const c = createAssetChartController({ onChange: () => { throw new Error('private row data'); }, logger: (...a) => logs.push(a) });
  c.configure(rows(40), 'one'); c.handle(click('overlay-boll')); assert.equal(logs.length, 1); assert.doesNotMatch(JSON.stringify(logs), /private row data/);
});

function fakeDOM() {
  const nodes = new Map(); const handlers = new Map(); const doc = { defaultView: null };
  const node = { ownerDocument: doc, style: { setProperty() {} }, dataset: {}, clientHeight: 690, textContent: '', innerHTML: '', addEventListener: (n, f) => handlers.set(n, f), removeEventListener: n => handlers.delete(n), querySelector: selector => nodes.get(selector) || null, querySelectorAll: () => [], getBoundingClientRect: () => ({ left: 0, top: 0, right: 1000, bottom: 690, width: 1000, height: 690 }) };
  for (const selector of ['[data-asset-echarts]', '[data-asset-chip-chart]', '[data-asset-history]', '[data-asset-overlay-label]', '[data-asset-chip-stats]', '[data-asset-chip-window]', '[data-asset-range-summary]', '[data-asset-chart-metadata]', '.kline-terminal-layout']) nodes.set(selector, { ...node, dataset: {} });
  const frames = new Map(); let frame = 0; const instances = []; const observers = [];
  doc.defaultView = { devicePixelRatio: 1, requestAnimationFrame: fn => { frames.set(++frame, fn); return frame; }, cancelAnimationFrame: id => frames.delete(id), ResizeObserver: class { constructor(fn) { this.fn = fn; observers.push(this); } observe() {} disconnect() { this.disconnected = true; } }, echarts: { init: () => { const events = new Map(); const zrEvents = new Map(); const c = { events, zrEvents, setOption: (option, replace) => { c.option = replace || !c.option ? option : { ...c.option, ...option }; }, on: (n, f) => events.set(n, f), off: n => events.delete(n), getZr: () => ({ on: (n, f) => zrEvents.set(n, f), off: n => zrEvents.delete(n) }), resize() { c.resizes = (c.resizes || 0) + 1; }, dispose() { c.disposed = true; } }; instances.push(c); return c; } } };
  return { node, nodes, handlers, instances, observers, frames, flush: () => { const work = [...frames.values()]; frames.clear(); work.forEach(fn => fn()); } };
}

function pageTheme(f, mode) {
  const values = mode === 'light' ? { '--text': '#242424', '--muted': '#686860', '--line': '#e8e8e5', '--surface': '#fafaf9', '--selected': '#e8e8e5' } : { '--text': '#ecece7', '--muted': '#aaa99f', '--line': '#343430', '--surface': '#222220', '--selected': '#30302c' };
  f.node.ownerDocument.documentElement = { dataset: { theme: mode } };
  f.node.ownerDocument.defaultView.getComputedStyle = () => ({ getPropertyValue: name => values[name] || '' });
  return values;
}

test('theme remount reads page variables and preserves controls, range, history and series data', () => {
  const f = fakeDOM(); pageTheme(f, 'dark'); const c = createAssetChartController(); c.configure(rows(320), 'one'); c.mount(f.node); f.flush();
  c.handle(click('ma-250')); c.pan(-30); c.select(230); f.flush();
  const state = c.getState(); const points = f.instances[1].option.series[0].data;
  const light = pageTheme(f, 'light'); c.mount(f.node); f.flush();
  assert.ok(f.instances.slice(0, 2).every(chart => chart.disposed));
  assert.equal(f.instances[2].option.xAxis[0].axisLabel.color, light['--muted']);
  assert.equal(f.instances[2].option.graphic[0].style.fill, light['--text']);
  assert.equal(f.instances[3].option.tooltip.backgroundColor, light['--surface']);
  assert.deepEqual(c.getState(), state); assert.deepEqual(f.instances[3].option.series[0].data, points);
  c.select(231); f.flush(); assert.equal(f.instances[2].option.graphic[0].style.fill, light['--text']);
  const dark = pageTheme(f, 'dark'); c.mount(f.node); f.flush();
  assert.equal(f.instances[4].option.xAxis[0].axisLabel.color, dark['--muted']);
  assert.equal(f.instances[5].option.yAxis.axisLine.lineStyle.color, dark['--line']);
  assert.equal(c.getState().activeIndex, 231); c.dispose();
});

test('computed-theme failures use deterministic fallback and log only stable diagnostic codes', () => {
  const f = fakeDOM(); pageTheme(f, 'light'); const errors = [];
  f.node.ownerDocument.defaultView.getComputedStyle = () => { throw new Error('private page content'); };
  const c = createAssetChartController({ logger: event => errors.push(event) }); c.configure(rows(30), 'one');
  assert.equal(c.mount(f.node), true); f.flush();
  assert.equal(f.instances[0].option.xAxis[0].axisLabel.color, '#686860');
  assert.deepEqual(errors, ['asset_chart_theme_failed']); c.dispose();
});

test('mount keeps chart instances across pointer updates, coalesces frames and disposes every resource', () => {
  const f = fakeDOM(); let calls = 0; const c = createAssetChartController({ onChange: () => calls++ }); c.configure(rows(200), 'one'); c.mount(f.node); f.flush();
  assert.equal(f.instances.length, 2); const main = f.instances[0]; const oldMarkup = f.node.innerHTML;
  main.events.get('updateAxisPointer')({ axesInfo: [{ axisDim: 'x', axisIndex: 0, value: 100 }] }); main.events.get('updateAxisPointer')({ axesInfo: [{ axisDim: 'x', axisIndex: 0, value: 120 }] });
  assert.equal(f.frames.size, 1); f.flush(); assert.equal(c.getState().activeIndex, 120); assert.equal(f.node.innerHTML, oldMarkup); assert.equal(f.instances.length, 2);
  main.events.get('dataZoom')({ startValue: 50, endValue: 100 }); f.flush(); assert.equal(c.getState().start, 50); assert.equal(c.getState().end, 101);
  f.handlers.get('mouseleave')?.(); f.flush(); assert.equal(c.getState().activeIndex, 100);
  const callsBefore = calls; c.configure(rows(202), 'one'); f.flush(); assert.equal(calls, callsBefore);
  c.dispose(); assert.ok(f.instances.every(i => i.disposed)); assert.ok(f.observers.every(o => o.disconnected)); assert.equal(f.frames.size, 0); assert.equal(f.handlers.size, 0); assert.equal(main.events.size, 0); assert.equal(main.zrEvents.size, 0);
});

test('remount disposes previous instances and missing library remains an explicit recoverable state', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(20), 'one'); c.mount(f.node); f.flush(); c.mount(f.node); f.flush(); assert.ok(f.instances.slice(0, 2).every(i => i.disposed)); c.dispose();
  const missing = fakeDOM(); delete missing.node.ownerDocument.defaultView.echarts; c.mount(missing.node); assert.match(missing.nodes.get('[data-asset-echarts]').textContent, /图表资源/); c.dispose();
});

test('local events cannot double toggle through root delegation; DOM exposes serialized view state', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(200), 'one'); c.mount(f.node); f.flush();
  const event = click('ma-60'); let stopped = false; event.stopPropagation = () => { stopped = true; };
  f.handlers.get('click')(event); c.handle(event); f.flush(); assert.equal(stopped, true); assert.equal(c.getState().enabledMA.includes(60), false);
  const attrs = f.nodes.get('[data-asset-echarts]').dataset; assert.equal(attrs.visibleCount, '120'); assert.equal(attrs.activeIndex, '199'); assert.equal(attrs.enabledMa, '5,10,20,120,250'); c.dispose();
});

test('keyboard navigation pans safely and leaves button arrow behavior untouched', () => {
  const c = createAssetChartController(); c.configure(rows(200), 'one'); let prevented = 0;
  const target = { closest: selector => selector === '[data-asset-chart]' ? {} : null };
  assert.equal(c.handle({ type: 'keydown', target: { closest: () => null }, key: 'Home' }), false);
  assert.equal(c.handle({ type: 'keydown', target, key: 'Home', preventDefault: () => prevented++ }), true); assert.equal(c.getState().activeIndex, 0); assert.equal(c.getState().start, 0);
  c.handle({ type: 'keydown', target, key: 'End' }); assert.equal(c.getState().activeIndex, 199); assert.equal(c.getState().end, 200); assert.equal(prevented, 1);
});

test('cancel clears queued work; dispose retains user controls for the next render', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(200), 'one'); c.mount(f.node); f.flush();
  c.handle(click('ma-250')); c.pan(-30); assert.equal(f.frames.size, 1); c.cancel(); assert.equal(f.frames.size, 0);
  const old = c.getState(); c.dispose(); c.mount(f.node); f.flush(); assert.deepEqual(c.getState(), old); c.dispose();
});

test('historical select then cancel then leave keeps state, readout, panel labels and chips consistent', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(200), 'one'); c.mount(f.node); f.flush();
  c.select(100); f.flush(); assert.match(f.nodes.get('[data-asset-history]').innerHTML, new RegExp(day(100)));
  c.select(110); assert.equal(f.frames.size, 1); c.cancel(); assert.equal(f.frames.size, 0);
  assert.equal(c.getState().activeIndex, 199); assert.match(f.nodes.get('[data-asset-history]').innerHTML, new RegExp(day(199)));
  assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(199)));
  assert.equal(f.instances[0].option.graphic[0].style.text.includes('1,199'), true);
  f.handlers.get('mouseleave')(); f.flush(); assert.equal(c.getState().activeIndex, 199);
  assert.match(f.nodes.get('[data-asset-history]').innerHTML, new RegExp(day(199))); c.dispose();
});

test('mount initialization failure disposes partial charts and observers without leaking error data', () => {
  const f = fakeDOM(); const init = f.node.ownerDocument.defaultView.echarts.init; let count = 0; const logs = [];
  f.node.ownerDocument.defaultView.echarts.init = (...a) => { if (++count === 2) throw new Error('sensitive'); return init(...a); };
  const c = createAssetChartController({ logger: (...a) => logs.push(a) }); c.configure(rows(20), 'one'); assert.equal(c.mount(f.node), false);
  assert.ok(f.instances[0].disposed); assert.equal(f.handlers.size, 0); assert.equal(f.frames.size, 0); assert.doesNotMatch(JSON.stringify(logs), /sensitive/); c.dispose();
});

test('native zoom merges the visible price axis without resetting ECharts drag state', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(200), 'one'); c.mount(f.node); f.flush(); const chart = f.instances[0]; const original = chart.option;
  let replacement; const set = chart.setOption; chart.setOption = (option, replace) => { replacement = replace; set(option, replace); };
  chart.events.get('dataZoom')({ batch: [{ start: 10, end: 40 }] }); f.flush();
  assert.equal(replacement, false); assert.equal(chart.option.series, original.series); assert.equal(c.getState().start, 20); assert.equal(c.getState().end, 81); c.dispose();
});

test('native zoom also expands KDJ to historical visible J extremes', () => {
  const f = fakeDOM(); const c = createAssetChartController(); const input = rows(300, i => i < 25 ? 100 : i < 50 ? 200 : 100);
  c.configure(input, 'one'); c.mount(f.node); f.flush(); const chart = f.instances[0];
  chart.events.get('dataZoom')({ startValue: 0, endValue: 99 }); f.flush();
  assert.ok(chart.option.yAxis[3].min < 0); assert.ok(chart.option.yAxis[3].max > 100); c.dispose();
});

test('mounted overlay toggles change the render price axis without changing chip points/statistics', () => {
  const f = fakeDOM(); const c = createAssetChartController(); c.configure(rows(260, i => i < 250 ? 1000 : 100), 'one'); c.mount(f.node); f.flush();
  f.instances[0].events.get('dataZoom')({ startValue: 250, endValue: 259 }); f.flush();
  const chip = f.instances[1]; const points = chip.option.series[0].data; const stats = f.nodes.get('[data-asset-chip-stats]').innerHTML; const max = chip.option.yAxis.max;
  c.handle(click('overlay-none')); f.flush();
  assert.notEqual(chip.option.yAxis.max, max); assert.deepEqual(chip.option.series[0].data, points); assert.equal(f.nodes.get('[data-asset-chip-stats]').innerHTML, stats); c.dispose();
});

test('mounted configure refreshes metadata and can recover from an initially missing ECharts library', () => {
  const f = fakeDOM(); const library = f.node.ownerDocument.defaultView.echarts; delete f.node.ownerDocument.defaultView.echarts;
  const c = createAssetChartController({ logger: () => {} }); c.configure(rows(20), 'one'); c.mount(f.node); f.flush();
  f.node.ownerDocument.defaultView.echarts = library; c.configure(rows(30), 'one', { currency: 'CNY', adjustment: '前复权', frequency: 'daily' }); f.flush();
  assert.equal(f.instances.length, 2); assert.match(f.nodes.get('[data-asset-chart-metadata]').textContent, /CNY 前复权/); c.dispose();
});

test('real pinned ECharts creates every series view and survives controls, keyboard, cancel and native zoom', () => {
  const timers = new Set();
  const runtime = { console, clearTimeout, setTimeout: (callback, delay) => { const timer = setTimeout(callback, delay); timers.add(timer); return timer; } };
  runInNewContext(readFileSync(new URL('../../app/research_web/ui/vendor/echarts-5.5.0.min.js', import.meta.url), 'utf8'), runtime);
  const f = fakeDOM(); const charts = []; const errors = [];
  f.node.ownerDocument.defaultView.echarts = { ...runtime.echarts, init: () => {
    const chart = runtime.echarts.init(null, null, { renderer: 'svg', ssr: true, width: 1000, height: 690 });
    charts.push(chart); return chart;
  } };
  const c = createAssetChartController({ logger: event => errors.push(event) });
  const viewsAreReady = () => {
    assert.deepEqual(errors, []);
    const series = charts.at(-2).getModel().getSeries();
    assert.equal(series.length, 18);
    assert.ok(series.every(model => charts.at(-2).getViewOfSeriesModel(model)), 'every series must have an actual ECharts view');
  };
  try {
    c.configure(rows(320), 'one');
    for (const mode of ['dark', 'light', 'dark']) {
      const palette = pageTheme(f, mode); c.reset(); c.mount(f.node); f.flush(); viewsAreReady();
      assert.equal(charts.at(-2).getOption().backgroundColor, 'transparent');
      assert.equal(charts.at(-1).getOption().backgroundColor, 'transparent');
      assert.equal(charts.at(-2).getOption().xAxis[0].axisLabel.color, palette['--muted']);
      for (const action of ['ma-250', 'ma-250', 'overlay-boll', 'overlay-none', 'overlay-ma', 'period-week', 'period-month', 'period-day', 'all', 'reset']) {
        c.cancel(); c.handle(click(action)); f.flush(); viewsAreReady();
      }
      c.handle({ type: 'keydown', key: 'ArrowLeft', target: { closest: () => ({}) } }); f.flush();
      assert.equal(c.getState().activeIndex, 318);
      assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(318)));
      charts.at(-2).dispatchAction({ type: 'dataZoom', startValue: 200, endValue: 279 }); f.flush(); viewsAreReady();
      assert.equal(c.getState().start, 200); assert.equal(c.getState().end, 280);
      c.select(250); f.flush(); c.cancel(); viewsAreReady();
      assert.equal(c.getState().activeIndex, 279);
      assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(279)));
    }
  } finally { c.dispose(); for (const timer of timers) clearTimeout(timer); }
});
