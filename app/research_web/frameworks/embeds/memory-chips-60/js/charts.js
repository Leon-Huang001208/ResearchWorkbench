/* ============ ECharts 主题与 26 图构建器 ============ */
const C = { bg:'#0b0e14', panel:'#10141d', line:'#1e2634', txt:'#c9d4e3', dim:'#6b7a90',
  amber:'#e6a817', red:'#e74c3c', green:'#2ecc71', blue:'#4a90d9', teal:'#1abc9c', purple:'#9b59b6', orange:'#e67e22' };
const F = "'IBM Plex Mono','JetBrains Mono',ui-monospace,monospace";
const AX = (o={}) => Object.assign({ axisLine:{lineStyle:{color:C.line}}, axisLabel:{color:C.dim,fontFamily:F,fontSize:10},
  splitLine:{lineStyle:{color:C.line,type:'dashed',opacity:.5}} }, o);
const TT = { backgroundColor:'#141a26', borderColor:C.line, textStyle:{color:C.txt,fontFamily:F,fontSize:11} };

function yearsVals(obj){ return YEARS.map(y => obj[y] !== undefined ? obj[y] : null); }

const builders = {

/* 01 周期墙 */
wallTimeline(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:6},
  grid:{left:56,right:20,top:70,bottom:64},
  xAxis:AX({type:'category',data:YEARS,axisLabel:Object.assign(AX().axisLabel,{interval:4,rotate:45})}),
  yAxis:AX({type:'value',name:'$B · 对数',nameTextStyle:{color:C.dim,fontFamily:F},type:'log',min:0.01}),
  dataZoom:[{type:'inside'},{type:'slider',height:16,bottom:8,borderColor:C.line,textStyle:{color:C.dim}}],
  series:[
    { name:'DRAM 收入', type:'line', data:yearsVals(DRAM_REV), connectNulls:true, smooth:.3,
      lineStyle:{color:C.amber,width:2}, itemStyle:{color:C.amber}, symbol:'none',
      markArea:{ itemStyle:{opacity:.10}, label:{color:'#8fa0b5',fontFamily:F,fontSize:9,position:'insideTop'},
        data:CYCLE_WINDOWS.map(w=>[{name:w.name,xAxis:w.start,itemStyle:{color:w.color}},{xAxis:w.end}]) },
      markPoint:{ symbol:'pin', symbolSize:34, label:{color:'#000',fontSize:8,fontFamily:F},
        data:[
          {coord:[YEARS.indexOf(1995),41], value:'$41B', itemStyle:{color:C.amber}},
          {coord:[YEARS.indexOf(2018),99.7], value:'$99.7B', itemStyle:{color:C.red}},
          {coord:[YEARS.indexOf(2023),51.9], value:'$51.9B', itemStyle:{color:C.dim}},
          {coord:[YEARS.indexOf(2026),372], value:'$372B·E', itemStyle:{color:C.green}},
        ]}
    },
    { name:'NAND 收入', type:'line', data:yearsVals(NAND_REV), connectNulls:true, smooth:.3,
      lineStyle:{color:C.teal,width:2}, itemStyle:{color:C.teal}, symbol:'none' }
  ]};},

/* 02 厂商生命线（自定义甘特） */
vendorLifeline(){
  const cats = VENDOR_LINES.map(v=>v.name);
  const data=[];
  VENDOR_LINES.forEach((v,i)=>v.seg.forEach(s=>data.push({value:[s[0],s[1],i],itemStyle:{color:s[2]},name:v.name,note:v.note})));
  return {
  tooltip:Object.assign({},TT,{formatter:p=>{const v=VENDOR_LINES[p.value[2]];return `<b>${v.name}</b><br>${p.value[0]}–${p.value[1]}<br><span style="color:#8fa0b5">${v.note}</span>`;}}),
  grid:{left:130,right:20,top:20,bottom:40},
  xAxis:AX({type:'value',min:1970,max:2028,interval:10}),
  yAxis:AX({type:'category',data:cats,inverse:true,axisLabel:Object.assign(AX().axisLabel,{fontSize:9}),splitLine:{show:false}}),
  series:[{ type:'custom',
    renderItem:(p,api)=>{ const y=api.coord([0,api.value(2)])[1]; const x1=api.coord([api.value(0),0])[0]; const x2=api.coord([api.value(1),0])[0];
      return {type:'rect',shape:{x:x1,y:y-6,width:Math.max(x2-x1,3),height:12,r:3},style:api.style()}; },
    encode:{x:[0,1],y:2}, data } ]};},

