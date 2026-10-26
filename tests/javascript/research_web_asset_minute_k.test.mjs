import test from 'node:test';
import assert from 'node:assert/strict';
import {enrichMarketBars, sourceFrequency} from '../../app/research_web/ui/asset-indicators.mjs';
import {renderMarketTerminal, minuteChipInputs, createAssetChartController} from '../../app/research_web/ui/asset-chart.mjs';
import {MINUTE_K_CYCLES} from '../../app/research_web/ui/asset-minute-k.mjs';
const row=(date,close=10)=>({date,open:10,high:12,low:9,close,volume:100,amount:1000,vwap:10,turnover_rate_pct:2});
test('minute timestamps never collapse and 1m retains legacy month meaning',()=>{
  const input=[row('2026-05-25T09:31:00+08:00'),row('2026-05-25T09:32:00+08:00',11)];
  assert.equal(enrichMarketBars(input).length,1);
  const minute=enrichMarketBars(input,{timestamp:true});
  assert.equal(minute.length,2);assert.equal(minute[1].close,11);
  assert.equal(enrichMarketBars([row('2026-05-25T09:31:00')],{timestamp:true}).length,0);
  assert.equal(sourceFrequency('1m'),'month');assert.equal(sourceFrequency('minute'),'minute');
  assert.deepEqual(MINUTE_K_CYCLES,['1m','5m','15m','30m','60m','120m']);
});
test('minute renderer calculates MA on candles, uses minute-to-minute return',()=>{
  const rows=Array.from({length:30},(_,i)=>row(`2026-05-25T10:${String(i).padStart(2,'0')}:00+08:00`,10+i));
  for(const r of rows){r.high=r.close+1;r.open=r.close-1;r.low=r.close-2;}
  const c=createAssetChartController();c.configure(rows,'minute-test',{frequency:'minute',minute_k:true});
  assert.equal(c.getState().end,30);assert.equal(c.getState().period,'minute');
  const html=renderMarketTerminal(rows,c.getState(),{frequency:'minute',minute_k:true});
  assert.match(html,/2026-05-25 10:29/);assert.match(html,/2.63%/);assert.match(html,/MA5: 37.00/);
});
test('minute chip cutoff ignores every same-day daily candle and zoom state',()=>{
  const rows=[row('2026-05-22'),row('2026-05-25',12),row('2026-05-26',11)];
  const ref={rows,cutoff_policy:'strictly_before_selected_minute_date'};
  assert.deepEqual(minuteChipInputs(ref,'2026-05-25T14:30:00+08:00').map(r=>r.date),['2026-05-22']);
  assert.equal(minuteChipInputs(ref,'2026-05-25T09:35:00+08:00').length,1);
  assert.equal(minuteChipInputs({rows},'2026-05-26T15:00:00+08:00').length,0);
});
test('changing minute cycle resets visible window, adjustment keeps selection',()=>{
  const input=Array.from({length:250},(_,i)=>row(`2026-05-${String(1+Math.floor(i/120)).padStart(2,'0')}T${String(9+Math.floor(i%120/60)).padStart(2,'0')}:${String(i%60).padStart(2,'0')}:00+08:00`));
  const c=createAssetChartController();const meta={frequency:'minute',minute_k:true,assetIdentity:'stock:603986.SH',chartIdentity:'minute:1m'};
  c.configure(input,'one-minute',meta);c.select(100);
  c.configure(input,'five-minute',{...meta,chartIdentity:'minute:5m'});
  assert.equal(c.getState().end,250);assert.equal(c.getState().start,130);
  c.select(120);const date=c.getState().selectedDate;
  c.configure(input,'five-minute-qfq',{...meta,chartIdentity:'minute:5m',adjustment:'qfq'});
  assert.equal(c.getState().selectedDate,date);
});
