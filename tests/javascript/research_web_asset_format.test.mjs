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

test('A-share movement colors are strict, red up/green down, neutral for zero and unknown', async () => {
  const {assetChangeClass,assetPriceClass}=await import('../../app/research_web/ui/asset-format.mjs');
  assert.equal(assetChangeClass(1),'asset-price-up'); assert.equal(assetChangeClass(-1),'asset-price-down');
  assert.equal(assetPriceClass(101,100),'asset-price-up'); assert.equal(assetPriceClass(99,100),'asset-price-down');
  assert.equal(assetPriceClass('100','100'),'');
  for(const value of [0,-0,null,undefined,NaN,Infinity,false,true,'','bad','0x10']) assert.equal(assetChangeClass(value),'');
  for(const value of [0,-1,null,undefined,NaN,false,true,'']) {assert.equal(assetPriceClass(100,value),'');assert.equal(assetPriceClass(value,100),'');}
});

test('OHLC colors compare each value to previous close, not candle direction, while amounts stay neutral', async () => {
  const {renderMarketTerminal}=await import('../../app/research_web/ui/asset-chart.mjs');
  const bars=[{date:'2026-10-21',open:100,high:101,low:99,close:100,volume:1},{date:'2026-10-22',open:101,high:102,low:95,close:98,volume:2}];
  const html=renderMarketTerminal(bars);
  for(const [label,value,tone] of [['开','101.00','up'],['高','102.00','up'],['低','95.00','down'],['收','98.00','down'],['幅','-2.00%（-2.00）','down']]) assert.ok(html.includes(`${label} <strong class="asset-price-${tone}">${value}</strong>`));
  const readout=html.slice(html.indexOf('data-asset-history'),html.indexOf('<div class="kline-terminal-layout"'));
  assert.equal((readout.match(/asset-price-/g)||[]).length,5);
  assert.doesNotMatch(readout,/涨跌额|涨跌幅/);
  const first=renderMarketTerminal([bars[0]]); const firstReadout=first.slice(first.indexOf('data-asset-history'),first.indexOf('<div class="kline-terminal-layout"'));
  assert.doesNotMatch(firstReadout,/asset-price-up|asset-price-down/);
});

test('current quote and side prices retain independent directions without coloring all price fields alike', async () => {
  const {renderAssetWorkspace}=await import('../../app/research_web/ui/asset-workspace.mjs');
  const props={route:{asset:'603986.SH',assetType:'stock'},rows:{overview:[{asset:'603986.SH',date:'2026-10-22',price:98,yclose:100,open:101,high:102,low:95,change:-2,change_pct:-2}]}};
  const html=renderAssetWorkspace(props);
  assert.match(html,/id="asset-price" class="asset-price-down"/);
  assert.match(html,/id="asset-change" class="asset-price-down"/);
  assert.match(html,/id="asset-change-pct" class="asset-price-down"/);
  assert.match(html,/<dt>开盘<\/dt><dd class="asset-price-up">101/);
  assert.match(html,/<dt>最低<\/dt><dd class="asset-price-down">95/);
  const flat=renderAssetWorkspace({...props,rows:{overview:[{...props.rows.overview[0],price:100,change:0,change_pct:0}]}});
  assert.match(flat,/id="asset-price" class=""/); assert.match(flat,/id="asset-change-pct" class=""/);
});


test('missing or nonpositive quote prices stay neutral even when vendor changes are present', async () => {
  const {renderAssetWorkspace}=await import('../../app/research_web/ui/asset-workspace.mjs');
  for(const price of [0,-1,null]) {
    const html=renderAssetWorkspace({route:{asset:'603986.SH',assetType:'stock'},rows:{overview:[{date:'2026-10-22',price,change:-1,change_pct:-100}]}});
    assert.match(html,/id="asset-price" class=""/);
    assert.match(html,price === null ? /id="asset-change" class=""/ : /id="asset-change" class="asset-price-down"/);
  }
});