/* 03 技术演进树 */
techTree(){ return {
  tooltip:TT,
  series:[{ type:'tree', data:[TECH_TREE], left:'6%', right:'22%', top:'2%', bottom:'2%',
    symbol:'roundRect', symbolSize:[10,10], orient:'LR',
    label:{ color:C.txt, fontFamily:"'Noto Sans SC',sans-serif", fontSize:10, position:'right', verticalAlign:'middle' },
    leaves:{ label:{ color:C.amber, fontSize:10 } },
    lineStyle:{ color:C.line, width:1.2 }, itemStyle:{ color:C.blue, borderColor:C.amber },
    expandAndCollapse:false, emphasis:{focus:'descendant'} }]};},

/* 04 制程节点迁移 */
nodeMigration(){ return {
  tooltip:Object.assign({},TT,{formatter:p=>`<b>${p.data.year}</b><br>${p.data.label}`}),
  grid:{left:70,right:24,top:30,bottom:40},
  xAxis:AX({type:'value',min:1968,max:2028,interval:10}),
  yAxis:AX({type:'log',min:10,max:20000,name:'nm (log)',nameTextStyle:{color:C.dim,fontFamily:F},
    axisLabel:Object.assign(AX().axisLabel,{formatter:v=>v>=1000?(v/1000)+'µm':v+'nm'})}),
  series:[{ type:'line', step:'end', symbol:'circle', symbolSize:6,
    data:NODE_MIGRATION.map(d=>({value:[d.year,d.node],year:d.year,label:d.label})),
    lineStyle:{color:C.purple,width:2}, itemStyle:{color:C.purple},
    markPoint:{symbol:'pin',symbolSize:40,label:{color:'#000',fontSize:8,fontFamily:F},data:[
      {coord:[2021,14],value:'EUV',itemStyle:{color:C.amber}},
      {coord:[2025,11.5],value:'1c',itemStyle:{color:C.red}} ]}}]};},

/* 05 HBM4 与先进封装 */
hbmPackage(){ return {
  tooltip:TT, legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:[{left:56,right:24,top:34,height:'36%'},{left:56,right:24,top:'58%',bottom:36}],
  xAxis:[ AX({type:'category',data:HBM_GEN.map(g=>g.gen),gridIndex:0,axisLabel:Object.assign(AX().axisLabel,{fontSize:8,rotate:18})}),
          AX({type:'category',data:COWOS_CAP.map(c=>c.year),gridIndex:1}) ],
  yAxis:[ AX({type:'value',gridIndex:0,name:'GB/s',nameTextStyle:{color:C.dim,fontFamily:F}}),
          AX({type:'value',gridIndex:1,name:'千片/月',nameTextStyle:{color:C.dim,fontFamily:F}}) ],
  series:[
    { name:'HBM 单堆带宽', type:'bar', xAxisIndex:0,yAxisIndex:0, barWidth:'55%',
      data:HBM_GEN.map(g=>({value:g.bw,itemStyle:{color:g.color}})), label:{show:true,position:'top',color:C.dim,fontFamily:F,fontSize:9} },
    { name:'TSMC CoWoS 月产能', type:'bar', xAxisIndex:1,yAxisIndex:1, barWidth:'55%',
      data:COWOS_CAP.map(c=>c.cap), itemStyle:{color:C.orange}, label:{show:true,position:'top',color:C.dim,fontFamily:F,fontSize:9},
      markLine:{data:[{yAxis:75,label:{formatter:'2025 售罄线',color:C.red,fontFamily:F}}],lineStyle:{color:C.red,type:'dashed'}} }
  ]};},

