import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRangeController } from '../../app/research_web/ui/asset-range-controller.mjs';
import { createAssetChartController } from '../../app/research_web/ui/asset-chart.mjs';

const daily = Array.from({length: 8}, (_,i) => ({date:`2026-01-0${i+1}`,open:10,close:11,high:12,low:9,volume:100,amount:1000}));
function fixture(displayBars=daily) {
  const nodes = new Map(); const node = () => ({style:{},innerHTML:'',hidden:false,focus(){this.focused=true;},querySelector(){return null;}});
  for (const key of ['[data-asset-range-layer]','[data-asset-range-selection]','[data-asset-range-card]','[data-asset-echarts]']) nodes.set(key,node());
  const host={querySelector:key=>nodes.get(key),getBoundingClientRect:()=>({left:0,top:0,width:800,height:600})};
  const context={daily,displayBars,metadata:{frequency:'daily'},plot:{left:10,top:20,width:160,height:300},visibleStart:0,visibleEnd:displayBars.length,indexAt:x=>Math.min(displayBars.length-1,Math.floor((x-10)/20)),pixelAt:i=>20+i*20};
  const controller=createRangeController({host,getContext:()=>context,logger:()=>{}});
  return {controller,context,nodes};
}
const event=(x,y=40,button=2)=>({clientX:x,clientY:y,button,preventDefault(){this.prevented=true;},stopImmediatePropagation(){this.stopped=true;}});
test('right drag only, strict threshold and main plot boundary',()=>{
 const {controller:c}=fixture(); assert.equal(c.begin(event(20,40,0)),false);assert.equal(c.begin(event(20,400)),false);
 assert.equal(c.begin(event(20)),true); c.end(event(24));assert.equal(c.getState().selection,null);
 c.begin(event(20));c.end(event(26));assert.equal(c.getState().result.range.count,1);
});
test('reverse drag clamps to loaded visible bars and replaces single range',()=>{
 const {controller:c}=fixture();c.begin(event(100));c.move(event(-200));c.end(event(-200));assert.deepEqual(c.getState().selection,{startDate:'2026-01-01',endDate:'2026-01-05'});
 c.begin(event(120));c.end(event(150));assert.deepEqual(c.getState().selection,{startDate:'2026-01-06',endDate:'2026-01-08'});
});
test('weekly and monthly bar source dates expand to daily records',()=>{
 const {controller:c}=fixture([{date:'2026-01-04',source_start_date:'2026-01-01',source_end_date:'2026-01-04'},{date:'2026-01-08',source_start_date:'2026-01-05',source_end_date:'2026-01-08'}]);
 c.begin(event(20));c.end(event(50));assert.equal(c.getState().result.range.count,8);
});
test('cancel affects active gesture while committed card survives global pointerup cancellation',()=>{
 const {controller:c}=fixture();c.begin(event(20));c.end(event(60));c.cancel();assert.ok(c.getState().selection);
 c.begin(event(80));c.cancel();assert.equal(c.getState().gesture,null);assert.ok(c.getState().selection);
});
test('keyboard entry defaults to visible interval and input failures stay explicit',()=>{
 const {controller:c,context}=fixture();context.visibleStart=2;context.visibleEnd=5;c.open();assert.equal(c.getState().result.range.count,3);
 c.setDates('','2026-01-04');assert.ok(c.getState().result.diagnostics.includes('range_dates_invalid'));
 c.setDates('2027-01-01','2027-01-03');assert.ok(c.getState().result.diagnostics.includes('range_empty'));
});
test('render preserves selection across viewport changes and clear restores chart focus',()=>{
 const {controller:c,context,nodes}=fixture();c.open();const selected=c.getState().selection;context.visibleStart=4;c.render();assert.deepEqual(c.getState().selection,selected);
 assert.match(nodes.get('[data-asset-range-card]').innerHTML,/行业对比/);assert.match(nodes.get('[data-asset-range-card]').innerHTML,/未取得/);
 c.clear();assert.equal(c.getState().selection,null);assert.equal(nodes.get('[data-asset-echarts]').focused,true);c.dispose();
});
test('capture consumes right native gesture before chart handling, with contextmenu and synthetic click',()=>{
 const {controller:c}=fixture();const down={...event(30),type:'pointerdown'};assert.equal(c.capture(down),true);assert.ok(down.prevented&&down.stopped);
 const compatibility={...event(30),type:'mousedown'};c.capture(compatibility);assert.ok(compatibility.stopped);
 c.capture({...event(80),type:'pointerup'});const click={...event(80,40,0),type:'click'};assert.equal(c.capture(click),true);assert.ok(click.stopped);
 const context={...event(80),type:'contextmenu'};assert.equal(c.capture(context),true);assert.ok(context.prevented);
 assert.equal(c.capture({...event(80,450),type:'contextmenu'}),false);
 const left={...event(30,40,0),type:'pointerdown'};assert.equal(c.capture(left),false);assert.equal(left.prevented,undefined);
 assert.equal(c.capture({...event(30,40,0),type:'click'}),false);
});
test('outside release clamps gesture, blur and pointercancel abandon only active gesture',()=>{
 const {controller:c}=fixture();c.begin(event(60));c.capture({...event(1000,500),type:'mouseup'});assert.equal(c.getState().selection.endDate,'2026-01-08');
 c.begin(event(20));c.capture({type:'blur'});assert.equal(c.getState().gesture,null);assert.ok(c.getState().selection);
 c.begin(event(20));c.capture({type:'pointercancel'});assert.equal(c.getState().gesture,null);
 const escape={type:'keydown',key:'Escape'};c.handle(escape);assert.equal(c.getState().selection,null);
});
test('floating drag captures header, clamps outside bounds and releases capture',()=>{
 const {controller:c,nodes}=fixture();c.open();let captured=null,released=null;
 const header={setPointerCapture:id=>{captured=id;},releasePointerCapture:id=>{released=id;}};
 const target={closest:selector=>selector==='[data-asset-range-drag]'?header:null};
 assert.equal(c.handle({...event(30,40,0),type:'pointerdown',pointerId:7,target}),true);assert.equal(captured,7);
 c.capture({...event(3000,3000,0),type:'pointermove',pointerId:7,target});assert.deepEqual(c.getState().position,{x:360,y:180});
 c.capture({...event(3000,3000,0),type:'pointerup',pointerId:7,target});assert.equal(released,7);
 assert.equal(nodes.get('[data-asset-range-card]').style.left,'360px');
});
test('matching lost pointer capture cancels either gesture, normal release preserves committed range',()=>{
 const {controller:c}=fixture();c.open();const original=c.getState().selection;
 c.begin({...event(30),pointerId:9});assert.equal(c.capture({type:'lostpointercapture',pointerId:8}),false);assert.ok(c.getState().gesture);
 assert.equal(c.capture({type:'lostpointercapture',pointerId:9}),true);assert.equal(c.getState().gesture,null);assert.deepEqual(c.getState().selection,original);
 assert.equal(c.capture({...event(60),type:'mousemove'}),false);
 const header={setPointerCapture(){},releasePointerCapture(id){c.capture({type:'lostpointercapture',pointerId:id});}};
 const target={closest:selector=>selector==='[data-asset-range-drag]'?header:null};
 c.handle({...event(30,40,0),type:'pointerdown',pointerId:7,target});
 assert.equal(c.capture({type:'lostpointercapture',pointerId:6}),false);
 assert.equal(c.capture({type:'lostpointercapture',pointerId:7}),true);
 assert.equal(c.capture({...event(60),type:'mousemove'}),false);
 c.handle({...event(30,40,0),type:'pointerdown',pointerId:7,target});c.end({...event(50),pointerId:7});
 assert.deepEqual(c.getState().selection,original);assert.equal(c.capture({...event(60),type:'mousemove'}),false);
});
test('critical price and extrema definitions are visible with a keyboard native disclosure',()=>{
 const {controller:c,nodes}=fixture();c.open();const markup=nodes.get('[data-asset-range-card]').innerHTML;
 assert.match(markup,/<dt>原始均价<\/dt>/);assert.match(markup,/<dt>极值回撤<\/dt>/);assert.match(markup,/<dt>极值上涨<\/dt>/);
 assert.match(markup,/<details[^>]*><summary>统计口径与公式<\/summary>/);assert.match(markup,/不按时间顺序/);assert.match(markup,/不作为复权均价/);
});

