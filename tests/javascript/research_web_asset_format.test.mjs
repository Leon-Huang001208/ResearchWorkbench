import test from 'node:test';
import assert from 'node:assert/strict';
import { formatAssetMagnitude as format } from '../../app/research_web/ui/asset-format.mjs';

test('large figures use absolute one-hundred-million threshold and two decimals', () => {
  assert.equal(format(8837425848,'元'),'88.37亿元');
  assert.equal(format(31744248,'股'),'3174.42万股');
  assert.equal(format(1e8,'元'),'1.00亿元');
  assert.equal(format(99999999,'元'),'10000.00万元');
  assert.equal(format(-256789000,'元'),'-2.57亿元');
  assert.equal(format(0,'股'),'0.00万股');
  assert.equal(format(100),'0.01万');
});
test('already scaled vendor units convert once, preserve currency and never mutate inputs', () => {
  assert.equal(format(19482409.24,'万元'),'1948.24亿元');
  assert.equal(format(2.5,'亿元'),'2.50亿元');
  assert.equal(format(70397.1427,'万股'),'7.04亿股');
  assert.equal(format(125000000,'currency','USD'),'1.25亿美元');
  assert.equal(format(125000000,'currency'),'1.25亿原币');
  for (const value of [null,undefined,'',false,true,NaN,Infinity,{},'bad']) assert.equal(format(value),'—');
});

test('historical quote uses the same normalized units as the summary instead of multiplying unit names', async () => {
  const {renderMarketTerminal} = await import('../../app/research_web/ui/asset-chart.mjs');
  const row = {asset:'603986.SH',date:'2026-10-22',open:10,high:12,low:9,close:11,volume:70397.1427,amount:19482409.24};
  const html=renderMarketTerminal([row],{}, {fields:{volume:{unit:'万股'},amount:{unit:'万元'}}});
  assert.match(html,/成交量 <strong>7\.04亿股<\/strong>/);
  assert.match(html,/成交额 <strong>1948\.24亿元<\/strong>/);
  assert.doesNotMatch(html,/万万元|亿万元|亿万股/);
});