/* 06/07 供需缺口 */
_gap(sup,dem,color,name){ return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>v+'%'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:46,right:20,top:34,bottom:36},
  xAxis:AX({type:'category',data:GAP_YEARS}),
  yAxis:AX({type:'value',name:'bit 增速 %',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[
    { name:'需求 bit 增速', type:'line', data:dem, lineStyle:{color:color,width:2}, itemStyle:{color:color}, symbolSize:5, areaStyle:{opacity:.06} },
    { name:'供给 bit 增速', type:'line', data:sup, lineStyle:{color:C.dim,width:2,type:'dashed'}, itemStyle:{color:C.dim}, symbolSize:5 },
    { name:'缺口(需求-供给)', type:'bar', data:dem.map((d,i)=>+(d-sup[i]).toFixed(1)), barWidth:'40%',
      itemStyle:{color:p=>p.value>=0?C.green:C.red,opacity:.85} },
    { name:name, type:'line', data:[], markLine:{data:[{yAxis:0}],lineStyle:{color:C.line},label:{show:false}} }
  ]};},
dramGap(){ return this._gap(DRAM_SUPPLY_BIT,DRAM_DEMAND_BIT,C.amber,''); },
nandGap(){ return this._gap(NAND_SUPPLY_BIT,NAND_DEMAND_BIT,C.teal,''); },

/* 08 库存温度计 */
invThermo(){ return {
  tooltip:Object.assign({},TT,{formatter:p=>`${INV_QUARTERS[p.dataIndex]}<br>库存 ${p.value} 天`}),
  grid:{left:46,right:20,top:30,bottom:52},
  xAxis:AX({type:'category',data:INV_QUARTERS,axisLabel:Object.assign(AX().axisLabel,{rotate:40,fontSize:9})}),
  yAxis:AX({type:'value',name:'天',nameTextStyle:{color:C.dim,fontFamily:F}}),
  visualMap:{ min:40,max:140,dimension:1,orient:'horizontal',left:'center',bottom:0,
    inRange:{color:[C.green,C.amber,C.red]}, textStyle:{color:C.dim,fontFamily:F,fontSize:9}, itemHeight:80 },
  series:[{ type:'line', data:INV_DAYS, smooth:.3, symbolSize:7, lineStyle:{width:2.5},
    areaStyle:{opacity:.12},
    markLine:{data:[{yAxis:90,label:{formatter:'警戒线 90 天',color:C.amber,fontFamily:F,fontSize:9}},{yAxis:60,label:{formatter:'短缺线 60 天',color:C.green,fontFamily:F,fontSize:9}}],
      lineStyle:{type:'dashed'}} }]};},

