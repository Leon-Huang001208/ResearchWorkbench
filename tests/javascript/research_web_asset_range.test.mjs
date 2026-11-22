import assert from 'node:assert/strict';
import test from 'node:test';
import { calculateRangeStatistics } from '../../app/research_web/ui/asset-range-statistics.mjs';

const bar = (date, overrides = {}) => ({ date, open: 100, high: 110, low: 90, close: 100, volume: 100, amount: 10000, turnover_rate_pct: 1, ...overrides });
const priceField = { unit: 'currency_per_share', currency: 'CNY' };
const metadata = (overrides = {}) => ({ frequency: 'daily', fields: { open: { ...priceField }, high: { ...priceField }, low: { ...priceField }, close: { ...priceField }, volume: { unit: 'shares' }, amount: { unit: 'CNY' }, turnover_rate_pct: { unit: 'percent' } }, asset_history: { canonical_version: 'test-v1', adjustment: 'none', coverage: { scanned_ranges: [{ start_date: '2026-01-01', end_date: '2026-03-31' }] } }, ...overrides });
const select = { startDate: '2026-02-01', endDate: '2026-03-31' };
const near = (actual, expected) => assert.ok(Math.abs(actual - expected) < 1e-8, `${actual} != ${expected}`);
const unknown = metric => { assert.equal(metric.status, 'unknown'); assert.equal(metric.value, null); assert.ok(metric.reason); };

test('32-day screenshot formulas use prior close and extrema, with complete metric descriptors', () => {
  const daily = [bar('2026-01-31', { open: 463.15, close: 463.15, high: 464, low: 460 }), ...Array.from({ length: 32 }, (_, i) => bar(new Date(Date.UTC(2026, 1, i + 1)).toISOString().slice(0, 10), { open: 400, close: i === 31 ? 393 : 400, high: i === 0 ? 501.26 : 450, low: i === 31 ? 337.10 : 380 }))];
  const result = calculateRangeStatistics(daily, select, metadata()); const m = result.metrics;
  assert.equal(result.range.count, 32); near(m.previousClose.value, 463.15);
  near(m.changePct.value, (393 / 463.15 - 1) * 100); near(m.changeAmount.value, 393 - 463.15);
  near(m.annualizedPct.value, ((393 / 463.15) ** (250 / 32) - 1) * 100);
  near(m.maxDrawdownPct.value, (337.10 / 501.26 - 1) * 100); near(m.maxRisePct.value, (501.26 / 337.10 - 1) * 100);
  near(m.amplitudePct.value, (501.26 - 337.10) / 463.15 * 100);
  assert.match(m.maxDrawdownPct.definition, /极值/); assert.match(m.previousClose.definition, /非交易所/);
  for (const metric of Object.values(m)) for (const key of ['value', 'unit', 'status', 'reason', 'definition']) assert.ok(Object.hasOwn(metric, key));
  unknown(m.industryComparisonPct); assert.equal(result.provenance.canonicalVersion, 'test-v1'); assert.equal(result.provenance.adjustment, 'none');
});

test('reverse dates, cross-month ranges, and boundaries map to actual daily bars without mutation', () => {
  const daily = [bar('2026-01-30'), bar('2026-02-02'), bar('2026-02-03')]; const before = JSON.stringify(daily);
  const result = calculateRangeStatistics(daily, { startDate: '2026-02-28', endDate: '2026-01-31' }, metadata());
  const { coverage, ...range } = result.range;
  assert.deepEqual(range, { requestedStart: '2026-01-31', requestedEnd: '2026-02-28', startDate: '2026-02-02', endDate: '2026-02-03', count: 2 });
  assert.equal(coverage.countBasis, 'loaded_daily_rows');
  assert.equal(result.metrics.previousClose.value, 100); assert.equal(JSON.stringify(daily), before);
});

