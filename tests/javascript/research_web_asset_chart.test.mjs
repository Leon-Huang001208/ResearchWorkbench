import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
import { enrichMarketBars, renderMarketTerminal, createAssetChartController, buildMarketChartOption, buildChipChartOption } from '../../app/research_web/ui/asset-chart.mjs';
import { aggregateMarketBars, estimateChipDistribution } from '../../app/research_web/ui/asset-indicators.mjs';

const day = i => new Date(Date.UTC(2025, 0, i + 1)).toISOString().slice(0, 10);
const rows = (n, value = i => 100 + i) => Array.from({ length: n }, (_, i) => ({ asset: '603986.SH', vwap: value(i), date: day(i), open: value(i) - .2, high: value(i) + 1, low: value(i) - 1, close: value(i), volume: 1000 + i, amount: 100000 + i, turnover_rate_pct: 2 }));
const chipInputs = { status: 'complete', contract_version: 'chip-turnover-1', turnover_unit: 'percent' };
const near = (a, b, tolerance = 1e-8) => assert.ok(Math.abs(a - b) < tolerance, `${a} should equal ${b}`);
const click = action => ({ type: 'click', target: { closest: selector => selector === '[data-asset-chart-action]' ? { dataset: { assetChartAction: action } } : null } });

test('approved workspace defaults to two removable panels and a flat chart/chips surface', () => {
  const html = renderMarketTerminal(rows(260));
  assert.doesNotMatch(html, /MARKET TERMINAL|kline-indicator-rail|<h2>K 线/);
  assert.match(html, /data-asset-chart-action="panel-remove-volume"/);
  assert.match(html, /data-asset-chart-action="panel-remove-macd"/);
  assert.doesNotMatch(html, /data-asset-chart-action="panel-remove-kdj"/);
  assert.doesNotMatch(html, /data-asset-selected-date|asset-date-controls|asset-range-controls/);
  assert.match(html, /asset-history-date/);
  assert.match(html, /data-asset-chart-adjustment/);
  assert.match(html, /筹码输入/);
  const option = buildMarketChartOption(enrichMarketBars(rows(260)));
  assert.equal(option.grid.length, 3);
  assert.deepEqual(option.dataZoom[0].xAxisIndex, [0, 1, 2]);
});

test('panel preferences normalize, deduplicate, allow none and notify only user mutations', () => {
  const changes = []; const c = createAssetChartController({ onPanelsChange: panels => changes.push(panels) });
  c.configure(rows(100), 'one', {}, { panels: ['rsi', 'rsi', 'unknown', 'volume'] });
  assert.deepEqual(c.getState().panels, ['rsi', 'volume']);
  c.handle(click('panel-add-kdj')); c.handle(click('panel-add-kdj'));
  assert.deepEqual(c.getState().panels, ['rsi', 'volume', 'kdj']); assert.equal(changes.length, 1);
  c.setPreferences({ panels: [] }); assert.deepEqual(c.getState().panels, []); assert.equal(changes.length, 1);
  const option = buildMarketChartOption(enrichMarketBars(rows(100)), c.getState());
  assert.equal(option.grid.length, 1); assert.ok(option.series.every(series => series.yAxisIndex === 0));
  assert.deepEqual(option.dataZoom[1].xAxisIndex, [0]);
});

test('history status refresh leaves identical native date properties untouched', () => {
  const f = fakeDOM(); const input = rows(300); const date = {}; const values = { value: '', min: '', max: '' }; const writes = { value: 0, min: 0, max: 0 };
  for (const key of Object.keys(values)) Object.defineProperty(date, key, { get: () => values[key], set: next => { values[key] = next; writes[key]++; } });
  f.nodes.set('[data-asset-selected-date]', date);
  const c = createAssetChartController();
  c.configure(input, 'one', { assetIdentity: 'same', historyJob: { status: 'queued' } }); c.mount(f.node); f.flush();
  for (const key of Object.keys(writes)) writes[key] = 0;
  c.configure(input, 'one', { assetIdentity: 'same', historyJob: { status: 'completed' } }); f.flush();
  assert.deepEqual(writes, { value: 0, min: 0, max: 0 });
  c.selectDate(day(80)); f.flush(); assert.deepEqual(writes, { value: 1, min: 0, max: 0 });
  c.configure(rows(301), 'two', { assetIdentity: 'same' }); f.flush();
  assert.deepEqual(writes, { value: 1, min: 0, max: 1 });
  assert.equal(date.value, day(80)); assert.equal(date.max, day(300)); c.dispose();
});