/* 09/10 ASP */
_asp(data,color,name){ return {
  tooltip:Object.assign({},TT,{trigger:'axis'}),
  grid:{left:52,right:20,top:30,bottom:40},
  xAxis:AX({type:'category',data:ASP_Q,axisLabel:Object.assign(AX().axisLabel,{rotate:40,fontSize:9})}),
  yAxis:AX({type:'log',name:'指数(log)',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[{ type:'line', data, smooth:.25, symbol:'circle', symbolSize:5,
    lineStyle:{color:color,width:2.5}, itemStyle:{color:color}, areaStyle:{opacity:.08},
    markPoint:{symbol:'pin',symbolSize:36,label:{color:'#000',fontSize:8,fontFamily:F},data:[
      {type:'max',itemStyle:{color:C.green}},{type:'min',itemStyle:{color:C.red}}]}}]};},
dramAsp(){ return this._asp(DRAM_ASP,C.amber,'DRAM'); },
nandAsp(){ return this._asp(NAND_ASP,C.teal,'NAND'); },

/* 11 Capex vs 盈利 */
capexMargin(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:50,right:50,top:34,bottom:36},
  xAxis:AX({type:'category',data:CAPEX_YEARS}),
  yAxis:[AX({type:'value',name:'Capex $B',nameTextStyle:{color:C.dim,fontFamily:F}}),
         AX({type:'value',name:'营业利润率 %',nameTextStyle:{color:C.dim,fontFamily:F},splitLine:{show:false}})],
  series:[
    { name:'存储行业 Capex', type:'bar', data:MEM_CAPEX, barWidth:'50%', itemStyle:{color:C.blue,opacity:.85},
      markLine:{symbol:'none',data:[],lineStyle:{color:C.red}}},
    { name:'行业营业利润率', type:'line', yAxisIndex:1, data:MEM_OP_MARGIN, lineStyle:{color:C.amber,width:2.5},
      itemStyle:{color:C.amber}, symbolSize:6,
      markLine:{data:[{yAxis:0,lineStyle:{color:C.line},label:{show:false}}]} }
  ]};},

/* 12 Top-5 份额 */
top5Share(){
  const colors=[C.dim,C.green,C.teal,C.red,C.orange,'#4a5568'];
  return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>v+'%'}),
  legend:{textStyle:{color:C.dim,fontFamily:F,fontSize:9},top:2,type:'scroll'},
  grid:{left:44,right:16,top:56,bottom:36},
  xAxis:AX({type:'category',data:SHARE_YEARS,boundaryGap:false}),
  yAxis:AX({type:'value',max:100,name:'%',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:Object.keys(SHARE_SERIES).map((k,i)=>({ name:k,type:'line',stack:'s',areaStyle:{opacity:.7},
    symbol:'none',lineStyle:{width:.5,color:colors[i]},itemStyle:{color:colors[i]},data:SHARE_SERIES[k]}))};},

/* 13 国产产业链 */
chinaChain(){ return {
  tooltip:TT,
  series:[{ type:'graph', layout:'none', roam:false,
    symbol:'roundRect', symbolSize:[12,12],
    data:CHINA_CHAIN.nodes.map((n,i)=>({ name:n.name, x:n.x*320+40, y:n.y*86+30,
      symbolSize: n.x===1&&n.y===0 ? 26 : 16,
      itemStyle:{color: n.x===1&&n.y===0 ? C.amber : (n.x===3? C.green : C.blue)} })),
    links:CHINA_CHAIN.links.map(l=>({source:l[0],target:l[1],lineStyle:{color:'#3a4658',width:1.5,curveness:.15}})),
    label:{show:true,position:'bottom',color:C.txt,fontSize:9,fontFamily:"'Noto Sans SC',sans-serif",lineHeight:13},
    edgeSymbol:['none','arrow'], edgeSymbolSize:6, emphasis:{focus:'adjacency'} }]};},

/* 14 AI Server 价值量 */
aiServerValue(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis',axisPointer:{type:'shadow'},
    formatter:ps=>{let h=`<b>${ps[0].name}</b>`;let t=0;ps.forEach(p=>{t+=p.value;h+=`<br>${p.marker}${p.seriesName}: $${p.value.toLocaleString()}`;});return h+`<br><b>合计 $${t.toLocaleString()}</b>`;}}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:70,right:20,top:34,bottom:36},
  xAxis:AX({type:'category',data:SERVER_VALUE.map(s=>s.name),axisLabel:Object.assign(AX().axisLabel,{fontSize:9})}),
  yAxis:AX({type:'log',name:'$/台 (log)',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[
    {name:'DRAM(DDR5/RDIMM)',type:'bar',stack:'v',data:SERVER_VALUE.map(s=>s.dram),itemStyle:{color:C.blue},barWidth:'46%'},
    {name:'HBM',type:'bar',stack:'v',data:SERVER_VALUE.map(s=>s.hbm||0),itemStyle:{color:C.red}},
    {name:'NAND/eSSD',type:'bar',stack:'v',data:SERVER_VALUE.map(s=>s.ssd),itemStyle:{color:C.teal},
     label:{show:true,position:'top',color:C.amber,fontFamily:F,fontSize:10,formatter:p=>'$'+SERVER_VALUE[p.dataIndex].total.toLocaleString()}}
  ]};},

