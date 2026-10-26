import test from 'node:test';
import assert from 'node:assert/strict';
import {enrichMarketBars,aggregateMarketBars} from '../../app/research_web/ui/asset-indicators.mjs';
import {INDICATOR_IDS,INDICATOR_RULES,PANEL_SERIES,calculatePanelIndicators,normalizeIndicatorSettings,normalizeFavorites,panelField} from '../../app/research_web/ui/asset-indicator-library.mjs';
import {createAssetChartController,buildMarketChartOption,renderMarketTerminal} from '../../app/research_web/ui/asset-chart.mjs';
const rows=(n,flat=false)=>Array.from({length:n},(_,i)=>({date:new Date(Date.UTC(2020,0,i+1)).toISOString().slice(0,10),open:flat?10:10+i,close:flat?10:10+i,high:flat?11:11+i,low:flat?9:9+i,volume:100,amount:1000}));
const close=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
const values=(bars,id,key)=>bars.map(b=>b[panelField(id,key)]);
const click=action=>({type:'click',target:{closest:selector=>selector==='[data-asset-chart-action]'?{dataset:{assetChartAction:action}}:null}});
test('15 closed schemas reject unknown or unsafe parameters and allow isolated copies',()=>{
 assert.equal(INDICATOR_IDS.length,15);
 for(const value of [{fake:{}},{sar:{step:NaN}},{rsi:{period:true}},{rsi:{period:'14'}},{rsi:null},{bias:{short:24}},{volume:{short:10}},{sar:{step:.5,maximum:.2}}])assert.throws(()=>normalizeIndicatorSettings(value));
 for(const value of [['fake'],['rsi','rsi'],[{}],null])assert.throws(()=>normalizeFavorites(value));
 const a=normalizeIndicatorSettings();a.rsi.period=1;assert.equal(normalizeIndicatorSettings().rsi.period,14);
 assert.equal(Object.isFrozen(INDICATOR_RULES.rsi.period),true);
});
test('default aliases preserve existing AF math and full warmup',()=>{
 const enriched=enrichMarketBars(rows(300));const bars=calculatePanelIndicators(enriched);
 for(let i=0;i<bars.length;i++)for(const [id,key,source] of [['macd','dif','dif'],['macd','dea','dea'],['macd','hist','macd'],['kdj','k','k'],['rsi','rsi','rsi'],['boll','upper','bollUpper'],['volume','volShort','volumeMA5']])assert.equal(bars[i][panelField(id,key)],enriched[i][source]);
 const custom=calculatePanelIndicators(enriched,{rsi:{period:3},boll:{period:3},atr:{period:3}});
 assert.equal(custom[2].panel_rsi_rsi,null);close(custom[3].panel_rsi_rsi,100);
 assert.equal(custom[1].panel_boll_middle,null);close(custom[2].panel_boll_middle,11);
 assert.equal(custom[2].panel_atr_atr,null);close(custom[3].panel_atr_atr,2);
});
test('independent linear and flat golden values for additional indicators',()=>{
 const bars=calculatePanelIndicators(enrichMarketBars(rows(80)));
 close(bars[14].panel_atr_atr,2);close(bars[14].panel_dmi_pdi,50);close(bars[14].panel_dmi_mdi,0);
 assert.equal(bars[18].panel_dmi_adx,null);close(bars[19].panel_dmi_adx,100);close(bars[25].panel_dmi_adxr,100);
 close(bars[13].panel_cci_cci,6.5/(.015*3.5));close(bars[12].panel_roc_roc,120);close(bars[5].panel_wr_wr2,100/7);
 const flat=calculatePanelIndicators(enrichMarketBars(rows(80,true)));
 for(const [id,key,expected]of [['wr','wr1',50],['cci','cci',0],['bias','b1',0],['roc','roc',0],['obv','obv',100],['vr','vr',100],['emv','emv',0],['atr','atr',2]])close(flat[79][panelField(id,key)],expected);
});
test('SAR initialization and reversal match fixed reference example',()=>{
 const high=[10,11,12,13,10,9],low=[9,10,11,12,8,7];const input=rows(6).map((r,i)=>({...r,open:(high[i]+low[i])/2,close:(high[i]+low[i])/2,high:high[i],low:low[i]}));
 const actual=values(calculatePanelIndicators(enrichMarketBars(input)),'sar','sar');
 assert.equal(actual[0],null);[9,9.04,9.1584,13,13].forEach((v,i)=>close(actual[i+1],v));
});
test('missing volume is distinct from zero; gaps reset price indicator warmup',()=>{
 const input=rows(80);input[40].volume=null;input[41].volume=0;input[50].close=null;
 const bars=calculatePanelIndicators(enrichMarketBars(input));
 assert.equal(bars[40].panel_obv_obv,null);assert.equal(bars[41].panel_obv_obv,0);
 assert.equal(bars[41].panel_emv_emv,null);assert.equal(bars[51].panel_atr_atr,null);
 for(const row of bars)for(const id of INDICATOR_IDS)for(const [key]of PANEL_SERIES[id])assert.ok(row[panelField(id,key)]===null||Number.isFinite(row[panelField(id,key)]));
});
test('all new outputs are causal; aggregate before recalculating weekly/monthly series',()=>{
 const input=rows(330);const full=calculatePanelIndicators(enrichMarketBars(input));
 for(const length of [1,2,6,14,26,35,60,123])assert.deepEqual(calculatePanelIndicators(enrichMarketBars(input.slice(0,length))),full.slice(0,length));
 for(const period of ['week','month']){
  const bars=aggregateMarketBars(enrichMarketBars(input),period);const out=calculatePanelIndicators(bars,{atr:{period:3}});
  assert.equal(out[2].panel_atr_atr,null);assert.ok(out[3].panel_atr_atr>2);
  assert.equal(out.at(-1).panel_obv_obv,out.reduce((sum,b)=>sum+b.volume,0));
 }
});
test('6001 records and every panel create full ECharts series without truncation',()=>{
 const bars=enrichMarketBars(rows(6001));const option=buildMarketChartOption(bars,{panels:[...INDICATOR_IDS],start:5881,end:6001});
 assert.equal(option.grid.length,16);assert.equal(option.series[0].data.length,6001);assert.equal(option.series[0].large,false);
 for(const series of option.series)assert.equal(series.data.length,6001);
 assert.deepEqual(option.dataZoom[0].xAxisIndex,Array.from({length:16},(_,i)=>i));
});
test('favorites replace active panel, removal preserves range/date, parameters roundtrip controller',()=>{
 const saved=[];const c=createAssetChartController({onIndicatorPreferencesChange:p=>saved.push(p)});
 c.configure(rows(300),'one',{}, {panels:['volume','macd'],favorites:['cci'],indicator_settings:{cci:{period:10}}});
 const before=c.getState();c.handle(click('panel-choose-cci'));
 assert.deepEqual(c.getState().panels,['volume','cci']);assert.equal(saved[0].indicator_settings.cci.period,10);
 c.handle(click('panel-remove-cci'));assert.equal(c.getState().start,before.start);assert.equal(c.getState().selectedDate,before.selectedDate);
 saved[0].indicator_settings.cci.period=1;assert.equal(c.getState().indicatorSettings.cci.period,10);
 const html=renderMarketTerminal(rows(10));assert.match(html,/data-asset-indicator-manager/);assert.match(html,/data-asset-chart-action="indicator-add"/);assert.match(html,/indicator-replace-macd/);
});