test('selected actual date survives every viewport gesture, leave and same-asset version refresh', () => {
  const c = createAssetChartController(); const metadata = { frequency: 'daily', assetIdentity: { code: '603986.SH', type: 'stock' } };
  c.configure(rows(300), 'dataset-v1', metadata); c.select(180);
  const selected = c.getState().selectedDate; c.pan(100); c.zoom(.5); c.handle({ type: 'mouseleave' }); c.cancel();
  assert.equal(c.getState().selectedDate, selected); assert.equal(c.getState().activeIndex, 180);
  assert.equal(c.getState().selectedOutsideView, true);
  c.handle(click('period-week')); assert.equal(c.getState().selectedDate, selected);
  c.handle(click('period-month')); assert.equal(c.getState().selectedDate, selected);
  c.configure(rows(305), 'dataset-v2', metadata); assert.equal(c.getState().selectedDate, selected);
  c.handle(click('locate')); assert.equal(c.getState().selectedOutsideView, false);
  c.handle(click('latest')); assert.equal(c.getState().selectedDate, day(304));
});

test('recent 120 resets only the viewport while latest explicitly selects the last trade day', () => {
  const f = fakeDOM(); const c = createAssetChartController();
  c.configure(rows(300), 'one', { asset_history: { chip_inputs: chipInputs } }); c.mount(f.node); c.select(80); f.flush();
  const points = f.instances[1].option.series[0].data; const stats = f.nodes.get('[data-asset-chip-stats]').innerHTML;
  const readout = f.nodes.get('[data-asset-history]').innerHTML;
  assert.equal(points.length, 180);
  c.zoom(.5); c.pan(1000); f.flush();
  assert.equal(c.getState().end - c.getState().start, 60);
  c.handle(click('reset')); f.flush();
  const state = c.getState();
  assert.equal(state.start, 180); assert.equal(state.end, 300);
  assert.equal(state.selectedDate, day(80)); assert.equal(state.activeIndex, 80);
  assert.equal(state.selectedOutsideView, true);
  assert.deepEqual(f.instances[1].option.series[0].data, points);
  assert.equal(f.nodes.get('[data-asset-chip-stats]').innerHTML, stats);
  assert.equal(f.nodes.get('[data-asset-history]').innerHTML, readout);
  assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(`${day(0)}.*${day(80)}`));
  c.handle(click('latest')); f.flush();
  assert.equal(c.getState().selectedDate, day(299)); assert.equal(c.getState().activeIndex, 299);
  assert.equal(c.getState().start, 180); assert.equal(c.getState().end, 300);
  assert.equal(c.getState().selectedOutsideView, false);
  assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(299)));
  c.dispose();
});

for (const period of ['week', 'month']) {
  test(`recent 120 preserves an actual trade day and its ${period} aggregate index`, () => {
    const input = rows(900).filter(bar => ![0, 6].includes(new Date(`${bar.date}T00:00:00Z`).getUTCDay()));
    const c = createAssetChartController(); c.configure(input, 'one');
    c.selectDate(day(14)); c.handle(click(`period-${period}`));
    const aggregated = aggregateMarketBars(enrichMarketBars(input), period);
    const selected = c.getState();
    assert.notEqual(selected.selectedDate, aggregated[selected.activeIndex].source_end_date);
    c.zoom(.5); c.pan(-1000); c.reset();
    assert.equal(c.getState().selectedDate, day(14)); assert.equal(c.getState().activeIndex, selected.activeIndex);
    assert.equal(c.getState().start, Math.max(0, aggregated.length - 120));
    assert.equal(c.getState().end, aggregated.length);
    c.handle(click('latest'));
    assert.equal(c.getState().selectedDate, input.at(-1).date);
    assert.equal(c.getState().activeIndex, aggregated.length - 1);
    assert.equal(c.getState().selectedOutsideView, false);
  });
}

test('daily cumulative chip statistics remain identical after zoom, overlays and period changes', () => {
  const f = fakeDOM(); const c = createAssetChartController();
  c.configure(rows(300), 'version-one', { assetIdentity: '603986.SH:stock', asset_history: { canonical_version: 'v1', factor_version: 'f1', chip_inputs: chipInputs, adjustment: 'qfq' } });
  c.mount(f.node); c.select(180); f.flush();
  const points = f.instances[1].option.series[0].data; const stats = f.nodes.get('[data-asset-chip-stats]').innerHTML;
  assert.equal(points.length, 180); assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(`${day(0)}.*${day(180)}`));
  for (const action of ['zoom-in', 'pan-forward', 'reset', 'overlay-boll', 'period-week', 'period-month', 'period-day']) {
    c.handle(click(action)); f.flush();
    assert.equal(c.getState().selectedDate, day(180));
    assert.deepEqual(f.instances[1].option.series[0].data, points, action);
    assert.equal(f.nodes.get('[data-asset-chip-stats]').innerHTML, stats, action);
  }
  c.dispose();
});

test('all-history requests are real jobs and reaching the loaded left edge requests older only once', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => requests.push(request) });
  const metadata = { assetIdentity: 'one', canLoadHistory: true, asset_history: { coverage: { complete: false }, canonical_version: 'v1', adjustment: 'qfq' } };
  c.configure(rows(300), 'v1', metadata); assert.equal(requests.length, 0);
  c.pan(-1000); c.pan(-1000); assert.deepEqual(requests, [{ action: 'load', scope: 'older', adjustment: 'qfq' }]);
  c.configure(rows(301), 'v2', { ...metadata, historyJob: { status: 'completed' } });
  c.handle(click('all')); assert.equal(requests.at(-1).scope, 'all');
  c.handle(click('history-cancel')); assert.equal(requests.at(-1).action, 'cancel');
});