/* 15 机制矩阵 */
mechMatrix(){
  const data=[]; MECH_MATRIX.forEach((row,i)=>row.forEach((v,j)=>data.push([j,i,v])));
  return {
  tooltip:Object.assign({},TT,{formatter:p=>`<b>${MECH_CYCLES[p.value[1]]}</b><br>${MECH_PHASES[p.value[0]]}: ${p.value[2]}/10`}),
  grid:{left:120,right:20,top:20,bottom:70},
  xAxis:AX({type:'category',data:MECH_PHASES,axisLabel:Object.assign(AX().axisLabel,{fontSize:9,interval:0,rotate:14}),splitLine:{show:false}}),
  yAxis:AX({type:'category',data:MECH_CYCLES,axisLabel:Object.assign(AX().axisLabel,{fontSize:9}),splitLine:{show:false}}),
  visualMap:{min:0,max:10,orient:'horizontal',left:'center',bottom:0,itemHeight:70,
    inRange:{color:['#141a26','#3a5a8c','#e6a817','#e74c3c']},textStyle:{color:C.dim,fontFamily:F,fontSize:9}},
  series:[{type:'heatmap',data,label:{show:true,color:'#fff',fontFamily:F,fontSize:10},
    itemStyle:{borderColor:C.bg,borderWidth:2}}]};},

/* 16 情景树 */
scenarioTree(){ return {
  tooltip:TT,
  series:[{ type:'tree', data:[SCENARIO_TREE], left:'2%', right:'30%', top:'6%', bottom:'6%', orient:'LR',
    symbol:'roundRect', symbolSize:[12,12],
    label:{color:C.txt,fontSize:10,fontFamily:"'Noto Sans SC',sans-serif",position:'right',lineHeight:14},
    leaves:{label:{color:'#9fb0c5',fontSize:9}},
    lineStyle:{color:C.line,width:1.4}, itemStyle:{color:C.amber,borderColor:'#fff',borderWidth:.5},
    expandAndCollapse:false, emphasis:{focus:'descendant'} }]};},

/* 17/18 bit growth */
_bit(data,color){ return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>v+'%'}),
  grid:{left:44,right:16,top:26,bottom:34},
  xAxis:AX({type:'category',data:BIT_YEARS,axisLabel:Object.assign(AX().axisLabel,{fontSize:9,rotate:30})}),
  yAxis:AX({type:'value',name:'%',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[{type:'bar',data,barWidth:'58%',itemStyle:{color:p=>BIT_YEARS[p.dataIndex].includes('E')?'#3a4658':color,opacity:.9},
    label:{show:true,position:'top',color:C.dim,fontFamily:F,fontSize:8},
    markLine:{data:[{type:'average',label:{color:C.amber,fontFamily:F,fontSize:9,formatter:'均值'}}],lineStyle:{color:C.amber,type:'dashed'}}}]};},
dramBit(){ return this._bit(DRAM_BIT,C.amber); },
nandBit(){ return this._bit(NAND_BIT,C.teal); },

