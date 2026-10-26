import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { enrichMarketBars, aggregateMarketBars, estimateChipDistribution } from '../../app/research_web/ui/asset-indicators.mjs';

const fixture = JSON.parse(fs.readFileSync(new URL('../fixtures/alphafoundry_indicators_golden.json', import.meta.url)));
const mapping = { ma5: ['ma5', 5], ma10: ['ma10', 10], ma20: ['ma20', 20], ma60: ['ma60', 60], ma120: ['ma120', 120], ma250: ['ma250', 250], boll_upper: ['bollUpper', 20], boll_lower: ['bollLower', 20], macd_dif: ['dif', 26], macd_dea: ['dea', 34], macd_hist: ['macd', 34], kdj_k: ['k', 9], kdj_d: ['d', 9], kdj_j: ['j', 9], rsi: ['rsi', 15] };

for (const period of ['day', 'week', 'month']) test(`actual AlphaFoundry backend golden values align after ${period} aggregation and display warmup`, () => {
  const bars = aggregateMarketBars(enrichMarketBars(fixture.input), period);
  const expected = fixture.expected[period];
  assert.equal(bars.length, expected.length);
  let compared = 0;
  for (let index = 0; index < bars.length; index++) {
    assert.equal(bars[index].date, expected[index].date);
    for (const [source, [target, warmup]] of Object.entries(mapping)) {
      if (index + 1 < warmup) { assert.equal(bars[index][target], null, `${period} ${index} ${target} before warmup`); continue; }
      const value = expected[index][source];
      // AF returns null when the rolling loss is zero; the approved corrected
      // RSI 100/50 edge behavior has its own regression tests.
      if (value === null && source === 'rsi') continue;
      if (value === null) { assert.equal(bars[index][target], null); continue; }
      assert.ok(Number.isFinite(bars[index][target]), `${period} ${index} ${target} must be finite`);
      assert.ok(Math.abs(bars[index][target] - value) < 1e-9, `${period} ${index} ${target}: ${bars[index][target]} != ${value}`);
      compared++;
    }
  }
  assert.ok(compared > 10);
});

test('legacy OHLCV-only golden inputs cannot masquerade as verified turnover chips', () => {
  const bars = enrichMarketBars(fixture.input);
  for (const window of fixture.expectedChips) {
    const chip = estimateChipDistribution(bars, window.start, window.end);
    assert.equal(chip.status, 'unavailable'); assert.deepEqual(chip.points, []);
  }
});