test('requested adjustment never renames the visible canonical dataset before atomic configure', () => {
  const requests = []; const f = fakeDOM(); const c = createAssetChartController({ onHistoryRequest: request => requests.push(request) });
  const metadata = { assetIdentity: 'one', canLoadHistory: true, adjustment: 'qfq', asset_history: { canonical_version: 'v1', factor_version: 'f1', chip_inputs: chipInputs, adjustment: 'qfq', anchor_verified: true } };
  c.configure(rows(200), 'v1', metadata); c.mount(f.node); f.flush();
  const before = f.instances[1].option.series[0].data;
  c.handle({ type: 'change', target: { value: 'hfq', matches: selector => selector === '[data-asset-chart-adjustment]' } }); f.flush();
  assert.equal(c.getState().adjustment, 'qfq'); assert.equal(c.getState().requestedAdjustment, 'hfq');
  assert.equal(requests[0].adjustment, 'hfq'); assert.deepEqual(f.instances[1].option.series[0].data, before);
  assert.match(renderMarketTerminal(rows(200), c.getState(), metadata), /正在生成后复权，当前仍显示前复权原版本/);
  c.configure(rows(200, i => 200 + i), 'v2', { ...metadata, asset_history: { ...metadata.asset_history, canonical_version: 'v2', adjustment: 'hfq' }, adjustment: 'hfq' }); f.flush();
  assert.equal(c.getState().adjustment, 'hfq'); assert.equal(c.getState().requestedAdjustment, null);
  assert.notDeepEqual(f.instances[1].option.series[0].data, before); c.dispose();
});

for (const failure of ['false', 'throw', 'reject', 'resolved-false']) {
  test(`left-edge loading can be requested again after callback ${failure}`, async () => {
    const requests = []; const errors = [];
    const c = createAssetChartController({ logger: code => errors.push(code), onHistoryRequest: request => {
      requests.push(request);
      if (requests.length > 1) return true;
      if (failure === 'throw') throw new Error('submission failed');
      if (failure === 'reject') return Promise.reject(new Error('submission failed'));
      return failure === 'resolved-false' ? Promise.resolve(false) : false;
    } });
    c.configure(rows(300), 'v1', { assetIdentity: 'one', canLoadHistory: true, asset_history: { canonical_version: 'v1', adjustment: 'qfq' } });
    c.pan(-1000); await Promise.resolve();
    assert.equal(c.getState().historyRequestPending, false);
    c.pan(-1);
    assert.equal(requests.length, 2);
    assert.equal(requests[1].adjustment, 'qfq');
    assert.equal(errors.length, ['throw', 'reject'].includes(failure) ? 1 : 0);
  });
}

test('server-required rebuild hides and rejects retry without changing loaded data', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return true; } });
  c.configure(rows(300), 'v1', { assetIdentity: 'one', canLoadHistory: true,
    asset_history: { canonical_version: 'v1', adjustment: 'qfq' },
    historyJob: { state: 'failed', retryable: false, failure_code: 'history_factor_version_changed' } });
  assert.equal(c.handle(click('history-retry')), false);
  assert.equal(requests.length, 0);
  assert.equal(c.getState().adjustment, 'qfq');
});

test('the first older request from a legacy snapshot builds a separate recent canonical version', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return true; } });
  const input = rows(10);
  c.configure(input, 'legacy', { assetIdentity: 'one', canLoadHistory: true, adjustment: 'qfq' });
  c.pan(-1);
  assert.deepEqual(requests, [{ action: 'load', scope: 'recent', adjustment: 'qfq' }]);
  assert.equal(c.getState().selectedDate, input.at(-1).date);
  assert.equal(c.getState().adjustment, 'qfq');
  c.configure(rows(300), 'canonical', { assetIdentity: 'one', canLoadHistory: true,
    asset_history: { canonical_version: 'v1', adjustment: 'qfq', coverage: { full_history: false } } });
  c.pan(-1000);
  assert.deepEqual(requests.at(-1), { action: 'load', scope: 'older', adjustment: 'qfq' });
});

test('a failed factor version can rebuild full history while the prior complete snapshot stays readable', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return true; } });
  c.configure(rows(300), 'v1', { assetIdentity: 'one', canLoadHistory: true,
    asset_history: { canonical_version: 'v1', adjustment: 'qfq', coverage: { full_history: true } },
    historyJob: { state: 'failed', retryable: false, failure_code: 'history_factor_version_changed' } });
  assert.equal(c.handle(click('all')), true);
  assert.deepEqual(requests, [{ action: 'load', scope: 'all', adjustment: 'qfq' }]);
  assert.equal(c.getState().adjustment, 'qfq');
  assert.equal(c.getState().selectedDate, rows(300).at(-1).date);
});