/* 19 HBM 出货与价格 */
hbmShip(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:52,right:52,top:36,bottom:34},
  xAxis:AX({type:'category',data:HBM_YEARS}),
  yAxis:[AX({type:'value',name:'$B / 十亿Gb',nameTextStyle:{color:C.dim,fontFamily:F}}),
         AX({type:'value',name:'$/Gb',nameTextStyle:{color:C.dim,fontFamily:F},splitLine:{show:false}})],
  series:[
    {name:'HBM 收入 $B',type:'bar',data:HBM_REV,barWidth:'42%',itemStyle:{color:C.red,opacity:.9},
     label:{show:true,position:'top',color:C.dim,fontFamily:F,fontSize:8}},
    {name:'bit 出货(十亿Gb)',type:'line',data:HBM_BIT,lineStyle:{color:C.amber,width:2},itemStyle:{color:C.amber},symbolSize:6},
    {name:'ASP $/Gb',type:'line',yAxisIndex:1,data:HBM_ASP,lineStyle:{color:C.teal,width:2,type:'dashed'},itemStyle:{color:C.teal},symbolSize:6}
  ]};},

/* 20 三大原厂 Capex */
capex3(){
  const colors=[C.green,C.teal,C.red];
  return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>'$'+v+'B'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:48,right:16,top:36,bottom:34},
  xAxis:AX({type:'category',data:CAPEX3.years}),
  yAxis:AX({type:'value',name:'$B',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:Object.keys(CAPEX3).filter(k=>k!=='years').map((k,i)=>({name:k,type:'bar',data:CAPEX3[k],barGap:'8%',itemStyle:{color:colors[i],opacity:.9}}))};},

/* 21 库存天数 */
invDays(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis'}),
  grid:{left:44,right:16,top:26,bottom:40},
  xAxis:AX({type:'category',data:INV3_Q,axisLabel:Object.assign(AX().axisLabel,{fontSize:9,rotate:35})}),
  yAxis:AX({type:'value',name:'天',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[{type:'line',data:INV3,smooth:.3,symbolSize:6,lineStyle:{color:C.blue,width:2.5},itemStyle:{color:C.blue},areaStyle:{opacity:.1},
    markPoint:{symbol:'pin',symbolSize:38,label:{color:'#000',fontSize:8,fontFamily:F},data:[
      {coord:[6,141],value:'141d',itemStyle:{color:C.red}},{coord:[12,52],value:'52d',itemStyle:{color:C.green}}]},
    markLine:{data:[{yAxis:90,label:{color:C.amber,fontSize:9,fontFamily:F}}],lineStyle:{color:C.amber,type:'dashed'}}}]};},

/* 22 毛利率周期 */
gmCycle(){
  const colors=[C.green,C.teal,C.red];
  return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>v+'%'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:44,right:16,top:36,bottom:34},
  xAxis:AX({type:'category',data:GM_Y,boundaryGap:false}),
  yAxis:AX({type:'value',name:'%',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:Object.keys(GM).map((k,i)=>({name:k,type:'line',data:GM[k],smooth:.3,symbolSize:5,
    lineStyle:{color:colors[i],width:2},itemStyle:{color:colors[i]},
    markLine:i===0?{data:[{yAxis:0}],lineStyle:{color:C.line},label:{show:false}}:undefined}))};},

/* 23 服务器单机价值 */
serverValue(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis',valueFormatter:v=>v?'$'+v.toLocaleString():'—'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:64,right:16,top:36,bottom:34},
  xAxis:AX({type:'category',data:SV_Y,boundaryGap:false}),
  yAxis:AX({type:'log',name:'$/台 (log)',nameTextStyle:{color:C.dim,fontFamily:F}}),
  series:[
    {name:'传统服务器 DRAM',type:'line',data:SV_TRAD,symbolSize:6,lineStyle:{color:C.blue,width:2},itemStyle:{color:C.blue}},
    {name:'AI 服务器 DRAM+HBM',type:'line',data:SV_AI,symbolSize:7,lineStyle:{color:C.red,width:2.5},itemStyle:{color:C.red},connectNulls:false,
     label:{show:true,position:'top',color:C.red,fontFamily:F,fontSize:9,formatter:p=>p.value?'$'+(p.value/1000)+'k':''}}
  ]};},

