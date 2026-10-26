import test from 'node:test';
import assert from 'node:assert/strict';
import {renderMarketTerminal, buildMarketChartOption, enrichMarketBars} from '../../app/research_web/ui/asset-chart.mjs';
import {formatAssetMagnitude} from '../../app/research_web/ui/asset-format.mjs';

const bars = () => [
  {asset:'603986.SH',date:'2026-10-22',open:280,high:285,low:270,close:276.75,volume:10000000,amount:2800000000},
  {asset:'603986.SH',date:'2026-10-23',open:271.09,high:294.80,low:268.30,close:292,vwap:280.65,volume:46027100,amount:12918000000,turnover_rate_pct:6.86},
];
const meta = unit => ({assetIdentity:'stock:603986.SH',frequency:'daily',fields:{volume:{unit},amount:{unit:'元'}}});
const strip = html => html.slice(html.indexOf('data-asset-history'),html.indexOf('<div class="kline-terminal-layout"'));

test('Wind strip uses close/change/open/high/low/average/volume/turnover/amplitude/amount in one compact contract', () => {
  const input=bars(), frozen=structuredClone(input), html=strip(renderMarketTerminal(input,{},meta('股')));
  const labels=[...html.matchAll(/<span(?: [^>]*)?>([^<]+) <strong/g)].map(m=>m[1]);
  assert.deepEqual(labels,['收','幅','开','高','低','均','量','换','振','额']);
  assert.match(html,/量 <strong>46\.03万<\/strong>/);
  assert.match(html,/额 <strong>129\.18亿<\/strong>/);
  assert.match(html,/幅 <strong class="asset-price-up">\+5\.51%（\+15\.25）/);
  assert.match(html,/开 <strong class="asset-price-down">271\.09/);
  assert.doesNotMatch(html,/亿元|万元|万股|万手|均价 <|换手率 <|振幅 </);
  assert.match(html,/title="[^"]*手[^"]*100/);
  assert.deepEqual(input,frozen);
});

test('confirmed A-share shares and lots scale once, while unknown asset/unit keeps original numeric basis', () => {
  for(const [value,unit] of [[46027100,'股'],[4602.71,'万股'],[460271,'手'],[46.0271,'万手']]) {
    const input=bars();input[1].volume=value;
    assert.match(strip(renderMarketTerminal(input,{},meta(unit))),/量 <strong>46\.03万<\/strong>/);
  }
  for(const identity of ['index:000001.SH','stock:AAPL','stock:00700.HK','']) {
    assert.match(strip(renderMarketTerminal(bars(),{}, {...meta('股'),assetIdentity:identity})),/量 <strong>4602\.71万<\/strong>/);
  }
  assert.match(strip(renderMarketTerminal(bars(),{},meta('provider_defined'))),/量 <strong>4602\.71万<\/strong>/);
});

test('compact strip preserves zero/missing distinctions and default financial formatter units', () => {
  const input=bars();Object.assign(input[1],{volume:0,amount:0});
  const zero=strip(renderMarketTerminal(input,{},meta('股')));assert.match(zero,/量 <strong>0\.00万/);assert.match(zero,/额 <strong>0\.00万/);
  Object.assign(input[1],{volume:null,amount:null});const missing=strip(renderMarketTerminal(input,{},meta('股')));
  assert.match(missing,/量 <strong>—/);assert.match(missing,/额 <strong>—/);
  assert.equal(formatAssetMagnitude(12918000000,'元'),'129.18亿元');
});

test('volume panel display shares the lot basis but retains unmodified OHLCV series', () => {
  const input=bars(), enriched=enrichMarketBars(input), option=buildMarketChartOption(enriched,{panels:['volume']},meta('股'));
  assert.equal(option.yAxis[1].axisLabel.formatter(46027100),'46.03万');
  assert.equal(option.series.find(s=>s.name==='成交量').data[1][1],46027100);
});

test('confirmed current quote volume uses the same compact lot display as historical readout', async () => {
  const {renderAssetWorkspace}=await import('../../app/research_web/ui/asset-workspace.mjs');
  const row=bars()[1];const props={route:{asset:'603986.SH',assetType:'stock'},observation:{asset:'603986.SH',asset_type:'stock',blocks:{overview:{status:'complete',dataset:{provider:'tinysoft',fields:{volume:{unit:'股'},amount:{unit:'元'}}}}}},rows:{overview:[row]}};
  const frozen=structuredClone(props);const html=renderAssetWorkspace(props);
  assert.match(html,/<dd id="asset-volume"[^>]*>46\.03万<\/dd>/);
  assert.match(html,/<dd id="asset-amount">129\.18亿<\/dd>/);
  assert.deepEqual(props,frozen);
});

test('unrecognized identity objects remain raw-unit display instead of coercing their methods', () => {
  const html=strip(renderMarketTerminal(bars(),{}, {...meta('股'),assetIdentity:{code:'603986.SH',asset_type:'stock',toString:null}}));
  assert.match(html,/量 <strong>4602\.71万<\/strong>/);
});

test('average price follows previous-close red/green semantics and keeps flat or missing neutral', () => {
  for(const [average,tone] of [[280.65,'up'],[270,'down'],[276.75,''],[null,''],[0,'']]) {
    const input=bars();input[1].vwap=average;const html=strip(renderMarketTerminal(input,{},meta('股')));
    const averageSpan=html.match(/<span>均 <strong([^>]*)>([^<]*)<\/strong><\/span>/);
    assert.ok(averageSpan);
    assert.equal(averageSpan[1],tone ? ` class="asset-price-${tone}"` : '');
  }
  const html=strip(renderMarketTerminal([bars()[1]],{},meta('股')));assert.match(html,/均 <strong>280\.65<\/strong>/);
});

test('native snapshot vol metadata drives the same lot display and does not rewrite unknown old units', async () => {
  const {renderAssetWorkspace}=await import('../../app/research_web/ui/asset-workspace.mjs');
  const native={'代码':'SH603986','时间':'2026-10-23',close:292,vol:46027129,amount:12917512995};
  const daily=bars();Object.assign(daily[1],{volume:native.vol,amount:native.amount});
  const props={route:{asset:'603986.SH',assetType:'stock'},observation:{asset:'603986.SH',asset_type:'stock',blocks:{
    overview:{status:'complete',dataset:{provider:'tinysoft',fields:{vol:{unit:'share',currency:null},amount:{unit:'元',currency:null}}}},
    history:{status:'complete',dataset:{provider:'tinysoft',fields:{volume:{unit:'share'},amount:{unit:'元'}}}}
  }},rows:{overview:[native],history:daily}};
  const frozen=structuredClone(props),html=renderAssetWorkspace(props);
  assert.match(html,/<dd id="asset-volume"[^>]*>46\.03万<\/dd>/);
  assert.match(html,/量 <strong>46\.03万<\/strong>/);
  assert.match(html,/<dd id="asset-amount">129\.18亿<\/dd>/);
  assert.deepEqual(props,frozen);
  const old=structuredClone(props);old.observation.blocks.overview.dataset.fields.vol.unit=null;
  const oldBefore=structuredClone(old),unknown=renderAssetWorkspace(old);
  assert.match(unknown,/<dd id="asset-volume"[^>]*源单位未提供[^>]*>4602\.71万<\/dd>/);
  assert.deepEqual(old,oldBefore);
});