test('cancelled adjustment does not change the basis of a new older request; explicit retry retains its target', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => { requests.push(request); return true; } });
  const input = rows(300); const metadata = { assetIdentity: 'one', canLoadHistory: true, asset_history: { canonical_version: 'v1', adjustment: 'qfq' } };
  c.configure(input, 'v1', metadata);
  c.handle({ type: 'change', target: { value: 'hfq', matches: selector => selector === '[data-asset-chart-adjustment]' } });
  c.configure(input, 'v1', { ...metadata, historyJob: { state: 'running', scope: 'recent', adjustment: 'hfq' } });
  c.handle(click('history-cancel'));
  const cancelled = { ...metadata, historyJob: { state: 'cancelled', scope: 'recent', adjustment: 'hfq', retryable: true } };
  c.configure(input, 'v1', cancelled);
  assert.equal(c.getState().adjustment, 'qfq');
  assert.equal(c.getState().requestedAdjustment, null);
  c.handle(click('history-retry'));
  assert.deepEqual(requests.at(-1), { action: 'retry', scope: 'recent', adjustment: 'hfq' });
  c.configure(input, 'v1', { ...cancelled });
  c.pan(-1000);
  assert.deepEqual(requests.at(-1), { action: 'load', scope: 'older', adjustment: 'qfq', source: 'tinysoft', includeChipInputs: true });
});

test('atomic canonical metadata updates the displayed basis while the history job is still running', () => {
  const c = createAssetChartController({ onHistoryRequest: () => true });
  const metadata = { assetIdentity: 'one', canLoadHistory: true, asset_history: { canonical_version: 'v1', adjustment: 'qfq' } };
  c.configure(rows(200), 'v1', metadata);
  c.handle({ type: 'change', target: { value: 'hfq', matches: selector => selector === '[data-asset-chart-adjustment]' } });
  c.configure(rows(200, i => 200 + i), 'v2', { ...metadata, asset_history: { canonical_version: 'v2', adjustment: 'hfq' }, historyJob: { state: 'running', scope: 'recent', adjustment: 'hfq' } });
  assert.equal(c.getState().adjustment, 'hfq');
  assert.equal(c.getState().requestedAdjustment, null);
});

test('weekly/monthly bar selection uses its last actual trade day and prepend preserves viewport dates', () => {
  const input = rows(300).filter((bar, index) => ![0, 6].includes(new Date(`${bar.date}T00:00:00Z`).getUTCDay()));
  const c = createAssetChartController(); const metadata = { assetIdentity: 'same', frequency: 'daily' };
  c.configure(input.slice(40), 'v1', metadata); c.select(80);
  const previous = c.getState(); const startDate = input.slice(40)[previous.start].date; const endDate = input.slice(40)[previous.end - 1].date;
  c.configure(input, 'v2', metadata); const after = c.getState();
  assert.equal(after.selectedDate, previous.selectedDate); assert.equal(input[after.start].date, startDate); assert.equal(input[after.end - 1].date, endDate);
  c.handle(click('period-week')); c.select(3); const weekly = aggregateMarketBars(enrichMarketBars(input), 'week');
  assert.equal(c.getState().selectedDate, weekly[3].source_end_date);
  c.handle(click('period-month')); c.select(1); const monthly = aggregateMarketBars(enrichMarketBars(input), 'month');
  assert.equal(c.getState().selectedDate, monthly[1].source_end_date);
});

test('programmatic initialization never requests history; wheel/drag axis updates never select another date', () => {
  const f = fakeDOM(); const requests = []; const c = createAssetChartController({ onHistoryRequest: request => requests.push(request) });
  c.configure(rows(300), 'v1', { assetIdentity: 'same', canLoadHistory: true }); c.mount(f.node); f.flush();
  assert.deepEqual(requests, []); c.select(180); f.flush(); const chart = f.instances[0];
  chart.zrEvents.get('mousewheel')({});
  chart.events.get('updateAxisPointer')({ axesInfo: [{ axisDim: 'x', axisIndex: 0, value: 200 }] });
  chart.events.get('dataZoom')({ startValue: 200, endValue: 250 }); f.flush();
  assert.equal(c.getState().selectedDate, day(180));
  chart.zrEvents.get('mousedown')({}); chart.zrEvents.get('mousemove')({ event: { buttons: 1 } });
  chart.events.get('updateAxisPointer')({ axesInfo: [{ axisDim: 'x', axisIndex: 2, value: 220 }] });
  assert.equal(c.getState().selectedDate, day(180)); chart.zrEvents.get('mouseup')({}); chart.zrEvents.get('mousemove')({});
  chart.events.get('updateAxisPointer')({ axesInfo: [{ axisDim: 'x', axisIndex: 2, value: 220 }] });
  assert.equal(c.getState().selectedDate, day(220)); c.dispose();
});