/* 24 需求弹性 */
elasticity(){ return {
  tooltip:Object.assign({},TT,{trigger:'axis',axisPointer:{type:'shadow'},valueFormatter:v=>'+'+v+'%'}),
  legend:{textStyle:{color:C.dim,fontFamily:F},top:4},
  grid:{left:150,right:30,top:36,bottom:24},
  xAxis:AX({type:'value',name:'需求拉动 %',nameTextStyle:{color:C.dim,fontFamily:F}}),
  yAxis:AX({type:'category',data:ELASTICITY.map(e=>e.name),axisLabel:Object.assign(AX().axisLabel,{fontSize:9})}),
  series:[
    {name:'DRAM',type:'bar',data:ELASTICITY.map(e=>e.dram),itemStyle:{color:C.blue},barWidth:'26%'},
    {name:'HBM',type:'bar',data:ELASTICITY.map(e=>e.hbm),itemStyle:{color:C.red}},
    {name:'NAND',type:'bar',data:ELASTICITY.map(e=>e.nand),itemStyle:{color:C.teal}}
  ]};},

/* 25 HBM 份额 */
hbmShare(){ return {
  tooltip:Object.assign({},TT,{formatter:p=>`${p.name}: ${p.value}%`}),
  legend:{textStyle:{color:C.dim,fontFamily:F},bottom:0},
  series:[
    { name:'2025 出货份额', type:'pie', radius:['18%','38%'], center:['30%','52%'],
      label:{color:C.txt,fontSize:9,fontFamily:F}, itemStyle:{borderColor:C.bg,borderWidth:2},
      data:HBM_SHARE_2025.map((d,i)=>({...d,itemStyle:{color:[C.teal,C.red,C.green][i]}})) },
    { name:'2026E HBM4 份额', type:'pie', radius:['18%','38%'], center:['72%','52%'],
      label:{color:C.txt,fontSize:9,fontFamily:F}, itemStyle:{borderColor:C.bg,borderWidth:2},
      data:HBM4_SHARE_2026.map((d,i)=>({...d,itemStyle:{color:[C.teal,C.green,C.red,C.orange][i]}})) },
    { name:'t1',type:'pie',radius:0,center:['30%','10%'],label:{show:true,position:'center',formatter:'2025 出货',color:C.dim,fontSize:11,fontFamily:F},data:[{value:1,itemStyle:{color:'transparent'},label:{show:false}}],silent:true },
  ],
  graphic:[
    {type:'text',left:'24%',top:'8%',style:{text:'2025 出货份额',fill:C.dim,font:'11px '+F}},
    {type:'text',left:'66%',top:'8%',style:{text:'2026E HBM4 份额',fill:C.dim,font:'11px '+F}}
  ]};},

/* 26 周期时钟 */
cycleClock(){ return {
  tooltip:TT,
  series:[{ type:'pie', radius:['30%','62%'], roseType:'radius', center:['50%','54%'],
    label:{color:C.txt,fontSize:9.5,fontFamily:"'Noto Sans SC',sans-serif",lineHeight:13},
    labelLine:{lineStyle:{color:C.dim}},
    itemStyle:{borderColor:C.bg,borderWidth:3},
    data:CYCLE_CLOCK.map((d,i)=>({...d,itemStyle:{color:['#2ecc71','#e6a817','#e67e22','#e74c3c','#9b59b6','#4a90d9'][i]}})) }],
  graphic:[{type:'text',left:'center',top:'47%',style:{text:'供给\n决定\n周期',fill:C.amber,font:'bold 13px "Noto Sans SC"',align:'center'}}]};},

};

/* 渲染器：在指定 DOM 构建图表 */
function renderChart(id, dom, opts){
  const chart = echarts.init(dom, null, {renderer:'canvas'});
  chart.setOption(builders[id]());
  if(!opts||!opts.silent) chart.on('click', ()=>openDrill(id));
  return chart;
}