test('single day and genuine zero quantities stay zero, zero-volume mean is unknown', () => {
  const result = calculateRangeStatistics([bar('2026-02-02', { volume: 0, amount: 0, turnover_rate_pct: 0 })], select, metadata());
  for (const id of ['volume', 'amount', 'turnoverPct', 'dailyTurnoverPct', 'upCount', 'downCount', 'maxVolume', 'minVolume']) assert.equal(result.metrics[id].value, 0, id);
  assert.equal(result.metrics.flatCount.value, 1); unknown(result.metrics.meanPrice); unknown(result.metrics.previousClose);
});

test('one missing interval value rejects partial sums and extrema independently', () => {
  const m = calculateRangeStatistics([bar('2026-02-02'), bar('2026-02-03', { volume: null, amount: null, turnover_rate_pct: null })], select, metadata()).metrics;
  for (const id of ['amount', 'volume', 'maxVolume', 'minVolume', 'turnoverPct', 'dailyTurnoverPct', 'meanPrice']) unknown(m[id]);
  assert.equal(m.close.value, 100);
});

test('invalid OHLC and explicit gaps prevent complete direction counts and range extrema', () => {
  for (const changed of [{ high: 80 }, { validOHLC: false }, { gap: true }]) {
    const m = calculateRangeStatistics([bar('2026-02-02'), bar('2026-02-03', changed)], select, metadata()).metrics;
    for (const id of ['upCount', 'downCount', 'flatCount', 'high', 'low', 'maxDrawdownPct', 'maxRisePct']) unknown(m[id]);
  }
});

test('previous close requires coverage of every calendar date between adjacent dataset rows', () => {
  const daily = [bar('2026-01-30'), bar('2026-02-02')];
  for (const history of [{}, { canonical_version: 'v', adjustment: 'none', coverage: { complete: true } }, { canonical_version: 'v', adjustment: 'none', coverage: { scanned_ranges: [{ start_date: '2026-01-01', end_date: '2026-01-30' }, { start_date: '2026-02-02', end_date: '2026-03-31' }] } }]) {
    const m = calculateRangeStatistics(daily, select, metadata({ asset_history: history })).metrics;
    for (const id of ['previousClose', 'changePct', 'changeAmount', 'annualizedPct', 'amplitudePct']) unknown(m[id]);
  }
});

test('gapped preceding bar is never skipped in search of earlier close', () => {
  const m = calculateRangeStatistics([bar('2026-01-29'), bar('2026-01-30', { gap: true }), bar('2026-02-02')], select, metadata()).metrics;
  unknown(m.previousClose);
});

test('adjacent scan segments can establish dataset adjacency without asserting an exchange calendar', () => {
  const meta = metadata(); meta.asset_history.coverage.scanned_ranges = [{ start_date: '2026-01-30', end_date: '2026-01-31' }, { start_date: '2026-02-01', end_date: '2026-02-02' }];
  assert.equal(calculateRangeStatistics([bar('2026-01-30'), bar('2026-02-02')], select, meta).metrics.previousClose.value, 100);
});

test('unit evidence is required, verified native units remain unformatted', () => {
  const daily = [bar('2026-02-02')]; const m = calculateRangeStatistics(daily, select, metadata({ fields: {} })).metrics;
  for (const id of ['volume', 'amount', 'meanPrice', 'turnoverPct']) unknown(m[id]);
  const good = calculateRangeStatistics(daily, select, metadata()).metrics;
  assert.equal(good.volume.unit, 'shares'); assert.equal(good.volume.value, 100); assert.equal(good.amount.unit, 'CNY'); assert.equal(good.meanPrice.value, 100);
});

test('adjusted prices do not imply adjusted traded mean; source provenance stays explicit', () => {
  const meta = metadata(); meta.asset_history.adjustment = 'qfq'; meta.asset_history.factor_version = 'factor-v2';
  const result = calculateRangeStatistics([bar('2026-01-30'), bar('2026-02-02')], select, meta);
  unknown(result.metrics.meanPrice); assert.equal(result.metrics.previousClose.value, 100); assert.equal(result.provenance.factorVersion, 'factor-v2');
});