test('canonical job metadata distinguishes completed recent coverage from full history and renders real chunk progress', () => {
  const metadata = { canLoadHistory: true, adjustment: 'qfq', asset_history: { canonical_version: 'asset-history-1', factor_version: 'f1', anchor_date: day(299), adjustment: 'qfq', coverage: { complete: true, full_history: false, scope: 'recent', actual_range: { start_date: day(0), end_date: day(299) }, boundary_verified: false } }, historyJob: { status: 'running', progress: { chunks_completed: 2, chunks_total: 4, rows: 300 } } };
  const html = renderMarketTerminal(rows(300), {}, metadata);
  assert.match(html, /加载历史 50% · 300条/);
  assert.doesNotMatch(html, /全部历史已加载|全部已加载/);
  const requests = []; const c = createAssetChartController({ onHistoryRequest: request => requests.push(request) });
  c.configure(rows(300), 'v1', { ...metadata, historyJob: { status: 'cancelled', retryable: true, scope: 'older' } });
  c.handle(click('history-retry')); assert.equal(requests[0].scope, 'older'); assert.equal(requests[0].action, 'retry');
});

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
  const input = rows(1); delete input[0].vwap; assert.equal(enrichMarketBars(input)[0].vwap, null);
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

test('terminal retains whole overlays and panels while removing redundant controls', () => {
  const html = renderMarketTerminal(rows(150), {}, { currency: 'CNY', adjustment: '前复权', frequency: 'daily' });
  assert.match(html, /kline-terminal-layout/); assert.match(html, /data-asset-echarts/); assert.match(html, /data-asset-chip-chart/); assert.doesNotMatch(html, /<svg/);
  assert.doesNotMatch(html, /data-asset-chart-action="(?:ma-\d+|pan-back|pan-forward|zoom-in|zoom-out|reset|all)"|asset-date-controls|data-asset-history-source/);
  for (const action of ['period-day', 'period-week', 'period-month', 'overlay-boll', 'overlay-none']) assert.ok(html.includes(`data-asset-chart-action="${action}"`));
  assert.doesNotMatch(html, /分时<\/button>/); assert.match(html, /估算/); assert.match(html, /不代表实际持仓/); assert.match(html, /前复权/);
});

test('historical change and amplitude use previous close and metadata is escaped', () => {
  const html = renderMarketTerminal([{ ...rows(1)[0], close: 100 }, { ...rows(1)[0], date: day(1), open: 105, close: 110, low: 100, high: 120 }], {}, { dataset: '<img src=x>', currency: 'CNY' });
  assert.match(html, /10\.00%/); assert.match(html, /20\.00%/); assert.doesNotMatch(html, /<img src=x>/); assert.match(html, /asset-history-date/);
});

test('historical readout retains change amount and average-price slots without guessing units', () => {
  const input = [{ ...rows(1)[0], close: 100 }, { ...rows(1)[0], date: day(1), open: 105, close: 110, low: 100, high: 120, amount: 999000, volume: 3 }];
  for (const b of input) delete b.vwap;
  const missing = renderMarketTerminal(input);
  assert.match(missing, /涨跌额 <strong>\+10\.00<\/strong>/);
  assert.match(missing, /均价 <strong>—<\/strong>/);
  for (const key of ['vwap', 'avg_price', 'average_price']) {
    const source = [{ ...input[1], [key]: 108.25 }];
    assert.equal(enrichMarketBars(source)[0].vwap, 108.25);
    assert.match(renderMarketTerminal(source), /均价 <strong>108\.25<\/strong>/);
  }
  assert.match(renderMarketTerminal([input[0]]), /涨跌额 <strong>—<\/strong>/);
});

test('price axes format floating-point ticks to readable two-decimal prices', () => {
  const option = buildMarketChartOption(enrichMarketBars(rows(30)));
  assert.equal(option.yAxis[0].axisLabel.formatter(129.99999996), '130.00');
  assert.equal(option.yAxis[0].axisPointer.label.formatter({ value: 129.99999996 }), '130.00');
  const chip = estimateChipDistribution(enrichMarketBars(rows(10)), 0, 9);
  assert.equal(buildChipChartOption(chip, [90, 130]).yAxis.axisLabel.show, false, 'chip prices share the main price axis');
});

test('confirmed share/currency units are translated and unknown units remain source units', () => {
  for (const unit of ['share', 'shares']) {
    const html = renderMarketTerminal(rows(2), {}, { fields: { volume: { unit }, turnover: { unit: 'currency', currency: 'CNY' } } });
    assert.match(html, /成交量 <strong>0\.10万股/); assert.match(html, /成交额 <strong>10\.00万元/); assert.doesNotMatch(html, /万shares|万currency/);
  }
  const foreign = renderMarketTerminal(rows(2), {}, { fields: { volume: { unit: 'shares' }, amount: { unit: 'currency', currency: 'USD' } } });
  assert.match(foreign, /成交额 <strong>10\.00万美元/); assert.doesNotMatch(foreign, /成交额 <strong>10\.00万元/);
  assert.match(renderMarketTerminal(rows(2), {}, { fields: { amount: { unit: 'currency' } } }), /成交额 <strong>10\.00万<\/strong>/);
  assert.match(renderMarketTerminal(rows(2)), /成交量 <strong>0\.10万<\/strong>/);
});