function mountedChart() {
 const {nodes}=fixture();const handlers=new Map(),windowHandlers=new Map(),instances=[];
 const add=(map,name,handler,options)=>{const list=map.get(name)||[];list.push({handler,options});map.set(name,list);};
 const view={addEventListener:(name,handler,options)=>add(windowHandlers,name,handler,options),removeEventListener:(name,handler)=>windowHandlers.set(name,(windowHandlers.get(name)||[]).filter(item=>item.handler!==handler)),echarts:{init:()=>{const events=new Map(),zrEvents=new Map();const chart={on:(n,h)=>events.set(n,h),off:n=>events.delete(n),getZr:()=>({on:(n,h)=>zrEvents.set(n,h),off:n=>zrEvents.delete(n)}),setOption(){},resize(){},dispose(){},events,zrEvents};instances.push(chart);return chart;}}};
 const host={style:{},ownerDocument:{defaultView:view},querySelector:key=>nodes.get(key),querySelectorAll:()=>[],getBoundingClientRect:()=>({left:0,top:0,width:800,height:600}),addEventListener:(name,handler,options)=>add(handlers,name,handler,options),removeEventListener:(name,handler)=>handlers.set(name,(handlers.get(name)||[]).filter(item=>item.handler!==handler))};
 for(const key of ['[data-asset-echarts]','[data-asset-chip-chart]'])nodes.set(key,{style:{setProperty(){}},dataset:{},getBoundingClientRect:host.getBoundingClientRect,addEventListener(){},removeEventListener(){}});
 return {host,nodes,handlers,windowHandlers,instances};
}
test('mounted capture retains viewport, selected date and chips, requests no history and clears on version change',()=>{
 const f=mountedChart(),requests=[],changes=[],errors=[];
 const c=createAssetChartController({onHistoryRequest:value=>requests.push(value),onChange:value=>changes.push(value),logger:(code,data)=>{if(data.status==='error')errors.push(code);}});
 const metadata={frequency:'daily',assetIdentity:'stock:600000.SH',asset_history:{canonical_version:'v1',adjustment:'none'}};
 c.configure(daily,'v1',metadata);assert.equal(c.mount(f.host),true);const before=c.getState();
 const capture=f.handlers.get('pointerdown').find(item=>item.options===true).handler;
 const right={...event(20,40),type:'pointerdown'};capture(right);assert.ok(right.stopped);
 f.windowHandlers.get('pointerup')[0].handler({...event(400,40),type:'pointerup'});c.cancel();
 assert.deepEqual(c.getState(),before);assert.equal(requests.length,0);assert.equal(changes.length,0);assert.equal(f.nodes.get('[data-asset-range-card]').hidden,false);
 c.handle({type:'click',target:{closest:selector=>selector==='[data-asset-chart-action]'?{dataset:{assetChartAction:'period-month'}}:null}});
 assert.equal(f.nodes.get('[data-asset-range-card]').hidden,false);assert.equal(c.getState().selectedDate,before.selectedDate);
 c.configure(daily,'v2',{...metadata,asset_history:{...metadata.asset_history,canonical_version:'v2'}});assert.equal(f.nodes.get('[data-asset-range-card]').hidden,true);
 assert.deepEqual(errors,[]);c.dispose();assert.ok([...f.windowHandlers.values()].every(list=>list.length===0));
});
test('same-slot theme mount keeps committed date range and position, drops active gesture and respects version clear',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});
 const metadata={frequency:'daily',assetIdentity:'stock:600000.SH',asset_history:{canonical_version:'v1',adjustment:'none'}};
 c.configure(daily,'v1',metadata);c.mount(f.host);
 const down=e=>f.handlers.get('pointerdown').find(item=>item.options===true).handler({...e,type:'pointerdown'});
 down({...event(50),pointerId:2});f.windowHandlers.get('pointerup')[0].handler({...event(100),type:'pointerup',pointerId:2});
 const header={setPointerCapture(){},releasePointerCapture(){}};const target={closest:s=>s==='[data-asset-range-drag]'?header:s==='[data-asset-range-card]'?{matches:()=>true}:null};
 down({...event(70,60,0),pointerId:3,target});f.windowHandlers.get('pointermove')[0].handler({...event(100,100,0),type:'pointermove',pointerId:3,target});f.windowHandlers.get('pointerup')[0].handler({...event(100,100,0),type:'pointerup',pointerId:3,target});
 const card=f.nodes.get('[data-asset-range-card]'),markup=card.innerHTML,left=card.style.left,top=card.style.top,before=c.getState();
 down({...event(120),pointerId:4});f.host.ownerDocument.documentElement={dataset:{theme:'light'}};c.mount(f.host);
 assert.equal(card.hidden,false);assert.equal(card.innerHTML,markup);assert.equal(card.style.left,left);assert.equal(card.style.top,top);assert.deepEqual(c.getState(),before);
 const move={...event(160),type:'pointermove',pointerId:4};f.windowHandlers.get('pointermove')[0].handler(move);assert.equal(move.prevented,undefined);
 assert.ok(f.handlers.get('lostpointercapture').some(item=>item.options===true));
 c.configure(daily,'v2',{...metadata,asset_history:{...metadata.asset_history,canonical_version:'v2'}});c.mount(f.host);assert.equal(card.hidden,true);
 c.dispose();
});
test('display contents slot and terminal use actual kline stage box with viewport height cap',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});
 f.host.style.display='contents';f.host.getBoundingClientRect=()=>({left:0,top:0,width:0,height:0});
 const terminal={getBoundingClientRect:()=>({left:0,top:0,width:0,height:0}),querySelector:f.host.querySelector};
 f.nodes.set('.asset-market-terminal',terminal);
 const stage={getBoundingClientRect:()=>({left:250,top:175,width:701,height:584}),querySelector:f.host.querySelector,ownerDocument:f.host.ownerDocument};
 f.nodes.set('.asset-kline-stage',stage);f.host.ownerDocument.defaultView.innerHeight=720;
 f.nodes.get('[data-asset-echarts]').getBoundingClientRect=()=>({left:250,top:175,width:701,height:500});
 c.configure(daily,'v1',{frequency:'daily'});c.mount(f.host);
 f.handlers.get('pointerdown').find(item=>item.options===true).handler({...event(290,240),type:'pointerdown'});
 f.windowHandlers.get('pointerup')[0].handler({...event(600,240),type:'pointerup'});
 const card=f.nodes.get('[data-asset-range-card]');assert.equal(card.hidden,false);assert.equal(card.style.left,'52px');assert.equal(card.style.top,'44px');assert.equal(card.style.maxHeight,'537px');
 assert.equal(f.host.style.position,undefined);assert.match(f.host.innerHTML,/data-asset-range-card[^>]*[\s\S]*<\/section><\/div><div class="asset-panel-controls">/);
 card.getBoundingClientRect=()=>({width:460,height:537});
 f.handlers.get('toggle')[0].handler({target:{matches:()=>true}});assert.equal(card.style.top,'0px');
 c.dispose();
});
test('floating card fits visible desktop bottom and mobile flow has no height cap',()=>{
 const {controller:c,nodes,context}=fixture();
 // Host below the viewport top; the visible slice, not its full height, bounds the card.
 const card=nodes.get('[data-asset-range-card]');card.getBoundingClientRect=()=>({width:440,height:584});
 const hostView={innerHeight:720,matchMedia:()=>({matches:false})};
 const host={querySelector:key=>nodes.get(key),getBoundingClientRect:()=>({left:84,top:175,width:701,height:584}),ownerDocument:{defaultView:hostView}};
 const bounded=createRangeController({host,getContext:()=>context,logger:()=>{}});bounded.open();assert.equal(card.style.maxHeight,'537px');assert.equal(bounded.getState().position.y,0);
 hostView.matchMedia=()=>({matches:true});bounded.render();assert.equal(card.style.maxHeight,'none');bounded.dispose();c.dispose();
});
test('collapsed fields stay compact while disclosure retains missing reasons and coverage',()=>{
 const {controller:c,nodes}=fixture();c.open();const markup=nodes.get('[data-asset-range-card]').innerHTML;
 const [visible,details]=markup.split('<details class="asset-range-method">');
 assert.doesNotMatch(visible,/<small>/);assert.match(visible,/>未取得<\/dd>/);
 assert.match(details,/行业分类及基准未核实/);assert.match(details,/覆盖：0\/8条/);
});
test('range signed values and extrema use existing rise/fall classes, neutral and unknown stay neutral',()=>{
 const {controller:c,nodes,context}=fixture();
 context.metadata={frequency:'daily',asset_history:{canonical_version:'v1',adjustment:'none',coverage:{scanned_ranges:[{start_date:'2026-01-01',end_date:'2026-01-08'}]}}};
 context.daily=daily.map((row,i)=>({...row,close:i===1?10:11}));c.setDates('2026-01-02','2026-01-02');
 let markup=nodes.get('[data-asset-range-card]').innerHTML;
 assert.match(markup,/<dt>涨跌幅<\/dt><dd class="asset-price-down">-9\.09%/);assert.match(markup,/<dt>收盘价<\/dt><dd class="asset-price-down">10\.00/);
 assert.match(markup,/<dt>极值回撤<\/dt><dd class="asset-price-down">-25\.00%/);assert.match(markup,/<dt>极值上涨<\/dt><dd class="asset-price-up">33\.33%/);
 assert.match(markup,/<dt>行业对比<\/dt><dd class="">未取得/);assert.match(markup,/<dt>前收盘价<\/dt><dd class="">11\.00/);
 c.setDates('2026-01-03','2026-01-03');markup=nodes.get('[data-asset-range-card]').innerHTML;assert.match(markup,/<dt>涨跌幅<\/dt><dd class="asset-price-up">10\.00%/);
 c.setDates('2026-01-04','2026-01-04');markup=nodes.get('[data-asset-range-card]').innerHTML;assert.match(markup,/<dt>涨跌幅<\/dt><dd class="">0\.00%/);
});
test('change amount uses its sign before price units while absolute OHLC still compare previous close',()=>{
 for(const [close,expected] of [[1050,'asset-price-up'],[950,'asset-price-down'],[1000,''],[null,'']]){
  const {controller:c,nodes,context}=fixture();
  context.metadata={frequency:'daily',asset_history:{canonical_version:'v1',adjustment:'none',coverage:{scanned_ranges:[{start_date:'2026-01-01',end_date:'2026-01-02'}]}}};
  context.daily=[{date:'2026-01-01',open:1000,high:1100,low:900,close:1000},{date:'2026-01-02',open:980,high:1100,low:900,close}];
  c.setDates('2026-01-02','2026-01-02');const markup=nodes.get('[data-asset-range-card]').innerHTML;
  const field=label=>{const match=new RegExp(`<dt>${label}<\\/dt><dd class="([^"]*)">([^<]*)<\\/dd>`).exec(markup);assert.ok(match,`${label} must be a visible metric`);return {tone:match[1],text:match[2]};};
  assert.deepEqual(field('涨跌'),{tone:expected,text:close===null?'未取得':(close-1000).toFixed(2)},`change amount ${close}`);
  assert.equal(field('收盘价').tone,expected,`closing absolute price ${close}`);
  assert.deepEqual(field('开盘价'),{tone:'asset-price-down',text:'980.00'});
  assert.equal(field('前收盘价').tone,'');
  if(close!==null){assert.deepEqual(field('最高价'),{tone:'asset-price-up',text:'1100.00'});assert.deepEqual(field('最低价'),{tone:'asset-price-down',text:'900.00'});}
  c.dispose();
 }
});
test('range card rise/fall selectors consume the same theme tokens as existing Wind readouts',()=>{
 const chartCSS=readFileSync(new URL('../../app/research_web/ui/asset-chart.css',import.meta.url),'utf8');
 const layoutCSS=readFileSync(new URL('../../app/research_web/ui/asset-layout.css',import.meta.url),'utf8');
 for(const [tone,token] of [['up','danger'],['down','green']]){
  assert.match(chartCSS,new RegExp(`\\.asset-range-card \\.asset-price-${tone}\\s*\\{\\s*color:var\\(--${token}\\)`));
  assert.match(layoutCSS,new RegExp(`\\.asset-wind-metrics \\.asset-price-${tone}\\s*\\{\\s*color:var\\(--${token}\\)`));
 }
});
test('secondary pointer and compatibility mouse cannot move, complete or cancel primary selection',()=>{
 const {controller:c}=fixture();c.begin({...event(30),type:'pointerdown',pointerId:1});const start=c.getState().gesture;
 for(const type of ['pointermove','pointerup','pointercancel'])assert.equal(c.capture({...event(120),type,pointerId:2}),false);
 assert.deepEqual(c.getState().gesture,start);
 for(const type of ['mousemove','mouseup'])assert.equal(c.capture({...event(120),type}),true);
 assert.deepEqual(c.getState().gesture,start);assert.equal(c.getState().selection,null);
 c.capture({...event(120),type:'pointerup',pointerId:1});assert.ok(c.getState().selection);
 assert.equal(c.capture({...event(120),type:'mouseup'}),false);
});
test('floating drag ignores foreign pointer and fallback mouse, while real mouse fallback remains usable',()=>{
 const {controller:c}=fixture();c.open();const original=c.getState().position;
 const header={setPointerCapture(){},releasePointerCapture(){}};const target={closest:s=>s==='[data-asset-range-drag]'?header:null};
 c.handle({...event(30,40,0),type:'pointerdown',pointerId:1,target});
 for(const type of ['pointermove','pointerup','pointercancel'])assert.equal(c.capture({...event(120),type,pointerId:2}),false);
 c.capture({...event(120),type:'mousemove'});assert.deepEqual(c.getState().position,original);
 c.capture({...event(50,60,0),type:'pointermove',pointerId:1});assert.notDeepEqual(c.getState().position,original);
 c.capture({...event(50,60,0),type:'pointerup',pointerId:1});
 c.begin({...event(30),type:'mousedown'});c.capture({...event(90),type:'mousemove'});c.capture({...event(90),type:'mouseup'});assert.equal(c.getState().selection.endDate,'2026-01-05');
});
test('reverse date edits normalize requested selection and inputs without losing invalid editable values',()=>{
 const {controller:c,nodes}=fixture();c.setDates('2026-01-07','2026-01-03');
 assert.deepEqual(c.getState().selection,{startDate:'2026-01-03',endDate:'2026-01-07'});assert.equal(nodes.get('[data-asset-range-selection]').hidden,false);
 assert.match(nodes.get('[data-asset-range-card]').innerHTML,/data-asset-range-start value="2026-01-03"/);assert.match(nodes.get('[data-asset-range-card]').innerHTML,/data-asset-range-end value="2026-01-07"/);
 c.setDates('','2026-01-07');assert.deepEqual(c.getState().selection,{startDate:'',endDate:'2026-01-07'});assert.match(nodes.get('[data-asset-range-card]').innerHTML,/日期无效或未填写/);
});
test('theme remount restores full card before and after first setOption when ECharts has no initial model',()=>{
 const f=mountedChart(),errors=[],frames=new Map();let nextFrame=0,html='',earlyConversions=0;
 const card=f.nodes.get('[data-asset-range-card]');
 Object.defineProperty(f.host,'innerHTML',{get:()=>html,set:value=>{html=value;card.innerHTML='';card.dataset={};card.hidden=true;}});
 const view=f.host.ownerDocument.defaultView,baseInit=view.echarts.init;
 view.requestAnimationFrame=fn=>{const id=++nextFrame;frames.set(id,fn);return id;};view.cancelAnimationFrame=id=>frames.delete(id);
 const flush=()=>{const callbacks=[...frames.values()];frames.clear();for(const fn of callbacks)fn();};
 view.echarts.init=(...args)=>{const chart=baseInit(...args);let ready=false;
  chart.getModel=()=>ready?{getComponent:()=>({coordinateSystem:{getRect:()=>({x:8,y:26,width:738,height:300})}})}:undefined;
  chart.setOption=()=>{ready=true;};
  chart.convertFromPixel=()=>{if(!ready){earlyConversions++;throw new Error('model not ready');}return 2;};
  chart.convertToPixel=index=>{if(!ready){earlyConversions++;throw new Error('model not ready');}return 8+92*(index+.5);};
  return chart;
 };
 const c=createAssetChartController({logger:(code,data)=>{if(data.status==='error')errors.push(code);}});
 c.configure(daily,'theme-ready',{frequency:'daily'});c.mount(f.host);flush();
 c.handle({type:'click',target:{closest:selector=>selector==='[data-asset-chart-action]'?{dataset:{assetChartAction:'range-open'}}:null}});
 const markup=card.innerHTML,left=card.style.left,top=card.style.top;assert.match(markup,/区间统计/);
 for(const theme of ['light','dark']){
  f.host.ownerDocument.documentElement={dataset:{theme}};c.mount(f.host);
  assert.equal(card.hidden,false);assert.equal(card.innerHTML,markup);assert.equal(card.style.left,left);assert.equal(card.style.top,top);
  flush();assert.equal(card.innerHTML,markup);assert.deepEqual(errors,[]);assert.equal(earlyConversions,0);
 }
 c.dispose();
});
test('context failure never commits dates without a matching calculation result',()=>{
 const {context,nodes}=fixture();let broken=false;const errors=[];
 const host={querySelector:key=>nodes.get(key),getBoundingClientRect:()=>({left:0,top:0,width:800,height:600})};
 const c=createRangeController({host,getContext:()=>{if(broken)throw new Error('not ready');return context;},logger:code=>errors.push(code)});
 broken=true;assert.equal(c.setDates('2026-01-02','2026-01-03'),false);assert.equal(c.getState().selection,null);assert.equal(c.getState().result,null);
 broken=false;c.setDates('2026-01-02','2026-01-03');const previous=c.getState();broken=true;
 assert.equal(c.setDates('2026-01-04','2026-01-05'),false);assert.deepEqual(c.getState().selection,previous.selection);assert.deepEqual(c.getState().result,previous.result);assert.ok(errors.includes('asset_range_dates'));
});
test('mobile range controls have 44px targets without changing desktop sizing',()=>{
 const css=readFileSync(new URL('../../app/research_web/ui/asset-chart.css',import.meta.url),'utf8');
 const mobile=css.slice(css.lastIndexOf('@media(max-width:619px)'));
 assert.match(mobile,/\.asset-range-card button\s*\{[^}]*min-width:44px;[^}]*min-height:44px;/);
 assert.match(mobile,/\.asset-range-card input\s*\{[^}]*min-height:44px;/);
 assert.match(mobile,/\.asset-range-method summary\s*\{[^}]*min-height:44px;[^}]*display:flex;[^}]*align-items:center;/);
 assert.match(css.slice(0,css.lastIndexOf('@media(max-width:619px)')),/\.asset-range-card button\s*\{[^}]*min-width:30px;[^}]*min-height:30px;/);
});
for(const foreignType of ['pointerup','pointercancel'])test(`app global cancel after foreign ${foreignType} leaves owned range gesture active`,()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});c.configure(daily,'global-cancel',{frequency:'daily'});c.mount(f.host);
 const down=f.handlers.get('pointerdown').find(item=>item.options===true).handler;
 const dispatch=event=>{const capture=f.windowHandlers.get(event.type).find(item=>item.options===true).handler;const handled=capture(event);if(!event.stopped)c.cancel();return handled;};
 const layer=f.nodes.get('[data-asset-range-layer]'),card=f.nodes.get('[data-asset-range-card]');
 down({...event(30),type:'pointerdown',pointerId:1});assert.equal(layer.hidden,false);
 assert.equal(dispatch({...event(120),type:foreignType,pointerId:2}),false);assert.equal(layer.hidden,false);assert.equal(card.hidden,true);
 const owned={...event(120),type:'pointerup',pointerId:1,stopPropagation(){this.stopped=true;},stopImmediatePropagation(){this.stopped=true;}};
 assert.equal(dispatch(owned),true);assert.equal(card.hidden,false);assert.match(card.innerHTML,/区间统计/);c.dispose();
});
test('range window cancellation, Esc and disposal still own their cleanup independently of app cancel',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});c.configure(daily,'owned-cancel',{frequency:'daily'});c.mount(f.host);
 const down=f.handlers.get('pointerdown').find(item=>item.options===true).handler;
 const layer=f.nodes.get('[data-asset-range-layer]'),card=f.nodes.get('[data-asset-range-card]');
 const begin=()=>{down({...event(30),type:'pointerdown',pointerId:1});assert.equal(layer.hidden,false);};
 const dispatch=event=>f.windowHandlers.get(event.type).find(item=>item.options===true).handler(event);
 begin();assert.equal(dispatch({type:'pointercancel',pointerId:1}),true);c.cancel();assert.equal(layer.hidden,true);
 begin();assert.equal(dispatch({type:'blur'}),true);c.cancel();assert.equal(layer.hidden,true);
 begin();c.handle({type:'keydown',key:'Escape',preventDefault(){},stopImmediatePropagation(){}});assert.equal(layer.hidden,true);
 begin();dispatch({...event(120),type:'pointerup',pointerId:1});assert.equal(card.hidden,false);
 c.handle({type:'keydown',key:'Escape',preventDefault(){},stopImmediatePropagation(){}});assert.equal(layer.hidden,true);assert.equal(card.hidden,true);
 begin();c.dispose();assert.equal(layer.hidden,true);assert.equal(card.hidden,true);assert.ok([...f.windowHandlers.values()].every(list=>list.length===0));
});
test('owned indicator dialog Esc closes before root catchall while preserving committed range',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});
 const dialog={open:false,innerHTML:'',querySelector:()=>null,showModal(){this.open=true;},close(){this.open=false;},addEventListener(){},removeEventListener(){}};
 f.nodes.set('[data-asset-indicator-manager]',dialog);
 c.configure(daily,'modal-escape',{frequency:'daily'});assert.equal(c.mount(f.host),true);
 const click=action=>({type:'click',target:{closest:s=>s==='[data-asset-chart-action]'?{dataset:{assetChartAction:action}}:null}});
 c.handle(click('range-open'));c.handle(click('indicator-manager'));assert.equal(dialog.open,true);
 const card=f.nodes.get('[data-asset-range-card]');const markup=card.innerHTML;
 const modalTarget={closest:s=>['dialog[open], [aria-modal="true"]','[data-asset-indicator-manager], [data-asset-indicator-parameter-dialog]'].includes(s)&&dialog.open?dialog:null};f.host.ownerDocument.activeElement=modalTarget;
 const escape={type:'keydown',key:'Escape',target:modalTarget,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;},stopImmediatePropagation(){this.stopped=true;}};
 f.windowHandlers.get('keydown')[0].handler(escape);
 // Match app.mjs: the slot must stop this before the root's unconditional
 // Escape preventDefault/render; otherwise native dialog cancel never runs.
 f.handlers.get('keydown').find(item=>item.options!==true).handler(escape);let rootCalls=0;
 if(!escape.stopped){rootCalls++;escape.preventDefault();}
 assert.equal(rootCalls,0);assert.equal(escape.defaultPrevented,true);assert.equal(escape.stopped,true);
 assert.equal(dialog.open,false);assert.equal(card.hidden,false);assert.equal(card.innerHTML,markup);
 f.host.ownerDocument.activeElement=null;
 const plain={type:'keydown',key:'Escape',target:{closest:()=>null},preventDefault(){},stopImmediatePropagation(){}};
 f.windowHandlers.get('keydown')[0].handler(plain);assert.equal(card.hidden,true);c.dispose();
});
test('parameter dialog Esc closes only parameters and composing Esc keeps owned dialog open',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});
 const make=()=>({open:false,innerHTML:'',querySelector:()=>null,showModal(){this.open=true;},close(){this.open=false;},addEventListener(){},removeEventListener(){}});
 const manager=make(),parameters=make();f.nodes.set('[data-asset-indicator-manager]',manager);f.nodes.set('[data-asset-indicator-parameter-dialog]',parameters);
 c.configure(daily,'parameter-escape',{frequency:'daily'});assert.equal(c.mount(f.host),true);
 const click=action=>({type:'click',target:{closest:s=>s==='[data-asset-chart-action]'?{dataset:{assetChartAction:action}}:null}});
 c.handle(click('range-open'));c.handle(click('indicator-manager'));c.handle(click('indicator-parameters-volume'));assert.equal(parameters.open,true);
 const target={closest:s=>['dialog[open], [aria-modal="true"]','[data-asset-indicator-manager], [data-asset-indicator-parameter-dialog]'].includes(s)?parameters:null};f.host.ownerDocument.activeElement=target;
 for(const isComposing of [true,false]){
  const escape={type:'keydown',key:'Escape',isComposing,target,preventDefault(){this.defaultPrevented=true;},stopPropagation(){this.stopped=true;}};
  f.windowHandlers.get('keydown')[0].handler(escape);f.handlers.get('keydown').find(item=>item.options!==true).handler(escape);
  let rootCalls=0;if(!escape.stopped){rootCalls++;escape.preventDefault();}
  assert.equal(rootCalls,0);assert.equal(parameters.open,isComposing);assert.equal(manager.open,true);assert.equal(f.nodes.get('[data-asset-range-card]').hidden,false);
  assert.equal(escape.defaultPrevented,isComposing?undefined:true);
 }
 c.dispose();
});
test('aria-modal drawer or modal-focused window Esc stays with its existing modal handler',()=>{
 const f=mountedChart(),c=createAssetChartController({logger:()=>{}});c.configure(daily,'drawer-escape',{frequency:'daily'});c.mount(f.host);
 c.handle({type:'click',target:{closest:s=>s==='[data-asset-chart-action]'?{dataset:{assetChartAction:'range-open'}}:null}});
 const modalTarget={closest:s=>s==='dialog[open], [aria-modal="true"]'?{}:null};
 for(const focusOnly of [false,true]){
  f.host.ownerDocument.activeElement=modalTarget;
  const escape={type:'keydown',key:'Escape',target:focusOnly?{}:modalTarget,preventDefault(){this.defaultPrevented=true;},stopImmediatePropagation(){this.stopped=true;}};
  f.windowHandlers.get('keydown')[0].handler(escape);c.handle(escape);
  assert.equal(escape.defaultPrevented,undefined);assert.equal(f.nodes.get('[data-asset-range-card]').hidden,false);
 }
 c.dispose();
});