test('mixed source versions or adjustment rows cannot form same-basis statistics', () => {
  for (const mismatch of [{ canonical_version: 'other' }, { adjustment: 'hfq' }]) {
    const result = calculateRangeStatistics([bar('2026-01-30'), bar('2026-02-02', mismatch)], select, metadata());
    for (const metric of Object.values(result.metrics)) unknown(metric);
    assert.ok(result.diagnostics.includes('range_basis_mismatch'));
  }
});

test('invalid requests, duplicate dates and non-daily inputs return explicit diagnostics', () => {
  for (const [daily, range, meta] of [[null, select, metadata()], [[bar('2026-02-02')], { startDate: '2026-02-31', endDate: '2026-03-01' }, metadata()], [[bar('2026-02-02'), bar('2026-02-02')], select, metadata()], [[bar('2026-02-02')], select, metadata({ frequency: 'weekly' })]]) {
    const result = calculateRangeStatistics(daily, range, meta); assert.ok(result.diagnostics.length); for (const metric of Object.values(result.metrics)) unknown(metric);
  }
});

test('empty interval is explicit and aggregate fields never invent zero observations', () => {
  const result = calculateRangeStatistics([bar('2026-01-01')], select, metadata());
  assert.equal(result.range.count, 0); assert.equal(result.range.startDate, null); for (const metric of Object.values(result.metrics)) unknown(metric);
});

test('verified magnitude units compute original share-weighted mean without formatting raw sums', () => {
  const meta = metadata({ fields: [{ name: 'close', ...priceField }, { name: 'volume', unit: '万股' }, { key: 'amount', unit: '万元' }] });
  const m = calculateRangeStatistics([bar('2026-02-02', { volume: 2, amount: 30 }), bar('2026-02-03', { volume: 1, amount: 15 })], select, meta).metrics;
  assert.equal(m.meanPrice.value, 15); assert.equal(m.volume.value, 3); assert.equal(m.amount.value, 45); assert.equal(m.amount.unit, '万元');
});

test('unknown lot conversion and nonmatching price currency cannot imply a raw price basis', () => {
  const lots = metadata(); lots.fields.volume.unit = '手';
  unknown(calculateRangeStatistics([bar('2026-02-02')], select, lots).metrics.meanPrice);
  unknown(calculateRangeStatistics([bar('2026-02-02')], select, metadata({ currency: 'HKD' })).metrics.meanPrice);
});

test('chip percent contract and enriched numeric strings are accepted without input mutation', () => {
  const meta = metadata({ fields: { close: { ...priceField }, volume: { unit: 'shares' }, amount: { unit: 'CNY' } } });
  meta.asset_history.chip_inputs = { status: 'complete', contract_version: 'chip-turnover-1', turnover_unit: 'percent' };
  const daily = [Object.freeze(bar('2026-02-02', { volume: '100', amount: '10000', turnover_rate_pct: '0', validOHLC: true }))];
  const result = calculateRangeStatistics(Object.freeze(daily), select, meta);
  assert.equal(result.metrics.meanPrice.value, 100); assert.equal(result.metrics.turnoverPct.value, 0);
});

test('overflow and nonnumeric values never escape as infinite, NaN or implicit zero', () => {
  for (const value of [Infinity, NaN, '', 'unknown', -1]) {
    const m = calculateRangeStatistics([bar('2026-02-02', { amount: value })], select, metadata()).metrics;
    unknown(m.amount); unknown(m.meanPrice);
  }
  const result = calculateRangeStatistics([bar('2026-02-02', { amount: 1e308 }), bar('2026-02-03', { amount: 1e308 })], select, metadata());
  unknown(result.metrics.amount); unknown(result.metrics.meanPrice);
});