test('aggregated week/month turnover rate cannot reuse the final day percentage as a whole-period fact', () => {
  const daily = rows(5).map(b => ({ ...b, turnover_rate_pct: 1 }));
  assert.equal(aggregateMarketBars(enrichMarketBars(daily), 'week')[0].turnover_rate_pct, null);
  assert.equal(aggregateMarketBars(enrichMarketBars(daily), 'month')[0].turnover_rate_pct, null);
  const html = renderMarketTerminal(daily, { period: 'week' }, { frequency: 'daily' });
  assert.match(html, /换手率 <strong>1\.00%<\/strong>/, 'historical quote explicitly follows the selected actual daily record');
});

test('five ECharts grids, cross-panel pointer, two linked zooms, all six MA and no volume MA series', () => {
  const bars = enrichMarketBars(rows(260)); const option = buildMarketChartOption(bars, { start: 140, end: 260, panels: ['volume', 'macd', 'kdj', 'rsi'], overlay: 'ma', enabledMA: [5, 10, 20, 60, 120, 250] });
  assert.equal(option.grid.length, 5); assert.equal(option.grid[0].height, 300); assert.equal(option.grid[4].top, 654);
  assert.equal(option.axisPointer.link[0].xAxisIndex, 'all'); assert.equal(option.dataZoom.length, 2);
  for (const zoom of option.dataZoom) { assert.deepEqual(zoom.xAxisIndex, [0, 1, 2, 3, 4]); assert.equal(zoom.startValue, 140); assert.equal(zoom.endValue, 259); }
  assert.equal(option.series.filter(s => /^MA\d+$/.test(s.name)).length, 6); assert.equal(option.series.some(s => /^VOLMA/.test(s.name)), false);
  assert.match(option.graphic[0].style.text, /VOL:.*MA5:.*MA10:/); assert.equal(option.series[0].data.length, 260);
});

test('both terminal canvases are transparent and explicit themes keep neutral labels readable', () => {
  const bars = enrichMarketBars(rows(260)); const chip = estimateChipDistribution(bars, 140, 259);
  const state = { start: 140, end: 260, overlay: 'ma', panels: ['volume', 'macd', 'kdj', 'rsi'] };
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
    assert.equal(chips.xAxis.axisLabel.show, false); assert.equal(chips.yAxis.axisLabel.show, false);
    assert.equal(option.series.at(-1).markLine.label.color, muted);
    assert.equal(chips.series[0].markLine.label.color, text);
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
  const option = buildMarketChartOption(bars, { start: 0, end: 100, panels: ['volume', 'macd', 'kdj', 'rsi'] });
  assert.ok(option.yAxis[3].min <= Math.min(...values)); assert.ok(option.yAxis[3].max >= Math.max(...values));
  assert.equal(option.yAxis[4].min, 0); assert.equal(option.yAxis[4].max, 100);
});

