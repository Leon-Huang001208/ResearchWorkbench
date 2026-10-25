import { calculateRangeStatistics } from './asset-range-statistics.mjs';
import { formatAssetMagnitude, formatAssetVolume, assetPriceClass, assetChangeClass } from './asset-format.mjs';
import { escapeHTML as e } from './markdown.mjs';
import { safeLog } from './core.mjs';

const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
const COLUMNS = [
  [['changePct','涨跌幅'],['industryComparisonPct','行业对比'],['changeAmount','涨跌'],['previousClose','前收盘价'],['close','收盘价'],['meanPrice','原始均价'],['amplitudePct','振幅'],['amount','成交额'],['volume','成交量'],['turnoverPct','区间换手'],['dailyTurnoverPct','日均换手']],
  [['annualizedPct','年化收益率'],['maxDrawdownPct','极值回撤'],['maxRisePct','极值上涨'],['open','开盘价'],['high','最高价'],['low','最低价'],['upCount','阳线'],['downCount','阴线'],['flatCount','平线'],['maxVolume','最大量'],['minVolume','最小量']],
];
const REASONS = {range_dates_invalid:'日期无效或未填写',range_empty:'所选日期没有已取得日线',range_daily_required:'缺少日线底稿',industry_benchmark_unverified:'行业分类及基准未核实',previous_close_adjacency_unverified:'同版本前收相邻关系未核实',raw_mean_basis_or_input_unverified:'原始量额与价格基础未核实',range_scan_incomplete:'日期扫描范围不完整',amount_unit_unverified:'成交额单位未核实',volume_unit_unverified:'成交量单位未核实',turnover_unit_unverified:'换手单位未核实'};
const reasonText = code => REASONS[code] || '必需数据或覆盖未完整取得';
const consume = event => {event.preventDefault?.();event.stopImmediatePropagation?.();event.stopPropagation?.();};