test('explicit legacy or new-account preferences reset optional fields without persisting defaults',()=>{
 const writes=[];const c=createAssetChartController({onIndicatorPreferencesChange:p=>writes.push(p)});
 const data=rows(100);c.configure(data,'same',{}, {panels:['rsi'],favorites:['cci'],indicator_settings:{rsi:{period:7}}});
 assert.equal(c.getState().indicatorSettings.rsi.period,7);
 c.configure(data,'same',{}, {panels:['volume','macd']});
 assert.equal(c.getState().indicatorSettings.rsi.period,14);assert.ok(c.getState().favorites.includes('volume'));assert.equal(writes.length,0);
 c.configure(data,'same');assert.equal(c.getState().indicatorSettings.rsi.period,14);
});

test('account chart identity resets date and chip defaults even for the same asset',()=>{
 const c=createAssetChartController();const data=rows(300);
 c.configure(data,'same',{assetIdentity:'603986.SH',accountIdentity:'a'},{panels:['cci'],chip_settings:{decay:.8},favorites:['cci'],indicator_settings:{cci:{period:7}}});c.select(5);
 c.configure(data,'same',{assetIdentity:'603986.SH',accountIdentity:'b'},{panels:['volume','macd']});
 assert.equal(c.getState().selectedDate,data.at(-1).date);assert.notEqual(c.getState().chipSettings.decay,.8);assert.equal(c.getState().indicatorSettings.cci.period,14);
});