test('180 probability buckets conserve turnover mass without old volume quantization', () => {
  const source = rows(5, () => 10).map(b => ({ ...b, open: 10, low: 8, high: 12, close: 10, volume: 100 }));
  const chip = estimateChipDistribution(enrichMarketBars(source), 0, 4);
  assert.equal(chip.status, 'ready'); assert.equal(chip.points.length, 180);
  near(chip.points.reduce((sum, point) => sum + point.mass, 0), 1);
  near(chip.averageCost, 10); near(chip.profitFraction, .5);
  near(chip.peak, 10); near(chip.peakLower, 9); near(chip.peakUpper, 11);
  const option = buildChipChartOption(chip, [8, 12]); assert.equal(option.yAxis.min, 8); assert.equal(option.yAxis.max, 12);
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

test('flat candles keep exact-price mass and configurable peak bounds', () => {
  const flat = rows(5, () => 10).map(b => ({ ...b, open: 10, low: 10, high: 10, volume: 100 }));
  const chip = estimateChipDistribution(enrichMarketBars(flat), 0, 4);
  assert.equal(chip.status, 'ready'); near(chip.peak, 10); near(chip.averageCost, 10);
  near(chip.atCostFraction, 1); near(chip.profitFraction, 0); near(chip.lockedFraction, 0);
  near(chip.peakLower, 9); near(chip.peakUpper, 11);
});

test('configure never triggers outer render and controls retain independent MA choices', () => {
  let changes = 0; const c = createAssetChartController({ onChange: () => changes++ }); c.configure(rows(260), 'one', { asset_history: { coverage: { complete: true } } });
  assert.equal(changes, 0); assert.equal(c.getState().start, 140); assert.equal(c.getState().activeIndex, 259);
  c.handle(click('ma-60')); assert.equal(c.getState().enabledMA.includes(60), false); assert.equal(c.getState().enabledMA.includes(120), true);
  c.handle(click('overlay-boll')); assert.equal(c.getState().overlay, 'boll'); c.handle(click('overlay-ma')); assert.equal(c.getState().enabledMA.includes(60), false);
  c.handle(click('all')); assert.equal(c.getState().start, 0); assert.equal(c.getState().end, 260); assert.equal(changes, 4);
});

test('weekly/monthly controls recompute, legacy weekly inputs never masquerade as day', () => {
  const c = createAssetChartController(); c.configure(rows(300), 'one'); c.handle(click('period-week')); assert.equal(c.getState().period, 'week'); assert.ok(c.getState().end < 50);
  c.handle(click('period-month')); assert.equal(c.getState().end, 10); c.configure(rows(20), 'legacy', { frequency: 'weekly' });
  assert.equal(c.getState().period, 'week'); assert.equal(c.handle(click('period-day')), false);
  assert.match(renderMarketTerminal(rows(20), c.getState(), { frequency: 'weekly' }), /周K/);
});

test('refresh preserves viewport dates and selected actual day; empty/cancel/dispose safe', () => {
  const c = createAssetChartController(); c.configure(rows(200), 'one'); c.configure(rows(202), 'one'); assert.equal(c.getState().end, 200); assert.equal(c.getState().selectedDate, day(199));
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
  for (const selector of ['[data-asset-echarts]', '[data-asset-chip-chart]', '[data-asset-history]', '[data-asset-overlay-label]', '[data-asset-chip-stats]', '[data-asset-chip-window]', '[data-asset-range-summary]', '[data-asset-chart-metadata]', '.kline-terminal-layout', '.asset-chip-panel']) nodes.set(selector, { ...node, dataset: {} });
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
  assert.equal(f.instances[5].option.yAxis.axisLine.show, false);
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
  f.handlers.get('mouseleave')?.(); f.flush(); assert.equal(c.getState().activeIndex, 120);
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
  assert.equal(c.getState().activeIndex, 110); assert.match(f.nodes.get('[data-asset-history]').innerHTML, new RegExp(day(110)));
  assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(110)));
  assert.equal(f.instances[0].option.graphic[0].style.text.includes('0.11万'), true);
  f.handlers.get('mouseleave')(); f.flush(); assert.equal(c.getState().activeIndex, 110);
  assert.match(f.nodes.get('[data-asset-history]').innerHTML, new RegExp(day(110))); c.dispose();
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
  c.configure(input, 'one', {}, { panels: ['volume', 'macd', 'kdj', 'rsi'] }); c.mount(f.node); f.flush(); const chart = f.instances[0];
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
  assert.equal(f.instances.length, 2); assert.match(f.nodes.get('[data-asset-chart-metadata]').textContent, /日线 · 前复权/); c.dispose();
});

test('real pinned ECharts retains candle bodies above 600 rows with only 120 visible bars', () => {
  const timers = new Set();
  const runtime = { console, clearTimeout, setTimeout: (callback, delay) => { const timer = setTimeout(callback, delay); timers.add(timer); return timer; } };
  runInNewContext(readFileSync(new URL('../../app/research_web/ui/vendor/echarts-5.5.0.min.js', import.meta.url), 'utf8'), runtime);
  const chart = runtime.echarts.init(null, null, { renderer: 'svg', ssr: true, width: 1000, height: 400 });
  try {
    chart.setOption(buildMarketChartOption(enrichMarketBars(rows(2261)), { start: 2141, end: 2261, panels: [] }));
    const model = chart.getModel().getSeriesByType('candlestick')[0]; const data = model.getData();
    assert.equal(data.count(), 2261);
    assert.equal(chart.getOption().dataZoom[0].startValue, 2141);
    assert.equal(chart.getOption().dataZoom[0].endValue, 2260);
    for (const index of [2142, 2200, 2259]) {
      const candle = data.getItemGraphicEl(index);
      assert.ok(candle, `visible candle ${index} must have a body graphic (large=${model.pipelineContext.large})`);
      const body = candle.shape.points.slice(0, 4);
      assert.ok(Math.max(...body.map(point => point[0])) > Math.min(...body.map(point => point[0])), 'candle body must have positive width');
      assert.ok(Math.max(...body.map(point => point[1])) > Math.min(...body.map(point => point[1])), 'unequal open/close must have positive body height');
    }
  } finally { chart.dispose(); for (const timer of timers) clearTimeout(timer); }
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
    assert.equal(series.length, 10 + c.getState().panels.reduce((sum, id) => sum + ({ volume: 1, macd: 3, kdj: 3, rsi: 1 })[id], 0));
    assert.ok(series.every(model => charts.at(-2).getViewOfSeriesModel(model)), 'every series must have an actual ECharts view');
  };
  try {
    c.configure(rows(320), 'one');
    for (const mode of ['dark', 'light', 'dark']) {
      const palette = pageTheme(f, mode); c.handle(click('latest')); c.mount(f.node); f.flush(); viewsAreReady();
      assert.equal(charts.at(-2).getOption().backgroundColor, 'transparent');
      assert.equal(charts.at(-1).getOption().backgroundColor, 'transparent');
      assert.equal(charts.at(-2).getOption().xAxis[0].axisLabel.color, palette['--muted']);
      for (const action of ['ma-250', 'ma-250', 'overlay-boll', 'overlay-none', 'overlay-ma', 'period-week', 'period-month', 'period-day', 'all', 'reset', 'latest']) {
        c.cancel(); c.handle(click(action)); f.flush(); viewsAreReady();
      }
      c.handle({ type: 'keydown', key: 'ArrowLeft', target: { closest: () => ({}) } }); f.flush();
      assert.equal(c.getState().activeIndex, 318);
      assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(318)));
      charts.at(-2).dispatchAction({ type: 'dataZoom', startValue: 200, endValue: 279 }); f.flush(); viewsAreReady();
      assert.equal(c.getState().start, 200); assert.equal(c.getState().end, 280);
      c.select(250); f.flush(); c.cancel(); viewsAreReady();
      assert.equal(c.getState().activeIndex, 250);
      assert.match(f.nodes.get('[data-asset-chip-window]').textContent, new RegExp(day(250)));
    }
  } finally { c.dispose(); for (const timer of timers) clearTimeout(timer); }
});

