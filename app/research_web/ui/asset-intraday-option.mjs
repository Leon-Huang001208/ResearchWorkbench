import {formatAssetMagnitude,formatAssetVolume} from './asset-format.mjs';
import {escapeHTML as e} from './markdown.mjs';
const price=n=>Number.isFinite(n)?n.toFixed(2):'—';
const cash=n=>formatAssetMagnitude(n,'元','',{compact:true});
/** Fixed exchange-time slots are empty axis scaffolding, never synthesized prices. */
export function intradayOption(data, {dark = false, selected = 0, updateReadout = () => {}} = {}) {
  const qty=n=>formatAssetVolume(n,'share',`stock:${data.asset}`,{compact:true});
  const fg=dark?'#d1d5db':'#242424', grid=dark?'rgba(148,163,184,.18)':'#e8e8e5';
  const rowByTime=new Map(data.rows.map((row,index)=>[row.time,{row,index}]));
  const times=['09:25'];
  for(const [start,end] of [[571,690],[781,900]]) for(let t=start;t<=end;t++) times.push(`${String(Math.floor(t/60)).padStart(2,'0')}:${String(t%60).padStart(2,'0')}`);
  for(const time of rowByTime.keys()) if(!times.includes(time))times.push(time);
  times.sort();
  const rows=times.map(time=>rowByTime.get(time)?.row||null),prev=data.previous_close;
  const prices=rows.map(row=>row?.price??null),means=rows.map(row=>row?.mean??null);
  const span=Math.max(...[...prices,...means].filter(Number.isFinite).map(value=>Math.abs(value-prev)),prev*.001)*1.07;
  return {
    backgroundColor:'transparent',animation:false,
    legend:{icon:'line',data:['价格','计算均价'],left:8,top:0,textStyle:{color:fg,fontSize:12}},
    grid:[{left:8,right:62,top:30,height:365,containLabel:true},{left:8,right:62,top:425,height:90,containLabel:true}],
    axisPointer:{link:[{xAxisIndex:'all'}],label:{backgroundColor:dark?'#343430':'#ddd'}},
    tooltip:{trigger:'axis',confine:true,axisPointer:{type:'cross'},formatter:points=>{
      const slot=points[0]?.dataIndex;
      const found=rowByTime.get(times[slot]);
      if(!found)return `${e(times[slot]||'')} 暂无分钟记录`;
      updateReadout(found.index);const r=found.row;
      return `${e(data.trading_date)} ${e(r.time)}<br>价格 ${price(r.price)}<br>计算均价 ${price(r.mean)}<br>分钟量 ${qty(r.volume_shares)}<br>分钟额 ${cash(r.amount)}`;
    }},
    xAxis:[{type:'category',gridIndex:0,data:times,boundaryGap:false,axisLabel:{show:false},axisLine:{lineStyle:{color:grid}},axisTick:{show:false}},
      {type:'category',gridIndex:1,data:times,axisLabel:{color:fg,interval:(_i,time)=>['09:25','10:30','11:30','14:00','15:00'].includes(time),formatter:time=>time==='11:30'?'11:30 / 13:00':time,fontSize:11},axisTick:{show:false},axisLine:{lineStyle:{color:grid}}}],
    yAxis:[{type:'value',gridIndex:0,min:prev-span,max:prev+span,axisLabel:{color:fg,formatter:n=>n.toFixed(2)},splitLine:{lineStyle:{color:grid}},axisPointer:{label:{formatter:p=>Number(p.value).toFixed(2)}}},
      {type:'value',gridIndex:0,position:'right',min:-span/prev*100,max:span/prev*100,axisLabel:{color:fg,formatter:n=>n.toFixed(2)+'%'},splitLine:{show:false}},
      {type:'value',gridIndex:1,axisLabel:{color:fg,formatter:n=>formatAssetMagnitude(n,'手','',{compact:true})},splitLine:{lineStyle:{color:grid}}}],
    series:[{name:'价格',type:'line',xAxisIndex:0,yAxisIndex:0,data:prices,showSymbol:data.rows.length===1,itemStyle:{color:dark?'#eeeeea':'#246eac'},lineStyle:{width:1.5,color:dark?'#eeeeea':'#246eac'},markLine:{silent:true,symbol:'none',label:{show:true,position:'insideEndTop',formatter:'昨收 '+price(prev),color:fg},lineStyle:{color:dark?'#9a9a91':'#999',type:'dashed'},data:[{yAxis:prev}]}},
      {name:'计算均价',type:'line',xAxisIndex:0,yAxisIndex:0,data:means,showSymbol:data.rows.length===1,itemStyle:{color:dark?'#e8ce50':'#a07806'},lineStyle:{width:1.2,color:dark?'#e8ce50':'#a07806'}},
      {name:'分钟成交量（手）',type:'bar',xAxisIndex:1,yAxisIndex:2,data:rows.map((r,i)=>r?{value:r.volume_lots,itemStyle:{color:r.price>(rows[i-1]?.price??prev)?'#ef4e53':r.price<(rows[i-1]?.price??prev)?'#00b685':'#999'}}:null),barMaxWidth:5}],
    graphic:[{type:'text',left:10,top:402,silent:true,style:{text:'分钟成交量（手）',fill:fg,fontSize:12}}],
  };
}
