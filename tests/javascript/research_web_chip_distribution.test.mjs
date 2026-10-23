import test from 'node:test';
import assert from 'node:assert/strict';
import { estimateChips, normalizeChipSettings } from '../../app/research_web/ui/asset-chips.mjs';

const bars = (count = 5) => Array.from({ length: count }, (_, i) => ({
  asset: '603986.SH', date: new Date(Date.UTC(2026, 0, i + 1)).toISOString().slice(0, 10),
  open: 11, high: 12, low: 10, close: 11, vwap: 11, volume: 100, turnover_rate_pct: 50,
}));
const near = (actual, expected, tolerance = 1e-9) => assert.ok(Math.abs(actual - expected) <= tolerance, `${actual} != ${expected}`);

test('Wind-observed defaults are explicit and settings reject coercion or inverted ages', () => {
  const s = normalizeChipSettings();
  assert.equal(s.algorithm, 'triangle'); assert.equal(s.decay, 1);
  assert.equal(s.peakUpperPct, 10); assert.equal(s.peakLowerPct, 10);
  assert.deepEqual([s.ageShort, s.ageMiddle, s.ageLong], [2, 10, 100]);
  for (const patch of [{ decay: NaN }, { decay: '1' }, { ageShort: 0 }, { ageMiddle: 2 }, { ageLong: 10 }, { peakLowerPct: 101 }, { algorithm: 'invented' }]) {
    assert.throws(() => normalizeChipSettings(patch));
  }
});

test('turnover removes old holdings, conserves mass, and uses observed-bar age boundaries', () => {
  const p = estimateChips(bars(), { algorithm: 'uniform', ageShort: 1, ageMiddle: 2, ageLong: 3 });
  assert.equal(p.status, 'ready'); near(p.points.reduce((s, b) => s + b.mass, 0), 1);
  near(p.averageCost, 11); near(p.profitFraction, .5); near(p.lockedFraction, .5);
  near(p.cost90[0], 10.1); near(p.cost90[1], 11.9);
  [.125, .125, .25, .5].forEach((v, i) => near(p.ageFractions[i], v));
  near(p.meanAge, .9375); near(p.initialResidual, .0625);
});

test('triangle uses verified VWAP, exact quantiles and a peak independent of drawing buckets', () => {
  const a = estimateChips(bars(), {}, 180); const b = estimateChips(bars(), {}, 512);
  assert.equal(a.status, 'ready'); near(a.peak, 11); near(a.peak, b.peak);
  near(a.averageCost, 11); near(a.cost90[0], 10 + Math.sqrt(.1));
  near(a.cost90[1], 12 - Math.sqrt(.1)); near(a.profitFraction, .5);
  near(a.peakLower, 9.9); near(a.peakUpper, 12.1); near(a.peakFraction, 1);
  near(a.peakAverageCost, 11);
  const upperHalf = estimateChips(bars(), { peakLowerPct: 0 });
  near(upperHalf.peakFraction, .5); near(upperHalf.peakAverageCost, 11 + 1 / 3);
});

test('missing turnover, wrong asset, duplicate dates and unverified triangle input fail closed', () => {
  for (const change of [b => { delete b[1].turnover_rate_pct; }, b => { b[1].turnover_rate_pct = -1; }, b => { b[1].asset = '600519.SH'; }, b => { b[1].date = b[0].date; }, b => { b[1].date = '2026-99-99'; }, b => { delete b[1].vwap; }, b => { b[1].vwap = 1200; }]) {
    const input = bars(); change(input); const p = estimateChips(input);
    assert.equal(p.status, 'unavailable'); assert.deepEqual(p.points, []);
  }
});

test('zero turnover is retained, flat candles are atoms, and equal-cost chips are not called profitable', () => {
  const input = bars().map((b, i) => ({ ...b, open: 11, high: 11, low: 11, close: 11, vwap: 11, turnover_rate_pct: i ? 0 : 50 }));
  const p = estimateChips(input); assert.equal(p.status, 'ready'); near(p.averageCost, 11);
  near(p.profitFraction, 0); near(p.lockedFraction, 0); near(p.atCostFraction, 1);
  near(p.initialResidual, 1); near(p.meanAge, 4);
  near(estimateChips(input, { peakLowerPct: 0 }).peakAverageCost, 11);
});

test('more than 5000 rows remain in the model and cutoff excludes all future bars', () => {
  const input = bars(6001); const p = estimateChips(input);
  assert.equal(p.validBars, 6001); assert.equal(p.endDate, input.at(-1).date);
  const prefix = input.slice(0, 120); const before = estimateChips(prefix);
  input[120].close = 1000;
  assert.deepEqual(estimateChips(input.slice(0, 120)), before);
});

test('non-array inputs and endpoint-mode triangles do not leak exceptions or NaN', () => {
  for (const input of [null, {}, 42]) assert.equal(estimateChips(input).status, 'unavailable');
  const lowMode = bars().map(b => ({ ...b, open: 10, close: 10, vwap: 10 }));
  const low = estimateChips(lowMode, { peakLowerPct: 0 });
  near(low.peak, 10); near(low.peakFraction, .75); near(low.peakAverageCost, 10 + 4 / 9);
  const highMode = bars().map(b => ({ ...b, open: 12, close: 12, vwap: 12 }));
  assert.ok(Number.isFinite(estimateChips(highMode).peakAverageCost));
});

test('a negligible old flat-price atom cannot force the chip peak back to the IPO price', () => {
  const input = bars(60); input[0] = { ...input[0], open: 1, high: 1, low: 1, close: 1, vwap: 1 };
  const p = estimateChips(input); near(p.peak, 11);
  near(p.points.reduce((s, b) => s + b.mass, 0), 1);
});

test('shared bucket edges assign each flat-price atom exactly once', () => {
  const input = bars().map((b, i) => ({ ...b, ...Object.fromEntries(['open','high','low','close','vwap'].map(k => [k, [.01,10,5.56,5.56,5.56][i]])) }));
  for (const count of [179,180,512]) {
    const p = estimateChips(input, {}, count);
    near(p.points.reduce((sum, point) => sum + point.mass, 0), 1);
    for (let age = 0; age < 4; age++) near(p.points.reduce((sum, point) => sum + point.massByAge[age], 0), p.ageFractions[age]);
  }
});

test('zero decay retains the initial cohort and extreme turnover cannot create negative mass', () => {
  const input = bars(); input[4].turnover_rate_pct = 300;
  const zero = estimateChips(input, { decay: 0 }); near(zero.initialResidual, 1); near(zero.meanAge, 4);
  const high = estimateChips(input); near(high.meanAge, 0); assert.equal(high.clampedTurnoverDays, 1);
  near(high.points.reduce((sum, point) => sum + point.mass, 0), 1);
  assert.ok(high.points.every(point => point.mass >= 0));
});