test('real ECharts price and chip coordinates align globally within one pixel at three prices and sizes', () => {
  const timers = new Set();
  const runtime = { console, clearTimeout, setTimeout: (callback, delay) => { const timer = setTimeout(callback, delay); timers.add(timer); return timer; } };
  runInNewContext(readFileSync(new URL('../../app/research_web/ui/vendor/echarts-5.5.0.min.js', import.meta.url), 'utf8'), runtime);
  try {
    for (const [width, height, panels] of [[800, 480, []], [1200, 690, ['volume', 'macd']], [1600, 900, ['rsi', 'kdj', 'volume', 'macd']]]) {
      const f = fakeDOM(); const charts = []; const errors = []; const variables = new Map(); const chartTop = 117;
      f.nodes.get('[data-asset-echarts]').getBoundingClientRect = () => ({ top: chartTop, left: 0, width, height });
      f.nodes.get('.asset-chip-panel').getBoundingClientRect = () => ({ top: 83, left: width + 12, width: 200, height });
      f.nodes.get('.asset-chip-panel').style = { setProperty: (name, value) => variables.set(name, value) };
      f.node.ownerDocument.defaultView.echarts = { ...runtime.echarts, init: node => {
        const chart = runtime.echarts.init(null, null, { renderer: 'svg', ssr: true, width: node === f.nodes.get('[data-asset-echarts]') ? width : 200, height }); charts.push(chart); return chart;
      } };
      const c = createAssetChartController({ logger: code => errors.push(code) });
      try {
        c.configure(rows(300), 'one', {}, { panels }); c.mount(f.node); f.flush(); assert.deepEqual(errors, []);
        const axis = charts[0].getOption().yAxis[0]; const chipTop = 83 + parseFloat(variables.get('--chip-plot-top'));
        assert.equal(parseFloat(variables.get('--chip-plot-height')), 300);
        for (const price of [axis.min, (axis.min + axis.max) / 2, axis.max]) {
          const mainY = chartTop + charts[0].convertToPixel({ yAxisIndex: 0 }, price);
          const chipY = chipTop + charts[1].convertToPixel({ yAxisIndex: 0 }, price);
          assert.ok(Math.abs(mainY - chipY) <= 1, `${width}px ${panels.length} panels ${price}: ${mainY}/${chipY}`);
        }
      } finally { c.dispose(); }
    }
  } finally { for (const timer of timers) clearTimeout(timer); }
});


test('source control explicitly selects raw auto while retry preserves frozen source', () => {
  const requests = []; const c = createAssetChartController({ onHistoryRequest: value => { requests.push(value); return false; } });
  c.configure(rows(50), 'old', { canLoadHistory: true, historySource: 'tinysoft', adjustment: 'none', historyJob: { id: 'failed', state: 'failed', retryable: true, scope: 'recent', adjustment: 'none', source: 'baostock' } });
  assert.doesNotMatch(renderMarketTerminal(rows(50), c.getState(), { canLoadHistory: true, historySource: 'tinysoft' }), /data-asset-history-source/);
  c.handle({ type: 'change', target: { value: 'auto', matches: selector => selector === '[data-asset-history-source]' } });
  assert.deepEqual(requests[0], { action: 'load', scope: 'recent', adjustment: 'none', source: 'auto' });
  c.handle(click('history-retry'));
  assert.equal(requests.at(-1).source, 'baostock');
});
