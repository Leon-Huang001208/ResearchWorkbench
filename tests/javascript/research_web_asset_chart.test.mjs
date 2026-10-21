import assert from 'node:assert/strict';
import test from 'node:test';
test('canonical DataHub turnover is amount and never turnover rate', async () => {
  const { enrichMarketBars } = await import('../../app/research_web/ui/asset-chart.mjs');
  const bar = enrichMarketBars([{ date: '2026-10-20', open: 10, high: 12, low: 9, close: 11, turnover: 139000, turnover_rate_pct: 1.39 }])[0];
  assert.equal(bar.amount, 139000); assert.equal(bar.turnover_rate_pct, 1.39);
});

let chartModule;
try {
  chartModule = await import('../../app/research_web/ui/asset-chart.mjs');
} catch (error) {
  if (error.code !== 'ERR_MODULE_NOT_FOUND') throw error;
}
const chart = () => { assert.ok(chartModule, '独立行情图表模块应已实现'); return chartModule; };
const day = index => new Date(Date.UTC(2025, 0, index + 1)).toISOString().slice(0, 10);
const rows = (count, value = index => 100 + index) => Array.from({ length: count }, (_, index) => ({
  date: day(index), open: value(index) - 0.2, high: value(index) + 1, low: value(index) - 1,
  close: value(index), volume: 1000 + index, amount: 100000 + index, turnover_rate_pct: 2,
}));
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} should equal ${expected}`);

test('normalization sorts and deduplicates real dates without turning missing values into zero', () => {
  const { enrichMarketBars } = chart();
  const bars = enrichMarketBars([
    { date: '20250103', open: '12', high: '14', low: '11', close: '13', volume: '', amount: null, turnover_rate_pct: '3.2' },
    { trade_date: '2025-01-01', open: 10, high: 12, low: 9, close: 11, volume: 0, amount: 0 },
    { date: '2025-01-03', open: 12, high: 14, low: 11, close: 13, volume: null, turnover: 99, turnover_rate_pct: 4 },
    { date: '2025-02-30', close: 22 },
    { date: 'not-a-date', close: 23 },
    { date: '2025-01-02', close: true, open: null, high: 12, low: 9, volume: false },
  ]);
  assert.deepEqual(bars.map(bar => bar.date), [day(0), day(1), day(2)]);
  assert.equal(bars[0].volume, 0);
  assert.equal(bars[1].close, null);
  assert.equal(bars[1].validOHLC, false);
  assert.equal(bars[2].volume, null);
  assert.equal(bars[2].amount, 99, 'DataHub canonical turnover is monetary amount');
  assert.equal(bars[2].turnover_rate_pct, 4);
  assert.equal(bars.diagnostics.invalidDates, 2);
  assert.equal(bars.diagnostics.duplicates, 1);
});

test('history is bounded to latest 5000 records and reports dropped rows and calendar intervals', () => {
  const { enrichMarketBars } = chart();
  const bars = enrichMarketBars(rows(5002));
  assert.equal(bars.length, 5000);
  assert.equal(bars[0].date, day(2));
  assert.equal(bars.diagnostics.truncated, 2);
  const spaced = enrichMarketBars([rows(1)[0], { ...rows(1)[0], date: day(4) }]);
  assert.equal(spaced[1].gapDays, 4);
});

test('MA and BOLL require complete windows and use population deviation', () => {
  const { enrichMarketBars } = chart();
  const bars = enrichMarketBars(rows(20));
  assert.equal(bars[3].ma5, null);
  near(bars[4].ma5, 102);
  assert.equal(bars[8].ma10, null);
  near(bars[9].ma10, 104.5);
  assert.equal(bars[18].ma20, null);
  assert.equal(bars[18].bollUpper, null);
  near(bars[19].ma20, 109.5);
  near(bars[19].bollUpper, 109.5 + 2 * Math.sqrt(33.25));
  near(bars[19].bollLower, 109.5 - 2 * Math.sqrt(33.25));
});

test('MACD seeds full EMA windows and waits for nine complete DIF values', () => {
  const bars = chart().enrichMarketBars(rows(40));
  assert.equal(bars[24].dif, null);
  near(bars[25].dif, 7);
  assert.equal(bars[32].dea, null);
  assert.equal(bars[32].macd, null);
  near(bars[33].dea, 7);
  near(bars[33].macd, 0);
});

test('KDJ requires nine complete OHLC records and RSI fourteen actual price changes', () => {
  const { enrichMarketBars } = chart();
  const bars = enrichMarketBars(rows(20));
  assert.equal(bars[7].k, null);
  near(bars[8].k, (100 + 90) / 3);
  near(bars[8].d, (100 + bars[8].k) / 3);
  assert.equal(bars[13].rsi, null);
  assert.equal(bars[14].rsi, 100);
  assert.equal(enrichMarketBars(rows(20, () => 100))[14].rsi, 50);
  assert.equal(enrichMarketBars(rows(20, index => 100 - index))[14].rsi, 0);
});

test('missing close restarts indicator warmup and missing high does not invent a KDJ window', () => {
  const input = rows(65); input[20].close = null;
  const bars = chart().enrichMarketBars(input);
  for (let index = 20; index < 25; index++) assert.equal(bars[index].ma5, null);
  near(bars[25].ma5, 123);
  assert.equal(bars[45].dif, null);
  near(bars[46].dif, 7);
  assert.equal(bars[53].macd, null);
  near(bars[54].macd, 0);
  assert.equal(bars[34].rsi, null);
  assert.equal(bars[35].rsi, 100);
  input[20] = { ...input[20], close: 120, high: null };
  const highGap = chart().enrichMarketBars(input);
  assert.equal(highGap[28].k, null);
  assert.notEqual(highGap[29].k, null);
});

test('render defaults to the latest 120 real records with linked panels and historical readout', () => {
  const html = chart().renderMarketTerminal(rows(150));
  assert.equal((html.match(/class="asset-candle /g) || []).length, 120);
  assert.match(html, /aria-label="包含 K 线、成交量、MACD、KDJ 和 RSI/);
  for (const panel of ['price', 'volume', 'macd', 'kdj', 'rsi']) assert.match(html, new RegExp(`data-panel="${panel}"`));
  assert.match(html, /历史读数/);
  assert.match(html, /data-active-date="2025-05-30"/);
  assert.match(html, /tabindex="0"/);
  assert.doesNotMatch(html, /NaN|Infinity/);
});

test('overlays are mutually exclusive and price axes only scale the selected visible range', () => {
  const { renderMarketTerminal } = chart();
  const input = [...rows(22), { date: day(22), open: 999, high: 1001, low: 998, close: 1000 }];
  const bare = renderMarketTerminal(input, { start: 0, end: 20, overlay: 'none' });
  assert.doesNotMatch(bare, /class="asset-series (?:ma5|ma10|ma20|boll)/);
  assert.ok(Number(bare.match(/data-price-max="([^"]+)"/)[1]) < 200);
  const ma = renderMarketTerminal(input, { overlay: 'ma' });
  assert.match(ma, /class="asset-series ma5"/); assert.doesNotMatch(ma, /class="asset-series boll/);
  const boll = renderMarketTerminal(input, { overlay: 'boll' });
  assert.match(boll, /class="asset-series boll/); assert.doesNotMatch(boll, /class="asset-series ma5/);
});

test('missing candles and volume are absent, path gaps restart, and invalid dates are explained', () => {
  const input = rows(50); input[20].close = null; input[21].volume = null;
  input.push({ date: 'unknown', close: 999 });
  const html = chart().renderMarketTerminal(input);
  assert.equal((html.match(/class="asset-candle /g) || []).length, 49);
  assert.equal((html.match(/class="asset-volume /g) || []).length, 49);
  assert.match(html, /日期无效.*1/);
  const path = html.match(/class="asset-series ma5" d="([^"]*)"/)[1];
  assert.equal((path.match(/M/g) || []).length, 2);
  assert.doesNotMatch(html, /NaN|Infinity/);
});

test('controller initializes and changes identity without configure feedback loops', () => {
  const changes = []; const controller = chart().createAssetChartController({ onChange: (...args) => changes.push(args) });
  controller.configure(rows(200), 'one');
  assert.deepEqual(Object.fromEntries(['overlay', 'start', 'end', 'activeIndex'].map(key => [key, controller.getState()[key]])), { overlay: 'ma', start: 80, end: 200, activeIndex: 199 });
  controller.pan(-40); assert.equal(controller.getState().start, 40);
  controller.configure(rows(200), 'one'); assert.equal(controller.getState().start, 40);
  assert.equal(changes.length, 1);
  controller.configure(rows(150), 'two'); assert.equal(controller.getState().start, 30);
  assert.equal(changes.length, 1);
});

test('zoom and pan clamp valid half-open ranges and selection remains visible', () => {
  const controller = chart().createAssetChartController(); controller.configure(rows(200), 'one');
  controller.zoom(0.5, 199); let state = controller.getState();
  assert.equal(state.end - state.start, 60);
  assert.equal(state.end, 200);
  controller.pan(-10000); state = controller.getState();
  assert.equal(state.start, 0); assert.equal(state.end, 60);
  controller.select(199); state = controller.getState();
  assert.equal(state.activeIndex, 199); assert.equal(state.end, 200);
  controller.zoom(0.0001); assert.equal(controller.getState().end - controller.getState().start, 10);
  controller.zoom(10000); assert.equal(controller.getState().end - controller.getState().start, 200);
  controller.reset(); assert.equal(controller.getState().start, 80);
});

const chartTarget = () => {
  const element = { getBoundingClientRect: () => ({ left: 0, top: 0, width: 1060, height: 718 }) };
  element.closest = selector => selector === '[data-asset-chart]' ? element : null;
  return element;
};

test('delegated pointer and keyboard interactions select real bars and do not trap normal wheel scrolling', () => {
  const controller = chart().createAssetChartController(); controller.configure(rows(200), 'one');
  const target = chartTarget(); let prevented = 0;
  const event = { target, preventDefault: () => { prevented++; } };
  assert.equal(controller.handle({ ...event, type: 'pointermove', clientX: 62, clientY: 80 }), true);
  assert.equal(controller.getState().activeIndex, 80);
  assert.equal(controller.handle({ ...event, type: 'keydown', key: 'ArrowRight' }), true);
  assert.equal(controller.getState().activeIndex, 81);
  const before = controller.getState();
  assert.equal(controller.handle({ ...event, type: 'wheel', deltaY: -100 }), false);
  assert.equal(controller.getState().end - controller.getState().start, before.end - before.start);
  assert.equal(controller.handle({ ...event, type: 'wheel', deltaY: -100, ctrlKey: true, clientX: 500 }), true);
  assert.ok(controller.getState().end - controller.getState().start < 120);
  assert.equal(prevented, 2);
});

test('delegated controls switch one overlay and actual callback failures are logged safely', () => {
  const logs = []; const controller = chart().createAssetChartController({
    onChange: () => { throw new Error('private row data'); }, logger: (...args) => logs.push(args),
  });
  controller.configure(rows(40), 'one');
  const control = { dataset: { assetChartAction: 'overlay-boll' }, closest: selector => selector === '[data-asset-chart-action]' ? control : null };
  assert.equal(controller.handle({ type: 'click', target: control }), true);
  assert.equal(controller.getState().overlay, 'boll');
  assert.equal(logs.length, 1);
  assert.doesNotMatch(JSON.stringify(logs), /private row data/);
});

test('dragging pans the viewport even after leaving the SVG and cancellation stops the gesture', () => {
  const controller = chart().createAssetChartController(); controller.configure(rows(200), 'one');
  const target = chartTarget(); const outside = { closest: () => null }; let prevented = 0;
  controller.handle({ type: 'pointerdown', target, clientX: 500, clientY: 100, pointerId: 4, button: 0 });
  controller.handle({ type: 'pointermove', target: outside, clientX: 700, clientY: 100, pointerId: 4, preventDefault: () => { prevented++; } });
  assert.ok(controller.getState().start < 80);
  assert.equal(prevented, 1);
  const before = controller.getState();
  assert.equal(controller.handle({ type: 'pointercancel', target: outside, pointerId: 4 }), true);
  controller.handle({ type: 'pointermove', target: outside, clientX: 900, clientY: 100, pointerId: 4 });
  assert.equal(controller.getState().start, before.start);
});

test('captured descendant pointerleave events do not cancel dragging across candle elements', () => {
  const controller = chart().createAssetChartController(); controller.configure(rows(200), 'one');
  const target = chartTarget(); const candle = { closest: selector => selector === '[data-asset-chart]' ? target : null };
  const outside = { closest: () => null };
  controller.handle({ type: 'pointerdown', target, clientX: 500, clientY: 100, pointerId: 4, button: 0 });
  assert.equal(controller.handle({ type: 'pointerleave', target: candle }), false);
  controller.handle({ type: 'pointerleave', target, relatedTarget: outside });
  controller.handle({ type: 'pointermove', target: outside, clientX: 700, clientY: 100, pointerId: 4 });
  assert.ok(controller.getState().start < 80, 'document-level drag continues outside SVG until pointerup/cancel');
});

test('refresh follows latest only when already at latest and preserves a historical selection by date', () => {
  const controller = chart().createAssetChartController(); controller.configure(rows(200), 'one');
  controller.configure(rows(202), 'one');
  assert.equal(controller.getState().end, 202);
  assert.equal(controller.getState().activeIndex, 201);
  controller.pan(-30); controller.select(130);
  const before = controller.getState();
  controller.configure(rows(204), 'one');
  assert.equal(controller.getState().start, before.start);
  assert.equal(controller.getState().activeIndex, 130);
  controller.configure([], 'one');
  assert.deepEqual(controller.getState(), { overlay: 'ma', start: 0, end: 0, activeIndex: -1, crosshairY: null });
  assert.equal(controller.select(0), false);
  assert.equal(controller.zoom(0.5), false);
});

test('date aliases require calendar dates with consistent separators and no invalid timestamps', () => {
  const input = [
    { date: '2025-0101', close: 1 }, { date: '202501-02', close: 1 },
    { date: '2025-01-01T25:00:00Z', close: 1 },
    { date: '', trade_date: '2025-01-03', close: 1 },
    { datetime: '2025-01-04T10:30:00+08:00', close: 1 },
  ];
  const bars = chart().enrichMarketBars(input);
  assert.deepEqual(bars.map(bar => bar.date), [day(2), day(3)]);
  assert.equal(bars.diagnostics.invalidDates, 3);
});