test('unscanned internal dates reject complete interval statistics while preserving endpoints', () => {
  const meta = metadata(); meta.asset_history.coverage.scanned_ranges = [{ start_date: '2026-01-30', end_date: '2026-02-03' }, { start_date: '2026-02-05', end_date: '2026-02-05' }];
  const result = calculateRangeStatistics([bar('2026-01-30'), bar('2026-02-03'), bar('2026-02-05')], select, meta);
  for (const id of ['amount', 'volume', 'turnoverPct', 'dailyTurnoverPct', 'meanPrice', 'maxVolume', 'minVolume', 'high', 'low', 'maxDrawdownPct', 'maxRisePct', 'amplitudePct', 'upCount', 'downCount', 'flatCount', 'annualizedPct']) unknown(result.metrics[id]);
  assert.equal(result.metrics.close.value, 100); assert.equal(result.metrics.open.value, 100); assert.equal(result.metrics.changePct.value, 0);
  assert.equal(result.range.count, 2); assert.equal(result.range.coverage.scanComplete, false);
  assert.equal(result.range.coverage.expectedCount, 2); assert.equal(result.range.coverage.countBasis, 'loaded_daily_rows');
});

test('every metric exposes coverage and missing input counts stay distinct from unknown calendar dates', () => {
  const result = calculateRangeStatistics([bar('2026-02-02'), bar('2026-02-03', { amount: null })], select, metadata());
  for (const metric of Object.values(result.metrics)) {
    for (const key of ['expectedCount', 'validCount', 'missingCount', 'scanComplete', 'countBasis']) assert.ok(Object.hasOwn(metric.coverage, key), key);
    assert.equal(metric.coverage.expectedCount, metric.coverage.validCount + metric.coverage.missingCount);
    assert.equal(metric.coverage.countBasis, 'loaded_daily_rows');
  }
  assert.deepEqual(result.metrics.amount.coverage, { expectedCount: 2, validCount: 1, missingCount: 1, scanComplete: true, countBasis: 'loaded_daily_rows' });
});

test('missing high never erases independently verified open, close or close-based changes', () => {
  const result = calculateRangeStatistics([bar('2026-01-30', { high: null }), bar('2026-02-02', { high: null, close: 105 })], select, metadata());
  assert.equal(result.metrics.open.value, 100); assert.equal(result.metrics.close.value, 105); assert.equal(result.metrics.previousClose.value, 100);
  near(result.metrics.changePct.value, 5); assert.equal(result.metrics.changeAmount.value, 5);
  unknown(result.metrics.high); unknown(result.metrics.low); unknown(result.metrics.upCount);
});

test('raw mean requires explicit price currency evidence in the real normalized-history field shape', () => {
  const daily = [bar('2026-02-02')];
  const priceFields = Object.fromEntries(['open', 'high', 'low', 'close'].map(key => [key, { unit: 'currency_per_share', currency: 'CNY' }]));
  const meta = metadata(); meta.fields = { ...meta.fields, ...priceFields };
  assert.equal(calculateRangeStatistics(daily, select, meta).metrics.meanPrice.value, 100);
  for (const key of ['open', 'high', 'low', 'close', 'vwap']) {
    const conflicting = metadata(); conflicting.fields = { ...conflicting.fields, ...priceFields, [key]: { unit: 'currency_per_share', currency: 'USD' } };
    unknown(calculateRangeStatistics(daily, select, conflicting).metrics.meanPrice);
  }
  const unverified = metadata(); unverified.fields = { amount: { unit: 'CNY' }, volume: { unit: 'shares' } };
  unknown(calculateRangeStatistics(daily, select, unverified).metrics.meanPrice);
  const conflictingTop = { ...meta, currency: 'USD' };
  unknown(calculateRangeStatistics(daily, select, conflictingTop).metrics.meanPrice);
});

test('amount and volume unit dimensions cannot be interchanged', () => {
  for (const [key, unit] of [['amount', '份'], ['volume', '元'], ['amount', 'shares'], ['volume', 'CNY'], ['volume', 'currency']]) {
    const meta = metadata(); meta.fields[key] = { unit, currency: 'CNY' };
    const m = calculateRangeStatistics([bar('2026-02-02')], select, meta).metrics;
    unknown(m[key]); unknown(m.meanPrice);
  }
});