/** Range state deliberately has no reference to viewport, selected-date or chips mutations. */
export function createRangeController({host,getContext,logger=safeLog}) {
  let selection=null, result=null, gesture=null, position=null, floating=null, disposed=false, suppressClick=false;
  const find=selector=>host?.querySelector?.(selector);
  const report=(action,status='ok')=>{try{logger(`asset_range_${action}`,{status});}catch{/* Logging cannot interrupt chart gestures. */}};
  const guarded=(action,fn)=>{try{return disposed?false:fn();}catch{report(action,'error');return false;}};
  const point=event=>{const rect=host.getBoundingClientRect();return {x:event.clientX-rect.left,y:event.clientY-rect.top};};
  const inPlot=(p,plot)=>plot && p.x>=plot.left && p.x<=plot.left+plot.width && p.y>=plot.top && p.y<=plot.top+plot.height;
  const barRange=(context,a,b)=>{
    const first=context.displayBars[Math.min(a,b)],last=context.displayBars[Math.max(a,b)];
    return first && last ? {startDate:first.source_start_date||first.date,endDate:last.source_end_date||last.date}:null;
  };
  const indexAt=(context,x)=>clamp(Math.round(context.indexAt(clamp(x,context.plot.left,context.plot.left+context.plot.width))),context.visibleStart,context.visibleEnd-1);
  const focusChart=()=>find('[data-asset-echarts]')?.focus?.({preventScroll:true});
  const matchingPointer=(event,active=floating||gesture)=>!active||((active.id??active.pointerId)==null?event.pointerId==null:event.pointerId===(active.id??active.pointerId));
  function releaseFloating(){const previous=floating;floating=null;if(previous){try{previous.node.releasePointerCapture?.(previous.id);}catch{report('capture_release','error');}}}
  function clear(focus=true){const changed=Boolean(gesture||selection||floating);gesture=null;selection=null;result=null;position=null;releaseFloating();render();if(focus)focusChart();if(changed)report('clear');return true;}
  function cancel(){if(!gesture && !floating)return false;gesture=null;releaseFloating();render();report('cancel');return true;}
  function constrain(){
    if(!position)return;const rect=host.getBoundingClientRect(),card=find('[data-asset-range-card]');
    const view=host.ownerDocument?.defaultView;
    const mobile=view?.matchMedia?.('(max-width: 619px)')?.matches===true;
    const visibleTop=mobile?0:Math.max(0,-rect.top);
    const visibleBottom=mobile||!Number.isFinite(view?.innerHeight)?rect.height:Math.min(rect.height,view.innerHeight-rect.top-8);
    const availableHeight=Math.max(0,visibleBottom-visibleTop);
    if(card?.style)card.style.maxHeight=mobile?'none':`${availableHeight}px`;
    const size=card?.getBoundingClientRect?.()||{width:440,height:420};
    position={x:clamp(position.x,0,Math.max(0,rect.width-size.width)),y:clamp(position.y,visibleTop,Math.max(visibleTop,visibleBottom-Math.min(size.height,availableHeight)))};
    if(card?.style){card.style.left=`${position.x}px`;card.style.top=`${position.y}px`;}
  }
  function render(){return guarded('render',()=>{
    const context=getContext(),layer=find('[data-asset-range-layer]'),box=find('[data-asset-range-selection]'),card=find('[data-asset-range-card]');
    if(layer)layer.hidden=!selection&&!gesture;
    if(box){
      let left=null,right=null;
      if(gesture){left=Math.min(gesture.x,gesture.currentX);right=Math.max(gesture.x,gesture.currentX);}
      else if(selection && context.plot){
        const indices=context.displayBars.map((bar,i)=>({bar,i})).filter(({bar,i})=>i>=context.visibleStart&&i<context.visibleEnd&&(bar.source_end_date||bar.date)>=selection.startDate&&(bar.source_start_date||bar.date)<=selection.endDate).map(({i})=>i);
        if(indices.length){const step=context.plot.width/Math.max(1,context.visibleEnd-context.visibleStart);left=context.pixelAt(indices[0])-step/2;right=context.pixelAt(indices.at(-1))+step/2;}
      }
      box.hidden=left===null||!context.plot;
      if(!box.hidden){const plot=context.plot;left=clamp(left,plot.left,plot.left+plot.width);right=clamp(right,plot.left,plot.left+plot.width);Object.assign(box.style,{left:`${left}px`,top:`${plot.top}px`,width:`${Math.max(1,right-left)}px`,height:`${plot.height}px`});}
    }
    if(card){card.hidden=!selection;if(selection && result){
      const value=(key,metric)=>{
        if(metric.status!=='ok')return '未取得';
        if(['volume','maxVolume','minVolume'].includes(key))return formatAssetVolume(metric.value,metric.unit,context.metadata.assetIdentity);
        if(key==='amount')return formatAssetMagnitude(metric.value,metric.unit,'',{compact:true});
        return `${Number(metric.value).toFixed(metric.unit==='count'?0:2)}${metric.unit==='percent'?'%':''}`;
      };
      const fields=COLUMNS.map(column=>`<dl>${column.map(([key,label])=>{const m=result.metrics[key],coverage=m.coverage;const missing=m.status!=='ok';const title=[m.definition,m.unit?`来源单位：${m.unit}`:'',missing?reasonText(m.reason):'',`${coverage.validCount}/${coverage.expectedCount}条${coverage.scanComplete?'，扫描完整':'，扫描未完整核实'}`].filter(Boolean).join('；');const tone=['changePct','changeAmount','annualizedPct','maxDrawdownPct','maxRisePct'].includes(key)?assetChangeClass(m.value):m.unit==='price'?assetPriceClass(m.value,result.metrics.previousClose.value):'';return `<div title="${e(title)}"><dt>${label}</dt><dd class="${tone}">${e(value(key,m))}</dd></div>`;}).join('')}</dl>`).join('');
      const definitions=COLUMNS.flat().map(([key,label])=>{const m=result.metrics[key];return `<div><dt>${e(label)}</dt><dd>${e(m.definition)}${m.status==='ok'?'':`；未取得：${e(reasonText(m.reason))}`}；覆盖：${m.coverage.validCount}/${m.coverage.expectedCount}条${m.coverage.scanComplete?'，扫描完整':'，扫描未完整核实'}</dd></div>`;}).join('');
      const markup=`<header data-asset-range-drag><strong>区间统计</strong><button type="button" data-asset-range-close aria-label="关闭区间统计">×</button></header><div class="asset-range-dates"><label>起始<input type="date" data-asset-range-start value="${e(selection.startDate)}"></label><label>结束<input type="date" data-asset-range-end value="${e(selection.endDate)}"></label></div><p class="asset-range-period" role="status">${result.range.startDate?`${e(result.range.startDate)} — ${e(result.range.endDate)} · ${result.range.count}个交易日`:e(reasonText(result.diagnostics[0]))}</p><div class="asset-range-fields">${fields}</div><details class="asset-range-method"><summary>统计口径与公式</summary><dl>${definitions}</dl></details>`;
      if(card.dataset?.rangeMarkup!==markup){card.innerHTML=markup;if(card.dataset)card.dataset.rangeMarkup=markup;}
      constrain();
    }}return true;
  });}
  function setDates(startDate,endDate){return guarded('dates',()=>{
    const requested={startDate,endDate},context=getContext();
    const calculated=calculateRangeStatistics(context.daily,requested,context.metadata);
    // Commit the date/result pair together. A failed context read must never
    // expose a new selection backed by a null or previous calculation.
    selection=calculated.range.requestedStart&&calculated.range.requestedEnd?{startDate:calculated.range.requestedStart,endDate:calculated.range.requestedEnd}:requested;
    result=calculated;render();report('calculate',result.range.count?'ok':'unavailable');return true;
  });}
  function open(){return guarded('open',()=>{const context=getContext();const next=barRange(context,context.visibleStart,context.visibleEnd-1);if(!next)return false;position={x:context.plot?.left||0,y:(context.plot?.top||0)+16};setDates(next.startDate,next.endDate);find('[data-asset-range-start]')?.focus?.({preventScroll:true});return true;});}
  function begin(event){return guarded('begin',()=>{
    if(event.button!==2)return false;const context=getContext(),p=point(event);if(!context.daily.length||!inPlot(p,context.plot))return false;
    if(floating||gesture){if(event.type!=='mousedown'&&!matchingPointer(event))return false;consume(event);return true;}
    consume(event);gesture={x:p.x,currentX:p.x,index:indexAt(context,p.x),pointerId:event.pointerId};suppressClick=true;render();report('begin');return true;
  });}
  function move(event){return guarded('move',()=>{if(!matchingPointer(event))return false;if(floating){consume(event);const p=point(event);position={x:floating.x+p.x-floating.startX,y:floating.y+p.y-floating.startY};constrain();return true;}if(!gesture)return false;consume(event);const context=getContext();gesture.currentX=clamp(point(event).x,context.plot.left,context.plot.left+context.plot.width);render();return true;});}
  function end(event){return guarded('end',()=>{if(!matchingPointer(event))return false;if(floating){consume(event);releaseFloating();return true;}if(!gesture)return false;consume(event);const context=getContext();const x=clamp(point(event).x,context.plot.left,context.plot.left+context.plot.width),start=gesture;gesture=null;
    if(Math.abs(x-start.x)>4){const next=barRange(context,start.index,indexAt(context,x));if(next){position={x:Math.min(start.x,x)+12,y:context.plot.top+18};setDates(next.startDate,next.endDate);focusChart();}}
    render();return true;
  });}
  function handle(event){return guarded('interaction',()=>{
    const target=event.target;
    if(event.type==='keydown'&&event.key==='Escape'&&(gesture||selection||floating)){consume(event);if(gesture||floating)cancel();else clear();focusChart();return true;}
    if(event.type==='click'&&target?.closest?.('[data-asset-range-close]')){consume(event);return clear();}
    if(event.type==='change'&&target?.matches?.('[data-asset-range-start], [data-asset-range-end]')){const start=find('[data-asset-range-start]')?.value||'',end=find('[data-asset-range-end]')?.value||'';consume(event);setDates(start,end);find(target.matches('[data-asset-range-start]')?'[data-asset-range-start]':'[data-asset-range-end]')?.focus?.({preventScroll:true});return true;}
    if(event.type==='pointerdown'&&event.button===0&&target?.closest?.('[data-asset-range-drag]')&&!target?.closest?.('button')){if((floating||gesture)&&!matchingPointer(event))return false;consume(event);const p=point(event),node=target.closest('[data-asset-range-drag]');position ||= {x:0,y:0};floating={node,id:event.pointerId,startX:p.x,startY:p.y,...position};node.setPointerCapture?.(event.pointerId);return true;}
    return Boolean(target?.closest?.('[data-asset-range-card]')?.matches?.('[data-asset-range-card]'));
  });}
  function capture(event){return guarded('capture',()=>{
    if(event.type==='lostpointercapture')return event.pointerId!=null&&(floating?.id===event.pointerId||gesture?.pointerId===event.pointerId)?cancel():false;
    if((floating||gesture)&&['mousemove','mouseup'].includes(event.type)&&!matchingPointer(event)){consume(event);return true;}
    if((floating||gesture)&&['pointermove','mousemove'].includes(event.type))return move(event);
    if((floating||gesture)&&['pointerup','mouseup'].includes(event.type))return end(event);
    if(event.type==='pointercancel')return matchingPointer(event)?cancel():false;
    if(event.type==='blur')return cancel();
    if(targetInCard(event)){if(event.type==='pointerdown')return handle(event);return false;}
    if(['pointerdown','mousedown'].includes(event.type)){if(event.button===0)suppressClick=false;return begin(event);}
    if(['pointermove','mousemove'].includes(event.type))return move(event);
    if(['pointerup','mouseup'].includes(event.type))return end(event);
    if(event.type==='contextmenu'&&inPlot(point(event),getContext().plot)){consume(event);return true;}
    if(event.type==='click'&&suppressClick){suppressClick=false;consume(event);return true;}
    return false;
  });}
  const targetInCard=event=>Boolean(event.target?.closest?.('[data-asset-range-card]'));
  function restore(snapshot){return guarded('restore',()=>{
    if(!snapshot?.selection)return false;
    position=snapshot.position?{...snapshot.position}:null;
    return setDates(snapshot.selection.startDate,snapshot.selection.endDate);
  });}
  return {begin,move,end,open,setDates,clear,cancel,render,restore,handle,capture,getState:()=>({selection:selection?{...selection}:null,result,gesture:gesture?{...gesture}:null,position:position?{...position}:null}),dispose(){cancel();clear(false);disposed=true;}};
}
